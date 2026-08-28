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
    V               Edit AVR voltage setpoint of selected generator (then digits + Enter)
    , / .           Adjust manual SVC MVAr at selected bus (down / up)
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
import datetime
from enum import Enum

# Ensure the src directory is on the path when running as `python src/main.py`
sys.path.insert(0, os.path.dirname(__file__))

import pygame
import pygame.freetype

from display.renderer import Renderer
from config.palette import COL_TEXT_BODY, COL_TEXT_SCREEN_HDR, COL_ALARM_CRIT
from display.menus import (
    build_splash_lines,
    build_main_menu_items,
    build_mode_select_items,
    build_difficulty_items,
    build_campaign_intro_screens,
    build_campaign_end_lines,
    build_menu_title_art,
    build_shift_select_items,
    build_quit_confirm_items,
)
from data.layout_override import load_layout
from data.profiles import DEMAND_PROFILE_NORMALISED
from data.campaign_save import (
    CampaignSaveState, save_campaign, load_campaign, has_campaign_save,
)
from gameplay.scoring import count_unit_trips, grade_campaign, grade_shift
from gameplay.shifts.loader import load_shift_config
from simulation.simulation import GridSimulation
from config.constants import (
    NATIVE_WIDTH, NATIVE_HEIGHT,
    TARGET_FPS, SIM_TICK_INTERVAL_S,
    TIME_COMPRESSION,
    SPEED_PAUSE, SPEED_SLOW, SPEED_NORMAL, SPEED_FAST, SPEED_VERY_FAST,
    TYPEWRITER_CHARS_PER_SEC,
    AGC_ELIGIBLE_TYPES as _AGC_ELIGIBLE_TYPES_DEFAULT,
    LANDING_FREEZE_S as _LANDING_FREEZE_S_DEFAULT,
    CAMPAIGN_STARTING_BUDGET_EUR, GRADE_TO_BUDGET_DELTA_EUR, CAMPAIGN_BUDGET_FLOOR_EUR,
)
import config.constants as _const


# ─── Game state ──────────────────────────────────────────────────────────────

class GameState(Enum):
    SPLASH            = 'splash'
    MAIN_MENU         = 'main_menu'
    MODE_SELECT       = 'mode_select'
    DIFFICULTY_SELECT = 'difficulty_select'
    CAMPAIGN_INTRO    = 'campaign_intro'
    BRIEFING          = 'briefing'
    PLANNING          = 'planning'
    PLAYING           = 'playing'
    QUIT_CONFIRM      = 'quit_confirm'
    DEBRIEF           = 'debrief'
    SHIFT_SELECT      = 'shift_select'
    CAMPAIGN_END      = 'campaign_end'
    DESIGNER          = 'designer'
    DESIGNER_TEST     = 'designer_test'
    GRID_TEST_SELECT  = 'grid_test_select'
    GRID_TEST_TIME_SELECT = 'grid_test_time_select'
    SHIFT_BUILDER     = 'shift_builder'
    SHIFT_SELECT_JSON = 'shift_select_json'


# Phase 2 speed control: F12 steps through the run speeds in order and wraps.
# Pause is deliberately NOT in this cycle — it lives on P, so the player can
# always stop the clock in one keystroke without cycling past it. The digit
# keys are left entirely to unit target entry.
_SPEED_CYCLE = (SPEED_SLOW, SPEED_NORMAL, SPEED_FAST, SPEED_VERY_FAST)


def _next_speed(current: float) -> float:
    """Return the next run speed after `current`, wrapping at the end.

    Cycling while paused resumes at the slowest speed rather than jumping
    back to whatever was running before the pause.
    """
    if current not in _SPEED_CYCLE:
        return _SPEED_CYCLE[0]
    return _SPEED_CYCLE[(_SPEED_CYCLE.index(current) + 1) % len(_SPEED_CYCLE)]

_SEP = '═' * 64


def _hm(hours: float) -> str:
    h = int(hours) % 24
    m = int((hours % 1) * 60)
    return f'{h:02d}:{m:02d}'


# ─── Menu title block ─────────────────────────────────────────────────────────

def _menu_title_lines() -> list:
    return build_menu_title_art()


# ─── Text screen content builders ────────────────────────────────────────────

def build_briefing_lines(shift_number: int) -> list:
    """Return list of (text, colour) pairs for the pre-shift briefing screen."""
    H = COL_TEXT_SCREEN_HDR
    B = COL_TEXT_BODY
    cfg = load_shift_config(shift_number)
    date_str        = cfg.get('shift_date',       'MON 07 NOV 1994')
    difficulty_label = cfg.get('difficulty_label', '')
    handover_notes   = cfg.get('handover_notes',   ())
    lines = [
        (_SEP, H),
        (' NATIONAL ENERGY CONTROL CENTRE — ASHFORD', H),
        (' SHIFT HANDOVER RECORD', H),
        (_SEP, H),
        (f' DATE: {date_str}    TIME: {_hm(cfg["start_hour"])}    SHIFT: {shift_number} OF 10', B),
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
        (f' DURATION: {int(cfg["duration_hours"]):02d}H 00M    PEAK FORECAST: {cfg["peak_demand_mw"]:.0f} MW', B),
        (_SEP, H),
    ]
    return lines


def build_debrief_lines(shift_number: int, state, failed: bool = False,
                        failed_objective: dict | None = None) -> list:
    """Return list of (text, colour) pairs for the end-of-shift report screen.

    failed: True if the shift ended early via GridSimulation.is_shift_failed()
    — either frequency pinned at the F_MIN/F_MAX hard clamp for BLACKOUT_TRIP_S,
    or a FAIL_CONDITION being met — overrides the usual metric-based assessment
    with a hard FAILED verdict.

    failed_objective: the FAIL_CONDITION that ended the shift, if any
    (GridSimulation.get_failed_objective()). None for a blackout or a clean
    run. Distinguishes "you broke a stated rule" from "the grid collapsed".

    Grading itself lives in gameplay/scoring.grade_shift() — this function
    only formats it.
    """
    H = COL_TEXT_SCREEN_HDR
    B = COL_TEXT_BODY
    C = COL_ALARM_CRIT
    cfg = load_shift_config(shift_number)
    date_str = cfg.get('shift_date', 'MON 07 NOV 1994')
    dur_h = int(cfg['duration_hours'])
    dur_m = int((cfg['duration_hours'] % 1) * 60)
    trips  = count_unit_trips(state)
    alarms = len(state.active_alarms)
    freq_pct = state.frequency_in_bounds_pct
    result = grade_shift(state, failed=failed, failed_objective=failed_objective)
    assessment = ('FAILED — SYSTEM BLACKOUT' if failed and failed_objective is None
                  else result['grade'])
    lines = [
        (_SEP, H),
        (' NATIONAL ENERGY CONTROL CENTRE — ASHFORD', H),
        (' SHIFT COMPLETION RECORD', H),
        (_SEP, H),
        (f' SHIFT: {shift_number} OF 10    DURATION: {dur_h:02d}H {dur_m:02d}M    DATE: {date_str}', B),
        (_SEP, H),
    ]
    if failed:
        lines += [
            (' FREQUENCY COLLAPSE:', H),
            ('   System frequency remained outside safe limits until protective', C),
            ('   systems isolated the network. Shift terminated early.', C),
            ('', B),
        ]
    lines += [
        (' FREQUENCY PERFORMANCE:', H),
        (f'   Within \xb10.2 Hz: {freq_pct:.1f}%    Max line loading: {state.max_line_loading_seen:.0f}%', B),
        ('', B),
        (' NETWORK SECURITY:', H),
        (f'   Cascade events: {state.cascade_events}    Load shed events: {state.load_shed_events}    Unit trips: {trips}', B),
        (f'   Minimum bus voltage: {state.min_voltage_seen:.3f} pu', B),
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
    use_planned_schedule: bool = False,
):
    """
    Build sim + renderer for a campaign shift.

    Topology/fleet always come from the shift's own shift_NN.py GRID_SOURCE
    (assets/designer_grids/<name>.json) via DesignerGrid — every campaign
    shift declares one. shift_number is passed through unchanged so
    briefing/debrief/HUD/scripted-events key off the real shift number.

    use_planned_schedule: True if the player went through and confirmed the
    Phase 1 planning screen for this shift. When True, the handover dispatch
    and full 24h hourly schedule are loaded from
    gameplay.phase1.load_schedule_json(shift) (written by
    write_schedule_json() when the plan was confirmed) instead of from the
    shift file's own INITIAL_SCHEDULE.
    """
    cfg         = load_shift_config(shift)
    grid_source = cfg.get('grid_source')
    if not grid_source:
        raise ValueError(
            f'Shift {shift} has no GRID_SOURCE — every campaign shift must '
            f'declare one (see gameplay/shifts/shift_{shift:02d}.py).'
        )

    from data.designer_io import load_designer_grid_named
    from simulation.designer_grid import DesignerGrid
    buses, lines, units = load_designer_grid_named(grid_source)
    grid = DesignerGrid(buses, lines, units)

    initial_schedule = cfg['initial_schedule']
    hourly_schedule   = None
    agc_enrolled_units: frozenset[str] | None = None
    if use_planned_schedule:
        from gameplay.phase1 import load_schedule_json
        initial_schedule, hourly_schedule, agc_enrolled_units = load_schedule_json(shift)

    # load_shift_config() already derives substation_load_mw from the grid's
    # own per-bus peak_load_mw (GRID_SOURCE shifts) or from SUBSTATION_LOAD_MW.
    substation_load_mw = cfg['substation_load_mw'] or None

    # Substation types (and the reactive devices they seed) come from the
    # grid itself — every DesignerBus always carries an explicit authored
    # substation_type (Grid Designer click-to-cycle field), so reading it
    # here keeps this in sync with the grid JSON instead of duplicating it
    # by hand in the shift file (see _make_designer_test() below, which
    # reads the same way).
    substation_types = {
        b.label: b.substation_type for b in buses
        if b.label in (substation_load_mw or {})
    } or None

    sim = GridSimulation(grid=grid, shift_number=shift, difficulty=difficulty,
                         initial_schedule=initial_schedule,
                         maintenance_units=cfg['maintenance_units'],
                         maintenance_lines=cfg['maintenance_lines'],
                         substation_load_mw=substation_load_mw,
                         substation_types=substation_types,
                         hourly_schedule=hourly_schedule)
    if substation_types:
        sim.seed_default_reactive_devices(substation_types)
        # Optional per-bus resizing of an automatic shunt bank the seeding
        # above just created (e.g. undersized so it cannot fully compensate
        # a sag alone, and a manual SVC is genuinely needed) — opt-in via
        # the shift file's SHUNT_BANK_OVERRIDES, empty for every shift that
        # declares none.
        for _bus, _overrides in cfg.get('shunt_bank_overrides', {}).items():
            sim.resize_shunt_bank(_bus, max_steps=_overrides.get('max_steps'),
                                  mvar_per_step=_overrides.get('mvar_per_step'),
                                  initial_step=_overrides.get('initial_step'))

    # Optional per-unit reactive-power target at handover, overriding the
    # default 0.0 MVAr — opt-in via the shift file's INITIAL_Q_MVAR, empty
    # for every shift that declares none.
    for _unit, _q_mvar in cfg.get('initial_q_mvar', {}).items():
        sim.set_unit_q_target(_unit, _q_mvar)

    renderer = Renderer(display_surf, shift=shift,
                        display_size=display_surf.get_size(),
                        has_designer_grid=True)
    renderer.set_designer_grid(grid)
    _const.AGC_ENABLED = cfg['agc_enabled']
    _const.FREQ_TOLERANCE_MULT = cfg.get('freq_tolerance_mult', 1.0)
    _const.AGC_SPEED_MULT = cfg.get('agc_speed_mult', 1.0)
    _const.LANDING_FREEZE_S = cfg.get('landing_freeze_s', _LANDING_FREEZE_S_DEFAULT)

    # Per-unit AGC enrollment chosen on the Planning screen (Phase 1) —
    # invert into the exclusion set FleetModel already supports (same
    # mechanism the AGC_EXCLUDE_UNITS scripted action uses mid-shift), so
    # only units the player actually enrolled regulate, not the whole
    # eligible type. AGC_ELIGIBLE_TYPES itself is fixed campaign-wide (CCGT +
    # HYDRO, never per-shift), so this only ever narrows within that fixed
    # set. Shifts without a planning session keep today's behavior
    # unchanged (whole eligible type regulates, no exclusions).
    if agc_enrolled_units is not None:
        eligible_labels = {
            u.label for u in grid.get_active_units()
            if u.unit_type in _const.AGC_ELIGIBLE_TYPES
        }
        sim.set_agc_excluded_units(eligible_labels - agc_enrolled_units)

    return sim, grid, renderer


def _make_designer_test(
    display_surf: pygame.Surface,
    grid_name: str,
    start_hour: float = 0.0,
    duration_hours: float = 24.0,
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
    # Read each bus's own authored substation_type (Grid Designer, click-to-cycle
    # field) directly — every bus always has an explicit value (defaulting to
    # MIXED), so there is no hole left to fill with a random assignment.
    substation_types = {
        b.label: b.substation_type for b in buses if b.label in substation_load_mw
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
        substation_types=substation_types,
        start_hour=start_hour,
        duration_hours=duration_hours,
    )
    sim.seed_default_reactive_devices(substation_types)
    # Renderer uses shift=1 as a title-bar sentinel only — the canvas comes
    # entirely from set_designer_grid() below (has_designer_grid=True skips
    # the topology.py seed), simulation state (frequency, dispatch, alarms)
    # is live regardless.
    renderer = Renderer(display_surf, shift=1,
                        display_size=display_surf.get_size(),
                        has_designer_grid=True)
    renderer.set_designer_grid(designer_grid)
    _const.AGC_ENABLED = True
    _const.FREQ_TOLERANCE_MULT = 1.0
    _const.AGC_ELIGIBLE_TYPES = _AGC_ELIGIBLE_TYPES_DEFAULT
    _const.AGC_SPEED_MULT = 1.0
    _const.LANDING_FREEZE_S = _LANDING_FREEZE_S_DEFAULT
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
                        display_size=display_surf.get_size(),
                        has_designer_grid=True)
    renderer.set_designer_grid(designer_grid)
    _const.AGC_ENABLED = cfg['agc_enabled']
    _const.FREQ_TOLERANCE_MULT = cfg.get('freq_tolerance_mult', 1.0)
    _const.AGC_SPEED_MULT = cfg.get('agc_speed_mult', 1.0)
    _const.LANDING_FREEZE_S = cfg.get('landing_freeze_s', _LANDING_FREEZE_S_DEFAULT)
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
    pygame.mixer.init()

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
    _planning_screen = None   # PlanningScreen instance — lazily created on entry
                              # to the PLANNING state
    _planning_model  = None   # PlanningModel for the PLANNING state (Phase 1) —
                              # built in BRIEFING's completion handler when the
                              # target shift's config has uses_planning=True
    shift = 1

    # Placeholder canvas — never actually drawn (tick_menu_screen() doesn't
    # touch the grid canvas), replaced the moment a real shift/grid loads.
    # has_designer_grid=True + an empty DesignerGrid avoids needing any real
    # topology at all just to get the loop started.
    from simulation.designer_grid import DesignerGrid
    renderer   = Renderer(display_surf, shift=1,
                          display_size=display_surf.get_size(),
                          has_designer_grid=True)
    renderer.set_designer_grid(DesignerGrid([], [], []))
    game_state = GameState.MAIN_MENU

    # ── Splash state ─────────────────────────────────────────────────────────
    splash_timer  = 0.0
    splash_lines  = build_splash_lines()
    splash_chars  = 0.0   # typewriter for splash

    # ── Menu state ───────────────────────────────────────────────────────────
    menu_selected = 0
    _raw = build_main_menu_items(has_save=has_campaign_save())   # [NEW GAME, CONTINUE, GRID DESIGNER, TEST GRID, SHIFT BUILDER, QUIT]
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

    # Abandon-shift confirmation (Escape from PLAYING with nothing selected).
    # _quit_confirm_speed remembers the run speed so RESUME restores it.
    _quit_confirm_items = build_quit_confirm_items()
    _quit_confirm_speed = SPEED_NORMAL

    # ── Designer test state ──────────────────────────────────────────────────
    _designer_test_sim:      object    = None
    _designer_test_grid:     object    = None
    _designer_test_renderer: object    = None
    _designer_test_origin:   GameState = GameState.DESIGNER
    _grid_test_items:        list      = []
    _grid_test_error:        str       = ''
    _grid_test_pending_name: str       = ''       # grid chosen, awaiting time-window pick
    _time_window_origin:     GameState = GameState.GRID_TEST_SELECT
    _shift_json_items:       list      = []
    mode_select_items   = build_mode_select_items()
    difficulty_items    = build_difficulty_items()
    menu_title          = _menu_title_lines()
    shift_grades:  dict = {}
    shift_select_items  = build_shift_select_items(shift_grades)
    shift_select_idx    = 0

    # Persistent campaign budget (EUR) — carries forward across shifts via
    # data/campaign_save.py, rather than resetting every Phase 1 plan.
    # Reset to CAMPAIGN_STARTING_BUDGET_EUR at DIFFICULTY_SELECT (new
    # campaign) or restored from disk at MAIN_MENU's CONTINUE (loaded
    # campaign). See gameplay/phase1.py's build_planning_model().
    campaign_budget: float = CAMPAIGN_STARTING_BUDGET_EUR

    # ── Campaign intro ───────────────────────────────────────────────────────
    intro_screens    = build_campaign_intro_screens()
    intro_screen_idx = 0
    intro_chars      = 0.0
    difficulty       = 'standard'

    # ── Briefing / debrief state ─────────────────────────────────────────────
    briefing_lines = build_briefing_lines(shift)
    briefing_chars = 0.0
    debrief_lines: list = []
    debrief_chars  = 0.0

    # ── Campaign end ─────────────────────────────────────────────────────────
    campaign_end_lines: list = []
    campaign_end_chars  = 0.0
    campaign_start_time = pygame.time.get_ticks()   # ms — for total watch time
    # Wall-clock timestamp of campaign start, display-only, saved/restored
    # with the campaign (unlike campaign_start_time above, which is a
    # pygame tick count only meaningful within the current process).
    campaign_start_time_iso = datetime.datetime.now().isoformat()

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
                        elif idx == 2: # CONTINUE — load saved campaign
                            saved                   = load_campaign()
                            difficulty              = saved.difficulty
                            shift_grades            = saved.shift_grades
                            campaign_budget         = saved.budget_eur
                            campaign_start_time_iso = saved.campaign_start_time_iso
                            campaign_start_time     = pygame.time.get_ticks()
                            shift_select_items      = build_shift_select_items(shift_grades)
                            shift_select_idx        = max(shift_grades.keys(), default=0)
                            game_state              = GameState.SHIFT_SELECT
                        elif idx == 4: # GRID DESIGNER
                            from display.designer import GridDesigner
                            _designer  = GridDesigner(display_surf)
                            game_state = GameState.DESIGNER
                        elif idx == 6: # TEST GRID
                            from data.designer_io import list_designer_grids
                            from display.menus import build_grid_test_select_items
                            _grid_test_items = build_grid_test_select_items(list_designer_grids())
                            menu_selected    = 0
                            _grid_test_error = ''
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
                            _grid_test_pending_name = _grid_test_items[menu_selected][0]
                            _time_window_origin     = GameState.GRID_TEST_SELECT
                            menu_selected            = 0
                            _grid_test_error         = ''
                            game_state               = GameState.GRID_TEST_TIME_SELECT
                    elif event.key == pygame.K_ESCAPE:
                        game_state    = GameState.MAIN_MENU
                        menu_selected = 0
                        _grid_test_error = ''

            _grid_test_footer = ('[UP / DOWN]  Select    [ENTER]  Test    [ESC]  Back'
                                 if not _grid_test_error else _grid_test_error)
            renderer.tick_menu_screen(
                dt,
                title_lines=menu_title,
                items=_grid_test_items,
                selected_idx=menu_selected,
                footer_hint=_grid_test_footer,
            )

        # ── GRID TEST TIME WINDOW SELECT ────────────────────────────────────
        elif game_state == GameState.GRID_TEST_TIME_SELECT:
            from display.menus import build_time_window_select_items, TIME_WINDOWS
            _time_window_items = build_time_window_select_items()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        menu_selected = _next_enabled(_time_window_items, menu_selected, -1)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        menu_selected = _next_enabled(_time_window_items, menu_selected, +1)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        _, start_hour, duration_hours = TIME_WINDOWS[menu_selected]
                        try:
                            _designer_test_sim, _designer_test_grid, _designer_test_renderer = \
                                _make_designer_test(display_surf, _grid_test_pending_name,
                                                    start_hour, duration_hours)
                            sim_accum             = 0.0
                            speed                 = SPEED_NORMAL
                            _designer_test_origin = _time_window_origin
                            game_state            = GameState.DESIGNER_TEST
                            _grid_test_error       = ''
                        except Exception as e:
                            _grid_test_error = f'Test failed: {e}'
                    elif event.key == pygame.K_ESCAPE:
                        game_state    = _time_window_origin
                        menu_selected = 0
                        _grid_test_error = ''

            _time_window_footer = ('[UP / DOWN]  Select    [ENTER]  Test    [ESC]  Back'
                                   if not _grid_test_error else _grid_test_error)
            renderer.tick_menu_screen(
                dt,
                title_lines=menu_title,
                items=_time_window_items,
                selected_idx=menu_selected,
                footer_hint=_time_window_footer,
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
                        # sim/grid deliberately NOT built here — for a
                        # USES_PLANNING shift the real dispatch only exists
                        # once the Phase 1 plan is confirmed, so building
                        # from the shift's default INITIAL_SCHEDULE here
                        # would be thrown away unused the moment BRIEFING
                        # routes to PLANNING. Built once, for real, in
                        # BRIEFING's completion handler below (either
                        # directly, for non-planning shifts, or via
                        # _on_plan_complete after Phase 1 confirms). The
                        # existing renderer (built at startup, shift-
                        # agnostic for menu/text screens) carries through
                        # unchanged.
                        campaign_start_time = pygame.time.get_ticks()
                        # New campaign begins here — fresh budget, no prior
                        # shift grades. A loaded campaign (MAIN_MENU's
                        # CONTINUE) skips DIFFICULTY_SELECT entirely and
                        # goes straight to SHIFT_SELECT, so this branch only
                        # ever runs for a genuinely new campaign.
                        shift_grades             = {}
                        campaign_budget          = CAMPAIGN_STARTING_BUDGET_EUR
                        campaign_start_time_iso  = datetime.datetime.now().isoformat()
                        # Campaign intro (6 typewriter screens, see
                        # build_campaign_intro_screens()) plays first; its own
                        # completion handler sets shift = 1 and routes to
                        # BRIEFING once the player has clicked through it.
                        intro_screen_idx = 0
                        intro_chars      = 0.0
                        game_state = GameState.CAMPAIGN_INTRO
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
                                speed                 = SPEED_NORMAL
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
                            briefing_lines = build_briefing_lines(shift)
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
                        if load_shift_config(shift).get('uses_planning'):
                            from gameplay.phase1 import build_planning_model
                            _planning_model = build_planning_model(
                                shift, starting_budget_eur=campaign_budget,
                                difficulty=difficulty,
                            )
                            game_state = GameState.PLANNING
                        else:
                            sim, grid, renderer = _make_sim_and_renderer(
                                display_surf, shift=shift, difficulty=difficulty,
                            )
                            state      = sim.get_state()
                            sim_accum  = 0.0
                            speed      = SPEED_PAUSE
                            game_state = GameState.PLAYING
            briefing_chars = min(briefing_chars + TYPEWRITER_CHARS_PER_SEC * dt,
                                 float(total) + 1)
            renderer.tick_text_screen(dt, briefing_lines, int(briefing_chars))

        # ── PLANNING (Phase 1 — pre-shift unit scheduling) ──────────────────────
        # Entered from BRIEFING when the shift's config declares
        # uses_planning (shift_NN.py's USES_PLANNING = True). Other shifts
        # skip straight to PLAYING as before.
        elif game_state == GameState.PLANNING:
            if _planning_screen is None:
                from display.planning import PlanningScreen
                _planning_screen = PlanningScreen(display_surf, _planning_model, shift_number=shift)

            if _planning_screen.on_plan_complete is None:
                def _on_plan_complete(model) -> None:
                    nonlocal game_state, sim, grid, renderer, state, sim_accum, speed, _planning_screen, campaign_budget
                    from gameplay.phase1 import write_schedule_json
                    write_schedule_json(model, shift)
                    # Confirmed plan's actual EUR spend comes out of the
                    # persistent campaign budget now, not just the in-screen
                    # display — carried forward at the next debrief's save
                    # (see the DEBRIEF handler below).
                    campaign_budget = max(
                        CAMPAIGN_BUDGET_FLOOR_EUR, campaign_budget - model.total_cost()
                    )
                    sim, grid, renderer = _make_sim_and_renderer(
                        display_surf, shift=shift, difficulty=difficulty,
                        use_planned_schedule=True,
                    )
                    state      = sim.get_state()
                    sim_accum  = 0.0
                    speed      = SPEED_PAUSE
                    _planning_screen = None
                    game_state = GameState.PLAYING

                _planning_screen.on_plan_complete = _on_plan_complete

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if not _planning_screen.on_key(event):
                            game_state    = GameState.MAIN_MENU
                            menu_selected = 0
                    else:
                        _planning_screen.on_key(event)

                elif event.type == pygame.MOUSEMOTION:
                    _planning_screen.on_mouse_move(
                        _planning_screen.to_native(event.pos))

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        native = _planning_screen.to_native(event.pos)
                        _planning_screen.on_mouse_down(native)
                        _planning_screen.on_click(native)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        _planning_screen.on_mouse_up(
                            _planning_screen.to_native(event.pos))

            if _planning_screen is not None:
                _planning_screen.tick(dt, display_surf)

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

                    # Escape backs out one level at a time; with nothing left to
                    # close it asks before abandoning the shift, rather than
                    # dropping the player straight to the menu mid-run.
                    # (Q is no longer an alias — it now sets reactive power.)
                    elif event.key == pygame.K_ESCAPE:
                        if _const.EDITOR_MODE:
                            _const.EDITOR_MODE = False
                        elif renderer._report_active or renderer._report3_active:
                            renderer.on_escape()
                        elif (renderer._selected_label is not None
                              or renderer._input_active
                              or renderer._setpoint_active
                              or renderer._adjust_active):
                            renderer.on_escape()
                        else:
                            _quit_confirm_speed = speed
                            speed         = SPEED_PAUSE
                            sim_accum     = 0.0
                            menu_selected = 0
                            game_state    = GameState.QUIT_CONFIRM

                    elif ctrl and shift_held and event.key == pygame.K_e:
                        _const.EDITOR_MODE = not _const.EDITOR_MODE

                    # Speed cycle: F12 steps 1x -> 3x -> 10x -> 0.25x -> ...
                    elif event.key == pygame.K_F12 and not _const.EDITOR_MODE:
                        speed = _next_speed(speed)

                    elif event.key == pygame.K_s and _const.EDITOR_MODE:
                        renderer.save_layout()

                    elif event.key == pygame.K_r and _const.EDITOR_MODE:
                        renderer.editor_key_r()

                    # S/X are dual-purpose based on current selection:
                    # start/stop the selected unit, or restore/shed load in
                    # 25% steps at the selected substation — S always
                    # increases (start unit / restore load), X always
                    # decreases (stop unit / shed load), mirroring the
                    # unit binding exactly rather than a single toggle key.
                    elif (event.key == pygame.K_s and not _const.EDITOR_MODE
                          and not renderer._input_active):
                        if renderer._get_selected_bus() is not None:
                            renderer.on_restore_load(sim)
                        else:
                            renderer.on_start_unit(sim)

                    elif (event.key == pygame.K_x and not _const.EDITOR_MODE
                          and not renderer._input_active):
                        if renderer._get_selected_bus() is not None:
                            renderer.on_shed_load(sim)
                        else:
                            renderer.on_stop_unit(sim)

                    elif (event.key == pygame.K_m and not _const.EDITOR_MODE
                          and not renderer._input_active):
                        renderer.on_toggle_auto_mode(sim)

                    elif (event.key == pygame.K_t and not _const.EDITOR_MODE
                          and not renderer._input_active):
                        renderer.on_trip_line(sim)

                    elif (event.key == pygame.K_c and not _const.EDITOR_MODE
                          and not renderer._input_active):
                        renderer.on_close_line(sim)

                    elif ctrl and not shift_held and event.key == pygame.K_a:
                        _const.AGC_ENABLED = not _const.AGC_ENABLED

                    elif ctrl and event.key == pygame.K_n and _const.DEBUG_EVENTS and not _const.EDITOR_MODE:
                        debrief_lines = build_debrief_lines(shift, sim.get_state())
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

                    elif (event.key == pygame.K_F2 and not _const.EDITOR_MODE
                          and not renderer._input_active):
                        renderer.on_report_toggle()

                    elif (event.key == pygame.K_F3 and not _const.EDITOR_MODE
                          and not renderer._input_active):
                        renderer.on_report3_toggle()

                    elif (event.key == pygame.K_COMMA and not _const.EDITOR_MODE
                          and not renderer._input_active and not renderer._setpoint_active):
                        renderer.on_svc_adjust(sim, -1)

                    elif (event.key == pygame.K_PERIOD and not _const.EDITOR_MODE
                          and not renderer._input_active and not renderer._setpoint_active):
                        renderer.on_svc_adjust(sim, +1)

                    # W = active power (MW), Q = reactive power (AVR setpoint).
                    # Adjacent on QWERTY, and P/Q is the standard engineering
                    # pairing. Both arm a nudge mode driven by UP/DOWN below;
                    # arming one disarms the other so the arrows are never
                    # ambiguous. Typing an exact value still works via Enter.
                    elif (event.key == pygame.K_w and not _const.EDITOR_MODE
                          and not renderer._input_active and not renderer._setpoint_active
                          and not ctrl):
                        renderer.on_adjust_toggle()

                    elif (event.key == pygame.K_q and not _const.EDITOR_MODE
                          and not renderer._input_active and not ctrl):
                        renderer.on_setpoint_adjust_toggle()

                    elif (event.key == pygame.K_UP and not _const.EDITOR_MODE
                          and renderer._setpoint_adjust_active):
                        renderer.on_setpoint_adjust(sim, +1, fast=ctrl)

                    elif (event.key == pygame.K_DOWN and not _const.EDITOR_MODE
                          and renderer._setpoint_adjust_active):
                        renderer.on_setpoint_adjust(sim, -1, fast=ctrl)

                    elif (event.key == pygame.K_UP and not _const.EDITOR_MODE
                          and renderer._adjust_active):
                        renderer.on_target_adjust(sim, +1, fast=ctrl)

                    elif (event.key == pygame.K_DOWN and not _const.EDITOR_MODE
                          and renderer._adjust_active):
                        renderer.on_target_adjust(sim, -1, fast=ctrl)

                    elif event.key == pygame.K_d:
                        _const.DEBUG_DISPLAY = not _const.DEBUG_DISPLAY

                    elif (not _const.EDITOR_MODE and not ctrl and not shift_held
                          and event.key in (
                              pygame.K_0, pygame.K_1, pygame.K_2, pygame.K_3,
                              pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7,
                              pygame.K_8, pygame.K_9,
                          )
                          and renderer._setpoint_active):
                        renderer.on_setpoint_digit(pygame.key.name(event.key))

                    elif (event.key == pygame.K_MINUS and not _const.EDITOR_MODE
                          and not ctrl and not shift_held and renderer._setpoint_active):
                        renderer.on_setpoint_minus()

                    elif (not _const.EDITOR_MODE and not ctrl and not shift_held
                          and event.key in (
                              pygame.K_0, pygame.K_1, pygame.K_2, pygame.K_3,
                              pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7,
                              pygame.K_8, pygame.K_9,
                          )
                          and (renderer._input_active or renderer._get_selected_unit() is not None)):
                        renderer.on_key_digit(pygame.key.name(event.key))

                    elif (event.key == pygame.K_p
                          and not _const.EDITOR_MODE and not renderer._input_active):
                        if speed > 0.0:
                            speed = SPEED_PAUSE
                            sim_accum = 0.0
                        else:
                            speed = SPEED_NORMAL

                    elif (event.key == pygame.K_SPACE
                          and not _const.EDITOR_MODE and not renderer._input_active):
                        renderer.on_silence_alarm()

                    elif not _const.EDITOR_MODE and event.key == pygame.K_BACKSPACE:
                        if renderer._setpoint_active:
                            renderer.on_setpoint_backspace()
                        else:
                            renderer.on_backspace()

                    elif not _const.EDITOR_MODE and event.key == pygame.K_RETURN:
                        if renderer._setpoint_active:
                            renderer.on_setpoint_enter(sim)
                        else:
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
                sim.tick_real_seconds(dt)
                sim_accum += dt
                if sim_accum >= SIM_TICK_INTERVAL_S:
                    sim.tick(sim_accum * TIME_COMPRESSION * speed)
                    state = sim.get_state()
                    sim_accum = 0.0

            if renderer._report_active:
                renderer.tick_report_screen(dt, state=state, speed_mult=speed)
            elif renderer._report3_active:
                renderer.tick_report3_screen(dt, state=state, speed_mult=speed)
            else:
                renderer.tick(dt, state=state, speed_mult=speed)

            if sim.is_shift_complete():
                debrief_lines = build_debrief_lines(
                    shift, sim.get_state(),
                    failed=sim.is_shift_failed(),
                    failed_objective=sim.get_failed_objective(),
                )
                game_state    = GameState.DEBRIEF
                debrief_chars = 0.0

        # ── QUIT CONFIRM ─────────────────────────────────────────────────────
        # Guards against losing a shift to a stray Escape. The simulation is
        # paused (not torn down) while this is up, so RESUME returns to the
        # shift exactly where it was left.
        elif game_state == GameState.QUIT_CONFIRM:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        menu_selected = _next_enabled(_quit_confirm_items, menu_selected, -1)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        menu_selected = _next_enabled(_quit_confirm_items, menu_selected, +1)
                    elif event.key == pygame.K_ESCAPE:
                        speed      = _quit_confirm_speed
                        game_state = GameState.PLAYING
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if menu_selected == 0:      # RESUME SHIFT
                            speed      = _quit_confirm_speed
                            game_state = GameState.PLAYING
                        else:                        # ABANDON SHIFT
                            game_state    = GameState.MAIN_MENU
                            menu_selected = 0

            renderer.tick_menu_screen(
                dt,
                title_lines=[
                    (_SEP, COL_TEXT_SCREEN_HDR),
                    (' ABANDON SHIFT?', COL_TEXT_SCREEN_HDR),
                    (_SEP, COL_TEXT_SCREEN_HDR),
                    ('', COL_TEXT_BODY),
                    (' The shift is still running. Leaving now discards it —', COL_TEXT_BODY),
                    (' there is no save, and it will not be graded.', COL_TEXT_BODY),
                    ('', COL_TEXT_BODY),
                ],
                items=_quit_confirm_items,
                selected_idx=menu_selected,
                footer_hint='[UP / DOWN]  Navigate    [ENTER]  Select    [ESC]  Resume',
            )

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
                        # Capture grade from current sim state. Same rubric the
                        # debrief screen just displayed — one implementation,
                        # in gameplay/scoring.py.
                        this_grade = grade_shift(
                            sim.get_state(),
                            failed=sim.is_shift_failed(),
                            failed_objective=sim.get_failed_objective(),
                        )['grade']
                        shift_grades[shift] = this_grade

                        # Persistent campaign budget: grade adds a bonus,
                        # or for FAILED a flat penalty (see constants.py's
                        # GRADE_TO_BUDGET_DELTA_EUR) — floored so even a
                        # failed shift can never make a later shift's plan
                        # mechanically impossible.
                        campaign_budget = max(
                            CAMPAIGN_BUDGET_FLOOR_EUR,
                            campaign_budget + GRADE_TO_BUDGET_DELTA_EUR.get(this_grade, 0.0),
                        )
                        save_campaign(CampaignSaveState(
                            difficulty=difficulty,
                            shift_grades=dict(shift_grades),
                            budget_eur=campaign_budget,
                            campaign_start_time_iso=campaign_start_time_iso,
                        ))

                        if shift < 10:
                            shift_select_items = build_shift_select_items(shift_grades)
                            shift_select_idx   = shift   # index N = shift N+1 (next shift)
                            game_state         = GameState.SHIFT_SELECT
                        else:
                            watch_s = (pygame.time.get_ticks() - campaign_start_time) / 1000.0
                            campaign_end_lines = build_campaign_end_lines(
                                shifts_completed=10,
                                watch_time_s=watch_s,
                                grade=grade_campaign(shift_grades),
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
                        briefing_lines = build_briefing_lines(shift)
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

            if _designer.on_test_request is None:
                def _on_test_request(grid_name: str) -> None:
                    nonlocal game_state, _grid_test_pending_name, _time_window_origin, menu_selected, _grid_test_error
                    _grid_test_pending_name = grid_name
                    _time_window_origin     = GameState.DESIGNER
                    menu_selected            = 0
                    _grid_test_error         = ''
                    game_state               = GameState.GRID_TEST_TIME_SELECT

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
                    nonlocal game_state, _designer_test_sim, _designer_test_grid, _designer_test_renderer, sim_accum, _designer_test_origin, speed
                    try:
                        _designer_test_sim, _designer_test_grid, _designer_test_renderer = \
                            _make_shift_test(display_surf, shift_name)
                        sim_accum             = 0.0
                        speed                 = SPEED_NORMAL
                        _designer_test_origin = GameState.SHIFT_BUILDER
                        game_state             = GameState.DESIGNER_TEST
                    except Exception as e:
                        _shift_builder._set_status(f'Test failed: {e}',
                                                   (255, 100, 0))

                _shift_builder.on_test_request = _on_shift_test_request

            if _shift_builder.on_campaign_test_request is None:
                def _on_campaign_test_request(shift_number: int) -> None:
                    nonlocal game_state, _designer_test_sim, _designer_test_grid, _designer_test_renderer, sim_accum, _designer_test_origin, speed
                    try:
                        _designer_test_sim, _designer_test_grid, _designer_test_renderer = \
                            _make_campaign_shift_test(display_surf, shift_number)
                        sim_accum             = 0.0
                        speed                 = SPEED_NORMAL
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
                        if _rend._report_active or _rend._report3_active:
                            _rend.on_escape()
                        else:
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

                    elif (event.key == pygame.K_p
                          and not _rend._input_active):
                        if speed > 0.0:
                            speed = SPEED_PAUSE
                            sim_accum = 0.0
                        else:
                            speed = SPEED_NORMAL

                    elif (event.key == pygame.K_SPACE
                          and not _rend._input_active):
                        _rend.on_silence_alarm()

                    elif event.key == pygame.K_F2 and not _rend._input_active:
                        _rend.on_report_toggle()

                    elif event.key == pygame.K_F3 and not _rend._input_active:
                        _rend.on_report3_toggle()

                    elif ctrl and not shift_held and event.key == pygame.K_a:
                        _const.AGC_ENABLED = not _const.AGC_ENABLED

                    elif (event.key == pygame.K_s and not _rend._input_active):
                        if _rend._get_selected_bus() is not None:
                            _rend.on_restore_load(_sim)
                        else:
                            _rend.on_start_unit(_sim)
                    elif (event.key == pygame.K_x and not _rend._input_active):
                        if _rend._get_selected_bus() is not None:
                            _rend.on_shed_load(_sim)
                        else:
                            _rend.on_stop_unit(_sim)
                    elif (event.key == pygame.K_m and not _rend._input_active):
                        _rend.on_toggle_auto_mode(_sim)
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
                    elif (event.key == pygame.K_COMMA and not _rend._input_active
                          and not _rend._setpoint_active):
                        _rend.on_svc_adjust(_sim, -1)
                    elif (event.key == pygame.K_PERIOD and not _rend._input_active
                          and not _rend._setpoint_active):
                        _rend.on_svc_adjust(_sim, +1)

                    # W = active power (MW), Q = reactive power (AVR setpoint).
                    # Mirrors the PLAYING loop's binding — see main.py's PLAYING
                    # KEYDOWN handling for the full rationale.
                    elif (event.key == pygame.K_w and not _const.EDITOR_MODE
                          and not _rend._input_active and not _rend._setpoint_active
                          and not ctrl):
                        _rend.on_adjust_toggle()

                    elif (event.key == pygame.K_q and not _const.EDITOR_MODE
                          and not _rend._input_active and not ctrl):
                        _rend.on_setpoint_adjust_toggle()

                    elif (event.key == pygame.K_UP and not _const.EDITOR_MODE
                          and _rend._setpoint_adjust_active):
                        _rend.on_setpoint_adjust(_sim, +1, fast=ctrl)

                    elif (event.key == pygame.K_DOWN and not _const.EDITOR_MODE
                          and _rend._setpoint_adjust_active):
                        _rend.on_setpoint_adjust(_sim, -1, fast=ctrl)

                    elif (event.key == pygame.K_UP and not _const.EDITOR_MODE
                          and _rend._adjust_active):
                        _rend.on_target_adjust(_sim, +1, fast=ctrl)

                    elif (event.key == pygame.K_DOWN and not _const.EDITOR_MODE
                          and _rend._adjust_active):
                        _rend.on_target_adjust(_sim, -1, fast=ctrl)

                    elif (event.key == pygame.K_v and not _rend._input_active
                          and not ctrl):
                        _rend.on_setpoint_toggle()
                    elif event.key == pygame.K_BACKSPACE:
                        if _rend._setpoint_active:
                            _rend.on_setpoint_backspace()
                        else:
                            _rend.on_backspace()
                    elif event.key == pygame.K_RETURN:
                        if _rend._setpoint_active:
                            _rend.on_setpoint_enter(_sim)
                        else:
                            _rend.on_enter(_sim)
                    elif (not ctrl and not shift_held
                          and event.key in (
                              pygame.K_0, pygame.K_1, pygame.K_2, pygame.K_3,
                              pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7,
                              pygame.K_8, pygame.K_9, pygame.K_PERIOD,
                          )
                          and _rend._setpoint_active):
                        ch = '.' if event.key == pygame.K_PERIOD else pygame.key.name(event.key)
                        _rend.on_setpoint_digit(ch)
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
                _sim.tick_real_seconds(dt)
                sim_accum += dt
                if sim_accum >= SIM_TICK_INTERVAL_S:
                    _sim.tick(sim_accum * TIME_COMPRESSION * speed)
                    state = _sim.get_state()
                    sim_accum = 0.0

            if game_state == GameState.DESIGNER_TEST:
                if _rend._report_active:
                    _rend.tick_report_screen(dt, state=state, speed_mult=speed)
                elif _rend._report3_active:
                    _rend.tick_report3_screen(dt, state=state, speed_mult=speed)
                else:
                    _rend.tick(dt, state=state, speed_mult=speed)

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()
