"""
src/gameplay/shifts/shift_07.py

Shift 7 scenario definition — Phase A minimal structure pass (see
shift_01.py's docstring for the pattern this follows, and shift_05.py's for
the USES_PLANNING variant). Same grid_medium grid as Shifts 5-6. No
INITIAL_SCHEDULE is declared — a USES_PLANNING shift's handover dispatch
always comes from the player's confirmed plan.

Full narrative content (the brainstorm's Part 1 "reactive power doesn't
forgive guesswork, neither do the substations") is deferred to a later
authoring pass.
"""

from __future__ import annotations


GRID_SOURCE: str = 'grid_medium'

SHIFT_DATE: str = 'TUE 14 FEB 1995'

DIFFICULTY_LABEL: str = 'Standard'

START_HOUR: float = 6.0

DURATION_HOURS: float = 4.0

USES_PLANNING: bool = True

HANDOVER_NOTES: tuple[str, ...] = (
    'Reactive power doesn\'t forgive guesswork. Neither do the substations.',
)

MAINTENANCE_UNITS: set[str] = set()

MAINTENANCE_LINES: set[str] = set()

AGC_ENABLED: bool = True

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
