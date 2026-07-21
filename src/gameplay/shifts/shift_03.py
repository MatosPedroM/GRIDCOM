"""
src/gameplay/shifts/shift_03.py

Shift 3 scenario definition — "Reserve": AGC and regulation margin.

Narrative:
  RIVE now runs two coal units. RIVE-1 sits at technical minimum (105 MW) —
  deliberately under-dispatched, held as reserve. RIVE-2 carries the bulk of
  RIVE's normal output. ASHC-1 (fast hydro) sits low, near its own minimum —
  the grid's regulation "shock absorber," with maximal headroom deliberately
  available. AGC is on for the first time this shift.

  A new branch off RIVE (SUTT -> RAVE, mirroring the GREY/OAKE redundant-pair
  pattern) raises total system demand to a 500 MW combined peak across three
  load buses (GREY 150 MW, OAKE 200 MW, RAVE 150 MW — each bus's saved peak
  from assets/designer_grids/shift3.json), so that if RIVE-1 is left parked
  at minimum, ASHC-1 alone cannot cover a generation shortfall on top of the
  demand ramp.

  Mid-shift, RIVE-2 develops a cooling problem and permanently derates to its
  own 105 MW minimum. AGC reacts by driving ASHC-1 upward to cover the
  shortfall — correctly doing its job, but silently consuming ASHC's
  headroom with no awareness of how much is left. If the player does
  nothing, ASHC-1 is driven toward and past its 250 MW ceiling as demand
  keeps climbing, and frequency genuinely degrades. The fix is to raise
  RIVE-1 off its minimum — the reserve that was there the whole time — which
  lets AGC relax ASHC-1 back down and restores real regulation headroom.

  Demand is derived at load time from GREY/OAKE/RAVE's saved peak_load_mw in
  shift3.json (500 MW combined) scaled by the campaign's shared
  DEMAND_PROFILE_NORMALISED curve (src/data/profiles.py) — not authored here.
  Across this shift's 14:00-18:00 played window that curve runs 425 -> 435 ->
  455 -> 480 -> 500 MW.

  NOTE: INITIAL_SCHEDULE dispatches 545 MW (105+300+140) against a 14:00
  demand checkpoint of 425 MW — a ~120 MW oversupply at shift start,
  narrowing as demand climbs toward the 500 MW end-of-shift peak. Not
  rebalanced here; flagged for a separate gameplay-balance pass.

Teaching goal: AGC corrects deviation in real time but has no concept of
"running low" — a dispatcher must watch where reserve is going and fix root
causes, not just watch a frequency number that currently looks fine.

Grid: RIVE (slack) --L01--> ASHC --{L02,L03}--> GREY, ASHC --{L04,L05}--> OAKE,
      RIVE --L06--> SUTT --{L07,L08}--> RAVE
      (6 buses, 8 lines, 3 units: RIVE-1, RIVE-2, ASHC-1)

GRID_SOURCE below points this shift at the hand-authored Grid Designer grid
(assets/designer_grids/shift3.json) instead of the campaign's topology.py/
fleet.py — see shift_02.py / shift_10.py for the same pattern.
"""

from __future__ import annotations


GRID_SOURCE: str = 'shift3'

SHIFT_DATE: str = 'TUE 08 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

START_HOUR: float = 14.0

DURATION_HOURS: float = 4.0

HANDOVER_NOTES: tuple[str, ...] = (
    'Mid-morning handover.',
    'Riverside now runs two units. RIVE-1 on-line at 105 MW (technical minimum — held in reserve).',
    'RIVE-2 on-line at 165 MW — carrying the bulk of Riverside output.',
    'Ashcombe Hydro Unit 1 (ASHC-1) on-line at 140 MW.',
    'AGC on for the first time — small deviations correct automatically.',
    'Demand rising through the shift across Greymoor, Oakendale, and Ravensmere.',
)

# Units on planned maintenance — visible on canvas but cannot be started.
MAINTENANCE_UNITS: set[str] = set()

AGC_ENABLED: bool = True

# Starting dispatch — units absent from this dict start OFFLINE.
# Total 545 MW (105+300+140) — see NOTE in the module docstring re: oversupply
# vs the 14:00 combined-load checkpoint (425 MW).
INITIAL_SCHEDULE: dict[str, float] = {
    'RIVE-1': 105.0,   # Riverside Coal Unit 1 — 300 MW rated, 105 MW min — the reserve
    'RIVE-2': 300.0,   # Riverside Coal Unit 2 — 300 MW rated, 105 MW min — the workhorse
    'ASHC-1': 140.0,   # Ashcombe Hydro Unit 1  — 250 MW rated, 25 MW min — the shock absorber
}


# ── Conditions (declarative — see src/data/shift_io.py for the schema) ────────

_ASHC1_ABOVE_200MW: dict = {
    'metric': 'UNIT_OUTPUT_MW', 'target': 'ASHC-1', 'op': '>', 'value': 200.0,
}
_RIVE1_STILL_AT_MIN: dict = {
    'metric': 'UNIT_OUTPUT_MW', 'target': 'RIVE-1', 'op': '<', 'value': 115.0,
}
_ASHC1_RECOVERED: dict = {
    'metric': 'UNIT_OUTPUT_MW', 'target': 'ASHC-1', 'op': '<=', 'value': 160.0,
}


# ── Scripted events ────────────────────────────────────────────────────────────

SCRIPTED_EVENTS: list[dict] = [
    {
        'trigger_min': 0.0,
        'priority':    'TUTOR',
        'message':     'RIVE-1, RIVE-2 and ASHC-1 on-line. AGC on for the first time.',
        'detail':      ('AGC is now active — it will automatically nudge fast-response '
                        'units (like ASHC-1) to correct small frequency deviations. '
                        'RIVE-1 is deliberately parked at its 105 MW technical minimum '
                        '— that is your reserve. Watch where AGC draws from, not just '
                        'the frequency number.'),
        'element':     None,
        'condition':   None,
    },
    {
        'trigger_min': 30.0,
        'priority':    'TUTOR',
        'message':     'Demand rising across three load centres.',
        'detail':      ('Greymoor, Oakendale and Ravensmere are all climbing. AGC will '
                        'track small deviations on ASHC-1 automatically — you should '
                        'still expect to ramp RIVE-2 yourself as the base load rises.'),
        'element':     None,
        'condition':   None,
    },
    {
        'trigger_min': 60.0,
        'priority':    'WARNING',
        'message':     'RIVE-2: cooling fault. Output derated to 105 MW.',
        'detail':      ('RIVE-2 has developed a cooling problem and its output has been '
                        'capped at 105 MW for the rest of the shift — a real, permanent '
                        'loss of ~60 MW from Riverside. AGC will pick up the shortfall '
                        'automatically via ASHC-1. That is not a fix — it is borrowing '
                        'from your regulation reserve.'),
        'element':     'RIVE-2',
        'condition':   None,
        'action':      {'type': 'UNIT_DERATE', 'unit': 'RIVE-2', 'cap_mw': 105.0},
    },
    {
        'trigger_min': 90.0,
        'priority':    'TUTOR',
        'message':     'ASHC-1 climbing toward its ceiling. RIVE-1 is still at minimum.',
        'detail':      ('AGC has been raising ASHC-1 to cover both the RIVE-2 shortfall '
                        'and the ongoing demand ramp. ASHC-1 has only 250 MW rated — if '
                        'it is driven to its ceiling, there is no reserve left for '
                        'anything else. RIVE-1 is still sitting at its 105 MW minimum. '
                        'Raise RIVE-1 to take the permanent load off ASHC-1 and restore '
                        'real headroom.'),
        'element':     'ASHC-1',
        'condition':   _ASHC1_ABOVE_200MW,
    },
    {
        'trigger_min': 120.0,
        'priority':    'WARNING',
        'message':     'ASHC-1 near ceiling and RIVE-1 still at minimum. Reserve exhausted.',
        'detail':      ('Frequency may still look nominal, but ASHC-1 has little or no '
                        'headroom left — the grid has no meaningful spinning reserve. '
                        'Raise RIVE-1 now. A dispatcher who only watches frequency will '
                        'miss this until it is too late.'),
        'element':     'RIVE-1',
        'condition':   _RIVE1_STILL_AT_MIN,
    },
    {
        'trigger_min': 150.0,
        'priority':    'TUTOR',
        'message':     'RIVE-1 picking up the slack. ASHC-1 relaxing back down.',
        'detail':      ('With RIVE-1 carrying more of the base load, AGC no longer needs '
                        'to hold ASHC-1 so high — regulation headroom is being restored. '
                        'This is the new normal: RIVE now runs both units to cover the '
                        'derated RIVE-2.'),
        'element':     'ASHC-1',
        'condition':   _ASHC1_RECOVERED,
    },
]
