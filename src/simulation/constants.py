"""
src/simulation/constants.py

All constants for the GRIDCOM simulation and display.
Every numeric value, threshold, timing, and configuration parameter lives here.
No hardcoded numbers anywhere else in the codebase.

See CLAUDE.md Rule 1.
"""

import pygame

# ─────────────────────────────────────────────
# DEBUG FLAGS
# ─────────────────────────────────────────────
DEBUG_SIMULATION: bool = False
DEBUG_DISPLAY:    bool = False
DEBUG_PERF:       bool = False  # per-frame render timing breakdown — see PERF_DEBUG_LOG
DEBUG_EVENTS:     bool = True
EDITOR_MODE:      bool = False
FLOW_ANIMATION:        bool = False
DEBUG_SCENARIO_ACTIVE: bool = False
DEV_SKIP_INTRO:        bool = True
VOLTAGE_COLOUR_VIEW:   bool = True  # 'L' toggle — colour lines/substations by voltage tier instead of load

# ─────────────────────────────────────────────
# DIFFICULTY
# ─────────────────────────────────────────────
# General-purpose scalar keyed by the menu's trainee/standard/dispatcher
# selection (GridSimulation's difficulty: str, set at construction —
# previously stored but never read by any mechanic). Not scoped to any one
# feature: any mechanic that wants to scale a rate/magnitude/frequency by
# player-chosen difficulty should read this rather than inventing its own
# difficulty dial. A difficulty string not present in this dict resolves
# to 1.0 (standard) via .get(). First consumer: random unit deviation
# (derate/drift) chance-per-hour scaling — see UNIT DEVIATION below.
DIFFICULTY_MULT: dict[str, float] = {
    'trainee':    0.5,
    'standard':   1.0,
    'dispatcher': 1.6,
}

# ─────────────────────────────────────────────
# POWER SYSTEM BASE VALUES
# ─────────────────────────────────────────────
S_BASE: float = 1000.0          # MVA base for per-unit calculations
F_NOMINAL: float = 50.0         # Hz — nominal system frequency
V_NOMINAL_400: float = 400.0    # kV
V_NOMINAL_220: float = 220.0    # kV
V_NOMINAL_150: float = 150.0    # kV

# ─────────────────────────────────────────────
# NETWORK TOPOLOGY
# ─────────────────────────────────────────────
SLACK_BUS: str = 'MDBY'         # Slack bus — voltage angle reference (θ = 0)

# ─────────────────────────────────────────────
# LOAD FLOW NUMERICAL
# ─────────────────────────────────────────────
YSHUNT_REG:  float = 1e-6   # DC load flow B matrix: diagonal shunt for numerical stability
VSHUNT_REG:  float = 0.1    # Voltage B' matrix: stronger shunt for isolated load buses

# ─────────────────────────────────────────────
# VOLTAGE THRESHOLDS (per-unit)
# ─────────────────────────────────────────────
V_HEALTHY_HIGH:   float = 1.05  # Above nominal — upper healthy limit
V_HEALTHY_LOW:    float = 0.95  # Below nominal — lower healthy limit
V_WATCH_LOW:      float = 0.90  # Watch threshold
V_WARNING_LOW:    float = 0.85  # Warning threshold — collapse acceleration begins
V_CRITICAL_LOW:   float = 0.70  # Blackout threshold
V_COLLAPSE_GAIN:  float = 0.01  # Gain factor for voltage collapse acceleration — reduced
                                # from 2.0 (~200x) so a sustained bad bus collapses over
                                # ~10-20 real seconds instead of within a single tick.
V_COLLAPSE_SEVERITY_LOW:   float = 0.85  # Severity = 0 at this voltage (== V_WARNING_LOW)
V_COLLAPSE_SEVERITY_FLOOR: float = 0.70  # Severity = 1 at this voltage (== V_CRITICAL_LOW)
V_COLLAPSE_RECOVERY_PU_S:  float = 0.00035  # Offset decay rate toward 0 when voltage recovers
                                            # (pu/sim-second) — reduced from 0.02 so recovery
                                            # takes ~3x the worst-case decay time (was ~44x).

# PV→PQ correction: the decoupled voltage solver adjusts each PV bus's Q to
# hold its target voltage, then re-solves. A single pass is only adequate
# when every PV bus has one dominant electrical path; buses with two
# comparable paths (or one very weak/remote path) need the correction
# iterated to a fixed point, or Q never settles and the bus can diverge.
PV_CORRECTION_MAX_ITERS:   int   = 8    # hard cap — solve can never hang the tick
PV_CORRECTION_Q_TOL_MVAR:  float = 0.5  # early exit once the largest per-pass Q change falls below this

# ─────────────────────────────────────────────
# REACTIVE POWER / SUBSTATION LOAD TYPES
# ─────────────────────────────────────────────
# Power factor by load-substation type — determines each type's reactive
# (MVAr) draw relative to its active (MW) load: Q = P * tan(acos(PF)).
PF_INDUSTRIAL: float = 0.85  # low PF — heavy inductive motor load, sags voltage most
PF_RESIDENTIAL: float = 0.97  # high PF — mostly resistive/electronic load
PF_MIXED:       float = 0.92  # blended commercial/residential

SUBSTATION_TYPE_PF: dict = {
    'INDUSTRIAL': PF_INDUSTRIAL,
    'RESIDENTIAL': PF_RESIDENTIAL,
    'MIXED': PF_MIXED,
}

# Generator reactive-power target (MVAr) — player-editable, clamped per unit
# to [q_min_mvar, q_max_mvar] (data/fleet.py), not a single global range —
# every unit's Q capability differs, unlike the AVR pu setpoint this replaced.

# ─────────────────────────────────────────────
# REACTIVE DEVICES — automatic shunt banks, manual SVC
# ─────────────────────────────────────────────
# Automatic shunt capacitor/reactor bank: discrete steps, +cap/-reactor MVAr,
# deadband + hysteresis + minimum dwell time between switches to prevent hunting.
SHUNT_BANK_MVAR_PER_STEP: float = 50.0
SHUNT_BANK_MAX_STEPS:     int   = 4
SHUNT_DEADBAND_LOW_PU:    float = 0.97
SHUNT_DEADBAND_HIGH_PU:   float = 1.03
SHUNT_SWITCH_DWELL_S:     float = 30.0  # minimum simulated seconds between switches

# Manual continuous SVC/STATCOM — player-set MVAr setpoint.
SVC_Q_MIN_MVAR:  float = -150.0
SVC_Q_MAX_MVAR:  float =  150.0

# Line charging (Ferranti effect) — an energised line injects reactive
# power locally at BOTH ends, proportional to its length, raising nearby
# voltage even when it carries no load. Modelled the same way the shunt
# bank/SVC reactive devices already are (reactive_devices.py) — a fixed
# MVAr injection per bus, fed into simulation.py's _build_q_injections()
# — NOT a change to voltage.py's B' matrix, since Q injections here are
# solver inputs, not admittance terms (VSHUNT_REG is a numerical-stability
# regulariser and a different thing). Only in-service lines contribute
# (simulation.py's _get_in_service_lines() — a tripped/open line charges
# nothing), so closing a spare/parallel circuit and leaving it closed has
# a real, small, visible voltage cost instead of being a free action —
# first used by the Shift 2/3 N-1 tutorial lesson but applies to every
# shift. Magnitude is a first-pass playtest value, not derived from a
# formula — verified empirically against the new tutorial.json grid:
# small enough that a 100+km weak-feed line (Shift 2's Fenwick lesson)
# doesn't pre-saturate the supporting generator's Q range regardless of
# AVR setpoint, while still giving a short ~20km spare/parallel circuit
# (Shift 2/3's N-1 lesson) a real, non-zero MVAr contribution when closed.
LINE_CHARGING_MVAR_PER_KM_150KV: float = 0.06
LINE_CHARGING_MVAR_PER_KM_220KV: float = 0.15
LINE_CHARGING_MVAR_PER_KM_400KV: float = 0.4
SVC_Q_STEP_MVAR: float =   10.0  # per keyboard adjust command

# Unit active-power nudge (G to arm, Up/Down to step) — alternative to
# typing an exact MW target via digit keys + Enter.
UNIT_MW_STEP:       float =  1.0  # MW per keyboard adjust command
UNIT_MW_STEP_FAST_MULT: float = 5.0  # Ctrl+Up/Down multiplier (1 MW * 5 = 5 MW)

# Reactive-power target nudge (Q key arms, Up/Down adjusts). Clamped per unit
# to its own [q_min_mvar, q_max_mvar] (data/fleet.py) — every unit's Q range
# differs, so there is no single global band to size the step against.
GEN_Q_SETPOINT_STEP_MVAR:        float = 5.0
GEN_Q_SETPOINT_STEP_FAST_MULT:   float = 5.0  # Ctrl+Up/Down (5 * 5 = 25 MVAr)

# ─────────────────────────────────────────────
# FREQUENCY THRESHOLDS (Hz)
# ─────────────────────────────────────────────
F_MAX:            float = 55.0  # Hard clamp maximum
F_MIN:            float = 45.0  # Hard clamp minimum
F_ALERT_HIGH:     float = 50.2  # Warning alarm threshold (above nominal)
F_ALERT_LOW:      float = 49.8  # Warning alarm threshold (below nominal)
F_CRITICAL_HIGH:  float = 50.5  # Critical alarm threshold
F_CRITICAL_LOW:   float = 49.5  # Critical alarm threshold
F_TRIP_ISLAND_HIGH: float = 50.5  # Over-frequency relay trip for isolated islands
F_TRIP_ISLAND_LOW:  float = 49.5  # Under-frequency relay trip for isolated islands
F_IN_BOUNDS_TOL:  float = 0.2   # Tolerance for frequency_in_bounds_pct scoring
F_STABLE_TOL:     float = 0.005 # Hz — threshold for STABLE vs RISING/FALLING trend

FREQ_TOLERANCE_MULT: float = 1.0  # Per-shift multiplier on F_ALERT_*/F_CRITICAL_*'s
                                   # deltas from F_NOMINAL — widened for tutorial
                                   # shifts via shift_NN.py's FREQ_TOLERANCE_MULT.
                                   # F_MIN/F_MAX (hard clamp) are never scaled.

FREQ_HISTORY_WINDOW_S: float = 60.0  # Real seconds of history shown in the frequency trend plot

# ─────────────────────────────────────────────
# AUTOMATIC GENERATION CONTROL (AGC)
# ─────────────────────────────────────────────
AGC_ENABLED:       bool  = True  # Toggled at runtime via Ctrl+A; starts disabled
AGC_KP:            float = 100.0    # Proportional gain (MW per Hz of error)
AGC_KI:            float = 5.0    # Integral gain (MW per Hz·sim-second of error) —
                                   # raised from 0.01 so integral action is numerically
                                   # significant against AGC_INTEGRAL_MAX (was capped at
                                   # 0.05 MW, effectively dead — AGC parked at a P-term-only
                                   # offset instead of returning frequency to nominal).
AGC_KD:            float = 2000.0  # Derivative gain (MW per Hz/sim-second of error) —
                                   # cut from 1000.0 so it damps transients without
                                   # dominating now that KI is doing real work.
AGC_MAX_RATE_MW_S: float = 100.0   # Max total AGC correction rate (MW per sim-second)
AGC_DEADBAND_HZ:   float = 0.01   # ±Hz inside which AGC is silent
AGC_INTEGRAL_MAX:  float = 60.0   # Anti-windup clamp on integral accumulator (Hz·s) —
                                   # raised from 5.0; AGC_KI * AGC_INTEGRAL_MAX = 300 MW,
                                   # sized to fully close realistic sustained deficits.
AGC_LOG:           bool  = True  # Write per-tick PID data to agc_log.csv when True

# Unit types eligible for AGC dispatch. Fixed for every shift at every
# difficulty — CCGT and (conventional/cascade) HYDRO are always AGC-capable
# fast-response plant; not a per-shift or per-difficulty setting. Run-of-
# river has no stored head to draw on (HYDRO_ROR) and pumped storage is
# excluded too (HYDRO_PUMP) — neither is ever eligible.
# FleetModel.apply_agc_signal()/agc_regulation_state() read this live via
# _sim_const.AGC_ELIGIBLE_TYPES (see units.py).
AGC_ELIGIBLE_TYPES: frozenset[str] = frozenset({'HYDRO', 'CCGT'})

AGC_SPEED_MULT: float = 1.0  # Per-shift multiplier on AGC_MAX_RATE_MW_S and AGC_KI
                              # together (both scaled the same way, since scaling
                              # either alone risks a sluggish-but-still-100%-authoritative
                              # or a fast-integral-hitting-a-wall controller instead of a
                              # genuinely slower one) — read live in _apply_agc() via
                              # _sim_const.AGC_SPEED_MULT, set per-shift via
                              # shift_NN.py's AGC_SPEED_MULT. 1.0 = today's baseline.
SIM_DEBUG_LOG:     str   = 'logs/sim_debug.log'  # DEBUG_SIMULATION output destination
PERF_DEBUG_LOG:    str   = 'logs/perf_debug.log'  # DEBUG_PERF output destination
PERF_LOG_INTERVAL_S: float = 1.0  # seconds between perf-log summary lines
SIM_STATE_LOG:      bool = True  # Write full per-tick bus/unit state to sim_state.csv when True
SIM_STATE_LOG_PATH: str  = 'logs/sim_state.csv'

# ─────────────────────────────────────────────
# LOSSES
# ─────────────────────────────────────────────
LOSSES_FRACTION: float = 0.025  # 2.5% of total generation added to load

# ─────────────────────────────────────────────
# LINE TRIP / CASCADE
# ─────────────────────────────────────────────
TRIP_DELAY_S:        float = 720.0  # Seconds (SIM-time) a line must be >100% before tripping —
                                     # 720 / TIME_COMPRESSION(24) = 30 real seconds at 1x speed,
                                     # raised from 60.0 (was only 1.25 real seconds — unreadable).

BLACKOUT_TRIP_S:     float = 360.0  # Seconds (SIM-time) frequency must stay pinned at the
                                     # F_MIN/F_MAX hard clamp before the shift ends as FAILED —
                                     # 360 / TIME_COMPRESSION(24) = 15 real seconds at 1x speed.
OVERLOAD_WARN_PCT:   float = 85.0   # Loading % at which WARNING alarm fires
OVERLOAD_CRIT_PCT:   float = 100.0  # Loading % at which overload timer starts

# Severity-scaled overload accumulation. Real protection relays are
# inverse-time: the harder a line is overloaded, the sooner it trips. The
# timer accrues dt * (1 + (excess_pct / OVERLOAD_SEVERITY_REF_PCT)), so a
# line at 100% accrues at 1x and one at 150% accrues at 3x with the
# reference below — letting the player triage a bad line from a doomed one.
# Capped so an extreme transient cannot skip the countdown entirely.
OVERLOAD_SEVERITY_REF_PCT:  float = 25.0  # % over rating that doubles the accrual rate
OVERLOAD_SEVERITY_MAX_MULT: float = 6.0   # hard ceiling on the accrual multiplier

# Below 100% the timer DECAYS rather than hard-resetting to zero: a line
# that has been cooking for ten minutes is not instantly healthy the moment
# it dips to 99%. Decay is this multiple of real elapsed time, so recovery
# is faster than accumulation but not free.
OVERLOAD_DECAY_RATE: float = 2.0

# ─────────────────────────────────────────────
# RAMP RATES (% of rated MW per simulated minute)
# ─────────────────────────────────────────────
RAMP_COAL_PCT_MIN:    float = 3.0
RAMP_CCGT_PCT_MIN:    float = 8.0
RAMP_NUCLEAR_PCT_MIN: float = 1.0
RAMP_HYDRO_PCT_MIN:   float = 100.0  # Near-instant

# ─────────────────────────────────────────────
# INERTIA CONSTANTS (seconds)
# ─────────────────────────────────────────────
H_COAL:    float = 5.0
H_CCGT:    float = 4.0
H_NUCLEAR: float = 6.0
H_HYDRO:   float = 3.0
H_WIND:    float = 0.0
H_SOLAR:   float = 0.0

# ─────────────────────────────────────────────
# COLD START TIMES (simulated minutes)
# ─────────────────────────────────────────────
COLD_START_COAL_MIN:    float = 240.0   # 4 hours
COLD_START_CCGT_MIN:    float = 60.0    # 1 hour
COLD_START_NUCLEAR_MIN: float = 480.0   # 8 hours (not used — nuclear always on)
COLD_START_HYDRO_MIN:   float = 5.0     # 5 minutes

# ─────────────────────────────────────────────
# UNIT OUTPUT LIMITS
# ─────────────────────────────────────────────
MIN_OUTPUT_FRACTION: float = 0.20       # Legacy fallback minimum (20% of rated)

# Technical minimum output by unit type (fraction of rated_mw).
# Below this level, stable generation cannot be sustained.
TECH_MIN_FRAC_HYDRO:      float = 0.10
TECH_MIN_FRAC_HYDRO_ROR:  float = 0.10
TECH_MIN_FRAC_HYDRO_PUMP: float = 0.10
TECH_MIN_FRAC_WIND:       float = 0.00
TECH_MIN_FRAC_SOLAR:      float = 0.00
TECH_MIN_FRAC_CCGT:       float = 0.25
TECH_MIN_FRAC_COAL:       float = 0.35
TECH_MIN_FRAC_NUCLEAR:    float = 0.60

# Minimum cooldown after shutdown before restart is permitted (simulated minutes).
COOLDOWN_MIN_HYDRO:       float =   2.0
COOLDOWN_MIN_HYDRO_ROR:   float =   2.0
COOLDOWN_MIN_HYDRO_PUMP:  float =   5.0
COOLDOWN_MIN_WIND:        float =   1.0
COOLDOWN_MIN_SOLAR:       float =   1.0
COOLDOWN_MIN_CCGT:        float =  45.0
COOLDOWN_MIN_COAL:        float = 150.0
COOLDOWN_MIN_NUCLEAR:     float = 360.0

# ─────────────────────────────────────────────
# PUMPED STORAGE
# ─────────────────────────────────────────────
PUMP_MODE_TRANSITION_MIN: float = 8.0   # Simulated minutes for mode change
RESERVOIR_WARN_LOW:  float = 0.15       # Below this: cannot generate
RESERVOIR_WARN_HIGH: float = 0.90       # Above this: cannot pump

# ─────────────────────────────────────────────
# INTERCONNECTORS
# ─────────────────────────────────────────────
INTC_N_CAPACITY_MW: float = 800.0       # INTC-N max import/export
INTC_S_CAPACITY_MW: float = 600.0       # INTC-S max import/export

# ─────────────────────────────────────────────
# LINE RATINGS
# ─────────────────────────────────────────────
LINE_RATING_MW_BY_VOLTAGE: dict = {     # Flat MW rating per nominal line voltage tier
    400.0: 2250.0,
    220.0:  400.0,
    150.0:  175.0,
}
GENERATOR_CONNECTOR_RATING_MW: float = 5000.0  # Flat rating for lines that are a station's sole
                                                # electrical egress into the wider grid (overrides
                                                # the flat per-voltage-tier default for just these
                                                # specific lines — see topology.py usage)
CONSOLIDATED_FEED_RATING_MW_TRIPLE: float = 1250.0  # Feed rating for a single-region Shift-10 load
                                                     # substation dual-fed directly from its
                                                     # region's own 2 spine-anchor buses
                                                     # (~950-1035 MW peak) — a single surviving feed
                                                     # must carry the whole region's load under N-1
CONSOLIDATED_FEED_RATING_MW_CAP:    float = 2400.0  # Feed rating for CAP's single consolidated
                                                     # substation (~1988 MW peak, merged from what
                                                     # were 2 substations) — CAP has only 2
                                                     # independent spine-anchor buses (ASHF, WRNT),
                                                     # so it hosts exactly 1 substation, sized to
                                                     # cover the region's full former 2-substation
                                                     # demand under N-1
CONSOLIDATED_FEED_RATING_MW_WEST:   float = 3100.0  # Feed rating for WEST's single consolidated
                                                     # substation (~2591 MW peak, merged from what
                                                     # were 3 substations) — same reasoning as CAP,
                                                     # WEST's 2 spine-anchor buses (DUND, RDST) can
                                                     # only safely host 1 substation

# ─────────────────────────────────────────────
# SIMULATION TIMING
# ─────────────────────────────────────────────
SIM_TICKS_PER_SECOND: int   = 10        # Simulation ticks per real second
TIME_COMPRESSION:     float = 24.0      # 1 sim hour = 2.5 real minutes — halved from 48.0
                                         # so a shift's demand ramp and frequency swings leave
                                         # a first-time player real reaction time (was 1.25
                                         # real min/sim hour, too fast to think->act->observe).

# Minimum time (real seconds — converted to SIM-time seconds below via
# TIME_COMPRESSION) a line must wait after ANY switch — trip or close,
# manual or automatic — before it can be switched again. Models real
# switching/synchrocheck procedure: higher voltage tiers take longer to
# safely reclose. Scales with difficulty (same trainee/standard/dispatcher
# keys as DIFFICULTY_MULT above) rather than being a per-shift opt-in —
# this is a procedural/physical constraint every shift has, not a shift-
# specific difficulty lever, so every shift gets it automatically at
# whatever level the player chose. A voltage tier absent from the active
# difficulty's dict falls back to LINE_RECLOSE_COOLDOWN_DEFAULT_S (no
# cooldown). See simulation.py's _start_reclose_cooldown() for the lookup
# (keyed by both self._difficulty and the line's voltage_kv).
LINE_RECLOSE_COOLDOWN_S_BY_DIFFICULTY: dict[str, dict[float, float]] = {
    'trainee': {
        150.0: 3.0  * TIME_COMPRESSION,
        220.0: 6.0  * TIME_COMPRESSION,
        400.0: 12.0 * TIME_COMPRESSION,
    },
    'standard': {
        150.0: 5.0  * TIME_COMPRESSION,
        220.0: 15.0 * TIME_COMPRESSION,
        400.0: 30.0 * TIME_COMPRESSION,
    },
    'dispatcher': {
        150.0: 15.0 * TIME_COMPRESSION,
        220.0: 30.0 * TIME_COMPRESSION,
        400.0: 60.0 * TIME_COMPRESSION,
    },
}
LINE_RECLOSE_COOLDOWN_DEFAULT_S: float = 0.0  # Cooldown for a voltage tier absent from the active dict

# Real seconds the sim clock holds at shift start (T+0) before demand,
# renewables, and scripted-event timers begin advancing — frequency/AGC/
# load-flow/voltage keep running normally throughout, so the player sees a
# live, stable grid rather than a paused screenshot while reading the
# handover. A UX courtesy, not a difficulty knob — kept short on hard
# shifts. Per-shift overridable via shift_NN.py's LANDING_FREEZE_S, same
# pattern as AGC_SPEED_MULT/FREQ_TOLERANCE_MULT.
LANDING_FREEZE_S: float = 5.0

# ─────────────────────────────────────────────
# FREQUENCY DYNAMICS
# ─────────────────────────────────────────────
# Multiplier on df/dt applied on top of the already-compressed sim-second
# timestep. Frequency is the one subsystem that must NOT run at full
# TIME_COMPRESSION speed (real dispatchers react to frequency in real time,
# not compressed time) -- this tunable dial sets how fast a disturbance
# reaches the player, independent of TIME_COMPRESSION. Read live via
# _sim_const.FREQ_DYNAMICS_SCALE in frequency.py (not a bare imported name),
# so it can be retuned/verified without a process restart.
# Not derived from any other constant -- retune against playtest/verification
# harness, not by formula.
# Retuned 0.02 -> 0.005 (developer report: real-time play reacts too fast
# to control even at 1x, worst on Shift 10). Headless do-nothing trace
# against Shift 10's real grid/fleet (auto-scheduled plan, 1x speed):
#   0.02 (old)  leaves the alert band at  13.8 real-s, bottoms at F_MIN (45.0)
#   0.005 (new) leaves the alert band at  21.7 real-s, still bottoms at F_MIN
# ~1.6x more reaction time before the alert band, without going low enough
# to blunt frequency response on easier shifts (single-unit-trip scale
# disturbances) into feeling sluggish. Does not by itself make Shift 10
# recoverable by reaction speed alone -- its do-nothing/responsive-player
# gap is a separate, structural AGC-headroom shortfall in the Phase 1
# auto-scheduler, not a frequency-timing issue; deferred as a follow-up.
FREQ_DYNAMICS_SCALE: float = 0.005

# ─────────────────────────────────────────────
# DISPLAY / RENDERING
# ─────────────────────────────────────────────
NATIVE_WIDTH:  int = 1920
NATIVE_HEIGHT: int = 1080
TITLE_BAR_HEIGHT: int = 22      # Top-most row — shift description, moved up out of the
                                # canvas (was drawn overlapping the canvas's top pixels)
                                # into its own dedicated row above the topbar
TOPBAR_HEIGHT: int = 60         # Power balance bar — below the title row
CANVAS_HEIGHT: int = 762        # Middle portion — grid schematic — shrunk 22px (TITLE_BAR_HEIGHT)
                                # to make room for the new title row, holding NATIVE_HEIGHT
                                # fixed at 1080
STRIP_HEIGHT:  int = 192        # Instrument strip — shrunk 2 rows (was 236) to make
                                # room for HINT_GAP_HEIGHT + HINT_BAR_HEIGHT below it,
                                # holding NATIVE_HEIGHT fixed at 1080
                                # (22+60+762+192+22+22 = 1080)
HINT_GAP_HEIGHT: int = 22       # Blank row between the strip and the shortcut hint bar
HINT_BAR_HEIGHT: int = 22       # Bottom-most row — context-sensitive keyboard shortcut hint
TARGET_FPS:           int   = 60
SIM_TICK_INTERVAL_S:  float = 0.1    # Simulation advances at 10 Hz regardless of render FPS
LETTERBOX_COLOUR: tuple[int, int, int] = (0, 0, 0)

FONT_PATH_MONO_REGULAR:  str = 'assets/fonts/TerminusTTF-4.49.3.ttf' #'assets/fonts/Px437_IBM_VGA_8x16.ttf'

FONT_ANTIALIAS_THRESHOLD: int = 11      # px — disable antialiasing at or below this size
FONT_SIZE_LABEL:          int = 17      # bus/station labels on canvas
LABEL_PAD_PX:             int = 3       # px — gap between a label and the symbol it labels
FONT_SIZE_OVERLAY:        int = 15      # interconnector labels, debug overlay
FONT_SIZE_PANEL:          int = 16      # standard instrument strip text
FONT_SIZE_HINT:           int = 15      # bottom-of-screen keyboard shortcut hint bar
FONT_SIZE_PANEL_LARGE:    int = 30      # frequency Hz readout
FONT_SIZE_CONTEXT:        int = 17      # unit context overlay text

UNIT_BORDER_W_PX:          int = 3       # px — generation unit square border, normal
UNIT_BORDER_W_SELECTED_PX: int = 4       # px — generation unit square border, selected

TYPEWRITER_CHARS_PER_SEC: int   = 400  # Characters revealed per real second on text screens
TEXT_SCREEN_FONT_SIZE:    int   = 17   # px — font size for briefing/debrief screens
TEXT_SCREEN_LEFT_MARGIN:  int   = 120  # px — left margin at native 1920×1080
TEXT_SCREEN_TOP_MARGIN:   int   = 80   # px — top margin at native 1920×1080
TEXT_SCREEN_ROW_H:        int   = 22   # px — row height at native 1920×1080

SPLASH_DURATION_S:  float = 4.0   # seconds before splash auto-advances to main menu
MENU_FONT_SIZE:     int   = 20    # px — menu item font size
MENU_ROW_H:         int   = 30    # px — row height for menu items
MENU_LEFT_MARGIN:   int   = 120   # px — left margin for menus (matches text screen)
MENU_TOP_MARGIN:    int   = 440   # px — top margin for menu item list (below art title block)

# ─────────────────────────────────────────────
# UNIT CONTEXT OVERLAY
# ─────────────────────────────────────────────
CONTEXT_OVERLAY_X:     int = 8     # px from canvas left edge
CONTEXT_OVERLAY_Y:     int = 8     # px from canvas top edge
CONTEXT_OVERLAY_W:     int = 288   # panel width in px
CONTEXT_OVERLAY_PAD:   int = 6     # inner padding
CONTEXT_OVERLAY_ROW_H: int = 19    # text row height
CONTEXT_OVERLAY_HDR_H: int = 22    # header row height

# ─────────────────────────────────────────────
# VSI VOLTAGE HALOS + REACTIVE DEVICE GLYPHS
# ─────────────────────────────────────────────
VSI_HALO_RADIUS_PX: int   = 20     # px — halo ring radius around a substation symbol
VSI_HALO_WIDTH_PX:  int   = 2      # px — halo ring stroke width
VSI_HALO_BLINK_HZ:  float = 2.0    # CRITICAL tier halo blink rate (matches ALARM_BLINK_RATE_HZ)
DEVICE_GLYPH_SIZE_PX: int = 5      # px — shunt/tap/SVC glyph size at a bus
DEVICE_GLYPH_OFFSET_PX: int = 12   # px — offset from bus centre for each device glyph slot
UNIT_MODE_BADGE_RADIUS_PX: int = 3   # px — AUTO/MANUAL dispatch-mode dot on a unit square

# ─────────────────────────────────────────────
# INSTRUMENT STRIP PANEL LAYOUT
# ─────────────────────────────────────────────
# Power Balance and the clock/speed readout both moved out of the strip:
# Power Balance into the horizontal TOPBAR above the canvas
# (see draw_topbar_panel()), clock/speed alongside it (see
# draw_topbar_panel()'s CLOCK/SPEED columns). Freq shrank 20% (162->130,
# its trend line and horizontal analog bar were both removed, leaving
# just the Hz readout and the vertical history plot) — unlike prior
# rounds, this freed width (32px) went directly to Dispatch (656->688)
# rather than to Alarm, per developer directive, which also helps
# Dispatch's known tight 4-column fit (see DISPATCH_STATUS_X_OFFSET/
# DISPATCH_VALUE_X_OFFSET below). Forecast (218), GenMix (121), and Alarm
# (763) unchanged this round. Order left to right: Freq, Dispatch,
# Forecast, GenMix, Alarm. Panel widths still sum to exactly
# NATIVE_WIDTH.
PANEL_FREQ_X:     int = 0
PANEL_FREQ_W:     int = 130
PANEL_DISPATCH_X:  int = 130
PANEL_DISPATCH_W:  int = 688
PANEL_FORECAST_X:  int = 818
PANEL_FORECAST_W:  int = 218
PANEL_GENMIX_X:    int = 1036
PANEL_GENMIX_W:    int = 121
PANEL_ALARM_X:     int = 1157
PANEL_ALARM_W:     int = 763

# Unit Dispatch panel always lays out this many columns, regardless of unit
# count or panel height (previously auto-computed as
# ceil(unit_count / rows_that_fit_vertically) — see draw_dispatch_panel()).
DISPATCH_NUM_COLS: int = 4

# Within-row x-offsets (px, pre-font_scale), unit label at 0. Measured
# against JetBrainsMono at FONT_SIZE_PANEL=16: longest label (e.g.
# 'RVSD-1') ~59px, status abbreviation up to 3 letters always (ONL/MAN/
# AGC/OFF/TRP/SDN/STA, see draw_dispatch_panel()) ~29px, value string
# 'NNNN NNN' (~78px, e.g. '1000 300') — MW padded to 4 digits, MVAr to 3,
# right-aligned (fleet-wide max is 1000 MW, 3-digit MVAr — see
# data/fleet.py; setpoint/target values are no longer shown, only
# actuals) so digits stay column-aligned across rows regardless of unit
# size. At DISPATCH_NUM_COLS=4 (164px columns, PANEL_DISPATCH_W=656,
# ~152px usable after padding), label+status+value together (~59+29+78 =
# 166px worst case) exceed the column's usable width — deliberately
# tight (developer directive: accept overlap rather than shrink the font
# further or drop MVAr from the row). DISPATCH_STATUS_X_OFFSET is set
# just past the longest label so label/status never collide; the value
# block is the field that runs tight against or past the next column's
# separator for large units, not label/status. A per-column header row
# ('UNIT STAT MW MVAr', see draw_dispatch_panel()) reuses these same
# offsets so it lines up with the data rows below it.
DISPATCH_STATUS_X_OFFSET: int = 64   # unit label -> ONL/MAN/AGC/OFF/TRP/SDN/STA abbreviation
DISPATCH_VALUE_X_OFFSET:  int = 97   # unit label -> MW/MVAr value block

# Row count per column is capped by how many rows actually fit the panel's
# fixed height (STRIP_HEIGHT/_HEADER_H/_ROW_H in panels.py), not by unit
# count — DISPATCH_NUM_COLS stays fixed regardless of fleet size (developer
# directive: don't grow columns or shrink row height to fit every unit).
# One row-slot per column is reserved for the 'UNIT STAT MW MVAr' header
# (see draw_dispatch_panel()) before unit rows start. When the fleet
# exceeds the remaining num_cols * (rows_that_fit - 1) capacity, the last
# visible row slot is reserved for a '+N MORE' indicator instead of a unit
# row, so a truncated list never looks like a silent bug.

# ─────────────────────────────────────────────
# SIMULATION SPEED MULTIPLIERS
# ─────────────────────────────────────────────
SPEED_PAUSE:     float = 0.00
SPEED_SLOW:      float = 0.25
SPEED_NORMAL:    float = 1.00
SPEED_FAST:      float = 3.00
SPEED_VERY_FAST: float = 10.00

# ─────────────────────────────────────────────
# RENEWABLES NOISE
# ─────────────────────────────────────────────
# Base seed for per-shift renewables RNG. A shift's generator is seeded with
# SHIFT_RNG_SEED_BASE + shift_number, so every run of the same shift replays the
# same wind/solar noise trace and a hard shift can be tuned and replayed fairly.
# Set to None for non-reproducible (freshly entropy-seeded) runs.
SHIFT_RNG_SEED_BASE: int | None = 19941107   # in-fiction campaign date, arbitrary

WIND_NOISE_STD_FRACTION:   float = 0.03     # Wind forecast noise (target std, before rate limiting)
SOLAR_NOISE_STD_FRACTION:  float = 0.01     # Solar forecast noise (target std, before rate limiting)
WIND_NOISE_RAMP_PCT_MIN:   float = 20.0     # Max noise-driven output change, %-of-rated per sim-minute
SOLAR_NOISE_RAMP_PCT_MIN:  float = 30.0     # Max noise-driven output change, %-of-rated per sim-minute

# ─────────────────────────────────────────────
# UNIT DEVIATION — operator derate & setpoint drift
# ─────────────────────────────────────────────
# Dispatchable units (HYDRO/COAL/NUCLEAR/CCGT — never WIND/SOLAR, which are
# non-dispatchable) occasionally fail to deliver exactly what's commanded,
# whether the command came from the Phase 1 schedule (AUTO) or a player's
# manual setpoint. Two independent event types, each an ONLINE-unit-per-
# sim-hour probability roll scaled by DIFFICULTY_MULT (see DIFFICULTY
# above). Rates below are tuned so "standard" difficulty across a ~12-unit
# online fleet lands close to one combined event every 12-24 sim-hours
# (30-60 real-minutes at TIME_COMPRESSION=24) — rare and noticeable, not
# background noise. Per-shift overridable via shift_NN.py, same pattern as
# AGC_SPEED_MULT.
#
# DERATE — a technical fault caps the unit's effective ceiling below its
# rated/commanded max for a sustained period. The unit still obeys
# commands, it just can't reach the top until the fault clears (handled
# by UnitModel.derate()/clear_derate() — see units.py). Raises an INFO
# alarm naming the unit and an in-fiction reason at the moment it starts;
# the player must still notice the practical ceiling themselves.
RANDOM_DERATE_CHANCE_PER_HOUR: float = 0.0025   # per ONLINE dispatchable unit, per sim-hour
RANDOM_DERATE_PCT_MIN:         float = 10.0     # cap reduction, % of rated_mw
RANDOM_DERATE_PCT_MAX:         float = 30.0
RANDOM_DERATE_DURATION_H_MIN:  float = 2.0      # sim-hours the derate holds before clearing
RANDOM_DERATE_DURATION_H_MAX:  float = 6.0
#
# DRIFT — an operator error makes the unit's actual output settle at a
# different value than commanded and hold there silently (no alarm) —
# handled entirely via UnitModel's _drift_offset_mw, see units.py. Clears
# the instant the player re-issues the currently-commanded setpoint, or
# automatically at the next sim-hour boundary, whichever comes first —
# never persists across an hour crossing.
RANDOM_DRIFT_CHANCE_PER_HOUR: float = 0.0025    # per ONLINE dispatchable unit, per sim-hour
RANDOM_DRIFT_PCT_MIN:         float = 10.0      # offset magnitude, % of target_mw
RANDOM_DRIFT_PCT_MAX:         float = 30.0
DRIFT_CLEAR_TOLERANCE_MW:     float = 0.5       # how close a re-command must be to the
                                                 # already-commanded target to count as
                                                 # "noticed and re-confirmed" (UnitModel.
                                                 # _set_target_internal())

# Flavour reasons shown in the derate alarm's detail text (drift is silent,
# no reason is ever surfaced to the player for it). Mixed technical and
# wry-comedic per unit type, matching the campaign's dry control-room
# voice. Sampled via the same seeded per-shift RNG as the trigger roll, so
# the same shift replay shows the same reason for the same event. Not
# type-specific beyond this split — every unit of a given type draws from
# the same pool regardless of station.
RANDOM_DERATE_REASONS_COAL: tuple[str, ...] = (
    'boiler tube leak — output capped pending inspection',
    'coal handling plant fault — bunker feed running short',
    'induced draught fan vibration — load restricted as a precaution',
    'condenser cooling water flow below spec',
    'mill outage — one pulveriser down, full load unavailable',
)
RANDOM_DERATE_REASONS_NUCLEAR: tuple[str, ...] = (
    'feedwater pump running on reduced capacity',
    'routine reactivity margin check — output held below ceiling',
    'turbine governor valve partially throttled for maintenance',
    'condenser vacuum slightly degraded — capped as a precaution',
)
RANDOM_DERATE_REASONS_CCGT: tuple[str, ...] = (
    'gas turbine inlet filter fouling — derated pending a clean',
    'ambient temperature derate — embarrassingly, it is just too warm today',
    'HRSG steam drum level instability — output capped',
    'compressor wash overdue — a few percent efficiency quietly missing',
)
RANDOM_DERATE_REASONS_HYDRO: tuple[str, ...] = (
    'intake trash screen partially blocked — flow restricted',
    'penstock inspection in progress on one unit',
    'reservoir level lower than forecast — conserving head',
    'gate actuator sluggish — full opening not currently available',
)

# ─────────────────────────────────────────────
# ALARM DISPLAY
# ─────────────────────────────────────────────
ALARM_BLINK_RATE_HZ:   float = 2.0          # Unacknowledged alarms blink at 2Hz
ALARM_RECENT_FADE_S:   float = 10.0         # Acknowledged alarms shown for 10s then removed
ALARM_MESSAGE_MAX_LEN: int   = 60           # Max characters in alarm message

# ─────────────────────────────────────────────
# SOUND
# ─────────────────────────────────────────────
SOUND_PATH_ALARM:         str   = 'assets/sounds/alarm.wav'         # Loops while a CRITICAL alarm is unacknowledged
SOUND_PATH_PING:          str   = 'assets/sounds/ping.wav'          # One-shot on new INFO/TUTOR alarm
SOUND_PATH_WARNING_PING:  str   = 'assets/sounds/warning_ping.wav'  # Loops while a WARNING alarm is unacknowledged
SOUND_VOLUME_ALARM:       float = 0.6
SOUND_VOLUME_PING:        float = 0.5
SOUND_VOLUME_WARNING_PING: float = 0.5

# ─────────────────────────────────────────────
# LINE LOAD TRIANGLE INDICATOR
# ─────────────────────────────────────────────
LOAD_TRIANGLE_PCT_1: float = 25.0  # 1 triangle below this loading %
LOAD_TRIANGLE_PCT_2: float = 50.0  # 2 triangles below this loading %
LOAD_TRIANGLE_PCT_3: float = 75.0  # 3 triangles below this loading %, else 4
LOAD_TRIANGLE_SIZE:  int   = 6     # px — side length of each load-indicator triangle
LOAD_TRIANGLE_SPACING: int = 10    # px — fixed gap between consecutive load-indicator triangles

# ─────────────────────────────────────────────
# DEBUG OVERLAY
# ─────────────────────────────────────────────
DEBUG_GRID_SPACING:    int = 30            # px — coordinate grid spacing
DEBUG_CLICK_DISPLAY_S: float = 3.0         # seconds to display clicked coordinates

# ─────────────────────────────────────────────
# GRID DESIGNER MODE
# ─────────────────────────────────────────────
DESIGNER_SIDEBAR_W:          int   = 208    # px — sidebar panel width (left edge)
DESIGNER_CANVAS_W:           int   = NATIVE_WIDTH - DESIGNER_SIDEBAR_W  # px — canvas area width (right edge)
DESIGNER_X_SCALE:            float = 0.05   # superseded by KM_PER_PX/REACTANCE_PU_PER_KM_* below; no remaining call sites
KM_PER_PX:                   float = 0.35   # Manhattan-distance px -> km, new-line placement/length editing
REACTANCE_PU_PER_KM_150KV:   float = 0.015556  # X_pu/km = 0.35 Ohm/km OHL reactance / Z_BASE(150kV, S_BASE=1000MVA)=22.5 Ohm
REACTANCE_PU_PER_KM_220KV:   float = 0.007231  # Z_BASE(220kV) = 48.4 Ohm
REACTANCE_PU_PER_KM_400KV:   float = 0.002187  # Z_BASE(400kV) = 160.0 Ohm
DESIGNER_TARGET_LOADING_PCT: float = 70.0   # auto-route: add parallel line when loading exceeds this
DESIGNER_N1_OVERLOAD_PCT:    float = 90.0   # auto-route: N-1 contingency overload threshold
DESIGNER_STATUS_DISPLAY_S:   float = 3.0    # seconds to show auto-route completion message
DESIGNER_HIT_RADIUS:         int   = 14     # px — hit-test radius for buses in designer
DESIGNER_LINE_HIT_PX:        int   = 8      # px — perpendicular distance threshold for line hit
DESIGNER_FONT_SIZE:          int   = 12     # px — designer sidebar and overlay font size
DESIGNER_FONT_SIZE_LARGE:    int   = 22     # px — status messages on canvas
DESIGNER_UNDO_MAX:           int   = 50     # maximum undo stack depth
DESIGNER_MARQUEE_THRESHOLD_PX: int = 3       # px — drag distance before a marquee counts as a drag, not a click
DESIGNER_GRID_SPACING_PX:    int   = 10     # px — background reference dot-grid spacing
DESIGNER_GRID_DEFAULT_ON:    bool  = False  # dot-grid visibility on Designer entry
DESIGNER_SNAP_SPACING_PX:    int   = 5      # px — snap-to-grid resolution for bus/station placement and drag
DESIGNER_SNAP_DEFAULT_ON:    bool  = True   # whether snap-to-grid is active by default

# ─────────────────────────────────────────────
# SHIFT BUILDER MODE
# ─────────────────────────────────────────────
SHIFT_BUILDER_FONT_SIZE:        int   = 14    # px — body text
SHIFT_BUILDER_FONT_SIZE_LARGE:  int   = 20    # px — section headings
SHIFT_BUILDER_ROW_H:            int   = 24    # px — list row height
SHIFT_BUILDER_LEFT_MARGIN:      int   = 40    # px — left content margin
SHIFT_BUILDER_TOP_MARGIN:       int   = 40    # px — top content margin
SHIFT_BUILDER_STATUS_DISPLAY_S: float = 3.0   # seconds to show status messages
SHIFT_BUILDER_DEFAULT_DURATION_H: float = 8.0 # default duration for a new shift

# ─────────────────────────────────────────────
# PLANNING PHASE (Phase 1 — pre-shift unit scheduling screen)
# ─────────────────────────────────────────────
PLANNING_FONT_SIZE:             int   = 12    # px — table body text (24 columns is tight)
PLANNING_FONT_SIZE_LARGE:       int   = 18    # px — section headings
PLANNING_ROW_H:                 int   = 16    # px — table row height
PLANNING_LEFT_MARGIN:           int   = 24    # px — left content margin
PLANNING_TOP_MARGIN:            int   = 56    # px — top content margin (plot/table start here)
PLANNING_LABEL_COL_W:           int   = 190   # px — unit label / rated / ON-OFF column
PLANNING_HOUR_COL_W:            int   = 70    # px — per-hour column (24 columns must fit)
PLANNING_PLOT_H:                int   = 220   # px — stacked plot region height
PLANNING_PLOT_Y_HEADROOM_FRAC:  float = 1.10  # plot Y max = peak value * this
PLANNING_STATUS_DISPLAY_S:      float = 3.0   # seconds to show status messages
PLANNING_TABLE_GROUP_GAP:       int   = 4     # px — extra gap before each tech-group header row
PLANNING_TABLE_VISIBLE_H:       int   = 480   # px — scrollable table viewport height (unit rows only)

# Planning-grid time resolution, in hours per column (24 columns/day at the
# default 1.0). Single source of truth for both the planning data model
# (gameplay/phase1.py's _PLANNING_HOURS, ramp-per-column and cost-per-column
# math) and the real-time simulation's schedule-boundary detection
# (simulation.py's _apply_hourly_schedule(), which reads this directly
# rather than duplicating it — the two must never drift out of sync, since
# schedule keys are produced exclusively by phase1.py and consumed
# exclusively there). Tried at 0.5 (half-hourly) — reverted per developer
# feedback: added clutter without meaningfully improving gameplay.
PLANNING_STEP_HOURS:            float = 1.0

# ─────────────────────────────────────────────
# PLANNING PHASE — KEYBOARD SHORTCUTS
# ─────────────────────────────────────────────
PLANNING_KEY_UP:            tuple = (pygame.K_UP, pygame.K_w)      # move cursor up a row
PLANNING_KEY_DOWN:          tuple = (pygame.K_DOWN, pygame.K_s)    # move cursor down a row
PLANNING_KEY_LEFT:          int   = pygame.K_LEFT                  # move cursor to previous hour
PLANNING_KEY_RIGHT:         int   = pygame.K_RIGHT                 # move cursor to next hour
PLANNING_KEY_EDIT:          int   = pygame.K_RETURN                # open / commit the cell editor
PLANNING_KEY_TECH_MIN:      int   = pygame.K_n                     # fill selected cell to tech min (+Shift: whole row)
PLANNING_KEY_TECH_MAX:      int   = pygame.K_m                     # fill selected cell to tech max (+Shift: whole row)
PLANNING_KEY_ZERO:          int   = pygame.K_BACKSPACE              # fill selected cell to 0 MW (+Shift: whole row)
PLANNING_KEY_TOGGLE_ONLINE: int   = pygame.K_o                     # toggle selected unit ONLINE/OFFLINE
PLANNING_KEY_TOGGLE_AGC:    int   = pygame.K_g                     # toggle selected unit's AGC enrollment
PLANNING_KEY_RESET:         int   = pygame.K_r                     # reset schedule to shift handover dispatch
PLANNING_KEY_AUTO:          int   = pygame.K_a                     # auto-schedule the full 24h (Ctrl+A)
PLANNING_KEY_CONFIRM:       int   = pygame.K_F10                   # confirm plan and start the real-time shift
PLANNING_KEY_BACK:          int   = pygame.K_ESCAPE                # cancel cell edit / exit planner to main menu

# ─────────────────────────────────────────────
# PLANNING PHASE — AUTO-SCHEDULER (heuristic day-ahead unit commitment)
# ─────────────────────────────────────────────
# Minimum hours a unit must stay ONLINE once committed / OFFLINE once
# stopped, by dispatchable technology. Planning-layer-only constraint —
# not enforced by the real-time simulation (units.py has no cooldown).
MIN_UP_HOURS_NUCLEAR:      float = 24.0
MIN_DOWN_HOURS_NUCLEAR:    float = 24.0
MIN_UP_HOURS_COAL:         float = 6.0
MIN_DOWN_HOURS_COAL:       float = 8.0
MIN_UP_HOURS_CCGT:         float = 2.0
MIN_DOWN_HOURS_CCGT:       float = 2.0
MIN_UP_HOURS_HYDRO:        float = 0.0
MIN_DOWN_HOURS_HYDRO:      float = 0.0
MIN_UP_HOURS_HYDRO_ROR:    float = 0.0
MIN_DOWN_HOURS_HYDRO_ROR:  float = 0.0
MIN_UP_HOURS_HYDRO_PUMP:   float = 0.0
MIN_DOWN_HOURS_HYDRO_PUMP: float = 0.0
MIN_UP_HOURS_WIND:         float = 0.0
MIN_DOWN_HOURS_WIND:       float = 0.0
MIN_UP_HOURS_SOLAR:        float = 0.0
MIN_DOWN_HOURS_SOLAR:      float = 0.0

# Pooled AGC regulating-reserve target the auto-scheduler tries to leave
# available on every hour's online, AGC-enrolled CCGT/HYDRO fleet (see
# PlanningModel.reg_band_up()/reg_band_down()). Both directions (up AND
# down) must independently clear this value — a combined 2x band could
# still be entirely one-sided, which would leave AGC unable to regulate
# the other way. Load coverage (0 MW diff against forecast demand) always
# takes priority over this reserve if the two ever genuinely conflict
# (a capacity-scarce fleet/hour) — the auto-scheduler never leaves load
# uncovered just to manufacture regulating headroom.
PLANNING_AGC_RESERVE_MW: float = 50.0

# Previous-day boundary state: the auto-scheduler's commitment/ramp logic
# for hour 00:00 needs a "previous hour" to compare against. Since there
# is no actual prior day, every non-maintenance dispatchable unit is
# assumed to have been ONLINE at this fraction of its rated_mw during the
# previous day's final hour (H24 of D-1), per technology (default: full
# output). Calculation-only — never displayed or written to the
# schedule/online table. WIND/SOLAR are forecast-driven and never
# commitment-scheduled, so their fractions are unused.
PLANNING_PREV_DAY_FRAC_NUCLEAR:     float = 1.0
PLANNING_PREV_DAY_FRAC_COAL:        float = 1.0
PLANNING_PREV_DAY_FRAC_CCGT:        float = 1.0
PLANNING_PREV_DAY_FRAC_HYDRO:       float = 1.0
PLANNING_PREV_DAY_FRAC_HYDRO_ROR:   float = 1.0
PLANNING_PREV_DAY_FRAC_HYDRO_PUMP:  float = 1.0

# ─────────────────────────────────────────────
# ECONOMICS (Phase 1 — scheduler budget)
# ─────────────────────────────────────────────
# Dummy/placeholder values — this is scaffolding for a real economy later,
# not a tuned constraint yet. Cost is a per-TECHNOLOGY property (looked up
# by unit_type), not a per-fleet-unit override — every unit of a given
# unit_type costs the same to start/run. PLANNING_INITIAL_BUDGET_EUR is
# deliberately huge so it never blocks a plan at this stage; the per-type
# cost tables below exist so PlanningModel has something real to sum.
# Baseline VARIABLE_COST_EUR_PER_MWH_BY_TYPE values carried over from the
# orphaned COST_MAP that used to live in simulation.py's unused
# run_forecast_mode().
STARTUP_COST_EUR_BY_TYPE: dict = {
    'NUCLEAR':    50000.0,
    'COAL':       8000.0,
    'CCGT':       3000.0,
    'HYDRO':      200.0,
    'HYDRO_ROR':  0.0,
    'HYDRO_PUMP': 200.0,
    'WIND':       0.0,
    'SOLAR':      0.0,
}
VARIABLE_COST_EUR_PER_MWH_BY_TYPE: dict = {
    'COAL':       45.0,
    'CCGT':       55.0,
    'NUCLEAR':    12.0,
    'HYDRO':      5.0,
    'HYDRO_PUMP': 5.0,
    'HYDRO_ROR':  5.0,
    'WIND':       0.0,
    'SOLAR':      0.0,
}

# Flat surcharge (EUR per online hour) for any unit the player has enrolled
# in AGC (see PlanningModel.agc_enrolled) — the cost of keeping that unit's
# headroom available for automatic regulation, independent of its fuel cost.
AGC_AVAILABILITY_COST_EUR_PER_HOUR: float = 150.0

# Difficulty cost multiplier — scales STARTUP_COST_EUR_BY_TYPE,
# VARIABLE_COST_EUR_PER_MWH_BY_TYPE and AGC_AVAILABILITY_COST_EUR_PER_HOUR
# uniformly, same trainee/standard/dispatcher keys as DIFFICULTY_MULT
# (above). Only the COSTS scale — PLANNING_INITIAL_BUDGET_EUR itself does
# not change with difficulty — so a lower multiplier on trainee stretches
# the same EUR budget further (a bigger relative cushion), while dispatcher
# makes every action cost more against that same fixed budget.
DIFFICULTY_COST_MULT: dict[str, float] = {
    'trainee':    0.5,
    'standard':   1.0,
    'dispatcher': 1.6,
}

# Starting Phase 1 budget. Deliberately huge for now — large enough that no
# plan a player could plausibly build against Shift 10's fleet can exceed
# it, so the budget gate exists (PlanningScreen._confirm_plan) but never
# actually fires yet. Not scaled by difficulty (see DIFFICULTY_COST_MULT).
PLANNING_INITIAL_BUDGET_EUR: float = 100_000_000.0

# ─────────────────────────────────────────────
# SHIFT SCORING (gameplay/scoring.py)
# ─────────────────────────────────────────────
# Grade bands are evaluated worst-first: a shift is only EXCELLENT if it
# clears every EXCELLENT gate, and so on down. Frequency is the headline
# metric but no longer the only one — voltage, line loading and unit trips
# are all already measured by SimulationState and were previously discarded.
SCORE_FREQ_PCT_EXCELLENT:    float = 95.0   # min frequency-in-bounds % for EXCELLENT
SCORE_FREQ_PCT_SATISFACTORY: float = 80.0   # min for SATISFACTORY
SCORE_FREQ_PCT_MARGINAL:     float = 60.0   # min for MARGINAL (below this: UNSATISFACTORY)

SCORE_LOADING_PCT_EXCELLENT:    float = 100.0  # no line may exceed its rating
SCORE_LOADING_PCT_SATISFACTORY: float = 120.0  # brief overload tolerated

SCORE_VOLTAGE_PU_EXCELLENT:    float = 0.90    # min bus voltage seen, per-unit
SCORE_VOLTAGE_PU_SATISFACTORY: float = 0.85    # V_WARNING_LOW — collapse onset

SCORE_UNIT_TRIPS_EXCELLENT:    int = 0
SCORE_UNIT_TRIPS_SATISFACTORY: int = 1

SCORE_SHED_EVENTS_EXCELLENT:    int = 0
SCORE_SHED_EVENTS_SATISFACTORY: int = 1

# Campaign rating is the modal/worst-weighted roll-up of the ten shift
# grades — a campaign is only as good as its weakest shifts. A campaign
# grade is awarded if at least this fraction of shifts reach it.
SCORE_CAMPAIGN_FRACTION: float = 0.7

# ─────────────────────────────────────────────
# LOAD SHEDDING (operator emergency tool)
# ─────────────────────────────────────────────
# Fraction of a substation's load dropped per shed command. Shedding is
# cumulative at a bus (see DemandModel.shed_load) and reversible via
# GridSimulation.clear_shed(), but every shed still counts against the
# shift's security score.
LOAD_SHED_STEP_FRACTION: float = 0.25
