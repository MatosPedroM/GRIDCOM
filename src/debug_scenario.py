"""
src/debug_scenario.py

Debug scenario configuration — template for the future in-game scenario system.

Set DEBUG_SCENARIO_ACTIVE = True in constants.py to boot into the configured
scenario instead of the normal shift handover.
"""

from dataclasses import dataclass
from simulation.grid import Grid
from simulation.simulation import GridSimulation
from gameplay.shifts.loader import load_shift_config


@dataclass
class DebugScenario:
    shift_number:            int
    initial_schedule:        dict[str, float]   # {unit_label: initial_mw}
    peak_demand_mw:          float              # overrides the shift's grid-derived peak demand
    start_hour:              float              # sim clock start (0.0–23.0)
    line_outages:            list[str]          # line labels to trip on init
    interconnector_north_mw: float             # INTC-N MW (positive = import)
    interconnector_south_mw: float             # INTC-S MW (positive = import)
    reservoir_levels:        dict[str, float]  # {station_prefix: 0.0–1.0} — future use
    demand_schedule:         dict[float, float] # {sim_hour: demand_mw} — overrides profile
    description:             str               # shown in debug overlay


def make_debug_sim(scenario: DebugScenario) -> tuple[GridSimulation, Grid]:
    """
    Construct a GridSimulation and Grid from a DebugScenario spec.
    Returns (sim, grid) ready to pass to Renderer.
    """
    grid = Grid(scenario.shift_number)
    sim  = GridSimulation(
        grid=grid,
        shift_number=scenario.shift_number,
        difficulty='standard',
        initial_schedule=scenario.initial_schedule,
        start_hour=scenario.start_hour,
        duration_hours=load_shift_config(scenario.shift_number)['duration_hours'],
    )
    sim._demand._peak_demand_mw = scenario.peak_demand_mw

    for line_label in scenario.line_outages:
        sim.trip_line(line_label)

    sim.set_interconnector_schedule('INTC-N', scenario.interconnector_north_mw)
    sim.set_interconnector_schedule('INTC-S', scenario.interconnector_south_mw)

    if scenario.demand_schedule:
        sim._demand.set_demand_override(scenario.demand_schedule, scenario.start_hour)

    # reservoir_levels: placeholder — no-op until UnitModel gains set_reservoir_level()
    # in Stage 13. Add calls here when that API exists.

    return sim, grid


# ─────────────────────────────────────────────────────────────────────────────
# CONCRETE DEBUG SCENARIO
# Edit this instance to change what the game boots into.
# ─────────────────────────────────────────────────────────────────────────────

DEBUG_SCENARIO: DebugScenario = DebugScenario(
    # Minimal starting state: one HYDRO_PUMP unit feeding one load bus.
    # Topology: DUNH-1 (STHW) → L06 → MDBY(slack) + L08 → ASHF → L14 → DUNM
    #           → L15 → RDST → L22 → BRCK → L37 → LD01
    # L01 (MDBY-CNTR) and L28 (DUNM-DUND) are tripped on init, isolating
    # CNTR (HART offline) and DUND (DUND offline) as correct blackout zones.
    # Use this to verify: power flow delivery, AGC frequency control (Ctrl+A),
    # and frequency runaway trip when L22 is opened (isolates LD01 from DUNH-1).
    description='Minimal: DUNH-1 (100 MW HYDRO_PUMP) → LD01 (90 MW). AGC + power flow test.',
    shift_number=1,
    start_hour=9.0,
    peak_demand_mw=225.0,       # overridden entirely by demand_schedule below
    initial_schedule={
        'DUNH-1': 100.0,        # HYDRO_PUMP, 200 MW rated — starts at 100 MW
    },
    # Keep in service: L06(STHW-MDBY), L08(STHW-ASHF), L14(ASHF-DUNM),
    #                  L15(DUNM-RDST), L22(RDST-BRCK), L37(BRCK-LD01)
    line_outages=['L01', 'L28'],
    interconnector_north_mw=0.0,
    interconnector_south_mw=0.0,
    reservoir_levels={
        'DUNH': 0.70,
    },
    demand_schedule={
         0.0: 90.0,   # flat 90 MW all day — ~10 MW headroom above DUNH-1 output
        24.0: 90.0,   # AGC should settle DUNH-1 near 92–93 MW to cover losses
    },
)
