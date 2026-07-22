"""
src/gameplay/shifts/shift_00.py

Sentinel shift for Designer/Shift-Builder test sessions (_make_designer_test,
_make_campaign_shift_test in main.py pass shift_number=0). Not a real
campaign shift — no constants defined; load_shift_config() falls back to
its defaults (empty schedule, AGC off, zero peak demand). All real config
for these sessions is passed explicitly to GridSimulation's constructor
(grid, initial_schedule, substation_load_mw, etc.), so the fallback values
here are never actually used — this module exists only so
importlib.import_module('gameplay.shifts.shift_00') resolves.
"""

from __future__ import annotations
