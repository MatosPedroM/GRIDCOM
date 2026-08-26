"""
src/simulation/simulation.py

Master simulation loop and SimulationState snapshot for GRIDCOM.

GridSimulation orchestrates all physics modules each tick:
  demand → fleet → frequency+AGC → load flow → voltage → overloads
  → cascade → islands → alarms → state snapshot

SimulationState is the complete snapshot transferred to the renderer
and gameplay layer each frame. See SIMULATION_API.md for the full
interface contract.

Scripted events are loaded from gameplay/shifts/shift_NN.py and
fired at scheduled simulation times during each shift.

See GRID_SIMULATION_MECHANICS.md for physics tick ordering.
See SIMULATION_API.md for the complete public interface.
"""

from __future__ import annotations

import csv
import importlib
import logging
import os

import numpy as np
from dataclasses import dataclass

from config.constants import (
    F_NOMINAL,
    F_MIN, F_MAX,
    F_ALERT_LOW, F_ALERT_HIGH,
    F_CRITICAL_LOW, F_CRITICAL_HIGH,
    F_TRIP_ISLAND_HIGH, F_TRIP_ISLAND_LOW,
    F_IN_BOUNDS_TOL,
    OVERLOAD_WARN_PCT, OVERLOAD_CRIT_PCT,
    V_WATCH_LOW, V_WARNING_LOW, V_CRITICAL_LOW,
    V_COLLAPSE_GAIN, V_COLLAPSE_SEVERITY_LOW, V_COLLAPSE_SEVERITY_FLOOR,
    V_COLLAPSE_RECOVERY_PU_S,
    ALARM_MESSAGE_MAX_LEN,
    ALARM_FADE_INFO_TUTOR_MIN, ALARM_FADE_CRIT_WARN_MIN, ALARM_LIST_MAX,
    INTC_N_CAPACITY_MW, INTC_S_CAPACITY_MW,
    DEBUG_SIMULATION, SIM_DEBUG_LOG,
    TRIP_DELAY_S, TIME_COMPRESSION,
    BLACKOUT_TRIP_S,
    LINE_CHARGING_MVAR_PER_KM_150KV,
    LINE_CHARGING_MVAR_PER_KM_220KV,
    LINE_CHARGING_MVAR_PER_KM_400KV,
    LOAD_SHED_STEP_FRACTION,
)
import config.constants as _sim_const
from simulation.designer_grid import DesignerGrid
from simulation.loadflow import DCLoadFlow
from simulation.voltage import VoltageModel
from simulation.frequency import FrequencyModel
from simulation.units import FleetModel
from simulation.demand import DemandModel
from simulation.renewables import RenewablesModel
from simulation.cascade import CascadeModel
from simulation.reactive_devices import ReactiveDevices
from data.profiles import get_substation_demand_specs
from gameplay.shifts.loader import load_shift_config

# Real-seconds equivalent of TRIP_DELAY_S, for alarm text — avoids a hardcoded
# literal going stale if TRIP_DELAY_S is retuned (see CLAUDE.md Rule 1).
_TRIP_DELAY_REAL_S: float = TRIP_DELAY_S / TIME_COMPRESSION


def _line_charging_mvar_per_km(voltage_kv: float) -> float:
    """Per-tier line-charging (Ferranti effect) rate, keyed by a line's voltage_kv."""
    if voltage_kv >= 400.0:
        return LINE_CHARGING_MVAR_PER_KM_400KV
    if voltage_kv >= 220.0:
        return LINE_CHARGING_MVAR_PER_KM_220KV
    return LINE_CHARGING_MVAR_PER_KM_150KV


# ─────────────────────────────────────────────────────────────────────────────
# SCRIPTED EVENT LOADER
# ─────────────────────────────────────────────────────────────────────────────

def _load_scripted_events(shift_number: int) -> list[dict]:
    """
    Load SCRIPTED_EVENTS from gameplay/shifts/shift_NN.py if the module exists.

    Returns a list of mutable event dicts with a 'fired' flag added.
    Returns [] if the shift module is absent or defines no events.
    """
    try:
        mod = importlib.import_module(f'gameplay.shifts.shift_{shift_number:02d}')
        raw = getattr(mod, 'SCRIPTED_EVENTS', [])
        return [dict(e, fired=False) for e in raw]
    except ImportError:
        return []


def _load_objectives(shift_number: int, name: str) -> list[dict]:
    """
    Load WIN_CONDITIONS or FAIL_CONDITIONS from gameplay/shifts/shift_NN.py.

    Each entry uses the same declarative schema as a scripted-event condition
    ({'metric', 'target', 'op', 'value'} — see _eval_condition), plus two
    optional keys:
        sustained_s: float  — the condition must hold continuously for this
                              many simulated seconds before it counts. Absent
                              or 0.0 means it counts the instant it is true.
        message:     str    — operator-facing text for the debrief.

    Returns a list of mutable dicts with a 'held_s' accumulator added.
    Returns [] if the shift module is absent or defines no such list.
    """
    try:
        mod = importlib.import_module(f'gameplay.shifts.shift_{shift_number:02d}')
        raw = getattr(mod, name, [])
        return [dict(c, held_s=0.0) for c in raw]
    except ImportError:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# ALARM
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Alarm:
    alarm_id:       int
    priority:       str     # 'CRITICAL', 'WARNING', 'INFO', 'TUTOR'
    timestamp_min:  float
    message:        str     # max ALARM_MESSAGE_MAX_LEN chars
    element_label:  str | None
    acknowledged:   bool
    detail:         str


# ─────────────────────────────────────────────────────────────────────────────
# SIMULATION STATE SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SimulationState:
    # Time
    sim_time_min:            float
    sim_hour:                float

    # Frequency
    frequency_hz:            float
    frequency_trend:         str
    frequency_deviation_hz:  float

    # Power balance
    total_generation_mw:     float
    total_load_mw:           float
    net_imbalance_mw:        float
    spinning_reserve_mw:     float
    system_inertia_h:        float
    losses_mw:               float
    bus_loads:               dict   # {bus_label: demand_mw} live load at each LD bus

    # AGC regulation availability
    agc_current_mw:          float  # total MW currently from online AGC units
    agc_max_mw:              float  # total rated MW of online AGC units
    agc_min_mw:              float  # total tech-minimum MW of online AGC units
    agc_saturated:           bool   # True if the last AGC correction attempt found no
                                     # eligible unit with headroom (apply_agc_signal returned {})

    # Network — buses
    bus_voltages:            dict
    bus_angles:              dict
    bus_vsi:                 dict
    bus_vsi_tier:            dict   # {bus_label: 'HEALTHY'|'WATCH'|'WARNING'|'CRITICAL'}

    # Reactive devices — automatic (read-only to player) and manual
    bus_shunt_step:          dict   # {bus_label: int} automatic shunt bank step, signed
    bus_shunt_mvar:          dict   # {bus_label: float} automatic shunt bank MVAr
    bus_svc_mvar:            dict   # {bus_label: float} manual SVC setpoint, buses hosting one
    bus_svc_limits:          dict   # {bus_label: (q_min_mvar, q_max_mvar)}
    bus_q_injection_mvar:    dict   # {bus_label: float} total device Q injection
    bus_load_q_mvar:         dict   # {bus_label: float} load's own reactive demand (negative = consuming)
    total_q_generated_mvar:  float  # system-wide positive Q contributions (generators/devices/lines)
    total_q_consumed_mvar:   float  # system-wide negative Q contributions, as a positive magnitude

    # Network — lines
    line_flows_mw:           dict
    line_loading_pct:        dict
    line_status:             dict
    overload_timers:         dict

    # Generation units
    unit_states:             dict
    unit_outputs_mw:         dict
    unit_targets_mw:         dict
    unit_q_injections_mvar:  dict
    unit_start_progress:     dict
    unit_maintenance:        frozenset   # labels of units on planned maintenance
    unit_q_target_mvar:      dict   # {unit_label: float} player-commanded reactive target
    unit_q_reserve_mvar:     dict   # {unit_label: float} headroom to q_max (0 if not ONLINE)
    unit_dispatch_modes:     dict   # {unit_label: 'AUTO'|'MANUAL'}
    unit_has_schedule:       frozenset   # labels covered by this shift's Phase 1 hourly schedule
    unit_agc_enabled:        frozenset   # labels currently AGC-participating (eligible + not excluded + ONLINE)
    reservoir_levels:        dict
    pumped_storage_modes:    dict

    # Generation mix by fuel type (ONLINE units only)
    gen_mix_mw:              dict   # {unit_type: total_mw}

    # Forecasts
    demand_forecast_mw:      dict
    wind_forecast_mw:        dict
    solar_forecast_mw:       dict

    # Alarms
    active_alarms:           list

    # Topology
    islands:                 list
    blackout_zones:          frozenset

    # Crisis
    crisis_active:           bool
    crisis_type:             str | None
    crisis_element:          str | None

    # Performance tracking
    frequency_in_bounds_pct: float
    max_line_loading_seen:   float
    load_shed_events:        int
    cascade_events:          int
    derate_events:           int
    drift_events:            int
    min_voltage_seen:        float


# ─────────────────────────────────────────────────────────────────────────────
# FORECAST RESULT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ForecastResult:
    generation_stack:     dict   # {sim_hour: {unit_type: mw}}
    reserve_by_hour:      dict   # {sim_hour: reserve_mw}
    congestion_risk:      dict   # {line_label: max_loading_pct}
    voltage_risk:         dict   # {bus_label: min_vsi}
    reservoir_end_levels: dict   # {station_label: level_fraction}
    estimated_cost_eur:   float
    risk_hours:           list   # hours where reserve < 8% of demand
    congestion_hours:     dict   # {line_label: [hours]}


# ─────────────────────────────────────────────────────────────────────────────
# GRID SIMULATION
# ─────────────────────────────────────────────────────────────────────────────

class GridSimulation:
    """
    Master simulation orchestrator for a single shift.

    Owns all physics sub-models and advances them each tick in the
    prescribed order from GRID_SIMULATION_MECHANICS.md.

    Scripted events are loaded from the corresponding gameplay/shifts/
    shift_NN.py module and fired via _process_scripted_events() each tick.
    """

    def __init__(
        self,
        grid: DesignerGrid,
        shift_number: int,
        difficulty: str,
        initial_schedule: dict | None = None,
        maintenance_units: set | None = None,
        maintenance_lines: set | None = None,
        substation_load_mw: dict | None = None,
        substation_types: dict[str, str] | None = None,
        scripted_events: list[dict] | None = None,
        start_hour: float | None = None,
        duration_hours: float | None = None,
        hourly_schedule: dict[str, dict[float, float]] | None = None,
        rng_seed: int | None = None,
    ) -> None:
        self._grid         = grid
        self._shift_number = shift_number
        self._difficulty   = difficulty

        # Reproducibility: seed this shift's renewables noise. An explicit
        # rng_seed wins; otherwise derive one from SHIFT_RNG_SEED_BASE so the
        # same shift replays the same wind/solar trace every run. A None base
        # (or None resolved seed) means entropy-seeded, non-reproducible runs.
        if rng_seed is None and _sim_const.SHIFT_RNG_SEED_BASE is not None:
            rng_seed = _sim_const.SHIFT_RNG_SEED_BASE + shift_number
        self._rng_seed = rng_seed

        # Full 24h per-unit schedule from the Phase 1 planning screen
        # ({unit_label: {hour: mw}}), if the shift went through planning.
        # Consumed each simulated-hour boundary by _apply_hourly_schedule()
        # to advance every AUTO-mode unit's target to the plan's value for
        # the new hour (see tick()). None if the shift has no planning
        # phase (Shifts 1-4) — the per-hour executor is then a no-op.
        self._hourly_schedule: dict[str, dict[float, float]] | None = hourly_schedule
        self._last_dispatch_hour: float | None = None

        cfg = load_shift_config(shift_number)
        self._start_hour        = start_hour if start_hour is not None else cfg['start_hour']
        self._duration_minutes  = (duration_hours * 60.0 if duration_hours is not None
                                    else cfg['duration_hours'] * 60.0)

        # Resolve substation load table: prefer explicit arg, fall back to shift file.
        if substation_load_mw is None:
            substation_load_mw = cfg.get('substation_load_mw', {})
        substation_specs = get_substation_demand_specs(substation_load_mw, substation_types)

        # Physics sub-models
        self._loadflow   = DCLoadFlow(grid)
        self._voltage    = VoltageModel(grid)
        self._frequency  = FrequencyModel()
        self._fleet      = FleetModel(grid, initial_schedule or {}, maintenance_units)
        if self._hourly_schedule:
            # A plan exists for this shift — every unit it schedules starts
            # AUTO (following that plan) rather than the pre-planning
            # default of MANUAL. Touching a unit's target later drops it
            # back to MANUAL (UnitModel.set_target()).
            for _label in self._hourly_schedule:
                if self._fleet.has_unit(_label):
                    self._fleet.set_unit_auto_mode(_label)
        self._demand     = DemandModel(cfg['peak_demand_mw'], substation_specs)
        self._renewables = RenewablesModel(
            grid,
            rng=np.random.default_rng(self._rng_seed) if self._rng_seed is not None else None,
        )
        # Separate generator for random unit deviation (derate/drift) events
        # — offset from the renewables seed so the two streams don't draw
        # from the same sequence, while staying derived from the same
        # per-shift base for reproducible replays (see _rng_seed above).
        self._deviation_rng = (
            np.random.default_rng(self._rng_seed + 100000)
            if self._rng_seed is not None else np.random.default_rng()
        )
        self._cascade    = CascadeModel()
        self._reactive   = ReactiveDevices()

        # Interconnector injections (positive = import into grid)
        self._intc_schedule: dict = {
            'INTC-N': 0.0,
            'INTC-S': 0.0,
        }
        # Line service status
        self._line_in_service: dict = {
            l.label: True for l in grid.get_active_lines()
        }
        self._maintenance_lines: frozenset = frozenset(maintenance_lines or set())
        for _label in self._maintenance_lines:
            if _label in self._line_in_service:
                self._line_in_service[_label] = False
        if self._maintenance_lines:
            _in_service = self._get_in_service_lines()
            self._loadflow.rebuild(_in_service)
            self._voltage.rebuild(_in_service)

        # Overload timer state (owned here, passed to CascadeModel each tick)
        self._overload_timers: dict = {}

        # Reclose-cooldown state — {line_label: sim-seconds remaining before
        # this line may be switched again}, decremented every tick. Voltage
        # lookup cached once here rather than re-derived per trip/close call.
        self._line_voltage_kv: dict = {
            l.label: l.voltage_kv for l in grid.get_active_lines()
        }
        self._reclose_cooldown_remaining: dict = {}

        # Random-derate expiry state — {unit_label: sim-minutes remaining
        # before UnitModel.clear_derate() is called}, decremented every
        # tick alongside the deviation trigger roll (see _apply_hourly_schedule()
        # / _roll_random_deviations()). Only entries for units currently
        # under a RANDOM (non-scripted) derate live here — a scripted
        # UNIT_DERATE action's cap is intentionally permanent for the
        # shift, matching today's behaviour, so it's never added here.
        self._random_derate_remaining_min: dict = {}

        # {unit_label: unit_type} / {unit_label: rated_mw} lookups for the
        # deviation trigger/flavour-reason logic, built once here from the
        # public GenerationUnit spec rather than reaching into FleetModel's
        # private UnitModel._spec from this module — mirrors the existing
        # self._line_voltage_kv cache-once pattern.
        self._unit_type_by_label: dict = {
            u.label: u.unit_type for u in grid.get_active_units()
        }
        self._unit_rated_mw_by_label: dict = {
            u.label: u.rated_mw for u in grid.get_active_units()
        }

        # Voltage collapse acceleration — stateful post-solve overlay (see
        # _apply_collapse_acceleration). {bus_label: offset_pu}, offset <= 0.
        self._v_collapse_offset: dict = {}

        # Previous tick's solved bus voltages — fed to ReactiveDevices.step_automatics()
        # so automatic shunt banks act with a one-tick lag (no algebraic loop).
        self._prev_bus_voltages: dict = {}

        # Alarm state
        self._alarms:     list  = []
        self._alarm_id:   int   = 0
        self._seen_warn:  set   = set()   # line labels with active warn alarm
        self._seen_crit:  set   = set()   # line labels with active crit alarm
        self._seen_v_warn: set  = set()   # bus labels with active voltage warn alarm
        self._seen_v_crit: set  = set()   # bus labels with active voltage crit alarm
        self._freq_alarm_state: str = 'OK'  # 'OK' | 'ALERT' | 'CRITICAL'

        # Blackout / frequency-collapse fail state — consecutive sim-seconds
        # spent pinned at the F_MIN/F_MAX hard clamp. Reset to 0 whenever
        # frequency is back inside the clamp; triggers a FAILED shift end
        # once it exceeds BLACKOUT_TRIP_S (see is_shift_complete()).
        self._blackout_clamp_s: float = 0.0
        self._shift_failed:     bool  = False

        # Landing freeze — real seconds remaining before the sim clock
        # (_sim_time_min) starts advancing. Decremented by true wall-clock
        # dt (passed separately via tick_real_seconds(), NOT by
        # dt_sim_seconds — that argument already has TIME_COMPRESSION and
        # the player's speed multiplier baked in by the caller, so it can't
        # drive a speed-immune real-time countdown). Frequency/AGC/load
        # flow/voltage still run normally on the frozen T+0 snapshot while
        # this is > 0, so the player sees a live, stable grid rather than a
        # paused screenshot while reading the handover.
        #
        # Deliberately NOT read from _sim_const.LANDING_FREEZE_S here:
        # main.py sets _const.LANDING_FREEZE_S from the shift's config
        # AFTER constructing GridSimulation (same call-order as every other
        # _const.X assignment in _make_sim_and_renderer()), so caching it
        # in __init__ would always see the previous shift's leftover value,
        # never this shift's own override. None is a lazy-init sentinel —
        # tick_real_seconds() resolves it from _sim_const on first call,
        # by which point main.py has already set the real per-shift value.
        self._landing_freeze_remaining_s: float | None = None

        # Simulation time
        self._sim_time_min: float = 0.0

        # Performance counters
        self._ticks_in_bounds:  int   = 0
        self._total_ticks:      int   = 0
        self._max_line_loading: float = 0.0
        self._load_shed_events: int   = 0
        self._cascade_events:   int   = 0
        self._derate_events:    int   = 0
        self._drift_events:     int   = 0
        self._min_voltage:      float = 1.0

        # AGC PID state
        self._agc_integral:     float = 0.0
        self._agc_prev_delta_f: float = 0.0
        self._agc_saturated:    bool  = False

        # Debug file logger (used when DEBUG_SIMULATION is True)
        if DEBUG_SIMULATION:
            os.makedirs('logs', exist_ok=True)
            _logger = logging.getLogger('sim')
            _logger.setLevel(logging.DEBUG)
            _logger.propagate = False
            _logger.handlers.clear()
            _handler = logging.FileHandler(SIM_DEBUG_LOG, mode='w', encoding='utf-8')
            _handler.setFormatter(logging.Formatter('%(message)s'))
            _logger.addHandler(_handler)
            self._log = _logger
        else:
            self._log = None

        # AGC log state (used when AGC_LOG is True)
        self._agc_log_file         = None
        self._agc_log_writer       = None
        self._agc_log_headers:     list[str] | None = None
        self._agc_log_flush_counter: int = 0

        # Sim state log (used when SIM_STATE_LOG is True)
        self._state_log_file           = None
        self._state_log_writer         = None
        self._state_log_bus_labels:  list[str] | None = None
        self._state_log_unit_labels: list[str] | None = None
        self._state_log_flush_counter: int = 0

        # Forecast cache (recomputed only when sim hour integer changes)
        self._cached_demand_fc:    dict = {}
        self._cached_renew_fc:     dict = {}
        self._cached_forecast_hour: int = -1

        # Crisis state
        self._crisis_active:  bool      = False
        self._crisis_type:    str|None  = None
        self._crisis_element: str|None  = None

        # Cached state snapshot (built in _solve_and_snapshot)
        self._state: SimulationState | None = None

        # Scripted events — explicit list takes precedence (Shift Builder /
        # JSON-authored shifts); otherwise loaded from shift_NN.py.
        # Each entry is a dict with keys: trigger_min, priority, message, detail,
        # element, condition (declarative dict|None), action (declarative dict|None),
        # fired (bool, mutable).
        if scripted_events is not None:
            self._scripted_events: list[dict] = [dict(e, fired=False) for e in scripted_events]
        else:
            self._scripted_events = _load_scripted_events(shift_number)

        # Objectives — optional WIN_CONDITIONS / FAIL_CONDITIONS in shift_NN.py.
        # A FAIL condition ends the shift the moment it holds for its
        # sustained_s; WIN conditions are all evaluated once at shift end.
        # Both reuse the scripted-event condition schema and evaluator.
        self._win_conditions:  list[dict] = _load_objectives(shift_number, 'WIN_CONDITIONS')
        self._fail_conditions: list[dict] = _load_objectives(shift_number, 'FAIL_CONDITIONS')
        self._failed_objective: dict | None = None

        # Build initial state snapshot
        self._solve_and_snapshot()

        # Truncate/recreate both per-tick log files now, regardless of
        # whether AGC_LOG/SIM_STATE_LOG end up writing any data rows this
        # run — otherwise a run where AGC never fires (AGC off all shift)
        # or SIM_STATE_LOG is off leaves the *previous* run's file
        # completely untouched, silently stale, with nothing marking it as
        # not belonging to this shift.
        self._reset_log_files()

    # ─────── MAIN TICK ────────────────────────────────────────────────────

    def tick_real_seconds(self, real_dt_seconds: float) -> None:
        """
        Decrement the landing-freeze countdown by true wall-clock elapsed
        time, independent of TIME_COMPRESSION and the player's speed
        multiplier. Call once per real frame BEFORE tick(), with the same
        unscaled dt main.py's loop already tracks (real_dt_seconds), so the
        freeze takes the same real time to clear at 1x or 10x speed — a
        player can't skip it by changing speed. No-op once the freeze has
        already cleared.
        """
        if self._landing_freeze_remaining_s is None:
            # Lazy-resolve on first call — see __init__'s comment on why
            # this can't be read at construction time.
            self._landing_freeze_remaining_s = _sim_const.LANDING_FREEZE_S
        if self._landing_freeze_remaining_s > 0.0:
            self._landing_freeze_remaining_s = max(
                0.0, self._landing_freeze_remaining_s - real_dt_seconds)

    def tick(self, dt_sim_seconds: float) -> None:
        """
        Advance simulation by dt_sim_seconds of simulated time.

        Tick order (per GRID_SIMULATION_MECHANICS.md):
          1.  Advance time
          2.  Update demand
          3.  Update renewable outputs → inject into fleet
          4.  Tick unit state machines (ramp, cold start)
          5.  Frequency update (swing equation) + AGC secondary response
          6.  Build P/Q injection vectors
          7.  Solve DC load flow
          8.  Solve voltage
          9.  Check line overloads → trip if timer exceeded
          10. Rebuild topology if lines tripped
          11. Island detection + blackout classification
          12. Update alarms
          13. Compute crisis state
          14. Update performance counters
          15. Build state snapshot
        """
        if dt_sim_seconds <= 0.0:
            return

        dt_min = dt_sim_seconds / 60.0

        # Reclose-cooldown decrement — sim-seconds, so it scales with speed
        # like every other tripped-line timer (TRIP_DELAY_S, overload
        # timers), unlike the landing freeze below.
        if self._reclose_cooldown_remaining:
            for _label in list(self._reclose_cooldown_remaining):
                remaining = self._reclose_cooldown_remaining[_label] - dt_sim_seconds
                if remaining <= 0.0:
                    del self._reclose_cooldown_remaining[_label]
                else:
                    self._reclose_cooldown_remaining[_label] = remaining

        # 1. Advance time — held at T+0 during the landing freeze (real
        # seconds, decremented via tick_real_seconds(), independent of
        # dt_sim_seconds/speed) so demand/renewables/scripted-event timers
        # don't move until the player has had a moment to land. Frequency/
        # AGC and the sustained_s fail/blackout timers are held too
        # (see the freeze_active checks below) — only load flow/voltage
        # keep resolving every tick, so the canvas still reflects the
        # handover state exactly rather than looking stale. A caller that
        # never calls tick_real_seconds() (headless traces, any test
        # harness driving tick() directly) sees _landing_freeze_remaining_s
        # stay None, which is treated as "already cleared" — the freeze is
        # purely a tick_real_seconds() opt-in, never a behaviour change for
        # a caller that ignores it.
        freeze_active = (self._landing_freeze_remaining_s is not None
                          and self._landing_freeze_remaining_s > 0.0)
        if not freeze_active:
            self._sim_time_min += dt_min
        sim_hour = self._start_hour + self._sim_time_min / 60.0

        # 1b. Phase 1 per-hour schedule executor — advance AUTO-mode units'
        # targets whenever the simulated hour crosses an integer boundary.
        self._apply_hourly_schedule(sim_hour)

        # 2. Update demand
        self._demand.update(sim_hour, self._fleet.total_generation_mw())

        # 3. Renewable outputs → fleet
        rng_outputs = self._renewables.update(sim_hour, dt_sim_seconds, deterministic=False)
        for label, mw in rng_outputs.items():
            self._fleet.set_renewable_output(label, mw)

        # 4. Tick unit state machines
        self._fleet.tick(dt_sim_seconds)

        # 4b. Random unit deviation (derate/drift) — trigger rolls and
        # derate expiry. See _roll_random_deviations().
        self._roll_random_deviations(dt_min)

        # 5. Frequency update (swing equation) — held during the landing
        # freeze along with sim time above, so AGC doesn't integrate
        # against a static handover imbalance the player can't see or react
        # to yet. AGC derives from frequency_hz, so gating the update alone
        # is sufficient to freeze the whole chain.
        if not freeze_active:
            self._frequency.update(
                dt_sim_seconds=dt_sim_seconds,
                p_generation_mw=self._fleet.total_generation_mw(),
                p_load_mw=self._demand.total_load_mw,
                online_unit_types=self._fleet.online_unit_types(),
            )

            # 5a. AGC secondary frequency response
            if _sim_const.AGC_ENABLED:
                self._apply_agc(dt_sim_seconds)

        # 5b. Automatic reactive devices (shunt banks) act on the previous
        # tick's solved voltage — one-tick lag, no algebraic loop with the solver.
        self._reactive.step_automatics(self._prev_bus_voltages, dt_sim_seconds)

        # 6. Build injection vectors (exclude load on buses already blacked out)
        in_service = self._get_in_service_lines()
        _active_gen_buses = self._get_active_generation_buses()
        _islands_pre      = self._cascade.find_islands(self._grid.get_active_buses(), in_service)
        _blackout_pre     = self._cascade.get_blackout_zones(_islands_pre, _active_gen_buses)
        p_injections = self._build_p_injections(_blackout_pre)
        q_injections = self._build_q_injections(_blackout_pre)

        # 7. DC load flow
        lf_result  = self._loadflow.solve(p_injections)

        # 8. Voltage
        vr_result = self._voltage.solve(q_injections)

        # 9. Check overloads
        trips, self._overload_timers = self._cascade.check_overloads(
            lf_result.line_loading_pct,
            self._overload_timers,
            dt_sim_seconds,
        )

        # 10. Trip lines and rebuild if needed
        if trips:
            self._cascade_events += 1
            for line_label in trips:
                self._line_in_service[line_label] = False
                self._start_reclose_cooldown(line_label)
                self._raise_alarm(
                    priority='CRITICAL',
                    message=f'Line {line_label} tripped — overload protection',
                    element_label=line_label,
                    detail=(f'Line {line_label} sustained loading above 100%. '
                            f'Protection relay operated. Line removed from service.'),
                )
                if self._log:
                    self._log.debug(f'[CASCADE] Line {line_label} tripped at '
                                    f't={self._sim_time_min:.1f} min')

            in_service = self._get_in_service_lines()
            self._loadflow.rebuild(in_service)
            self._voltage.rebuild(in_service)
            lf_result = self._loadflow.solve(p_injections)
            vr_result = self._voltage.solve(q_injections)

        # 11. Island detection and isolated unit protection
        self._trip_isolated_units(in_service)
        islands = self._cascade.find_islands(self._grid.get_active_buses(), in_service)
        _active_gen_buses_post = self._get_active_generation_buses()

        if self._trip_frequency_runaway_islands(islands, _active_gen_buses_post):
            _active_gen_buses_post = self._get_active_generation_buses()
            islands = self._cascade.find_islands(self._grid.get_active_buses(), in_service)

        blackout_zones = self._cascade.get_blackout_zones(islands, _active_gen_buses_post)

        # 11b. Voltage collapse acceleration overlay — stateful, applied once
        # per tick after topology is final. v_eff (never the raw solve) feeds
        # every downstream consumer (alarms, crisis, min-voltage, snapshot).
        for bus_label in blackout_zones:
            self._reset_collapse_offset(bus_label)
        v_eff = self._apply_collapse_acceleration(vr_result.bus_voltages, dt_sim_seconds)
        self._prev_bus_voltages = dict(vr_result.bus_voltages)

        # 12. Alarms
        self._update_loading_alarms(lf_result.line_loading_pct)
        self._update_voltage_alarms(v_eff)
        self._update_frequency_alarms()
        self._process_scripted_events()
        self._expire_alarms()

        # 13. Crisis state
        self._update_crisis(lf_result.line_loading_pct, v_eff)

        # 13b. Blackout / frequency-collapse fail state — track consecutive
        # sim-seconds pinned at the F_MIN/F_MAX hard clamp. Held during the
        # landing freeze, same as the frequency update itself above.
        self._update_blackout_state(0.0 if freeze_active else dt_sim_seconds)

        # 14. Performance counters
        self._total_ticks += 1
        if abs(self._frequency.frequency_hz - F_NOMINAL) <= F_IN_BOUNDS_TOL:
            self._ticks_in_bounds += 1
        max_load = max(lf_result.line_loading_pct.values(), default=0.0)
        self._max_line_loading = max(self._max_line_loading, max_load)
        min_v = min(v_eff.values(), default=1.0)
        self._min_voltage = min(self._min_voltage, min_v)

        # 15. Snapshot
        self._state = self._build_state(
            sim_hour, lf_result, vr_result, islands, blackout_zones, v_eff,
        )

        # 16. Objective evaluation — after the snapshot, so _eval_condition()
        # reads this tick's state rather than the previous one. Held during
        # the landing freeze so a sustained_s timer can't accrue against a
        # frozen handover state before the player has had a chance to react.
        self._update_fail_conditions(0.0 if freeze_active else dt_sim_seconds)

        if DEBUG_SIMULATION:
            self._print_debug(lf_result, vr_result)

        if _sim_const.SIM_STATE_LOG:
            self._write_sim_state_log()

    def _roll_random_deviations(self, dt_min: float) -> None:
        """
        Random unit deviation — derate and drift trigger rolls, plus
        derate expiry. Runs every tick against every ONLINE dispatchable
        (non-renewable) unit, converting each event type's per-sim-hour
        probability (RANDOM_DERATE_CHANCE_PER_HOUR/RANDOM_DRIFT_CHANCE_PER_HOUR,
        scaled by DIFFICULTY_MULT) into a per-tick probability via
        dt_min/60 so risk accrues continuously through the hour rather
        than only at hour boundaries. See constants.py's UNIT DEVIATION
        section for the full mechanic description.
        """
        derate_chance_per_hour = (_sim_const.RANDOM_DERATE_CHANCE_PER_HOUR
                                   * _sim_const.DIFFICULTY_MULT.get(self._difficulty, 1.0))
        drift_chance_per_hour = (_sim_const.RANDOM_DRIFT_CHANCE_PER_HOUR
                                  * _sim_const.DIFFICULTY_MULT.get(self._difficulty, 1.0))
        derate_p_tick = derate_chance_per_hour * (dt_min / 60.0)
        drift_p_tick = drift_chance_per_hour * (dt_min / 60.0)

        # Derate expiry — decrement first, so a unit whose derate expires
        # this tick is eligible to roll a fresh one the same tick (rare,
        # but no reason to special-case it out).
        if self._random_derate_remaining_min:
            for _label in list(self._random_derate_remaining_min):
                remaining = self._random_derate_remaining_min[_label] - dt_min
                if remaining <= 0.0:
                    del self._random_derate_remaining_min[_label]
                    self._fleet.clear_unit_derate(_label)
                else:
                    self._random_derate_remaining_min[_label] = remaining

        if derate_p_tick <= 0.0 and drift_p_tick <= 0.0:
            return

        for label in self._fleet.online_dispatchable_labels():
            unit = self._fleet.get_unit(label)

            if (derate_p_tick > 0.0 and not unit.is_derated
                    and self._deviation_rng.random() < derate_p_tick):
                self._trigger_random_derate(label)
                continue  # one event per unit per tick

            if (drift_p_tick > 0.0 and not unit.is_drifting
                    and self._deviation_rng.random() < drift_p_tick):
                self._trigger_random_drift(label, unit.target_mw)

    def _trigger_random_derate(self, label: str) -> None:
        """
        Start a random capacity derate on the named unit: pick a magnitude
        and duration, apply via FleetModel.derate_unit(), track expiry,
        and raise an INFO alarm naming the unit and an in-fiction reason —
        the player is told WHAT happened but must still notice the
        practical ceiling themselves (see constants.py's UNIT DEVIATION
        section for the full rationale).
        """
        rated_mw = self._unit_rated_mw_by_label.get(label, 0.0)
        pct = self._deviation_rng.uniform(
            _sim_const.RANDOM_DERATE_PCT_MIN, _sim_const.RANDOM_DERATE_PCT_MAX)
        cap_mw = rated_mw * (1.0 - pct / 100.0)
        duration_h = self._deviation_rng.uniform(
            _sim_const.RANDOM_DERATE_DURATION_H_MIN, _sim_const.RANDOM_DERATE_DURATION_H_MAX)

        self._fleet.derate_unit(label, cap_mw)
        self._random_derate_remaining_min[label] = duration_h * 60.0
        self._derate_events += 1

        reason = self._pick_derate_reason(label)
        self._raise_alarm(
            priority='INFO',
            message=f'{label} — capacity reduced',
            element_label=label,
            detail=f'{label}: {reason} (capped near {cap_mw:.0f} MW).',
        )

    def _trigger_random_drift(self, label: str, target_mw: float) -> None:
        """
        Start a random setpoint drift on the named unit: pick a magnitude
        and direction, apply via FleetModel.drift_unit(). No alarm — the
        player must notice the Target/Output mismatch themselves (see
        constants.py's UNIT DEVIATION section).
        """
        pct = self._deviation_rng.uniform(
            _sim_const.RANDOM_DRIFT_PCT_MIN, _sim_const.RANDOM_DRIFT_PCT_MAX)
        sign = 1.0 if self._deviation_rng.random() < 0.5 else -1.0
        offset_mw = sign * target_mw * (pct / 100.0)

        self._fleet.drift_unit(label, offset_mw)
        self._drift_events += 1

    def _pick_derate_reason(self, label: str) -> str:
        """Sample an in-fiction derate reason from the pool matching the
        unit's type, via the deviation RNG (reproducible per shift replay)."""
        unit_type = self._unit_type_by_label.get(label, '')
        pool = {
            'COAL':    _sim_const.RANDOM_DERATE_REASONS_COAL,
            'NUCLEAR': _sim_const.RANDOM_DERATE_REASONS_NUCLEAR,
            'CCGT':    _sim_const.RANDOM_DERATE_REASONS_CCGT,
            'HYDRO':   _sim_const.RANDOM_DERATE_REASONS_HYDRO,
        }.get(unit_type, _sim_const.RANDOM_DERATE_REASONS_COAL)
        idx = int(self._deviation_rng.integers(0, len(pool)))
        return pool[idx]

    def _apply_hourly_schedule(self, sim_hour: float) -> None:
        """
        Advance every AUTO-mode unit's target to its Phase 1 planned MW
        whenever sim_hour crosses a PLANNING_STEP_HOURS boundary (schedules
        are keyed at that same step, 0.0-23.0 by default — see
        gameplay/phase1.py), and clear every unit's active setpoint drift
        fleet-wide at that same crossing (see UnitModel.drift()/
        FleetModel.clear_all_drifts()) — drift never persists across a
        schedule boundary regardless of whether this shift has a Phase 1
        schedule at all, so the boundary-crossing detection below always
        runs even when self._hourly_schedule is empty (shifts without a
        planning phase); only the schedule application itself is
        conditional on a plan existing. This makes drift-clearing itself
        run at PLANNING_STEP_HOURS cadence campaign-wide (every shift, not
        just planning-enabled ones) — a single unified boundary-crossing
        concept, not two independently-tuned timers.

        hour_key is snapped to the nearest PLANNING_STEP_HOURS grid point
        (not floored) since sim_hour accumulates continuously from
        tick-driven float addition and will essentially never land exactly
        on a grid point — nearest-neighbour rounding resolves the boundary
        the moment sim_hour gets close, same tolerance the old int()-floor
        version implicitly had at hourly granularity.
        """
        steps_per_hour = 1.0 / _sim_const.PLANNING_STEP_HOURS
        hour_key = round(sim_hour * steps_per_hour) / steps_per_hour % 24.0
        hour_key = round(hour_key, 10)
        if hour_key == self._last_dispatch_hour:
            return
        self._last_dispatch_hour = hour_key
        self._fleet.clear_all_drifts()
        if self._hourly_schedule:
            self._fleet.apply_hourly_schedule(hour_key, self._hourly_schedule)

    # ─────── PUBLIC INTERFACE ─────────────────────────────────────────────

    def get_state(self) -> SimulationState:
        return self._state

    def is_shift_complete(self) -> bool:
        return self._shift_failed or self._sim_time_min >= self._duration_minutes

    def is_shift_failed(self) -> bool:
        """True if the shift ended early, either because frequency stayed
        pinned at the F_MIN/F_MAX hard clamp for BLACKOUT_TRIP_S (a real
        blackout) or because a FAIL_CONDITION was met. Distinct from reaching
        the shift's scheduled end time. See get_failed_objective() to tell
        the two apart."""
        return self._shift_failed

    def set_unit_target(self, unit_label: str, target_mw: float) -> bool:
        return self._fleet.set_unit_target(unit_label, target_mw)

    def set_unit_auto_mode(self, unit_label: str) -> bool:
        """Return a unit to AUTO dispatch mode (follows its Phase 1 hourly schedule)."""
        return self._fleet.set_unit_auto_mode(unit_label)

    def get_unit_dispatch_mode(self, unit_label: str) -> str:
        """Return a unit's dispatch mode: 'AUTO' or 'MANUAL'."""
        return self._fleet.get_unit_dispatch_mode(unit_label)

    def has_hourly_schedule(self, unit_label: str) -> bool:
        """True if this shift has a Phase 1 plan covering unit_label (AUTO mode is meaningful)."""
        return bool(self._hourly_schedule) and unit_label in self._hourly_schedule

    def start_unit(self, unit_label: str) -> bool:
        return self._fleet.start_unit(unit_label)

    def stop_unit(self, unit_label: str) -> bool:
        return self._fleet.stop_unit(unit_label)

    def set_agc_excluded_units(self, labels) -> None:
        """
        Exclude the named units from AGC eligibility regardless of type —
        the AGC_EXCLUDE_UNITS scripted action's effect. Pass an empty
        iterable to restore all units to normal type-based eligibility.
        """
        self._fleet.set_agc_excluded_units(labels)

    def set_unit_q_target(self, unit_label: str, q_target_mvar: float) -> bool:
        """Set a generator's reactive-power target (MVAr). Manual lever #1."""
        return self._fleet.set_unit_q_target(unit_label, q_target_mvar)

    def set_svc_setpoint(self, bus_label: str, q_mvar: float) -> bool:
        """Set a bus's manual SVC MVAr setpoint. Manual lever #2. False if no SVC there."""
        return self._reactive.set_svc_setpoint(bus_label, q_mvar)

    def seed_default_reactive_devices(self, substation_types: dict[str, str]) -> None:
        """
        Disabled by design: automatic shunt banks and the manual SVC used to
        be seeded here (driven by each load bus's substation type), but that
        let a device auto-correct reactive deficits the player was meant to
        fix by hand via a generation unit's Q (AVR) setpoint. Reactive
        compensation is now entirely a manual generator-setpoint lever — see
        GridSimulation.set_unit_q_target(). No-op, kept as a no-arg-shape
        stub so call sites need no changes.

        Args:
            substation_types: {bus_label: 'INDUSTRIAL'|'RESIDENTIAL'|'MIXED'}
        """
        return

    def resize_shunt_bank(self, bus_label: str, max_steps: int | None = None,
                          mvar_per_step: float | None = None,
                          initial_step: int | None = None) -> bool:
        """
        Resize an existing automatic shunt bank at a bus (e.g. undersized so
        it cannot fully compensate a sag alone and a manual SVC is genuinely
        needed). No-op (returns False) if the bus has no shunt bank. Called
        after seed_default_reactive_devices(); unspecified args keep the
        bank's current value. initial_step pre-engages the bank (e.g. already
        at its ceiling at handover, consistent with "the automatic has been
        holding routine drift" rather than starting from an unregulated
        raw-solve tick before it first switches).
        """
        from simulation.reactive_devices import ShuntBank

        bank = self._reactive._shunt_banks.get(bus_label)
        if bank is None:
            return False
        self._reactive.add_shunt_bank(ShuntBank(
            bus=bus_label,
            mvar_per_step=bank.mvar_per_step if mvar_per_step is None else mvar_per_step,
            max_steps=bank.max_steps if max_steps is None else max_steps,
            step=bank.step if initial_step is None else initial_step,
        ))
        return True

    def set_pumped_storage_mode(self, station_label: str, mode: str) -> bool:
        return False  # deferred to Shift 8 mechanics

    def _start_reclose_cooldown(self, line_label: str) -> None:
        """
        Arm the reclose cooldown for a line after ANY switch (trip or
        close, manual or automatic). Looked up by the line's voltage_kv
        against _sim_const.LINE_RECLOSE_COOLDOWN_S_BY_DIFFICULTY[self._difficulty]
        — scales with the trainee/standard/dispatcher difficulty selection
        (same keys as DIFFICULTY_MULT), not per-shift — every shift gets
        this procedural constraint automatically. A difficulty or voltage
        tier absent from the table falls back to LINE_RECLOSE_COOLDOWN_DEFAULT_S
        (no cooldown) — see constants.py. Symmetric: arms on every switch
        in either direction, so the next switch of any kind on this line
        is blocked until it elapses.
        """
        voltage_kv = self._line_voltage_kv.get(line_label)
        cooldown_table = _sim_const.LINE_RECLOSE_COOLDOWN_S_BY_DIFFICULTY.get(self._difficulty, {})
        cooldown_s = cooldown_table.get(voltage_kv, _sim_const.LINE_RECLOSE_COOLDOWN_DEFAULT_S)
        if cooldown_s > 0.0:
            self._reclose_cooldown_remaining[line_label] = cooldown_s

    def _reclose_cooldown_active(self, line_label: str) -> bool:
        return self._reclose_cooldown_remaining.get(line_label, 0.0) > 0.0

    def trip_line(self, line_label: str) -> bool:
        if not self._line_in_service.get(line_label, False):
            return False
        if self._reclose_cooldown_active(line_label):
            self._raise_alarm(
                priority='WARNING',
                message=f'Line {line_label} switch blocked — cooldown active',
                element_label=line_label,
                detail=(f'Line {line_label} switched too recently. Wait for the '
                        f'reclose cooldown to clear before switching it again.'),
            )
            return False
        self._line_in_service[line_label] = False
        self._start_reclose_cooldown(line_label)
        in_service = self._get_in_service_lines()
        self._loadflow.rebuild(in_service)
        self._voltage.rebuild(in_service)
        self._raise_alarm(
            priority='INFO',
            message=f'Line {line_label} opened manually',
            element_label=line_label,
            detail=f'Operator manually opened line {line_label}.',
        )
        self._trip_isolated_units(in_service)
        return True

    def close_line(self, line_label: str) -> bool:
        if self._line_in_service.get(line_label, True):
            return False
        if self._reclose_cooldown_active(line_label):
            self._raise_alarm(
                priority='WARNING',
                message=f'Line {line_label} reclose blocked — cooldown active',
                element_label=line_label,
                detail=(f'Line {line_label} switched too recently. Wait for the '
                        f'reclose cooldown to clear before closing it.'),
            )
            return False
        self._line_in_service[line_label] = True
        self._start_reclose_cooldown(line_label)
        in_service = self._get_in_service_lines()
        self._loadflow.rebuild(in_service)
        self._voltage.rebuild(in_service)
        self._raise_alarm(
            priority='INFO',
            message=f'Line {line_label} closed manually',
            element_label=line_label,
            detail=f'Operator re-energised line {line_label}.',
        )
        return True

    def shed_load(self, bus_label: str, fraction: float) -> bool:
        result = self._demand.shed_load(bus_label, fraction)
        if result:
            self._load_shed_events += 1
            self._raise_alarm(
                priority='INFO',
                message=f'Load shed at {bus_label}: {fraction*100:.0f}%',
                element_label=bus_label,
                detail=(f'Operator shed {fraction*100:.0f}% of load at '
                        f'substation {bus_label}.'),
            )
        return result

    def clear_shed(self, bus_label: str) -> bool:
        """
        Restore all shed load at a bus.

        The counterpart to shed_load() — shedding is a reversible emergency
        tool, not a one-way door. Deliberately does NOT decrement
        _load_shed_events: the shed still happened and still counts against
        the shift's security score.
        """
        if self._demand.get_shed_fraction(bus_label) <= 0.0:
            return False
        result = self._demand.clear_shed(bus_label)
        if result:
            self._raise_alarm(
                priority='INFO',
                message=f'Load restored at {bus_label}',
                element_label=bus_label,
                detail=f'Operator restored shed load at substation {bus_label}.',
            )
        return result

    def restore_load(self, bus_label: str, fraction: float) -> bool:
        """
        Restore a fraction of previously shed load at a bus — the
        incremental counterpart to shed_load(). Unlike clear_shed()
        (restores everything at once, used by the LOAD_RESTORE scripted
        event), this only steps the shed fraction down by `fraction`,
        floored at 0.0. Deliberately does NOT decrement _load_shed_events:
        the shed still happened and still counts against the shift's
        security score.
        """
        result = self._demand.restore_load(bus_label, fraction)
        if result:
            self._raise_alarm(
                priority='INFO',
                message=f'Load restored at {bus_label}: {fraction*100:.0f}%',
                element_label=bus_label,
                detail=(f'Operator restored {fraction*100:.0f}% of load at '
                        f'substation {bus_label}.'),
            )
        return result

    def get_shed_fraction(self, bus_label: str) -> float:
        """Current shed fraction (0.0-1.0) at a bus — 0.0 if not a load bus."""
        return self._demand.get_shed_fraction(bus_label)

    def acknowledge_alarm(self, alarm_id: int) -> bool:
        for alarm in self._alarms:
            if alarm.alarm_id == alarm_id and not alarm.acknowledged:
                alarm.acknowledged = True
                self._refresh_crisis()
                return True
        return False

    def acknowledge_all_alarms(self) -> int:
        count = sum(1 for a in self._alarms if not a.acknowledged)
        for alarm in self._alarms:
            alarm.acknowledged = True
        self._refresh_crisis()
        return count

    def set_interconnector_schedule(
        self,
        interconnector_label: str,
        schedule_mw: float,
    ) -> bool:
        if interconnector_label == 'INTC-N':
            cap = INTC_N_CAPACITY_MW
        elif interconnector_label == 'INTC-S':
            cap = INTC_S_CAPACITY_MW
        else:
            return False
        self._intc_schedule[interconnector_label] = float(
            np.clip(schedule_mw, -cap, cap)
        )
        return True

    # ─────── FORECAST MODE ────────────────────────────────────────────────

    def run_forecast_mode(
        self,
        schedule: dict,
        start_hour: float,
        duration_hours: float,
    ) -> ForecastResult:
        """
        Fast deterministic evaluation of a proposed schedule.
        No stochastic noise, no cascade, no scripted events.
        Steps at 1-minute resolution.
        """
        peak_demand_mw = load_shift_config(self._shift_number)['peak_demand_mw']
        fleet_fc  = FleetModel(self._grid, schedule)
        demand_fc = DemandModel(peak_demand_mw)
        renew_fc  = RenewablesModel(self._grid)
        lf_fc     = DCLoadFlow(self._grid)
        vt_fc     = VoltageModel(self._grid)

        dt_s  = 60.0
        steps = int(duration_hours * 3600 / dt_s)

        gen_stack:     dict  = {}
        reserve_hours: dict  = {}
        cong_risk:     dict  = {}
        volt_risk:     dict  = {}
        cost:          float = 0.0

        COST_MAP = {
            'COAL':      45.0,
            'CCGT':      55.0,
            'NUCLEAR':   12.0,
            'HYDRO':      5.0,
            'HYDRO_PUMP': 5.0,
            'HYDRO_ROR':  5.0,
            'WIND':       0.0,
            'SOLAR':      0.0,
        }

        for step in range(steps):
            hour = start_hour + step * dt_s / 3600.0

            demand_fc.update(hour, fleet_fc.total_generation_mw())
            for lbl, mw in renew_fc.update(hour, dt_s, deterministic=True).items():
                fleet_fc.set_renewable_output(lbl, mw)
            fleet_fc.tick(dt_s)

            p_inj = {b.label: 0.0 for b in self._grid.get_active_buses()}
            for bus_label, mw in fleet_fc.p_injections().items():
                p_inj[bus_label] = p_inj.get(bus_label, 0.0) + mw
            for bus_label, mw in demand_fc.p_load_injections().items():
                p_inj[bus_label] = p_inj.get(bus_label, 0.0) + mw

            q_inj = {b.label: 0.0 for b in self._grid.get_active_buses()}
            for bus_label, mvar in demand_fc.q_load_injections().items():
                q_inj[bus_label] = q_inj.get(bus_label, 0.0) + mvar

            lf_r = lf_fc.solve(p_inj)
            vt_r = vt_fc.solve(q_inj)

            h_key = round(hour, 2)
            if h_key not in gen_stack:
                stack: dict = {}
                for u in self._grid.get_active_units():
                    um = fleet_fc._units.get(u.label)
                    if um and um.state == 'ONLINE':
                        stack[u.unit_type] = (
                            stack.get(u.unit_type, 0.0) + um.current_mw
                        )
                gen_stack[h_key]     = stack
                reserve_hours[h_key] = fleet_fc.spinning_reserve_mw()
                for utype, mw in stack.items():
                    cost += mw * COST_MAP.get(utype, 0.0) * (dt_s / 3600.0)

            for lbl, pct in lf_r.line_loading_pct.items():
                cong_risk[lbl] = max(cong_risk.get(lbl, 0.0), pct)
            for blbl, v in vt_r.bus_voltages.items():
                volt_risk[blbl] = min(volt_risk.get(blbl, 1.0), v)

        # Risk hour classification
        peak_demand = max(
            demand_fc.forecast_by_hour(
                start_hour, start_hour + duration_hours, step=1.0
            ).values(),
            default=1.0,
        )
        risk_hours = [
            h for h, res in reserve_hours.items()
            if res < 0.08 * peak_demand
        ]

        return ForecastResult(
            generation_stack=gen_stack,
            reserve_by_hour=reserve_hours,
            congestion_risk={k: v for k, v in cong_risk.items()
                             if v > OVERLOAD_WARN_PCT},
            voltage_risk={k: v for k, v in volt_risk.items()
                          if v < 0.92},
            reservoir_end_levels={},
            estimated_cost_eur=cost,
            risk_hours=risk_hours,
            congestion_hours={},
        )

    # ─────── INJECTION BUILDERS ───────────────────────────────────────────

    def _build_p_injections(self, blackout_zones: frozenset = frozenset()) -> dict:
        p: dict = {b.label: 0.0 for b in self._grid.get_active_buses()}
        for bus_label, mw in self._fleet.p_injections().items():
            p[bus_label] = p.get(bus_label, 0.0) + mw
        for bus_label, mw in self._demand.p_load_injections().items():
            if bus_label not in blackout_zones:
                p[bus_label] = p.get(bus_label, 0.0) + mw
        # Interconnector schedules folded into slack bus imbalance
        for mw in self._intc_schedule.values():
            p['MDBY'] = p.get('MDBY', 0.0) + mw
        return p

    def _build_q_injections(self, blackout_zones: frozenset = frozenset()) -> dict:
        q_inj  = {b.label: 0.0 for b in self._grid.get_active_buses()}
        for bus_label, mvar in self._demand.q_load_injections().items():
            if bus_label not in blackout_zones:
                q_inj[bus_label] = q_inj.get(bus_label, 0.0) + mvar

        for bus_label, mvar in self._reactive.q_injections().items():
            if bus_label not in blackout_zones:
                q_inj[bus_label] = q_inj.get(bus_label, 0.0) + mvar

        for bus_label, mvar in self._fleet.q_injections().items():
            if bus_label not in blackout_zones:
                q_inj[bus_label] = q_inj.get(bus_label, 0.0) + mvar

        for line in self._get_in_service_lines():
            if not line.length_km:
                continue
            mvar = line.length_km * _line_charging_mvar_per_km(line.voltage_kv)
            for bus_label in (line.from_bus, line.to_bus):
                if bus_label not in blackout_zones and bus_label in q_inj:
                    q_inj[bus_label] += mvar

        return q_inj

    def _q_generated_consumed(self, blackout_zones: frozenset = frozenset()) -> tuple[float, float]:
        """
        Sum every positive Q contribution (generated) and every negative
        contribution (consumed, returned as a positive magnitude) across
        load, reactive devices, generators, and line charging — the same
        four components _build_q_injections() feeds to the voltage solver,
        split by sign instead of net-combined per bus.
        """
        generated = 0.0
        consumed = 0.0
        for mvar in self._demand.q_load_injections().values():
            if mvar >= 0.0:
                generated += mvar
            else:
                consumed += -mvar

        for mvar in self._reactive.q_injections().values():
            if mvar >= 0.0:
                generated += mvar
            else:
                consumed += -mvar

        for mvar in self._fleet.q_injections().values():
            if mvar >= 0.0:
                generated += mvar
            else:
                consumed += -mvar

        for line in self._get_in_service_lines():
            if not line.length_km:
                continue
            mvar = line.length_km * _line_charging_mvar_per_km(line.voltage_kv)
            for bus_label in (line.from_bus, line.to_bus):
                if bus_label not in blackout_zones:
                    generated += mvar

        return generated, consumed

    # ─────── AGC ──────────────────────────────────────────────────────────

    def _apply_agc(self, dt_sim_seconds: float) -> None:
        """
        Distribute a PID AGC correction to fast-response units.

        Reads its six gain/rate/deadband constants live via _sim_const (not
        bare module-level names) so a shift's AGC_SPEED_MULT — scaled onto
        AGC_MAX_RATE_MW_S and AGC_KI together, the pair that actually
        determines how fast AGC can close an error rather than just how it
        shapes the response — takes effect without a GridSimulation restart.
        AGC_KP/AGC_KD are left unscaled (response shape, not overall speed).
        """
        agc_kp            = _sim_const.AGC_KP
        agc_kd            = _sim_const.AGC_KD
        agc_deadband_hz   = _sim_const.AGC_DEADBAND_HZ
        agc_integral_max  = _sim_const.AGC_INTEGRAL_MAX
        speed_mult        = _sim_const.AGC_SPEED_MULT
        agc_ki            = _sim_const.AGC_KI * speed_mult
        agc_max_rate_mw_s = _sim_const.AGC_MAX_RATE_MW_S * speed_mult

        delta_f = self._frequency.frequency_hz - F_NOMINAL
        if abs(delta_f) <= agc_deadband_hz:
            self._agc_integral = 0.0
            self._agc_prev_delta_f = 0.0
            self._agc_saturated = False
            return

        self._agc_integral += delta_f * dt_sim_seconds
        self._agc_integral = float(np.clip(self._agc_integral, -agc_integral_max, agc_integral_max))
        d_delta_f = (
            (delta_f - self._agc_prev_delta_f) / dt_sim_seconds
            if dt_sim_seconds > 0.0 else 0.0
        )
        self._agc_prev_delta_f = delta_f

        p_term = agc_kp * delta_f
        i_term = agc_ki * self._agc_integral
        d_term = agc_kd * d_delta_f
        raw_delta_mw = -(p_term + i_term + d_term)
        max_delta = agc_max_rate_mw_s * dt_sim_seconds
        agc_delta_mw = float(np.clip(raw_delta_mw, -max_delta, max_delta))

        unit_targets = self._fleet.apply_agc_signal(agc_delta_mw)

        was_saturated = self._agc_saturated
        self._agc_saturated = not unit_targets and abs(agc_delta_mw) > 0.0
        if self._agc_saturated and not was_saturated:
            eligible_str = '/'.join(sorted(_sim_const.AGC_ELIGIBLE_TYPES))
            self._raise_alarm(
                priority='WARNING',
                message='AGC regulation exhausted — no headroom available',
                element_label=None,
                detail=(f'AGC requested {agc_delta_mw:+.1f} MW but no eligible unit '
                        f'({eligible_str}) has headroom. Manual dispatch required.'),
            )

        if _sim_const.AGC_LOG:
            self._write_agc_log(
                delta_f, p_term, i_term, d_term,
                raw_delta_mw, agc_delta_mw, unit_targets,
                agc_kp, agc_ki, agc_kd, agc_max_rate_mw_s, agc_deadband_hz,
            )

    def _reset_log_files(self) -> None:
        """
        Truncate/recreate logs/agc_log.csv and logs/sim_state.csv for this
        shift run, independent of whether AGC_LOG/SIM_STATE_LOG end up
        writing any per-tick data (AGC may never fire if AGC is off all
        shift; SIM_STATE_LOG may be False). Without this, a run that never
        reaches either log's lazy first-write leaves the *previous* run's
        file completely untouched — silently stale, with nothing marking
        it as not belonging to this shift.
        """
        agc_eligible = sorted(
            u.label for u in self._grid.get_active_units()
            if u.unit_type in _sim_const.AGC_ELIGIBLE_TYPES
        )
        self._open_agc_log(agc_eligible)
        self._open_sim_state_log()   # called after _solve_and_snapshot(), self._state is set

    def _open_agc_log(self, unit_labels) -> None:
        """(Re)create logs/agc_log.csv and write its header. unit_labels is
        the set of unit labels the per-unit target_mw columns will cover."""
        log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, 'agc_log.csv')
        self._agc_log_file = open(path, 'w', newline='')
        self._agc_log_writer = csv.writer(self._agc_log_file)
        self._agc_log_headers = [f'unit_{lbl}_target_mw' for lbl in sorted(unit_labels)]
        self._agc_log_writer.writerow([
            'sim_time_min', 'frequency_hz', 'target_hz', 'delta_f_hz',
            'p_term_mw', 'i_term_mw', 'd_term_mw',
            'raw_delta_mw', 'agc_delta_mw',
            'kp', 'ki', 'kd', 'max_rate_mw_s', 'deadband_hz',
            *self._agc_log_headers,
        ])
        self._agc_log_file.flush()

    def _write_agc_log(
        self,
        delta_f: float,
        p_term: float,
        i_term: float,
        d_term: float,
        raw_delta_mw: float,
        agc_delta_mw: float,
        unit_targets: dict,
        agc_kp: float,
        agc_ki: float,
        agc_kd: float,
        agc_max_rate_mw_s: float,
        agc_deadband_hz: float,
    ) -> None:
        if self._agc_log_file is None:
            self._open_agc_log(unit_targets.keys())
        elif set(unit_targets) - {
            col[len('unit_'):-len('_target_mw')] for col in self._agc_log_headers
        }:
            # A unit not covered by the header written at construction time
            # (e.g. became AGC-eligible mid-shift) — reopen with the full
            # column set rather than silently dropping it from the row.
            self._open_agc_log(unit_targets.keys())
        unit_vals = []
        for col in self._agc_log_headers:
            lbl = col[len('unit_'):-len('_target_mw')]
            val = unit_targets.get(lbl)
            unit_vals.append(f'{val:.2f}' if val is not None else '')
        self._agc_log_writer.writerow([
            f'{self._sim_time_min:.4f}',
            f'{self._frequency.frequency_hz:.6f}',
            f'{F_NOMINAL:.1f}',
            f'{delta_f:.6f}',
            f'{p_term:.4f}', f'{i_term:.4f}', f'{d_term:.4f}',
            f'{raw_delta_mw:.4f}', f'{agc_delta_mw:.4f}',
            agc_kp, agc_ki, agc_kd, agc_max_rate_mw_s, agc_deadband_hz,
            *unit_vals,
        ])
        self._agc_log_flush_counter += 1
        if self._agc_log_flush_counter >= 10:
            self._agc_log_file.flush()
            self._agc_log_flush_counter = 0

    def _open_sim_state_log(self) -> None:
        """(Re)create logs/sim_state.csv and write its header, using the
        bus/unit labels from the current state snapshot."""
        state = self._state
        log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, os.path.basename(_sim_const.SIM_STATE_LOG_PATH))
        self._state_log_file = open(path, 'w', newline='')
        self._state_log_writer = csv.writer(self._state_log_file)
        self._state_log_bus_labels = sorted(state.bus_voltages)
        self._state_log_unit_labels = sorted(state.unit_outputs_mw)

        header = ['sim_time_min', 'sim_hour', 'frequency_hz',
                  'total_generation_mw', 'total_load_mw', 'net_imbalance_mw']
        for bus in self._state_log_bus_labels:
            header += [f'bus_{bus}_voltage_pu', f'bus_{bus}_vsi_tier',
                       f'bus_{bus}_q_injection_mvar', f'bus_{bus}_shunt_step',
                       f'bus_{bus}_shunt_mvar', f'bus_{bus}_svc_mvar']
        for unit in self._state_log_unit_labels:
            header += [f'unit_{unit}_output_mw', f'unit_{unit}_target_mw',
                       f'unit_{unit}_q_injection_mvar', f'unit_{unit}_q_target_mvar',
                       f'unit_{unit}_q_reserve_mvar']
        self._state_log_writer.writerow(header)
        self._state_log_file.flush()

    def _write_sim_state_log(self) -> None:
        """
        Write one CSV row of the full per-tick SimulationState snapshot —
        every bus's voltage/reactive state and every unit's dispatch/AVR/Q
        state — to logs/sim_state.csv. Gated by SIM_STATE_LOG (see
        constants.py); a debugging aid for tuning voltage/reactive shifts
        without hand-estimating network behaviour.
        """
        state = self._state
        if self._state_log_file is None:
            self._open_sim_state_log()

        row = [
            f'{state.sim_time_min:.4f}', f'{state.sim_hour:.4f}',
            f'{state.frequency_hz:.6f}',
            f'{state.total_generation_mw:.2f}', f'{state.total_load_mw:.2f}',
            f'{state.net_imbalance_mw:.2f}',
        ]
        for bus in self._state_log_bus_labels:
            row += [
                f'{state.bus_voltages.get(bus, 0.0):.4f}',
                state.bus_vsi_tier.get(bus, ''),
                f'{state.bus_q_injection_mvar.get(bus, 0.0):.2f}',
                state.bus_shunt_step.get(bus, ''),
                f'{state.bus_shunt_mvar.get(bus, 0.0):.2f}' if bus in state.bus_shunt_mvar else '',
                f'{state.bus_svc_mvar.get(bus, 0.0):.2f}' if bus in state.bus_svc_mvar else '',
            ]
        for unit in self._state_log_unit_labels:
            row += [
                f'{state.unit_outputs_mw.get(unit, 0.0):.2f}',
                f'{state.unit_targets_mw.get(unit, 0.0):.2f}',
                f'{state.unit_q_injections_mvar.get(unit, 0.0):.2f}',
                f'{state.unit_q_target_mvar.get(unit, 0.0):.2f}' if unit in state.unit_q_target_mvar else '',
                f'{state.unit_q_reserve_mvar.get(unit, 0.0):.2f}' if unit in state.unit_q_reserve_mvar else '',
            ]
        self._state_log_writer.writerow(row)

        self._state_log_flush_counter += 1
        if self._state_log_flush_counter >= 10:
            self._state_log_file.flush()
            self._state_log_flush_counter = 0

    def __del__(self) -> None:
        if self._agc_log_file is not None:
            self._agc_log_file.close()
        if self._state_log_file is not None:
            self._state_log_file.close()

    # ─────── TOPOLOGY HELPERS ─────────────────────────────────────────────

    def _get_in_service_lines(self) -> list:
        return [
            l for l in self._grid.get_active_lines()
            if self._line_in_service.get(l.label, True)
        ]

    def _trip_isolated_units(self, in_service: list) -> None:
        """Trip any non-OFFLINE unit whose bus has been cut off from the slack bus."""
        islands = self._cascade.find_islands(self._grid.get_active_buses(), in_service)
        if len(islands) <= 1:
            return
        slack_island = next((isl for isl in islands if self._grid.slack_bus in isl), None)
        if slack_island is None:
            return
        for unit in self._grid.get_active_units():
            if unit.bus_label not in slack_island:
                model = self._fleet._units.get(unit.label)
                if model is not None and model.state != 'OFFLINE':
                    self._fleet.trip_unit(unit.label)
                    self._raise_alarm(
                        priority='CRITICAL',
                        message=f'{unit.label} tripped — isolated from grid',
                        element_label=unit.label,
                        detail=(f'Unit {unit.label} lost grid connection '
                                f'after line trip. Protection relay operated.'),
                    )
                    if self._log:
                        self._log.debug(f'[CASCADE] {unit.label} tripped — isolated '
                                        f'at t={self._sim_time_min:.1f} min')

    def _get_active_generation_buses(self) -> frozenset:
        """Return frozenset of bus labels with at least one ONLINE or SHUTDOWN unit."""
        buses: set[str] = set()
        for unit in self._grid.get_active_units():
            model = self._fleet._units.get(unit.label)
            if model is not None and model.state in ('ONLINE', 'SHUTDOWN'):
                buses.add(unit.bus_label)
        return frozenset(buses)

    def _trip_frequency_runaway_islands(
        self,
        islands: list,
        active_generation_buses: frozenset,
    ) -> bool:
        """
        For each non-slack island with active generation, simulate a short
        frequency step. If frequency would leave [F_TRIP_ISLAND_LOW,
        F_TRIP_ISLAND_HIGH], trip all units in that island.

        Models the under/over-frequency protection relay that operates within
        seconds of islanding when generation has no load path (or vice versa).

        Returns True if any units were tripped (caller should re-detect islands).
        """
        any_tripped = False
        for island in islands:
            if self._grid.slack_bus in island:
                continue
            if not (island & active_generation_buses):
                continue  # no generation — blackout zone, handled elsewhere

            island_gen_mw = 0.0
            island_unit_types: list[tuple[str, float]] = []
            for unit in self._grid.get_active_units():
                if unit.bus_label not in island:
                    continue
                model = self._fleet._units.get(unit.label)
                if model is not None and model.state in ('ONLINE', 'SHUTDOWN'):
                    island_gen_mw += model.current_mw
                    island_unit_types.append((unit.unit_type, model.current_mw))

            if island_gen_mw < 1.0:
                continue

            island_load_mw = sum(
                abs(mw)
                for bus, mw in self._demand.p_load_injections().items()
                if bus in island
            )

            _test_fm = FrequencyModel()
            _test_fm.update(
                dt_sim_seconds=30.0,
                p_generation_mw=island_gen_mw,
                p_load_mw=island_load_mw,
                online_unit_types=island_unit_types,
            )
            test_freq = _test_fm.frequency_hz

            if test_freq >= F_TRIP_ISLAND_HIGH or test_freq <= F_TRIP_ISLAND_LOW:
                for unit in self._grid.get_active_units():
                    if unit.bus_label not in island:
                        continue
                    model = self._fleet._units.get(unit.label)
                    if model is not None and model.state != 'OFFLINE':
                        self._fleet.trip_unit(unit.label)
                        any_tripped = True
                        self._raise_alarm(
                            priority='CRITICAL',
                            message=f'{unit.label} tripped — island freq runaway',
                            element_label=unit.label,
                            detail=(
                                f'Island at {unit.bus_label}: '
                                f'gen={island_gen_mw:.0f} MW '
                                f'load={island_load_mw:.0f} MW '
                                f'→ f={test_freq:.2f} Hz. '
                                f'Over/under-frequency relay operated.'
                            ),
                        )
                        if self._log:
                            self._log.debug(
                                f'[CASCADE] {unit.label} tripped — island freq runaway '
                                f'({test_freq:.2f} Hz) at t={self._sim_time_min:.1f} min'
                            )
        return any_tripped

    # ─────── ALARM MANAGEMENT ─────────────────────────────────────────────

    def _raise_alarm(
        self,
        priority: str,
        message: str,
        element_label: str | None,
        detail: str,
    ) -> None:
        self._alarm_id += 1
        self._alarms.insert(0, Alarm(
            alarm_id=self._alarm_id,
            priority=priority,
            timestamp_min=self._sim_time_min,
            message=message[:ALARM_MESSAGE_MAX_LEN],
            element_label=element_label,
            acknowledged=False,
            detail=detail,
        ))

    def _eval_condition(self, condition: dict) -> bool:
        """
        Evaluate a declarative scripted-event condition against live
        simulation state. See src/data/shift_io.py module docstring for
        the condition schema.
        """
        metric = condition['metric']
        op     = condition['op']
        value  = condition['value']
        target = condition.get('target')

        if metric == 'LINE_LOADING':
            current = self._state.line_loading_pct.get(target, 0.0) if self._state else 0.0
        elif metric == 'VOLTAGE_PU':
            current = self._state.bus_voltages.get(target, 1.0) if self._state else 1.0
        elif metric == 'UNIT_OUTPUT_MW':
            current = self._fleet.get_unit(target).current_mw if self._fleet.has_unit(target) else 0.0
        elif metric == 'UNIT_OUTPUT_MW_SUM':
            current = sum(
                self._fleet.get_unit(lbl).current_mw
                for lbl in condition['targets'] if self._fleet.has_unit(lbl)
            )
        elif metric == 'UNIT_ONLINE':
            current = 1.0 if (self._fleet.has_unit(target)
                               and self._fleet.get_unit(target).state == 'ONLINE') else 0.0
        elif metric == 'SPINNING_RESERVE_MW':
            current = self._fleet.spinning_reserve_mw()
        elif metric == 'FREQUENCY_HZ':
            current = self._frequency.frequency_hz
        elif metric == 'TIME_MIN':
            current = self._sim_time_min
        else:
            raise ValueError(f"Unknown condition metric: {metric!r}")

        if op == '<':   return current <  value
        if op == '<=':  return current <= value
        if op == '>':   return current >  value
        if op == '>=':  return current >= value
        if op == '==':  return current == value
        if op == '!=':  return current != value
        raise ValueError(f"Unknown condition op: {op!r}")

    def _execute_action(self, action: dict) -> None:
        """Execute a declarative scripted-event action. See shift_io.py."""
        action_type = action['type']
        if action_type == 'LINE_OPEN':
            self.trip_line(action['line'])
        elif action_type == 'LINE_CLOSE':
            self.close_line(action['line'])
        elif action_type == 'UNIT_TRIP':
            label = action['unit']
            if self._fleet.has_unit(label):
                self._fleet.get_unit(label).trip()
        elif action_type == 'UNIT_DERATE':
            label = action['unit']
            if self._fleet.has_unit(label):
                self._fleet.derate_unit(label, action['cap_mw'])
        elif action_type == 'DEMAND_OVERRIDE':
            schedule = {float(h): mw for h, mw in action['schedule'].items()}
            sim_hour = self._start_hour + self._sim_time_min / 60.0
            self._demand.set_demand_override(schedule, sim_hour)
        elif action_type == 'LOAD_SHED':
            # fraction defaults to LOAD_SHED_STEP_FRACTION so an event can just
            # name a bus. Omit 'fraction' for a standard block, or give one
            # explicitly for a deeper cut.
            self.shed_load(action['bus'],
                           float(action.get('fraction', LOAD_SHED_STEP_FRACTION)))
        elif action_type == 'LOAD_RESTORE':
            self.clear_shed(action['bus'])
        elif action_type == 'AGC_SET':
            # Mirrors main.py's Ctrl+A debug toggle — AGC_ENABLED is a
            # runtime-mutable module global, not per-instance state.
            _sim_const.AGC_ENABLED = bool(action['enabled'])
        elif action_type == 'AGC_EXCLUDE_UNITS':
            # Excludes specific named units from AGC eligibility regardless
            # of type, on top of the fixed campaign-wide AGC_ELIGIBLE_TYPES
            # filter — instance state (self._fleet), not a _sim_const
            # global, since this is scoped to one shift run and must reset
            # cleanly between runs. An empty 'units' list restores full
            # eligibility.
            self.set_agc_excluded_units(action.get('units', []))

    def _process_scripted_events(self) -> None:
        """Fire any scripted events whose trigger time has been reached."""
        for evt in self._scripted_events:
            if evt['fired']:
                continue
            if self._sim_time_min < evt['trigger_min']:
                continue
            cond = evt.get('condition')
            if cond is not None and not self._eval_condition(cond):
                evt['fired'] = True  # condition not met — skip, don't retry
                continue
            self._raise_alarm(
                priority=evt['priority'],
                message=evt['message'],
                element_label=evt.get('element'),
                detail=evt.get('detail', ''),
            )
            action = evt.get('action')
            if action is not None:
                self._execute_action(action)
            evt['fired'] = True

    def _update_fail_conditions(self, dt_sim_seconds: float) -> None:
        """
        Evaluate FAIL_CONDITIONS against this tick's state.

        Unlike scripted-event conditions (which sample once at trigger_min and
        never re-arm), these are re-evaluated every tick. A condition with a
        sustained_s must hold continuously for that many simulated seconds —
        its accumulator decays back to 0.0 as soon as it stops holding, so a
        momentary excursion does not end the shift.

        Sets _shift_failed and records the offending condition in
        _failed_objective, which is_shift_complete() then reports.
        """
        if self._shift_failed or not self._fail_conditions:
            return

        for cond in self._fail_conditions:
            if not self._eval_condition(cond):
                cond['held_s'] = 0.0
                continue
            cond['held_s'] += dt_sim_seconds
            if cond['held_s'] >= cond.get('sustained_s', 0.0):
                self._shift_failed     = True
                self._failed_objective = cond
                self._raise_alarm(
                    priority='CRITICAL',
                    message=cond.get('message', 'Shift failed — operating limit breached'),
                    element_label=cond.get('target'),
                    detail=cond.get('detail', ''),
                )
                return

    def evaluate_win_conditions(self) -> tuple[bool, list[dict]]:
        """
        Evaluate WIN_CONDITIONS once, at shift end.

        Returns (all_met, unmet) — unmet is the list of condition dicts that
        did not hold. A shift with no WIN_CONDITIONS trivially returns
        (True, []), preserving today's behaviour for every existing shift.
        """
        unmet = [c for c in self._win_conditions if not self._eval_condition(c)]
        return (not unmet), unmet

    def get_failed_objective(self) -> dict | None:
        """The FAIL_CONDITION that ended the shift, or None (blackout/clock end)."""
        return self._failed_objective

    def _update_loading_alarms(self, loading: dict) -> None:
        for lbl, pct in loading.items():
            if pct >= OVERLOAD_CRIT_PCT and lbl not in self._seen_crit:
                self._seen_crit.add(lbl)
                self._seen_warn.discard(lbl)
                self._raise_alarm(
                    priority='CRITICAL',
                    message=f'Line {lbl} loading {pct:.0f}% — overload',
                    element_label=lbl,
                    detail=(f'Line {lbl} at {pct:.1f}% loading. '
                            f'Protection trips in {_TRIP_DELAY_REAL_S:.0f}s if sustained.'),
                )
            elif (pct >= OVERLOAD_WARN_PCT
                  and lbl not in self._seen_warn
                  and lbl not in self._seen_crit):
                self._seen_warn.add(lbl)
                self._raise_alarm(
                    priority='WARNING',
                    message=f'Line {lbl} loading {pct:.0f}% — high load',
                    element_label=lbl,
                    detail=f'Line {lbl} at {pct:.1f}% loading — approaching limit.',
                )
            elif pct < OVERLOAD_WARN_PCT:
                self._seen_warn.discard(lbl)
                self._seen_crit.discard(lbl)

    # ─────── VOLTAGE COLLAPSE OVERLAY ──────────────────────────────────────

    def _apply_collapse_acceleration(self, solved_v: dict, dt_sim_seconds: float) -> dict:
        """
        Stateful post-solve overlay: buses sustained below V_WARNING_LOW
        accelerate downward (nonlinear in severity); buses at or above it
        decay their offset back toward 0. Returns {bus_label: v_eff} —
        solved_v + offset, clamped to >= 0. The voltage solver itself stays
        pure; this is the only stateful piece in the voltage path.
        """
        v_eff: dict = {}
        for bus_label, v in solved_v.items():
            offset = self._v_collapse_offset.get(bus_label, 0.0)
            if v < V_WARNING_LOW:
                severity = max(0.0, min(1.0,
                    (V_COLLAPSE_SEVERITY_LOW - v) /
                    (V_COLLAPSE_SEVERITY_LOW - V_COLLAPSE_SEVERITY_FLOOR)
                ))
                accel = severity ** 2 * V_COLLAPSE_GAIN
                offset -= accel * dt_sim_seconds
            else:
                if offset < 0.0:
                    offset = min(0.0, offset + V_COLLAPSE_RECOVERY_PU_S * dt_sim_seconds)
            self._v_collapse_offset[bus_label] = offset
            v_eff[bus_label] = max(0.0, v + offset)
        return v_eff

    def _reset_collapse_offset(self, bus_label: str) -> None:
        """Reset a bus's collapse offset to 0 — called on blackout entry."""
        self._v_collapse_offset[bus_label] = 0.0

    @staticmethod
    def _vsi_tier(v: float) -> str:
        if v < V_CRITICAL_LOW:
            return 'CRITICAL'
        if v < V_WARNING_LOW:
            return 'WARNING'
        if v < V_WATCH_LOW:
            return 'WATCH'
        return 'HEALTHY'

    def _update_voltage_alarms(self, voltages: dict) -> None:
        for bus_label, v in voltages.items():
            if v < V_CRITICAL_LOW:
                if bus_label not in self._seen_v_crit:
                    self._seen_v_crit.add(bus_label)
                    self._seen_v_warn.discard(bus_label)
                    self._raise_alarm(
                        priority='CRITICAL',
                        message=f'Voltage {bus_label} {v:.3f} pu — collapse risk',
                        element_label=bus_label,
                        detail=(f'Bus {bus_label} at {v:.3f} pu — below '
                                f'collapse threshold {V_CRITICAL_LOW} pu.'),
                    )
            elif v < V_WARNING_LOW:
                if bus_label not in self._seen_v_warn and bus_label not in self._seen_v_crit:
                    self._seen_v_warn.add(bus_label)
                    self._raise_alarm(
                        priority='WARNING',
                        message=f'Voltage {bus_label} {v:.3f} pu — low voltage',
                        element_label=bus_label,
                        detail=(f'Bus {bus_label} at {v:.3f} pu — below '
                                f'warning threshold {V_WARNING_LOW} pu.'),
                    )
            else:
                self._seen_v_warn.discard(bus_label)
                self._seen_v_crit.discard(bus_label)

    def _freq_bounds(self) -> tuple[float, float, float, float]:
        """
        Effective (alert_low, alert_high, critical_low, critical_high), scaled
        by _sim_const.FREQ_TOLERANCE_MULT (shift_NN.py's FREQ_TOLERANCE_MULT,
        1.0 by default) around F_NOMINAL. F_MIN/F_MAX (the hard clamp) are
        never scaled — only the alarm/crisis band widens for tutorial shifts.
        """
        mult = _sim_const.FREQ_TOLERANCE_MULT
        return (
            F_NOMINAL - (F_NOMINAL - F_ALERT_LOW) * mult,
            F_NOMINAL + (F_ALERT_HIGH - F_NOMINAL) * mult,
            F_NOMINAL - (F_NOMINAL - F_CRITICAL_LOW) * mult,
            F_NOMINAL + (F_CRITICAL_HIGH - F_NOMINAL) * mult,
        )

    def _update_frequency_alarms(self) -> None:
        f = self._frequency.frequency_hz
        alert_low, alert_high, crit_low, crit_high = self._freq_bounds()
        if f <= crit_low or f >= crit_high:
            new_state = 'CRITICAL'
        elif f <= alert_low or f >= alert_high:
            new_state = 'ALERT'
        else:
            new_state = 'OK'

        if new_state != self._freq_alarm_state:
            if new_state == 'CRITICAL':
                self._raise_alarm(
                    priority='CRITICAL',
                    message=f'Frequency {f:.3f} Hz — critical deviation',
                    element_label=None,
                    detail=f'System frequency {f:.3f} Hz has exceeded the critical threshold.',
                )
            elif new_state == 'ALERT':
                self._raise_alarm(
                    priority='WARNING',
                    message=f'Frequency {f:.3f} Hz — alert threshold',
                    element_label=None,
                    detail=f'System frequency {f:.3f} Hz has deviated beyond the alert band.',
                )
            self._freq_alarm_state = new_state

    def _expire_alarms(self) -> None:
        def _expired(a: Alarm) -> bool:
            if not a.acknowledged:
                return False
            age_min = self._sim_time_min - a.timestamp_min
            if a.priority in ('INFO', 'TUTOR'):
                return age_min > ALARM_FADE_INFO_TUTOR_MIN
            return age_min > ALARM_FADE_CRIT_WARN_MIN

        self._alarms = [a for a in self._alarms if not _expired(a)]

        # Hard backstop: newest-first list (see _raise_alarm's insert(0, ...)), so
        # trimming the tail drops the oldest alarms once the cap is exceeded — keeps
        # draw_alarm_panel's cost bounded even mid-cascade, before ack-based fade
        # above has had a chance to catch up.
        if len(self._alarms) > ALARM_LIST_MAX:
            del self._alarms[ALARM_LIST_MAX:]

    # ─────── CRISIS STATE ─────────────────────────────────────────────────

    def _update_crisis(self, loading: dict, voltages: dict) -> None:
        f        = self._frequency.frequency_hz
        max_load = max(loading.values(), default=0.0)
        min_v    = min(voltages.values(), default=1.0)
        alert_low, alert_high, crit_low, crit_high = self._freq_bounds()

        crisis   = False
        ctype:   str | None = None
        celement: str | None = None

        if f <= crit_low or f >= crit_high:
            crisis, ctype = True, 'CRITICAL'
        elif max_load >= OVERLOAD_CRIT_PCT:
            crisis, ctype = True, 'CRITICAL'
            celement = max(loading, key=loading.get)
        elif min_v < V_CRITICAL_LOW:
            crisis, ctype = True, 'CRITICAL'
            celement = min(voltages, key=voltages.get)
        elif f <= alert_low or f >= alert_high:
            crisis, ctype = True, 'WARNING'
        elif max_load >= OVERLOAD_WARN_PCT:
            crisis, ctype = True, 'WARNING'
            celement = max(loading, key=loading.get)

        self._crisis_active  = crisis
        self._crisis_type    = ctype
        self._crisis_element = celement

    # ─────── BLACKOUT / FREQUENCY-COLLAPSE FAIL STATE ─────────────────────

    def _update_blackout_state(self, dt_sim_seconds: float) -> None:
        """
        Track consecutive sim-seconds spent pinned at the F_MIN/F_MAX hard
        clamp. Resets to 0 the moment frequency is back inside the clamp,
        so a brief spike can't accumulate toward BLACKOUT_TRIP_S across
        separate excursions. Sets self._shift_failed once the threshold is
        exceeded — checked by is_shift_complete().
        """
        f = self._frequency.frequency_hz
        if f <= F_MIN or f >= F_MAX:
            self._blackout_clamp_s += dt_sim_seconds
            if self._blackout_clamp_s >= BLACKOUT_TRIP_S:
                self._shift_failed = True
        else:
            self._blackout_clamp_s = 0.0

    def _refresh_crisis(self) -> None:
        if not any(not a.acknowledged and a.priority == 'CRITICAL'
                   for a in self._alarms):
            self._crisis_active  = False
            self._crisis_type    = None
            self._crisis_element = None

    # ─────── STATE SNAPSHOT ───────────────────────────────────────────────

    def _solve_and_snapshot(self) -> None:
        """Build initial state snapshot at t=0 without advancing time."""
        sim_hour = self._start_hour

        self._demand.update(sim_hour, 0.0)
        for lbl, mw in self._renewables.update(sim_hour, 0.0, deterministic=True).items():
            self._fleet.set_renewable_output(lbl, mw)

        p_inj = self._build_p_injections()
        q_inj = self._build_q_injections()
        lf_r = self._loadflow.solve(p_inj)  # no blackout zones known yet at t=0
        vr_r = self._voltage.solve(q_inj)

        islands = self._cascade.find_islands(
            self._grid.get_active_buses(),
            self._get_in_service_lines(),
        )
        blackout = self._cascade.get_blackout_zones(
            islands, self._get_active_generation_buses()
        )
        self._state = self._build_state(sim_hour, lf_r, vr_r, islands, blackout)

    def _build_state(
        self,
        sim_hour: float,
        lf_result,
        vr_result,
        islands: list,
        blackout_zones: frozenset,
        v_eff: dict | None = None,
    ) -> SimulationState:
        # v_eff is the collapse-overlay-adjusted voltage (see
        # _apply_collapse_acceleration); None only at t=0 init snapshot,
        # before any overlay has run — falls back to the raw solve.
        if v_eff is None:
            v_eff = dict(vr_result.bus_voltages)
        freq    = self._frequency.frequency_hz
        total_gen  = self._fleet.total_generation_mw()
        total_load = self._demand.total_load_mw
        reserve    = self._fleet.spinning_reserve_mw()
        q_generated, q_consumed = self._q_generated_consumed(blackout_zones)
        h_sys      = self._frequency._compute_system_inertia(
            self._fleet.online_unit_types()
        )
        raw_snap = self._fleet.get_state_snapshot()

        # Transpose per-unit dict into per-field dicts for SimulationState
        snap = {
            'states':           {lbl: d['state']          for lbl, d in raw_snap.items()},
            'outputs_mw':       {lbl: d['current_mw']     for lbl, d in raw_snap.items()},
            'targets_mw':       {lbl: d['target_mw']      for lbl, d in raw_snap.items()},
            'q_injections_mvar':{lbl: d['q_mvar']         for lbl, d in raw_snap.items()},
            'start_progress':   {lbl: d['start_progress'] for lbl, d in raw_snap.items()},
            'q_target_mvar':    {lbl: d['q_target_mvar']   for lbl, d in raw_snap.items()},
            'q_reserve_mvar':   {lbl: d['q_reserve_mvar']  for lbl, d in raw_snap.items()},
            'dispatch_mode':    {lbl: d['dispatch_mode']   for lbl, d in raw_snap.items()},
        }

        # Generation mix by fuel type (online units only)
        gen_mix: dict = {}
        for unit in self._grid.get_active_units():
            if snap['states'].get(unit.label) == 'ONLINE':
                gen_mix[unit.unit_type] = (
                    gen_mix.get(unit.unit_type, 0.0)
                    + snap['outputs_mw'].get(unit.label, 0.0)
                )

        # Demand + renewable forecasts — recomputed only when sim_hour integer advances
        end_hour = self._start_hour + self._duration_minutes / 60.0
        cur_hour_int = int(sim_hour)
        if cur_hour_int != self._cached_forecast_hour:
            self._cached_demand_fc    = self._demand.forecast_by_hour(sim_hour, end_hour, step=0.5)
            self._cached_renew_fc     = self._renewables.forecast_by_hour(sim_hour, end_hour, step=0.5)
            self._cached_forecast_hour = cur_hour_int
        demand_fc = self._cached_demand_fc
        renew_fc  = self._cached_renew_fc

        wind_fc:  dict = {}
        solar_fc: dict = {}
        for unit in self._grid.get_active_units():
            if unit.unit_type == 'WIND' and unit.label in renew_fc:
                wind_fc[unit.label] = renew_fc[unit.label]
            elif unit.unit_type == 'SOLAR' and unit.label in renew_fc:
                solar_fc[unit.label] = renew_fc[unit.label]

        freq_in_bounds = (
            self._ticks_in_bounds / self._total_ticks * 100.0
            if self._total_ticks > 0 else 100.0
        )

        agc_cur, agc_min, agc_max = self._fleet.agc_regulation_state()

        line_status = {
            l.label: (
                'IN_SERVICE' if self._line_in_service.get(l.label, True)
                else 'TRIPPED'
            )
            for l in self._grid.get_active_lines()
        }

        # Reactive device state (read-only auto shunt banks, manual SVC)
        shunt_state = self._reactive.get_shunt_state()
        svc_state   = self._reactive.get_svc_state()
        device_q_by_bus = self._reactive.q_injections()

        return SimulationState(
            sim_time_min=self._sim_time_min,
            sim_hour=sim_hour,

            frequency_hz=freq,
            frequency_trend=self._frequency.frequency_trend,
            frequency_deviation_hz=freq - F_NOMINAL,

            total_generation_mw=total_gen,
            total_load_mw=total_load,
            net_imbalance_mw=total_gen - total_load,
            spinning_reserve_mw=reserve,
            system_inertia_h=h_sys,
            losses_mw=self._demand.losses_mw,
            bus_loads={bus: self._demand.get_bus_demand_mw(bus)
                       for bus in self._demand._bus_demand},

            agc_current_mw=agc_cur,
            agc_max_mw=agc_max,
            agc_min_mw=agc_min,
            agc_saturated=self._agc_saturated,

            bus_voltages=dict(v_eff),
            bus_angles=dict(lf_result.bus_angles),
            bus_vsi=dict(v_eff),
            bus_vsi_tier={bus: self._vsi_tier(v) for bus, v in v_eff.items()},

            bus_shunt_step={bus: step for bus, (step, _mvar) in shunt_state.items()},
            bus_shunt_mvar={bus: mvar for bus, (_step, mvar) in shunt_state.items()},
            bus_svc_mvar={bus: q for bus, (q, _qmin, _qmax) in svc_state.items()},
            bus_svc_limits={bus: (qmin, qmax) for bus, (_q, qmin, qmax) in svc_state.items()},
            bus_q_injection_mvar=dict(device_q_by_bus),
            bus_load_q_mvar=self._demand.q_load_injections(),
            total_q_generated_mvar=q_generated,
            total_q_consumed_mvar=q_consumed,

            line_flows_mw=dict(lf_result.line_flows_mw),
            line_loading_pct=dict(lf_result.line_loading_pct),
            line_status=line_status,
            overload_timers={k: v for k, v in self._overload_timers.items()
                             if v > 0.0},

            unit_states=snap['states'],
            unit_outputs_mw=snap['outputs_mw'],
            unit_targets_mw=snap['targets_mw'],
            unit_q_injections_mvar=snap['q_injections_mvar'],
            unit_start_progress=snap['start_progress'],
            unit_maintenance=self._fleet.get_maintenance_units(),
            unit_q_target_mvar=snap['q_target_mvar'],
            unit_q_reserve_mvar=snap['q_reserve_mvar'],
            unit_dispatch_modes=snap['dispatch_mode'],
            unit_has_schedule=frozenset(self._hourly_schedule) if self._hourly_schedule else frozenset(),
            unit_agc_enabled=self._fleet.get_agc_enabled_units(),
            reservoir_levels={},
            pumped_storage_modes={},

            gen_mix_mw=gen_mix,

            demand_forecast_mw=demand_fc,
            wind_forecast_mw=wind_fc,
            solar_forecast_mw=solar_fc,

            active_alarms=list(self._alarms),

            islands=islands,
            blackout_zones=blackout_zones,

            crisis_active=self._crisis_active,
            crisis_type=self._crisis_type,
            crisis_element=self._crisis_element,

            frequency_in_bounds_pct=freq_in_bounds,
            max_line_loading_seen=self._max_line_loading,
            load_shed_events=self._load_shed_events,
            cascade_events=self._cascade_events,
            derate_events=self._derate_events,
            drift_events=self._drift_events,
            min_voltage_seen=self._min_voltage,
        )

    # ─────── DEBUG ────────────────────────────────────────────────────────

    def _print_debug(self, lf_result, vr_result) -> None:
        if not self._log:
            return
        max_load = max(lf_result.line_loading_pct.values(), default=0.0)
        min_v    = min(vr_result.bus_voltages.values(), default=1.0)
        self._log.debug(
            f'[SIM] t={self._sim_time_min:6.2f}min '
            f'f={self._frequency.frequency_hz:.3f}Hz '
            f'gen={self._fleet.total_generation_mw():.0f}MW '
            f'load={self._demand.total_load_mw:.0f}MW '
            f'imb={self._fleet.total_generation_mw()-self._demand.total_load_mw:+.0f}MW '
            f'L_max={max_load:.1f}% '
            f'V_min={min_v:.3f}pu'
        )
