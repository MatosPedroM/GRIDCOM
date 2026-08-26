"""
tests/test_report_screen.py

Headless smoke test for the F2 bus/line report screen (Renderer.tick_report_
screen(), on_report_toggle(), and the report branch of on_escape()/on_scroll()).
No test framework required — run directly: python tests/test_report_screen.py

Uses SDL_VIDEODRIVER=dummy so pygame can create a real display surface and a
real Renderer without an actual window — no rendered pixels are asserted on,
only Renderer state and the underlying P/Q/flow arithmetic.

See CODING_STANDARDS.md for test pattern conventions.
"""

import os
import sys

# Must be set before pygame is imported anywhere (including via src.display.renderer).
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def _build_report_fixture():
    """One slack bus, one gen bus (one online unit), one load bus, one line
    between gen and load — enough to exercise _report_bus_pq() on both a
    generation-only and a load-only bus, and to populate the line table."""
    from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
    from simulation.designer_grid import DesignerGrid

    buses = [
        DesignerBus(label='SLK', name='Slack', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=100, canvas_y=100,
                    active_from_shift=1, is_slack=True),
        DesignerBus(label='GEN', name='Gen bus', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=300, canvas_y=100,
                    active_from_shift=1, is_slack=False),
        DesignerBus(label='LD01', name='Load 1', voltage_kv=150.0,
                    bus_type='LOAD', canvas_x=300, canvas_y=300,
                    active_from_shift=1, is_slack=False, peak_load_mw=200.0),
    ]
    lines = [
        DesignerLine(label='L01', from_bus='SLK', to_bus='GEN',
                     reactance_pu=0.05, rating_mw=1500.0, voltage_kv=400.0),
        DesignerLine(label='L02', from_bus='GEN', to_bus='LD01',
                     reactance_pu=0.12, rating_mw=500.0, voltage_kv=150.0),
    ]
    units = [
        DesignerUnit(label='GENS-1', station_label='GENS', bus_label='GEN',
                     unit_type='COAL', rated_mw=300.0, min_mw=40.0,
                     inertia_h=5.0, cold_start_min=240.0,
                     q_max_mvar=150.0, q_min_mvar=-80.0, can_pump=False,
                     active_from_shift=1, description='Test unit, ONLINE via schedule'),
    ]
    grid = DesignerGrid(buses, lines, units)
    return grid


def _build_sim_and_renderer():
    """Real GridSimulation + real Renderer, both headless. Returns (sim, grid,
    renderer) with GENS-1 online at 40 MW via initial_schedule, and the
    Renderer's designer grid already wired up."""
    import pygame
    from simulation.simulation import GridSimulation
    from data.profiles import DEMAND_PROFILE_NORMALISED
    from display.renderer import Renderer

    grid = _build_report_fixture()
    substation_load_mw = {
        'LD01': {h: 200.0 * DEMAND_PROFILE_NORMALISED[h] for h in DEMAND_PROFILE_NORMALISED},
    }
    sim = GridSimulation(grid, shift_number=1, difficulty='NORMAL',
                          initial_schedule={'GENS-1': 40.0},
                          substation_load_mw=substation_load_mw)

    pygame.init()
    display_surf = pygame.display.set_mode((1920, 1080))
    renderer = Renderer(display_surf, shift=1, has_designer_grid=True)
    renderer.set_designer_grid(grid)

    return sim, grid, renderer


def test_report_toggle_and_escape() -> bool:
    """on_report_toggle()/on_escape() correctly flip _report_active, and
    on_report_toggle() resets scroll + clears sampling history on open."""
    print("test_report_toggle_and_escape...")
    all_passed = True

    try:
        sim, grid, renderer = _build_sim_and_renderer()

        try:
            assert renderer._report_active is False, \
                "Report should start inactive"

            renderer.on_report_toggle()
            assert renderer._report_active is True, \
                "on_report_toggle() should activate the report"
            assert renderer._report_scroll_buses == 0, "scroll_buses should reset to 0 on open"
            assert renderer._report_scroll_lines == 0, "scroll_lines should reset to 0 on open"
            assert renderer._report_bus_p_hist == {}, "bus P history should be cleared on open"

            renderer.on_escape()
            assert renderer._report_active is False, \
                "on_escape() should close an active report"
            assert renderer._selected_label is None, \
                "on_escape() closing the report should not touch unrelated selection state"

            # Full cycle: OFF -> toggle -> ON -> toggle -> OFF
            renderer.on_report_toggle()
            assert renderer._report_active is True
            renderer.on_report_toggle()
            assert renderer._report_active is False

            print("  toggle/escape state transitions — PASS")
        except AssertionError as e:
            print(f"  FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


def test_report_bus_pq_math() -> bool:
    """_report_bus_pq() sums per-unit output/Q at the bus and nets against
    bus_loads, matching hand-computed values for the fixture."""
    print("test_report_bus_pq_math...")
    all_passed = True

    try:
        sim, grid, renderer = _build_sim_and_renderer()

        try:
            sim.tick(60.0)  # let the unit ramp / voltage solve settle a little
            state = sim.get_state()

            gen_bus = next(b for b in grid.get_active_buses() if b.label == 'GEN')
            load_bus = next(b for b in grid.get_active_buses() if b.label == 'LD01')

            gen_p, gen_q = renderer._report_bus_pq(gen_bus, state)
            expected_gen_p = sum(state.unit_outputs_mw.get(u.label, 0.0)
                                  for u in grid.get_units_at_bus('GEN')) \
                             - state.bus_loads.get('GEN', 0.0)
            assert abs(gen_p - expected_gen_p) < 1e-6, \
                f"GEN net P mismatch: got {gen_p}, expected {expected_gen_p}"

            load_p, load_q = renderer._report_bus_pq(load_bus, state)
            expected_load_p = -state.bus_loads.get('LD01', 0.0)
            assert abs(load_p - expected_load_p) < 1e-6, \
                f"LD01 net P mismatch: got {load_p}, expected {expected_load_p}"
            assert load_p < 0.0, "A pure load bus with no local generation should net negative P"

            print(f"  GEN net P={gen_p:.1f} MW, LD01 net P={load_p:.1f} MW — PASS")
        except AssertionError as e:
            print(f"  FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


def test_report_sampling_and_trend() -> bool:
    """_report_sample() populates and prunes rolling history to roughly
    REPORT_AVG_WINDOW_MIN sim-minutes, and _report_trend() reflects it."""
    print("test_report_sampling_and_trend...")
    all_passed = True

    try:
        from simulation.constants import REPORT_AVG_WINDOW_MIN

        sim, grid, renderer = _build_sim_and_renderer()

        try:
            renderer.on_report_toggle()  # activates + clears history

            # Advance well past the averaging window, sampling every sim tick
            # (60 sim-seconds) via tick_report_screen(), mirroring how main.py
            # drives it once per real sim.tick() call.
            total_sim_minutes = REPORT_AVG_WINDOW_MIN * 3.0
            n_ticks = int(total_sim_minutes)  # 1 tick per sim-minute
            for _ in range(max(1, n_ticks)):
                sim.tick(60.0)
                state = sim.get_state()
                renderer.tick_report_screen(0.016, state=state, speed_mult=1.0)

            assert 'GEN' in renderer._report_bus_p_hist, \
                "GEN should have accumulated P history"
            hist = renderer._report_bus_p_hist['GEN']
            assert len(hist) >= 1, "History should be non-empty after several ticks"

            newest_hour = hist[-1][0]
            oldest_hour = hist[0][0]
            span_min = (newest_hour - oldest_hour) * 60.0
            assert span_min <= REPORT_AVG_WINDOW_MIN + 2.0, \
                (f"History span should be pruned to ~{REPORT_AVG_WINDOW_MIN} sim-minutes, "
                 f"got {span_min:.1f} min")

            state = sim.get_state()
            gen_bus = next(b for b in grid.get_active_buses() if b.label == 'GEN')
            gen_p, _ = renderer._report_bus_pq(gen_bus, state)
            glyph, avg = renderer._report_trend(gen_p, renderer._report_bus_p_hist.get('GEN'))
            assert glyph in ('^', 'v', '-'), f"Trend glyph should be ^/v/- once history exists, got {glyph!r}"
            assert avg is not None, "Average should be populated once history exists"

            print(f"  history span={span_min:.1f} min, trend glyph={glyph!r}, avg={avg:.1f} MW — PASS")
        except AssertionError as e:
            print(f"  FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


def test_report_scroll_independent_halves() -> bool:
    """on_scroll() routes wheel input to the buses (left) or lines (right)
    half independently, based on cursor x position, only while active."""
    print("test_report_scroll_independent_halves...")
    all_passed = True

    try:
        sim, grid, renderer = _build_sim_and_renderer()

        try:
            renderer.on_report_toggle()

            renderer.on_scroll(-1, (100, 500))    # left half -> buses
            assert renderer._report_scroll_buses == 1, \
                f"Left-half scroll should bump scroll_buses, got {renderer._report_scroll_buses}"
            assert renderer._report_scroll_lines == 0, \
                "Left-half scroll should not affect scroll_lines"

            renderer.on_scroll(-1, (1800, 500))   # right half -> lines
            assert renderer._report_scroll_lines == 1, \
                f"Right-half scroll should bump scroll_lines, got {renderer._report_scroll_lines}"
            assert renderer._report_scroll_buses == 1, \
                "Right-half scroll should not affect scroll_buses"

            print("  independent left/right scroll routing — PASS")
        except AssertionError as e:
            print(f"  FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


def test_tick_report_screen_no_crash() -> bool:
    """tick_report_screen() runs without raising, both with and without a
    live SimulationState, and leaves _display_dirty cleared like the other
    full-screen tick_*_screen() methods."""
    print("test_tick_report_screen_no_crash...")
    all_passed = True

    try:
        sim, grid, renderer = _build_sim_and_renderer()

        try:
            renderer.on_report_toggle()

            renderer.tick_report_screen(0.016, state=None, speed_mult=1.0)
            assert renderer._display_dirty is False

            sim.tick(60.0)
            renderer.tick_report_screen(0.016, state=sim.get_state(), speed_mult=1.0)
            assert renderer._display_dirty is False

            print("  tick_report_screen() runs clean with state=None and a live state — PASS")
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
        test_report_toggle_and_escape(),
        test_report_bus_pq_math(),
        test_report_sampling_and_trend(),
        test_report_scroll_independent_halves(),
        test_tick_report_screen_no_crash(),
    ]
    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    if passed < total:
        sys.exit(1)
