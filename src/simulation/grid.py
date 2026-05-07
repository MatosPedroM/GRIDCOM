"""
src/simulation/grid.py

Grid class: loads and exposes the active network topology and generation fleet
for a given shift. Acts as the single point of access for topology data
within the simulation layer.

Read-only after construction. All simulation modules receive a Grid object
and query it — they do not import from data.topology or data.fleet directly.

See SIMULATION_API.md for the Grid public interface contract.
See DOMAIN_GLOSSARY.md for bus type and network component definitions.
"""

from data.topology import (
    Bus, Line,
    get_buses_by_shift, get_lines_by_shift,
    get_bus as _topology_get_bus,
    get_line as _topology_get_line,
    INTERCONNECTOR_POSITIONS,
)
from data.fleet import (
    GenerationUnit,
    get_units_by_shift,
    get_unit as _fleet_get_unit,
    get_units_at_bus as _fleet_get_units_at_bus,
    STATION_POSITIONS,
)
from data.profiles import get_demand_mw, LOAD_DISTRIBUTION


class Grid:
    """
    Active network topology and generation fleet for a specific shift.

    Loads buses, lines, and units filtered to those active at shift_number.
    Provides read-only query methods used throughout the simulation layer.

    Attributes:
        slack_bus:    Always 'MDBY' — the voltage angle reference bus.
        shift_number: The shift this Grid was constructed for.

    Usage:
        grid = Grid(shift_number=1)
        buses = grid.get_active_buses()
        lf = DCLoadFlow(grid)
    """

    def __init__(self, shift_number: int) -> None:
        """
        Load topology and fleet filtered to nodes active in this shift.

        Args:
            shift_number: 1-10. Controls which buses, lines, and units are active.

        Raises:
            ValueError: If shift_number is not in range 1-10.
        """
        if not (1 <= shift_number <= 10):
            raise ValueError(f"shift_number must be 1-10, got {shift_number}")

        self._shift_number: int = shift_number

        buses = get_buses_by_shift(shift_number)
        lines = get_lines_by_shift(shift_number)
        units = get_units_by_shift(shift_number)

        self._buses: dict[str, Bus] = {b.label: b for b in buses}
        self._lines: dict[str, Line] = {l.label: l for l in lines}
        self._units: dict[str, GenerationUnit] = {u.label: u for u in units}

        self._bus_list: list[Bus] = buses
        self._line_list: list[Line] = lines
        self._unit_list: list[GenerationUnit] = units

        # Pre-build bus → unit index for fast lookup
        self._units_at_bus: dict[str, list[GenerationUnit]] = {}
        for unit in units:
            self._units_at_bus.setdefault(unit.bus_label, []).append(unit)

    # ─────── PROPERTIES ───────────────────────────────────────────────────

    @property
    def slack_bus(self) -> str:
        """Always returns 'MDBY'."""
        return 'MDBY'

    @property
    def shift_number(self) -> int:
        """The shift this grid was loaded for."""
        return self._shift_number

    # ─────── ACTIVE ELEMENT QUERIES ───────────────────────────────────────

    def get_active_buses(self) -> list[Bus]:
        """All buses active in this shift, ordered as defined in topology.py."""
        return self._bus_list

    def get_active_lines(self) -> list[Line]:
        """All lines active in this shift, ordered as defined in topology.py."""
        return self._line_list

    def get_active_units(self) -> list[GenerationUnit]:
        """All generation units active in this shift."""
        return self._unit_list

    # ─────── ELEMENT LOOKUPS ──────────────────────────────────────────────

    def get_bus(self, label: str) -> Bus:
        """
        Get bus by 4-char label.

        Raises:
            KeyError: If label not found among active buses for this shift.
        """
        try:
            return self._buses[label]
        except KeyError:
            raise KeyError(
                f"Bus {label!r} not found in shift {self._shift_number} "
                f"(not active until shift {_topology_get_bus(label).active_from_shift})"
            )

    def get_line(self, label: str) -> Line:
        """
        Get line by label.

        Raises:
            KeyError: If label not found among active lines for this shift.
        """
        try:
            return self._lines[label]
        except KeyError:
            raise KeyError(
                f"Line {label!r} not found in shift {self._shift_number}"
            )

    def get_unit(self, label: str) -> GenerationUnit:
        """
        Get generation unit by label.

        Raises:
            KeyError: If label not found among active units for this shift.
        """
        try:
            return self._units[label]
        except KeyError:
            raise KeyError(
                f"Unit {label!r} not found in shift {self._shift_number}"
            )

    def get_units_at_bus(self, bus_label: str) -> list[GenerationUnit]:
        """All active units whose bus matches bus_label. Empty list if none."""
        return self._units_at_bus.get(bus_label, [])

    # ─────── DEMAND QUERY ─────────────────────────────────────────────────

    def get_load_at_bus(self, bus_label: str, sim_hour: float) -> float:
        """
        Return forecast demand in MW at a load substation for a given hour.

        Returns 0.0 for non-load buses (transmission buses with generation).
        Demand is the deterministic forecast — noise is added by the simulation.

        Args:
            bus_label: Bus label (e.g. 'LD01').
            sim_hour:  Current time of day in decimal hours.

        Returns:
            Forecast load in MW, or 0.0 if not a load bus.
        """
        bus = self._buses.get(bus_label)
        if bus is None or bus.bus_type != 'LOAD':
            return 0.0
        if bus_label not in LOAD_DISTRIBUTION:
            return 0.0
        from data.profiles import SHIFT_SPECS
        spec = SHIFT_SPECS.get(self._shift_number)
        if spec is None:
            return 0.0
        total_demand = get_demand_mw(sim_hour, spec.peak_demand_mw)
        return total_demand * LOAD_DISTRIBUTION[bus_label]

    # ─────── CANVAS POSITION QUERY ────────────────────────────────────────

    def get_canvas_position(self, label: str) -> tuple[int, int]:
        """
        Return (x, y) canvas position in native 1920×844 coordinates.

        Works for bus labels, station labels, and interconnector labels.

        Args:
            label: Bus label (e.g. 'MDBY'), station label (e.g. 'RVSD'),
                   or interconnector label (e.g. 'INTC-N').

        Returns:
            (x, y) tuple in native canvas pixels.

        Raises:
            KeyError: If label not found.
        """
        if label in self._buses:
            bus = self._buses[label]
            return (bus.canvas_x, bus.canvas_y)
        if label in STATION_POSITIONS:
            return STATION_POSITIONS[label]
        if label in INTERCONNECTOR_POSITIONS:
            return INTERCONNECTOR_POSITIONS[label]
        raise KeyError(f"Canvas position not found for label {label!r}")

    # ─────── MEMBERSHIP CHECKS ────────────────────────────────────────────

    def has_bus(self, label: str) -> bool:
        """True if bus is active in this shift."""
        return label in self._buses

    def has_line(self, label: str) -> bool:
        """True if line is active in this shift."""
        return label in self._lines

    def has_unit(self, label: str) -> bool:
        """True if unit is active in this shift."""
        return label in self._units

    def get_load_bus_labels(self) -> list[str]:
        """Return labels of all active 60kV load substations."""
        return [b.label for b in self._bus_list if b.bus_type == 'LOAD']

    def get_transmission_bus_labels(self) -> list[str]:
        """Return labels of all active transmission buses (non-load)."""
        return [b.label for b in self._bus_list if b.bus_type == 'TRANSMISSION']
