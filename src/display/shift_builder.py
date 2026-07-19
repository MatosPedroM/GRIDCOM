"""
src/display/shift_builder.py

ShiftBuilder — authors a Shift Builder JSON file (src/assets/shifts/<name>.json)
on top of a saved Grid Designer grid.

Entered from the main menu → SHIFT BUILDER.
Picks a saved designer grid (read-only reference — topology is edited in
the Grid Designer, not here), then edits shift metadata: starting
conditions, per-bus hourly demand, and a scripted event timeline. Saves/
loads via src/data/shift_io.py. Ctrl+T runs the authored shift live,
reusing the same GridSimulation + Renderer plumbing as DESIGNER_TEST.

Coordinate system: native 1920×1080 space, single-panel form layout (no
canvas — the grid is referenced by name only, not edited spatially here).
"""

from __future__ import annotations

from typing import Callable

import pygame
import pygame.freetype

from data.shift_io import (
    ShiftDefinition, ShiftEvent,
    save_shift_named, load_shift_named, list_shift_names,
    load_campaign_shift_for_editing, save_campaign_shift_fields,
    list_campaign_shift_numbers, CAMPAIGN_EDITABLE_FIELDS,
)
from data.designer_io import list_designer_grids, load_designer_grid_named
from display.palette import (
    COL_BACKGROUND, COL_TEXT_PRIMARY, COL_TEXT_SECONDARY, COL_TEXT_DIM,
    COL_TEXT_VALUE, COL_TEXT_HEADING, COL_TEXT_WARN, COL_TEXT_CRIT, COL_TEXT_GOOD,
    COL_PANEL_BORDER, COL_SELECTION,
    COL_DESIGNER_STATUS_OK, COL_DESIGNER_STATUS_INFO, COL_DESIGNER_FIELD_ACTIVE,
)
from simulation.constants import (
    NATIVE_WIDTH, NATIVE_HEIGHT,
    FONT_PATH_MONO_REGULAR,
    SHIFT_BUILDER_FONT_SIZE, SHIFT_BUILDER_FONT_SIZE_LARGE,
    SHIFT_BUILDER_ROW_H, SHIFT_BUILDER_LEFT_MARGIN, SHIFT_BUILDER_TOP_MARGIN,
    SHIFT_BUILDER_STATUS_DISPLAY_S, SHIFT_BUILDER_DEFAULT_DURATION_H,
)
from utils.helpers import resource_path


TABS = ('META', 'GRID', 'SCHEDULE', 'DEMAND', 'EVENTS')

_PRIORITY_CYCLE = ('INFO', 'WARNING', 'ALARM', 'CRITICAL', 'MAINTENANCE')
_METRIC_CYCLE = (
    'LINE_LOADING', 'UNIT_OUTPUT_MW', 'UNIT_OUTPUT_MW_SUM',
    'UNIT_ONLINE', 'SPINNING_RESERVE_MW', 'FREQUENCY_HZ', 'TIME_MIN',
)
_OP_CYCLE = ('<', '<=', '>', '>=', '==', '!=')
_ACTION_TYPE_CYCLE = ('NONE', 'LINE_OPEN', 'LINE_CLOSE', 'UNIT_TRIP')


class ShiftBuilder:
    """
    Form-driven shift-scenario editor. Owns its own rendering and event
    handling — call tick(dt, display_surf) each frame, route pygame events
    to on_key / on_click / on_mouse_move.
    """

    def __init__(self, display_surf: pygame.Surface) -> None:
        self._display_surf = display_surf
        dw, dh = display_surf.get_size()
        self._scale = min(dw / NATIVE_WIDTH, dh / NATIVE_HEIGHT)
        ox = (dw - int(NATIVE_WIDTH * self._scale)) // 2
        oy = (dh - int(NATIVE_HEIGHT * self._scale)) // 2
        self._letterbox = pygame.Rect(ox, oy,
                                      int(NATIVE_WIDTH * self._scale),
                                      int(NATIVE_HEIGHT * self._scale))
        # Native surface, sized to the real (scaled) display resolution so
        # text is rasterized directly at final pixel size instead of being
        # bitmap-stretched afterward (matches Renderer's approach).
        self._native = pygame.Surface((self._letterbox.width, self._letterbox.height)).convert()

        _font_path = resource_path(FONT_PATH_MONO_REGULAR)
        try:
            self._font       = pygame.freetype.Font(_font_path, SHIFT_BUILDER_FONT_SIZE)
            self._font_large = pygame.freetype.Font(_font_path, SHIFT_BUILDER_FONT_SIZE_LARGE)
        except Exception:
            self._font       = pygame.freetype.SysFont('monospace', SHIFT_BUILDER_FONT_SIZE)
            self._font_large = pygame.freetype.SysFont('monospace', SHIFT_BUILDER_FONT_SIZE_LARGE)
        self._font.antialiased       = False
        self._font_large.antialiased = False

        # Shift state being edited
        self._shift = ShiftDefinition(
            name='untitled', grid='',
            duration_hours=SHIFT_BUILDER_DEFAULT_DURATION_H,
        )
        self._shift_file_name: str = ''   # saved-as name, '' = unsaved
        self._dirty: bool = False

        # Set to a shift number (1-10) when editing an existing campaign
        # shift (shift_NN.py) instead of an authored JSON shift; controls
        # save-target routing (Ctrl+S) and which fields render read-only.
        self._campaign_shift_number: int | None = None
        # Fields touched this editing session, restricted to
        # CAMPAIGN_EDITABLE_FIELDS — only these get spliced back into
        # shift_NN.py on save, so an untouched tab's formatting survives.
        self._edited_fields: set[str] = set()

        # Tabs
        self._tab_idx: int = 0

        # List cursors per tab (which row is selected)
        self._schedule_cursor: int = 0
        self._demand_bus_cursor: int = 0
        self._demand_hour_cursor: int = 0
        self._events_cursor: int = 0
        self._maint_unit_cursor: int = 0
        self._maint_line_cursor: int = 0

        # Field-edit state (text-buffer editing of one value)
        self._editing_field: str | None = None
        self._edit_buffer: str = ''

        # Sidebar/overlay mode: 'normal', 'save_dialog', 'load_browser', 'grid_browser'
        self._mode: str = 'normal'
        self._dialog_buf: str = ''
        self._browser_list: list[str] = []
        self._browser_idx: int = 0

        # Status message
        self._status_text: str = ''
        self._status_colour: tuple = COL_DESIGNER_STATUS_INFO
        self._status_timer: float = 0.0

        # Cached grid contents (read-only reference), keyed by grid name
        self._grid_buses = []
        self._grid_units = []

        # Callback invoked when the user requests a live test session for
        # an authored JSON shift. Signature: (shift_name: str) -> None
        self.on_test_request: Callable[[str], None] | None = None
        # Callback invoked when the user requests a live test session for
        # a campaign shift currently open for editing. Signature:
        # (shift_number: int) -> None
        self.on_campaign_test_request: Callable[[int], None] | None = None

    # ─── Public event interface ────────────────────────────────────────────

    def to_native(self, pos: tuple[int, int]) -> tuple[int, int]:
        nx = int((pos[0] - self._letterbox.left) / self._scale)
        ny = int((pos[1] - self._letterbox.top) / self._scale)
        return (
            max(0, min(NATIVE_WIDTH - 1, nx)),
            max(0, min(NATIVE_HEIGHT - 1, ny)),
        )

    def on_mouse_move(self, native_pos: tuple[int, int]) -> None:
        pass

    def on_mouse_down(self, native_pos: tuple[int, int]) -> None:
        pass

    def on_mouse_up(self, native_pos: tuple[int, int]) -> None:
        pass

    def on_click(self, native_pos: tuple[int, int]) -> None:
        if self._mode != 'normal' or self._editing_field is not None:
            return
        x, y = native_pos
        # Tab bar click
        tab_y = SHIFT_BUILDER_TOP_MARGIN
        if tab_y <= y <= tab_y + SHIFT_BUILDER_ROW_H:
            tab_w = 160
            idx = (x - SHIFT_BUILDER_LEFT_MARGIN) // tab_w
            if 0 <= idx < len(TABS):
                self._tab_idx = int(idx)

    def on_key(self, event: pygame.event.Event) -> bool:
        """Handle a KEYDOWN event. Returns True if consumed."""
        if self._mode == 'save_dialog':
            return self._handle_save_dialog_key(event)
        if self._mode in ('load_browser', 'grid_browser', 'campaign_browser'):
            return self._handle_browser_key(event)
        if self._editing_field is not None:
            return self._handle_edit_key(event)

        mods = pygame.key.get_mods()
        ctrl = bool(mods & pygame.KMOD_CTRL)
        shift = bool(mods & pygame.KMOD_SHIFT)

        if event.key == pygame.K_ESCAPE:
            return False   # nothing to dismiss — let main.py exit the builder

        if ctrl and shift and event.key == pygame.K_o:
            self._open_campaign_browser()
            return True
        if ctrl and event.key == pygame.K_s:
            self._save_current()
            return True
        if ctrl and event.key == pygame.K_o:
            self._open_load_browser()
            return True
        if ctrl and event.key == pygame.K_g:
            if self._campaign_shift_number is not None:
                self._set_status('Campaign topology is not editable here — use the Grid Designer', COL_TEXT_WARN)
                return True
            self._open_grid_browser()
            return True
        if ctrl and event.key == pygame.K_t:
            self._request_test()
            return True

        if event.key in (pygame.K_TAB, pygame.K_RIGHT) and not ctrl:
            self._tab_idx = (self._tab_idx + 1) % len(TABS)
            return True
        if event.key == pygame.K_LEFT and not ctrl:
            self._tab_idx = (self._tab_idx - 1) % len(TABS)
            return True

        tab = TABS[self._tab_idx]
        if tab == 'META':
            return self._on_key_meta(event)
        elif tab == 'GRID':
            return self._on_key_grid(event)
        elif tab == 'SCHEDULE':
            return self._on_key_schedule(event)
        elif tab == 'DEMAND':
            return self._on_key_demand(event)
        elif tab == 'EVENTS':
            return self._on_key_events(event)
        return False

    def tick(self, dt: float, display_surf: pygame.Surface) -> None:
        if self._status_timer > 0.0:
            self._status_timer -= dt
        self._draw()
        # self._native is already sized at display resolution — blit 1:1, no resize.
        display_surf.fill(COL_BACKGROUND)
        display_surf.blit(self._native, self._letterbox.topleft)

    # ─── Status / dirty helpers ────────────────────────────────────────────

    def _set_status(self, text: str, colour: tuple = None) -> None:
        self._status_text = text
        self._status_colour = colour or COL_DESIGNER_STATUS_INFO
        self._status_timer = SHIFT_BUILDER_STATUS_DISPLAY_S

    def _mark_dirty(self, field: str | None = None) -> None:
        self._dirty = True
        if field is not None:
            self._edited_fields.add(field)

    # ─── Save / load / grid browser ────────────────────────────────────────

    def _open_save_dialog(self) -> None:
        self._mode = 'save_dialog'
        self._dialog_buf = self._shift_file_name or self._shift.name

    def _handle_save_dialog_key(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_RETURN:
            name = self._dialog_buf.strip()
            if name:
                self._commit_save(name)
            self._mode = 'normal'
            return True
        if event.key == pygame.K_ESCAPE:
            self._mode = 'normal'
            return True
        if event.key == pygame.K_BACKSPACE:
            self._dialog_buf = self._dialog_buf[:-1]
            return True
        if event.unicode and (event.unicode.isalnum() or event.unicode == '_'):
            self._dialog_buf += event.unicode
        return True

    def _commit_save(self, name: str) -> None:
        if not self._shift.grid:
            self._set_status('Cannot save — no grid selected (Ctrl+G)', COL_TEXT_WARN)
            return
        try:
            self._shift.name = name
            save_shift_named(self._shift, name)
            self._shift_file_name = name
            self._dirty = False
            self._set_status(f'Saved: {name}', COL_DESIGNER_STATUS_OK)
        except Exception as e:
            self._set_status(f'Save failed: {e}', COL_TEXT_CRIT)

    def _save_current(self) -> None:
        """Ctrl+S — routes to the campaign splice-writer or the JSON saver
        depending on what's currently loaded."""
        if self._campaign_shift_number is not None:
            if not self._edited_fields:
                self._set_status('Nothing to save — no fields edited', COL_DESIGNER_STATUS_INFO)
                return
            try:
                save_campaign_shift_fields(self._campaign_shift_number, self._shift, self._edited_fields)
                self._dirty = False
                self._edited_fields = set()
                self._set_status(
                    f'Saved to shift_{self._campaign_shift_number:02d}.py', COL_DESIGNER_STATUS_OK)
            except Exception as e:
                self._set_status(f'Save failed: {e}', COL_TEXT_CRIT)
            return
        self._open_save_dialog()

    def _open_load_browser(self) -> None:
        self._mode = 'load_browser'
        self._browser_list = list_shift_names()
        self._browser_idx = 0

    def _open_grid_browser(self) -> None:
        self._mode = 'grid_browser'
        self._browser_list = list_designer_grids()
        self._browser_idx = 0

    def _open_campaign_browser(self) -> None:
        self._mode = 'campaign_browser'
        self._browser_list = [f'SHIFT {n}' for n in list_campaign_shift_numbers()]
        self._browser_idx = 0

    def _handle_browser_key(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_ESCAPE:
            self._mode = 'normal'
            return True
        if event.key in (pygame.K_UP, pygame.K_w):
            self._browser_idx = max(0, self._browser_idx - 1)
            return True
        if event.key in (pygame.K_DOWN, pygame.K_s):
            self._browser_idx = min(max(0, len(self._browser_list) - 1), self._browser_idx + 1)
            return True
        if event.key == pygame.K_RETURN:
            if self._browser_list:
                name = self._browser_list[self._browser_idx]
                if self._mode == 'load_browser':
                    self._commit_load(name)
                elif self._mode == 'campaign_browser':
                    shift_number = int(name.split()[1])
                    self._commit_campaign_load(shift_number)
                else:
                    self._commit_grid_select(name)
            self._mode = 'normal'
            return True
        return True

    def _commit_load(self, name: str) -> None:
        try:
            self._shift = load_shift_named(name)
            self._shift_file_name = name
            self._campaign_shift_number = None
            self._edited_fields = set()
            self._dirty = False
            self._sync_grid_cache()
            self._set_status(f'Loaded: {name}', COL_DESIGNER_STATUS_OK)
        except Exception as e:
            self._set_status(f'Load failed: {e}', COL_TEXT_CRIT)

    def _commit_campaign_load(self, shift_number: int) -> None:
        try:
            self._shift = load_campaign_shift_for_editing(shift_number)
            self._shift_file_name = ''
            self._campaign_shift_number = shift_number
            self._edited_fields = set()
            self._dirty = False
            self._sync_grid_cache()
            self._set_status(f'Editing campaign SHIFT {shift_number} (shift_{shift_number:02d}.py)',
                             COL_DESIGNER_STATUS_OK)
        except Exception as e:
            self._set_status(f'Load failed: {e}', COL_TEXT_CRIT)

    def _commit_grid_select(self, name: str) -> None:
        self._shift.grid = name
        self._mark_dirty()
        self._sync_grid_cache()
        self._set_status(f'Grid set: {name}', COL_DESIGNER_STATUS_OK)

    def _sync_grid_cache(self) -> None:
        self._grid_buses = []
        self._grid_units = []
        if not self._shift.grid:
            return
        try:
            buses, _lines, units = load_designer_grid_named(self._shift.grid)
            self._grid_buses = buses
            self._grid_units = units
        except Exception:
            pass

    def _request_test(self) -> None:
        if self._campaign_shift_number is not None:
            if self.on_campaign_test_request is not None:
                self.on_campaign_test_request(self._campaign_shift_number)
            return
        if not self._shift.grid:
            self._set_status('Select a grid first (Ctrl+G)', COL_TEXT_WARN)
            return
        if not self._shift_file_name:
            self._set_status('Save the shift first (Ctrl+S)', COL_TEXT_WARN)
            return
        if self.on_test_request is not None:
            self.on_test_request(self._shift_file_name)

    # ─── Field-edit helpers (shared text-buffer editor) ────────────────────

    def _start_edit(self, field: str, current: str) -> None:
        self._editing_field = field
        self._edit_buffer = current

    def _handle_edit_key(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_RETURN:
            self._commit_edit()
            self._editing_field = None
            return True
        if event.key == pygame.K_ESCAPE:
            self._editing_field = None
            return True
        if event.key == pygame.K_BACKSPACE:
            self._edit_buffer = self._edit_buffer[:-1]
            return True
        if event.unicode:
            self._edit_buffer += event.unicode
        return True

    def _commit_edit(self) -> None:
        field = self._editing_field
        buf = self._edit_buffer.strip()
        try:
            if field == 'shift_date':
                self._shift.shift_date = buf
                self._mark_dirty()
            elif field == 'difficulty_label':
                self._shift.difficulty_label = buf
                self._mark_dirty()
            elif field == 'start_hour':
                self._shift.start_hour = max(0.0, min(24.0, float(buf)))
                self._mark_dirty()
            elif field == 'duration_hours':
                self._shift.duration_hours = max(0.5, float(buf))
                self._mark_dirty()
            elif field == 'handover_note_new':
                if buf:
                    self._shift.handover_notes.append(buf)
                self._mark_dirty()
            elif field.startswith('schedule_mw:'):
                unit_label = field.split(':', 1)[1]
                self._shift.initial_schedule[unit_label] = float(buf)
                self._mark_dirty('initial_schedule')
            elif field.startswith('demand_mw:'):
                _, bus, hour_s = field.split(':', 2)
                hour = float(hour_s)
                self._shift.substation_load_mw.setdefault(bus, {})[hour] = float(buf)
                self._mark_dirty('substation_load_mw')
            elif field.startswith('event_'):
                self._commit_event_edit(field, buf)
                self._mark_dirty('events')
        except ValueError:
            self._set_status(f'Invalid value: {buf!r}', COL_TEXT_CRIT)

    # ─── META tab ───────────────────────────────────────────────────────────

    def _on_key_meta(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_1:
            self._start_edit('shift_date', self._shift.shift_date)
        elif event.key == pygame.K_2:
            self._start_edit('difficulty_label', self._shift.difficulty_label)
        elif event.key == pygame.K_3:
            self._start_edit('start_hour', str(self._shift.start_hour))
        elif event.key == pygame.K_4:
            self._start_edit('duration_hours', str(self._shift.duration_hours))
        elif event.key == pygame.K_5:
            self._shift.agc_enabled = not self._shift.agc_enabled
            self._mark_dirty('agc_enabled')
        elif event.key == pygame.K_6:
            if self._campaign_shift_number is not None:
                return False   # narrative field — read-only for campaign shifts
            self._start_edit('handover_note_new', '')
        elif event.key == pygame.K_BACKSPACE and self._shift.handover_notes:
            if self._campaign_shift_number is not None:
                return False
            self._shift.handover_notes.pop()
            self._mark_dirty()
        else:
            return False
        return True

    # ─── GRID tab ───────────────────────────────────────────────────────────

    def _on_key_grid(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_g:
            if self._campaign_shift_number is not None:
                # Campaign topology isn't Designer-grid-backed (except
                # Shift 10's read-only GRID_SOURCE) — edit in the Grid
                # Designer instead, not here.
                self._set_status('Campaign topology is not editable here — use the Grid Designer', COL_TEXT_WARN)
                return True
            self._open_grid_browser()
            return True
        if event.key in (pygame.K_UP, pygame.K_w):
            self._maint_unit_cursor = max(0, self._maint_unit_cursor - 1)
            return True
        if event.key in (pygame.K_DOWN, pygame.K_s):
            self._maint_unit_cursor = min(max(0, len(self._grid_units) - 1),
                                          self._maint_unit_cursor + 1)
            return True
        if event.key == pygame.K_SPACE and self._grid_units:
            label = self._grid_units[self._maint_unit_cursor].label
            if label in self._shift.maintenance_units:
                self._shift.maintenance_units.remove(label)
            else:
                self._shift.maintenance_units.append(label)
            self._mark_dirty('maintenance_units')
            return True
        return False

    # ─── SCHEDULE tab (initial dispatch, per unit) ─────────────────────────

    def _on_key_schedule(self, event: pygame.event.Event) -> bool:
        if not self._grid_units:
            return False
        if event.key in (pygame.K_UP, pygame.K_w):
            self._schedule_cursor = max(0, self._schedule_cursor - 1)
            return True
        if event.key in (pygame.K_DOWN, pygame.K_s):
            self._schedule_cursor = min(len(self._grid_units) - 1, self._schedule_cursor + 1)
            return True
        if event.key == pygame.K_RETURN:
            unit = self._grid_units[self._schedule_cursor]
            current = self._shift.initial_schedule.get(unit.label, 0.0)
            self._start_edit(f'schedule_mw:{unit.label}', str(current))
            return True
        if event.key == pygame.K_BACKSPACE:
            unit = self._grid_units[self._schedule_cursor]
            self._shift.initial_schedule.pop(unit.label, None)   # absent = OFFLINE
            self._mark_dirty('initial_schedule')
            return True
        if event.key == pygame.K_m:
            unit = self._grid_units[self._schedule_cursor]
            self._shift.initial_schedule[unit.label] = unit.min_mw   # TECH MIN
            self._mark_dirty('initial_schedule')
            return True
        if event.key == pygame.K_x:
            unit = self._grid_units[self._schedule_cursor]
            self._shift.initial_schedule[unit.label] = unit.rated_mw   # MAX
            self._mark_dirty('initial_schedule')
            return True
        return False

    # ─── DEMAND tab (per-bus hourly load table) ────────────────────────────

    def _load_buses(self) -> list:
        return [b for b in self._grid_buses if b.bus_type == 'LOAD']

    def _on_key_demand(self, event: pygame.event.Event) -> bool:
        load_buses = self._load_buses()
        if not load_buses:
            return False
        if event.key in (pygame.K_LEFT,):
            return False   # reserved for tab switch
        if event.key in (pygame.K_UP, pygame.K_w):
            self._demand_bus_cursor = max(0, self._demand_bus_cursor - 1)
            return True
        if event.key in (pygame.K_DOWN, pygame.K_s):
            self._demand_bus_cursor = min(len(load_buses) - 1, self._demand_bus_cursor + 1)
            return True
        if event.key == pygame.K_PAGEUP:
            self._demand_hour_cursor = max(0, self._demand_hour_cursor - 1)
            return True
        if event.key == pygame.K_PAGEDOWN:
            self._demand_hour_cursor = min(24, self._demand_hour_cursor + 1)
            return True
        if event.key == pygame.K_RETURN:
            bus = load_buses[self._demand_bus_cursor]
            hour = float(self._demand_hour_cursor)
            current = self._shift.substation_load_mw.get(bus.label, {}).get(hour, 0.0)
            self._start_edit(f'demand_mw:{bus.label}:{hour}', str(current))
            return True
        return False

    # ─── EVENTS tab ─────────────────────────────────────────────────────────

    def _on_key_events(self, event: pygame.event.Event) -> bool:
        events = self._shift.events
        if event.key == pygame.K_INSERT or (event.key == pygame.K_n):
            events.append(ShiftEvent(trigger_min=0.0, priority='INFO', message='New event'))
            self._events_cursor = len(events) - 1
            self._mark_dirty('events')
            return True
        if not events:
            return False
        if event.key in (pygame.K_UP, pygame.K_w):
            self._events_cursor = max(0, self._events_cursor - 1)
            return True
        if event.key in (pygame.K_DOWN, pygame.K_s):
            self._events_cursor = min(len(events) - 1, self._events_cursor + 1)
            return True
        if event.key == pygame.K_DELETE:
            events.pop(self._events_cursor)
            self._events_cursor = max(0, self._events_cursor - 1)
            self._mark_dirty('events')
            return True

        evt = events[self._events_cursor]
        if event.key == pygame.K_1:
            self._start_edit('event_trigger_min', str(evt.trigger_min))
        elif event.key == pygame.K_2:
            idx = (_PRIORITY_CYCLE.index(evt.priority) + 1) % len(_PRIORITY_CYCLE) \
                if evt.priority in _PRIORITY_CYCLE else 0
            evt.priority = _PRIORITY_CYCLE[idx]
            self._mark_dirty('events')
        elif event.key == pygame.K_3:
            self._start_edit('event_message', evt.message)
        elif event.key == pygame.K_4:
            self._start_edit('event_detail', evt.detail)
        elif event.key == pygame.K_5:
            self._start_edit('event_element', evt.element or '')
        elif event.key == pygame.K_6:
            self._cycle_condition_metric(evt)
        elif event.key == pygame.K_7:
            self._cycle_action_type(evt)
        else:
            return False
        return True

    def _cycle_condition_metric(self, evt: ShiftEvent) -> None:
        if evt.condition is None:
            evt.condition = {'metric': _METRIC_CYCLE[0], 'op': '>=', 'value': 0.0, 'target': ''}
        else:
            idx = _METRIC_CYCLE.index(evt.condition['metric'])
            next_idx = idx + 1
            if next_idx >= len(_METRIC_CYCLE):
                evt.condition = None
                self._mark_dirty('events')
                return
            evt.condition['metric'] = _METRIC_CYCLE[next_idx]
        self._mark_dirty('events')

    def _cycle_action_type(self, evt: ShiftEvent) -> None:
        current = evt.action['type'] if evt.action else 'NONE'
        idx = (_ACTION_TYPE_CYCLE.index(current) + 1) % len(_ACTION_TYPE_CYCLE)
        new_type = _ACTION_TYPE_CYCLE[idx]
        if new_type == 'NONE':
            evt.action = None
        elif new_type == 'LINE_OPEN':
            evt.action = {'type': 'LINE_OPEN', 'line': ''}
        elif new_type == 'LINE_CLOSE':
            evt.action = {'type': 'LINE_CLOSE', 'line': ''}
        elif new_type == 'UNIT_TRIP':
            evt.action = {'type': 'UNIT_TRIP', 'unit': ''}
        self._mark_dirty('events')

    def _commit_event_edit(self, field: str, buf: str) -> None:
        evt = self._shift.events[self._events_cursor]
        if field == 'event_trigger_min':
            evt.trigger_min = float(buf)
        elif field == 'event_message':
            evt.message = buf
        elif field == 'event_detail':
            evt.detail = buf
        elif field == 'event_element':
            evt.element = buf or None
        elif field == 'event_condition_target':
            if evt.condition is not None:
                evt.condition['target'] = buf
        elif field == 'event_condition_value':
            if evt.condition is not None:
                evt.condition['value'] = float(buf)
        elif field == 'event_action_target':
            if evt.action is not None:
                key = 'line' if evt.action['type'] in ('LINE_OPEN', 'LINE_CLOSE') else 'unit'
                evt.action[key] = buf

    # ─── Drawing ────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        from display.shift_builder_panels import draw_shift_builder
        self._native.fill(COL_BACKGROUND)
        draw_shift_builder(self._native, self, self._font, self._font_large, self._scale)
