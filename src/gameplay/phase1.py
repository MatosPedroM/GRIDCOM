"""
src/gameplay/phase1.py

Planning-phase data model — the hourly generation schedule the player builds
before a shift's real-time session, plus the forecasts it's checked against.

Pure data/logic, no pygame. The player plans a full 24-hour day (00:00-23:00)
independent of the real-time shift's own start hour and duration; the shift
window is a sub-window of that day, highlighted by the display layer via
in_shift_window(). The real-time handover dispatch is seeded from the
schedule's start_hour column (e.g. 06:00 for Shift 10), not column 0.

Scope: Shift 10 only (build_planning_model_for_shift10()). Other shifts are
not wired in yet — see STAGE_STATUS.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from data.designer_io import load_designer_grid_named
from data.fleet import GenerationUnit
from data.profiles import SHIFT_SPECS, get_substation_demand_specs
from gameplay.shifts.loader import load_shift_config
from simulation.constants import (
    TECH_MIN_FRAC_HYDRO,
    TECH_MIN_FRAC_HYDRO_ROR,
    TECH_MIN_FRAC_HYDRO_PUMP,
    TECH_MIN_FRAC_CCGT,
    TECH_MIN_FRAC_COAL,
    TECH_MIN_FRAC_NUCLEAR,
    PLANNING_LOAD_TOLERANCE_FRAC,
    MIN_UP_HOURS_NUCLEAR, MIN_DOWN_HOURS_NUCLEAR,
    MIN_UP_HOURS_COAL, MIN_DOWN_HOURS_COAL,
    MIN_UP_HOURS_CCGT, MIN_DOWN_HOURS_CCGT,
    MIN_UP_HOURS_HYDRO, MIN_DOWN_HOURS_HYDRO,
    MIN_UP_HOURS_HYDRO_ROR, MIN_DOWN_HOURS_HYDRO_ROR,
    MIN_UP_HOURS_HYDRO_PUMP, MIN_DOWN_HOURS_HYDRO_PUMP,
    PLANNING_HOUR0_FRAC_NUCLEAR, PLANNING_HOUR0_FRAC_COAL,
    PLANNING_HOUR0_FRAC_CCGT, PLANNING_HOUR0_FRAC_HYDRO,
    PLANNING_HOUR0_FRAC_HYDRO_ROR, PLANNING_HOUR0_FRAC_HYDRO_PUMP,
)
from simulation.demand import DemandModel
from simulation.designer_grid import DesignerGrid
from simulation.renewables import RenewablesModel
from simulation.units import AGC_UNIT_TYPES

# Non-dispatchable (forecast-driven, not player-scheduled) unit types.
_RENEWABLE_TYPES: frozenset[str] = frozenset({'WIND', 'SOLAR'})

# Technical-minimum fraction per unit type, for TECH MIN quick-fills and the
# regulation band. Mirrors simulation.units._TECH_MIN_FRAC.
_TECH_MIN_FRAC: dict[str, float] = {
    'HYDRO':      TECH_MIN_FRAC_HYDRO,
    'HYDRO_ROR':  TECH_MIN_FRAC_HYDRO_ROR,
    'HYDRO_PUMP': TECH_MIN_FRAC_HYDRO_PUMP,
    'CCGT':       TECH_MIN_FRAC_CCGT,
    'COAL':       TECH_MIN_FRAC_COAL,
    'NUCLEAR':    TECH_MIN_FRAC_NUCLEAR,
}

# Minimum up/down time per dispatchable unit type (hours). Planning-layer
# constraint enforced only by PlanningModel.auto_schedule() — the
# real-time simulation (simulation.units) has no cooldown of its own.
_MIN_UP_HOURS: dict[str, float] = {
    'NUCLEAR':    MIN_UP_HOURS_NUCLEAR,
    'COAL':       MIN_UP_HOURS_COAL,
    'CCGT':       MIN_UP_HOURS_CCGT,
    'HYDRO':      MIN_UP_HOURS_HYDRO,
    'HYDRO_ROR':  MIN_UP_HOURS_HYDRO_ROR,
    'HYDRO_PUMP': MIN_UP_HOURS_HYDRO_PUMP,
}
_MIN_DOWN_HOURS: dict[str, float] = {
    'NUCLEAR':    MIN_DOWN_HOURS_NUCLEAR,
    'COAL':       MIN_DOWN_HOURS_COAL,
    'CCGT':       MIN_DOWN_HOURS_CCGT,
    'HYDRO':      MIN_DOWN_HOURS_HYDRO,
    'HYDRO_ROR':  MIN_DOWN_HOURS_HYDRO_ROR,
    'HYDRO_PUMP': MIN_DOWN_HOURS_HYDRO_PUMP,
}

# Fraction of rated_mw the auto-scheduler seeds every non-maintenance
# dispatchable unit at, at hour 0 (fixed starting point — see auto_schedule()).
_HOUR0_FRAC: dict[str, float] = {
    'NUCLEAR':    PLANNING_HOUR0_FRAC_NUCLEAR,
    'COAL':       PLANNING_HOUR0_FRAC_COAL,
    'CCGT':       PLANNING_HOUR0_FRAC_CCGT,
    'HYDRO':      PLANNING_HOUR0_FRAC_HYDRO,
    'HYDRO_ROR':  PLANNING_HOUR0_FRAC_HYDRO_ROR,
    'HYDRO_PUMP': PLANNING_HOUR0_FRAC_HYDRO_PUMP,
}

# Auto-scheduler fill order (player-specified): wind/solar (non-scheduled,
# forecast-driven, not a commitment decision) -> hydro ROR -> nuclear ->
# coal -> CCGT -> hydro (conventional/cascade). Pumped storage (HYDRO_PUMP,
# fastest-ramping, no min-up/down) fills last as final fast reserve.
_AUTO_SCHEDULE_FILL_ORDER: tuple[str, ...] = (
    'HYDRO_ROR', 'NUCLEAR', 'COAL', 'CCGT', 'HYDRO', 'HYDRO_PUMP',
)

_PLANNING_HOURS: tuple[float, ...] = tuple(float(h) for h in range(24))


@dataclass
class PlanningModel:
    """
    Hourly generation schedule for a full 24-hour planning day, checked
    against the shift's load and wind/solar forecasts.

    schedule/online are keyed [unit_label][hour] over all 24 hours
    (0.0-23.0). Renewable units (WIND/SOLAR) are excluded from unit_specs/
    schedule/online — their contribution comes from wind_forecast instead.
    """
    unit_specs:     list[GenerationUnit]
    start_hour:     float
    duration_hours: float
    schedule:       dict[str, dict[float, float]] = field(default_factory=dict)
    online:         dict[str, dict[float, bool]]  = field(default_factory=dict)
    load_forecast:  dict[float, float] = field(default_factory=dict)
    wind_forecast:  dict[float, float] = field(default_factory=dict)
    maintenance_units: frozenset[str] = frozenset()

    hours: tuple[float, ...] = _PLANNING_HOURS

    # ─────── lookups ───────────────────────────────────────────────────────

    def unit(self, label: str) -> GenerationUnit:
        for u in self.unit_specs:
            if u.label == label:
                return u
        raise KeyError(f'Unit {label!r} not in planning model')

    def tech_min(self, unit: GenerationUnit) -> float:
        frac = _TECH_MIN_FRAC.get(unit.unit_type)
        return unit.min_mw if frac is None else unit.rated_mw * frac

    def tech_max(self, unit: GenerationUnit) -> float:
        return unit.rated_mw

    def in_shift_window(self, hour: float) -> bool:
        return self.start_hour <= hour < self.start_hour + self.duration_hours

    # ─────── editing ───────────────────────────────────────────────────────

    def set_cell(self, label: str, hour: float, mw: float) -> None:
        unit = self.unit(label)
        clamped = max(0.0, min(self.tech_max(unit), mw))
        self.schedule.setdefault(label, {})[hour] = clamped

    def fill_row(self, label: str, mw: float) -> None:
        unit = self.unit(label)
        clamped = max(0.0, min(self.tech_max(unit), mw))
        for h in self.hours:
            self.schedule.setdefault(label, {})[h] = clamped

    def fill_cell_min(self, label: str, hour: float) -> None:
        self.set_cell(label, hour, self.tech_min(self.unit(label)))

    def fill_cell_max(self, label: str, hour: float) -> None:
        self.set_cell(label, hour, self.tech_max(self.unit(label)))

    def fill_row_min(self, label: str) -> None:
        self.fill_row(label, self.tech_min(self.unit(label)))

    def fill_row_max(self, label: str) -> None:
        self.fill_row(label, self.tech_max(self.unit(label)))

    def toggle_online(self, label: str) -> None:
        currently_on = self.online.get(label, {}).get(self.hours[0], False)
        new_state = not currently_on
        self.online[label] = {h: new_state for h in self.hours}

    def is_online(self, label: str, hour: float) -> bool:
        return self.online.get(label, {}).get(hour, False)

    def reset(self, shift_number: int = 10) -> None:
        _default_init_schedule(self, shift_number)

    # ─────── aggregates ─────────────────────────────────────────────────────

    def stacked_by_tech(self, hour: float) -> dict[str, float]:
        stack: dict[str, float] = {}
        for unit in self.unit_specs:
            if not self.is_online(unit.label, hour):
                continue
            mw = self.schedule.get(unit.label, {}).get(hour, 0.0)
            stack[unit.unit_type] = stack.get(unit.unit_type, 0.0) + mw
        wind_mw = self.wind_forecast.get(hour, 0.0)
        if wind_mw > 0.0:
            stack['WIND'] = stack.get('WIND', 0.0) + wind_mw
        return stack

    def total_gen(self, hour: float) -> float:
        return sum(self.stacked_by_tech(hour).values())

    def difference(self, hour: float) -> float:
        return self.total_gen(hour) - self.load_forecast.get(hour, 0.0)

    def reg_band(self, hour: float) -> float:
        sum_pmax = 0.0
        sum_pmin = 0.0
        for unit in self.unit_specs:
            if unit.unit_type not in AGC_UNIT_TYPES:
                continue
            if not self.is_online(unit.label, hour):
                continue
            sum_pmax += self.tech_max(unit)
            sum_pmin += self.tech_min(unit)
        return sum_pmax - sum_pmin

    def out_of_tolerance_hours(self, frac: float = PLANNING_LOAD_TOLERANCE_FRAC) -> list[float]:
        """Hours where scheduled generation is outside load_forecast * (1 +/- frac)."""
        result = []
        for h in self.hours:
            load = self.load_forecast.get(h, 0.0)
            if abs(self.difference(h)) > frac * load:
                result.append(h)
        return result

    # ─────── auto-scheduler ──────────────────────────────────────────────────

    def auto_schedule(self) -> None:
        """
        Fill the entire 24h schedule automatically: a numpy-free heuristic
        day-ahead unit commitment, respecting each unit's ramp rate, minimum
        up/down time, and cold-start lead time.

        Optional player shortcut — never invoked automatically. Overwrites
        the whole schedule/online table; the player is free to hand-edit
        the result afterward exactly as with any other schedule.

        Hour 0 is a fixed starting point (not derived from commitment
        logic): every non-maintenance dispatchable unit is forced ONLINE
        at PLANNING_HOUR0_FRAC_<TYPE> * rated_mw. Hours 1-23 are then
        committed and filled hour by hour, walking technology groups in
        _AUTO_SCHEDULE_FILL_ORDER within each hour so faster/peaking
        technologies only cover what slower/baseload ones didn't.
        """
        units_by_type: dict[str, list[GenerationUnit]] = {}
        for unit in self.unit_specs:
            units_by_type.setdefault(unit.unit_type, []).append(unit)

        net_load: dict[float, float] = {
            h: self.load_forecast.get(h, 0.0) - self.wind_forecast.get(h, 0.0)
            for h in self.hours
        }

        # Hour 0: fixed seed, every non-maintenance unit forced online at
        # its technology's hour-0 output fraction (developer-approved
        # boundary rule — every unit is treated as already having been
        # running/stopped long enough before hour 0 to satisfy its own
        # min-up/min-down window from hour 0 onward).
        h0 = self.hours[0]
        last_change_hour: dict[str, float] = {}
        prev_mw: dict[str, float] = {}
        for unit in self.unit_specs:
            label = unit.label
            on_maintenance = label in self.maintenance_units
            online0 = not on_maintenance
            frac = _HOUR0_FRAC.get(unit.unit_type, 1.0)
            mw0 = 0.0 if on_maintenance else self.tech_max(unit) * frac
            self.online.setdefault(label, {})[h0] = online0
            self.schedule.setdefault(label, {})[h0] = mw0
            last_change_hour[label] = h0
            prev_mw[label] = mw0

        for h in self.hours[1:]:
            covered = 0.0
            for tech in _AUTO_SCHEDULE_FILL_ORDER:
                min_up = _MIN_UP_HOURS.get(tech, 0.0)
                min_down = _MIN_DOWN_HOURS.get(tech, 0.0)
                for unit in units_by_type.get(tech, []):
                    label = unit.label
                    shortfall = net_load[h] - covered
                    prev_online = self.online[label][h - 1.0]
                    hours_in_state = h - last_change_hour[label]

                    if min_up == 0.0 and min_down == 0.0:
                        # Free to toggle every hour (hydro variants, pumped storage).
                        want_online = shortfall > 0.0
                    elif prev_online:
                        # Baseload/CCGT: stay committed unless the shortfall
                        # has dropped enough to justify shedding this unit's
                        # own technical minimum, and only if min_up_time_h
                        # has already elapsed since it was last started.
                        want_online = (hours_in_state < min_up) or (shortfall > -self.tech_min(unit))
                    else:
                        # Offline: only restart once min_down_time_h has
                        # elapsed since it was last stopped.
                        want_online = (hours_in_state >= min_down) and (shortfall > 0.0)

                    if want_online != prev_online:
                        last_change_hour[label] = h

                    ramp_mw = (unit.ramp_pct_per_min / 100.0) * unit.rated_mw * 60.0
                    prev = prev_mw[label]
                    if want_online:
                        desired = min(self.tech_max(unit), self.tech_min(unit) + max(0.0, shortfall))
                    else:
                        desired = 0.0
                    delta = desired - prev
                    if abs(delta) > ramp_mw:
                        mw = prev + (ramp_mw if delta > 0 else -ramp_mw)
                    else:
                        mw = desired
                    mw = max(0.0, min(self.tech_max(unit), mw))

                    self.online.setdefault(label, {})[h] = want_online
                    self.schedule.setdefault(label, {})[h] = mw
                    prev_mw[label] = mw
                    covered += mw

    # ─────── output to the sim ─────────────────────────────────────────────

    def to_initial_schedule(self) -> dict[str, float]:
        """{unit_label: MW} at the shift's start_hour column — the real-time
        handover dispatch. Offline units are omitted (they start OFFLINE)."""
        result: dict[str, float] = {}
        for unit in self.unit_specs:
            if not self.is_online(unit.label, self.start_hour):
                continue
            result[unit.label] = self.schedule.get(unit.label, {}).get(self.start_hour, 0.0)
        return result

    def to_hourly_dispatch(self) -> dict[str, dict[float, float]]:
        """Full 24h schedule, zeroed for hours a unit is offline. Consumed by
        a future per-hour executor; currently inert once passed to the sim."""
        result: dict[str, dict[float, float]] = {}
        for unit in self.unit_specs:
            result[unit.label] = {
                h: (self.schedule.get(unit.label, {}).get(h, 0.0)
                    if self.is_online(unit.label, h) else 0.0)
                for h in self.hours
            }
        return result


# ─────────────────────────────────────────────────────────────────────────────
# FACTORY — Shift 10 only
# ─────────────────────────────────────────────────────────────────────────────

def build_planning_model_for_shift10() -> PlanningModel:
    """Build a PlanningModel for Shift 10 (the only wired-in shift so far)."""
    return build_planning_model(10)


def build_planning_model(shift_number: int) -> PlanningModel:
    cfg = load_shift_config(shift_number)
    spec = SHIFT_SPECS[shift_number]

    grid_source = cfg.get('grid_source')
    if grid_source:
        buses, lines, units = load_designer_grid_named(grid_source)
        grid = DesignerGrid(buses, lines, units)
    else:
        from simulation.grid import Grid
        grid = Grid(shift_number)

    dispatchable = [
        u for u in grid.get_active_units() if u.unit_type not in _RENEWABLE_TYPES
    ]

    substation_specs = get_substation_demand_specs(cfg['substation_load_mw'])
    demand_model = DemandModel(spec, substation_specs)
    load_forecast = demand_model.forecast_by_hour(0.0, 23.0, step=1.0)

    renewables = RenewablesModel(grid)
    renew_fc = renewables.forecast_by_hour(0.0, 23.0, step=1.0)
    wind_forecast: dict[float, float] = {h: 0.0 for h in _PLANNING_HOURS}
    for unit_label, by_hour in renew_fc.items():
        for h, mw in by_hour.items():
            wind_forecast[h] = wind_forecast.get(h, 0.0) + mw

    model = PlanningModel(
        unit_specs=dispatchable,
        start_hour=spec.start_hour,
        duration_hours=spec.duration_hours,
        load_forecast=load_forecast,
        wind_forecast=wind_forecast,
        maintenance_units=frozenset(cfg['maintenance_units']),
    )
    _default_init_schedule(model, shift_number, cfg=cfg)
    return model


def _default_init_schedule(model: PlanningModel, shift_number: int, cfg: dict | None = None) -> None:
    """Seed the schedule flat across all 24 hours from the shift's
    INITIAL_SCHEDULE / MAINTENANCE_UNITS. Units absent from INITIAL_SCHEDULE
    (or on maintenance) start OFFLINE."""
    if cfg is None:
        cfg = load_shift_config(shift_number)
    initial_schedule: dict[str, float] = cfg['initial_schedule']
    maintenance_units: set[str] = cfg['maintenance_units']

    for unit in model.unit_specs:
        label = unit.label
        mw = initial_schedule.get(label)
        is_on = (mw is not None) and (label not in maintenance_units)
        model.online[label] = {h: is_on for h in model.hours}
        flat_mw = mw if mw is not None else 0.0
        model.schedule[label] = {h: flat_mw for h in model.hours}
