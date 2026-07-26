"""
src/gameplay/shifts/shift_01.py

Shift 1 scenario definition — manual dispatch tutorial (single unit, then two).

Narrative:
  ASHC-1 (Ashcombe Hydro Unit 1, 250 MW) is the unit to watch at handover,
  feeding Greymoor substation. RIVE-1 (Riverside Coal Unit 1, 300 MW) is
  already synchronised in the background at its 105 MW technical minimum —
  nothing to do there yet. AGC and governor droop are both off — the player
  observes basic frequency and load behaviour and must manually correct
  ASHC-1's output to hold frequency nominal as demand ramps through the
  pre-dawn trough.

  As demand keeps climbing, ASHC-1 needs to cover load minus RIVE-1's fixed
  105 MW floor — it crosses 200 MW around T+254 (~08:14) and keeps rising
  toward its 250 MW ceiling by shift end. This is a real mechanical forcing
  function, not just a narrative cue, but it lands late in this shift's
  demand curve (RIVE-1's 105 MW minimum plus a 400 MW peak means the
  two-unit phase is necessarily a last-90-minutes affair, not a mid-shift
  one) — the player finishes the shift managing both units together as
  demand keeps rising toward the mid-morning peak.

  Demand is derived at load time from GREY/OAKE's saved peak_load_mw in
  shift2.json (200 MW each, 400 MW combined) scaled by the campaign's
  shared DEMAND_PROFILE_NORMALISED curve (src/data/profiles.py) — not
  authored here. Across this shift's 04:00-10:00 window that curve runs
  128 -> 140 -> 176 -> 232 -> 288 -> 328 -> 348 MW hour-by-hour, a single
  continuous ramp rather than two separately-shaped windows.

Grid: RIVE ──L01──► ASHC ──{L02,L03}──► GREY, ASHC ──{L04,L05}──► OAKE
      (4 buses, 5 lines)

GRID_SOURCE below points this shift at the hand-authored Grid Designer grid
(assets/designer_grids/shift2.json) instead of the campaign's topology.py/
fleet.py — see shift_10.py for the same pattern. shift2.json is used
rather than the smaller shift1.json (which this shift used before it
absorbed the former Shift 2's two-unit lesson) since it's a strict
superset — RIVE-1 and the OAKE load bus are simply idle/quiet during the
opening single-unit phase.
"""

from __future__ import annotations


GRID_SOURCE: str = 'shift2'

SHIFT_DATE: str = 'MON 07 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

START_HOUR: float = 4.0

DURATION_HOURS: float = 6.0

HANDOVER_NOTES: tuple[str, ...] = (
    'Night handover from R. Ferris.',
    'Ashcombe Hydro Unit 1 (ASHC-1) on-line at 30 MW — the unit to watch.',
    'Riverside Coal Unit 1 (RIVE-1) on-line at its 105 MW minimum, idling — nothing to do there yet.',
    'AGC off, governor droop off — manual dispatch only.',
    'Demand very low — pre-dawn trough, a long morning ramp ahead.',
    'Your task: keep frequency nominal as demand rises. Ashcombe alone can carry it for now.',
)

# Starting dispatch — units absent from this dict start OFFLINE.
INITIAL_SCHEDULE: dict[str, float] = {
    'ASHC-1': 30.0,     # Ashcombe Hydro Unit 1 — the unit the player actively works
    'RIVE-1': 105.0,    # Riverside Coal Unit 1 — idling at its technical minimum
}

# Units on planned maintenance — visible on canvas but cannot be started.
MAINTENANCE_UNITS: set[str] = set()

AGC_ENABLED: bool = False

DROOP_ENABLED: bool = False

SCRIPTED_EVENTS: list[dict] = [
    {
        'trigger_min': 0.0,
        'priority':    'TUTOR',
        'message':     'ASHC-1 on-line at 30 MW. AGC and droop off — you are in manual control.',
        'detail':      ('Ashcombe Hydro Unit 1 is the unit to watch. AGC is off and '
                        'governor droop is off, so its output never changes unless '
                        'you change it. Watch the frequency indicator — it drifts '
                        'below 50 Hz when generation falls behind demand, and above '
                        'when it exceeds it. Riverside Coal Unit 1 (RIVE-1) is also '
                        'on-line in the background at its 105 MW minimum — nothing '
                        'to do there yet.'),
        'element':     'ASHC-1',
        'condition':   None,
    },
    {
        'trigger_min': 60.0,
        'priority':    'TUTOR',
        'message':     'Demand is rising. Raise ASHC-1 output to hold frequency.',
        'detail':      ('Load is climbing through the pre-dawn ramp. If frequency '
                        'has started drifting low, increase ASHC-1\'s target output '
                        '— hydro responds almost immediately.'),
        'element':     'ASHC-1',
        'condition':   {'metric': 'FREQUENCY_HZ', 'op': '<', 'value': 49.9},
    },
    {
        'trigger_min': 120.0,
        'priority':    'TUTOR',
        'message':     'Morning ramp continuing. Keep ASHC-1 tracking demand.',
        'detail':      ('Demand keeps climbing. Keep an eye on both frequency and '
                        'ASHC-1\'s output — small, steady adjustments are easier to '
                        'manage than large corrections.'),
        'element':     'ASHC-1',
        'condition':   {'metric': 'UNIT_OUTPUT_MW', 'target': 'ASHC-1',
                        'op': '<', 'value': 33.0},
    },
    {
        'trigger_min': 250.0,
        'priority':    'WARNING',
        'message':     'Ashcombe nearing its ceiling. Bring Riverside up to help.',
        'detail':      ('ASHC-1 is approaching its 250 MW rated output as demand '
                        'keeps climbing. It cannot carry the rest of the morning '
                        'ramp alone — raise RIVE-1 off its 105 MW minimum to take '
                        'some of the load. RIVE-1 responds more slowly than '
                        'Ashcombe\'s hydro, so start early.'),
        'element':     'RIVE-1',
        'condition':   {'metric': 'UNIT_OUTPUT_MW', 'target': 'ASHC-1',
                        'op': '>', 'value': 195.0},
    },
    {
        'trigger_min': 285.0,
        'priority':    'WARNING',
        'message':     'Ashcombe nearing its ceiling. Bring Riverside up to help.',
        'detail':      ('ASHC-1 is approaching its 250 MW rated output as demand '
                        'keeps climbing. It cannot carry the rest of the morning '
                        'ramp alone — raise RIVE-1 off its 105 MW minimum to take '
                        'some of the load. RIVE-1 responds more slowly than '
                        'Ashcombe\'s hydro, so start early.'),
        'element':     'RIVE-1',
        'condition':   {'metric': 'UNIT_OUTPUT_MW', 'target': 'ASHC-1',
                        'op': '>', 'value': 195.0},
    },
    {
        'trigger_min': 290.0,
        'priority':    'TUTOR',
        'message':     'Two units now. Split the load between Ashcombe and Riverside.',
        'detail':      ('Demand keeps rising toward the mid-morning peak. You now '
                        'have two units to balance — Ashcombe responds quickly, '
                        'Riverside has the larger reserve but ramps more slowly. '
                        'Keep both tracking the total as it climbs.'),
        'element':     None,
        'condition':   None,
    },
    {
        'trigger_min': 340.0,
        'priority':    'TUTOR',
        'message':     'Approaching handover. Confirm both units are tracking demand.',
        'detail':      ('The shift is nearly over. If either unit has drifted from '
                        'demand, ramp it back — total generation should be tracking '
                        'close to system load by end of shift.'),
        'element':     None,
        'condition':   {'metric': 'UNIT_OUTPUT_MW_SUM', 'targets': ['RIVE-1', 'ASHC-1'],
                        'op': '<', 'value': 330.0},
    },
]
