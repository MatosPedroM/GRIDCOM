"""
src/gameplay/shifts/shift_01.py

Shift 1 scenario definition — single-unit dispatch tutorial.

Narrative:
  ASHC-1 (Ashcombe Hydro Unit 1, 250 MW) is the sole online unit, feeding
  Greymoor substation. AGC is off — the player observes basic frequency and
  load behaviour and must manually correct ASHC-1's output to hold frequency
  nominal as demand ramps.

  Demand is derived at load time from GREY's saved peak_load_mw in
  shift1.json (100 MW) scaled by the campaign's shared
  DEMAND_PROFILE_NORMALISED curve (src/data/profiles.py) — not authored here.

Grid: RIVE ──L01──► ASHC ──L02──► GREY   (3 buses, 2 lines)

GRID_SOURCE below points this shift at the hand-authored Grid Designer grid
(assets/designer_grids/shift1.json) instead of the campaign's topology.py/
fleet.py — see shift_10.py for the same pattern.
"""

from __future__ import annotations


GRID_SOURCE: str = 'shift1'

SHIFT_DATE: str = 'MON 07 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

START_HOUR: float = 4.0

DURATION_HOURS: float = 3.0

HANDOVER_NOTES: tuple[str, ...] = (
    'Night handover from R. Ferris.',
    'Ashcombe hydro unit 1 (ASHC-1) on-line.',
    'AGC off — manual dispatch only.',
    'Demand very low — pre-dawn trough, gentle morning ramp ahead.',
    'Your task: keep frequency nominal as demand rises.',
)

# Starting dispatch — units absent from this dict start OFFLINE.
INITIAL_SCHEDULE: dict[str, float] = {
    'ASHC-1': 30.0,    # Ashcombe Hydro Unit 1 — sole generator (tutorial)
}

# Units on planned maintenance — visible on canvas but cannot be started.
MAINTENANCE_UNITS: set[str] = set()

AGC_ENABLED: bool = False

SCRIPTED_EVENTS: list[dict] = [
    {
        'trigger_min': 0.0,
        'priority':    'TUTOR',
        'message':     'ASHC-1 on-line at 30 MW. AGC off — you are in manual control.',
        'detail':      ('Ashcombe Hydro Unit 1 is the only generator on this grid. '
                        'AGC is off, so its output never changes unless you change '
                        'it. Watch the frequency indicator — it drifts below 50 Hz '
                        'when generation falls behind demand, and above when it '
                        'exceeds it.'),
        'element':     'ASHC-1',
        'condition':   None,
    },
    {
        'trigger_min': 60.0,
        'priority':    'TUTOR',
        'message':     'Demand is rising. Raise ASHC-1 output to hold frequency.',
        'detail':      ('Load at Greymoor is climbing through the pre-dawn ramp. '
                        'If frequency has started drifting low, increase ASHC-1\'s '
                        'target output — hydro responds almost immediately.'),
        'element':     'ASHC-1',
        'condition':   {'metric': 'FREQUENCY_HZ', 'op': '<', 'value': 49.9},
    },
    {
        'trigger_min': 120.0,
        'priority':    'TUTOR',
        'message':     'Morning ramp continuing. Keep ASHC-1 tracking demand.',
        'detail':      ('Demand keeps climbing toward the 07:00 handover. Keep an '
                        'eye on both frequency and ASHC-1\'s output — small, steady '
                        'adjustments are easier to manage than large corrections.'),
        'element':     'ASHC-1',
        'condition':   {'metric': 'UNIT_OUTPUT_MW', 'target': 'ASHC-1',
                        'op': '<', 'value': 33.0},
    },
]
