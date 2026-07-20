"""
src/gameplay/shifts/shift_02.py

Shift 2 scenario definition — two-unit manual dispatch tutorial.

Narrative:
  RIVE-1 (Riverside Coal Unit 1, 300 MW) and ASHC-1 (Ashcombe Hydro Unit 1,
  250 MW) are both on-line at handover. AGC is off — neither unit responds
  to demand automatically. Demand rises steadily through the shift and the
  player must manually raise both units' output to keep pace, splitting the
  rise between them however they see fit.

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

HANDOVER_NOTES: tuple[str, ...] = (
    'Mid-morning handover.',
    'Riverside Coal Unit 1 (RIVE-1) on-line at 120 MW.',
    'Ashcombe Hydro Unit 1 (ASHC-1) on-line at 160 MW.',
    'AGC off — manual dispatch only, on both units.',
    'Demand rising through the shift. Your task: keep both units tracking it.',
)

# Units on planned maintenance — visible on canvas but cannot be started.
MAINTENANCE_UNITS: set[str] = set()

AGC_ENABLED: bool = False

# Per-bus hourly load table (MW). Shift 2: GREY + OAKE, 400 MW combined peak.
# Full 24h table required by DemandModel/get_profile_value (interpolates across
# the whole day even though the shift itself only plays 10:00-14:00). Shaped like
# the old shift's full-day curve (which also rises 10:00-14:00), rescaled 400/315
# to the new grid's 400 MW combined peak, with the 10:00-14:00 window forced to
# exact values matching the SCRIPTED_EVENTS thresholds below: combined load
# 273 -> 311 -> 340 -> 371 -> 400 MW. Split evenly 50/50 GREY/OAKE (both buses
# share an identical 200 MW peak_load_mw in shift2.json).
SUBSTATION_LOAD_MW: dict[str, dict[float, float]] = {
    'GREY': {
         0.0: 63.5,  1.0: 60.3,  2.0: 57.15, 3.0: 55.85, 4.0: 57.15,
         5.0: 62.2,  6.0: 76.2,  7.0: 98.4,  8.0:117.45, 9.0:133.35,
        10.0:136.5, 11.0:155.5, 12.0:170.0, 13.0:185.5, 14.0:200.0,
        15.0:198.1, 16.0:193.65,17.0:189.2, 18.0:184.15,19.0:176.5,
        20.0:166.35,21.0:151.1, 22.0:132.05,23.0:104.75,24.0: 77.45,
    },
    'OAKE': {
         0.0: 63.5,  1.0: 60.3,  2.0: 57.15, 3.0: 55.85, 4.0: 57.15,
         5.0: 62.2,  6.0: 76.2,  7.0: 98.4,  8.0:117.45, 9.0:133.35,
        10.0:136.5, 11.0:155.5, 12.0:170.0, 13.0:185.5, 14.0:200.0,
        15.0:198.1, 16.0:193.65,17.0:189.2, 18.0:184.15,19.0:176.5,
        20.0:166.35,21.0:151.1, 22.0:132.05,23.0:104.75,24.0: 77.45,
    },
}

# Starting dispatch — units absent from this dict start OFFLINE.
INITIAL_SCHEDULE: dict[str, float] = {
    'RIVE-1': 120.0,   # Riverside Coal Unit 1 — 300 MW rated, 105 MW min
    'ASHC-1': 160.0,   # Ashcombe Hydro Unit 1  — 250 MW rated, 25 MW min
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
                        'frequency and adjust both units manually as load rises.'),
        'element':     None,
        'condition':   None,
    },
    {
        'trigger_min': 30.0,
        'priority':    'TUTOR',
        'message':     'Demand rising. Two units, your call how to split the load.',
        'detail':      ('Load is climbing steadily through the shift. ASHC-1 responds '
                        'quickly; RIVE-1 responds more slowly but has the larger '
                        'reserve. Split the rise between them as you see fit — just '
                        'keep total generation tracking load.'),
        'element':     None,
        'condition':   None,
    },
    {
        'trigger_min': 60.0,
        'priority':    'TUTOR',
        'message':     'Generation lagging demand. Ramp RIVE-1 or ASHC-1 to keep up.',
        'detail':      ('Load has risen toward 310 MW but total dispatch is still '
                        'near its 280 MW handover level. Increase RIVE-1 and/or '
                        'ASHC-1 output to close the gap and hold frequency nominal.'),
        'element':     None,
        'condition':   {'metric': 'UNIT_OUTPUT_MW_SUM', 'targets': ['RIVE-1', 'ASHC-1'],
                        'op': '<', 'value': 290.0},
    },
    {
        'trigger_min': 120.0,
        'priority':    'TUTOR',
        'message':     'Midday load near 340 MW. Confirm both units are tracking it.',
        'detail':      ('The shift is at its halfway point. Total generation should '
                        'be tracking close to system load by now. If either unit is '
                        'still near its handover output, ramp it before the final '
                        'push toward the 400 MW peak at end of shift.'),
        'element':     None,
        'condition':   {'metric': 'UNIT_OUTPUT_MW_SUM', 'targets': ['RIVE-1', 'ASHC-1'],
                        'op': '<', 'value': 320.0},
    },
]
