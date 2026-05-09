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
)
from simulation.constants import CANVAS_HEIGHT, FONT_SIZE_LABEL
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

    def __init__(self, shift: int, font: pygame.freetype.Font) -> None:
        self._shift = shift
        self._font  = font

        # Active topology for this shift
        self._buses: list[Bus] = get_buses_by_shift(shift)
        self._lines: list[Line] = get_lines_by_shift(shift)

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
            self._station_pos[sl] = _unit_positions(sl, len(units))

        # Hydraulic connectors: only those where both buses are active this shift
        self._hydraulic: list[tuple[Bus, Bus]] = []
        for from_lbl, to_lbl in _HYDRAULIC_CONNECTORS:
            if from_lbl in active_bus_labels and to_lbl in active_bus_labels:
                self._hydraulic.append(
                    (self._bus_map[from_lbl], self._bus_map[to_lbl])
                )

    def rebuild(self, shift: int | None = None) -> None:
        """Re-run __init__ pre-computation after layout overrides change."""
        if shift is not None:
            self._shift = shift
        self.__init__(self._shift, self._font)

    # ─── Main draw entry point ────────────────────────────────────────────────

    def draw(
        self,
        surf: pygame.Surface,
        state=None,
        blink_on: bool = True,
        selected_label: str | None = None,
    ) -> None:
        """
        Draw the complete grid schematic.

        Args:
            surf:           Target surface (1920×CANVAS_HEIGHT).
            state:          SimulationState (or None for static view).
            blink_on:       Current blink phase (1Hz).
            selected_label: Bus or unit label that is currently selected.
        """
        surf.fill(COL_BACKGROUND)

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
                # Compute output fraction against rated_mw from fleet
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
                tripped  = line_tripped.get(line.label, False)
                loading  = line_loading.get(line.label, 0.0)
                draw_transmission_line(
                    surf,
                    fb.canvas_x, fb.canvas_y,
                    tb.canvas_x, tb.canvas_y,
                    voltage_kv=line.voltage_kv,
                    loading_pct=loading,
                    tripped=tripped,
                    blink_on=blink_on,
                )

        # ── Layer 5: Hydraulic connectors ──────────────────────────────────────
        for fb, tb in self._hydraulic:
            draw_hydraulic_connector(
                surf,
                fb.canvas_x, fb.canvas_y,
                tb.canvas_x, tb.canvas_y,
            )

        # ── Layer 6: Substation symbols ────────────────────────────────────────
        for bus in self._buses:
            blacked  = bus_blacked.get(bus.label, False)
            selected = (selected_label == bus.label)
            draw_substation(surf, bus.canvas_x, bus.canvas_y,
                            voltage_kv=bus.voltage_kv,
                            blacked=blacked, selected=selected)

        # ── Layer 7: Generation unit squares + collectors ──────────────────────
        for sl, units in self._station_units.items():
            positions = self._station_pos[sl]
            bus_lbl   = units[0].bus_label
            bus       = self._bus_map.get(bus_lbl)
            if bus is None:
                continue

            bus_cx, bus_cy = bus.canvas_x, bus.canvas_y

            # Collector line from unit row to bus
            draw_station_collector(
                surf, positions, bus_cx, bus_cy,
                voltage_kv=bus.voltage_kv,
            )

            # Individual unit squares
            for unit, (ux, uy) in zip(units, positions):
                u_state   = unit_states.get(unit.label, 'OFFLINE')
                u_frac    = unit_outputs.get(unit.label, 0.0)
                selected  = (selected_label == unit.label)
                draw_unit_square(
                    surf, ux, uy,
                    unit_type=unit.unit_type,
                    unit_state=u_state,
                    output_fraction=u_frac,
                    selected=selected,
                    blink_on=blink_on,
                )

        # ── Layer 8: Interconnector markers ────────────────────────────────────
        for intc_label, (ix, iy) in INTERCONNECTOR_POSITIONS.items():
            flow = intc_flows.get(intc_label, 0.0)
            draw_interconnector(surf, ix, iy, flow_mw=flow,
                                label=intc_label, font=self._font)

        # ── Layer 9: Node labels ───────────────────────────────────────────────
        self._draw_labels(surf)

    # ─── Label drawing ────────────────────────────────────────────────────────

    def _draw_labels(self, surf: pygame.Surface) -> None:
        """Draw bus and station labels at positions offset from symbols."""
        font = self._font
        label_size = FONT_SIZE_LABEL

        for bus in self._buses:
            # Offset label below the symbol for most buses, above for 400kV backbone
            lx = bus.canvas_x + 9
            ly = bus.canvas_y - 5
            col = COL_TEXT_SECONDARY
            font.render_to(surf, (lx, ly), bus.label, col, size=label_size)

        # Station labels below unit row
        for sl, positions in self._station_pos.items():
            if not positions:
                continue
            # Centre the label under the unit row
            cx = sum(p[0] for p in positions) // len(positions)
            cy = max(p[1] for p in positions) + 10
            font.render_to(surf, (cx - 12, cy), sl, COL_TEXT_DIM, size=label_size)
