"""
scripts/verify_freq_dynamics_scale.py

Headless tuning harness for FREQ_DYNAMICS_SCALE, built against Shift 10's
real grid/fleet (the campaign's hardest shift and the one that motivated
this retune) rather than a synthetic fixture. Drives a real GridSimulation
exactly as main.py's loop does (dt_sim_seconds = real_dt * TIME_COMPRESSION
* speed), using the same construction path as _make_sim_and_renderer():
Phase 1's build_planning_model(10) + auto_schedule() for a real,
well-formed handover dispatch, then a do-nothing trace at 1x speed.

Confirms two things:
  1. FREQ_DYNAMICS_SCALE is live-readable (mutating simulation.constants
     mid-process changes the result) -- this was NOT true before the
     frozen-import fix in frequency.py, so a run of this script that shows
     different results per scale is itself a regression check that the fix
     is real.
  2. The current constants.py value gives roughly the reaction window
     measured during its own retuning (see constants.py's own comment).

This is a tuning tool, not a correctness assertion -- re-run after any
change to FREQ_DYNAMICS_SCALE and eyeball the results. Not part of the
pytest/test_simulation.py suite.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import simulation.constants as _sim_const
from gameplay.phase1 import build_planning_model
from simulation.simulation import GridSimulation
from simulation.constants import F_ALERT_LOW, F_ALERT_HIGH, TIME_COMPRESSION, SIM_TICK_INTERVAL_S
from data.designer_io import load_designer_grid_named
from simulation.designer_grid import DesignerGrid
from gameplay.shifts.loader import load_shift_config

REAL_DT = SIM_TICK_INTERVAL_S


def make_shift10_sim() -> GridSimulation:
    """
    Builds Shift 10 exactly as _make_sim_and_renderer() does, but with the
    handover dispatch coming from Phase 1's own auto_schedule() heuristic
    (a real, well-formed 0-diff plan) instead of a player-confirmed
    schedule file -- so this harness has no dependency on a saved plan
    existing on disk.
    """
    model = build_planning_model(10, difficulty='standard')
    model.auto_schedule()
    initial_schedule = model.to_initial_schedule()
    hourly_schedule = model.to_hourly_dispatch()
    agc_enrolled_units = frozenset(l for l, en in model.agc_enrolled.items() if en)

    cfg = load_shift_config(10)
    buses, lines, units = load_designer_grid_named(cfg['grid_source'])
    grid = DesignerGrid(buses, lines, units)

    _sim_const.AGC_ENABLED = cfg['agc_enabled']
    _sim_const.FREQ_TOLERANCE_MULT = cfg.get('freq_tolerance_mult', 1.0)
    _sim_const.AGC_SPEED_MULT = cfg.get('agc_speed_mult', 1.0)
    _sim_const.LANDING_FREEZE_S = 0.0  # skip freeze; this harness measures from T+0

    sim = GridSimulation(
        grid=grid, shift_number=10, difficulty='standard',
        initial_schedule=initial_schedule,
        maintenance_units=cfg['maintenance_units'],
        maintenance_lines=cfg['maintenance_lines'],
        substation_load_mw=cfg['substation_load_mw'] or None,
        substation_types=cfg.get('substation_types') or None,
        hourly_schedule=hourly_schedule,
    )
    if cfg.get('substation_types'):
        sim.seed_default_reactive_devices(cfg['substation_types'])

    eligible_labels = {
        u.label for u in grid.get_active_units()
        if u.unit_type in _sim_const.AGC_ELIGIBLE_TYPES
    }
    sim.set_agc_excluded_units(eligible_labels - agc_enrolled_units)
    return sim


def run_do_nothing_trace(scale: float, max_real_s: float = 120.0) -> None:
    _sim_const.FREQ_DYNAMICS_SCALE = scale
    sim = make_shift10_sim()

    elapsed_real_s = 0.0
    left_band_at: float | None = None
    min_freq = 50.0

    n_ticks_per_real_s = int(round(1.0 / REAL_DT))
    for _ in range(int(max_real_s * n_ticks_per_real_s)):
        sim.tick(REAL_DT * TIME_COMPRESSION * 1.0)
        elapsed_real_s += REAL_DT
        f = sim.get_state().frequency_hz
        min_freq = min(min_freq, f)
        if left_band_at is None and not (F_ALERT_LOW <= f <= F_ALERT_HIGH):
            left_band_at = elapsed_real_s

    print(f'  scale={scale:<8} left_alert_band={left_band_at!r:>8}  '
          f'min_freq(after {max_real_s:.0f}s)={min_freq:.4f} Hz')


if __name__ == '__main__':
    _shipped_value = _sim_const.FREQ_DYNAMICS_SCALE
    print(f'Shipped value (constants.py): FREQ_DYNAMICS_SCALE = {_shipped_value}')
    print()
    print('Shift 10 do-nothing worst-case trace (auto-scheduled plan, 1x speed):')
    print('(different results per scale below confirm FREQ_DYNAMICS_SCALE is live-readable)')
    for candidate in (0.02, 0.01, 0.005, 0.002, 0.001):
        run_do_nothing_trace(candidate)
