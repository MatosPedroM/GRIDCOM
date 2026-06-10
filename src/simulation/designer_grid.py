"""
src/simulation/designer_grid.py

DesignerGrid: a Grid-compatible adapter built from DesignerBus/Line/Unit lists.

Satisfies the same public interface as Grid (grid.py) so that GridSimulation
can run against a designer-built topology without touching topology.py or
fleet.py at all.

Used exclusively by the DESIGNER_TEST game state in main.py.
"""

from __future__ import annotations

import dataclasses

from data.topology import Bus, Line
from data.fleet import GenerationUnit
from data.designer_io import DesignerBus, DesignerLine, DesignerUnit


class DesignerGrid:
    """
    Grid-compatible adapter constructed from designer dataclass lists.

    get_load_at_bus() returns a flat 50% of peak_load_mw for all hours —
    this gives generation headroom from the start of a test session.

    shift_number returns 0 as a sentinel (not a real shift).
    slack_bus returns the label of the first bus marked is_slack, or the
    first bus in the list if none are marked.
    """

    def __init__(
        self,
        d_buses: list[DesignerBus],
        d_lines: list[DesignerLine],
        d_units: list[DesignerUnit],
    ) -> None:
        buses = [_to_bus(b) for b in d_buses]
        lines = [_to_line(l) for l in d_lines]
        units = [_to_unit(u) for u in d_units]

        self._bus_list:  list[Bus]              = buses
        self._line_list: list[Line]             = lines
        self._unit_list: list[GenerationUnit]   = units

        self._buses: dict[str, Bus]             = {b.label: b for b in buses}
        self._lines: dict[str, Line]            = {l.label: l for l in lines}
        self._units: dict[str, GenerationUnit]  = {u.label: u for u in units}

        # Bus → unit index
        self._units_at_bus: dict[str, list[GenerationUnit]] = {}
        for unit in units:
            self._units_at_bus.setdefault(unit.bus_label, []).append(unit)

        # Load values (flat 50% for the test session)
        self._load_mw: dict[str, float] = {
            b.label: b.peak_load_mw * 0.5
            for b in d_buses
            if b.bus_type == 'LOAD'
        }

        # Station canvas positions (bus position used as fallback for station)
        self._station_positions: dict[str, tuple[int, int]] = {}
        for b in d_buses:
            self._station_positions[b.label] = (b.canvas_x, b.canvas_y)

        # Slack bus label
        slack_candidates = [b for b in d_buses if b.is_slack]
        self._slack_bus: str = (
            slack_candidates[0].label if slack_candidates
            else (d_buses[0].label if d_buses else 'MDBY')
        )

    # ─────── PROPERTIES ──────────────────────────────────────────────────────

    @property
    def slack_bus(self) -> str:
        return self._slack_bus

    @property
    def shift_number(self) -> int:
        return 0  # sentinel — not a real shift

    # ─────── ACTIVE ELEMENT QUERIES ──────────────────────────────────────────

    def get_active_buses(self) -> list[Bus]:
        return self._bus_list

    def get_active_lines(self) -> list[Line]:
        return self._line_list

    def get_active_units(self) -> list[GenerationUnit]:
        return self._unit_list

    # ─────── ELEMENT LOOKUPS ─────────────────────────────────────────────────

    def get_bus(self, label: str) -> Bus:
        try:
            return self._buses[label]
        except KeyError:
            raise KeyError(f"Bus {label!r} not found in designer grid")

    def get_line(self, label: str) -> Line:
        try:
            return self._lines[label]
        except KeyError:
            raise KeyError(f"Line {label!r} not found in designer grid")

    def get_unit(self, label: str) -> GenerationUnit:
        try:
            return self._units[label]
        except KeyError:
            raise KeyError(f"Unit {label!r} not found in designer grid")

    def get_units_at_bus(self, bus_label: str) -> list[GenerationUnit]:
        return self._units_at_bus.get(bus_label, [])

    # ─────── DEMAND QUERY ────────────────────────────────────────────────────

    def get_load_at_bus(self, bus_label: str, sim_hour: float) -> float:
        """Return flat 50% peak load for LOAD buses; 0 for transmission buses."""
        return self._load_mw.get(bus_label, 0.0)

    # ─────── CANVAS POSITION QUERY ───────────────────────────────────────────

    def get_canvas_position(self, label: str) -> tuple[int, int]:
        if label in self._buses:
            bus = self._buses[label]
            return (bus.canvas_x, bus.canvas_y)
        if label in self._station_positions:
            return self._station_positions[label]
        raise KeyError(f"Canvas position not found for label {label!r}")

    # ─────── MEMBERSHIP CHECKS ───────────────────────────────────────────────

    def has_bus(self, label: str) -> bool:
        return label in self._buses

    def has_line(self, label: str) -> bool:
        return label in self._lines

    def has_unit(self, label: str) -> bool:
        return label in self._units

    def get_load_bus_labels(self) -> list[str]:
        return [b.label for b in self._bus_list if b.bus_type == 'LOAD']

    def get_transmission_bus_labels(self) -> list[str]:
        return [b.label for b in self._bus_list if b.bus_type == 'TRANSMISSION']


# ─────────────────────────────────────────────────────────────────────────────
# CONVERSION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _to_bus(b: DesignerBus) -> Bus:
    return Bus(
        label=b.label,
        name=b.name,
        voltage_kv=b.voltage_kv,
        bus_type=b.bus_type,
        canvas_x=b.canvas_x,
        canvas_y=b.canvas_y,
        active_from_shift=1,
        is_slack=b.is_slack,
    )


def _to_line(l: DesignerLine) -> Line:
    return Line(
        label=l.label,
        from_bus=l.from_bus,
        to_bus=l.to_bus,
        reactance_pu=l.reactance_pu,
        rating_mw=l.rating_mw,
        active_from_shift=1,
        active_until_shift=99,
        voltage_kv=l.voltage_kv,
    )


def _to_unit(u: DesignerUnit) -> GenerationUnit:
    return GenerationUnit(
        label=u.label,
        station_label=u.station_label,
        bus_label=u.bus_label,
        unit_type=u.unit_type,
        rated_mw=u.rated_mw,
        min_mw=u.min_mw,
        ramp_pct_per_min=u.ramp_pct_per_min,
        inertia_h=u.inertia_h,
        cold_start_min=u.cold_start_min,
        q_max_mvar=u.q_max_mvar,
        q_min_mvar=u.q_min_mvar,
        can_pump=u.can_pump,
        active_from_shift=1,
        description=u.description,
    )
