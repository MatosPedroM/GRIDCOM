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

A **plain square** — no inscribed triangle.

```
┌───────┐
│       │   12×12 px at native resolution
└───────┘
```

- Square border: 2px, colour = voltage level base colour
- Interior: filled with voltage level base colour at 20% brightness (dark tint)
- No triangle or other interior symbol

State modifiers on the border:

| State | Border | Effect |
|-------|--------|--------|
| Normal | 2px voltage colour | None |
| Voltage warning (VSI 0.90–0.95) | 2px yellow | None |
| Voltage critical (VSI 0.85–0.90) | 2px orange | None |
| Voltage collapse risk (<0.85) | 2px red | Blink 1Hz |
| Out of service | 2px dark grey | Fill black |

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

### 3.3 Generation Unit Circle

A **circle**, 12px diameter. This is the most repeated element on the canvas.

```
   ___
  /   \
 |  ░  |   Arc fill shows output level — filled clockwise from bottom
  \___/
```

**Border colour**: unit type colour (see palette above), 2px stroke
**Interior**: dark fill (near-black), with a clockwise arc fill from the bottom showing output level

**Arc fill**: drawn inside the circle from the bottom, sweeping clockwise proportional to `current_MW / rated_MW`. Full arc = full output. Empty arc = zero output. Arc colour = unit type colour at 80% brightness.

**Border state modifiers**:

| Unit State | Border Colour | Effect |
|------------|---------------|--------|
| Online, dispatched | unit type colour | None |
| Online, zero output | `#666666` dim grey | None |
| Starting up | `#FFFF00` yellow | Blink slow (0.5Hz) |
| Shutdown sequence | `#888888` grey | Blink slow |
| Offline / cold | `#333333` near-black | Interior darkened |
| Fault / tripped | `#FF0000` red | Blink fast (2Hz) |

**Multi-unit stations**: circles are drawn side by side with 2px gap between them, connected by a single horizontal collector line at their base before the feeder drop to the substation.

```
  (●)(●)(●)     ← 3 unit circles, 2px gap
   └──┬──┘      ← collector line
      │          ← feeder to substation bus
```

### 3.4 Pumped Storage Mode Indicator

Large hydro upper reservoir units have an additional mode arrow drawn in the centre of the unit circle, overlaid on the arc fill:

| Mode | Arrow | Border Colour |
|------|-------|-------------|
| Generating | ↑ (upward, 6px) | `COL_HYDRO` cyan |
| Pumping | ↓ (downward, 6px) | `COL_HYDRO_PUMP` dark blue |
| Idle | None | Darkened cyan |

The arrow is white, 1px stroke, centred in the circle.

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

The layout goal is **zero line crossings**. Node positions are chosen specifically to achieve a crossing-free topology. If a crossing appears during layout, it is resolved by adjusting node positions — not by accepting the crossing.

Where crossings cannot be avoided during early layout iterations, the temporary convention is:
- **No hop symbols** — crossings are drawn as simple overlapping lines
- **Connection dot** (4px filled circle, white) marks every actual junction
- Players learn: dot = connected, crossing without dot = not connected

This convention exists as a fallback only. The target is a fully crossing-free schematic.

Higher voltage lines are drawn on top of lower voltage lines at any temporary crossings (draw order: 60kV first, then 150kV, 220kV, 400kV last).

---

## 5. Node Labelling

### 5.1 Label Convention

Every node on the canvas has a **4-character uppercase label**. Labels are unique across the entire grid. The convention encodes asset type in the prefix:

| Prefix | Asset Type | Example |
|--------|-----------|---------|
| `S` + 3 chars | Transmission substation | `SNOR`, `SCEN`, `SSUL` |
| `CA`, `CB`, `CC` + 2 digits | Coal plant (A/B/C) | `CA01`, `CB01` |
| `GA`, `GB` + 2 digits | CCGT / gas plant | `GA01`, `GB01` |
| `NU` + 2 digits | Nuclear | `NU01` |
| `HA`, `HB`, `HC` | Large hydro upper | `HA01`, `HB01` |
| `DA`, `DB`, `DC` | Large hydro lower (downstream) | `DA01`, `DB01` |
| `RA`, `RB`, `RC` + digit | Run-of-river cascade | `RA01`–`RA04` |
| `WN` + 2 digits | Wind farm | `WN01`, `WN02` |
| `SL` + 2 digits | Solar farm | `SL01`, `SL02` |
| `LD` + 2 digits | Load substation (60kV) | `LD01`–`LD06` |
| `SP` + suffix | Spain interconnector | `SPAN`, `SPAS` |

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
Target installed capacity: **~9,600 MW** (20% reserve margin)
System base: **1,000 MVA**

```
ASSET         LABEL  CONFIG      MW     VOLTAGE  TYPE
──────────────────────────────────────────────────────────────────
COAL
  Coal A      CA     3 × 300MW   900    400kV    Thermal baseload
  Coal B      CB     3 × 300MW   900    400kV    Thermal baseload

CCGT / GAS
  CCGT A      GA     2 × 400MW   800    220kV    Mid-merit / peaker
  CCGT B      GB     2 × 400MW   800    220kV    Mid-merit / peaker

NUCLEAR
  Nuclear     NU     2 × 700MW  1400    400kV    Baseload

LARGE HYDRO (pumped storage complexes)
  Hydro A upper  HA  2 × 250MW   500    400kV    Pumped storage
  Hydro A lower  DA  2 ×  80MW   160    220kV    Downstream RoR
  Hydro B upper  HB  2 × 250MW   500    400kV    Pumped storage
  Hydro B lower  DB  2 ×  80MW   160    220kV    Downstream RoR
  Hydro C upper  HC  2 × 200MW   400    400kV    Pumped storage
  Hydro C lower  DC  2 ×  65MW   130    220kV    Downstream RoR

RUN-OF-RIVER CASCADES
  Cascade A   RA  4 stations × 60MW   240    220kV    RoR sequential
  Cascade B   RB  3 stations × 55MW   165    150kV    RoR sequential
  Cascade C   RC  3 stations × 45MW   135    150kV    RoR sequential

RENEWABLES
  Wind A      WN01   aggregated  500    220kV    Large wind farm
  Wind B      WN02   aggregated  300    150kV    Medium wind farm
  Solar A     SL01   aggregated  600    220kV    Large solar farm
  Solar B     SL02   aggregated  400    150kV    Medium solar farm

INTERCONNECTORS
  Spain North  SPAN  ±800MW     400kV    External reference
  Spain South  SPAS  ±600MW     400kV    External reference

TOTAL FIRM CAPACITY (excl. wind, solar, interconnectors): 7,190 MW
TOTAL INSTALLED (all sources):                            9,990 MW
PEAK DEMAND:                                              8,000 MW
```

### 6.2 Pumped Storage Structure

Each large hydro complex consists of two electrically independent plants sharing a hydraulic connection:

**Upper plant** (reversible pump-turbines):
- Connects to grid at 400kV
- Can generate (water releases through turbines) or pump (motor mode, pushes water uphill)
- In pump mode: appears as a **load** on the network (PQ bus, negative injection)
- In generate mode: appears as a **generator** (PV bus, positive injection)

**Lower plant** (conventional turbines, smaller):
- Connects to grid at 220kV
- Generate or idle only — cannot pump
- Output depends on water released from upper reservoir plus natural inflow

**Hydraulic connection** (penstock):
- Not an electrical connection
- Shown as dashed cyan line between upper and lower plant nodes
- Carries no electrical flow — display only

**Operational modes and net grid impact:**

| Mode | Upper Plant | Lower Plant | Net MW |
|------|------------|------------|--------|
| Full generate | +500MW gen | +160MW gen | +660MW |
| Partial generate | +Xmw gen | +160MW gen | +(X+160)MW |
| Natural flow | idle | +160MW gen | +160MW |
| Pump + lower gen | -500MW load | +160MW gen | -340MW |
| Full pump | -500MW load | idle | -500MW |

The pump mode creates an interesting schematic situation: the upper plant unit squares display in pumping-mode dark blue with downward arrow, while the substation feeding it shows increased load on its incoming lines.

### 6.3 Run-of-River Cascade Structure

Each cascade is a sequence of stations on the same notional river. Water flows from station 1 → 2 → 3 (→ 4 for Cascade A). Each station is electrically independent — each has its own feeder to the transmission grid.

On the schematic, cascade stations are placed in sequence with short hydraulic connectors (dashed lines) between them, distinct from electrical lines. The sequence reads left-to-right or top-to-bottom depending on available canvas space.

```
RA01──┊──RA02──┊──RA03──┊──RA04    Cascade A (220kV, 4 stations)
       hydraulic connectors (┊)
       electrical feeders go independently to nearest 220kV bus
```

Output of downstream stations depends on upstream release rates. In the simulation this is a simplified dependency — upstream station output increases downstream station's available flow by a time-delayed factor.

---

## 7. Network Topology

### 7.1 Node List (32 nodes)

```
ID    LABEL  VOLTAGE  TYPE                    CONNECTS TO
────────────────────────────────────────────────────────────────────
 1    SNOR   400kV    Transmission substation  Coal A, nuclear, 400kV backbone
 2    SCEN   400kV    Transmission substation  400kV backbone, Hydro A upper
 3    SEST   400kV    Transmission substation  400kV backbone, Spain North
 4    SSUL   400kV    Transmission substation  Coal B, 400kV backbone
 5    SWST   400kV    Transmission substation  Hydro B upper, 400kV backbone
 6    SMID   400kV    Transmission substation  Nuclear, 400kV backbone hub
 7    SA01   220kV    Transmission substation  CCGT A, 220kV network
 8    SA02   220kV    Transmission substation  CCGT B, 220kV network
 9    SA03   220kV    Transmission substation  Cascade A, Hydro A lower
10    SA04   220kV    Transmission substation  Wind A, Solar A
11    SA05   220kV    Transmission substation  Hydro B lower, Hydro C lower
12    SA06   220kV    Transmission substation  Hydro C upper feed, Spain South
13    SB01   150kV    Transmission substation  Cascade B, Wind B
14    SB02   150kV    Transmission substation  Cascade C, Solar B
15    SB03   150kV    Transmission substation  Regional 150kV link
16    CA     400kV    Coal A (3×300MW)         SNOR
17    CB     400kV    Coal B (3×300MW)         SSUL
18    GA     220kV    CCGT A (2×400MW)         SA01
19    GB     220kV    CCGT B (2×400MW)         SA02
20    NU     400kV    Nuclear (2×700MW)        SMID
21    HA     400kV    Hydro A upper (2×250MW)  SCEN
22    DA     220kV    Hydro A lower (2×80MW)   SA03
23    HB     400kV    Hydro B upper (2×250MW)  SWST
24    DB     220kV    Hydro B lower (2×80MW)   SA05
25    HC     400kV    Hydro C upper (2×200MW)  SA06 (via 400/220 sub)
26    DC     220kV    Hydro C lower (2×65MW)   SA05
27    WN01   220kV    Wind A (500MW)           SA04
28    WN02   150kV    Wind B (300MW)           SB01
29    SL01   220kV    Solar A (600MW)          SA04
30    SL02   150kV    Solar B (400MW)          SB02
31    SPAN   400kV    Spain North (±800MW)     SEST
32    SPAS   400kV    Spain South (±600MW)     SA06
```

Load substations (60kV) — 6 nodes, fed from various 220kV and 400kV buses:

```
ID    LABEL  VOLTAGE  PEAK LOAD   FED FROM
─────────────────────────────────────────────
33    LD01   60kV     1,800MW     SCEN
34    LD02   60kV     1,600MW     SMID
35    LD03   60kV     1,200MW     SA01
36    LD04   60kV     1,000MW     SA02
37    LD05   60kV       800MW     SSUL
38    LD06   60kV       600MW     SA04
```

Total load substation peak: 7,000MW (remaining 1,000MW spread as hanging demand arrows on various 220kV buses).

### 7.2 Transmission Line List

**400kV backbone lines** (double-line rendering, cyan):

```
LINE   FROM   TO     RATING   REACTANCE(pu)   LENGTH NOTES
L01    SNOR   SCEN   1200MW   0.04            North-centre backbone
L02    SCEN   SMID   1400MW   0.03            Central hub link
L03    SMID   SSUL   1200MW   0.05            Centre-south backbone
L04    SNOR   SEST   1000MW   0.06            North-east link
L05    SEST   SMID   1200MW   0.04            East backbone
L06    SMID   SWST   1000MW   0.05            West hub link
L07    SWST   SSUL   1000MW   0.06            South-west link
L08    SCEN   SWST    800MW   0.07            Cross link (N-1 support)
```

**220kV lines** (single-line, 3px, green):

```
LINE   FROM   TO     RATING   REACTANCE(pu)
L09    SCEN   SA01   600MW    0.08
L10    SMID   SA02   600MW    0.08
L11    SA01   SA02   400MW    0.10
L12    SA02   SA03   400MW    0.09
L13    SA03   SA04   400MW    0.11
L14    SA04   SA05   400MW    0.10
L15    SA05   SA06   400MW    0.09
L16    SA06   SSUL   500MW    0.07
L17    SNOR   SA01   500MW    0.08
L18    SSUL   SA05   400MW    0.09
```

**150kV lines** (single-line, 2px, amber):

```
LINE   FROM   TO     RATING   REACTANCE(pu)
L19    SA03   SB01   250MW    0.12
L20    SA04   SB02   250MW    0.13
L21    SB01   SB02   200MW    0.15
L22    SB02   SB03   200MW    0.14
L23    SA05   SB03   200MW    0.13
```

**60kV load feeds** (dotted, 1px, dark amber):

```
LINE   FROM   TO     RATING   NOTES
L24    SCEN   LD01   600MW    Major load feed (double circuit implied)
L25    SMID   LD02   600MW    Major load feed
L26    SA01   LD03   400MW    
L27    SA02   LD04   400MW    
L28    SSUL   LD05   300MW    
L29    SA04   LD06   250MW    
```

### 7.3 Slack Bus

**SMID** (central 400kV substation) is the slack bus — it absorbs the system imbalance and provides the voltage angle reference (θ = 0). In simulation terms it represents the system's balancing point. In game terms, it is the electrical centre of gravity of the network.

Spain interconnectors (SPAN, SPAS) are external reference buses — they have fixed voltage and absorb/inject power based on the interconnector schedule set by the player.

---

## 8. Canvas Layout

### 8.1 Layout Doctrine

Node positions follow four rules, in priority order. These rules are **authoritative** — the coordinates in Section 8.2 are starting references only, and must be adjusted until all four rules are satisfied.

**Rule 1 — Vertical axis encodes voltage hierarchy.**
Higher voltage assets sit higher on the canvas. Lower voltage assets descend toward the bottom. The general flow reads top-to-bottom: generation and 400kV backbone at the top, 220kV in the middle tier, 150kV below that, 60kV load substations at the bottom. This maps the electrical hierarchy directly onto the visual hierarchy.

**Rule 2 — Horizontal axis encodes lateral spread.**
When multiple assets exist at the same voltage tier, they spread left and right from a central spine. The centre of the canvas is the primary trunk. Assets branch outward as the grid fans out. Asymmetric placement is acceptable — assets do not need to be mirror-symmetric. The constraint is direction (centre-outward), not balance.

**Rule 3 — No diagonal lines.**
All transmission line segments are strictly horizontal or vertical. A connection that must move in both axes uses a staircase route: one horizontal segment followed by one vertical segment (or vice versa), with a single right-angle bend. Multiple bends are permitted only when a single bend cannot avoid a crossing or collision. Acute angles are never acceptable.

**Rule 4 — No line crossings.**
Node positions are chosen to produce a crossing-free topology. If two lines would cross, the lower-voltage node is repositioned to eliminate the crossing. This rule is the primary driver of layout decisions and takes precedence over the starting coordinates in Section 8.2.

**Minimum inter-node distance**: 80px centre-to-centre.
**Maximum local density**: 4 nodes within any 200×200px area.

### 8.2 Node Positions (native 1920×844)

Positions are (X, Y) in pixels from top-left corner of the grid canvas.

**400kV backbone substations** (drawn as plain cyan squares):

```
SNOR   (240,  180)   North
SCEN   (720,  240)   Centre-north
SMID   (960,  420)   Central hub (slack bus)
SEST   (480,  320)   East
SWST   (580,  560)   West
SSUL   (1200, 620)   South
```

**220kV substations** (drawn as plain green squares):

```
SA01   (380,  480)   
SA02   (720,  580)   
SA03   (480,  680)   
SA04   (1100, 380)   
SA05   (900,  680)   
SA06   (1380, 520)   
```

**150kV substations** (drawn as plain amber squares):

```
SB01   (340,  740)   
SB02   (1020, 760)   
SB03   (780,  760)   
```

**Generation nodes** (drawn as circles, adjacent to host substation):

```
CA     (180,  130)   above SNOR — 3 squares horizontal
CB     (1140, 560)   above SSUL — 3 squares horizontal
GA     (300,  520)   left of SA01 — 2 squares
GB     (660,  630)   left of SA02 — 2 squares
NU     (960,  320)   above SMID — 2 squares
HA     (680,  180)   above SCEN, left — 2 squares
DA     (440,  700)   near SA03 — 2 squares
HB     (520,  500)   near SWST — 2 squares
DB     (860,  700)   near SA05 — 2 squares
HC     (1360, 460)   near SA06 — 2 squares
DC     (940,  720)   near SA05 — 2 squares
```

**Renewable nodes** (drawn as circles at their bus):

```
WN01   (1100, 320)   above SA04 — wind symbol
WN02   (280,  760)   at SB01 — wind symbol
SL01   (1160, 440)   right of SA04 — solar symbol
SL02   (1020, 800)   at SB02 — solar symbol
```

**Run-of-river cascades** (sequential, 80px spacing):

```
Cascade A (220kV, 4 stations):
  RA01  (380, 760)
  RA02  (460, 760)
  RA03  (540, 760)
  RA04  (620, 760)
  hydraulic connectors between sequential stations

Cascade B (150kV, 3 stations):
  RB01  (140, 680)
  RB02  (220, 680)
  RB03  (300, 680)

Cascade C (150kV, 3 stations):
  RC01  (1200, 760)
  RC02  (1280, 760)
  RC03  (1360, 760)
```

**Load substations** (drawn as amber ▽-in-square):

```
LD01   (760,  300)   near SCEN
LD02   (1020, 480)   near SMID
LD03   (340,  560)   near SA01
LD04   (740,  640)   near SA02
LD05   (1260, 680)   near SSUL
LD06   (1140, 460)   near SA04
```

**Interconnectors** (at canvas edges):

```
SPAN   (1780, 180)   right edge, north — chevron pointing right
SPAS   (1780, 620)   right edge, south — chevron pointing right
```

### 8.3 Layout Adjustment Rules

These positions are a starting reference. During implementation, apply the doctrine from Section 8.1 to adjust them:

- **No crossings** — if any two lines would cross, reposition the lower-voltage node to eliminate the crossing. This takes priority over all other placement preferences.
- **No diagonals** — all line segments must be horizontal or vertical. If a connection requires movement in both axes, use a staircase route (one bend only where possible).
- **Voltage hierarchy** — if a node sits at the wrong vertical tier for its voltage level, move it. Correct hierarchy is more important than proximity to the starting coordinate.
- **Label collision** — if two node labels overlap, move the label of the lower-priority node (lower voltage = lower priority). If the label cannot move without ambiguity, move the node itself.
- **Generation circle clearance** — generation circles need 20px clearance above or below their host substation to avoid overlapping feeder lines.
- **Cascade readability** — cascade stations must have enough horizontal space that their individual labels are legible — minimum 80px centre-to-centre.

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
        Unit circle states (online/offline/fault/starting)
        Arc fill with fake values
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

*Document version 1.1 — revised symbol vocabulary (Section 3.1: plain square substations; Section 3.3: circle generation units) and layout doctrine (Section 8.1: voltage hierarchy top-to-bottom, centre-to-lateral spread, no diagonals, no crossings). Cross-reference GRID_SIMULATION_MECHANICS.md for physics engine detail. Update node positions in Section 8.2 after Step 1 layout validation.*
