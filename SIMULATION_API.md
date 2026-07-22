# SIMULATION_API.md — Simulation↔Display Interface Contract
### The authoritative definition of what the simulation provides and what the display consumes.
### Read before working on any Stage 5+ code.

---

## Purpose

This document defines the exact interface between the simulation layer
(`src/simulation/`) and the display layer (`src/display/`) and gameplay
layer (`src/gameplay/`).

The simulation produces a `SimulationState` snapshot every tick.
The display consumes this snapshot to render the game.
The gameplay layer reads it to evaluate win/fail conditions.
Nothing in the display or gameplay layers reads simulation internals directly.

---

## SimulationState — The Complete Snapshot

Defined in `src/simulation/simulation.py`. Produced by `GridSimulation.get_state()`.
Consumed by renderer, panels, context panels, scoring, and win/fail evaluation.

```python
@dataclass(slots=True)
class SimulationState:
    # ─────────────────────────────────────────────
    # TIME
    # ─────────────────────────────────────────────
    sim_time_min: float
    # Minutes elapsed since shift start. 0.0 at shift begin.
    # Range: 0.0 to (shift_duration_hours × 60)

    sim_hour: float
    # Current time of day in decimal hours. E.g. 2.67 = 02:40
    # Range: shift_start_hour to (shift_start_hour + duration_hours)

    # ─────────────────────────────────────────────
    # FREQUENCY
    # ─────────────────────────────────────────────
    frequency_hz: float
    # Current system frequency in Hz.
    # Nominal: 50.0 Hz. Valid range: 45.0 to 55.0 (clamped).

    frequency_trend: str
    # Direction of frequency movement: 'RISING', 'FALLING', or 'STABLE'
    # STABLE: |Δf| < 0.005 Hz since last tick

    frequency_deviation_hz: float
    # frequency_hz - 50.0. Positive = above nominal. Negative = below.

    # ─────────────────────────────────────────────
    # POWER BALANCE
    # ─────────────────────────────────────────────
    total_generation_mw: float
    # Sum of current_mw for all ONLINE units. MW (not pu).

    total_load_mw: float
    # Total system demand (actual, including noise). MW.

    net_imbalance_mw: float
    # total_generation_mw - total_load_mw. Positive = surplus. Negative = deficit.

    spinning_reserve_mw: float
    # Sum of (rated_mw - current_mw) for all ONLINE units. MW.
    # This is the headroom available for frequency response.

    system_inertia_h: float
    # Generation-weighted average H constant. Seconds.
    # Computed from all ONLINE units only.

    losses_mw: float
    # Estimated system losses (fixed percentage of generation). MW.

    # ─────────────────────────────────────────────
    # NETWORK — BUSES
    # ─────────────────────────────────────────────
    bus_voltages: dict[str, float]
    # {bus_label: voltage_pu} for all active buses.
    # Per-unit. Nominal = 1.0. Healthy range: 0.95 to 1.05.
    # This is v_effective — the raw voltage solve plus the persistent
    # collapse-acceleration offset (see GRID_SIMULATION_MECHANICS.md §5.6).
    # Never the raw solver output directly.

    bus_angles: dict[str, float]
    # {bus_label: angle_rad} for all active buses.
    # Slack bus (MDBY) = 0.0 always.

    bus_vsi: dict[str, float]
    # {bus_label: vsi} Voltage Stability Index = voltage_pu (same value as
    # bus_voltages — both carry v_effective). Kept separate for semantic
    # clarity in display code.

    bus_vsi_tier: dict[str, str]
    # {bus_label: tier} where tier is 'HEALTHY' | 'WATCH' | 'WARNING' | 'CRITICAL'.
    # Derived from bus_vsi against constants.py's V_WATCH_LOW / V_WARNING_LOW /
    # V_CRITICAL_LOW thresholds — display must read this, never recompute it.

    # ─────────────────────────────────────────────
    # NETWORK — REACTIVE DEVICES
    # ─────────────────────────────────────────────
    bus_shunt_step: dict[str, int]
    # {bus_label: step} automatic shunt bank position, signed
    # (+capacitive .. -reactive). Present only for buses with a shunt bank.
    # Read-only — no player method; the device is fully automatic.

    bus_shunt_mvar: dict[str, float]
    # {bus_label: mvar} automatic shunt bank's current MVAr injection
    # (step * SHUNT_BANK_MVAR_PER_STEP). Read-only.

    bus_svc_mvar: dict[str, float]
    # {bus_label: mvar} manual SVC's current setpoint. Present only for
    # buses hosting an SVC. Player-settable via set_svc_setpoint().

    bus_svc_limits: dict[str, tuple[float, float]]
    # {bus_label: (q_min_mvar, q_max_mvar)} for buses hosting an SVC.

    transformer_taps: dict[str, tuple[str, int]]
    # {tap_label: (regulated_bus, step)} automatic transformer tap position.
    # Read-only — no player method; the device is fully automatic. Modelled
    # as a Q-injection approximation, not a true voltage-ratio change.

    bus_q_injection_mvar: dict[str, float]
    # {bus_label: mvar} total reactive device Q injection at each bus
    # (shunt + SVC + tap-approximation combined). Does not include load Q
    # or generator Q — those are separate (see bus_loads, unit_q_injections_mvar).

    # ─────────────────────────────────────────────
    # NETWORK — LINES
    # ─────────────────────────────────────────────
    line_flows_mw: dict[str, float]
    # {line_label: flow_mw}
    # Positive: power flows in conventional direction (from_bus → to_bus)
    # Negative: reverse flow (to_bus → from_bus)

    line_loading_pct: dict[str, float]
    # {line_label: loading_pct}
    # |flow_mw| / rating_mw × 100. Range: 0.0 to 200.0+ (overloaded).

    line_status: dict[str, str]
    # {line_label: status} where status is 'IN_SERVICE' or 'TRIPPED'

    overload_timers: dict[str, float]
    # {line_label: seconds_overloaded} for lines currently above 100% loading.
    # Line trips when timer exceeds TRIP_DELAY_S.
    # 0.0 for lines not currently overloaded.

    # ─────────────────────────────────────────────
    # GENERATION UNITS
    # ─────────────────────────────────────────────
    unit_states: dict[str, str]
    # {unit_label: state_name}
    # state_name is one of: 'OFFLINE', 'STARTING', 'ONLINE', 'SHUTDOWN'

    unit_outputs_mw: dict[str, float]
    # {unit_label: current_mw}
    # 0.0 for OFFLINE and STARTING units.

    unit_targets_mw: dict[str, float]
    # {unit_label: target_mw}
    # The setpoint the unit is ramping toward.

    unit_q_injections_mvar: dict[str, float]
    # {unit_label: q_mvar}
    # Reactive power injection. Positive = injection. Negative = absorption.
    # For PV/PQ (non-renewable, ONLINE) units this is the voltage solver's
    # actual q_injections_used for the unit's bus (split evenly across
    # co-located units) — not just whatever set_unit_q_target() last set.
    # 0.0 for OFFLINE/renewable units.

    unit_start_progress: dict[str, float]
    # {unit_label: progress_fraction} for STARTING units only.
    # 0.0 = just started. 1.0 = ready to synchronise.
    # Used to render startup arc animation.

    unit_bus_types: dict[str, str]
    # {unit_label: bus_type} where bus_type is 'PV' or 'PQ'
    # PQ means unit has hit reactive limit and lost voltage control.

    unit_v_setpoint_pu: dict[str, float]
    # {unit_label: v_pu} AVR voltage setpoint. Default GEN_VOLTAGE_SETPOINT_DEFAULT_PU
    # (1.02), editable range [0.95, 1.05] via set_generator_voltage_setpoint().
    # Where multiple units share a bus, the bus's PV target is the mean of
    # their individual setpoints — this field is always per-unit.

    unit_q_reserve_mvar: dict[str, float]
    # {unit_label: mvar} headroom to q_max_mvar (max(0, q_max_mvar - current_q)).
    # 0.0 for OFFLINE units. Lets the display show which generators can still
    # support voltage before a setpoint increase has no further effect.

    reservoir_levels: dict[str, float]
    # {station_label: level_fraction} for hydro stations only.
    # 0.0 = empty. 1.0 = full.
    # Stations: 'BARR', 'KELM', 'DUNH' (upper reservoirs only)

    pumped_storage_modes: dict[str, str]
    # {station_label: mode} for pumped storage stations.
    # mode: 'GENERATING', 'PUMPING', or 'IDLE'

    # ─────────────────────────────────────────────
    # FORECASTS (for display — not affected by noise)
    # ─────────────────────────────────────────────
    demand_forecast_mw: dict[float, float]
    # {sim_hour: forecast_mw} for remaining shift hours.
    # This is what the player sees — the deterministic forecast.

    wind_forecast_mw: dict[str, dict[float, float]]
    # {station_label: {sim_hour: forecast_mw}}

    solar_forecast_mw: dict[str, dict[float, float]]
    # {station_label: {sim_hour: forecast_mw}}

    # ─────────────────────────────────────────────
    # ALARMS
    # ─────────────────────────────────────────────
    active_alarms: list['Alarm']
    # All unacknowledged and recently acknowledged alarms.
    # Newest first. See Alarm dataclass below.

    # ─────────────────────────────────────────────
    # TOPOLOGY STATE
    # ─────────────────────────────────────────────
    islands: list[frozenset[str]]
    # List of connected sub-networks (bus label sets).
    # Normal operation: one island containing all active buses.
    # After line trips: may be multiple islands.

    blackout_zones: frozenset[str]
    # Set of bus labels currently without power.
    # Empty in normal operation.

    # ─────────────────────────────────────────────
    # CRISIS STATE
    # ─────────────────────────────────────────────
    crisis_active: bool
    # True if any crisis condition is currently triggered.
    # Causes automatic speed reduction and border flash.

    crisis_type: str | None
    # 'CRITICAL' or 'WARNING' or None.

    crisis_element: str | None
    # Label of the element that triggered the crisis (bus or line label).
    # None if crisis is system-wide (frequency).

    # ─────────────────────────────────────────────
    # PERFORMANCE TRACKING (for scoring)
    # ─────────────────────────────────────────────
    frequency_in_bounds_pct: float
    # Percentage of elapsed sim time with frequency within ±0.2 Hz.

    max_line_loading_seen: float
    # Highest line loading percentage seen this shift.

    load_shed_events: int
    # Count of automatic load shedding events this shift.

    cascade_events: int
    # Count of cascade sequences (each sequence = one cascade event).

    min_voltage_seen: float
    # Lowest bus voltage (pu) seen this shift.
```

---

## Alarm Dataclass

```python
@dataclass
class Alarm:
    alarm_id: int
    # Unique monotonically increasing ID. Used for deduplication.

    priority: str
    # 'CRITICAL', 'WARNING', or 'INFO'

    timestamp_min: float
    # sim_time_min when the alarm was generated.

    message: str
    # Human-readable alarm description. Max 60 characters.
    # Examples:
    #   "Line L03 loading 91% — approaching limit"
    #   "Voltage LD02 0.91 pu — below lower limit"
    #   "Unit RVSD-2 tripped — overcurrent protection"
    #   "Frequency 49.6 Hz — alert threshold"

    element_label: str | None
    # Bus or line label associated with this alarm.
    # None for system-wide alarms (frequency events).

    acknowledged: bool
    # False until player presses ACK. Unacknowledged alarms blink.

    detail: str
    # Extended description for the alarm detail panel.
    # May be multiple sentences. No length limit.
```

---

## GridSimulation — Public Interface

Defined in `src/simulation/simulation.py`.
These are the ONLY methods the gameplay and display layers may call.
Do not access simulation internals directly.

```python
class GridSimulation:

    def __init__(
        self,
        grid: Grid,
        shift_number: int,
        difficulty: str,
        initial_schedule: dict[str, float] | None = None
    ) -> None:
        """
        Initialise simulation for a specific shift.

        Args:
            grid: Loaded Grid object for this shift's node count.
            shift_number: 1-10. Determines scripted events and shift window.
            difficulty: 'TRAINEE', 'OPERATOR', or 'DISPATCHER'.
            initial_schedule: {unit_label: initial_mw_target} from autopilot
                              or Phase 1 planning. If None, uses all units
                              at minimum output.
        """

    def tick(self, dt_sim_seconds: float) -> None:
        """
        Advance simulation by dt_sim_seconds of simulated time.

        Called every frame from the game loop. dt_sim_seconds is the
        product of real elapsed time, speed multiplier, and TIME_COMPRESSION.

        Side effects:
            Updates all internal simulation state.
            May fire scripted events.
            May trip lines and rebuild network topology.
            Updates SimulationState snapshot (accessible via get_state()).
        """

    def get_state(self) -> SimulationState:
        """
        Return a complete snapshot of current simulation state.

        Returns a new SimulationState object each call.
        Caller may hold references safely — state is not modified after return.
        Called every frame by the renderer.
        """

    def is_shift_complete(self) -> bool:
        """
        Returns True when sim_time_min >= shift_duration_minutes.
        Called by Phase2Session to detect shift end.
        """

    # ─────── PLAYER CONTROLS ───────

    def set_unit_target(self, unit_label: str, target_mw: float) -> bool:
        """
        Set dispatch target for a generation unit.

        Args:
            unit_label: e.g. 'RVSD-1', 'HART-2'
            target_mw: Target output in MW. Clamped to [min_mw, rated_mw].

        Returns:
            True if command accepted.
            False if unit is not ONLINE (cannot set target for offline unit).

        Side effects:
            Unit begins ramping toward target_mw at its ramp rate.
        """

    def start_unit(self, unit_label: str) -> bool:
        """
        Issue start command to an OFFLINE unit. (Available from Shift 2.)

        Returns:
            True if command accepted (unit was OFFLINE).
            False if unit is not OFFLINE.

        Side effects:
            Unit transitions to STARTING state.
            Unit begins cold start countdown (cold_start_min).
            Unit has zero output and zero inertia contribution during STARTING.
        """

    def stop_unit(self, unit_label: str) -> bool:
        """
        Issue shutdown command to an ONLINE unit. (Available from Shift 2.)

        Returns:
            True if command accepted (unit was ONLINE).
            False if unit is not ONLINE.

        Side effects:
            Unit transitions to SHUTDOWN state.
            Unit ramps to minimum output, then transitions to OFFLINE.
        """

    def set_unit_q_target(self, unit_label: str, q_target_mvar: float) -> bool:
        """
        Set reactive power target for a voltage-controlling unit.
        (Available from Shift 7.)

        Args:
            q_target_mvar: Target reactive injection. Positive = inject.
                           Clamped to [q_min_mvar, q_max_mvar].

        Returns:
            True if command accepted (unit is ONLINE and voltage-controlling).
            False otherwise.
        """
        # Kept callable for direct MVAr control, but has no dedicated UI —
        # set_generator_voltage_setpoint() below is the intended player lever.

    def set_generator_voltage_setpoint(self, unit_label: str, v_pu: float) -> bool:
        """
        Set a generator's AVR voltage setpoint (per-unit). Manual voltage
        lever #1 — supports a sagging region from nearby generation.

        Args:
            v_pu: Target voltage, clamped to
                  [GEN_VOLTAGE_SETPOINT_MIN_PU, GEN_VOLTAGE_SETPOINT_MAX_PU]
                  (0.95-1.05).

        Returns:
            True if command accepted (unit is ONLINE).
            False otherwise.

        Side effects:
            Feeds into pv_bus_constraints() as this unit's v_target on the
            next voltage solve. Where units share a bus, the bus's PV target
            becomes the mean of all their setpoints. If the resulting Q
            requirement exceeds the unit's q_max_mvar/q_min_mvar, the bus
            converts PV->PQ (unit_bus_types flips) and unit_q_reserve_mvar
            reaches 0 — further setpoint increases have no additional effect.
        """

    def set_svc_setpoint(self, bus_label: str, q_mvar: float) -> bool:
        """
        Set a bus's manual SVC/STATCOM reactive power setpoint. Manual
        voltage lever #2 — for regions with no nearby generation to lean on.

        Args:
            q_mvar: Target injection, clamped to
                    [SVC_Q_MIN_MVAR, SVC_Q_MAX_MVAR] (±150 MVAr).

        Returns:
            True if command accepted (bus hosts an SVC).
            False if the bus has no SVC.

        Side effects:
            Feeds directly into the next tick's Q injections at that bus.
        """

    # Note: automatic shunt banks and transformer taps have no player-facing
    # set_* method — they are stepped internally by
    # ReactiveDevices.step_automatics() each tick and are read-only from the
    # player's perspective (see bus_shunt_step/bus_shunt_mvar/transformer_taps
    # in SimulationState above).

    def set_pumped_storage_mode(self, station_label: str, mode: str) -> bool:
        """
        Set operating mode of a pumped storage station. (Available from Shift 8.)

        Args:
            station_label: e.g. 'BARR', 'KELM', 'DUNH'
            mode: 'GENERATING', 'PUMPING', or 'IDLE'

        Returns:
            True if mode change accepted.
            False if station is not a pumped storage station, or if
            reservoir is too empty for GENERATING, or too full for PUMPING.

        Side effects:
            Mode transition takes 8 simulated minutes.
            During transition, station output ramps to zero before reversing.
        """

    def trip_line(self, line_label: str) -> bool:
        """
        Manually trip (open) a transmission line. (Available from Shift 6.)

        Returns:
            True if line was IN_SERVICE and is now TRIPPED.
            False if line was already TRIPPED.

        Side effects:
            Line removed from network topology.
            B matrix rebuilt.
            Load flow re-solved.
            Cascade check performed.
        """

    def close_line(self, line_label: str) -> bool:
        """
        Close (re-energise) a TRIPPED transmission line. (Available from Shift 6.)

        Returns:
            True if line was TRIPPED and is now IN_SERVICE.
            False if line was already IN_SERVICE.

        Side effects:
            Line added back to network topology.
            B matrix rebuilt.
            Load flow re-solved.
        """

    def shed_load(self, bus_label: str, fraction: float) -> bool:
        """
        Shed a fraction of load at a specific load substation.
        (Available from Shift 4.)

        Args:
            bus_label: Load substation label (LD01-LD06).
            fraction: Fraction of load to shed. 0.0 to 1.0.

        Returns:
            True if command accepted (bus is a load substation, currently energised).
            False otherwise.

        Side effects:
            Reduces effective demand at bus_label by fraction.
            Generates INFO alarm: "Load shed at {bus_label}: {fraction×100:.0f}%"
        """

    def acknowledge_alarm(self, alarm_id: int) -> bool:
        """
        Acknowledge a specific alarm.

        Returns:
            True if alarm found and acknowledged.
            False if alarm_id not found or already acknowledged.

        Side effects:
            Alarm.acknowledged set to True.
            If all CRITICAL alarms acknowledged: crisis_active may become False,
            allowing speed increase above NORMAL.
        """

    def acknowledge_all_alarms(self) -> int:
        """
        Acknowledge all current alarms.
        Returns count of alarms acknowledged.
        """

    def set_interconnector_schedule(
        self,
        interconnector_label: str,
        schedule_mw: float
    ) -> bool:
        """
        Set import/export schedule for an interconnector. (Available from Shift 5.)

        Args:
            interconnector_label: 'INTC-N' or 'INTC-S'
            schedule_mw: Positive = import (power enters grid).
                         Negative = export (power leaves grid).
                         Clamped to interconnector capacity limits.

        Returns:
            True if accepted.
            False if interconnector is tripped.
        """

    # ─────── FORECAST MODE ───────

    def run_forecast_mode(
        self,
        schedule: dict[str, float],
        start_hour: float,
        duration_hours: float
    ) -> 'ForecastResult':
        """
        Fast deterministic evaluation of a proposed schedule.
        Used by Phase 1 shift preview screen.

        IMPORTANT: This runs the full shift window deterministically with
        no stochastic noise and no cascade events. Must complete in < 500ms.

        Args:
            schedule: {unit_label: mw_target} initial dispatch plan.
            start_hour: Shift start time (decimal hours, e.g. 6.0 = 06:00).
            duration_hours: Length of shift window.

        Returns:
            ForecastResult containing:
              generation_stack: {hour: {unit_type: mw}} hourly breakdown
              reserve_by_hour: {hour: reserve_mw}
              congestion_risk: {line_label: max_loading_pct}
              voltage_risk: {bus_label: min_vsi}
              reservoir_end_levels: {station_label: level_fraction}
              estimated_cost_eur: float
              risk_hours: list of hours where reserve < 8%
        """
```

---

## Grid — Public Interface

Defined in `src/simulation/grid.py`.
Read-only after construction. Do not modify Grid attributes directly.

```python
class Grid:

    def __init__(self, shift_number: int) -> None:
        """Load topology filtered to nodes/units active in this shift."""

    def get_active_buses(self) -> list[Bus]:
        """All buses active in this shift (active_from_shift <= shift_number)."""

    def get_active_lines(self) -> list[Line]:
        """All lines active in this shift."""

    def get_active_units(self) -> list[GenerationUnit]:
        """All generation units active in this shift."""

    def get_bus(self, label: str) -> Bus:
        """Get bus by 4-char label. Raises KeyError if not found."""

    def get_line(self, label: str) -> Line:
        """Get line by label. Raises KeyError if not found."""

    def get_unit(self, label: str) -> GenerationUnit:
        """Get unit by label. Raises KeyError if not found."""

    def get_units_at_bus(self, bus_label: str) -> list[GenerationUnit]:
        """All units whose bus matches bus_label."""

    def get_load_at_bus(self, bus_label: str, sim_hour: float) -> float:
        """
        Returns current demand (MW) at a load substation.
        Returns 0.0 for non-load buses.
        This is the deterministic forecast value, not actual (noisy) demand.
        """

    def get_canvas_position(self, label: str) -> tuple[int, int]:
        """
        Returns (x, y) canvas position in native 1920×1080 coordinates.
        Works for both bus labels and station labels.
        Raises KeyError if label not found.
        """

    @property
    def slack_bus(self) -> str:
        """Always returns 'MDBY'."""

    @property
    def shift_number(self) -> int:
        """The shift this grid was loaded for."""
```

---

## ForecastResult — Phase 1 Preview Data

```python
@dataclass(frozen=True)
class ForecastResult:
    generation_stack: dict[float, dict[str, float]]
    # {sim_hour: {unit_type: total_mw}}
    # e.g. {6.0: {'COAL': 900, 'NUCLEAR': 1400, 'HYDRO': 500, ...}}

    reserve_by_hour: dict[float, float]
    # {sim_hour: spinning_reserve_mw}

    congestion_risk: dict[str, float]
    # {line_label: max_loading_pct_forecast}
    # Lines expected to exceed 85% loading at any point during shift.

    voltage_risk: dict[str, float]
    # {bus_label: min_vsi_forecast}
    # Buses expected to fall below 0.92 pu at any point.

    reservoir_end_levels: dict[str, float]
    # {station_label: level_fraction} at shift end.
    # Stations: 'BARR', 'KELM', 'DUNH'

    estimated_cost_eur: float
    # Estimated fuel + carbon + start cost for the shift.

    risk_hours: list[float]
    # Hours where reserve_by_hour < (0.08 × total_demand_mw).
    # These are the RED risk indicators in the preview screen.

    congestion_hours: dict[str, list[float]]
    # {line_label: [hours where loading > 85%]}
    # These are the ORANGE risk indicators.
```

---

## ShiftResults — Post-Shift Scoring Data

```python
@dataclass(frozen=True)
class ShiftResults:
    shift_number: int
    difficulty: str

    # Frequency performance
    frequency_in_bounds_pct: float      # % time within ±0.2 Hz
    min_frequency_hz: float
    min_frequency_time_min: float       # when lowest frequency occurred
    frequency_recovery_time_min: float  # minutes to recover after each event

    # Security performance
    max_line_loading_pct: float
    line_overload_count: int            # number of overload events (>85%)
    line_trip_count: int
    cascade_count: int
    load_shed_events: int
    load_shed_total_pct: float          # total % of demand shed
    blackout_duration_min: float        # total sim minutes of blackout

    # Voltage performance (Shifts 7-10 only)
    voltage_in_bounds_pct: float        # % time all buses within ±5% nominal
    min_voltage_pu: float
    voltage_violation_count: int        # buses below 0.90 pu event count

    # Economics (Shifts 5-10 only)
    operating_cost_eur: float
    target_cost_eur: float

    # Planning accuracy (Shifts 5-10 only)
    risk_indicators_predicted: int      # how many Phase 1 red/orange flags fired
    risk_indicators_total: int          # total Phase 1 risk indicators shown
    unpredicted_events: int             # events that fired without a warning

    # Carry-forward state
    reservoir_levels_end: dict[str, float]   # {station_label: level_fraction}
    unit_commitment_end: dict[str, str]      # {unit_label: state_name}
```

---

## What Display Code Must NOT Do

- Do not import from `simulation.loadflow`, `simulation.voltage`,
  `simulation.frequency`, `simulation.cascade`, or `simulation.units` directly.
  Use `GridSimulation.get_state()` exclusively.

- Do not call `GridSimulation.tick()` — that is `main.py`'s job.

- Do not modify any field of `SimulationState` — it is read-only.

- Do not compute derived quantities from SimulationState that the simulation
  already computes (e.g. do not recompute VSI from voltages — use `bus_vsi`).

- Do not access `Grid` internals directly from display code — use
  `Grid.get_canvas_position()` for positions, `Grid.get_bus()` for bus data.

---

## What Simulation Code Must NOT Do

- Do not import from `display.*` — the simulation has no knowledge of rendering.

- Do not import from `gameplay.*` — the simulation does not know about campaigns.

- Do not call `pygame.*` — the simulation is pure Python/numpy.

- Do not read user input — all player commands arrive via the public interface methods.

- Do not write to files — save/load is the gameplay layer's responsibility.
