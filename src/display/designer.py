"""
src/display/designer.py

GridDesigner — development-only visual grid topology editor.

Entered from the main menu → GRID DESIGNER.
Allows placing buses, generation units, and transmission lines on the
1920×844 canvas, then auto-routing lines using DC load flow.
Saves to assets/designer_grids/<name>.json.

Coordinate system: all positions are in native 1920×1080 space.
The sidebar (drawn by designer_panels.py) occupies the left
DESIGNER_SIDEBAR_W (208) px; the canvas area is the remaining
DESIGNER_CANVAS_W (1712) px on the right.
"""

from __future__ import annotations

import math
import copy
from typing import Callable

import pygame
import pygame.freetype

import simulation.constants as _const
from data.designer_io import (
    DesignerBus, DesignerLine, DesignerUnit,
    save_designer_grid_named, load_designer_grid_named,
    list_designer_grids,
    next_bus_label, next_station_label, next_line_label,
    UNIT_DEFAULTS,
    designer_buses_to_topology, designer_lines_to_topology, designer_units_to_fleet,
    import_shift_as_designer_grid,
)
from display.geometry import point_segment_dist
from display.palette import (
    COL_BACKGROUND, COL_TEXT_PRIMARY,
    COL_TEXT_VALUE, COL_TEXT_WARN, COL_TEXT_CRIT,
    COL_400KV, COL_220KV, COL_150KV,
    COL_LINE_NORMAL, COL_LINE_TRIPPED,
    COL_SELECTION, COL_PANEL_BORDER,
    COL_DESIGNER_LINE_DRAW, COL_DESIGNER_STATUS_OK, COL_DESIGNER_STATUS_INFO,
    COL_DESIGNER_DELETE_CURSOR,
    COL_UNIT_COAL, COL_UNIT_CCGT, COL_UNIT_NUCLEAR,
    COL_UNIT_HYDRO, COL_UNIT_WIND, COL_UNIT_SOLAR, COL_UNIT_HYDRO_PUMP,
)
from display.symbols import _draw_dashed_line
from simulation.constants import (
    NATIVE_WIDTH, NATIVE_HEIGHT, CANVAS_HEIGHT,
    DESIGNER_SIDEBAR_W, DESIGNER_CANVAS_W,
    DESIGNER_X_SCALE, DESIGNER_TARGET_LOADING_PCT,
    DESIGNER_STATUS_DISPLAY_S, DESIGNER_HIT_RADIUS, DESIGNER_LINE_HIT_PX,
    DESIGNER_FONT_SIZE, DESIGNER_FONT_SIZE_LARGE, DESIGNER_UNDO_MAX,
    LINE_RATING_MW_BY_VOLTAGE,
    OVERLOAD_WARN_PCT, OVERLOAD_CRIT_PCT,
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

_VOLT_LINE_COLOUR: dict[float, tuple] = {
    400.0: COL_400KV,
    220.0: COL_220KV,
    150.0: COL_150KV,
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

# The 8 fixed bus attachment ports, in cycling order, for the line-rotate
# feature (R while a line endpoint is picked) — matches display.symbols.PORT_OFFSETS.
_PORT_CYCLE: list[tuple[str, int]] = [
    ('N', 0), ('N', 1), ('E', 0), ('E', 1),
    ('S', 0), ('S', 1), ('W', 0), ('W', 1),
]


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

        # Production-quality canvas (ports + obstacle-avoiding routing),
        # rebuilt from the designer state whenever topology shape changes.
        self._canvas = None            # display.canvas.GridCanvas | None
        self._canvas_dirty: bool = True

        # Selection
        self._selected_bus:  DesignerBus  | None = None
        self._selected_line: DesignerLine | None = None
        self._selected_unit: DesignerUnit | None = None

        # Palette / mode
        self._palette_mode:         str   = MODE_SELECT
        self._palette_voltage:      float = 400.0    # for MODE_BUS
        self._palette_load_toggle:  bool  = False    # for MODE_BUS — place a 150kV LOAD bus
        self._palette_unit_type:    str   = 'COAL'   # for MODE_UNIT

        # Line-draw state
        self._line_first_bus: DesignerBus | None = None

        # Line-port rotation state — 'from'/'to' once an endpoint bus has
        # been picked for the selected line, else None.
        self._rotating_line_end: str | None = None

        # Drag state (bus drag)
        self._dragging_bus:  DesignerBus | None = None
        self._drag_offset:   tuple[int, int] = (0, 0)
        # Drag state (station drag) — reuses _drag_offset, only one drag active at a time
        self._dragging_station: str | None = None   # station_label

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

        # Analysis mode — session-only what-if state, never persisted to the
        # saved grid JSON (peak_load_mw/rated_mw on the real dataclasses are
        # the source of truth; these are overrides for one analysis run).
        self._analysis_unit_mw:         dict[str, float] = {}
        self._analysis_unit_available:  dict[str, bool]  = {}
        self._analysis_bus_load_mw:     dict[str, float] = {}
        self._analysis_line_in_service: dict[str, bool]  = {}
        self._analysis_result = None   # designer_analysis.AnalysisResult | None

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
            nx = max(DESIGNER_SIDEBAR_W, min(NATIVE_WIDTH - 1, nx))
            ny = max(0, min(CANVAS_HEIGHT - 1, ny))
            self._dragging_bus.canvas_x = nx
            self._dragging_bus.canvas_y = ny
            # Full GridCanvas resync (ports/routing/dash pre-bake) is too
            # costly to run every drag frame at Shift-10 scale (measured
            # ~30-50ms at 41 buses/62 lines, well over a 16.6ms frame
            # budget). Draw a cheap straight-line ghost for the dragged
            # bus's own lines during the drag instead (see
            # _draw_canvas_overlays); the full resync runs once on release.
        elif self._dragging_station is not None:
            nx = native_pos[0] + self._drag_offset[0]
            ny = native_pos[1] + self._drag_offset[1]
            nx = max(DESIGNER_SIDEBAR_W, min(NATIVE_WIDTH - 1, nx))
            ny = max(0, min(CANVAS_HEIGHT - 1, ny))
            for u in self._units:
                if u.station_label == self._dragging_station:
                    u.station_x = nx
                    u.station_y = ny
            # Same deferred-resync rationale as bus drag — see
            # _draw_canvas_overlays for the station-drag ghost.

    def on_mouse_down(self, native_pos: tuple[int, int]) -> None:
        if self._dialog_active:
            return
        # Only drag in SELECT mode over the canvas area
        if self._palette_mode != MODE_SELECT:
            return
        if native_pos[0] < DESIGNER_SIDEBAR_W:
            return
        station_label = self._hit_station(native_pos)
        if station_label is not None:
            sx, sy = self._station_anchor(station_label)
            self._dragging_station = station_label
            self._drag_offset      = (sx - native_pos[0], sy - native_pos[1])
            return
        bus = self._hit_bus(native_pos)
        if bus is not None:
            self._dragging_bus   = bus
            self._drag_offset    = (bus.canvas_x - native_pos[0],
                                    bus.canvas_y - native_pos[1])

    def on_mouse_up(self, native_pos: tuple[int, int]) -> None:
        if self._dragging_bus is not None:
            self._dragging_bus = None
            self._mark_dirty()
        elif self._dragging_station is not None:
            self._dragging_station = None
            self._mark_dirty()

    def on_click(self, native_pos: tuple[int, int]) -> None:
        if self._dialog_active:
            return

        x, y = native_pos

        # Sidebar click → delegate to panel handler
        if x < DESIGNER_SIDEBAR_W:
            self._handle_sidebar_click(x, y)
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
        if self._sidebar_mode == 'analysis' and self._editing_field is None:
            if event.key == pygame.K_ESCAPE:
                self._close_sidebar_overlay()
                return True
            if event.key == pygame.K_RETURN:
                self._run_analysis()
                return True

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

        if ctrl and event.key == pygame.K_a:
            self._open_analysis()
            return True

        if ctrl and event.key == pygame.K_l:
            _const.VOLTAGE_COLOUR_VIEW = not _const.VOLTAGE_COLOUR_VIEW
            self._mark_dirty()
            self._set_status(
                'Line colour view: ON' if _const.VOLTAGE_COLOUR_VIEW else 'Line colour view: OFF',
                COL_DESIGNER_STATUS_INFO)
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
                self._mark_dirty()
            elif self._selected_line is not None:
                if self._rotating_line_end is None:
                    self._set_status(
                        'Click the origin or destination bus to rotate its port',
                        COL_DESIGNER_STATUS_INFO)
                else:
                    self._cycle_line_port(self._selected_line, self._rotating_line_end)
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
        self._rotating_line_end = None
        self._editing_field = None
        self._edit_buffer   = ''

    def _set_status(self, text: str, colour: tuple = None) -> None:
        self._status_text   = text
        self._status_colour = colour or COL_DESIGNER_STATUS_INFO
        self._status_timer  = DESIGNER_STATUS_DISPLAY_S

    def _mark_dirty(self) -> None:
        """
        Flag unsaved changes AND flag the production canvas as needing a
        rebuild (ports/routing/double-circuit offsets). Every topology
        mutation goes through this — simplest safe rule, resync cost is
        cheap at this project's grid scale (see Part 1 of the plan).
        """
        self._dirty = True
        self._canvas_dirty = True

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
        self._mark_dirty()
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

    def _import_campaign_shift(self, shift_number: int = 10) -> None:
        """
        Import the current campaign topology for the given shift as a named
        Designer grid ('shift{N}'), then load it into the editor. Confirms
        before overwriting an existing file under that name — the one
        genuinely destructive action in the Designer sidebar.
        """
        name = f'shift{shift_number}'
        if name in list_designer_grids():
            self._dialog_prompt   = f"'{name}' already exists — overwrite? (y/n):"
            self._dialog_buffer   = ''
            self._dialog_active   = True
            self._dialog_callback = lambda ans: self._confirm_import_campaign_shift(
                shift_number, name, ans)
        else:
            self._do_import_campaign_shift(shift_number, name)

    def _confirm_import_campaign_shift(self, shift_number: int, name: str, answer: str) -> None:
        if answer.strip().lower().startswith('y'):
            self._do_import_campaign_shift(shift_number, name)
        else:
            self._set_status('Import cancelled', COL_DESIGNER_STATUS_INFO)

    def _do_import_campaign_shift(self, shift_number: int, name: str) -> None:
        try:
            import_shift_as_designer_grid(shift_number, name)
            self._commit_load(name)
            self._set_status(f'Imported Shift {shift_number} as {name!r}',
                             COL_DESIGNER_STATUS_OK)
        except Exception as e:
            self._set_status(f'Import failed: {e}', COL_DESIGNER_STATUS_INFO)

    def _open_analysis(self) -> None:
        self._sync_analysis_state()
        self._sidebar_mode   = 'analysis'
        self._analysis_result = None   # cleared until RUN is pressed

    def _sync_analysis_state(self) -> None:
        """
        Seed the what-if dicts from current dataclass defaults for any
        element not already present (preserves user overrides across
        open/close within one session), and prune entries for elements no
        longer in the topology.
        """
        for u in self._units:
            self._analysis_unit_mw.setdefault(u.label, u.rated_mw)
            self._analysis_unit_available.setdefault(u.label, True)
        for b in self._buses:
            if b.bus_type == 'LOAD':
                self._analysis_bus_load_mw.setdefault(b.label, b.peak_load_mw)
        for l in self._lines:
            self._analysis_line_in_service.setdefault(l.label, True)

        live_units = {u.label for u in self._units}
        live_buses = {b.label for b in self._buses if b.bus_type == 'LOAD'}
        live_lines = {l.label for l in self._lines}
        self._analysis_unit_mw = {
            k: v for k, v in self._analysis_unit_mw.items() if k in live_units}
        self._analysis_unit_available = {
            k: v for k, v in self._analysis_unit_available.items() if k in live_units}
        self._analysis_bus_load_mw = {
            k: v for k, v in self._analysis_bus_load_mw.items() if k in live_buses}
        self._analysis_line_in_service = {
            k: v for k, v in self._analysis_line_in_service.items() if k in live_lines}

    def _run_analysis(self) -> None:
        if not self._buses or not self._lines:
            self._set_status('No topology to analyse', COL_DESIGNER_STATUS_INFO)
            return
        self._sync_analysis_state()
        from simulation.designer_grid import DesignerGrid
        from simulation.designer_analysis import run_full_analysis
        grid = DesignerGrid(self._buses, self._lines, self._units)
        self._analysis_result = run_full_analysis(
            grid, self._analysis_unit_mw, self._analysis_unit_available,
            self._analysis_bus_load_mw, self._analysis_line_in_service)
        if self._analysis_result.solver_error:
            self._set_status(f'Solve failed: {self._analysis_result.solver_error}',
                             COL_DESIGNER_STATUS_INFO)
        else:
            self._set_status('Analysis complete', COL_DESIGNER_STATUS_OK)

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
            self._canvas_dirty = True
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
        """
        Hit-test against the line's routed waypoints (matching what's
        actually drawn post rendering-parity), not the naive bus-centre
        segment — mirrors renderer.py's production click hit-test pattern.
        """
        px, py = pos
        best_dist = DESIGNER_LINE_HIT_PX + 1
        best = None
        waypoints_map = self._canvas._line_waypoints if self._canvas is not None else {}
        for l in self._lines:
            waypoints = waypoints_map.get(l.label)
            if waypoints is None:
                continue  # canvas not yet synced this session — no hit this frame
            d = min(point_segment_dist(px, py, sx1, sy1, sx2, sy2)
                    for (sx1, sy1), (sx2, sy2) in zip(waypoints, waypoints[1:]))
            if d < best_dist:
                best_dist = d
                best = l
        return best

    def _bus_by_label(self, label: str) -> DesignerBus | None:
        for b in self._buses:
            if b.label == label:
                return b
        return None

    def _station_anchor(self, station_label: str) -> tuple[int, int]:
        """
        Resolve a station's current canvas anchor. Falls back to 20px above
        its bus when unset (sentinel -1, e.g. a pre-feature save file).
        """
        for u in self._units:
            if u.station_label == station_label:
                if u.station_x != -1 and u.station_y != -1:
                    return u.station_x, u.station_y
                bus = self._bus_by_label(u.bus_label)
                if bus is not None:
                    return bus.canvas_x, max(0, bus.canvas_y - 20)
                return 0, 0
        return 0, 0

    def _hit_station(self, pos: tuple[int, int]) -> str | None:
        px, py = pos
        best_dist = DESIGNER_HIT_RADIUS + 1
        best = None
        seen: set[str] = set()
        for u in self._units:
            sl = u.station_label
            if sl in seen:
                continue
            seen.add(sl)
            sx, sy = self._station_anchor(sl)
            d = max(abs(sx - px), abs(sy - py))
            if d < best_dist:
                best_dist = d
                best = sl
        return best

    def _units_at_station(self, station_label: str) -> list[DesignerUnit]:
        return [u for u in self._units if u.station_label == station_label]

    # ─── Placement ───────────────────────────────────────────────────────────

    def _do_place_bus(self, x: int, y: int) -> None:
        if self._palette_load_toggle:
            # Ask for peak load
            self._dialog_prompt  = 'Peak load MW (150kV LOAD bus):'
            self._dialog_buffer  = '100'
            self._dialog_active  = True
            self._dialog_callback = lambda mw_str: self._finish_place_load_bus(x, y, mw_str)
        else:
            self._push_undo()
            self._place_bus(x, y, self._palette_voltage, peak_load_mw=0.0)

    def _finish_place_load_bus(self, x: int, y: int, mw_str: str) -> None:
        try:
            mw = max(0.0, float(mw_str))
        except ValueError:
            mw = 100.0
        self._push_undo()
        self._place_bus(x, y, 150.0, bus_type='LOAD', peak_load_mw=mw)

    def _place_bus(self, x: int, y: int, voltage_kv: float,
                   bus_type: str = 'TRANSMISSION',
                   peak_load_mw: float = 0.0) -> None:
        label = next_bus_label(self._used_bus_labels)
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
        self._mark_dirty()

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
        sx, sy = bus.canvas_x, max(0, bus.canvas_y - 20)
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
                station_x=sx,
                station_y=sy,
            )
            self._units.append(unit)
        self._palette_mode = MODE_SELECT
        self._mark_dirty()
        self._set_status(f'Placed {count}× {unit_type} at {bus.label}',
                         COL_DESIGNER_STATUS_OK)

    def _place_line(self, b1: DesignerBus, b2: DesignerBus) -> None:
        # Infer voltage: lower of the two endpoints
        vkv  = min(b1.voltage_kv, b2.voltage_kv)
        dist = math.hypot(b2.canvas_x - b1.canvas_x, b2.canvas_y - b1.canvas_y)
        x_pu = max(0.010, dist / NATIVE_WIDTH * DESIGNER_X_SCALE * 10)
        # Rating always matches the standard rating for this line's voltage tier
        rating = LINE_RATING_MW_BY_VOLTAGE.get(vkv, LINE_RATING_MW_BY_VOLTAGE[150.0])
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
        self._mark_dirty()
        self._set_status(f'Line {label}: {b1.label}↔{b2.label}  {vkv:.0f}kV  {rating:.0f}MW',
                         COL_DESIGNER_STATUS_OK)

    # ─── Selection ───────────────────────────────────────────────────────────

    def _do_select(self, pos: tuple[int, int]) -> None:
        self._editing_field = None
        self._edit_buffer   = ''
        bus = self._hit_bus(pos)
        if bus is not None:
            if (self._selected_line is not None and
                    bus.label in (self._selected_line.from_bus, self._selected_line.to_bus)):
                self._rotating_line_end = (
                    'from' if bus.label == self._selected_line.from_bus else 'to')
                return
            if self._selected_bus is bus:
                self._clear_selection()
            else:
                self._selected_bus  = bus
                self._selected_line = None
                self._selected_unit = None
            return
        station = self._hit_station(pos)
        if station is not None:
            units = self._units_at_station(station)
            if units:
                unit = units[0]
                if self._selected_unit is unit:
                    self._clear_selection()
                else:
                    self._selected_unit = unit
                    self._selected_bus  = None
                    self._selected_line = None
                return
        line = self._hit_line(pos)
        if line is not None:
            self._selected_line = line
            self._selected_bus  = None
            self._selected_unit = None
            self._rotating_line_end = None
            return
        self._clear_selection()

    # ─── Delete ──────────────────────────────────────────────────────────────

    def _do_delete_at(self, pos: tuple[int, int]) -> None:
        bus = self._hit_bus(pos)
        if bus is not None:
            self._push_undo()
            self._remove_bus(bus)
            return
        station_label = self._hit_station(pos)
        if station_label is not None:
            self._push_undo()
            self._remove_station(station_label)
            return
        line = self._hit_line(pos)
        if line is not None:
            self._push_undo()
            self._lines.remove(line)
            self._used_line_labels.discard(line.label)
            self._mark_dirty()
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
            self._mark_dirty()
        elif self._selected_unit is not None:
            self._push_undo()
            self._remove_station(self._selected_unit.station_label)

    def _remove_bus(self, bus: DesignerBus) -> None:
        lbl = bus.label
        self._buses  = [b for b in self._buses  if b.label != lbl]
        self._lines  = [l for l in self._lines
                        if l.from_bus != lbl and l.to_bus != lbl]
        self._units  = [u for u in self._units  if u.bus_label != lbl]
        self._used_bus_labels.discard(lbl)
        self._used_line_labels = {l.label for l in self._lines}
        self._clear_selection()
        self._mark_dirty()

    def _remove_station(self, station_label: str) -> None:
        self._units = [u for u in self._units if u.station_label != station_label]
        self._clear_selection()
        self._mark_dirty()

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

        if action == 'bus_load_toggle':
            self._palette_mode        = MODE_BUS
            self._palette_load_toggle = not self._palette_load_toggle
            self._line_first_bus      = None

        elif action.startswith('bus_'):
            self._palette_mode        = MODE_BUS
            self._palette_voltage     = float(action.split('_')[1])
            self._palette_load_toggle = False
            self._line_first_bus      = None

        elif action.startswith('unit_'):
            self._palette_mode      = MODE_UNIT
            self._palette_unit_type = action[5:]
            self._line_first_bus    = None

        elif action == 'delete':
            self._palette_mode = MODE_DELETE

        elif action == 'line_mode':
            self._palette_mode   = MODE_LINE
            self._line_first_bus = None

        elif action == 'auto_route':
            self._auto_route()

        elif action == 'clear_lines':
            self._push_undo()
            self._lines.clear()
            self._used_line_labels.clear()
            self._mark_dirty()
            self._set_status('All lines cleared', COL_DESIGNER_STATUS_INFO)

        elif action == 'save':
            self._open_save_dialog()

        elif action == 'load':
            self._open_load_browser()

        elif action == 'test_grid':
            self._open_test_browser()

        elif action == 'import_shift10':
            self._import_campaign_shift(10)

        elif action == 'analysis':
            self._open_analysis()

        elif action == 'analysis_run':
            self._run_analysis()

        elif action == 'analysis_close':
            self._close_sidebar_overlay()

        elif action == 'prop_shift_plus':
            self._change_active_shift(+1)

        elif action == 'prop_shift_minus':
            self._change_active_shift(-1)

        elif action == 'prop_slack_toggle':
            if self._selected_bus is not None:
                for b in self._buses:
                    b.is_slack = False
                self._selected_bus.is_slack = True
                self._mark_dirty()

        elif action == 'edit_reactance_pu':
            if self._selected_line is not None:
                self._start_edit('reactance_pu', f'{self._selected_line.reactance_pu:.4f}')

        elif action == 'edit_peak_load_mw':
            if self._selected_bus is not None:
                self._start_edit('peak_load_mw', f'{self._selected_bus.peak_load_mw:.0f}')

        elif action == 'prop_unit_cycle_next':
            if self._selected_unit is not None:
                sibs = self._units_at_station(self._selected_unit.station_label)
                if len(sibs) > 1:
                    idx = sibs.index(self._selected_unit)
                    self._selected_unit = sibs[(idx + 1) % len(sibs)]

        elif action == 'prop_unit_cycle_prev':
            if self._selected_unit is not None:
                sibs = self._units_at_station(self._selected_unit.station_label)
                if len(sibs) > 1:
                    idx = sibs.index(self._selected_unit)
                    self._selected_unit = sibs[(idx - 1) % len(sibs)]

        elif action == 'edit_start_mw':
            if self._selected_unit is not None:
                u = self._selected_unit
                start_val = u.start_mw if u.start_mw >= 0 else u.rated_mw * 0.5
                self._start_edit('start_mw', f'{start_val:.0f}')

        elif action == 'prop_unit_in_service_toggle':
            if self._selected_unit is not None:
                self._selected_unit.in_service = not self._selected_unit.in_service
                self._mark_dirty()

        elif action == 'edit_analysis_unit_mw':
            if self._selected_unit is not None:
                mw = self._analysis_unit_mw.get(self._selected_unit.label,
                                                self._selected_unit.rated_mw)
                self._start_edit('analysis_unit_mw', f'{mw:.0f}')

        elif action == 'edit_analysis_bus_load_mw':
            if self._selected_bus is not None:
                mw = self._analysis_bus_load_mw.get(self._selected_bus.label,
                                                    self._selected_bus.peak_load_mw)
                self._start_edit('analysis_bus_load_mw', f'{mw:.0f}')

        elif action == 'analysis_unit_toggle_avail':
            if self._selected_unit is not None:
                lbl = self._selected_unit.label
                self._analysis_unit_available[lbl] = not self._analysis_unit_available.get(lbl, True)
                self._analysis_result = None

        elif action == 'analysis_line_toggle_service':
            if self._selected_line is not None:
                lbl = self._selected_line.label
                self._analysis_line_in_service[lbl] = not self._analysis_line_in_service.get(lbl, True)
                self._analysis_result = None

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
                self._mark_dirty()
        elif self._selected_line is not None and field == 'reactance_pu':
            try:
                self._selected_line.reactance_pu = max(0.001, float(val))
                self._mark_dirty()
            except ValueError:
                pass
        elif self._selected_bus is not None and field == 'peak_load_mw':
            try:
                self._selected_bus.peak_load_mw = max(0.0, float(val))
                self._mark_dirty()
            except ValueError:
                pass
        elif self._selected_unit is not None and field == 'analysis_unit_mw':
            try:
                u  = self._selected_unit
                mw = max(u.min_mw, min(u.rated_mw, float(val)))
                self._analysis_unit_mw[u.label] = mw
                self._analysis_result = None
            except ValueError:
                pass
        elif self._selected_bus is not None and field == 'analysis_bus_load_mw':
            try:
                mw = max(0.0, float(val))
                self._analysis_bus_load_mw[self._selected_bus.label] = mw
                self._analysis_result = None
            except ValueError:
                pass
        elif self._selected_unit is not None and field == 'start_mw':
            try:
                u = self._selected_unit
                u.start_mw = max(0.0, min(u.rated_mw, float(val)))
                self._mark_dirty()
            except ValueError:
                pass
        self._editing_field = None
        self._edit_buffer   = ''

    def _change_active_shift(self, delta: int) -> None:
        if self._selected_bus is not None:
            self._selected_bus.active_from_shift = max(1, min(10,
                self._selected_bus.active_from_shift + delta))
            self._mark_dirty()
        elif self._selected_line is not None:
            self._selected_line.active_from_shift = max(1, min(10,
                self._selected_line.active_from_shift + delta))
            self._mark_dirty()
        elif self._selected_unit is not None:
            self._selected_unit.active_from_shift = max(1, min(10,
                self._selected_unit.active_from_shift + delta))
            self._mark_dirty()

    def _cycle_line_port(self, line: DesignerLine, end: str) -> None:
        """Advance one endpoint of a line to the next of its bus's 8 fixed
        attachment ports (cosmetic — does not change from_bus/to_bus)."""
        override = line.from_port_override if end == 'from' else line.to_port_override
        idx = (_PORT_CYCLE.index(override) + 1) % len(_PORT_CYCLE) if override else 0
        new_port = _PORT_CYCLE[idx]
        if end == 'from':
            line.from_port_override = new_port
        else:
            line.to_port_override = new_port
        self._mark_dirty()

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
        self._mark_dirty()
        self._set_status(f'AUTO-ROUTE COMPLETE — {n} line{"s" if n != 1 else ""} added',
                         COL_DESIGNER_STATUS_OK)

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

    def _selected_label_for_canvas(self) -> str | None:
        """Bus/unit label to highlight via GridCanvas's own selection ring."""
        if self._selected_bus is not None:
            return self._selected_bus.label
        if self._selected_unit is not None:
            return self._selected_unit.label
        return None

    def _sync_canvas(self) -> None:
        """
        Rebuild the production-quality GridCanvas from current designer
        state (ports, obstacle-avoiding routing, double-circuit offsets).

        Converts Designer* dataclasses to the real frozen topology/fleet
        dataclasses GridCanvas expects, via the previously-unused
        designer_io.py conversion helpers.
        """
        from display.canvas import GridCanvas

        real_buses = designer_buses_to_topology(self._buses)
        real_lines = designer_lines_to_topology(self._lines)
        real_units = designer_units_to_fleet(self._units)

        station_positions: dict[str, tuple[int, int]] = {}
        for u in self._units:
            if u.station_label in station_positions:
                continue
            if u.station_x != -1 and u.station_y != -1:
                station_positions[u.station_label] = (u.station_x, u.station_y)

        if self._canvas is None:
            # shift=0 sentinel — never actually used; load_designer_topology()
            # immediately replaces everything __init__ would have populated
            # from get_buses_by_shift(0).
            self._canvas = GridCanvas(shift=0, font=self._font, scale=1.0)
        self._canvas.load_designer_topology(real_buses, real_lines, real_units,
                                            station_positions)
        self._canvas_dirty = False

    def _draw_canvas(self, surf: pygame.Surface) -> None:
        # Canvas clip region — occupies the right side, sidebar is on the left
        canvas_rect = pygame.Rect(DESIGNER_SIDEBAR_W, 0, DESIGNER_CANVAS_W, CANVAS_HEIGHT)
        pygame.draw.rect(surf, (10, 10, 10), canvas_rect)

        if self._canvas_dirty:
            self._sync_canvas()

        if self._buses:
            # GridCanvas.draw() always blits at (0,0) of the surface it's
            # given, and bus/line positions are native-space (not offset by
            # the sidebar) — so it must draw directly onto the full native
            # surf, never a subsurface (a subsurface would double-offset
            # every position by the sidebar width).
            self._canvas.draw(surf, state=None, blink_on=True,
                              selected_label=self._selected_label_for_canvas())

        self._draw_canvas_overlays(surf)

    def _draw_canvas_overlays(self, surf: pygame.Surface) -> None:
        """
        Designer-only chrome drawn on top of GridCanvas's blit: selected-line
        highlight, ghost line while drawing, delete-mode cursor, mode hint,
        and (when in analysis mode) loading-% labels / out-of-service marks.
        """
        # While actively dragging a bus, GridCanvas's last-synced routing is
        # stale (a full resync is deferred to drag-end for performance — see
        # on_mouse_move). Cover the dragged bus's own lines with a cheap
        # straight-line ghost that tracks the live position, so the display
        # doesn't visibly lag behind the mouse.
        if self._dragging_bus is not None:
            dx, dy = self._dragging_bus.canvas_x, self._dragging_bus.canvas_y
            for l in self._lines:
                other_lbl = None
                if l.from_bus == self._dragging_bus.label:
                    other_lbl = l.to_bus
                elif l.to_bus == self._dragging_bus.label:
                    other_lbl = l.from_bus
                if other_lbl is None:
                    continue
                other = self._bus_by_label(other_lbl)
                if other is None:
                    continue
                col = _VOLT_LINE_COLOUR.get(l.voltage_kv, COL_LINE_NORMAL)
                pygame.draw.line(surf, col, (dx, dy),
                                 (other.canvas_x, other.canvas_y), 1)

        # Same deferred-resync trick for a dragged station: draw a cheap
        # collector-line ghost to its bus plus an outline marker at the
        # live anchor, instead of reproducing the exact unit-square layout.
        if self._dragging_station is not None:
            sx, sy = self._station_anchor(self._dragging_station)
            station_units = [u for u in self._units
                             if u.station_label == self._dragging_station]
            if station_units:
                bus = self._bus_by_label(station_units[0].bus_label)
                if bus is not None:
                    pygame.draw.line(surf, COL_LINE_NORMAL, (sx, sy),
                                     (bus.canvas_x, bus.canvas_y), 1)
                pygame.draw.rect(surf, COL_SELECTION,
                                 pygame.Rect(sx - 8, sy - 8, 16, 16), 1)

        # Selected-line highlight — GridCanvas has no line-selection concept
        # of its own (production gameplay only has click-to-trip), so redraw
        # a highlight stroke along the line's already-computed waypoints.
        if self._selected_line is not None and self._canvas is not None:
            waypoints = self._canvas._line_waypoints.get(self._selected_line.label)
            if waypoints:
                for (x1, y1), (x2, y2) in zip(waypoints, waypoints[1:]):
                    pygame.draw.line(surf, COL_SELECTION, (x1, y1), (x2, y2), 3)

        # Analysis mode: loading-% labels + out-of-service dashed overstroke.
        # Lines toggled out of service render no differently in GridCanvas's
        # own topology-only (state=None) draw path, so overstroke them here
        # rather than adding a designer-only concept to production rendering.
        if (self._sidebar_mode == 'analysis' and self._canvas is not None
                and self._analysis_result is not None):
            for l in self._lines:
                waypoints = self._canvas._line_waypoints.get(l.label)
                if not waypoints:
                    continue
                in_service = self._analysis_line_in_service.get(l.label, True)
                if not in_service:
                    for (x1, y1), (x2, y2) in zip(waypoints, waypoints[1:]):
                        _draw_dashed_line(surf, COL_LINE_TRIPPED,
                                          (x1, y1), (x2, y2), dash=4, gap=3, width=2)
                    continue
                flow = self._analysis_result.line_flows.get(l.label)
                if flow is None:
                    continue
                pct = flow.loading_pct
                pcol = (COL_TEXT_CRIT if pct >= OVERLOAD_CRIT_PCT
                        else COL_TEXT_WARN if pct >= OVERLOAD_WARN_PCT
                        else COL_DESIGNER_STATUS_OK)
                mid_idx = len(waypoints) // 2
                mx, my = waypoints[max(0, mid_idx - 1)]
                mx2, my2 = waypoints[min(len(waypoints) - 1, mid_idx)]
                lx, ly = (mx + mx2) // 2, (my + my2) // 2
                self._font.render_to(surf, (lx - 8, ly - 4), f'{pct:.0f}%', pcol)

        # Ghost line while in LINE mode and first bus chosen — not yet a
        # real line with ports/routing (no second endpoint exists yet), so a
        # straight-line ghost is the correct preview.
        if self._palette_mode == MODE_LINE and self._line_first_bus is not None:
            fx = self._line_first_bus.canvas_x
            fy = self._line_first_bus.canvas_y
            mx, my = self._mouse_pos
            if mx >= DESIGNER_SIDEBAR_W:
                pygame.draw.line(surf, COL_DESIGNER_LINE_DRAW,
                                 (fx, fy), (mx, my), 1)

        # Delete cursor hint
        if self._palette_mode == MODE_DELETE:
            mx, my = self._mouse_pos
            if mx >= DESIGNER_SIDEBAR_W:
                pygame.draw.circle(surf, COL_DESIGNER_DELETE_CURSOR,
                                   (mx, my), DESIGNER_HIT_RADIUS, 1)

        # Mode hint bottom-left of canvas
        bus_hint = (f'PLACE BUS  150kV LOAD  (click canvas)' if self._palette_load_toggle
                    else f'PLACE BUS  {self._palette_voltage:.0f}kV  (click canvas)')
        hint_map = {
            MODE_SELECT: '',
            MODE_BUS:    bus_hint,
            MODE_UNIT:   f'PLACE UNIT  {self._palette_unit_type}  (click a bus)',
            MODE_LINE:   ('Click first bus' if self._line_first_bus is None
                          else f'Click second bus  (from {self._line_first_bus.label})'),
            MODE_DELETE: 'DELETE MODE  (click element)',
        }
        hint = hint_map.get(self._palette_mode, '')
        if hint:
            self._font.render_to(surf, (DESIGNER_SIDEBAR_W + 8, CANVAS_HEIGHT - 20), hint,
                                 COL_DESIGNER_STATUS_INFO)

    def _draw_sidebar(self, surf: pygame.Surface) -> None:
        from display.designer_panels import draw_sidebar
        sidebar_surf = surf.subsurface(
            (0, 0, DESIGNER_SIDEBAR_W, NATIVE_HEIGHT))
        draw_sidebar(sidebar_surf, self, self._font, self._font_bold)

    def get_sidebar_mode(self) -> str:
        return self._sidebar_mode

    def _draw_dialog(self, surf: pygame.Surface) -> None:
        if not self._dialog_active:
            return
        # Modal dialog box centred on the canvas region (right of the sidebar)
        dw, dh = 500, 90
        dx = DESIGNER_SIDEBAR_W + (DESIGNER_CANVAS_W - dw) // 2
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
        rect_x = DESIGNER_SIDEBAR_W + (DESIGNER_CANVAS_W - rect_w) // 2
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
            rating_mw=LINE_RATING_MW_BY_VOLTAGE.get(vkv, LINE_RATING_MW_BY_VOLTAGE[150.0]),
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

    # Steps 2-5: iterative load flow, parallel lines where overloaded.
    # Uses the real DCLoadFlow (via a throwaway DesignerGrid) instead of a
    # bespoke duplicate solver — same numerics the analysis panel uses.
    all_lines_for_lf = existing_lines + new_lines
    try:
        from simulation.designer_grid import DesignerGrid
        from simulation.designer_analysis import run_static_solve

        unit_mw        = {u.label: u.rated_mw for u in units}
        unit_available = {u.label: True for u in units}
        bus_load_mw    = {b.label: b.peak_load_mw for b in buses if b.bus_type == 'LOAD'}

        for _iteration in range(5):
            line_in_service = {l.label: True for l in all_lines_for_lf}
            grid = DesignerGrid(buses, all_lines_for_lf, units)
            line_flows, error = run_static_solve(
                grid, unit_mw, unit_available, bus_load_mw, line_in_service)
            if error:
                break
            added_any = False
            for lbl, flow in line_flows.items():
                if flow.loading_pct > DESIGNER_TARGET_LOADING_PCT:
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


