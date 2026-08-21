"""
src/gameplay/shifts/shift_01.py

Shift 1 scenario definition — placeholder, pending re-authoring against
direct reactive-power control (F9, Session 2026-08-21). Previously "First
Watch," the Phase 2 tutorial arc; reverted to a stub because its voltage/AVR
content (INITIAL_VOLTAGE_SETPOINTS, the Holt Hydro AVR-setpoint lesson) no
longer applies now that generator voltage control is direct-Q (W = MW,
Q = MVAr) rather than an AVR setpoint. No constants defined;
load_shift_config() falls back to its defaults (empty schedule, AGC off,
zero peak demand) if this shift is loaded.
"""

from __future__ import annotations
