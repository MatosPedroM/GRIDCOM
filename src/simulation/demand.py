"""
src/simulation/demand.py

Demand model for the GRIDCOM simulation.

Wraps per-substation demand profiles from data.profiles. Total system demand
is the bottom-up sum of active substation demands. Supports fractional load
shed per substation.

See SIMULATION_API.md — total_load_mw, net_imbalance_mw for output contract.
See DOMAIN_GLOSSARY.md — "Demand Model" for definitions.
"""

import logging
import math

from simulation.constants import (
    LOSSES_FRACTION,
    DEBUG_SIMULATION,
    SUBSTATION_TYPE_PF,
)
from data.profiles import (
    get_demand_mw,
    get_profile_value,
    SubstationDemandSpec,
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
    System demand model with per-bus load shed.

    Demand follows the deterministic per-substation profile exactly.
    The forecast is always identical to the live demand (no noise).

    Total effective load passed to the power balance includes losses:
        total_load_eff = total_demand_actual + losses_mw

    Losses are computed as LOSSES_FRACTION × total_generation_mw and are
    updated each tick by the caller passing current generation.

    Attributes:
        total_demand_mw:  Current system demand (MW), excluding losses.
        losses_mw:        Estimated transmission losses (MW).
        total_load_mw:    total_demand_mw + losses_mw — used for power balance.

    Usage:
        dm = DemandModel(peak_demand_mw)
        # Each tick:
        dm.update(sim_hour, total_generation_mw)
        # Query per-bus injections for load flow:
        p_load = dm.p_load_injections()   # {bus_label: -load_mw}  (negative)
    """

    def __init__(self, peak_demand_mw: float, substation_specs: dict | None = None) -> None:
        """
        Initialise demand model for a shift.

        Args:
            peak_demand_mw:    Forecast peak system demand for this shift (MW) —
                               used as the fallback peak when a demand override
                               schedule has no explicit peak of its own.
            substation_specs:  Pre-built {bus_label: SubstationDemandSpec} mapping.
                               If None, an empty dict is used (no load buses active).
        """
        self._peak_demand_mw = peak_demand_mw

        self._substation_specs: dict[BusLabel, SubstationDemandSpec] = (
            substation_specs if substation_specs is not None else {}
        )

        # Per-bus shed fraction: 0.0 = no shedding, 1.0 = full shed.
        self._shed_fractions: dict[BusLabel, float] = {
            bus: 0.0 for bus in self._substation_specs
        }

        # Current demand per bus (MW), initialised to zero.
        self._bus_demand: dict[BusLabel, float] = {
            bus: 0.0 for bus in self._substation_specs
        }

        self._total_demand_mw: float = 0.0
        self._losses_mw: float = 0.0

        self._demand_override: dict[float, float] | None = None

        # Reactive-load tangent per bus, cached from each bus's substation type:
        # Q = P * tan(acos(PF)). Computed once here rather than per-tick.
        self._bus_q_tan: dict[BusLabel, float] = {
            bus: math.tan(math.acos(SUBSTATION_TYPE_PF.get(spec.substation_type, SUBSTATION_TYPE_PF['MIXED'])))
            for bus, spec in self._substation_specs.items()
        }

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
    ) -> None:
        """
        Advance demand state to the current sim_hour.

        Args:
            sim_hour:            Current time of day in decimal hours.
            total_generation_mw: Current total online generation (MW).
                                 Used to estimate losses.
        """
        total_unshed = 0.0

        if self._demand_override:
            # Override mode: total MW is prescribed; distribute across substations
            # proportional to their profile weights at this hour.
            override_total = _interpolate_override(
                self._demand_override, sim_hour, self._peak_demand_mw)
            weights = {
                bus: get_profile_value(spec.profile, sim_hour) * spec.peak_mw
                for bus, spec in self._substation_specs.items()
            }
            weight_sum = sum(weights.values()) or 1.0
            for bus, w in weights.items():
                shed_factor = max(0.0, 1.0 - self._shed_fractions.get(bus, 0.0))
                self._bus_demand[bus] = override_total * (w / weight_sum) * shed_factor
                total_unshed += self._bus_demand[bus]
        else:
            # Bottom-up: each substation follows its own profile.
            for bus, spec in self._substation_specs.items():
                profile_mw = get_profile_value(spec.profile, sim_hour) * spec.peak_mw
                shed_factor = max(0.0, 1.0 - self._shed_fractions.get(bus, 0.0))
                self._bus_demand[bus] = profile_mw * shed_factor
                total_unshed += self._bus_demand[bus]

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
                self._demand_override, sim_hour, self._peak_demand_mw)
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

    def q_load_injections(self) -> dict[BusLabel, float]:
        """
        Return {bus_label: -q_mvar} for all load buses.

        Q = P * tan(acos(PF)), where PF is the bus's substation-type power
        factor (cached in _bus_q_tan). Negative because load buses absorb
        reactive power, mirroring p_load_injections()'s sign convention.
        Callers are responsible for blackout-zone filtering, exactly as for
        p_load_injections() (see simulation.py::_build_p_injections).
        """
        return {
            bus: -mw * self._bus_q_tan.get(bus, 0.0)
            for bus, mw in self._bus_demand.items()
        }

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
