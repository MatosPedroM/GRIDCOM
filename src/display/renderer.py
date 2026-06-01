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
)
import simulation.constants as _sim_const
from simulation.constants import (
    CANVAS_HEIGHT, STRIP_HEIGHT,
    NATIVE_WIDTH, NATIVE_HEIGHT,
    LETTERBOX_COLOUR,
    FONT_SIZE_PANEL, FONT_SIZE_OVERLAY,
    PANEL_FREQ_X, PANEL_FREQ_W,
    PANEL_POWER_X, PANEL_POWER_W,
    PANEL_DISPATCH_X, PANEL_DISPATCH_W,
    PANEL_FORECAST_X, PANEL_FORECAST_W,
    PANEL_GENMIX_X, PANEL_GENMIX_W,
    PANEL_ALARM_X, PANEL_ALARM_W,
    FLOW_ANIMATION,
)
from utils.helpers import resource_path


_BLINK_2HZ_PERIOD = 0.5   # seconds per 2Hz blink cycle (alarm panel)
_BLINK_PERIOD     = 1.0   # seconds per blink cycle (canvas, dispatch panel)
_HIT_RADIUS       = 10    # px — Chebyshev hit radius for bus/unit selection
_LINE_HIT_PX      = 6     # px — max perpendicular distance for line selection


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

    def __init__(self, display_surf: pygame.Surface, shift: int) -> None:
        self._display = display_surf
        self._native  = pygame.Surface((NATIVE_WIDTH, NATIVE_HEIGHT))

        # Canvas region: top CANVAS_HEIGHT rows
        self._canvas_surf = self._native.subsurface(
            pygame.Rect(0, 0, NATIVE_WIDTH, CANVAS_HEIGHT)
        )
        # Strip region: bottom STRIP_HEIGHT rows
        self._strip_surf = self._native.subsurface(
            pygame.Rect(0, CANVAS_HEIGHT, NATIVE_WIDTH, STRIP_HEIGHT)
        )

        self._letterbox_rect = self._calc_letterbox(display_surf)

        font_path = resource_path('assets/fonts/JetBrainsMono-Regular.ttf')
        if font_path.exists():
            self._font = pygame.freetype.Font(str(font_path), 11)
        else:
            self._font = pygame.freetype.SysFont('monospace', 11)

        self._canvas = GridCanvas(shift=shift, font=self._font)
        self._editor = GridEditor(self._canvas)
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

        # Panel surface cache: standalone surfaces redrawn only when data changes
        self._panel_cache: dict[str, pygame.Surface] = {
            'freq':     pygame.Surface((PANEL_FREQ_W,     STRIP_HEIGHT)),
            'power':    pygame.Surface((PANEL_POWER_W,    STRIP_HEIGHT)),
            'dispatch': pygame.Surface((PANEL_DISPATCH_W, STRIP_HEIGHT)),
            'forecast': pygame.Surface((PANEL_FORECAST_W, STRIP_HEIGHT)),
            'genmix':   pygame.Surface((PANEL_GENMIX_W,   STRIP_HEIGHT)),
            'alarm':    pygame.Surface((PANEL_ALARM_W,    STRIP_HEIGHT)),
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
        self._mouse_pos:   tuple[int, int] = (0, 0)
        self._click_pos:   tuple[int, int] | None = None
        self._click_timer: float = 0.0
        self._frame_time:  float = 0.0
        self._fps:         float = 0.0

    # ─── Per-frame entry point ────────────────────────────────────────────────

    def set_grid(self, grid) -> None:
        """Store the Grid reference used by the dispatch panel."""
        self._grid = grid

    def on_scroll(self, delta: int, pos: tuple[int, int]) -> None:
        """Route mouse wheel to dispatch or alarm panel based on native-space position."""
        if pos[1] < CANVAS_HEIGHT:
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
        # Update blink phases
        self._blink_timer += dt_real_s
        if self._blink_timer >= _BLINK_PERIOD:
            self._blink_timer -= _BLINK_PERIOD
        self._blink_on = self._blink_timer < _BLINK_PERIOD * 0.5

        self._blink_2hz_timer += dt_real_s
        if self._blink_2hz_timer >= _BLINK_2HZ_PERIOD:
            self._blink_2hz_timer -= _BLINK_2HZ_PERIOD
        self._blink_2hz_on = self._blink_2hz_timer < _BLINK_2HZ_PERIOD * 0.5

        self._frame_time = dt_real_s
        self._fps = 1.0 / dt_real_s if dt_real_s > 0.0 else 0.0

        # ── Draw canvas ───────────────────────────────────────────────────────
        self._canvas.draw(
            self._canvas_surf,
            state=state,
            blink_on=self._blink_on,
            selected_label=self._selected_label,
        )

        # ── Flow markers (drawn on top of canvas) ─────────────────────────────
        if state is not None and FLOW_ANIMATION:
            self._flow.update(dt_real_s, speed_mult)
            self._flow.draw(self._canvas_surf, state,
                            self._canvas._bus_map, self._canvas._lines)

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
            int(state.sim_hour)           if state else 0,
        )
        genmix_key = (
            tuple(round(v) for _, v in sorted(state.gen_mix_mw.items())) if state else None,
        )
        _has_unacked = (
            any(not a.acknowledged for a in state.active_alarms) if state else False
        )
        alarm_key = (
            len(state.active_alarms)                               if state else 0,
            sum(1 for a in state.active_alarms if a.acknowledged)  if state else 0,
            self._alarm_scroll,
            self._blink_2hz_on if _has_unacked else True,
        )

        if freq_key != self._panel_keys['freq']:
            draw_frequency_panel(
                self._panel_cache['freq'], self._font, self._blink_on, state, paused=paused)
            self._panel_keys['freq'] = freq_key

        if power_key != self._panel_keys['power']:
            draw_power_panel(self._panel_cache['power'], self._font, state)
            self._panel_keys['power'] = power_key

        if dispatch_key != self._panel_keys['dispatch']:
            draw_dispatch_panel(
                self._panel_cache['dispatch'], self._font, self._blink_on,
                state, self._grid, self._dispatch_scroll)
            self._panel_keys['dispatch'] = dispatch_key

        if forecast_key != self._panel_keys['forecast']:
            draw_forecast_panel(self._panel_cache['forecast'], self._font, state)
            self._panel_keys['forecast'] = forecast_key

        if genmix_key != self._panel_keys['genmix']:
            draw_genmix_panel(self._panel_cache['genmix'], self._font, state)
            self._panel_keys['genmix'] = genmix_key

        if alarm_key != self._panel_keys['alarm']:
            draw_alarm_panel(
                self._panel_cache['alarm'], self._font, self._blink_2hz_on,
                state, self._alarm_scroll)
            self._panel_keys['alarm'] = alarm_key

        # Blit all cached panel surfaces to the strip in one pass
        self._strip_surf.blit(self._panel_cache['freq'],     (PANEL_FREQ_X,     0))
        self._strip_surf.blit(self._panel_cache['power'],    (PANEL_POWER_X,    0))
        self._strip_surf.blit(self._panel_cache['dispatch'], (PANEL_DISPATCH_X, 0))
        self._strip_surf.blit(self._panel_cache['forecast'], (PANEL_FORECAST_X, 0))
        self._strip_surf.blit(self._panel_cache['genmix'],   (PANEL_GENMIX_X,   0))
        self._strip_surf.blit(self._panel_cache['alarm'],    (PANEL_ALARM_X,    0))

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
            )
        elif self._selected_label is not None:
            selected_bus = self._canvas._bus_map.get(self._selected_label)
            if selected_bus is not None:
                draw_bus_context(self._canvas_surf, self._font,
                                 bus=selected_bus, state=state)
            else:
                selected_line = next(
                    (l for l in self._canvas._lines if l.label == self._selected_label),
                    None,
                )
                if selected_line is not None:
                    draw_line_context(self._canvas_surf, self._font,
                                      line=selected_line, state=state,
                                      cmd_active=self._line_cmd_active)

        # ── Editor overlay ────────────────────────────────────────────────────
        if _sim_const.EDITOR_MODE:
            self._editor.draw_overlay(self._canvas_surf, self._font)

        # ── Debug overlay ──────────────────────────────────────────────────────
        if _sim_const.DEBUG_DISPLAY:
            self._draw_debug()

        # ── Scale to display with letterboxing ────────────────────────────────
        self._display.fill(LETTERBOX_COLOUR)
        pygame.transform.scale(
            self._native,
            self._letterbox_rect.size,
            self._display.subsurface(self._letterbox_rect),
        )

    # ─── Letterbox helpers ────────────────────────────────────────────────────

    @staticmethod
    def _calc_letterbox(display_surf: pygame.Surface) -> pygame.Rect:
        dw, dh = display_surf.get_size()
        if dw / dh >= NATIVE_WIDTH / NATIVE_HEIGHT:
            sh, sw = dh, int(dh * NATIVE_WIDTH / NATIVE_HEIGHT)
        else:
            sw, sh = dw, int(dw * NATIVE_HEIGHT / NATIVE_WIDTH)
        return pygame.Rect((dw - sw) // 2, (dh - sh) // 2, sw, sh)

    def set_display(self, display_surf: pygame.Surface) -> None:
        self._display = display_surf
        self._letterbox_rect = self._calc_letterbox(display_surf)

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
        if ny >= CANVAS_HEIGHT:
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
        for bus in self._canvas._buses:
            dist = max(abs(nx - bus.canvas_x), abs(ny - bus.canvas_y))
            if dist <= _HIT_RADIUS and dist < best_dist:
                best_dist  = dist
                best_label = bus.label

        # Lines — only if no bus/unit was hit within its own radius
        if best_label is None:
            for line in self._canvas._lines:
                fb = self._canvas._bus_map.get(line.from_bus)
                tb = self._canvas._bus_map.get(line.to_bus)
                if fb is None or tb is None:
                    continue
                bx, by = fb.canvas_x, tb.canvas_y  # bend point: vertical-first routing
                d1 = _point_segment_dist(nx, ny, fb.canvas_x, fb.canvas_y, bx, by)
                d2 = _point_segment_dist(nx, ny, bx, by, tb.canvas_x, tb.canvas_y)
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
        grid_spacing = 120
        font = self._font

        # Faint coordinate grid
        for x in range(0, NATIVE_WIDTH, grid_spacing):
            pygame.draw.line(self._native, COL_DEBUG_GRID, (x, 0), (x, CANVAS_HEIGHT), 1)
        for y in range(0, CANVAS_HEIGHT, grid_spacing):
            pygame.draw.line(self._native, COL_DEBUG_GRID, (0, y), (NATIVE_WIDTH, y), 1)

        # Mouse position — top-left
        mx, my = self._mouse_pos
        font.render_to(self._native, (4, 4),
                       f'mouse {mx},{my}', COL_DEBUG_TEXT, size=FONT_SIZE_OVERLAY)

        # FPS / frame time — top-right
        fps_str = f'{self._fps:.0f}fps  {self._frame_time*1000:.1f}ms'
        tw, _ = font.get_rect(fps_str, size=FONT_SIZE_OVERLAY)[2:4]
        font.render_to(self._native, (NATIVE_WIDTH - tw - 8, 4),
                       fps_str, COL_DEBUG_TEXT, size=FONT_SIZE_OVERLAY)

        # AGC status — top-right, second line
        agc_str = f'AGC {"ON" if _sim_const.AGC_ENABLED else "OFF"}'
        agc_col = COL_DEBUG_TEXT if _sim_const.AGC_ENABLED else COL_TEXT_DIM
        agc_w, _ = font.get_rect(agc_str, size=FONT_SIZE_OVERLAY)[2:4]
        font.render_to(self._native, (NATIVE_WIDTH - agc_w - 8, 18),
                       agc_str, agc_col, size=FONT_SIZE_OVERLAY)

        # Resolution / scale — top-right, third line
        dw, dh = self._display.get_size()
        scale = self._letterbox_rect.width / NATIVE_WIDTH
        res_str = f'{dw}\xd7{dh}  {NATIVE_WIDTH}\xd7{NATIVE_HEIGHT}  {scale:.2f}\xd7'
        res_w, _ = font.get_rect(res_str, size=FONT_SIZE_OVERLAY)[2:4]
        font.render_to(self._native, (NATIVE_WIDTH - res_w - 8, 32),
                       res_str, COL_DEBUG_TEXT, size=FONT_SIZE_OVERLAY)

        # Click position — shown for 3 seconds
        if self._click_pos is not None:
            self._click_timer -= self._frame_time
            if self._click_timer > 0.0:
                cx, cy = self._click_pos
                from display.palette import COL_DEBUG_CLICK
                font.render_to(self._native, (4, 18),
                               f'click {cx},{cy}', COL_DEBUG_CLICK, size=FONT_SIZE_OVERLAY)
            else:
                self._click_pos = None
