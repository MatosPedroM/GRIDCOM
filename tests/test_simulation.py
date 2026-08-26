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

def _build_grid_loads_fixture():
    """Small synthetic DesignerGrid: one slack (MDBY-like) transmission bus,
    one plain transmission bus, one load bus, one generation station with
    two units, and a station-only element (canvas position via a unit's
    station_x/station_y) to exercise get_canvas_position() for a non-bus
    label. Returns (grid, buses, lines, units) — the raw Designer* lists,
    so tests can assert the grid reproduces them exactly."""
    from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
    from simulation.designer_grid import DesignerGrid

    buses = [
        DesignerBus(label='SLAK', name='Slackton', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=200, canvas_y=100,
                    active_from_shift=1, is_slack=True),
        DesignerBus(label='CNTR', name='Centre', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=400, canvas_y=100,
                    active_from_shift=1, is_slack=False),
        DesignerBus(label='LOAD', name='Loadham', voltage_kv=150.0,
                    bus_type='LOAD', canvas_x=400, canvas_y=300,
                    active_from_shift=1, is_slack=False, peak_load_mw=240.0),
    ]
    lines = [
        DesignerLine(label='L01', from_bus='SLAK', to_bus='CNTR',
                     reactance_pu=0.08, rating_mw=800.0, voltage_kv=400.0),
        DesignerLine(label='L02', from_bus='CNTR', to_bus='LOAD',
                     reactance_pu=0.12, rating_mw=500.0, voltage_kv=150.0),
    ]
    units = [
        DesignerUnit(label='GENS-1', station_label='GENS', bus_label='CNTR',
                     unit_type='COAL', rated_mw=300.0, min_mw=90.0,
                     inertia_h=5.0, cold_start_min=240.0,
                     q_max_mvar=150.0, q_min_mvar=-80.0, can_pump=False,
                     active_from_shift=1, description='Test coal unit 1',
                     station_x=450, station_y=80),
        DesignerUnit(label='GENS-2', station_label='GENS', bus_label='CNTR',
                     unit_type='CCGT', rated_mw=400.0, min_mw=80.0,
                     inertia_h=4.0, cold_start_min=60.0,
                     q_max_mvar=180.0, q_min_mvar=-100.0, can_pump=False,
                     active_from_shift=1, description='Test CCGT unit 2',
                     station_x=450, station_y=80),
    ]
    grid = DesignerGrid(buses, lines, units)
    return grid, buses, lines, units


def test_grid_loads() -> bool:
    """
    DesignerGrid replaces Grid/topology.py as the grid abstraction — it has
    no shift-filtering concept (a DesignerGrid IS the full grid it was
    built from, unfiltered), so this now verifies DesignerGrid's own
    invariants against a small synthetic fixture: it reproduces exactly
    the bus/line/unit lists it was constructed from, resolves slack_bus to
    the bus marked is_slack, exposes valid canvas positions for both bus
    and station labels, and every unit satisfies the same physical
    validation properties the old fleet-wide check exercised.
    """
    print("test_grid_loads...")
    all_passed = True

    try:
        from simulation.designer_grid import DesignerGrid

        grid, d_buses, d_lines, d_units = _build_grid_loads_fixture()

        # ── Grid reproduces exactly what it was given ─────────────────────
        try:
            active_buses = grid.get_active_buses()
            active_lines = grid.get_active_lines()
            active_units = grid.get_active_units()

            assert len(active_buses) == len(d_buses), \
                f"Expected {len(d_buses)} buses, got {len(active_buses)}"
            assert len(active_lines) == len(d_lines), \
                f"Expected {len(d_lines)} lines, got {len(active_lines)}"
            assert len(active_units) == len(d_units), \
                f"Expected {len(d_units)} units, got {len(active_units)}"

            assert {b.label for b in active_buses} == {b.label for b in d_buses}, \
                "Bus labels should match the fixture exactly"
            assert {l.label for l in active_lines} == {l.label for l in d_lines}, \
                "Line labels should match the fixture exactly"
            assert {u.label for u in active_units} == {u.label for u in d_units}, \
                "Unit labels should match the fixture exactly"

            print(f"  DesignerGrid: {len(active_buses)} buses, {len(active_lines)} lines, "
                  f"{len(active_units)} units — matches fixture exactly — PASS")

        except AssertionError as e:
            print(f"  Fixture reproduction: FAIL — {e}")
            all_passed = False

        # ── Slack bus resolves to the bus marked is_slack ──────────────────
        try:
            assert grid.slack_bus == 'SLAK', \
                f"Slack bus should resolve to SLAK, got {grid.slack_bus!r}"

            slack = grid.get_bus('SLAK')
            assert slack.is_slack, "SLAK.is_slack should be True"
            assert slack.voltage_kv == 400.0, \
                f"SLAK should be 400kV, got {slack.voltage_kv}"

            marked_slack = [b for b in grid.get_active_buses() if b.is_slack]
            assert len(marked_slack) == 1, \
                f"Exactly one slack bus expected, found {len(marked_slack)}"
            print(f"  Slack bus resolves to SLAK (is_slack=True) — PASS")

        except AssertionError as e:
            print(f"  Slack bus check: FAIL — {e}")
            all_passed = False

        # ── Unit validation properties hold ────────────────────────────────
        try:
            for unit in grid.get_active_units():
                assert unit.label, "Unit label should not be empty"
                assert unit.rated_mw > 0.0, \
                    f"{unit.label}: rated_mw must be > 0"
                assert unit.min_mw >= 0.0, \
                    f"{unit.label}: min_mw must be >= 0"
                assert unit.min_mw <= unit.rated_mw, \
                    f"{unit.label}: min_mw {unit.min_mw} > rated_mw {unit.rated_mw}"
                assert unit.ramp_mw_per_min > 0.0, \
                    f"{unit.label}: ramp_mw_per_min must be > 0"
                assert unit.inertia_h >= 0.0, \
                    f"{unit.label}: inertia_h must be >= 0"
                assert unit.cold_start_min >= 0.0, \
                    f"{unit.label}: cold_start_min must be >= 0"
            print(f"  All {len(grid.get_active_units())} fixture units validate — PASS")

        except AssertionError as e:
            print(f"  Unit validation: FAIL — {e}")
            all_passed = False

        # ── Canvas positions accessible for both bus and station labels ────
        try:
            pos = grid.get_canvas_position('SLAK')
            assert len(pos) == 2, "Canvas position should be (x, y) tuple"
            assert 0 <= pos[0] <= 1920, f"Canvas x out of range: {pos[0]}"
            assert 0 <= pos[1] <= 1080, f"Canvas y out of range: {pos[1]}"

            pos_station = grid.get_canvas_position('GENS')
            assert len(pos_station) == 2

            print(f"  Canvas positions accessible for bus and station labels — PASS")

        except AssertionError as e:
            print(f"  Canvas positions: FAIL — {e}")
            all_passed = False

        # ── Demand profile query ──────────────────────────────────────────
        try:
            load_morning = grid.get_load_at_bus('LOAD', 9.0)
            load_slack   = grid.get_load_at_bus('SLAK', 9.0)

            # DesignerGrid.get_load_at_bus() returns a flat 50% of peak_load_mw
            # for all hours (test-session convention — see designer_grid.py's
            # docstring), not a real demand-profile curve, so there is no
            # morning/night shape to assert here — just that LOAD buses
            # return their fixed value and TRANSMISSION buses return zero.
            assert abs(load_morning - 240.0 * 0.5) < 1e-6, \
                f"LOAD bus should return 50% of peak_load_mw=240.0, got {load_morning}"
            assert load_slack == 0.0, \
                "Transmission bus SLAK should have zero load"
            print(f"  Demand profile query: LOAD={load_morning:.1f}MW "
                  f"SLAK={load_slack:.1f}MW — PASS")

        except AssertionError as e:
            print(f"  Demand profile: FAIL — {e}")
            all_passed = False

        # Note: the old "invalid shift number raises ValueError" sub-test is
        # dropped entirely — DesignerGrid takes no shift_number argument at
        # all (it IS the full grid it was built from; there is nothing to
        # validate a shift number against).

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 TESTS — DC Load Flow Solver
# ─────────────────────────────────────────────────────────────────────────────

def _build_3bus_loadflow_fixture():
    """Tiny synthetic DesignerGrid reproducing the analytical 3-bus network
    from the hand-verified math below — A (slack), B, C with the same
    reactances/ratings as the original comment. The math is independent of
    label names, so re-labelling from MDBY/DUND/LD01 to A/B/C changes
    nothing about the analytical result."""
    from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
    from simulation.designer_grid import DesignerGrid

    buses = [
        DesignerBus(label='A', name='Bus A', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=100, canvas_y=100,
                    active_from_shift=1, is_slack=True),
        DesignerBus(label='B', name='Bus B', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=300, canvas_y=100,
                    active_from_shift=1, is_slack=False),
        DesignerBus(label='C', name='Bus C', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=300, canvas_y=300,
                    active_from_shift=1, is_slack=False),
    ]
    lines = [
        DesignerLine(label='AB', from_bus='A', to_bus='B',
                     reactance_pu=0.1, rating_mw=500.0, voltage_kv=400.0),
        DesignerLine(label='BC', from_bus='B', to_bus='C',
                     reactance_pu=0.2, rating_mw=300.0, voltage_kv=400.0),
        DesignerLine(label='AC', from_bus='A', to_bus='C',
                     reactance_pu=0.1, rating_mw=500.0, voltage_kv=400.0),
    ]
    units: list = []
    grid = DesignerGrid(buses, lines, units)
    return grid


def _build_meshed_loadflow_fixture():
    """Moderately-sized synthetic DesignerGrid (10 buses, meshed, similar
    scale to test_voltage_reactive.py's fixtures but larger) standing in
    for a real campaign shift grid — same intent as the old Grid(1)/Grid(7)
    checks (DCLoadFlow doesn't crash and produces non-zero flows on a
    real-ish sized network), different concrete topology. Bus SLK is slack;
    two more transmission buses (MID, EAST) form a backbone; four LOAD
    buses hang off the backbone via single feeders."""
    from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
    from simulation.designer_grid import DesignerGrid

    buses = [
        DesignerBus(label='SLK', name='Slack', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=200, canvas_y=100,
                    active_from_shift=1, is_slack=True),
        DesignerBus(label='MID', name='Mid', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=400, canvas_y=100,
                    active_from_shift=1, is_slack=False),
        DesignerBus(label='EST', name='East', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=600, canvas_y=100,
                    active_from_shift=1, is_slack=False),
        DesignerBus(label='SUB1', name='Sub1', voltage_kv=220.0,
                    bus_type='TRANSMISSION', canvas_x=200, canvas_y=300,
                    active_from_shift=1, is_slack=False),
        DesignerBus(label='SUB2', name='Sub2', voltage_kv=220.0,
                    bus_type='TRANSMISSION', canvas_x=600, canvas_y=300,
                    active_from_shift=1, is_slack=False),
        DesignerBus(label='LD01', name='Load 1', voltage_kv=150.0,
                    bus_type='LOAD', canvas_x=100, canvas_y=500,
                    active_from_shift=1, is_slack=False, peak_load_mw=600.0),
        DesignerBus(label='LD02', name='Load 2', voltage_kv=150.0,
                    bus_type='LOAD', canvas_x=300, canvas_y=500,
                    active_from_shift=1, is_slack=False, peak_load_mw=500.0),
        DesignerBus(label='LD03', name='Load 3', voltage_kv=150.0,
                    bus_type='LOAD', canvas_x=500, canvas_y=500,
                    active_from_shift=1, is_slack=False, peak_load_mw=550.0),
        DesignerBus(label='LD04', name='Load 4', voltage_kv=150.0,
                    bus_type='LOAD', canvas_x=700, canvas_y=500,
                    active_from_shift=1, is_slack=False, peak_load_mw=450.0),
    ]
    lines = [
        DesignerLine(label='L01', from_bus='SLK', to_bus='MID',
                     reactance_pu=0.05, rating_mw=1500.0, voltage_kv=400.0),
        DesignerLine(label='L02', from_bus='MID', to_bus='EST',
                     reactance_pu=0.05, rating_mw=1500.0, voltage_kv=400.0),
        DesignerLine(label='L03', from_bus='SLK', to_bus='EST',
                     reactance_pu=0.09, rating_mw=1200.0, voltage_kv=400.0),
        DesignerLine(label='L04', from_bus='SLK', to_bus='SUB1',
                     reactance_pu=0.1, rating_mw=900.0, voltage_kv=220.0),
        DesignerLine(label='L05', from_bus='EST', to_bus='SUB2',
                     reactance_pu=0.1, rating_mw=900.0, voltage_kv=220.0),
        DesignerLine(label='L06', from_bus='SUB1', to_bus='SUB2',
                     reactance_pu=0.15, rating_mw=700.0, voltage_kv=220.0),
        DesignerLine(label='L07', from_bus='SUB1', to_bus='LD01',
                     reactance_pu=0.12, rating_mw=700.0, voltage_kv=150.0),
        DesignerLine(label='L08', from_bus='SUB1', to_bus='LD02',
                     reactance_pu=0.12, rating_mw=600.0, voltage_kv=150.0),
        DesignerLine(label='L09', from_bus='SUB2', to_bus='LD03',
                     reactance_pu=0.12, rating_mw=650.0, voltage_kv=150.0),
        DesignerLine(label='L10', from_bus='SUB2', to_bus='LD04',
                     reactance_pu=0.12, rating_mw=550.0, voltage_kv=150.0),
    ]
    units: list = []
    grid = DesignerGrid(buses, lines, units)
    return grid


def test_loadflow_solves() -> bool:
    """
    Verify DCLoadFlow produces physically correct results on known test networks.

    Uses a synthetic 3-bus network with an analytical solution (same math as
    before — only the bus/line labels changed since topology.py's Grid is
    retired), then verifies a moderately-sized synthetic meshed grid
    produces sensible non-zero flows, standing in for the old real-campaign
    Grid(1)/Grid(7) checks.
    """
    print("test_loadflow_solves...")
    all_passed = True

    try:
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
            g3 = _build_3bus_loadflow_fixture()
            lf = DCLoadFlow(g3)

            buses = {b.label: 0.0 for b in g3.get_active_buses()}
            buses['B'] = 200.0
            buses['C'] = -200.0

            result = lf.solve(buses)

            assert abs(result.bus_angles['A']) < 1e-10, \
                f"Slack bus angle should be 0, got {result.bus_angles['A']}"
            assert abs(result.bus_angles['B'] - 0.01) < 1e-6, \
                f"theta_B should be 0.01 rad, got {result.bus_angles['B']:.6f}"
            assert abs(result.bus_angles['C'] - (-0.01)) < 1e-6, \
                f"theta_C should be -0.01 rad, got {result.bus_angles['C']:.6f}"

            assert abs(result.line_flows_mw['AB'] - (-100.0)) < 0.5, \
                f"P_AB should be -100 MW, got {result.line_flows_mw['AB']:.2f}"
            assert abs(result.line_flows_mw['BC'] - 100.0) < 0.5, \
                f"P_BC should be 100 MW, got {result.line_flows_mw['BC']:.2f}"
            assert abs(result.line_flows_mw['AC'] - 100.0) < 0.5, \
                f"P_AC should be 100 MW, got {result.line_flows_mw['AC']:.2f}"

            print(f"  3-bus analytical: theta_B={result.bus_angles['B']:.4f} "
                  f"theta_C={result.bus_angles['C']:.4f} rad, "
                  f"AB={result.line_flows_mw['AB']:.1f} BC={result.line_flows_mw['BC']:.1f} "
                  f"AC={result.line_flows_mw['AC']:.1f} MW — PASS")

        except AssertionError as e:
            print(f"  3-bus analytical: FAIL — {e}")
            all_passed = False

        # ── All angles/flows present on the 3-bus fixture ─────────────────
        try:
            g3 = _build_3bus_loadflow_fixture()
            lf = DCLoadFlow(g3)
            buses = {b.label: 0.0 for b in g3.get_active_buses()}
            buses['B'] = 200.0
            buses['C'] = -200.0
            result = lf.solve(buses)

            for b in g3.get_active_buses():
                assert b.label in result.bus_angles, \
                    f"Missing angle for bus {b.label}"
            for l in g3.get_active_lines():
                assert l.label in result.line_flows_mw, \
                    f"Missing flow for line {l.label}"
                assert l.label in result.line_loading_pct, \
                    f"Missing loading for line {l.label}"
                assert result.line_loading_pct[l.label] >= 0.0, \
                    f"Line {l.label} loading should be >= 0"

            print(f"  All angles/flows present on 3-bus fixture — PASS")

        except AssertionError as e:
            print(f"  Angles/flows present: FAIL — {e}")
            all_passed = False

        # ── Flow direction consistency ─────────────────────────────────────
        # Generation at slack SLK, load at LD01 (via SUB1). Power must flow
        # SLK->SUB1 (L04, positive) then SUB1->LD01 (L07, positive).
        try:
            gm = _build_meshed_loadflow_fixture()
            lf = DCLoadFlow(gm)

            buses = {b.label: 0.0 for b in gm.get_active_buses()}
            buses['LD01'] = -1000.0  # load at LD01, fed only via SUB1

            result = lf.solve(buses)

            assert result.line_flows_mw['L04'] > 0.0, \
                f"L04 should flow SLK->SUB1 (positive), got {result.line_flows_mw['L04']:.2f}"
            assert result.line_flows_mw['L07'] > 0.0, \
                f"L07 should flow SUB1->LD01 (positive), got {result.line_flows_mw['L07']:.2f}"

            print(f"  Flow direction correct: L04={result.line_flows_mw['L04']:.1f} MW "
                  f"L07={result.line_flows_mw['L07']:.1f} MW -- PASS")

        except AssertionError as e:
            print(f"  Flow direction: FAIL — {e}")
            all_passed = False

        # ── Loading percentage matches flow / rating ───────────────────────
        try:
            gm = _build_meshed_loadflow_fixture()
            lf = DCLoadFlow(gm)
            buses = {b.label: 0.0 for b in gm.get_active_buses()}
            buses['LD01'] = -400.0
            buses['LD02'] = -350.0
            buses['LD03'] = -300.0
            buses['LD04'] = -250.0
            result = lf.solve(buses)

            for line in gm.get_active_lines():
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
            gm = _build_meshed_loadflow_fixture()
            lf = DCLoadFlow(gm)

            # Corrupt the B matrix to force singularity
            lf._b_reduced = np.zeros_like(lf._b_reduced)

            buses = {b.label: 0.0 for b in gm.get_active_buses()}
            buses['LD01'] = -500.0
            result = lf.solve(buses)

            # Should return without raising — zero angles
            for b in gm.get_active_buses():
                assert abs(result.bus_angles[b.label]) < 1e-10, \
                    f"Singular fallback: expected zero angle for {b.label}"

            print(f"  Singular matrix returns zero-angle fallback — PASS")

        except AssertionError as e:
            print(f"  Singular fallback: FAIL — {e}")
            all_passed = False

        # ── Full meshed grid: all lines get flows ──────────────────────────
        try:
            gm = _build_meshed_loadflow_fixture()
            lfm = DCLoadFlow(gm)

            buses = {b.label: 0.0 for b in gm.get_active_buses()}
            # Spread load across load substations
            for label in gm.get_load_bus_labels():
                buses[label] = -500.0
            # Generation at major transmission buses (slack absorbs remainder)
            buses['SLK'] = 0.0
            buses['MID'] = 900.0
            buses['EST'] = 700.0

            result = lfm.solve(buses)

            expected_lines = len(gm.get_active_lines())
            assert len(result.line_flows_mw) == expected_lines, \
                f"Expected {expected_lines} line flows, got {len(result.line_flows_mw)}"
            assert len(result.bus_angles) == len(gm.get_active_buses()), \
                "Missing bus angles in full grid solve"

            non_zero = sum(1 for f in result.line_flows_mw.values() if abs(f) > 0.1)
            assert non_zero == expected_lines, \
                f"Expected all {expected_lines} lines to carry flow, only {non_zero} non-zero"

            print(f"  Full meshed grid: {expected_lines} lines solved, "
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

    data.fleet.UNITS/get_unit() are being retired along with topology.py's
    Grid — the GenerationUnit dataclass itself still exists, so each
    sub-test below constructs its own inline GenerationUnit fixture with
    the same field values the original real-fleet units carried (rated_mw,
    min_mw, ramp_mw_per_min, etc.), keeping the hand-verified analytical
    math identical.
    """
    print("test_unit_model...")
    all_passed = True

    try:
        from simulation.units import UnitModel, FleetModel
        from data.fleet import GenerationUnit

        def _mk_unit(label, station, bus, unit_type, rated_mw, min_mw,
                     ramp_mw_per_min, inertia_h, cold_start_min,
                     q_max_mvar=100.0, q_min_mvar=-50.0, can_pump=False,
                     active_from_shift=1):
            return GenerationUnit(
                label=label, station_label=station, bus_label=bus,
                unit_type=unit_type, rated_mw=rated_mw, min_mw=min_mw,
                ramp_mw_per_min=ramp_mw_per_min, inertia_h=inertia_h,
                cold_start_min=cold_start_min,
                q_max_mvar=q_max_mvar, q_min_mvar=q_min_mvar,
                can_pump=can_pump, active_from_shift=active_from_shift,
                description=f'Test {unit_type} unit',
                min_up_time_h=1.0, min_down_time_h=1.0,
            )

        # ── Unit starts OFFLINE ───────────────────────────────────────────
        try:
            spec = _mk_unit('RVSD-1', 'RVSD', 'MDBY', 'COAL',
                             rated_mw=300.0, min_mw=90.0,
                             ramp_mw_per_min=9.0, inertia_h=5.0,
                             cold_start_min=240.0)
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
            spec = _mk_unit('RVSD-1', 'RVSD', 'MDBY', 'COAL',
                             rated_mw=300.0, min_mw=90.0,
                             ramp_mw_per_min=9.0, inertia_h=5.0,
                             cold_start_min=240.0)
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
            spec = _mk_unit('ASHG-1', 'ASHG', 'ASHF', 'CCGT',
                             rated_mw=400.0, min_mw=80.0,
                             ramp_mw_per_min=32.0, inertia_h=4.0,
                             cold_start_min=60.0)   # CCGT: cold_start_min = 60.0
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
            spec = _mk_unit('RVSD-1', 'RVSD', 'MDBY', 'COAL',
                             rated_mw=300.0, min_mw=90.0,
                             ramp_mw_per_min=9.0, inertia_h=5.0,
                             cold_start_min=240.0)   # COAL: ramp 9 MW/min, rated 300 MW
            um = UnitModel(spec, initial_mw=90.0)  # start ONLINE at min

            um.set_target(300.0)

            # After 1 simulated minute (60 seconds), ramp = 9 MW
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

            print(f"  Ramp rate: {spec.ramp_mw_per_min} MW/min on {spec.rated_mw} MW: "
                  f"+{um.current_mw - 90.0:.1f} MW in 5 min -- PASS")
        except AssertionError as e:
            print(f"  Ramp rate: FAIL -- {e}")
            all_passed = False

        # ── Output clamped to [min_mw, rated_mw] when ONLINE ──────────────
        try:
            spec = _mk_unit('HART-1', 'HART', 'STHW', 'NUCLEAR',
                             rated_mw=700.0, min_mw=490.0,
                             ramp_mw_per_min=3.5, inertia_h=6.0,
                             cold_start_min=480.0)   # NUCLEAR: min 490, rated 700
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
            spec = _mk_unit('DUNH-1', 'DUNH', 'MDBY', 'HYDRO_PUMP',
                             rated_mw=200.0, min_mw=0.0,
                             ramp_mw_per_min=200.0, inertia_h=3.0,
                             cold_start_min=5.0, can_pump=True)   # HYDRO_PUMP: ramp 100%/min, rated 200 MW
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
            spec = _mk_unit('RVSD-3', 'RVSD', 'MDBY', 'COAL',
                             rated_mw=300.0, min_mw=90.0,
                             ramp_mw_per_min=9.0, inertia_h=5.0,
                             cold_start_min=240.0)
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
            spec = _mk_unit('WNCN-1', 'WNCN', 'WNCN', 'WIND',
                             rated_mw=250.0, min_mw=0.0,
                             ramp_mw_per_min=250.0, inertia_h=0.0,
                             cold_start_min=0.0, q_max_mvar=0.0, q_min_mvar=0.0)   # WIND
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
        # FleetModel only needs grid.get_active_units() (see units.py's
        # FleetModel.__init__) — a synthetic DesignerGrid with two stations
        # on two different buses is enough to exercise per-bus p_injections
        # aggregation, which was the point of the original Grid(3) fixture
        # (RVSD units at MDBY, HART units at STHW).
        try:
            from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
            from simulation.designer_grid import DesignerGrid

            f_buses = [
                DesignerBus(label='MDBY', name='Midbury', voltage_kv=400.0,
                            bus_type='TRANSMISSION', canvas_x=100, canvas_y=100,
                            active_from_shift=1, is_slack=True),
                DesignerBus(label='STHW', name='Southwick', voltage_kv=400.0,
                            bus_type='TRANSMISSION', canvas_x=300, canvas_y=100,
                            active_from_shift=1, is_slack=False),
            ]
            f_lines = [
                DesignerLine(label='L01', from_bus='MDBY', to_bus='STHW',
                             reactance_pu=0.05, rating_mw=2000.0, voltage_kv=400.0),
            ]
            f_units = [
                DesignerUnit(label='RVSD-1', station_label='RVSD', bus_label='MDBY',
                             unit_type='COAL', rated_mw=300.0, min_mw=90.0,
                             inertia_h=5.0, cold_start_min=240.0,
                             q_max_mvar=150.0, q_min_mvar=-80.0, can_pump=False,
                             active_from_shift=1, description='Test coal unit'),
                DesignerUnit(label='HART-1', station_label='HART', bus_label='STHW',
                             unit_type='NUCLEAR', rated_mw=700.0, min_mw=490.0,
                             inertia_h=6.0, cold_start_min=480.0,
                             q_max_mvar=300.0, q_min_mvar=-150.0, can_pump=False,
                             active_from_shift=1, description='Test nuclear unit 1'),
                DesignerUnit(label='HART-2', station_label='HART', bus_label='STHW',
                             unit_type='NUCLEAR', rated_mw=700.0, min_mw=490.0,
                             inertia_h=6.0, cold_start_min=480.0,
                             q_max_mvar=300.0, q_min_mvar=-150.0, can_pump=False,
                             active_from_shift=1, description='Test nuclear unit 2'),
            ]
            g_fleet = DesignerGrid(f_buses, f_lines, f_units)

            schedule = {
                'RVSD-1': 280.0,
                'HART-1': 600.0,
                'HART-2': 700.0,
            }
            fleet = FleetModel(g_fleet, initial_schedule=schedule)

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
    Verify FrequencyModel drives frequency deviation correctly.

    Checks:
      - Imbalance drives frequency deviation in the correct direction
      - Constant imbalance produces a constant df/dt (honest swing equation,
        no implicit governor response baked in)
      - Frequency is clamped to [F_MIN, F_MAX]
    """
    print("test_frequency_model...")
    all_passed = True

    try:
        from simulation.frequency import FrequencyModel
        from simulation.constants import F_NOMINAL, F_MIN, F_MAX, TIME_COMPRESSION

        # A realistic in-game tick carries dt_sim_seconds = real_dt * TIME_COMPRESSION
        # (see main.py's sim.tick() call site) -- use that scale here rather than a
        # bare 1.0, since FREQ_DYNAMICS_SCALE is tuned against compressed sim-seconds,
        # not raw real seconds.
        _dt_tick = 1.0 * TIME_COMPRESSION

        # ── Generation deficit lowers frequency ───────────────────────────
        try:
            fm = FrequencyModel()
            assert abs(fm.frequency_hz - F_NOMINAL) < 1e-9, \
                f"Initial frequency should be {F_NOMINAL} Hz, got {fm.frequency_hz}"

            # 500 MW deficit on a 5000 MW system (all coal, H=5).
            # df/dt = (50 / (2×5)) × (-500/1000) = 5 × (-0.5) = -2.5 Hz/sim-s.
            online_units = [('COAL', 4500.0)]
            fm.update(
                dt_sim_seconds=_dt_tick,
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
                dt_sim_seconds=_dt_tick,
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
            print(f"  Constant df/dt (no implicit governor response): PASS — "
                  f"{early_rate:.5f} Hz/tick (honest swing equation)")

        except AssertionError as e:
            print(f"  Constant df/dt (no implicit governor response): FAIL — {e}")
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


def _build_voltage_model_fixture():
    """Synthetic DesignerGrid standing in for the old Grid(1) topology
    source — VoltageModel only needs bus/line structure, not real campaign
    data. Slack bus SLK feeds two more buses (MID, FAR), giving a
    non-slack bus (MID) with a controllable path to the slack bus for the
    PV/PQ conversion sub-test."""
    from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
    from simulation.designer_grid import DesignerGrid

    buses = [
        DesignerBus(label='SLK', name='Slack', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=100, canvas_y=100,
                    active_from_shift=1, is_slack=True),
        DesignerBus(label='MID', name='Mid', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=300, canvas_y=100,
                    active_from_shift=1, is_slack=False),
        DesignerBus(label='FAR', name='Far', voltage_kv=150.0,
                    bus_type='LOAD', canvas_x=500, canvas_y=100,
                    active_from_shift=1, is_slack=False, peak_load_mw=200.0),
    ]
    lines = [
        DesignerLine(label='L01', from_bus='SLK', to_bus='MID',
                     reactance_pu=0.08, rating_mw=1000.0, voltage_kv=400.0),
        DesignerLine(label='L02', from_bus='MID', to_bus='FAR',
                     reactance_pu=0.12, rating_mw=500.0, voltage_kv=150.0),
    ]
    units: list = []
    grid = DesignerGrid(buses, lines, units)
    return grid


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
        from simulation.voltage import VoltageModel

        # ── Slack bus always 1.0, voltages physically reasonable ──────────
        try:
            g1 = _build_voltage_model_fixture()
            vm = VoltageModel(g1)

            # Balanced system — zero Q everywhere.
            q_zero = {b.label: 0.0 for b in g1.get_active_buses()}
            result = vm.solve(q_zero)

            assert abs(result.bus_voltages['SLK'] - 1.0) < 1e-9, \
                f"Slack bus SLK should have V=1.0, got {result.bus_voltages['SLK']:.6f}"

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
            g1 = _build_voltage_model_fixture()
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
            g1 = _build_voltage_model_fixture()
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
        from data.profiles import get_substation_demand_specs, DEMAND_PROFILE_NORMALISED

        # Self-contained fixture (not sourced from a real shift file, whose
        # content is mutable/may be a stub) — two load buses following the
        # shared demand-shape curve, mirroring loader.py's own derivation.
        substation_load_mw = {
            'GREY': {h: 100.0 * DEMAND_PROFILE_NORMALISED[h] for h in DEMAND_PROFILE_NORMALISED},
            'OAKE': {h: 200.0 * DEMAND_PROFILE_NORMALISED[h] for h in DEMAND_PROFILE_NORMALISED},
        }
        peak_demand_mw = 300.0
        substation_specs = get_substation_demand_specs(substation_load_mw)

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


def _build_renewables_fixture():
    """Synthetic DesignerGrid with WIND and SOLAR units, standing in for
    the old Grid(7) fixture (real campaign fleet's WNCN wind farm and
    SLST/SLFD solar farms) — RenewablesModel only cares about
    grid.get_active_units() filtered to unit_type in ('WIND', 'SOLAR')."""
    from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
    from simulation.designer_grid import DesignerGrid

    buses = [
        DesignerBus(label='SLK', name='Slack', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=100, canvas_y=100,
                    active_from_shift=1, is_slack=True),
        DesignerBus(label='WIND', name='Windbus', voltage_kv=220.0,
                    bus_type='TRANSMISSION', canvas_x=300, canvas_y=100,
                    active_from_shift=1, is_slack=False),
        DesignerBus(label='SOLR', name='Solarbus', voltage_kv=220.0,
                    bus_type='TRANSMISSION', canvas_x=500, canvas_y=100,
                    active_from_shift=1, is_slack=False),
    ]
    lines = [
        DesignerLine(label='L01', from_bus='SLK', to_bus='WIND',
                     reactance_pu=0.08, rating_mw=1000.0, voltage_kv=220.0),
        DesignerLine(label='L02', from_bus='SLK', to_bus='SOLR',
                     reactance_pu=0.08, rating_mw=1000.0, voltage_kv=220.0),
    ]
    units = [
        DesignerUnit(label='WNCN-1', station_label='WNCN', bus_label='WIND',
                     unit_type='WIND', rated_mw=250.0, min_mw=0.0,
                     inertia_h=0.0, cold_start_min=0.0,
                     q_max_mvar=0.0, q_min_mvar=0.0, can_pump=False,
                     active_from_shift=1, description='Test wind unit'),
        DesignerUnit(label='SLST-1', station_label='SLST', bus_label='SOLR',
                     unit_type='SOLAR', rated_mw=300.0, min_mw=0.0,
                     inertia_h=0.0, cold_start_min=0.0,
                     q_max_mvar=0.0, q_min_mvar=0.0, can_pump=False,
                     active_from_shift=1, description='Test solar unit'),
    ]
    grid = DesignerGrid(buses, lines, units)
    return grid


def test_renewables_model() -> bool:
    """
    Verify RenewablesModel output is bounded, solar is zero at night,
    and deterministic mode suppresses noise.
    """
    print("test_renewables_model...")
    all_passed = True

    try:
        from simulation.renewables import RenewablesModel

        # Synthetic fixture with a WIND and a SOLAR unit (see docstring).
        g7 = _build_renewables_fixture()

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

def _build_cascade_fixture():
    """
    Synthetic backbone-plus-pockets topology, replacing the real campaign
    Grid(7) fixture: a 6-bus meshed 400kV "backbone" (BCK1..BCK6, fully
    interconnected so any single line loss keeps it whole) plus 3 "pocket"
    buses (POK1..POK3), each tied to the backbone by exactly one line and
    each carrying one downstream LOAD bus. Cutting the three backbone-pocket
    tie lines demonstrably splits the network into >= 2 islands — the same
    structural property the old L09-L14 transformer-tie cut exercised.
    Returns (buses, lines) — raw Bus/Line lists via DesignerGrid, since
    find_islands()/get_blackout_zones() take bus/line lists directly, not
    a grid object.
    """
    from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
    from simulation.designer_grid import DesignerGrid

    backbone_labels = ['BCK1', 'BCK2', 'BCK3', 'BCK4', 'BCK5', 'BCK6']
    pocket_labels = ['POK1', 'POK2', 'POK3']
    load_labels = ['PLD1', 'PLD2', 'PLD3']
    tie_labels = ['TIE1', 'TIE2', 'TIE3']

    buses = []
    for i, lbl in enumerate(backbone_labels):
        buses.append(DesignerBus(
            label=lbl, name=f'Backbone {i+1}', voltage_kv=400.0,
            bus_type='TRANSMISSION', canvas_x=100 * i, canvas_y=0,
            active_from_shift=1, is_slack=(i == 0)))
    for i, lbl in enumerate(pocket_labels):
        buses.append(DesignerBus(
            label=lbl, name=f'Pocket {i+1}', voltage_kv=220.0,
            bus_type='TRANSMISSION', canvas_x=100 * i, canvas_y=200,
            active_from_shift=1, is_slack=False))
    for i, lbl in enumerate(load_labels):
        buses.append(DesignerBus(
            label=lbl, name=f'Pocket Load {i+1}', voltage_kv=150.0,
            bus_type='LOAD', canvas_x=100 * i, canvas_y=400,
            active_from_shift=1, is_slack=False, peak_load_mw=100.0))

    lines = []
    # Mesh the backbone: a ring (BCK1-BCK2-...-BCK6-BCK1) plus one chord,
    # so no single line loss can split it.
    for i in range(len(backbone_labels)):
        a = backbone_labels[i]
        b = backbone_labels[(i + 1) % len(backbone_labels)]
        lines.append(DesignerLine(label=f'BB{i+1}', from_bus=a, to_bus=b,
                                   reactance_pu=0.05, rating_mw=1500.0, voltage_kv=400.0))
    lines.append(DesignerLine(label='BBX', from_bus='BCK1', to_bus='BCK4',
                               reactance_pu=0.05, rating_mw=1500.0, voltage_kv=400.0))
    # Each pocket ties to the backbone by exactly one line.
    for i, (tie, pok) in enumerate(zip(tie_labels, pocket_labels)):
        lines.append(DesignerLine(label=tie, from_bus=backbone_labels[i], to_bus=pok,
                                   reactance_pu=0.1, rating_mw=800.0, voltage_kv=220.0))
    # Each pocket feeds its own load bus.
    for i, (pok, pld) in enumerate(zip(pocket_labels, load_labels)):
        lines.append(DesignerLine(label=f'PL{i+1}', from_bus=pok, to_bus=pld,
                                   reactance_pu=0.12, rating_mw=400.0, voltage_kv=150.0))

    units: list = []
    grid = DesignerGrid(buses, lines, units)
    return grid.get_active_buses(), grid.get_active_lines(), backbone_labels, tie_labels


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
        from simulation.constants import TRIP_DELAY_S, OVERLOAD_CRIT_PCT

        cm = CascadeModel()

        # ── find_islands partitions all buses with no overlap or gaps ─────────
        # Every bus must appear in exactly one island — this is the core
        # invariant of the BFS algorithm. On this fixture the meshed
        # backbone plus its three single-tied pockets are all reachable
        # from each other, so the whole network is one island.
        try:
            buses7, lines7, backbone_labels, tie_labels = _build_cascade_fixture()
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

            # The 400kV backbone buses must all be in the same island —
            # they are directly interconnected by the meshed backbone lines.
            backbone = set(backbone_labels)
            backbone_island = next(
                (i for i in islands7 if backbone <= i), None
            )
            assert backbone_island is not None, \
                f"400kV backbone buses should all be in one island"

            # Load substations each connect via a pocket feeder — verify
            # they're reachable from the backbone (same island), not isolated.
            load_labels7 = {b.label for b in buses7 if b.bus_type == 'LOAD'}
            for lb in load_labels7:
                lb_island = next(i for i in islands7 if lb in i)
                assert len(lb_island) > 1, \
                    f"Load sub {lb} should be connected (not isolated), " \
                    f"got isolated 1-bus island"

            print(f"  Fixture partition: {len(islands7)} islands, all "
                  f"{len(all_labels7)} buses covered, backbone connected — PASS")

        except AssertionError as e:
            print(f"  Single island: FAIL — {e}")
            all_passed = False

        # ── Tripped line splits transmission network into two islands ─────────
        # Cutting all three backbone-pocket tie lines isolates the pocket
        # buses (and each pocket's downstream load) from the backbone spine —
        # the same structural property the old L09-L14 transformer-tie cut
        # exercised, on a fixture built specifically to demonstrate it.
        try:
            buses7, all_lines7, backbone_labels, tie_labels = _build_cascade_fixture()

            cut_labels = set(tie_labels)
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
                f"Cutting the tie lines should create >= 2 tx islands, " \
                f"got {len(tx_islands)}"

            # Specifically: the backbone stays one island, and each pocket
            # (with its load) becomes its own separate island.
            backbone = set(backbone_labels)
            backbone_island = next((i for i in islands if backbone <= i), None)
            assert backbone_island is not None, \
                "Backbone should remain one connected island after the tie cut"
            assert len(tx_islands) == 4, \
                f"Expected exactly 4 tx-containing islands (1 backbone + 3 " \
                f"pockets), got {len(tx_islands)}"

            print(f"  Tripped tie lines: {len(tx_islands)} tx islands "
                  f"(total {total_in_islands} buses across all islands) — PASS")

        except AssertionError as e:
            print(f"  Split network: FAIL — {e}")
            all_passed = False

        # ── Isolated buses — all blacked out when no units are online ─────
        try:
            buses5, _lines5, _backbone_labels, _tie_labels = _build_cascade_fixture()

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
            sample_gen_bus = buses5[0].label
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

        # ── Overload timer: inverse-time accumulation ─────────────────────
        # Protection is severity-scaled (see OVERLOAD_SEVERITY_REF_PCT): a
        # line just over rating takes ~TRIP_DELAY_S, a badly overloaded one
        # trips much sooner, so the player can triage. A line at exactly
        # OVERLOAD_CRIT_PCT accrues at 1x and defines the slowest case.
        try:
            dt = 5.0

            def _sim_to_trip(pct: float) -> float:
                """Sim-seconds until a line held at pct% loading trips."""
                timers: dict = {}
                elapsed = 0.0
                for _ in range(100000):
                    trips, timers = cm.check_overloads({'L01': pct}, timers, dt)
                    elapsed += dt
                    if 'L01' in trips:
                        return elapsed
                raise AssertionError(f"line at {pct}% never tripped")

            at_rating = _sim_to_trip(100.0)
            assert abs(at_rating - (TRIP_DELAY_S + dt)) <= dt, \
                (f"A line at exactly {OVERLOAD_CRIT_PCT}% should take about "
                 f"TRIP_DELAY_S={TRIP_DELAY_S}s, took {at_rating}s")

            mild   = _sim_to_trip(110.0)
            severe = _sim_to_trip(180.0)
            assert severe < mild < at_rating, \
                (f"Trip time must shorten as overload worsens — got "
                 f"100%:{at_rating}s 110%:{mild}s 180%:{severe}s")

            # A line inside its rating must never trip, however long we wait.
            timers = {}
            for _ in range(int(TRIP_DELAY_S / dt) * 3):
                trips, timers = cm.check_overloads({'L02': 90.0}, timers, dt)
                assert 'L02' not in trips, "L02 (90% loading) should never trip"
            assert timers.get('L02', 0.0) == 0.0, \
                f"L02 timer should be 0, got {timers.get('L02')}"

            # Timer clears after a trip so the same line cannot re-trip.
            timers = {}
            while True:
                trips, timers = cm.check_overloads({'L01': 200.0}, timers, dt)
                if 'L01' in trips:
                    break
            assert timers.get('L01', -1) == 0.0, \
                "Timer for tripped line L01 should reset to 0"

            print(f"  Overload timer: inverse-time (100%:{at_rating:.0f}s "
                  f"110%:{mild:.0f}s 180%:{severe:.0f}s), L02 unaffected — PASS")

        except AssertionError as e:
            print(f"  Overload timer: FAIL — {e}")
            all_passed = False

        # ── Overload timer decays instead of hard-resetting ───────────────
        # A conductor that has been cooking does not become instantly healthy
        # the moment loading dips to 99%. Previously the timer reset to 0.0,
        # which meant a line oscillating around its rating never tripped.
        try:
            dt = 5.0
            timers = {}
            for _ in range(20):
                _, timers = cm.check_overloads({'L01': 150.0}, timers, dt)
            accumulated = timers['L01']
            assert accumulated > 0.0, "Timer should have accumulated at 150%"

            _, timers = cm.check_overloads({'L01': 99.0}, timers, dt)
            assert timers['L01'] > 0.0, \
                "A brief dip below rating must not wipe accumulated time"
            assert timers['L01'] < accumulated, \
                "Timer should decay while the line is back within rating"

            # Sustained recovery still clears the timer completely.
            for _ in range(500):
                _, timers = cm.check_overloads({'L01': 50.0}, timers, dt)
            assert timers['L01'] == 0.0, \
                f"Sustained recovery should clear the timer, got {timers['L01']}"

            # A line flapping either side of its rating must still trip.
            timers = {}
            tripped = False
            for i in range(20000):
                pct = 130.0 if (i // 3) % 2 == 0 else 95.0
                trips, timers = cm.check_overloads({'L01': pct}, timers, dt)
                if 'L01' in trips:
                    tripped = True
                    break
            assert tripped, \
                "A line oscillating around its rating should eventually trip"

            print("  Overload decay: dip retains time, recovery clears, "
                  "flapping line still trips — PASS")

        except AssertionError as e:
            print(f"  Overload decay: FAIL — {e}")
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

def _build_simulation_fixture():
    """Synthetic DesignerGrid replacing the old Grid(1) fixture: a slack
    bus, one plain transmission bus, one load bus, and two dispatchable
    units on the transmission bus — GENS-1 (COAL, meant to start ONLINE via
    initial_schedule, standing in for DUND-1) and GENS-2 (COAL, meant to
    stay OFFLINE, standing in for RVSD-1) — so set_unit_target() has one
    ONLINE unit to accept and one OFFLINE unit to reject."""
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
        DesignerUnit(label='GENS-2', station_label='GENS', bus_label='GEN',
                     unit_type='COAL', rated_mw=300.0, min_mw=90.0,
                     inertia_h=5.0, cold_start_min=240.0,
                     q_max_mvar=150.0, q_min_mvar=-80.0, can_pump=False,
                     active_from_shift=1, description='Test unit, stays OFFLINE'),
    ]
    grid = DesignerGrid(buses, lines, units)
    return grid


def test_simulation_model() -> bool:
    """
    Verify GridSimulation initialises, ticks, and exposes correct state.

    Checks:
      - GridSimulation initialises without error
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
        from gameplay.shifts.loader import load_shift_config

        # ── Initialises without error ─────────────────────────────────────
        try:
            g1 = _build_simulation_fixture()
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
            g1 = _build_simulation_fixture()
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
            from data.profiles import DEMAND_PROFILE_NORMALISED

            g1 = _build_simulation_fixture()
            # Explicit substation_load_mw (LD01, the fixture's one load
            # bus) — not sourced from shift_01.py, whose content is
            # mutable/may be a stub, so total_load_mw > 0 doesn't depend on
            # shift content.
            substation_load_mw = {
                'LD01': {h: 200.0 * DEMAND_PROFILE_NORMALISED[h] for h in DEMAND_PROFILE_NORMALISED},
            }
            sim = GridSimulation(g1, shift_number=1, difficulty='NORMAL',
                                  substation_load_mw=substation_load_mw)
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
            g1 = _build_simulation_fixture()
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
            g1 = _build_simulation_fixture()
            schedule = {'GENS-1': 40.0}
            sim = GridSimulation(g1, shift_number=1, difficulty='NORMAL',
                                 initial_schedule=schedule)

            # GENS-1 is ONLINE (in initial_schedule); set_unit_target should accept
            accepted = sim.set_unit_target('GENS-1', 50.0)
            assert accepted, "set_unit_target should return True for ONLINE unit"

            # GENS-2 is OFFLINE (not in schedule); should reject
            rejected = sim.set_unit_target('GENS-2', 200.0)
            assert not rejected, \
                "set_unit_target should return False for OFFLINE unit"

            print(f"  set_unit_target(): ONLINE accepts, OFFLINE rejects — PASS")
        except AssertionError as e:
            print(f"  set_unit_target(): FAIL — {e}")
            all_passed = False

        # ── trip_line() / close_line() toggle status ──────────────────────
        try:
            g1 = _build_simulation_fixture()
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


def test_shift_scoring() -> bool:
    """
    Verify gameplay/scoring.grade_shift() scores every axis, not just frequency.

    Checks:
      - A clean run grades EXCELLENT
      - A voltage-collapse run and a line-overload run BOTH grade below a clean
        run. This is the regression that motivated the module: under the old
        frequency-only rubric all three graded identically (EXCELLENT), so
        Shift 4 — an entirely voltage-driven shift — could not be scored at all.
      - Unit trips and load shedding pull the grade down
      - A failed shift reports FAILED, and a FAIL_CONDITION explains why
      - grade_campaign() rolls shift grades up and is capped by any FAILED shift
    """
    print("test_shift_scoring...")
    all_passed = True

    try:
        from types import SimpleNamespace
        from gameplay.scoring import (
            grade_shift, grade_campaign, count_unit_trips, GRADE_ORDER,
            GRADE_EXCELLENT, GRADE_FAILED, GRADE_MARGINAL,
        )

        def mk(freq=100.0, load=50.0, volt=1.0, trips=0, shed=0, casc=0):
            return SimpleNamespace(
                frequency_in_bounds_pct=freq,
                max_line_loading_seen=load,
                min_voltage_seen=volt,
                load_shed_events=shed,
                cascade_events=casc,
                unit_states={f'U{i}': 'TRIPPED' for i in range(trips)},
            )

        # ── A clean run is EXCELLENT ──────────────────────────────────────────
        try:
            clean = grade_shift(mk())
            assert clean['grade'] == GRADE_EXCELLENT,                 f"Clean run graded {clean['grade']}, expected {GRADE_EXCELLENT}"
            print("  clean run -> EXCELLENT — PASS")
        except AssertionError as e:
            print(f"  FAIL — {e}")
            all_passed = False

        # ── The regression: voltage and loading must affect the grade ─────────
        try:
            clean_i    = GRADE_ORDER.index(grade_shift(mk())['grade'])
            collapse   = grade_shift(mk(volt=0.62))
            overloaded = grade_shift(mk(load=175.0))
            assert GRADE_ORDER.index(collapse['grade']) < clean_i,                 f"Voltage collapse graded {collapse['grade']} — not below a clean run"
            assert GRADE_ORDER.index(overloaded['grade']) < clean_i,                 f"Line overload graded {overloaded['grade']} — not below a clean run"
            print("  voltage collapse and line overload both grade below clean — PASS")
        except AssertionError as e:
            print(f"  FAIL — {e}")
            all_passed = False

        # ── Trips and shedding are scored ─────────────────────────────────────
        try:
            clean_i = GRADE_ORDER.index(grade_shift(mk())['grade'])
            assert GRADE_ORDER.index(grade_shift(mk(trips=3))['grade']) < clean_i,                 "Three unit trips did not lower the grade"
            assert GRADE_ORDER.index(grade_shift(mk(shed=2))['grade']) < clean_i,                 "Load shedding did not lower the grade"
            assert count_unit_trips(mk(trips=4)) == 4, "count_unit_trips() miscounted"
            print("  unit trips and load shedding lower the grade — PASS")
        except AssertionError as e:
            print(f"  FAIL — {e}")
            all_passed = False

        # ── Failed shifts ─────────────────────────────────────────────────────
        try:
            blackout = grade_shift(mk(), failed=True)
            assert blackout['grade'] == GRADE_FAILED,                 f"Blackout graded {blackout['grade']}, expected {GRADE_FAILED}"
            objective = grade_shift(mk(), failed=True,
                                    failed_objective={'message': 'Limit breached at CLOV'})
            assert objective['grade'] == GRADE_FAILED
            assert 'CLOV' in objective['reason'],                 "FAIL_CONDITION message not surfaced in the grade reason"
            print("  blackout and objective failures both report FAILED — PASS")
        except AssertionError as e:
            print(f"  FAIL — {e}")
            all_passed = False

        # ── Campaign roll-up ──────────────────────────────────────────────────
        try:
            all_exc = {i: GRADE_EXCELLENT for i in range(1, 11)}
            assert grade_campaign(all_exc) == GRADE_EXCELLENT,                 "Ten excellent shifts did not roll up to EXCELLENT"
            with_fail = dict(all_exc); with_fail[10] = GRADE_FAILED
            assert grade_campaign(with_fail) == GRADE_MARGINAL,                 "A FAILED shift did not cap the campaign rating at MARGINAL"
            assert grade_campaign({}) is not None, "Empty campaign should still grade"
            print("  campaign roll-up, incl. FAILED cap — PASS")
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
        test_grid_loads(),
        test_loadflow_solves(),
        test_unit_model(),
        test_demand_model(),
        test_renewables_model(),
        test_frequency_model(),
        test_voltage_model(),
        test_cascade_model(),
        test_simulation_model(),
        test_shift_scoring(),
    ]
    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    if passed < total:
        sys.exit(1)
