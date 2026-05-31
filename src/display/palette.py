"""
src/display/palette.py

All colour constants for the GRIDCOM display.
Every RGB tuple in the codebase lives here — nowhere else.

See CLAUDE.md Rule 2.
See GRID_TOPOLOGY_AND_DISPLAY.md for visual specification.
"""

# Type alias
Colour = tuple[int, int, int]

# ─────────────────────────────────────────────
# BACKGROUND
# ─────────────────────────────────────────────
COL_BACKGROUND:     Colour = (10, 14, 20)       # Near-black canvas background
COL_CANVAS_BG:      Colour = (8,  12, 18)       # Grid canvas background (slightly darker)
COL_STRIP_BG:       Colour = (14, 16, 22)       # Instrument strip background
COL_PANEL_BG:       Colour = (12, 18, 24)       # Panel / context box background
COL_PANEL_BORDER:   Colour = (0, 102, 51)       # Panel border — dark green (SCADA terminal)

# ─────────────────────────────────────────────
# VOLTAGE LEVEL LINES
# ─────────────────────────────────────────────
COL_400KV:  Colour = (0, 200, 255)      # Bright cyan — 400kV backbone
COL_220KV:  Colour = (0, 255, 136)      # Bright green — 220kV
COL_150KV:  Colour = (255, 200, 0)      # Amber — 150kV
COL_60KV:   Colour = (200, 136, 0)      # Dark amber — 60kV load lines

# ─────────────────────────────────────────────
# LINE STATES
# ─────────────────────────────────────────────
COL_LINE_NORMAL:    Colour = (60, 70, 85)       # De-emphasised — unenergised / no-state
COL_LINE_ENERGISED: Colour = (40, 160, 80)      # Energised, load < 60% — dim green
COL_LOAD_WARN:      Colour = (204, 204, 0)      # 60-80% loading — yellow
COL_LOAD_HIGH:      Colour = (255, 136, 0)      # 80-95% loading — orange
COL_LOAD_CRIT:      Colour = (255, 34, 0)       # 95-100% and >100% loading — red
COL_LINE_LOADED:    Colour = (204, 204, 0)      # Alias for LOAD_WARN (backwards compat)
COL_LINE_OVERLOAD:  Colour = (255, 34, 0)       # Alias for LOAD_CRIT (backwards compat)
COL_LINE_TRIPPED:   Colour = (68, 68, 68)       # Tripped — dead line
COL_LINE_HYDRAULIC: Colour = (60, 110, 160)     # Dashed hydraulic connector (non-electrical)
COL_LOAD_SUB:       Colour = (200, 136, 0)      # Load substation triangle fill

# ─────────────────────────────────────────────
# SUBSTATION SYMBOLS
# ─────────────────────────────────────────────
COL_BUS_NORMAL:     Colour = (160, 170, 185)    # Normal energised substation
COL_BUS_SELECTED:   Colour = (255, 255, 255)    # Selected element highlight
COL_BUS_BLACKED:    Colour = (40, 40, 50)       # Blacked out substation
COL_BUS_400KV:      Colour = (0, 200, 255)      # 400kV substation symbol — bright cyan
COL_BUS_220KV:      Colour = (0, 255, 136)      # 220kV substation symbol — bright green
COL_BUS_150KV:      Colour = (255, 200, 0)      # 150kV substation symbol — amber
COL_BUS_60KV:       Colour = (200, 136, 0)      # 60kV load substation symbol — dark amber

# ─────────────────────────────────────────────
# GENERATION UNIT SQUARES
# ─────────────────────────────────────────────
COL_UNIT_ONLINE:    Colour = (60, 180, 100)     # Online and generating
COL_UNIT_STARTING:  Colour = (180, 140, 40)     # Starting — warming up
COL_UNIT_OFFLINE:   Colour = (55, 60, 72)       # Offline
COL_UNIT_SHUTDOWN:  Colour = (100, 80, 40)      # Shutting down
COL_UNIT_TRIPPED:   Colour = (180, 40, 40)      # Tripped by protection
COL_UNIT_BORDER:    Colour = (80, 90, 110)      # Unit square border

# ─────────────────────────────────────────────
# UNIT TYPE ACCENT COLOURS
# ─────────────────────────────────────────────
COL_UNIT_COAL:      Colour = (136, 136, 136)    # Coal — grey
COL_UNIT_CCGT:      Colour = (68, 136, 255)     # CCGT — blue
COL_UNIT_NUCLEAR:   Colour = (255, 136, 0)      # Nuclear — orange
COL_UNIT_HYDRO:     Colour = (0, 200, 255)      # Hydro — cyan
COL_UNIT_HYDRO_PUMP:Colour = (0, 68, 170)       # Hydro pumping mode — dark blue
COL_UNIT_WIND:      Colour = (136, 255, 68)     # Wind — lime green
COL_UNIT_SOLAR:     Colour = (255, 255, 0)      # Solar — yellow

# ─────────────────────────────────────────────
# DEMAND ARROWS
# ─────────────────────────────────────────────
COL_DEMAND_ARROW:   Colour = (200, 136, 0)      # Load demand arrow (dark amber, matches 60kV)
COL_DEMAND_HIGH:    Colour = (255, 34, 0)       # High demand indicator

# ─────────────────────────────────────────────
# INTERCONNECTOR MARKERS
# ─────────────────────────────────────────────
COL_INTC_IMPORT:    Colour = (60, 200, 140)     # Importing — green
COL_INTC_EXPORT:    Colour = (200, 120, 60)     # Exporting — orange
COL_INTC_IDLE:      Colour = (80, 90, 110)      # Zero flow
COL_INTERCONNECT:   Colour = (255, 136, 255)    # Interconnector marker — magenta

# ─────────────────────────────────────────────
# VSI VOLTAGE HALOS
# ─────────────────────────────────────────────
COL_VSI_WATCH:      Colour = (200, 180, 60)     # 0.90-0.95: yellow watch
COL_VSI_WARNING:    Colour = (220, 120, 40)     # 0.85-0.90: orange warning
COL_VSI_CRITICAL:   Colour = (200, 40, 40)      # <0.85: red critical

# ─────────────────────────────────────────────
# FLOW MARKERS
# ─────────────────────────────────────────────
COL_FLOW_400KV:     Colour = (180, 148, 50)     # Slightly dimmer than line colour
COL_FLOW_220KV:     Colour = (65, 130, 180)
COL_FLOW_150KV:     Colour = (80, 160, 105)
COL_FLOW_60KV:      Colour = (110, 80, 145)

# ─────────────────────────────────────────────
# ALARM COLOURS
# ─────────────────────────────────────────────
COL_ALARM_CRIT:     Colour = (255, 34, 0)       # Critical alarm — red
COL_ALARM_WARN:     Colour = (204, 204, 0)      # Warning alarm — yellow
COL_ALARM_INFO:     Colour = (0, 200, 255)      # Info alarm — cyan
COL_ALARM_ACK:      Colour = (60, 70, 85)       # Acknowledged alarm — dim

# ─────────────────────────────────────────────
# TEXT
# ─────────────────────────────────────────────
COL_TEXT_PRIMARY:   Colour = (210, 215, 225)    # Primary labels
COL_TEXT_SECONDARY: Colour = (130, 140, 160)    # Secondary / dim labels
COL_TEXT_DIM:       Colour = (80, 90, 110)      # Very dim — background labels
COL_TEXT_VALUE:     Colour = (180, 220, 180)    # Numeric values — light green
COL_TEXT_GOOD:      Colour = (80, 200, 100)     # Good status
COL_TEXT_WARN:      Colour = (220, 160, 40)     # Warning status
COL_TEXT_CRIT:      Colour = (220, 50, 50)      # Critical status
COL_TEXT_HEADING:   Colour = (220, 180, 60)     # Panel headings — amber

# ─────────────────────────────────────────────
# INSTRUMENT STRIP PANELS
# ─────────────────────────────────────────────
COL_FREQ_NOMINAL:   Colour = (60, 200, 100)     # Frequency at nominal
COL_FREQ_ALERT:     Colour = (220, 160, 40)     # Frequency at alert threshold
COL_FREQ_CRITICAL:  Colour = (220, 50, 50)      # Frequency at critical threshold
COL_METER_BG:       Colour = (12, 16, 22)       # Meter background
COL_METER_TICK:     Colour = (60, 70, 85)       # Meter tick marks

# ─────────────────────────────────────────────
# SELECTION AND HIGHLIGHT
# ─────────────────────────────────────────────
COL_SELECTION:      Colour = (255, 255, 255)    # Selected element outline
COL_HOVER:          Colour = (160, 180, 200)    # Hovered element

# ─────────────────────────────────────────────
# CRISIS BORDER FLASH
# ─────────────────────────────────────────────
COL_CRISIS_WARN:    Colour = (180, 120, 20)     # Warning crisis border
COL_CRISIS_CRIT:    Colour = (180, 30, 30)      # Critical crisis border

# ─────────────────────────────────────────────
# DEBUG OVERLAY
# ─────────────────────────────────────────────
COL_DEBUG_GRID:     Colour = (30, 35, 45)       # Faint coordinate grid
COL_DEBUG_TEXT:     Colour = (0, 220, 120)      # Debug text — bright green
COL_DEBUG_CLICK:    Colour = (255, 200, 0)      # Clicked coordinate display

# ─────────────────────────────────────────────
# LAYOUT EDITOR
# ─────────────────────────────────────────────
COL_EDITOR_LABEL:     Colour = (255, 220, 60)   # Editor banner and drag label — amber
COL_EDITOR_DIRTY:     Colour = (255, 160, 40)   # Save indicator — unsaved changes
COL_EDITOR_CLEAN:     Colour = (60, 80, 100)    # Save indicator — all saved
COL_EDITOR_HIGHLIGHT: Colour = (255, 255, 100)  # Hovered / dragged element ring

# ─────────────────────────────────────────────
# FORECAST OVERLAY
# ─────────────────────────────────────────────
COL_FORECAST_DEMAND:    Colour = (70, 80, 100)    # Demand bars — muted blue-grey
COL_FORECAST_NETLOAD:   Colour = (200, 140, 40)   # Net load bars — amber
COL_FORECAST_NETDEMAND: Colour = (220, 50, 50)    # Net demand line — red

# ─────────────────────────────────────────────
# UNIT CONTEXT OVERLAY
# ─────────────────────────────────────────────
COL_CONTEXT_FIELD_BG:     Colour = (18, 28, 36)   # Input field background
COL_CONTEXT_FIELD_ACTIVE: Colour = (0, 80, 40)    # Active input border — dim green
COL_CONTEXT_CURSOR:       Colour = (0, 200, 120)   # Text cursor — bright green
