"""
src/gameplay/shifts/shift_01.py

Shift 1 scenario definition — Phase A minimal structure pass (see
STAGE_STATUS.md / GRIDCOM_CAMPAIGN_BRAINSTORM.md). Gives the shift a real,
balanced handover and win/fail conditions so BRIEFING -> PLAYING -> DEBRIEF
is fully playable end to end; full narrative content (handover-notes prose,
scripted events) is deferred to a later authoring pass per the brainstorm's
Part 3 sequencing — this file intentionally does not yet build the "First
night alone" tutorial arc described there.

Previously reverted to a stub because its old voltage/AVR content
(INITIAL_VOLTAGE_SETPOINTS, the Holt Hydro AVR-setpoint lesson) depended on
generator voltage control being an AVR setpoint; that's now direct-Q
(W = MW, Q = MVAr), so that content no longer applies and is not restored
here.

INITIAL_SCHEDULE follows the brainstorm's Act I framing (Part 1: "RIVE-1
and two Oakendale hydro units are the whole world... two out-of-service
Riverside units (RVSD-2/3 easter egg territory)") — RIVE-2/RIVE-3 start on
MAINTENANCE_UNITS, RIVE-1 plus both OAKE hydro units cover the shift's
~277 MW handover demand (grid_small.json peak 375 MW x profile[22:00]
0.740, plus headroom for line/demand losses).
"""

from __future__ import annotations


GRID_SOURCE: str = 'grid_small'

SHIFT_DATE: str = 'MON 07 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

START_HOUR: float = 22.0

DURATION_HOURS: float = 6.0

HANDOVER_NOTES: tuple[str, ...] = (
    'First night alone. Commenced watch.',
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
