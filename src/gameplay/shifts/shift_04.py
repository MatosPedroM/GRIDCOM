"""
src/gameplay/shifts/shift_04.py

Shift 4 scenario definition — placeholder, pending re-authoring against
direct reactive-power control (F9, Session 2026-08-21). Previously "Local
Support," the voltage/reactive-power tutorial; reverted to a stub because
its entire lesson — "raise Batherton's AVR setpoint" — no longer applies
now that generator voltage control is direct-Q (W = MW, Q = MVAr) rather
than an AVR setpoint. No constants defined; load_shift_config() falls back
to its defaults (empty schedule, AGC off, zero peak demand) if this shift
is loaded.
"""

from __future__ import annotations


GRID_SOURCE: str = 'grid_small'
