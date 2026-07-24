"""
src/display/palette.py

All colour constants for the GRIDCOM display.
Every RGB tuple in the codebase lives here — nowhere else.

Palette: strict 4-bit RGBI (ZX Spectrum / CGA philosophy).
All constants are drawn exclusively from these 16 values:

  Black          (0,   0,   0)     Dark Grey      (85,  85,  85)
  Blue           (0,   0, 170)     Bright Blue    (0,   0, 255)
  Red            (170, 0,   0)     Bright Red     (255, 0,   0)
  Magenta        (170, 0, 170)     Bright Magenta (255, 0, 255)
  Green          (0, 170,   0)     Bright Green   (0, 255,   0)
  Cyan           (0, 170, 170)     Bright Cyan    (0, 255, 255)
  Yellow         (170,170,  0)     Bright Yellow  (255,255,  0)
  White          (170,170,170)     Bright White   (255,255,255)

See CLAUDE.md Rule 2.
See GRID_TOPOLOGY_AND_DISPLAY.md for visual specification.
"""

# Type alias
Colour = tuple[int, int, int]

# ─────────────────────────────────────────────
# BACKGROUND
# ─────────────────────────────────────────────
COL_BACKGROUND:     Colour = (0,   0,   0)      # Canvas background — black
COL_CANVAS_BG:      Colour = (0,   0,   0)      # Grid canvas background — black
COL_STRIP_BG:       Colour = (0,   0,   0)      # Instrument strip background — black
COL_PANEL_BG:       Colour = (0,   0,   0)      # Panel / context box background — black
COL_PANEL_BORDER:   Colour = (0, 170,   0)      # Panel border — green (SCADA terminal)

# ─────────────────────────────────────────────
# VOLTAGE LEVEL LINES (used for collector lines and UI hints only)
# Transmission lines and substations are coloured by load state, not voltage.
# ─────────────────────────────────────────────
COL_400KV:  Colour = (0,  255, 255)     # Bright Cyan  — 400kV collector lines
COL_220KV:  Colour = (0,  255,   0)     # Bright Green — 220kV collector lines
COL_150KV:  Colour = (255,255,   0)     # Bright Yellow — 150kV collector lines

# ─────────────────────────────────────────────
# VOLTAGE COLOUR VIEW ('L' toggle — lines/substations by voltage tier)
# ─────────────────────────────────────────────
COL_VVIEW_400KV:    Colour = (0,  255, 255)     # 400kV — bright cyan
COL_VVIEW_220KV:    Colour = (255,  0,   0)     # 220kV — bright red
COL_VVIEW_150KV:    Colour = (0,  255,   0)     # 150kV — bright green
COL_VVIEW_60KV:     Colour = (170,170,   0)     # 60kV — yellow (unused; no 60kV tier exists in the real topology, kept for completeness)

# ─────────────────────────────────────────────
# LINE STATES
# ─────────────────────────────────────────────
COL_LINE_NORMAL:    Colour = (85,  85,  85)     # De-emphasised — unenergised / no-state
COL_LINE_ENERGISED: Colour = (0,  255,   0)     # Energised, load < 60% — bright green
COL_LOAD_WARN:      Colour = (255,255,   0)     # 60-80% loading — bright yellow
COL_LOAD_HIGH:      Colour = (255,  0,   0)     # 80-95% loading — bright red
COL_LOAD_CRIT:      Colour = (255,  0,   0)     # 95-100% and >100% loading — bright red
COL_LINE_LOADED:    Colour = (255,255,   0)     # Alias for LOAD_WARN (backwards compat)
COL_LINE_OVERLOAD:  Colour = (255,  0,   0)     # Alias for LOAD_CRIT (backwards compat)
COL_LINE_TRIPPED:   Colour = (85,  85,  85)     # Tripped — dark grey dead line
COL_LINE_HYDRAULIC: Colour = (0,    0, 170)     # Dashed hydraulic connector — blue (water)
COL_LOAD_SUB:       Colour = (170,170,   0)     # Load substation triangle fill — yellow

# ─────────────────────────────────────────────
# SUBSTATION SYMBOLS
# ─────────────────────────────────────────────
COL_BUS_NORMAL:     Colour = (170,170, 170)     # Normal energised substation — white
COL_BUS_SELECTED:   Colour = (255,255, 255)     # Selected element highlight — bright white
COL_BUS_BLACKED:    Colour = (85,  85,  85)     # Blacked out — dark grey (remains locatable)
COL_BUS_400KV:      Colour = (0,  255, 255)     # 400kV symbol — bright cyan (collector lines)
COL_BUS_220KV:      Colour = (0,  255,   0)     # 220kV symbol — bright green (collector lines)
COL_BUS_150KV:      Colour = (255,255,   0)     # 150kV symbol — bright yellow (collector lines)
COL_BUS_60KV:       Colour = (170,170,   0)     # 60kV symbol — yellow (collector lines)

# ─────────────────────────────────────────────
# GENERATION UNIT SQUARES
# ─────────────────────────────────────────────
COL_UNIT_ONLINE:    Colour = (0,  255,   0)     # Online and generating — bright green
COL_UNIT_STARTING:  Colour = (0,  255,   0)     # Starting — bright green (blinks with offline)
COL_UNIT_OFFLINE:   Colour = (85,  85,  85)     # Offline — dark grey
COL_UNIT_SHUTDOWN:  Colour = (0,  255,   0)     # Shutting down — bright green (blinks with offline)
COL_UNIT_TRIPPED:   Colour = (255,  0,   0)     # Tripped by protection — bright red
COL_UNIT_BORDER:    Colour = (85,  85,  85)     # Default unit border — dark grey

# ─────────────────────────────────────────────
# UNIT TYPE ACCENT COLOURS
# ─────────────────────────────────────────────
COL_UNIT_COAL:      Colour = (165, 42,  42)     # Coal — red (closest in-palette to brown/earth)
COL_UNIT_CCGT:      Colour = (85,  85,  85)     # CCGT — dark grey
COL_UNIT_NUCLEAR:   Colour = (170,  0, 170)     # Nuclear — purple
COL_UNIT_HYDRO:     Colour = (0,  200, 255)     # Hydro — blue (water)
COL_UNIT_HYDRO_PUMP:Colour = (0,  200, 255)     # Hydro pumping mode — blue, same as HYDRO
COL_UNIT_WIND:      Colour = (255,255, 255)     # Wind — white
COL_UNIT_SOLAR:     Colour = (255,255,   0)     # Solar — bright yellow (sunshine)

# ─────────────────────────────────────────────
# DEMAND ARROWS
# ─────────────────────────────────────────────
COL_DEMAND_ARROW:   Colour = (170,170,   0)     # Load demand arrow — yellow
COL_DEMAND_HIGH:    Colour = (255,  0,   0)     # High demand indicator — bright red

# ─────────────────────────────────────────────
# INTERCONNECTOR MARKERS
# ─────────────────────────────────────────────
COL_INTC_IMPORT:    Colour = (0,  170,   0)     # Importing — green (receiving power)
COL_INTC_EXPORT:    Colour = (170,170,   0)     # Exporting — yellow (sending power)
COL_INTC_IDLE:      Colour = (85,  85,  85)     # Zero flow — dark grey
COL_INTERCONNECT:   Colour = (255,  0, 255)     # Interconnector marker — bright magenta

# ─────────────────────────────────────────────
# VSI VOLTAGE HALOS
# ─────────────────────────────────────────────
COL_VSI_HEALTHY:    Colour = (0,    0,   0)     # >=0.90: no halo drawn — placeholder, unused for drawing
COL_VSI_WATCH:      Colour = (255,255,   0)     # 0.90-0.85: bright yellow watch
COL_VSI_WARNING:    Colour = (255,  0,   0)     # 0.85-0.70: bright red warning
COL_VSI_CRITICAL:   Colour = (255,  0, 255)     # <0.70: bright magenta critical — distinct from WARNING's red

# ─────────────────────────────────────────────
# REACTIVE DEVICE GLYPHS
# ─────────────────────────────────────────────
COL_SHUNT_CAP:      Colour = (0,  255,   0)     # Auto shunt bank, capacitive step (+) — bright green
COL_SHUNT_REACTOR:  Colour = (0,    0, 255)     # Auto shunt bank, reactive step (-) — bright blue
COL_SVC:            Colour = (255,  0, 255)     # Manual SVC/STATCOM — bright magenta

# ─────────────────────────────────────────────
# FLOW MARKERS
# ─────────────────────────────────────────────
COL_FLOW_400KV:     Colour = (0,  170, 170)     # Cyan — dim sibling of Bright Cyan 400kV
COL_FLOW_220KV:     Colour = (0,  170,   0)     # Green — dim sibling of Bright Green 220kV
COL_FLOW_150KV:     Colour = (170,170,   0)     # Yellow — dim sibling of Bright Yellow 150kV
COL_FLOW_60KV:      Colour = (0,    0, 170)     # Blue — contrasts against yellow 60kV

# ─────────────────────────────────────────────
# ALARM COLOURS
# ─────────────────────────────────────────────
COL_ALARM_CRIT:     Colour = (255,  0,   0)     # Critical alarm — bright red
COL_ALARM_WARN:     Colour = (170,170,   0)     # Warning alarm — yellow
COL_ALARM_INFO:     Colour = (0,  170, 170)     # Info alarm — cyan
COL_ALARM_TUTOR:    Colour = (0,  170,   0)     # Tutorial alarm — green
COL_ALARM_ACK:      Colour = (85,  85,  85)     # Acknowledged alarm — dark grey

# ─────────────────────────────────────────────
# TEXT
# ─────────────────────────────────────────────
COL_TEXT_PRIMARY:   Colour = (255,255, 255)     # Primary labels — bright white
COL_TEXT_SECONDARY: Colour = (170,170, 170)     # Secondary / dim labels — white
COL_TEXT_DIM:       Colour = (85,  85,  85)     # Very dim — background labels
COL_TEXT_VALUE:     Colour = (0,  255,   0)     # Numeric values — bright green (CRT)
COL_TEXT_GOOD:      Colour = (0,  170,   0)     # Good status — green
COL_TEXT_WARN:      Colour = (170,170,   0)     # Warning status — yellow
COL_TEXT_CRIT:      Colour = (255,  0,   0)     # Critical status — bright red
COL_TEXT_HEADING:   Colour = (255,255,   0)     # Panel headings — bright yellow
COL_TEXT_BODY:      Colour = (0,  170,   0)     # Terminal screen body text — green
COL_TEXT_SCREEN_HDR:Colour = (0,  255,   0)     # Terminal screen header/separator — bright green

# ─────────────────────────────────────────────
# MENUS
# ─────────────────────────────────────────────
COL_MENU_CURSOR:    Colour = (0,  255,   0)     # Selected menu item — bright green
COL_MENU_DISABLED:  Colour = (85,  85,  85)     # Unavailable menu item — dark grey

# ─────────────────────────────────────────────
# INSTRUMENT STRIP PANELS
# ─────────────────────────────────────────────
COL_FREQ_NOMINAL:   Colour = (0,  170,   0)     # Frequency at nominal — green
COL_FREQ_ALERT:     Colour = (170,170,   0)     # Frequency at alert threshold — yellow
COL_FREQ_CRITICAL:  Colour = (255,  0,   0)     # Frequency at critical threshold — bright red
COL_METER_BG:       Colour = (0,    0,   0)     # Meter background — black
COL_FORECAST_CUR_BG:Colour = (85,  85,  85)     # Current forecast slot row highlight — dark grey
COL_METER_TICK:     Colour = (85,  85,  85)     # Meter tick marks — dark grey

# ─────────────────────────────────────────────
# SELECTION AND HIGHLIGHT
# ─────────────────────────────────────────────
COL_SELECTION:      Colour = (255,255, 255)     # Selected element outline — bright white
COL_HOVER:          Colour = (170,170, 170)     # Hovered element — white

# ─────────────────────────────────────────────
# CRISIS BORDER FLASH
# ─────────────────────────────────────────────
COL_CRISIS_WARN:    Colour = (170,170,   0)     # Warning crisis border — yellow
COL_CRISIS_CRIT:    Colour = (255,  0,   0)     # Critical crisis border — bright red

# ─────────────────────────────────────────────
# FPS COUNTER (always-on)
# ─────────────────────────────────────────────
COL_FPS_TEXT:       Colour = (0,  170,   0)     # Dim green — unobtrusive FPS readout

# ─────────────────────────────────────────────
# DEBUG OVERLAY
# ─────────────────────────────────────────────
COL_DEBUG_GRID:     Colour = (85,  85,  85)     # Faint coordinate grid — dark grey
COL_DEBUG_TEXT:     Colour = (0,  255,   0)     # Debug text — bright green
COL_DEBUG_CLICK:    Colour = (255,255,   0)     # Clicked coordinate display — bright yellow

# ─────────────────────────────────────────────
# LAYOUT EDITOR
# ─────────────────────────────────────────────
COL_EDITOR_LABEL:     Colour = (255,255,   0)   # Editor banner and drag label — bright yellow
COL_EDITOR_DIRTY:     Colour = (170,170,   0)   # Save indicator — unsaved changes (yellow)
COL_EDITOR_CLEAN:     Colour = (0,    0, 170)   # Save indicator — all saved (blue = calm)
COL_EDITOR_HIGHLIGHT: Colour = (255,255,   0)   # Hovered / dragged element ring — bright yellow

# ─────────────────────────────────────────────
# FORECAST OVERLAY
# ─────────────────────────────────────────────
COL_FORECAST_DEMAND:    Colour = (0,    0, 170)  # Demand bars — blue
COL_FORECAST_NETLOAD:   Colour = (170,170,   0)  # Net load bars — yellow
COL_FORECAST_NETDEMAND: Colour = (255,  0,   0)  # Net demand line — bright red

# ─────────────────────────────────────────────
# UNIT CONTEXT OVERLAY
# ─────────────────────────────────────────────
COL_CONTEXT_FIELD_BG:     Colour = (0,    0,   0)   # Input field background — black
COL_CONTEXT_FIELD_ACTIVE: Colour = (0,  170,   0)   # Active input border — green
COL_CONTEXT_CURSOR:       Colour = (0,  255,   0)   # Text cursor — bright green

# ─────────────────────────────────────────────
# GRID DESIGNER
# ─────────────────────────────────────────────
COL_DESIGNER_SIDEBAR_BG:  Colour = (0,    0,   0)   # Sidebar background — black
COL_DESIGNER_SIDEBAR_SEP: Colour = (85,  85,  85)   # Sidebar section separator — dark grey
COL_DESIGNER_PALETTE_SEL: Colour = (0,  255,   0)   # Selected palette button — bright green
COL_DESIGNER_PALETTE_BTN: Colour = (85,  85,  85)   # Unselected palette button — dark grey
COL_DESIGNER_LINE_DRAW:   Colour = (255,255,   0)   # Line-draw mode ghost line — bright yellow
COL_DESIGNER_STATUS_OK:   Colour = (0,  255,   0)   # Status message — success (bright green)
COL_DESIGNER_STATUS_INFO: Colour = (255,255, 255)   # Status message — info (bright white)
COL_DESIGNER_SURPLUS_POS: Colour = (0,  255,   0)   # Power surplus positive — bright green
COL_DESIGNER_SURPLUS_NEG: Colour = (255,  0,   0)   # Power surplus negative — bright red
COL_DESIGNER_FIELD_ACTIVE:Colour = (0,  170,   0)   # Active property field border — green
COL_DESIGNER_DELETE_CURSOR:Colour= (255,  0,   0)   # Delete mode cursor — bright red
COL_DESIGNER_GRID_DOT:    Colour = (60,  60,  60)   # Background reference dot-grid — dim grey

# ─────────────────────────────────────────────
# PLANNING PHASE (Phase 1 — pre-shift unit scheduling screen)
# ─────────────────────────────────────────────
COL_PLAN_LOAD_LINE:  Colour = (255,255,   0)  # Load-forecast overlay polyline — bright yellow
COL_PLAN_GRID_LINE:  Colour = (85,  85,  85)  # Plot/table gridlines and column separators
COL_PLAN_CELL_SEL:   Colour = (255,255, 255)  # Selected table cell highlight — bright white
COL_PLAN_OFFLINE:    Colour = (85,  85,  85)  # Dimmed row colour for an OFFLINE unit
COL_PLAN_WINDOW_MARK:Colour = (0,  170,   0)  # Shift-window bracket/highlight on the 24h axis
