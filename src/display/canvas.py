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
    UNIT_SIZE, UNIT_GAP, PARALLEL_LINE_OFFSET_PX,
    _draw_dashed_line,
)
from display.palette import COL_LINE_TRIPPED, COL_LINE_HYDRAULIC
from data.layout_override import get_label_anchor
from simulation.constants import CANVAS_HEIGHT, FONT_SIZE_LABEL, FONT_SIZE_PANEL, NATIVE_WIDTH
from utils.helpers import resource_path


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
            if line.from_bus not in self._bus_pos or line.to_bus not in self._bus_pos:
                continue
            # Tripped lines route vertical-first: bend at (x1, y2)
            x1, y1 = self._bus_pos[line.from_bus]
            x2, y2 = self._bus_pos[line.to_bus]
            x1, y1, x2, y2 = _parallel_offset_endpoints(x1, y1, x2, y2, line.parallel, self._scale)
            bx, by = x1, y2
            min_x = min(x1, x2) - pad
            min_y = min(y1, y2) - pad
            max_x = max(x1, x2) + pad
            max_y = max(y1, y2) + pad
            w = max(1, max_x - min_x)
            h = max(1, max_y - min_y)
            surf = pygame.Surface((w, h), pygame.SRCALPHA).convert_alpha()
            surf.fill((0, 0, 0, 0))
            ox, oy = min_x, min_y
            td = max(1, int(3 * scale))
            tg = max(1, int(2 * scale))
            if y1 != y2:
                _draw_dashed_line(
                    surf, COL_LINE_TRIPPED,
                    (x1 - ox, y1 - oy), (bx - ox, by - oy),
                    dash=td, gap=tg, width=dash_w,
                )
            if x1 != x2:
                _draw_dashed_line(
                    surf, COL_LINE_TRIPPED,
                    (bx - ox, by - oy), (x2 - ox, y2 - oy),
                    dash=td, gap=tg, width=dash_w,
                )
            self._tripped_line_surfs[line.label] = (surf, ox, oy)

    def _bus_max_loading(self, bus_label: str, state) -> float:
        """Return max loading_pct of connected in-service lines, or 0 if none."""
        if state is None:
            return 0.0
        best = 0.0
        for lbl in self._bus_lines.get(bus_label, []):
            if state.line_status.get(lbl) == 'IN_SERVICE':
                best = max(best, state.line_loading_pct.get(lbl, 0.0))
        return best

    def load_designer_topology(
        self,
        buses:  list,
        lines:  list,
        units:  list,
    ) -> None:
        """
        Replace the canvas topology with designer-supplied Bus/Line/Unit lists.

        Bypasses get_buses_by_shift(), UNITS, and get_station_position() so the
        canvas draws the designer grid instead of the campaign shift topology.
        Station position is taken from the unit's bus position (designer units
        live at their bus node).
        """
        scale = self._scale

        self._buses    = buses
        self._lines    = lines
        self._bus_pos  = {b.label: (int(b.canvas_x * scale), int(b.canvas_y * scale))
                          for b in buses}
        self._bus_map  = {b.label: b for b in buses}

        # Unit layout — group by station_label, position at bus node
        active_bus_labels = {b.label for b in buses}
        self._station_units = {}
        for unit in units:
            if unit.bus_label not in active_bus_labels:
                continue
            sl = unit.station_label
            self._station_units.setdefault(sl, []).append(unit)

        # Station screen position = bus canvas position scaled
        self._station_pos = {}
        for sl, sunits in self._station_units.items():
            bus_lbl = sunits[0].bus_label
            if bus_lbl in self._bus_pos:
                bx, by = self._bus_pos[bus_lbl]
                n = len(sunits)
                total_w = n * int(UNIT_SIZE * scale) + (n - 1) * max(1, int(UNIT_GAP * scale))
                start_x = bx - total_w // 2 + int(UNIT_SIZE * scale) // 2
                gap = int(UNIT_SIZE * scale) + max(1, int(UNIT_GAP * scale))
                self._station_pos[sl] = [
                    (start_x + i * gap, by) for i in range(n)
                ]

        # Bus → connected line labels
        self._bus_lines = {b.label: [] for b in buses}
        for line in lines:
            if line.from_bus in self._bus_lines:
                self._bus_lines[line.from_bus].append(line.label)
            if line.to_bus in self._bus_lines:
                self._bus_lines[line.to_bus].append(line.label)

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
            if line.from_bus not in self._bus_pos or line.to_bus not in self._bus_pos:
                continue
            x1, y1 = self._bus_pos[line.from_bus]
            x2, y2 = self._bus_pos[line.to_bus]
            bx2, by2 = x1, y2
            min_x = min(x1, x2) - pad
            min_y = min(y1, y2) - pad
            max_x = max(x1, x2) + pad
            max_y = max(y1, y2) + pad
            w = max(1, max_x - min_x)
            h = max(1, max_y - min_y)
            surf = pygame.Surface((w, h), pygame.SRCALPHA).convert_alpha()
            surf.fill((0, 0, 0, 0))
            ox, oy = min_x, min_y
            td = max(1, int(3 * scale))
            tg = max(1, int(2 * scale))
            if y1 != y2:
                _draw_dashed_line(
                    surf, COL_LINE_TRIPPED,
                    (x1 - ox, y1 - oy), (bx2 - ox, by2 - oy),
                    dash=td, gap=tg, width=dash_w,
                )
            if x1 != x2:
                _draw_dashed_line(
                    surf, COL_LINE_TRIPPED,
                    (bx2 - ox, by2 - oy), (x2 - ox, y2 - oy),
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
        if state is None:
            return (None, selected_label)

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
            selected_label, blink_key, font_scale,
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
                    fx, fy = self._bus_pos[line.from_bus]
                    tx, ty = self._bus_pos[line.to_bus]
                    fx, fy, tx, ty = _parallel_offset_endpoints(
                        fx, fy, tx, ty, line.parallel, self._scale)
                    draw_transmission_line(
                        target,
                        fx, fy, tx, ty,
                        voltage_kv=line.voltage_kv,
                        loading_pct=loading,
                        tripped=False,
                        blink_on=blink_on,
                        scale=self._scale,
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
            if bus.bus_type == 'LOAD':
                draw_load_substation(target, bx, by,
                                     loading_pct=loading,
                                     blacked=blacked, selected=selected,
                                     scale=self._scale)
            else:
                draw_substation(target, bx, by,
                                loading_pct=loading,
                                blacked=blacked, selected=selected,
                                scale=self._scale)

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
