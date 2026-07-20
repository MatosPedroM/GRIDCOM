"""
src/gameplay/shifts/shift_01.py

Shift 1 scenario definition — single-unit dispatch tutorial.

Narrative:
  ASHC-1 (Ashcombe Hydro Unit 1, 250 MW) is the sole online unit, feeding
  Oakendale substation via Greymoor. AGC is off — the player observes basic
  frequency and load behaviour and must manually correct ASHC-1's output to
  hold frequency nominal as demand ramps.

Grid: RIVE ──L01──► ASHC ──L02──► GREY ──L03──► OAKE   (4 buses, 3 lines)

GRID_SOURCE below points this shift at the hand-authored Grid Designer grid
(assets/designer_grids/shift1.json) instead of the campaign's topology.py/
fleet.py — see shift_10.py for the same pattern.
"""

from __future__ import annotations


GRID_SOURCE: str = 'shift1'

SHIFT_DATE: str = 'MON 07 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

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

# Per-bus hourly load table (MW). Shift 1: OAKE only, peak 100 MW.
# Pre-dawn trough into early morning ramp. Single hydro unit.
SUBSTATION_LOAD_MW: dict[str, dict[float, float]] = {
    'OAKE': {
         0.0:  31,  1.0:  29,  2.0:  27,  3.0:  27,  4.0:  27,
         5.0:  31,  6.0:  38,  7.0:  49,  8.0:  65,  9.0:  80,
        10.0:  91, 11.0:  95, 12.0:  93, 13.0:  89, 14.0:  87,
        15.0:  91, 16.0:  95, 17.0:  98, 18.0: 100, 19.0:  98,
        20.0:  95, 21.0:  87, 22.0:  75, 23.0:  55, 24.0:  36,
    },
}

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
        'detail':      ('Load at Oakendale is climbing through the pre-dawn ramp. '
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
