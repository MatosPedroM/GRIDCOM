"""
src/gameplay/shifts/shift_01.py

Shift 1 scenario definition — single-unit dispatch tutorial.

Narrative:
  DUND-1 (Dunmore Lower 1, 65 MW hydro) is the sole online unit, fed from
  the Midbury 400kV substation via the L11 transformer link. DUND-2 is on
  planned maintenance. The player observes basic frequency and load
  behaviour with no dispatch decisions.

Grid: MDBY ──L11──► DUND ──L49──► LD01   (3 buses, 2 lines)
"""

from __future__ import annotations


SHIFT_DATE: str = 'MON 07 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

HANDOVER_NOTES: tuple[str, ...] = (
    'Night handover from R. Ferris.',
    'Dunmore lower hydro unit 1 (DUND-1) on-line.',
    'All other units off-line.',
    'Demand very low — pre-dawn trough, gentle morning ramp ahead.',
    'Your task: keep frequency nominal as demand rises.',
)

# Starting dispatch — units absent from this dict start OFFLINE.
INITIAL_SCHEDULE: dict[str, float] = {
    'DUND-1': 16.0,    # Dunmore Lower 1 — sole generator (tutorial)
}

# Units on planned maintenance — visible on canvas but cannot be started.
MAINTENANCE_UNITS: set[str] = {'DUND-2'}

AGC_ENABLED: bool = False

# Per-bus hourly load table (MW). Shift 1: LD01 only, peak 55 MW.
# Pre-dawn trough into early morning ramp. Single hydro unit.
SUBSTATION_LOAD_MW: dict[str, dict[float, float]] = {
    'LD01': {
         0.0:  17,  1.0:  16,  2.0:  15,  3.0:  15,  4.0:  15,
         5.0:  17,  6.0:  21,  7.0:  27,  8.0:  36,  9.0:  44,
        10.0:  50, 11.0:  52, 12.0:  51, 13.0:  49, 14.0:  48,
        15.0:  50, 16.0:  52, 17.0:  54, 18.0:  55, 19.0:  54,
        20.0:  52, 21.0:  48, 22.0:  41, 23.0:  30, 24.0:  20,
    },
}

SCRIPTED_EVENTS: list[dict] = []
