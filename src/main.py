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
    L               Toggle voltage-tier colour view (lines/substations)
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
    build_campaign_intro_screens,
    build_campaign_end_lines,
    build_menu_title_art,
    build_shift_select_items,
)
from data.layout_override import load_layout
from data.profiles import SHIFT_SPECS, DEMAND_PROFILE_NORMALISED
from gameplay.shifts.loader import load_shift_config
from simulation.grid import Grid
from simulation.simulation import GridSimulation
from simulation.constants import (
    NATIVE_WIDTH, NATIVE_HEIGHT,
    TARGET_FPS, SIM_TICK_INTERVAL_S,
    TIME_COMPRESSION,
    SPEED_PAUSE, SPEED_SLOW, SPEED_NORMAL, SPEED_FAST, SPEED_VERY_FAST,
    TYPEWRITER_CHARS_PER_SEC,
)
import simulation.constants as _const
from debug_scenario import make_debug_sim, DEBUG_SCENARIO


# ─── Game state ──────────────────────────────────────────────────────────────

class GameState(Enum):
    SPLASH            = 'splash'
    MAIN_MENU         = 'main_menu'
    MODE_SELECT       = 'mode_select'
    DIFFICULTY_SELECT = 'difficulty_select'
    CAMPAIGN_INTRO    = 'campaign_intro'
    BRIEFING          = 'briefing'
    PLAYING           = 'playing'
    DEBRIEF           = 'debrief'
    SHIFT_SELECT      = 'shift_select'
    CAMPAIGN_END      = 'campaign_end'
    DESIGNER          = 'designer'
    DESIGNER_TEST     = 'designer_test'
    GRID_TEST_SELECT  = 'grid_test_select'
    SHIFT_BUILDER     = 'shift_builder'
    SHIFT_SELECT_JSON = 'shift_select_json'


_SEP = '═' * 64


def _hm(hours: float) -> str:
    h = int(hours) % 24
    m = int((hours % 1) * 60)
    return f'{h:02d}:{m:02d}'


# ─── Menu title block ─────────────────────────────────────────────────────────

def _menu_title_lines() -> list:
    return build_menu_title_art()


# ─── Text screen content builders ────────────────────────────────────────────

def build_briefing_lines(spec) -> list:
    """Return list of (text, colour) pairs for the pre-shift briefing screen."""
    H = COL_TEXT_SCREEN_HDR
    B = COL_TEXT_BODY
    cfg = load_shift_config(spec.shift_number)
    date_str        = cfg.get('shift_date',       'MON 07 NOV 1994')
    difficulty_label = cfg.get('difficulty_label', '')
    handover_notes   = cfg.get('handover_notes',   ())
    lines = [
        (_SEP, H),
        (' NATIONAL ENERGY CONTROL CENTRE — ASHFORD', H),
        (' SHIFT HANDOVER RECORD', H),
        (_SEP, H),
        (f' DATE: {date_str}    TIME: {_hm(spec.start_hour)}    SHIFT: {spec.shift_number} OF 10', B),
        (' OUTGOING: R. FERRIS, DISPATCHER GRADE 2', B),
        (f' DIFFICULTY: {difficulty_label.upper()}', B),
        (_SEP, H),
        (' HANDOVER NOTES:', H),
        ('', B),
    ]
    for note in handover_notes:
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
    date_str = load_shift_config(spec.shift_number).get('shift_date', 'MON 07 NOV 1994')
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


def _make_sim_and_renderer(
    display_surf: pygame.Surface,
    shift: int,
    difficulty: str = 'standard',
):
    """
    Build sim + renderer for a campaign shift.

    Normally topology/fleet come from Grid(shift) (topology.py/fleet.py,
    filtered by shift number). If the shift's own shift_NN.py declares
    GRID_SOURCE, topology instead comes from that named Grid Designer grid
    (assets/designer_grids/<name>.json) via DesignerGrid — shift_number is
    still passed through unchanged so briefing/debrief/HUD/scripted-events
    continue to key off the real shift number either way.
    """
    cfg         = load_shift_config(shift)
    grid_source = cfg.get('grid_source')

    if grid_source:
        from data.designer_io import load_designer_grid_named
        from simulation.designer_grid import DesignerGrid
        buses, lines, units = load_designer_grid_named(grid_source)
        grid = DesignerGrid(buses, lines, units)
    else:
        grid = Grid(shift)

    sim = GridSimulation(grid=grid, shift_number=shift, difficulty=difficulty,
                         initial_schedule=cfg['initial_schedule'],
                         maintenance_units=cfg['maintenance_units'],
                         maintenance_lines=cfg['maintenance_lines'],
                         substation_load_mw=cfg['substation_load_mw'] or None)
    renderer = Renderer(display_surf, shift=shift,
                        display_size=display_surf.get_size())
    if grid_source:
        renderer.set_designer_grid(grid)
    else:
        renderer.set_grid(grid)
    _const.AGC_ENABLED = cfg['agc_enabled']
    return sim, grid, renderer


def _make_designer_test(
    display_surf: pygame.Surface,
    grid_name: str,
):
    """Build sim + renderer for a designer-grid test session."""
    from data.designer_io import load_designer_grid_named
    from simulation.designer_grid import DesignerGrid

    buses, lines, units = load_designer_grid_named(grid_name)
    designer_grid = DesignerGrid(buses, lines, units)

    # Profile each LOAD bus's peak_load_mw (the grid design's maximum load
    # for that substation) across the day using the campaign's generic
    # demand shape, instead of a flat value.
    substation_load_mw = {
        b.label: {h: b.peak_load_mw * DEMAND_PROFILE_NORMALISED[h]
                  for h in DEMAND_PROFILE_NORMALISED}
        for b in buses
        if b.bus_type == 'LOAD' and b.peak_load_mw > 0
    }

    initial_schedule = {
        u.label: (u.start_mw if u.start_mw >= 0 else u.rated_mw * 0.5)
        for u in units
    }
    maintenance_units = {u.label for u in units if not u.in_service}
    sim = GridSimulation(
        grid=designer_grid,
        shift_number=0,
        difficulty='standard',
        initial_schedule=initial_schedule,
        maintenance_units=maintenance_units,
        maintenance_lines=set(),
        substation_load_mw=substation_load_mw,
    )
    # Renderer uses shift=1 as a safe sentinel — the canvas will show shift-1
    # topology but the simulation state (frequency, dispatch, alarms) is live.
    renderer = Renderer(display_surf, shift=1,
                        display_size=display_surf.get_size())
    renderer.set_designer_grid(designer_grid)
    _const.AGC_ENABLED = True
    return sim, designer_grid, renderer


def _make_campaign_shift_test(
    display_surf: pygame.Surface,
    shift_number: int,
    difficulty: str = 'standard',
):
    """
    Build sim + renderer for a campaign shift being fine-tuned in the Shift
    Builder dev tool. Reuses _make_sim_and_renderer() directly — the exact
    real bootstrap path (including Shift 10's Alpha grid_source branch) —
    so testing here reflects what actually ships, unlike _make_shift_test's
    generic DesignerGrid preview for authored JSON shifts.
    """
    return _make_sim_and_renderer(display_surf, shift_number, difficulty)


def _make_shift_test(
    display_surf: pygame.Surface,
    shift_name: str,
):
    """Build sim + renderer for an authored Shift Builder JSON test session."""
    from data.designer_io import load_designer_grid_named
    from simulation.designer_grid import DesignerGrid
    from gameplay.shifts.loader import load_shift_config_from_json

    cfg = load_shift_config_from_json(shift_name)
    buses, lines, units = load_designer_grid_named(cfg['grid'])
    designer_grid = DesignerGrid(buses, lines, units)

    initial_schedule = cfg['initial_schedule'] or {
        u.label: (u.start_mw if u.start_mw >= 0 else u.rated_mw * 0.5)
        for u in units
    }
    maintenance_units = set(cfg['maintenance_units']) | {
        u.label for u in units if not u.in_service
    }
    sim = GridSimulation(
        grid=designer_grid,
        shift_number=0,
        difficulty='standard',
        initial_schedule=initial_schedule,
        maintenance_units=maintenance_units,
        maintenance_lines=set(cfg['maintenance_lines']),
        substation_load_mw=cfg['substation_load_mw'],
        scripted_events=cfg['scripted_events'],
        start_hour=cfg['start_hour'],
        duration_hours=cfg['duration_hours'],
    )
    renderer = Renderer(display_surf, shift=1,
                        display_size=display_surf.get_size())
    renderer.set_designer_grid(designer_grid)
    _const.AGC_ENABLED = cfg['agc_enabled']
    return sim, designer_grid, renderer


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

    sim = grid = renderer = None
    state = None
    _designer = None   # GridDesigner instance — set below if booting straight
                        # into it, or lazily on entry to the DESIGNER state
    _shift_builder = None   # ShiftBuilder instance — lazily created on entry
                            # to the SHIFT_BUILDER state
    shift = 10   # default for SHIFT_SPECS.get(shift) below regardless of boot path

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
        state = sim.get_state()
    else:
        renderer   = Renderer(display_surf, shift=1,
                              display_size=display_surf.get_size())
        game_state = GameState.MAIN_MENU

    # ── Splash state ─────────────────────────────────────────────────────────
    splash_timer  = 0.0
    splash_lines  = build_splash_lines()
    splash_chars  = 0.0   # typewriter for splash

    # ── Menu state ───────────────────────────────────────────────────────────
    menu_selected = 0
    _raw = build_main_menu_items()   # [NEW GAME, CONTINUE, GRID DESIGNER, TEST GRID, SHIFT BUILDER, QUIT]
    main_menu_items = [
        _raw[0],
        ('', None),
        _raw[1],
        ('', None),
        _raw[2],
        ('', None),
        _raw[3],
        ('', None),
        _raw[4],
        ('', None),
        _raw[5],
    ]

    # ── Designer test state ──────────────────────────────────────────────────
    _designer_test_sim:      object    = None
    _designer_test_grid:     object    = None
    _designer_test_renderer: object    = None
    _designer_test_origin:   GameState = GameState.DESIGNER
    _grid_test_items:        list      = []
    _shift_json_items:       list      = []
    mode_select_items   = build_mode_select_items()
    difficulty_items    = build_difficulty_items()
    menu_title          = _menu_title_lines()
    shift_grades:  dict = {}
    shift_select_items  = build_shift_select_items(shift_grades)
    shift_select_idx    = 0

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
                        elif idx == 2: # CONTINUE — disabled
                            pass
                        elif idx == 4: # GRID DESIGNER
                            from display.designer import GridDesigner
                            _designer  = GridDesigner(display_surf)
                            game_state = GameState.DESIGNER
                        elif idx == 6: # TEST GRID
                            from data.designer_io import list_designer_grids
                            from display.menus import build_grid_test_select_items
                            _grid_test_items = build_grid_test_select_items(list_designer_grids())
                            menu_selected    = 0
                            game_state       = GameState.GRID_TEST_SELECT
                        elif idx == 8: # SHIFT BUILDER
                            from display.shift_builder import ShiftBuilder
                            _shift_builder = ShiftBuilder(display_surf)
                            game_state     = GameState.SHIFT_BUILDER
                        elif idx == 10: # QUIT
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

        # ── GRID TEST SELECT ─────────────────────────────────────────────────
        elif game_state == GameState.GRID_TEST_SELECT:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        menu_selected = _next_enabled(_grid_test_items, menu_selected, -1)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        menu_selected = _next_enabled(_grid_test_items, menu_selected, +1)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if _grid_test_items and _grid_test_items[menu_selected][1]:
                            grid_name = _grid_test_items[menu_selected][0]
                            try:
                                _designer_test_sim, _designer_test_grid, _designer_test_renderer = \
                                    _make_designer_test(display_surf, grid_name)
                                sim_accum             = 0.0
                                _designer_test_origin = GameState.GRID_TEST_SELECT
                                game_state            = GameState.DESIGNER_TEST
                            except Exception:
                                pass   # stay on list
                    elif event.key == pygame.K_ESCAPE:
                        game_state    = GameState.MAIN_MENU
                        menu_selected = 0

            renderer.tick_menu_screen(
                dt,
                title_lines=menu_title,
                items=_grid_test_items,
                selected_idx=menu_selected,
                footer_hint='[UP / DOWN]  Select    [ENTER]  Test    [ESC]  Back',
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
                            from data.shift_io import list_shift_names
                            from display.menus import build_shift_json_select_items
                            _shift_json_items = build_shift_json_select_items(list_shift_names())
                            menu_selected     = 0
                            game_state        = GameState.SHIFT_SELECT_JSON
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

        # ── SHIFT SELECT (JSON — CONTINUOUS mode) ──────────────────────────────
        elif game_state == GameState.SHIFT_SELECT_JSON:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        menu_selected = _next_enabled(_shift_json_items, menu_selected, -1)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        menu_selected = _next_enabled(_shift_json_items, menu_selected, +1)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if _shift_json_items and _shift_json_items[menu_selected][1]:
                            shift_name = _shift_json_items[menu_selected][0]
                            try:
                                _designer_test_sim, _designer_test_grid, _designer_test_renderer = \
                                    _make_shift_test(display_surf, shift_name)
                                sim_accum             = 0.0
                                _designer_test_origin = GameState.SHIFT_SELECT_JSON
                                game_state            = GameState.DESIGNER_TEST
                            except Exception:
                                pass   # stay on list
                    elif event.key == pygame.K_ESCAPE:
                        game_state    = GameState.MODE_SELECT
                        menu_selected = 1   # keep CONTINUOUS highlighted

            renderer.tick_menu_screen(
                dt,
                title_lines=menu_title,
                items=_shift_json_items,
                selected_idx=menu_selected,
                footer_hint='[UP / DOWN]  Select    [ENTER]  Play    [ESC]  Back',
            )

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

                    elif event.key == pygame.K_r and _const.EDITOR_MODE:
                        renderer.editor_key_r()

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

                    elif (event.key == pygame.K_l and not _const.EDITOR_MODE
                          and not renderer._input_active):
                        _const.VOLTAGE_COLOUR_VIEW = not _const.VOLTAGE_COLOUR_VIEW

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
                        if speed > 0.0:
                            speed = SPEED_PAUSE
                            sim_accum = 0.0
                        else:
                            speed = SPEED_NORMAL

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

            if speed > 0.0:
                sim_accum += dt
                if sim_accum >= SIM_TICK_INTERVAL_S:
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
                        # Capture grade from current sim state
                        _s = sim.get_state()
                        _fp = _s.frequency_in_bounds_pct
                        if _fp >= 95.0 and _s.load_shed_events == 0 and _s.cascade_events == 0:
                            _grade = 'EXCELLENT'
                        elif _fp >= 80.0 and _s.load_shed_events <= 1:
                            _grade = 'SATISFACTORY'
                        elif _fp >= 60.0:
                            _grade = 'MARGINAL'
                        else:
                            _grade = 'UNSATISFACTORY'
                        shift_grades[shift] = _grade

                        if shift < 10:
                            shift_select_items = build_shift_select_items(shift_grades)
                            shift_select_idx   = shift   # index N = shift N+1 (next shift)
                            game_state         = GameState.SHIFT_SELECT
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

        # ── SHIFT SELECT ─────────────────────────────────────────────────────
        elif game_state == GameState.SHIFT_SELECT:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        next_shift = max(shift_grades.keys(), default=0) + 1
                        shift = next_shift
                        sim, grid, renderer = _make_sim_and_renderer(display_surf, shift, difficulty)
                        state          = sim.get_state()
                        sim_accum      = 0.0
                        _spec          = SHIFT_SPECS.get(shift)
                        briefing_lines = build_briefing_lines(_spec) if _spec else []
                        briefing_chars = 0.0
                        game_state     = GameState.BRIEFING
                    elif event.key == pygame.K_ESCAPE:
                        game_state    = GameState.MAIN_MENU
                        menu_selected = 0

            renderer.tick_menu_screen(
                dt,
                title_lines=menu_title,
                items=shift_select_items,
                selected_idx=shift_select_idx,
                footer_hint='[ENTER]  Begin next shift    [ESC]  Main menu',
            )

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

        # ── DESIGNER ──────────────────────────────────────────────────────────
        elif game_state == GameState.DESIGNER:
            if _designer is None:
                from display.designer import GridDesigner
                _designer = GridDesigner(display_surf)

                def _on_test_request(grid_name: str) -> None:
                    nonlocal game_state, _designer_test_sim, _designer_test_grid, _designer_test_renderer, sim_accum, _designer_test_origin
                    try:
                        _designer_test_sim, _designer_test_grid, _designer_test_renderer = \
                            _make_designer_test(display_surf, grid_name)
                        sim_accum             = 0.0
                        _designer_test_origin = GameState.DESIGNER
                        game_state            = GameState.DESIGNER_TEST
                    except Exception as e:
                        _designer._set_status(f'Test failed: {e}',
                                              (255, 100, 0))

                _designer.on_test_request = _on_test_request

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if not _designer.on_key(event):
                            # Exit designer — optionally warn about unsaved changes
                            game_state    = GameState.MAIN_MENU
                            menu_selected = 0
                    else:
                        _designer.on_key(event)

                elif event.type == pygame.MOUSEMOTION:
                    _designer.on_mouse_move(
                        _designer.to_native(event.pos))

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        native = _designer.to_native(event.pos)
                        _designer.on_mouse_down(native)
                        _designer.on_click(native)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        _designer.on_mouse_up(
                            _designer.to_native(event.pos))

            _designer.tick(dt, display_surf)

        # ── SHIFT BUILDER ─────────────────────────────────────────────────────
        elif game_state == GameState.SHIFT_BUILDER:
            if _shift_builder is None:
                from display.shift_builder import ShiftBuilder
                _shift_builder = ShiftBuilder(display_surf)

            if _shift_builder.on_test_request is None:
                def _on_shift_test_request(shift_name: str) -> None:
                    nonlocal game_state, _designer_test_sim, _designer_test_grid, _designer_test_renderer, sim_accum, _designer_test_origin
                    try:
                        _designer_test_sim, _designer_test_grid, _designer_test_renderer = \
                            _make_shift_test(display_surf, shift_name)
                        sim_accum             = 0.0
                        _designer_test_origin = GameState.SHIFT_BUILDER
                        game_state             = GameState.DESIGNER_TEST
                    except Exception as e:
                        _shift_builder._set_status(f'Test failed: {e}',
                                                   (255, 100, 0))

                _shift_builder.on_test_request = _on_shift_test_request

            if _shift_builder.on_campaign_test_request is None:
                def _on_campaign_test_request(shift_number: int) -> None:
                    nonlocal game_state, _designer_test_sim, _designer_test_grid, _designer_test_renderer, sim_accum, _designer_test_origin
                    try:
                        _designer_test_sim, _designer_test_grid, _designer_test_renderer = \
                            _make_campaign_shift_test(display_surf, shift_number)
                        sim_accum             = 0.0
                        _designer_test_origin = GameState.SHIFT_BUILDER
                        game_state             = GameState.DESIGNER_TEST
                    except Exception as e:
                        _shift_builder._set_status(f'Test failed: {e}',
                                                   (255, 100, 0))

                _shift_builder.on_campaign_test_request = _on_campaign_test_request

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if not _shift_builder.on_key(event):
                            game_state    = GameState.MAIN_MENU
                            menu_selected = 0
                    else:
                        _shift_builder.on_key(event)

                elif event.type == pygame.MOUSEMOTION:
                    _shift_builder.on_mouse_move(
                        _shift_builder.to_native(event.pos))

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        native = _shift_builder.to_native(event.pos)
                        _shift_builder.on_mouse_down(native)
                        _shift_builder.on_click(native)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        _shift_builder.on_mouse_up(
                            _shift_builder.to_native(event.pos))

            _shift_builder.tick(dt, display_surf)

        # ── DESIGNER TEST ─────────────────────────────────────────────────────
        elif game_state == GameState.DESIGNER_TEST:
            _sim   = _designer_test_sim
            _rend  = _designer_test_renderer
            state  = _sim.get_state()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    mods       = pygame.key.get_mods()
                    ctrl       = bool(mods & pygame.KMOD_CTRL)
                    shift_held = bool(mods & pygame.KMOD_SHIFT)

                    if event.key == pygame.K_ESCAPE:
                        dest = _designer_test_origin
                        _designer_test_sim      = None
                        _designer_test_grid     = None
                        _designer_test_renderer = None
                        _designer_test_origin   = GameState.DESIGNER
                        if dest == GameState.GRID_TEST_SELECT:
                            from data.designer_io import list_designer_grids
                            from display.menus import build_grid_test_select_items
                            _grid_test_items = build_grid_test_select_items(list_designer_grids())
                            menu_selected    = 0
                            game_state       = GameState.GRID_TEST_SELECT
                        elif dest == GameState.SHIFT_BUILDER:
                            game_state = GameState.SHIFT_BUILDER
                        else:
                            game_state = GameState.DESIGNER

                    elif (event.key in (pygame.K_p, pygame.K_SPACE)
                          and not _rend._input_active):
                        if speed > 0.0:
                            speed = SPEED_PAUSE
                            sim_accum = 0.0
                        else:
                            speed = SPEED_NORMAL

                    elif event.key == pygame.K_1:
                        speed = SPEED_SLOW
                    elif event.key == pygame.K_2:
                        speed = SPEED_NORMAL
                    elif event.key == pygame.K_3:
                        speed = SPEED_FAST
                    elif event.key == pygame.K_4:
                        speed = SPEED_VERY_FAST

                    elif ctrl and not shift_held and event.key == pygame.K_a:
                        _const.AGC_ENABLED = not _const.AGC_ENABLED

                    elif (event.key == pygame.K_s and not _rend._input_active):
                        _rend.on_start_unit(_sim)
                    elif (event.key == pygame.K_x and not _rend._input_active):
                        _rend.on_stop_unit(_sim)
                    elif (event.key == pygame.K_t and not _rend._input_active):
                        _rend.on_trip_line(_sim)
                    elif (event.key == pygame.K_c and not _rend._input_active):
                        _rend.on_close_line(_sim)
                    elif (event.key == pygame.K_a and not _rend._input_active and not ctrl):
                        if shift_held:
                            _rend.on_ack_all_alarms(_sim)
                        else:
                            _rend.on_ack_alarm(_sim)
                    elif event.key == pygame.K_TAB and not _rend._input_active:
                        _rend.on_tab()
                    elif event.key == pygame.K_l and not _rend._input_active:
                        _const.VOLTAGE_COLOUR_VIEW = not _const.VOLTAGE_COLOUR_VIEW
                    elif event.key == pygame.K_BACKSPACE:
                        _rend.on_backspace()
                    elif event.key == pygame.K_RETURN:
                        _rend.on_enter(_sim)
                    elif (not ctrl and not shift_held
                          and event.key in (
                              pygame.K_0, pygame.K_1, pygame.K_2, pygame.K_3,
                              pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7,
                              pygame.K_8, pygame.K_9,
                          )
                          and (_rend._input_active or _rend._get_selected_unit() is not None)):
                        _rend.on_key_digit(pygame.key.name(event.key))

                elif event.type == pygame.MOUSEMOTION:
                    _rend.on_mouse_move(_to_native(event.pos, _rend._letterbox_rect, _rend._scale))

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        _rend.on_click(_to_native(event.pos, _rend._letterbox_rect, _rend._scale))

                elif event.type == pygame.MOUSEWHEEL:
                    _rend.on_scroll(event.y, _to_native(pygame.mouse.get_pos(), _rend._letterbox_rect, _rend._scale))

            if game_state == GameState.DESIGNER_TEST and speed > 0.0:
                sim_accum += dt
                if sim_accum >= SIM_TICK_INTERVAL_S:
                    _sim.tick(sim_accum * TIME_COMPRESSION * speed)
                    state = _sim.get_state()
                    sim_accum = 0.0

            if game_state == GameState.DESIGNER_TEST:
                _rend.tick(dt, state=state, speed_mult=speed)

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()
