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
from data.fleet import UNITS, STATION_POSITIONS, get_units_at_bus, get_unit, get_station_position
from display.palette import (
    COL_BACKGROUND,
    COL_TEXT_PRIMARY, COL_TEXT_SECONDARY, COL_TEXT_DIM,
)
from display.symbols import (
    draw_substation, draw_load_substation,
    draw_unit_square, draw_station_collector,
    draw_transmission_line, draw_hydraulic_connector,
    draw_interconnector,
    UNIT_SIZE, UNIT_GAP,
    _draw_dashed_line,
)
from display.palette import COL_LINE_TRIPPED, COL_LINE_HYDRAULIC
from simulation.constants import CANVAS_HEIGHT, FONT_SIZE_LABEL, NATIVE_WIDTH
from utils.helpers import resource_path


# ─── Hydraulic penstock connections (visual only, not electrical) ─────────────
# Each entry: (from_bus_label, to_bus_label)  — drawn as dashed connectors.
_HYDRAULIC_CONNECTORS: list[tuple[str, str]] = [
    ('STHW', 'DUND'),    # Dunmore upper reservoir → lower tailwater
    ('WEST', 'KELD'),    # Kelmore upper reservoir → lower tailwater
    ('EAST', 'BARD'),    # Barrow upper reservoir  → lower tailwater
]


# ─── Unit square layout helpers ───────────────────────────────────────────────

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
                dash=max(1, int(5 * scale)), gap=max(1, int(4 * scale)), width=dash_w,
            )

        # Pre-baked tripped-line surfaces: one per line, drawn once at init.
        # Each surface covers only the line's bounding box (offset stored alongside).
        self._tripped_line_surfs: dict[str, tuple[pygame.Surface, int, int]] = {}
        pad = max(2, int(3 * scale))
        for line in self._lines:
            if line.from_bus not in self._bus_pos or line.to_bus not in self._bus_pos:
                continue
            # Tripped lines route vertical-first: bend at (x1, y2)
            x1, y1 = self._bus_pos[line.from_bus]
            x2, y2 = self._bus_pos[line.to_bus]
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
            td = max(1, int(6 * scale))
            tg = max(1, int(4 * scale))
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
                try:
                    unit_obj = get_unit(lbl)
                    unit_outputs[lbl] = mw / unit_obj.rated_mw if unit_obj.rated_mw > 0 else 0.0
                except KeyError:
                    unit_outputs[lbl] = 0.0
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

        # ── Layer 6: Substation symbols ────────────────────────────────────────
        for bus in self._buses:
            bx, by   = self._bus_pos[bus.label]
            blacked  = bus_blacked.get(bus.label, False)
            selected = (selected_label == bus.label)
            draw_substation(target, bx, by,
                            voltage_kv=bus.voltage_kv,
                            blacked=blacked, selected=selected,
                            scale=self._scale)

        # ── Layer 7: Generation unit squares + collectors ──────────────────────
        for sl, units in self._station_units.items():
            positions = self._station_pos[sl]
            bus_lbl   = units[0].bus_label
            bus       = self._bus_map.get(bus_lbl)
            if bus is None:
                continue

            bus_cx, bus_cy = self._bus_pos[bus_lbl]

            draw_station_collector(
                target, positions, bus_cx, bus_cy,
                voltage_kv=bus.voltage_kv,
                scale=self._scale,
            )

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
        """Draw bus and station labels at positions offset from symbols."""
        font   = self._font
        sl     = int(FONT_SIZE_LABEL * font_scale)
        sc     = self._scale
        loff_x = int(14 * sc)
        loff_y = int(5  * sc)
        soff_y = int(16 * sc)
        soff_x = int(12 * sc)

        for bus in self._buses:
            bx, by = self._bus_pos[bus.label]
            lx = bx + loff_x
            ly = by - loff_y
            font.render_to(surf, (lx, ly), bus.label, COL_TEXT_SECONDARY, size=sl)

        # Station labels below unit row
        for station_lbl, positions in self._station_pos.items():
            if not positions:
                continue
            cx = sum(p[0] for p in positions) // len(positions)
            cy = max(p[1] for p in positions) + soff_y
            font.render_to(surf, (cx - soff_x, cy), station_lbl, COL_TEXT_DIM, size=sl)
