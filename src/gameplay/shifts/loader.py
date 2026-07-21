"""
src/gameplay/shifts/loader.py

Reads per-shift configuration from the appropriate shift_NN.py module.
Each shift file is the single source of truth for its own config.

Demand is never hand-authored per shift: for GRID_SOURCE shifts, peak_demand_mw
and substation_load_mw are both derived here from the Designer grid's own
per-bus peak_load_mw values (summed for the peak; scaled by the shared
DEMAND_PROFILE_NORMALISED curve for the hourly shape), so a shift's demand can
never drift out of sync with its grid file.

load_shift_config_from_json() reads the same configuration shape from a
Shift Builder JSON file (src/assets/shifts/<name>.json) instead, for
authored/Continuous-mode shifts. Both paths produce a dict GridSimulation
can consume identically; the JSON path additionally returns
'scripted_events' and 'grid' (the campaign loader omits events, since
shift_NN.py's SCRIPTED_EVENTS is read separately by simulation.py).
"""

from __future__ import annotations

import importlib

from data.profiles import DEMAND_PROFILE_NORMALISED


def load_shift_config(shift_number: int) -> dict:
    """
    Load configuration for a shift from its shift_NN.py module.

    Returns a dict with keys:
        shift_date          str                       — formatted date string, e.g. 'MON 07 NOV 1994'
        difficulty_label    str                       — human-readable difficulty descriptor
        start_hour          float                     — shift start time (decimal hours, 24h clock)
        duration_hours      float                     — length of the shift window in simulated hours
        peak_demand_mw      float                     — sum of every active LOAD bus's peak_load_mw
                                                          in this shift's Grid Designer grid (0.0 if
                                                          the shift has no grid_source)
        handover_notes      tuple[str, ...]           — bulletin lines shown at shift start
        initial_schedule    dict[str, float]          — unit label -> MW at handover
        maintenance_units   set[str]                  — units locked on planned maintenance
        maintenance_lines   set[str]                  — lines that start the shift electrically open
        agc_enabled         bool                      — whether AGC is active at shift start
        substation_load_mw  dict[str, dict[float, float]] — per-bus hourly load table (MW), built by
                                                          scaling each LOAD bus's peak_load_mw by the
                                                          shared DEMAND_PROFILE_NORMALISED curve; empty
                                                          if the shift has no grid_source
        grid_source         str | None                — saved Grid Designer grid name
                                                          (assets/designer_grids/<grid_source>.json)
                                                          to use instead of topology.py/fleet.py,
                                                          or None for the normal campaign topology
    """
    mod = importlib.import_module(f'gameplay.shifts.shift_{shift_number:02d}')
    grid_source = getattr(mod, 'GRID_SOURCE', None)

    peak_demand_mw: float = 0.0
    substation_load_mw: dict[str, dict[float, float]] = {}
    if grid_source:
        from data.designer_io import load_designer_grid_named
        buses, _lines, _units = load_designer_grid_named(grid_source)
        load_buses = [b for b in buses if b.bus_type == 'LOAD' and b.peak_load_mw > 0]
        peak_demand_mw = sum(b.peak_load_mw for b in load_buses)
        substation_load_mw = {
            b.label: {h: b.peak_load_mw * DEMAND_PROFILE_NORMALISED[h]
                      for h in DEMAND_PROFILE_NORMALISED}
            for b in load_buses
        }

    return {
        'shift_date':              getattr(mod, 'SHIFT_DATE',              ''),
        'difficulty_label':        getattr(mod, 'DIFFICULTY_LABEL',        ''),
        'start_hour':              getattr(mod, 'START_HOUR',              0.0),
        'duration_hours':          getattr(mod, 'DURATION_HOURS',          8.0),
        'peak_demand_mw':          peak_demand_mw,
        'handover_notes':          getattr(mod, 'HANDOVER_NOTES',          ()),
        'initial_schedule':        getattr(mod, 'INITIAL_SCHEDULE',        {}),
        'maintenance_units':       getattr(mod, 'MAINTENANCE_UNITS',       set()),
        'maintenance_lines':       getattr(mod, 'MAINTENANCE_LINES',       set()),
        'agc_enabled':             getattr(mod, 'AGC_ENABLED',             False),
        'substation_load_mw':      substation_load_mw,
        'grid_source':             grid_source,
    }


def load_shift_config_from_json(name: str) -> dict:
    """
    Load configuration for an authored shift from src/assets/shifts/<name>.json.

    Returns everything shift_def_to_config() returns (shift_date, difficulty_label,
    handover_notes, initial_schedule, maintenance_units, maintenance_lines,
    agc_enabled, substation_load_mw, scripted_events — no peak_demand_mw or
    grid_source: JSON shifts derive demand bottom-up from substation_load_mw
    and always carry an explicit grid instead), plus:
        grid              str        — saved designer grid name (assets/designer_grids/<grid>.json)
        start_hour        float
        duration_hours    float
    """
    from data.shift_io import load_shift_named, shift_def_to_config

    shift_def = load_shift_named(name)
    cfg = shift_def_to_config(shift_def)
    cfg['grid'] = shift_def.grid
    cfg['start_hour'] = shift_def.start_hour
    cfg['duration_hours'] = shift_def.duration_hours
    return cfg
