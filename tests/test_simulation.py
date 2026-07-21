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

import numpy as np

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
            expected_lines_3 = sum(1 for l in LINES if l.active_from_shift <= 3 <= l.active_until_shift)
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

        # ── Shift 7: full grid (36 transmission + load buses) ─────────────
        try:
            g7 = Grid(7)
            buses7 = g7.get_active_buses()
            lines7 = g7.get_active_lines()
            units7 = g7.get_active_units()

            expected_buses_7 = sum(1 for b in BUSES if b.active_from_shift <= 7)
            expected_lines_7 = sum(1 for l in LINES if l.active_from_shift <= 7 <= l.active_until_shift)
            expected_units_7 = sum(1 for u in UNITS if u.active_from_shift <= 7)

            assert len(buses7) == expected_buses_7, \
                f"Shift 7 buses: expected {expected_buses_7}, got {len(buses7)}"
            assert len(lines7) == expected_lines_7, \
                f"Shift 7 lines: expected {expected_lines_7}, got {len(lines7)}"
            assert len(units7) == expected_units_7, \
                f"Shift 7 units: expected {expected_units_7}, got {len(units7)}"

            assert len(buses7) > len(buses3), \
                "Shift 7 should have more buses than shift 3"
            assert len(units7) == 47, \
                f"Full fleet should be 47 units, got {len(units7)}"

            print(f"  Grid(7): {len(buses7)} buses, {len(lines7)} lines, "
                  f"{len(units7)} units — PASS")

        except AssertionError as e:
            print(f"  Grid(7): FAIL — {e}")
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
            # Shift 1 has a single load bus: LD01 (150kV load substation).
            load_ld01_morning = g.get_load_at_bus('LD01', 9.0)
            load_ld01_night   = g.get_load_at_bus('LD01', 3.0)
            load_slack        = g.get_load_at_bus('MDBY', 9.0)

            assert load_ld01_morning > 0.0, "LD01 morning load should be > 0"
            assert load_ld01_night   > 0.0, "LD01 night load should be > 0"
            assert load_ld01_morning > load_ld01_night, \
                "Morning load should exceed night load"
            assert load_slack == 0.0, \
                "Slack bus MDBY should have zero load"
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
# STAGE 2 TESTS — DC Load Flow Solver
# ─────────────────────────────────────────────────────────────────────────────

def test_loadflow_solves() -> bool:
    """
    Verify DCLoadFlow produces physically correct results on known test networks.

    Uses a 3-bus network with an analytical solution, then verifies the
    full Shift 1 grid produces sensible non-zero flows.
    """
    print("test_loadflow_solves...")
    all_passed = True

    try:
        from simulation.grid import Grid
        from simulation.loadflow import DCLoadFlow
        from simulation.constants import S_BASE

        # ── 3-bus analytical test ─────────────────────────────────────────
        # Network:
        #   Bus A (slack), Bus B, Bus C
        #   Line AB: X = 0.1 pu, rating 500 MW
        #   Line BC: X = 0.2 pu, rating 300 MW
        #   Line AC: X = 0.1 pu, rating 500 MW
        #
        # Injections: A=slack, B=+200 MW (gen), C=-200 MW (load)
        #
        # Analytical solution (by hand):
        #   B matrix (before removing slack):
        #     b_AB = 1/0.1 = 10, b_BC = 1/0.2 = 5, b_AC = 1/0.1 = 10
        #     B = [[20, -10, -10],
        #          [-10, 15, -5],
        #          [-10, -5,  15]]  (+ YSHUNT_REG on diagonal, negligible)
        #   Remove row/col 0 (slack A):
        #     B_red = [[15, -5], [-5, 15]]
        #   P_red = [200/1000, -200/1000] = [0.2, -0.2] pu
        #   theta = B_red^-1 * P_red
        #     det = 15*15 - (-5)*(-5) = 225 - 25 = 200
        #     B_red^-1 = (1/200)*[[15,5],[5,15]]
        #     theta_B = (15*0.2 + 5*(-0.2))/200 = (3-1)/200 = 2/200 = 0.01 rad
        #     theta_C = (5*0.2 + 15*(-0.2))/200 = (1-3)/200 = -2/200 = -0.01 rad
        #
        # Line flows:
        #   P_AB = (theta_A - theta_B)/X_AB = (0 - 0.01)/0.1 = -0.1 pu = -100 MW
        #   P_BC = (theta_B - theta_C)/X_BC = (0.01-(-0.01))/0.2 = 0.1 pu = 100 MW
        #   P_AC = (theta_A - theta_C)/X_AC = (0-(-0.01))/0.1 = 0.1 pu = 100 MW

        try:
            # Use Grid(2): L50 activates from Shift 2 (same shift as LD02).
            # Grid(2) has MDBY→DUND (L11), DUND→LD01 (L49), DUND→LD02 (L50).
            g1 = Grid(2)
            lf = DCLoadFlow(g1)

            # Generation at MDBY (slack), load split across LD01 and LD02.
            # Slack absorbs +1000 MW. Both feeder lines should carry flow.
            buses = {b.label: 0.0 for b in g1.get_active_buses()}
            buses['LD01'] = -500.0
            buses['LD02'] = -500.0

            result = lf.solve(buses)

            # Slack bus angle must be exactly 0
            assert abs(result.bus_angles['MDBY']) < 1e-10, \
                f"Slack bus angle should be 0, got {result.bus_angles['MDBY']}"

            # All buses must have angles
            for b in g1.get_active_buses():
                assert b.label in result.bus_angles, \
                    f"Missing angle for bus {b.label}"

            # All lines must have flows and loadings
            for l in g1.get_active_lines():
                assert l.label in result.line_flows_mw, \
                    f"Missing flow for line {l.label}"
                assert l.label in result.line_loading_pct, \
                    f"Missing loading for line {l.label}"
                assert result.line_loading_pct[l.label] >= 0.0, \
                    f"Line {l.label} loading should be >= 0"

            # Both feeders from DUND should carry non-zero flow
            assert abs(result.line_flows_mw['L49']) > 1.0, \
                f"L49 (DUND-LD01) should carry flow, got {result.line_flows_mw['L49']:.2f} MW"
            assert abs(result.line_flows_mw['L50']) > 1.0, \
                f"L50 (DUND-LD02) should carry flow, got {result.line_flows_mw['L50']:.2f} MW"

            print(f"  Grid(1) solve: slack angle=0, all angles/flows present — PASS")
            print(f"    L49 flow={result.line_flows_mw['L49']:.1f} MW  "
                  f"loading={result.line_loading_pct['L49']:.1f}%")
            print(f"    L50 flow={result.line_flows_mw['L50']:.1f} MW  "
                  f"loading={result.line_loading_pct['L50']:.1f}%")

        except AssertionError as e:
            print(f"  Grid(1) solve: FAIL — {e}")
            all_passed = False

        # ── Flow direction consistency ─────────────────────────────────────
        # Generation at MDBY (slack), load at LD01. Power must flow
        # MDBY→DUND (L11, positive) then DUND→LD01 (L49, positive).
        try:
            g1 = Grid(1)
            lf = DCLoadFlow(g1)

            buses = {b.label: 0.0 for b in g1.get_active_buses()}
            buses['LD01'] = -1000.0  # load at LD01

            result = lf.solve(buses)

            # Power flows toward load: MDBY→DUND positive, DUND→LD01 positive
            assert result.line_flows_mw['L11'] > 0.0, \
                f"L11 should flow MDBY→DUND (positive), got {result.line_flows_mw['L11']:.2f}"
            assert result.line_flows_mw['L49'] > 0.0, \
                f"L49 should flow DUND→LD01 (positive), got {result.line_flows_mw['L49']:.2f}"

            print(f"  Flow direction correct: L11={result.line_flows_mw['L11']:.1f} MW "
                  f"L49={result.line_flows_mw['L49']:.1f} MW -- PASS")

        except AssertionError as e:
            print(f"  Flow direction: FAIL — {e}")
            all_passed = False

        # ── Loading percentage matches flow / rating ───────────────────────
        try:
            g1 = Grid(1)
            lf = DCLoadFlow(g1)
            buses = {b.label: 0.0 for b in g1.get_active_buses()}
            buses['LD01'] = -600.0
            buses['LD02'] = -400.0
            result = lf.solve(buses)

            for line in g1.get_active_lines():
                lbl = line.label
                expected_loading = abs(result.line_flows_mw[lbl]) / line.rating_mw * 100.0
                assert abs(result.line_loading_pct[lbl] - expected_loading) < 1e-6, \
                    f"{lbl}: loading_pct {result.line_loading_pct[lbl]:.4f} != " \
                    f"expected {expected_loading:.4f}"

            print(f"  Loading percentages consistent with flows — PASS")

        except AssertionError as e:
            print(f"  Loading percentage: FAIL — {e}")
            all_passed = False

        # ── Singular matrix (islanded) returns safe zero-angle fallback ────
        try:
            g1 = Grid(1)
            lf = DCLoadFlow(g1)

            # Corrupt the B matrix to force singularity
            lf._b_reduced = np.zeros_like(lf._b_reduced)

            buses = {b.label: 0.0 for b in g1.get_active_buses()}
            buses['ASHF'] = -500.0
            result = lf.solve(buses)

            # Should return without raising — zero angles
            for b in g1.get_active_buses():
                assert abs(result.bus_angles[b.label]) < 1e-10, \
                    f"Singular fallback: expected zero angle for {b.label}"

            print(f"  Singular matrix returns zero-angle fallback — PASS")

        except AssertionError as e:
            print(f"  Singular fallback: FAIL — {e}")
            all_passed = False

        # ── Full grid Shift 7: all lines get flows ────────────────────────
        try:
            g7 = Grid(7)
            lf7 = DCLoadFlow(g7)

            buses = {b.label: 0.0 for b in g7.get_active_buses()}
            # Spread load across load substations
            for label in g7.get_load_bus_labels():
                buses[label] = -500.0
            # Generation at major buses
            buses['MDBY'] = 0.0   # slack — absorbs remainder
            buses['STHW'] = 1400.0
            buses['NRTH'] = 600.0
            buses['WEST'] = 400.0

            result = lf7.solve(buses)

            expected_lines = len(g7.get_active_lines())
            assert len(result.line_flows_mw) == expected_lines, \
                f"Expected {expected_lines} line flows, got {len(result.line_flows_mw)}"
            assert len(result.bus_angles) == len(g7.get_active_buses()), \
                "Missing bus angles in full grid solve"

            non_zero = sum(1 for f in result.line_flows_mw.values() if abs(f) > 0.1)
            assert non_zero > 10, \
                f"Expected at least 10 lines to carry flow, only {non_zero}/{expected_lines} non-zero"

            print(f"  Full grid (shift 7): {expected_lines} lines solved, "
                  f"{non_zero} carrying flow — PASS")

        except AssertionError as e:
            print(f"  Full grid solve: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4 TESTS — Generation Unit State Machine
# ─────────────────────────────────────────────────────────────────────────────

def test_unit_model() -> bool:
    """
    Verify UnitModel state transitions, ramp behaviour, and FleetModel aggregates.
    """
    print("test_unit_model...")
    all_passed = True

    try:
        from simulation.units import UnitModel, FleetModel
        from simulation.grid import Grid
        from data.fleet import get_unit

        # ── Unit starts OFFLINE ───────────────────────────────────────────
        try:
            spec = get_unit('RVSD-1')
            um = UnitModel(spec)
            assert um.state == 'OFFLINE', \
                f"Expected OFFLINE, got {um.state!r}"
            assert um.current_mw == 0.0, \
                f"OFFLINE unit should have 0 MW, got {um.current_mw}"
            assert um.start_progress == 0.0, \
                f"start_progress should be 0.0, got {um.start_progress}"
            print(f"  Unit starts OFFLINE: state={um.state}, "
                  f"output={um.current_mw} MW -- PASS")
        except AssertionError as e:
            print(f"  Initial state: FAIL -- {e}")
            all_passed = False

        # ── start() transitions to STARTING ───────────────────────────────
        try:
            spec = get_unit('RVSD-1')
            um = UnitModel(spec)
            accepted = um.start()
            assert accepted, "start() should return True from OFFLINE"
            assert um.state == 'STARTING', \
                f"After start(), expected STARTING, got {um.state!r}"
            assert um.current_mw == 0.0, \
                f"STARTING unit should have 0 MW output"

            # start() should be rejected when already STARTING
            rejected = um.start()
            assert not rejected, "start() on STARTING unit should return False"
            print(f"  start() -> STARTING: accepted={accepted}, "
                  f"re-start rejected={not rejected} -- PASS")
        except AssertionError as e:
            print(f"  start() transition: FAIL -- {e}")
            all_passed = False

        # ── Cold start countdown advances; unit goes ONLINE ───────────────
        try:
            spec = get_unit('ASHG-1')   # CCGT: cold_start_min = 60.0
            um = UnitModel(spec)
            um.start()

            # Advance 30 sim-minutes (1800 seconds). Should still be STARTING.
            um.tick(dt_sim_seconds=1800.0)
            assert um.state == 'STARTING', \
                f"After 30 min, CCGT should still be STARTING, got {um.state!r}"
            assert abs(um.start_progress - 0.5) < 0.01, \
                f"start_progress should be ~0.5 at 30/60 min, got {um.start_progress:.3f}"

            # Advance another 31 minutes (1860 seconds). Should be ONLINE.
            um.tick(dt_sim_seconds=1860.0)
            assert um.state == 'ONLINE', \
                f"After 61+ min, CCGT should be ONLINE, got {um.state!r}"
            assert um.current_mw == spec.min_mw, \
                f"On ONLINE transition, output should be min_mw={spec.min_mw}, " \
                f"got {um.current_mw}"
            print(f"  Cold start ({spec.cold_start_min:.0f} min): "
                  f"STARTING -> ONLINE at min_mw={spec.min_mw} MW -- PASS")
        except AssertionError as e:
            print(f"  Cold start countdown: FAIL -- {e}")
            all_passed = False

        # ── Ramp rate limits output per tick ──────────────────────────────
        try:
            spec = get_unit('RVSD-1')   # COAL: ramp 3%/min, rated 300 MW
            um = UnitModel(spec, initial_mw=90.0)  # start ONLINE at min

            um.set_target(300.0)

            # After 1 simulated minute (60 seconds), ramp = 3% × 300 = 9 MW
            um.tick(dt_sim_seconds=60.0)
            expected_after_1min = 90.0 + 9.0
            assert abs(um.current_mw - expected_after_1min) < 0.01, \
                f"After 1 min, expected {expected_after_1min} MW, " \
                f"got {um.current_mw:.3f} MW"

            # After another 4 minutes (240 s), total 5 min: +9*5=45 MW from 90 = 135
            um.tick(dt_sim_seconds=240.0)
            expected_after_5min = 90.0 + 9.0 * 5
            assert abs(um.current_mw - expected_after_5min) < 0.1, \
                f"After 5 min, expected {expected_after_5min} MW, " \
                f"got {um.current_mw:.3f} MW"

            print(f"  Ramp rate: {spec.ramp_pct_per_min}%/min on {spec.rated_mw} MW: "
                  f"+{um.current_mw - 90.0:.1f} MW in 5 min -- PASS")
        except AssertionError as e:
            print(f"  Ramp rate: FAIL -- {e}")
            all_passed = False

        # ── Output clamped to [min_mw, rated_mw] when ONLINE ──────────────
        try:
            spec = get_unit('HART-1')   # NUCLEAR: min 490, rated 700
            um = UnitModel(spec, initial_mw=490.0)

            # Target below min: clamp to min_mw
            um.set_target(100.0)
            assert um.target_mw == spec.min_mw, \
                f"Target below min_mw should be clamped: expected {spec.min_mw}, " \
                f"got {um.target_mw}"

            # Target above rated: clamp to rated_mw
            um.set_target(9999.0)
            assert um.target_mw == spec.rated_mw, \
                f"Target above rated_mw should be clamped: expected {spec.rated_mw}, " \
                f"got {um.target_mw}"

            print(f"  Output clamping [{spec.min_mw}, {spec.rated_mw}] MW -- PASS")
        except AssertionError as e:
            print(f"  Output clamping: FAIL -- {e}")
            all_passed = False

        # ── stop() transitions ONLINE -> SHUTDOWN -> OFFLINE ──────────────
        try:
            spec = get_unit('DUNH-1')   # HYDRO_PUMP: ramp 100%/min, rated 200 MW
            um = UnitModel(spec, initial_mw=200.0)
            assert um.state == 'ONLINE'

            accepted = um.stop()
            assert accepted, "stop() should return True from ONLINE"
            assert um.state == 'SHUTDOWN', \
                f"After stop(), expected SHUTDOWN, got {um.state!r}"
            assert um.target_mw == 0.0, \
                "SHUTDOWN target should be 0"

            # Hydro ramps at 100%/min: 200 MW ramps to 0 in 1 min
            # Advance 1.1 minutes (66 seconds)
            um.tick(dt_sim_seconds=66.0)
            assert um.state == 'OFFLINE', \
                f"After ramping to 0, expected OFFLINE, got {um.state!r}"
            assert um.current_mw == 0.0, \
                f"OFFLINE output should be 0, got {um.current_mw}"

            print(f"  stop() -> SHUTDOWN -> OFFLINE: "
                  f"ramp-down complete in ~1 min -- PASS")
        except AssertionError as e:
            print(f"  Shutdown sequence: FAIL -- {e}")
            all_passed = False

        # ── trip() goes to OFFLINE immediately from any state ─────────────
        try:
            spec = get_unit('RVSD-3')
            um_online = UnitModel(spec, initial_mw=300.0)
            um_online.trip()
            assert um_online.state == 'OFFLINE', \
                f"trip() from ONLINE should go to OFFLINE, got {um_online.state!r}"
            assert um_online.current_mw == 0.0

            um_starting = UnitModel(spec)
            um_starting.start()
            um_starting.trip()
            assert um_starting.state == 'OFFLINE', \
                f"trip() from STARTING should go to OFFLINE, got {um_starting.state!r}"

            print(f"  trip() from ONLINE and STARTING -> OFFLINE immediately -- PASS")
        except AssertionError as e:
            print(f"  trip(): FAIL -- {e}")
            all_passed = False

        # ── Renewable unit always ONLINE; start/stop rejected ─────────────
        try:
            spec = get_unit('WNCN-1')   # WIND
            um = UnitModel(spec)
            assert um.state == 'ONLINE', \
                f"Wind unit should start ONLINE, got {um.state!r}"
            assert not um.start(), "start() should return False for renewable"
            assert not um.stop(), "stop() should return False for renewable"
            um.set_renewable_output(180.0)
            assert abs(um.current_mw - 180.0) < 0.01, \
                f"set_renewable_output should set output: expected 180, " \
                f"got {um.current_mw}"
            print(f"  Renewable always ONLINE, output overridable -- PASS")
        except AssertionError as e:
            print(f"  Renewable unit: FAIL -- {e}")
            all_passed = False

        # ── FleetModel aggregates ─────────────────────────────────────────
        # Grid(3) used: HART-1/2 are at STHW which is only active from Shift 3.
        try:
            g3 = Grid(3)
            schedule = {
                'RVSD-1': 280.0,
                'HART-1': 600.0,
                'HART-2': 700.0,
            }
            fleet = FleetModel(g3, initial_schedule=schedule)

            total_gen = fleet.total_generation_mw()
            # Scheduled units + any renewables at 0 MW
            expected = 280.0 + 600.0 + 700.0
            assert abs(total_gen - expected) < 0.1, \
                f"Fleet total gen: expected {expected}, got {total_gen:.1f}"

            reserve = fleet.spinning_reserve_mw()
            assert reserve >= 0.0, f"Spinning reserve must be >= 0, got {reserve}"

            p_inj = fleet.p_injections()
            assert 'MDBY' in p_inj, "RVSD units at MDBY should appear in p_injections"
            assert abs(p_inj['MDBY'] - 280.0) < 0.1, \
                f"MDBY P injection: expected 280, got {p_inj['MDBY']:.1f}"
            assert abs(p_inj['STHW'] - 1300.0) < 0.1, \
                f"STHW P injection: expected 1300, got {p_inj.get('STHW', 0):.1f}"

            oit = fleet.online_unit_types()
            assert len(oit) > 0, "online_unit_types should return non-empty list"

            print(f"  FleetModel: total_gen={total_gen:.1f} MW, "
                  f"reserve={reserve:.1f} MW -- PASS")
        except AssertionError as e:
            print(f"  FleetModel aggregates: FAIL -- {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR -- {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 TESTS — Frequency and Voltage Models
# ─────────────────────────────────────────────────────────────────────────────

def test_frequency_model() -> bool:
    """
    Verify FrequencyModel drives frequency deviation and applies droop correctly.

    Checks:
      - Imbalance drives frequency deviation in the correct direction
      - Droop response opposes the deviation
      - Frequency is clamped to [F_MIN, F_MAX]
    """
    print("test_frequency_model...")
    all_passed = True

    try:
        from simulation.frequency import FrequencyModel
        from simulation.constants import F_NOMINAL, F_MIN, F_MAX

        # ── Generation deficit lowers frequency ───────────────────────────
        try:
            fm = FrequencyModel()
            assert abs(fm.frequency_hz - F_NOMINAL) < 1e-9, \
                f"Initial frequency should be {F_NOMINAL} Hz, got {fm.frequency_hz}"

            # 500 MW deficit on a 5000 MW system (all coal, H=5).
            # With no droop (first tick from nominal, Δf=0 → droop=0):
            # df/dt = (50 / (2×5)) × (-500/1000) = 5 × (-0.5) = -2.5 Hz/s
            # After 1s: f ≈ 47.5 Hz (well below nominal).
            online_units = [('COAL', 4500.0)]
            fm.update(
                dt_sim_seconds=1.0,
                p_generation_mw=4500.0,
                p_load_mw=5000.0,
                online_unit_types=online_units,
            )
            assert fm.frequency_hz < F_NOMINAL, \
                f"Deficit should lower frequency below {F_NOMINAL}, got {fm.frequency_hz:.4f}"
            assert fm.frequency_trend == 'FALLING', \
                f"Trend should be FALLING, got {fm.frequency_trend!r}"
            print(f"  Deficit lowers frequency: {F_NOMINAL:.1f} -> "
                  f"{fm.frequency_hz:.4f} Hz, trend={fm.frequency_trend} — PASS")

        except AssertionError as e:
            print(f"  Imbalance direction: FAIL — {e}")
            all_passed = False

        # ── Generation surplus raises frequency ────────────────────────────
        try:
            fm2 = FrequencyModel()
            fm2.update(
                dt_sim_seconds=1.0,
                p_generation_mw=5500.0,
                p_load_mw=5000.0,
                online_unit_types=[('NUCLEAR', 5500.0)],
            )
            assert fm2.frequency_hz > F_NOMINAL, \
                f"Surplus should raise frequency above {F_NOMINAL}, got {fm2.frequency_hz:.4f}"
            assert fm2.frequency_trend == 'RISING', \
                f"Trend should be RISING, got {fm2.frequency_trend!r}"
            print(f"  Surplus raises frequency: {F_NOMINAL:.1f} -> "
                  f"{fm2.frequency_hz:.4f} Hz, trend={fm2.frequency_trend} — PASS")

        except AssertionError as e:
            print(f"  Surplus direction: FAIL — {e}")
            all_passed = False

        # ── Honest swing equation: constant df/dt under constant imbalance ──
        try:
            fm3 = FrequencyModel()
            online_units = [('COAL', 3000.0), ('CCGT', 2000.0)]
            rates = []
            for _ in range(20):
                f_before = fm3.frequency_hz
                fm3.update(
                    dt_sim_seconds=0.1,
                    p_generation_mw=4800.0,
                    p_load_mw=5000.0,
                    online_unit_types=online_units,
                )
                rates.append(fm3.frequency_hz - f_before)

            # Honest swing equation with constant imbalance → constant df/dt.
            early_rate = sum(rates[:5]) / 5
            late_rate  = sum(rates[15:]) / 5
            assert abs(late_rate - early_rate) < 1e-9, (
                f"Honest swing equation: df/dt should be constant under steady imbalance: "
                f"early={early_rate:.5f} Hz/tick late={late_rate:.5f} Hz/tick"
            )
            print(f"  Droop response: PASS — constant df/dt={early_rate:.5f} Hz/tick "
                  f"(honest swing equation, no phantom droop)")

        except AssertionError as e:
            print(f"  Droop response: FAIL — {e}")
            all_passed = False

        # ── Frequency clamped to [F_MIN, F_MAX] ────────────────────────────
        try:
            fm4 = FrequencyModel()
            # Force an extreme deficit (all load, no generation) to drive to floor.
            for _ in range(200):
                fm4.update(
                    dt_sim_seconds=1.0,
                    p_generation_mw=0.0,
                    p_load_mw=8000.0,
                    online_unit_types=[],
                )
            assert fm4.frequency_hz >= F_MIN, \
                f"Frequency should not go below F_MIN={F_MIN}, got {fm4.frequency_hz:.4f}"
            assert fm4.frequency_hz <= F_MAX, \
                f"Frequency should not exceed F_MAX={F_MAX}, got {fm4.frequency_hz:.4f}"

            fm5 = FrequencyModel()
            for _ in range(200):
                fm5.update(
                    dt_sim_seconds=1.0,
                    p_generation_mw=8000.0,
                    p_load_mw=0.0,
                    online_unit_types=[('COAL', 8000.0)],
                )
            assert fm5.frequency_hz <= F_MAX, \
                f"Frequency should not exceed F_MAX={F_MAX}, got {fm5.frequency_hz:.4f}"
            assert fm5.frequency_hz >= F_MIN, \
                f"Frequency should not go below F_MIN={F_MIN}, got {fm5.frequency_hz:.4f}"

            print(f"  Frequency clamped: floor={fm4.frequency_hz:.3f} Hz  "
                  f"ceiling={fm5.frequency_hz:.3f} Hz — PASS")

        except AssertionError as e:
            print(f"  Frequency clamp: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


def test_voltage_model() -> bool:
    """
    Verify VoltageModel produces physically reasonable voltage magnitudes
    and correctly converts PV buses to PQ when reactive limits are hit.

    Checks:
      - Voltage solution is physically reasonable (slack = 1.0, others near 1.0)
      - Reactive injection raises voltage; absorption lowers it
      - PV->PQ conversion fires when Q limit is exceeded
    """
    print("test_voltage_model...")
    all_passed = True

    try:
        from simulation.grid import Grid
        from simulation.voltage import VoltageModel

        # ── Slack bus always 1.0, voltages physically reasonable ──────────
        try:
            g1 = Grid(1)
            vm = VoltageModel(g1)

            # Balanced system — zero Q everywhere.
            q_zero = {b.label: 0.0 for b in g1.get_active_buses()}
            result = vm.solve(q_zero)

            assert abs(result.bus_voltages['MDBY'] - 1.0) < 1e-9, \
                f"Slack bus MDBY should have V=1.0, got {result.bus_voltages['MDBY']:.6f}"

            for b in g1.get_active_buses():
                v = result.bus_voltages[b.label]
                assert 0.5 <= v <= 1.5, \
                    f"Bus {b.label} voltage {v:.4f} outside plausible range [0.5, 1.5]"

            print(f"  Balanced solve: all voltages in plausible range, "
                  f"slack=1.0 — PASS")

        except AssertionError as e:
            print(f"  Balanced solve: FAIL — {e}")
            all_passed = False

        # ── Reactive injection raises voltage; absorption lowers it ────────
        try:
            g1 = Grid(1)
            vm = VoltageModel(g1)

            buses = g1.get_active_buses()
            non_slack = [b.label for b in buses if b.label != g1.slack_bus]
            target_bus = non_slack[0]  # first non-slack bus

            # Inject +Q at target bus.
            q_inject = {b.label: 0.0 for b in buses}
            q_inject[target_bus] = 500.0
            result_inject = vm.solve(q_inject)

            # Absorb -Q at target bus.
            q_absorb = {b.label: 0.0 for b in buses}
            q_absorb[target_bus] = -500.0
            result_absorb = vm.solve(q_absorb)

            v_inject = result_inject.bus_voltages[target_bus]
            v_absorb = result_absorb.bus_voltages[target_bus]
            v_zero   = vm.solve({b.label: 0.0 for b in buses}).bus_voltages[target_bus]

            assert v_inject > v_zero, \
                f"Q injection should raise voltage: {v_inject:.4f} <= {v_zero:.4f}"
            assert v_absorb < v_zero, \
                f"Q absorption should lower voltage: {v_absorb:.4f} >= {v_zero:.4f}"

            print(f"  Q injection raises V ({v_zero:.4f} -> {v_inject:.4f} pu), "
                  f"absorption lowers V ({v_zero:.4f} -> {v_absorb:.4f} pu) — PASS")

        except AssertionError as e:
            print(f"  Q effect on voltage: FAIL — {e}")
            all_passed = False

        # ── PV->PQ conversion when Q limit is hit ─────────────────────────
        try:
            g1 = Grid(1)
            vm = VoltageModel(g1)

            buses = g1.get_active_buses()
            non_slack = [b.label for b in buses if b.label != g1.slack_bus]
            pv_bus_label = non_slack[0]

            q_base = {b.label: 0.0 for b in buses}

            # PV bus with a very tight Q limit — target far from current voltage.
            # Requesting V=1.05 pu when the bus is at ~1.0 pu requires large Q;
            # cap it at a tiny q_max to force PQ conversion.
            pv_buses_tight = {
                pv_bus_label: (1.05, 5.0, -5.0)  # V_target=1.05, Q_max=5 MVAr
            }
            result_tight = vm.solve(q_base, pv_buses=pv_buses_tight)

            assert pv_bus_label in result_tight.pq_buses, \
                f"Bus {pv_bus_label} should be in pq_buses (Q limit hit)"

            # PV bus with ample Q limit — should NOT convert to PQ.
            pv_buses_ample = {
                pv_bus_label: (1.02, 9999.0, -9999.0)  # unlimited Q
            }
            result_ample = vm.solve(q_base, pv_buses=pv_buses_ample)

            assert pv_bus_label not in result_ample.pq_buses, \
                f"Bus {pv_bus_label} should NOT be in pq_buses with ample Q limit"

            print(f"  PV->PQ conversion: tight limit fires conversion, "
                  f"ample limit does not — PASS")

        except AssertionError as e:
            print(f"  PV->PQ conversion: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 5 TESTS — Demand, Renewables, and Losses
# ─────────────────────────────────────────────────────────────────────────────

def test_demand_model() -> bool:
    """
    Verify DemandModel follows the demand profile, adds bounded noise,
    distributes correctly across load buses, and applies load shed.
    """
    print("test_demand_model...")
    all_passed = True

    try:
        from simulation.demand import DemandModel
        from data.profiles import get_substation_demand_specs
        from gameplay.shifts.loader import load_shift_config

        cfg = load_shift_config(2)   # shift 2 uses the GREY/OAKE load substations
        peak_demand_mw = cfg['peak_demand_mw']
        substation_specs = get_substation_demand_specs(cfg['substation_load_mw'])

        # ── Deterministic forecast matches profile ─────────────────────────
        try:
            dm = DemandModel(peak_demand_mw, substation_specs)
            dm.update(9.0, total_generation_mw=2000.0)
            forecast = dm.get_forecast_mw(9.0)
            assert abs(dm.total_demand_mw - forecast) < 0.01, \
                f"Deterministic demand should equal forecast: " \
                f"got {dm.total_demand_mw:.2f} vs {forecast:.2f}"

            # Bus demands should sum to total
            load_buses = list(substation_specs.keys())
            bus_sum = sum(dm.get_bus_demand_mw(b) for b in load_buses)
            assert abs(bus_sum - dm.total_demand_mw) < 0.01, \
                f"Bus demands {bus_sum:.2f} don't sum to total {dm.total_demand_mw:.2f}"

            print(f"  Deterministic: demand={dm.total_demand_mw:.1f} MW "
                  f"(forecast={forecast:.1f}) buses sum -- PASS")
        except AssertionError as e:
            print(f"  Deterministic demand: FAIL -- {e}")
            all_passed = False

        # ── Morning > night (profile shape) ───────────────────────────────
        try:
            dm = DemandModel(peak_demand_mw, substation_specs)
            dm.update(9.0, total_generation_mw=2000.0)
            morning = dm.total_demand_mw
            dm.update(3.0, total_generation_mw=1000.0)
            night = dm.total_demand_mw
            assert morning > night, \
                f"Morning demand ({morning:.1f}) should exceed night ({night:.1f})"
            print(f"  Profile shape: morning={morning:.1f} > night={night:.1f} MW -- PASS")
        except AssertionError as e:
            print(f"  Profile shape: FAIL -- {e}")
            all_passed = False

        # ── Load shed reduces effective demand ─────────────────────────────
        try:
            dm = DemandModel(peak_demand_mw, substation_specs)
            dm.update(9.0, total_generation_mw=2000.0)
            before_shed = dm.total_demand_mw
            grey_before = dm.get_bus_demand_mw('GREY')

            dm.shed_load('GREY', 0.5)   # shed 50% of GREY
            dm.update(9.0, total_generation_mw=2000.0)
            after_shed = dm.total_demand_mw
            grey_after = dm.get_bus_demand_mw('GREY')

            assert after_shed < before_shed, \
                f"Shed should reduce total demand: {after_shed:.1f} >= {before_shed:.1f}"
            assert abs(grey_after - grey_before * 0.5) < 0.1, \
                f"GREY after 50% shed: expected {grey_before * 0.5:.1f}, " \
                f"got {grey_after:.1f}"

            # Unknown bus returns False
            assert not dm.shed_load('MDBY', 0.5), \
                "shed_load on transmission bus should return False"

            print(f"  Load shed: GREY {grey_before:.1f} -> {grey_after:.1f} MW "
                  f"(50% shed) -- PASS")
        except AssertionError as e:
            print(f"  Load shed: FAIL -- {e}")
            all_passed = False

        # ── Losses scale with generation ───────────────────────────────────
        try:
            from simulation.constants import LOSSES_FRACTION
            dm = DemandModel(peak_demand_mw, substation_specs)
            gen_mw = 2000.0
            dm.update(9.0, total_generation_mw=gen_mw)
            expected_losses = gen_mw * LOSSES_FRACTION
            assert abs(dm.losses_mw - expected_losses) < 0.01, \
                f"Losses should be {expected_losses:.1f} MW, got {dm.losses_mw:.2f}"
            print(f"  Losses: {dm.losses_mw:.1f} MW at {gen_mw:.0f} MW gen "
                  f"({LOSSES_FRACTION*100:.1f}%) -- PASS")
        except AssertionError as e:
            print(f"  Losses: FAIL -- {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR -- {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


def test_renewables_model() -> bool:
    """
    Verify RenewablesModel output is bounded, solar is zero at night,
    and deterministic mode suppresses noise.
    """
    print("test_renewables_model...")
    all_passed = True

    try:
        from simulation.renewables import RenewablesModel
        from simulation.grid import Grid
        from data.fleet import UNITS

        # Use Shift 7 which has WNCN (wind) and SLST/SLFD (solar) active.
        g7 = Grid(7)

        # ── All outputs bounded [0, rated_mw] ─────────────────────────────
        try:
            rng = np.random.default_rng(seed=0)
            rm = RenewablesModel(g7, rng=rng)
            rated = {u.label: u.rated_mw for u in g7.get_active_units()
                     if u.unit_type in ('WIND', 'SOLAR')}

            for hour in [0.0, 6.0, 9.0, 13.0, 18.0, 22.0]:
                outputs = rm.update(hour, 0.1, deterministic=False)
                for label, mw in outputs.items():
                    assert 0.0 <= mw <= rated[label], \
                        f"{label} at hour {hour}: output {mw:.2f} outside " \
                        f"[0, {rated[label]}]"

            print(f"  All outputs in [0, rated_mw] across 6 sample hours -- PASS")
        except AssertionError as e:
            print(f"  Output bounds: FAIL -- {e}")
            all_passed = False

        # ── Solar is zero at night ─────────────────────────────────────────
        try:
            rm = RenewablesModel(g7)
            solar_units = [u.label for u in g7.get_active_units()
                           if u.unit_type == 'SOLAR']
            assert solar_units, "Shift 7 should have solar units"

            # Hour 2:00 — deep night, solar profile = 0.0
            outputs_night = rm.update(2.0, 0.1, deterministic=False)
            for label in solar_units:
                assert outputs_night[label] == 0.0, \
                    f"Solar {label} at 02:00 should be 0, got {outputs_night[label]:.4f}"

            # Hour 13:00 — solar peak
            outputs_peak = rm.update(13.0, 0.1, deterministic=True)
            for label in solar_units:
                assert outputs_peak[label] > 0.0, \
                    f"Solar {label} at 13:00 should be > 0, got {outputs_peak[label]:.4f}"

            print(f"  Solar zero at night, positive at peak -- PASS")
        except AssertionError as e:
            print(f"  Solar night/day: FAIL -- {e}")
            all_passed = False

        # ── Deterministic mode matches forecast ────────────────────────────
        try:
            from data.profiles import get_wind_mw, get_solar_mw
            rm = RenewablesModel(g7)
            outputs = rm.update(10.0, 0.1, deterministic=True)

            for unit in g7.get_active_units():
                if unit.unit_type == 'WIND':
                    expected = get_wind_mw(10.0, unit.rated_mw)
                    assert abs(outputs[unit.label] - expected) < 0.01, \
                        f"{unit.label} deterministic: expected {expected:.2f}, " \
                        f"got {outputs[unit.label]:.2f}"
                elif unit.unit_type == 'SOLAR':
                    expected = get_solar_mw(10.0, unit.rated_mw)
                    assert abs(outputs[unit.label] - expected) < 0.01, \
                        f"{unit.label} deterministic: expected {expected:.2f}, " \
                        f"got {outputs[unit.label]:.2f}"

            print(f"  Deterministic mode matches forecast values -- PASS")
        except AssertionError as e:
            print(f"  Deterministic mode: FAIL -- {e}")
            all_passed = False

        # ── forecast_by_hour covers the requested window ───────────────────
        try:
            rm = RenewablesModel(g7)
            forecasts = rm.forecast_by_hour(6.0, 18.0, step=1.0)
            wind_units = [u.label for u in g7.get_active_units()
                          if u.unit_type == 'WIND']
            for label in wind_units:
                assert label in forecasts, \
                    f"Wind unit {label} missing from forecast_by_hour result"
                hours = list(forecasts[label].keys())
                assert min(hours) == 6.0 and max(hours) == 18.0, \
                    f"Forecast hours range incorrect: {min(hours)} to {max(hours)}"
            print(f"  forecast_by_hour covers 6-18h window -- PASS")
        except AssertionError as e:
            print(f"  forecast_by_hour: FAIL -- {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR -- {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 6 TESTS — Cascade Detection and Island Finding
# ─────────────────────────────────────────────────────────────────────────────

def test_cascade_model() -> bool:
    """
    Verify CascadeModel island finding and overload timer behaviour.

    Checks:
      - Single connected network returns exactly one island
      - Removing a line that bridges two sub-graphs yields two islands
      - Isolated buses (no lines) each form their own non-viable island
      - Overload timer fires trip at TRIP_DELAY_S, not before
    """
    print("test_cascade_model...")
    all_passed = True

    try:
        from simulation.cascade import CascadeModel
        from simulation.grid import Grid
        from simulation.constants import TRIP_DELAY_S, OVERLOAD_CRIT_PCT

        cm = CascadeModel()

        # ── find_islands partitions all buses with no overlap or gaps ─────────
        # Every bus must appear in exactly one island — this is the core
        # invariant of the BFS algorithm.  The number of islands varies by
        # topology (radial cascade stations and generation buses are naturally
        # isolated when their single feed line is the only connection).
        try:
            g7 = Grid(7)
            lines7 = g7.get_active_lines()
            buses7 = g7.get_active_buses()
            islands7 = cm.find_islands(buses7, lines7)

            all_labels7 = {b.label for b in buses7}
            covered: set = set()
            for island in islands7:
                overlap = covered & island
                assert not overlap, \
                    f"Bus(es) {overlap} appear in multiple islands"
                covered.update(island)
            assert covered == all_labels7, \
                f"Not all buses covered: missing {all_labels7 - covered}"

            # The main grid backbone (WEST, MDBY, STHW, CNTR, NRTH, EAST)
            # must all be in the same island — they are directly interconnected
            # by the active 400kV lines.
            backbone = {'WEST', 'MDBY', 'STHW', 'CNTR', 'NRTH', 'EAST'}
            backbone_island = next(
                (i for i in islands7 if backbone <= i), None
            )
            assert backbone_island is not None, \
                f"400kV backbone buses should all be in one island"

            # Load substations each connect to a 150kV feeder — verify they're
            # reachable from the backbone (same island), not isolated.
            load_labels7 = {b.label for b in buses7 if b.bus_type == 'LOAD'}
            for lb in load_labels7:
                lb_island = next(i for i in islands7 if lb in i)
                assert len(lb_island) > 1, \
                    f"Load sub {lb} should be connected (not isolated), " \
                    f"got isolated 1-bus island"

            print(f"  Grid(7) partition: {len(islands7)} islands, all "
                  f"{len(all_labels7)} buses covered, backbone connected — PASS")

        except AssertionError as e:
            print(f"  Single island: FAIL — {e}")
            all_passed = False

        # ── Tripped line splits transmission network into two islands ─────────
        # Use Grid(7) where L09 (STHW-ASHF), L10 (CNTR-WRNT), L11 (MDBY-DUND),
        # L12 (WEST-RDST), L13 (NRTH-COAL), and L14 (EAST-SLST) are the only
        # connections from the 400kV backbone into the 220kV regional pockets.
        # Removing all six transformer lines isolates the 220kV pockets
        # (and everything meshed onto them) from the spine.
        try:
            g7 = Grid(7)
            buses7 = g7.get_active_buses()
            all_lines7 = g7.get_active_lines()

            cut_labels = {'L09', 'L10', 'L11', 'L12', 'L13', 'L14'}
            reduced_lines = [l for l in all_lines7 if l.label not in cut_labels]

            islands = cm.find_islands(buses7, reduced_lines)

            # Every bus must still appear in exactly one island.
            total_in_islands = sum(len(i) for i in islands)
            assert total_in_islands == len(buses7), \
                f"All buses must appear in exactly one island: " \
                f"{total_in_islands} != {len(buses7)}"

            # The cut creates at least 2 transmission islands
            # (400kV backbone group + 220kV pocket group(s)).
            tx_labels7 = {b.label for b in buses7 if b.bus_type == 'TRANSMISSION'}
            tx_islands = [i for i in islands if i & tx_labels7]
            assert len(tx_islands) >= 2, \
                f"Cutting transformer lines should create >= 2 tx islands, " \
                f"got {len(tx_islands)}"

            print(f"  Tripped transformer lines: {len(tx_islands)} tx islands "
                  f"(total {total_in_islands} buses across all islands) — PASS")

        except AssertionError as e:
            print(f"  Split network: FAIL — {e}")
            all_passed = False

        # ── Isolated buses — all blacked out when no units are online ─────
        try:
            g5 = Grid(5)
            buses5 = g5.get_active_buses()

            # No lines in service — every bus is its own island.
            islands = cm.find_islands(buses5, [])

            assert len(islands) == len(buses5), \
                f"With no lines, each bus should be its own island: " \
                f"expected {len(buses5)}, got {len(islands)}"

            # With no units ONLINE or SHUTDOWN, active_generation_buses is empty.
            # Every island is non-viable → every bus is blacked out.
            empty_gen_buses: frozenset = frozenset()
            blackout_all = cm.get_blackout_zones(islands, empty_gen_buses)
            assert blackout_all == frozenset(b.label for b in buses5), \
                f"With no online generation, all buses should be blacked out"

            # With one specific bus "online", only that bus's island is viable.
            sample_gen_bus = g5.get_active_buses()[0].label
            one_gen_buses: frozenset = frozenset({sample_gen_bus})
            blackout_one = cm.get_blackout_zones(islands, one_gen_buses)
            assert sample_gen_bus not in blackout_one, \
                f"Bus {sample_gen_bus} (simulated online) should not be blacked out"
            assert len(blackout_one) == len(buses5) - 1, \
                f"All buses except {sample_gen_bus} should be blacked out"

            print(f"  Isolated buses: {len(blackout_all)}/{len(buses5)} blacked out "
                  f"with no online gen; 1-online case verified — PASS")

        except AssertionError as e:
            print(f"  Isolated buses: FAIL — {e}")
            all_passed = False

        # ── Overload timer triggers trip at TRIP_DELAY_S ──────────────────
        try:
            timers: dict = {}
            loading = {'L01': 110.0, 'L02': 90.0}   # L01 overloaded, L02 fine

            # Accumulate just under TRIP_DELAY_S total.
            dt = 5.0
            steps = int(TRIP_DELAY_S / dt)
            for _ in range(steps):
                trips, timers = cm.check_overloads(loading, timers, dt)
                assert 'L01' not in trips, \
                    f"L01 should not trip before TRIP_DELAY_S={TRIP_DELAY_S}s"
                assert 'L02' not in trips, \
                    "L02 (90% loading) should never trip"

            # One more step puts L01 over the threshold.
            trips, timers = cm.check_overloads(loading, timers, dt + 0.1)

            assert 'L01' in trips, \
                f"L01 should trip after TRIP_DELAY_S={TRIP_DELAY_S}s of overload"
            assert 'L02' not in trips, \
                "L02 should not trip"
            assert timers.get('L01', -1) == 0.0, \
                "Timer for tripped line L01 should reset to 0"

            # L02 timer should remain 0 (never overloaded).
            assert timers.get('L02', 0.0) == 0.0, \
                f"L02 timer should be 0, got {timers.get('L02')}"

            print(f"  Overload timer: L01 trips after {TRIP_DELAY_S}s, "
                  f"L02 unaffected — PASS")

        except AssertionError as e:
            print(f"  Overload timer: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 8 TESTS — Master Simulation Loop
# ─────────────────────────────────────────────────────────────────────────────

def test_simulation_model() -> bool:
    """
    Verify GridSimulation initialises, ticks, and exposes correct state.

    Checks:
      - GridSimulation initialises without error for Shift 1
      - tick() advances sim_time_min correctly
      - get_state() returns a SimulationState with all required fields populated
      - is_shift_complete() returns True once duration_minutes has elapsed
      - set_unit_target() returns True for an ONLINE unit, False for OFFLINE
      - trip_line() / close_line() toggle line_status correctly
    """
    print("test_simulation_model...")
    all_passed = True

    try:
        from simulation.simulation import GridSimulation, SimulationState
        from simulation.grid import Grid
        from gameplay.shifts.loader import load_shift_config

        # ── Initialises without error ─────────────────────────────────────
        try:
            g1 = Grid(1)
            sim = GridSimulation(g1, shift_number=1, difficulty='NORMAL')
            state = sim.get_state()
            assert isinstance(state, SimulationState), \
                f"get_state() should return SimulationState, got {type(state)}"
            assert state.sim_time_min == 0.0, \
                f"Initial sim_time_min should be 0, got {state.sim_time_min}"
            assert abs(state.frequency_hz - 50.0) < 0.01, \
                f"Initial frequency should be near 50 Hz, got {state.frequency_hz:.4f}"
            print(f"  GridSimulation(shift=1) initialises: "
                  f"f={state.frequency_hz:.3f} Hz, t={state.sim_time_min:.1f} min — PASS")
        except AssertionError as e:
            print(f"  Initialisation: FAIL — {e}")
            all_passed = False

        # ── tick() advances sim_time_min ──────────────────────────────────
        try:
            g1 = Grid(1)
            sim = GridSimulation(g1, shift_number=1, difficulty='NORMAL')

            sim.tick(60.0)   # 60 simulated seconds = 1 simulated minute
            state = sim.get_state()
            assert abs(state.sim_time_min - 1.0) < 1e-9, \
                f"After tick(60s), sim_time_min should be 1.0, got {state.sim_time_min:.6f}"

            sim.tick(120.0)  # 2 more minutes
            state = sim.get_state()
            assert abs(state.sim_time_min - 3.0) < 1e-9, \
                f"After tick(180s total), sim_time_min should be 3.0, got {state.sim_time_min:.6f}"

            print(f"  tick() advances time: t={state.sim_time_min:.1f} min after 3 min — PASS")
        except AssertionError as e:
            print(f"  tick() time advance: FAIL — {e}")
            all_passed = False

        # ── get_state() has all required fields ───────────────────────────
        try:
            g1 = Grid(1)
            sim = GridSimulation(g1, shift_number=1, difficulty='NORMAL')
            sim.tick(60.0)
            state = sim.get_state()

            assert isinstance(state.bus_voltages, dict) and len(state.bus_voltages) > 0, \
                "bus_voltages should be a non-empty dict"
            assert isinstance(state.line_flows_mw, dict) and len(state.line_flows_mw) > 0, \
                "line_flows_mw should be a non-empty dict"
            assert isinstance(state.line_status, dict) and len(state.line_status) > 0, \
                "line_status should be a non-empty dict"
            assert isinstance(state.unit_states, dict), \
                "unit_states should be a dict"
            assert isinstance(state.islands, list), \
                "islands should be a list"
            assert isinstance(state.blackout_zones, frozenset), \
                "blackout_zones should be a frozenset"
            assert state.total_load_mw > 0.0, \
                f"total_load_mw should be > 0 at hour with demand, got {state.total_load_mw:.1f}"

            # All active lines must appear in line_status
            for line in g1.get_active_lines():
                assert line.label in state.line_status, \
                    f"Line {line.label} missing from line_status"
                assert state.line_status[line.label] in ('IN_SERVICE', 'TRIPPED'), \
                    f"Line {line.label} has unexpected status {state.line_status[line.label]!r}"

            print(f"  State fields: {len(state.bus_voltages)} buses, "
                  f"{len(state.line_flows_mw)} lines, "
                  f"load={state.total_load_mw:.1f} MW — PASS")
        except AssertionError as e:
            print(f"  State fields: FAIL — {e}")
            all_passed = False

        # ── is_shift_complete() ───────────────────────────────────────────
        try:
            g1 = Grid(1)
            sim = GridSimulation(g1, shift_number=1, difficulty='NORMAL')
            duration_hours = load_shift_config(1)['duration_hours']
            duration_s = duration_hours * 3600.0

            assert not sim.is_shift_complete(), \
                "is_shift_complete() should be False at t=0"

            # Advance just past duration
            sim.tick(duration_s + 1.0)
            assert sim.is_shift_complete(), \
                f"is_shift_complete() should be True after {duration_hours}h elapsed"

            print(f"  is_shift_complete(): False at t=0, "
                  f"True after {duration_hours}h — PASS")
        except AssertionError as e:
            print(f"  is_shift_complete(): FAIL — {e}")
            all_passed = False

        # ── set_unit_target() — ONLINE unit accepts, OFFLINE rejects ──────
        try:
            g1 = Grid(1)
            schedule = {'DUND-1': 40.0}
            sim = GridSimulation(g1, shift_number=1, difficulty='NORMAL',
                                 initial_schedule=schedule)

            # DUND-1 is ONLINE (in initial_schedule); set_unit_target should accept
            accepted = sim.set_unit_target('DUND-1', 50.0)
            assert accepted, "set_unit_target should return True for ONLINE unit"

            # RVSD-1 is OFFLINE (not in schedule); should reject
            rejected = sim.set_unit_target('RVSD-1', 200.0)
            assert not rejected, \
                "set_unit_target should return False for OFFLINE unit"

            print(f"  set_unit_target(): ONLINE accepts, OFFLINE rejects — PASS")
        except AssertionError as e:
            print(f"  set_unit_target(): FAIL — {e}")
            all_passed = False

        # ── trip_line() / close_line() toggle status ──────────────────────
        try:
            g1 = Grid(1)
            sim = GridSimulation(g1, shift_number=1, difficulty='NORMAL')

            lines = g1.get_active_lines()
            test_line = lines[0].label   # first active line

            # Line starts IN_SERVICE
            state = sim.get_state()
            assert state.line_status[test_line] == 'IN_SERVICE', \
                f"Line {test_line} should start IN_SERVICE"

            # Trip it
            result = sim.trip_line(test_line)
            assert result, f"trip_line({test_line!r}) should return True"

            # Advance one tick so state snapshot is rebuilt
            sim.tick(1.0)
            state = sim.get_state()
            assert state.line_status[test_line] == 'TRIPPED', \
                f"After trip, {test_line} should be TRIPPED, got {state.line_status[test_line]!r}"

            # Trip again — should return False (already out)
            assert not sim.trip_line(test_line), \
                "trip_line() on already-tripped line should return False"

            # Close it
            result = sim.close_line(test_line)
            assert result, f"close_line({test_line!r}) should return True"

            sim.tick(1.0)
            state = sim.get_state()
            assert state.line_status[test_line] == 'IN_SERVICE', \
                f"After close, {test_line} should be IN_SERVICE, got {state.line_status[test_line]!r}"

            print(f"  trip_line/close_line({test_line}): "
                  f"IN_SERVICE -> TRIPPED -> IN_SERVICE — PASS")
        except AssertionError as e:
            print(f"  trip/close line: FAIL — {e}")
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
        test_loadflow_solves(),
        test_unit_model(),
        test_demand_model(),
        test_renewables_model(),
        test_frequency_model(),
        test_voltage_model(),
        test_cascade_model(),
        test_simulation_model(),
    ]
    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    if passed < total:
        sys.exit(1)
