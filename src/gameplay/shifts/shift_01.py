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
  mid-morning climb.

  As demand keeps climbing, ASHC-1 needs to cover load minus RIVE-1's fixed
  105 MW floor — with a realistic player tracking demand, it crosses 195 MW
  around T+105 (~08:15) and keeps rising toward its 250 MW ceiling by shift
  end (~242 MW at T+180). This is a real mechanical forcing function, not
  just a narrative cue, and lands in the back half of this shift's
  (deliberately shortened) window — the player finishes the shift managing
  both units together as demand keeps rising toward the late-morning peak.

  Demand is derived at load time from GREY/OAKE's saved peak_load_mw in
  shift2.json (200 MW each, 400 MW combined) scaled by the campaign's
  shared DEMAND_PROFILE_NORMALISED curve (src/data/profiles.py) — not
  authored here. Across this shift's 06:30-09:30 window that curve runs
  204 -> 232 -> 288 -> 328 -> 338 MW hour-by-hour, a single continuous ramp.
  START_HOUR was deliberately moved later (was 4.0/04:00) when the shift's
  DURATION_HOURS was halved (6.0 -> 3.0) — demand here is driven by
  real sim-hour-of-day, not shift-relative time, so simply halving the
  duration at the old 04:00 start would have left the shift entirely within
  the flattest part of the morning ramp and never actually forced ASHC-1
  past its single-unit capacity within the shorter window (confirmed via a
  headless trace before picking 06:30). All SCRIPTED_EVENTS trigger_min
  values are re-timed against this window, not simply halved from the old
  6-hour shift's timings, for the same reason.

  FREQ_TOLERANCE_MULT = 2.0 roughly doubles the alarm/crisis band from the
  default (see constants.py FREQ_TOLERANCE_MULT) — a first-time player
  needs more reaction room than the standard shifts allow. The G-key
  active-power nudge (select unit, G, Up/Down) is the fast path for
  splitting load between two units under time pressure; typing an exact
  MW value via digit keys + Enter still works identically.

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

START_HOUR: float = 6.5

DURATION_HOURS: float = 3.0

HANDOVER_NOTES: tuple[str, ...] = (
    'Morning handover from R. Ferris.',
    'Ashcombe Hydro Unit 1 (ASHC-1) on-line at 30 MW — the unit to watch.',
    'Riverside Coal Unit 1 (RIVE-1) on-line at its 105 MW minimum, idling — nothing to do there yet.',
    'AGC off, governor droop off — manual dispatch only.',
    'Demand climbing fast through the morning ramp — stay ahead of it.',
    'Your task: keep frequency nominal as demand rises. Ashcombe alone can carry it for now.',
    'Tip: select a unit, press G, then Up/Down to adjust its output (Ctrl for a bigger step).',
)

# Starting dispatch — units absent from this dict start OFFLINE.
INITIAL_SCHEDULE: dict[str, float] = {
    'ASHC-1': 103.0,     # Ashcombe Hydro Unit 1 — the unit the player actively works
    'RIVE-1': 105.0,    # Riverside Coal Unit 1 — idling at its technical minimum
}

# Units on planned maintenance — visible on canvas but cannot be started.
MAINTENANCE_UNITS: set[str] = set()

AGC_ENABLED: bool = False

DROOP_ENABLED: bool = False

# Roughly doubles the alarm/crisis band (~+-0.4 Hz alert, +-1.0 Hz critical
# instead of the default +-0.2/+-0.5 Hz) — a first-time player needs more
# room to react manually than the standard shifts allow. F_MIN/F_MAX (the
# hard 45/55 Hz clamp) are not affected by this multiplier.
FREQ_TOLERANCE_MULT: float = 2.0

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
        'trigger_min': 2.5,
        'priority':    'TUTOR',
        'message':     'To adjust ASHC-1: select it, press G, then Up/Down.',
        'detail':      ('Tab selects a unit (or click it on the canvas). With ASHC-1 '
                        'selected, press G to arm output adjust, then Up raises its '
                        'target output, Down lowers it — hold Ctrl for a bigger 5x '
                        'step. You can also type an exact MW number: press Enter, '
                        'type the digits, press Enter again to commit.'),
        'element':     'ASHC-1',
        'condition':   None,
    },
    {
        'trigger_min': 30.0,
        'priority':    'TUTOR',
        'message':     'Demand is rising. Raise ASHC-1 output to hold frequency.',
        'detail':      ('Load is climbing through the morning ramp. If frequency '
                        'has started drifting low, increase ASHC-1\'s target output '
                        '— hydro responds almost immediately.'),
        'element':     'ASHC-1',
        'condition':   {'metric': 'FREQUENCY_HZ', 'op': '<', 'value': 49.9},
    },
    {
        'trigger_min': 60.0,
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
        'trigger_min': 80.0,
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
        'trigger_min': 90.0,
        'priority':    'TUTOR',
        'message':     'To bring Riverside up: Tab to select RIVE-1, press G, hold Up.',
        'detail':      ('Press Tab until RIVE-1 is selected (or click it on the '
                        'canvas), press G to arm output adjust, then hold Up to '
                        'raise its target — Ctrl+Up steps faster. RIVE-1 is coal and '
                        'ramps slowly, so raise it gradually and keep watching '
                        'ASHC-1 and frequency at the same time.'),
        'element':     'RIVE-1',
        'condition':   {'metric': 'UNIT_OUTPUT_MW', 'target': 'ASHC-1',
                        'op': '>', 'value': 195.0},
    },
    {
        'trigger_min': 105.0,
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
        'trigger_min': 110.0,
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
        'trigger_min': 165.0,
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
