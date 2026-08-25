"""
src/display/editor.py

GridEditor: in-game drag-and-drop layout editor.

Active when constants.EDITOR_MODE is True (toggle with CTRL+SHIFT+E).
Hit-test buses and station anchors, drag to new positions, press S to save.

Positions are persisted to src/assets/layout.json via layout_override.py.
GridCanvas.rebuild() is called on mouse-up to reflect the new layout.

All mouse coordinates are in physical (scaled) pixel space — the same space
used by the rest of the renderer.  Layout overrides are stored in logical
1920×1080 space and scaled on read.
"""

from __future__ import annotations

import pygame
import pygame.freetype

from data.layout_override import (
    get_bus_pos, get_station_pos,
    set_bus_pos, set_station_pos,
    save_layout,
    get_label_anchor, set_label_anchor,
)
from display.palette import (
    COL_TEXT_PRIMARY, COL_EDITOR_LABEL, COL_EDITOR_DIRTY, COL_EDITOR_CLEAN,
    COL_EDITOR_HIGHLIGHT,
)
from simulation.constants import FONT_SIZE_OVERLAY, CANVAS_HEIGHT

_HIT_RADIUS: int = 14   # px — hit-test radius in physical pixel space
_ANCHOR_CYCLE: tuple[str, ...] = ('top', 'right', 'bottom', 'left')


class GridEditor:
    """
    In-game drag-and-drop layout editor.

    Usage:
        editor = GridEditor(canvas, scale)
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

    def __init__(self, canvas, scale: float = 1.0) -> None:
        self._canvas = canvas
        self._scale  = scale

        self._dragging:    str | None          = None
        self._drag_type:   str | None          = None   # 'bus' or 'station'
        self._drag_offset: tuple[int, int]     = (0, 0)
        self._hover_label: str | None          = None
        self._hover_type:  str | None          = None
        self._drag_pos:    tuple[int, int]     = (0, 0)
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
            new_x = max(0, min(int(1919 * self._scale), new_x))
            new_y = max(0, min(int((CANVAS_HEIGHT - 1) * self._scale), new_y))
            self._drag_pos = (new_x, new_y)
            lx = int(new_x / self._scale)
            ly = int(new_y / self._scale)
            if self._drag_type == 'bus':
                set_bus_pos(self._dragging, lx, ly)
            else:
                set_station_pos(self._dragging, lx, ly)
        else:
            label, kind = self._hit_test(pos)
            self._hover_label = label
            self._hover_type  = kind

    def on_mouse_up(self, pos: tuple[int, int]) -> None:
        if self._dragging is None:
            return
        mx, my = pos
        ox, oy = self._drag_offset
        new_x = max(0, min(int(1919 * self._scale), mx + ox))
        new_y = max(0, min(int((CANVAS_HEIGHT - 1) * self._scale), my + oy))
        lx = int(new_x / self._scale)
        ly = int(new_y / self._scale)
        if self._drag_type == 'bus':
            set_bus_pos(self._dragging, lx, ly)
        else:
            set_station_pos(self._dragging, lx, ly)
        self._dirty    = True
        self._dragging = None
        self._canvas.rebuild()

    def on_key_r(self) -> None:
        """Rotate label anchor clockwise for the hovered (or dragged) element."""
        label = self._hover_label or self._dragging
        if label is None:
            return
        current = get_label_anchor(label)
        idx = _ANCHOR_CYCLE.index(current) if current in _ANCHOR_CYCLE else 1
        set_label_anchor(label, _ANCHOR_CYCLE[(idx + 1) % 4])
        self._dirty = True
        self._canvas.rebuild()

    def save(self) -> None:
        save_layout()
        self._dirty = False

    # ─── Overlay ──────────────────────────────────────────────────────────────

    def draw_overlay(self, surf: pygame.Surface, font: pygame.freetype.Font) -> None:
        banner = 'EDIT MODE'
        rect = font.get_rect(banner, size=FONT_SIZE_OVERLAY)
        bx = (surf.get_width() - rect.width) // 2
        font.render_to(surf, (bx, 4), banner, COL_EDITOR_LABEL, size=FONT_SIZE_OVERLAY)

        save_col = COL_EDITOR_DIRTY if self._dirty else COL_EDITOR_CLEAN
        font.render_to(surf, (surf.get_width() - 80, 4),
                       '[S] Save', save_col, size=FONT_SIZE_OVERLAY)

        if self._hover_label is not None and self._dragging is None:
            hx, hy = self._element_pos(self._hover_label, self._hover_type)
            pygame.draw.circle(surf, COL_EDITOR_HIGHLIGHT, (hx, hy), _HIT_RADIUS, 1)

        if self._dragging is not None:
            dx, dy = self._drag_pos
            pygame.draw.circle(surf, COL_EDITOR_HIGHLIGHT, (dx, dy), _HIT_RADIUS, 2)
            lx = int(dx / self._scale)
            ly = int(dy / self._scale)
            anchor = get_label_anchor(self._dragging)
            info = f'{self._dragging}  {lx},{ly}  [{anchor}]'
            font.render_to(surf, (4, 18), info, COL_EDITOR_LABEL, size=FONT_SIZE_OVERLAY)

    # ─── Internals ────────────────────────────────────────────────────────────

    def _hit_test(self, pos: tuple[int, int]) -> tuple[str | None, str | None]:
        """
        Return (label, kind) for the element closest to pos, or (None, None).

        Only tests elements active in the current shift (from canvas._buses and
        canvas._station_units).  All coords are in physical pixel space.
        """
        mx, my = pos
        sc = self._scale

        best_d2 = _HIT_RADIUS * _HIT_RADIUS
        best_label: str | None = None
        best_kind:  str | None = None

        # Buses — use canvas._buses so only shift-active buses are checked
        for bus in self._canvas._buses:
            bx, by = get_bus_pos(bus.label, bus.canvas_x, bus.canvas_y)
            bx = int(bx * sc)
            by = int(by * sc)
            d2 = (mx - bx) ** 2 + (my - by) ** 2
            if d2 <= best_d2:
                best_d2    = d2
                best_label = bus.label
                best_kind  = 'bus'

        if best_label is not None:
            return best_label, best_kind

        # Station anchors — only shift-active stations
        for sl in self._canvas._station_units:
            default = self._default_station_pos(sl)
            sx, sy = get_station_pos(sl, default)
            sx = int(sx * sc)
            sy = int(sy * sc)
            d2 = (mx - sx) ** 2 + (my - sy) ** 2
            if d2 <= best_d2:
                best_d2    = d2
                best_label = sl
                best_kind  = 'station'

        return best_label, best_kind

    def _element_pos(self, label: str, kind: str | None) -> tuple[int, int]:
        sc = self._scale
        if kind == 'bus':
            for bus in self._canvas._buses:
                if bus.label == label:
                    bx, by = get_bus_pos(label, bus.canvas_x, bus.canvas_y)
                    return int(bx * sc), int(by * sc)
        else:
            default = self._default_station_pos(label)
            sx, sy = get_station_pos(label, default)
            return int(sx * sc), int(sy * sc)
        return (0, 0)

    def _default_station_pos(self, station_label: str) -> tuple[int, int]:
        """
        Fallback station anchor when no layout override exists yet: 20px
        (native-space) above the station's own bus, mirroring
        GridCanvas.load_designer_topology()'s identical fallback. Replaces
        the old fleet.py STATION_POSITIONS dict lookup — every station now
        gets a sensible default from its own bus rather than a hardcoded
        campaign-specific position table.
        """
        units = self._canvas._station_units.get(station_label)
        if not units:
            return (0, 0)
        bus_label = units[0].bus_label
        bx, by = self._canvas._bus_pos.get(bus_label, (0, 0))
        return (int(bx / self._scale), int(by / self._scale - 20))
