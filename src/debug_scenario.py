"""
src/debug_scenario.py

Debug scenario configuration — template for the future in-game scenario system.

Set DEBUG_SCENARIO_ACTIVE = True in constants.py to boot into the configured
scenario instead of the normal shift handover.
"""

from dataclasses import dataclass
from simulation.grid import Grid
from simulation.simulation import GridSimulation
from data.profiles import SHIFT_SPECS, ShiftSpec


@dataclass
class DebugScenario:
    shift_number:            int
    initial_schedule:        dict[str, float]   # {unit_label: initial_mw}
    peak_demand_mw:          float              # overrides ShiftSpec.peak_demand_mw
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
    base_spec = SHIFT_SPECS[scenario.shift_number]
    patched_spec = ShiftSpec(
        shift_number=base_spec.shift_number,
        start_hour=scenario.start_hour,
        duration_hours=base_spec.duration_hours,
        grid_size=base_spec.grid_size,
        has_phase1=base_spec.has_phase1,
        peak_demand_mw=scenario.peak_demand_mw,
        difficulty_label=base_spec.difficulty_label,
        handover_notes=(f'[DEBUG] {scenario.description}',),
    )

    # Temporarily replace SHIFT_SPECS entry so GridSimulation.__init__ sees the overrides.
    # ShiftSpec is frozen=True so we construct a new instance rather than mutating.
    from data import profiles as _profiles
    original_spec = _profiles.SHIFT_SPECS[scenario.shift_number]
    _profiles.SHIFT_SPECS[scenario.shift_number] = patched_spec

    try:
        grid = Grid(scenario.shift_number)
        sim  = GridSimulation(
            grid=grid,
            shift_number=scenario.shift_number,
            difficulty='standard',
            initial_schedule=scenario.initial_schedule,
        )
    finally:
        _profiles.SHIFT_SPECS[scenario.shift_number] = original_spec

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
    description='Shift 1 Dispatch Stress Test — L22 out, demand near peak, limited thermal headroom',
    shift_number=1,
    start_hour=6.0,         # 09:00 — morning ramp complete, demand climbing
    peak_demand_mw=1800.0,  # near Shift 1 peak (normal = 2200 MW)
    initial_schedule={
        'HART-1': 680.0,    # nuclear baseload
        'HART-2': 680.0,
        'RVSD-1': 280.0,    # coal raised from 200 MW handover — tighter headroom
        'RVSD-3': 240.0,    # RVSD-2 still OOS (COALCOM easter egg)
        'DUNH-1': 100.0,
        'DUNH-2': 100.0,
        'DUND-1':  40.0,
        'DUND-2':  40.0,
        'BR01-1':  30.0,
        'BR01-2':  30.0,
    },
    line_outages=['L22'],           # L22 (RDST–BRCK) out → BRCK and LD01 isolated
    interconnector_north_mw=100.0,
    interconnector_south_mw=0.0,
    reservoir_levels={
        'DUNH': 0.50,               # placeholder — no effect until Stage 13
    },
    demand_schedule={
         6.0: 2100.0,   # 06:00 — morning low
         9.0: 2100.0,   # 09:00 — ramp complete (scenario start)
        12.0: 2180.0,   # midday plateau
        18.0: 2180.0,   # evening peak
        22.0: 2180.0,   # late-night decline
    },
)
