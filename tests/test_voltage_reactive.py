"""
tests/test_voltage_reactive.py

Tests for reactive-power forcing (Phase A of VOLTAGE_REACTIVE_PLAN.md):
per-substation-type power factor driving real Q load, direct generator
reactive-power targets feeding q_injections() (F9), and blackout-zone
filtering of reactive injections. No test framework required — run directly:
python tests/test_voltage_reactive.py

Each test function prints PASS / FAIL / ERROR and returns True/False.
Script exits with code 1 if any test fails.

See CODING_STANDARDS.md for test pattern conventions.
"""

import sys
import os

# Ensure src/ is on the path so simulation and data packages resolve.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC FIXTURE — one slack/gen bus feeding two load buses of different
# substation types, so PF-driven Q differences are isolated from topology.
#
#   Bus SLK (slack, TRANSMISSION, gen unit) ── IND (INDUSTRIAL load, low PF)
#   Bus SLK ── RES (RESIDENTIAL load, high PF)
#
#   Both load lines are identical (same reactance/rating), both loads have
#   the same MW peak — the only difference is substation type / power factor.
# ─────────────────────────────────────────────────────────────────────────────

def _build_fixture():
    """Returns (grid, buses) — buses is the raw DesignerBus list (has peak_load_mw),
    distinct from grid.get_active_buses() which returns plain topology.Bus objects."""
    from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
    from simulation.designer_grid import DesignerGrid

    buses = [
        DesignerBus(label='SLK', name='Slack', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=0, canvas_y=0,
                    active_from_shift=1, is_slack=True),
        DesignerBus(label='IND', name='Industrial', voltage_kv=150.0,
                    bus_type='LOAD', canvas_x=100, canvas_y=0,
                    active_from_shift=1, is_slack=False, peak_load_mw=300.0),
        DesignerBus(label='RES', name='Residential', voltage_kv=150.0,
                    bus_type='LOAD', canvas_x=100, canvas_y=100,
                    active_from_shift=1, is_slack=False, peak_load_mw=300.0),
    ]
    lines = [
        DesignerLine(label='L1', from_bus='SLK', to_bus='IND',
                     reactance_pu=0.10, rating_mw=500.0, voltage_kv=150.0),
        DesignerLine(label='L2', from_bus='SLK', to_bus='RES',
                     reactance_pu=0.10, rating_mw=500.0, voltage_kv=150.0),
    ]
    units = [
        DesignerUnit(label='SLK-1', station_label='SLK', bus_label='SLK',
                     unit_type='CCGT', rated_mw=800.0, min_mw=0.0, inertia_h=4.0, cold_start_min=5.0,
                     q_max_mvar=400.0, q_min_mvar=-400.0, can_pump=False,
                     active_from_shift=1, description='Test gen unit'),
    ]
    grid = DesignerGrid(buses, lines, units)
    return grid, buses


def _build_sim(substation_types=None):
    from simulation.simulation import GridSimulation
    from data.profiles import DEMAND_PROFILE_NORMALISED

    grid, buses = _build_fixture()
    substation_load_mw = {
        b.label: {h: b.peak_load_mw * DEMAND_PROFILE_NORMALISED[h]
                  for h in DEMAND_PROFILE_NORMALISED}
        for b in buses
        if b.bus_type == 'LOAD' and b.peak_load_mw > 0
    }
    sim = GridSimulation(
        grid=grid,
        shift_number=1,  # any real shift stub works — substation_load_mw/substation_types override its own grid
        difficulty='standard',
        initial_schedule={'SLK-1': 500.0},
        substation_load_mw=substation_load_mw,
        substation_types=substation_types,
        start_hour=12.0,
        duration_hours=1.0,
    )
    return sim


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — reactive load moves voltage away from 1.0 pu
# ─────────────────────────────────────────────────────────────────────────────

def test_reactive_load_moves_voltage() -> bool:
    """
    With typed load buses, non-slack bus voltages should deviate from the
    flat 1.000 pu the solver produced before Phase A (all-zero Q). Slack
    stays exactly 1.0. All voltages remain finite.
    """
    print("test_reactive_load_moves_voltage...")
    all_passed = True

    try:
        sim = _build_sim(substation_types={'IND': 'INDUSTRIAL', 'RES': 'RESIDENTIAL'})

        for _ in range(5):
            sim.tick(60.0)
        state = sim.get_state()

        try:
            assert state.bus_voltages['SLK'] == 1.0, \
                f"Slack bus should be exactly 1.0, got {state.bus_voltages['SLK']}"

            non_slack = [v for label, v in state.bus_voltages.items() if label != 'SLK']
            assert any(abs(v - 1.0) > 1e-6 for v in non_slack), \
                f"Expected at least one non-slack bus away from 1.000, got {state.bus_voltages}"

            assert all(v == v and abs(v) < 1e6 for v in state.bus_voltages.values()), \
                f"All voltages must be finite, got {state.bus_voltages}"

            print(f"  voltages: {state.bus_voltages} — PASS")
        except AssertionError as e:
            print(f"  reactive load moves voltage: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — low-PF (industrial) buses sag more than high-PF (residential)
# ─────────────────────────────────────────────────────────────────────────────

def test_low_pf_sags_more() -> bool:
    """
    Under comparable MW load, the INDUSTRIAL bus (PF=0.85, more reactive
    draw) should show a lower voltage than the RESIDENTIAL bus (PF=0.97,
    less reactive draw) — both fed identically from the same slack/gen bus.
    """
    print("test_low_pf_sags_more...")
    all_passed = True

    try:
        sim = _build_sim(substation_types={'IND': 'INDUSTRIAL', 'RES': 'RESIDENTIAL'})
        for _ in range(5):
            sim.tick(60.0)
        state = sim.get_state()

        try:
            v_ind = state.bus_voltages['IND']
            v_res = state.bus_voltages['RES']
            assert v_ind < v_res, \
                f"Industrial (PF=0.85) should sag more than residential (PF=0.97): " \
                f"IND={v_ind:.5f} RES={v_res:.5f}"
            print(f"  IND={v_ind:.5f} < RES={v_res:.5f} — PASS")
        except AssertionError as e:
            print(f"  low-PF sags more: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — q_load_injections() sign convention and PF scaling
# ─────────────────────────────────────────────────────────────────────────────

def test_q_load_injections_math() -> bool:
    """
    Verify DemandModel.q_load_injections() directly: negative sign (load
    absorbs reactive power, mirroring p_load_injections()), and Q magnitude
    scales with tan(acos(PF)) — a lower PF must yield a larger |Q| for the
    same MW.
    """
    print("test_q_load_injections_math...")
    all_passed = True

    try:
        import math
        from simulation.demand import DemandModel
        from data.profiles import get_substation_demand_specs, SubstationDemandSpec

        hourly = {h: 100.0 for h in range(25)}
        specs_industrial = get_substation_demand_specs(
            {'A': hourly}, {'A': 'INDUSTRIAL'})
        specs_residential = get_substation_demand_specs(
            {'A': hourly}, {'A': 'RESIDENTIAL'})

        dm_ind = DemandModel(100.0, specs_industrial)
        dm_ind.update(12.0, total_generation_mw=100.0)
        dm_res = DemandModel(100.0, specs_residential)
        dm_res.update(12.0, total_generation_mw=100.0)

        try:
            q_ind = dm_ind.q_load_injections()['A']
            q_res = dm_res.q_load_injections()['A']
            p_ind = dm_ind.p_load_injections()['A']

            assert q_ind < 0.0, f"Q injection should be negative (load absorbs), got {q_ind}"
            assert q_res < 0.0, f"Q injection should be negative (load absorbs), got {q_res}"
            assert abs(q_ind) > abs(q_res), \
                f"Industrial (lower PF) should draw more |Q| than residential: " \
                f"|q_ind|={abs(q_ind):.2f} |q_res|={abs(q_res):.2f}"

            from simulation.constants import PF_INDUSTRIAL
            expected_q_ind = p_ind * math.tan(math.acos(PF_INDUSTRIAL))
            assert abs(q_ind - expected_q_ind) < 0.01, \
                f"q_ind should equal p*tan(acos(PF)): expected {expected_q_ind:.3f}, got {q_ind:.3f}"

            print(f"  q_ind={q_ind:.2f} MVAr, q_res={q_res:.2f} MVAr — PASS")
        except AssertionError as e:
            print(f"  q_load_injections math: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — direct reactive-power target feeds q_injections() and clamps
# ─────────────────────────────────────────────────────────────────────────────

def test_generator_q_target_feeds_injections() -> bool:
    """
    A unit's set_unit_q_target() should flow through to
    FleetModel.q_injections()'s net MVAr at that unit's bus (F9 — direct
    reactive-power control replaced the AVR voltage setpoint; generators no
    longer target a voltage, they target a Q injection directly, clamped to
    their own [q_min_mvar, q_max_mvar] rather than a shared pu band).
    """
    print("test_generator_q_target_feeds_injections...")
    all_passed = True

    try:
        sim = _build_sim()
        try:
            accepted = sim._fleet.set_unit_q_target('SLK-1', 250.0)
            assert accepted, "set_unit_q_target should accept a known unit"

            q_inj = sim._fleet.q_injections()
            assert abs(q_inj['SLK'] - 250.0) < 1e-9, \
                f"q_injections should reflect the new target 250.0, got {q_inj['SLK']}"

            # Clamped to the unit's own q_max_mvar (400.0 in the test fixture).
            sim._fleet.set_unit_q_target('SLK-1', 1000.0)
            q_inj2 = sim._fleet.q_injections()
            assert abs(q_inj2['SLK'] - 400.0) < 1e-9, \
                f"Target should clamp to q_max_mvar=400.0, got {q_inj2['SLK']}"

            print(f"  target 250.0 -> q_injections['SLK']=250.0, clamp OK — PASS")
        except AssertionError as e:
            print(f"  generator Q target feeds injections: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — blackout zones exclude reactive load, mirroring p_load_injections
# ─────────────────────────────────────────────────────────────────────────────

def test_blackout_zones_exclude_reactive_load() -> bool:
    """
    _build_q_injections(blackout_zones) must zero out Q for buses in the
    blackout set, exactly like _build_p_injections does for P.
    """
    print("test_blackout_zones_exclude_reactive_load...")
    all_passed = True

    try:
        sim = _build_sim(substation_types={'IND': 'INDUSTRIAL', 'RES': 'RESIDENTIAL'})
        sim._demand.update(12.0, total_generation_mw=500.0)

        try:
            q_none = sim._build_q_injections(frozenset())
            assert q_none['IND'] != 0.0, \
                f"With no blackout, IND should draw nonzero Q, got {q_none['IND']}"

            q_blackout = sim._build_q_injections(frozenset({'IND'}))
            assert q_blackout['IND'] == 0.0, \
                f"Blacked-out IND should have zero Q injection, got {q_blackout['IND']}"
            assert q_blackout['RES'] == q_none['RES'], \
                "Non-blacked-out RES should be unaffected by IND's blackout"

            print(f"  blackout zeroes Q: IND {q_none['IND']:.2f} -> {q_blackout['IND']:.2f} — PASS")
        except AssertionError as e:
            print(f"  blackout excludes reactive load: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC FIXTURE — a heavily-loaded, generation-poor bus (weak Q support,
# high reactance feed) whose solved voltage starts just under V_WARNING_LOW,
# for Phase B collapse-acceleration / tier / alarm / crisis verification.
# ─────────────────────────────────────────────────────────────────────────────

def _build_weak_bus_sim():
    from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
    from simulation.designer_grid import DesignerGrid
    from simulation.simulation import GridSimulation

    buses = [
        DesignerBus(label='SLK', name='Slack', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=0, canvas_y=0,
                    active_from_shift=1, is_slack=True),
        DesignerBus(label='WEAK', name='Weak', voltage_kv=150.0,
                    bus_type='LOAD', canvas_x=100, canvas_y=0,
                    active_from_shift=1, is_slack=False, peak_load_mw=850.0),
    ]
    lines = [
        DesignerLine(label='L1', from_bus='SLK', to_bus='WEAK',
                     reactance_pu=0.30, rating_mw=2000.0, voltage_kv=150.0),
    ]
    units = [
        # Q range clamped tiny so the PV correction pass can't meaningfully
        # prop up WEAK's voltage — isolates the collapse-offset behaviour.
        DesignerUnit(label='SLK-1', station_label='SLK', bus_label='SLK',
                     unit_type='CCGT', rated_mw=1000.0, min_mw=0.0, inertia_h=4.0, cold_start_min=5.0,
                     q_max_mvar=1.0, q_min_mvar=-1.0, can_pump=False,
                     active_from_shift=1, description='weak gen, tiny Q range'),
    ]
    grid = DesignerGrid(buses, lines, units)
    sim = GridSimulation(
        grid=grid,
        shift_number=1,
        difficulty='standard',
        initial_schedule={'SLK-1': 850.0},
        substation_load_mw={'WEAK': {h: 850.0 for h in range(25)}},
        substation_types={'WEAK': 'INDUSTRIAL'},
        start_hour=12.0,
        duration_hours=1.0,
    )
    return sim


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — collapse offset accumulates while sustained below V_WARNING_LOW
# ─────────────────────────────────────────────────────────────────────────────

def test_collapse_offset_accumulates() -> bool:
    """
    A bus solving just under V_WARNING_LOW should see its effective voltage
    keep dropping tick-over-tick (the collapse offset accumulating), not
    hold flat at the raw solved value.
    """
    print("test_collapse_offset_accumulates...")
    all_passed = True

    try:
        sim = _build_weak_bus_sim()
        voltages = []
        for _ in range(10):
            sim.tick(1.0)
            voltages.append(sim.get_state().bus_voltages['WEAK'])

        try:
            assert voltages[0] < 0.85, \
                f"Fixture should start below V_WARNING_LOW=0.85, got {voltages[0]:.4f}"
            assert all(voltages[i + 1] < voltages[i] for i in range(len(voltages) - 1)), \
                f"Voltage should strictly decrease tick-over-tick while sustained " \
                f"below warning threshold, got {[round(v, 5) for v in voltages]}"
            print(f"  voltages strictly decreasing: {[round(v, 4) for v in voltages]} — PASS")
        except AssertionError as e:
            print(f"  collapse offset accumulates: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7 — WARNING -> CRITICAL alarms fire, crisis_active True, tiers transition
# ─────────────────────────────────────────────────────────────────────────────

def test_warning_to_critical_alarms_and_crisis() -> bool:
    """
    As the collapse offset drags WEAK's voltage down over successive ticks,
    a WARNING voltage alarm should fire, then a CRITICAL one once the
    effective voltage crosses V_CRITICAL_LOW, crisis_active should become
    True, and bus_vsi_tier should visibly transition through the tiers.
    """
    print("test_warning_to_critical_alarms_and_crisis...")
    all_passed = True

    try:
        sim = _build_weak_bus_sim()
        tiers_seen = []
        warning_alarm_seen = False
        critical_alarm_seen = False
        crisis_seen = False

        for _ in range(200):
            sim.tick(1.0)
            state = sim.get_state()
            tier = state.bus_vsi_tier['WEAK']
            if not tiers_seen or tiers_seen[-1] != tier:
                tiers_seen.append(tier)
            for a in state.active_alarms:
                if a.element_label == 'WEAK' and a.priority == 'WARNING':
                    warning_alarm_seen = True
                if a.element_label == 'WEAK' and a.priority == 'CRITICAL':
                    critical_alarm_seen = True
            if state.crisis_active and state.crisis_type == 'CRITICAL':
                crisis_seen = True
            if critical_alarm_seen and crisis_seen:
                break

        try:
            assert warning_alarm_seen, "Expected a WARNING alarm for bus WEAK"
            assert critical_alarm_seen, "Expected a CRITICAL alarm for bus WEAK"
            assert crisis_seen, "Expected crisis_active=True with crisis_type='CRITICAL'"
            # Tiers should have transitioned through at least WARNING then CRITICAL,
            # in that relative order (collapse only ever worsens while sustained low).
            assert 'WARNING' in tiers_seen and 'CRITICAL' in tiers_seen, \
                f"Expected WARNING and CRITICAL tiers, saw {tiers_seen}"
            assert tiers_seen.index('WARNING') < tiers_seen.index('CRITICAL'), \
                f"WARNING should precede CRITICAL, saw {tiers_seen}"
            print(f"  tiers seen: {tiers_seen}, alarms + crisis fired — PASS")
        except AssertionError as e:
            print(f"  warning->critical alarms/crisis: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# TEST 8 — offset decays and voltage recovers once load is relieved
# ─────────────────────────────────────────────────────────────────────────────

def test_offset_decays_on_recovery() -> bool:
    """
    Once the bus is relieved (load shed so the solved voltage rises back
    above V_WARNING_LOW), the collapse offset should decay back toward 0
    and the effective voltage should recover upward over successive ticks,
    rather than staying pinned at its worst value.
    """
    print("test_offset_decays_on_recovery...")
    all_passed = True

    try:
        sim = _build_weak_bus_sim()
        for _ in range(15):
            sim.tick(1.0)
        worst_v = sim.get_state().bus_voltages['WEAK']

        sim._demand.shed_load('WEAK', 0.6)
        recovery_voltages = []
        for _ in range(10):
            sim.tick(1.0)
            recovery_voltages.append(sim.get_state().bus_voltages['WEAK'])

        try:
            assert recovery_voltages[0] > worst_v, \
                f"Voltage should rise immediately after load relief: " \
                f"worst={worst_v:.4f}, first recovery tick={recovery_voltages[0]:.4f}"
            assert recovery_voltages[-1] >= recovery_voltages[0] - 1e-9, \
                f"Voltage should not keep falling after relief: {recovery_voltages}"
            print(f"  worst={worst_v:.4f} -> recovered to {recovery_voltages[-1]:.4f} — PASS")
        except AssertionError as e:
            print(f"  offset decays on recovery: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# TEST 9 — automatic shunt bank steps up to hold voltage, does not hunt
# ─────────────────────────────────────────────────────────────────────────────

def test_auto_shunt_holds_without_hunting() -> bool:
    """
    An automatic shunt bank at the weak bus should step up toward its
    deadband as voltage sags, then hold — total switch count over a
    sustained run must stay bounded (<= max_steps), never oscillating.
    """
    print("test_auto_shunt_holds_without_hunting...")
    all_passed = True

    try:
        from simulation.reactive_devices import ShuntBank
        from simulation.constants import SHUNT_BANK_MAX_STEPS

        sim = _build_weak_bus_sim()
        sim._reactive.add_shunt_bank(ShuntBank(bus='WEAK'))

        switches = 0
        prev_step = 0
        v_before = None
        for i in range(600):
            sim.tick(1.0)
            state = sim.get_state()
            if i == 0:
                v_before = state.bus_voltages['WEAK']
            step = state.bus_shunt_step['WEAK']
            if step != prev_step:
                switches += 1
                prev_step = step
        v_after = sim.get_state().bus_voltages['WEAK']

        try:
            assert switches <= SHUNT_BANK_MAX_STEPS, \
                f"Shunt bank should not hunt — expected <= {SHUNT_BANK_MAX_STEPS} " \
                f"switches over the run, got {switches}"
            assert switches > 0, "Expected the shunt bank to step up at least once"
            assert v_after > v_before, \
                f"Shunt bank should raise voltage: before={v_before:.4f}, after={v_after:.4f}"
            print(f"  {switches} switches (bounded), v {v_before:.4f} -> {v_after:.4f} — PASS")
        except AssertionError as e:
            print(f"  auto shunt holds without hunting: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# TEST 11 — manual SVC moves voltage monotonically and clamps at limits
# ─────────────────────────────────────────────────────────────────────────────

def test_manual_svc_monotonic_and_clamped() -> bool:
    """
    set_svc_setpoint() should move the hosting bus's voltage monotonically
    with the setpoint, and clamp at SVC_Q_MIN_MVAR / SVC_Q_MAX_MVAR.
    """
    print("test_manual_svc_monotonic_and_clamped...")
    all_passed = True

    try:
        from simulation.reactive_devices import SVC
        from simulation.constants import SVC_Q_MAX_MVAR

        sim = _build_weak_bus_sim()
        sim._reactive.add_svc(SVC(bus='WEAK'))
        sim.tick(1.0)

        setpoints = [0.0, 50.0, 100.0, 150.0, 300.0]  # last exceeds SVC_Q_MAX_MVAR
        voltages = []
        applied_q = []
        for q in setpoints:
            accepted = sim.set_svc_setpoint('WEAK', q)
            sim.tick(0.001)
            state = sim.get_state()
            voltages.append(state.bus_voltages['WEAK'])
            applied_q.append(state.bus_svc_mvar['WEAK'])
            if not accepted:
                all_passed = False
                print(f"  set_svc_setpoint({q}) unexpectedly returned False")

        try:
            assert all(voltages[i + 1] >= voltages[i] for i in range(len(voltages) - 1)), \
                f"Voltage should rise monotonically with SVC setpoint: {voltages}"
            assert applied_q[-1] == SVC_Q_MAX_MVAR, \
                f"SVC setpoint should clamp to {SVC_Q_MAX_MVAR}, got {applied_q[-1]}"
            # Unknown bus (no SVC hosted) must reject
            assert not sim.set_svc_setpoint('SLK', 10.0), \
                "set_svc_setpoint on a bus with no SVC should return False"
            print(f"  voltages: {[round(v, 4) for v in voltages]}, "
                  f"clamped to {applied_q[-1]} — PASS")
        except AssertionError as e:
            print(f"  manual SVC monotonic/clamped: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# TEST 12 — generator setpoint raises a region; Q rises to q_max then PV->PQ
# ─────────────────────────────────────────────────────────────────────────────

def _build_regional_support_sim():
    from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
    from simulation.designer_grid import DesignerGrid
    from simulation.simulation import GridSimulation

    buses = [
        DesignerBus(label='SLK', name='Slack', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=0, canvas_y=0,
                    active_from_shift=1, is_slack=True),
        DesignerBus(label='GEN', name='Support gen', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=50, canvas_y=0,
                    active_from_shift=1, is_slack=False),
        DesignerBus(label='WEAK', name='Weak', voltage_kv=150.0,
                    bus_type='LOAD', canvas_x=100, canvas_y=0,
                    active_from_shift=1, is_slack=False, peak_load_mw=300.0),
    ]
    lines = [
        DesignerLine(label='L1', from_bus='SLK', to_bus='GEN',
                     reactance_pu=0.05, rating_mw=2000.0, voltage_kv=400.0),
        DesignerLine(label='L2', from_bus='GEN', to_bus='WEAK',
                     reactance_pu=0.15, rating_mw=2000.0, voltage_kv=150.0),
    ]
    units = [
        DesignerUnit(label='GEN-1', station_label='GEN', bus_label='GEN',
                     unit_type='CCGT', rated_mw=1000.0, min_mw=0.0, inertia_h=4.0, cold_start_min=5.0,
                     q_max_mvar=200.0, q_min_mvar=-200.0, can_pump=False,
                     active_from_shift=1, description='regional support gen'),
    ]
    grid = DesignerGrid(buses, lines, units)
    sim = GridSimulation(
        grid=grid,
        shift_number=1,
        difficulty='standard',
        initial_schedule={'GEN-1': 300.0},
        substation_load_mw={'WEAK': {h: 300.0 for h in range(25)}},
        substation_types={'WEAK': 'INDUSTRIAL'},
        start_hour=12.0,
        duration_hours=1.0,
    )
    return sim


def test_generator_q_target_raises_region_and_clamps() -> bool:
    """
    Raising GEN-1's reactive-power target from a low starting point should
    raise the neighbouring WEAK bus's voltage, monotonically, up to
    q_max_mvar — where q_reserve_mvar reaches exactly 0 (F9: direct
    reactive-power control replaced the AVR PV/PQ conversion; there is no
    more "PV" state to convert out of, every bus is solved as PQ directly
    from whatever Q the player commands).
    """
    print("test_generator_q_target_raises_region_and_clamps...")
    all_passed = True

    try:
        sim = _build_regional_support_sim()
        sim.set_unit_q_target('GEN-1', -180.0)
        sim.tick(1.0)
        state = sim.get_state()
        v_before = state.bus_voltages['WEAK']

        try:
            q_values = []
            for q_target in (-100.0, -50.0, 0.0, 100.0, 200.0, 300.0):
                sim.set_unit_q_target('GEN-1', q_target)
                sim.tick(0.001)
                state = sim.get_state()
                q_values.append(state.unit_q_injections_mvar['GEN-1'])

            v_after = state.bus_voltages['WEAK']
            assert v_after > v_before, \
                f"Raising GEN-1's Q target should raise WEAK's voltage: " \
                f"before={v_before:.4f}, after={v_after:.4f}"
            assert abs(q_values[-1] - 200.0) < 1e-6, \
                f"GEN-1's Q should be clamped at q_max_mvar=200, got {q_values[-1]}"
            assert state.unit_q_reserve_mvar['GEN-1'] == 0.0, \
                f"GEN-1's q_reserve should be 0 once saturated, got {state.unit_q_reserve_mvar['GEN-1']}"
            assert q_values == sorted(q_values), \
                f"Q should rise monotonically as target rises: {q_values}"
            print(f"  WEAK {v_before:.4f} -> {v_after:.4f}, "
                  f"GEN-1 Q -> {q_values[-1]:.1f} (clamped) — PASS")
        except AssertionError as e:
            print(f"  generator Q target raises region: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# TEST 13 — PV correction converges: a satisfied bus keeps real Q reserve
# ─────────────────────────────────────────────────────────────────────────────
#
# These two tests exercise VoltageModel.solve()'s PV correction directly (the
# code changed in the "converging PV correction" simplification). The old
# single-pass correction could never leave a PV bus "satisfied" with reserve —
# it re-chased the same voltage error every tick and pinned any active PV bus
# to its Q ceiling — and it could diverge on a bus with two comparable
# electrical paths (SHIFT4_VOLTAGE_INVESTIGATION.md §5). The bounded
# fixed-point iteration fixes both; these lock that in.

def _two_path_voltage_model():
    """
    Grid reproducing the investigation's §5 topology: a generator bus (GEN)
    tied to the strong backbone (SLK) by TWO comparable-reactance paths — a
    direct tie and one via an intermediate bus (MID). This is the arrangement
    the single-pass correction diverged on. Returns (VoltageModel, grid).
    """
    from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
    from simulation.designer_grid import DesignerGrid
    from simulation.voltage import VoltageModel

    buses = [
        DesignerBus(label='SLK', name='Slack', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=0, canvas_y=0,
                    active_from_shift=1, is_slack=True),
        DesignerBus(label='MID', name='Mid', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=50, canvas_y=50,
                    active_from_shift=1, is_slack=False),
        DesignerBus(label='GEN', name='Support gen', voltage_kv=400.0,
                    bus_type='TRANSMISSION', canvas_x=100, canvas_y=0,
                    active_from_shift=1, is_slack=False),
        DesignerBus(label='LOAD', name='Load', voltage_kv=150.0,
                    bus_type='LOAD', canvas_x=150, canvas_y=0,
                    active_from_shift=1, is_slack=False, peak_load_mw=200.0),
    ]
    lines = [
        # Two comparable paths from GEN back to the backbone: GEN-SLK direct,
        # and GEN-MID-SLK. Comparable reactances = two competing pulls on GEN.
        DesignerLine(label='L1', from_bus='SLK', to_bus='GEN',
                     reactance_pu=0.20, rating_mw=2000.0, voltage_kv=400.0),
        DesignerLine(label='L2', from_bus='SLK', to_bus='MID',
                     reactance_pu=0.10, rating_mw=2000.0, voltage_kv=400.0),
        DesignerLine(label='L3', from_bus='MID', to_bus='GEN',
                     reactance_pu=0.10, rating_mw=2000.0, voltage_kv=400.0),
        DesignerLine(label='L4', from_bus='GEN', to_bus='LOAD',
                     reactance_pu=0.15, rating_mw=2000.0, voltage_kv=150.0),
    ]
    units = [
        DesignerUnit(label='GEN-1', station_label='GEN', bus_label='GEN',
                     unit_type='CCGT', rated_mw=1000.0, min_mw=0.0, inertia_h=4.0, cold_start_min=5.0,
                     q_max_mvar=200.0, q_min_mvar=-200.0, can_pump=False,
                     active_from_shift=1, description='two-path support gen'),
    ]
    grid = DesignerGrid(buses, lines, units)
    return VoltageModel(grid), grid


def test_pv_bus_satisfied_keeps_reserve() -> bool:
    """
    A PV bus that is NOT reactive-exhausted must settle at a Q strictly inside
    its limits — leaving real reserve — and that Q must be a stable fixed
    point: re-solving with the settled Q supplied as a fixed injection
    reproduces the same bus voltage. The pre-simplification single pass could
    do neither — it pinned any active PV bus to its ceiling every tick (so
    unit_q_reserve was always ~0) and never reached a fixed point (it
    re-chased the same voltage error indefinitely). This is the direct
    regression test for the investigation's core finding.
    """
    print("test_pv_bus_satisfied_keeps_reserve...")
    all_passed = True

    try:
        vm, _grid = _two_path_voltage_model()
        q_inj = {'SLK': 0.0, 'MID': 0.0, 'GEN': 0.0, 'LOAD': -40.0}
        q_max, q_min = 200.0, -200.0
        result = vm.solve(q_inj, pv_buses={'GEN': (1.0, q_max, q_min)})

        q_used = result.q_injections_used['GEN']
        v_gen = result.bus_voltages['GEN']

        # Fixed-point check: feed the settled Q back in as a plain injection,
        # no PV correction — a converged PV solve must reproduce the voltage.
        q_fixed = dict(q_inj)
        q_fixed['GEN'] = q_used
        v_gen_replay = vm.solve(q_fixed, pv_buses={}).bus_voltages['GEN']

        try:
            assert 'GEN' not in result.pq_buses, \
                f"GEN should stay PV (not exhausted) for a reachable target, " \
                f"but it converted to PQ (Q={q_used:.1f})"
            assert q_min + 1.0 < q_used < q_max - 1.0, \
                f"GEN should settle strictly inside its Q range with reserve " \
                f"left, got Q={q_used:.2f} (limits {q_min}..{q_max})"
            assert abs(v_gen - v_gen_replay) < 1e-6, \
                f"Settled Q must be a fixed point: PV solve gave V={v_gen:.6f}, " \
                f"replay with that Q gave {v_gen_replay:.6f}"
            print(f"  GEN Q={q_used:.1f} MVAr (reserve to ±{q_max:.0f}), "
                  f"V={v_gen:.4f}, still PV, fixed point — PASS")
        except AssertionError as e:
            print(f"  pv bus satisfied keeps reserve: FAIL — {e}")
            all_passed = False

    except Exception as e:
        print(f"  ERROR — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# TEST 14 — PV correction terminates and stays bounded on a two-path bus
# ─────────────────────────────────────────────────────────────────────────────

def test_pv_correction_bounded_on_two_path_bus() -> bool:
    """
    A generator bus with two comparable electrical paths to the backbone —
    the arrangement that diverged the single-pass correction into an
    oscillating, off-scale voltage (investigation §5) — must now solve to a
    finite, physically-bounded voltage across a sweep of setpoints, with the
    iteration terminating (never NaN/inf, never runaway).
    """
    print("test_pv_correction_bounded_on_two_path_bus...")
    import math
    all_passed = True

    try:
        vm, _grid = _two_path_voltage_model()
        q_inj = {'SLK': 0.0, 'MID': 0.0, 'GEN': 0.0, 'LOAD': -120.0}

        try:
            for setpoint in (0.95, 0.98, 1.0, 1.02, 1.05):
                result = vm.solve(q_inj, pv_buses={'GEN': (setpoint, 200.0, -200.0)})
                for label, v in result.bus_voltages.items():
                    assert math.isfinite(v), \
                        f"Voltage at {label} must be finite (setpoint {setpoint}), got {v}"
                    # A decoupled solve on a sane grid should never leave the
                    # [0, 2] pu envelope; the old divergence blew far past this.
                    assert 0.0 <= v <= 2.0, \
                        f"Voltage at {label} out of physical envelope " \
                        f"(setpoint {setpoint}): {v:.4f}"
                q_used = result.q_injections_used['GEN']
                assert -200.0 - 1e-6 <= q_used <= 200.0 + 1e-6, \
                    f"GEN Q must stay within limits, got {q_used:.2f}"
            print("  finite, bounded voltages across setpoint sweep — PASS")
        except AssertionError as e:
            print(f"  pv correction bounded on two-path bus: FAIL — {e}")
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
        test_reactive_load_moves_voltage(),
        test_low_pf_sags_more(),
        test_q_load_injections_math(),
        test_generator_q_target_feeds_injections(),
        test_blackout_zones_exclude_reactive_load(),
        test_collapse_offset_accumulates(),
        test_warning_to_critical_alarms_and_crisis(),
        test_offset_decays_on_recovery(),
        test_auto_shunt_holds_without_hunting(),
        test_manual_svc_monotonic_and_clamped(),
        test_generator_q_target_raises_region_and_clamps(),
        test_pv_bus_satisfied_keeps_reserve(),
        test_pv_correction_bounded_on_two_path_bus(),
    ]
    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    if passed < total:
        sys.exit(1)
