"""
src/display/canvas.py

GridCanvas: draws the full 1920×844 grid schematic onto a pygame Surface.

Rendering layers (bottom to top):
  0. Canvas background fill
  1. 60kV load lines
  2. 150kV lines
  3. 220kV lines
  4. 400kV lines
  5. Hydraulic connectors (dashed, non-electrical)
  6. Substation symbols
  7. Generation unit squares + collector lines
  8. Interconnector markers
  9. Node labels

All coordinates are in native 1920×844 canvas pixels.

See GRID_TOPOLOGY_AND_DISPLAY.md for visual specification.
"""

from __future__ import annotations

import pygame
import pygame.freetype

from data.topology import (
    BUSES, LINES, INTERCONNECTOR_POSITIONS,
    get_buses_by_shift, get_lines_by_shift,
    Bus, Line,
)
from data.fleet import UNITS, STATION_POSITIONS, get_units_at_bus, get_station_position
from display.palette import (
    COL_BACKGROUND,
    COL_TEXT_PRIMARY,
)
from display.symbols import (
    draw_substation, draw_load_substation,
    draw_unit_square, draw_station_collector,
    draw_transmission_line, draw_hydraulic_connector,
    draw_interconnector,
    UNIT_SIZE, UNIT_GAP, PARALLEL_LINE_OFFSET_PX, HALF_BUS,
    get_port_point,
    _draw_dashed_line,
)
from display.palette import COL_LINE_TRIPPED, COL_LINE_HYDRAULIC
from display.geometry import point_segment_dist
from data.layout_override import get_label_anchor
from simulation.constants import CANVAS_HEIGHT, FONT_SIZE_LABEL, FONT_SIZE_PANEL, NATIVE_WIDTH
import simulation.constants as _sim_const
from utils.helpers import resource_path


_ROUTE_CLEARANCE_PX: float = HALF_BUS + 6


# ─── Hydraulic penstock connections (visual only, not electrical) ─────────────
# Each entry: (from_bus_label, to_bus_label)  — drawn as dashed connectors.
_HYDRAULIC_CONNECTORS: list[tuple[str, str]] = [
    ('MDBY', 'DUND'),    # Dunmore upper (DUNH) reservoir → lower tailwater
    ('WEST', 'KELD'),    # Kelmore upper (KELM) reservoir → lower tailwater
    ('NRTH', 'BARD'),    # Barrow upper (BARR)  reservoir → lower tailwater
]


# ─── Unit square layout helpers ───────────────────────────────────────────────

def _parallel_offset_endpoints(
    x1: int, y1: int, x2: int, y2: int,
    parallel: int, scale: float,
) -> tuple[int, int, int, int]:
    """
    Offset a line's endpoints perpendicular to its direction for double-circuit
    display. parallel=0 returns the endpoints unchanged.

    Display-only — has no electrical meaning. Both circuits of a pair (e.g.
    parallel=+1 and parallel=-1) are offset in opposite directions so they
    render as two visually distinct, separately clickable parallel lines.
    """
    if parallel == 0:
        return x1, y1, x2, y2
    dx = x2 - x1
    dy = y2 - y1
    length = max(1.0, (dx * dx + dy * dy) ** 0.5)
    # Perpendicular unit vector, scaled by the display offset constant.
    off = PARALLEL_LINE_OFFSET_PX * scale * parallel
    ox = int(-dy / length * off)
    oy = int(dx / length * off)
    return x1 + ox, y1 + oy, x2 + ox, y2 + oy


def assign_line_ports(
    buses: list[Bus],
    lines: list[Line],
    bus_pos: dict[str, tuple[int, int]],
    bus_lines: dict[str, list[str]],
    scale: float,
) -> dict[str, tuple[int, int, int, int]]:
    """
    Assign each line's two endpoints to one of its bus's 8 fixed attachment
    points (2 per side: N/S/E/W), instead of the bus centre.

    Each line still departs its substation strictly horizontally (N/S ports)
    or vertically (E/W ports) — see GRID_TOPOLOGY_AND_DISPLAY.md Rule 3.

    Side is chosen by the dominant axis of the bearing to the line's *other*
    raw bus centre (not its assigned port — avoids a two-pass dependency
    between a line's two ends). Within a side, lines are ordered by the
    secondary coordinate of their other endpoint (closest position first).
    Ties break toward N/S, then by line label, for a deterministic layout.

    Buses with more than 2 lines on one side (>8 lines total) stack the
    overflow on the nearest of that side's 2 slots — this never happens with
    the shipped topology (max bus degree is 7) but degrades to cosmetic
    overlap rather than raising if it ever does.

    A line may carry a manual per-end override (Grid Designer's line-rotate
    feature: `from_port_override` / `to_port_override`, each a (side, slot)
    tuple or None) — when set for an end, that end's port is taken directly
    instead of being derived from bearing, and is reserved so no auto-assigned
    line on the same bus/side collides with it. Only DesignerLine carries
    these attributes; the production Line dataclass does not, so getattr()
    with a None default keeps this safe for both.

    Returns:
        dict[line_label, (fx, fy, tx, ty)] — resolved port for from_bus and
        to_bus respectively.
    """
    bus_map = {b.label: b for b in buses}
    line_map = {l.label: l for l in lines}

    def _override_for(line, bus_label: str):
        if line.from_bus == bus_label:
            return getattr(line, 'from_port_override', None)
        return getattr(line, 'to_port_override', None)

    # bus_label -> list of (line_label, other_dx, other_dy), auto-assigned
    # lines only — overridden ends are handled separately below.
    per_bus: dict[str, list[tuple[str, int, int]]] = {}
    # bus_label -> line_label -> (side, slot), pre-seeded with overrides.
    port_slot: dict[str, dict[str, tuple[str, int]]] = {}
    for bus in buses:
        cx, cy = bus_pos[bus.label]
        entries = []
        slots: dict[str, tuple[str, int]] = {}
        for lbl in bus_lines.get(bus.label, []):
            line = line_map.get(lbl)
            if line is None:
                continue
            override = _override_for(line, bus.label)
            if override is not None:
                slots[lbl] = tuple(override)
                continue
            other_lbl = line.to_bus if line.from_bus == bus.label else line.from_bus
            if other_lbl not in bus_pos:
                continue
            ox, oy = bus_pos[other_lbl]
            entries.append((lbl, ox - cx, oy - cy))
        per_bus[bus.label] = entries
        port_slot[bus.label] = slots

    for bus_label, entries in per_bus.items():
        reserved = set(port_slot[bus_label].values())
        sides: dict[str, list[tuple[str, int]]] = {'N': [], 'S': [], 'E': [], 'W': []}
        for lbl, dx, dy in entries:
            if abs(dx) > abs(dy):
                side = 'E' if dx > 0 else 'W'
                secondary = dy
            else:
                side = 'S' if dy > 0 else 'N'
                secondary = dx
            sides[side].append((lbl, secondary))

        slots = port_slot[bus_label]
        for side, members in sides.items():
            members.sort(key=lambda m: (m[1], m[0]))
            free_slots = [s for s in (0, 1) if (side, s) not in reserved]
            for i, (lbl, _secondary) in enumerate(members):
                if free_slots:
                    slot = free_slots[0] if i == 0 else free_slots[-1]
                else:
                    slot = 1  # both slots reserved by overrides — cosmetic overlap
                slots[lbl] = (side, slot)

    line_ports: dict[str, tuple[int, int, int, int]] = {}
    for line in lines:
        if line.from_bus not in bus_pos or line.to_bus not in bus_pos:
            continue
        fside, fslot = port_slot[line.from_bus][line.label]
        tside, tslot = port_slot[line.to_bus][line.label]
        fx, fy = get_port_point(*bus_pos[line.from_bus], fside, fslot, scale)
        tx, ty = get_port_point(*bus_pos[line.to_bus], tside, tslot, scale)
        line_ports[line.label] = (fx, fy, tx, ty)

    return line_ports


def _segment_clips_bus(
    x1: float, y1: float, x2: float, y2: float,
    other_bus_positions: list[tuple[int, int]],
    clearance_px: float,
) -> bool:
    """True if segment (x1,y1)-(x2,y2) passes within clearance_px of any bus."""
    for bx, by in other_bus_positions:
        if point_segment_dist(bx, by, x1, y1, x2, y2) < clearance_px:
            return True
    return False


def route_line(
    x1: int, y1: int, x2: int, y2: int,
    other_bus_positions: list[tuple[int, int]],
    clearance_px: float = _ROUTE_CLEARANCE_PX,
) -> list[tuple[int, int]]:
    """
    Return an ordered orthogonal waypoint list [(x1,y1), ..., (x2,y2)]
    connecting the two endpoints without a diagonal, preferring the default
    single vertical-then-horizontal bend and only detouring around a bus
    footprint when that default path would clip it.

    other_bus_positions should exclude the line's own two endpoint buses.
    Deterministic — never raises, never loops unboundedly. If no candidate
    clears every bus (not expected at this grid's scale), falls back to the
    default bend and accepts the visual clip.
    """
    if x1 == x2 or y1 == y2:
        # Already a single straight segment — no bend to route around.
        return [(x1, y1), (x2, y2)]

    # Candidate 1: default vertical-then-horizontal bend.
    bx, by = x1, y2
    if not (_segment_clips_bus(x1, y1, bx, by, other_bus_positions, clearance_px)
            or _segment_clips_bus(bx, by, x2, y2, other_bus_positions, clearance_px)):
        return [(x1, y1), (bx, by), (x2, y2)]

    # Candidate 2: mirror bend, horizontal-then-vertical.
    bx2, by2 = x2, y1
    if not (_segment_clips_bus(x1, y1, bx2, by2, other_bus_positions, clearance_px)
            or _segment_clips_bus(bx2, by2, x2, y2, other_bus_positions, clearance_px)):
        return [(x1, y1), (bx2, by2), (x2, y2)]

    # Both single-bend options clip — escalate to a 3-segment detour that
    # jogs sideways around the clipping bus. Try 4 fixed candidate shapes,
    # offset by clearance_px + HALF_BUS from the midline, in a deterministic
    # order; use the first one that clears every bus.
    offset = clearance_px + HALF_BUS
    mid_x = (x1 + x2) / 2.0
    mid_y = (y1 + y2) / 2.0
    detours = [
        # Jog vertically at a shifted x, then horizontal-vertical-horizontal.
        [(x1, y1), (mid_x + offset, y1), (mid_x + offset, y2), (x2, y2)],
        [(x1, y1), (mid_x - offset, y1), (mid_x - offset, y2), (x2, y2)],
        # Jog horizontally at a shifted y, then vertical-horizontal-vertical.
        [(x1, y1), (x1, mid_y + offset), (x2, mid_y + offset), (x2, y2)],
        [(x1, y1), (x1, mid_y - offset), (x2, mid_y - offset), (x2, y2)],
    ]
    for path in detours:
        path_i = [(int(px), int(py)) for px, py in path]
        clipped = False
        for (sx1, sy1), (sx2, sy2) in zip(path_i, path_i[1:]):
            if _segment_clips_bus(sx1, sy1, sx2, sy2, other_bus_positions, clearance_px):
                clipped = True
                break
        if not clipped:
            return path_i

    # Nothing cleared — fall back to the default bend (cosmetic overlap only).
    return [(x1, y1), (bx, by), (x2, y2)]


def _unit_positions(station_label: str, n_units: int) -> list[tuple[int, int]]:
    """
    Return (cx, cy) for each unit square at a station.
    Units are laid out horizontally, centred on the station anchor.
    """
    ax, ay = get_station_position(station_label)
    total_w = n_units * UNIT_SIZE + (n_units - 1) * UNIT_GAP
    start_x = ax - total_w // 2 + UNIT_SIZE // 2
    return [(start_x + i * (UNIT_SIZE + UNIT_GAP), ay) for i in range(n_units)]


class GridCanvas:
    """
    Renders the full grid schematic for one shift.

    Usage:
        canvas = GridCanvas(shift=1, font=font)
        canvas.draw(surf, state=None, blink_on=True)

    Args:
        shift:  Active shift number (1-10). Controls which buses/lines appear.
        font:   pygame.freetype.Font for labels.
    """

    def __init__(
        self,
        shift: int,
        font: pygame.freetype.Font,
        scale: float = 1.0,
    ) -> None:
        self._shift = shift
        self._font  = font
        self._scale = scale

        # Active topology for this shift
        self._buses: list[Bus] = get_buses_by_shift(shift)
        self._lines: list[Line] = get_lines_by_shift(shift)

        # Bus is frozen=True; store scaled positions separately rather than mutating.
        self._bus_pos: dict[str, tuple[int, int]] = {
            b.label: (int(b.canvas_x * scale), int(b.canvas_y * scale))
            for b in self._buses
        }

        # Fast bus lookup
        self._bus_map: dict[str, Bus] = {b.label: b for b in self._buses}

        # Pre-compute unit layout per station (only stations active this shift)
        active_bus_labels = {b.label for b in self._buses}
        self._station_units: dict[str, list] = {}    # station → [GenerationUnit]
        self._station_pos:   dict[str, list[tuple[int, int]]] = {}  # station → [(cx,cy)]

        seen_stations: set[str] = set()
        for unit in UNITS:
            if unit.active_from_shift > shift:
                continue
            if unit.bus_label not in active_bus_labels:
                continue
            sl = unit.station_label
            if sl not in seen_stations:
                seen_stations.add(sl)
                self._station_units[sl] = []
            self._station_units[sl].append(unit)

        for sl, units in self._station_units.items():
            # _unit_positions returns 1920-unit coords; scale to physical space
            raw = _unit_positions(sl, len(units))
            self._station_pos[sl] = [
                (int(x * scale), int(y * scale)) for x, y in raw
            ]

        # Fast rated_mw lookup by unit label (avoids fleet.get_unit() in hot path)
        self._unit_rated_mw: dict[str, float] = {
            u.label: u.rated_mw
            for units in self._station_units.values()
            for u in units
        }

        # Bus → connected line labels (for load-state colouring of substation symbols)
        self._bus_lines: dict[str, list[str]] = {b.label: [] for b in self._buses}
        for line in self._lines:
            if line.from_bus in self._bus_lines:
                self._bus_lines[line.from_bus].append(line.label)
            if line.to_bus in self._bus_lines:
                self._bus_lines[line.to_bus].append(line.label)

        # Per-line attachment points (8 fixed ports per bus instead of centre)
        self._line_ports: dict[str, tuple[int, int, int, int]] = assign_line_ports(
            self._buses, self._lines, self._bus_pos, self._bus_lines, scale,
        )

        # Obstacle-avoiding waypoints per line — computed once here (not per
        # frame). Offsetting for double circuits happens first, then each
        # (already-offset) endpoint pair is routed independently.
        self._line_waypoints: dict[str, list[tuple[int, int]]] = self._build_line_waypoints(
            self._lines, self._line_ports, scale,
        )

        # Hydraulic connectors: only those where both buses are active this shift
        self._hydraulic: list[tuple[Bus, Bus]] = []
        for from_lbl, to_lbl in _HYDRAULIC_CONNECTORS:
            if from_lbl in active_bus_labels and to_lbl in active_bus_labels:
                self._hydraulic.append(
                    (self._bus_map[from_lbl], self._bus_map[to_lbl])
                )

        scaled_w  = int(NATIVE_WIDTH  * scale)
        scaled_ch = int(CANVAS_HEIGHT * scale)

        # Canvas cache: converted to display pixel format for hardware-accelerated blits.
        self._canvas_surf_cache: pygame.Surface = pygame.Surface((scaled_w, scaled_ch)).convert()
        self._canvas_key: object = object()  # sentinel forces first-frame draw

        # Pre-baked hydraulic connector surface — convert_alpha() for fast SRCALPHA blits.
        self._hydraulic_surf: pygame.Surface = pygame.Surface(
            (scaled_w, scaled_ch), pygame.SRCALPHA
        ).convert_alpha()
        self._hydraulic_surf.fill((0, 0, 0, 0))
        dash_w = max(1, round(scale))
        for fb, tb in self._hydraulic:
            fx, fy = self._bus_pos[fb.label]
            tx, ty = self._bus_pos[tb.label]
            _draw_dashed_line(
                self._hydraulic_surf, COL_LINE_HYDRAULIC,
                (fx, fy), (tx, ty),
                dash=max(1, int(3 * scale)), gap=max(1, int(2 * scale)), width=dash_w,
            )

        # Pre-baked tripped-line surfaces: one per line, drawn once at init.
        # Each surface covers only the line's bounding box (offset stored alongside).
        self._tripped_line_surfs: dict[str, tuple[pygame.Surface, int, int]] = {}
        pad = max(2, int(2 * scale))
        for line in self._lines:
            waypoints = self._line_waypoints.get(line.label)
            if waypoints is None:
                continue
            xs = [p[0] for p in waypoints]
            ys = [p[1] for p in waypoints]
            min_x, max_x = min(xs) - pad, max(xs) + pad
            min_y, max_y = min(ys) - pad, max(ys) + pad
            w = max(1, max_x - min_x)
            h = max(1, max_y - min_y)
            surf = pygame.Surface((w, h), pygame.SRCALPHA).convert_alpha()
            surf.fill((0, 0, 0, 0))
            ox, oy = min_x, min_y
            td = max(1, int(3 * scale))
            tg = max(1, int(2 * scale))
            for (sx1, sy1), (sx2, sy2) in zip(waypoints, waypoints[1:]):
                _draw_dashed_line(
                    surf, COL_LINE_TRIPPED,
                    (sx1 - ox, sy1 - oy), (sx2 - ox, sy2 - oy),
                    dash=td, gap=tg, width=dash_w,
                )
            self._tripped_line_surfs[line.label] = (surf, ox, oy)

    def _build_line_waypoints(
        self,
        lines: list[Line],
        line_ports: dict[str, tuple[int, int, int, int]],
        scale: float,
    ) -> dict[str, list[tuple[int, int]]]:
        """
        Resolve each line's obstacle-avoiding waypoint path, in the order:
        parallel-offset endpoints first, then route around unrelated buses.

        Uses self._bus_pos, which must already be populated (both call sites
        — __init__ and load_designer_topology — set it before calling this).
        """
        clearance = _ROUTE_CLEARANCE_PX * scale
        waypoints: dict[str, list[tuple[int, int]]] = {}
        for line in lines:
            ports = line_ports.get(line.label)
            if ports is None:
                continue
            fx, fy, tx, ty = ports
            fx, fy, tx, ty = _parallel_offset_endpoints(fx, fy, tx, ty, line.parallel, scale)
            other_positions = [
                pos for lbl, pos in self._bus_pos.items()
                if lbl != line.from_bus and lbl != line.to_bus
            ]
            waypoints[line.label] = route_line(fx, fy, tx, ty, other_positions, clearance)
        return waypoints

    def _bus_max_loading(self, bus_label: str, state) -> float:
        """Return max loading_pct of connected in-service lines, or 0 if none."""
        if state is None:
            return 0.0
        best = 0.0
        for lbl in self._bus_lines.get(bus_label, []):
            if state.line_status.get(lbl) == 'IN_SERVICE':
                best = max(best, state.line_loading_pct.get(lbl, 0.0))
        return best

    def _bus_connected_tiers(self, bus_label: str) -> tuple[float, ...]:
        """
        Return the distinct voltage tiers of lines connected to a bus, sorted
        descending by kV. Used to fill the substation symbol by voltage tier
        instead of loading when the 'L' (voltage_view) toggle is on — see
        draw_substation()/draw_load_substation().
        """
        line_map = {l.label: l for l in self._lines}
        tiers: set[float] = set()
        for lbl in self._bus_lines.get(bus_label, []):
            line = line_map.get(lbl)
            if line is not None:
                tiers.add(line.voltage_kv)
        return tuple(sorted(tiers, reverse=True))

    def load_designer_topology(
        self,
        buses:  list,
        lines:  list,
        units:  list,
        station_positions: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        """
        Replace the canvas topology with designer-supplied Bus/Line/Unit lists.

        Bypasses get_buses_by_shift(), UNITS, and get_station_position() so the
        canvas draws the designer grid instead of the campaign shift topology.
        Station position comes from station_positions (unscaled, native-space
        anchors set/dragged in the Designer); a station missing an entry falls
        back to 20px above its bus.
        """
        scale = self._scale
        station_positions = station_positions or {}

        self._buses    = buses
        self._lines    = lines
        self._bus_pos  = {b.label: (int(b.canvas_x * scale), int(b.canvas_y * scale))
                          for b in buses}
        self._bus_map  = {b.label: b for b in buses}

        # Unit layout — group by station_label, position at its stored anchor
        active_bus_labels = {b.label for b in buses}
        self._station_units = {}
        for unit in units:
            if unit.bus_label not in active_bus_labels:
                continue
            sl = unit.station_label
            self._station_units.setdefault(sl, []).append(unit)

        self._station_pos = {}
        for sl, sunits in self._station_units.items():
            bus_lbl = sunits[0].bus_label
            if bus_lbl not in self._bus_pos:
                continue
            bx, by = self._bus_pos[bus_lbl]
            pos = station_positions.get(sl)
            if pos is not None:
                ax, ay = int(pos[0] * scale), int(pos[1] * scale)
            else:
                ax, ay = bx, by - int(20 * scale)
            n = len(sunits)
            total_w = n * int(UNIT_SIZE * scale) + (n - 1) * max(1, int(UNIT_GAP * scale))
            start_x = ax - total_w // 2 + int(UNIT_SIZE * scale) // 2
            gap = int(UNIT_SIZE * scale) + max(1, int(UNIT_GAP * scale))
            self._station_pos[sl] = [
                (start_x + i * gap, ay) for i in range(n)
            ]

        # Bus → connected line labels
        self._bus_lines = {b.label: [] for b in buses}
        for line in lines:
            if line.from_bus in self._bus_lines:
                self._bus_lines[line.from_bus].append(line.label)
            if line.to_bus in self._bus_lines:
                self._bus_lines[line.to_bus].append(line.label)

        # Per-line attachment points (8 fixed ports per bus instead of centre)
        self._line_ports = assign_line_ports(
            buses, lines, self._bus_pos, self._bus_lines, scale,
        )

        # Obstacle-avoiding waypoints per line — see __init__ for details.
        self._line_waypoints = self._build_line_waypoints(
            lines, self._line_ports, scale,
        )

        # No hydraulic connectors in designer topology
        self._hydraulic = []
        scaled_w  = int(NATIVE_WIDTH  * scale)
        scaled_ch = int(CANVAS_HEIGHT * scale)
        self._hydraulic_surf = pygame.Surface(
            (scaled_w, scaled_ch), pygame.SRCALPHA
        ).convert_alpha()
        self._hydraulic_surf.fill((0, 0, 0, 0))

        # Pre-bake tripped-line surfaces for the designer lines
        pad   = max(2, int(2 * scale))
        dash_w = max(1, round(scale))
        self._tripped_line_surfs = {}
        for line in lines:
            waypoints = self._line_waypoints.get(line.label)
            if waypoints is None:
                continue
            xs = [p[0] for p in waypoints]
            ys = [p[1] for p in waypoints]
            min_x, max_x = min(xs) - pad, max(xs) + pad
            min_y, max_y = min(ys) - pad, max(ys) + pad
            w = max(1, max_x - min_x)
            h = max(1, max_y - min_y)
            surf = pygame.Surface((w, h), pygame.SRCALPHA).convert_alpha()
            surf.fill((0, 0, 0, 0))
            ox, oy = min_x, min_y
            td = max(1, int(3 * scale))
            tg = max(1, int(2 * scale))
            for (sx1, sy1), (sx2, sy2) in zip(waypoints, waypoints[1:]):
                _draw_dashed_line(
                    surf, COL_LINE_TRIPPED,
                    (sx1 - ox, sy1 - oy), (sx2 - ox, sy2 - oy),
                    dash=td, gap=tg, width=dash_w,
                )
            self._tripped_line_surfs[line.label] = (surf, ox, oy)

        # Fast rated_mw lookup by unit label
        self._unit_rated_mw = {
            u.label: u.rated_mw
            for sunits in self._station_units.values()
            for u in sunits
        }

        # Force full redraw next frame
        self._canvas_key = object()

    def rebuild(self, shift: int | None = None) -> None:
        """Re-run __init__ pre-computation after layout overrides change."""
        if shift is not None:
            self._shift = shift
        self.__init__(self._shift, self._font, self._scale)

    # ─── Main draw entry point ────────────────────────────────────────────────

    def draw(
        self,
        surf: pygame.Surface,
        state=None,
        blink_on: bool = True,
        selected_label: str | None = None,
        font_scale: float = 1.0,
    ) -> None:
        """
        Draw the complete grid schematic, using a cached surface to skip
        redundant redraws when the visible state has not changed.

        Args:
            surf:           Target surface (1920×CANVAS_HEIGHT).
            state:          SimulationState (or None for static view).
            blink_on:       Current blink phase (1Hz).
            selected_label: Bus or unit label that is currently selected.
        """
        canvas_key = self._build_canvas_key(state, blink_on, selected_label, font_scale)
        if canvas_key != self._canvas_key:
            self._redraw_to(self._canvas_surf_cache, state, blink_on, selected_label,
                            font_scale)
            self._canvas_key = canvas_key
        surf.blit(self._canvas_surf_cache, (0, 0))

    def _build_canvas_key(
        self,
        state,
        blink_on: bool,
        selected_label: str | None,
        font_scale: float = 1.0,
    ) -> tuple:
        """Return a compact tuple that changes when the canvas must be redrawn."""
        voltage_view = _sim_const.VOLTAGE_COLOUR_VIEW
        if state is None:
            return (None, selected_label, voltage_view)

        # Tripped lines and blacked buses (infrequent changes)
        tripped_lines = frozenset(
            lbl for lbl, status in state.line_status.items() if status == 'TRIPPED'
        )
        blacked_buses = frozenset(state.blackout_zones)

        # Unit states as a compact character-per-unit string
        unit_state_sig = ''.join(v[:1] for _, v in sorted(state.unit_states.items()))

        # Line loading quantised to 5% steps — caps redraw rate to a few per second
        loading_sig = tuple(
            round(state.line_loading_pct.get(line.label, 0.0) / 5)
            for line in self._lines
        )

        # Unit outputs quantised to 5% of rated — same reasoning
        output_sig = tuple(
            round(state.unit_outputs_mw.get(u.label, 0.0) / u.rated_mw * 20)
            if u.rated_mw > 0 else 0
            for units in self._station_units.values()
            for u in units
        )

        # Interconnector flows quantised to 50 MW
        intc_sig = tuple(
            round(v / 50)
            for _, v in sorted(
                (state.interconnector_flows if hasattr(state, 'interconnector_flows') else {}).items()
            )
        )

        # Blink only affects the canvas when tripped elements are present
        has_blink_effect = bool(tripped_lines) or any(
            s[:1] in ('T', 'S') for s in state.unit_states.values()
        )
        blink_key = blink_on if has_blink_effect else True

        return (
            tripped_lines, blacked_buses, unit_state_sig,
            loading_sig, output_sig, intc_sig,
            selected_label, blink_key, font_scale, voltage_view,
        )

    def _redraw_to(
        self,
        target: pygame.Surface,
        state=None,
        blink_on: bool = True,
        selected_label: str | None = None,
        font_scale: float = 1.0,
    ) -> None:
        """Full schematic redraw into target surface."""
        target.fill(COL_BACKGROUND)
        voltage_view = _sim_const.VOLTAGE_COLOUR_VIEW

        # Build lookup tables from state (if provided)
        line_loading:  dict[str, float] = {}
        line_tripped:  dict[str, bool]  = {}
        bus_blacked:   dict[str, bool]  = {}
        unit_states:   dict[str, str]   = {}
        unit_outputs:  dict[str, float] = {}   # fraction 0-1
        intc_flows:    dict[str, float] = {'INTC-N': 0.0, 'INTC-S': 0.0}

        if state is not None:
            for lbl, pct in state.line_loading_pct.items():
                line_loading[lbl] = pct
            for lbl, status in state.line_status.items():
                line_tripped[lbl] = (status == 'TRIPPED')
            blacked = state.blackout_zones
            for b in self._buses:
                bus_blacked[b.label] = (b.label in blacked)
            unit_states  = state.unit_states
            for lbl, mw in state.unit_outputs_mw.items():
                rated = self._unit_rated_mw.get(lbl, 0.0)
                unit_outputs[lbl] = mw / rated if rated > 0 else 0.0
            if hasattr(state, 'interconnector_flows'):
                intc_flows = state.interconnector_flows

        # ── Layer 1-4: Transmission lines by voltage tier ─────────────────────
        for voltage in (60.0, 150.0, 220.0, 400.0):
            for line in self._lines:
                if line.voltage_kv != voltage:
                    continue
                fb = self._bus_map.get(line.from_bus)
                tb = self._bus_map.get(line.to_bus)
                if fb is None or tb is None:
                    continue
                tripped = line_tripped.get(line.label, False)
                if tripped:
                    # Use pre-baked dashed surface — avoids per-dash Python loop
                    entry = self._tripped_line_surfs.get(line.label)
                    if entry is not None:
                        surf, ox, oy = entry
                        target.blit(surf, (ox, oy))
                else:
                    loading = line_loading.get(line.label, 0.0)
                    waypoints = self._line_waypoints.get(line.label)
                    if waypoints is None:
                        continue
                    draw_transmission_line(
                        target,
                        waypoints,
                        voltage_kv=line.voltage_kv,
                        loading_pct=loading,
                        tripped=False,
                        blink_on=blink_on,
                        scale=self._scale,
                        voltage_view=voltage_view,
                    )

        # ── Layer 5: Hydraulic connectors (pre-baked, blit once) ──────────────
        target.blit(self._hydraulic_surf, (0, 0))

        # ── Layer 6: Station collector lines ──────────────────────────────────
        for sl, units in self._station_units.items():
            positions = self._station_pos[sl]
            bus_lbl   = units[0].bus_label
            bus       = self._bus_map.get(bus_lbl)
            if bus is None:
                continue
            bus_cx, bus_cy = self._bus_pos[bus_lbl]
            station_outputs = [unit_outputs.get(u.label, 0.0) for u in units]
            station_loading = (sum(station_outputs) / len(station_outputs) * 100.0
                               if station_outputs else 0.0)
            draw_station_collector(
                target, positions, bus_cx, bus_cy,
                voltage_kv=bus.voltage_kv,
                loading_pct=station_loading,
                scale=self._scale,
            )

        # ── Layer 7: Substation symbols ────────────────────────────────────────
        for bus in self._buses:
            bx, by   = self._bus_pos[bus.label]
            blacked  = bus_blacked.get(bus.label, False)
            selected = (selected_label == bus.label)
            loading  = self._bus_max_loading(bus.label, state)
            tiers    = self._bus_connected_tiers(bus.label)
            if bus.bus_type == 'LOAD':
                draw_load_substation(target, bx, by,
                                     voltage_kv=bus.voltage_kv,
                                     connected_tiers=tiers,
                                     loading_pct=loading,
                                     blacked=blacked, selected=selected,
                                     scale=self._scale,
                                     voltage_view=voltage_view)
            else:
                draw_substation(target, bx, by,
                                voltage_kv=bus.voltage_kv,
                                connected_tiers=tiers,
                                loading_pct=loading,
                                blacked=blacked, selected=selected,
                                scale=self._scale,
                                voltage_view=voltage_view)

        # ── Layer 8: Generation unit squares ──────────────────────────────────
        for sl, units in self._station_units.items():
            positions = self._station_pos[sl]
            for unit, (ux, uy) in zip(units, positions):
                u_state  = unit_states.get(unit.label, 'OFFLINE')
                u_frac   = unit_outputs.get(unit.label, 0.0)
                selected = (selected_label == unit.label)
                draw_unit_square(
                    target, ux, uy,
                    unit_type=unit.unit_type,
                    unit_state=u_state,
                    output_fraction=u_frac,
                    selected=selected,
                    blink_on=blink_on,
                    scale=self._scale,
                )

        # ── Layer 8: Interconnector markers ────────────────────────────────────
        for intc_label, (ix, iy) in INTERCONNECTOR_POSITIONS.items():
            flow = intc_flows.get(intc_label, 0.0)
            draw_interconnector(target, int(ix * self._scale), int(iy * self._scale),
                                flow_mw=flow, label=intc_label, font=self._font,
                                font_scale=font_scale, scale=self._scale)

        # ── Layer 9: Node labels ───────────────────────────────────────────────
        self._draw_labels(target, font_scale)

    # ─── Label drawing ────────────────────────────────────────────────────────

    def _draw_labels(self, surf: pygame.Surface, font_scale: float = 1.0) -> None:
        """Draw bus and station labels at anchor-relative positions."""
        font = self._font
        sl   = int(FONT_SIZE_PANEL * font_scale)
        sc   = self._scale
        off  = int(8 * sc)   # distance from symbol centre to text edge

        for bus in self._buses:
            bx, by = self._bus_pos[bus.label]
            self._render_anchored(surf, font, bus.label, bx, by, sl, off)

        for station_lbl, positions in self._station_pos.items():
            if not positions:
                continue
            cx = sum(p[0] for p in positions) // len(positions)
            cy = sum(p[1] for p in positions) // len(positions)
            self._render_anchored(surf, font, station_lbl, cx, cy, sl, off)

    def _render_anchored(
        self,
        surf: pygame.Surface,
        font,
        label: str,
        cx: int,
        cy: int,
        size: int,
        off: int,
    ) -> None:
        """Render a 4-char label at the anchor position relative to (cx, cy)."""
        anchor = get_label_anchor(label)
        rect   = font.get_rect(label, size=size)
        w, h   = rect.width, rect.height
        if anchor == 'top':
            lx = cx - w // 2
            ly = cy - off - h
        elif anchor == 'bottom':
            lx = cx - w // 2
            ly = cy + off
        elif anchor == 'left':
            lx = cx - off - w
            ly = cy - h // 2
        else:  # right (default)
            lx = cx + off
            ly = cy - h // 2
        font.render_to(surf, (lx, ly), label, COL_TEXT_PRIMARY, size=size)
