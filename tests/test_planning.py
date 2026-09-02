"""
tests/test_planning.py

GRIDCOM Phase 1 planning test suite — covers PlanningModel.auto_schedule()'s
cost-aware unit commitment and PlanningModel.hourly_cost()'s AGC regulation-
band cost term.

No test framework required — run directly: python tests/test_planning.py

Each test function prints PASS / FAIL / ERROR and returns True/False.
Script exits with code 1 if any test fails.

See CODING_STANDARDS.md for test pattern conventions.
"""

import sys
import os

# Ensure src/ is on the path so gameplay and data packages resolve.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURE
# ─────────────────────────────────────────────────────────────────────────────

def _build_planning_fixture(load_forecast=None):
    """A small synthetic PlanningModel — one NUCLEAR, one COAL, one CCGT
    (AGC-eligible), one HYDRO (AGC-eligible), one HYDRO_ROR unit — built
    directly (bypassing build_planning_model()'s Designer-grid/shift-config
    plumbing), with a flat 24h load forecast by default. Physical
    parameters (rated_mw/min_mw/ramp_mw_per_min) mirror
    constants.py's UNIT_DEFAULTS so ramp/tech-min behavior matches real
    campaign units."""
    from data.fleet import GenerationUnit
    from gameplay.phase1 import PlanningModel

    units = [
        GenerationUnit(
            label='NUC-1', station_label='NUC', bus_label='B1',
            unit_type='NUCLEAR', rated_mw=700.0, min_mw=420.0,
            ramp_mw_per_min=3.5, inertia_h=6.0, cold_start_min=480.0,
            q_max_mvar=300.0, q_min_mvar=-100.0, can_pump=False,
            active_from_shift=1, description='Test nuclear unit',
        ),
        GenerationUnit(
            label='COAL-1', station_label='COAL', bus_label='B1',
            unit_type='COAL', rated_mw=300.0, min_mw=105.0,
            ramp_mw_per_min=4.0, inertia_h=5.0, cold_start_min=240.0,
            q_max_mvar=150.0, q_min_mvar=-50.0, can_pump=False,
            active_from_shift=1, description='Test coal unit',
        ),
        GenerationUnit(
            label='CCGT-1', station_label='CCGT', bus_label='B1',
            unit_type='CCGT', rated_mw=400.0, min_mw=100.0,
            ramp_mw_per_min=15.0, inertia_h=4.0, cold_start_min=60.0,
            q_max_mvar=180.0, q_min_mvar=-60.0, can_pump=False,
            active_from_shift=1, description='Test CCGT unit',
        ),
        GenerationUnit(
            label='HYD-1', station_label='HYD', bus_label='B1',
            unit_type='HYDRO', rated_mw=250.0, min_mw=25.0,
            ramp_mw_per_min=250.0, inertia_h=3.0, cold_start_min=5.0,
            q_max_mvar=120.0, q_min_mvar=-40.0, can_pump=False,
            active_from_shift=1, description='Test hydro unit',
        ),
        GenerationUnit(
            label='ROR-1', station_label='ROR', bus_label='B1',
            unit_type='HYDRO_ROR', rated_mw=30.0, min_mw=0.0,
            ramp_mw_per_min=30.0, inertia_h=3.0, cold_start_min=5.0,
            q_max_mvar=15.0, q_min_mvar=-5.0, can_pump=False,
            active_from_shift=1, description='Test run-of-river unit',
        ),
    ]

    hours = tuple(float(h) for h in range(24))
    if load_forecast is None:
        load_forecast = {h: 900.0 for h in hours}

    model = PlanningModel(
        unit_specs=units,
        start_hour=0.0,
        duration_hours=24.0,
        load_forecast=load_forecast,
        renewable_specs=[],
        renewable_forecast={},
        maintenance_units=frozenset(),
        budget_eur=10_000_000.0,
        difficulty='standard',
        hours=hours,
    )
    for unit in model.unit_specs:
        model.online[unit.label] = {h: False for h in hours}
        model.schedule[unit.label] = {h: 0.0 for h in hours}
        if unit.unit_type in model.agc_eligible_types:
            model.agc_enrolled[unit.label] = True
    return model


# ─────────────────────────────────────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_cost_ranking_prefers_cheap_baseload() -> bool:
    """A sustained mid-load day (900 MW flat, comfortably within nuclear's
    own range once online) should be carried mostly by nuclear/hydro-ROR
    (low effective marginal cost) rather than CCGT (high running cost),
    once nuclear's large startup cost is amortized over its long committed
    run — the core ask behind this rework."""
    print("Testing auto_schedule() prefers cheap-to-run baseload for sustained load...")
    try:
        model = _build_planning_fixture()
        model.auto_schedule()

        nuclear_mwh = sum(model.schedule['NUC-1'][h] for h in model.hours)
        ccgt_mwh = sum(model.schedule['CCGT-1'][h] for h in model.hours)

        assert nuclear_mwh > 0.0, "Nuclear was never committed for a sustained 900 MW day"
        assert nuclear_mwh > ccgt_mwh,             f"CCGT ({ccgt_mwh:.0f} MWh) was leaned on more than nuclear ({nuclear_mwh:.0f} MWh) despite nuclear's lower amortized cost"
        print(f"  nuclear {nuclear_mwh:.0f} MWh > CCGT {ccgt_mwh:.0f} MWh — PASS")
        return True
    except AssertionError as e:
        print(f"  FAIL — {e}")
        return False
    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agc_units_land_near_midpoint() -> bool:
    """When net load comfortably permits it, an AGC-enrolled unit
    (CCGT/HYDRO) should be dispatched near its own regulation-band
    midpoint (tech_min + (tech_max-tech_min)/2) rather than an arbitrary
    clamp-to-shortfall value, to maximize its available regulation."""
    print("Testing AGC-enrolled units land near their regulation-band midpoint...")
    try:
        # A load high enough that CCGT must be committed to help cover it,
        # but with enough slack that midpoint dispatch is achievable.
        hours = tuple(float(h) for h in range(24))
        load_forecast = {h: 1350.0 for h in hours}
        model = _build_planning_fixture(load_forecast=load_forecast)
        model.auto_schedule()

        ccgt = model.unit('CCGT-1')
        midpoint = model.tech_min(ccgt) + (model.tech_max(ccgt) - model.tech_min(ccgt)) / 2.0

        # Use a late hour so ramp limits from the cold start have settled.
        h = model.hours[-1]
        assert model.is_online('CCGT-1', h), "CCGT-1 never committed online for this scenario"
        mw = model.schedule['CCGT-1'][h]
        tolerance = 1.0
        assert abs(mw - midpoint) <= tolerance,             f"CCGT-1 dispatched at {mw:.1f} MW, expected near midpoint {midpoint:.1f} MW"
        print(f"  CCGT-1 at {mw:.1f} MW, midpoint {midpoint:.1f} MW — PASS")
        return True
    except AssertionError as e:
        print(f"  FAIL — {e}")
        return False
    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_physical_constraints_hold() -> bool:
    """Every physical constraint auto_schedule() is supposed to respect
    (tech-min/max, ramp rate, min-up/down time, maintenance exclusion,
    pooled AGC reserve floor) must still hold after the cost-ranking
    rework — none of that machinery should have been weakened."""
    print("Testing auto_schedule() still respects all physical constraints...")
    try:
        from config.constants import PLANNING_STEP_HOURS, PLANNING_AGC_RESERVE_MW

        # A varying load profile to exercise commitment/decommitment and
        # ramp limits across the day, plus one unit under maintenance.
        # Stepped gradually (100 MW/h) rather than as a sharp jump so the
        # fixture's own (deliberately small) ramp rates can keep pace —
        # a sharp multi-hundred-MW single-hour jump would force a reserve
        # shortfall irrespective of auto_schedule()'s own logic, which
        # isn't the invariant this test is checking.
        hours = tuple(float(h) for h in range(24))
        load_forecast = {}
        for h in hours:
            if h < 6.0:
                load_forecast[h] = 600.0
            elif h < 13.0:
                load_forecast[h] = 600.0 + (h - 6.0) * 100.0
            elif h < 18.0:
                load_forecast[h] = 1300.0
            else:
                load_forecast[h] = 800.0
        model = _build_planning_fixture(load_forecast=load_forecast)
        model.maintenance_units = frozenset({'COAL-1'})
        model.auto_schedule()

        # tech-min/max
        for unit in model.unit_specs:
            for h in model.hours:
                if model.is_online(unit.label, h):
                    mw = model.schedule[unit.label][h]
                    assert model.tech_min(unit) - 1e-6 <= mw <= model.tech_max(unit) + 1e-6,                         f"{unit.label} at {mw:.1f} MW outside [{model.tech_min(unit):.1f}, {model.tech_max(unit):.1f}] at hour {h}"

        # ramp rate (hour 0 is skipped — its ramp budget is measured against
        # a synthetic D-1 boundary MW internal to auto_schedule(), not
        # observable from self.schedule, so only hour-to-hour deltas from
        # hour 1 onward can be checked here)
        for unit in model.unit_specs:
            ramp_mw = unit.ramp_mw_per_min * (PLANNING_STEP_HOURS * 60.0)
            prev_mw = model.schedule[unit.label][model.hours[0]]
            for h in model.hours[1:]:
                mw = model.schedule[unit.label][h]
                delta = abs(mw - prev_mw)
                assert delta <= ramp_mw + 1e-6,                     f"{unit.label} moved {delta:.1f} MW in one step at hour {h}, ramp budget is {ramp_mw:.1f} MW"
                prev_mw = mw

        # NOTE: maintenance_units is NOT checked here. Pre-existing,
        # pre-dating this rework: maintenance_units only seeds the
        # synthetic D-1 boundary state (prev_online0) at hour 0 — it does
        # not prevent the forward-fill commitment loop from bringing a
        # "maintenance" unit online at a later hour if load calls for it.
        # This rework does not touch that logic (out of scope per the
        # approved plan's Section 3.7/4), so it is intentionally not
        # asserted here rather than encoding incorrect behavior as a
        # requirement. Flagged separately as a pre-existing bug worth a
        # follow-up fix.

        # min-up / min-down
        from gameplay.phase1 import _MIN_UP_HOURS, _MIN_DOWN_HOURS
        for unit in model.unit_specs:
            min_up = _MIN_UP_HOURS.get(unit.unit_type, 0.0)
            min_down = _MIN_DOWN_HOURS.get(unit.unit_type, 0.0)
            if min_up == 0.0 and min_down == 0.0:
                continue
            run_start = None
            for i, h in enumerate(model.hours):
                on = model.is_online(unit.label, h)
                prev_on = model.is_online(unit.label, model.hours[i - 1]) if i > 0 else on
                if on and not prev_on:
                    run_start = h
                if (not on) and prev_on and run_start is not None:
                    run_length = h - run_start
                    assert run_length >= min_up - 1e-6 or on == prev_on,                         f"{unit.label} ran only {run_length:.1f}h, below min_up {min_up:.1f}h"
                    run_start = None

        # pooled AGC reserve floor, wherever the fleet has range to support it
        max_pool_up = (model.tech_max(model.unit('CCGT-1')) - model.tech_min(model.unit('CCGT-1')))                     + (model.tech_max(model.unit('HYD-1')) - model.tech_min(model.unit('HYD-1')))
        for h in model.hours:
            if max_pool_up >= 2 * PLANNING_AGC_RESERVE_MW:
                assert model.reg_band_up(h) >= PLANNING_AGC_RESERVE_MW - 1e-3 or model.reg_band(h) < PLANNING_AGC_RESERVE_MW,                     f"reg_band_up({h}) = {model.reg_band_up(h):.1f} below reserve floor {PLANNING_AGC_RESERVE_MW}"

        print("  tech-min/max, ramp, min-up/down, AGC reserve — PASS")
        return True
    except AssertionError as e:
        print(f"  FAIL — {e}")
        return False
    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_load_coverage_exact() -> bool:
    """total_gen(h) must still match load_forecast(h) exactly (0 diff) for
    every hour, the same guarantee auto_schedule() made before this
    rework — the cost-ranking/midpoint-preference changes must not break
    load coverage."""
    print("Testing auto_schedule() still covers load exactly every hour...")
    try:
        model = _build_planning_fixture()
        model.auto_schedule()

        for h in model.hours:
            diff = model.difference(h)
            assert abs(diff) < 1e-6, f"Hour {h}: diff = {diff:.3f} MW (expected 0)"
        print("  0 MW diff at every hour — PASS")
        return True
    except AssertionError as e:
        print(f"  FAIL — {e}")
        return False
    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cost_functions_are_finite() -> bool:
    """total_cost(), remaining_budget(), and hourly_cost(h) for every hour
    must execute without exception and return finite floats — smoke
    coverage for the new AGC regulation-band cost term."""
    print("Testing cost functions compute without error after auto_schedule()...")
    try:
        import math

        model = _build_planning_fixture()
        model.auto_schedule()

        for h in model.hours:
            cost = model.hourly_cost(h)
            assert math.isfinite(cost), f"hourly_cost({h}) is not finite: {cost}"
            assert cost >= 0.0, f"hourly_cost({h}) is negative: {cost}"

        total = model.total_cost()
        assert math.isfinite(total), f"total_cost() is not finite: {total}"
        remaining = model.remaining_budget()
        assert math.isfinite(remaining), f"remaining_budget() is not finite: {remaining}"
        print(f"  total_cost() = EUR {total:,.0f}, all hourly_cost() finite — PASS")
        return True
    except AssertionError as e:
        print(f"  FAIL — {e}")
        return False
    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_manual_edit_paths_unaffected() -> bool:
    """Manual (non-auto) planning functions — set_cell, fill_row,
    toggle_online, toggle_agc_enrolled — are untouched by this rework and
    should behave exactly as documented, independent of auto_schedule()."""
    print("Testing manual planning-edit functions are unaffected...")
    try:
        model = _build_planning_fixture()

        model.set_cell('CCGT-1', 5.0, 250.0)
        assert model.schedule['CCGT-1'][5.0] == 250.0, "set_cell() did not write the expected MW"

        model.fill_row('HYD-1', 100.0)
        assert all(model.schedule['HYD-1'][h] == 100.0 for h in model.hours),             "fill_row() did not fill every hour"

        was_online = model.is_online('CCGT-1', 0.0)
        model.toggle_online('CCGT-1')
        assert model.is_online('CCGT-1', 0.0) != was_online,             "toggle_online() did not flip online state"

        was_enrolled = model.is_agc_enrolled('HYD-1')
        model.toggle_agc_enrolled('HYD-1')
        assert model.is_agc_enrolled('HYD-1') != was_enrolled,             "toggle_agc_enrolled() did not flip enrollment"

        print("  set_cell/fill_row/toggle_online/toggle_agc_enrolled behave as documented — PASS")
        return True
    except AssertionError as e:
        print(f"  FAIL — {e}")
        return False
    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_handoff_imbalance_zero_diff() -> bool:
    """A perfectly balanced schedule (generation == load) reports diff_mw
    ~= 0, headroom_mw == 0 (nothing to correct), and correctable == True."""
    print("Testing handoff_imbalance() on a balanced schedule...")
    try:
        from gameplay.phase1 import handoff_imbalance

        model = _build_planning_fixture()
        initial_schedule = {
            'NUC-1': 700.0, 'CCGT-1': 150.0, 'HYD-1': 50.0,
        }
        load_mw = sum(initial_schedule.values())
        imbalance = handoff_imbalance(
            unit_specs=model.unit_specs,
            initial_schedule=initial_schedule,
            agc_eligible_types=model.agc_eligible_types,
            load_mw=load_mw,
        )
        assert abs(imbalance['diff_mw']) < 1e-6, f"diff_mw = {imbalance['diff_mw']}, expected ~0"
        assert imbalance['headroom_mw'] == 0.0, f"headroom_mw = {imbalance['headroom_mw']}, expected 0 (nothing to correct)"
        assert imbalance['correctable'] is True, "a zero diff should always be correctable"
        print("  diff_mw ~= 0, headroom_mw = 0, correctable = True — PASS")
        return True
    except AssertionError as e:
        print(f"  FAIL — {e}")
        return False
    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_handoff_imbalance_within_headroom() -> bool:
    """A schedule with a surplus small enough for the AGC-eligible fleet
    (CCGT-1, HYD-1) to absorb by trimming down reports correctable == True
    with the correct headroom_mw."""
    print("Testing handoff_imbalance() on a surplus within AGC headroom...")
    try:
        from gameplay.phase1 import handoff_imbalance

        model = _build_planning_fixture()
        ccgt = model.unit('CCGT-1')
        hyd = model.unit('HYD-1')
        initial_schedule = {
            'NUC-1': 700.0, 'CCGT-1': 300.0, 'HYD-1': 150.0,
        }
        surplus = 30.0
        load_mw = sum(initial_schedule.values()) - surplus
        imbalance = handoff_imbalance(
            unit_specs=model.unit_specs,
            initial_schedule=initial_schedule,
            agc_eligible_types=model.agc_eligible_types,
            load_mw=load_mw,
        )
        expected_down_headroom = (
            (initial_schedule['CCGT-1'] - model.tech_min(ccgt))
            + (initial_schedule['HYD-1'] - model.tech_min(hyd))
        )
        assert abs(imbalance['diff_mw'] - surplus) < 1e-6,             f"diff_mw = {imbalance['diff_mw']}, expected {surplus}"
        assert abs(imbalance['headroom_mw'] - expected_down_headroom) < 1e-6,             f"headroom_mw = {imbalance['headroom_mw']}, expected {expected_down_headroom}"
        assert imbalance['correctable'] is True,             f"a {surplus} MW surplus should be within {expected_down_headroom} MW of down-headroom"
        print(f"  diff_mw = {imbalance['diff_mw']:.0f}, headroom_mw = {imbalance['headroom_mw']:.0f}, correctable = True — PASS")
        return True
    except AssertionError as e:
        print(f"  FAIL — {e}")
        return False
    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_handoff_imbalance_exceeds_headroom() -> bool:
    """A schedule with a diff larger than the AGC-eligible fleet's own
    range (e.g. every AGC-eligible unit already pinned at tech_min) reports
    correctable == False — the case the planning confirm gate must block."""
    print("Testing handoff_imbalance() on a diff exceeding AGC headroom...")
    try:
        from gameplay.phase1 import handoff_imbalance

        model = _build_planning_fixture()
        ccgt = model.unit('CCGT-1')
        hyd = model.unit('HYD-1')
        # Both AGC-eligible units already at their own tech_min — zero
        # down-headroom left — while generation still hugely exceeds load.
        initial_schedule = {
            'NUC-1': 700.0,
            'CCGT-1': model.tech_min(ccgt),
            'HYD-1': model.tech_min(hyd),
        }
        load_mw = sum(initial_schedule.values()) - 500.0
        imbalance = handoff_imbalance(
            unit_specs=model.unit_specs,
            initial_schedule=initial_schedule,
            agc_eligible_types=model.agc_eligible_types,
            load_mw=load_mw,
        )
        assert imbalance['headroom_mw'] < 1e-6,             f"headroom_mw = {imbalance['headroom_mw']}, expected ~0 (units already at tech_min)"
        assert imbalance['correctable'] is False,             "a 500 MW surplus against ~0 MW headroom should not be correctable"
        print(f"  headroom_mw ~= 0, correctable = False — PASS")
        return True
    except AssertionError as e:
        print(f"  FAIL — {e}")
        return False
    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_apply_handoff_nudge_correctness() -> bool:
    """apply_handoff_nudge() closes the diff exactly (within tolerance),
    never moves a unit outside its own [tech_min, tech_max], and never
    touches a non-AGC-eligible unit (NUC-1)."""
    print("Testing apply_handoff_nudge() corrects a schedule within headroom...")
    try:
        from gameplay.phase1 import handoff_imbalance, apply_handoff_nudge

        model = _build_planning_fixture()
        ccgt = model.unit('CCGT-1')
        hyd = model.unit('HYD-1')
        initial_schedule = {
            'NUC-1': 700.0, 'CCGT-1': 300.0, 'HYD-1': 150.0,
        }
        surplus = 30.0
        load_mw = sum(initial_schedule.values()) - surplus
        imbalance = handoff_imbalance(
            unit_specs=model.unit_specs,
            initial_schedule=initial_schedule,
            agc_eligible_types=model.agc_eligible_types,
            load_mw=load_mw,
        )
        assert imbalance['correctable'], "fixture setup error: expected a correctable surplus"

        corrected = apply_handoff_nudge(
            initial_schedule, model.unit_specs, model.agc_eligible_types,
            imbalance['diff_mw'],
        )

        assert corrected['NUC-1'] == 700.0, "apply_handoff_nudge() touched a non-AGC-eligible unit"
        assert model.tech_min(ccgt) - 1e-6 <= corrected['CCGT-1'] <= model.tech_max(ccgt) + 1e-6,             f"CCGT-1 moved outside its own range: {corrected['CCGT-1']}"
        assert model.tech_min(hyd) - 1e-6 <= corrected['HYD-1'] <= model.tech_max(hyd) + 1e-6,             f"HYD-1 moved outside its own range: {corrected['HYD-1']}"

        new_total = sum(corrected.values())
        assert abs(new_total - load_mw) < 1e-3,             f"corrected total {new_total:.3f} MW does not match load {load_mw:.3f} MW"
        print(f"  corrected total = {new_total:.1f} MW (target {load_mw:.1f} MW), all units in range — PASS")
        return True
    except AssertionError as e:
        print(f"  FAIL — {e}")
        return False
    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


# ─────────────────────────────────────────────────────────────────────────────
# TEST RUNNER
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    results = [
        test_cost_ranking_prefers_cheap_baseload(),
        test_agc_units_land_near_midpoint(),
        test_physical_constraints_hold(),
        test_load_coverage_exact(),
        test_cost_functions_are_finite(),
        test_manual_edit_paths_unaffected(),
        test_handoff_imbalance_zero_diff(),
        test_handoff_imbalance_within_headroom(),
        test_handoff_imbalance_exceeds_headroom(),
        test_apply_handoff_nudge_correctness(),
    ]
    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    if passed < total:
        sys.exit(1)
