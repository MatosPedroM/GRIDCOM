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
        shift_date          str                       — formatted date string, e.g. 'MON 07 NOV 1994'
        difficulty_label    str                       — human-readable difficulty descriptor
        handover_notes      tuple[str, ...]           — bulletin lines shown at shift start
        initial_schedule    dict[str, float]          — unit label -> MW at handover
        maintenance_units   set[str]                  — units locked on planned maintenance
        maintenance_lines   set[str]                  — lines that start the shift electrically open
        agc_enabled         bool                      — whether AGC is active at shift start
        substation_load_mw  dict[str, dict[float, float]] — per-bus hourly load table (MW)
    """
    mod = importlib.import_module(f'gameplay.shifts.shift_{shift_number:02d}')
    return {
        'shift_date':         getattr(mod, 'SHIFT_DATE',         ''),
        'difficulty_label':   getattr(mod, 'DIFFICULTY_LABEL',   ''),
        'handover_notes':     getattr(mod, 'HANDOVER_NOTES',     ()),
        'initial_schedule':   getattr(mod, 'INITIAL_SCHEDULE',   {}),
        'maintenance_units':  getattr(mod, 'MAINTENANCE_UNITS',  set()),
        'maintenance_lines':  getattr(mod, 'MAINTENANCE_LINES',  set()),
        'agc_enabled':        getattr(mod, 'AGC_ENABLED',        False),
        'substation_load_mw': getattr(mod, 'SUBSTATION_LOAD_MW', {}),
    }
