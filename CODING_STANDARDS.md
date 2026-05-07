# CODING_STANDARDS.md — GRIDCOM Python Conventions
### Reference document for Claude Code — read before writing any code.

---

## Python Version

Python 3.12.7. Use all modern syntax freely:
- `X | Y` union types (not `Union[X, Y]`)
- `match` statements where appropriate
- `@dataclass` with `slots=True` for performance-critical data classes
- `f-strings` exclusively (no `.format()` or `%` formatting)
- `pathlib.Path` for any path manipulation beyond `resource_path()`

---

## File Header

Every source file begins with a module docstring:

```python
"""
src/simulation/loadflow.py

DC load flow solver for the GRIDCOM transmission network.
Solves the linear system θ = B⁻¹ × P using numpy.
Provides line flows, loading percentages, and bus voltage angles.

See GRID_SIMULATION_MECHANICS.md Section 4 for physics detail.
See SIMULATION_API.md for the public interface contract.
"""
```

Format:
- Line 1: relative path from project root
- Line 3: one-sentence description of what this module does
- Lines 4+: what it provides or how it fits into the architecture
- Final line: reference to relevant design document(s)

---

## Imports

Import order (one blank line between each group):

```python
# 1. Standard library
import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque
from typing import TYPE_CHECKING

# 2. Third-party
import numpy as np
import pygame
import pygame.freetype

# 3. Project — simulation layer
from simulation.constants import F_NOMINAL, S_BASE, TRIP_DELAY_S
from simulation.grid import Grid, Bus, Line

# 4. Project — display layer (only in display modules)
from display.palette import COL_400KV, COL_ALARM_CRIT

# 5. Project — utils
from utils.helpers import resource_path
```

Rules:
- Never use `from module import *`
- Never use implicit relative imports
- Always use explicit `from simulation.constants import X` — never `import constants`
- `TYPE_CHECKING` guard for circular import avoidance where needed

---

## Type Hints

All public functions and methods must have complete type hints. Private functions (`_name`) should have type hints unless trivially obvious.

```python
# Good — complete type hints
def compute_line_loading(
    flows: dict[str, float],
    ratings: dict[str, float]
) -> dict[str, float]:
    ...

# Good — Python 3.12 union syntax
def get_element_at(
    mouse_pos: tuple[int, int],
    grid: Grid
) -> tuple[str, str] | None:
    ...

# Bad — missing type hints
def compute_line_loading(flows, ratings):
    ...
```

Type aliases for domain clarity:

```python
# Define at module top, use throughout
BusLabel = str          # 4-char bus identifier: 'MDBY', 'CNTR'
LineLabel = str         # line identifier: 'L01', 'L02'
UnitLabel = str         # unit identifier: 'RVSD-1', 'HART-2'
LoadingPct = float      # 0.0 to 100.0+ (percent)
VoltagePU = float       # per-unit voltage: normally 0.95 to 1.05
AngleRad = float        # bus voltage angle in radians
PowerMW = float         # active power in MW
ReactiveMVAr = float    # reactive power in MVAr
```

---

## Docstrings

**Module docstring:** as shown in File Header section above.

**Class docstring:** describes purpose, key attributes, and usage:

```python
class DCLoadFlow:
    """
    DC load flow solver for the GRIDCOM transmission network.

    Solves the linear system θ = B⁻¹ × P where B is the network
    susceptance matrix and P is the net power injection vector.

    The slack bus (MDBY) provides the angle reference (θ = 0) and
    absorbs system imbalance. Its row/column is removed before solving.

    Attributes:
        slack_bus: Label of the slack bus (always 'MDBY')
        b_matrix: Reduced susceptance matrix (n-1 × n-1 numpy array)
        bus_index: Maps bus labels to matrix indices

    Usage:
        lf = DCLoadFlow(grid.get_active_buses(), grid.get_active_lines())
        theta = lf.solve(p_injections)
        flows = lf.compute_line_flows(theta)
    """
```

**Method docstring:** describes what it does, parameters, return value, and any side effects:

```python
def solve(self, p_injections: dict[BusLabel, PowerMW]) -> dict[BusLabel, AngleRad]:
    """
    Solve for bus voltage angles given net power injections.

    Args:
        p_injections: Net MW injection at each bus (generation minus load).
                      Positive = generation dominates. Negative = load dominates.
                      Must include all active buses except the slack bus.

    Returns:
        Voltage angle in radians at each non-slack bus.
        Slack bus (MDBY) angle is always 0.0 — not included in return dict.

    Raises:
        ValueError: If network is islanded (singular B matrix).
                    Call cascade.find_islands() before solving.

    Side effects:
        None. Pure function — does not modify instance state.
    """
```

---

## Error Handling

### Simulation Errors — Never Crash the Game

The simulation runs inside the game loop. Any unhandled exception in the simulation crashes the game. Use defensive patterns:

```python
def solve(self, p_injections: dict[BusLabel, PowerMW]) -> dict[BusLabel, AngleRad]:
    try:
        p_vector = self._build_injection_vector(p_injections)
        theta_vector = np.linalg.solve(self.b_matrix, p_vector)
        return self._vector_to_dict(theta_vector)
    except np.linalg.LinAlgError:
        # Singular matrix — network is islanded
        # Return zero angles — caller must check island state
        return {bus: 0.0 for bus in self.bus_index}
```

Log the error via debug output, return a safe fallback, let the game continue. The cascade detector will handle the island state.

### Display Errors — Degrade Gracefully

If a display element fails to render, skip it and continue:

```python
def draw_node_label(surface, cx, cy, label, font):
    try:
        font.render_to(surface, (cx - 10, cy + 16), label, COL_TEXT_DIM)
    except Exception:
        pass  # Label rendering failure is not fatal
```

### Asset Loading Errors — Fail Fast

Asset loading happens at startup. If a font or sound file is missing, fail immediately with a clear error message:

```python
def load_fonts() -> dict[str, pygame.freetype.Font]:
    fonts = {}
    required = {
        'mono_regular': ('assets/fonts/JetBrainsMono-Regular.ttf', 11),
        'mono_bold':    ('assets/fonts/JetBrainsMono-Bold.ttf', 28),
        'sans':         ('assets/fonts/LiberationSans-Regular.ttf', 13),
    }
    for name, (path, size) in required.items():
        full_path = resource_path(path)
        try:
            fonts[name] = pygame.freetype.Font(full_path, size)
        except FileNotFoundError:
            raise SystemExit(
                f"Required font not found: {full_path}\n"
                f"Ensure fonts are in src/assets/fonts/"
            )
    return fonts
```

---

## Numpy Conventions

### Array Construction

Always use explicit dtype when creating matrices that will be used in linear algebra:

```python
# Good
b_matrix = np.zeros((n, n), dtype=np.float64)

# Bad — implicit dtype, may cause issues
b_matrix = np.zeros((n, n))
```

### Matrix Solve

Always use `numpy.linalg.solve` (not `numpy.linalg.inv`). Solve is numerically stable; inv is not:

```python
# Good
theta = np.linalg.solve(b_reduced, p_vector)

# Bad — numerically unstable
theta = np.linalg.inv(b_reduced) @ p_vector
```

### Array Slicing for Slack Bus Removal

The slack bus is always removed before solving. Use index-based slicing:

```python
# Build full n×n matrix, then remove slack bus row/column
b_full = self._build_full_b_matrix()
slack_idx = self.bus_index[self.slack_bus]
# Remove slack row and column
mask = np.ones(n, dtype=bool)
mask[slack_idx] = False
b_reduced = b_full[np.ix_(mask, mask)]
```

### Per-Unit Conversion

All internal calculations use per-unit values on S_BASE = 1000 MVA:

```python
from simulation.constants import S_BASE

# Convert MW to per-unit for calculations
p_pu = power_mw / S_BASE

# Convert per-unit back to MW for display/output
power_mw = p_pu * S_BASE
```

---

## Pygame Conventions

### Surface Management

Never draw directly to the display surface. Always draw to the native surface:

```python
# main.py pattern
screen, native_surface, scale = init_display()

while running:
    # All drawing goes here
    renderer.render(native_surface, state)
    
    # Scale native to display — one call per frame
    scaled = pygame.transform.scale(native_surface, screen.get_size())
    screen.blit(scaled, (0, 0))
    pygame.display.flip()
```

### Coordinate System

All coordinate values in the codebase are in native 1920×1080 pixels. Never multiply by scale factors in individual draw functions — the scaling happens once in the main loop.

```python
# Good — native coordinates
pygame.draw.rect(surface, colour, pygame.Rect(100, 200, 12, 12))

# Bad — scaled coordinates in draw functions
pygame.draw.rect(surface, colour, pygame.Rect(100*scale, 200*scale, 12*scale, 12*scale))
```

### Font Rendering

Use `pygame.freetype` exclusively (not `pygame.font`):

```python
import pygame.freetype

# Render without antialiasing (hard pixel look for small sizes)
font.render_to(surface, (x, y), text, colour, None)  # None bgcolor = transparent

# Render with antialiasing (for larger heading fonts)
font.antialiased = True
font.render_to(surface, (x, y), text, colour)
```

Disable antialiasing for sizes ≤ `FONT_ANTIALIAS_THRESHOLD` (11px) from constants.

### Rect Usage

Use `pygame.Rect` for all bounding box calculations and hit detection:

```python
# Symbol hit detection
symbol_rect = pygame.Rect(cx - 6, cy - 6, 12, 12)
if symbol_rect.collidepoint(mouse_pos):
    return 'BUS', bus.label
```

### Clock and Timing

One clock in `main.py`, passed to nothing — just used for `tick()`:

```python
clock = pygame.time.Clock()
real_dt_ms = clock.tick(TARGET_FPS)  # caps frame rate, returns elapsed ms
real_dt_s = real_dt_ms / 1000.0
```

---

## Dataclasses

Use `@dataclass` for data transfer objects. Use `slots=True` for objects created frequently:

```python
@dataclass(slots=True)
class SimulationState:
    """Complete simulation snapshot for renderer consumption."""
    sim_time_min: float
    frequency_hz: float
    # ... all fields
```

Use `@dataclass(frozen=True)` for immutable configuration objects:

```python
@dataclass(frozen=True)
class ShiftSpec:
    """Immutable shift configuration — set at shift load, never modified."""
    shift_number: int
    start_hour: int
    duration_hours: int
    grid_size: int
    has_phase1: bool
```

---

## Enumerations

Use `Enum` for state machines. Use `auto()` for values that don't need specific integers:

```python
from enum import Enum, auto

class UnitState(Enum):
    OFFLINE  = auto()
    STARTING = auto()
    ONLINE   = auto()
    SHUTDOWN = auto()

class AlarmPriority(Enum):
    INFO     = auto()
    WARNING  = auto()
    CRITICAL = auto()

class SimSpeed(Enum):
    PAUSE     = 0.00
    SLOW      = 0.25
    NORMAL    = 1.00
    FAST      = 3.00
    VERY_FAST = 10.00
```

---

## Logging and Debug Output

Use the DEBUG constants from `constants.py`, never `print()` directly in production code paths:

```python
from simulation.constants import DEBUG_SIMULATION, DEBUG_EVENTS

def _apply_event(self, event: ScriptedEvent) -> None:
    # ... apply event logic
    if DEBUG_EVENTS:
        print(f"[EVENT] t={self.sim_time_min:.1f}min "
              f"{event.event_type} → {event.target}: {event.description}")
```

Debug output format:
```
[SIMULATION] t=040.00min f=49.871Hz gen=3842MW load=3920MW imb=-78MW L_max=71.2% V_min=0.964pu
[EVENT]      t=040.00min UNIT_TRIP → RVSD-2: Riverside #2 overcurrent protection
[CASCADE]    t=041.50min LINE_TRIP → L03: sustained overload 108% for 61.2s
[ISLAND]     t=041.51min Island detected: {NRTH, BARR, KELM, WNCN} — non-viable
```

---

## Testing

Test functions live in `tests/test_simulation.py`. All test functions are standalone — no test framework required, just `python tests/test_simulation.py`.

Pattern:

```python
def test_loadflow_solves() -> bool:
    """
    Verify DC load flow produces physically reasonable results
    on a 3-bus test network with known analytical solution.
    """
    print("test_loadflow_solves...", end=" ")
    try:
        # Setup
        # ... create minimal test network
        
        # Execute
        result = lf.solve(p_injections)
        
        # Assert
        assert abs(result['BUS_A'] - expected_angle) < 1e-6, \
            f"Expected angle {expected_angle:.6f}, got {result['BUS_A']:.6f}"
        
        print("PASS")
        return True
    except AssertionError as e:
        print(f"FAIL — {e}")
        return False
    except Exception as e:
        print(f"ERROR — {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    results = [
        test_grid_loads(),
        test_loadflow_solves(),
        test_unit_trip(),
        test_cascade(),
        test_island_detect(),
        test_shift1_nominal(),
        test_shift1_with_event(),
    ]
    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    if passed < total:
        exit(1)
```

---

## Code Review Checklist

Before accepting any code from Claude Code, verify:

```
□ Module docstring present and accurate
□ All public functions have complete type hints
□ All public functions have docstrings with Args/Returns/Raises
□ No hardcoded numbers (all in constants.py)
□ No hardcoded colours (all in palette.py)
□ No direct file paths (all via resource_path())
□ No imports of scipy or unlisted libraries
□ numpy.linalg.solve used (not inv)
□ Error handling present on simulation code paths
□ Debug output uses DEBUG_ constants, not bare print()
□ py_compile passes: python -m py_compile src/[file].py
```
