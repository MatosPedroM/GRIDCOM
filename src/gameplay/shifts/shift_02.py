"""
src/gameplay/shifts/shift_02.py

Shift 2 scenario definition — two-unit manual dispatch tutorial.

Narrative:
  RIVE-1 (Riverside Coal Unit 1, 300 MW) and ASHC-1 (Ashcombe Hydro Unit 1,
  250 MW) are both on-line at handover. AGC is off — neither unit responds
  to demand automatically. Demand holds in a narrow band (~340-356 MW)
  through the 10:00-14:00 window and the player must manually track it,
  splitting the load between the two units however they see fit.

  Demand is derived at load time from GREY/OAKE's saved peak_load_mw in
  shift2.json (200 MW each, 400 MW combined) scaled by the campaign's shared
  DEMAND_PROFILE_NORMALISED curve (src/data/profiles.py) — not authored here.
  That curve's true daily peak (1.0, 400 MW) falls at 18:00, outside this
  shift's played window; across 10:00-14:00 it instead runs 348 -> 356 -> 352
  -> 344 -> 340 MW.

Grid: RIVE ──L01──► ASHC ──{L02,L03}──► GREY, ASHC ──{L04,L05}──► OAKE
      (4 buses, 5 lines)

GRID_SOURCE below points this shift at the hand-authored Grid Designer grid
(assets/designer_grids/shift2.json) instead of the campaign's topology.py/
fleet.py — see shift_10.py for the same pattern.
"""

from __future__ import annotations


GRID_SOURCE: str = 'shift2'

SHIFT_DATE: str = 'MON 07 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

START_HOUR: float = 10.0

DURATION_HOURS: float = 4.0

HANDOVER_NOTES: tuple[str, ...] = (
    'Mid-morning handover.',
    'Riverside Coal Unit 1 (RIVE-1) on-line at 150 MW.',
    'Ashcombe Hydro Unit 1 (ASHC-1) on-line at 200 MW.',
    'AGC off — manual dispatch only, on both units.',
    'Demand steady around 350 MW through the shift. Your task: keep both units tracking it.',
)

# Units on planned maintenance — visible on canvas but cannot be started.
MAINTENANCE_UNITS: set[str] = set()

AGC_ENABLED: bool = False

# Starting dispatch — units absent from this dict start OFFLINE.
INITIAL_SCHEDULE: dict[str, float] = {
    'RIVE-1': 150.0,   # Riverside Coal Unit 1 — 300 MW rated, 105 MW min
    'ASHC-1': 200.0,   # Ashcombe Hydro Unit 1  — 250 MW rated, 25 MW min
}


# ── Scripted events ────────────────────────────────────────────────────────────

SCRIPTED_EVENTS: list[dict] = [
    {
        'trigger_min': 0.0,
        'priority':    'TUTOR',
        'message':     'RIVE-1 and ASHC-1 on-line. AGC off — manual dispatch only.',
        'detail':      ('Riverside Coal Unit 1 (RIVE-1, 300 MW) and Ashcombe Hydro '
                        'Unit 1 (ASHC-1, 250 MW) are both on-line. AGC is off — '
                        'neither unit will respond to demand automatically. Monitor '
                        'frequency and adjust both units manually to track it.'),
        'element':     None,
        'condition':   None,
    },
    {
        'trigger_min': 30.0,
        'priority':    'TUTOR',
        'message':     'Demand steady near 350 MW. Two units, your call how to split it.',
        'detail':      ('Load holds in a narrow band through the shift rather than '
                        'ramping hard. ASHC-1 responds quickly; RIVE-1 responds more '
                        'slowly but has the larger reserve. Split the load between '
                        'them as you see fit — just keep total generation tracking it.'),
        'element':     None,
        'condition':   None,
    },
    {
        'trigger_min': 60.0,
        'priority':    'TUTOR',
        'message':     'Generation drifting from demand. Ramp RIVE-1 or ASHC-1 to correct.',
        'detail':      ('Load is holding near 350 MW but total dispatch has drifted '
                        'from its 350 MW handover level. Adjust RIVE-1 and/or ASHC-1 '
                        'output to close the gap and hold frequency nominal.'),
        'element':     None,
        'condition':   {'metric': 'UNIT_OUTPUT_MW_SUM', 'targets': ['RIVE-1', 'ASHC-1'],
                        'op': '<', 'value': 330.0},
    },
    {
        'trigger_min': 120.0,
        'priority':    'TUTOR',
        'message':     'Midday load near 350 MW. Confirm both units are tracking it.',
        'detail':      ('The shift is at its halfway point. Total generation should '
                        'be tracking close to system load by now. If either unit has '
                        'drifted from its handover output, ramp it back — demand '
                        'holds in this same band through to end of shift.'),
        'element':     None,
        'condition':   {'metric': 'UNIT_OUTPUT_MW_SUM', 'targets': ['RIVE-1', 'ASHC-1'],
                        'op': '<', 'value': 330.0},
    },
]
