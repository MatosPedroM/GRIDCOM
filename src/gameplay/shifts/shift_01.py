"""
src/gameplay/shifts/shift_01.py

Shift 1 scenario definition — single-unit dispatch tutorial.

Narrative:
  DUND-1 (Dunmore Lower 1, 65 MW hydro) is the sole online unit.
  All Riverside Coal units and DUND-2 are on planned maintenance.
  The player observes basic frequency and load behaviour with no dispatch decisions.
"""

from __future__ import annotations


SHIFT_DATE: str = 'MON 07 NOV 1994'

# Starting dispatch — units absent from this dict start OFFLINE.
INITIAL_SCHEDULE: dict[str, float] = {
    'DUND-1': 16.0,    # Dunmore Lower 1 — sole generator (tutorial)
}

# Units on planned maintenance — visible on canvas but cannot be started.
MAINTENANCE_UNITS: set[str] = {'RVSD-1', 'RVSD-2', 'RVSD-3', 'DUND-2'}

AGC_ENABLED: bool = False

SCRIPTED_EVENTS: list[dict] = []
