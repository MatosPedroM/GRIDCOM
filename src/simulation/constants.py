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

# Generator AVR voltage setpoint (per-unit) — player-editable range.
GEN_VOLTAGE_SETPOINT_DEFAULT_PU: float = 1.02
GEN_VOLTAGE_SETPOINT_MIN_PU:     float = 0.95
GEN_VOLTAGE_SETPOINT_MAX_PU:     float = 1.05

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
# DROOP / GOVERNOR
# ─────────────────────────────────────────────
# 4% droop setting (per-unit on machine base). Applied to ALL ONLINE
# synchronous units (COAL, NUCLEAR, HYDRO, HYDRO_ROR, HYDRO_PUMP, CCGT) as
# an immediate, non-ramp-limited primary frequency response -- see
# units.py FleetModel.apply_droop_response(). Runs ahead of AGC each tick.
DROOP_R: float = 0.04

# Per-shift override, mirroring AGC_ENABLED's plumbing (see gameplay/shifts
# loader.py's 'droop_enabled' config key). Defaults False -- playtesting
# found universal droop (non-ramp-limited, re-anchoring target_mw every
# tick on every synchronous unit including slow-ramping COAL) fought a
# player's manual setpoint hard enough to read as a control bug, and with
# AGC already handling fast correction on HYDRO/CCGT, droop's realism
# wasn't earning its confusion cost. Any shift_NN.py can still set
# DROOP_ENABLED = True explicitly to opt back in.
DROOP_ENABLED: bool = False

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

# ─────────────────────────────────────────────
# FREQUENCY DYNAMICS
# ─────────────────────────────────────────────
# Multiplier on df/dt applied on top of the already-compressed sim-second
# timestep. Frequency is the one subsystem that must NOT run at full
# TIME_COMPRESSION speed (real dispatchers react to frequency in real time,
# not compressed time) -- this tunable dial sets how fast a disturbance
# reaches the player, independent of TIME_COMPRESSION. Target: a large
# unit trip should leave the alert band in ~10-20 real seconds at 1x speed.
# Not derived from any other constant -- retune against playtest/verification
# harness, not by formula.
FREQ_DYNAMICS_SCALE: float = 0.02

# ─────────────────────────────────────────────
# DISPLAY / RENDERING
# ─────────────────────────────────────────────
NATIVE_WIDTH:  int = 1920
NATIVE_HEIGHT: int = 1080
CANVAS_HEIGHT: int = 844        # Top portion — grid schematic
STRIP_HEIGHT:  int = 236        # Bottom portion — instrument strip
TARGET_FPS:           int   = 60
SIM_TICK_INTERVAL_S:  float = 0.1    # Simulation advances at 10 Hz regardless of render FPS
LETTERBOX_COLOUR: tuple[int, int, int] = (0, 0, 0)

FONT_PATH_MONO_REGULAR:  str = 'assets/fonts/TerminusTTF-4.49.3.ttf' #'assets/fonts/Px437_IBM_VGA_8x16.ttf'

FONT_ANTIALIAS_THRESHOLD: int = 11      # px — disable antialiasing at or below this size
FONT_SIZE_LABEL:          int = 18      # bus/station labels on canvas
LABEL_PAD_PX:             int = 3       # px — gap between a label and the symbol it labels
FONT_SIZE_OVERLAY:        int = 15      # interconnector labels, debug overlay
FONT_SIZE_PANEL:          int = 13      # standard instrument strip text
FONT_SIZE_PANEL_LARGE:    int = 30      # frequency Hz readout
FONT_SIZE_CONTEXT:        int = 13      # unit context overlay text

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
CONTEXT_OVERLAY_W:     int = 240   # panel width in px
CONTEXT_OVERLAY_PAD:   int = 6     # inner padding
CONTEXT_OVERLAY_ROW_H: int = 16    # text row height
CONTEXT_OVERLAY_HDR_H: int = 18    # header row height

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
PANEL_FREQ_X:     int = 0
PANEL_FREQ_W:     int = 240
PANEL_POWER_X:    int = 240
PANEL_POWER_W:    int = 240
PANEL_DISPATCH_X:  int = 480
PANEL_DISPATCH_W:  int = 590
PANEL_FORECAST_X:  int = 1070
PANEL_FORECAST_W:  int = 180
PANEL_GENMIX_X:    int = 1250
PANEL_GENMIX_W:    int = 130
PANEL_ALARM_X:     int = 1380
PANEL_ALARM_W:     int = 540

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
WIND_NOISE_STD_FRACTION:   float = 0.03     # Wind forecast noise (target std, before rate limiting)
SOLAR_NOISE_STD_FRACTION:  float = 0.01     # Solar forecast noise (target std, before rate limiting)
WIND_NOISE_RAMP_PCT_MIN:   float = 20.0     # Max noise-driven output change, %-of-rated per sim-minute
SOLAR_NOISE_RAMP_PCT_MIN:  float = 30.0     # Max noise-driven output change, %-of-rated per sim-minute

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

# Confirm-time adequacy gate: F10 is refused if any hour's scheduled
# generation is below load_forecast(h) * (1 + this fraction) — i.e. the plan
# must carry at least this much spinning-reserve margin above forecast load.
PLANNING_MIN_RESERVE_MARGIN_FRAC: float = 0.05

# Confirm-time warning (non-blocking): F10 still succeeds, but a yellow
# warning is shown if any hour's scheduled generation exceeds
# load_forecast(h) * (1 + this fraction) — an oversized, inefficient margin.
PLANNING_WARN_RESERVE_MARGIN_FRAC: float = 0.20

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
