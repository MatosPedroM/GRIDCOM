"""
src/gameplay/shifts/loader.py

Reads per-shift configuration from the appropriate shift_NN.py module.
Each shift file is the single source of truth for its own config.

load_shift_config_from_json() reads the same configuration shape from a
Shift Builder JSON file (src/assets/shifts/<name>.json) instead, for
authored/Continuous-mode shifts. Both paths produce a dict GridSimulation
can consume identically; the JSON path additionally returns
'scripted_events' and 'grid' (the campaign loader omits events, since
shift_NN.py's SCRIPTED_EVENTS is read separately by simulation.py).
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
        grid_source         str | None                — saved Grid Designer grid name
                                                          (assets/designer_grids/<grid_source>.json)
                                                          to use instead of topology.py/fleet.py,
                                                          or None for the normal campaign topology
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
        'grid_source':        getattr(mod, 'GRID_SOURCE',        None),
    }


def load_shift_config_from_json(name: str) -> dict:
    """
    Load configuration for an authored shift from src/assets/shifts/<name>.json.

    Returns everything load_shift_config() returns, plus:
        grid              str        — saved designer grid name (assets/designer_grids/<grid>.json)
        start_hour        float
        duration_hours    float
        scripted_events   list[dict] — raw event dicts (fired-flag added by GridSimulation)
    """
    from data.shift_io import load_shift_named, shift_def_to_config

    shift_def = load_shift_named(name)
    cfg = shift_def_to_config(shift_def)
    cfg['grid'] = shift_def.grid
    cfg['start_hour'] = shift_def.start_hour
    cfg['duration_hours'] = shift_def.duration_hours
    return cfg
