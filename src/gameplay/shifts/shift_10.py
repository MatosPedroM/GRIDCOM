"""
src/gameplay/shifts/shift_10.py

Shift 10 scenario definition — Phase A minimal structure pass (see
shift_01.py's docstring for the pattern this follows, and shift_05.py's for
the USES_PLANNING variant).

This replaces the previous "The Cold Snap" content wholesale. That version
was authored against a grid_big.json that never existed on disk (GRID_SOURCE
pointed at a dead reference — Shifts 8/9/10 were all unplayable) and its
station/bus names (Stourbrook, Welbeck, Hartwell, PORT/TRUS/CARR/SEDG/WREK/
MILL) do not exist in grid_large.json, the grid GRID_SOURCE now correctly
points at (its anchors are CLOV nuclear, RIVE coal, DOWN CCGT; its five
INDUSTRIAL buses are BATH/APPL/SOUT/LAMB/MOSS) — reducing to a placeholder
here rather than patching individual label references, per developer
decision (2026-08-28), since the mismatch was total, not cosmetic.

A full Act III finale rebuild against grid_large.json's real topology and
GRIDCOM_CAMPAIGN_BRAINSTORM.md's narrative (Part 1: "everything you already
know, all at once, without enough time to think about each thing
individually," ideally a full three-channel Heatwave or full-intensity
High-Wind Storm Weather Regime per Part 2.5) is the first sub-task of the
later content-authoring pass — see STAGE_STATUS.md. No INITIAL_SCHEDULE is
declared here — a USES_PLANNING shift's handover dispatch always comes from
the player's confirmed plan.
"""

from __future__ import annotations


GRID_SOURCE: str = 'grid_large'

SHIFT_DATE: str = 'THU 8 FEB 1996'

DIFFICULTY_LABEL: str = 'Extreme'

START_HOUR: float = 5.0

DURATION_HOURS: float = 5.5

USES_PLANNING: bool = True

HANDOVER_NOTES: tuple[str, ...] = (
    'Storm inbound. Everything you know. All at once.',
)

MAINTENANCE_UNITS: set[str] = set()

MAINTENANCE_LINES: set[str] = set()

AGC_ENABLED: bool = True

# Halved response speed carried over from the previous authoring pass —
# still a defensible Act III-finale value (AGC alone should not be able to
# cover a real deficit unassisted) even though the rest of that pass's
# content is gone. AGC eligibility itself (CCGT + HYDRO) is fixed
# campaign-wide, not a per-shift setting — see AGC_ELIGIBLE_TYPES in
# constants.py.
AGC_SPEED_MULT: float = 0.5

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
