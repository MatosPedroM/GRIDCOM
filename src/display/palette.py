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
COL_BACKGROUND:     Colour = (10, 12, 16)       # Near-black canvas background
COL_STRIP_BG:       Colour = (14, 16, 22)       # Instrument strip background
COL_PANEL_BG:       Colour = (18, 22, 30)       # Panel / context box background
COL_PANEL_BORDER:   Colour = (40, 50, 65)       # Panel border

# ─────────────────────────────────────────────
# VOLTAGE LEVEL LINES
# ─────────────────────────────────────────────
COL_400KV:  Colour = (220, 180, 60)     # Amber — 400kV backbone
COL_220KV:  Colour = (80, 160, 220)     # Sky blue — 220kV
COL_150KV:  Colour = (100, 200, 130)    # Green — 150kV
COL_60KV:   Colour = (140, 100, 180)    # Violet — 60kV load lines

# ─────────────────────────────────────────────
# LINE STATES
# ─────────────────────────────────────────────
COL_LINE_NORMAL:    Colour = (60, 70, 85)       # De-emphasised — within limits
COL_LINE_LOADED:    Colour = (200, 160, 40)     # Approaching limit (>85%)
COL_LINE_OVERLOAD:  Colour = (220, 60, 40)      # Overloaded (>100%)
COL_LINE_TRIPPED:   Colour = (35, 40, 50)       # Tripped — dead line
COL_LINE_HYDRAULIC: Colour = (60, 110, 160)     # Dashed hydraulic connector (non-electrical)

# ─────────────────────────────────────────────
# SUBSTATION SYMBOLS
# ─────────────────────────────────────────────
COL_BUS_NORMAL:     Colour = (160, 170, 185)    # Normal energised substation
COL_BUS_SELECTED:   Colour = (255, 255, 255)    # Selected element highlight
COL_BUS_BLACKED:    Colour = (40, 40, 50)       # Blacked out substation
COL_BUS_400KV:      Colour = (220, 180, 60)     # 400kV substation symbol
COL_BUS_220KV:      Colour = (80, 160, 220)     # 220kV substation symbol
COL_BUS_150KV:      Colour = (100, 200, 130)    # 150kV substation symbol
COL_BUS_60KV:       Colour = (140, 100, 180)    # 60kV load substation symbol

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
COL_UNIT_COAL:      Colour = (160, 130, 80)     # Coal — warm brown
COL_UNIT_CCGT:      Colour = (80, 160, 200)     # CCGT — light blue
COL_UNIT_NUCLEAR:   Colour = (100, 200, 100)    # Nuclear — green
COL_UNIT_HYDRO:     Colour = (60, 140, 200)     # Hydro — water blue
COL_UNIT_WIND:      Colour = (130, 200, 160)    # Wind — pale green
COL_UNIT_SOLAR:     Colour = (220, 200, 80)     # Solar — yellow

# ─────────────────────────────────────────────
# DEMAND ARROWS
# ─────────────────────────────────────────────
COL_DEMAND_ARROW:   Colour = (140, 100, 180)    # Load demand arrow (violet, matches 60kV)
COL_DEMAND_HIGH:    Colour = (200, 80, 80)      # High demand indicator

# ─────────────────────────────────────────────
# INTERCONNECTOR MARKERS
# ─────────────────────────────────────────────
COL_INTC_IMPORT:    Colour = (60, 200, 140)     # Importing — green
COL_INTC_EXPORT:    Colour = (200, 120, 60)     # Exporting — orange
COL_INTC_IDLE:      Colour = (80, 90, 110)      # Zero flow

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
COL_ALARM_CRIT:     Colour = (220, 50, 50)      # Critical alarm — red
COL_ALARM_WARN:     Colour = (220, 160, 40)     # Warning alarm — amber
COL_ALARM_INFO:     Colour = (80, 160, 220)     # Info alarm — blue
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
