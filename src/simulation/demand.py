"""
src/simulation/demand.py

Demand model for the GRIDCOM simulation.

Wraps the deterministic forecast from data.profiles with per-tick Gaussian
noise. Distributes total system demand across load substations according to
LOAD_DISTRIBUTION. Supports fractional load shed per substation.

In run_forecast_mode() the caller passes deterministic=True to suppress noise.

See SIMULATION_API.md — total_load_mw, net_imbalance_mw for output contract.
See DOMAIN_GLOSSARY.md — "Demand Model" for definitions.
"""

import numpy as np

from simulation.constants import (
    DEMAND_NOISE_STD_FRACTION,
    LOSSES_FRACTION,
    DEBUG_SIMULATION,
)
from data.profiles import (
    get_demand_mw,
    LOAD_DISTRIBUTION,
    ShiftSpec,
)

# Type alias
BusLabel = str


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

        # Per-bus shed fraction: 0.0 = no shedding, 1.0 = full shed.
        self._shed_fractions: dict[BusLabel, float] = {
            bus: 0.0 for bus in LOAD_DISTRIBUTION
        }

        # Current actual demand per bus (MW), initialised to zero.
        self._bus_demand: dict[BusLabel, float] = {
            bus: 0.0 for bus in LOAD_DISTRIBUTION
        }

        self._total_demand_mw: float = 0.0
        self._losses_mw: float = 0.0

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
    ) -> None:
        """
        Advance demand state to the current sim_hour.

        Args:
            sim_hour:            Current time of day in decimal hours.
            total_generation_mw: Current total online generation (MW).
                                 Used to estimate losses.
            deterministic:       If True, suppress noise (forecast mode).
        """
        forecast = get_demand_mw(sim_hour, self._spec.peak_demand_mw)

        if deterministic:
            noise_fraction = 0.0
        else:
            noise_fraction = float(
                self._rng.normal(0.0, DEMAND_NOISE_STD_FRACTION)
            )

        # Clip noise to ±3σ to prevent runaway values.
        noise_fraction = float(np.clip(
            noise_fraction,
            -3.0 * DEMAND_NOISE_STD_FRACTION,
             3.0 * DEMAND_NOISE_STD_FRACTION,
        ))

        actual_total = forecast * (1.0 + noise_fraction)
        actual_total = max(0.0, actual_total)

        # Distribute across buses, apply shed fractions.
        total_unshed = 0.0
        for bus, fraction in LOAD_DISTRIBUTION.items():
            raw = actual_total * fraction
            shed_factor = max(0.0, 1.0 - self._shed_fractions.get(bus, 0.0))
            effective = raw * shed_factor
            self._bus_demand[bus] = effective
            total_unshed += effective

        self._total_demand_mw = total_unshed
        self._losses_mw = total_generation_mw * LOSSES_FRACTION

        if DEBUG_SIMULATION:
            print(f'[DEMAND] hour={sim_hour:.2f} forecast={forecast:.1f} '
                  f'actual={actual_total:.1f} after_shed={total_unshed:.1f} '
                  f'losses={self._losses_mw:.1f} MW')

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
            print(f'[DEMAND] Load shed at {bus_label}: '
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

    # ─────── QUERIES ──────────────────────────────────────────────────────

    def get_forecast_mw(self, sim_hour: float) -> float:
        """Return deterministic forecast demand (no noise) at sim_hour."""
        return get_demand_mw(sim_hour, self._spec.peak_demand_mw)

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
