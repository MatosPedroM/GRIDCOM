"""
src/display/editor.py

GridEditor: in-game drag-and-drop layout editor.

Active when constants.EDITOR_MODE is True (toggle with CTRL+SHIFT+E).
Hit-test buses and station anchors, drag to new positions, press S to save.

Positions are persisted to src/assets/layout.json via layout_override.py.
GridCanvas.rebuild() is called on mouse-up to reflect the new layout.
"""

from __future__ import annotations

import pygame
import pygame.freetype

from data.topology import BUSES
from data.fleet import STATION_POSITIONS
from data.layout_override import (
    get_bus_pos, get_station_pos,
    set_bus_pos, set_station_pos,
    save_layout,
)
from display.palette import (
    COL_TEXT_PRIMARY, COL_EDITOR_LABEL, COL_EDITOR_DIRTY, COL_EDITOR_CLEAN,
    COL_EDITOR_HIGHLIGHT,
)
from simulation.constants import FONT_SIZE_OVERLAY, CANVAS_HEIGHT

_HIT_RADIUS: int = 14   # px — hit-test radius for buses and station anchors


class GridEditor:
    """
    In-game drag-and-drop layout editor.

    Usage:
        editor = GridEditor(canvas)
        # in event loop:
        editor.on_mouse_down(native_pos)
        editor.on_mouse_move(native_pos)
        editor.on_mouse_up(native_pos)
        editor.save()
        # after canvas.rebuild():
        editor.set_canvas(new_canvas)
        # in render loop:
        editor.draw_overlay(native_surf, font)
    """

    def __init__(self, canvas) -> None:
        self._canvas = canvas

        self._dragging:    str | None          = None   # element label
        self._drag_type:   str | None          = None   # 'bus' or 'station'
        self._drag_offset: tuple[int, int]     = (0, 0) # click pos relative to element centre
        self._hover_label: str | None          = None
        self._hover_type:  str | None          = None
        self._drag_pos:    tuple[int, int]     = (0, 0) # current drag position
        self._dirty:       bool                = False

    def set_canvas(self, canvas) -> None:
        self._canvas = canvas

    # ─── Event handlers ───────────────────────────────────────────────────────

    def on_mouse_down(self, pos: tuple[int, int]) -> None:
        label, kind = self._hit_test(pos)
        if label is None:
            return
        self._dragging  = label
        self._drag_type = kind
        ex, ey = self._element_pos(label, kind)
        self._drag_offset = (ex - pos[0], ey - pos[1])
        self._drag_pos = (ex, ey)

    def on_mouse_move(self, pos: tuple[int, int]) -> None:
        mx, my = pos
        ox, oy = self._drag_offset

        if self._dragging is not None:
            new_x = mx + ox
            new_y = my + oy
            new_x = max(0, min(1919, new_x))
            new_y = max(0, min(CANVAS_HEIGHT - 1, new_y))
            self._drag_pos = (new_x, new_y)
            # Update override in real-time so the overlay tracks the drag
            if self._drag_type == 'bus':
                set_bus_pos(self._dragging, new_x, new_y)
            else:
                set_station_pos(self._dragging, new_x, new_y)
        else:
            label, kind = self._hit_test(pos)
            self._hover_label = label
            self._hover_type  = kind

    def on_mouse_up(self, pos: tuple[int, int]) -> None:
        if self._dragging is None:
            return
        mx, my = pos
        ox, oy = self._drag_offset
        new_x = max(0, min(1919, mx + ox))
        new_y = max(0, min(CANVAS_HEIGHT - 1, my + oy))
        if self._drag_type == 'bus':
            set_bus_pos(self._dragging, new_x, new_y)
        else:
            set_station_pos(self._dragging, new_x, new_y)
        self._dirty    = True
        self._dragging = None
        # Rebuild canvas so lines redraw from new positions
        self._canvas.rebuild()

    def save(self) -> None:
        save_layout()
        self._dirty = False

    # ─── Overlay ──────────────────────────────────────────────────────────────

    def draw_overlay(self, surf: pygame.Surface, font: pygame.freetype.Font) -> None:
        # 'EDIT MODE' banner — top centre
        banner = 'EDIT MODE'
        rect = font.get_rect(banner, size=FONT_SIZE_OVERLAY)
        bx = (surf.get_width() - rect.width) // 2
        font.render_to(surf, (bx, 4), banner, COL_EDITOR_LABEL, size=FONT_SIZE_OVERLAY)

        # Save indicator — top right
        save_col = COL_EDITOR_DIRTY if self._dirty else COL_EDITOR_CLEAN
        font.render_to(surf, (surf.get_width() - 80, 4),
                       '[S] Save', save_col, size=FONT_SIZE_OVERLAY)

        # Highlight hovered element
        if self._hover_label is not None and self._dragging is None:
            hx, hy = self._element_pos(self._hover_label, self._hover_type)
            pygame.draw.circle(surf, COL_EDITOR_HIGHLIGHT, (hx, hy), _HIT_RADIUS, 1)

        # Show dragged element label + live coordinates
        if self._dragging is not None:
            dx, dy = self._drag_pos
            pygame.draw.circle(surf, COL_EDITOR_HIGHLIGHT, (dx, dy), _HIT_RADIUS, 2)
            info = f'{self._dragging}  {dx},{dy}'
            font.render_to(surf, (4, 18), info, COL_EDITOR_LABEL, size=FONT_SIZE_OVERLAY)

    # ─── Internals ────────────────────────────────────────────────────────────

    def _hit_test(self, pos: tuple[int, int]) -> tuple[str | None, str | None]:
        """Return (label, kind) for the element closest to pos, or (None, None)."""
        mx, my = pos

        # Buses have priority (drawn on top of station anchors)
        best_d2 = _HIT_RADIUS * _HIT_RADIUS
        best_label: str | None = None
        best_kind:  str | None = None

        for bus in BUSES:
            bx, by = get_bus_pos(bus.label, bus.canvas_x, bus.canvas_y)
            d2 = (mx - bx) ** 2 + (my - by) ** 2
            if d2 <= best_d2:
                best_d2    = d2
                best_label = bus.label
                best_kind  = 'bus'

        if best_label is not None:
            return best_label, best_kind

        # Station anchors
        for sl, default in STATION_POSITIONS.items():
            sx, sy = get_station_pos(sl, default)
            d2 = (mx - sx) ** 2 + (my - sy) ** 2
            if d2 <= best_d2:
                best_d2    = d2
                best_label = sl
                best_kind  = 'station'

        return best_label, best_kind

    def _element_pos(self, label: str, kind: str | None) -> tuple[int, int]:
        if kind == 'bus':
            for bus in BUSES:
                if bus.label == label:
                    return get_bus_pos(label, bus.canvas_x, bus.canvas_y)
        else:
            default = STATION_POSITIONS.get(label, (0, 0))
            return get_station_pos(label, default)
        return (0, 0)
