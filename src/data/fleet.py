"""
src/data/fleet.py

GenerationUnit dataclass definition for GRIDCOM.

The campaign's hardcoded 47-unit fleet (formerly UNITS + get_units_by_shift()/
get_unit()/get_units_at_bus()/get_units_at_station(), plus STATION_POSITIONS/
get_station_position()) was retired once every campaign shift moved onto
GRID_SOURCE (a Grid Designer JSON grid, loaded via DesignerGrid) — see
simulation/designer_grid.py. This dataclass remains as the shared unit type:
DesignerGrid still constructs GenerationUnit instances from DesignerUnit
(data/designer_io.py) for its internal representation, and several
simulation modules type-hint against it.

See DOMAIN_GLOSSARY.md for unit type definitions and ramp/inertia values.
See CLAUDE.md for station and unit naming conventions.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationUnit:
    """
    A single generation unit (one turbine-generator set).

    Attributes:
        label:             Unit identifier, e.g. 'RVSD-1', 'HART-2'
        station_label:     Parent station label, e.g. 'RVSD', 'HART'
        bus_label:         Bus this unit connects to (transmission bus label)
        unit_type:         'COAL', 'CCGT', 'NUCLEAR', 'HYDRO', 'HYDRO_ROR',
                           'HYDRO_PUMP', 'WIND', or 'SOLAR'
        rated_mw:          Maximum output at rated conditions (MW)
        min_mw:            Minimum stable output when online (MW)
        ramp_mw_per_min:   Max ramp rate in MW per simulated minute (absolute,
                           looked up by unit_type from constants.py's
                           UNIT_DEFAULTS — not authored per-unit)
        inertia_h:         Inertia constant H in seconds (0.0 for wind/solar)
        cold_start_min:    Simulated minutes from OFFLINE to ONLINE
        q_max_mvar:        Maximum reactive power injection (MVAr)
        q_min_mvar:        Maximum reactive power absorption (MVAr, negative)
        can_pump:          True for pumped storage units (HYDRO_PUMP)
        active_from_shift: First shift where this unit is available
        description:       Human-readable description for context panel
        min_up_time_h:     Minimum hours a unit must stay ONLINE once
                           committed (Phase 1 planning-layer constraint only —
                           not enforced by the real-time simulation)
        min_down_time_h:   Minimum hours a unit must stay OFFLINE before
                           restarting (Phase 1 planning-layer constraint only)

    Phase 1 scheduler economics (startup cost, fuel cost, AGC-availability
    cost) are NOT unit fields — they're looked up by unit_type from
    constants.py's STARTUP_COST_EUR_BY_TYPE / VARIABLE_COST_EUR_PER_MWH_BY_TYPE,
    scaled by DIFFICULTY_COST_MULT. Cost is a per-technology property, not a
    per-fleet-unit override.
    """
    label:             str
    station_label:     str
    bus_label:         str
    unit_type:         str
    rated_mw:          float
    min_mw:            float
    ramp_mw_per_min:   float
    inertia_h:         float
    cold_start_min:    float
    q_max_mvar:        float
    q_min_mvar:        float
    can_pump:          bool
    active_from_shift: int
    description:       str
    min_up_time_h:     float = 0.0
    min_down_time_h:   float = 0.0
