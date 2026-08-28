"""
src/gameplay/shifts/shift_03.py

Shift 3 scenario definition — Phase A minimal structure pass (see
shift_01.py's docstring for the pattern this follows). Same grid_small
fleet/handover balance as Shifts 1-2; full narrative content (the
brainstorm's Part 1 frames this as "three weeks in, first real contingency
you'll call yourself" — an N-1 lesson) is deferred to a later authoring
pass.

Previously a placeholder noting its old integration-capstone content had
merged into shift_01.py — that history no longer applies now that every
shift in Act I gets its own real (if minimal) win/fail-condition structure.
"""

from __future__ import annotations


GRID_SOURCE: str = 'grid_small'

SHIFT_DATE: str = 'MON 28 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

START_HOUR: float = 22.0

DURATION_HOURS: float = 6.0

HANDOVER_NOTES: tuple[str, ...] = (
    'Three weeks in. First real contingency you\'ll call yourself.',
)

INITIAL_SCHEDULE: dict[str, float] = {
    'OAKE-1': 35.0,
    'OAKE-2': 35.0,
    'RIVE-1': 215.0,
}

MAINTENANCE_UNITS: set[str] = {'RIVE-2', 'RIVE-3'}

MAINTENANCE_LINES: set[str] = set()

AGC_ENABLED: bool = False

SCRIPTED_EVENTS: list[dict] = []

WIN_CONDITIONS: list[dict] = [
    {'metric': 'FREQUENCY_HZ', 'op': '>=', 'value': 49.2},
    {'metric': 'FREQUENCY_HZ', 'op': '<=', 'value': 50.8},
]

FAIL_CONDITIONS: list[dict] = [
    {'metric': 'FREQUENCY_HZ', 'op': '<', 'value': 47.5, 'sustained_s': 10.0,
     'message': 'Frequency collapse — protective systems isolated the network.'},
    {'metric': 'FREQUENCY_HZ', 'op': '>', 'value': 52.5, 'sustained_s': 10.0,
     'message': 'Over-frequency — protective systems isolated the network.'},
]
