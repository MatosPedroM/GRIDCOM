"""
src/display/renderer.py

Renderer: owns the native 1920×1080 surface, drives the render loop,
and composites all display layers each frame.

Native resolution is always 1920×1080 regardless of monitor size.
At the end of each frame the native surface is scaled to the display surface.

Layers (bottom to top):
  1. Canvas background + grid schematic (GridCanvas)
  2. Instrument strip background  (placeholder — filled black for Stage 9)
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
from display.palette import COL_BACKGROUND, COL_STRIP_BG, COL_DEBUG_TEXT, COL_DEBUG_GRID
from simulation.constants import (
    CANVAS_HEIGHT, STRIP_HEIGHT,
    NATIVE_WIDTH, NATIVE_HEIGHT,
    DEBUG_DISPLAY,
)
from utils.helpers import resource_path


_BLINK_PERIOD = 1.0   # seconds per blink cycle


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

        font_path = resource_path('assets/fonts/JetBrainsMono-Regular.ttf')
        if font_path.exists():
            self._font = pygame.freetype.Font(str(font_path), 11)
        else:
            self._font = pygame.freetype.SysFont('monospace', 11)

        self._canvas = GridCanvas(shift=shift, font=self._font)

        self._blink_timer: float = 0.0
        self._blink_on:    bool  = True

        # Debug state
        self._mouse_pos:   tuple[int, int] = (0, 0)
        self._click_pos:   tuple[int, int] | None = None
        self._click_timer: float = 0.0
        self._frame_time:  float = 0.0
        self._fps:         float = 0.0

    # ─── Per-frame entry point ────────────────────────────────────────────────

    def tick(
        self,
        dt_real_s: float,
        state=None,
        selected_label: str | None = None,
    ) -> None:
        """
        Render one frame.

        Args:
            dt_real_s:      Real-time delta in seconds since last frame.
            state:          Current SimulationState, or None for static view.
            selected_label: Currently selected bus/unit label, or None.
        """
        # Update blink phase
        self._blink_timer += dt_real_s
        if self._blink_timer >= _BLINK_PERIOD:
            self._blink_timer -= _BLINK_PERIOD
        self._blink_on = self._blink_timer < _BLINK_PERIOD * 0.5

        self._frame_time = dt_real_s
        self._fps = 1.0 / dt_real_s if dt_real_s > 0.0 else 0.0

        # ── Draw canvas ───────────────────────────────────────────────────────
        self._canvas.draw(
            self._canvas_surf,
            state=state,
            blink_on=self._blink_on,
            selected_label=selected_label,
        )

        # ── Draw instrument strip (Stage 9: plain background) ─────────────────
        self._strip_surf.fill(COL_STRIP_BG)

        # ── Debug overlay ──────────────────────────────────────────────────────
        if DEBUG_DISPLAY:
            self._draw_debug()

        # ── Scale to display ───────────────────────────────────────────────────
        if self._native.get_size() != self._display.get_size():
            pygame.transform.scale(self._native, self._display.get_size(),
                                   self._display)
        else:
            self._display.blit(self._native, (0, 0))

    # ─── Debug overlay ────────────────────────────────────────────────────────

    def on_mouse_move(self, pos: tuple[int, int]) -> None:
        """Call with native-space mouse position each motion event."""
        self._mouse_pos = pos

    def on_click(self, pos: tuple[int, int]) -> None:
        """Call with native-space position on mouse click; prints coords."""
        self._click_pos   = pos
        self._click_timer = 3.0
        print(f'[DEBUG CLICK] x={pos[0]}, y={pos[1]}')

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
                       f'mouse {mx},{my}', COL_DEBUG_TEXT, size=10)

        # FPS / frame time — top-right
        fps_str = f'{self._fps:.0f}fps  {self._frame_time*1000:.1f}ms'
        tw, _ = font.get_rect(fps_str, size=10)[2:4]
        font.render_to(self._native, (NATIVE_WIDTH - tw - 8, 4),
                       fps_str, COL_DEBUG_TEXT, size=10)

        # Click position — shown for 3 seconds
        if self._click_pos is not None:
            self._click_timer -= self._frame_time
            if self._click_timer > 0.0:
                cx, cy = self._click_pos
                from display.palette import COL_DEBUG_CLICK
                font.render_to(self._native, (4, 18),
                               f'click {cx},{cy}', COL_DEBUG_CLICK, size=10)
            else:
                self._click_pos = None
