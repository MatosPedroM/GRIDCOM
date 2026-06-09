"""
src/gameplay/shifts/loader.py

Reads per-shift configuration from the appropriate shift_NN.py module.
Each shift file is the single source of truth for its own config.
"""

from __future__ import annotations

import importlib


def load_shift_config(shift_number: int) -> dict:
    """
    Load configuration for a shift from its shift_NN.py module.

    Returns a dict with keys:
        shift_date        str              — formatted date string, e.g. 'MON 07 NOV 1994'
        initial_schedule  dict[str, float] — unit label -> MW at handover
        maintenance_units set[str]         — units locked on planned maintenance
        agc_enabled       bool             — whether AGC is active at shift start
    """
    mod = importlib.import_module(f'gameplay.shifts.shift_{shift_number:02d}')
    return {
        'shift_date':        getattr(mod, 'SHIFT_DATE',        ''),
        'initial_schedule':  getattr(mod, 'INITIAL_SCHEDULE',  {}),
        'maintenance_units': getattr(mod, 'MAINTENANCE_UNITS', set()),
        'agc_enabled':       getattr(mod, 'AGC_ENABLED',       False),
    }
