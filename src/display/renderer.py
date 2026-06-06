"""
src/display/renderer.py

Renderer: owns the native 1920×1080 surface, drives the render loop,
and composites all display layers each frame.

Native resolution is always 1920×1080 regardless of monitor size.
At the end of each frame the native surface is scaled to the display surface.

Layers (bottom to top):
  1. Canvas background + grid schematic (GridCanvas)
  2. Instrument strip — four panels (frequency, power, dispatch, alarms)
  3. Debug overlay                 (when DEBUG_DISPLAY = True)

Usage:
    renderer = Renderer(display_surf, shift=1)
    # game loop:
    renderer.tick(dt_real_s, state=None)
    pygame.display.flip()
"""

from __future__ import annotations

import pygame
import pygame.freetype

from display.canvas import GridCanvas
from display.context import draw_unit_context, draw_bus_context, draw_line_context
from display.editor import GridEditor
from display.animation import FlowAnimator
from display.panels import (
    draw_frequency_panel, draw_power_panel,
    draw_dispatch_panel, draw_alarm_panel,
    draw_genmix_panel, draw_forecast_panel,
)
from display.palette import (
    COL_BACKGROUND, COL_STRIP_BG, COL_DEBUG_TEXT, COL_DEBUG_GRID, COL_TEXT_DIM,
    COL_FPS_TEXT, COL_150KV,
    COL_TEXT_BODY, COL_TEXT_SCREEN_HDR, COL_MENU_CURSOR, COL_MENU_DISABLED,
)
import simulation.constants as _sim_const
from simulation.constants import (
    CANVAS_HEIGHT, STRIP_HEIGHT,
    NATIVE_WIDTH, NATIVE_HEIGHT,
    FONT_SIZE_PANEL, FONT_SIZE_OVERLAY,
    PANEL_FREQ_X, PANEL_FREQ_W,
    PANEL_POWER_X, PANEL_POWER_W,
    PANEL_DISPATCH_X, PANEL_DISPATCH_W,
    PANEL_FORECAST_X, PANEL_FORECAST_W,
    PANEL_GENMIX_X, PANEL_GENMIX_W,
    PANEL_ALARM_X, PANEL_ALARM_W,
    FLOW_ANIMATION,
    TEXT_SCREEN_FONT_SIZE, TEXT_SCREEN_LEFT_MARGIN, TEXT_SCREEN_TOP_MARGIN, TEXT_SCREEN_ROW_H,
    MENU_FONT_SIZE, MENU_ROW_H, MENU_LEFT_MARGIN, MENU_TOP_MARGIN,
)
from utils.helpers import resource_path
from data.profiles import SHIFT_SPECS


_BLINK_2HZ_PERIOD = 0.5   # seconds per 2Hz blink cycle (alarm panel)
_BLINK_PERIOD     = 1.0   # seconds per blink cycle (canvas, dispatch panel)
_HIT_RADIUS       = 10    # px — Chebyshev hit radius for bus/unit selection
_LINE_HIT_PX      = 8     # px — max perpendicular distance for line selection


def _point_segment_dist(px: int, py: int,
                        x1: int, y1: int, x2: int, y2: int) -> float:
    """Return the minimum distance from point (px,py) to segment (x1,y1)-(x2,y2)."""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    nx = x1 + t * dx
    ny = y1 + t * dy
    return ((px - nx) ** 2 + (py - ny) ** 2) ** 0.5


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
        scaled_canvas_h      = int(CANVAS_HEIGHT * self._scale)
        scaled_strip_h       = scaled_h - scaled_canvas_h
        self._scaled_canvas_h = scaled_canvas_h
        offset_x             = (disp_w - scaled_w) // 2
        offset_y             = (disp_h - scaled_h) // 2
        self._letterbox_rect = pygame.Rect(offset_x, offset_y, scaled_w, scaled_h)

        # Paint letterbox bars black once — they never change so no per-frame fill needed.
        self._display.fill((0, 0, 0))

        # Native surface converted to display pixel format for hardware-accelerated blits.
        self._native        = pygame.Surface((scaled_w, scaled_h)).convert()
        self._display_dirty = True   # force first-frame blit to display

        # Canvas region: top scaled_canvas_h rows
        self._canvas_surf = self._native.subsurface(
            pygame.Rect(0, 0, scaled_w, scaled_canvas_h)
        )
        # Strip region: bottom scaled_strip_h rows
        self._strip_surf = self._native.subsurface(
            pygame.Rect(0, scaled_canvas_h, scaled_w, scaled_strip_h)
        )

        font_path = resource_path('assets/fonts/JetBrainsMono-Regular.ttf')
        if font_path.exists():
            self._font = pygame.freetype.Font(str(font_path), 11)
        else:
            self._font = pygame.freetype.SysFont('monospace', 11)
        self._font.antialiased = False   # hard pixel edges; NN-equivalent at integer scale

        self._canvas = GridCanvas(shift=shift, font=self._font, scale=self._scale)
        self._editor = GridEditor(self._canvas, scale=self._scale)
        _spec = SHIFT_SPECS.get(shift)
        self._shift_title: str = (
            f'SHIFT {shift}  —  {_spec.difficulty_label.upper()}'
            if _spec else f'SHIFT {shift}'
        )
        self._flow   = FlowAnimator()

        # Grid reference for dispatch panel (set by main via set_grid)
        self._grid = None

        self._blink_timer: float = 0.0
        self._blink_on:    bool  = True

        # 2Hz blink for alarm panel
        self._blink_2hz_timer: float = 0.0
        self._blink_2hz_on:    bool  = True

        # Panel scroll offsets
        self._dispatch_scroll: int = 0
        self._alarm_scroll:    int = 0

        # Panel surface cache: converted to display pixel format for fast blits.
        _sc = self._scale
        self._panel_cache: dict[str, pygame.Surface] = {
            'freq':     pygame.Surface((int(PANEL_FREQ_W     * _sc), scaled_strip_h)).convert(),
            'power':    pygame.Surface((int(PANEL_POWER_W    * _sc), scaled_strip_h)).convert(),
            'dispatch': pygame.Surface((int(PANEL_DISPATCH_W * _sc), scaled_strip_h)).convert(),
            'forecast': pygame.Surface((int(PANEL_FORECAST_W * _sc), scaled_strip_h)).convert(),
            'genmix':   pygame.Surface((int(PANEL_GENMIX_W   * _sc), scaled_strip_h)).convert(),
            'alarm':    pygame.Surface((int(PANEL_ALARM_W    * _sc), scaled_strip_h)).convert(),
        }
        # Sentinel objects force a full draw on the first frame
        self._panel_keys: dict[str, object] = {k: object() for k in self._panel_cache}

        # Selection state
        self._selected_label: str | None = None

        # Unit dispatch input state
        self._input_buffer: str  = ''
        self._input_active: bool = False

        # START/STOP button keyboard focus
        self._cmd_active: bool = False

        # TRIP/CLOSE button keyboard focus
        self._line_cmd_active: bool = False

        # Debug state
        self._mouse_pos:       tuple[int, int] = (0, 0)
        self._click_pos:       tuple[int, int] | None = None
        self._click_timer:     float = 0.0
        self._frame_time:      float = 0.0
        self._fps:             float = 0.0
        self._fps_smooth:      float = 0.0
        self._debug_grid_surf: pygame.Surface | None = None  # cached on first debug draw

    # ─── Per-frame entry point ────────────────────────────────────────────────

    def set_grid(self, grid) -> None:
        """Store the Grid reference used by the dispatch panel."""
        self._grid = grid

    def on_scroll(self, delta: int, pos: tuple[int, int]) -> None:
        """Route mouse wheel to dispatch or alarm panel based on native-space position."""
        if pos[1] < self._scaled_canvas_h:
            return
        nx = pos[0]
        if PANEL_DISPATCH_X <= nx < PANEL_DISPATCH_X + PANEL_DISPATCH_W:
            self._dispatch_scroll = max(0, self._dispatch_scroll - delta)
        elif PANEL_ALARM_X <= nx < PANEL_ALARM_X + PANEL_ALARM_W:
            self._alarm_scroll = max(0, self._alarm_scroll - delta)

    def clear_selection(self) -> None:
        """Clear the currently selected element and reset input state."""
        self._selected_label  = None
        self._input_buffer    = ''
        self._input_active    = False
        self._cmd_active      = False
        self._line_cmd_active = False

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
        if sim.get_state().unit_states.get(unit.label) != 'OFFLINE':
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

    def on_escape(self) -> None:
        """
        Cancel input if active; clear cmd focus if active; otherwise deselect.
        No-op when nothing is selected — main.py handles global quit.
        """
        if self._input_active:
            self._input_buffer = ''
            self._input_active = False
        elif self._cmd_active:
            self._cmd_active = False
        elif self._line_cmd_active:
            self._line_cmd_active = False
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
        x0  = int(TEXT_SCREEN_LEFT_MARGIN * sc)
        y0  = int(TEXT_SCREEN_TOP_MARGIN  * sc)
        row = int(TEXT_SCREEN_ROW_H       * sc)

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
            self._font.render_to(
                self._native,
                (x0, y + row),
                '[PRESS ANY KEY TO CONTINUE]',
                COL_150KV,
                size=fso,
            )

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
        x0    = int(MENU_LEFT_MARGIN      * sc)
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

        # Menu items, starting below title
        y = int(MENU_TOP_MARGIN * sc)
        cursor_x = x0
        label_x  = x0 + int(24 * sc)   # indent label past the cursor glyph

        for i, item in enumerate(items):
            label, enabled = item[0], item[1]
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

        # Footer hint near bottom
        footer_y = int((NATIVE_HEIGHT - 60) * sc)
        self._font.render_to(
            self._native,
            (x0, footer_y),
            footer_hint,
            COL_TEXT_DIM,
            size=fsh,
        )

        self._display.blit(self._native, self._letterbox_rect.topleft)
        self._display_dirty = False

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
            speed_mult: Current simulation speed multiplier (for flow markers).
        """
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

        # ── Flow markers (drawn on top of canvas) ─────────────────────────────
        if state is not None and FLOW_ANIMATION:
            self._flow.update(dt_real_s, speed_mult)
            self._flow.draw(self._canvas_surf, state,
                            self._canvas._bus_map, self._canvas._lines)
            native_changed = True

        # ── Draw instrument strip panels (cached — only redrawn when data changes) ─
        paused = (speed_mult == 0.0)

        # Dirty keys: tuples of values visible in each panel, rounded to display precision
        freq_key = (
            round(state.frequency_hz, 2) if state else None,
            state.frequency_trend        if state else None,
            int(state.sim_hour * 60)     if state else None,
            paused,
        )
        power_key = (
            round(state.total_generation_mw)  if state else None,
            round(state.total_load_mw)        if state else None,
            round(state.net_imbalance_mw)     if state else None,
            round(state.spinning_reserve_mw)  if state else None,
            round(state.system_inertia_h, 1)  if state else None,
            round(state.losses_mw)            if state else None,
        )
        dispatch_key = (
            ''.join(v[:1] for _, v in sorted(state.unit_states.items())) if state else None,
            round(sum(state.unit_outputs_mw.values()))                    if state else None,
            round(sum(state.unit_start_progress.values()) * 100)          if state else None,
            self._dispatch_scroll,
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
                paused=paused, font_scale=_fs)
            self._panel_keys['freq'] = freq_key
            panel_changed = True

        if power_key != self._panel_keys['power']:
            draw_power_panel(self._panel_cache['power'], self._font, state,
                             font_scale=_fs)
            self._panel_keys['power'] = power_key
            panel_changed = True

        if dispatch_key != self._panel_keys['dispatch']:
            draw_dispatch_panel(
                self._panel_cache['dispatch'], self._font, self._blink_on,
                state, self._grid, self._dispatch_scroll, font_scale=_fs)
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
            self._strip_surf.blit(self._panel_cache['power'],    (int(PANEL_POWER_X    * _sc), 0))
            self._strip_surf.blit(self._panel_cache['dispatch'], (int(PANEL_DISPATCH_X * _sc), 0))
            self._strip_surf.blit(self._panel_cache['forecast'], (int(PANEL_FORECAST_X * _sc), 0))
            self._strip_surf.blit(self._panel_cache['genmix'],   (int(PANEL_GENMIX_X   * _sc), 0))
            self._strip_surf.blit(self._panel_cache['alarm'],    (int(PANEL_ALARM_X    * _sc), 0))
            native_changed = True

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
            )
            native_changed = True
        elif self._selected_label is not None:
            selected_bus = self._canvas._bus_map.get(self._selected_label)
            if selected_bus is not None:
                draw_bus_context(self._canvas_surf, self._font,
                                 bus=selected_bus, state=state, font_scale=_fs)
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

        # ── Shift title (top-centre of canvas) ───────────────────────────────
        fso = int(FONT_SIZE_OVERLAY * self._scale)
        tw, _ = self._font.get_rect(self._shift_title, size=fso)[2:4]
        cx = (self._canvas_surf.get_width() - tw) // 2
        self._font.render_to(
            self._canvas_surf,
            (cx, int(6 * self._scale)),
            self._shift_title, COL_TEXT_DIM, size=fso,
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

    # ─── Letterbox helpers ────────────────────────────────────────────────────

    # ─── Debug overlay ────────────────────────────────────────────────────────

    def on_mouse_move(self, pos: tuple[int, int]) -> None:
        """Call with native-space mouse position each motion event."""
        self._mouse_pos = pos
        if _sim_const.EDITOR_MODE:
            self._editor.on_mouse_move(pos)

    def on_mouse_down(self, pos: tuple[int, int]) -> None:
        """Call with native-space position on mouse button down."""
        if _sim_const.EDITOR_MODE:
            self._editor.on_mouse_down(pos)

    def on_mouse_up(self, pos: tuple[int, int]) -> None:
        """Call with native-space position on mouse button release."""
        if _sim_const.EDITOR_MODE:
            self._editor.on_mouse_up(pos)
            self._editor.set_canvas(self._canvas)

    def save_layout(self) -> None:
        """Save current layout overrides to layout.json."""
        self._editor.save()

    def rebuild_canvas(self) -> None:
        """Reconstruct GridCanvas after layout changes."""
        self._canvas.rebuild()
        self._editor.set_canvas(self._canvas)

    def on_click(self, pos: tuple[int, int]) -> None:
        """Hit-test buses and unit squares; update selection. Canvas clicks only."""
        nx, ny = pos
        if ny >= self._scaled_canvas_h:
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
            for line in self._canvas._lines:
                if line.from_bus not in bus_pos or line.to_bus not in bus_pos:
                    continue
                fx, fy = bus_pos[line.from_bus]
                tx, ty = bus_pos[line.to_bus]
                bend_x, bend_y = fx, ty  # vertical-first routing
                d1 = _point_segment_dist(nx, ny, fx, fy, bend_x, bend_y)
                d2 = _point_segment_dist(nx, ny, bend_x, bend_y, tx, ty)
                dist = min(d1, d2)
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
