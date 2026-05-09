"""
src/main.py

GRIDCOM : Grid Control Terminal — entry point.

Initialises pygame, creates the display window, instantiates the
Renderer and GridSimulation, and runs the main loop.

Controls:
    Escape / Q      Quit (or exit EDITOR_MODE)
    D               Toggle DEBUG_DISPLAY overlay
    Ctrl+Shift+E    Toggle EDITOR_MODE
    S               Save layout (EDITOR_MODE only)
    F1 / F3 / F5    Switch active shift (1, 3, or 5)
    0 / Space       Pause simulation
    1               Slow speed (0.25×)
    2               Normal speed (1×)
    3               Fast speed (3×)
    4               Very fast speed (10×)
    Mouse wheel     Scroll dispatch or alarm panel (when over strip)
"""

import sys
import os

# Ensure the src directory is on the path when running as `python src/main.py`
sys.path.insert(0, os.path.dirname(__file__))

import pygame
import pygame.freetype

from display.renderer import Renderer
from data.layout_override import load_layout
from simulation.grid import Grid
from simulation.simulation import GridSimulation
from simulation.constants import (
    NATIVE_WIDTH, NATIVE_HEIGHT,
    TARGET_FPS,
    TIME_COMPRESSION,
    SPEED_PAUSE, SPEED_SLOW, SPEED_NORMAL, SPEED_FAST, SPEED_VERY_FAST,
)
import simulation.constants as _const


def _to_native(display_surf: pygame.Surface, pos: tuple[int, int]) -> tuple[int, int]:
    """Convert display-resolution mouse position to native 1920×1080 coordinates."""
    dw, dh = display_surf.get_size()
    nx = int(pos[0] * NATIVE_WIDTH  / dw)
    ny = int(pos[1] * NATIVE_HEIGHT / dh)
    return nx, ny


def _make_sim_and_renderer(
    display_surf: pygame.Surface,
    shift: int,
) -> tuple[GridSimulation, Grid, Renderer]:
    grid     = Grid(shift)
    sim      = GridSimulation(grid=grid, shift_number=shift, difficulty='standard')
    renderer = Renderer(display_surf, shift=shift)
    renderer.set_grid(grid)
    return sim, grid, renderer


def main() -> None:
    pygame.init()
    pygame.freetype.init()

    load_layout()

    # Window: resizable, starts at native resolution
    flags = pygame.RESIZABLE
    display_surf = pygame.display.set_mode((NATIVE_WIDTH, NATIVE_HEIGHT), flags)
    pygame.display.set_caption('GRIDCOM : Grid Control Terminal')

    clock = pygame.time.Clock()
    shift = 1
    speed = SPEED_NORMAL

    sim, grid, renderer = _make_sim_and_renderer(display_surf, shift)

    running = True
    while running:
        dt = clock.tick(TARGET_FPS) / 1000.0
        if dt <= 0.0:
            dt = 1.0 / TARGET_FPS

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                mods       = pygame.key.get_mods()
                ctrl       = bool(mods & pygame.KMOD_CTRL)
                shift_held = bool(mods & pygame.KMOD_SHIFT)

                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    if _const.EDITOR_MODE:
                        _const.EDITOR_MODE = False
                    elif renderer._selected_label is not None:
                        renderer.clear_selection()
                    else:
                        running = False

                elif ctrl and shift_held and event.key == pygame.K_e:
                    _const.EDITOR_MODE = not _const.EDITOR_MODE

                elif event.key == pygame.K_s and _const.EDITOR_MODE:
                    renderer.save_layout()

                elif event.key == pygame.K_d:
                    _const.DEBUG_DISPLAY = not _const.DEBUG_DISPLAY

                # Shift-switch: F1 / F3 / F5
                elif event.key == pygame.K_F1 and not _const.EDITOR_MODE:
                    shift = 1
                    sim, grid, renderer = _make_sim_and_renderer(display_surf, shift)
                elif event.key == pygame.K_F3 and not _const.EDITOR_MODE:
                    shift = 3
                    sim, grid, renderer = _make_sim_and_renderer(display_surf, shift)
                elif event.key == pygame.K_F5 and not _const.EDITOR_MODE:
                    shift = 5
                    sim, grid, renderer = _make_sim_and_renderer(display_surf, shift)

                # Speed keys: 0/Space=pause, 1-4=speeds
                elif event.key in (pygame.K_0, pygame.K_SPACE) and not _const.EDITOR_MODE:
                    speed = SPEED_PAUSE
                elif event.key == pygame.K_1 and not _const.EDITOR_MODE:
                    speed = SPEED_SLOW
                elif event.key == pygame.K_2 and not _const.EDITOR_MODE:
                    speed = SPEED_NORMAL
                elif event.key == pygame.K_3 and not _const.EDITOR_MODE:
                    speed = SPEED_FAST
                elif event.key == pygame.K_4 and not _const.EDITOR_MODE:
                    speed = SPEED_VERY_FAST

            elif event.type == pygame.MOUSEMOTION:
                renderer.on_mouse_move(_to_native(display_surf, event.pos))

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    native_pos = _to_native(display_surf, event.pos)
                    if _const.EDITOR_MODE:
                        renderer.on_mouse_down(native_pos)
                    else:
                        renderer.on_click(native_pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and _const.EDITOR_MODE:
                    renderer.on_mouse_up(_to_native(display_surf, event.pos))

            elif event.type == pygame.MOUSEWHEEL:
                renderer.on_scroll(event.y, _to_native(display_surf, pygame.mouse.get_pos()))

            elif event.type == pygame.VIDEORESIZE:
                display_surf = pygame.display.set_mode(event.size, flags)
                sim, grid, renderer = _make_sim_and_renderer(display_surf, shift)

        # Advance simulation
        if speed > 0.0:
            dt_sim_s = dt * TIME_COMPRESSION * speed
            sim.tick(dt_sim_s)
        state = sim.get_state()

        renderer.tick(dt, state=state, speed_mult=speed)
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()
