"""
src/gameplay/shifts/shift_05.py

Shift 5 scenario definition. GRID_SOURCE jumps to grid_medium — the first
shift on the full/medium grid, "the jump" per GRIDCOM_CAMPAIGN_BRAINSTORM.md's
Act I -> Act II transition.

USES_PLANNING = True: this is the first shift (chronologically) wired to
Phase 1 planning, per the persistent-campaign-budget work — a campaign
economy only means something once more than one shift spends against it,
so wiring this in was bundled with that feature rather than built later.
No INITIAL_SCHEDULE is declared — a USES_PLANNING shift's handover dispatch
always comes from the player's confirmed plan (see phase1.py's
_default_init_schedule()), never a shift-authored default.

Phase A minimal structure pass (see shift_01.py's docstring for the
pattern): HANDOVER_NOTES/WIN_CONDITIONS/FAIL_CONDITIONS added below so
BRIEFING -> PLANNING -> PLAYING -> DEBRIEF is fully playable end to end.
Full narrative content (the brainstorm's Part 1 "new assignment, full
board, everything is bigger than it looks on paper") is deferred to a
later authoring pass.
"""

from __future__ import annotations


GRID_SOURCE: str = 'grid_medium'

SHIFT_DATE: str = 'MON 09 JAN 1995'

DIFFICULTY_LABEL: str = 'Standard'

START_HOUR: float = 6.0

DURATION_HOURS: float = 4.0

USES_PLANNING: bool = True

HANDOVER_NOTES: tuple[str, ...] = (
    'New assignment. Full board. Everything is bigger than it looks on paper.',
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
