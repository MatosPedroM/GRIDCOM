"""
src/simulation/demand.py

Demand model for the GRIDCOM simulation.

Wraps per-substation demand profiles from data.profiles with per-tick Gaussian
noise. Total system demand is the bottom-up sum of active substation demands.
Supports fractional load shed per substation.

In run_forecast_mode() the caller passes deterministic=True to suppress noise.

See SIMULATION_API.md — total_load_mw, net_imbalance_mw for output contract.
See DOMAIN_GLOSSARY.md — "Demand Model" for definitions.
"""

import logging

import numpy as np

from simulation.constants import (
    DEMAND_NOISE_STD_FRACTION,
    DEMAND_NOISE_UPDATE_S,
    LOSSES_FRACTION,
    DEBUG_SIMULATION,
)
from data.profiles import (
    get_demand_mw,
    get_profile_value,
    get_substation_demand_specs,
    SubstationDemandSpec,
    ShiftSpec,
)

# Type alias
BusLabel = str


def _interpolate_override(
    schedule: dict[float, float],
    sim_hour: float,
    fallback_peak_mw: float,
) -> float:
    hours = sorted(schedule)
    if not hours:
        return get_demand_mw(sim_hour, fallback_peak_mw)
    if sim_hour <= hours[0]:
        return schedule[hours[0]]
    if sim_hour >= hours[-1]:
        return schedule[hours[-1]]
    for i in range(len(hours) - 1):
        h0, h1 = hours[i], hours[i + 1]
        if h0 <= sim_hour <= h1:
            t = (sim_hour - h0) / (h1 - h0)
            return schedule[h0] * (1.0 - t) + schedule[h1] * t
    return get_demand_mw(sim_hour, fallback_peak_mw)


class DemandModel:
    """
    System demand model with stochastic noise and per-bus load shed.

    Maintains the actual (noisy) demand at each load substation.
    The deterministic forecast is available separately via get_forecast_mw().

    Total effective load passed to the power balance includes losses:
        total_load_eff = total_demand_actual + losses_mw

    Losses are computed as LOSSES_FRACTION × total_generation_mw and are
    updated each tick by the caller passing current generation.

    Attributes:
        total_demand_mw:  Current actual system demand (MW), excluding losses.
        losses_mw:        Estimated transmission losses (MW).
        total_load_mw:    total_demand_mw + losses_mw — used for power balance.

    Usage:
        dm = DemandModel(spec)
        # Each tick:
        dm.update(sim_hour, total_generation_mw, rng)
        # Query per-bus injections for load flow:
        p_load = dm.p_load_injections()   # {bus_label: -load_mw}  (negative)
    """

    def __init__(self, spec: ShiftSpec, rng: np.random.Generator | None = None) -> None:
        """
        Initialise demand model for a shift.

        Args:
            spec: ShiftSpec for this shift — provides peak_demand_mw.
            rng:  Optional numpy random generator for reproducible noise.
                  If None, a fresh default_rng() is created.
        """
        self._spec = spec
        self._rng = rng if rng is not None else np.random.default_rng()

        self._substation_specs: dict[BusLabel, SubstationDemandSpec] = (
            get_substation_demand_specs(spec.shift_number)
        )

        # Per-bus shed fraction: 0.0 = no shedding, 1.0 = full shed.
        self._shed_fractions: dict[BusLabel, float] = {
            bus: 0.0 for bus in self._substation_specs
        }

        # Current actual demand per bus (MW), initialised to zero.
        self._bus_demand: dict[BusLabel, float] = {
            bus: 0.0 for bus in self._substation_specs
        }

        self._total_demand_mw: float = 0.0
        self._losses_mw: float = 0.0

        # Noise hold: re-sample only every DEMAND_NOISE_UPDATE_S simulated seconds.
        self._noise_fraction: float = 0.0
        self._noise_timer_s:  float = DEMAND_NOISE_UPDATE_S  # fire immediately on first tick

        self._demand_override: dict[float, float] | None = None

    # ─────── PROPERTIES ───────────────────────────────────────────────────

    @property
    def total_demand_mw(self) -> float:
        """Current actual system demand (MW), excluding losses."""
        return self._total_demand_mw

    @property
    def losses_mw(self) -> float:
        """Estimated transmission losses (MW)."""
        return self._losses_mw

    @property
    def total_load_mw(self) -> float:
        """Effective load for power balance: demand + losses."""
        return self._total_demand_mw + self._losses_mw

    # ─────── UPDATE ───────────────────────────────────────────────────────

    def update(
        self,
        sim_hour: float,
        total_generation_mw: float,
        deterministic: bool = False,
        dt_sim_seconds: float = 0.0,
    ) -> None:
        """
        Advance demand state to the current sim_hour.

        Args:
            sim_hour:            Current time of day in decimal hours.
            total_generation_mw: Current total online generation (MW).
                                 Used to estimate losses.
            deterministic:       If True, suppress noise (forecast mode).
            dt_sim_seconds:      Elapsed sim time this tick (seconds). Used to
                                 pace noise re-sampling.
        """
        if deterministic:
            noise_fraction = 0.0
        else:
            self._noise_timer_s += dt_sim_seconds
            if self._noise_timer_s >= DEMAND_NOISE_UPDATE_S:
                self._noise_timer_s = 0.0
                raw = float(self._rng.normal(0.0, DEMAND_NOISE_STD_FRACTION))
                self._noise_fraction = float(np.clip(
                    raw,
                    -3.0 * DEMAND_NOISE_STD_FRACTION,
                     3.0 * DEMAND_NOISE_STD_FRACTION,
                ))
            noise_fraction = self._noise_fraction

        # Clip noise to ±3σ to prevent runaway values.
        noise_fraction = float(np.clip(
            noise_fraction,
            -3.0 * DEMAND_NOISE_STD_FRACTION,
             3.0 * DEMAND_NOISE_STD_FRACTION,
        ))

        total_unshed = 0.0

        if self._demand_override:
            # Override mode: total MW is prescribed; distribute across substations
            # proportional to their profile weights at this hour, then apply noise.
            override_total = _interpolate_override(
                self._demand_override, sim_hour, self._spec.peak_demand_mw)
            noisy_total = max(0.0, override_total * (1.0 + noise_fraction))
            weights = {
                bus: get_profile_value(spec.profile, sim_hour) * spec.peak_mw
                for bus, spec in self._substation_specs.items()
            }
            weight_sum = sum(weights.values()) or 1.0
            for bus, w in weights.items():
                raw = noisy_total * (w / weight_sum)
                shed_factor = max(0.0, 1.0 - self._shed_fractions.get(bus, 0.0))
                self._bus_demand[bus] = raw * shed_factor
                total_unshed += self._bus_demand[bus]
        else:
            # Bottom-up: each substation has its own profile; noise applied uniformly.
            for bus, spec in self._substation_specs.items():
                forecast_bus = get_profile_value(spec.profile, sim_hour) * spec.peak_mw
                noisy = max(0.0, forecast_bus * (1.0 + noise_fraction))
                shed_factor = max(0.0, 1.0 - self._shed_fractions.get(bus, 0.0))
                effective = noisy * shed_factor
                self._bus_demand[bus] = effective
                total_unshed += effective

        self._total_demand_mw = total_unshed
        self._losses_mw = total_generation_mw * LOSSES_FRACTION

        if DEBUG_SIMULATION:
            bus_str = '  '.join(f'{b}={self._bus_demand[b]:.0f}' for b in self._bus_demand)
            logging.getLogger('sim').debug(f'[DEMAND] hour={sim_hour:.2f} total={total_unshed:.1f} '
                                           f'losses={self._losses_mw:.1f} MW  [{bus_str}]')

    # ─────── LOAD SHED ────────────────────────────────────────────────────

    def shed_load(self, bus_label: BusLabel, fraction: float) -> bool:
        """
        Shed a fraction of load at a specific load substation.

        Args:
            bus_label: Load substation label (e.g. 'LD01').
            fraction:  Fraction to shed. Clamped to [0.0, 1.0].
                       Adds to any existing shed at that bus.

        Returns:
            True if bus_label is a known load bus.
            False otherwise.
        """
        if bus_label not in self._shed_fractions:
            return False
        new_shed = min(1.0, self._shed_fractions[bus_label] + float(fraction))
        self._shed_fractions[bus_label] = new_shed
        if DEBUG_SIMULATION:
            logging.getLogger('sim').debug(f'[DEMAND] Load shed at {bus_label}: '
                                           f'{new_shed * 100:.0f}% total')
        return True

    def clear_shed(self, bus_label: BusLabel) -> bool:
        """Remove all load shedding at a bus. Returns True if bus found."""
        if bus_label not in self._shed_fractions:
            return False
        self._shed_fractions[bus_label] = 0.0
        return True

    def get_shed_fraction(self, bus_label: BusLabel) -> float:
        """Return current shed fraction at a bus (0.0–1.0)."""
        return self._shed_fractions.get(bus_label, 0.0)

    def set_demand_override(
        self,
        schedule: dict[float, float] | None,
        sim_hour: float | None = None,
    ) -> None:
        """
        Set a sparse hour→MW demand schedule that replaces the standard profile.
        Values between provided hours are linearly interpolated. Pass None or
        an empty dict to revert to the standard DEMAND_PROFILE_NORMALISED curve.

        If sim_hour is provided the current demand is seeded immediately from
        the new schedule so that the displayed value is correct before the first
        update() call.
        """
        self._demand_override = dict(schedule) if schedule else None
        if self._demand_override and sim_hour is not None:
            seeded = _interpolate_override(
                self._demand_override, sim_hour, self._spec.peak_demand_mw)
            self._total_demand_mw = seeded

    # ─────── QUERIES ──────────────────────────────────────────────────────

    def get_forecast_mw(self, sim_hour: float) -> float:
        """Return deterministic forecast demand (no noise) at sim_hour — sum of all active substations."""
        return sum(
            get_profile_value(spec.profile, sim_hour) * spec.peak_mw
            for spec in self._substation_specs.values()
        )

    def get_bus_demand_mw(self, bus_label: BusLabel) -> float:
        """Return current actual demand (after shed) at a load bus."""
        return self._bus_demand.get(bus_label, 0.0)

    def p_load_injections(self) -> dict[BusLabel, float]:
        """
        Return {bus_label: -demand_mw} for all load buses.

        Negative because load buses consume power (negative injection
        in the load flow convention).
        """
        return {bus: -mw for bus, mw in self._bus_demand.items()}

    def forecast_by_hour(
        self,
        start_hour: float,
        end_hour: float,
        step: float = 0.5,
    ) -> dict[float, float]:
        """
        Return deterministic demand forecast for a time window.

        Args:
            start_hour: Start of window (decimal hours).
            end_hour:   End of window (decimal hours).
            step:       Time step between samples (decimal hours).

        Returns:
            {sim_hour: forecast_mw} for hours in [start_hour, end_hour].
        """
        result: dict[float, float] = {}
        hour = start_hour
        while hour <= end_hour + 1e-9:
            result[hour] = self.get_forecast_mw(hour)
            hour += step
        return result
