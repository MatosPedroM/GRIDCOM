"""
src/simulation/units.py

Generation unit state machine for the GRIDCOM simulation.

Each physical generator is represented by a UnitModel instance.
UnitModel tracks state (OFFLINE/STARTING/ONLINE/SHUTDOWN), output (MW),
target setpoint, ramp progress, and reactive injection (MVAr).

FleetModel owns all UnitModel instances for a shift and provides aggregate
queries (total generation, system inertia, spinning reserve).

States:
    OFFLINE   — unit is shut down. Output = 0. Inertia contribution = 0.
    STARTING  — cold start in progress. Output = 0. Timer counts up to
                cold_start_min. Inertia contribution = 0 (not synchronised).
    ONLINE    — unit is synchronised and producing. Output ramps toward target.
                Output clamped to [min_mw, rated_mw].
    SHUTDOWN  — unit received stop command. Ramps down to min_mw, then trips
                to OFFLINE automatically.

Transitions:
    OFFLINE  -> STARTING  : start() called
    STARTING -> ONLINE    : start timer reaches cold_start_min
    ONLINE   -> SHUTDOWN  : stop() called
    SHUTDOWN -> OFFLINE   : output reaches min_mw (or 0 if min_mw == 0)
    Any      -> OFFLINE   : trip() called (protection trip, immediate)

Wind and Solar units are always ONLINE — their output is overridden by
the renewables model each tick via set_renewable_output(). start()/stop()
do nothing for wind/solar units.

See SIMULATION_API.md for the unit_states / unit_outputs_mw contract.
See DOMAIN_GLOSSARY.md for unit type definitions and ramp/inertia values.
"""

import logging
from config.constants import (
    MIN_OUTPUT_FRACTION,
    DEBUG_SIMULATION,
)
import config.constants as _sim_const
from data.fleet import GenerationUnit

# Unit types that are non-dispatchable (renewables — output set externally).
_RENEWABLE_TYPES: frozenset[str] = frozenset({'WIND', 'SOLAR'})

# Technical minimum fraction per unit type — used by AGC lower-bound and regulation indicator.
_TECH_MIN_FRAC: dict[str, float] = {
    'HYDRO':      _sim_const.TECH_MIN_FRAC_HYDRO,
    'HYDRO_ROR':  _sim_const.TECH_MIN_FRAC_HYDRO_ROR,
    'HYDRO_PUMP': _sim_const.TECH_MIN_FRAC_HYDRO_PUMP,
    'WIND':       _sim_const.TECH_MIN_FRAC_WIND,
    'SOLAR':      _sim_const.TECH_MIN_FRAC_SOLAR,
    'CCGT':       _sim_const.TECH_MIN_FRAC_CCGT,
    'COAL':       _sim_const.TECH_MIN_FRAC_COAL,
    'NUCLEAR':    _sim_const.TECH_MIN_FRAC_NUCLEAR,
}

# Unit types that require minimum output > 0 when online.
# For these types, min_mw from fleet.py is already correct.
# HYDRO variants and renewables allow min_mw = 0.
_THERMAL_TYPES: frozenset[str] = frozenset({'COAL', 'CCGT', 'NUCLEAR'})


class UnitModel:
    """
    Mutable state machine for a single generation unit.

    Constructed from a GenerationUnit dataclass (immutable spec).
    All physics state lives here; GenerationUnit is read-only after creation.

    Attributes (read-only via properties):
        label:        Unit label string, e.g. 'RVSD-1'.
        state:        Current state string: 'OFFLINE', 'STARTING', 'ONLINE', 'SHUTDOWN'.
        current_mw:   Current output in MW.
        target_mw:    Dispatch setpoint the unit is ramping toward.
        start_progress: Fraction of cold start complete (0.0–1.0). 0.0 when not STARTING.
        q_injection_mvar: Current reactive injection (MVAr). Positive = injection.
        is_renewable: True for WIND and SOLAR units.
    """

    def __init__(self, spec: GenerationUnit, initial_mw: float | None = None) -> None:
        """
        Initialise unit from its static specification.

        Args:
            spec:        Frozen GenerationUnit dataclass from fleet.py.
            initial_mw:  Starting output in MW. None = unit starts OFFLINE (0 MW).
                         If provided, unit starts ONLINE at this output level.
                         Clamped to [min_mw, rated_mw].
        """
        self._spec = spec
        self._is_renewable = spec.unit_type in _RENEWABLE_TYPES

        if initial_mw is not None:
            clamped = max(spec.min_mw, min(spec.rated_mw, float(initial_mw)))
            self._state: str = 'ONLINE'
            self._current_mw: float = clamped
            self._target_mw: float = clamped
        else:
            self._state = 'ONLINE' if self._is_renewable else 'OFFLINE'
            self._current_mw = 0.0
            self._target_mw = 0.0

        self._start_timer_min: float = 0.0   # simulated minutes elapsed since STARTING
        self._q_injection_mvar: float = 0.0
        self._maintenance: bool = False
        self._derate_cap_mw: float | None = None   # None = not derated
        # Setpoint drift (random deviation event) — added to target_mw in
        # _tick_online()'s ramp loop, so current_mw converges toward the
        # WRONG value while active. 0.0 = no drift. See drift()/clear_drift().
        self._drift_offset_mw: float = 0.0
        self._dispatch_mode: str = 'MANUAL'   # 'MANUAL' or 'AUTO' — see set_target()/set_auto_mode()
        # Running total of AGC-attributable adjustment to target_mw since the
        # unit's last hourly-schedule snap. Carried across hour boundaries by
        # apply_hourly_schedule() so AGC's correction isn't discarded there —
        # see FleetModel.apply_hourly_schedule().
        self._agc_offset_mw: float = 0.0

    # ─────── READ-ONLY PROPERTIES ─────────────────────────────────────────

    @property
    def label(self) -> str:
        return self._spec.label

    @property
    def state(self) -> str:
        return self._state

    @property
    def current_mw(self) -> float:
        return self._current_mw

    @property
    def target_mw(self) -> float:
        return self._target_mw

    @property
    def start_progress(self) -> float:
        """Cold start completion fraction. 0.0–1.0. 0.0 when not STARTING."""
        if self._state != 'STARTING' or self._spec.cold_start_min <= 0.0:
            return 0.0
        return min(1.0, self._start_timer_min / self._spec.cold_start_min)

    @property
    def q_injection_mvar(self) -> float:
        return self._q_injection_mvar

    @property
    def is_renewable(self) -> bool:
        return self._is_renewable

    @property
    def is_maintenance(self) -> bool:
        return self._maintenance

    @property
    def dispatch_mode(self) -> str:
        """'AUTO' (following the Phase 1 hourly schedule) or 'MANUAL'
        (player/AGC-controlled target). New units always start MANUAL."""
        return self._dispatch_mode

    def set_maintenance(self, flag: bool) -> None:
        self._maintenance = flag

    @property
    def is_derated(self) -> bool:
        return self._derate_cap_mw is not None

    @property
    def is_drifting(self) -> bool:
        return self._drift_offset_mw != 0.0

    @property
    def drift_offset_mw(self) -> float:
        return self._drift_offset_mw

    @property
    def effective_max_mw(self) -> float:
        """Current dispatch ceiling: rated_mw, or the derate cap if derated."""
        if self._derate_cap_mw is None:
            return self._spec.rated_mw
        return min(self._spec.rated_mw, self._derate_cap_mw)

    @property
    def inertia_contribution(self) -> tuple[str, float]:
        """Returns (unit_type, current_mw) for FrequencyModel inertia calculation.
        Returns (unit_type, 0.0) when not ONLINE — no inertia contribution."""
        if self._state == 'ONLINE':
            return (self._spec.unit_type, self._current_mw)
        return (self._spec.unit_type, 0.0)

    # ─────── COMMANDS ─────────────────────────────────────────────────────

    def start(self) -> bool:
        """
        Issue start command. Transitions OFFLINE -> STARTING.

        Returns:
            True if command accepted (was OFFLINE).
            False if unit is not OFFLINE (already running or starting).
        """
        if self._is_renewable:
            return False
        if self._maintenance:
            return False
        if self._state != 'OFFLINE':
            return False
        self._state = 'STARTING'
        self._start_timer_min = 0.0
        if DEBUG_SIMULATION:
            logging.getLogger('sim').debug(f'[UNITS] {self.label} OFFLINE -> STARTING '
                                           f'(cold start {self._spec.cold_start_min:.0f} min)')
        return True

    def stop(self) -> bool:
        """
        Issue stop command. Transitions ONLINE -> SHUTDOWN.

        Returns:
            True if command accepted (was ONLINE).
            False if unit is not ONLINE.
        """
        if self._is_renewable:
            return False
        if self._state != 'ONLINE':
            return False
        self._state = 'SHUTDOWN'
        self._target_mw = 0.0
        if DEBUG_SIMULATION:
            logging.getLogger('sim').debug(f'[UNITS] {self.label} ONLINE -> SHUTDOWN')
        return True

    def trip(self) -> None:
        """
        Protection trip — immediate transition to OFFLINE from any state.
        Zeroes output and clears reactive injection.
        """
        if DEBUG_SIMULATION and self._state != 'OFFLINE':
            logging.getLogger('sim').debug(f'[UNITS] {self.label} TRIPPED from {self._state} '
                                           f'({self._current_mw:.1f} MW -> 0)')
        self._state = 'OFFLINE'
        self._current_mw = 0.0
        self._target_mw = 0.0
        self._start_timer_min = 0.0
        self._q_injection_mvar = 0.0
        self._dispatch_mode = 'MANUAL'
        self._agc_offset_mw = 0.0

    def derate(self, cap_mw: float) -> None:
        """
        Reduce the unit's dispatch ceiling to cap_mw and hold it there
        (e.g. a cooling fault) — unlike trip(), the unit stays ONLINE and
        keeps producing, just below its nameplate rating. If output is
        currently above the new cap, it ramps down at the unit's normal
        ramp_pct_per_min rate (via the target setpoint) rather than
        snapping instantly. Clamped to min_mw.
        """
        cap = max(self._spec.min_mw, min(self._spec.rated_mw, float(cap_mw)))
        self._derate_cap_mw = cap
        if DEBUG_SIMULATION:
            logging.getLogger('sim').debug(f'[UNITS] {self.label} DERATED to {cap:.1f} MW '
                                           f'(was rated {self._spec.rated_mw:.1f} MW)')
        if self._target_mw > cap:
            self._target_mw = cap

    def clear_derate(self) -> None:
        """
        Remove an active derate — effective_max_mw returns to rated_mw.
        No-op if not currently derated. Does not touch target_mw; a unit
        below its old cap simply gains headroom to be commanded higher
        again, it doesn't jump up on its own.
        """
        self._derate_cap_mw = None
        if DEBUG_SIMULATION:
            logging.getLogger('sim').debug(f'[UNITS] {self.label} derate cleared')

    def drift(self, offset_mw: float) -> None:
        """
        Start a setpoint drift (random deviation event) — current_mw will
        converge toward target_mw + offset_mw instead of target_mw alone,
        via _tick_online()'s normal ramp-rate-limited chase, until cleared.
        No alarm is raised here (see simulation.py's trigger site) — the
        player must notice the Target/Output mismatch themselves.
        No-op if the unit is not ONLINE or already drifting (offsets don't
        stack — see the trigger site's is_drifting guard).
        """
        if self._state != 'ONLINE' or self.is_drifting:
            return
        self._drift_offset_mw = float(offset_mw)
        if DEBUG_SIMULATION:
            logging.getLogger('sim').debug(f'[UNITS] {self.label} DRIFT {offset_mw:+.1f} MW '
                                           f'off target {self._target_mw:.1f}')

    def clear_drift(self) -> None:
        """
        Clear an active drift — current_mw resumes converging toward bare
        target_mw. Called either when the player re-issues the currently-
        commanded setpoint (see set_target()/_set_target_internal()) or by
        the fleet-wide hour-boundary sweep in simulation.py. No-op if not
        currently drifting.
        """
        self._drift_offset_mw = 0.0
        if DEBUG_SIMULATION and self.is_drifting:
            logging.getLogger('sim').debug(f'[UNITS] {self.label} drift cleared')

    def set_target(self, target_mw: float) -> bool:
        """
        Set dispatch target from a direct player command. Only valid when
        ONLINE. Drops the unit to MANUAL dispatch mode — see set_auto_mode()
        to return it to AUTO. Clears an active setpoint drift if this
        matches the already-commanded target (see
        _maybe_clear_drift_on_recommand()) — a genuine player re-command,
        exactly the "notice and re-confirm" fix.

        Args:
            target_mw: Target output in MW. Clamped to [min_mw, rated_mw].

        Returns:
            True if accepted (unit is ONLINE).
            False otherwise.
        """
        prior_target_mw = self._target_mw
        if not self._set_target_internal(target_mw):
            return False
        self._maybe_clear_drift_on_recommand(target_mw, prior_target_mw)
        self._dispatch_mode = 'MANUAL'
        self._agc_offset_mw = 0.0   # player command asserts a new baseline
        return True

    def _set_target_internal(self, target_mw: float) -> bool:
        """
        Set dispatch target without touching dispatch_mode. Used by AGC
        regulation (apply_agc_signal()) and the Phase 1 per-hour schedule
        executor, neither of which should force a unit to MANUAL.

        Does NOT touch an active setpoint drift — see
        _maybe_clear_drift_on_recommand() for that, called explicitly only
        from the genuine "operator re-issued a command" sites (set_target()
        and the hourly-schedule executor), never from here directly, since
        this is also AGC's path (_apply_agc_delta()) and AGC's small
        incremental deltas can easily land within DRIFT_CLEAR_TOLERANCE_MW
        of the current target by pure chance during normal operation —
        that must never be mistaken for a player noticing and re-confirming.

        Args:
            target_mw: Target output in MW. Clamped to [min_mw, rated_mw].

        Returns:
            True if accepted (unit is ONLINE).
            False otherwise.
        """
        if self._state != 'ONLINE':
            return False
        self._target_mw = max(
            self._spec.min_mw,
            min(self.effective_max_mw, float(target_mw))
        )
        return True

    def _maybe_clear_drift_on_recommand(self, requested_mw: float, prior_target_mw: float) -> None:
        """
        Clear an active setpoint drift if requested_mw matches the target
        that was ALREADY commanded (prior_target_mw, captured before the
        new value is applied) within DRIFT_CLEAR_TOLERANCE_MW — i.e. the
        operator/schedule has re-issued the same command that was in
        effect when the drift started, the deliberate "notice and
        re-confirm" fix. Call ONLY from a genuine re-command site
        (set_target(), the hourly-schedule executor) — never from AGC's
        path, whose incremental deltas are not re-commands and could
        collide with the tolerance by chance.
        """
        if self.is_drifting and abs(float(requested_mw) - prior_target_mw) <= _sim_const.DRIFT_CLEAR_TOLERANCE_MW:
            self.clear_drift()

    def _apply_agc_delta(self, share_mw: float) -> bool:
        """
        Apply this unit's share of an AGC correction: sets target_mw via
        _set_target_internal() and accumulates the AGC-attributable offset
        (see _agc_offset_mw docstring in __init__) so apply_hourly_schedule()
        can carry it across the next hour boundary instead of discarding it.
        Deliberately does not touch an active drift — see
        _set_target_internal()'s docstring.
        """
        if not self._set_target_internal(self.target_mw + share_mw):
            return False
        self._agc_offset_mw += share_mw
        return True

    def set_auto_mode(self) -> bool:
        """
        Return the unit to AUTO dispatch mode — it will follow the Phase 1
        hourly schedule (if one exists) from the next hour boundary. Only
        valid when ONLINE.

        Returns:
            True if accepted (unit is ONLINE).
            False otherwise.
        """
        if self._state != 'ONLINE':
            return False
        self._dispatch_mode = 'AUTO'
        return True

    def set_q_target(self, q_mvar: float) -> bool:
        """
        Set reactive injection target. Valid in any state — an OFFLINE unit's
        target is stored and takes effect once it comes ONLINE (e.g. a
        shift's INITIAL_Q_MVAR pre-configuring a unit that starts OFFLINE
        and is brought online later by the player). Has no electrical effect
        until the unit is ONLINE (see FleetModel.q_injections(), which sums
        only ONLINE units).

        Args:
            q_mvar: Reactive injection in MVAr. Clamped to [q_min_mvar, q_max_mvar].

        Returns:
            True (always accepted).
        """
        self._q_injection_mvar = max(
            self._spec.q_min_mvar,
            min(self._spec.q_max_mvar, float(q_mvar))
        )
        return True

    def set_renewable_output(self, output_mw: float) -> None:
        """
        Override current output for renewable units (WIND/SOLAR).

        Called each tick by the renewables model. Clamped to [0, rated_mw].
        Has no effect on non-renewable units.
        """
        if not self._is_renewable:
            return
        self._current_mw = max(0.0, min(self._spec.rated_mw, float(output_mw)))
        self._target_mw = self._current_mw

    # ─────── TICK ─────────────────────────────────────────────────────────

    def tick(self, dt_sim_seconds: float) -> None:
        """
        Advance unit state by dt_sim_seconds of simulated time.

        Args:
            dt_sim_seconds: Elapsed simulated time this tick (seconds).
        """
        if self._state == 'OFFLINE':
            return

        if self._state == 'STARTING':
            self._tick_starting(dt_sim_seconds)
            return

        if self._state == 'ONLINE':
            self._tick_online(dt_sim_seconds)
            return

        if self._state == 'SHUTDOWN':
            self._tick_shutdown(dt_sim_seconds)

    # ─────── TICK HELPERS ─────────────────────────────────────────────────

    def _tick_starting(self, dt_sim_seconds: float) -> None:
        """Advance cold start timer. Transition to ONLINE when complete."""
        dt_min = dt_sim_seconds / 60.0
        self._start_timer_min += dt_min

        if self._start_timer_min >= self._spec.cold_start_min:
            self._state = 'ONLINE'
            self._start_timer_min = 0.0
            self._current_mw = self._spec.min_mw
            self._target_mw = self._spec.min_mw
            self._agc_offset_mw = 0.0
            if DEBUG_SIMULATION:
                logging.getLogger('sim').debug(f'[UNITS] {self.label} STARTING -> ONLINE '
                                               f'(min output {self._spec.min_mw:.1f} MW)')

    def _tick_online(self, dt_sim_seconds: float) -> None:
        """Ramp output toward (target + any active drift offset) at the
        unit's ramp rate — a drifting unit chases the WRONG value, exactly
        as if it had been commanded there, until the drift clears (see
        drift()/clear_drift())."""
        if self._is_renewable:
            return  # renewable output is set externally

        ramp_mw_per_sec = (self._spec.ramp_pct_per_min / 100.0) \
                          * self._spec.rated_mw / 60.0
        max_delta = ramp_mw_per_sec * dt_sim_seconds

        chase_mw = self._target_mw + self._drift_offset_mw
        delta = chase_mw - self._current_mw
        if abs(delta) <= max_delta:
            self._current_mw = chase_mw
        else:
            self._current_mw += max_delta if delta > 0.0 else -max_delta

        # Enforce output bounds. Upper bound is rated_mw, not effective_max_mw —
        # a fresh derate cap below current_mw must be ramped down to via
        # target_mw (set in derate()), not snapped here in the same tick.
        # A drift offset can legitimately push current_mw above target_mw
        # (that's the point), but never past the unit's real physical limits.
        self._current_mw = max(
            self._spec.min_mw,
            min(self._spec.rated_mw, self._current_mw)
        )

    def _tick_shutdown(self, dt_sim_seconds: float) -> None:
        """Ramp down toward 0. Transition to OFFLINE when output reaches 0."""
        ramp_mw_per_sec = (self._spec.ramp_pct_per_min / 100.0) \
                          * self._spec.rated_mw / 60.0
        max_delta = ramp_mw_per_sec * dt_sim_seconds

        self._current_mw = max(0.0, self._current_mw - max_delta)

        if self._current_mw <= 0.0:
            self._current_mw = 0.0
            self._state = 'OFFLINE'
            self._q_injection_mvar = 0.0
            if DEBUG_SIMULATION:
                logging.getLogger('sim').debug(f'[UNITS] {self.label} SHUTDOWN -> OFFLINE')


class FleetModel:
    """
    Manages all UnitModel instances for the active shift.

    Constructed from a Grid object — creates one UnitModel per active unit.
    Provides aggregate queries (total generation, inertia, reserve) and
    routes player commands to individual units.

    Usage:
        fleet = FleetModel(grid)
        fleet.start_unit('ASHG-1')
        fleet.set_unit_target('RVSD-1', 250.0)
        fleet.tick(dt_sim_seconds)
        total_mw = fleet.total_generation_mw()
    """

    def __init__(
        self,
        grid,
        initial_schedule: dict[str, float] | None = None,
        maintenance_units: set[str] | None = None,
    ) -> None:
        """
        Build unit models from the grid's active fleet.

        Args:
            grid:              Grid object for the active shift.
            initial_schedule:  {unit_label: initial_mw} starting dispatch.
                               Units in the schedule start ONLINE at the given MW.
                               Units not in the schedule start OFFLINE
                               (except renewables, which always start ONLINE).
            maintenance_units: Set of unit labels that are on planned maintenance
                               and cannot be started by the player this shift.
        """
        initial_schedule  = initial_schedule  or {}
        maintenance_units = maintenance_units or set()
        self._units: dict[str, UnitModel] = {}

        # Units named by a mid-shift AGC_EXCLUDE_UNITS scripted action, or
        # by Phase 1's per-unit AGC enrollment — excluded from AGC
        # eligibility regardless of unit_type, on top of the fixed
        # campaign-wide _sim_const.AGC_ELIGIBLE_TYPES filter. Instance
        # state (not _sim_const) since this varies per shift run and must
        # reset cleanly between shifts/test runs, unlike the type filter
        # itself, which never varies.
        self._agc_excluded_units: frozenset[str] = frozenset()

        for spec in grid.get_active_units():
            initial_mw = initial_schedule.get(spec.label)
            model = UnitModel(spec, initial_mw=initial_mw)
            if spec.label in maintenance_units:
                model.set_maintenance(True)
            self._units[spec.label] = model

    def set_agc_excluded_units(self, labels) -> None:
        """
        Set the units excluded from AGC eligibility regardless of type —
        the AGC_EXCLUDE_UNITS scripted action's effect. Pass an empty
        iterable to restore all units to normal type-based eligibility.
        """
        self._agc_excluded_units = frozenset(labels)

    # ─────── TICK ─────────────────────────────────────────────────────────

    def tick(self, dt_sim_seconds: float) -> None:
        """Advance all unit state machines by dt_sim_seconds."""
        for model in self._units.values():
            model.tick(dt_sim_seconds)

    # ─────── COMMANDS ─────────────────────────────────────────────────────

    def start_unit(self, label: str) -> bool:
        """Start an OFFLINE unit. Returns False if not found or not OFFLINE."""
        model = self._units.get(label)
        if model is None:
            return False
        return model.start()

    def stop_unit(self, label: str) -> bool:
        """Stop an ONLINE unit. Returns False if not found or not ONLINE."""
        model = self._units.get(label)
        if model is None:
            return False
        return model.stop()

    def trip_unit(self, label: str) -> None:
        """Protection trip — immediate OFFLINE from any state."""
        model = self._units.get(label)
        if model is not None:
            model.trip()

    def derate_unit(self, label: str, cap_mw: float) -> None:
        """Reduce a unit's dispatch ceiling to cap_mw (stays ONLINE)."""
        model = self._units.get(label)
        if model is not None:
            model.derate(cap_mw)

    def clear_unit_derate(self, label: str) -> None:
        """Remove an active derate — effective_max_mw returns to rated_mw."""
        model = self._units.get(label)
        if model is not None:
            model.clear_derate()

    def drift_unit(self, label: str, offset_mw: float) -> None:
        """Start a setpoint drift (see UnitModel.drift())."""
        model = self._units.get(label)
        if model is not None:
            model.drift(offset_mw)

    def clear_unit_drift(self, label: str) -> None:
        """Clear an active setpoint drift (see UnitModel.clear_drift())."""
        model = self._units.get(label)
        if model is not None:
            model.clear_drift()

    def clear_all_drifts(self) -> None:
        """Clear every active drift fleet-wide — called at each sim-hour
        boundary crossing (see GridSimulation._apply_hourly_schedule())."""
        for model in self._units.values():
            if model.is_drifting:
                model.clear_drift()

    def set_unit_target(self, label: str, target_mw: float) -> bool:
        """Set dispatch target. Returns False if not found or not ONLINE."""
        model = self._units.get(label)
        if model is None:
            return False
        return model.set_target(target_mw)

    def set_unit_q_target(self, label: str, q_mvar: float) -> bool:
        """Set reactive-power target. Returns False if the unit is not found."""
        model = self._units.get(label)
        if model is None:
            return False
        return model.set_q_target(q_mvar)

    def set_unit_auto_mode(self, label: str) -> bool:
        """Return a unit to AUTO dispatch mode. Returns False if not found or not ONLINE."""
        model = self._units.get(label)
        if model is None:
            return False
        return model.set_auto_mode()

    def get_unit_dispatch_mode(self, label: str) -> str:
        """Return a unit's dispatch mode ('AUTO'/'MANUAL'). 'MANUAL' if not found."""
        model = self._units.get(label)
        if model is None:
            return 'MANUAL'
        return model.dispatch_mode

    def set_renewable_output(self, label: str, output_mw: float) -> None:
        """Set renewable unit output. Has no effect on non-renewable units."""
        model = self._units.get(label)
        if model is not None:
            model.set_renewable_output(output_mw)

    def apply_agc_signal(self, delta_mw: float) -> dict[str, float]:
        """
        Distribute an AGC raise/lower signal among fast-response ONLINE units
        (fixed campaign-wide eligible types, _sim_const.AGC_ELIGIBLE_TYPES —
        HYDRO/CCGT, never per-shift), proportional to available headroom (raise) or
        regulating range above min_mw (lower). Units named by a mid-shift
        AGC_EXCLUDE_UNITS scripted action (self._agc_excluded_units) are
        skipped regardless of type. Calls set_target() so ramp rate limits
        apply on the next tick.

        Returns:
            {unit_label: new_target_mw} for every unit that received a share.
            Empty dict if no eligible units or total weight is too small.
        """
        eligible = [
            u for u in self._units.values()
            if u.state == 'ONLINE'
            and u._spec.unit_type in _sim_const.AGC_ELIGIBLE_TYPES
            and u._spec.label not in self._agc_excluded_units
        ]
        if not eligible:
            return {}

        if delta_mw > 0:
            weights = [max(0.0, u.effective_max_mw - u.current_mw) for u in eligible]
        else:
            weights = [
                max(0.0, u.current_mw - _TECH_MIN_FRAC.get(u._spec.unit_type, MIN_OUTPUT_FRACTION) * u._spec.rated_mw)
                for u in eligible
            ]

        total_w = sum(weights)
        if total_w < 1.0:
            return {}

        assignments: dict[str, float] = {}
        for unit, w in zip(eligible, weights):
            share = delta_mw * (w / total_w)
            unit._apply_agc_delta(share)
            assignments[unit.label] = unit.target_mw
        return assignments

    def apply_hourly_schedule(self, hour: float, hourly_schedule: dict[str, dict[float, float]]) -> None:
        """
        Advance every ONLINE unit in AUTO dispatch mode to its Phase 1
        planned MW for `hour`, plus whatever AGC-attributable offset it has
        accumulated since the last boundary (see UnitModel._agc_offset_mw) —
        preserves AGC's standing correction instead of discarding it in one
        step at the hour boundary. Called once per simulated-hour boundary
        by GridSimulation. MANUAL units and units absent from hourly_schedule
        are untouched; ramp-rate limiting still applies via the normal
        tick() path since this only sets target_mw, not current_mw.
        """
        for label, model in self._units.items():
            if model.state != 'ONLINE' or model.dispatch_mode != 'AUTO':
                continue
            hours = hourly_schedule.get(label)
            if hours is None or hour not in hours:
                continue
            model._set_target_internal(hours[hour] + model._agc_offset_mw)

    def agc_regulation_state(self) -> tuple[float, float, float]:
        """
        Return (current_mw, min_mw, max_mw) for all online AGC-eligible units.

        Used by the Regulation Availability indicator in the Power Balance panel.
        min_mw is derived from per-type technical minimum fractions (not fleet
        min_mw). Excludes units named by a mid-shift AGC_EXCLUDE_UNITS action
        (self._agc_excluded_units), same as apply_agc_signal(), so the
        indicator never reports capacity that dispatch can't actually use.
        """
        current = min_total = max_total = 0.0
        for unit in self._units.values():
            if unit.state != 'ONLINE':
                continue
            if unit._spec.unit_type not in _sim_const.AGC_ELIGIBLE_TYPES:
                continue
            if unit._spec.label in self._agc_excluded_units:
                continue
            frac = _TECH_MIN_FRAC.get(unit._spec.unit_type, MIN_OUTPUT_FRACTION)
            current   += unit.current_mw
            min_total += unit._spec.rated_mw * frac
            max_total += unit.effective_max_mw
        return current, min_total, max_total

    # ─────── QUERIES — INDIVIDUAL ─────────────────────────────────────────

    def get_unit(self, label: str) -> UnitModel:
        """
        Get unit model by label.

        Raises:
            KeyError: If label not in active fleet.
        """
        try:
            return self._units[label]
        except KeyError:
            raise KeyError(f"Unit {label!r} not in active fleet")

    def has_unit(self, label: str) -> bool:
        """True if unit is in the active fleet."""
        return label in self._units

    def online_dispatchable_labels(self) -> list[str]:
        """Labels of every ONLINE, non-renewable unit — the population
        eligible for random derate/drift events (see GridSimulation's
        deviation trigger roll). WIND/SOLAR are never dispatchable."""
        return [
            u.label for u in self._units.values()
            if u.state == 'ONLINE' and not u.is_renewable
        ]

    # ─────── QUERIES — AGGREGATE ──────────────────────────────────────────

    def total_generation_mw(self) -> float:
        """
        Sum of current_mw for all ONLINE or SHUTDOWN units. SHUTDOWN units
        still physically ramp down to 0 over _tick_shutdown() rather than
        dropping out instantly — excluding them here would create a
        one-tick generation cliff at every stop_unit() call, not the
        gradual ramp-down the state machine actually models.
        """
        return sum(
            m.current_mw for m in self._units.values()
            if m.state in ('ONLINE', 'SHUTDOWN')
        )

    def spinning_reserve_mw(self) -> float:
        """Sum of (effective_max_mw - current_mw) for all ONLINE units."""
        total = 0.0
        for m in self._units.values():
            if m.state == 'ONLINE':
                total += m.effective_max_mw - m.current_mw
        return total

    def online_unit_types(self) -> list[tuple[str, float]]:
        """
        Return [(unit_type, current_mw), ...] for all ONLINE units.
        Used by FrequencyModel to compute weighted system inertia.
        """
        return [
            (m._spec.unit_type, m.current_mw)
            for m in self._units.values()
            if m.state == 'ONLINE'
        ]

    def p_injections(self) -> dict[str, float]:
        """
        Build {bus_label: net_p_mw} injection dict for the load flow solver.

        Sums ONLINE and SHUTDOWN unit outputs at each bus (SHUTDOWN units
        are still ramping down, not yet at 0 — see total_generation_mw()).
        Load buses are not included — the simulation adds load injections separately.
        """
        result: dict[str, float] = {}
        for m in self._units.values():
            if m.state in ('ONLINE', 'SHUTDOWN') and m.current_mw > 0.0:
                bus = m._spec.bus_label
                result[bus] = result.get(bus, 0.0) + m.current_mw
        return result

    def q_injections(self) -> dict[str, float]:
        """
        Build {bus_label: net_q_mvar} reactive injection dict for the voltage solver.

        Sums ONLINE and SHUTDOWN unit Q injections at each bus — a SHUTDOWN
        unit's q_injection_mvar is unchanged by _tick_shutdown() (only
        current_mw ramps), so it keeps its pre-stop() reactive output until
        it actually reaches OFFLINE, where trip()/the final transition
        zeroes it.
        """
        result: dict[str, float] = {}
        for m in self._units.values():
            if m.state in ('ONLINE', 'SHUTDOWN'):
                bus = m._spec.bus_label
                result[bus] = result.get(bus, 0.0) + m.q_injection_mvar
        return result

    # ─────── STATE SNAPSHOT ───────────────────────────────────────────────

    def get_state_snapshot(self) -> dict[str, dict]:
        """
        Return a complete snapshot of fleet state for SimulationState construction.

        Returns:
            {unit_label: {
                'state': str,
                'current_mw': float,
                'target_mw': float,
                'q_mvar': float,
                'start_progress': float,
                'q_target_mvar': float,  # player-commanded reactive target
                'q_reserve_mvar': float,  # headroom to q_max_mvar; 0.0 if not ONLINE
            }}
        """
        snapshot = {}
        for label, m in self._units.items():
            snapshot[label] = {
                'state': m.state,
                'current_mw': m.current_mw,
                'target_mw': m.target_mw,
                'q_mvar': m.q_injection_mvar,
                'start_progress': m.start_progress,
                'q_target_mvar': m.q_injection_mvar,
                'q_reserve_mvar': (
                    max(0.0, m._spec.q_max_mvar - m.q_injection_mvar)
                    if m.state == 'ONLINE' else 0.0
                ),
                'dispatch_mode': m.dispatch_mode,
            }
        return snapshot

    def get_maintenance_units(self) -> frozenset[str]:
        """Return frozenset of unit labels currently flagged as on maintenance."""
        return frozenset(lbl for lbl, m in self._units.items() if m.is_maintenance)

    def get_agc_enabled_units(self) -> frozenset[str]:
        """
        Return frozenset of unit labels currently AGC-participating: eligible
        type, not excluded, and ONLINE right now. Mirrors the eligibility
        filter in apply_agc_signal()/agc_regulation_state() exactly, so it
        reflects live AGC participation rather than static type eligibility
        or Phase 1 enrollment intent.
        """
        return frozenset(
            lbl for lbl, m in self._units.items()
            if m.state == 'ONLINE'
            and m._spec.unit_type in _sim_const.AGC_ELIGIBLE_TYPES
            and lbl not in self._agc_excluded_units
        )
