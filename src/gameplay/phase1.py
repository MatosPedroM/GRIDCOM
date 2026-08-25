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

import json
from dataclasses import dataclass, field
from pathlib import Path

from data.designer_io import load_designer_grid_named
from data.fleet import GenerationUnit
from data.profiles import get_substation_demand_specs
from gameplay.shifts.loader import load_shift_config
from config.constants import (
    TECH_MIN_FRAC_HYDRO,
    TECH_MIN_FRAC_HYDRO_ROR,
    TECH_MIN_FRAC_HYDRO_PUMP,
    TECH_MIN_FRAC_CCGT,
    TECH_MIN_FRAC_COAL,
    TECH_MIN_FRAC_NUCLEAR,
    MIN_UP_HOURS_NUCLEAR, MIN_DOWN_HOURS_NUCLEAR,
    MIN_UP_HOURS_COAL, MIN_DOWN_HOURS_COAL,
    MIN_UP_HOURS_CCGT, MIN_DOWN_HOURS_CCGT,
    MIN_UP_HOURS_HYDRO, MIN_DOWN_HOURS_HYDRO,
    MIN_UP_HOURS_HYDRO_ROR, MIN_DOWN_HOURS_HYDRO_ROR,
    MIN_UP_HOURS_HYDRO_PUMP, MIN_DOWN_HOURS_HYDRO_PUMP,
    PLANNING_PREV_DAY_FRAC_NUCLEAR, PLANNING_PREV_DAY_FRAC_COAL,
    PLANNING_PREV_DAY_FRAC_CCGT, PLANNING_PREV_DAY_FRAC_HYDRO,
    PLANNING_PREV_DAY_FRAC_HYDRO_ROR, PLANNING_PREV_DAY_FRAC_HYDRO_PUMP,
    PLANNING_AGC_RESERVE_MW,
    PLANNING_STEP_HOURS,
    STARTUP_COST_EUR_BY_TYPE, VARIABLE_COST_EUR_PER_MWH_BY_TYPE,
    AGC_AVAILABILITY_COST_EUR_PER_HOUR, PLANNING_INITIAL_BUDGET_EUR,
    DIFFICULTY_COST_MULT,
)
from simulation.demand import DemandModel
from simulation.designer_grid import DesignerGrid
from simulation.renewables import RenewablesModel
from config.constants import AGC_ELIGIBLE_TYPES as _AGC_ELIGIBLE_TYPES_DEFAULT

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

# Fraction of rated_mw every non-maintenance dispatchable unit is assumed
# to have been producing during the previous day's final hour (H24 of
# D-1) — a calculation-only boundary state auto_schedule() uses to
# ramp-limit into and decide min-up/min-down for 00:00, the planning
# day's own first hour. Never displayed or written to the schedule.
_PREV_DAY_H24_FRAC: dict[str, float] = {
    'NUCLEAR':    PLANNING_PREV_DAY_FRAC_NUCLEAR,
    'COAL':       PLANNING_PREV_DAY_FRAC_COAL,
    'CCGT':       PLANNING_PREV_DAY_FRAC_CCGT,
    'HYDRO':      PLANNING_PREV_DAY_FRAC_HYDRO,
    'HYDRO_ROR':  PLANNING_PREV_DAY_FRAC_HYDRO_ROR,
    'HYDRO_PUMP': PLANNING_PREV_DAY_FRAC_HYDRO_PUMP,
}

# Auto-scheduler fill order (player-specified): wind/solar (non-scheduled,
# forecast-driven, not a commitment decision) -> hydro ROR -> nuclear ->
# coal -> CCGT -> hydro (conventional/cascade). Pumped storage (HYDRO_PUMP,
# fastest-ramping, no min-up/down) fills last as final fast reserve.
_AUTO_SCHEDULE_FILL_ORDER: tuple[str, ...] = (
    'HYDRO_ROR', 'NUCLEAR', 'COAL', 'CCGT', 'HYDRO', 'HYDRO_PUMP',
)

_PLANNING_HOURS: tuple[float, ...] = tuple(
    round(h * PLANNING_STEP_HOURS, 10) for h in range(int(24 / PLANNING_STEP_HOURS))
)


@dataclass
class PlanningModel:
    """
    Hourly generation schedule for a full 24-hour planning day, checked
    against the shift's load and renewable forecasts.

    schedule/online are keyed [unit_label][hour] over all 24 hours
    (0.0-23.0). Renewable units (WIND/SOLAR) are excluded from unit_specs/
    schedule/online — they are not player-scheduled at all (no ON/OFF,
    no MW to edit). Their forecasted contribution lives in
    renewable_specs/renewable_forecast instead, and is shown in the
    planning screen as locked, read-only rows that still feed into
    total_gen()/stacked_by_tech().
    """
    unit_specs:     list[GenerationUnit]
    start_hour:     float
    duration_hours: float
    schedule:       dict[str, dict[float, float]] = field(default_factory=dict)
    online:         dict[str, dict[float, bool]]  = field(default_factory=dict)
    load_forecast:  dict[float, float] = field(default_factory=dict)
    renewable_specs:     list[GenerationUnit] = field(default_factory=list)
    renewable_forecast:  dict[str, dict[float, float]] = field(default_factory=dict)
    maintenance_units: frozenset[str] = frozenset()
    # Fixed campaign-wide, same value as constants.py AGC_ELIGIBLE_TYPES
    # (CCGT + HYDRO) — not shift-configurable. Kept as a field (rather than
    # importing the constant directly at every call site) purely so
    # is_agc_eligible()/reg_band()/hourly_cost() have one place to read it.
    agc_eligible_types: frozenset[str] = _AGC_ELIGIBLE_TYPES_DEFAULT

    # Per-unit AGC enrollment for the whole plan (not per-hour — a day-long
    # commitment decision, unlike schedule/online). Only meaningful for units
    # whose unit_type is in agc_eligible_types; seeded True by default for
    # those units (see _default_init_schedule) so the player opts OUT rather
    # than starting from nothing enrolled.
    agc_enrolled:   dict[str, bool] = field(default_factory=dict)

    budget_eur: float = PLANNING_INITIAL_BUDGET_EUR

    # trainee/standard/dispatcher — scales per-technology costs via
    # DIFFICULTY_COST_MULT (constants.py). Does not affect budget_eur itself.
    difficulty: str = 'standard'

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

    def fill_cell_zero(self, label: str, hour: float) -> None:
        self.set_cell(label, hour, 0.0)

    def fill_row_min(self, label: str) -> None:
        self.fill_row(label, self.tech_min(self.unit(label)))

    def fill_row_max(self, label: str) -> None:
        self.fill_row(label, self.tech_max(self.unit(label)))

    def fill_row_zero(self, label: str) -> None:
        self.fill_row(label, 0.0)

    def toggle_online(self, label: str) -> None:
        currently_on = self.online.get(label, {}).get(self.hours[0], False)
        new_state = not currently_on
        self.online[label] = {h: new_state for h in self.hours}

    def is_online(self, label: str, hour: float) -> bool:
        return self.online.get(label, {}).get(hour, False)

    def is_agc_eligible(self, label: str) -> bool:
        return self.unit(label).unit_type in self.agc_eligible_types

    def is_agc_enrolled(self, label: str) -> bool:
        return self.agc_enrolled.get(label, False)

    def toggle_agc_enrolled(self, label: str) -> None:
        """Flip a unit's AGC enrollment for the whole plan. No-op for units
        whose unit_type isn't in agc_eligible_types this shift."""
        if not self.is_agc_eligible(label):
            return
        self.agc_enrolled[label] = not self.agc_enrolled.get(label, False)

    def reset(self) -> None:
        _default_init_schedule(self)

    # ─────── aggregates ─────────────────────────────────────────────────────

    def stacked_by_tech(self, hour: float) -> dict[str, float]:
        """Generation by technology this column, including a decommitting
        unit's shutdown-ramp residual (self.schedule holds that ramped-down
        MW even once self.online flips False — see auto_schedule()'s
        offline-branch ramp, which moves current output toward 0 rather
        than snapping it there) — physically that unit is still generating
        that MW, so it counts toward total_gen()/difference() the same as
        any online unit. At the previous (hourly) step length this residual
        always reached exactly 0 within one column, so the distinction was
        invisible; at a finer step it doesn't always finish ramping down
        that fast, so counting it is required for total_gen() to match
        auto_schedule()'s own internal covered-MW accounting."""
        stack: dict[str, float] = {}
        for unit in self.unit_specs:
            mw = self.schedule.get(unit.label, {}).get(hour, 0.0)
            if mw == 0.0:
                continue
            stack[unit.unit_type] = stack.get(unit.unit_type, 0.0) + mw
        for unit in self.renewable_specs:
            mw = self.renewable_forecast.get(unit.label, {}).get(hour, 0.0)
            stack[unit.unit_type] = stack.get(unit.unit_type, 0.0) + mw
        return stack

    def total_gen(self, hour: float) -> float:
        return sum(self.stacked_by_tech(hour).values())

    def renewable_total(self, hour: float, unit_type: str | None = None) -> float:
        """Sum of forecasted renewable MW at hour, optionally filtered to
        one unit_type ('WIND' or 'SOLAR'). Informational only — this MW
        is not player-scheduled but is already counted in total_gen()."""
        return sum(
            self.renewable_forecast.get(unit.label, {}).get(hour, 0.0)
            for unit in self.renewable_specs
            if unit_type is None or unit.unit_type == unit_type
        )

    def difference(self, hour: float) -> float:
        return self.total_gen(hour) - self.load_forecast.get(hour, 0.0)

    def reg_band(self, hour: float) -> float:
        sum_pmax = 0.0
        sum_pmin = 0.0
        for unit in self.unit_specs:
            if unit.unit_type not in self.agc_eligible_types:
                continue
            if not self.is_agc_enrolled(unit.label):
                continue
            if not self.is_online(unit.label, hour):
                continue
            sum_pmax += self.tech_max(unit)
            sum_pmin += self.tech_min(unit)
        return sum_pmax - sum_pmin

    def reg_band_up(self, hour: float) -> float:
        """Pooled up-regulation headroom (sum of tech_max - scheduled_mw)
        across online, AGC-enrolled CCGT/HYDRO units this hour. Always
        reg_band_up(h) + reg_band_down(h) == reg_band(h)."""
        total = 0.0
        for unit in self.unit_specs:
            if unit.unit_type not in self.agc_eligible_types:
                continue
            if not self.is_agc_enrolled(unit.label):
                continue
            if not self.is_online(unit.label, hour):
                continue
            mw = self.schedule.get(unit.label, {}).get(hour, 0.0)
            total += self.tech_max(unit) - mw
        return total

    def reg_band_down(self, hour: float) -> float:
        """Pooled down-regulation headroom (sum of scheduled_mw - tech_min)
        across online, AGC-enrolled CCGT/HYDRO units this hour. Always
        reg_band_up(h) + reg_band_down(h) == reg_band(h)."""
        total = 0.0
        for unit in self.unit_specs:
            if unit.unit_type not in self.agc_eligible_types:
                continue
            if not self.is_agc_enrolled(unit.label):
                continue
            if not self.is_online(unit.label, hour):
                continue
            mw = self.schedule.get(unit.label, {}).get(hour, 0.0)
            total += mw - self.tech_min(unit)
        return total

    # ─────── economics ────────────────────────────────────────────────────

    def hourly_cost(self, hour: float) -> float:
        """Variable (fuel) cost + AGC-availability surcharge + startup cost
        for this hour, summed across all online dispatchable units. Costs
        are looked up per unit_type (STARTUP_COST_EUR_BY_TYPE /
        VARIABLE_COST_EUR_PER_MWH_BY_TYPE / AGC_AVAILABILITY_COST_EUR_PER_HOUR,
        constants.py) and scaled uniformly by DIFFICULTY_COST_MULT[difficulty]
        — cost is a per-technology property, not a per-fleet-unit one. The
        fuel and AGC-surcharge terms are rate-based (EUR/MWh, EUR/hour) so
        both are also scaled by PLANNING_STEP_HOURS to reflect the fraction
        of an hour each schedule column actually represents — a no-op at
        the default 1.0 (hourly) step, but keeps total_cost() correct if
        the step is ever tuned finer again.

        Startup cost is a one-time per-event charge, not a rate, so it is
        NOT scaled by PLANNING_STEP_HOURS — it fires once on a rising edge
        (offline -> online) between the previous hour and this one; hour 0
        is never treated as a startup edge (the fleet is assumed already in
        whatever state it's in, same boundary assumption auto_schedule()
        makes)."""
        cost_mult = DIFFICULTY_COST_MULT.get(self.difficulty, 1.0)
        total = 0.0
        h0 = self.hours[0]
        for unit in self.unit_specs:
            label = unit.label
            if not self.is_online(label, hour):
                continue
            mw = self.schedule.get(label, {}).get(hour, 0.0)
            var_cost = VARIABLE_COST_EUR_PER_MWH_BY_TYPE.get(unit.unit_type, 0.0)
            total += mw * var_cost * cost_mult * PLANNING_STEP_HOURS

            if unit.unit_type in self.agc_eligible_types and self.is_agc_enrolled(label):
                total += AGC_AVAILABILITY_COST_EUR_PER_HOUR * cost_mult * PLANNING_STEP_HOURS

            if hour != h0 and not self.is_online(label, hour - PLANNING_STEP_HOURS):
                total += STARTUP_COST_EUR_BY_TYPE.get(unit.unit_type, 0.0) * cost_mult
        return total

    def total_cost(self) -> float:
        return sum(self.hourly_cost(h) for h in self.hours)

    def remaining_budget(self) -> float:
        return self.budget_eur - self.total_cost()

    # ─────── auto-scheduler ──────────────────────────────────────────────────

    def auto_schedule(self) -> None:
        """
        Fill the entire 24h schedule automatically: a numpy-free heuristic
        day-ahead unit commitment, respecting each unit's ramp rate, minimum
        up/down time, and cold-start lead time.

        Optional player shortcut — never invoked automatically. Overwrites
        the whole schedule/online table; the player is free to hand-edit
        the result afterward exactly as with any other schedule.

        All 24 hours (00:00-23:00) are committed and filled by the same
        per-hour logic, walking technology groups in
        _AUTO_SCHEDULE_FILL_ORDER within each hour so faster/peaking
        technologies only cover what slower/baseload ones didn't. Since
        there is no actual previous day, 00:00's own commitment/ramp
        decision is computed against a synthetic, calculation-only
        boundary state: every non-maintenance dispatchable unit is
        assumed to have been ONLINE at PLANNING_PREV_DAY_FRAC_<TYPE> *
        rated_mw throughout the previous day's final hour (H24 of D-1),
        already having satisfied its own min-up/min-down window. This
        boundary state is never written to schedule/online and never
        displayed — 00:00 is a fully computed, ordinary hour like any
        other.

        Each hour, after the fill-order commitment pass, three more passes
        run to reach exactly 0 MW diff and leave AGC (CCGT/HYDRO) with
        real regulating room, without disturbing any commitment decision
        above (min-up/min-down, ramp rate):

          1. Trim-back — a baseload/CCGT unit that stays committed because
             shedding it would need the shortfall to drop below its own
             -tech_min (not just <=0) can still overshoot a small residual
             shortfall once online. Walks technologies in *reverse* fill
             order (most flexible first) pulling already-online units down
             toward their own tech_min to absorb any such overshoot.
          2. Force-start — if the hour's online, AGC-enrolled CCGT/HYDRO
             fleet doesn't have at least 2*PLANNING_AGC_RESERVE_MW of
             combined range (tech_max-tech_min) to work with, starts the
             smallest available free-toggle (no min-up/down) AGC-eligible
             unit at its own range midpoint, shedding the same MW from
             online baseload to keep diff at 0. Skipped if there isn't
             enough sheddable baseload room (never overshoots load just to
             manufacture reserve).
          3. Substitution — swaps MW between online AGC-eligible and
             baseload units (same total covered MW, diff undisturbed) so
             pooled up-headroom and down-headroom across enrolled CCGT/
             HYDRO units are each independently >= PLANNING_AGC_RESERVE_MW
             wherever the fleet has the range to support it. Load coverage
             always wins if the two ever conflict — this pass only ever
             reallocates MW that's already scheduled, never adds or removes
             any.
        """
        units_by_type: dict[str, list[GenerationUnit]] = {}
        for unit in self.unit_specs:
            units_by_type.setdefault(unit.unit_type, []).append(unit)

        net_load: dict[float, float] = {
            h: self.load_forecast.get(h, 0.0) - self.renewable_total(h)
            for h in self.hours
        }

        # Synthetic previous-day-H24 boundary state (calculation-only —
        # see docstring). Seeded far enough in the past that every
        # technology's own min-up/min-down is already satisfied by 00:00.
        h0 = self.hours[0]
        prev_online0: dict[str, bool] = {}
        prev_mw0: dict[str, float] = {}
        last_change_hour: dict[str, float] = {}
        prev_mw: dict[str, float] = {}
        for unit in self.unit_specs:
            label = unit.label
            on_maintenance = label in self.maintenance_units
            frac = _PREV_DAY_H24_FRAC.get(unit.unit_type, 1.0)
            prev_online0[label] = not on_maintenance
            prev_mw0[label] = 0.0 if on_maintenance else self.tech_max(unit) * frac
            last_change_hour[label] = h0 - 1000.0
            prev_mw[label] = prev_mw0[label]

        trim_order: tuple[str, ...] = tuple(reversed(_AUTO_SCHEDULE_FILL_ORDER))

        for h in self.hours:
            covered = 0.0
            want_online_this_hour: dict[str, bool] = {}
            # Snapshot each unit's actual committed MW from the previous
            # column (or the synthetic D-1 boundary at h0) BEFORE this
            # column's forward-fill pass mutates prev_mw — Pass 1/2/3 below
            # need this as the true ramp-budget anchor, since prev_mw
            # itself becomes "this column's MW so far" partway through.
            prev_hour_mw: dict[str, float] = dict(prev_mw)
            for tech in _AUTO_SCHEDULE_FILL_ORDER:
                min_up = _MIN_UP_HOURS.get(tech, 0.0)
                min_down = _MIN_DOWN_HOURS.get(tech, 0.0)
                for unit in units_by_type.get(tech, []):
                    label = unit.label
                    shortfall = net_load[h] - covered
                    prev_online = prev_online0[label] if h == h0 else self.online[label][h - PLANNING_STEP_HOURS]
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

                    if h == h0 or want_online != prev_online:
                        # 00:00 always resets the change-hour to itself —
                        # the synthetic D-1 lookback only frees up 00:00's
                        # own decision (see docstring); it must never
                        # propagate as "already been in this state
                        # indefinitely" into 01:00 onward.
                        last_change_hour[label] = h

                    ramp_mw = (unit.ramp_pct_per_min / 100.0) * unit.rated_mw * (PLANNING_STEP_HOURS * 60.0)
                    prev = prev_mw[label]
                    if want_online:
                        # Clamp the remaining shortfall into this unit's own
                        # [tech_min, tech_max] range — NOT tech_min+shortfall,
                        # which would double-count tech_min as an offset on
                        # top of the shortfall and over-size every committed
                        # unit toward its own ceiling regardless of how much
                        # is actually still needed.
                        desired = min(self.tech_max(unit), max(self.tech_min(unit), shortfall))
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
                    want_online_this_hour[label] = want_online
                    covered += mw

            # ---- Pass 1: trim-back ----
            # A "sticky" baseload/CCGT unit kept online above can overshoot
            # a small residual shortfall (or shortfall <= 0) once running,
            # since shedding it was correctly refused unless doing so would
            # itself create a *worse* shortfall. Pull already-online units
            # down toward their own tech_min, most flexible technology
            # first, to soak up any such overshoot — never forces a unit
            # offline (that stays purely a commitment decision, above).
            # room_to_trim is bounded by BOTH tech_min and the unit's
            # remaining ramp-down budget for this column relative to its
            # actual previous-column MW (prev_hour_mw[label], the true
            # committed value carried in from the last column) — the
            # forward-fill pass above may already have used some of that
            # budget moving toward its own `desired`, so this pass must not
            # push the unit further than the ramp still allows in total.
            overshoot = covered - net_load[h]
            if overshoot > 1e-6:
                for tech in trim_order:
                    if overshoot <= 1e-6:
                        break
                    for unit in reversed(units_by_type.get(tech, [])):
                        if overshoot <= 1e-6:
                            break
                        label = unit.label
                        if not want_online_this_hour.get(label, False):
                            continue
                        current_mw = self.schedule[label][h]
                        ramp_mw = (unit.ramp_pct_per_min / 100.0) * unit.rated_mw * (PLANNING_STEP_HOURS * 60.0)
                        min_mw_this_column = max(
                            self.tech_min(unit), prev_hour_mw[label] - ramp_mw
                        )
                        room_to_trim = current_mw - min_mw_this_column
                        trim = min(room_to_trim, overshoot)
                        if trim <= 1e-9:
                            continue
                        new_mw = current_mw - trim
                        self.schedule[label][h] = new_mw
                        prev_mw[label] = new_mw
                        overshoot -= trim
                        covered -= trim

            # ---- Pass 2: force-start (AGC reserve floor) ----
            # Triggered on the online AGC-enrolled fleet's ACTUAL remaining
            # pooled headroom (not nominal tech_max-tech_min range) — a
            # CCGT run flat-out to cover a tight hour's load has plenty of
            # nominal range but zero real headroom left, and that case must
            # still trigger a force-start. If pooled up-headroom (or
            # down-headroom) is short of PLANNING_AGC_RESERVE_MW, starts
            # the largest available free-toggle (no min-up/down — CCGT is
            # never a candidate here, it can't flip on for one hour) AGC-
            # eligible unit at its own midpoint, shedding the same MW from
            # online BASELOAD only (never another AGC unit — shedding an
            # AGC donor would just relocate headroom, not create any) to
            # keep diff at 0. Skips a candidate if there isn't enough
            # sheddable baseload room to fully offset it.
            def _agc_online_units() -> list[GenerationUnit]:
                return [
                    u for u in self.unit_specs
                    if u.unit_type in self.agc_eligible_types
                    and self.is_agc_enrolled(u.label)
                    and want_online_this_hour.get(u.label, False)
                ]

            def _baseload_online_units() -> list[GenerationUnit]:
                return [
                    u for u in self.unit_specs
                    if u.unit_type not in self.agc_eligible_types
                    and want_online_this_hour.get(u.label, False)
                ]

            def _pooled_up() -> float:
                return sum(self.tech_max(u) - self.schedule[u.label][h] for u in _agc_online_units())

            def _pooled_down() -> float:
                return sum(self.schedule[u.label][h] - self.tech_min(u) for u in _agc_online_units())

            def _force_start_toward(pooled_fn) -> None:
                candidates = [
                    u for u in self.unit_specs
                    if u.unit_type in self.agc_eligible_types
                    and self.is_agc_enrolled(u.label)
                    and _MIN_UP_HOURS.get(u.unit_type, 0.0) == 0.0
                    and _MIN_DOWN_HOURS.get(u.unit_type, 0.0) == 0.0
                    and not want_online_this_hour.get(u.label, False)
                ]
                candidates.sort(key=lambda u: -(self.tech_max(u) - self.tech_min(u)))
                for unit in candidates:
                    if pooled_fn() >= PLANNING_AGC_RESERVE_MW - 1e-6:
                        break
                    label = unit.label
                    # Midpoint gives roughly equal up/down headroom from
                    # this one start regardless of which direction
                    # triggered it — Pass 3 (substitution) fine-tunes the
                    # exact balance afterward using whatever is committed.
                    start_mw = (self.tech_min(unit) + self.tech_max(unit)) / 2.0
                    need_to_shed = start_mw
                    for tech in trim_order:
                        if need_to_shed <= 1e-6:
                            break
                        if tech in self.agc_eligible_types:
                            continue
                        for bunit in reversed(units_by_type.get(tech, [])):
                            if need_to_shed <= 1e-6:
                                break
                            blabel = bunit.label
                            if not want_online_this_hour.get(blabel, False):
                                continue
                            current = self.schedule[blabel][h]
                            bramp_mw = (bunit.ramp_pct_per_min / 100.0) * bunit.rated_mw * (PLANNING_STEP_HOURS * 60.0)
                            bmin_mw_this_column = max(
                                self.tech_min(bunit), prev_hour_mw[blabel] - bramp_mw
                            )
                            room = current - bmin_mw_this_column
                            take = min(room, need_to_shed)
                            if take <= 1e-9:
                                continue
                            self.schedule[blabel][h] = current - take
                            prev_mw[blabel] = self.schedule[blabel][h]
                            need_to_shed -= take
                    if need_to_shed > 1e-6:
                        # Not enough sheddable baseload room to fully offset
                        # this unit without overshooting net_load — skip it
                        # rather than break 0 diff to manufacture reserve.
                        continue
                    self.online.setdefault(label, {})[h] = True
                    self.schedule.setdefault(label, {})[h] = start_mw
                    prev_mw[label] = start_mw
                    want_online_this_hour[label] = True
                    last_change_hour[label] = h

            if _pooled_up() < PLANNING_AGC_RESERVE_MW:
                _force_start_toward(_pooled_up)
            if _pooled_down() < PLANNING_AGC_RESERVE_MW:
                _force_start_toward(_pooled_down)

            # ---- Pass 3: substitution (balance up/down headroom) ----
            # Swap MW between online AGC-eligible and baseload units (net
            # covered MW unchanged, so diff stays exactly as passes 1-2
            # left it) so pooled up-headroom and down-headroom across
            # enrolled CCGT/HYDRO are each independently pushed toward
            # PLANNING_AGC_RESERVE_MW wherever the fleet's online range
            # allows it. Reuses _agc_online_units()/_baseload_online_units()
            # from Pass 2. Every MW moved here is bounded by the receiving/
            # donating unit's remaining ramp budget against its actual
            # previous-column MW (prev_hour_mw), same as Pass 1/2 — a swap
            # can move a unit further from its own last committed value
            # than a single column's ramp allows otherwise.
            def _ramp_mw_of(u: GenerationUnit) -> float:
                return (u.ramp_pct_per_min / 100.0) * u.rated_mw * (PLANNING_STEP_HOURS * 60.0)

            def _room_up(u: GenerationUnit, label: str) -> float:
                # How much this unit can rise this column: capped by both
                # tech_max and its remaining ramp-up budget from prev_hour_mw.
                current = self.schedule[label][h]
                max_mw_this_column = min(self.tech_max(u), prev_hour_mw[label] + _ramp_mw_of(u))
                return max(0.0, max_mw_this_column - current)

            def _room_down(u: GenerationUnit, label: str) -> float:
                # How much this unit can fall this column: capped by both
                # tech_min and its remaining ramp-down budget from prev_hour_mw.
                current = self.schedule[label][h]
                min_mw_this_column = max(self.tech_min(u), prev_hour_mw[label] - _ramp_mw_of(u))
                return max(0.0, current - min_mw_this_column)

            agc_units = _agc_online_units()
            if agc_units:
                up_headroom = sum(self.tech_max(u) - self.schedule[u.label][h] for u in agc_units)
                need_up = max(0.0, PLANNING_AGC_RESERVE_MW - up_headroom)
                if need_up > 1e-6:
                    baseload_units = _baseload_online_units()
                    for unit in reversed(agc_units):
                        if need_up <= 1e-6:
                            break
                        label = unit.label
                        can_pull = _room_down(unit, label)
                        pull = min(can_pull, need_up)
                        if pull <= 1e-9:
                            continue
                        for bunit in baseload_units:
                            if pull <= 1e-9:
                                break
                            blabel = bunit.label
                            spare = _room_up(bunit, blabel)
                            take = min(spare, pull)
                            if take <= 1e-9:
                                continue
                            self.schedule[blabel][h] += take
                            self.schedule[label][h] -= take
                            pull -= take
                            need_up -= take

                agc_units = _agc_online_units()
                down_headroom = sum(self.schedule[u.label][h] - self.tech_min(u) for u in agc_units)
                need_down = max(0.0, PLANNING_AGC_RESERVE_MW - down_headroom)
                if need_down > 1e-6:
                    baseload_units = _baseload_online_units()
                    for unit in agc_units:
                        if need_down <= 1e-6:
                            break
                        label = unit.label
                        can_push = _room_up(unit, label)
                        push = min(can_push, need_down)
                        if push <= 1e-9:
                            continue
                        for bunit in baseload_units:
                            if push <= 1e-9:
                                break
                            blabel = bunit.label
                            spare = _room_down(bunit, blabel)
                            take = min(spare, push)
                            if take <= 1e-9:
                                continue
                            self.schedule[blabel][h] -= take
                            self.schedule[label][h] += take
                            push -= take
                            need_down -= take

            for label, hours_dict in self.schedule.items():
                if h in hours_dict:
                    prev_mw[label] = hours_dict[h]

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
        """Full 24h schedule, zeroed for hours a unit is offline. Written to
        disk by write_schedule_json() and consumed each simulated-hour
        boundary by FleetModel.apply_hourly_schedule() (see
        GridSimulation._apply_hourly_schedule())."""
        result: dict[str, dict[float, float]] = {}
        for unit in self.unit_specs:
            result[unit.label] = {
                h: (self.schedule.get(unit.label, {}).get(h, 0.0)
                    if self.is_online(unit.label, h) else 0.0)
                for h in self.hours
            }
        return result


# ─────────────────────────────────────────────────────────────────────────────
# JSON HANDOFF — Phase 1 -> Phase 2
#
# The confirmed plan is written to disk rather than passed to GridSimulation
# in memory: src/assets/planning_schedules/shift{NN}_hourly.json is the
# actual automatic hourly per-unit setpoint program Phase 2 runs against,
# not a debug mirror of something else already carrying the data. This
# makes the handoff inspectable/editable by hand and reproducible
# independent of the PlanningModel instance that produced it.
# ─────────────────────────────────────────────────────────────────────────────

_PLANNING_SCHEDULES_DIR = Path(__file__).parent.parent / 'assets' / 'planning_schedules'


def write_schedule_json(model: PlanningModel, shift_number: int) -> Path:
    """Serialize the confirmed plan's handover dispatch and full 24h
    schedule to src/assets/planning_schedules/shift{NN}_hourly.json.
    Overwrites any existing file for this shift."""
    _PLANNING_SCHEDULES_DIR.mkdir(parents=True, exist_ok=True)
    path = _PLANNING_SCHEDULES_DIR / f'shift{shift_number:02d}_hourly.json'

    hourly = model.to_hourly_dispatch()
    data = {
        'shift_number':     shift_number,
        'start_hour':       model.start_hour,
        'duration_hours':   model.duration_hours,
        'initial_schedule': model.to_initial_schedule(),
        'hourly_schedule':  {
            label: {str(h): mw for h, mw in by_hour.items()}
            for label, by_hour in hourly.items()
        },
        'agc_enrolled_units': sorted(
            label for label, enrolled in model.agc_enrolled.items() if enrolled
        ),
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return path


def load_schedule_json(
    shift_number: int,
) -> tuple[dict[str, float], dict[str, dict[float, float]], frozenset[str]]:
    """Read back shift{NN}_hourly.json written by write_schedule_json().

    Returns (initial_schedule, hourly_schedule, agc_enrolled_units) in
    exactly the shapes GridSimulation/_make_sim_and_renderer expect.
    agc_enrolled_units is an empty frozenset for files predating that field.
    Raises FileNotFoundError if the shift was never planned — this is only
    ever called right after a confirmed plan, so a missing file means the
    caller is wired wrong, not a normal fallback case."""
    path = _PLANNING_SCHEDULES_DIR / f'shift{shift_number:02d}_hourly.json'
    if not path.exists():
        raise FileNotFoundError(
            f'No confirmed Phase 1 plan for shift {shift_number} — expected {path}'
        )
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    initial_schedule: dict[str, float] = dict(data['initial_schedule'])
    hourly_schedule: dict[str, dict[float, float]] = {
        label: {float(h): mw for h, mw in by_hour.items()}
        for label, by_hour in data['hourly_schedule'].items()
    }

    # Defensive: a schedule file written before a PLANNING_STEP_HOURS change
    # would silently under-apply (units never update at the missing
    # columns) rather than error, if read back today. This is only ever
    # called right after write_schedule_json() in the same session (see
    # this function's docstring), so a mismatch should never occur in
    # normal play — this exists purely to fail loudly instead of silently
    # if that assumption is ever violated.
    expected_hours = frozenset(
        round(h * PLANNING_STEP_HOURS, 10) for h in range(int(24 / PLANNING_STEP_HOURS))
    )
    for label, by_hour in hourly_schedule.items():
        if frozenset(by_hour.keys()) != expected_hours:
            raise ValueError(
                f'{path} has a stale/mismatched schedule granularity for '
                f'{label!r} (expected {len(expected_hours)} columns at '
                f'{PLANNING_STEP_HOURS}h steps) — reconfirm the Phase 1 '
                f'plan for shift {shift_number} to regenerate it.'
            )

    agc_enrolled_units: frozenset[str] = frozenset(data.get('agc_enrolled_units', []))
    return initial_schedule, hourly_schedule, agc_enrolled_units


# ─────────────────────────────────────────────────────────────────────────────
# FACTORY — Shift 10 only
# ─────────────────────────────────────────────────────────────────────────────

def build_planning_model_for_shift10() -> PlanningModel:
    """Build a PlanningModel for Shift 10 (the only wired-in shift so far)."""
    return build_planning_model(10)


def build_planning_model(shift_number: int, difficulty: str = 'standard') -> PlanningModel:
    cfg = load_shift_config(shift_number)

    grid_source = cfg.get('grid_source')
    if not grid_source:
        raise ValueError(
            f'Shift {shift_number} has no GRID_SOURCE — every campaign shift '
            f'must declare one (see gameplay/shifts/shift_{shift_number:02d}.py).'
        )
    buses, lines, units = load_designer_grid_named(grid_source)
    grid = DesignerGrid(buses, lines, units)

    dispatchable = [
        u for u in grid.get_active_units() if u.unit_type not in _RENEWABLE_TYPES
    ]
    renewable_specs = [
        u for u in grid.get_active_units() if u.unit_type in _RENEWABLE_TYPES
    ]

    substation_specs = get_substation_demand_specs(cfg['substation_load_mw'])
    demand_model = DemandModel(cfg['peak_demand_mw'], substation_specs)
    load_forecast = demand_model.forecast_by_hour(
        0.0, 24.0 - PLANNING_STEP_HOURS, step=PLANNING_STEP_HOURS
    )

    renewables = RenewablesModel(grid)
    renewable_forecast = renewables.forecast_by_hour(
        0.0, 24.0 - PLANNING_STEP_HOURS, step=PLANNING_STEP_HOURS
    )

    model = PlanningModel(
        unit_specs=dispatchable,
        start_hour=cfg['start_hour'],
        duration_hours=cfg['duration_hours'],
        load_forecast=load_forecast,
        renewable_specs=renewable_specs,
        renewable_forecast=renewable_forecast,
        maintenance_units=frozenset(cfg['maintenance_units']),
        difficulty=difficulty,
    )
    _default_init_schedule(model)
    return model


def _default_init_schedule(model: PlanningModel) -> None:
    """Seed the schedule flat across all 24 hours: every dispatchable unit
    starts OFFLINE at 0 MW, with no shift-authored starting point — the
    player builds the whole day's commitment from a blank slate. No shift
    file hardcodes a handover dispatch; the confirmed plan's start_hour
    column is the only source of Phase 2's initial dispatch."""
    for unit in model.unit_specs:
        label = unit.label
        model.online[label] = {h: False for h in model.hours}
        model.schedule[label] = {h: 0.0 for h in model.hours}
        if unit.unit_type in model.agc_eligible_types:
            model.agc_enrolled[label] = True
