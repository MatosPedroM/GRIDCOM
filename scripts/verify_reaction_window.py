"""
scripts/verify_reaction_window.py

Headless tuning harness for Improvement #1 ("put the player back on the
clock"). Drives a real GridSimulation exactly as main.py's loop does
(dt_sim_seconds = real_dt * TIME_COMPRESSION * speed), fires the Shift 3
RIVE-2 derate scripted action directly, and measures:

  - real seconds from the derate to frequency first leaving the alert band
  - real seconds from the derate to frequency settling back near nominal
  - real seconds from a forced sustained overload to the line tripping
  - real seconds from a forced low-voltage bus to full collapse and recovery

This is a tuning tool, not a correctness assertion -- re-run after any
constant change in GAMEPLAY_ANALYSIS.md's Improvement #1 and eyeball the
results against the developer's 10-20 real-second target. Not part of the
pytest/test_simulation.py suite.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from simulation.grid import Grid
from simulation.simulation import GridSimulation
from simulation.constants import (
    F_NOMINAL, F_ALERT_LOW, F_ALERT_HIGH, TIME_COMPRESSION,
    SIM_TICK_INTERVAL_S, TRIP_DELAY_S, V_WARNING_LOW,
)

REAL_DT = SIM_TICK_INTERVAL_S  # mirror main.py's per-tick real-time accumulation


def make_sim(shift_number: int = 3) -> GridSimulation:
    """
    Uses the plain campaign topology (Grid(3), not shift_03.py's Designer
    grid) since this harness only needs a realistic-scale fleet to measure
    timing against, not the exact hand-authored Shift 3 scenario. RVSD-2
    (300 MW COAL, 90 MW min) stands in for the RIVE-2 derate this plan's
    derivations were based on -- HART/ASHG/WRNG are excluded here since
    their technical minimums alone (490+490+80+80... MW) already exceed
    this shift's ~425 MW demand on the plain topology, which would leave
    generation permanently oversupplied regardless of dispatch.

    Dispatch is auto-balanced against this shift's actual peak demand
    (rather than a guessed schedule) so frequency starts genuinely flat at
    nominal instead of drifting from an accidental supply/demand mismatch.
    """
    grid = Grid(shift_number=shift_number)
    probe = GridSimulation(grid, shift_number=shift_number, difficulty='Tutorial')
    target_mw = probe.get_state().total_load_mw

    # RVSD-1/2/3 (COAL, 90 MW min, 300 MW rated) plus DUND-1/2 (HYDRO, 0 min)
    # -- small enough combined minimum to sit below ~425 MW demand, while
    # dispatching RVSD-2 well above its 90 MW floor so derating it to that
    # floor later is a real, large drop (not a no-op).
    rvsd2_mw = 250.0
    remaining = max(0.0, target_mw - rvsd2_mw)
    other_units = ['RVSD-1', 'RVSD-3', 'DUND-1', 'DUND-2']
    share = remaining / len(other_units)
    initial_schedule = {label: share for label in other_units}
    initial_schedule['RVSD-2'] = rvsd2_mw

    return GridSimulation(grid, shift_number=shift_number, difficulty='Tutorial',
                          initial_schedule=initial_schedule)


def run_freq_reaction_window(speed: float = 1.0, max_real_s: float = 120.0) -> None:
    sim = make_sim(3)

    # Run a couple of sim-minutes so AGC/fleet state settles before the
    # trip, rather than triggering from a cold start.
    while sim.get_state().sim_time_min < 2.0:
        sim.tick(REAL_DT * TIME_COMPRESSION * speed)

    # RVSD-2 dispatched at 250 MW, derating to its 90 MW minimum -- a 160 MW
    # loss on a ~425 MW fleet, comparable in relative scale to the RIVE-2
    # 200->105 MW derate this plan's derivations were based on.
    sim._fleet.get_unit('RVSD-2').derate(90.0)

    elapsed_real_s = 0.0
    left_band_at: float | None = None
    settled_at: float | None = None
    min_freq = F_NOMINAL

    while elapsed_real_s <= max_real_s:
        sim.tick(REAL_DT * TIME_COMPRESSION * speed)
        elapsed_real_s += REAL_DT
        f = sim.get_state().frequency_hz
        min_freq = min(min_freq, f)

        if left_band_at is None and not (F_ALERT_LOW <= f <= F_ALERT_HIGH):
            left_band_at = elapsed_real_s

        if left_band_at is not None and settled_at is None:
            if abs(f - F_NOMINAL) <= 0.02:
                settled_at = elapsed_real_s

    print(f'  speed={speed:>4.1f}x  '
          f'left_alert_band={left_band_at!r:>8}  '
          f'settled(<=0.02Hz)={settled_at!r:>8}  '
          f'min_freq={min_freq:.4f} Hz')


def run_overload_trip(speed: float = 1.0) -> None:
    """
    Drives CascadeModel.check_overloads() directly rather than through
    GridSimulation.tick() -- tick()'s own cascade step re-solves the real
    load flow each tick and would reset the timer back to 0 immediately
    (the line isn't actually overloaded in a real solve here), which
    defeats the point of isolating the timer's own timing.
    """
    from simulation.cascade import CascadeModel
    cascade = CascadeModel()
    line_label = make_sim(3)._grid.get_active_lines()[0].label

    elapsed_real_s = 0.0
    tripped_at: float | None = None
    timers: dict = {}
    max_real_s = (TRIP_DELAY_S / TIME_COMPRESSION) * 3.0  # generous ceiling

    while elapsed_real_s <= max_real_s and tripped_at is None:
        dt_sim = REAL_DT * TIME_COMPRESSION * speed
        elapsed_real_s += REAL_DT
        trips, timers = cascade.check_overloads({line_label: 100.0}, timers, dt_sim)
        if trips:
            tripped_at = elapsed_real_s

    print(f'  speed={speed:>4.1f}x  line={line_label}  tripped_at={tripped_at!r} real-s '
          f'(target ~15s)')


def run_voltage_collapse(speed: float = 1.0, max_real_s: float = 120.0) -> None:
    sim = make_sim(3)
    bus_label = next(iter(sim._grid.get_active_buses())).label

    elapsed_real_s = 0.0
    collapsed_at: float | None = None
    recovered_at: float | None = None

    # Force the bus into a sustained bad-voltage condition, then release it,
    # to measure the overlay's own decay/recovery timing in isolation.
    for _ in range(int(30.0 / REAL_DT)):
        sim.tick(REAL_DT * TIME_COMPRESSION * speed)
        elapsed_real_s += REAL_DT
        v_eff = sim._apply_collapse_acceleration(
            {bus_label: 0.80}, REAL_DT * TIME_COMPRESSION * speed
        )
        if v_eff[bus_label] <= 0.01 and collapsed_at is None:
            collapsed_at = elapsed_real_s

    recover_start = elapsed_real_s
    for _ in range(int(max_real_s / REAL_DT)):
        elapsed_real_s += REAL_DT
        v_eff = sim._apply_collapse_acceleration(
            {bus_label: 1.0}, REAL_DT * TIME_COMPRESSION * speed
        )
        if v_eff[bus_label] >= 0.99 and recovered_at is None:
            recovered_at = elapsed_real_s - recover_start
            break

    print(f'  speed={speed:>4.1f}x  bus={bus_label}  '
          f'collapsed_at={collapsed_at!r} real-s (target ~15s)  '
          f'recovered_after={recovered_at!r} real-s (target ~3x decay)')


if __name__ == '__main__':
    print('Frequency reaction window (Shift 3 RIVE-2 derate, 200->105 MW):')
    for spd in (1.0, 3.0, 10.0):
        run_freq_reaction_window(speed=spd)

    print()
    print('Overload trip timing (forced sustained 100%+ line):')
    for spd in (1.0, 3.0):
        run_overload_trip(speed=spd)

    print()
    print('Voltage collapse timing (forced 0.80pu bus, isolated overlay):')
    for spd in (1.0,):
        run_voltage_collapse(speed=spd)
