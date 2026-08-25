"""
src/data/topology.py

Bus and Line dataclass definitions for GRIDCOM's network representation.

The campaign's hardcoded bus/line data (formerly BUSES/LINES/
INTERCONNECTOR_POSITIONS + get_buses_by_shift()/get_lines_by_shift()/
get_bus()/get_line()) was retired once every campaign shift moved onto
GRID_SOURCE (a Grid Designer JSON grid, loaded via DesignerGrid) — see
simulation/designer_grid.py. These two dataclasses remain as the shared
network-element types: DesignerGrid still constructs Bus/Line instances
from DesignerBus/DesignerLine (data/designer_io.py) for its internal
representation, and several simulation modules type-hint against them.

See GRID_TOPOLOGY_AND_DISPLAY.md for visual specification.
See DOMAIN_GLOSSARY.md for bus type definitions.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Bus:
    """
    A node in the electrical network.

    Attributes:
        label:            4-char uppercase identifier (e.g. 'MDBY', 'CNTR')
        name:             Human-readable name for display
        voltage_kv:       Nominal voltage level (400, 220, 150, or 60)
        bus_type:         'TRANSMISSION' or 'LOAD' (150kV load substations)
        canvas_x:         X coordinate in native 1920×844 canvas pixels
        canvas_y:         Y coordinate in native 1920×844 canvas pixels
        active_from_shift: First shift in which this bus is active
        is_slack:         True only for the grid's designated slack bus
    """
    label:             str
    name:              str
    voltage_kv:        float
    bus_type:          str
    canvas_x:          int
    canvas_y:          int
    active_from_shift: int
    is_slack:          bool = False


@dataclass(frozen=True)
class Line:
    """
    A transmission line connecting two buses.

    Attributes:
        label:             Line identifier (e.g. 'L01')
        from_bus:          Label of the originating bus
        to_bus:            Label of the destination bus
        reactance_pu:      Series reactance in per-unit on S_BASE = 1000 MVA
        rating_mw:         Thermal rating in MW (100% = trip threshold)
        active_from_shift: First shift in which this line is active
        active_until_shift: Last shift in which this line is active (99 = permanent)
        voltage_kv:        Voltage level (matches the higher-voltage endpoint)
        parallel:          Perpendicular draw offset direction for double-circuit
                           pairs (+1 / -1); 0 for single-circuit lines. Display
                           only — has no electrical meaning.
        from_port_override: Manual attachment-port override for the from_bus
                           end, (side, slot) e.g. ('N', 0), or None for the
                           automatic bearing-derived port. Display only — has
                           no electrical meaning. Set via the Grid Designer's
                           line-rotate feature.
        to_port_override:  Same as from_port_override, for the to_bus end.
        length_km:         Physical span in km — the basis reactance_pu is
                           derived from (see config.constants.
                           reactance_pu_per_km()). None only for legacy data
                           predating this field; never solved on directly.
    """
    label:              str
    from_bus:           str
    to_bus:             str
    reactance_pu:       float
    rating_mw:          float
    active_from_shift:  int
    voltage_kv:         float
    active_until_shift: int = 99
    parallel:           int = 0
    from_port_override: tuple[str, int] | None = None
    to_port_override:   tuple[str, int] | None = None
    length_km:          float | None = None
