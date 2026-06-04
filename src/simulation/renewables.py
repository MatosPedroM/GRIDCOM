"""
src/simulation/renewables.py

Renewable generation model (wind and solar) for the GRIDCOM simulation.

Wraps the deterministic forecast profiles from data.profiles with per-tick
Gaussian noise. Provides actual output in MW for each active renewable unit,
ready to pass to FleetModel.set_renewable_output().

Wind noise is larger (WIND_NOISE_STD_FRACTION = 3%) to model variability.
Solar noise is smaller (SOLAR_NOISE_STD_FRACTION = 1%) and only applied
when the forecast is non-zero (no noise at night).

In run_forecast_mode() the caller passes deterministic=True to suppress noise.

See SIMULATION_API.md — wind_forecast_mw, solar_forecast_mw for contract.
See DOMAIN_GLOSSARY.md — "Renewables Model" for definitions.
"""

import logging

import numpy as np

from simulation.constants import (
    WIND_NOISE_STD_FRACTION,
    SOLAR_NOISE_STD_FRACTION,
    DEBUG_SIMULATION,
)
from data.profiles import get_wind_mw, get_solar_mw
from data.fleet import GenerationUnit

# Unit types handled by this model.
_WIND_TYPE  = 'WIND'
_SOLAR_TYPE = 'SOLAR'


class RenewablesModel:
    """
    Wind and solar generation model with stochastic noise.

    Maintains the actual (noisy) output for every active WIND and SOLAR unit.
    Output is clamped to [0, rated_mw] after noise is applied.

    Deterministic forecast values are available separately via
    get_wind_forecast_mw() and get_solar_forecast_mw() for the Phase 1
    planning screen.

    Usage:
        rm = RenewablesModel(grid)
        # Each tick:
        outputs = rm.update(sim_hour, rng)
        # outputs = {unit_label: actual_mw}
        # Pass to fleet:
        for label, mw in outputs.items():
            fleet.set_renewable_output(label, mw)
    """

    def __init__(self, grid, rng: np.random.Generator | None = None) -> None:
        """
        Initialise renewables model from active grid fleet.

        Args:
            grid: Grid object for the active shift.
            rng:  Optional numpy random generator for reproducible noise.
        """
        self._rng = rng if rng is not None else np.random.default_rng()

        # Separate wind and solar unit specs for fast per-type processing.
        self._wind_units:  list[GenerationUnit] = []
        self._solar_units: list[GenerationUnit] = []

        for unit in grid.get_active_units():
            if unit.unit_type == _WIND_TYPE:
                self._wind_units.append(unit)
            elif unit.unit_type == _SOLAR_TYPE:
                self._solar_units.append(unit)

        # Current actual outputs.
        self._wind_outputs:  dict[str, float] = {u.label: 0.0 for u in self._wind_units}
        self._solar_outputs: dict[str, float] = {u.label: 0.0 for u in self._solar_units}

    # ─────── UPDATE ───────────────────────────────────────────────────────

    def update(
        self,
        sim_hour: float,
        deterministic: bool = False,
    ) -> dict[str, float]:
        """
        Compute actual renewable output for the current sim_hour.

        Args:
            sim_hour:      Current time of day in decimal hours.
            deterministic: If True, suppress noise (forecast mode).

        Returns:
            {unit_label: actual_mw} for all wind and solar units.
            Always non-negative and bounded by rated_mw.
        """
        outputs: dict[str, float] = {}

        for unit in self._wind_units:
            forecast = get_wind_mw(sim_hour, unit.rated_mw)
            actual = self._apply_noise(
                forecast, unit.rated_mw,
                WIND_NOISE_STD_FRACTION,
                deterministic,
                always_noisy=True,
            )
            self._wind_outputs[unit.label] = actual
            outputs[unit.label] = actual

        for unit in self._solar_units:
            forecast = get_solar_mw(sim_hour, unit.rated_mw)
            actual = self._apply_noise(
                forecast, unit.rated_mw,
                SOLAR_NOISE_STD_FRACTION,
                deterministic,
                always_noisy=False,  # no noise when forecast is zero (night)
            )
            self._solar_outputs[unit.label] = actual
            outputs[unit.label] = actual

        if DEBUG_SIMULATION and (self._wind_units or self._solar_units):
            total_wind  = sum(self._wind_outputs.values())
            total_solar = sum(self._solar_outputs.values())
            logging.getLogger('sim').debug(f'[RENEWABLES] hour={sim_hour:.2f} '
                                           f'wind={total_wind:.1f} MW  solar={total_solar:.1f} MW')

        return outputs

    # ─────── FORECASTS ────────────────────────────────────────────────────

    def get_wind_forecast_mw(self, unit_label: str, sim_hour: float) -> float:
        """Return deterministic wind forecast (no noise) for a unit at sim_hour."""
        for unit in self._wind_units:
            if unit.label == unit_label:
                return get_wind_mw(sim_hour, unit.rated_mw)
        return 0.0

    def get_solar_forecast_mw(self, unit_label: str, sim_hour: float) -> float:
        """Return deterministic solar forecast (no noise) for a unit at sim_hour."""
        for unit in self._solar_units:
            if unit.label == unit_label:
                return get_solar_mw(sim_hour, unit.rated_mw)
        return 0.0

    def forecast_by_hour(
        self,
        start_hour: float,
        end_hour: float,
        step: float = 0.5,
    ) -> dict[str, dict[float, float]]:
        """
        Return deterministic forecast for all renewable units over a time window.

        Returns:
            {unit_label: {sim_hour: forecast_mw}}
            Matches the wind_forecast_mw / solar_forecast_mw format in
            SimulationState.
        """
        result: dict[str, dict[float, float]] = {}

        for unit in self._wind_units + self._solar_units:
            is_wind = unit.unit_type == _WIND_TYPE
            result[unit.label] = {}
            hour = start_hour
            while hour <= end_hour + 1e-9:
                if is_wind:
                    mw = get_wind_mw(hour, unit.rated_mw)
                else:
                    mw = get_solar_mw(hour, unit.rated_mw)
                result[unit.label][hour] = mw
                hour += step

        return result

    def get_current_output(self, unit_label: str) -> float:
        """Return the most recent actual output for a unit. 0.0 if not found."""
        return self._wind_outputs.get(
            unit_label,
            self._solar_outputs.get(unit_label, 0.0)
        )

    # ─────── HELPERS ──────────────────────────────────────────────────────

    def _apply_noise(
        self,
        forecast_mw: float,
        rated_mw: float,
        std_fraction: float,
        deterministic: bool,
        always_noisy: bool,
    ) -> float:
        """
        Apply Gaussian noise to a forecast value and clamp to [0, rated_mw].

        Args:
            forecast_mw:   Deterministic forecast (MW).
            rated_mw:      Unit rated capacity (MW) — used as noise scale base.
            std_fraction:  Noise std dev as fraction of rated_mw.
            deterministic: If True, return forecast_mw unchanged.
            always_noisy:  If False, suppress noise when forecast_mw == 0.0
                           (used for solar at night).

        Returns:
            Actual output in MW, clamped to [0, rated_mw].
        """
        if deterministic:
            return float(np.clip(forecast_mw, 0.0, rated_mw))

        if not always_noisy and forecast_mw <= 0.0:
            return 0.0

        noise = float(self._rng.normal(0.0, std_fraction * rated_mw))
        # Clip noise to ±3σ.
        noise = float(np.clip(noise, -3.0 * std_fraction * rated_mw,
                                       3.0 * std_fraction * rated_mw))
        actual = forecast_mw + noise
        return float(np.clip(actual, 0.0, rated_mw))
