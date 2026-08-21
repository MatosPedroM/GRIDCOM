"""
src/gameplay/shifts/shift_05.py

Shift 5 scenario definition — placeholder, pending re-authoring against
direct reactive-power control (F9, Session 2026-08-21). Previously "The
Plan," the Phase 1 planning-screen tutorial; reverted to a stub because its
voltage tuning (the FENN/YEWB automatic shunt bank lesson, tuned against
AVR-driven voltage behaviour) is no longer valid now that generator voltage
control is direct-Q (W = MW, Q = MVAr) rather than an AVR setpoint. No
constants defined; load_shift_config() falls back to its defaults (empty
schedule, AGC off, zero peak demand) if this shift is loaded.
"""

from __future__ import annotations
