"""
tests/test_alarm_perf.py

Headless stress test guarding against the alarm-count FPS collapse
investigated in the "grid_medium shoulder scenario" session: a rough shift
with repeated line trips/overloads/voltage excursions raises many CRITICAL/
WARNING alarms, and two things previously scaled badly with that count —
GridSimulation._expire_alarms() never pruned acknowledged CRITICAL/WARNING
alarms (unbounded list growth for the rest of the shift), and
draw_alarm_panel() paid O(alarms) pygame.freetype.Font.get_rect() calls
(via _wrap_text) plus an O(alarms^2) scroll-window scan on every 2Hz-gated
redraw.

Uses SDL_VIDEODRIVER=dummy so pygame can create a real display surface and a
real Renderer without an actual window, loading the real grid_medium
Designer grid (46 buses / 83 lines / 14 units) so the stress test reflects
the actual reported scenario's scale.

No test framework required — run directly: python tests/test_alarm_perf.py

See CODING_STANDARDS.md for test pattern conventions.
"""

import os
import sys
import time

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def _build_sim_and_renderer():
    """Real GridSimulation + real Renderer over the real grid_medium Designer
    grid, both headless."""
    import pygame
    from simulation.simulation import GridSimulation
    from simulation.designer_grid import DesignerGrid
    from data.designer_io import load_designer_grid_named
    from display.renderer import Renderer

    buses, lines, units = load_designer_grid_named('grid_medium')
    grid = DesignerGrid(buses, lines, units)
    sim = GridSimulation(grid, shift_number=1, difficulty='NORMAL')

    pygame.init()
    display_surf = pygame.display.set_mode((1920, 1080))
    renderer = Renderer(display_surf, shift=1, has_designer_grid=True)
    renderer.set_designer_grid(grid)

    return sim, grid, renderer


def _flood_alarms(sim, count: int, ack_fraction: float = 0.6) -> None:
    """Directly raise `count` CRITICAL/WARNING alarms on a running
    GridSimulation, bypassing full physics — this is a display-cost stress
    test, not a physics test. Acknowledges ack_fraction of them (oldest
    first) so both the ack-based fade path and the still-unacked path get
    exercised, matching a real rough shift where some alarms get acked and
    some don't."""
    for i in range(count):
        priority = 'CRITICAL' if i % 3 == 0 else 'WARNING'
        sim._raise_alarm(
            priority=priority,
            message=f'Line L{i % 50:02d} overload {80 + i % 40}% loading',
            element_label=f'L{i % 50:02d}',
            detail=(f'Line L{i % 50:02d} sustained loading above threshold. '
                    f'Protection relay monitoring engaged, trip pending if '
                    f'condition persists beyond the configured delay window.'),
        )
    n_ack = int(count * ack_fraction)
    # _raise_alarm inserts newest-first; acknowledge the oldest n_ack entries
    # (the tail of the list) so the fresh/unacked alarms stay at the front,
    # same shape a real incident has (older events get acked as attention
    # moves to newer ones).
    for alarm in sim._alarms[-n_ack:] if n_ack else []:
        alarm.acknowledged = True


def test_alarm_list_stays_bounded() -> bool:
    """_expire_alarms() must cap total alarm count even when far more than
    ALARM_LIST_MAX alarms have been raised and most are still unacknowledged
    (the hard-cap backstop, not just ack-based fade)."""
    print("test_alarm_list_stays_bounded...")
    all_passed = True

    try:
        from config.constants import ALARM_LIST_MAX

        sim, grid, renderer = _build_sim_and_renderer()

        try:
            _flood_alarms(sim, count=ALARM_LIST_MAX * 3, ack_fraction=0.1)
            assert len(sim._alarms) > ALARM_LIST_MAX, \
                "Fixture should have raised more than ALARM_LIST_MAX alarms before pruning"

            sim._expire_alarms()

            assert len(sim._alarms) <= ALARM_LIST_MAX, \
                (f"_expire_alarms() should cap the list at ALARM_LIST_MAX="
                 f"{ALARM_LIST_MAX}, got {len(sim._alarms)}")

            # Newest (highest alarm_id) alarms must be the ones kept, not the
            # oldest — a hard cap that silently drops the newest/most-relevant
            # alarms during an active incident would be worse than no cap.
            kept_ids = sorted(a.alarm_id for a in sim._alarms)
            assert kept_ids[-1] == sim._alarm_id, \
                "The most recently raised alarm should survive the cap"

            print(f"  {ALARM_LIST_MAX * 3} raised -> capped to {len(sim._alarms)} "
                  f"(<= ALARM_LIST_MAX={ALARM_LIST_MAX}) — PASS")
        except AssertionError as e:
            print(f"  FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


def test_acknowledged_alarms_expire() -> bool:
    """Acknowledged CRITICAL/WARNING alarms must eventually be pruned by
    age (ALARM_FADE_CRIT_WARN_MIN), not kept forever — this was the actual
    root-cause bug (previously only INFO/TUTOR ever expired)."""
    print("test_acknowledged_alarms_expire...")
    all_passed = True

    try:
        from config.constants import ALARM_FADE_CRIT_WARN_MIN

        sim, grid, renderer = _build_sim_and_renderer()

        try:
            sim._raise_alarm(priority='CRITICAL', message='Test critical',
                             element_label=None, detail='')
            sim._raise_alarm(priority='WARNING', message='Test warning',
                             element_label=None, detail='')
            for alarm in sim._alarms:
                alarm.acknowledged = True

            sim._sim_time_min += ALARM_FADE_CRIT_WARN_MIN + 1.0
            sim._expire_alarms()

            assert len(sim._alarms) == 0, \
                (f"Acknowledged CRITICAL/WARNING alarms older than "
                 f"ALARM_FADE_CRIT_WARN_MIN should expire, {len(sim._alarms)} remain")

            print(f"  acked CRITICAL+WARNING pruned after "
                  f"{ALARM_FADE_CRIT_WARN_MIN}+1 sim-min — PASS")
        except AssertionError as e:
            print(f"  FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


def test_alarm_panel_cost_bounded_by_alarm_count() -> bool:
    """draw_alarm_panel()'s per-call cost must stay roughly flat as alarm
    count grows from a handful to several hundred — guards against the
    O(alarms) get_rect()-per-word wrap cost and the O(alarms^2) scroll-
    window scan both being reintroduced."""
    print("test_alarm_panel_cost_bounded_by_alarm_count...")
    all_passed = True

    try:
        import pygame.freetype
        from display.panels import draw_alarm_panel
        from utils.helpers import resource_path
        from config.constants import FONT_PATH_MONO_REGULAR, PANEL_ALARM_W, STRIP_HEIGHT

        sim, grid, renderer = _build_sim_and_renderer()

        font_path = resource_path(FONT_PATH_MONO_REGULAR)
        font = (pygame.freetype.Font(str(font_path), 11) if font_path.exists()
                else pygame.freetype.SysFont('monospace', 11))
        font.antialiased = False

        surf = pygame.Surface((PANEL_ALARM_W, STRIP_HEIGHT))

        def _time_draw(n_calls: int) -> float:
            # get_state() returns a cached snapshot, only rebuilt inside
            # tick() — force a fresh one (picking up alarms just raised
            # directly via _raise_alarm) with a negligible dt.
            sim.tick(0.01)
            state = sim.get_state()
            t0 = time.perf_counter()
            for _ in range(n_calls):
                draw_alarm_panel(surf, font, blink_on=True, state=state,
                                 scroll_row=0, font_scale=1.0)
            return (time.perf_counter() - t0) / n_calls * 1000.0  # ms/call

        try:
            _flood_alarms(sim, count=10, ack_fraction=0.5)
            ms_small = _time_draw(50)

            # 500 raised total — comfortably past ALARM_LIST_MAX, so this also
            # exercises the panel with a list sitting right at the hard cap
            # (the worst case draw_alarm_panel can ever actually see).
            _flood_alarms(sim, count=490, ack_fraction=0.5)
            ms_large = _time_draw(50)
            assert len(sim._alarms) >= 100, \
                f"Fixture should still have a large alarm list post-cap, got {len(sim._alarms)}"

            # No absolute-ms budget here: pygame.freetype's per-call cost
            # under SDL_VIDEODRIVER=dummy (this headless test environment)
            # is far higher than in a real windowed session — measured
            # standalone at roughly 0.5-1ms per single get_rect()/render_to()
            # call in this harness, dwarfing the algorithmic cost being
            # tested. What actually distinguishes "fixed cost per visible
            # row" (the fix) from "cost scales with total alarm count" (the
            # bug still present) is the ratio, which stays valid regardless
            # of the environment's absolute font-rendering overhead.
            print(f"  10 alarms: {ms_small:.3f}ms/call; "
                  f"{len(sim._alarms)} alarms: {ms_large:.3f}ms/call")
            assert ms_large < ms_small * 10.0 + 1.0, \
                (f"draw_alarm_panel cost grew {ms_large / max(ms_small, 1e-6):.1f}x "
                 f"going from 10 to {len(sim._alarms)} alarms — looks like an "
                 f"O(alarms) or worse regression, not the expected roughly-flat "
                 f"O(visible rows) cost")

            print("  panel draw cost stays roughly flat from 10 -> 500 alarms — PASS")
        except AssertionError as e:
            print(f"  FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


def test_renderer_tick_no_crash_under_alarm_flood() -> bool:
    """End-to-end smoke test: Renderer.tick() must run cleanly (no crash) and
    its per-frame cost must not scale up with active alarm count, once many
    alarms are active on the real grid_medium grid — exercising the full
    alarm_key dirty-gating + draw_alarm_panel path together rather than
    draw_alarm_panel in isolation.

    No absolute per-frame ms budget: pygame.freetype's per-call cost under
    SDL_VIDEODRIVER=dummy (this headless test environment) is far higher
    than in a real windowed session (see test_alarm_panel_cost_bounded_by_
    alarm_count's docstring), so 60fps-budget assertions would be
    environment noise, not a signal about the fix. The ratio between a
    small-alarm-count baseline and a large-alarm-count run is what actually
    distinguishes "flat regardless of alarm count" from a regression."""
    print("test_renderer_tick_no_crash_under_alarm_flood...")
    all_passed = True

    try:
        sim, grid, renderer = _build_sim_and_renderer()

        try:
            def _time_ticks(n_frames: int, dt: float = 1.0 / 60.0) -> float:
                # get_state() returns a cached snapshot, only rebuilt inside
                # tick() — a negligible dt forces a fresh one.
                sim.tick(0.01)
                state = sim.get_state()
                t0 = time.perf_counter()
                for _ in range(n_frames):
                    renderer.tick(dt, state=state, speed_mult=1.0)
                return (time.perf_counter() - t0) / n_frames * 1000.0, len(state.active_alarms)

            ms_baseline, n_baseline = _time_ticks(60)

            _flood_alarms(sim, count=300, ack_fraction=0.4)
            ms_flooded, n_flooded = _time_ticks(120)  # spans several 2Hz blink cycles

            print(f"  {n_baseline} alarms: {ms_baseline:.2f}ms/frame; "
                  f"{n_flooded} alarms: {ms_flooded:.2f}ms/frame")
            assert ms_flooded < ms_baseline * 5.0 + 5.0, \
                (f"Renderer.tick() cost grew {ms_flooded / max(ms_baseline, 1e-6):.1f}x "
                 f"going from {n_baseline} to {n_flooded} active alarms — expected "
                 f"roughly flat cost regardless of alarm count")

            print(f"  Renderer.tick() cost stays roughly flat under alarm flood — PASS")
        except AssertionError as e:
            print(f"  FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# TEST RUNNER
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    results = [
        test_alarm_list_stays_bounded(),
        test_acknowledged_alarms_expire(),
        test_alarm_panel_cost_bounded_by_alarm_count(),
        test_renderer_tick_no_crash_under_alarm_flood(),
    ]
    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    if passed < total:
        sys.exit(1)
