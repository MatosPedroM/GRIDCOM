"""
src/display/planning.py

PlanningScreen — the Phase 1 pre-shift unit-scheduling screen.

Player builds a full 24-hour generation schedule per dispatchable unit
against the forecasted load and wind, grouped by technology, with TECH
MIN/MAX quick-fills and an ONLINE/OFFLINE toggle per unit. On confirm,
invokes on_plan_complete(model) so the caller can seed the real-time
session's initial_schedule from the shift-start-hour column.

Coordinate system: native 1920x1080 space (mirrors ShiftBuilder/GridDesigner
— own letterboxed native surface sized at the real scaled display
resolution so text rasterizes crisply, no post-hoc stretch).

Used by any shift whose shift_NN.py sets USES_PLANNING = True (currently
Shift 5) — see gameplay/phase1.py and main.py's BRIEFING state handler.
"""

from __future__ import annotations

from typing import Callable

import pygame
import pygame.freetype

from display.palette import COL_BACKGROUND, COL_DESIGNER_STATUS_INFO, COL_TEXT_CRIT
from gameplay.phase1 import PlanningModel
from simulation.constants import (
    NATIVE_WIDTH, NATIVE_HEIGHT,
    FONT_PATH_MONO_REGULAR,
    PLANNING_FONT_SIZE, PLANNING_FONT_SIZE_LARGE,
    PLANNING_STATUS_DISPLAY_S,
    PLANNING_KEY_UP, PLANNING_KEY_DOWN, PLANNING_KEY_LEFT, PLANNING_KEY_RIGHT,
    PLANNING_KEY_EDIT, PLANNING_KEY_TECH_MIN, PLANNING_KEY_TECH_MAX,
    PLANNING_KEY_ZERO, PLANNING_KEY_TOGGLE_ONLINE, PLANNING_KEY_TOGGLE_AGC,
    PLANNING_KEY_RESET,
    PLANNING_KEY_AUTO, PLANNING_KEY_CONFIRM, PLANNING_KEY_BACK,
)
from utils.helpers import resource_path


class PlanningScreen:
    """
    Form-driven 24h unit-scheduling editor. Owns its own rendering and
    event handling — call tick(dt, display_surf) each frame, route pygame
    events to on_key / on_click / on_mouse_move / on_mouse_down / on_mouse_up.
    """

    def __init__(self, display_surf: pygame.Surface, model: PlanningModel,
                 shift_number: int = 10) -> None:
        self._display_surf = display_surf
        dw, dh = display_surf.get_size()
        self._scale = min(dw / NATIVE_WIDTH, dh / NATIVE_HEIGHT)
        ox = (dw - int(NATIVE_WIDTH * self._scale)) // 2
        oy = (dh - int(NATIVE_HEIGHT * self._scale)) // 2
        self._letterbox = pygame.Rect(ox, oy,
                                      int(NATIVE_WIDTH * self._scale),
                                      int(NATIVE_HEIGHT * self._scale))
        self._native = pygame.Surface((self._letterbox.width, self._letterbox.height)).convert()

        _font_path = resource_path(FONT_PATH_MONO_REGULAR)
        try:
            self._font       = pygame.freetype.Font(_font_path, PLANNING_FONT_SIZE)
            self._font_large = pygame.freetype.Font(_font_path, PLANNING_FONT_SIZE_LARGE)
        except Exception:
            self._font       = pygame.freetype.SysFont('monospace', PLANNING_FONT_SIZE)
            self._font_large = pygame.freetype.SysFont('monospace', PLANNING_FONT_SIZE_LARGE)
        self._font.antialiased       = False
        self._font_large.antialiased = False

        self._model = model
        self._shift_number = shift_number

        # Table cursor: row index into _row_index (unit labels, rebuilt each
        # draw), column index into model.hours.
        self._sel_row: int = 0
        self._sel_col: int = 0
        self._row_index: list[str] = []

        # Click hit-rect registry, rebuilt each draw in logical native coords.
        self._hit_rects: list[tuple[str, pygame.Rect]] = []

        # Cell text-buffer editor.
        self._editing: str | None = None   # f'{unit_label}:{hour}' while editing
        self._edit_buffer: str = ''

        self._status_text: str = ''
        self._status_colour: tuple = COL_DESIGNER_STATUS_INFO
        self._status_timer: float = 0.0

        # Set when F10 is pressed and the plan clears the minimum-reserve
        # floor but trips the over-generation warning — confirmation is
        # held until a second F10 press so the player actually sees the
        # warning (on_plan_complete() switches the game state away from
        # this screen immediately, so a toast set right before it would
        # never be visible). Cleared by any edit to the plan.
        self._pending_confirm: bool = False

        # Invoked with the finished model when the player confirms the plan.
        self.on_plan_complete: Callable[[PlanningModel], None] | None = None

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
        if self._editing is not None:
            return
        x, y = native_pos
        for action, rect in reversed(self._hit_rects):
            if rect.collidepoint(x, y):
                self._handle_action(action)
                return

    def on_key(self, event: pygame.event.Event) -> bool:
        """Handle a KEYDOWN event. Returns True if consumed, False if the
        caller should back out to the main menu (ESC at top level)."""
        if self._editing is not None:
            return self._handle_edit_key(event)

        mods = pygame.key.get_mods()
        shift_held = bool(mods & pygame.KMOD_SHIFT)
        ctrl_held = bool(mods & pygame.KMOD_CTRL)

        if event.key == PLANNING_KEY_BACK:
            return False

        # Any key other than CONFIRM itself means the player is doing
        # something other than answering the pending over-generation
        # warning — drop it so a stale "press again" state can't silently
        # wave through a plan the player has since changed.
        if event.key != PLANNING_KEY_CONFIRM:
            self._pending_confirm = False

        if ctrl_held and event.key == PLANNING_KEY_AUTO:
            self._model.auto_schedule()
            self._set_status('Auto-scheduled 24h plan', COL_DESIGNER_STATUS_INFO)
            return True

        if not self._row_index:
            return True

        if event.key in PLANNING_KEY_UP:
            self._sel_row = max(0, self._sel_row - 1)
        elif event.key in PLANNING_KEY_DOWN:
            self._sel_row = min(len(self._row_index) - 1, self._sel_row + 1)
        elif event.key == PLANNING_KEY_LEFT:
            self._sel_col = max(0, self._sel_col - 1)
        elif event.key == PLANNING_KEY_RIGHT:
            self._sel_col = min(len(self._model.hours) - 1, self._sel_col + 1)
        elif event.key == PLANNING_KEY_EDIT:
            self._start_cell_edit()
        elif event.key == PLANNING_KEY_TECH_MIN:
            label = self._selected_label()
            hour = self._selected_hour()
            if shift_held:
                self._model.fill_row_min(label)
            else:
                self._model.fill_cell_min(label, hour)
        elif event.key == PLANNING_KEY_TECH_MAX:
            label = self._selected_label()
            hour = self._selected_hour()
            if shift_held:
                self._model.fill_row_max(label)
            else:
                self._model.fill_cell_max(label, hour)
        elif event.key == PLANNING_KEY_ZERO:
            label = self._selected_label()
            hour = self._selected_hour()
            if shift_held:
                self._model.fill_row_zero(label)
            else:
                self._model.fill_cell_zero(label, hour)
        elif event.key == PLANNING_KEY_TOGGLE_ONLINE:
            self._model.toggle_online(self._selected_label())
        elif event.key == PLANNING_KEY_TOGGLE_AGC:
            label = self._selected_label()
            if self._model.is_agc_eligible(label):
                self._model.toggle_agc_enrolled(label)
                state = 'ENROLLED' if self._model.is_agc_enrolled(label) else 'excluded'
                self._set_status(f'{label} AGC {state}', COL_DESIGNER_STATUS_INFO)
            else:
                self._set_status(f'{label} is not an AGC-eligible type this shift', COL_TEXT_CRIT)
        elif event.key == PLANNING_KEY_RESET:
            self._model.reset()
            self._set_status('Schedule reset — all units OFFLINE', COL_DESIGNER_STATUS_INFO)
        elif event.key == PLANNING_KEY_CONFIRM:
            self._confirm_plan()
        return True

    def tick(self, dt: float, display_surf: pygame.Surface) -> None:
        if self._status_timer > 0.0:
            self._status_timer -= dt
        from display.planning_panels import draw_planning
        draw_planning(self._native, self, self._font, self._font_large, self._scale)
        display_surf.fill(COL_BACKGROUND)
        display_surf.blit(self._native, self._letterbox.topleft)

    # ─── Internal ───────────────────────────────────────────────────────────

    def _selected_label(self) -> str:
        return self._row_index[self._sel_row]

    def _selected_hour(self) -> float:
        return self._model.hours[self._sel_col]

    def _handle_action(self, action: str) -> None:
        self._pending_confirm = False
        kind, _, rest = action.partition(':')
        if kind == 'toggle':
            label = rest
            self._model.toggle_online(label)
            if label in self._row_index:
                self._sel_row = self._row_index.index(label)
        elif kind == 'cell':
            label, _, hour_s = rest.partition(':')
            hour = float(hour_s)
            if label in self._row_index:
                self._sel_row = self._row_index.index(label)
            self._sel_col = self._model.hours.index(hour)
            self._start_cell_edit()

    def _start_cell_edit(self) -> None:
        label = self._selected_label()
        hour = self._selected_hour()
        current = self._model.schedule.get(label, {}).get(hour, 0.0)
        self._editing = f'{label}:{hour}'
        self._edit_buffer = f'{current:.0f}'

    def _handle_edit_key(self, event: pygame.event.Event) -> bool:
        if event.key == PLANNING_KEY_EDIT:
            self._commit_edit()
            self._editing = None
            return True
        if event.key == PLANNING_KEY_BACK:
            self._editing = None
            return True
        if event.key == pygame.K_BACKSPACE:
            self._edit_buffer = self._edit_buffer[:-1]
            return True
        if event.unicode and (event.unicode.isdigit() or event.unicode in '.-'):
            self._edit_buffer += event.unicode
        return True

    def _commit_edit(self) -> None:
        self._pending_confirm = False
        label, _, hour_s = self._editing.partition(':')
        hour = float(hour_s)
        buf = self._edit_buffer.strip()
        try:
            self._model.set_cell(label, hour, float(buf))
        except ValueError:
            self._set_status(f'Invalid value: {buf!r}', COL_TEXT_CRIT)

    def _confirm_plan(self) -> None:
        remaining = self._model.remaining_budget()
        if remaining < 0.0:
            self._pending_confirm = False
            self._set_status(
                f'Cannot confirm: plan is EUR {-remaining:,.0f} over budget',
                COL_TEXT_CRIT)
            return

        self._pending_confirm = False
        if self.on_plan_complete is not None:
            self.on_plan_complete(self._model)

    def _set_status(self, text: str, colour: tuple = None) -> None:
        self._status_text = text
        self._status_colour = colour or COL_DESIGNER_STATUS_INFO
        self._status_timer = PLANNING_STATUS_DISPLAY_S
