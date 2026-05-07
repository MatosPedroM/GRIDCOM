"""
tests/test_simulation.py

GRIDCOM simulation test suite.
No test framework required — run directly: python tests/test_simulation.py

Each test function prints PASS / FAIL / ERROR and returns True/False.
Script exits with code 1 if any test fails.

See CODING_STANDARDS.md for test pattern conventions.
"""

import sys
import os

# Ensure src/ is on the path so simulation and data packages resolve.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 TESTS — Network Data Model
# ─────────────────────────────────────────────────────────────────────────────

def test_grid_loads() -> bool:
    """
    Verify the Grid class loads the correct number of buses, lines, and units
    for shifts 1, 3, and 5 (the three grid-size tiers).

    Also verifies all 47 units load without error across the full fleet.
    """
    print("test_grid_loads...")
    all_passed = True

    try:
        from simulation.grid import Grid
        from data.topology import BUSES, LINES
        from data.fleet import UNITS

        # ── Shift 1: south sub-grid (12 buses) ───────────────────────────
        try:
            g1 = Grid(1)
            buses1 = g1.get_active_buses()
            lines1 = g1.get_active_lines()
            units1 = g1.get_active_units()

            expected_buses_1 = sum(1 for b in BUSES if b.active_from_shift <= 1)
            expected_lines_1 = sum(1 for l in LINES if l.active_from_shift <= 1)
            expected_units_1 = sum(1 for u in UNITS if u.active_from_shift <= 1)

            assert len(buses1) == expected_buses_1, \
                f"Shift 1 buses: expected {expected_buses_1}, got {len(buses1)}"
            assert len(lines1) == expected_lines_1, \
                f"Shift 1 lines: expected {expected_lines_1}, got {len(lines1)}"
            assert len(units1) == expected_units_1, \
                f"Shift 1 units: expected {expected_units_1}, got {len(units1)}"
            assert g1.slack_bus == 'MDBY', \
                f"Slack bus should be MDBY, got {g1.slack_bus!r}"

            print(f"  Grid(1): {len(buses1)} buses, {len(lines1)} lines, "
                  f"{len(units1)} units — PASS")

        except AssertionError as e:
            print(f"  Grid(1): FAIL — {e}")
            all_passed = False

        # ── Shift 3: south + centre (20 buses) ───────────────────────────
        try:
            g3 = Grid(3)
            buses3 = g3.get_active_buses()
            lines3 = g3.get_active_lines()
            units3 = g3.get_active_units()

            expected_buses_3 = sum(1 for b in BUSES if b.active_from_shift <= 3)
            expected_lines_3 = sum(1 for l in LINES if l.active_from_shift <= 3)
            expected_units_3 = sum(1 for u in UNITS if u.active_from_shift <= 3)

            assert len(buses3) == expected_buses_3, \
                f"Shift 3 buses: expected {expected_buses_3}, got {len(buses3)}"
            assert len(lines3) == expected_lines_3, \
                f"Shift 3 lines: expected {expected_lines_3}, got {len(lines3)}"
            assert len(units3) == expected_units_3, \
                f"Shift 3 units: expected {expected_units_3}, got {len(units3)}"

            assert len(buses3) > len(buses1), \
                "Shift 3 should have more buses than shift 1"

            print(f"  Grid(3): {len(buses3)} buses, {len(lines3)} lines, "
                  f"{len(units3)} units — PASS")

        except AssertionError as e:
            print(f"  Grid(3): FAIL — {e}")
            all_passed = False

        # ── Shift 5: full grid (32 transmission buses) ────────────────────
        try:
            g5 = Grid(5)
            buses5 = g5.get_active_buses()
            lines5 = g5.get_active_lines()
            units5 = g5.get_active_units()

            expected_buses_5 = sum(1 for b in BUSES if b.active_from_shift <= 5)
            expected_lines_5 = sum(1 for l in LINES if l.active_from_shift <= 5)
            expected_units_5 = sum(1 for u in UNITS if u.active_from_shift <= 5)

            assert len(buses5) == expected_buses_5, \
                f"Shift 5 buses: expected {expected_buses_5}, got {len(buses5)}"
            assert len(lines5) == expected_lines_5, \
                f"Shift 5 lines: expected {expected_lines_5}, got {len(lines5)}"
            assert len(units5) == expected_units_5, \
                f"Shift 5 units: expected {expected_units_5}, got {len(units5)}"

            assert len(buses5) > len(buses3), \
                "Shift 5 should have more buses than shift 3"
            assert len(units5) == 47, \
                f"Full fleet should be 47 units, got {len(units5)}"

            print(f"  Grid(5): {len(buses5)} buses, {len(lines5)} lines, "
                  f"{len(units5)} units — PASS")

        except AssertionError as e:
            print(f"  Grid(5): FAIL — {e}")
            all_passed = False

        # ── All 47 units load without error ───────────────────────────────
        try:
            g_full = Grid(10)   # Shift 10 = all units active
            for unit in g_full.get_active_units():
                assert unit.label, "Unit label should not be empty"
                assert unit.rated_mw > 0.0, \
                    f"{unit.label}: rated_mw must be > 0"
                assert unit.min_mw >= 0.0, \
                    f"{unit.label}: min_mw must be >= 0"
                assert unit.min_mw <= unit.rated_mw, \
                    f"{unit.label}: min_mw {unit.min_mw} > rated_mw {unit.rated_mw}"
                assert unit.ramp_pct_per_min > 0.0, \
                    f"{unit.label}: ramp_pct_per_min must be > 0"
                assert unit.inertia_h >= 0.0, \
                    f"{unit.label}: inertia_h must be >= 0"
                assert unit.cold_start_min >= 0.0, \
                    f"{unit.label}: cold_start_min must be >= 0"
            print(f"  All 47 units load without error — PASS")

        except AssertionError as e:
            print(f"  Unit validation: FAIL — {e}")
            all_passed = False

        # ── Slack bus is present and marked correctly ─────────────────────
        try:
            g = Grid(1)
            slack = g.get_bus('MDBY')
            assert slack.is_slack, "MDBY.is_slack should be True"
            assert slack.voltage_kv == 400.0, \
                f"MDBY should be 400kV, got {slack.voltage_kv}"

            non_slack_buses = [b for b in g.get_active_buses() if b.is_slack]
            assert len(non_slack_buses) == 1, \
                f"Exactly one slack bus expected, found {len(non_slack_buses)}"
            print(f"  Slack bus MDBY correctly defined — PASS")

        except AssertionError as e:
            print(f"  Slack bus check: FAIL — {e}")
            all_passed = False

        # ── Canvas positions accessible ───────────────────────────────────
        try:
            g = Grid(5)
            pos = g.get_canvas_position('MDBY')
            assert len(pos) == 2, "Canvas position should be (x, y) tuple"
            assert 0 <= pos[0] <= 1920, f"Canvas x out of range: {pos[0]}"
            assert 0 <= pos[1] <= 844, f"Canvas y out of range: {pos[1]}"

            pos_station = g.get_canvas_position('RVSD')
            assert len(pos_station) == 2

            pos_intc = g.get_canvas_position('INTC-N')
            assert len(pos_intc) == 2
            print(f"  Canvas positions accessible — PASS")

        except AssertionError as e:
            print(f"  Canvas positions: FAIL — {e}")
            all_passed = False

        # ── Demand profile query ──────────────────────────────────────────
        try:
            g = Grid(1)
            load_ld01_morning = g.get_load_at_bus('LD01', 9.0)
            load_ld01_night   = g.get_load_at_bus('LD01', 3.0)
            load_transmission = g.get_load_at_bus('MDBY', 9.0)

            assert load_ld01_morning > 0.0, "LD01 morning load should be > 0"
            assert load_ld01_night   > 0.0, "LD01 night load should be > 0"
            assert load_ld01_morning > load_ld01_night, \
                "Morning load should exceed night load"
            assert load_transmission == 0.0, \
                "Transmission bus MDBY should have zero load"
            print(f"  Demand profile query: morning={load_ld01_morning:.1f}MW "
                  f"night={load_ld01_night:.1f}MW — PASS")

        except AssertionError as e:
            print(f"  Demand profile: FAIL — {e}")
            all_passed = False

        # ── Invalid shift number raises ValueError ────────────────────────
        try:
            try:
                Grid(0)
                print(f"  ValueError for shift 0: FAIL — no exception raised")
                all_passed = False
            except ValueError:
                pass
            try:
                Grid(11)
                print(f"  ValueError for shift 11: FAIL — no exception raised")
                all_passed = False
            except ValueError:
                pass
            print(f"  Invalid shift raises ValueError — PASS")

        except Exception as e:
            print(f"  ValueError check: ERROR — {type(e).__name__}: {e}")
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
        test_grid_loads(),
    ]
    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    if passed < total:
        sys.exit(1)
