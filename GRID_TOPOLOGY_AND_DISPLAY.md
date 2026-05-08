# Grid Construction, Topology and Display
### Power Plant Simulator — Developer Reference

---

## 1. Design Philosophy

### 1.1 Core Principles

The grid is a **schematic one-line diagram**, not a geographic map. Node positions are chosen for visual clarity and electrical legibility, not geographic accuracy. The layout is inspired by a Portuguese-scale power system in terms of density, generation mix, and topology — but is entirely fictional with no obligation to represent real infrastructure.

Three principles govern every display decision:

- **Electrical logic over geography** — nodes that are strongly coupled electrically should be visually close, regardless of where they would be on a map
- **State readable at a glance** — a player must be able to assess system health within 2 seconds of looking at the screen, without clicking anything
- **90s SCADA aesthetic** — the visual language of EMS/SCADA systems running on HP and Sun workstations in the early-to-mid 1990s. High contrast, hard edges, limited palette, monospace readouts, no gradients, no rounded corners

### 1.2 What the Grid Is Not

- Not a geographic map — no coastlines, no rivers, no terrain
- Not a force-directed graph — layout is hand-crafted for clarity
- Not procedurally generated (v1) — fixed topology with dynamic operational state
- Not zoned — no strict left/right/north/south regional boundaries enforced on the canvas. Assets that are geographically close in the fictional world are placed close on the schematic, but the layout reads as a network, not a map

---

## 2. Screen Layout and Resolution

### 2.1 Resolution Strategy

The game renders natively at **1920×1080** (16:9). All coordinates, sizes, and positions are authored at this resolution. At runtime, the display scales to the best available 16:9 resolution on the player's monitor:

```python
NATIVE_W, NATIVE_H = 1920, 1080

def get_display_resolution():
    info = pygame.display.Info()
    scale = min(info.current_w / NATIVE_W, info.current_h / NATIVE_H)
    w = int(NATIVE_W * scale)
    h = int(NATIVE_H * scale)
    return w, h, scale
```

The `scale` factor applies uniformly to all coordinates, line widths, font sizes, and symbol sizes. The game runs fullscreen — this sells the control room aesthetic and avoids titlebar height complications.

### 2.2 Screen Regions

The screen divides into two primary regions:

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│                      GRID CANVAS                               │
│                      1920 × 844 px                             │
│                      (78% of height)                           │
│                                                                │
├──────────┬─────────────┬──────────────────┬────────────────────┤
│FREQUENCY │ GEN / LOAD  │   UNIT DISPATCH  │   ALARM FEED       │
│  panel   │   BALANCE   │     panel        │   panel            │
│  280px   │   280px     │   640px          │   720px            │
│  × 236px │   × 236px   │   × 236px        │   × 236px          │
└──────────┴─────────────┴──────────────────┴────────────────────┘
                         INSTRUMENT STRIP
                         1920 × 236 px  (22% of height)
```

Grid canvas: **1920 × 844 px**
Instrument strip: **1920 × 236 px**
Strip top boundary: **Y = 844**

### 2.3 Typography

Use `pygame.freetype` — not the basic `pygame.font`. This gives proper hinting and subpixel rendering at small sizes.

Font assignments:

| Use | Font | Size | Anti-alias |
|-----|------|------|------------|
| Numeric readouts (MW, Hz, kV) | JetBrains Mono / Courier New | 11px | No — hard pixels |
| Node labels (4-letter codes) | JetBrains Mono | 10px | No |
| Panel headings | Liberation Sans / Roboto Condensed | 13px | Yes |
| Alarm text | JetBrains Mono | 11px | No |
| Major readout (frequency display) | JetBrains Mono Bold | 28px | Yes |

Ship JetBrains Mono with the game (open source, free). Do not rely on system fonts.

### 2.4 Colour Palette

The palette is deliberately restricted. Every colour has a specific semantic meaning and is used only for that meaning.

```python
# Background
COL_BACKGROUND    = (10,  14,  20)   # near-black, slightly blue
COL_CANVAS_BG     = (8,   12,  18)   # grid canvas, slightly darker

# Voltage level base colours (healthy state)
COL_400KV         = (0,  200, 255)   # bright cyan
COL_220KV         = (0,  255, 136)   # bright green
COL_150KV         = (255, 200,  0)   # amber
COL_60KV          = (200, 136,  0)   # dark amber / brown

# Loading state overrides (applied when loading > 60%)
COL_LOAD_WARN     = (204, 204,  0)   # yellow      60-80%
COL_LOAD_HIGH     = (255, 136,  0)   # orange      80-95%
COL_LOAD_CRIT     = (255,  34,  0)   # red         95-100%
COL_LOAD_OVER     = (255,  34,  0)   # red + blink >100%
COL_LINE_TRIPPED  = (68,  68,  68)   # dark grey   out of service

# Generation unit type colours
COL_COAL          = (136, 136, 136)  # grey
COL_CCGT          = (68,  136, 255)  # blue
COL_NUCLEAR       = (255, 136,  0)   # orange
COL_HYDRO         = (0,  200, 255)   # cyan (same family as 400kV)
COL_HYDRO_PUMP    = (0,   68, 170)   # dark blue (pumping mode)
COL_WIND          = (136, 255,  68)  # lime green
COL_SOLAR         = (255, 255,  0)   # yellow

# Load substation
COL_LOAD_SUB      = (200, 136,  0)   # amber
COL_LOAD_HIGH_SUB = (255,  68,  0)   # orange-red (>85% loading)

# Interconnector
COL_INTERCONNECT  = (255, 136, 255)  # magenta

# UI chrome
COL_PANEL_BORDER  = (0,  102,  51)   # dark green (SCADA terminal)
COL_PANEL_BG      = (12,  18,  24)   # very dark blue-grey
COL_TEXT_PRIMARY  = (220, 220, 220)  # near-white
COL_TEXT_DIM      = (120, 120, 120)  # grey

# Alarm colours
COL_ALARM_CRIT    = (255,  34,  0)   # red
COL_ALARM_WARN    = (204, 204,  0)   # yellow
COL_ALARM_INFO    = (0,  200, 255)   # cyan
```

---

## 3. Symbol Vocabulary

All symbols are drawn procedurally with pygame draw calls — no sprite sheets. This keeps the codebase clean and allows colour changes at runtime without texture management.

### 3.1 Transmission Substation

A **square with an upward triangle** inscribed inside.

```
┌───────┐
│   △   │   12×12 px at native resolution
└───────┘
```

- Square border: 1px, colour = voltage level base colour
- Triangle fill: voltage level base colour at 70% brightness
- Triangle: pointing upward, vertices at (centre-top, bottom-left, bottom-right) inset 2px from square edges

State modifiers on the border:

| State | Border | Effect |
|-------|--------|--------|
| Normal | 1px voltage colour | None |
| Voltage warning (VSI 0.90–0.95) | 2px yellow | None |
| Voltage critical (VSI 0.85–0.90) | 2px orange | None |
| Voltage collapse risk (<0.85) | 2px red | Blink 1Hz |
| Out of service | 1px dark grey | Fill black |

### 3.2 Load Substation (60kV)

A **square with a downward triangle** inscribed inside. Same size and construction as transmission substation. The inverted triangle semantically suggests "energy flowing down into distribution."

```
┌───────┐
│   ▽   │   12×12 px
└───────┘
```

- Square border: 1px `COL_60KV` amber
- Triangle fill: `COL_LOAD_SUB` amber at 70% brightness
- Triangle: pointing downward

Load state modifiers:

| Load Level | Fill Colour |
|-----------|-------------|
| < 50% | `COL_LOAD_SUB` dim |
| 50–85% | `COL_LOAD_SUB` normal |
| 85–100% | `COL_LOAD_HIGH_SUB` orange |
| > 100% | Red + blink |

### 3.3 Generation Unit Square

A **filled square**, 12×12 px. This is the most repeated element on the canvas.

```
┌───────┐
│  ░░░  │   Output bar — bottom-aligned, height = output/rated
│  ░░░  │
│       │
└───────┘
```

**Fill colour**: unit type colour (see palette above)
**Border**: 2px, state-dependent:

| Unit State | Border Colour | Effect |
|------------|---------------|--------|
| Online, dispatched | `#FFFFFF` white | None |
| Online, zero output | `#666666` dim grey | None |
| Starting up | `#FFFF00` yellow | Blink slow (0.5Hz) |
| Shutdown sequence | `#888888` grey | Blink slow |
| Offline / cold | `#333333` near-black | Fill darkened 70% |
| Fault / tripped | `#FF0000` red | Blink fast (2Hz) |

**Output bar**: drawn inside the square, bottom-aligned.
- Width: full interior width (8px)
- Height: proportional to `current_MW / rated_MW`, clamped 0–8px
- Colour: unit type colour at 160% brightness (brighter than fill)

**Multi-unit stations**: unit squares are drawn side by side with 2px gap between them, connected by a single horizontal collector line at their base before the feeder drop to the substation.

```
  [■][■][■]     ← 3 unit squares, 2px gap
   └──┬──┘      ← collector line
      │          ← feeder to substation bus
```

### 3.4 Pumped Storage Mode Indicator

Large hydro upper reservoir units have an additional mode arrow drawn in the centre of the unit square, overriding the output bar:

| Mode | Arrow | Fill Colour |
|------|-------|-------------|
| Generating | ↑ (upward, 6px) | `COL_HYDRO` cyan |
| Pumping | ↓ (downward, 6px) | `COL_HYDRO_PUMP` dark blue |
| Idle | None | Darkened cyan |

The arrow is white, 1px stroke, centred in the square.

### 3.5 Demand Arrow

Small loads that hang off transmission buses without their own node:

```
      ▼       ← solid filled triangle, 8×10px, COL_LOAD_SUB amber
    NNNN      ← 4-digit MW label, 10px monospace below
```

Always hangs downward from the bus line. Never interactive — informational only. Multiple demand arrows on the same bus stack horizontally with 4px gap.

### 3.6 Hydraulic Penstock Connector

The connection between a pumped storage upper reservoir and its downstream lower plant is **hydraulic, not electrical**. It must be visually distinct from transmission lines:

```
Upper reservoir bus
        ┊
        ┊   ← dashed line, 2px, COL_HYDRO cyan, 4px dash / 4px gap
        ┊
Lower plant bus
```

This connector carries no electrical flow and is not part of the load flow network. It is display-only, showing the hydraulic relationship. A small water-drop symbol (◈ or custom 6px sprite) can be placed at the midpoint.

### 3.7 Interconnector Terminus

Spain interconnectors terminate at the canvas edge with a chevron:

```
══════════►  ESP-N     ← double line ending in filled chevron, label after
```

Colour: `COL_INTERCONNECT` magenta — the only magenta element on the canvas, immediately distinguishable from all domestic grid elements. MW flow label shown on the line, positive = import, negative = export.

---

## 4. Transmission Lines

### 4.1 Voltage Level Representation

Lines are distinguished by **parallel line count and thickness**, not colour alone. Colour encodes loading state (overrides voltage colour above 60% loading).

| Voltage | Representation | Healthy Colour |
|---------|---------------|----------------|
| 400kV | Two parallel lines, 2px each, 4px gap | `COL_400KV` cyan |
| 220kV | Single line, 3px | `COL_220KV` green |
| 150kV | Single line, 2px | `COL_150KV` amber |
| 60kV | Dotted line, 1px, 3px dot / 3px gap | `COL_60KV` dark amber |

The 400kV double-line representation is the primary voltage hierarchy signal. A player learns instantly that thick cyan double-lines are the backbone.

### 4.2 Loading State Colour Override

Loading state overrides the voltage base colour above 60%:

```
0  –  60%:   voltage base colour (identity preserved)
60 –  80%:   COL_LOAD_WARN   yellow
80 –  95%:   COL_LOAD_HIGH   orange
95 – 100%:   COL_LOAD_CRIT   red
    > 100%:  COL_LOAD_OVER   red + blink 2Hz
Tripped:     COL_LINE_TRIPPED dark grey, dashed regardless of voltage
```

Both parallel lines of a 400kV double-line change colour together.

### 4.3 Power Flow Animation

Animated markers travel along every energised line showing power flow direction and magnitude:

- **Marker shape**: filled square, 3×3px
- **Marker colour**: matches current line colour (loading state colour)
- **Speed**: proportional to MW flow — `speed_px = (MW_flow / line_rating) × MAX_SPEED`
- **MAX_SPEED**: 80px/second at full rating (tunable)
- **Direction**: from injection bus toward receiving bus
- **Spacing**: markers every 40px along line at full speed, wider spaced at low flow
- **Zero flow**: no markers shown
- **Tripped line**: no markers

For 400kV double-lines, markers travel on both parallel lines simultaneously (same direction, same speed).

### 4.4 Line Crossings

The canvas uses a mattress layout where line crossings are unavoidable and acceptable. The convention is:

- **No hop symbols** — crossings are drawn as simple overlapping lines
- **Connection dot** (4px filled circle, white) marks every actual junction
- Players learn: dot = connected, crossing without dot = not connected
- This is identical to real one-line diagram convention

Higher voltage lines are drawn on top of lower voltage lines at crossings (draw order: 60kV first, then 150kV, 220kV, 400kV last).

---

## 5. Node Labelling

### 5.1 Label Convention

Every bus on the canvas has a **4-character uppercase label**. Labels are unique across the entire grid. The full label list is defined in `src/data/topology.py`; the convention by asset type is:

| Label(s) | Asset Type | Voltage |
|----------|-----------|---------|
| `MDBY` | Midbury — slack bus, 400kV backbone | 400kV |
| `CNTR`, `NRTH`, `EAST`, `WEST`, `STHW` | 400kV backbone substations | 400kV |
| `ASHF`, `WRNT`, `RDST`, `FAIR`, `COAL`, `DUNM` | 220kV south sub-grid | 220kV |
| `KELM`, `BARR`, `SLST`, `WNCN`, `ASHG`, `WRNG` | 220kV centre expansion | 220kV |
| `BARD`, `KELD`, `DUND` | Downstream hydro lower plants | 220kV |
| `AR01`–`AR04` | River Arden run-of-river cascade | 220kV |
| `BRCK`, `STAN`, `FLDN` | 150kV regional substations | 150kV |
| `BR01`–`BR03` | River Brent run-of-river cascade | 150kV |
| `CO01`–`CO03` | River Coln run-of-river cascade | 150kV |
| `LD01`–`LD06` | 60kV load substations | 60kV |
| `INTC-N`, `INTC-S` | Interconnectors (display-only, not electrical nodes) | — |

Generation units are **not separate canvas nodes**. They are drawn as unit squares offset from their host bus. Unit labels follow the format `STATION-N` (e.g. `RVSD-1`, `HART-2`). Station canvas positions are defined in `src/data/fleet.py` → `STATION_POSITIONS`.

### 5.2 Label Placement

Labels are placed **below** the node symbol by default (4px gap below symbol bottom edge). If below is occupied by unit squares or feeder lines, the label moves **above** the symbol.

Label colour: `COL_TEXT_DIM` grey — present but not competing with operational data. On selection (click), label brightens to `COL_TEXT_PRIMARY`.

### 5.3 Real-Time Data Labels

A second, smaller label shows the most operationally relevant value for each node type:

| Node Type | Live Label | Format |
|-----------|-----------|--------|
| Transmission substation | Voltage (pu) | `1.02` |
| Load substation | Current demand | `342MW` |
| Generation unit | Current output | `285MW` |
| Interconnector | Net flow | `+412MW` |
| Wind / Solar | Current output | `187MW` |

Live labels use `COL_TEXT_PRIMARY` when within normal range, shift to warning/alarm colours when outside bounds. Size: 10px monospace.

---

## 6. Generation Fleet

### 6.1 Complete Asset List

System peak demand: **8,000 MW**
System base: **1,000 MVA**

All station data is authoritative in `src/data/fleet.py`.

```
STATION  UNITS  CONFIG       MW    VOLTAGE  BUS    TYPE              SHIFT
────────────────────────────────────────────────────────────────────────────
COAL
  RVSD   3      3 × 300MW    900   400kV    MDBY   Thermal baseload  1
  THNF   3      3 × 300MW    900   400kV    NRTH   Thermal baseload  5

CCGT / GAS
  ASHG   2      2 × 400MW    800   220kV    ASHG   Mid-merit         3
  WRNG   2      2 × 400MW    800   220kV    WRNG   Mid-merit         3

NUCLEAR
  HART   2      2 × 700MW   1400   400kV    CNTR   Baseload          1

LARGE HYDRO — pumped storage upper (reversible)
  DUNH   2      2 × 200MW    400   400kV    STHW   Pumped storage    1
  KELM   2      2 × 250MW    500   400kV    WEST   Pumped storage    3
  BARR   2      2 × 250MW    500   400kV    EAST   Pumped storage    3

LARGE HYDRO — downstream lower (conventional)
  DUND   2      2 ×  65MW    130   220kV    DUND   Downstream RoR    1
  KELD   2      2 ×  80MW    160   220kV    KELD   Downstream RoR    3
  BARD   2      2 ×  80MW    160   220kV    BARD   Downstream RoR    3

RUN-OF-RIVER CASCADES — River Arden (220kV)
  AR01   2      2 ×  40MW     80   220kV    AR01   RoR               5
  AR02   2      2 ×  35MW     70   220kV    AR02   RoR               5
  AR03   2      2 ×  30MW     60   220kV    AR03   RoR               5
  AR04   2      2 ×  25MW     50   220kV    AR04   RoR               5

RUN-OF-RIVER CASCADES — River Brent (150kV)
  BR01   2      2 ×  30MW     60   150kV    BR01   RoR               5
  BR02   2      2 ×  25MW     50   150kV    BR02   RoR               5
  BR03   2      2 ×  20MW     40   150kV    BR03   RoR               5

RUN-OF-RIVER CASCADES — River Coln (150kV)
  CO01   2      2 ×  28MW     56   150kV    CO01   RoR               5
  CO02   2      2 ×  23MW     46   150kV    CO02   RoR               5
  CO03   1      1 ×  18MW     18   150kV    CO03   RoR               5

RENEWABLES
  WNCN   1      aggregated   500   220kV    WNCN   Wind              3
  WNBR   1      aggregated   300   150kV    BRCK   Wind              5
  SLST   1      aggregated   600   220kV    SLST   Solar             3
  SLFD   1      aggregated   400   150kV    FLDN   Solar             5

INTERCONNECTORS (display-only, not electrical buses)
  INTC-N  —    ±800MW        —    400kV    —      External ref.     1
  INTC-S  —    ±600MW        —    400kV    —      External ref.     1

TOTAL FIRM CAPACITY (excl. wind, solar, interconnectors):  5,490 MW  (full grid)
TOTAL INSTALLED (all sources, full grid):                  7,240 MW
PEAK DEMAND:                                               8,000 MW
```

Note: peak demand (8,000 MW) exceeds firm capacity — interconnectors and renewables make up the difference. This is an intentional design constraint that creates operational tension.

### 6.2 Pumped Storage Structure

Three pumped storage complexes exist. Each consists of an upper reservoir plant (reversible, connects to 400kV backbone bus) and a downstream lower plant (conventional, connects to a 220kV bus).

| Complex | Upper station | Upper bus | Lower station | Lower bus |
|---------|--------------|-----------|--------------|-----------|
| Dunmore | DUNH (2×200MW) | STHW | DUND (2×65MW) | DUND |
| Kelmore | KELM (2×250MW) | WEST | KELD (2×80MW) | KELD |
| Barrow  | BARR (2×250MW) | EAST | BARD (2×80MW) | BARD |

**Upper plant** (reversible pump-turbines):
- Connects to grid at the named 400kV backbone bus
- Can generate (water releases through turbines) or pump (motor mode, pushes water uphill)
- In pump mode: appears as a **load** on the network (PQ bus, negative injection)
- In generate mode: appears as a **generator** (PV bus, positive injection)

**Lower plant** (conventional turbines):
- Connects to grid at its own dedicated 220kV bus (DUND, KELD, or BARD)
- Generate or idle only — cannot pump
- Output depends on water released from upper reservoir plus natural inflow

**Hydraulic connection** (penstock):
- Not an electrical connection
- Shown as dashed cyan line between upper bus and lower bus on the canvas
- Carries no electrical flow — display only

**Operational modes — Dunmore example (DUNH + DUND):**

| Mode | DUNH upper | DUND lower | Net MW |
|------|------------|------------|--------|
| Full generate | +400MW gen | +130MW gen | +530MW |
| Natural flow | idle | +130MW gen | +130MW |
| Pump + lower gen | −400MW load | +130MW gen | −270MW |
| Full pump | −400MW load | idle | −400MW |

The pump mode creates an interesting schematic situation: the upper plant unit squares display in pumping-mode dark blue with downward arrow, while the 400kV substation feeding it shows increased load on its incoming lines.

### 6.3 Run-of-River Cascade Structure

Three river cascades. Each is a sequence of stations on the same river; water flows station 1 → 2 → 3 (→ 4 for Arden). Each station is electrically independent with its own connection to the transmission grid.

| Cascade | Stations | Voltage | Connects to |
|---------|----------|---------|------------|
| River Arden | AR01, AR02, AR03, AR04 | 220kV | AR04 feeds STAN via L26 |
| River Brent | BR01, BR02, BR03 | 150kV | BR01 feeds BRCK via L25 |
| River Coln  | CO01, CO02, CO03 | 150kV | CO01 feeds FLDN via L27 |

On the schematic, cascade stations are drawn in a staircase sequence with short hydraulic connectors (dashed lines) between sequential stations, distinct from electrical lines.

```
AR01──┊──AR02──┊──AR03──┊──AR04    River Arden (220kV, 4 stations)
BR01──┊──BR02──┊──BR03             River Brent (150kV, 3 stations)
CO01──┊──CO02──┊──CO03             River Coln  (150kV, 3 stations)
       ┊ = hydraulic connector (dashed, not electrical)
```

Each cascade station bus has its own electrical feeder in the simulation. AR01–AR03 are radial (no electrical lines other than their single feed); AR04 is the exit point of the Arden cascade, connected to STAN via L26. Brent exit is BR01→BRCK (L25). Coln exit is CO01→FLDN (L27).

---

## 7. Network Topology

### 7.1 Bus List (40 buses)

Authoritative source: `src/data/topology.py` → `BUSES`. All 40 buses listed below.

**400kV backbone — 6 buses (Shifts 1–5)**

```
LABEL  NAME           SHIFT  NOTES
─────────────────────────────────────────────────────────────────
MDBY   Midbury        1      Slack bus — voltage/angle reference
CNTR   Centrefield    1      HART nuclear station connects here
STHW   Southwick      1      DUNH pumped storage connects here
EAST   Eastmoor       3      BARR pumped storage connects here
WEST   Westham        3      KELM pumped storage connects here
NRTH   Northgate      5      THNF coal station connects here
```

**220kV south sub-grid — 6 buses (Shifts 1–2)**

```
LABEL  NAME           SHIFT  NOTES
─────────────────────────────────────────────────────────────────
ASHF   Ashford        1      ASHG CCGT connects here (Shift 3)
WRNT   Wrentham       1      WRNG CCGT connects here (Shift 3)
RDST   Redstone       1      220kV ring, connects to KELM (Shift 3)
FAIR   Fairfield      1      220kV ring hub
COAL   Coalton        1      220kV ring, connects to BARR (Shift 3)
DUNM   Dunmore        1      DUND downstream hydro feeds here
```

**220kV centre expansion — 6 buses (Shifts 3–4)**

```
LABEL  NAME           SHIFT  NOTES
─────────────────────────────────────────────────────────────────
ASHG   Ashford CCGT   3      Generation bus — ASHG-1, ASHG-2
WRNG   Wrentham CCGT  3      Generation bus — WRNG-1, WRNG-2
KELM   Kelmore        3      Generation bus — KELM-1, KELM-2 (pumped storage)
BARR   Barrow         3      Generation bus — BARR-1, BARR-2 (pumped storage)
SLST   Stanton Solar  3      Generation bus — SLST-1 (600MW solar)
WNCN   Cairn Wind     3      Generation bus — WNCN-1 (500MW wind)
```

**220kV downstream hydro — 3 buses (Shifts 1–3)**

```
LABEL  NAME           SHIFT  NOTES
─────────────────────────────────────────────────────────────────
DUND   Dunmore Lower  1      Generation bus — DUND-1, DUND-2 (2×65MW)
KELD   Kelmore Lower  3      Generation bus — KELD-1, KELD-2 (2×80MW)
BARD   Barrow Lower   3      Generation bus — BARD-1, BARD-2 (2×80MW)
```

**150kV regional substations — 3 buses (Shift 5)**

```
LABEL  NAME     SHIFT  NOTES
─────────────────────────────────────────────────────────────────
BRCK   Brackley   5    WNBR wind (300MW) connects here
STAN   Stanton    5    Receives AR04 cascade via L26; SLST solar via L29
FLDN   Feldon     5    SLFD solar (400MW) connects here; receives CO01 via L27
```

**220kV River Arden cascade — 4 buses (Shift 5)**

```
LABEL  NAME      SHIFT  UNITS          NOTES
─────────────────────────────────────────────────────────────────
AR01   Arden 1   5      AR01-1, AR01-2  (2×40MW)   Radial — no exit line
AR02   Arden 2   5      AR02-1, AR02-2  (2×35MW)   Radial
AR03   Arden 3   5      AR03-1, AR03-2  (2×30MW)   Radial
AR04   Arden 4   5      AR04-1, AR04-2  (2×25MW)   Connects to STAN via L26
```

**150kV River Brent cascade — 3 buses (Shift 5)**

```
LABEL  NAME      SHIFT  UNITS          NOTES
─────────────────────────────────────────────────────────────────
BR01   Brent 1   5      BR01-1, BR01-2  (2×30MW)   Connects to BRCK via L25
BR02   Brent 2   5      BR02-1, BR02-2  (2×25MW)   Radial
BR03   Brent 3   5      BR03-1, BR03-2  (2×20MW)   Radial
```

**150kV River Coln cascade — 3 buses (Shift 5)**

```
LABEL  NAME      SHIFT  UNITS          NOTES
─────────────────────────────────────────────────────────────────
CO01   Coln 1    5      CO01-1, CO01-2  (2×28MW)   Connects to FLDN via L27
CO02   Coln 2    5      CO02-1, CO02-2  (2×23MW)   Radial
CO03   Coln 3    5      CO03-1           (1×18MW)   Radial
```

**60kV load substations — 6 buses (Shifts 1–3)**

```
LABEL  NAME        SHIFT  PEAK LOAD  FED FROM (electrical line)
────────────────────────────────────────────────────────────────
LD01   Load Sub 1  1      ~1,400MW   ASHF  (no explicit line modelled)
LD02   Load Sub 2  1      ~1,200MW   WRNT  (no explicit line modelled)
LD03   Load Sub 3  1      ~1,000MW   DUNM  (no explicit line modelled)
LD04   Load Sub 4  1      ~  800MW   FAIR  (no explicit line modelled)
LD05   Load Sub 5  1      ~  700MW   COAL  (no explicit line modelled)
LD06   Load Sub 6  3      ~  500MW   SLST  (no explicit line modelled)
```

Note: 60kV lines are not modelled in the electrical network. Load is represented as P-injection at the 220kV/400kV parent bus. The 60kV substation symbols are drawn on the canvas as demand nodes, but are electrically isolated in the simulation (no 60kV lines in `LINES`). This is intentional.

### 7.2 Transmission Line List

Authoritative source: `src/data/topology.py` → `LINES`. 29 lines total.

**400kV backbone — 7 lines (Shift 5), double-line cyan rendering**

```
LINE  FROM   TO     RATING   X(pu)  SHIFT  NOTES
──────────────────────────────────────────────────────
L01   MDBY   CNTR   2000MW   0.050  5      Central spine
L02   CNTR   NRTH   1800MW   0.055  5      North extension
L03   NRTH   EAST   2000MW   0.040  5      North-east ring
L04   MDBY   WEST   1800MW   0.045  5      West branch
L05   WEST   STHW   1600MW   0.050  5      West-centre link
L06   STHW   CNTR   1800MW   0.045  5      South-centre link
L07   EAST   STHW   1600MW   0.060  5      Cross-ring (N-1 support)
```

**400kV ↔ 220kV transformer links — 4 lines (Shifts 1–5)**
Modelled as low-reactance lines (not explicit transformer elements).

```
LINE  FROM   TO     RATING   X(pu)  SHIFT  NOTES
──────────────────────────────────────────────────────
L08   STHW   ASHF   1200MW   0.020  1      Primary south infeed
L09   CNTR   WRNT   1200MW   0.020  1      Secondary south infeed
L10   NRTH   COAL   1000MW   0.022  5      North → 220kV east
L11   WEST   RDST   1000MW   0.022  3      West → 220kV south
```

**220kV south sub-grid — 5 lines (Shift 1), single 3px green**

```
LINE  FROM   TO     RATING  X(pu)  SHIFT
──────────────────────────────────────────
L12   ASHF   FAIR    800MW  0.090  1
L13   FAIR   WRNT    800MW  0.095  1
L14   ASHF   DUNM    700MW  0.100  1
L15   DUNM   RDST    600MW  0.110  1
L16   WRNT   COAL    800MW  0.085  1
```

**220kV centre expansion — 5 lines (Shifts 1–3), single 3px green**

```
LINE  FROM   TO     RATING  X(pu)  SHIFT  NOTES
─────────────────────────────────────────────────────
L17   RDST   KELM    600MW  0.120  3      220kV west extension
L18   COAL   BARR    700MW  0.100  3      220kV east extension
L19   FAIR   SLST    700MW  0.095  3      Stanton Solar infeed
L20   WRNT   WRNG    900MW  0.030  3      WRNG CCGT transformer link
L21   ASHF   ASHG    900MW  0.025  3      ASHG CCGT transformer link
```

**150kV regional — 3 lines (Shift 5), single 2px amber**

```
LINE  FROM   TO     RATING  X(pu)  SHIFT
──────────────────────────────────────────
L22   RDST   BRCK    450MW  0.150  5
L23   FAIR   STAN    450MW  0.140  5
L24   COAL   FLDN    400MW  0.145  5
```

**150kV cascade feeders — 3 lines (Shift 5), single 2px amber**
These are the only electrical connections to the cascade buses.

```
LINE  FROM   TO     RATING  X(pu)  SHIFT  NOTES
───────────────────────────────────────────────────────
L25   BRCK   BR01    350MW  0.160  5      Brent exit → 150kV ring
L26   STAN   AR04    400MW  0.130  5      Arden exit → 150kV ring
L27   FLDN   CO01    350MW  0.155  5      Coln exit → 150kV ring
```

**Downstream hydro and cross-voltage links — 2 lines (Shifts 1/5)**

```
LINE  FROM   TO     RATING  X(pu)  SHIFT  NOTES
───────────────────────────────────────────────────────
L28   DUNM   DUND    200MW  0.080  1      Dunmore downstream hydro feed
L29   SLST   STAN    500MW  0.075  5      Stanton Solar → 150kV ring
```

### 7.3 Slack Bus

**MDBY** (Midbury, 400kV) is the slack bus — it absorbs the system imbalance and provides the voltage angle reference (θ = 0). In simulation terms it represents the system's balancing point. In game terms, it is the electrical centre of gravity of the network. Riverside Coal (RVSD) connects here.

Interconnectors (INTC-N ±800MW, INTC-S ±600MW) are external references not part of the network topology. Their scheduled flow is folded into the MDBY slack injection. They are shown on the canvas as chevron markers at the right edge.

---

## 8. Canvas Layout

### 8.1 Layout Philosophy

The mattress layout distributes nodes across the full 1920×844 canvas without strict regional boundaries. Nodes that are electrically adjacent are placed close together. The layout respects a minimum inter-node distance of **60px** and a maximum local density of **5 nodes within any 200×200px area**.

### 8.2 Node Positions (native 1920×844)

Positions are (X, Y) in pixels from top-left corner of the grid canvas.
Authoritative source: `src/data/topology.py` → `Bus.canvas_x / canvas_y`.
Station positions: `src/data/fleet.py` → `STATION_POSITIONS`.

**400kV backbone buses** (drawn as cyan △-in-square):

```
LABEL  NAME           (X,    Y)   NOTES
──────────────────────────────────────────────
MDBY   Midbury        (520,  160)  Slack bus — RVSD coal station above
CNTR   Centrefield    (960,  120)  HART nuclear above
STHW   Southwick      (760,  280)  DUNH pumped storage above
EAST   Eastmoor       (1640, 280)  BARR pumped storage above
WEST   Westham        (280,  280)  KELM pumped storage above
NRTH   Northgate      (1400, 160)  THNF coal above
```

**220kV south sub-grid buses** (drawn as green △-in-square):

```
LABEL  NAME           (X,    Y)
─────────────────────────────────────
ASHF   Ashford        (640,  400)
WRNT   Wrentham       (1080, 400)
RDST   Redstone       (360,  500)
FAIR   Fairfield      (860,  480)
COAL   Coalton        (1280, 460)
DUNM   Dunmore        (520,  520)
```

**220kV centre expansion buses** (drawn as green △-in-square):

```
LABEL  NAME           (X,    Y)   NOTES
────────────────────────────────────────────────
ASHG   Ashford CCGT   (680,  340)  Generation bus (ASHG station)
WRNG   Wrentham CCGT  (1180, 340)  Generation bus (WRNG station)
KELM   Kelmore        (160,  360)  Generation bus (KELM pumped storage)
BARR   Barrow         (1560, 360)  Generation bus (BARR pumped storage)
SLST   Stanton Solar  (1160, 520)  Generation bus (SLST solar)
WNCN   Cairn Wind     (1760, 420)  Generation bus (WNCN wind)
```

**220kV downstream hydro buses** (drawn as green △-in-square):

```
LABEL  NAME           (X,    Y)
─────────────────────────────────────
DUND   Dunmore Lower  (460,  560)
KELD   Kelmore Lower  (120,  460)
BARD   Barrow Lower   (1680, 460)
```

**150kV regional buses** (drawn as amber △-in-square):

```
LABEL  NAME     (X,    Y)
───────────────────────────
BRCK   Brackley (240,  580)
STAN   Stanton  (1080, 580)
FLDN   Feldon   (1480, 580)
```

**River Arden cascade buses** (220kV, staircase layout):

```
LABEL  NAME    (X,    Y)
──────────────────────────
AR01   Arden 1 (440,  620)
AR02   Arden 2 (540,  660)
AR03   Arden 3 (640,  700)
AR04   Arden 4 (740,  660)
```

**River Brent cascade buses** (150kV, staircase descending):

```
LABEL  NAME    (X,    Y)
──────────────────────────
BR01   Brent 1 (300,  640)
BR02   Brent 2 (200,  680)
BR03   Brent 3 (140,  720)
```

**River Coln cascade buses** (150kV, staircase descending):

```
LABEL  NAME    (X,    Y)
──────────────────────────
CO01   Coln 1  (1360, 640)
CO02   Coln 2  (1460, 680)
CO03   Coln 3  (1540, 720)
```

**60kV load substation buses** (drawn as amber ▽-in-square):

```
LABEL  NAME       (X,    Y)
────────────────────────────
LD01   Load Sub 1 (480,  760)
LD02   Load Sub 2 (720,  780)
LD03   Load Sub 3 (960,  760)
LD04   Load Sub 4 (1200, 780)
LD05   Load Sub 5 (1440, 760)
LD06   Load Sub 6 (240,  760)
```

**Interconnector display markers** (not electrical buses):

```
LABEL   (X,    Y)   NOTES
────────────────────────────────────────────────
INTC-N  (1840, 120)  Top-right — chevron pointing right
INTC-S  (1840, 300)  Right side — chevron pointing right
```

**Station positions** (unit squares drawn offset from host bus):

```
STATION  (X,    Y)   HOST BUS  UNITS
─────────────────────────────────────────────────────────────────
RVSD     (520,  220)  MDBY      3 squares horizontal, above bus
THNF     (1400, 220)  NRTH      3 squares horizontal, above bus
HART     (960,  180)  CNTR      2 squares horizontal, above bus
ASHG     (640,  320)  ASHG      2 squares horizontal, above bus
WRNG     (1120, 320)  WRNG      2 squares horizontal, above bus
DUNH     (760,  340)  STHW      2 squares horizontal, above bus
KELM     (200,  340)  WEST      2 squares horizontal, above bus
BARR     (1640, 340)  EAST      2 squares horizontal, above bus
DUND     (460,  600)  DUND      2 squares horizontal, above bus
KELD     (100,  500)  KELD      2 squares horizontal, above bus
BARD     (1700, 500)  BARD      2 squares horizontal, above bus
AR01     (440,  640)  AR01      2 squares
AR02     (540,  680)  AR02      2 squares
AR03     (640,  720)  AR03      2 squares
AR04     (740,  680)  AR04      2 squares
BR01     (300,  660)  BR01      2 squares
BR02     (200,  700)  BR02      2 squares
BR03     (140,  740)  BR03      2 squares
CO01     (1360, 660)  CO01      2 squares
CO02     (1460, 700)  CO02      2 squares
CO03     (1540, 740)  CO03      1 square
WNCN     (1800, 460)  WNCN      1 square
WNBR     (200,  560)  BRCK      1 square
SLST     (1120, 560)  SLST      1 square
SLFD     (1480, 620)  FLDN      1 square
```

### 8.3 Layout Adjustment Rules

These positions are a starting reference. During implementation, adjust for:

- **Label collision**: if two node labels overlap, move the label of the lower-priority node (lower voltage = lower priority)
- **Line routing**: lines should prefer horizontal/vertical/45° angles. Avoid acute angles.
- **Unit square clearance**: generation unit squares need 20px clearance above or below their host substation to avoid overlapping feeder lines
- **Cascade readability**: cascade stations must have enough horizontal space that their individual labels are legible — minimum 80px centre-to-centre

---

## 9. Rendering Layer Stack

Layers are drawn in this order every frame. Each layer can be a separate pygame Surface or a draw pass on the main surface.

```
Layer 0  BACKGROUND
         Canvas fill COL_CANVAS_BG
         Faint grid lines (optional): 1px, (20,28,36), 120px spacing
         Gives depth without competing with electrical elements

Layer 1  60KV LOAD LINES
         Dotted lines from 220kV/400kV buses to load substation nodes
         Drawn first (lowest priority at crossings)

Layer 2  150KV LINES
         Single 2px amber lines
         + flow animation markers

Layer 3  220KV LINES
         Single 3px green lines
         + flow animation markers

Layer 4  400KV LINES
         Double line (two 2px lines, 4px gap)
         + flow animation markers on both parallel lines

Layer 5  HYDRAULIC CONNECTORS
         Dashed cyan lines between pumped storage upper/lower
         Dashed lines between cascade stations
         No flow animation (not electrical)

Layer 6  SUBSTATION SYMBOLS
         Draw all △-in-square symbols at their positions
         Order: 60kV → 150kV → 220kV → 400kV (higher voltage on top)

Layer 7  GENERATION UNIT SQUARES
         Draw all unit squares at their computed positions
         Collector lines connecting multi-unit stations
         Feeder lines from collector to substation

Layer 8  DEMAND ARROWS
         Small hanging demand arrows on transmission buses
         MW labels below each arrow

Layer 9  INTERCONNECTOR MARKERS
         Chevron terminations at canvas edges
         Flow labels

Layer 10 STATE OVERLAYS
         Voltage warning halos on substations (semi-transparent circles)
         Overload flash highlights on lines

Layer 11 SELECTION HIGHLIGHT
         Bright white outline around selected element
         Detail panel trigger

Layer 12 NODE LABELS
         4-letter codes below/above each node
         Live data values (voltage pu, MW output, demand MW)

Layer 13 ALARM INDICATORS
         Blinking overlays on alarmed elements
         Priority: fault > overload > warning

Layer 14 INSTRUMENT STRIP
         Drawn last — always on top of canvas
         Frequency panel, balance panel, unit list, alarm feed
```

---

## 10. Instrument Strip Panels

### 10.1 Frequency Panel (leftmost, 280px wide)

```
┌──────────────────────────────┐
│ SYSTEM FREQUENCY             │  ← 13px sans, COL_PANEL_BORDER green
│                              │
│      50.02  Hz               │  ← 28px mono bold, colour = state
│                              │
│  ┤▓▓▓▓▓▓▓▓▓░░░░░░░░░├        │  ← analog bar, 260px wide
│  49.0              51.0      │  ← range labels, 10px
│                              │
│  Δ  +0.02 Hz   ↑ rising      │  ← deviation + trend, 11px
└──────────────────────────────┘
```

Frequency display colour:
- 49.8–50.2 Hz: `COL_220KV` green
- 49.5–49.8 / 50.2–50.5: `COL_150KV` yellow
- < 49.5 / > 50.5: `COL_LOAD_CRIT` red

Analog bar: green zone 49.8–50.2, yellow shoulders, red at extremes. Current value shown as bright marker on bar.

### 10.2 Generation/Load Balance Panel (280px wide)

```
┌──────────────────────────────┐
│ POWER BALANCE                │
│                              │
│  GEN    7,842 MW    ▲        │
│  LOAD   7,801 MW             │
│  ─────────────────           │
│  BAL      +41 MW   ●         │  ← green if |BAL| < 100MW
│                              │
│  SPIN RES  620 MW            │  ← spinning reserve available
│  INERTIA   4.8 s             │  ← system H constant
└──────────────────────────────┘
```

Balance colour: green if |imbalance| < 100MW, yellow < 300MW, red > 300MW.

### 10.3 Unit Dispatch Panel (640px wide)

Scrollable list of all generation units with current state and output:

```
┌──────────────────────────────────────────────────────────────────┐
│ UNIT DISPATCH                                            ↑ ↓     │
│ LABEL  TYPE    STATE    OUTPUT   RATED   LOADING  RAMP          │
│ ─────────────────────────────────────────────────────────────── │
│ CA01   COAL    ONLINE    285MW   300MW    95%     ████████████  │
│ CA02   COAL    ONLINE    285MW   300MW    95%     ████████████  │
│ CA03   COAL    OFFLINE     0MW   300MW     0%                   │
│ NU01   NUC     ONLINE    690MW   700MW    99%     ████████████  │
│ HA01   HYDRO   GEN       240MW   250MW    96%     ↑ ↑           │
│ HA02   HYDRO   PUMP     -250MW   250MW   100%     ↓ ↓           │
│ ...                                                              │
└──────────────────────────────────────────────────────────────────┘
```

Row colours: online=normal, offline=dim, fault=red, starting=yellow blink.

### 10.4 Alarm Feed Panel (720px wide)

Scrolling list, newest alarm at top, maximum 8 visible rows:

```
┌────────────────────────────────────────────────────────────────────────┐
│ ALARMS  [CRIT: 0]  [WARN: 2]  [INFO: 3]               CLR  ACK  ALL  │
│ ─────────────────────────────────────────────────────────────────────  │
│ [14:32] WARN  Line L03 loading 88% — approaching limit                │
│ [14:28] WARN  Voltage LD02 0.91pu — below lower limit                 │
│ [14:15] INFO  Unit CA03 synchronized — available for dispatch          │
│ [14:01] INFO  Spain North import +412MW                               │
│ ...                                                                    │
└────────────────────────────────────────────────────────────────────────┘
```

Row colours: CRIT=red, WARN=yellow, INFO=cyan. Unacknowledged alarms blink until ACK'd.

---

## 11. Interaction Model

### 11.1 Selectable Elements

Every node and line on the canvas is selectable by left-click. Selection highlights the element with a 2px white outline and opens a context panel overlay on the canvas (not replacing the instrument strip).

**Node context panel** (appears near selected node, 200×160px):

```
┌─────────────────────┐
│ SCEN  400kV  HUB    │
│ ─────────────────── │
│ Voltage:  1.024 pu  │
│ Angle:    +2.3°     │
│ P inject: +840 MW   │
│ Q inject: +120 MVAr │
│ Lines:    4 in svc  │
│ Load:     LD01 1800 │
└─────────────────────┘
```

**Line context panel**:

```
┌─────────────────────┐
│ L02  SCEN→SMID 400kV│
│ ─────────────────── │
│ Flow:   +842 MW →   │
│ Rating:  1400 MW    │
│ Loading:  60%       │
│ Status:  IN SERVICE │
│ Overload tmr: 0s    │
└─────────────────────┘
```

**Generation unit context panel**:

```
┌─────────────────────┐
│ HA01  HYDRO  UPPER  │
│ ─────────────────── │
│ Mode:   GENERATING  │
│ Output:  +240 MW    │
│ Rated:    250 MW    │
│ Ramp:   100%/min    │
│ Reservoir: 68%      │
│ Q output: +45 MVAr  │
└─────────────────────┘
```

### 11.2 Right-Click Context Menu

Right-click on a generation unit opens a dispatch menu:

```
  ► Set output target...
  ► Switch to pump mode  (hydro only)
  ► Start unit           (if offline)
  ► Shutdown unit        (if online)
  ─────────────────────
  ► Unit details...
```

Right-click on a line:

```
  ► Open line (trip manually)
  ► Close line (re-energise)
  ─────────────────────
  ► Line details...
```

### 11.3 Keyboard Shortcuts

```
SPACE       Pause / resume simulation
+  /  -     Simulation speed up / down
F           Jump to frequency panel
A           Jump to alarm panel (acknowledge top alarm)
ESC         Close context panel / deselect
1–5         Switch game level view (unlocked levels only)
```

---

## 12. Animation and Timing

### 12.1 Simulation vs Display Tick

The simulation and display run on separate timers:

```
Simulation tick:   every 100ms real time (= configurable simulated time step)
Display refresh:   60 fps (16.7ms) — always smooth regardless of sim speed
```

The display interpolates smoothly between simulation states. Flow animation, blinking, and panel updates run at display rate. Simulation state changes (line trips, unit state changes) are applied at simulation tick boundaries.

### 12.2 Blink Timing

All blink effects use a shared global blink clock to ensure all blinking elements are in phase:

```python
blink_slow = (pygame.time.get_ticks() // 1000) % 2 == 0   # 1Hz, 50% duty
blink_fast = (pygame.time.get_ticks() // 250) % 2 == 0    # 2Hz, 50% duty
```

Elements in alarm use `blink_fast`. Starting units use `blink_slow`. All elements of the same blink class flash together — avoids the visual noise of independently phased blinkers.

### 12.3 State Transition Animations

When a line trips:
1. Line colour transitions to grey over 200ms
2. Flow markers fade out over 200ms
3. Any loading colour on adjacent (now more loaded) lines transitions over 300ms
4. Alarm entry appears in alarm feed immediately

When a unit starts:
1. Unit square border begins yellow slow-blink immediately
2. A progress arc (thin arc around square, filling clockwise) shows startup progress
3. On synchronisation: border snaps to white, arc disappears, output bar appears from zero

---

## 13. Game Level Display Progression

The display adapts to what the player is managing at each game level. Autopilot elements are shown but visually subdued — the player can see the information but cannot interact with it.

| Level | Grid Nodes Active | New Display Elements Unlocked |
|-------|-----------------|-------------------------------|
| 1 | 12 nodes (south sub-grid) | MW flows, frequency panel, unit dispatch |
| 2 | 20 nodes (+ centre) | Unit commitment controls, spinning reserve indicator |
| 3 | 32 nodes (full grid) | Voltage overlays, VSI halos, reactive dispatch |
| 4 | 32 nodes + events | Island detection, blackout zones, restoration mode |
| 5 | 32 nodes + market | Day-ahead schedule display, bid/offer panel |

At Level 1, the nodes not yet in play are shown as dim outlines on the canvas — the player can see the full grid shape is there, but cannot interact with it. This creates anticipation and communicates that the world extends beyond the current challenge.

---

## 14. Implementation Build Order

Build and validate in this sequence. Each step produces something visually testable before the next begins.

```
Step 1  Static topology renderer
        Draw all nodes at fixed positions, placeholder colours
        Draw all lines with correct voltage rendering (double/single/dotted)
        No simulation, no animation — just prove the layout works

Step 2  Label system
        4-letter codes at correct positions
        Verify no label collisions at native resolution

Step 3  Instrument strip
        Static panels with hardcoded test values
        Verify layout, fonts, colours before connecting live data

Step 4  Flow animation
        Moving markers on lines with test speeds
        Tune marker size, speed, density for readability

Step 5  Loading state colours
        Feed fake loading percentages, verify colour transitions
        Test blink timing on overloaded lines

Step 6  Node state display
        Unit square states (online/offline/fault/starting)
        Output bars with fake values
        Pumped storage mode arrows

Step 7  Voltage overlays
        VSI halos on substation symbols
        Voltage pu labels

Step 8  Selection and context panels
        Click detection for all elements
        Context panel rendering and positioning

Step 9  Simulation hookup
        Connect real simulation state to display state
        Verify all display elements update correctly from sim

Step 10 Alarm system
        Alarm generation from simulation events
        Alarm feed panel with acknowledge/clear

Step 11 Animation polish
        Line trip transition
        Unit startup arc
        Blink phase synchronisation
```

---

*Document version 1.0 — covers grid topology, display specification, and visual language for all game levels. Cross-reference GRID_SIMULATION_MECHANICS.md for physics engine detail. Update node positions in Section 8.2 after Step 1 layout validation.*
