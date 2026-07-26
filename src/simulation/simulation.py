"""
src/simulation/simulation.py

Master simulation loop and SimulationState snapshot for GRIDCOM.

GridSimulation orchestrates all physics modules each tick:
  demand → fleet → frequency+droop+AGC → load flow → voltage → overloads
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

from simulation.constants import (
    F_NOMINAL,
    F_ALERT_LOW, F_ALERT_HIGH,
    F_CRITICAL_LOW, F_CRITICAL_HIGH,
    F_TRIP_ISLAND_HIGH, F_TRIP_ISLAND_LOW,
    F_IN_BOUNDS_TOL,
    OVERLOAD_WARN_PCT, OVERLOAD_CRIT_PCT,
    V_WATCH_LOW, V_WARNING_LOW, V_CRITICAL_LOW,
    V_COLLAPSE_GAIN, V_COLLAPSE_SEVERITY_LOW, V_COLLAPSE_SEVERITY_FLOOR,
    V_COLLAPSE_RECOVERY_PU_S,
    ALARM_MESSAGE_MAX_LEN,
    INTC_N_CAPACITY_MW, INTC_S_CAPACITY_MW,
    DEBUG_SIMULATION, SIM_DEBUG_LOG,
    AGC_KP, AGC_KI, AGC_KD, AGC_MAX_RATE_MW_S, AGC_DEADBAND_HZ, AGC_INTEGRAL_MAX,
    TRIP_DELAY_S, TIME_COMPRESSION,
)
import simulation.constants as _sim_const
from simulation.grid import Grid
from simulation.loadflow import DCLoadFlow
from simulation.voltage import VoltageModel
from simulation.frequency import FrequencyModel
from simulation.units import FleetModel, AGC_UNIT_TYPES
from simulation.demand import DemandModel
from simulation.renewables import RenewablesModel
from simulation.cascade import CascadeModel
from simulation.reactive_devices import ReactiveDevices
from data.profiles import get_substation_demand_specs
from gameplay.shifts.loader import load_shift_config

# Real-seconds equivalent of TRIP_DELAY_S, for alarm text — avoids a hardcoded
# literal going stale if TRIP_DELAY_S is retuned (see CLAUDE.md Rule 1).
_TRIP_DELAY_REAL_S: float = TRIP_DELAY_S / TIME_COMPRESSION


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
    unit_bus_types:          dict
    unit_maintenance:        frozenset   # labels of units on planned maintenance
    unit_v_setpoint_pu:      dict   # {unit_label: float} AVR voltage setpoint
    unit_q_reserve_mvar:     dict   # {unit_label: float} headroom to q_max (0 if not ONLINE)
    unit_dispatch_modes:     dict   # {unit_label: 'AUTO'|'MANUAL'}
    unit_has_schedule:       frozenset   # labels covered by this shift's Phase 1 hourly schedule
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
        grid: Grid,
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
    ) -> None:
        self._grid         = grid
        self._shift_number = shift_number
        self._difficulty   = difficulty

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
        self._renewables = RenewablesModel(grid)
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

        # Simulation time
        self._sim_time_min: float = 0.0

        # Performance counters
        self._ticks_in_bounds:  int   = 0
        self._total_ticks:      int   = 0
        self._max_line_loading: float = 0.0
        self._load_shed_events: int   = 0
        self._cascade_events:   int   = 0
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

    def tick(self, dt_sim_seconds: float) -> None:
        """
        Advance simulation by dt_sim_seconds of simulated time.

        Tick order (per GRID_SIMULATION_MECHANICS.md):
          1.  Advance time
          2.  Update demand
          3.  Update renewable outputs → inject into fleet
          4.  Tick unit state machines (ramp, cold start)
          5.  Frequency update (swing equation) + droop + AGC secondary response
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

        # 1. Advance time
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

        # 5. Frequency update (swing equation)
        self._frequency.update(
            dt_sim_seconds=dt_sim_seconds,
            p_generation_mw=self._fleet.total_generation_mw(),
            p_load_mw=self._demand.total_load_mw,
            online_unit_types=self._fleet.online_unit_types(),
        )

        # 5a. Governor droop — fast primary response, all synchronous units, ahead of AGC.
        if _sim_const.DROOP_ENABLED:
            delta_f = self._frequency.frequency_hz - F_NOMINAL
            self._fleet.apply_droop_response(delta_f)

        # 5b. AGC secondary frequency response
        if _sim_const.AGC_ENABLED:
            self._apply_agc(dt_sim_seconds)

        # 5c. Automatic reactive devices (shunt banks) act on the previous
        # tick's solved voltage — one-tick lag, no algebraic loop with the solver.
        self._reactive.step_automatics(self._prev_bus_voltages, dt_sim_seconds)

        # 6. Build injection vectors (exclude load on buses already blacked out)
        in_service = self._get_in_service_lines()
        _active_gen_buses = self._get_active_generation_buses()
        _islands_pre      = self._cascade.find_islands(self._grid.get_active_buses(), in_service)
        _blackout_pre     = self._cascade.get_blackout_zones(_islands_pre, _active_gen_buses)
        p_injections         = self._build_p_injections(_blackout_pre)
        q_injections, pv_buses = self._build_q_injections(_blackout_pre)

        # 7. DC load flow
        lf_result  = self._loadflow.solve(p_injections)

        # 8. Voltage
        vr_result = self._voltage.solve(q_injections, pv_buses=pv_buses)

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
            vr_result = self._voltage.solve(q_injections, pv_buses=pv_buses)

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

        if DEBUG_SIMULATION:
            self._print_debug(lf_result, vr_result)

        if _sim_const.SIM_STATE_LOG:
            self._write_sim_state_log()

    def _apply_hourly_schedule(self, sim_hour: float) -> None:
        """
        Advance every AUTO-mode unit's target to its Phase 1 planned MW
        whenever sim_hour crosses an integer-hour boundary (schedules are
        keyed by whole hour, 0.0-23.0 — see gameplay/phase1.py). No-op if
        this shift has no hourly_schedule (Shifts without a planning phase).
        """
        if not self._hourly_schedule:
            return
        hour_key = float(int(sim_hour) % 24)
        if hour_key == self._last_dispatch_hour:
            return
        self._last_dispatch_hour = hour_key
        self._fleet.apply_hourly_schedule(hour_key, self._hourly_schedule)

    # ─────── PUBLIC INTERFACE ─────────────────────────────────────────────

    def get_state(self) -> SimulationState:
        return self._state

    def is_shift_complete(self) -> bool:
        return self._sim_time_min >= self._duration_minutes

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

    def set_unit_q_target(self, unit_label: str, q_target_mvar: float) -> bool:
        return self._fleet.set_unit_q_target(unit_label, q_target_mvar)

    def set_generator_voltage_setpoint(self, unit_label: str, v_pu: float) -> bool:
        """Set a generator's AVR voltage setpoint (per-unit). Manual lever #1."""
        return self._fleet.set_unit_voltage_setpoint(unit_label, v_pu)

    def set_svc_setpoint(self, bus_label: str, q_mvar: float) -> bool:
        """Set a bus's manual SVC MVAr setpoint. Manual lever #2. False if no SVC there."""
        return self._reactive.set_svc_setpoint(bus_label, q_mvar)

    def seed_default_reactive_devices(self, substation_types: dict[str, str]) -> None:
        """
        Seed automatic shunt banks and one manual SVC at runtime, driven by
        each load bus's substation type — used by DESIGNER_TEST sessions
        that have no authored device layout in their grid JSON. Industrial
        buses get an automatic shunt bank (heaviest reactive load); a manual
        SVC is placed at the weakest bus with no nearby generation, if one
        can be identified.

        Args:
            substation_types: {bus_label: 'INDUSTRIAL'|'RESIDENTIAL'|'MIXED'}
        """
        from simulation.reactive_devices import ShuntBank, SVC

        load_bus_labels = {b.label for b in self._grid.get_active_buses()
                            if b.bus_type == 'LOAD'}
        gen_bus_labels = {u.bus_label for u in self._grid.get_active_units()}

        for bus_label, sub_type in substation_types.items():
            if bus_label not in load_bus_labels:
                continue
            if sub_type == 'INDUSTRIAL':
                self._reactive.add_shunt_bank(ShuntBank(bus=bus_label))

        # Manual SVC at a load bus with no on-bus generation — a region that
        # can only be supported by a device, not nearby generator setpoints.
        candidates = sorted(load_bus_labels - gen_bus_labels)
        if candidates:
            self._reactive.add_svc(SVC(bus=candidates[0]))

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

    def trip_line(self, line_label: str) -> bool:
        if not self._line_in_service.get(line_label, False):
            return False
        self._line_in_service[line_label] = False
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
        self._line_in_service[line_label] = True
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

            pv = fleet_fc.pv_bus_constraints()
            q_inj = {b.label: 0.0 for b in self._grid.get_active_buses()}
            for bus_label, mvar in demand_fc.q_load_injections().items():
                q_inj[bus_label] = q_inj.get(bus_label, 0.0) + mvar

            lf_r = lf_fc.solve(p_inj)
            vt_r = vt_fc.solve(q_inj, pv_buses=pv)

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

    def _build_q_injections(self, blackout_zones: frozenset = frozenset()) -> tuple:
        q_inj  = {b.label: 0.0 for b in self._grid.get_active_buses()}
        for bus_label, mvar in self._demand.q_load_injections().items():
            if bus_label not in blackout_zones:
                q_inj[bus_label] = q_inj.get(bus_label, 0.0) + mvar

        for bus_label, mvar in self._reactive.q_injections().items():
            if bus_label not in blackout_zones:
                q_inj[bus_label] = q_inj.get(bus_label, 0.0) + mvar

        pv_buses = self._fleet.pv_bus_constraints()
        return q_inj, pv_buses

    # ─────── AGC ──────────────────────────────────────────────────────────

    def _apply_agc(self, dt_sim_seconds: float) -> None:
        """Distribute a PID AGC correction to fast-response units."""
        delta_f = self._frequency.frequency_hz - F_NOMINAL
        if abs(delta_f) <= AGC_DEADBAND_HZ:
            self._agc_integral = 0.0
            self._agc_prev_delta_f = 0.0
            self._agc_saturated = False
            return

        self._agc_integral += delta_f * dt_sim_seconds
        self._agc_integral = float(np.clip(self._agc_integral, -AGC_INTEGRAL_MAX, AGC_INTEGRAL_MAX))
        d_delta_f = (
            (delta_f - self._agc_prev_delta_f) / dt_sim_seconds
            if dt_sim_seconds > 0.0 else 0.0
        )
        self._agc_prev_delta_f = delta_f

        p_term = AGC_KP * delta_f
        i_term = AGC_KI * self._agc_integral
        d_term = AGC_KD * d_delta_f
        raw_delta_mw = -(p_term + i_term + d_term)
        max_delta = AGC_MAX_RATE_MW_S * dt_sim_seconds
        agc_delta_mw = float(np.clip(raw_delta_mw, -max_delta, max_delta))

        unit_targets = self._fleet.apply_agc_signal(agc_delta_mw)

        was_saturated = self._agc_saturated
        self._agc_saturated = not unit_targets and abs(agc_delta_mw) > 0.0
        if self._agc_saturated and not was_saturated:
            self._raise_alarm(
                priority='WARNING',
                message='AGC regulation exhausted — no headroom available',
                element_label=None,
                detail=(f'AGC requested {agc_delta_mw:+.1f} MW but no eligible unit '
                        f'(HYDRO/CCGT) has headroom. Manual dispatch required.'),
            )

        if _sim_const.AGC_LOG:
            self._write_agc_log(
                delta_f, p_term, i_term, d_term,
                raw_delta_mw, agc_delta_mw, unit_targets,
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
            if u.unit_type in AGC_UNIT_TYPES
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
            AGC_KP, AGC_KI, AGC_KD, AGC_MAX_RATE_MW_S, AGC_DEADBAND_HZ,
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
                       f'unit_{unit}_q_injection_mvar', f'unit_{unit}_v_setpoint_pu',
                       f'unit_{unit}_bus_type', f'unit_{unit}_q_reserve_mvar']
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
                f'{state.unit_v_setpoint_pu.get(unit, 0.0):.4f}' if unit in state.unit_v_setpoint_pu else '',
                state.unit_bus_types.get(unit, ''),
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

    def _update_frequency_alarms(self) -> None:
        f = self._frequency.frequency_hz
        if f <= F_CRITICAL_LOW or f >= F_CRITICAL_HIGH:
            new_state = 'CRITICAL'
        elif f <= F_ALERT_LOW or f >= F_ALERT_HIGH:
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
        self._alarms = [
            a for a in self._alarms
            if not (a.acknowledged and a.priority in ('INFO', 'TUTOR')
                    and self._sim_time_min - a.timestamp_min > 60.0)
        ]

    # ─────── CRISIS STATE ─────────────────────────────────────────────────

    def _update_crisis(self, loading: dict, voltages: dict) -> None:
        f        = self._frequency.frequency_hz
        max_load = max(loading.values(), default=0.0)
        min_v    = min(voltages.values(), default=1.0)

        crisis   = False
        ctype:   str | None = None
        celement: str | None = None

        if f <= F_CRITICAL_LOW or f >= F_CRITICAL_HIGH:
            crisis, ctype = True, 'CRITICAL'
        elif max_load >= OVERLOAD_CRIT_PCT:
            crisis, ctype = True, 'CRITICAL'
            celement = max(loading, key=loading.get)
        elif min_v < V_CRITICAL_LOW:
            crisis, ctype = True, 'CRITICAL'
            celement = min(voltages, key=voltages.get)
        elif f <= F_ALERT_LOW or f >= F_ALERT_HIGH:
            crisis, ctype = True, 'WARNING'
        elif max_load >= OVERLOAD_WARN_PCT:
            crisis, ctype = True, 'WARNING'
            celement = max(loading, key=loading.get)

        self._crisis_active  = crisis
        self._crisis_type    = ctype
        self._crisis_element = celement

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

        p_inj          = self._build_p_injections()
        q_inj, pv_buses = self._build_q_injections()
        lf_r = self._loadflow.solve(p_inj)  # no blackout zones known yet at t=0
        vr_r = self._voltage.solve(q_inj, pv_buses=pv_buses)

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
        h_sys      = self._frequency._compute_system_inertia(
            self._fleet.online_unit_types()
        )
        raw_snap = self._fleet.get_state_snapshot()

        # Mark buses that hit Q limit as PQ (from voltage solver result), and
        # reflect the solver's actual per-bus Q (q_injections_used — includes
        # the PV correction pass, which UnitModel.q_injection_mvar never sees)
        # back onto each co-located unit, split evenly like pv_bus_constraints()
        # sums their limits. q_reserve_mvar is recomputed against this real Q.
        for bus_label in vr_result.pq_buses:
            for unit in self._grid.get_units_at_bus(bus_label):
                if unit.label in raw_snap:
                    raw_snap[unit.label]['bus_type'] = 'PQ'
        for bus_label, q_used_mvar in vr_result.q_injections_used.items():
            bus_units = [
                u for u in self._grid.get_units_at_bus(bus_label)
                if u.label in raw_snap and raw_snap[u.label]['state'] == 'ONLINE'
                and not self._fleet.get_unit(u.label).is_renewable
            ]
            if not bus_units:
                continue
            q_share = q_used_mvar / len(bus_units)
            for unit in bus_units:
                raw_snap[unit.label]['q_mvar'] = q_share
                raw_snap[unit.label]['q_reserve_mvar'] = max(
                    0.0, unit.q_max_mvar - q_share
                )

        # Transpose per-unit dict into per-field dicts for SimulationState
        snap = {
            'states':           {lbl: d['state']          for lbl, d in raw_snap.items()},
            'outputs_mw':       {lbl: d['current_mw']     for lbl, d in raw_snap.items()},
            'targets_mw':       {lbl: d['target_mw']      for lbl, d in raw_snap.items()},
            'q_injections_mvar':{lbl: d['q_mvar']         for lbl, d in raw_snap.items()},
            'start_progress':   {lbl: d['start_progress'] for lbl, d in raw_snap.items()},
            'bus_types':        {lbl: d['bus_type']        for lbl, d in raw_snap.items()},
            'v_setpoint_pu':    {lbl: d['v_setpoint_pu']   for lbl, d in raw_snap.items()},
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
            unit_bus_types=snap['bus_types'],
            unit_maintenance=self._fleet.get_maintenance_units(),
            unit_v_setpoint_pu=snap['v_setpoint_pu'],
            unit_q_reserve_mvar=snap['q_reserve_mvar'],
            unit_dispatch_modes=snap['dispatch_mode'],
            unit_has_schedule=frozenset(self._hourly_schedule) if self._hourly_schedule else frozenset(),
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
