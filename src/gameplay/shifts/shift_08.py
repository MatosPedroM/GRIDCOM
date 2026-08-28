"""
src/gameplay/shifts/shift_08.py

Shift 8 scenario definition — Phase A minimal structure pass (see
shift_01.py's docstring for the pattern this follows, and shift_05.py's for
the USES_PLANNING variant). GRID_SOURCE jumps to grid_large — "the second
jump" per GRIDCOM_CAMPAIGN_BRAINSTORM.md's Act II -> Act III transition
(fixes the old dead grid_big reference; grid_big.json never existed on
disk). No INITIAL_SCHEDULE is declared — a USES_PLANNING shift's handover
dispatch always comes from the player's confirmed plan.

Full narrative content (the brainstorm's Part 1 "second promotion, the
interconnectors are yours now too") is deferred to a later authoring pass.
"""

from __future__ import annotations


GRID_SOURCE: str = 'grid_large'

SHIFT_DATE: str = 'MON 13 MAR 1995'

DIFFICULTY_LABEL: str = 'Advanced'

START_HOUR: float = 6.0

DURATION_HOURS: float = 5.0

USES_PLANNING: bool = True

HANDOVER_NOTES: tuple[str, ...] = (
    'Second promotion. The interconnectors are yours now too.',
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
