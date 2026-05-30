"""
src/simulation/constants.py

All constants for the GRIDCOM simulation and display.
Every numeric value, threshold, timing, and configuration parameter lives here.
No hardcoded numbers anywhere else in the codebase.

See CLAUDE.md Rule 1.
"""

# ─────────────────────────────────────────────
# DEBUG FLAGS
# ─────────────────────────────────────────────
DEBUG_SIMULATION: bool = True
DEBUG_DISPLAY:    bool = True
DEBUG_EVENTS:     bool = False
EDITOR_MODE:      bool = False
FLOW_ANIMATION:        bool = False
DEBUG_SCENARIO_ACTIVE: bool = True

# ─────────────────────────────────────────────
# POWER SYSTEM BASE VALUES
# ─────────────────────────────────────────────
S_BASE: float = 1000.0          # MVA base for per-unit calculations
F_NOMINAL: float = 50.0         # Hz — nominal system frequency
V_NOMINAL_400: float = 400.0    # kV
V_NOMINAL_220: float = 220.0    # kV
V_NOMINAL_150: float = 150.0    # kV
V_NOMINAL_60:  float = 60.0     # kV

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
V_COLLAPSE_GAIN:  float = 2.0   # Gain factor for voltage collapse acceleration

# ─────────────────────────────────────────────
# FREQUENCY THRESHOLDS (Hz)
# ─────────────────────────────────────────────
F_MAX:            float = 55.0  # Hard clamp maximum
F_MIN:            float = 45.0  # Hard clamp minimum
F_ALERT_HIGH:     float = 50.2  # Warning alarm threshold (above nominal)
F_ALERT_LOW:      float = 49.8  # Warning alarm threshold (below nominal)
F_CRITICAL_HIGH:  float = 50.5  # Critical alarm threshold
F_CRITICAL_LOW:   float = 49.5  # Critical alarm threshold
F_IN_BOUNDS_TOL:  float = 0.2   # Tolerance for frequency_in_bounds_pct scoring
F_STABLE_TOL:     float = 0.005 # Hz — threshold for STABLE vs RISING/FALLING trend

# ─────────────────────────────────────────────
# DROOP / GOVERNOR
# ─────────────────────────────────────────────
DROOP_R: float = 0.04           # 4% droop setting (per-unit on machine base)

# ─────────────────────────────────────────────
# AUTOMATIC GENERATION CONTROL (AGC)
# ─────────────────────────────────────────────
AGC_ENABLED:       bool  = True  # Toggled at runtime via Ctrl+A; starts disabled
AGC_KP:            float = 8.0    # Proportional gain (MW per Hz of error)
AGC_KI:            float = 0.15   # Integral gain (MW per Hz·sim-second of error)
AGC_KD:            float = 25.0   # Derivative gain (MW per Hz/sim-second of error)
AGC_MAX_RATE_MW_S: float = 2.0   # Max total AGC correction rate (MW per sim-second)
AGC_DEADBAND_HZ:   float = 0.05   # ±Hz inside which AGC is silent
AGC_INTEGRAL_MAX:  float = 5.0   # Anti-windup clamp on integral accumulator (Hz·s)
AGC_LOG:           bool  = True  # Write per-tick PID data to agc_log.csv when True

# ─────────────────────────────────────────────
# LOSSES
# ─────────────────────────────────────────────
LOSSES_FRACTION: float = 0.025  # 2.5% of total generation added to load

# ─────────────────────────────────────────────
# LINE TRIP / CASCADE
# ─────────────────────────────────────────────
TRIP_DELAY_S:        float = 60.0   # Seconds a line must be >100% before tripping
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
MIN_OUTPUT_FRACTION: float = 0.20       # Units run at minimum 20% of rated when online

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
# SIMULATION TIMING
# ─────────────────────────────────────────────
SIM_TICKS_PER_SECOND: int   = 10        # Simulation ticks per real second
TIME_COMPRESSION:     float = 24.0      # 1 sim hour = 2.5 real minutes

# ─────────────────────────────────────────────
# DISPLAY / RENDERING
# ─────────────────────────────────────────────
NATIVE_WIDTH:  int = 1920
NATIVE_HEIGHT: int = 1080
CANVAS_HEIGHT: int = 844        # Top portion — grid schematic
STRIP_HEIGHT:  int = 236        # Bottom portion — instrument strip
TARGET_FPS:    int = 60
LETTERBOX_COLOUR: tuple[int, int, int] = (0, 0, 0)

FONT_ANTIALIAS_THRESHOLD: int = 11      # px — disable antialiasing at or below this size
FONT_SIZE_LABEL:          int = 12      # bus/station labels on canvas
FONT_SIZE_OVERLAY:        int = 13      # interconnector labels, debug overlay
FONT_SIZE_PANEL:          int = 11      # standard instrument strip text
FONT_SIZE_PANEL_LARGE:    int = 28      # frequency Hz readout
FONT_SIZE_CONTEXT:        int = 11      # unit context overlay text

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
# INSTRUMENT STRIP PANEL LAYOUT
# ─────────────────────────────────────────────
PANEL_FREQ_X:     int = 0
PANEL_FREQ_W:     int = 240
PANEL_POWER_X:    int = 240
PANEL_POWER_W:    int = 240
PANEL_DISPATCH_X:  int = 480
PANEL_DISPATCH_W:  int = 280
PANEL_FORECAST_X:  int = 760
PANEL_FORECAST_W:  int = 360
PANEL_GENMIX_X:    int = 1120
PANEL_GENMIX_W:    int = 260
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
# DEMAND NOISE
# ─────────────────────────────────────────────
DEMAND_NOISE_STD_FRACTION: float = 0.000001    # Std dev of demand noise as fraction of mean
DEMAND_NOISE_UPDATE_S:     float = 60.0     # Simulated seconds between noise re-samples
WIND_NOISE_STD_FRACTION:   float = 0.03     # Wind forecast noise
SOLAR_NOISE_STD_FRACTION:  float = 0.01     # Solar forecast noise (small)

# ─────────────────────────────────────────────
# ALARM DISPLAY
# ─────────────────────────────────────────────
ALARM_BLINK_RATE_HZ:   float = 2.0          # Unacknowledged alarms blink at 2Hz
ALARM_RECENT_FADE_S:   float = 10.0         # Acknowledged alarms shown for 10s then removed
ALARM_MESSAGE_MAX_LEN: int   = 60           # Max characters in alarm message

# ─────────────────────────────────────────────
# FLOW MARKER ANIMATION
# ─────────────────────────────────────────────
FLOW_MARKER_SIZE:      int   = 3            # px — square marker side length
FLOW_MARKER_SPACING:   float = 20.0         # px — spacing between markers on a line
FLOW_SPEED_BASE:       float = 30.0         # px/s at 50% loading
FLOW_SPEED_MAX:        float = 120.0        # px/s at 100%+ loading

# ─────────────────────────────────────────────
# DEBUG OVERLAY
# ─────────────────────────────────────────────
DEBUG_GRID_SPACING:    int = 30            # px — coordinate grid spacing
DEBUG_CLICK_DISPLAY_S: float = 3.0         # seconds to display clicked coordinates
