"""
src/simulation/simulation.py

Master simulation loop and SimulationState snapshot for GRIDCOM.

GridSimulation orchestrates all physics modules each tick:
  demand → fleet → frequency+droop → load flow → voltage → overloads
  → cascade → islands → alarms → state snapshot

SimulationState is the complete snapshot transferred to the renderer
and gameplay layer each frame. See SIMULATION_API.md for the full
interface contract.

EventSystem (src/simulation/events.py) is stubbed — scripted events
are wired after the rendering stage (roadmap Stage 7).

See GRID_SIMULATION_MECHANICS.md for physics tick ordering.
See SIMULATION_API.md for the complete public interface.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass

from simulation.constants import (
    F_NOMINAL,
    F_ALERT_LOW, F_ALERT_HIGH,
    F_CRITICAL_LOW, F_CRITICAL_HIGH,
    F_IN_BOUNDS_TOL,
    OVERLOAD_WARN_PCT, OVERLOAD_CRIT_PCT,
    V_WARNING_LOW, V_CRITICAL_LOW,
    ALARM_MESSAGE_MAX_LEN,
    INTC_N_CAPACITY_MW, INTC_S_CAPACITY_MW,
    DEBUG_SIMULATION,
)
from simulation.grid import Grid
from simulation.loadflow import DCLoadFlow
from simulation.voltage import VoltageModel
from simulation.frequency import FrequencyModel
from simulation.units import FleetModel
from simulation.demand import DemandModel
from simulation.renewables import RenewablesModel
from simulation.cascade import CascadeModel
from data.profiles import SHIFT_SPECS


# ─────────────────────────────────────────────────────────────────────────────
# ALARM
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Alarm:
    alarm_id:       int
    priority:       str     # 'CRITICAL', 'WARNING', 'INFO'
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

    # Network — buses
    bus_voltages:            dict
    bus_angles:              dict
    bus_vsi:                 dict

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
    reservoir_levels:        dict
    pumped_storage_modes:    dict

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

    The scripted event system (events.py) is stubbed — events will be
    wired after the rendering stage is complete.
    """

    def __init__(
        self,
        grid: Grid,
        shift_number: int,
        difficulty: str,
        initial_schedule: dict | None = None,
    ) -> None:
        self._grid         = grid
        self._shift_number = shift_number
        self._difficulty   = difficulty

        spec = SHIFT_SPECS[shift_number]
        self._start_hour        = spec.start_hour
        self._duration_minutes  = spec.duration_hours * 60.0

        # Physics sub-models
        self._loadflow   = DCLoadFlow(grid)
        self._voltage    = VoltageModel(grid)
        self._frequency  = FrequencyModel()
        self._fleet      = FleetModel(grid, initial_schedule or {})
        self._demand     = DemandModel(spec)
        self._renewables = RenewablesModel(grid)
        self._cascade    = CascadeModel()

        # Interconnector injections (positive = import into grid)
        self._intc_schedule: dict = {
            'INTC-N': 0.0,
            'INTC-S': 0.0,
        }
        # Line service status
        self._line_in_service: dict = {
            l.label: True for l in grid.get_active_lines()
        }

        # Overload timer state (owned here, passed to CascadeModel each tick)
        self._overload_timers: dict = {}

        # Alarm state
        self._alarms:     list  = []
        self._alarm_id:   int   = 0
        self._seen_warn:  set   = set()   # line labels with active warn alarm
        self._seen_crit:  set   = set()   # line labels with active crit alarm

        # Simulation time
        self._sim_time_min: float = 0.0

        # Performance counters
        self._ticks_in_bounds:  int   = 0
        self._total_ticks:      int   = 0
        self._max_line_loading: float = 0.0
        self._load_shed_events: int   = 0
        self._cascade_events:   int   = 0
        self._min_voltage:      float = 1.0

        # Crisis state
        self._crisis_active:  bool      = False
        self._crisis_type:    str|None  = None
        self._crisis_element: str|None  = None

        # Cached state snapshot (built in _solve_and_snapshot)
        self._state: SimulationState | None = None

        # Build initial state snapshot
        self._solve_and_snapshot()

    # ─────── MAIN TICK ────────────────────────────────────────────────────

    def tick(self, dt_sim_seconds: float) -> None:
        """
        Advance simulation by dt_sim_seconds of simulated time.

        Tick order (per GRID_SIMULATION_MECHANICS.md):
          1.  Advance time
          2.  Update demand
          3.  Update renewable outputs → inject into fleet
          4.  Tick unit state machines (ramp, cold start)
          5.  Frequency update + droop response
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

        # 2. Update demand
        self._demand.update(
            sim_hour,
            total_generation_mw=self._fleet.total_generation_mw(),
            deterministic=False,
        )

        # 3. Renewable outputs → fleet
        rng_outputs = self._renewables.update(sim_hour, deterministic=False)
        for label, mw in rng_outputs.items():
            self._fleet.set_renewable_output(label, mw)

        # 4. Tick unit state machines
        self._fleet.tick(dt_sim_seconds)

        # 5. Frequency update (swing equation + droop)
        self._frequency.update(
            dt_sim_seconds=dt_sim_seconds,
            p_generation_mw=self._fleet.total_generation_mw(),
            p_load_mw=self._demand.total_load_mw,
            online_unit_types=self._fleet.online_unit_types(),
        )

        # 6. Build injection vectors
        p_injections         = self._build_p_injections()
        q_injections, pv_buses = self._build_q_injections()

        # 7. DC load flow
        in_service = self._get_in_service_lines()
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
                if DEBUG_SIMULATION:
                    print(f'[CASCADE] Line {line_label} tripped at '
                          f't={self._sim_time_min:.1f} min')

            in_service = self._get_in_service_lines()
            self._loadflow.rebuild(in_service)
            self._voltage.rebuild(in_service)
            lf_result = self._loadflow.solve(p_injections)
            vr_result = self._voltage.solve(q_injections, pv_buses=pv_buses)

        # 11. Island detection
        islands      = self._cascade.find_islands(self._grid.get_active_buses(),
                                                   in_service)
        blackout_zones = self._cascade.get_blackout_zones(islands, self._grid)

        # 12. Alarms
        self._update_loading_alarms(lf_result.line_loading_pct)
        self._update_voltage_alarms(vr_result.bus_voltages)
        self._update_frequency_alarms()
        self._expire_alarms()

        # 13. Crisis state
        self._update_crisis(lf_result.line_loading_pct, vr_result.bus_voltages)

        # 14. Performance counters
        self._total_ticks += 1
        if abs(self._frequency.frequency_hz - F_NOMINAL) <= F_IN_BOUNDS_TOL:
            self._ticks_in_bounds += 1
        max_load = max(lf_result.line_loading_pct.values(), default=0.0)
        self._max_line_loading = max(self._max_line_loading, max_load)
        min_v = min(vr_result.bus_voltages.values(), default=1.0)
        self._min_voltage = min(self._min_voltage, min_v)

        # 15. Snapshot
        self._state = self._build_state(
            sim_hour, lf_result, vr_result, islands, blackout_zones,
        )

        if DEBUG_SIMULATION:
            self._print_debug(lf_result, vr_result)

    # ─────── PUBLIC INTERFACE ─────────────────────────────────────────────

    def get_state(self) -> SimulationState:
        return self._state

    def is_shift_complete(self) -> bool:
        return self._sim_time_min >= self._duration_minutes

    def set_unit_target(self, unit_label: str, target_mw: float) -> bool:
        return self._fleet.set_unit_target(unit_label, target_mw)

    def start_unit(self, unit_label: str) -> bool:
        return self._fleet.start_unit(unit_label)

    def stop_unit(self, unit_label: str) -> bool:
        return self._fleet.stop_unit(unit_label)

    def set_unit_q_target(self, unit_label: str, q_target_mvar: float) -> bool:
        return self._fleet.set_unit_q_target(unit_label, q_target_mvar)

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
        spec      = SHIFT_SPECS[self._shift_number]
        fleet_fc  = FleetModel(self._grid, schedule)
        demand_fc = DemandModel(spec)
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

            demand_fc.update(hour, fleet_fc.total_generation_mw(),
                             deterministic=True)
            for lbl, mw in renew_fc.update(hour, deterministic=True).items():
                fleet_fc.set_renewable_output(lbl, mw)
            fleet_fc.tick(dt_s)

            p_inj = {b.label: 0.0 for b in self._grid.get_active_buses()}
            for bus_label, mw in fleet_fc.p_injections().items():
                p_inj[bus_label] = p_inj.get(bus_label, 0.0) + mw
            for bus_label, mw in demand_fc.p_load_injections().items():
                p_inj[bus_label] = p_inj.get(bus_label, 0.0) + mw

            pv = fleet_fc.pv_bus_constraints()
            q_inj = {b.label: 0.0 for b in self._grid.get_active_buses()}

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

    def _build_p_injections(self) -> dict:
        p: dict = {b.label: 0.0 for b in self._grid.get_active_buses()}
        for bus_label, mw in self._fleet.p_injections().items():
            p[bus_label] = p.get(bus_label, 0.0) + mw
        for bus_label, mw in self._demand.p_load_injections().items():
            p[bus_label] = p.get(bus_label, 0.0) + mw
        # Interconnector schedules folded into slack bus imbalance
        for mw in self._intc_schedule.values():
            p['MDBY'] = p.get('MDBY', 0.0) + mw
        return p

    def _build_q_injections(self) -> tuple:
        q_inj  = {b.label: 0.0 for b in self._grid.get_active_buses()}
        pv_buses = self._fleet.pv_bus_constraints()
        return q_inj, pv_buses

    # ─────── TOPOLOGY HELPERS ─────────────────────────────────────────────

    def _get_in_service_lines(self) -> list:
        return [
            l for l in self._grid.get_active_lines()
            if self._line_in_service.get(l.label, True)
        ]

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
                            f'Protection trips in 60s if sustained.'),
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

    def _update_voltage_alarms(self, voltages: dict) -> None:
        for bus_label, v in voltages.items():
            if v < V_CRITICAL_LOW:
                self._raise_alarm(
                    priority='CRITICAL',
                    message=f'Voltage {bus_label} {v:.3f} pu — collapse risk',
                    element_label=bus_label,
                    detail=(f'Bus {bus_label} at {v:.3f} pu — below '
                            f'collapse threshold {V_CRITICAL_LOW} pu.'),
                )
            elif v < V_WARNING_LOW:
                self._raise_alarm(
                    priority='WARNING',
                    message=f'Voltage {bus_label} {v:.3f} pu — low voltage',
                    element_label=bus_label,
                    detail=(f'Bus {bus_label} at {v:.3f} pu — below '
                            f'warning threshold {V_WARNING_LOW} pu.'),
                )

    def _update_frequency_alarms(self) -> None:
        f = self._frequency.frequency_hz
        if f <= F_CRITICAL_LOW or f >= F_CRITICAL_HIGH:
            self._raise_alarm(
                priority='CRITICAL',
                message=f'Frequency {f:.3f} Hz — critical deviation',
                element_label=None,
                detail=(f'System frequency {f:.3f} Hz has exceeded the '
                        f'critical threshold.'),
            )
        elif f <= F_ALERT_LOW or f >= F_ALERT_HIGH:
            self._raise_alarm(
                priority='WARNING',
                message=f'Frequency {f:.3f} Hz — alert threshold',
                element_label=None,
                detail=(f'System frequency {f:.3f} Hz has deviated beyond '
                        f'the alert band.'),
            )

    def _expire_alarms(self) -> None:
        self._alarms = [
            a for a in self._alarms
            if not (a.acknowledged and a.priority == 'INFO'
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

        self._demand.update(sim_hour, 0.0, deterministic=True)
        for lbl, mw in self._renewables.update(sim_hour, deterministic=True).items():
            self._fleet.set_renewable_output(lbl, mw)

        p_inj          = self._build_p_injections()
        q_inj, pv_buses = self._build_q_injections()
        lf_r = self._loadflow.solve(p_inj)
        vr_r = self._voltage.solve(q_inj, pv_buses=pv_buses)

        islands = self._cascade.find_islands(
            self._grid.get_active_buses(),
            self._get_in_service_lines(),
        )
        blackout = self._cascade.get_blackout_zones(islands, self._grid)
        self._state = self._build_state(sim_hour, lf_r, vr_r, islands, blackout)

    def _build_state(
        self,
        sim_hour: float,
        lf_result,
        vr_result,
        islands: list,
        blackout_zones: frozenset,
    ) -> SimulationState:
        freq    = self._frequency.frequency_hz
        total_gen  = self._fleet.total_generation_mw()
        total_load = self._demand.total_load_mw
        reserve    = self._fleet.spinning_reserve_mw()
        h_sys      = self._frequency._compute_system_inertia(
            self._fleet.online_unit_types()
        )
        raw_snap = self._fleet.get_state_snapshot()

        # Mark buses that hit Q limit as PQ (from voltage solver result)
        for bus_label in vr_result.pq_buses:
            for unit in self._grid.get_units_at_bus(bus_label):
                if unit.label in raw_snap:
                    raw_snap[unit.label]['bus_type'] = 'PQ'

        # Transpose per-unit dict into per-field dicts for SimulationState
        snap = {
            'states':           {lbl: d['state']          for lbl, d in raw_snap.items()},
            'outputs_mw':       {lbl: d['current_mw']     for lbl, d in raw_snap.items()},
            'targets_mw':       {lbl: d['target_mw']      for lbl, d in raw_snap.items()},
            'q_injections_mvar':{lbl: d['q_mvar']         for lbl, d in raw_snap.items()},
            'start_progress':   {lbl: d['start_progress'] for lbl, d in raw_snap.items()},
            'bus_types':        {lbl: d['bus_type']        for lbl, d in raw_snap.items()},
        }

        # Demand + renewable forecasts for remaining shift
        end_hour = self._start_hour + self._duration_minutes / 60.0
        demand_fc = self._demand.forecast_by_hour(sim_hour, end_hour, step=0.5)
        renew_fc  = self._renewables.forecast_by_hour(sim_hour, end_hour, step=0.5)

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

        line_status = {
            l.label: (
                'IN_SERVICE' if self._line_in_service.get(l.label, True)
                else 'TRIPPED'
            )
            for l in self._grid.get_active_lines()
        }

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

            bus_voltages=dict(vr_result.bus_voltages),
            bus_angles=dict(lf_result.bus_angles),
            bus_vsi=dict(vr_result.bus_voltages),

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
            reservoir_levels={},
            pumped_storage_modes={},

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
        max_load = max(lf_result.line_loading_pct.values(), default=0.0)
        min_v    = min(vr_result.bus_voltages.values(), default=1.0)
        print(
            f'[SIM] t={self._sim_time_min:6.2f}min '
            f'f={self._frequency.frequency_hz:.3f}Hz '
            f'gen={self._fleet.total_generation_mw():.0f}MW '
            f'load={self._demand.total_load_mw:.0f}MW '
            f'imb={self._fleet.total_generation_mw()-self._demand.total_load_mw:+.0f}MW '
            f'L_max={max_load:.1f}% '
            f'V_min={min_v:.3f}pu'
        )
