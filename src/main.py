"""
src/main.py

GRIDCOM : Grid Control Terminal — entry point.

Initialises pygame, creates the display window, instantiates the
Renderer and GridSimulation, and runs the main loop.

Controls:
    Escape / Q      Quit (or exit EDITOR_MODE, cancel input, deselect)
    D               Toggle DEBUG_DISPLAY overlay
    Ctrl+Shift+E    Toggle EDITOR_MODE
    F12             Toggle EDITOR_MODE (same as Ctrl+Shift+E)
    Ctrl+A          Toggle AGC (Automatic Generation Control)
    S               Save layout (EDITOR_MODE) / Start selected unit (Play mode)
    X               Stop selected unit
    T               Trip selected line (if IN SERVICE)
    C               Close selected line (if TRIPPED)
    A               Acknowledge top alarm
    Shift+A         Acknowledge all alarms
    Tab             Cycle element selection
    F1 / F3 / F5    Switch active shift (1, 3, or 5)
    P / Space       Pause / resume simulation (toggle)
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
    TARGET_FPS, SIM_TICK_INTERVAL_S,
    TIME_COMPRESSION,
    SPEED_PAUSE, SPEED_SLOW, SPEED_NORMAL, SPEED_FAST, SPEED_VERY_FAST,
)
import simulation.constants as _const
from debug_scenario import make_debug_sim, DEBUG_SCENARIO


def _to_native(
    pos: tuple[int, int],
    letterbox: pygame.Rect,
    scale: float,
) -> tuple[int, int]:
    """Map a physical-display mouse position to native surface coordinates.

    The native surface is rendered at the physical game-area size (letterbox.size),
    so mouse coordinates only need the letterbox offset subtracted and clamped —
    no scale division needed.
    """
    nx = pos[0] - letterbox.left
    ny = pos[1] - letterbox.top
    return (
        max(0, min(letterbox.width  - 1, nx)),
        max(0, min(letterbox.height - 1, ny)),
    )


# Handover schedules: unit outputs (MW) at the start of each shift.
# Units absent from the dict start OFFLINE.
_SHIFT_SCHEDULES: dict[int, dict] = {
    1: {
        'DUND-1': 16.0,   # Dunmore lower hydro — sole generator (tutorial)
    },
    3: {},   # TODO: tune when shift 3 is tested
    5: {},   # TODO: tune when shift 5 is tested
}


def _make_sim_and_renderer(
    display_surf: pygame.Surface,
    shift: int,
) -> tuple[GridSimulation, Grid, Renderer]:
    grid     = Grid(shift)
    sim      = GridSimulation(grid=grid, shift_number=shift, difficulty='standard',
                              initial_schedule=_SHIFT_SCHEDULES.get(shift, {}))
    renderer = Renderer(display_surf, shift=shift,
                        display_size=display_surf.get_size())
    renderer.set_grid(grid)
    return sim, grid, renderer


def main() -> None:
    pygame.init()
    pygame.freetype.init()

    load_layout()

    # FULLSCREEN at the monitor's native resolution. Letterbox scaling is handled
    # manually in Renderer — a uniform scale factor maps 1920×1080 onto the physical
    # display with equal-sized black bars, preventing the axis-asymmetric distortion
    # that pygame.SCALED produces on non-16:9 monitors.
    display_surf = pygame.display.set_mode(
        (0, 0),
        pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF,
    )
    pygame.display.set_caption('GRIDCOM : Grid Control Terminal')

    clock     = pygame.time.Clock()
    shift     = 1
    speed     = SPEED_NORMAL
    sim_accum = 0.0   # accumulates real time until next simulation tick

    if _const.DEBUG_SCENARIO_ACTIVE:
        sim, grid = make_debug_sim(DEBUG_SCENARIO)
        renderer  = Renderer(display_surf, shift=DEBUG_SCENARIO.shift_number,
                             display_size=display_surf.get_size())
        renderer.set_grid(grid)
        shift = DEBUG_SCENARIO.shift_number
    else:
        sim, grid, renderer = _make_sim_and_renderer(display_surf, shift)

    state   = sim.get_state()   # initial state; updated every SIM_TICK_INTERVAL_S
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

                if (event.key == pygame.K_RETURN
                      and bool(mods & pygame.KMOD_ALT)
                      and _const.DEBUG_DISPLAY):
                    pygame.display.toggle_fullscreen()

                elif event.key in (pygame.K_ESCAPE, pygame.K_q):
                    if _const.EDITOR_MODE:
                        _const.EDITOR_MODE = False
                    elif renderer._selected_label is not None or renderer._input_active:
                        renderer.on_escape()
                    else:
                        running = False

                elif (ctrl and shift_held and event.key == pygame.K_e
                      or event.key == pygame.K_F12):
                    _const.EDITOR_MODE = not _const.EDITOR_MODE

                elif event.key == pygame.K_s and _const.EDITOR_MODE:
                    renderer.save_layout()

                elif (event.key == pygame.K_s and not _const.EDITOR_MODE
                      and not renderer._input_active):
                    renderer.on_start_unit(sim)

                elif (event.key == pygame.K_x and not _const.EDITOR_MODE
                      and not renderer._input_active):
                    renderer.on_stop_unit(sim)

                elif (event.key == pygame.K_t and not _const.EDITOR_MODE
                      and not renderer._input_active):
                    renderer.on_trip_line(sim)

                elif (event.key == pygame.K_c and not _const.EDITOR_MODE
                      and not renderer._input_active):
                    renderer.on_close_line(sim)

                elif ctrl and not shift_held and event.key == pygame.K_a:
                    _const.AGC_ENABLED = not _const.AGC_ENABLED

                elif (event.key == pygame.K_a and not _const.EDITOR_MODE
                      and not renderer._input_active and not ctrl):
                    if shift_held:
                        renderer.on_ack_all_alarms(sim)
                    else:
                        renderer.on_ack_alarm(sim)

                elif (event.key == pygame.K_TAB and not _const.EDITOR_MODE
                      and not renderer._input_active):
                    renderer.on_tab()

                elif event.key == pygame.K_d:
                    _const.DEBUG_DISPLAY = not _const.DEBUG_DISPLAY

                # Shift-switch: F1 / F3 / F5
                elif event.key == pygame.K_F1 and not _const.EDITOR_MODE:
                    shift = 1
                    sim, grid, renderer = _make_sim_and_renderer(display_surf, shift)
                    state = sim.get_state(); sim_accum = 0.0
                elif event.key == pygame.K_F3 and not _const.EDITOR_MODE:
                    shift = 3
                    sim, grid, renderer = _make_sim_and_renderer(display_surf, shift)
                    state = sim.get_state(); sim_accum = 0.0
                elif event.key == pygame.K_F5 and not _const.EDITOR_MODE:
                    shift = 5
                    sim, grid, renderer = _make_sim_and_renderer(display_surf, shift)
                    state = sim.get_state(); sim_accum = 0.0

                # Unit target input — checked before pause so digits aren't swallowed
                elif (not _const.EDITOR_MODE and not ctrl and not shift_held
                      and event.key in (
                          pygame.K_0, pygame.K_1, pygame.K_2, pygame.K_3,
                          pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7,
                          pygame.K_8, pygame.K_9,
                      )
                      and (renderer._input_active or renderer._get_selected_unit() is not None)):
                    renderer.on_key_digit(pygame.key.name(event.key))

                # Pause / resume toggle
                elif (event.key in (pygame.K_p, pygame.K_SPACE)
                      and not _const.EDITOR_MODE and not renderer._input_active):
                    speed = SPEED_PAUSE if speed > 0.0 else SPEED_NORMAL

                elif not _const.EDITOR_MODE and event.key == pygame.K_BACKSPACE:
                    renderer.on_backspace()

                elif not _const.EDITOR_MODE and event.key == pygame.K_RETURN:
                    renderer.on_enter(sim)

            elif event.type == pygame.MOUSEMOTION:
                renderer.on_mouse_move(_to_native(event.pos, renderer._letterbox_rect, renderer._scale))

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    native_pos = _to_native(event.pos, renderer._letterbox_rect, renderer._scale)
                    if _const.EDITOR_MODE:
                        renderer.on_mouse_down(native_pos)
                    else:
                        renderer.on_click(native_pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and _const.EDITOR_MODE:
                    renderer.on_mouse_up(_to_native(event.pos, renderer._letterbox_rect, renderer._scale))

            elif event.type == pygame.MOUSEWHEEL:
                renderer.on_scroll(event.y, _to_native(pygame.mouse.get_pos(), renderer._letterbox_rect, renderer._scale))

        # Advance simulation at fixed 10 Hz rate regardless of render FPS.
        # Accumulate real time and only tick when the interval is reached,
        # passing the full accumulated dt so simulated time stays accurate.
        sim_accum += dt
        if speed > 0.0 and sim_accum >= SIM_TICK_INTERVAL_S:
            sim.tick(sim_accum * TIME_COMPRESSION * speed)
            state = sim.get_state()
            sim_accum = 0.0

        renderer.tick(dt, state=state, speed_mult=speed)
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()
