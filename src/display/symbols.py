"""
src/display/symbols.py

Procedural symbol drawing for the GRIDCOM schematic canvas.
All symbols are drawn with pygame draw calls — no sprite sheets.

Every function draws to a supplied pygame Surface at a given (cx, cy) centre
position. Coordinates are in native 1920×844 canvas pixels.

See GRID_TOPOLOGY_AND_DISPLAY.md sections 3 and 4 for visual specification.
See display/palette.py for all colour constants.
"""

import pygame

from simulation.constants import FONT_SIZE_OVERLAY
from display.palette import (
    COL_BUS_400KV, COL_BUS_220KV, COL_BUS_150KV, COL_BUS_60KV,
    COL_BUS_BLACKED, COL_BUS_SELECTED,
    COL_UNIT_COAL, COL_UNIT_CCGT, COL_UNIT_NUCLEAR,
    COL_UNIT_HYDRO, COL_UNIT_HYDRO_PUMP, COL_UNIT_WIND, COL_UNIT_SOLAR,
    COL_UNIT_ONLINE, COL_UNIT_OFFLINE, COL_UNIT_STARTING,
    COL_UNIT_SHUTDOWN, COL_UNIT_TRIPPED, COL_UNIT_BORDER,
    COL_INTC_IMPORT, COL_INTC_EXPORT, COL_INTC_IDLE,
    COL_LINE_HYDRAULIC, COL_LOAD_SUB,
    COL_TEXT_PRIMARY, COL_TEXT_SECONDARY, COL_TEXT_DIM,
    COL_SELECTION,
)

# Symbol size constants
BUS_SIZE:   int = 12   # substation square side length (px)
UNIT_SIZE:  int = 12   # generation unit square side length (px)
UNIT_GAP:   int = 2    # gap between unit squares in a multi-unit station
HALF_BUS:   int = BUS_SIZE // 2
HALF_UNIT:  int = UNIT_SIZE // 2

# Unit type → fill colour
_UNIT_TYPE_COLOUR: dict[str, tuple] = {
    'COAL':      COL_UNIT_COAL,
    'CCGT':      COL_UNIT_CCGT,
    'NUCLEAR':   COL_UNIT_NUCLEAR,
    'HYDRO':     COL_UNIT_HYDRO,
    'HYDRO_PUMP':COL_UNIT_HYDRO_PUMP,
    'HYDRO_ROR': COL_UNIT_HYDRO,
    'WIND':      COL_UNIT_WIND,
    'SOLAR':     COL_UNIT_SOLAR,
}

# Voltage level → bus colour
_VOLTAGE_COLOUR: dict[float, tuple] = {
    400.0: COL_BUS_400KV,
    220.0: COL_BUS_220KV,
    150.0: COL_BUS_150KV,
    60.0:  COL_BUS_60KV,
}


# ─────── TRANSMISSION SUBSTATION ─────────────────────────────────────────────

def draw_substation(
    surf: pygame.Surface,
    cx: int,
    cy: int,
    voltage_kv: float,
    blacked: bool = False,
    selected: bool = False,
) -> None:
    """
    Draw a transmission substation symbol: plain square with filled interior.

    Args:
        surf:       Target surface (canvas).
        cx, cy:     Centre position of the symbol.
        voltage_kv: Nominal voltage — determines colour.
        blacked:    True if bus is in a blackout zone.
        selected:   True if this element is selected.
    """
    col = COL_BUS_BLACKED if blacked else _VOLTAGE_COLOUR.get(voltage_kv, COL_BUS_220KV)
    border_col = COL_SELECTION if selected else col

    x = cx - HALF_BUS
    y = cy - HALF_BUS

    if not blacked:
        # Interior fill at 20% brightness of voltage colour
        fill_col = _dim(col, 0.20)
        pygame.draw.rect(surf, fill_col, (x + 2, y + 2, BUS_SIZE - 4, BUS_SIZE - 4))

    # Square border — 2px
    pygame.draw.rect(surf, border_col, (x, y, BUS_SIZE, BUS_SIZE), 2)


def draw_load_substation(
    surf: pygame.Surface,
    cx: int,
    cy: int,
    blacked: bool = False,
    selected: bool = False,
) -> None:
    """
    Draw a load substation symbol: square with downward triangle inside.
    Always uses 60kV colour.
    """
    col = COL_BUS_BLACKED if blacked else COL_BUS_60KV
    border_col = COL_SELECTION if selected else col

    x = cx - HALF_BUS
    y = cy - HALF_BUS

    pygame.draw.rect(surf, border_col, (x, y, BUS_SIZE, BUS_SIZE), 1)

    if not blacked:
        inset = 2
        tx = x + inset
        ty = y + inset
        tw = BUS_SIZE - inset * 2
        th = BUS_SIZE - inset * 2
        dim_col = _dim(COL_LOAD_SUB, 0.70)
        pts = [
            (tx,           ty),            # top-left
            (tx + tw,      ty),            # top-right
            (tx + tw // 2, ty + th),       # apex (bottom)
        ]
        pygame.draw.polygon(surf, dim_col, pts)


# ─────── GENERATION UNIT SQUARE ──────────────────────────────────────────────

def draw_unit_square(
    surf: pygame.Surface,
    cx: int,
    cy: int,
    unit_type: str,
    unit_state: str,
    output_fraction: float = 0.0,
    selected: bool = False,
    blink_on: bool = True,
) -> None:
    """
    Draw a single generation unit square with state-dependent border and output bar.

    Args:
        surf:             Target surface.
        cx, cy:           Centre of the unit square.
        unit_type:        'COAL', 'CCGT', 'NUCLEAR', 'HYDRO', 'HYDRO_PUMP',
                          'HYDRO_ROR', 'WIND', or 'SOLAR'.
        unit_state:       'ONLINE', 'OFFLINE', 'STARTING', 'SHUTDOWN'.
        output_fraction:  current_mw / rated_mw, clamped 0–1.
        selected:         True if this unit is selected.
        blink_on:         Current blink phase (True = visible, False = hidden).
                          Used for STARTING and TRIPPED states.
    """
    type_col = _UNIT_TYPE_COLOUR.get(unit_type, COL_UNIT_WIND)
    x = cx - HALF_UNIT
    y = cy - HALF_UNIT

    # Fill colour and border based on state
    if unit_state == 'ONLINE':
        fill_col   = _dim(type_col, 0.45)
        border_col = COL_UNIT_ONLINE
    elif unit_state == 'STARTING':
        fill_col   = _dim(type_col, 0.30)
        border_col = COL_UNIT_STARTING if blink_on else COL_UNIT_OFFLINE
    elif unit_state == 'SHUTDOWN':
        fill_col   = _dim(type_col, 0.25)
        border_col = COL_UNIT_SHUTDOWN
    else:  # OFFLINE or unknown
        fill_col   = _dim(type_col, 0.18)
        border_col = COL_UNIT_BORDER

    pygame.draw.rect(surf, fill_col, (x, y, UNIT_SIZE, UNIT_SIZE))
    border_w = 2 if selected else 1
    border_c = COL_SELECTION if selected else border_col
    pygame.draw.rect(surf, border_c, (x, y, UNIT_SIZE, UNIT_SIZE), border_w)

    # Output bar — bottom-aligned, height proportional to output
    if unit_state == 'ONLINE' and output_fraction > 0.0:
        interior = UNIT_SIZE - 2   # inside the border
        bar_h = max(1, int(interior * min(output_fraction, 1.0)))
        bar_y = y + UNIT_SIZE - 1 - bar_h
        bar_col = _brighten(type_col, 1.5)
        pygame.draw.rect(surf, bar_col, (x + 1, bar_y, interior, bar_h))


def draw_station_collector(
    surf: pygame.Surface,
    unit_positions: list[tuple[int, int]],
    bus_cx: int,
    bus_cy: int,
    voltage_kv: float,
) -> None:
    """
    Draw the collector line connecting multiple unit squares and feeder to bus.

    For a single unit, draws just the feeder line from unit bottom to bus.
    For multiple units, draws a horizontal collector at unit bottoms then
    a single vertical feeder drop to the bus symbol.

    Args:
        unit_positions:  List of (cx, cy) for each unit square.
        bus_cx, bus_cy:  Centre of the host substation bus symbol.
        voltage_kv:      Determines line colour.
    """
    col = _dim(_VOLTAGE_COLOUR.get(voltage_kv, COL_BUS_220KV), 0.6)

    if not unit_positions:
        return

    # Exit from the unit side that faces the bus
    unit_cy = unit_positions[0][1]
    if bus_cy < unit_cy:
        exits = [(ux, uy - HALF_UNIT) for ux, uy in unit_positions]
    else:
        exits = [(ux, uy + HALF_UNIT) for ux, uy in unit_positions]

    if len(exits) == 1:
        ex, ey = exits[0]
        # Orthogonal feeder: vertical first, then horizontal
        if ey != bus_cy:
            pygame.draw.line(surf, col, (ex, ey), (ex, bus_cy), 1)
        if ex != bus_cx:
            pygame.draw.line(surf, col, (ex, bus_cy), (bus_cx, bus_cy), 1)
    else:
        # Horizontal collector bar across all exit points
        leftmost  = min(ex for ex, _ in exits)
        rightmost = max(ex for ex, _ in exits)
        coll_y    = exits[0][1]
        pygame.draw.line(surf, col, (leftmost, coll_y), (rightmost, coll_y), 1)
        # Orthogonal feeder from collector midpoint to bus
        mid_x = (leftmost + rightmost) // 2
        if coll_y != bus_cy:
            pygame.draw.line(surf, col, (mid_x, coll_y), (mid_x, bus_cy), 1)
        if mid_x != bus_cx:
            pygame.draw.line(surf, col, (mid_x, bus_cy), (bus_cx, bus_cy), 1)


# ─────── INTERCONNECTOR MARKER ───────────────────────────────────────────────

def draw_interconnector(
    surf: pygame.Surface,
    cx: int,
    cy: int,
    flow_mw: float,
    label: str,
    font: pygame.freetype.Font,
) -> None:
    """
    Draw an interconnector terminus: horizontal line ending in filled chevron.

    Args:
        cx, cy:   Centre of the chevron tip (right edge of canvas).
        flow_mw:  Current flow (+ve = import, −ve = export, 0 = idle).
        label:    Short label shown after the chevron (e.g. 'INTC-N').
        font:     freetype font for the label.
    """
    if flow_mw > 10.0:
        col = COL_INTC_IMPORT
    elif flow_mw < -10.0:
        col = COL_INTC_EXPORT
    else:
        col = COL_INTC_IDLE

    # Horizontal stub line
    line_len = 40
    pygame.draw.line(surf, col, (cx - line_len, cy), (cx, cy), 2)

    # Chevron pointing right
    chev_w = 8
    chev_h = 6
    pts = [
        (cx - chev_w, cy - chev_h),
        (cx,          cy),
        (cx - chev_w, cy + chev_h),
    ]
    pygame.draw.polygon(surf, col, pts)

    # Flow label
    flow_str = f'{flow_mw:+.0f}MW' if abs(flow_mw) > 1.0 else '0MW'
    font.render_to(surf, (cx - line_len, cy - 14), label, COL_TEXT_SECONDARY, size=FONT_SIZE_OVERLAY)
    font.render_to(surf, (cx - line_len, cy + 4),  flow_str, col, size=FONT_SIZE_OVERLAY)


# ─────── HYDRAULIC CONNECTOR ─────────────────────────────────────────────────

def draw_hydraulic_connector(
    surf: pygame.Surface,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> None:
    """
    Draw a dashed hydraulic penstock/cascade connector between two points.
    Not an electrical connection — display only.
    """
    _draw_dashed_line(surf, COL_LINE_HYDRAULIC, (x1, y1), (x2, y2),
                      dash=5, gap=4, width=1)


# ─────── TRANSMISSION LINE ───────────────────────────────────────────────────

def draw_transmission_line(
    surf: pygame.Surface,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    voltage_kv: float,
    loading_pct: float = 0.0,
    tripped: bool = False,
    blink_on: bool = True,
) -> None:
    """
    Draw a transmission line with voltage-appropriate style and loading colour.

    400kV: single 4px line.
    220kV: single 3px line.
    150kV: single 2px line.
    60kV:  dashed 1px line.

    Args:
        loading_pct: 0–200+. Determines colour override above 60%.
        tripped:     If True, draw in tripped (dead) style.
        blink_on:    Blink phase — used when loading > 100%.
    """
    from display.palette import (
        COL_400KV, COL_220KV, COL_150KV, COL_60KV,
        COL_LINE_TRIPPED, COL_LOAD_WARN, COL_LOAD_HIGH, COL_LOAD_CRIT,
    )

    if tripped:
        # Route tripped dashed lines orthogonally (vertical first, then horizontal)
        bx, by = x1, y2
        if y1 != y2:
            _draw_dashed_line(surf, COL_LINE_TRIPPED, (x1, y1), (bx, by), dash=6, gap=4, width=1)
        if x1 != x2:
            _draw_dashed_line(surf, COL_LINE_TRIPPED, (bx, by), (x2, y2), dash=6, gap=4, width=1)
        return

    # Determine colour from loading
    base_col = {
        400.0: COL_400KV,
        220.0: COL_220KV,
        150.0: COL_150KV,
        60.0:  COL_60KV,
    }.get(voltage_kv, COL_220KV)

    if loading_pct > 100.0:
        col = COL_LOAD_CRIT if blink_on else base_col
    elif loading_pct >= 95.0:
        col = COL_LOAD_CRIT
    elif loading_pct >= 80.0:
        col = _blend(COL_LOAD_WARN, COL_LOAD_HIGH, (loading_pct - 80.0) / 15.0)
    elif loading_pct >= 60.0:
        col = _blend(base_col, COL_LOAD_WARN, (loading_pct - 60.0) / 20.0)
    else:
        col = base_col

    # Route: vertical first, then horizontal
    bx, by = x1, y2
    if y1 != y2:
        _draw_line_segment(surf, x1, y1, bx, by, voltage_kv, col)
    if x1 != x2:
        _draw_line_segment(surf, bx, by, x2, y2, voltage_kv, col)


def _draw_line_segment(
    surf: pygame.Surface,
    x1: int, y1: int,
    x2: int, y2: int,
    voltage_kv: float,
    col: tuple,
) -> None:
    """Draw one styled orthogonal segment. No routing logic here."""
    if voltage_kv == 400.0:
        pygame.draw.line(surf, col, (x1, y1), (x2, y2), 4)
    elif voltage_kv == 220.0:
        pygame.draw.line(surf, col, (x1, y1), (x2, y2), 3)
    elif voltage_kv == 150.0:
        pygame.draw.line(surf, col, (x1, y1), (x2, y2), 2)
    else:  # 60kV
        _draw_dashed_line(surf, col, (x1, y1), (x2, y2), dash=3, gap=3, width=1)


# ─────── PRIVATE HELPERS ─────────────────────────────────────────────────────

def _dim(col: tuple, factor: float) -> tuple:
    """Multiply RGB components by factor (darkening)."""
    return (
        min(255, int(col[0] * factor)),
        min(255, int(col[1] * factor)),
        min(255, int(col[2] * factor)),
    )


def _brighten(col: tuple, factor: float) -> tuple:
    """Multiply RGB components by factor (brightening), clamped to 255."""
    return (
        min(255, int(col[0] * factor)),
        min(255, int(col[1] * factor)),
        min(255, int(col[2] * factor)),
    )


def _blend(a: tuple, b: tuple, t: float) -> tuple:
    """Linear interpolation between colours a and b at parameter t (0–1)."""
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _draw_dashed_line(
    surf: pygame.Surface,
    col: tuple,
    start: tuple,
    end: tuple,
    dash: int,
    gap: int,
    width: int,
) -> None:
    """Draw a dashed line between start and end."""
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length = max(1, (dx * dx + dy * dy) ** 0.5)
    ux = dx / length
    uy = dy / length

    pos = 0.0
    while pos < length:
        seg_end = min(pos + dash, length)
        sx = int(x1 + ux * pos)
        sy = int(y1 + uy * pos)
        ex = int(x1 + ux * seg_end)
        ey = int(y1 + uy * seg_end)
        pygame.draw.line(surf, col, (sx, sy), (ex, ey), width)
        pos += dash + gap
