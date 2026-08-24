"""
src/display/renderer.py

Renderer: owns the native 1920×1080 surface, drives the render loop,
and composites all display layers each frame.

Native resolution is always 1920×1080 regardless of monitor size.
At the end of each frame the native surface is scaled to the display surface.

Layers (bottom to top):
  1. Top bar — power balance (GEN/LOAD/BAL/... + regulation band)
  2. Canvas background + grid schematic (GridCanvas)
  3. Instrument strip — panels (frequency, dispatch, forecast, gen mix, alarms)
  4. Debug overlay                 (when DEBUG_DISPLAY = True)

Usage:
    renderer = Renderer(display_surf, shift=1)
    # game loop:
    renderer.tick(dt_real_s, state=None)
    pygame.display.flip()
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque

import pygame
import pygame.freetype

from display.canvas import GridCanvas
from display.geometry import point_segment_dist
from display.context import draw_unit_context, draw_bus_context, draw_line_context
from display.editor import GridEditor
from display.symbols import draw_load_triangles
from display.panels import (
    draw_frequency_panel, draw_topbar_panel,
    draw_dispatch_panel, draw_alarm_panel,
    draw_genmix_panel, draw_forecast_panel,
)
from display.palette import (
    COL_BACKGROUND, COL_STRIP_BG, COL_DEBUG_TEXT, COL_DEBUG_GRID, COL_TEXT_DIM,
    COL_FPS_TEXT, COL_150KV,
    COL_TEXT_BODY, COL_TEXT_SCREEN_HDR, COL_MENU_CURSOR, COL_MENU_DISABLED,
    COL_PANEL_BORDER, COL_TEXT_PRIMARY,
)
import simulation.constants as _sim_const
from simulation.constants import (
    TITLE_BAR_HEIGHT, TOPBAR_HEIGHT, CANVAS_HEIGHT, STRIP_HEIGHT,
    HINT_GAP_HEIGHT, HINT_BAR_HEIGHT,
    NATIVE_WIDTH, NATIVE_HEIGHT,
    FONT_PATH_MONO_REGULAR,
    FONT_SIZE_PANEL, FONT_SIZE_OVERLAY, FONT_SIZE_HINT,
    PANEL_FREQ_X, PANEL_FREQ_W,
    PANEL_DISPATCH_X, PANEL_DISPATCH_W,
    PANEL_FORECAST_X, PANEL_FORECAST_W,
    PANEL_GENMIX_X, PANEL_GENMIX_W,
    PANEL_ALARM_X, PANEL_ALARM_W,
    TEXT_SCREEN_FONT_SIZE, TEXT_SCREEN_TOP_MARGIN, TEXT_SCREEN_ROW_H,
    MENU_FONT_SIZE, MENU_ROW_H, MENU_TOP_MARGIN,
    PERF_DEBUG_LOG, PERF_LOG_INTERVAL_S,
    TARGET_FPS, FREQ_HISTORY_WINDOW_S,
    SVC_Q_STEP_MVAR,
    LOAD_SHED_STEP_FRACTION,
    UNIT_MW_STEP, UNIT_MW_STEP_FAST_MULT,
    GEN_Q_SETPOINT_STEP_MVAR, GEN_Q_SETPOINT_STEP_FAST_MULT,
)
from utils.helpers import resource_path
from gameplay.shifts.loader import load_shift_config
from display.sound import SoundManager


_BLINK_2HZ_PERIOD = 0.5   # seconds per 2Hz blink cycle (alarm panel)
_BLINK_PERIOD     = 1.0   # seconds per blink cycle (canvas, dispatch panel)
_HIT_RADIUS       = 10    # px — Chebyshev hit radius for bus/unit selection
_LINE_HIT_PX      = 8     # px — max perpendicular distance for line selection


class Renderer:
    """
    Owns the 1920×1080 native surface and drives frame composition.

    Args:
        display_surf:  The pygame display surface (any resolution).
        shift:         Active shift number; passed to GridCanvas.
    """

    def __init__(
        self,
        display_surf: pygame.Surface,
        shift: int,
        display_size: tuple[int, int] | None = None,
    ) -> None:
        self._display = display_surf

        # Letterbox geometry: uniform scale so both axes expand by the same factor.
        # min() picks the axis that runs out of space first; the other axis gets bars.
        disp_w, disp_h = display_size if display_size else (NATIVE_WIDTH, NATIVE_HEIGHT)
        self._scale          = min(disp_w / NATIVE_WIDTH, disp_h / NATIVE_HEIGHT)
        scaled_w             = int(NATIVE_WIDTH  * self._scale)
        scaled_h             = int(NATIVE_HEIGHT * self._scale)
        scaled_title_h       = int(TITLE_BAR_HEIGHT * self._scale)
        scaled_topbar_h      = int(TOPBAR_HEIGHT * self._scale)
        scaled_canvas_h      = int(CANVAS_HEIGHT * self._scale)
        scaled_strip_h       = int(STRIP_HEIGHT * self._scale)
        scaled_hint_gap_h    = int(HINT_GAP_HEIGHT * self._scale)
        scaled_hint_bar_h    = (scaled_h - scaled_title_h - scaled_topbar_h - scaled_canvas_h
                                 - scaled_strip_h - scaled_hint_gap_h)
        # _scaled_topbar_h doubles as "canvas's absolute y-offset from native
        # (0,0)" for hit-testing (_to_canvas_local(), on_scroll()) — title
        # bar sits above the topbar, so it's folded into this offset rather
        # than tracked as a separate variable every consumer would need.
        self._scaled_topbar_h = scaled_title_h + scaled_topbar_h
        self._scaled_canvas_h = scaled_canvas_h
        offset_x             = (disp_w - scaled_w) // 2
        offset_y             = (disp_h - scaled_h) // 2
        self._letterbox_rect = pygame.Rect(offset_x, offset_y, scaled_w, scaled_h)

        # Paint letterbox bars black once — they never change so no per-frame fill needed.
        self._display.fill((0, 0, 0))

        # Native surface converted to display pixel format for hardware-accelerated blits.
        self._native        = pygame.Surface((scaled_w, scaled_h)).convert()
        self._display_dirty = True   # force first-frame blit to display

        # Title region: top-most scaled_title_h rows — shift description
        self._title_surf = self._native.subsurface(
            pygame.Rect(0, 0, scaled_w, scaled_title_h)
        )
        # Top bar region: scaled_topbar_h rows below the title
        self._topbar_surf = self._native.subsurface(
            pygame.Rect(0, scaled_title_h, scaled_w, scaled_topbar_h)
        )
        # Canvas region: scaled_canvas_h rows below the top bar
        self._canvas_surf = self._native.subsurface(
            pygame.Rect(0, self._scaled_topbar_h, scaled_w, scaled_canvas_h)
        )
        # Strip region: scaled_strip_h rows below the canvas
        self._strip_surf = self._native.subsurface(
            pygame.Rect(0, self._scaled_topbar_h + scaled_canvas_h, scaled_w, scaled_strip_h)
        )
        # Shortcut hint bar: bottom-most rows, separated from the strip by a
        # blank scaled_hint_gap_h gap (left unpainted — native background colour)
        self._hint_bar_surf = self._native.subsurface(
            pygame.Rect(
                0,
                self._scaled_topbar_h + scaled_canvas_h + scaled_strip_h + scaled_hint_gap_h,
                scaled_w, scaled_hint_bar_h,
            )
        )

        font_path = resource_path(FONT_PATH_MONO_REGULAR)
        if font_path.exists():
            self._font = pygame.freetype.Font(str(font_path), 11)
        else:
            self._font = pygame.freetype.SysFont('monospace', 11)
        self._font.antialiased = False   # hard pixel edges; NN-equivalent at integer scale

        self._canvas = GridCanvas(shift=shift, font=self._font, scale=self._scale)
        self._editor = GridEditor(self._canvas, scale=self._scale)
        _difficulty_label = load_shift_config(shift).get('difficulty_label', '')
        self._shift_title: str = (
            f'SHIFT {shift}  —  {_difficulty_label.upper()}'
            if _difficulty_label else f'SHIFT {shift}'
        )
        # Drawn once — the title never changes after construction, unlike
        # every other region of the screen — into its own dedicated row
        # above the topbar (was previously drawn every frame overlapping
        # the canvas's top pixels).
        _fso = int(FONT_SIZE_OVERLAY * self._scale)
        _tw, _ = self._font.get_rect(self._shift_title, size=_fso)[2:4]
        _cx = (self._title_surf.get_width() - _tw) // 2
        self._font.render_to(
            self._title_surf,
            (_cx, int(4 * self._scale)),
            self._shift_title, COL_TEXT_PRIMARY, size=_fso,
        )

        # Grid reference for dispatch panel (set by main via set_grid)
        self._grid = None

        self._blink_timer: float = 0.0
        self._blink_on:    bool  = True

        # 2Hz blink for alarm panel
        self._blink_2hz_timer: float = 0.0
        self._blink_2hz_on:    bool  = True

        # Panel scroll offsets
        self._alarm_scroll: int = 0

        # Frequency / load-variation history — sampled once per rendered frame,
        # display-only concern (simulation.py holds no history of its own for
        # either). Load variation is MW/min, derived from consecutive load
        # samples using sim-time elapsed (not real-time — the game runs at
        # variable speed multipliers, so a real-time derivative would mean a
        # different thing at each speed).
        _freq_hist_len = max(1, int(FREQ_HISTORY_WINDOW_S * TARGET_FPS))
        self._freq_history: deque[float] = deque(maxlen=_freq_hist_len)
        self._load_rate_history: deque[float] = deque(maxlen=_freq_hist_len)
        self._prev_load_mw:      float | None = None
        self._prev_load_sim_hour: float | None = None

        # Panel surface cache: converted to display pixel format for fast blits.
        _sc = self._scale
        self._panel_cache: dict[str, pygame.Surface] = {
            'topbar':   pygame.Surface((scaled_w, scaled_topbar_h)).convert(),
            'freq':     pygame.Surface((int(PANEL_FREQ_W     * _sc), scaled_strip_h)).convert(),
            'dispatch': pygame.Surface((int(PANEL_DISPATCH_W * _sc), scaled_strip_h)).convert(),
            'forecast': pygame.Surface((int(PANEL_FORECAST_W * _sc), scaled_strip_h)).convert(),
            'genmix':   pygame.Surface((int(PANEL_GENMIX_W   * _sc), scaled_strip_h)).convert(),
            'alarm':    pygame.Surface((int(PANEL_ALARM_W    * _sc), scaled_strip_h)).convert(),
        }
        # Sentinel objects force a full draw on the first frame
        self._panel_keys: dict[str, object] = {k: object() for k in self._panel_cache}

        # Shortcut hint bar: redrawn only when the hint text changes (see
        # _build_shortcut_hint()/tick()) — sentinel forces the first-frame draw.
        self._hint_bar_text: object = object()

        # Sound: alarm loop + info/tutor ping, driven from tick()
        self._sound = SoundManager()

        # Selection state
        self._selected_label: str | None = None

        # Unit dispatch input state
        self._input_buffer: str  = ''
        self._input_active: bool = False

        # START/STOP button keyboard focus
        self._cmd_active: bool = False

        # AUTO/MANUAL dispatch-mode button keyboard focus
        self._mode_cmd_active: bool = False

        # TRIP/CLOSE button keyboard focus
        self._line_cmd_active: bool = False

        # AVR setpoint input state (generator voltage setpoint — separate
        # from the MW target buffer so the two commands never collide)
        self._setpoint_buffer: str  = ''
        self._setpoint_active: bool = False

        # SVC adjust command keyboard focus
        self._svc_cmd_active: bool = False

        # Active-power nudge mode (G arms it, Up/Down steps target_mw) —
        # alternative to the digit+Enter buffer above for fast adjustments.
        self._adjust_active: bool = False
        self._setpoint_adjust_active: bool = False

        # Debug state
        self._mouse_pos:       tuple[int, int] = (0, 0)
        self._click_pos:       tuple[int, int] | None = None
        self._click_timer:     float = 0.0
        self._frame_time:      float = 0.0
        self._fps:             float = 0.0
        self._fps_smooth:      float = 0.0
        self._debug_grid_surf: pygame.Surface | None = None  # cached on first debug draw

        # Perf profiling state (used when DEBUG_PERF is True — see tick())
        self._perf_last_ms:  dict[str, float] = {}   # last-frame timings, for on-screen display
        self._perf_accum_ms: dict[str, float] = {}   # sum since last log flush
        self._perf_accum_frames: int   = 0
        self._perf_log_timer:    float = 0.0
        self._perf_logger: logging.Logger | None = None
        if _sim_const.DEBUG_PERF:
            os.makedirs('logs', exist_ok=True)
            _plogger = logging.getLogger('perf')
            _plogger.setLevel(logging.DEBUG)
            _plogger.propagate = False
            _plogger.handlers.clear()
            _phandler = logging.FileHandler(PERF_DEBUG_LOG, mode='w', encoding='utf-8')
            _phandler.setFormatter(logging.Formatter('%(message)s'))
            _plogger.addHandler(_phandler)
            self._perf_logger = _plogger

    # ─── Per-frame entry point ────────────────────────────────────────────────

    def set_grid(self, grid) -> None:
        """Store the Grid reference used by the dispatch panel."""
        self._grid = grid

    def set_designer_grid(self, grid) -> None:
        """Load a DesignerGrid into both the dispatch panel and the canvas topology."""
        self._grid = grid
        self._canvas.load_designer_topology(
            buses=grid.get_active_buses(),
            lines=grid.get_active_lines(),
            units=grid.get_active_units(),
            station_positions=grid.get_station_positions(),
            bus_label_anchors=grid.get_bus_label_anchors(),
            station_label_anchors=grid.get_station_label_anchors(),
        )

    def on_scroll(self, delta: int, pos: tuple[int, int]) -> None:
        """Route mouse wheel to the alarm panel based on native-space position."""
        if pos[1] < self._scaled_topbar_h + self._scaled_canvas_h:
            return
        nx = pos[0]
        if PANEL_ALARM_X <= nx < PANEL_ALARM_X + PANEL_ALARM_W:
            self._alarm_scroll = max(0, self._alarm_scroll - delta)

    def clear_selection(self) -> None:
        """Clear the currently selected element and reset input state."""
        self._selected_label  = None
        self._input_buffer    = ''
        self._input_active    = False
        self._cmd_active      = False
        self._mode_cmd_active = False
        self._line_cmd_active = False
        self._setpoint_buffer = ''
        self._setpoint_active = False
        self._svc_cmd_active  = False
        self._adjust_active   = False
        self._setpoint_adjust_active = False

    def _get_selected_unit(self):
        """Return the GenerationUnit for _selected_label if it is a unit, else None."""
        if self._selected_label is None:
            return None
        for units in self._canvas._station_units.values():
            for unit in units:
                if unit.label == self._selected_label:
                    return unit
        return None

    def on_key_digit(self, ch: str) -> None:
        """Feed one digit character to the unit target input buffer."""
        if self._get_selected_unit() is None:
            return
        self._input_active = True
        if len(self._input_buffer) < 4:
            self._input_buffer += ch

    def on_backspace(self) -> None:
        """Remove last character from input buffer."""
        if self._input_active and self._input_buffer:
            self._input_buffer = self._input_buffer[:-1]

    def on_enter(self, sim) -> None:
        """
        Commit the input buffer as a dispatch target.
        Activates input mode if Enter is pressed with no buffer.
        Clamps target to [min_mw, rated_mw] before dispatching.
        """
        unit = self._get_selected_unit()
        if unit is None:
            return
        if not self._input_active or not self._input_buffer:
            self._input_active = True
            return
        try:
            raw = int(self._input_buffer)
        except ValueError:
            self._input_buffer = ''
            return
        clamped = max(int(unit.min_mw), min(int(unit.rated_mw), raw))
        sim.set_unit_target(unit.label, float(clamped))
        self._input_buffer = ''
        self._input_active = False

    def on_start_unit(self, sim) -> None:
        """Issue a START command for the selected OFFLINE unit."""
        unit = self._get_selected_unit()
        if unit is None:
            return
        if sim.get_state() is None:
            return
        state = sim.get_state()
        if state.unit_states.get(unit.label) != 'OFFLINE':
            return
        if unit.label in state.unit_maintenance:
            return
        sim.start_unit(unit.label)
        self._cmd_active = False

    def on_stop_unit(self, sim) -> None:
        """Issue a STOP command for the selected ONLINE unit."""
        unit = self._get_selected_unit()
        if unit is None:
            return
        if sim.get_state() is None:
            return
        if sim.get_state().unit_states.get(unit.label) != 'ONLINE':
            return
        sim.stop_unit(unit.label)
        self._cmd_active = False

    def on_toggle_auto_mode(self, sim) -> None:
        """
        Return the selected unit to AUTO dispatch mode (follows its Phase 1
        hourly schedule). No-op if the unit is already AUTO, not ONLINE, or
        this shift has no schedule for it — there is no button to leave
        AUTO; setting a target manually (digit keys + Enter) does that.
        """
        unit = self._get_selected_unit()
        if unit is None:
            return
        if not sim.has_hourly_schedule(unit.label):
            return
        if sim.get_unit_dispatch_mode(unit.label) == 'AUTO':
            return
        sim.set_unit_auto_mode(unit.label)
        self._mode_cmd_active = False

    def _get_selected_line(self):
        """Return the Line dataclass for _selected_label if it is a line, else None."""
        if self._selected_label is None:
            return None
        return next(
            (l for l in self._canvas._lines if l.label == self._selected_label),
            None,
        )

    def on_trip_line(self, sim) -> None:
        """Issue a TRIP command for the selected IN SERVICE line."""
        line = self._get_selected_line()
        if line is None:
            return
        state = sim.get_state()
        if state is None:
            return
        if state.line_status.get(line.label) != 'IN_SERVICE':
            return
        sim.trip_line(line.label)
        self._line_cmd_active = False

    def on_close_line(self, sim) -> None:
        """Issue a CLOSE command for the selected TRIPPED line."""
        line = self._get_selected_line()
        if line is None:
            return
        state = sim.get_state()
        if state is None:
            return
        if state.line_status.get(line.label) != 'TRIPPED':
            return
        sim.close_line(line.label)
        self._line_cmd_active = False

    def _get_selected_bus(self):
        """Return the Bus dataclass for _selected_label if it is a bus, else None."""
        if self._selected_label is None:
            return None
        return self._canvas._bus_map.get(self._selected_label)

    def on_setpoint_toggle(self) -> None:
        """Enter reactive-power (Q target) edit mode for the selected unit."""
        unit = self._get_selected_unit()
        if unit is None:
            return
        self._setpoint_active = True

    def on_setpoint_digit(self, ch: str) -> None:
        """Feed one character (digit) to the Q target input buffer."""
        if self._get_selected_unit() is None:
            return
        self._setpoint_active = True
        if len(self._setpoint_buffer) < 5:
            self._setpoint_buffer += ch

    def on_setpoint_minus(self) -> None:
        """
        Toggle a leading '-' on the Q target input buffer. MVAr targets are
        routinely negative (absorbing) — unlike the MW target buffer, which
        never needs a sign. Pressing again removes it.
        """
        if self._get_selected_unit() is None:
            return
        self._setpoint_active = True
        if self._setpoint_buffer.startswith('-'):
            self._setpoint_buffer = self._setpoint_buffer[1:]
        else:
            self._setpoint_buffer = '-' + self._setpoint_buffer

    def on_setpoint_backspace(self) -> None:
        if self._setpoint_active and self._setpoint_buffer:
            self._setpoint_buffer = self._setpoint_buffer[:-1]

    def on_setpoint_enter(self, sim) -> None:
        """
        Commit the setpoint buffer as the selected unit's reactive-power
        target (MVAr). Activates edit mode if Enter is pressed with no
        buffer — mirrors on_enter()'s MW-target behaviour, kept as a
        separate flag/buffer pair so the two input modes never collide.
        Clamped to [unit.q_min_mvar, unit.q_max_mvar] before dispatching —
        every unit has its own reactive range, unlike the old AVR pu
        setpoint's single global band.
        """
        unit = self._get_selected_unit()
        if unit is None:
            return
        if not self._setpoint_active or not self._setpoint_buffer:
            self._setpoint_active = True
            return
        try:
            raw = int(self._setpoint_buffer)
        except ValueError:
            self._setpoint_buffer = ''
            return
        clamped = max(unit.q_min_mvar, min(unit.q_max_mvar, float(raw)))
        sim.set_unit_q_target(unit.label, clamped)
        self._setpoint_buffer = ''
        self._setpoint_active = False

    def on_setpoint_adjust_toggle(self) -> None:
        """Arm reactive-power (Q target) nudge mode for the selected unit.

        Disarms active-power nudge mode so UP/DOWN always drive exactly one
        quantity.
        """
        unit = self._get_selected_unit()
        if unit is None:
            return
        self._setpoint_adjust_active = True
        self._adjust_active = False

    def on_setpoint_adjust(self, sim, direction: int, fast: bool = False) -> None:
        """
        Nudge the selected unit's reactive-power target by one
        GEN_Q_SETPOINT_STEP_MVAR (direction = +1 or -1), or by
        GEN_Q_SETPOINT_STEP_MVAR * GEN_Q_SETPOINT_STEP_FAST_MULT if
        fast=True (Ctrl held). Clamped to [unit.q_min_mvar, unit.q_max_mvar],
        same bounds on_setpoint_enter() applies. Mirrors on_target_adjust();
        no-op unless this mode is armed.
        """
        if not self._setpoint_adjust_active:
            return
        unit = self._get_selected_unit()
        if unit is None:
            return
        state = sim.get_state()
        if state is None:
            return
        step = GEN_Q_SETPOINT_STEP_MVAR * (
            GEN_Q_SETPOINT_STEP_FAST_MULT if fast else 1.0
        )
        current = state.unit_q_target_mvar.get(unit.label, 0.0)
        clamped = max(unit.q_min_mvar,
                      min(unit.q_max_mvar, current + direction * step))
        sim.set_unit_q_target(unit.label, clamped)

    def on_adjust_toggle(self) -> None:
        """Arm active-power nudge mode for the selected dispatchable unit.

        Disarms reactive-power nudge mode so UP/DOWN always drive exactly one
        quantity.
        """
        unit = self._get_selected_unit()
        if unit is None:
            return
        self._adjust_active = True
        self._setpoint_adjust_active = False

    def on_target_adjust(self, sim, direction: int, fast: bool = False) -> None:
        """
        Nudge the selected unit's MW target by one UNIT_MW_STEP (direction
        = +1 or -1), or UNIT_MW_STEP * UNIT_MW_STEP_FAST_MULT if fast=True
        (Ctrl held). Clamped to [unit.min_mw, unit.rated_mw], same bounds
        on_enter() applies. No-op unless adjust mode is armed.
        """
        if not self._adjust_active:
            return
        unit = self._get_selected_unit()
        if unit is None:
            return
        state = sim.get_state()
        if state is None:
            return
        step = UNIT_MW_STEP * (UNIT_MW_STEP_FAST_MULT if fast else 1.0)
        current = state.unit_targets_mw.get(unit.label, unit.min_mw)
        clamped = max(unit.min_mw, min(unit.rated_mw, current + direction * step))
        sim.set_unit_target(unit.label, clamped)

    def on_svc_adjust(self, sim, direction: int) -> None:
        """
        Adjust the selected bus's manual SVC setpoint by one step
        (direction = +1 or -1) via SVC_Q_STEP_MVAR. No-op if the selected
        bus hosts no SVC.
        """
        bus = self._get_selected_bus()
        if bus is None:
            return
        state = sim.get_state()
        if state is None or bus.label not in state.bus_svc_mvar:
            return
        self._svc_cmd_active = True
        current = state.bus_svc_mvar.get(bus.label, 0.0)
        sim.set_svc_setpoint(bus.label, current + direction * SVC_Q_STEP_MVAR)

    def on_shed_load(self, sim) -> None:
        """
        Shed one LOAD_SHED_STEP_FRACTION block of load at the selected bus.

        Cumulative — repeat presses shed progressively more, up to 100%.
        No-op unless a load substation is selected.
        """
        bus = self._get_selected_bus()
        if bus is None:
            return
        sim.shed_load(bus.label, LOAD_SHED_STEP_FRACTION)

    def on_clear_shed(self, sim) -> None:
        """Restore all shed load at the selected bus. No-op if none is shed."""
        bus = self._get_selected_bus()
        if bus is None:
            return
        sim.clear_shed(bus.label)

    def on_ack_alarm(self, sim) -> None:
        """Acknowledge the first unacknowledged alarm."""
        state = sim.get_state()
        if state is None:
            return
        for alarm in state.active_alarms:
            if not alarm.acknowledged:
                sim.acknowledge_alarm(alarm.alarm_id)
                return

    def on_ack_all_alarms(self, sim) -> None:
        """Acknowledge all unacknowledged alarms."""
        sim.acknowledge_all_alarms()

    def on_silence_alarm(self) -> None:
        """Stop the alarm sound until a new WARNING/CRITICAL alarm is raised."""
        self._sound.silence()

    def _selectable_labels(self) -> list[str]:
        """Flat ordered list: all active unit labels, then bus labels, then line labels."""
        labels: list[str] = []
        for units in self._canvas._station_units.values():
            for unit in units:
                labels.append(unit.label)
        for bus in self._canvas._buses:
            labels.append(bus.label)
        for line in self._canvas._lines:
            labels.append(line.label)
        return labels

    def on_tab(self) -> None:
        """Advance selection to the next element (units first, then buses), wrapping."""
        labels = self._selectable_labels()
        if not labels:
            return
        try:
            idx = labels.index(self._selected_label)
        except ValueError:
            idx = -1
        self._selected_label = labels[(idx + 1) % len(labels)]
        self._input_buffer   = ''
        self._input_active   = False
        self._cmd_active     = False
        self._setpoint_buffer = ''
        self._setpoint_active = False
        self._svc_cmd_active  = False
        self._adjust_active   = False
        self._setpoint_adjust_active = False

    def on_escape(self) -> None:
        """
        Cancel input if active; clear cmd focus if active; otherwise deselect.
        No-op when nothing is selected — main.py handles global quit.
        """
        if self._input_active:
            self._input_buffer = ''
            self._input_active = False
        elif self._setpoint_active:
            self._setpoint_buffer = ''
            self._setpoint_active = False
        elif self._cmd_active:
            self._cmd_active = False
        elif self._line_cmd_active:
            self._line_cmd_active = False
        elif self._svc_cmd_active:
            self._svc_cmd_active = False
        elif self._adjust_active:
            self._adjust_active = False
        elif self._setpoint_adjust_active:
            self._setpoint_adjust_active = False
        elif self._selected_label is not None:
            self.clear_selection()

    # ─── Text screen rendering ────────────────────────────────────────────────

    def tick_text_screen(
        self,
        dt_real_s:     float,
        lines:         list,   # list[tuple[str, tuple[int,int,int]]]
        chars_revealed: int,
    ) -> None:
        """Render one frame of a full-screen terminal text display.

        Args:
            dt_real_s:      Real-time delta in seconds since last frame.
            lines:          List of (text, colour) pairs to render.
            chars_revealed:  Number of characters to reveal (typewriter effect).
                             Pass sum of all line lengths to show everything.
        """
        self._blink_timer += dt_real_s
        if self._blink_timer >= _BLINK_PERIOD:
            self._blink_timer -= _BLINK_PERIOD
        self._blink_on = self._blink_timer < _BLINK_PERIOD * 0.5

        self._native.fill(COL_BACKGROUND)

        sc  = self._scale
        fso = int(TEXT_SCREEN_FONT_SIZE * sc)
        y0  = int(TEXT_SCREEN_TOP_MARGIN  * sc)
        row = int(TEXT_SCREEN_ROW_H       * sc)

        surf_w     = self._native.get_width()
        max_line_w = max(
            (self._font.get_rect(text, size=fso).width for text, _ in lines if text),
            default=0,
        )
        x0 = max(0, (surf_w - max_line_w) // 2)

        total_chars = sum(len(text) for text, _ in lines)
        budget      = chars_revealed
        y           = y0

        for text, colour in lines:
            if budget <= 0:
                break
            visible = text[:budget] if budget < len(text) else text
            budget -= len(text)
            if visible:
                self._font.render_to(self._native, (x0, y), visible, colour, size=fso)
            y += row

        if chars_revealed >= total_chars and self._blink_on:
            hint   = '[PRESS ANY KEY TO CONTINUE]'
            hint_w = self._font.get_rect(hint, size=fso).width
            hint_x = max(0, (self._native.get_width() - hint_w) // 2)
            hint_y = int((NATIVE_HEIGHT - 60) * sc)
            self._font.render_to(self._native, (hint_x, hint_y), hint, COL_150KV, size=fso)

        self._display.blit(self._native, self._letterbox_rect.topleft)
        self._display_dirty = False

    # ─── Splash screen rendering ─────────────────────────────────────────────

    def tick_splash_screen(
        self,
        dt_real_s:      float,
        lines:          list,   # list[tuple[str, colour]]
        chars_revealed: int,
    ) -> None:
        """Render one frame of the splash screen with horizontally and vertically
        centred content.  All non-empty lines are individually centred by pixel
        width.  Typewriter budget logic is identical to tick_text_screen()."""
        self._blink_timer += dt_real_s
        if self._blink_timer >= _BLINK_PERIOD:
            self._blink_timer -= _BLINK_PERIOD
        self._blink_on = self._blink_timer < _BLINK_PERIOD * 0.5

        sc  = self._scale
        fso = int(TEXT_SCREEN_FONT_SIZE * sc)
        row = int(TEXT_SCREEN_ROW_H     * sc)

        surf_w = self._native.get_width()
        surf_h = self._native.get_height()

        total_h = len(lines) * row
        y0      = max(0, (surf_h - total_h) // 2)

        self._native.fill(COL_BACKGROUND)

        total_chars = sum(len(text) for text, _ in lines)
        budget      = chars_revealed
        y           = y0

        for text, colour in lines:
            if budget <= 0:
                break
            visible = text[:budget] if budget < len(text) else text
            budget -= len(text)
            if visible:
                rect = self._font.get_rect(visible, size=fso)
                x    = max(0, (surf_w - rect.width) // 2)
                self._font.render_to(self._native, (x, y), visible, colour, size=fso)
            y += row

        if chars_revealed >= total_chars and self._blink_on:
            hint    = '[  PRESS ANY KEY  ]'
            hint_r  = self._font.get_rect(hint, size=fso)
            hint_x  = max(0, (surf_w - hint_r.width) // 2)
            self._font.render_to(
                self._native, (hint_x, y + row), hint, COL_150KV, size=fso,
            )

        self._display.blit(self._native, self._letterbox_rect.topleft)
        self._display_dirty = False

    # ─── Menu screen rendering ────────────────────────────────────────────────

    def tick_menu_screen(
        self,
        dt_real_s:    float,
        title_lines:  list,
        items:        list,
        selected_idx: int,
        footer_hint:  str = '[UP / DOWN]  Navigate    [ENTER]  Select    [ESC]  Back',
    ) -> None:
        """Render one frame of a cursor-based menu screen.

        Args:
            dt_real_s:   Real-time delta in seconds.
            title_lines: list[tuple[str, colour]] — header block above the items.
            items:       list[tuple[str, bool]] — (label, enabled) pairs.
            selected_idx: Index of the currently highlighted item.
            footer_hint: Navigation hint rendered near the bottom of the screen.
        """
        self._blink_timer += dt_real_s
        if self._blink_timer >= _BLINK_PERIOD:
            self._blink_timer -= _BLINK_PERIOD
        self._blink_on = self._blink_timer < _BLINK_PERIOD * 0.5

        sc    = self._scale
        fsh   = int(TEXT_SCREEN_FONT_SIZE * sc)   # header/separator font size
        fsm   = int(MENU_FONT_SIZE        * sc)   # menu item font size
        y0    = int(TEXT_SCREEN_TOP_MARGIN * sc)
        hrow  = int(TEXT_SCREEN_ROW_H    * sc)
        mrow  = int(MENU_ROW_H           * sc)
        surf_w = self._native.get_width()

        self._native.fill(COL_BACKGROUND)

        # Title block — each line centred horizontally
        y = y0
        for text, colour in title_lines:
            if text:
                rect = self._font.get_rect(text, size=fsh)
                cx   = max(0, (surf_w - rect.width) // 2)
                self._font.render_to(self._native, (cx, y), text, colour, size=fsh)
            y += hrow

        # Menu items — block centred horizontally, items left-aligned within block
        gap            = int(24 * sc)
        cursor_glyph_w = self._font.get_rect('>', size=fsm).width
        real_items     = [item for item in items if item[1] is not None]
        max_label_w    = max(self._font.get_rect(item[0], size=fsm).width for item in real_items)
        block_w        = cursor_glyph_w + gap + max_label_w
        cursor_x       = max(0, (surf_w - block_w) // 2)
        label_x        = cursor_x + gap

        y = int(MENU_TOP_MARGIN * sc)
        for i, item in enumerate(items):
            label, enabled = item[0], item[1]
            if enabled is None:
                y += mrow
                continue
            is_selected = (i == selected_idx)

            if not enabled:
                colour = COL_MENU_DISABLED
                self._font.render_to(self._native, (label_x, y), label, colour, size=fsm)
            elif is_selected:
                self._font.render_to(self._native, (cursor_x, y), '>', COL_MENU_CURSOR, size=fsm)
                self._font.render_to(self._native, (label_x,  y), label, COL_MENU_CURSOR, size=fsm)
            else:
                self._font.render_to(self._native, (label_x, y), label, COL_TEXT_BODY, size=fsm)

            y += mrow

        # Footer hint — centred
        footer_y = int((NATIVE_HEIGHT - 60) * sc)
        footer_w = self._font.get_rect(footer_hint, size=fsh).width
        footer_x = max(0, (surf_w - footer_w) // 2)
        self._font.render_to(self._native, (footer_x, footer_y), footer_hint, COL_TEXT_DIM, size=fsh)

        self._display.blit(self._native, self._letterbox_rect.topleft)
        self._display_dirty = False

    # ─── Shortcut hint bar (Phase 2 / DESIGNER_TEST) ──────────────────────────

    def _build_shortcut_hint(self) -> str:
        """
        One line of context-sensitive keyboard shortcuts for the bottom hint
        bar, based on current selection/input-arm state. Mirrors the
        Phase 2 keybindings documented in CLAUDE.md.
        """
        if self._input_active or self._setpoint_active:
            return '[ENTER]  Confirm    [ESC]  Cancel'
        if self._adjust_active or self._setpoint_adjust_active:
            return ('[UP/DOWN]  Step    [CTRL+UP/DOWN]  Coarse Step    '
                     '[ENTER]  Type Value    [ESC]  Cancel')
        if self._get_selected_unit() is not None:
            return ('[W]  Arm MW    [Q]  Arm MVAr    [S/X]  Start/Stop    '
                     '[M]  Auto    [TAB]  Cycle    [ESC]  Deselect')
        if self._get_selected_line() is not None:
            return '[T/C]  Trip/Close    [TAB]  Cycle    [ESC]  Deselect'
        if self._get_selected_bus() is not None:
            return ('[H]  Shed Load    [SHIFT+H]  Restore    [,/.]  SVC    '
                     '[TAB]  Cycle    [ESC]  Deselect')
        return ('[TAB]  Select    [P]  Pause    [F12]  Speed    '
                '[CTRL+A]  AGC    [A]  Ack    [SHIFT+A]  Ack All')

    def _draw_hint_bar(self) -> None:
        """Redraw the shortcut hint bar only when its text has changed."""
        hint_text = self._build_shortcut_hint()
        if hint_text == self._hint_bar_text:
            return
        self._hint_bar_text = hint_text
        sc  = self._scale
        pad = int(6 * sc)
        self._hint_bar_surf.fill(COL_STRIP_BG)
        self._font.render_to(
            self._hint_bar_surf, (pad, max(1, int(3 * sc))),
            hint_text, COL_TEXT_DIM, size=int(FONT_SIZE_HINT * sc),
        )

    # ─── Per-frame entry point ────────────────────────────────────────────────

    def tick(
        self,
        dt_real_s:  float,
        state=None,
        speed_mult: float = 1.0,
    ) -> None:
        """
        Render one frame.

        Args:
            dt_real_s:  Real-time delta in seconds since last frame.
            state:      Current SimulationState, or None for static view.
            speed_mult: Current simulation speed multiplier.
        """
        if state is not None:
            self._sound.update(state.active_alarms)

        # Track whether the blink phase changed this frame — drives display dirty.
        prev_blink_on    = self._blink_on
        prev_blink_2hz   = self._blink_2hz_on

        # Update blink phases
        self._blink_timer += dt_real_s
        if self._blink_timer >= _BLINK_PERIOD:
            self._blink_timer -= _BLINK_PERIOD
        self._blink_on = self._blink_timer < _BLINK_PERIOD * 0.5

        self._blink_2hz_timer += dt_real_s
        if self._blink_2hz_timer >= _BLINK_2HZ_PERIOD:
            self._blink_2hz_timer -= _BLINK_2HZ_PERIOD
        self._blink_2hz_on = self._blink_2hz_timer < _BLINK_2HZ_PERIOD * 0.5

        blink_changed = (self._blink_on != prev_blink_on
                         or self._blink_2hz_on != prev_blink_2hz)

        self._frame_time = dt_real_s
        self._fps = 1.0 / dt_real_s if dt_real_s > 0.0 else 0.0
        self._fps_smooth = 0.9 * self._fps_smooth + 0.1 * self._fps

        # native_changed tracks whether anything was drawn to _native this frame.
        native_changed = False

        _perf = _sim_const.DEBUG_PERF
        _t0 = time.perf_counter() if _perf else 0.0

        # ── Draw canvas ───────────────────────────────────────────────────────
        prev_canvas_key = self._canvas._canvas_key
        self._canvas.draw(
            self._canvas_surf,
            state=state,
            blink_on=self._blink_on,
            selected_label=self._selected_label,
            font_scale=self._scale,
        )
        if self._canvas._canvas_key != prev_canvas_key:
            native_changed = True

        if _perf:
            _t1 = time.perf_counter()
            self._perf_last_ms['canvas'] = (_t1 - _t0) * 1000.0
            _t0 = _t1

        # ── Line load triangles (drawn on top of canvas) ──────────────────────
        if state is not None:
            draw_load_triangles(self._canvas_surf, state,
                                self._canvas._lines, self._canvas._line_waypoints)
            native_changed = True

        # ── Overload trip countdowns (live, uncached — see draw_overload_countdowns) ──
        if state is not None and state.overload_timers:
            self._canvas.draw_overload_countdowns(self._canvas_surf, state, font_scale=self._scale)
            native_changed = True

        # ── Grid display zone framing — a green line along the bottom edge
        # of the canvas (the boundary with the instrument strip below), so
        # the grid schematic reads as a clearly bounded zone. The top edge
        # is framed by the topbar's own bottom border instead (drawn flush
        # under its content in draw_topbar_panel(), not at the topbar/
        # canvas boundary — see Session 106). Drawn every frame since the
        # canvas itself is blitted fresh every frame regardless of its own
        # redraw-to-cache state. ──
        canvas_w, canvas_h = self._canvas_surf.get_size()
        pygame.draw.line(self._canvas_surf, COL_PANEL_BORDER,
                         (0, canvas_h - 1), (canvas_w, canvas_h - 1), 1)
        native_changed = True

        if _perf:
            _t1 = time.perf_counter()
            self._perf_last_ms['triangles'] = (_t1 - _t0) * 1000.0
            _t0 = _t1

        # ── Draw instrument strip panels (cached — only redrawn when data changes) ─

        # Sample frequency/load-variation history once per rendered frame
        # (display-only concern — simulation.py holds no history of its own,
        # see FREQ_HISTORY_WINDOW_S). Load variation (MW/min) is derived from
        # consecutive load samples using sim-time elapsed, not real-time.
        if state:
            self._freq_history.append(state.frequency_hz)
            if self._prev_load_mw is not None:
                dt_sim_min = (state.sim_hour - self._prev_load_sim_hour) * 60.0
                if dt_sim_min > 0.0:
                    rate = (state.total_load_mw - self._prev_load_mw) / dt_sim_min
                    self._load_rate_history.append(rate)
            self._prev_load_mw = state.total_load_mw
            self._prev_load_sim_hour = state.sim_hour

        # Dirty keys: tuples of values visible in each panel, rounded to display precision
        freq_key = (
            round(state.frequency_hz, 2) if state else None,
            state.frequency_trend        if state else None,
            len(self._freq_history),
            round(self._freq_history[0], 2) if self._freq_history else None,
        )
        topbar_key = (
            round(state.total_generation_mw)  if state else None,
            round(state.total_load_mw)        if state else None,
            round(state.net_imbalance_mw)     if state else None,
            round(state.spinning_reserve_mw)  if state else None,
            round(state.system_inertia_h, 1)  if state else None,
            round(state.losses_mw)            if state else None,
            round(self._load_rate_history[-1], 2) if self._load_rate_history else None,
            int(state.sim_hour * 60)          if state else None,
            speed_mult,
        )
        dispatch_key = (
            ''.join(v[:1] for _, v in sorted(state.unit_states.items())) if state else None,
            round(sum(state.unit_outputs_mw.values()))                    if state else None,
            round(sum(state.unit_start_progress.values()) * 100)          if state else None,
            state.unit_agc_enabled                                        if state else None,
        )
        forecast_key = (
            len(state.demand_forecast_mw) if state else 0,
            int(state.sim_hour * 2)       if state else 0,
        )
        genmix_key = (
            tuple(round(v) for _, v in sorted(state.gen_mix_mw.items())) if state else None,
        )
        _has_unacked = (
            any(not a.acknowledged for a in state.active_alarms) if state else False
        )
        # Quantise blink to phase index (0 or 1, changes at 2Hz) so the dirty key
        # changes only 2×/s instead of every frame.
        _blink_phase = (
            int(self._blink_2hz_timer / (_BLINK_2HZ_PERIOD * 0.5)) if _has_unacked else 0
        )
        alarm_key = (
            len(state.active_alarms)                               if state else 0,
            sum(1 for a in state.active_alarms if a.acknowledged)  if state else 0,
            self._alarm_scroll,
            _blink_phase,
        )

        _fs = self._scale  # font/layout scale passed to all panel and context draw calls
        panel_changed = False

        if freq_key != self._panel_keys['freq']:
            draw_frequency_panel(
                self._panel_cache['freq'], self._font, self._blink_on, state,
                freq_history=self._freq_history, font_scale=_fs)
            self._panel_keys['freq'] = freq_key
            panel_changed = True

        if topbar_key != self._panel_keys['topbar']:
            draw_topbar_panel(self._panel_cache['topbar'], self._font, state,
                              load_rate_history=self._load_rate_history,
                              speed_mult=speed_mult, font_scale=_fs)
            self._panel_keys['topbar'] = topbar_key
            self._topbar_surf.blit(self._panel_cache['topbar'], (0, 0))
            native_changed = True

        if dispatch_key != self._panel_keys['dispatch']:
            draw_dispatch_panel(
                self._panel_cache['dispatch'], self._font, self._blink_on,
                state, self._grid, font_scale=_fs)
            self._panel_keys['dispatch'] = dispatch_key
            panel_changed = True

        if forecast_key != self._panel_keys['forecast']:
            draw_forecast_panel(self._panel_cache['forecast'], self._font, state,
                                font_scale=_fs)
            self._panel_keys['forecast'] = forecast_key
            panel_changed = True

        if genmix_key != self._panel_keys['genmix']:
            draw_genmix_panel(self._panel_cache['genmix'], self._font, state,
                              font_scale=_fs)
            self._panel_keys['genmix'] = genmix_key
            panel_changed = True

        if alarm_key != self._panel_keys['alarm']:
            draw_alarm_panel(
                self._panel_cache['alarm'], self._font, self._blink_2hz_on,
                state, self._alarm_scroll, font_scale=_fs)
            self._panel_keys['alarm'] = alarm_key
            panel_changed = True

        if panel_changed:
            # Blit updated panel surfaces to the strip (scaled X positions)
            _sc = self._scale
            self._strip_surf.blit(self._panel_cache['freq'],     (int(PANEL_FREQ_X     * _sc), 0))
            self._strip_surf.blit(self._panel_cache['dispatch'], (int(PANEL_DISPATCH_X * _sc), 0))
            self._strip_surf.blit(self._panel_cache['forecast'], (int(PANEL_FORECAST_X * _sc), 0))
            self._strip_surf.blit(self._panel_cache['genmix'],   (int(PANEL_GENMIX_X   * _sc), 0))
            self._strip_surf.blit(self._panel_cache['alarm'],    (int(PANEL_ALARM_X    * _sc), 0))
            # Grid display zone framing: the strip's own bottom edge (its top
            # edge is the canvas's own bottom border, drawn every frame as
            # part of canvas compositing above) — completes the green frame
            # around the grid schematic/instrument-strip block as a whole.
            strip_w, strip_h = self._strip_surf.get_size()
            pygame.draw.line(self._strip_surf, COL_PANEL_BORDER,
                             (0, strip_h - 1), (strip_w, strip_h - 1), 1)
            native_changed = True

        prev_hint_text = self._hint_bar_text
        self._draw_hint_bar()
        if self._hint_bar_text != prev_hint_text:
            native_changed = True

        if _perf:
            _t1 = time.perf_counter()
            self._perf_last_ms['panels'] = (_t1 - _t0) * 1000.0
            _t0 = _t1

        # ── Unit context overlay ──────────────────────────────────────────────
        selected_unit = self._get_selected_unit()
        if selected_unit is not None and state is not None:
            draw_unit_context(
                self._canvas_surf, self._font,
                unit=selected_unit,
                unit_state=state.unit_states.get(selected_unit.label, 'OFFLINE'),
                output_mw=state.unit_outputs_mw.get(selected_unit.label, 0.0),
                target_mw=state.unit_targets_mw.get(selected_unit.label, 0.0),
                input_buffer=self._input_buffer,
                input_active=self._input_active,
                blink_on=self._blink_on,
                cmd_active=self._cmd_active,
                font_scale=_fs,
                is_maintenance=selected_unit.label in state.unit_maintenance,
                q_target_mvar=state.unit_q_target_mvar.get(selected_unit.label),
                q_mvar=state.unit_q_injections_mvar.get(selected_unit.label),
                q_reserve_mvar=state.unit_q_reserve_mvar.get(selected_unit.label),
                setpoint_buffer=self._setpoint_buffer,
                setpoint_active=self._setpoint_active,
                dispatch_mode=(
                    state.unit_dispatch_modes.get(selected_unit.label)
                    if selected_unit.label in state.unit_has_schedule else None
                ),
                mode_cmd_active=self._mode_cmd_active,
                adjust_active=self._adjust_active,
                setpoint_adjust_active=self._setpoint_adjust_active,
            )
            native_changed = True
        elif self._selected_label is not None:
            selected_bus = self._canvas._bus_map.get(self._selected_label)
            if selected_bus is not None:
                draw_bus_context(self._canvas_surf, self._font,
                                 bus=selected_bus, state=state, font_scale=_fs,
                                 svc_cmd_active=self._svc_cmd_active)
                native_changed = True
            else:
                selected_line = next(
                    (l for l in self._canvas._lines if l.label == self._selected_label),
                    None,
                )
                if selected_line is not None:
                    draw_line_context(self._canvas_surf, self._font,
                                      line=selected_line, state=state,
                                      cmd_active=self._line_cmd_active,
                                      font_scale=_fs)
                    native_changed = True

        if _perf:
            _t1 = time.perf_counter()
            self._perf_last_ms['context'] = (_t1 - _t0) * 1000.0
            _t0 = _t1

        # ── Editor overlay ────────────────────────────────────────────────────
        if _sim_const.EDITOR_MODE:
            self._editor.draw_overlay(self._canvas_surf, self._font)
            native_changed = True

        # ── Always-on FPS counter (top-right of canvas) ──────────────────────
        if not _sim_const.DEBUG_DISPLAY:
            fps_str = f'{self._fps_smooth:.0f}'
            fso = int(FONT_SIZE_OVERLAY * self._scale)
            tw, _ = self._font.get_rect(fps_str, size=fso)[2:4]
            self._font.render_to(
                self._canvas_surf,
                (self._canvas_surf.get_width() - tw - int(6 * self._scale),
                 int(4 * self._scale)),
                fps_str, COL_FPS_TEXT, size=fso,
            )
            native_changed = True

        # ── Debug overlay ──────────────────────────────────────────────────────
        if _sim_const.DEBUG_DISPLAY:
            self._draw_debug()
            native_changed = True

        # ── Conditional blit to display ───────────────────────────────────────
        # Bars are already painted on the display (done once at init).
        # Only blit the native surface when content has actually changed.
        if native_changed or self._display_dirty:
            self._display.blit(self._native, self._letterbox_rect.topleft)
            self._display_dirty = False

        if _perf:
            _t1 = time.perf_counter()
            self._perf_last_ms['blit'] = (_t1 - _t0) * 1000.0
            self._perf_last_ms['frame_total'] = dt_real_s * 1000.0
            self._perf_tick_log(dt_real_s)

    # ─── Letterbox helpers ────────────────────────────────────────────────────

    # ─── Debug overlay ────────────────────────────────────────────────────────

    def on_mouse_move(self, pos: tuple[int, int]) -> None:
        """Call with native-space mouse position each motion event."""
        self._mouse_pos = pos
        if _sim_const.EDITOR_MODE:
            self._editor.on_mouse_move(self._to_canvas_local(pos))

    def on_mouse_down(self, pos: tuple[int, int]) -> None:
        """Call with native-space position on mouse button down."""
        if _sim_const.EDITOR_MODE:
            self._editor.on_mouse_down(self._to_canvas_local(pos))

    def on_mouse_up(self, pos: tuple[int, int]) -> None:
        """Call with native-space position on mouse button release."""
        if _sim_const.EDITOR_MODE:
            self._editor.on_mouse_up(self._to_canvas_local(pos))
            self._editor.set_canvas(self._canvas)

    def save_layout(self) -> None:
        """Save current layout overrides to layout.json."""
        self._editor.save()

    def editor_key_r(self) -> None:
        """Rotate label anchor for the hovered element in edit mode."""
        self._editor.on_key_r()

    def rebuild_canvas(self) -> None:
        """Reconstruct GridCanvas after layout changes."""
        self._canvas.rebuild()
        self._editor.set_canvas(self._canvas)

    def _to_canvas_local(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Translate a native-space position into the canvas subsurface's own
        local coordinate space (canvas top-left sits scaled_topbar_h rows
        below native (0,0))."""
        return (pos[0], pos[1] - self._scaled_topbar_h)

    def on_click(self, pos: tuple[int, int]) -> None:
        """Hit-test buses and unit squares; update selection. Canvas clicks only."""
        nx, ny = self._to_canvas_local(pos)
        if ny < 0 or ny >= self._scaled_canvas_h:
            return

        best_label: str | None = None
        best_dist:  float       = float('inf')

        # Units first — drawn on top of buses
        for station_label, positions in self._canvas._station_pos.items():
            units = self._canvas._station_units.get(station_label, [])
            for unit, (cx, cy) in zip(units, positions):
                dist = max(abs(nx - cx), abs(ny - cy))
                if dist <= _HIT_RADIUS and dist < best_dist:
                    best_dist  = dist
                    best_label = unit.label

        # Buses
        bus_pos = self._canvas._bus_pos
        for bus in self._canvas._buses:
            bx, by = bus_pos[bus.label]
            dist = max(abs(nx - bx), abs(ny - by))
            if dist <= _HIT_RADIUS and dist < best_dist:
                best_dist  = dist
                best_label = bus.label

        # Lines — only if no bus/unit was hit within its own radius
        if best_label is None:
            line_waypoints = self._canvas._line_waypoints
            for line in self._canvas._lines:
                waypoints = line_waypoints.get(line.label)
                if waypoints is None:
                    continue
                dist = min(
                    point_segment_dist(nx, ny, sx1, sy1, sx2, sy2)
                    for (sx1, sy1), (sx2, sy2) in zip(waypoints, waypoints[1:])
                )
                if dist <= _LINE_HIT_PX and dist < best_dist:
                    best_dist  = dist
                    best_label = line.label

        # Toggle deselect when clicking the same element
        self._selected_label = None if best_label == self._selected_label else best_label

        # Selection change always resets input state
        self._input_buffer = ''
        self._input_active = False

        if _sim_const.DEBUG_DISPLAY:
            self._click_pos   = pos
            self._click_timer = 3.0
            suffix = f'  →  {self._selected_label}' if self._selected_label else ''
            print(f'[DEBUG CLICK] x={nx}, y={ny}{suffix}')

    def _perf_tick_log(self, dt_real_s: float) -> None:
        """
        Accumulate this frame's section timings and flush a summary line to
        the perf logger roughly every PERF_LOG_INTERVAL_S. Only called when
        DEBUG_PERF is True (see tick()).
        """
        for key, ms in self._perf_last_ms.items():
            self._perf_accum_ms[key] = self._perf_accum_ms.get(key, 0.0) + ms
        self._perf_accum_frames += 1

        self._perf_log_timer += dt_real_s
        if self._perf_log_timer < PERF_LOG_INTERVAL_S or self._perf_logger is None:
            return

        n = max(1, self._perf_accum_frames)
        avg_fps = n / self._perf_log_timer if self._perf_log_timer > 0.0 else 0.0
        parts = [f'fps={avg_fps:.1f}']
        for key in ('frame_total', 'canvas', 'triangles', 'panels', 'context', 'blit'):
            total = self._perf_accum_ms.get(key)
            if total is not None:
                parts.append(f'{key}={total / n:.2f}ms')
        self._perf_logger.debug('  '.join(parts))

        self._perf_log_timer     = 0.0
        self._perf_accum_frames  = 0
        self._perf_accum_ms.clear()

    def _draw_debug(self) -> None:
        font  = self._font
        sc    = self._scale
        so    = int(FONT_SIZE_OVERLAY * sc)
        nw, nh = self._native.get_size()
        p4    = int(4  * sc)
        p8    = int(8  * sc)
        p18   = int(18 * sc)
        p32   = int(32 * sc)

        # Faint coordinate grid — built once at current scaled size, blitted every frame
        if self._debug_grid_surf is None:
            self._debug_grid_surf = pygame.Surface((nw, nh), pygame.SRCALPHA)
            self._debug_grid_surf.fill((0, 0, 0, 0))
            step = int(120 * sc)
            for x in range(0, nw, max(1, step)):
                pygame.draw.line(self._debug_grid_surf, COL_DEBUG_GRID, (x, 0), (x, nh), 1)
            for y in range(0, nh, max(1, step)):
                pygame.draw.line(self._debug_grid_surf, COL_DEBUG_GRID, (0, y), (nw, y), 1)
        self._native.blit(self._debug_grid_surf, (0, 0))

        # Mouse position — top-left (shown in logical 1920×1080 units)
        mx = int(self._mouse_pos[0] / sc)
        my = int(self._mouse_pos[1] / sc)
        font.render_to(self._native, (p4, p4),
                       f'mouse {mx},{my}', COL_DEBUG_TEXT, size=so)

        # FPS / frame time — top-right
        fps_str = f'{self._fps:.0f}fps  {self._frame_time*1000:.1f}ms'
        tw, _ = font.get_rect(fps_str, size=so)[2:4]
        font.render_to(self._native, (nw - tw - p8, p4),
                       fps_str, COL_DEBUG_TEXT, size=so)

        # AGC status — top-right, second line
        agc_str = f'AGC {"ON" if _sim_const.AGC_ENABLED else "OFF"}'
        agc_col = COL_DEBUG_TEXT if _sim_const.AGC_ENABLED else COL_TEXT_DIM
        agc_w, _ = font.get_rect(agc_str, size=so)[2:4]
        font.render_to(self._native, (nw - agc_w - p8, p18),
                       agc_str, agc_col, size=so)

        # Resolution / scale — top-right, third line
        ww, wh = pygame.display.get_window_size()
        res_str = f'{ww}\xd7{wh}  {NATIVE_WIDTH}\xd7{NATIVE_HEIGHT}  {sc:.2f}\xd7'
        res_w, _ = font.get_rect(res_str, size=so)[2:4]
        font.render_to(self._native, (nw - res_w - p8, p32),
                       res_str, COL_DEBUG_TEXT, size=so)

        # Perf section timings — top-right, fourth line (only when DEBUG_PERF is on)
        if _sim_const.DEBUG_PERF and self._perf_last_ms:
            order = ('frame_total', 'canvas', 'triangles', 'panels', 'context', 'blit')
            labels = {'frame_total': 'frame', 'canvas': 'cnv', 'triangles': 'tri',
                      'panels': 'pnl', 'context': 'ctx', 'blit': 'blit'}
            perf_str = '  '.join(
                f'{labels[k]} {self._perf_last_ms[k]:.1f}'
                for k in order if k in self._perf_last_ms
            )
            perf_w, _ = font.get_rect(perf_str, size=so)[2:4]
            font.render_to(self._native, (nw - perf_w - p8, p32 + p18),
                           perf_str, COL_DEBUG_TEXT, size=so)

        # Click position — shown for 3 seconds (in logical units)
        if self._click_pos is not None:
            self._click_timer -= self._frame_time
            if self._click_timer > 0.0:
                cx = int(self._click_pos[0] / sc)
                cy = int(self._click_pos[1] / sc)
                from display.palette import COL_DEBUG_CLICK
                font.render_to(self._native, (p4, p18),
                               f'click {cx},{cy}', COL_DEBUG_CLICK, size=so)
            else:
                self._click_pos = None
