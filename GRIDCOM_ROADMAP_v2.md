# GRIDCOM : Grid Control Terminal
### Development Roadmap
### Version 1.1 — Critical Path First

---

## Guiding Principles

**Critical path first.** Every stage produces something that directly enables the next stage. Nothing is built that isn't needed for a functioning game. Polish, aesthetics, and non-critical features are explicitly deferred to the end.

**Validate before building on top.** Each stage ends with a defined validation test. If the validation fails, the stage is fixed before proceeding. Building Stage 4 on a broken Stage 3 compounds problems.

**Simulation before display.** The physics engine is built and validated in console before any rendering work begins. A beautiful display connected to broken simulation is still broken.

**Shift 1 is the proof of concept.** Everything in Stages 1-5 exists to produce a fully playable Shift 1. If Shift 1 feels right, the architecture is sound and the remaining campaign is additive. If Shift 1 feels wrong, the problem is caught early when it is cheapest to fix.

**Everything is rendered.** There is no text mode, no separate subsystem for the intro story screens. Every pixel — prose text, terminal boot sequence, grid canvas, instrument panels — is drawn by the pygame renderer using the same drawing pipeline. The intro story text happens to contain mostly text; it is still a rendered scene.

**Both input methods always work.** Every player action is accessible by both mouse and keyboard where possible. No action is mouse-only. No action is keyboard-only. This is authentic to 1990s EMS workstation software.

---

## Project Structure

All source code lives under `gridcom/src/`. Assets are co-located under `gridcom/src/assets/`. No source files exist outside `src/`.

```
gridcom/
├── src/
│   ├── main.py                      ← entry point, pygame init, main loop
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── constants.py             ← ALL game constants — primary reference
│   │   ├── grid.py                  ← Grid object, topology loader
│   │   ├── loadflow.py              ← DC load flow solver
│   │   ├── voltage.py               ← decoupled voltage solver
│   │   ├── frequency.py             ← swing equation, droop response
│   │   ├── units.py                 ← generation unit state machine
│   │   ├── demand.py                ← demand model, forecast, noise
│   │   ├── renewables.py            ← wind and solar models
│   │   ├── cascade.py               ← cascade detection, island finding
│   │   ├── events.py                ← scripted event system
│   │   └── simulation.py            ← master simulation loop
│   ├── display/
│   │   ├── __init__.py
│   │   ├── renderer.py              ← main render loop, layer management
│   │   ├── canvas.py                ← grid schematic drawing
│   │   ├── symbols.py               ← all symbol drawing functions
│   │   ├── animation.py             ← flow markers, blink system
│   │   ├── panels.py                ← instrument strip panels
│   │   ├── context.py               ← context panels, selection
│   │   ├── palette.py               ← all colour constants
│   │   └── debug.py                 ← simulation debug + display debug overlays
│   ├── gameplay/
│   │   ├── __init__.py
│   │   ├── campaign.py              ← shift structure, state machine, save/load
│   │   ├── phase1.py                ← planning interface
│   │   ├── phase2.py                ← real-time session management
│   │   ├── debrief.py               ← post-shift scoring and display
│   │   ├── scoring.py               ← performance tracking
│   │   ├── autopilot.py             ← autopilot schedule generator (Shifts 1-4)
│   │   └── shifts/
│   │       ├── shift_01.py          ← shift definition, events, win conditions
│   │       ├── shift_02.py
│   │       ├── shift_03.py
│   │       ├── shift_04.py
│   │       ├── shift_05.py
│   │       ├── shift_06.py
│   │       ├── shift_07.py
│   │       ├── shift_08.py
│   │       ├── shift_09.py
│   │       └── shift_10.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── topology.py              ← 32-node network definition
│   │   ├── fleet.py                 ← generation asset definitions
│   │   └── profiles.py              ← demand profiles, shift parameters
│   ├── assets/
│   │   ├── fonts/
│   │   │   ├── JetBrainsMono-Regular.ttf
│   │   │   ├── JetBrainsMono-Bold.ttf
│   │   │   └── LiberationSans-Regular.ttf
│   │   └── sounds/
│   │       ├── alarm_critical.wav
│   │       ├── alarm_warning.wav
│   │       ├── alarm_ack.wav
│   │       ├── unit_trip.wav
│   │       └── ambient_room.wav
│   └── utils/
│       ├── __init__.py
│       └── helpers.py               ← resource_path(), shared utilities
├── saves/                           ← campaign save files (gitignored)
├── tests/
│   └── test_simulation.py           ← simulation validation harness
├── gridcom.spec                     ← PyInstaller build specification
└── requirements.txt                 ← pygame-ce, numpy
```

`requirements.txt`:
```
pygame-ce>=2.4.0
numpy>=1.24.0
```

---

## Stage 0 — Project Foundation

**Objective:** Clean, consistent project structure with all shared infrastructure in place before any game-specific code is written.

### 0.1 Repository and Directory Structure

Create the complete directory tree above, including empty `__init__.py` files in every Python package. Empty directories with placeholder files are better than reorganising mid-development. Commit the empty structure to version control before writing a single line of game code.

### 0.2 Constants File

Write `src/simulation/constants.py` — the single authoritative source for every tunable value in the game. Nothing is hardcoded anywhere else. When a value needs changing, this is the only file that changes.

```python
# ─────────────────────────────────────────────
# DISPLAY
# ─────────────────────────────────────────────
NATIVE_W            = 1920
NATIVE_H            = 1080
ASPECT_RATIO        = 16 / 9
TARGET_FPS          = 60

# Screen region boundaries (native resolution)
CANVAS_H            = 844       # grid canvas height
STRIP_Y             = 844       # instrument strip top boundary
STRIP_H             = 236       # instrument strip height
PANEL_RIGHT_X       = 1536      # right panel column left edge
PANEL_RIGHT_W       = 384       # right panel column width

# ─────────────────────────────────────────────
# SIMULATION
# ─────────────────────────────────────────────
SIM_TICK_HZ         = 10        # simulation ticks per real second
S_BASE              = 1000.0    # system MVA base
F_NOMINAL           = 50.0      # nominal frequency Hz

# Frequency thresholds (Hz)
F_WARNING           = 49.8
F_ALERT             = 49.5
F_LOADSHED_1        = 49.2
F_LOADSHED_2        = 49.0
F_LOADSHED_3        = 48.5
F_BLACKOUT          = 47.5
F_HIGH_WARNING      = 50.2
F_HIGH_ALERT        = 50.5

# Load shedding steps (fraction of total load)
LOADSHED_STEP_1     = 0.05
LOADSHED_STEP_2     = 0.10
LOADSHED_STEP_3     = 0.15

# Simulation physics
DROOP_R             = 0.04      # governor droop setting
TRIP_DELAY_S        = 60.0      # seconds of overload before line trips
NOISE_SIGMA         = 0.02      # demand forecast error std dev
COLLAPSE_GAIN       = 0.5       # voltage collapse acceleration factor
COLLAPSE_THRESHOLD  = 0.85      # VSI below this → acceleration starts
COLLAPSE_FLOOR      = 0.70      # VSI below this → blackout triggered
YSHUNT_REG          = 1e-6      # B matrix regularisation term

# ─────────────────────────────────────────────
# TIME COMPRESSION
# ─────────────────────────────────────────────
TIME_COMPRESSION    = 24.0      # fixed 24:1 for all shifts
                                # 1 sim hour = 2.5 real minutes

# Speed multipliers (applied to TIME_COMPRESSION)
SPEED_PAUSE         = 0.0
SPEED_SLOW          = 0.25
SPEED_NORMAL        = 1.0
SPEED_FAST          = 3.0
SPEED_VERY_FAST     = 10.0

# Crisis auto-force threshold
CRISIS_LINE_LOADING = 95.0      # % — triggers auto speed-force
CRISIS_VSI          = 0.88      # pu — triggers auto speed-force
CRISIS_FREQ_LOW     = 49.5      # Hz — triggers auto speed-force
CRISIS_FREQ_HIGH    = 50.5      # Hz — triggers auto speed-force

# ─────────────────────────────────────────────
# DISPLAY GEOMETRY
# ─────────────────────────────────────────────
SYMBOL_SIZE         = 12        # px — all node symbols (native res)
UNIT_SQUARE_SIZE    = 12        # px — generation unit squares
UNIT_SQUARE_GAP     = 2         # px — gap between unit squares in station
CONNECTION_DOT_R    = 4         # px — junction dot radius

# Line thicknesses (native resolution)
LINE_400KV_W        = 2         # px each parallel line
LINE_400KV_GAP      = 4         # px gap between parallel lines
LINE_220KV_W        = 3         # px
LINE_150KV_W        = 2         # px
LINE_60KV_DOT       = 3         # px dot / 3px gap

# Flow animation
FLOW_MARKER_SIZE    = 3         # px — animated flow marker square
FLOW_MAX_SPEED      = 80        # px/second at 100% line rating
FLOW_MARKER_SPACING = 40        # px between markers at full speed

# Blink timing
BLINK_SLOW_MS       = 1000      # ms per cycle (0.5Hz — starting units)
BLINK_FAST_MS       = 250       # ms per cycle (2Hz — fault/alarm)

# ─────────────────────────────────────────────
# PANEL GEOMETRY (instrument strip)
# ─────────────────────────────────────────────
FREQ_PANEL_W        = 280
BALANCE_PANEL_W     = 280
DISPATCH_PANEL_W    = 640
ALARM_PANEL_W       = 720
PANEL_PADDING       = 8         # px internal padding
PANEL_GAP           = 6         # px between panels

# ─────────────────────────────────────────────
# FONT SIZES (native resolution)
# ─────────────────────────────────────────────
FONT_DATA           = 11        # px — numeric readouts, alarm text
FONT_LABEL          = 10        # px — node 4-letter labels
FONT_HEADING        = 13        # px — panel headings
FONT_FREQ           = 28        # px — main frequency display
FONT_ANTIALIAS_THRESHOLD = 12   # px — below this, no antialiasing

# ─────────────────────────────────────────────
# ALARM THRESHOLDS
# ─────────────────────────────────────────────
ALARM_LINE_WARN     = 85.0      # % loading — WARNING alarm
ALARM_LINE_CRIT     = 95.0      # % loading — CRITICAL alarm
ALARM_VOLT_WARN     = 0.92      # pu — WARNING alarm
ALARM_VOLT_CRIT     = 0.88      # pu — CRITICAL alarm
ALARM_RESERVE_LOW   = 10.0      # % — spinning reserve WARNING

# ─────────────────────────────────────────────
# DEBUG MODES
# ─────────────────────────────────────────────
DEBUG_SIMULATION    = False     # print simulation state to console each tick
DEBUG_DISPLAY       = False     # show coordinate grid + mouse position overlay
DEBUG_EVENTS        = False     # print scripted event firing to console
DEBUG_LOADFLOW      = False     # print B matrix and solution each tick

# ─────────────────────────────────────────────
# DIFFICULTY MODIFIERS
# ─────────────────────────────────────────────
DIFFICULTY_TRAINEE = {
    'noise_sigma_multiplier':   0.5,
    'autopilot_reserve_bonus':  0.20,
    'random_events':            False,
}
DIFFICULTY_OPERATOR = {
    'noise_sigma_multiplier':   1.0,
    'autopilot_reserve_bonus':  0.10,
    'random_events':            True,
    'random_event_severity':    'minor',
}
DIFFICULTY_DISPATCHER = {
    'noise_sigma_multiplier':   1.5,
    'autopilot_reserve_bonus':  0.05,
    'random_events':            True,
    'random_event_severity':    'significant',
}
```

### 0.3 Palette File

Write `src/display/palette.py` — every colour constant in the game. No RGB tuples appear anywhere else.

```python
# Background
COL_BACKGROUND      = (10,  14,  20)
COL_CANVAS_BG       = (8,   12,  18)

# Voltage level base colours
COL_400KV           = (0,  200, 255)   # bright cyan
COL_220KV           = (0,  255, 136)   # bright green
COL_150KV           = (255, 200,  0)   # amber
COL_60KV            = (200, 136,  0)   # dark amber

# Loading state overrides
COL_LOAD_WARN       = (204, 204,  0)   # yellow      60-80%
COL_LOAD_HIGH       = (255, 136,  0)   # orange      80-95%
COL_LOAD_CRIT       = (255,  34,  0)   # red         95-100%
COL_LINE_TRIPPED    = (68,  68,  68)   # dark grey

# Generation unit type colours
COL_COAL            = (136, 136, 136)
COL_CCGT            = (68,  136, 255)
COL_NUCLEAR         = (255, 136,  0)
COL_HYDRO           = (0,  200, 255)
COL_HYDRO_PUMP      = (0,   68, 170)
COL_WIND            = (136, 255,  68)
COL_SOLAR           = (255, 255,  0)

# Load substation
COL_LOAD_SUB        = (200, 136,  0)
COL_LOAD_HIGH_SUB   = (255,  68,  0)

# Interconnector
COL_INTERCONNECT    = (255, 136, 255)  # magenta — unique, unmistakable

# UI chrome
COL_PANEL_BORDER    = (0,  102,  51)   # dark green — SCADA terminal
COL_PANEL_BG        = (12,  18,  24)
COL_TEXT_PRIMARY    = (220, 220, 220)
COL_TEXT_DIM        = (120, 120, 120)
COL_SELECTION       = (255, 255, 255)  # white — selected element outline

# Alarm colours
COL_ALARM_CRIT      = (255,  34,  0)
COL_ALARM_WARN      = (204, 204,  0)
COL_ALARM_INFO      = (0,  200, 255)

# Debug overlay
COL_DEBUG_GRID      = (30,  40,  50)   # faint grid lines
COL_DEBUG_COORD     = (0,  255,  0)    # coordinate text
COL_DEBUG_MOUSE     = (255, 255,  0)   # mouse position indicator
```

### 0.4 Asset Path Helper

Write `src/utils/helpers.py`. The `resource_path()` function is used for every asset reference — fonts, sounds, any future images. Never use hardcoded absolute paths.

```python
import sys
import os

def resource_path(relative_path: str) -> str:
    """
    Returns the correct absolute path to an asset file.
    Works both in development (running from src/) and in
    PyInstaller builds (where files are extracted to _MEIPASS).
    
    Usage:
        font_path = resource_path('assets/fonts/JetBrainsMono-Regular.ttf')
        sound_path = resource_path('assets/sounds/alarm_critical.wav')
    """
    if hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)
```

### 0.5 Debug Module

Write `src/display/debug.py` — two independent debug overlays, each toggled by a constant in `constants.py`.

**Simulation debug mode** (`DEBUG_SIMULATION = True`):
- Prints to console every simulation tick: sim time, frequency, total generation, total load, imbalance, worst line loading, worst VSI
- Prints when any scripted event fires
- Prints when any line trips or unit trips
- Prints B matrix solution if `DEBUG_LOADFLOW = True`

```python
def print_sim_state(state: SimulationState, tick: int):
    if not DEBUG_SIMULATION:
        return
    print(f"[{tick:06d}] t={state.sim_time_min:6.2f}min "
          f"f={state.frequency_hz:.3f}Hz "
          f"gen={state.total_generation_mw:.0f}MW "
          f"load={state.total_load_mw:.0f}MW "
          f"imb={state.total_generation_mw - state.total_load_mw:+.0f}MW "
          f"L_max={max(state.line_loading.values()):.1f}% "
          f"V_min={min(state.bus_voltages.values()):.3f}pu")
```

**Display debug mode** (`DEBUG_DISPLAY = True`):
- Renders a faint coordinate grid over the canvas (120px spacing, `COL_DEBUG_GRID`)
- Shows current mouse position as X,Y coordinates in top-left corner of canvas
- On left-click anywhere on canvas: prints clicked coordinates to console AND displays them on screen for 3 seconds
- Shows frame time (ms) and current FPS in top-right corner of canvas
- Shows current simulation speed multiplier

```python
def render_debug_overlay(surface, mouse_pos, frame_time_ms, fps, speed):
    if not DEBUG_DISPLAY:
        return
    # Draw coordinate grid
    # Draw mouse position
    # Draw performance metrics
    # Draw speed indicator
```

Both debug modes are independent. Both default to `False` in `constants.py`. Neither affects performance when disabled — the check is a single boolean comparison.

### 0.6 Test Harness Skeleton

Write `tests/test_simulation.py` with empty test function stubs. Tests will be filled in as each simulation module is completed.

```python
def test_grid_loads():       pass   # Stage 1
def test_loadflow_solves():  pass   # Stage 3.1
def test_unit_trip():        pass   # Stage 3.8
def test_cascade():          pass   # Stage 3.7
def test_island_detect():    pass   # Stage 3.7
def test_shift1_nominal():   pass   # Stage 3.10
```

**Validation:** `python src/main.py` runs without errors (blank window or placeholder). `python tests/test_simulation.py` runs without errors (all stubs pass vacuously). Directory structure complete and committed.

---

## Stage 1 — Network Data Model

**Objective:** Define the complete 32-node network as Python data structures. No simulation. No display. Just the topology everything else operates on.

### 1.1 Bus Definitions

Write `src/data/topology.py` — every network node as a dataclass:

```python
from dataclasses import dataclass

@dataclass
class Bus:
    label: str              # 4-char unique: CNTR, MDBY, RVSD, HART...
    name: str               # Full name: Centrefield, Midbury, Riverside...
    voltage_kv: float       # 400, 220, 150, or 60
    node_type: str          # TRANSIT, GENERATION, LOAD, INTERCONNECTOR
    x: int                  # canvas X position (native 1920×1080)
    y: int                  # canvas Y position
    active_from_shift: int  # 1, 3, or 5
```

All 32 transmission nodes and 6 load substations defined using positions from GRID_TOPOLOGY_AND_DISPLAY.md Section 8.2 as the starting reference. Positions will be adjusted after Stage 2 visual validation — this is expected.

### 1.2 Line Definitions

```python
@dataclass
class Line:
    label: str              # L01, L02...L29
    from_bus: str           # bus label
    to_bus: str             # bus label
    voltage_kv: float
    rating_mw: float
    reactance_pu: float
    active_from_shift: int
```

All lines from GRID_TOPOLOGY_AND_DISPLAY.md Section 7.2 defined.

### 1.3 Generation Fleet

Write `src/data/fleet.py`:

```python
@dataclass
class GenerationUnit:
    label: str              # RVSD-1, RVSD-2, RVSD-3, HART-1...
    station: str            # RVSD, HART, KELM...
    unit_type: str          # COAL, CCGT, NUCLEAR, HYDRO, HYDRO_PUMP,
                            # HYDRO_ROR, WIND, SOLAR
    rated_mw: float
    min_mw: float
    ramp_rate_pct: float    # % rated MW per simulated minute
    cold_start_min: int     # simulated minutes to synchronise from cold
    inertia_h: float        # seconds
    droop_r: float
    q_max_mvar: float
    q_min_mvar: float
    bus: str                # host bus label
    active_from_shift: int
    is_pumped_storage: bool = False
    downstream_unit: str = None  # label of downstream hydro unit (if any)
```

All 47 units defined. The count of 47 matches the GRIDCOM terminal boot sequence.

### 1.4 Demand Profile

Write `src/data/profiles.py`:

```python
# Normalised daily demand profile — fraction of peak, 24 hourly values
DEMAND_PROFILE_WEEKDAY = [
    0.65, 0.61, 0.58, 0.57, 0.57, 0.60,   # 00-05
    0.66, 0.74, 0.82, 0.87, 0.89, 0.90,   # 06-11
    0.89, 0.86, 0.85, 0.85, 0.87, 0.91,   # 12-17
    0.95, 0.98, 1.00, 0.97, 0.90, 0.78    # 18-23
]

# Peak demand per load substation (MW)
PEAK_LOAD_MW = {
    'LD01': 1800,   # Ashford North
    'LD02': 1600,   # Midbury Central
    'LD03': 1200,   # Rivergate
    'LD04': 1000,   # Wrentham East
    'LD05':  800,   # Southwick
    'LD06':  600,   # Feldon
}

# Shift specifications
SHIFT_SPECS = {
    1:  {'start_hour': 2,  'duration_hours': 2,  'grid_size': 12, 'phase1': False},
    2:  {'start_hour': 6,  'duration_hours': 3,  'grid_size': 12, 'phase1': False},
    3:  {'start_hour': 9,  'duration_hours': 4,  'grid_size': 20, 'phase1': False},
    4:  {'start_hour': 16, 'duration_hours': 4,  'grid_size': 20, 'phase1': False},
    5:  {'start_hour': 6,  'duration_hours': 6,  'grid_size': 32, 'phase1': True},
    6:  {'start_hour': 14, 'duration_hours': 6,  'grid_size': 32, 'phase1': True},
    7:  {'start_hour': 6,  'duration_hours': 8,  'grid_size': 32, 'phase1': True},
    8:  {'start_hour': 10, 'duration_hours': 8,  'grid_size': 32, 'phase1': True},
    9:  {'start_hour': 6,  'duration_hours': 10, 'grid_size': 32, 'phase1': True},
    10: {'start_hour': 6,  'duration_hours': 12, 'grid_size': 32, 'phase1': True},
}
```

### 1.5 Grid Object

Write `src/simulation/grid.py`:

```python
class Grid:
    def __init__(self, shift_number: int):
        # Load and filter topology to active_from_shift <= shift_number
        # Load and filter fleet to active_from_shift <= shift_number
        # Initialise all unit states
        
    def get_active_buses(self) -> list
    def get_active_lines(self) -> list
    def get_active_units(self) -> list
    def get_bus(self, label: str) -> Bus
    def get_line(self, label: str) -> Line
    def get_units_at_bus(self, bus_label: str) -> list
    def get_load_at_bus(self, bus_label: str, hour: float) -> float
```

**Validation:** Run `test_grid_loads()`:
- `Grid(1)` produces exactly 12 active buses and correct line count
- `Grid(3)` produces exactly 20 active buses
- `Grid(5)` produces exactly 32 active buses plus 6 load substations
- All 47 units load without errors
- Print active bus list and unit list to console for manual inspection

---

## Stage 2 — Static Grid Renderer

**Objective:** Draw the complete grid schematic on screen. No simulation connected. No animation. Prove the layout works visually.

### 2.1 Pygame Initialisation and Resolution Scaling

Write the display initialisation in `src/main.py`:

```python
import pygame
import pygame.freetype
from simulation.constants import NATIVE_W, NATIVE_H, ASPECT_RATIO, TARGET_FPS

def init_display():
    pygame.init()
    pygame.freetype.init()
    
    info = pygame.display.Info()
    monitor_w = info.current_w
    monitor_h = info.current_h
    
    # Scale down to fit monitor, maintaining 16:9
    scale = min(monitor_w / NATIVE_W, monitor_h / NATIVE_H)
    display_w = int(NATIVE_W * scale)
    display_h = int(NATIVE_H * scale)
    
    screen = pygame.display.set_mode(
        (display_w, display_h),
        pygame.FULLSCREEN
    )
    pygame.display.set_caption("GRIDCOM : Grid Control Terminal")
    
    # All game rendering happens on a native-resolution surface
    # then scaled to the display surface each frame
    native_surface = pygame.Surface((NATIVE_W, NATIVE_H))
    
    return screen, native_surface, scale
```

The `native_surface` is the authoritative rendering target. All coordinates, symbols, and text are authored at 1920×1080. At the end of each frame the native surface is scaled to the display surface:

```python
scaled = pygame.transform.scale(native_surface, (display_w, display_h))
screen.blit(scaled, (0, 0))
pygame.display.flip()
```

This single scaling step handles all resolutions cleanly. One coordinate system throughout the codebase.

### 2.2 Font Loading

Load all fonts through `resource_path()` using `pygame.freetype`:

```python
from utils.helpers import resource_path
import pygame.freetype

def load_fonts():
    mono_regular = pygame.freetype.Font(
        resource_path('assets/fonts/JetBrainsMono-Regular.ttf'), FONT_DATA)
    mono_bold = pygame.freetype.Font(
        resource_path('assets/fonts/JetBrainsMono-Bold.ttf'), FONT_FREQ)
    sans = pygame.freetype.Font(
        resource_path('assets/fonts/LiberationSans-Regular.ttf'), FONT_HEADING)
    return mono_regular, mono_bold, sans
```

Verify correct rendering at all required sizes. Hard pixel rendering (no antialias) for 10-11px. Proper hinting for 13px+.

### 2.3 Canvas Background

Draw the two screen regions on the native surface:
- Grid canvas: fill `COL_CANVAS_BG` from (0,0) to (NATIVE_W, CANVAS_H)
- Instrument strip: fill `COL_BACKGROUND` from (0, STRIP_Y) to (NATIVE_W, NATIVE_H)
- 1px border between canvas and strip in `COL_PANEL_BORDER`

### 2.4 Symbol Drawing Functions

Write `src/display/symbols.py` — one function per symbol type, all taking a `surface`, position, state, and `scale` parameter:

```python
def draw_transmission_substation(surface, cx, cy, voltage_kv, vsi=1.0):
    """
    Square (12×12px) with upward triangle inscribed.
    Border colour = voltage level base colour.
    Triangle fill = voltage colour at 70% brightness.
    Border width and colour modified by VSI state.
    """

def draw_load_substation(surface, cx, cy, load_pct=0.5):
    """
    Square (12×12px) with downward triangle inscribed.
    Fill colour shifts amber → orange-red as load increases.
    """

def draw_generation_unit(surface, cx, cy, unit_type, state, output_pct=0.0):
    """
    Filled square (12×12px).
    Fill colour = unit type colour from palette.
    Border colour and blink state = unit operational state.
    Output bar inside square, bottom-aligned, proportional to output_pct.
    """

def draw_pumped_storage_arrow(surface, cx, cy, mode):
    """
    Mode arrow overlaid on generation unit square:
    GENERATING: white upward arrow (↑)
    PUMPING:    white downward arrow (↓)
    IDLE:       nothing
    """

def draw_demand_arrow(surface, cx, cy, mw):
    """
    Solid downward triangle (8×10px) + MW label below.
    Hangs from a transmission bus. Not interactive.
    """

def draw_interconnector_terminus(surface, x, y, direction, flow_mw=0):
    """
    Double line ending in filled chevron at canvas edge.
    Colour: COL_INTERCONNECT magenta.
    Flow label: +MW (import) or -MW (export).
    """

def draw_station_collector(surface, units_x_list, y, bus_cx, bus_cy):
    """
    Horizontal collector line connecting unit squares in a multi-unit station.
    Vertical feeder line from collector centre to substation bus.
    """
```

### 2.5 Line Rendering

Write line drawing in `src/display/canvas.py`. Lines are drawn as the correct voltage representation:

```python
def draw_line(surface, from_pos, to_pos, voltage_kv, loading_pct=0.0,
              is_tripped=False):
    colour = get_line_colour(voltage_kv, loading_pct, is_tripped)
    
    if voltage_kv == 400:
        # Two parallel lines, offset perpendicular to line direction
        draw_parallel_lines(surface, from_pos, to_pos, colour,
                           width=LINE_400KV_W, gap=LINE_400KV_GAP)
    elif voltage_kv == 220:
        pygame.draw.line(surface, colour, from_pos, to_pos, LINE_220KV_W)
    elif voltage_kv == 150:
        pygame.draw.line(surface, colour, from_pos, to_pos, LINE_150KV_W)
    elif voltage_kv == 60:
        draw_dotted_line(surface, from_pos, to_pos, colour,
                        dot=3, gap=3, width=1)

def get_line_colour(voltage_kv, loading_pct, is_tripped):
    if is_tripped:
        return COL_LINE_TRIPPED
    if loading_pct > 95:
        return COL_LOAD_CRIT
    if loading_pct > 80:
        return COL_LOAD_HIGH
    if loading_pct > 60:
        return COL_LOAD_WARN
    # Healthy — return voltage base colour
    return {400: COL_400KV, 220: COL_220KV,
            150: COL_150KV, 60: COL_60KV}[voltage_kv]
```

Connection dots (4px filled white circle) at every actual electrical junction — not at crossings.

Higher voltage lines drawn on top of lower voltage lines at crossings (draw order: 60kV → 150kV → 220kV → 400kV).

### 2.6 Hydraulic Connectors

Dashed cyan lines between pumped storage upper/lower pairs and between cascade stations. Drawn on a separate pass, visually distinct from all electrical lines.

```python
def draw_hydraulic_connector(surface, from_pos, to_pos):
    # Dashed line: 4px dash, 4px gap, COL_HYDRO cyan, 2px width
    # Small water-drop indicator at midpoint (optional decorative element)
```

### 2.7 Label Rendering

4-character labels below each node (4px gap below symbol bottom). If below is occupied by unit squares, label moves above.

```python
def draw_node_label(surface, cx, cy, label, font, is_selected=False):
    colour = COL_TEXT_PRIMARY if is_selected else COL_TEXT_DIM
    # Render label centred below (or above) the symbol
```

### 2.8 Layer Rendering Stack

Write `src/display/renderer.py` with the complete layer stack:

```python
def render_grid(surface, grid, state=None):
    """
    Renders the grid canvas in layer order.
    If state is None, renders with placeholder healthy-state values.
    """
    # Layer 0: Canvas background
    # Layer 1: 60kV load lines (drawn first — lowest priority at crossings)
    # Layer 2: 150kV lines
    # Layer 3: 220kV lines
    # Layer 4: 400kV lines (drawn last — highest priority at crossings)
    # Layer 5: Hydraulic connectors
    # Layer 6: Substation symbols (60kV → 150kV → 220kV → 400kV)
    # Layer 7: Generation unit squares + collector lines + feeder lines
    # Layer 8: Demand arrows + MW labels
    # Layer 9: Interconnector markers + flow labels
    # Layer 10: State overlays (voltage halos — empty until Stage 5)
    # Layer 11: Selection highlight (empty until Stage 6)
    # Layer 12: Node labels + live data values
    # Layer 13: Alarm indicators (empty until Stage 5)
    # Layer 14: Debug overlay (if DEBUG_DISPLAY enabled)
```

### 2.9 Shift 1 Sub-Grid Filter

Active nodes (shift 1: 12 nodes) render in full colour. Inactive nodes render as very dim outlines only — the full grid shape is visible but greyed out, communicating that more grid exists beyond the current scope.

```python
def is_node_active(node, current_shift):
    return node.active_from_shift <= current_shift

def get_node_alpha(node, current_shift):
    return 255 if is_node_active(node, current_shift) else 30
```

**Validation:** Run the game. Screenshot the rendered canvas. Walk through the visual checklist:

```
□ All 32 nodes visible — 12 in full colour, 20 as dim outlines
□ 400kV backbone immediately readable (cyan double-lines dominant)
□ Voltage hierarchy legible without a legend
□ No label collisions — all 4-char codes clearly readable
□ Cascade stations visually grouped with hydraulic connectors
□ Hydraulic connectors clearly distinct from electrical lines
□ Load substations (inverted triangle) distinct from transmission (upright)
□ Generation unit squares correctly grouped into stations
□ Interconnector chevrons at canvas edges, magenta colour distinct
□ Debug grid displays correctly when DEBUG_DISPLAY = True
□ Mouse coordinate display works — click canvas, coordinates appear
```

Adjust node positions in `src/data/topology.py` until all checklist items pass. **Lock node positions after this step.** These coordinates do not change again.

---

## Stage 3 — Simulation Engine (Console Validation)

**Objective:** Build the complete physics simulation and validate it produces realistic power system behaviour. No display connection. Console output and test harness only.

### 3.1 DC Load Flow Solver

Write `src/simulation/loadflow.py`:

```python
import numpy as np
from simulation.constants import YSHUNT_REG

class DCLoadFlow:
    def __init__(self, buses: list, lines: list, slack_bus: str = 'MDBY'):
        self.buses = buses
        self.lines = lines
        self.slack_bus = slack_bus
        self.b_matrix = None
        self.build_b_matrix()
    
    def build_b_matrix(self):
        """
        Construct susceptance matrix from line reactances.
        B[i,i] = Σ(1/X) for all lines at bus i
        B[i,j] = -(1/X) for each line between bus i and j
        Add YSHUNT_REG to diagonal for numerical stability.
        Remove slack bus row/column before storing.
        """
    
    def solve(self, p_injections: dict) -> dict:
        """
        Solve θ = B⁻¹ × P using numpy.linalg.solve.
        Returns {bus_label: angle_rad} for all non-slack buses.
        Slack bus angle = 0 by definition.
        """
    
    def compute_line_flows(self, theta: dict) -> dict:
        """
        P_line(i→j) = (θᵢ - θⱼ) / Xᵢⱼ
        Returns {line_label: flow_mw}
        Positive = conventional direction (from_bus → to_bus)
        Negative = reverse direction
        """
    
    def compute_line_loading(self, flows: dict) -> dict:
        """
        Loading = |flow| / rating × 100
        Returns {line_label: loading_pct}
        """
    
    def rebuild(self, lines_in_service: list):
        """
        Rebuild B matrix after topology change (line trip).
        Called by cascade detector after each trip event.
        """
```

Slack bus: `MDBY` (Midbury 400kV — central backbone hub). Provides voltage angle reference (θ = 0) and absorbs system imbalance.

### 3.2 Decoupled Voltage Solver

Write `src/simulation/voltage.py`:

```python
class VoltageModel:
    def __init__(self, buses: list, lines: list):
        self.b_prime = None
        self.build_b_prime()
    
    def build_b_prime(self):
        """B' matrix from line susceptances and shunt elements."""
    
    def solve(self, q_injections: dict) -> dict:
        """
        ΔV = B'⁻¹ × Q
        Returns {bus_label: voltage_pu}
        """
    
    def check_reactive_limits(self, voltages: dict,
                               units: list) -> tuple[dict, bool]:
        """
        For each PV bus: compute Q required to hold V setpoint.
        If Q_required > Q_max: convert to PQ, fix Q at Q_max.
        If Q_required < Q_min: convert to PQ, fix Q at Q_min.
        Re-solve if any conversions occurred.
        Maximum 2 passes — no convergence loop.
        Returns: (updated_voltages, any_conversions_occurred)
        """
    
    def apply_collapse_acceleration(self, voltages: dict,
                                     dt: float) -> dict:
        """
        Below COLLAPSE_THRESHOLD (0.85 pu):
        Apply nonlinear voltage deterioration.
        severity = (threshold - vsi) / (threshold - floor)
        acceleration = severity² × COLLAPSE_GAIN
        voltage[bus] -= acceleration × dt
        Below COLLAPSE_FLOOR (0.70 pu): flag for blackout.
        """
    
    def compute_vsi(self, voltages: dict) -> dict:
        """VSI = V_bus / V_nominal. Returns {bus_label: vsi}"""
```

### 3.3 Frequency Model

Write `src/simulation/frequency.py`:

```python
class FrequencyModel:
    def __init__(self):
        self.frequency = F_NOMINAL
    
    def compute_system_inertia(self, online_units: list) -> float:
        """
        H_system = Σ(Hᵢ × Sᵢ) / S_online
        Only ONLINE state units contribute.
        """
    
    def update(self, imbalance_mw: float, dt_seconds: float,
               online_units: list) -> float:
        """
        Δf = F_NOMINAL × imbalance / (2 × H_system × S_BASE)
        self.frequency += Δf × dt_seconds
        Clamp to [45, 55] Hz — outside this range is blackout.
        Returns new frequency.
        """
    
    def apply_droop_response(self, freq_deviation: float,
                              online_units: list) -> dict:
        """
        ΔP_governor = (freq_deviation / F_NOMINAL) × (1/R) × P_rated
        Bounded by available headroom (rated - current output).
        Returns {unit_label: delta_mw} automatic governor response.
        """
    
    def check_thresholds(self) -> list:
        """
        Compare current frequency against all thresholds from constants.
        Returns list of threshold events (WARNING, ALERT, LOADSHED_1, etc.)
        """
```

### 3.4 Generation Unit Model

Write `src/simulation/units.py`:

```python
from enum import Enum

class UnitState(Enum):
    OFFLINE   = 'OFFLINE'
    STARTING  = 'STARTING'
    ONLINE    = 'ONLINE'
    SHUTDOWN  = 'SHUTDOWN'

class UnitModel:
    def __init__(self, unit_data: GenerationUnit):
        self.data = unit_data
        self.state = UnitState.OFFLINE
        self.current_mw = 0.0
        self.target_mw = 0.0
        self.start_timer = 0.0     # simulated minutes elapsed in STARTING state
        self.q_injection = 0.0
        self.bus_type = 'PV'       # PV (voltage controlled) or PQ (Q limited)
    
    # State transitions
    def start(self): ...           # OFFLINE → STARTING
    def synchronise(self): ...     # STARTING → ONLINE
    def shutdown(self): ...        # ONLINE → SHUTDOWN
    def trip(self): ...            # Any → OFFLINE (fault)
    def complete_shutdown(self): ...  # SHUTDOWN → OFFLINE
    
    # Physics
    def update(self, dt_minutes: float):
        """Advance state machine. Ramp current_mw toward target_mw."""
    
    def ramp_toward(self, target_mw: float, dt_minutes: float):
        """Respects ramp_rate_pct from unit data."""
    
    def contributes_inertia(self) -> bool:
        return self.state == UnitState.ONLINE
    
    def available_headroom_mw(self) -> float:
        """MW available for droop response."""
        if self.state != UnitState.ONLINE:
            return 0.0
        return max(0, self.data.rated_mw - self.current_mw)
```

### 3.5 Demand Model

Write `src/simulation/demand.py`:

```python
import random
from simulation.constants import NOISE_SIGMA
from data.profiles import DEMAND_PROFILE_WEEKDAY, PEAK_LOAD_MW

class DemandModel:
    SYSTEM_PEAK_MW = 8000.0
    
    def get_forecast(self, sim_hour: float) -> float:
        """Deterministic demand — what the player sees on the forecast curve."""
        hour_int = int(sim_hour) % 24
        return self.SYSTEM_PEAK_MW * DEMAND_PROFILE_WEEKDAY[hour_int]
    
    def get_actual(self, sim_hour: float,
                   noise_multiplier: float = 1.0) -> float:
        """Forecast plus gaussian noise — what actually happens."""
        forecast = self.get_forecast(sim_hour)
        noise = random.gauss(0, NOISE_SIGMA * noise_multiplier * forecast)
        return max(0, forecast + noise)
    
    def get_per_bus(self, total_demand: float) -> dict:
        """
        Distribute total system demand to load buses
        proportional to their peak demand ratios.
        Returns {bus_label: demand_mw}
        """
        total_peak = sum(PEAK_LOAD_MW.values())
        return {
            bus: total_demand * (peak / total_peak)
            for bus, peak in PEAK_LOAD_MW.items()
        }
```

### 3.6 Renewable Models

Write `src/simulation/renewables.py`:

```python
import math, random

class WindModel:
    def __init__(self, rated_mw: float, noise_sigma: float = 0.15):
        self.rated_mw = rated_mw
        self.noise_sigma = noise_sigma
        self._actual_factor = 0.5  # initialised; evolves over time
    
    def get_forecast(self, sim_hour: float) -> float:
        """Smooth diurnal wind pattern — moderate day, stronger night."""
    
    def get_actual(self, sim_hour: float) -> float:
        """Forecast with persistent noise — wind changes slowly."""
    
    def step(self, dt_minutes: float):
        """Evolve actual wind factor — mean-reverts to forecast."""

class SolarModel:
    def __init__(self, rated_mw: float):
        self.rated_mw = rated_mw
        self._cloud_factor = 0.0
    
    def get_forecast(self, sim_hour: float) -> float:
        """Clear-sky irradiance profile — sine curve, sunrise 6, sunset 18."""
        irradiance = max(0, math.sin(math.pi * (sim_hour - 6) / 12))
        return self.rated_mw * irradiance
    
    def get_actual(self, sim_hour: float) -> float:
        """Forecast × (1 - 0.75 × cloud_factor)."""
    
    def step(self, dt_minutes: float):
        """Evolve cloud cover — slower variation than wind."""
```

### 3.7 Cascade Detector

Write `src/simulation/cascade.py`:

```python
from collections import deque

class CascadeDetector:
    def find_islands(self, buses: list,
                     lines_in_service: list) -> list[frozenset]:
        """
        Breadth-first search from each unvisited bus.
        Returns list of frozensets, each containing bus labels in one island.
        Single island (normal) = list of length 1.
        """
        adjacency = self._build_adjacency(buses, lines_in_service)
        visited = set()
        islands = []
        for bus in buses:
            if bus.label not in visited:
                island = self._bfs(bus.label, adjacency)
                islands.append(frozenset(island))
                visited.update(island)
        return islands
    
    def check_island_viability(self, island: frozenset,
                                grid) -> bool:
        """
        Does this island contain a slack bus or reference generator?
        Is there enough generation to supply load?
        Returns False if island will collapse (blackout).
        """
    
    def check_overloads(self, loading: dict, timers: dict,
                         dt_seconds: float) -> tuple[list, dict]:
        """
        Increment overload timers for lines above 100% loading.
        Reset timers for lines back below 100%.
        Return (lines_to_trip, updated_timers).
        Lines to trip are those where timer > TRIP_DELAY_S.
        """
    
    def _bfs(self, start: str, adjacency: dict) -> set:
        visited = {start}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for neighbour in adjacency.get(node, []):
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(neighbour)
        return visited
```

### 3.8 Scripted Event System

Write `src/simulation/events.py`:

```python
from dataclasses import dataclass, field
import random

@dataclass
class ScriptedEvent:
    shift: int
    sim_time_min: float         # minutes from shift start
    time_jitter: float          # ±fraction of sim_time_min
    event_type: str             # UNIT_TRIP, LINE_TRIP, DEMAND_SPIKE, etc.
    target: str                 # unit or line label
    duration_min: float = None  # None = permanent
    difficulty_filter: list = field(default_factory=lambda: ['TRAINEE','OPERATOR','DISPATCHER'])
    description: str = ''

class EventSystem:
    def __init__(self, shift: int, difficulty: str):
        self.events = self._load_events(shift, difficulty)
        self.fired = set()
    
    def _load_events(self, shift: int, difficulty: str) -> list:
        """Load events for this shift from shift definition file."""
    
    def check(self, sim_time_min: float) -> list[ScriptedEvent]:
        """
        Return events due at this sim time (with jitter applied at load time).
        Mark fired events so they don't trigger again.
        Log to console if DEBUG_EVENTS enabled.
        """
    
    def _apply_jitter(self, event: ScriptedEvent) -> float:
        """Apply ±time_jitter randomisation to event timing at load time."""
        jitter = event.sim_time_min * event.time_jitter
        return event.sim_time_min + random.uniform(-jitter, jitter)
```

Shift 1 scripted event (defined in `src/gameplay/shifts/shift_01.py`):
```python
SHIFT_1_EVENTS = [
    ScriptedEvent(
        shift=1,
        sim_time_min=40,        # 02:40 sim time (40 min from 02:00 start)
        time_jitter=0.15,
        event_type='UNIT_TRIP',
        target='RVSD-2',
        description='Riverside #2 overcurrent protection operation',
        difficulty_filter=['TRAINEE', 'OPERATOR', 'DISPATCHER']
    )
]
```

### 3.9 Master Simulation Loop

Write `src/simulation/simulation.py`:

```python
class GridSimulation:
    def __init__(self, grid: Grid, shift: int, difficulty: str):
        self.grid = grid
        self.loadflow = DCLoadFlow(grid.get_active_buses(),
                                   grid.get_active_lines())
        self.voltage = VoltageModel(grid.get_active_buses(),
                                    grid.get_active_lines())
        self.frequency = FrequencyModel()
        self.demand = DemandModel()
        self.cascade = CascadeDetector()
        self.events = EventSystem(shift, difficulty)
        
        self.sim_time_min = 0.0
        self.overload_timers = {}
        self.islands = []
        self.blackout_zones = set()
        self._state = None
    
    def tick(self, dt_sim_seconds: float):
        dt_min = dt_sim_seconds / 60.0
        self.sim_time_min += dt_min
        
        # 1. Update exogenous inputs
        hour = self.grid.start_hour + self.sim_time_min / 60.0
        demand_actual = self.demand.get_actual(hour)
        
        # 2. Inject scripted events
        for event in self.events.check(self.sim_time_min):
            self._apply_event(event)
        
        # 3. Update unit states and ramp toward targets
        for unit in self.grid.get_active_units():
            unit.update(dt_min)
        
        # 4. Compute power imbalance
        total_gen = sum(u.current_mw for u in self.grid.get_active_units()
                        if u.state == UnitState.ONLINE)
        imbalance = total_gen - demand_actual
        
        # 5. Update frequency + droop response
        self.frequency.update(imbalance, dt_sim_seconds,
                               self.grid.get_active_units())
        droop = self.frequency.apply_droop_response(
            self.frequency.frequency - F_NOMINAL,
            self.grid.get_active_units())
        # Apply droop adjustments to unit outputs
        
        # 6. Check frequency thresholds → automatic load shedding
        threshold_events = self.frequency.check_thresholds()
        self._handle_threshold_events(threshold_events)
        
        # 7. Build injection vectors
        p_injections = self._build_p_injections(demand_actual)
        q_injections = self._build_q_injections()
        
        # 8. Solve DC load flow
        theta = self.loadflow.solve(p_injections)
        flows = self.loadflow.compute_line_flows(theta)
        loading = self.loadflow.compute_line_loading(flows)
        
        # 9. Solve voltage
        voltages = self.voltage.solve(q_injections)
        voltages, _ = self.voltage.check_reactive_limits(voltages,
                                                          self.grid.get_active_units())
        voltages = self.voltage.apply_collapse_acceleration(voltages, dt_sim_seconds)
        vsi = self.voltage.compute_vsi(voltages)
        
        # 10. Check line overloads → trip if sustained
        lines_to_trip, self.overload_timers = self.cascade.check_overloads(
            loading, self.overload_timers, dt_sim_seconds)
        
        for line_label in lines_to_trip:
            self._trip_line(line_label)
            # Rebuild topology, re-solve load flow
        
        # 11. Island detection
        self.islands = self.cascade.find_islands(
            self.grid.get_active_buses(),
            [l for l in self.grid.get_active_lines() if l.in_service])
        for island in self.islands:
            if not self.cascade.check_island_viability(island, self.grid):
                self.blackout_zones.update(island)
        
        # 12. Update state snapshot
        self._state = self._build_state(
            hour, demand_actual, total_gen, flows, loading,
            voltages, vsi, theta)
        
        # 13. Debug output
        from display.debug import print_sim_state
        print_sim_state(self._state, int(self.sim_time_min * 10))
    
    def get_state(self) -> 'SimulationState':
        return self._state
    
    # Player control interface
    def set_unit_target(self, unit_label: str, target_mw: float): ...
    def start_unit(self, unit_label: str): ...
    def stop_unit(self, unit_label: str): ...
    def trip_line(self, line_label: str): ...
    def shed_load(self, bus_label: str, fraction: float): ...
```

### 3.10 Console Validation

Fill in and run all test functions in `tests/test_simulation.py`:

```python
def test_grid_loads():
    # Grid(1) = 12 buses, Grid(3) = 20, Grid(5) = 32 — all verified

def test_loadflow_solves():
    # Run DC load flow on 12-bus grid with realistic injections
    # Assert all line flows are physically reasonable
    # Assert no matrix singularity

def test_unit_trip():
    # Inject RVSD-2 trip at t=40min
    # Assert frequency drops below 49.9Hz within 30 sim seconds
    # Assert frequency recovers above 49.8Hz within 5 sim minutes
    # Assert no cascade triggered

def test_cascade():
    # Manually overload a line
    # Run for TRIP_DELAY_S seconds of sim time
    # Assert line trips
    # Assert B matrix rebuilds
    # Assert flows redistribute to remaining lines

def test_island_detect():
    # Trip specific lines to create an island
    # Assert BFS identifies two separate islands
    # Assert island without reference generator flagged non-viable

def test_shift1_nominal():
    # Run full 120 sim minutes, no events
    # Assert frequency stays within 49.8-50.2 Hz
    # Assert no line overloads
    # Assert no load shedding

def test_shift1_with_event():
    # Run to t=40min, allow RVSD-2 trip event to fire
    # Assert all of the above except frequency dip at trip time
    # Assert recovery without cascade
```

**Validation:** All tests pass. Enable `DEBUG_SIMULATION = True` in constants and run a 120-minute simulation. Review console output. Frequency trace should be smooth — tight noise around 50.0Hz, clear dip at the unit trip event, recovery driven by droop response. If behaviour feels wrong, tune constants before proceeding.

---

## Stage 4 — Instrument Strip (Static Test Data)

**Objective:** Build all four instrument strip panels with hardcoded test values. Validate layout, fonts, and colour states before connecting live data.

### 4.1 Frequency Panel (280px wide)

```
┌──────────────────────────────┐
│ SYSTEM FREQUENCY             │
│                              │
│      50.02  Hz               │
│                              │
│  ┤▓▓▓▓▓▓▓▓▓░░░░░░░░░├        │
│  49.0              51.0      │
│                              │
│  Δ  +0.02 Hz   ↑ rising      │
└──────────────────────────────┘
```

Validate all three colour states: green (49.8-50.2), yellow (warning zones), red (critical). Analog bar zones correct.

### 4.2 Generation/Load Balance Panel (280px wide)

```
┌──────────────────────────────┐
│ POWER BALANCE                │
│  GEN    7,842 MW    ▲        │
│  LOAD   7,801 MW             │
│  ─────────────────           │
│  BAL      +41 MW   ●         │
│  SPIN RES  620 MW            │
│  INERTIA   4.8 s             │
└──────────────────────────────┘
```

### 4.3 Unit Dispatch Panel (640px wide)

Scrollable list with test data covering all unit states — ONLINE, OFFLINE, STARTING, FAULT. Column alignment correct. Output bars visible and proportional. Scroll behaviour (mouse wheel + keyboard up/down) functional.

### 4.4 Alarm Feed Panel (720px wide)

Scrollable list with test alarms at all three priority levels (CRIT/WARN/INFO). ACK button visible. ACK keyboard shortcut (A key) functional on test alarms. Unacknowledged alarms blinking correctly using shared blink clock.

**Validation:** Screenshot instrument strip. All four panels correctly proportioned. Every text element legible. No clipping. No overflow. Scroll works on both panels. Blink timing is in phase across all blinking elements.

---

## Stage 5 — Simulation to Display Connection

**Objective:** Connect live simulation state to the renderer. The grid responds to simulation ticks in real-time.

### 5.1 Simulation State Object

Define `SimulationState` dataclass in `src/simulation/simulation.py` — the complete snapshot transferred from simulation to renderer each frame:

```python
@dataclass
class SimulationState:
    sim_time_min: float
    sim_hour: float
    frequency_hz: float
    frequency_trend: str        # 'RISING', 'FALLING', 'STABLE'
    total_generation_mw: float
    total_load_mw: float
    spinning_reserve_mw: float
    system_inertia_h: float
    
    bus_voltages: dict          # {label: voltage_pu}
    bus_angles: dict            # {label: angle_rad}
    line_flows: dict            # {label: flow_mw}
    line_loading: dict          # {label: loading_pct}
    line_status: dict           # {label: 'IN_SERVICE' | 'TRIPPED'}
    
    unit_states: dict           # {label: UnitState}
    unit_outputs_mw: dict       # {label: current_mw}
    unit_q_injections: dict     # {label: q_mvar}
    
    demand_forecast: dict       # {hour: mw} — full shift forecast
    renewable_forecast: dict    # {source: {hour: mw}}
    
    active_alarms: list         # [Alarm] newest first
    islands: list               # [frozenset of bus labels]
    blackout_zones: frozenset   # bus labels currently blacked out
    
    crisis_active: bool         # any crisis condition currently triggered
    crisis_type: str            # 'CRITICAL' | 'WARNING' | None
```

### 5.2 Game Loop

Write the main game loop in `src/main.py`:

```python
def run():
    screen, native_surface, scale = init_display()
    fonts = load_fonts()
    clock = pygame.time.Clock()
    
    # Game state
    current_speed = SPEED_NORMAL
    crisis_acknowledged = True
    selected_element = None
    
    while running:
        # 1. Handle all input events
        for event in pygame.event.get():
            handle_event(event, ...)
        
        # 2. Advance simulation
        real_dt_ms = clock.tick(TARGET_FPS)
        real_dt_s = real_dt_ms / 1000.0
        
        if current_speed > 0:
            sim_dt_s = real_dt_s * current_speed * TIME_COMPRESSION
            simulation.tick(sim_dt_s)
        
        # 3. Get simulation state
        state = simulation.get_state()
        
        # 4. Check crisis conditions
        if check_crisis(state) and crisis_acknowledged:
            current_speed = SPEED_SLOW
            crisis_acknowledged = False
        
        # 5. Clear native surface
        native_surface.fill(COL_BACKGROUND)
        
        # 6. Render all layers
        renderer.render(native_surface, state, selected_element,
                        current_speed, fonts)
        
        # 7. Scale to display
        scaled = pygame.transform.scale(
            native_surface, screen.get_size())
        screen.blit(scaled, (0, 0))
        pygame.display.flip()
```

### 5.3 Dynamic Line Colours and Flow Animation

Connect simulation state to line rendering. Loading percentages from `SimulationState.line_loading` drive colour selection every frame. Flow animation markers use `line_flows` for speed and direction.

### 5.4 Dynamic Instrument Strip

Connect all four panels to live `SimulationState` values. Frequency display updates every frame (smooth — interpolated between ticks). Unit list and alarm feed update every simulation tick.

### 5.5 Unit State Display

Unit squares on canvas reflect `SimulationState.unit_states` and `unit_outputs_mw` every frame.

### 5.6 Speed Controls

Both keyboard (0-4 keys) and mouse (clickable speed buttons in instrument strip) control simulation speed. Speed indicator displayed in strip.

### 5.7 Crisis Auto-Forcing

Every frame, evaluate all crisis conditions against `SimulationState`. On first trigger:
- Force `current_speed = SPEED_SLOW`
- Set `crisis_acknowledged = False`
- Flash screen border (update renderer to draw coloured border when crisis active)
- Add alarm entry

Player must press A (keyboard) or click ACK button (mouse) to set `crisis_acknowledged = True` and allow speed increase.

**Validation:** Run simulation at VERY FAST. Observe the grid live for 2 minutes. All line colours update with loading. Flow markers move in correct directions. Frequency panel tracks simulation. When RVSD-2 trips: speed drops, border flashes, alarm appears, speed controls locked until ACK. ACK works by both mouse click and keyboard.

---

## Stage 6 — Player Interaction

**Objective:** All player controls for Shift 1 functional via both mouse and keyboard.

### 6.1 Element Selection

Hit detection for all canvas elements:

```python
def get_element_at(mouse_pos, grid, state) -> tuple[str, str]:
    """
    Returns (element_type, element_label) for element under mouse.
    element_type: 'BUS', 'LINE', 'UNIT', 'LOAD', 'INTERCONNECTOR', None
    
    Hit detection:
    - Bus/unit symbols: 12×12px bounding box
    - Lines: within 6px of line path (any point along the segment)
    - Load substations: 12×12px bounding box
    """
```

Left-click selects element. Selected element highlighted with 2px white outline. Pressing ESC (keyboard) or clicking empty canvas deselects.

### 6.2 Context Panels

Write `src/display/context.py` — context panels rendered near selected element, positioned to avoid canvas edges:

```python
def draw_context_panel(surface, element_type, element_label,
                        state, fonts, canvas_bounds):
    """
    Panel size: 200×160px
    Position: near selected element, adjusted to stay within canvas.
    Content varies by element_type.
    """
```

All context panel types from GRID_TOPOLOGY_AND_DISPLAY.md Section 11.1 implemented.

### 6.3 Unit Controls

From unit context panel and from right-click menu:

**SET OUTPUT** — numeric input for target MW. Both mouse (click field, type value) and keyboard (Tab to field, type value, Enter to confirm) work.

**START UNIT** — available from Shift 2 (greyed with "Shift 2" label in Shift 1).

**STOP UNIT** — available from Shift 2 (greyed).

```python
def handle_set_output(unit_label, target_mw, simulation):
    """Validate target within min/max. Send to simulation."""
    unit = simulation.grid.get_unit(unit_label)
    target_mw = max(unit.data.min_mw,
                    min(unit.data.rated_mw, target_mw))
    simulation.set_unit_target(unit_label, target_mw)
```

### 6.4 Right-Click Context Menus

Right-click on any element opens a context menu positioned near the click. Menu items that aren't available yet are shown greyed with "Available: Shift X" label.

```
Generation unit menu:
  ► Set output target...         [always available in Phase 2]
  ► Start unit                   [Shift 2]
  ► Shutdown unit                [Shift 2]
  ─────────────────────
  ► Unit details...              [always available]

Line menu:
  ► Open line (trip)             [Shift 6]
  ► Close line (re-energise)     [Shift 6]
  ─────────────────────
  ► Line details...              [always available]

Load substation menu:
  ► Shed load...                 [Shift 4]
  ─────────────────────
  ► Substation details...        [always available]
```

### 6.5 Keyboard Navigation

Full keyboard access to all mouse interactions:

```
Tab         Cycle selection through all active elements
Enter       Open context panel for selected element
Escape      Close context panel / deselect / cancel action
Arrow keys  Navigate through unit dispatch list
Page Up/Dn  Scroll alarm feed
A           Acknowledge top alarm
Shift+A     Acknowledge all alarms
0 / Space   Pause
1           Slow speed
2           Normal speed
3           Fast speed
4           Very fast speed
F           Focus / jump to frequency panel
?           Show keyboard shortcut reference card
```

**Validation:** Complete manual playthrough of Shift 1 using only keyboard. Complete another using only mouse. Both must be fully functional.

---

## Stage 7 — Campaign Shell and Shift 1 Complete

**Objective:** Intro sequence, main menu, campaign structure, debrief — Shift 1 fully playable from cold start to debrief.

### 7.1 Rendered Intro Sequence

Implement the intro story from GRIDCOM_INTRO_STORY.md as a rendered pygame scene. All screens are rendered — no separate text mode.

Text rendering approach:
- Each screen is a `Scene` object with a list of `TextReveal` elements
- `TextReveal` renders text character by character at a defined rate (typing effect)
- Formatted documents (handover notes, logbook) render with appropriate monospace layout
- Cursor blink uses the shared blink clock
- Player can hold any key to fast-forward text reveal
- On second+ playthrough, Screen 1 offers immediate skip

```python
class IntroScene:
    def __init__(self, fonts):
        self.screens = self._build_screens()
        self.current_screen = 0
        self.current_reveal = 0
    
    def update(self, dt): ...
    def render(self, surface, fonts): ...
    def advance(self): ...    # next screen or start game
    def skip(self): ...       # jump to boot sequence
```

The terminal boot sequence (Screen 6) renders output line by line with a short delay between lines — simulating a real system initialisation.

### 7.2 Main Menu

Rendered main menu screen — consistent with the SCADA aesthetic:

```
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║         G R I D C O M   v2.4.1                       ║
║         Grid Control Terminal                         ║
║                                                       ║
║         National Energy Control Centre                ║
║                                                       ║
║─────────────────────────────────────────────────────║
║                                                       ║
║    [ NEW CAMPAIGN ]                                   ║
║    [ CONTINUE     ]    (greyed if no save)            ║
║    [ FREEPLAY     ]    (greyed until campaign done)   ║
║    [ QUIT         ]                                   ║
║                                                       ║
║─────────────────────────────────────────────────────║
║  "Frequency nominal. For now."                        ║
╚═══════════════════════════════════════════════════════╝
```

Mouse hover highlights menu items. Keyboard up/down navigates. Enter selects. Both work.

### 7.3 Difficulty Selection

On NEW CAMPAIGN: difficulty selection screen before intro begins.

```
SELECT DIFFICULTY:

  [ TRAINEE ]     Forecast errors small. Generous reserves.
                  Scripted events only. Recommended: first playthrough.

  [ OPERATOR ]    Standard forecast errors. Normal reserves.
                  Scripted + minor random events.

  [ DISPATCHER ]  Large forecast errors. Thin reserves.
                  Scripted + significant random events.
```

### 7.4 Campaign State Machine

Write `src/gameplay/campaign.py`:

```python
class CampaignState(Enum):
    MAIN_MENU   = 'MAIN_MENU'
    INTRO       = 'INTRO'
    SHIFT_INTRO = 'SHIFT_INTRO'    # single logbook entry before each shift
    PHASE_1     = 'PHASE_1'        # planning (Shifts 5-10 only)
    PHASE_2     = 'PHASE_2'        # real-time operations
    DEBRIEF     = 'DEBRIEF'
    CAMPAIGN_END= 'CAMPAIGN_END'

class Campaign:
    def __init__(self, difficulty: str):
        self.difficulty = difficulty
        self.current_shift = 1
        self.carry_forward = ShiftCarryForward()
        self.cumulative_score = {}
    
    def load_shift(self, shift_number: int): ...
    def complete_shift(self, results: ShiftResults): ...
    def save(self, filepath: str): ...
    
    @classmethod
    def load(cls, filepath: str) -> 'Campaign': ...
```

### 7.5 Autopilot Schedule Generator

Write `src/gameplay/autopilot.py`:

```python
class AutopilotSchedule:
    def generate(self, grid: Grid, shift_spec: dict,
                 difficulty: str) -> dict:
        """
        Generate a plausible but imperfect schedule for Shifts 1-4.
        - Commits units to meet forecast demand + 12% reserve
          (adjusted by difficulty reserve bonus)
        - Does NOT anticipate scripted events
        - Makes suboptimal hydro decisions (generates early)
        - Returns: {unit_label: initial_mw_setpoint}
        """
```

The autopilot schedule is intentionally imperfect — it creates the operational stress that motivates wanting Phase 1 when it arrives.

### 7.6 Shift Intro Screens

Each shift (2-10) begins with a single logbook entry before the terminal boot:

```python
SHIFT_INTROS = {
    1:  "System quiet. Overnight trough. Watch the north wind.",
    2:  "Morning ramp beginning. Solar forecast uncertain.",
    3:  "Mid-morning plateau. Congestion risk on northern path.",
    4:  "Evening peak. Solar collapsing at sunset. Reserves tight.",
    5:  "Full grid active. INTC-N scheduled +400MW. Plan accordingly.",
    6:  "Peak demand period. N-1 security marginal in the west. Know your restoration sequence.",
    7:  "Full morning cycle. Voltage profiles tight on southern load buses. Reactive reserves committed.",
    8:  "Solar peak then collapse. Kelmore reservoir positioning is everything today.",
    9:  "Ten hours. Full hydro-thermal coordination. The cheap plan is usually the dangerous one.",
    10: "Storm system forecast from the west. Twelve hours. Everything you know. All at once.",
}
```

### 7.7 Phase 2 Session Manager

Write `src/gameplay/phase2.py`:

```python
class Phase2Session:
    def __init__(self, grid: Grid, simulation: GridSimulation,
                 shift_spec: dict, events: EventSystem):
        self.shift_start_hour = shift_spec['start_hour']
        self.shift_end_min = shift_spec['duration_hours'] * 60
    
    def is_complete(self) -> bool:
        return self.simulation.sim_time_min >= self.shift_end_min
    
    def get_results(self) -> ShiftResults:
        """Compile performance metrics for debrief."""
```

### 7.8 Win/Fail Conditions

Shift 1 win/fail as specified:

```python
def check_shift1_fail(state: SimulationState) -> tuple[bool, str]:
    if state.frequency_hz < F_LOADSHED_1:
        return True, "Frequency dropped to {:.2f} Hz — automatic load shedding triggered.".format(state.frequency_hz)
    return False, None
```

On fail: rendered fail screen with cause, option to retry (return to shift start) or main menu.

### 7.9 Post-Shift Debrief

Write `src/gameplay/debrief.py` — rendered debrief screen with five performance dimensions. Dimensions not yet active in Shift 1 (voltage, economics, planning accuracy) are shown as "N/A — available from Shift X".

### 7.10 Save System

JSON save file in `saves/campaign.json`. Save after every shift debrief. Auto-save — player never manually saves. One active save slot.

```json
{
    "version": 1,
    "difficulty": "OPERATOR",
    "current_shift": 2,
    "carry_forward": {
        "reservoir_levels": {"KELM": 0.71, "BARR": 0.68, "DUNM": 0.55},
        "unit_commitment": {"RVSD-1": "ONLINE", "RVSD-2": "OFFLINE", ...}
    },
    "cumulative_score": {...}
}
```

**Validation — Gate 1:** Full Shift 1 playthrough three times from main menu to debrief:
1. Normal play — respond to RVSD-2 trip, win the shift
2. Deliberate fail — ignore trip, confirm fail screen and retry
3. Fast-forward test — run at VERY FAST, confirm auto-forcing interrupts correctly

Does Shift 1 feel like the game you want to make? If yes, proceed. If no, fix it here.

---

## Stage 8 — Shifts 2 Through 4

**Objective:** Complete Shifts 2-4. Each shift adds exactly the mechanics in the unlock table. No Phase 1 yet.

### 8.1 Shift 2 — Morning Ramp

New Phase 2 mechanics:
- Unit start command (startup sequence, cold start timer, progress arc animation)
- Unit stop command (shutdown sequence)
- Ramp rate visualisation (small rate indicator on unit output bars)
- Demand forecast curve displayed in instrument strip
- Renewable forecast with uncertainty band (shaded area above/below forecast line)

Scripted event: solar 30% below forecast at 06:45, demand faster than forecast. Player must manually start a CCGT unit before the gap becomes a crisis.

### 8.2 Shift 3 — First Congestion

Grid expands to 20 nodes. New Phase 2 mechanics:
- Congestion alarm trigger (line loading thresholds in constants)
- Redispatch wizard (select congested line → wizard suggests which unit to adjust)
- Nuclear unit (HART) always online, minimal ramp

Scripted event: unexpected wind ramp overloads L03. System frequency fine — local congestion only.

### 8.3 Shift 4 — Cascade Risk

New Phase 2 mechanics:
- N-1 security indicator (single risk number in instrument strip)
- Cascade risk display (which lines trip next if one more fails)
- Manual load shedding (shed load substation via context menu)
- Island detection display (isolated sections in dim colour)
- Blackout zone rendering (dark canvas fill, no flow animation)

Scripted event: solar collapse + L05 protection fault compound event at 17:50. Player must shed load deliberately to prevent cascade.

**Validation:** Each shift playable end-to-end. Scripted events fire. New mechanics functional. Carry-forward state (unit commitment) persists correctly.

---

## Stage 9 — Full Grid and Phase 1 Introduction (Shift 5)

**Objective:** 32-node full grid. Phase 1 planning interface introduced for the first time.

### 9.1 Full Grid Activation

All 32 nodes active. INTC-N and INTC-S interconnectors visible at canvas edges with real-time flow display.

### 9.2 Phase 1 Planning Screen

Write `src/gameplay/phase1.py` — the most complex UI in the game.

Full planning workflow implemented:
- Forecast review (demand curve + wind/solar with uncertainty bands)
- Unit commitment (toggle online/offline, set scheduled start times)
- Reserve allocation (target output vs rated — spinning reserve display)
- Interconnector scheduling (hourly import/export by hour slider)
- Shift preview screen (risk indicators per hour, reservoir end-levels, cost estimate)

Both mouse (click, drag sliders) and keyboard (Tab navigation, arrow keys for values, Enter to confirm) work throughout.

### 9.3 Forecast Mode Simulation

Implement `run_forecast_mode()` — deterministic fast evaluation of a proposed schedule for the shift preview. Must complete in < 500ms for a full 12-hour schedule.

### 9.4 Shift Preview Risk Indicators

Risk indicators must be honest predictors of real Phase 2 conditions:
- RED: reserve margin < 8% — this hour is genuinely dangerous
- ORANGE: congestion risk on specific line — this line may overload
- GREEN: this hour looks secure

Player learns to trust indicators because they accurately predict what happens in Phase 2.

### 9.5 Shift 5 Scripted Event

INTC-N trips at 09:30 sim time. Consequence depends entirely on Phase 1 decisions. First event directly caused by player's plan.

**Validation — Gate 2:** Complete Shift 5 twice with different planning strategies. Conservative plan handles interconnector trip comfortably. Aggressive plan (heavy import reliance) causes frequency crisis. The connection between planning and real-time must be visceral and clear.

---

## Stage 10 — Shifts 6 Through 10

**Objective:** All remaining shifts and mechanics. Full campaign playable.

### 10.1 Shift 6 — Island Management

Phase 1: basic hydro reservoir scheduling, N-1 security check in preview.
Phase 2: tie-line controls, island restoration sequence UI, restoration mode.

Scripted event: relay maloperation trips L03 and L07 simultaneously. Northern section islands. Player must stabilise main grid, identify black-start unit, re-energise in sequence.

### 10.2 Shift 7 — Voltage and Reactive

Phase 1: reactive reserve planning, voltage-sensitive load identification, capacitor scheduling.
Phase 2: VSI halos on substations, per-bus voltage labels, Q setpoint controls, shunt capacitor switching, Q limit indicators, voltage collapse warning display.

The voltage solver has been running since Stage 3. This stage connects it to the display and player controls for the first time.

Scripted event: heavy loading causes progressive voltage sag on LD02. Generator hits Q_max. Player must switch capacitor bank and redispatch reactive within 4 sim minutes.

### 10.3 Shift 8 — Pumped Storage

Phase 1: pump/generate/idle scheduling by hour, reservoir trajectory display, downstream dependency.
Phase 2: real-time mode switching, reservoir level display, penstock flow animation.

Scripted event: wind collapse at 14:30. Whether player can respond depends entirely on reservoir positioning in Phase 1.

### 10.4 Shift 9 — Full Hydro-Thermal Coordination

Phase 1: full merit order with CO2 costs, multi-reservoir optimisation, cascade sequencing, price-based interconnector scheduling.
Phase 2: market cost ticker, cascade dependency arrows on canvas.

Scripted event: INTC-S trips during peak import. Tests full coordination of domestic reserve.

### 10.5 Shift 10 — Campaign Finale

No new mechanics. The Storm compound scenario as specified in GAMEPLAY_REFERENCE.md. Eight scripted events across the 12-hour window. Tests all ten shifts' worth of learning simultaneously.

**Validation — Gate 3:** Full campaign playthrough on OPERATOR difficulty. All 10 shifts complete. External playtest — at least one person who does not know power systems should play Shifts 1-4 and report what confused them.

---

## Stage 11 — Scoring and Campaign Completion

**Objective:** Campaign score, completion screen, and final narrative elements.

### 11.1 Scoring Engine

Write `src/gameplay/scoring.py` tracking all five dimensions across all shifts:

```
Frequency management   25%   time within ±0.2Hz, weighted by shift difficulty
Network security       25%   overloads, trips, blackouts (penalty-based)
Voltage management     20%   time within limits (Shifts 7-10 only)
Economics              15%   total cost vs target
Planning accuracy      15%   Phase 1 risk prediction accuracy (Shifts 5-10)
```

Single percentage, letter grade A/B/C/D/F.

### 11.2 Campaign Completion Screen

After Shift 10 debrief: full breakdown by shift and dimension, letter grade, final logbook entry with "Watch concluded" ritual, motto attribution — R. Ferris, NECC, 1994. Fade to black.

### 11.3 Carry-Forward Validation

Test all edge cases:
- Reservoir at 0% at shift end
- Unit tripped at shift end (starts repaired next shift)
- All line states reset healthy between shifts
- Save file correctly stores and restores all carry-forward state

---

## Stage 12 — PyInstaller Build and Steam Preparation

**Objective:** Clean distributable build. Find all packaging problems now, not after polish.

### 12.1 PyInstaller Spec File

Write `gridcom.spec`:

```python
a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    hiddenimports=[
        'numpy.core._methods',
        'numpy.lib.format',
    ],
    datas=[
        ('src/assets/fonts/', 'assets/fonts/'),
        ('src/assets/sounds/', 'assets/sounds/'),
    ],
)
```

Single-folder distribution (not one-file). Easier to debug. Steam doesn't care about folder count.

### 12.2 Build and Clean Machine Test

Run PyInstaller. Copy dist folder to a machine without Python installed (or a clean VM). Verify:
- Game launches without Python
- All fonts load (resource_path working)
- All sounds load
- Debug modes still toggleable via constants (rebuild required to change)
- No antivirus false positives

Fix any packaging issues before proceeding.

### 12.3 Steam Setup

- Create Steam developer account and app entry if not already done
- Configure SteamPipe depot
- Upload first build (pre-release, not publicly visible)
- Verify upload and download process works end-to-end

**Validation — Gate 4:** Clean machine build passes. Steam upload succeeds. Game downloads and runs from Steam on a second machine.

---

## Stage 13 — Freeplay Mode

**Objective:** Post-campaign sandbox mode.

Freeplay uses the full 32-node grid with parameterisable session. Player configures:
- Demand level (50-120% of peak)
- Renewable penetration (0-70%)
- Interconnector availability (none / north only / south only / both)
- Event frequency (none / low / medium / high)
- Starting reservoir levels (low / medium / high / custom)
- Session duration (8 or 12 simulated hours)

No campaign score. No scripted events. No carry-forward. Each freeplay session is self-contained. Available from main menu after campaign completion.

---

## Stage 14 — Polish and Non-Critical Improvements

**Everything in this stage was deliberately deferred.** None of these items block gameplay. All of them improve the experience. Addressed in order of player-facing impact.

### 14.1 Audio

Load all sounds via `resource_path('assets/sounds/...')`:

- `alarm_critical.wav` — sharp, attention-grabbing (crisis auto-force trigger)
- `alarm_warning.wav` — softer (warning threshold crossed)
- `alarm_ack.wav` — brief confirmation tone (alarm acknowledged)
- `unit_trip.wav` — mechanical thud (generation unit trips)
- `ambient_room.wav` — very quiet ventilation hum, played continuously in Phase 2

All audio optional — game fully playable with system sound muted.

### 14.2 Tutorial Overlay System

Optional first-playthrough hints:
- Arrow pointing to frequency display with "This is the grid's heartbeat"
- Arrow pointing to spinning reserve with "This is your buffer"
- Hint on first alarm: "Press A to acknowledge"
- Hints dismissable individually or all at once
- Does not interrupt gameplay — purely additive overlay

### 14.3 Visual Polish

- Line trip transition: colour fades to grey over 200ms (not instant)
- Unit startup arc: thin clockwise progress arc around unit square during STARTING state
- Context panel fade-in: 80ms alpha fade on panel appear
- Screen border crisis flash: smooth pulse rather than binary on/off
- Voltage halos: semi-transparent, smooth radius transition as VSI changes

### 14.4 Alarm Enhancements

- Click alarm in feed → full detail panel (cause, element, recommended action)
- Alarm history scrollback (beyond 8 visible rows)
- Alarm filter by priority (CRIT only / CRIT+WARN / ALL)

### 14.5 Performance Overlay

In-game debug performance display (separate from `DEBUG_DISPLAY`):
- Frame time (ms) and FPS
- Simulation tick time (ms)
- B matrix rebuild count this shift
- Useful for identifying performance issues on low-end hardware

Toggled by F12 key. Not visible in normal play.

### 14.6 Keyboard Shortcut Reference Card

Press `?` at any time during Phase 2 to display an overlay showing all keyboard shortcuts available in the current shift (only unlocked shortcuts shown).

### 14.7 Colour-Blind Accessibility Mode

Replace colour-only status indicators with colour + symbol combinations:
- Line overload: red colour + dashed line pattern
- Unit fault: red border + X symbol in unit square
- Voltage warning: coloured halo + V label
- Toggled in main menu settings

### 14.8 Localisation Preparation

Extract all display strings to `src/data/strings.py`. No hardcoded display text anywhere else. Does not translate — just prepares the structure so future translation is possible without code changes.

### 14.9 Steam Integration

- Achievements: 12 defined
  - One per shift completed (10 achievements)
  - "Unread" — complete any shift with no alarms requiring acknowledgement
  - "Dispatcher Grade 1" — complete full campaign on DISPATCHER difficulty
- Steam Cloud save: sync `saves/campaign.json` across machines
- Rich presence: shows current shift number and campaign rating in Steam friend list

### 14.10 Store Assets and Manual

- Steam store page: screenshots of each major mechanic (frequency event, congestion redispatch, Phase 1 planning, voltage management, campaign debrief)
- Short gameplay trailer
- In-game manual accessible from main menu — covers all mechanics with diagrams
- Steam capsule artwork consistent with SCADA terminal aesthetic

---

## Critical Path Summary

```
STAGE 0   Project foundation — structure, constants, palette, helpers, debug modes
          ↓
STAGE 1   Network data model — all buses, lines, fleet, demand profile
          ↓
STAGE 2   Static grid renderer — layout validated visually, positions locked
          ↓
STAGE 3   Simulation engine — physics validated in console, all tests pass
          ↓
STAGE 4   Instrument strip — panels validated with test data
          ↓
STAGE 5   Simulation → display — live grid on screen, crisis forcing works
          ↓
STAGE 6   Player interaction — all Shift 1 controls, mouse + keyboard
          ↓
STAGE 7   Campaign shell — Shift 1 fully playable end-to-end
          ↓           ← GATE 1: Does Shift 1 feel right?
STAGE 8   Shifts 2-4 — Phase 2 mechanic unlock sequence complete
          ↓
STAGE 9   Phase 1 planning + Shift 5 — planning interface introduced
          ↓           ← GATE 2: Does planning feel connected to real-time?
STAGE 10  Shifts 6-10 — all mechanics, full campaign
          ↓           ← GATE 3: External playtest. Is the campaign enjoyable?
STAGE 11  Campaign score and completion — scoring, debrief, ending
          ↓
STAGE 12  PyInstaller build + Steam preparation
          ↓           ← GATE 4: Clean machine test passes. Steam upload works.
STAGE 13  Freeplay mode
          ↓
STAGE 14  Polish and non-critical improvements
          ↓
          RELEASE CANDIDATE
```

---

## Go/No-Go Gates

**Gate 1 — After Stage 7:**
Does Shift 1 feel like the game you want to make? Is the frequency crisis tense? Is the SCADA display atmospheric? Is the RVSD-2 trip event dramatic? If anything is wrong here, fix it before Shifts 2-10 are built on top of it.

**Gate 2 — After Stage 9:**
Does the Phase 1 → Phase 2 connection feel real? Can you feel your planning decisions in the real-time phase? The interconnector trip event must feel like a consequence of your plan, not an arbitrary event. If the connection is weak, the two-phase design needs work before Shifts 6-10 are built.

**Gate 3 — After Stage 10:**
Is the full campaign enjoyable end-to-end? Do the difficulty curves feel right? Does the carry-forward state create meaningful continuity? Mandatory external playtest at this gate — at least one player who does not know power systems.

**Gate 4 — After Stage 12:**
Does the packaged build run on a clean machine? Does the Steam upload process work end-to-end? Do not begin Stage 14 polish until this gate passes. Polish on a build that doesn't package is wasted effort.

---

*Document version 1.1 — development roadmap for GRIDCOM : Grid Control Terminal. Incorporates: src/ directory structure, constants.py as primary constants store, simulation and display debug modes, 16:9 auto-scaling resolution, assets/sounds/ and assets/fonts/ directories, mouse and keyboard dual input throughout, fully rendered game pipeline. Cross-reference GRID_SIMULATION_MECHANICS.md, GRID_TOPOLOGY_AND_DISPLAY.md, GAMEPLAY_REFERENCE.md, and GRIDCOM_INTRO_STORY.md for full specification detail.*
