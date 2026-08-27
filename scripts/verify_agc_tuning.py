"""
scripts/verify_agc_tuning.py

Headless tuning harness for the AGC PID gains (AGC_KP/AGC_KI/AGC_KD),
built against the developer's own grid_medium_1 Designer test grid and
reported reproduction steps: bring the grid to a stable running state,
then step both Riverside coal units (RIVE-1/RIVE-2) down to their 105 MW
technical minimum, and watch whether frequency converges to 50.00 Hz or
settles into a persistent cyclical oscillation.

make_sim() builds grid_medium_1 via the same substation_load_mw derivation
main.py's _make_designer_test() uses (each LOAD bus's peak_load_mw x
DEMAND_PROFILE_NORMALISED) -- the real Designer "Test Grid" path, not a
synthetic fixture -- but with its own balanced initial dispatch (see
make_sim()'s docstring for why). Mirrors
scripts/verify_freq_dynamics_scale.py's sys.path/_sim_const live-mutation
pattern so gain candidates can be swept in-process without a restart.

This is a tuning tool, not a correctness assertion -- not part of the
pytest/test_simulation.py suite.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import config.constants as _sim_const
from simulation.simulation import GridSimulation
from simulation.designer_grid import DesignerGrid
from config.constants import TIME_COMPRESSION, SIM_TICK_INTERVAL_S, F_NOMINAL
from data.designer_io import load_designer_grid_named
from data.profiles import DEMAND_PROFILE_NORMALISED

REAL_DT = SIM_TICK_INTERVAL_S


def make_sim() -> GridSimulation:
    """
    Builds grid_medium_1 exactly as main.py's _make_designer_test() does
    (the real Designer "Test Grid" path) -- AGC on, default speed
    multiplier, shift_number=0 sentinel, substation loads profiled from
    each LOAD bus's own peak_load_mw across the campaign's generic demand
    shape.

    _make_designer_test()'s own initial_schedule (each unit at its
    authored start_mw, or 50% of rated_mw if unset) badly oversupplies
    grid_medium_1 -- pins frequency at F_MAX before AGC ever gets to act,
    which isn't the scenario being tested. This harness instead
    water-fills dispatch to the sim's own measured total_load_mw: every
    non-renewable unit starts at its min_mw, then the remaining load need
    is split proportionally by *headroom* (rated_mw - min_mw) across that
    same fleet -- guarantees every unit lands inside [min_mw, rated_mw]
    as long as total fleet headroom covers the remaining need (true at
    hour 12, ~2574 MW, this grid's fleet has ~2110 MW of combined
    headroom above the ~1300 MW combined floor). Total generation is
    scaled to the sim's own measured total_load_mw (read from a
    throwaway probe build), not a hardcoded figure, so this stays correct
    if grid_medium_1 is edited.
    """
    buses, lines, units = load_designer_grid_named('grid_medium_1')
    grid = DesignerGrid(buses, lines, units)

    substation_load_mw = {
        b.label: {h: b.peak_load_mw * DEMAND_PROFILE_NORMALISED[h]
                  for h in DEMAND_PROFILE_NORMALISED}
        for b in buses
        if b.bus_type == 'LOAD' and b.peak_load_mw > 0
    }
    substation_types = {
        b.label: b.substation_type for b in buses if b.label in substation_load_mw
    }
    maintenance_units = {u.label for u in units if not u.in_service}
    dispatchable = [u for u in units if u.unit_type not in ('WIND', 'SOLAR')]

    _sim_const.AGC_ENABLED = True
    _sim_const.AGC_SPEED_MULT = 1.0

    probe = GridSimulation(
        grid=grid, shift_number=0, difficulty='standard',
        maintenance_units=maintenance_units, maintenance_lines=set(),
        substation_load_mw=substation_load_mw, substation_types=substation_types,
        start_hour=12.0, duration_hours=6.0,
    )
    target_load = probe.get_state().total_load_mw

    total_floor = sum(u.min_mw for u in dispatchable)
    total_headroom = sum(u.rated_mw - u.min_mw for u in dispatchable)
    remaining = max(0.0, min(target_load, total_floor + total_headroom) - total_floor)
    initial_schedule = {
        u.label: u.min_mw + remaining * ((u.rated_mw - u.min_mw) / total_headroom)
        for u in dispatchable
    }
    initial_schedule.update({u.label: 0.0 for u in units if u.unit_type in ('WIND', 'SOLAR')})

    sim = GridSimulation(
        grid=grid, shift_number=0, difficulty='standard',
        initial_schedule=initial_schedule,
        maintenance_units=maintenance_units,
        maintenance_lines=set(),
        substation_load_mw=substation_load_mw,
        substation_types=substation_types,
        start_hour=12.0, duration_hours=6.0,
    )
    sim.seed_default_reactive_devices(substation_types)
    return sim


def run_trial(kp: float, ki: float, kd: float, integral_max: float,
               settle_real_s: float = 90.0, measure_real_s: float = 120.0,
               speed: float = 1.0) -> None:
    """
    speed multiplies dt_sim_seconds per tick exactly like main.py's own
    speed control (F12) does. Defaults to 1x (real-time, matching the
    developer's own manual playtest and main.py's default) -- a coarser
    dt_sim_seconds per tick at higher speed feeds AGC's derivative term a
    less accurate finite-difference approximation of df/dt, which risks
    conflating a speed-resolution artifact with genuine gain-tuning
    hunting. 1x costs ~4ms/tick in this environment, cheap enough to run
    the full settle+measure window directly.
    """
    _sim_const.AGC_KP = kp
    _sim_const.AGC_KI = ki
    _sim_const.AGC_KD = kd
    _sim_const.AGC_INTEGRAL_MAX = integral_max
    _sim_const.AGC_LOG = False
    _sim_const.SIM_STATE_LOG = False

    sim = make_sim()
    dt = REAL_DT * TIME_COMPRESSION * speed

    # Let the fleet/AGC settle to nominal from the initial dispatch before
    # applying the disturbance -- matches "reducing Riverside... after some
    # time to let the freq stabilized near 50 Hz" from the report.
    for _ in range(int(settle_real_s / REAL_DT / speed)):
        sim.tick(dt)

    settle_err = abs(sim.get_state().frequency_hz - F_NOMINAL)

    # The reported reproduction: both Riverside coal units to 105 MW.
    sim.set_unit_target('RIVE-1', 105.0)
    sim.set_unit_target('RIVE-2', 105.0)

    # Run past the initial transient, then measure steady-state cycling
    # over the back half of the measurement window only.
    n_ticks = int(measure_real_s / REAL_DT / speed)
    freqs = []
    for _ in range(n_ticks):
        sim.tick(dt)
        freqs.append(sim.get_state().frequency_hz)

    tail = freqs[len(freqs) // 2:]  # discard first half (transient), keep steady-state tail
    tail_min, tail_max = min(tail), max(tail)
    amplitude = tail_max - tail_min
    tail_mean_err = sum(abs(f - F_NOMINAL) for f in tail) / len(tail)
    final_err = abs(freqs[-1] - F_NOMINAL)

    print(f'  KP={kp:<7.1f} KI={ki:<6.2f} KD={kd:<8.1f} IMAX={integral_max:<6.1f}  '
          f'settle_err={settle_err:.4f} Hz  tail_p2p={amplitude:.4f} Hz  '
          f'tail_mean_err={tail_mean_err:.4f} Hz  final_err={final_err:.4f} Hz', flush=True)


if __name__ == '__main__':
    print('Old AGC_KI=5.0 (pre-fix) -- persistent hunting, does not settle to +/-0.01 Hz:')
    run_trial(kp=100.0, ki=5.0, kd=2000.0, integral_max=60.0)

    print()
    print('Current AGC_KI=1.0 (constants.py) -- settles to a steady +/-0.01 Hz band:')
    run_trial(kp=100.0, ki=1.0, kd=2000.0, integral_max=60.0)

    print()
    print('Same check from a cold (unsettled) start -- disturbance applied immediately at')
    print('T+0, no prior settle period, confirming the fix does not depend on the settle window:')
    run_trial(kp=100.0, ki=1.0, kd=2000.0, integral_max=60.0,
              settle_real_s=0.0, measure_real_s=300.0)

    print()
    print('KI narrowing sweep, for re-tuning if grid_medium_1 or the fleet changes')
    print('(KP=100, KD=2000.0, IMAX=60.0 held):')
    for ki in (2.0, 1.5, 1.0, 0.75, 0.5):
        run_trial(kp=100.0, ki=ki, kd=2000.0, integral_max=60.0)
