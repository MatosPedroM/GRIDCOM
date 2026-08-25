# CLAUDE.md — GRIDCOM Project Intelligence
### Read this file completely before writing any code or making any changes.

---

## What This Project Is

GRIDCOM : Grid Control Terminal is a 1990s-aesthetic power grid management game built in Python 3.12.7 with pygame-ce and numpy. The player is a grid dispatcher at the National Energy Control Centre (NECC) in Ashford, managing a fictional transmission network across a 10-shift campaign.

This is a **solo development project**. Every architectural decision has been made deliberately and is documented. Do not introduce new patterns, libraries, or structures without explicit instruction.

---

## Technology Stack

```
Language:     Python 3.12.7
Game engine:  pygame-ce >= 2.4.0
Math:         numpy >= 1.24.0
Platform:     Windows (primary development and target)
Distribution: PyInstaller (single-folder, Steam)
VCS:          Git with remote (GitHub/GitLab)
```

**No other dependencies.** Do not import or suggest scipy, pandas, or any other library. If a mathematical operation seems to require scipy, implement it with numpy directly.

---

## Project Structure

```
gridcom/
├── CLAUDE.md                    ← this file
├── CODING_STANDARDS.md          ← Python conventions — read before writing code
├── DOMAIN_GLOSSARY.md           ← power system terms — read before simulation work
├── SIMULATION_API.md            ← simulation↔display contract — read before Stage 5+
├── STAGE_STATUS.md              ← current development state — read every session
├── .gitignore
├── .gitattributes
├── .claudeignore
├── requirements.txt
├── gridcom.spec                 ← PyInstaller spec
└── src/
    ├── main.py                  ← entry point, pygame init, main loop
    ├── simulation/
    │   ├── constants.py         ← ALL constants live here — nowhere else
    │   ├── grid.py              ← Grid object, topology loader
    │   ├── loadflow.py          ← DC load flow solver (numpy only)
    │   ├── voltage.py           ← decoupled voltage solver
    │   ├── frequency.py         ← swing equation
    │   ├── units.py             ← generation unit state machine
    │   ├── demand.py            ← demand model, forecast, noise
    │   ├── renewables.py        ← wind and solar models
    │   ├── cascade.py           ← cascade detection, island finding (BFS)
    │   ├── events.py            ← scripted event system
    │   └── simulation.py        ← master simulation loop
    ├── display/
    │   ├── renderer.py          ← main render loop, layer management
    │   ├── canvas.py            ← grid schematic drawing
    │   ├── symbols.py           ← all symbol drawing functions
    │   ├── animation.py         ← flow markers, blink system
    │   ├── panels.py            ← instrument strip panels
    │   ├── context.py           ← context panels, selection
    │   ├── palette.py           ← ALL colour constants live here — nowhere else
    │   └── debug.py             ← simulation debug + display debug overlays
    ├── gameplay/
    │   ├── campaign.py          ← shift structure, state machine, save/load
    │   ├── phase1.py            ← planning interface (Shifts 5-10)
    │   ├── phase2.py            ← real-time session management
    │   ├── debrief.py           ← post-shift scoring and display
    │   ├── scoring.py           ← performance tracking
    │   ├── autopilot.py         ← autopilot schedule generator (Shifts 1-4)
    │   └── shifts/
    │       ├── shift_01.py      ← shift definition, scripted events, win conditions
    │       └── shift_02.py ... shift_10.py
    ├── data/
    │   ├── topology.py          ← 32-node network (buses, lines)
    │   ├── fleet.py             ← 47 generation units
    │   └── profiles.py          ← demand profiles, shift specs
    ├── assets/
    │   ├── fonts/
    │   │   ├── JetBrainsMono-Regular.ttf
    │   │   ├── JetBrainsMono-Bold.ttf
    │   │   └── LiberationSans-Regular.ttf
    │   └── sounds/
    │       ├── alarm_critical.wav
    │       ├── alarm_warning.wav
    │       ├── alarm_ack.wav
    │       ├── unit_trip.wav
    │       └── ambient_room.wav
    └── utils/
        └── helpers.py           ← resource_path() and shared utilities
```

---

## Absolute Architecture Rules

These rules are non-negotiable. Violating them creates bugs that are hard to trace.

**Rule 1 — Constants only in constants.py**
Every numeric value, threshold, timing, or configuration parameter lives in `src/simulation/constants.py`. No hardcoded numbers anywhere else in the codebase. Import from constants: `from simulation.constants import F_NOMINAL, TRIP_DELAY_S`.

**Rule 2 — Colours only in palette.py**
Every RGB tuple lives in `src/display/palette.py`. No colour values appear anywhere else. Import: `from display.palette import COL_400KV, COL_ALARM_CRIT`.

**Rule 3 — Asset paths always via resource_path()**
Every font, sound, or asset file is loaded using `resource_path()` from `src/utils/helpers.py`. Never use hardcoded absolute paths or relative paths directly. This is required for PyInstaller builds to work.

```python
from utils.helpers import resource_path
font = pygame.freetype.Font(resource_path('assets/fonts/JetBrainsMono-Regular.ttf'), 11)
```

**Rule 4 — Native surface rendering**
All game rendering happens on a 1920×1080 native surface. This surface is scaled to the player's monitor resolution at the end of each frame. All coordinates are authored at 1920×1080. Never use display surface coordinates directly in game logic.

**Rule 5 — No external power system libraries**
The simulation uses only numpy for matrix operations. Do not suggest or use pandapower, pypower, or any other power system library.

**Rule 6 — Simulation physics never auto-corrected**
The simulation uses deliberate approximations (DC load flow, decoupled voltage, simplified cascade). Do not "improve" the physics toward more accurate real-world models. The approximations are intentional game design decisions documented in GRID_SIMULATION_MECHANICS.md.

**Rule 7 — Read STAGE_STATUS.md before every session**
The stage status file tells you what is built, what is not, and what is in progress. Never reference a module that is listed as "not yet built" in STAGE_STATUS.md.

---

## Naming Conventions

### Bus Labels (4 characters, uppercase)
```
MDBY    Midbury 400kV (slack bus)
CNTR    Centrefield 400kV
NRTH    Northgate 400kV
EAST    Eastmoor 400kV
WEST    Westham 400kV
STHW    Southwick 400kV
ASHF    Ashford 220kV
WRNT    Wrentham 220kV
RDST    Redstone 220kV
FAIR    Fairfield 220kV
COAL    Coalton 220kV
DUNM    Dunmore 220kV
BRCK    Brackley 150kV
STAN    Stanton 150kV
FLDN    Feldon 150kV
LD01-LD15   Load substations (150kV) — each has its own place name in the
            `name` field (see topology.py); LD01-LD06 are permanent, LD07-LD15
            are Shift-10-only (Stage 24/25/26 capacity expansion). LD07-LD15
            are consolidated substations, each merged from 2-3 of the original
            23 single-substation buses that shared an identical feed-source
            pair (LD16-LD29 labels were retired in the Stage 26 consolidation
            and are not currently in use)
AR01-AR04   River Arden cascade connection buses (220kV) — each has its own
            place name distinct from the AR0N station/unit code (e.g. bus
            AR01 is named 'Ardenbridge'; the River Arden Station 1 units are
            still labelled AR01-1, AR01-2)
BR01-BR03   River Brent cascade connection buses (150kV) — same pattern
CO01-CO03   River Coln cascade connection buses (150kV) — same pattern
INTC-N      Interconnection North
INTC-S      Interconnection South
```

### Unit Labels
```
Format:  STATION-N  where N is unit number (1-based)
Examples: RVSD-1, RVSD-2, RVSD-3   (Riverside Coal, 3 units)
          HART-1, HART-2             (Hartwell Nuclear, 2 units)
          KELM-1, KELM-2             (Kelmore Hydro upper, 2 units)
          KELD-1, KELD-2             (Kelmore Hydro lower downstream)
```

### Station Labels (generation nodes)
```
RVSD    Riverside Coal (3×300MW, 400kV) — COALCOM easter egg
THNF    Thornfield Coal (3×300MW, 400kV)
ASHG    Ashford CCGT (2×400MW, 220kV)
WRNG    Wrentham CCGT (2×400MW, 220kV)
HART    Hartwell Nuclear (2×700MW, 400kV)
BARR    Barrow Hydro upper (2×250MW, 400kV, pumped storage)
BARD    Barrow Hydro lower (2×80MW, 220kV, downstream)
KELM    Kelmore Hydro upper (2×250MW, 400kV, pumped storage)
KELD    Kelmore Hydro lower (2×80MW, 220kV, downstream)
DUNH    Dunmore Hydro upper (2×200MW, 400kV, pumped storage)
DUND    Dunmore Hydro lower (2×65MW, 220kV, downstream)
AR01-AR04   River Arden cascade (4 stations, 220kV)
BR01-BR03   River Brent cascade (3 stations, 150kV)
CO01-CO03   River Coln cascade (3 stations, 150kV)
WNCN    Cairn Wind (500MW, 220kV)
WNBR    Brackley Wind (300MW, 150kV)
SLST    Stanton Solar (600MW, 220kV)
SLFD    Feldon Solar (400MW, 150kV)
```

### Line Labels
```
Format:  L + number (L01, L02 ... L154 — not all numbers in range are in use)
L01-L50     Permanent topology (all shifts once active_from_shift is reached)
L91-L154    Shift-10-only additions (Stage 24/25/26 capacity expansion):
              second circuits, dual-feed links for LD07-LD15, and the
              River Brent/Coln loop closures. Several numbers in this range
              (e.g. L102-L129, L139-L152) were retired in the Stage 26
              consolidation and are not currently in use — labels are not
              recycled, so gaps in the sequence are expected and permanent.
```

### Python Naming
```
Classes:        PascalCase          (DCLoadFlow, UnitModel, GridSimulation)
Functions:      snake_case          (build_b_matrix, compute_line_flows)
Constants:      UPPER_SNAKE_CASE    (F_NOMINAL, TRIP_DELAY_S)
Variables:      snake_case          (bus_label, line_loading, theta_rad)
Private:        _leading_underscore (_build_adjacency, _apply_jitter)
Type aliases:   PascalCase          (BusLabel = str, LoadingPct = float)
```

---

## The Grid — Key Facts

**System scale:** 8,000 MW peak demand, 1,000 MVA base

**Voltage levels:**
- 400kV: backbone, nuclear, large coal, large hydro, interconnectors
- 220kV: CCGT, run-of-river hydro, large wind/solar, sub-transmission
- 150kV: smaller renewables, cascade hydro, regional links
- 60kV: load substations (consumption sinks only, no generation)

**Slack bus:** MDBY (Midbury 400kV) — voltage angle reference (θ = 0), absorbs imbalance

**Total nodes:** 40 transmission + 6 load substations = 46 nodes
**Total units:** 47 generation units across all stations
**Total lines:** 45 transmission lines

**Grid activation by shift:**
- Shifts 1-2:  9 buses,  8 lines, 11 units (south sub-grid)
- Shifts 3-4: 28 buses, 29 lines, 29 units (south + centre)
- Shifts 5-10: 40 buses, 45 lines, 47 units (full grid)

**Interconnectors:** INTC-N (±800MW) and INTC-S (±600MW) — external reference buses, not part of the internal network topology

---

## Simulation — Key Facts

**The simulation uses these deliberate approximations:**
- DC load flow (not AC) — gives MW flows and angles, no voltage magnitudes from this solver
- Decoupled voltage model (ΔV = B'⁻¹ × Q) — gives voltage magnitudes separately
- No AC losses — losses are a fixed 2-3% of generation added to load
- No reactive power coupling to MW flows (decoupled approximation)
- Nonlinear voltage collapse acceleration below VSI 0.85 pu (intentional game fudge)

**Do not attempt to make these more accurate. They are correct by design.**

**Simulation tick rate:** 10 ticks per real second
**Time compression:** fixed 24:1 for all shifts (1 sim hour = 2.5 real minutes)
**Performance target:** full tick < 5ms, load flow solve < 1ms

**Two simulation modes:**
- `run_realtime_mode()` — full physics with stochastic noise, used during Phase 2
- `run_forecast_mode()` — deterministic, no noise, no cascade, used for Phase 1 preview

---

## Display — Key Facts

**Native resolution:** 1920×1080 (all coordinates authored here)
**Aspect ratio:** 16:9 (auto-scaled to player's monitor at runtime)
**Target FPS:** 60

**Screen regions:**
- Grid canvas: 1920 × 844px (top 78% of screen)
- Instrument strip: 1920 × 236px (bottom 22%)

**Rendering:** All drawing uses pygame draw calls — no sprite sheets, no image files for UI elements. Symbols are drawn procedurally.

**Layer order (bottom to top):**
0. Canvas background
1. 60kV load lines
2. 150kV lines
3. 220kV lines
4. 400kV lines (drawn last = highest priority at crossings)
5. Hydraulic connectors (dashed, not electrical)
6. Substation symbols
7. Generation unit squares + collectors + feeders
8. Demand arrows
9. Interconnector markers
10. State overlays (voltage halos)
11. Selection highlight
12. Node labels + live data
13. Alarm indicators
14. Instrument strip panels (always on top)
15. Debug overlay (when DEBUG_DISPLAY = True)

---

## Input — Key Facts

**Both mouse and keyboard work for every player action.** No action is mouse-only. No action is keyboard-only.

**Keyboard shortcuts (Phase 2):**
```
P           Pause / resume
F12         Cycle run speed (0.25x -> 1x -> 3x -> 10x -> wrap)

W           Arm ACTIVE power (MW) adjust on the selected unit
Q           Arm REACTIVE power (AVR setpoint) adjust on the selected unit
Up/Down     Step the armed quantity        (Ctrl+Up/Down = coarse step)
Enter       Type an exact value for the selected unit / open context panel

Tab         Cycle element selection
Escape      Cancel input -> disarm adjust -> deselect -> confirm abandon shift
A           Acknowledge top alarm
Shift+A     Acknowledge all alarms
S / X       Start / stop selected unit, OR restore / shed 25% load at selected
            substation (S/X are dual-purpose: act on whichever is selected;
            S always increases, X always decreases, in both contexts)
T / C       Trip / close selected line
, / .       Adjust selected bus's manual SVC setpoint
L           Toggle voltage-tier colour view (lines/substations)
M           Return selected unit to AUTO dispatch mode (Phase 1 shifts only)
D           Toggle display debug overlay
Ctrl+A      Toggle AGC
Ctrl+Shift+E  Toggle layout editor mode
```

**Design notes on the Phase 2 bindings.** W/Q are deliberately adjacent on QWERTY and
match the standard P/Q (active/reactive) engineering pairing; arming one disarms the
other, so Up/Down are never ambiguous. Digit keys are reserved exclusively for typing
unit targets — speed is on F12 alone so nothing competes with numeric entry. Pause is
kept off the F12 cycle so the clock can always be stopped in one keystroke.

---

## Debug Modes

Two independent debug modes, both default False in constants.py:

**DEBUG_SIMULATION** — console output each simulation tick:
- Sim time, frequency, generation, load, imbalance, max line loading, min VSI
- Prints when scripted events fire, when lines trip, when units trip

**DEBUG_DISPLAY** — visual overlay on canvas:
- Faint coordinate grid (120px spacing)
- Mouse position (X, Y) in top-left corner
- Click anywhere → coordinates printed to console + displayed 3 seconds
- Frame time and FPS in top-right corner
- Current speed multiplier

Enable by setting `DEBUG_SIMULATION = True` or `DEBUG_DISPLAY = True` in `src/simulation/constants.py`.

---

## The Fictional World (Narrative Context)

```
Country:          Unnamed (never referred to by name in-game)
Capital:          Ashford
Control centre:   National Energy Control Centre (NECC), Ashford
Incumbent:        VPC (Valdoria Power Corporation)
Interconnectors:  Interconnection North (INTC-N), Interconnection South (INTC-S)
Year:             1994
Outgoing dispatcher: R. Ferris (Dispatcher Grade 2, 11 years)
Player character: Dispatcher Grade 2, ex-Riverside (12 years)
Game motto:       "Frequency nominal. For now."
```

**COALCOM easter egg:** RVSD-2 (Riverside Coal #2) is out of service in the Shift 1 handover notes due to planned relay maintenance. This references the player's power station from COALCOM : Power Station Terminal.

All names in this game are fictional. Riverside, Ashford, Kelmore, Hartwell — none of these reference real locations.

---

## What To Do At The Start of Every Session

1. Read `STAGE_STATUS.md` — understand current project state
2. Read the files you will be modifying — never work from memory
3. Confirm the session objective with the developer before writing code
4. After completing work, run the validation test for the current stage
5. Update `STAGE_STATUS.md` to reflect what was completed

## What To Never Do

- Hardcode numbers anywhere outside `constants.py`
- Hardcode colours anywhere outside `palette.py`
- Use absolute file paths (always use `resource_path()`)
- Import scipy or any library not in `requirements.txt`
- "Improve" simulation physics beyond what is specified
- Modify files not relevant to the current session objective
- Assume a module is implemented — check `STAGE_STATUS.md` first
- Skip the validation test at the end of a session
- When committing code, always use clean technical commit messages that describe what changed. Never mention Claude, Claude Code, AI, or AI-assisted development in commit messages, branch names, or any git metadata.

## Design Decisions Are Fluid

The following are subject to change based on playtesting and aesthetic
judgement. When the developer changes these, update constants.py or
palette.py accordingly — do not treat current values as locked:

- All colour values in palette.py
- All font sizes in constants.py  
- All panel dimensions and positions in constants.py
- All symbol sizes in constants.py
- Screen layout proportions (CANVAS_H, STRIP_H, etc.)

When asked to change any of these, make the change in the relevant
constants file and update any hardcoded references in code files.
Do NOT update GRID_TOPOLOGY_AND_DISPLAY.md or other design documents
for these minor adjustments — those documents describe design intent,
not pixel-perfect specifications.

---

## Reference Documents

All design decisions are documented. Read the relevant document before working on each area:

```
GRID_SIMULATION_MECHANICS.md    Physics engine — all simulation decisions
GRID_TOPOLOGY_AND_DISPLAY.md    Visual specification — all display decisions
GAMEPLAY_REFERENCE.md           Campaign structure — all gameplay decisions
GRIDCOM_INTRO_STORY.md          Narrative — world, characters, motto
GRIDCOM_ROADMAP_v2.md           Development stages and validation tests
CODING_STANDARDS.md             Python conventions for this project
DOMAIN_GLOSSARY.md              Power system terminology definitions
SIMULATION_API.md               Simulation↔display interface contract
STAGE_STATUS.md                 Current development state (updated each session)
```
