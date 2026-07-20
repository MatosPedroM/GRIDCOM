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

SCRIPTED_EVENTS: list[dict] = []
