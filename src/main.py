"""
src/main.py

GRIDCOM : Grid Control Terminal — entry point.

Initialises pygame, creates the display window, instantiates the
Renderer, and runs the main loop. For Stage 9 this is a static viewer:
no simulation is running, the grid is drawn at rest with all units OFFLINE.

Controls (Stage 9 static viewer):
    Escape / Q    Quit
    D             Toggle DEBUG_DISPLAY overlay
    1 / 3 / 5     Switch active shift (shows different subsets of the grid)
"""

import sys
import os

# Ensure the src directory is on the path when running as `python src/main.py`
sys.path.insert(0, os.path.dirname(__file__))

import pygame
import pygame.freetype

from display.renderer import Renderer
from data.layout_override import load_layout
from simulation.constants import (
    NATIVE_WIDTH, NATIVE_HEIGHT,
    TARGET_FPS,
)
import simulation.constants as _const


def _to_native(display_surf: pygame.Surface, pos: tuple[int, int]) -> tuple[int, int]:
    """Convert display-resolution mouse position to native 1920×1080 coordinates."""
    dw, dh = display_surf.get_size()
    nx = int(pos[0] * NATIVE_WIDTH  / dw)
    ny = int(pos[1] * NATIVE_HEIGHT / dh)
    return nx, ny


def main() -> None:
    pygame.init()
    pygame.freetype.init()

    load_layout()

    # Window: resizable, starts at native resolution
    flags = pygame.RESIZABLE
    display_surf = pygame.display.set_mode((NATIVE_WIDTH, NATIVE_HEIGHT), flags)
    pygame.display.set_caption('GRIDCOM : Grid Control Terminal')

    clock   = pygame.time.Clock()
    shift   = 1
    renderer = Renderer(display_surf, shift=shift)

    running = True
    while running:
        dt = clock.tick(TARGET_FPS) / 1000.0
        if dt <= 0.0:
            dt = 1.0 / TARGET_FPS

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                ctrl  = bool(mods & pygame.KMOD_CTRL)
                shift_held = bool(mods & pygame.KMOD_SHIFT)

                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    if _const.EDITOR_MODE:
                        _const.EDITOR_MODE = False
                    else:
                        running = False
                elif ctrl and shift_held and event.key == pygame.K_e:
                    _const.EDITOR_MODE = not _const.EDITOR_MODE
                elif event.key == pygame.K_s and _const.EDITOR_MODE:
                    renderer.save_layout()
                elif event.key == pygame.K_d:
                    _const.DEBUG_DISPLAY = not _const.DEBUG_DISPLAY
                elif event.key == pygame.K_1 and not _const.EDITOR_MODE:
                    shift    = 1
                    renderer = Renderer(display_surf, shift=shift)
                elif event.key == pygame.K_3 and not _const.EDITOR_MODE:
                    shift    = 3
                    renderer = Renderer(display_surf, shift=shift)
                elif event.key == pygame.K_5 and not _const.EDITOR_MODE:
                    shift    = 5
                    renderer = Renderer(display_surf, shift=shift)

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

            elif event.type == pygame.VIDEORESIZE:
                display_surf = pygame.display.set_mode(event.size, flags)
                renderer = Renderer(display_surf, shift=shift)

        renderer.tick(dt, state=None)
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()
