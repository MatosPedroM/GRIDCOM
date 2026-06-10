"""
src/display/designer.py

GridDesigner — development-only visual grid topology editor.

Entered from the main menu → GRID DESIGNER.
Allows placing buses, generation units, and transmission lines on the
1920×844 canvas, then auto-routing lines using DC load flow.
Saves to assets/designer_grids/<name>.json.

Coordinate system: all positions are in native 1920×1080 space.
The canvas area is DESIGNER_CANVAS_W (1600) px wide; the right 320 px is
the sidebar (drawn by designer_panels.py).
"""

from __future__ import annotations

import math
import copy
from typing import Callable

import pygame
import pygame.freetype

from data.designer_io import (
    DesignerBus, DesignerLine, DesignerUnit,
    save_designer_grid_named, load_designer_grid_named,
    list_designer_grids,
    next_bus_label, next_station_label, next_line_label,
    UNIT_DEFAULTS,
)
from display.palette import (
    COL_BACKGROUND, COL_TEXT_PRIMARY, COL_TEXT_SECONDARY, COL_TEXT_DIM,
    COL_TEXT_VALUE, COL_TEXT_HEADING, COL_TEXT_WARN, COL_TEXT_CRIT,
    COL_BUS_400KV, COL_BUS_220KV, COL_BUS_150KV, COL_BUS_60KV,
    COL_400KV, COL_220KV, COL_150KV, COL_60KV,
    COL_LINE_ENERGISED, COL_LOAD_WARN, COL_LINE_NORMAL, COL_LINE_TRIPPED,
    COL_SELECTION, COL_PANEL_BORDER,
    COL_DESIGNER_SIDEBAR_BG, COL_DESIGNER_SIDEBAR_SEP,
    COL_DESIGNER_LINE_DRAW, COL_DESIGNER_STATUS_OK, COL_DESIGNER_STATUS_INFO,
    COL_DESIGNER_SURPLUS_POS, COL_DESIGNER_SURPLUS_NEG,
    COL_DESIGNER_DELETE_CURSOR,
    COL_UNIT_COAL, COL_UNIT_CCGT, COL_UNIT_NUCLEAR,
    COL_UNIT_HYDRO, COL_UNIT_WIND, COL_UNIT_SOLAR, COL_UNIT_HYDRO_PUMP,
    COL_UNIT_OFFLINE, COL_UNIT_BORDER,
)
from display.symbols import (
    draw_substation, draw_load_substation, draw_unit_square,
    draw_transmission_line, BUS_SIZE, UNIT_SIZE, UNIT_GAP,
)
from simulation.constants import (
    NATIVE_WIDTH, NATIVE_HEIGHT, CANVAS_HEIGHT,
    DESIGNER_SIDEBAR_W, DESIGNER_CANVAS_W,
    DESIGNER_X_SCALE, DESIGNER_TARGET_LOADING_PCT, DESIGNER_N1_OVERLOAD_PCT,
    DESIGNER_STATUS_DISPLAY_S, DESIGNER_HIT_RADIUS, DESIGNER_LINE_HIT_PX,
    DESIGNER_FONT_SIZE, DESIGNER_FONT_SIZE_LARGE, DESIGNER_UNDO_MAX,
    DESIGNER_DEFAULT_RATING, DESIGNER_LINE_RATING_PRESETS,
    YSHUNT_REG, S_BASE,
)
from utils.helpers import resource_path


# ─────────────────────────────────────────────────────────────────────────────
# PALETTE MODE CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

MODE_SELECT  = 'SELECT'
MODE_BUS     = 'BUS'
MODE_UNIT    = 'UNIT'
MODE_LINE    = 'LINE'
MODE_DELETE  = 'DELETE'

# Voltage → canvas colour
_VOLT_COLOUR: dict[float, tuple] = {
    400.0: COL_BUS_400KV,
    220.0: COL_BUS_220KV,
    150.0: COL_BUS_150KV,
     60.0: COL_BUS_60KV,
}

_VOLT_LINE_COLOUR: dict[float, tuple] = {
    400.0: COL_400KV,
    220.0: COL_220KV,
    150.0: COL_150KV,
     60.0: COL_60KV,
}

_UNIT_TYPE_COLOUR: dict[str, tuple] = {
    'COAL':       COL_UNIT_COAL,
    'CCGT':       COL_UNIT_CCGT,
    'NUCLEAR':    COL_UNIT_NUCLEAR,
    'HYDRO':      COL_UNIT_HYDRO,
    'HYDRO_ROR':  COL_UNIT_HYDRO,
    'HYDRO_PUMP': COL_UNIT_HYDRO_PUMP,
    'WIND':       COL_UNIT_WIND,
    'SOLAR':      COL_UNIT_SOLAR,
}

_ANCHOR_CYCLE = ('top', 'right', 'bottom', 'left')


class GridDesigner:
    """
    Visual grid topology editor.  Owns its own rendering and event handling.

    Call draw(native_surf) each frame, and route pygame events to
    on_click, on_key, on_mouse_down, on_mouse_up, on_mouse_move.
    """

    def __init__(self, display_surf: pygame.Surface) -> None:
        self._display_surf = display_surf
        dw, dh = display_surf.get_size()
        self._scale = min(dw / NATIVE_WIDTH, dh / NATIVE_HEIGHT)
        ox = (dw - int(NATIVE_WIDTH  * self._scale)) // 2
        oy = (dh - int(NATIVE_HEIGHT * self._scale)) // 2
        self._letterbox = pygame.Rect(ox, oy,
                                      int(NATIVE_WIDTH  * self._scale),
                                      int(NATIVE_HEIGHT * self._scale))

        # Native surface (1920×1080)
        self._native = pygame.Surface((NATIVE_WIDTH, NATIVE_HEIGHT))

        # Fonts — use the same IBMPlexMono as the main renderer
        _font_path = resource_path('assets/fonts/IBMPlexMono-Regular.ttf')
        try:
            self._font       = pygame.freetype.Font(_font_path, DESIGNER_FONT_SIZE)
            self._font_bold  = pygame.freetype.Font(_font_path, DESIGNER_FONT_SIZE)
            self._font_large = pygame.freetype.Font(_font_path, DESIGNER_FONT_SIZE_LARGE)
        except Exception:
            self._font       = pygame.freetype.SysFont('monospace', DESIGNER_FONT_SIZE)
            self._font_bold  = self._font
            self._font_large = pygame.freetype.SysFont('monospace', DESIGNER_FONT_SIZE_LARGE)

        self._font.antialiased       = False
        self._font_bold.antialiased  = False
        self._font_large.antialiased = False

        # Designer state
        self._buses:  list[DesignerBus]  = []
        self._lines:  list[DesignerLine] = []
        self._units:  list[DesignerUnit] = []

        # Selection
        self._selected_bus:  DesignerBus  | None = None
        self._selected_line: DesignerLine | None = None
        self._selected_unit: DesignerUnit | None = None

        # Palette / mode
        self._palette_mode:        str   = MODE_SELECT
        self._palette_voltage:     float = 400.0    # for MODE_BUS
        self._palette_unit_type:   str   = 'COAL'   # for MODE_UNIT
        self._palette_line_rating: float = 1200.0   # for MODE_LINE (manual placement)

        # Line-draw state
        self._line_first_bus: DesignerBus | None = None

        # Drag state (bus drag)
        self._dragging_bus:  DesignerBus | None = None
        self._drag_offset:   tuple[int, int] = (0, 0)

        # Undo stack (list of (buses_copy, lines_copy, units_copy))
        self._undo_stack: list = []

        # Status message
        self._status_text:  str   = ''
        self._status_colour: tuple = COL_DESIGNER_STATUS_INFO
        self._status_timer: float = 0.0

        # Save state
        self._dirty = False

        # Property edit state
        self._editing_field: str | None = None  # which field is being edited
        self._edit_buffer:   str        = ''

        # Dialog state (unit count, load mw)
        self._dialog_active:  bool  = False
        self._dialog_prompt:  str   = ''
        self._dialog_buffer:  str   = ''
        self._dialog_callback: Callable | None = None

        # Mouse position on canvas (native coords)
        self._mouse_pos: tuple[int, int] = (0, 0)

        # Label counter (used for auto-labelling)
        self._used_bus_labels:     set[str] = set()
        self._used_station_labels: set[str] = set()
        self._used_line_labels:    set[str] = set()

        # Named file save/load sidebar state
        # _sidebar_mode: 'normal', 'save_dialog', 'load_browser', 'test_browser'
        self._sidebar_mode:      str        = 'normal'
        self._grid_name:         str        = ''          # current file name
        self._save_dialog_buf:   str        = ''          # name being typed
        self._load_browser_list: list[str]  = []          # available grid names
        self._load_browser_idx:  int        = 0           # highlighted row
        self._load_browser_scroll: int      = 0           # top visible row

        # Callback from main.py: called when user picks a grid to test.
        # Signature: (grid_name: str) -> None
        self.on_test_request = None

    # ─── Public event interface ───────────────────────────────────────────────

    def to_native(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Convert display coords to native surface coords."""
        nx = int((pos[0] - self._letterbox.left) / self._scale)
        ny = int((pos[1] - self._letterbox.top)  / self._scale)
        return (
            max(0, min(NATIVE_WIDTH  - 1, nx)),
            max(0, min(NATIVE_HEIGHT - 1, ny)),
        )

    def on_mouse_move(self, native_pos: tuple[int, int]) -> None:
        self._mouse_pos = native_pos
        if self._dragging_bus is not None:
            nx = native_pos[0] + self._drag_offset[0]
            ny = native_pos[1] + self._drag_offset[1]
            nx = max(0, min(DESIGNER_CANVAS_W - 1, nx))
            ny = max(0, min(CANVAS_HEIGHT - 1, ny))
            self._dragging_bus.canvas_x = nx
            self._dragging_bus.canvas_y = ny

    def on_mouse_down(self, native_pos: tuple[int, int]) -> None:
        if self._dialog_active:
            return
        # Only drag in SELECT mode over the canvas area
        if self._palette_mode != MODE_SELECT:
            return
        if native_pos[0] >= DESIGNER_CANVAS_W:
            return
        bus = self._hit_bus(native_pos)
        if bus is not None:
            self._dragging_bus   = bus
            self._drag_offset    = (bus.canvas_x - native_pos[0],
                                    bus.canvas_y - native_pos[1])

    def on_mouse_up(self, native_pos: tuple[int, int]) -> None:
        if self._dragging_bus is not None:
            self._dragging_bus = None
            self._dirty = True

    def on_click(self, native_pos: tuple[int, int]) -> None:
        if self._dialog_active:
            return

        x, y = native_pos

        # Sidebar click → delegate to panel handler
        if x >= DESIGNER_CANVAS_W:
            self._handle_sidebar_click(x - DESIGNER_CANVAS_W, y)
            return

        # Canvas click
        if self._palette_mode == MODE_SELECT:
            self._do_select(native_pos)

        elif self._palette_mode == MODE_BUS:
            self._do_place_bus(x, y)

        elif self._palette_mode == MODE_UNIT:
            bus = self._hit_bus(native_pos)
            if bus is not None:
                self._ask_unit_count(bus)

        elif self._palette_mode == MODE_LINE:
            bus = self._hit_bus(native_pos)
            if bus is not None:
                if self._line_first_bus is None:
                    self._line_first_bus = bus
                    self._set_status(f'Click second bus to connect  (first: {bus.label})',
                                     COL_DESIGNER_STATUS_INFO)
                elif bus is not self._line_first_bus:
                    self._push_undo()
                    self._place_line(self._line_first_bus, bus)
                    self._line_first_bus = None
                    self._palette_mode = MODE_SELECT

        elif self._palette_mode == MODE_DELETE:
            self._do_delete_at(native_pos)

    def on_key(self, event: pygame.event.Event) -> bool:
        """Handle a KEYDOWN event.  Returns True if consumed."""
        if self._dialog_active:
            return self._handle_dialog_key(event)

        # Sidebar overlay modes have their own key handling
        if self._sidebar_mode == 'save_dialog':
            return self._handle_save_dialog_key(event)
        if self._sidebar_mode in ('load_browser', 'test_browser'):
            return self._handle_load_browser_key(event)

        if self._editing_field is not None:
            return self._handle_edit_key(event)

        mods  = pygame.key.get_mods()
        ctrl  = bool(mods & pygame.KMOD_CTRL)
        shift = bool(mods & pygame.KMOD_SHIFT)

        if event.key == pygame.K_ESCAPE:
            if self._line_first_bus is not None:
                self._line_first_bus = None
                self._palette_mode   = MODE_SELECT
                return True
            elif self._palette_mode != MODE_SELECT:
                self._palette_mode = MODE_SELECT
                return True
            elif (self._selected_bus is not None or
                  self._selected_line is not None or
                  self._selected_unit is not None):
                self._clear_selection()
                return True
            else:
                return False  # nothing to dismiss — let main.py exit the designer

        if ctrl and event.key == pygame.K_s:
            self._open_save_dialog()
            return True

        if ctrl and event.key == pygame.K_z:
            self._undo()
            return True

        if ctrl and event.key == pygame.K_r:
            self._auto_route()
            return True

        if ctrl and event.key == pygame.K_t:
            self._open_test_browser()
            return True

        if event.key == pygame.K_l:
            self._palette_mode = MODE_LINE
            self._line_first_bus = None
            return True

        if event.key == pygame.K_d and not ctrl:
            self._palette_mode = (MODE_SELECT if self._palette_mode == MODE_DELETE
                                  else MODE_DELETE)
            return True

        if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            self._delete_selected()
            return True

        if event.key == pygame.K_r and not ctrl:
            # Rotate label anchor on selected bus
            if self._selected_bus is not None:
                cur = self._selected_bus.label_anchor
                idx = (_ANCHOR_CYCLE.index(cur) + 1) % len(_ANCHOR_CYCLE)
                self._selected_bus.label_anchor = _ANCHOR_CYCLE[idx]
                self._dirty = True
            return True

        if event.key == pygame.K_e and not ctrl:
            if self._selected_bus is not None:
                self._start_edit('label', self._selected_bus.label)
            return True

        if event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
            self._change_active_shift(+1)
            return True

        if event.key == pygame.K_MINUS:
            self._change_active_shift(-1)
            return True

        return False

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _clear_selection(self) -> None:
        self._selected_bus  = None
        self._selected_line = None
        self._selected_unit = None
        self._editing_field = None
        self._edit_buffer   = ''

    def _set_status(self, text: str, colour: tuple = None) -> None:
        self._status_text   = text
        self._status_colour = colour or COL_DESIGNER_STATUS_INFO
        self._status_timer  = DESIGNER_STATUS_DISPLAY_S

    def _push_undo(self) -> None:
        snapshot = (
            copy.deepcopy(self._buses),
            copy.deepcopy(self._lines),
            copy.deepcopy(self._units),
        )
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > DESIGNER_UNDO_MAX:
            self._undo_stack.pop(0)

    def _undo(self) -> None:
        if not self._undo_stack:
            self._set_status('Nothing to undo', COL_DESIGNER_STATUS_INFO)
            return
        self._buses, self._lines, self._units = self._undo_stack.pop()
        self._clear_selection()
        self._dirty = True
        self._set_status('Undo', COL_DESIGNER_STATUS_INFO)

    def _open_save_dialog(self) -> None:
        self._sidebar_mode    = 'save_dialog'
        self._save_dialog_buf = self._grid_name  # pre-fill with current name

    def _open_load_browser(self) -> None:
        self._sidebar_mode       = 'load_browser'
        self._load_browser_list  = list_designer_grids()
        self._load_browser_idx   = 0
        self._load_browser_scroll = 0

    def _open_test_browser(self) -> None:
        self._sidebar_mode       = 'test_browser'
        self._load_browser_list  = list_designer_grids()
        self._load_browser_idx   = 0
        self._load_browser_scroll = 0

    def _close_sidebar_overlay(self) -> None:
        self._sidebar_mode = 'normal'

    def _handle_save_dialog_key(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_RETURN:
            name = self._save_dialog_buf.strip()
            if name:
                self._commit_save(name)
            self._sidebar_mode = 'normal'
            return True
        if event.key == pygame.K_ESCAPE:
            self._sidebar_mode = 'normal'
            return True
        if event.key == pygame.K_BACKSPACE:
            self._save_dialog_buf = self._save_dialog_buf[:-1]
            return True
        if event.unicode:
            ch = event.unicode
            if ch.isalnum() or ch == '_':
                self._save_dialog_buf += ch
            return True
        return True

    def _commit_save(self, name: str) -> None:
        try:
            save_designer_grid_named(self._buses, self._lines, self._units, name)
            self._grid_name = name
            self._dirty = False
            self._set_status(f'Saved: {name}', COL_DESIGNER_STATUS_OK)
        except Exception as e:
            self._set_status(f'Save failed: {e}', COL_DESIGNER_STATUS_INFO)

    def _handle_load_browser_key(self, event: pygame.event.Event) -> bool:
        lst = self._load_browser_list
        if event.key == pygame.K_ESCAPE:
            self._sidebar_mode = 'normal'
            return True
        if event.key in (pygame.K_UP, pygame.K_w):
            self._load_browser_idx = max(0, self._load_browser_idx - 1)
            return True
        if event.key in (pygame.K_DOWN, pygame.K_s):
            self._load_browser_idx = min(len(lst) - 1, self._load_browser_idx + 1)
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if lst:
                name = lst[self._load_browser_idx]
                if self._sidebar_mode == 'test_browser':
                    self._sidebar_mode = 'normal'
                    if self.on_test_request is not None:
                        self.on_test_request(name)
                else:
                    self._commit_load(name)
                    self._sidebar_mode = 'normal'
            return True
        return True

    def _commit_load(self, name: str) -> None:
        try:
            buses, lines, units = load_designer_grid_named(name)
            self._buses  = buses
            self._lines  = lines
            self._units  = units
            self._used_bus_labels     = {b.label for b in buses}
            self._used_station_labels = {u.station_label for u in units}
            self._used_line_labels    = {l.label for l in lines}
            self._grid_name = name
            self._clear_selection()
            self._dirty = False
            self._set_status(f'Loaded: {name}', COL_DESIGNER_STATUS_OK)
        except Exception as e:
            self._set_status(f'Load failed: {e}', COL_DESIGNER_STATUS_INFO)

    # ─── Hit testing ─────────────────────────────────────────────────────────

    def _hit_bus(self, pos: tuple[int, int]) -> DesignerBus | None:
        px, py = pos
        best_dist = DESIGNER_HIT_RADIUS + 1
        best = None
        for b in self._buses:
            d = max(abs(b.canvas_x - px), abs(b.canvas_y - py))
            if d < best_dist:
                best_dist = d
                best = b
        return best

    def _hit_line(self, pos: tuple[int, int]) -> DesignerLine | None:
        px, py = pos
        best_dist = DESIGNER_LINE_HIT_PX + 1
        best = None
        for l in self._lines:
            b1 = self._bus_by_label(l.from_bus)
            b2 = self._bus_by_label(l.to_bus)
            if b1 is None or b2 is None:
                continue
            d = _point_segment_dist(px, py,
                                    b1.canvas_x, b1.canvas_y,
                                    b2.canvas_x, b2.canvas_y)
            if d < best_dist:
                best_dist = d
                best = l
        return best

    def _bus_by_label(self, label: str) -> DesignerBus | None:
        for b in self._buses:
            if b.label == label:
                return b
        return None

    # ─── Placement ───────────────────────────────────────────────────────────

    def _do_place_bus(self, x: int, y: int) -> None:
        vkv = self._palette_voltage
        if vkv == 60.0:
            # Ask for peak load
            self._dialog_prompt  = 'Peak load MW (60kV bus):'
            self._dialog_buffer  = '100'
            self._dialog_active  = True
            self._dialog_callback = lambda mw_str: self._finish_place_load_bus(x, y, mw_str)
        else:
            self._push_undo()
            self._place_bus(x, y, vkv, peak_load_mw=0.0)

    def _finish_place_load_bus(self, x: int, y: int, mw_str: str) -> None:
        try:
            mw = max(0.0, float(mw_str))
        except ValueError:
            mw = 100.0
        self._push_undo()
        self._place_bus(x, y, 60.0, peak_load_mw=mw)

    def _place_bus(self, x: int, y: int, voltage_kv: float,
                   peak_load_mw: float = 0.0) -> None:
        label    = next_bus_label(self._used_bus_labels)
        bus_type = 'LOAD' if voltage_kv == 60.0 else 'TRANSMISSION'
        bus = DesignerBus(
            label=label,
            name=label,
            voltage_kv=voltage_kv,
            bus_type=bus_type,
            canvas_x=x,
            canvas_y=y,
            active_from_shift=1,
            is_slack=len(self._buses) == 0,  # first bus placed becomes slack
            peak_load_mw=peak_load_mw,
            label_anchor='right',
        )
        self._buses.append(bus)
        self._used_bus_labels.add(label)
        self._selected_bus  = bus
        self._selected_line = None
        self._selected_unit = None
        self._palette_mode  = MODE_SELECT
        self._dirty = True

    def _ask_unit_count(self, bus: DesignerBus) -> None:
        self._dialog_prompt  = f'How many {self._palette_unit_type} units at {bus.label}?'
        self._dialog_buffer  = '1'
        self._dialog_active  = True
        self._dialog_callback = lambda s: self._finish_place_units(bus, s)

    def _finish_place_units(self, bus: DesignerBus, count_str: str) -> None:
        try:
            count = max(1, min(6, int(count_str)))
        except ValueError:
            count = 1
        self._push_undo()
        unit_type = self._palette_unit_type
        station_label = next_station_label(self._used_station_labels)
        self._used_station_labels.add(station_label)
        defaults = UNIT_DEFAULTS.get(unit_type, UNIT_DEFAULTS['COAL'])
        for i in range(1, count + 1):
            unit_label = f'{station_label}-{i}'
            unit = DesignerUnit(
                label=unit_label,
                station_label=station_label,
                bus_label=bus.label,
                unit_type=unit_type,
                rated_mw=defaults['rated_mw'],
                min_mw=defaults['min_mw'],
                ramp_pct_per_min=defaults['ramp_pct_per_min'],
                inertia_h=defaults['inertia_h'],
                cold_start_min=defaults['cold_start_min'],
                q_max_mvar=defaults['q_max_mvar'],
                q_min_mvar=defaults['q_min_mvar'],
                can_pump=(unit_type == 'HYDRO_PUMP'),
                active_from_shift=1,
                description=f'{station_label} {unit_type} unit {i}',
            )
            self._units.append(unit)
        self._palette_mode = MODE_SELECT
        self._dirty = True
        self._set_status(f'Placed {count}× {unit_type} at {bus.label}',
                         COL_DESIGNER_STATUS_OK)

    def _place_line(self, b1: DesignerBus, b2: DesignerBus,
                    rating_override: float | None = None) -> None:
        # Infer voltage: lower of the two endpoints
        vkv  = min(b1.voltage_kv, b2.voltage_kv)
        dist = math.hypot(b2.canvas_x - b1.canvas_x, b2.canvas_y - b1.canvas_y)
        x_pu = max(0.010, dist / NATIVE_WIDTH * DESIGNER_X_SCALE * 10)
        # Manual placement uses the user-selected rating; auto-route passes its own
        rating = rating_override if rating_override is not None else self._palette_line_rating
        label  = next_line_label(self._used_line_labels)
        line = DesignerLine(
            label=label,
            from_bus=b1.label,
            to_bus=b2.label,
            reactance_pu=round(x_pu, 4),
            rating_mw=rating,
            voltage_kv=vkv,
            active_from_shift=1,
            active_until_shift=99,
        )
        self._lines.append(line)
        self._used_line_labels.add(label)
        self._selected_line = line
        self._dirty = True
        self._set_status(f'Line {label}: {b1.label}↔{b2.label}  {vkv:.0f}kV  {rating:.0f}MW',
                         COL_DESIGNER_STATUS_OK)

    # ─── Selection ───────────────────────────────────────────────────────────

    def _do_select(self, pos: tuple[int, int]) -> None:
        self._editing_field = None
        self._edit_buffer   = ''
        bus = self._hit_bus(pos)
        if bus is not None:
            if self._selected_bus is bus:
                self._clear_selection()
            else:
                self._selected_bus  = bus
                self._selected_line = None
                self._selected_unit = None
            return
        line = self._hit_line(pos)
        if line is not None:
            self._selected_line = line
            self._selected_bus  = None
            self._selected_unit = None
            return
        self._clear_selection()

    # ─── Delete ──────────────────────────────────────────────────────────────

    def _do_delete_at(self, pos: tuple[int, int]) -> None:
        bus = self._hit_bus(pos)
        if bus is not None:
            self._push_undo()
            self._remove_bus(bus)
            return
        line = self._hit_line(pos)
        if line is not None:
            self._push_undo()
            self._lines.remove(line)
            self._used_line_labels.discard(line.label)
            self._dirty = True
            return

    def _delete_selected(self) -> None:
        if self._selected_bus is not None:
            self._push_undo()
            self._remove_bus(self._selected_bus)
        elif self._selected_line is not None:
            self._push_undo()
            self._lines.remove(self._selected_line)
            self._used_line_labels.discard(self._selected_line.label)
            self._selected_line = None
            self._dirty = True

    def _remove_bus(self, bus: DesignerBus) -> None:
        lbl = bus.label
        self._buses  = [b for b in self._buses  if b.label != lbl]
        self._lines  = [l for l in self._lines
                        if l.from_bus != lbl and l.to_bus != lbl]
        self._units  = [u for u in self._units  if u.bus_label != lbl]
        self._used_bus_labels.discard(lbl)
        self._used_line_labels = {l.label for l in self._lines}
        self._clear_selection()
        self._dirty = True

    # ─── Sidebar interaction ─────────────────────────────────────────────────

    def _handle_sidebar_click(self, sx: int, sy: int) -> None:
        """sx, sy are relative to sidebar left edge."""
        # In overlay mode, route clicks to the overlay handler in designer_panels
        if self._sidebar_mode in ('save_dialog', 'load_browser', 'test_browser'):
            from display.designer_panels import sidebar_overlay_click_at
            action = sidebar_overlay_click_at(sx, sy, self)
            if action == 'load_browser_item':
                pass   # already handled by sidebar_overlay_click_at via select callback
            elif action == 'overlay_cancel':
                self._sidebar_mode = 'normal'
            elif action == 'save_dialog_commit':
                name = self._save_dialog_buf.strip()
                if name:
                    self._commit_save(name)
                self._sidebar_mode = 'normal'
            elif action and action.startswith('browser_select:'):
                name = action[len('browser_select:'):]
                if self._sidebar_mode == 'test_browser':
                    self._sidebar_mode = 'normal'
                    if self.on_test_request is not None:
                        self.on_test_request(name)
                else:
                    self._commit_load(name)
                    self._sidebar_mode = 'normal'
            return

        from display.designer_panels import sidebar_button_at
        action = sidebar_button_at(sx, sy, self)
        if action is None:
            return

        if action.startswith('bus_'):
            self._palette_mode    = MODE_BUS
            self._palette_voltage = float(action.split('_')[1])
            self._line_first_bus  = None

        elif action.startswith('unit_'):
            self._palette_mode      = MODE_UNIT
            self._palette_unit_type = action[5:]
            self._line_first_bus    = None

        elif action == 'delete':
            self._palette_mode = MODE_DELETE

        elif action == 'line_mode':
            self._palette_mode   = MODE_LINE
            self._line_first_bus = None

        elif action == 'line_rating_up':
            self._cycle_line_rating(+1)

        elif action == 'line_rating_down':
            self._cycle_line_rating(-1)

        elif action == 'auto_route':
            self._auto_route()

        elif action == 'clear_lines':
            self._push_undo()
            self._lines.clear()
            self._used_line_labels.clear()
            self._dirty = True
            self._set_status('All lines cleared', COL_DESIGNER_STATUS_INFO)

        elif action == 'save':
            self._open_save_dialog()

        elif action == 'load':
            self._open_load_browser()

        elif action == 'test_grid':
            self._open_test_browser()

        elif action == 'export_preview':
            self._export_preview()

        elif action == 'prop_shift_plus':
            self._change_active_shift(+1)

        elif action == 'prop_shift_minus':
            self._change_active_shift(-1)

        elif action == 'prop_slack_toggle':
            if self._selected_bus is not None:
                for b in self._buses:
                    b.is_slack = False
                self._selected_bus.is_slack = True
                self._dirty = True

        elif action == 'edit_reactance_pu':
            if self._selected_line is not None:
                self._start_edit('reactance_pu', f'{self._selected_line.reactance_pu:.4f}')

        elif action == 'edit_rating_mw':
            if self._selected_line is not None:
                self._start_edit('rating_mw', f'{self._selected_line.rating_mw:.0f}')

    # ─── Property editing ────────────────────────────────────────────────────

    def _start_edit(self, field: str, current: str) -> None:
        self._editing_field = field
        self._edit_buffer   = current

    def _handle_edit_key(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_RETURN:
            self._commit_edit()
            return True
        if event.key == pygame.K_ESCAPE:
            self._editing_field = None
            self._edit_buffer   = ''
            return True
        if event.key == pygame.K_BACKSPACE:
            self._edit_buffer = self._edit_buffer[:-1]
            return True
        if event.unicode and event.unicode.isprintable():
            self._edit_buffer += event.unicode
            return True
        return False

    def _commit_edit(self) -> None:
        field = self._editing_field
        val   = self._edit_buffer.strip()
        if self._selected_bus is not None and field == 'label':
            if val and val not in self._used_bus_labels:
                old = self._selected_bus.label
                self._selected_bus.label = val.upper()[:4]
                self._used_bus_labels.discard(old)
                self._used_bus_labels.add(self._selected_bus.label)
                # Update references in lines and units
                for l in self._lines:
                    if l.from_bus == old: l.from_bus = self._selected_bus.label
                    if l.to_bus   == old: l.to_bus   = self._selected_bus.label
                for u in self._units:
                    if u.bus_label == old: u.bus_label = self._selected_bus.label
                self._dirty = True
        elif self._selected_line is not None and field == 'reactance_pu':
            try:
                self._selected_line.reactance_pu = max(0.001, float(val))
                self._dirty = True
            except ValueError:
                pass
        elif self._selected_line is not None and field == 'rating_mw':
            try:
                self._selected_line.rating_mw = max(1.0, float(val))
                self._dirty = True
            except ValueError:
                pass
        self._editing_field = None
        self._edit_buffer   = ''

    def _change_active_shift(self, delta: int) -> None:
        if self._selected_bus is not None:
            self._selected_bus.active_from_shift = max(1, min(10,
                self._selected_bus.active_from_shift + delta))
            self._dirty = True
        elif self._selected_line is not None:
            self._selected_line.active_from_shift = max(1, min(10,
                self._selected_line.active_from_shift + delta))
            self._dirty = True
        elif self._selected_unit is not None:
            self._selected_unit.active_from_shift = max(1, min(10,
                self._selected_unit.active_from_shift + delta))
            self._dirty = True

    def _cycle_line_rating(self, direction: int) -> None:
        presets = DESIGNER_LINE_RATING_PRESETS
        try:
            idx = list(presets).index(self._palette_line_rating)
        except ValueError:
            idx = len(presets) // 2
        self._palette_line_rating = presets[
            max(0, min(len(presets) - 1, idx + direction))
        ]

    # ─── Dialog handling ─────────────────────────────────────────────────────

    def _handle_dialog_key(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_RETURN:
            val = self._dialog_buffer.strip()
            cb  = self._dialog_callback
            self._dialog_active   = False
            self._dialog_callback = None
            self._dialog_buffer   = ''
            if cb is not None:
                cb(val)
            return True
        if event.key == pygame.K_ESCAPE:
            self._dialog_active   = False
            self._dialog_callback = None
            self._dialog_buffer   = ''
            return True
        if event.key == pygame.K_BACKSPACE:
            self._dialog_buffer = self._dialog_buffer[:-1]
            return True
        if event.unicode and event.unicode.isprintable():
            self._dialog_buffer += event.unicode
            return True
        return False

    # ─── Auto-route ──────────────────────────────────────────────────────────

    def _auto_route(self) -> None:
        if len(self._buses) < 2:
            self._set_status('Need at least 2 buses to auto-route', COL_DESIGNER_STATUS_INFO)
            return
        self._set_status('AUTO-ROUTING...', COL_DESIGNER_STATUS_INFO)
        self._draw_frame()  # Force a frame so the message shows

        self._push_undo()
        added = _auto_route_lines(self._buses, self._lines,
                                  self._used_line_labels,
                                  self._units)
        n = len(added)
        self._lines.extend(added)
        for l in added:
            self._used_line_labels.add(l.label)
        self._dirty = True
        self._set_status(f'AUTO-ROUTE COMPLETE — {n} line{"s" if n != 1 else ""} added',
                         COL_DESIGNER_STATUS_OK)

    def _export_preview(self) -> None:
        """Run DC load flow and show loading on the canvas."""
        if not self._buses or not self._lines:
            self._set_status('No topology to preview', COL_DESIGNER_STATUS_INFO)
            return
        try:
            result = _run_loadflow(self._buses, self._lines, self._units)
            lines_shown = 0
            for label, pct in result.items():
                for l in self._lines:
                    if l.label == label:
                        l._preview_loading = pct
                        lines_shown += 1
            self._set_status(f'Preview: {lines_shown} lines computed', COL_DESIGNER_STATUS_OK)
        except Exception as e:
            self._set_status(f'Load flow error: {e}', COL_DESIGNER_STATUS_INFO)

    # ─── Drawing ─────────────────────────────────────────────────────────────

    def _draw_frame(self) -> None:
        """Draw one frame without waiting for the caller."""
        self.draw(self._display_surf)
        pygame.display.flip()

    def draw(self, display_surf: pygame.Surface) -> None:
        """Draw the full designer view to the display surface."""
        surf = self._native
        surf.fill(COL_BACKGROUND)

        self._draw_canvas(surf)
        self._draw_sidebar(surf)
        self._draw_dialog(surf)
        self._draw_status(surf)

        # Update status timer
        # (caller must track dt; status drawn as long as text is set)

        # Blit scaled to display
        scaled = pygame.transform.scale(surf,
                                        (self._letterbox.width, self._letterbox.height))
        display_surf.fill((0, 0, 0))
        display_surf.blit(scaled, self._letterbox.topleft)

    def tick(self, dt: float, display_surf: pygame.Surface) -> None:
        """Update timers and draw."""
        if self._status_timer > 0.0:
            self._status_timer -= dt
            if self._status_timer <= 0.0:
                self._status_text  = ''
                self._status_timer = 0.0
        self.draw(display_surf)

    def _draw_canvas(self, surf: pygame.Surface) -> None:
        # Canvas clip region
        canvas_rect = pygame.Rect(0, 0, DESIGNER_CANVAS_W, CANVAS_HEIGHT)
        pygame.draw.rect(surf, (10, 10, 10), canvas_rect)

        # Draw lines
        for l in self._lines:
            b1 = self._bus_by_label(l.from_bus)
            b2 = self._bus_by_label(l.to_bus)
            if b1 is None or b2 is None:
                continue
            selected = (l is self._selected_line)
            preview_loading = getattr(l, '_preview_loading', None)
            col = _VOLT_LINE_COLOUR.get(l.voltage_kv, COL_LINE_NORMAL)
            if selected:
                col = COL_SELECTION
            thickness = {400.0: 4, 220.0: 3, 150.0: 2, 60.0: 1}.get(l.voltage_kv, 2)
            pygame.draw.line(surf, col,
                             (b1.canvas_x, b1.canvas_y),
                             (b2.canvas_x, b2.canvas_y), thickness)
            if preview_loading is not None:
                mid_x = (b1.canvas_x + b2.canvas_x) // 2
                mid_y = (b1.canvas_y + b2.canvas_y) // 2
                pcol  = (COL_DESIGNER_SURPLUS_NEG if preview_loading > 90
                         else COL_LOAD_WARN if preview_loading > 70
                         else COL_DESIGNER_STATUS_OK)
                self._font.render_to(surf, (mid_x - 15, mid_y - 8),
                                     f'{preview_loading:.0f}%', pcol)

        # Ghost line while in LINE mode and first bus chosen
        if self._palette_mode == MODE_LINE and self._line_first_bus is not None:
            fx = self._line_first_bus.canvas_x
            fy = self._line_first_bus.canvas_y
            mx, my = self._mouse_pos
            if mx < DESIGNER_CANVAS_W:
                pygame.draw.line(surf, COL_DESIGNER_LINE_DRAW,
                                 (fx, fy), (mx, my), 1)

        # Draw buses
        for b in self._buses:
            vkv = b.voltage_kv
            col = _VOLT_COLOUR.get(vkv, COL_BUS_400KV)
            selected = (b is self._selected_bus)
            if b.bus_type == 'LOAD':
                draw_load_substation(surf, b.canvas_x, b.canvas_y,
                                     loading_pct=0.0, blacked=False,
                                     selected=selected, scale=1.0)
            else:
                draw_substation(surf, b.canvas_x, b.canvas_y,
                                loading_pct=0.0, blacked=False,
                                selected=selected, scale=1.0)
            # Voltage colour dot
            pygame.draw.circle(surf, col,
                               (b.canvas_x, b.canvas_y), BUS_SIZE // 2 + 2, 2)
            # Label
            lbl_col = COL_SELECTION if selected else COL_TEXT_PRIMARY
            lx, ly  = _label_pos(b.canvas_x, b.canvas_y, b.label_anchor)
            self._font.render_to(surf, (lx, ly), b.label, lbl_col)

            # Peak load for LOAD buses
            if b.bus_type == 'LOAD' and b.peak_load_mw > 0:
                self._font.render_to(surf, (lx, ly + 14),
                                     f'{b.peak_load_mw:.0f}MW',
                                     COL_TEXT_DIM)

        # Draw units (simple coloured squares below their bus)
        station_units: dict[str, list[DesignerUnit]] = {}
        for u in self._units:
            station_units.setdefault(u.bus_label, []).append(u)

        for bus_label, units in station_units.items():
            bus = self._bus_by_label(bus_label)
            if bus is None:
                continue
            n      = len(units)
            total  = n * UNIT_SIZE + (n - 1) * UNIT_GAP
            start_x = bus.canvas_x - total // 2
            uy      = bus.canvas_y + BUS_SIZE + 14
            for i, u in enumerate(units):
                ux = start_x + i * (UNIT_SIZE + UNIT_GAP) + UNIT_SIZE // 2
                draw_unit_square(surf, ux, uy,
                                 unit_type=u.unit_type,
                                 unit_state='OFFLINE',
                                 output_fraction=0.0,
                                 selected=False,
                                 blink_on=False,
                                 scale=1.0)

        # Delete cursor hint
        if self._palette_mode == MODE_DELETE:
            mx, my = self._mouse_pos
            if mx < DESIGNER_CANVAS_W:
                pygame.draw.circle(surf, COL_DESIGNER_DELETE_CURSOR,
                                   (mx, my), DESIGNER_HIT_RADIUS, 1)

        # Mode hint bottom-left of canvas
        hint_map = {
            MODE_SELECT: '',
            MODE_BUS:    f'PLACE BUS  {self._palette_voltage:.0f}kV  (click canvas)',
            MODE_UNIT:   f'PLACE UNIT  {self._palette_unit_type}  (click a bus)',
            MODE_LINE:   ('Click first bus' if self._line_first_bus is None
                          else f'Click second bus  (from {self._line_first_bus.label})'),
            MODE_DELETE: 'DELETE MODE  (click element)',
        }
        hint = hint_map.get(self._palette_mode, '')
        if hint:
            self._font.render_to(surf, (8, CANVAS_HEIGHT - 20), hint,
                                 COL_DESIGNER_STATUS_INFO)

    def _draw_sidebar(self, surf: pygame.Surface) -> None:
        from display.designer_panels import draw_sidebar
        sidebar_surf = surf.subsurface(
            (DESIGNER_CANVAS_W, 0, DESIGNER_SIDEBAR_W, NATIVE_HEIGHT))
        draw_sidebar(sidebar_surf, self, self._font, self._font_bold)

    def get_sidebar_mode(self) -> str:
        return self._sidebar_mode

    def _draw_dialog(self, surf: pygame.Surface) -> None:
        if not self._dialog_active:
            return
        # Modal dialog box centred on canvas
        dw, dh = 500, 90
        dx = (DESIGNER_CANVAS_W - dw) // 2
        dy = (CANVAS_HEIGHT     - dh) // 2
        pygame.draw.rect(surf, (0, 0, 0), (dx, dy, dw, dh))
        pygame.draw.rect(surf, COL_PANEL_BORDER, (dx, dy, dw, dh), 1)
        self._font.render_to(surf, (dx + 10, dy + 12), self._dialog_prompt,
                             COL_TEXT_PRIMARY)
        # Input field
        field_rect = pygame.Rect(dx + 10, dy + 40, dw - 20, 28)
        pygame.draw.rect(surf, (0, 40, 0), field_rect)
        pygame.draw.rect(surf, COL_PANEL_BORDER, field_rect, 1)
        self._font.render_to(surf, (dx + 14, dy + 46),
                             self._dialog_buffer + '_', COL_TEXT_VALUE)

    def _draw_status(self, surf: pygame.Surface) -> None:
        if not self._status_text or self._status_timer <= 0.0:
            return
        w, _ = surf.get_size()
        r, g, bb = self._status_colour
        rect_w = min(700, len(self._status_text) * 9 + 16)
        rect_x = (DESIGNER_CANVAS_W - rect_w) // 2
        rect_y = CANVAS_HEIGHT - 50
        pygame.draw.rect(surf, (0, 0, 0), (rect_x, rect_y, rect_w, 28))
        pygame.draw.rect(surf, self._status_colour, (rect_x, rect_y, rect_w, 28), 1)
        self._font.render_to(surf, (rect_x + 8, rect_y + 6),
                             self._status_text, self._status_colour)

    # ─── Save-unsaved state ──────────────────────────────────────────────────

    @property
    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def gen_capacity_mw(self) -> float:
        return sum(u.rated_mw for u in self._units)

    def peak_load_mw(self) -> float:
        return sum(b.peak_load_mw for b in self._buses if b.bus_type == 'LOAD')


# ─────────────────────────────────────────────────────────────────────────────
# AUTO-ROUTE ALGORITHM
# ─────────────────────────────────────────────────────────────────────────────

def _auto_route_lines(
    buses: list[DesignerBus],
    existing_lines: list[DesignerLine],
    used_labels: set[str],
    units: list[DesignerUnit],
) -> list[DesignerLine]:
    """Return new DesignerLine objects to add (does not modify existing_lines)."""

    if len(buses) < 2:
        return []

    new_lines: list[DesignerLine] = []
    working_used = set(used_labels)

    def make_line(b1: DesignerBus, b2: DesignerBus) -> DesignerLine:
        vkv  = min(b1.voltage_kv, b2.voltage_kv)
        dist = math.hypot(b2.canvas_x - b1.canvas_x, b2.canvas_y - b1.canvas_y)
        xpu  = max(0.010, dist / NATIVE_WIDTH * DESIGNER_X_SCALE * 10)
        lbl  = next_line_label(working_used)
        working_used.add(lbl)
        return DesignerLine(
            label=lbl,
            from_bus=b1.label,
            to_bus=b2.label,
            reactance_pu=round(xpu, 4),
            rating_mw=DESIGNER_DEFAULT_RATING.get(vkv, 300.0),
            voltage_kv=vkv,
        )

    # Step 1: Kruskal MST for connectivity
    all_buses = {b.label: b for b in buses}
    edges = []
    lbls  = [b.label for b in buses]
    for i in range(len(lbls)):
        for j in range(i + 1, len(lbls)):
            b1 = all_buses[lbls[i]]
            b2 = all_buses[lbls[j]]
            d  = math.hypot(b2.canvas_x - b1.canvas_x, b2.canvas_y - b1.canvas_y)
            # Same voltage tier preferred (lower distance bias)
            if b1.voltage_kv == b2.voltage_kv:
                d *= 0.8
            edges.append((d, b1.label, b2.label))
    edges.sort()

    # Union-Find
    parent = {b: b for b in lbls}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
            return True
        return False

    mst_edges: list[tuple[str, str]] = []
    for _d, a, b in edges:
        if union(a, b):
            mst_edges.append((a, b))
            if len(mst_edges) == len(lbls) - 1:
                break

    for a, b in mst_edges:
        new_lines.append(make_line(all_buses[a], all_buses[b]))

    # Steps 2-5: iterative load flow, parallel lines where overloaded
    all_lines_for_lf = existing_lines + new_lines
    try:
        for _iteration in range(5):
            p_inj = _build_p_injections(buses, units)
            lf_result = _run_loadflow_on(buses, all_lines_for_lf, p_inj)
            added_any = False
            for lbl, pct in lf_result.items():
                if pct > DESIGNER_TARGET_LOADING_PCT:
                    # Find the line and add a parallel
                    for l in all_lines_for_lf:
                        if l.label == lbl:
                            b1 = all_buses.get(l.from_bus)
                            b2 = all_buses.get(l.to_bus)
                            if b1 and b2:
                                para = make_line(b1, b2)
                                new_lines.append(para)
                                all_lines_for_lf.append(para)
                                added_any = True
                            break
            if not added_any:
                break
    except Exception:
        pass  # Load flow failure → return MST lines at minimum

    return new_lines


def _build_p_injections(
    buses: list[DesignerBus],
    units: list[DesignerUnit],
) -> dict[str, float]:
    p = {}
    bus_gen: dict[str, float] = {}
    for u in units:
        bus_gen[u.bus_label] = bus_gen.get(u.bus_label, 0.0) + u.rated_mw
    for b in buses:
        gen  = bus_gen.get(b.label, 0.0)
        load = b.peak_load_mw if b.bus_type == 'LOAD' else 0.0
        p[b.label] = gen - load
    return p


def _run_loadflow_on(
    buses: list[DesignerBus],
    lines: list[DesignerLine],
    p_injections: dict[str, float],
) -> dict[str, float]:
    """Return {line_label: loading_pct}. Raises on solver failure."""
    import numpy as np

    bus_labels = [b.label for b in buses]
    slack = next((b.label for b in buses if b.is_slack), bus_labels[0])
    idx   = {lbl: i for i, lbl in enumerate(bus_labels)}
    n     = len(bus_labels)

    B = np.zeros((n, n))
    for l in lines:
        if l.from_bus not in idx or l.to_bus not in idx:
            continue
        i, j = idx[l.from_bus], idx[l.to_bus]
        b_val = 1.0 / max(1e-6, l.reactance_pu)
        B[i, i] += b_val + YSHUNT_REG
        B[j, j] += b_val + YSHUNT_REG
        B[i, j] -= b_val
        B[j, i] -= b_val

    slack_idx = idx[slack]
    keep = [i for i in range(n) if i != slack_idx]
    Br   = B[np.ix_(keep, keep)]

    P_full = np.array([p_injections.get(lbl, 0.0) / S_BASE
                       for lbl in bus_labels])
    Pr = P_full[keep]

    theta_r = np.linalg.solve(Br, Pr)
    theta   = np.zeros(n)
    for k, i in enumerate(keep):
        theta[i] = theta_r[k]

    results: dict[str, float] = {}
    for l in lines:
        if l.from_bus not in idx or l.to_bus not in idx:
            continue
        i, j  = idx[l.from_bus], idx[l.to_bus]
        flow   = (theta[i] - theta[j]) / max(1e-6, l.reactance_pu) * S_BASE
        pct    = abs(flow) / max(1.0, l.rating_mw) * 100.0
        results[l.label] = pct
    return results


def _run_loadflow(
    buses: list[DesignerBus],
    lines: list[DesignerLine],
    units: list[DesignerUnit],
) -> dict[str, float]:
    """Public wrapper used by _export_preview."""
    p = _build_p_injections(buses, units)
    return _run_loadflow_on(buses, lines, p)


# ─────────────────────────────────────────────────────────────────────────────
# GEOMETRY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _point_segment_dist(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _label_pos(cx: int, cy: int, anchor: str) -> tuple[int, int]:
    off = BUS_SIZE // 2 + 4
    if anchor == 'right':
        return cx + off, cy - 6
    if anchor == 'left':
        return cx - off - 30, cy - 6
    if anchor == 'top':
        return cx - 12, cy - off - 14
    # bottom
    return cx - 12, cy + off + 2
