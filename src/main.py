"""
src/main.py

GRIDCOM : Grid Control Terminal — entry point.

Initialises pygame, creates the display window, instantiates the
Renderer and GridSimulation, and runs the main loop.

Controls (PLAYING state):
    Escape / Q      Deselect / close panel / quit
    D               Toggle DEBUG_DISPLAY overlay
    Ctrl+Shift+E    Toggle EDITOR_MODE
    F12             Toggle EDITOR_MODE (same as Ctrl+Shift+E)
    Ctrl+A          Toggle AGC (Automatic Generation Control)
    Ctrl+N          End current shift immediately (go to debrief) [debug]
    S               Save layout (EDITOR_MODE) / Start selected unit (Play mode)
    X               Stop selected unit
    T               Trip selected line (if IN SERVICE)
    C               Close selected line (if TRIPPED)
    A               Acknowledge top alarm
    Shift+A         Acknowledge all alarms
    Tab             Cycle element selection
    F1 / F3 / F5    Switch active shift (1, 3, or 5) [debug]
    P / Space       Pause / resume simulation (toggle)
    Mouse wheel     Scroll dispatch or alarm panel (when over strip)
"""

import sys
import os
from enum import Enum

# Ensure the src directory is on the path when running as `python src/main.py`
sys.path.insert(0, os.path.dirname(__file__))

import pygame
import pygame.freetype

from display.renderer import Renderer
from display.palette import COL_TEXT_BODY, COL_TEXT_SCREEN_HDR
from display.menus import (
    build_splash_lines,
    build_main_menu_items,
    build_mode_select_items,
    build_difficulty_items,
    build_continuous_placeholder_lines,
    build_campaign_intro_screens,
    build_campaign_end_lines,
)
from data.layout_override import load_layout
from data.profiles import SHIFT_SPECS
from simulation.grid import Grid
from simulation.simulation import GridSimulation
from simulation.constants import (
    NATIVE_WIDTH, NATIVE_HEIGHT,
    TARGET_FPS, SIM_TICK_INTERVAL_S,
    TIME_COMPRESSION,
    SPEED_PAUSE, SPEED_SLOW, SPEED_NORMAL, SPEED_FAST, SPEED_VERY_FAST,
    TYPEWRITER_CHARS_PER_SEC,
    SPLASH_DURATION_S,
)
import simulation.constants as _const
from debug_scenario import make_debug_sim, DEBUG_SCENARIO


# ─── Game state ──────────────────────────────────────────────────────────────

class GameState(Enum):
    SPLASH            = 'splash'
    MAIN_MENU         = 'main_menu'
    MODE_SELECT       = 'mode_select'
    DIFFICULTY_SELECT = 'difficulty_select'
    CONTINUOUS_STUB   = 'continuous_stub'
    CAMPAIGN_INTRO    = 'campaign_intro'
    BRIEFING          = 'briefing'
    PLAYING           = 'playing'
    DEBRIEF           = 'debrief'
    CAMPAIGN_END      = 'campaign_end'


# ─── Fictional shift dates ────────────────────────────────────────────────────

_SHIFT_DATES: dict[int, str] = {
    1:  'MON 07 NOV 1994',
    2:  'MON 07 NOV 1994',
    3:  'MON 07 NOV 1994',
    4:  'MON 07 NOV 1994',
    5:  'TUE 08 NOV 1994',
    6:  'TUE 08 NOV 1994',
    7:  'WED 09 NOV 1994',
    8:  'WED 09 NOV 1994',
    9:  'THU 10 NOV 1994',
    10: 'THU 10 NOV 1994',
}

_SEP = '═' * 64


def _hm(hours: float) -> str:
    h = int(hours) % 24
    m = int((hours % 1) * 60)
    return f'{h:02d}:{m:02d}'


# ─── Menu title block ─────────────────────────────────────────────────────────

def _menu_title_lines() -> list:
    H = COL_TEXT_SCREEN_HDR
    return [
        (_SEP, H),
        (' NATIONAL ENERGY CONTROL CENTRE — ASHFORD', H),
        (' GRIDCOM v2.4.1', H),
        (_SEP, H),
    ]


# ─── Text screen content builders ────────────────────────────────────────────

def build_briefing_lines(spec) -> list:
    """Return list of (text, colour) pairs for the pre-shift briefing screen."""
    H = COL_TEXT_SCREEN_HDR
    B = COL_TEXT_BODY
    date_str = _SHIFT_DATES.get(spec.shift_number, 'MON 07 NOV 1994')
    lines = [
        (_SEP, H),
        (' NATIONAL ENERGY CONTROL CENTRE — ASHFORD', H),
        (' SHIFT HANDOVER RECORD', H),
        (_SEP, H),
        (f' DATE: {date_str}    TIME: {_hm(spec.start_hour)}    SHIFT: {spec.shift_number} OF 10', B),
        (' OUTGOING: R. FERRIS, DISPATCHER GRADE 2', B),
        (f' DIFFICULTY: {spec.difficulty_label.upper()}', B),
        (_SEP, H),
        (' HANDOVER NOTES:', H),
        ('', B),
    ]
    for note in spec.handover_notes:
        lines.append((f'   {note}', B))
    lines += [
        ('', B),
        (_SEP, H),
        (f' DURATION: {int(spec.duration_hours):02d}H 00M    PEAK FORECAST: {spec.peak_demand_mw:.0f} MW', B),
        (_SEP, H),
    ]
    return lines


def build_debrief_lines(spec, state) -> list:
    """Return list of (text, colour) pairs for the end-of-shift report screen."""
    H = COL_TEXT_SCREEN_HDR
    B = COL_TEXT_BODY
    date_str = _SHIFT_DATES.get(spec.shift_number, 'MON 07 NOV 1994')
    dur_h = int(spec.duration_hours)
    dur_m = int((spec.duration_hours % 1) * 60)
    trips  = sum(1 for s in state.unit_states.values() if s == 'TRIPPED')
    alarms = len(state.active_alarms)
    freq_pct = state.frequency_in_bounds_pct
    if freq_pct >= 95.0 and state.load_shed_events == 0 and state.cascade_events == 0:
        assessment = 'EXCELLENT'
    elif freq_pct >= 80.0 and state.load_shed_events <= 1:
        assessment = 'SATISFACTORY'
    elif freq_pct >= 60.0:
        assessment = 'MARGINAL'
    else:
        assessment = 'UNSATISFACTORY'
    lines = [
        (_SEP, H),
        (' NATIONAL ENERGY CONTROL CENTRE — ASHFORD', H),
        (' SHIFT COMPLETION RECORD', H),
        (_SEP, H),
        (f' SHIFT: {spec.shift_number} OF 10    DURATION: {dur_h:02d}H {dur_m:02d}M    DATE: {date_str}', B),
        (_SEP, H),
        (' FREQUENCY PERFORMANCE:', H),
        (f'   Within \xb10.2 Hz: {freq_pct:.1f}%    Max line loading: {state.max_line_loading_seen:.0f}%', B),
        ('', B),
        (' NETWORK SECURITY:', H),
        (f'   Cascade events: {state.cascade_events}    Load shed events: {state.load_shed_events}    Unit trips: {trips}', B),
        ('', B),
        (' ALARMS:', H),
        (f'   Total active: {alarms}', B),
        ('', B),
        (_SEP, H),
        (f' ASSESSMENT: {assessment}', H),
        (_SEP, H),
    ]
    return lines


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _to_native(
    pos: tuple[int, int],
    letterbox: pygame.Rect,
    scale: float,
) -> tuple[int, int]:
    """Map a physical-display mouse position to native surface coordinates."""
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
    difficulty: str = 'standard',
) -> tuple[GridSimulation, Grid, Renderer]:
    grid     = Grid(shift)
    sim      = GridSimulation(grid=grid, shift_number=shift, difficulty=difficulty,
                              initial_schedule=_SHIFT_SCHEDULES.get(shift, {}))
    renderer = Renderer(display_surf, shift=shift,
                        display_size=display_surf.get_size())
    renderer.set_grid(grid)
    return sim, grid, renderer


def _total_chars(lines: list) -> int:
    return sum(len(text) for text, _ in lines)


def _next_enabled(items: list, current: int, direction: int) -> int:
    """Return the next enabled menu index in the given direction (+1 or -1)."""
    n = len(items)
    idx = current
    for _ in range(n):
        idx = (idx + direction) % n
        enabled = items[idx][1] if len(items[idx]) > 1 else True
        if enabled:
            return idx
    return current


# ─── Main loop ────────────────────────────────────────────────────────────────

def main() -> None:
    pygame.init()
    pygame.freetype.init()

    load_layout()

    display_surf = pygame.display.set_mode(
        (0, 0),
        pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF,
    )
    pygame.display.set_caption('GRIDCOM : Grid Control Terminal')

    clock     = pygame.time.Clock()
    speed     = SPEED_NORMAL
    sim_accum = 0.0

    if _const.DEBUG_SCENARIO_ACTIVE:
        sim, grid = make_debug_sim(DEBUG_SCENARIO)
        renderer  = Renderer(display_surf, shift=DEBUG_SCENARIO.shift_number,
                             display_size=display_surf.get_size())
        renderer.set_grid(grid)
        shift      = DEBUG_SCENARIO.shift_number
        game_state = GameState.BRIEFING
        _spec      = SHIFT_SPECS.get(shift)
        briefing_lines = build_briefing_lines(_spec) if _spec else []
        briefing_chars = 0.0
    else:
        shift      = 1
        difficulty = 'standard'
        sim, grid, renderer = _make_sim_and_renderer(display_surf, shift, difficulty)
        game_state = GameState.SPLASH

    state = sim.get_state()

    # ── Splash state ─────────────────────────────────────────────────────────
    splash_timer  = 0.0
    splash_lines  = build_splash_lines()
    splash_chars  = 0.0   # typewriter for splash

    # ── Menu state ───────────────────────────────────────────────────────────
    menu_selected = 0
    main_menu_items     = build_main_menu_items()
    mode_select_items   = build_mode_select_items()
    difficulty_items    = build_difficulty_items()
    menu_title          = _menu_title_lines()

    # ── Continuous stub ──────────────────────────────────────────────────────
    continuous_lines = build_continuous_placeholder_lines()
    continuous_chars = 0.0

    # ── Campaign intro ───────────────────────────────────────────────────────
    intro_screens    = build_campaign_intro_screens()
    intro_screen_idx = 0
    intro_chars      = 0.0
    difficulty       = 'standard'

    # ── Briefing / debrief state ─────────────────────────────────────────────
    _spec          = SHIFT_SPECS.get(shift)
    briefing_lines = build_briefing_lines(_spec) if _spec else []
    briefing_chars = 0.0
    debrief_lines: list = []
    debrief_chars  = 0.0

    # ── Campaign end ─────────────────────────────────────────────────────────
    campaign_end_lines: list = []
    campaign_end_chars  = 0.0
    campaign_start_time = pygame.time.get_ticks()   # ms — for total watch time

    running = True
    while running:
        dt = clock.tick(TARGET_FPS) / 1000.0
        if dt <= 0.0:
            dt = 1.0 / TARGET_FPS

        # ── SPLASH ───────────────────────────────────────────────────────────
        if game_state == GameState.SPLASH:
            total = _total_chars(splash_lines)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    if splash_timer >= 1.0:   # ignore very early presses
                        game_state    = GameState.MAIN_MENU
                        menu_selected = 0

            splash_timer += dt
            if splash_timer >= SPLASH_DURATION_S:
                game_state    = GameState.MAIN_MENU
                menu_selected = 0

            splash_chars = min(splash_chars + TYPEWRITER_CHARS_PER_SEC * dt,
                               float(total) + 1)
            renderer.tick_splash_screen(dt, splash_lines, int(splash_chars))

        # ── MAIN MENU ────────────────────────────────────────────────────────
        elif game_state == GameState.MAIN_MENU:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        menu_selected = _next_enabled(main_menu_items, menu_selected, -1)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        menu_selected = _next_enabled(main_menu_items, menu_selected, +1)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        idx = menu_selected
                        if idx == 0:   # NEW GAME
                            game_state    = GameState.MODE_SELECT
                            menu_selected = 0
                        elif idx == 1: # CONTINUE — disabled
                            pass
                        elif idx == 2: # QUIT
                            running = False
                    elif event.key == pygame.K_ESCAPE:
                        pass   # already at top level

            renderer.tick_menu_screen(
                dt,
                title_lines=menu_title,
                items=main_menu_items,
                selected_idx=menu_selected,
                footer_hint='[UP / DOWN]  Navigate    [ENTER]  Select',
            )

        # ── MODE SELECT ──────────────────────────────────────────────────────
        elif game_state == GameState.MODE_SELECT:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        menu_selected = _next_enabled(mode_select_items, menu_selected, -1)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        menu_selected = _next_enabled(mode_select_items, menu_selected, +1)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if menu_selected == 0:   # CAMPAIGN
                            game_state    = GameState.DIFFICULTY_SELECT
                            menu_selected = 1    # default OPERATOR
                        elif menu_selected == 1: # CONTINUOUS
                            game_state       = GameState.CONTINUOUS_STUB
                            continuous_chars = 0.0
                    elif event.key == pygame.K_ESCAPE:
                        game_state    = GameState.MAIN_MENU
                        menu_selected = 0

            renderer.tick_menu_screen(
                dt,
                title_lines=menu_title,
                items=mode_select_items,
                selected_idx=menu_selected,
            )

        # ── DIFFICULTY SELECT ─────────────────────────────────────────────────
        elif game_state == GameState.DIFFICULTY_SELECT:
            diff_as_items = [(label, True) for label, _ in difficulty_items]
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        menu_selected = max(0, menu_selected - 1)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        menu_selected = min(len(difficulty_items) - 1, menu_selected + 1)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        difficulty_map = {0: 'trainee', 1: 'standard', 2: 'dispatcher'}
                        difficulty     = difficulty_map.get(menu_selected, 'standard')
                        # Rebuild sim with selected difficulty
                        sim, grid, renderer = _make_sim_and_renderer(
                            display_surf, shift=1, difficulty=difficulty,
                        )
                        state = sim.get_state()
                        game_state       = GameState.CAMPAIGN_INTRO
                        intro_screen_idx = 0
                        intro_chars      = 0.0
                        campaign_start_time = pygame.time.get_ticks()
                    elif event.key == pygame.K_ESCAPE:
                        game_state    = GameState.MODE_SELECT
                        menu_selected = 0

            # Build items with description shown as subtitle
            display_items = [
                (f'{label}   —   {desc}', True)
                for label, desc in difficulty_items
            ]
            renderer.tick_menu_screen(
                dt,
                title_lines=menu_title,
                items=display_items,
                selected_idx=menu_selected,
            )

        # ── CONTINUOUS STUB ───────────────────────────────────────────────────
        elif game_state == GameState.CONTINUOUS_STUB:
            total = _total_chars(continuous_lines)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    if int(continuous_chars) < total:
                        continuous_chars = float(total)
                    else:
                        game_state    = GameState.MODE_SELECT
                        menu_selected = 1   # keep CONTINUOUS highlighted

            continuous_chars = min(continuous_chars + TYPEWRITER_CHARS_PER_SEC * dt,
                                   float(total) + 1)
            renderer.tick_text_screen(dt, continuous_lines, int(continuous_chars))

        # ── CAMPAIGN INTRO ────────────────────────────────────────────────────
        elif game_state == GameState.CAMPAIGN_INTRO:
            current_screen = intro_screens[intro_screen_idx]
            total = _total_chars(current_screen)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    if int(intro_chars) < total:
                        intro_chars = float(total)
                    else:
                        intro_screen_idx += 1
                        intro_chars = 0.0
                        if intro_screen_idx >= len(intro_screens):
                            # All intro screens done — start shift 1
                            shift      = 1
                            _spec      = SHIFT_SPECS.get(shift)
                            briefing_lines = build_briefing_lines(_spec) if _spec else []
                            briefing_chars = 0.0
                            game_state = GameState.BRIEFING

            intro_chars = min(intro_chars + TYPEWRITER_CHARS_PER_SEC * dt,
                              float(total) + 1)
            renderer.tick_text_screen(dt, current_screen, int(intro_chars))

        # ── BRIEFING ─────────────────────────────────────────────────────────
        elif game_state == GameState.BRIEFING:
            total = _total_chars(briefing_lines)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    if int(briefing_chars) < total:
                        briefing_chars = float(total)
                    else:
                        game_state = GameState.PLAYING
            briefing_chars = min(briefing_chars + TYPEWRITER_CHARS_PER_SEC * dt,
                                 float(total) + 1)
            renderer.tick_text_screen(dt, briefing_lines, int(briefing_chars))

        # ── PLAYING ──────────────────────────────────────────────────────────
        elif game_state == GameState.PLAYING:
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
                            game_state    = GameState.MAIN_MENU
                            menu_selected = 0

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

                    elif ctrl and event.key == pygame.K_n and _const.DEBUG_EVENTS and not _const.EDITOR_MODE:
                        _spec = SHIFT_SPECS.get(shift)
                        if _spec:
                            debrief_lines = build_debrief_lines(_spec, sim.get_state())
                        game_state    = GameState.DEBRIEF
                        debrief_chars = 0.0

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

                    # Shift-switch: F1 / F3 / F5 (dev convenience — no briefing reset)
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

                    elif (not _const.EDITOR_MODE and not ctrl and not shift_held
                          and event.key in (
                              pygame.K_0, pygame.K_1, pygame.K_2, pygame.K_3,
                              pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7,
                              pygame.K_8, pygame.K_9,
                          )
                          and (renderer._input_active or renderer._get_selected_unit() is not None)):
                        renderer.on_key_digit(pygame.key.name(event.key))

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

            sim_accum += dt
            if speed > 0.0 and sim_accum >= SIM_TICK_INTERVAL_S:
                sim.tick(sim_accum * TIME_COMPRESSION * speed)
                state = sim.get_state()
                sim_accum = 0.0

            renderer.tick(dt, state=state, speed_mult=speed)

            if sim.is_shift_complete():
                _spec = SHIFT_SPECS.get(shift)
                if _spec:
                    debrief_lines = build_debrief_lines(_spec, sim.get_state())
                game_state    = GameState.DEBRIEF
                debrief_chars = 0.0

        # ── DEBRIEF ───────────────────────────────────────────────────────────
        elif game_state == GameState.DEBRIEF:
            total = _total_chars(debrief_lines)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    if int(debrief_chars) < total:
                        debrief_chars = float(total)
                    else:
                        if shift < 10:
                            shift += 1
                            sim, grid, renderer = _make_sim_and_renderer(
                                display_surf, shift, difficulty,
                            )
                            state          = sim.get_state()
                            sim_accum      = 0.0
                            _spec          = SHIFT_SPECS.get(shift)
                            briefing_lines = build_briefing_lines(_spec) if _spec else []
                            briefing_chars = 0.0
                            game_state     = GameState.BRIEFING
                        else:
                            watch_s = (pygame.time.get_ticks() - campaign_start_time) / 1000.0
                            campaign_end_lines = build_campaign_end_lines(
                                shifts_completed=10,
                                watch_time_s=watch_s,
                                grade='A',
                            )
                            campaign_end_chars = 0.0
                            game_state         = GameState.CAMPAIGN_END

            debrief_chars = min(debrief_chars + TYPEWRITER_CHARS_PER_SEC * dt,
                                float(total) + 1)
            renderer.tick_text_screen(dt, debrief_lines, int(debrief_chars))

        # ── CAMPAIGN END ──────────────────────────────────────────────────────
        elif game_state == GameState.CAMPAIGN_END:
            total = _total_chars(campaign_end_lines)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    if int(campaign_end_chars) < total:
                        campaign_end_chars = float(total)
                    else:
                        game_state    = GameState.MAIN_MENU
                        menu_selected = 0

            campaign_end_chars = min(campaign_end_chars + TYPEWRITER_CHARS_PER_SEC * dt,
                                     float(total) + 1)
            renderer.tick_text_screen(dt, campaign_end_lines, int(campaign_end_chars))

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()
