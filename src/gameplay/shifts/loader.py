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
from simulation.constants import AGC_ELIGIBLE_TYPES as _AGC_ELIGIBLE_TYPES_DEFAULT


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
        droop_enabled       bool                      — whether governor droop is active at shift
                                                          start (default False — see constants.py
                                                          DROOP_ENABLED; set DROOP_ENABLED = True in
                                                          a shift_NN.py to opt a shift into universal
                                                          governor droop on top of AGC)
        freq_tolerance_mult float                     — multiplier on F_ALERT_*/F_CRITICAL_*'s
                                                          deltas from nominal (default 1.0 — see
                                                          constants.py FREQ_TOLERANCE_MULT; set > 1.0
                                                          in a shift_NN.py to widen the alarm/crisis
                                                          band for a tutorial shift. F_MIN/F_MAX, the
                                                          hard clamp, are never scaled)
        agc_eligible_types  frozenset[str]             — unit types AGC may dispatch (default
                                                          constants.py AGC_ELIGIBLE_TYPES, {HYDRO,
                                                          CCGT}); set AGC_ELIGIBLE_TYPES in a
                                                          shift_NN.py to widen (tutorial shifts —
                                                          add HYDRO_PUMP) or narrow (hard shifts —
                                                          HYDRO only) the campaign-wide AGC
                                                          difficulty curve. HYDRO_ROR is never
                                                          eligible on any shift — it has no
                                                          controllable reservoir to respond with
        agc_speed_mult      float                      — multiplier on AGC_MAX_RATE_MW_S and
                                                          AGC_KI together (default 1.0 — see
                                                          constants.py AGC_SPEED_MULT); < 1.0 makes
                                                          AGC noticeably slower to close a given
                                                          error, without changing eligibility
        substation_load_mw  dict[str, dict[float, float]] — per-bus hourly load table (MW), built by
                                                          scaling each LOAD bus's peak_load_mw by the
                                                          shared DEMAND_PROFILE_NORMALISED curve; empty
                                                          if the shift has no grid_source
        substation_types    dict[str, str]            — optional {bus_label: 'INDUSTRIAL'|
                                                          'RESIDENTIAL'|'MIXED'} from the shift file's
                                                          SUBSTATION_TYPES; empty if the shift declares
                                                          none (defaults to all-MIXED, no reactive
                                                          devices — see _make_sim_and_renderer())
        shunt_bank_overrides dict[str, dict]          — optional {bus_label: {'max_steps': int,
                                                          'mvar_per_step': float, 'initial_step': int}}
                                                          from the shift file's SHUNT_BANK_OVERRIDES,
                                                          applied after seed_default_reactive_devices()
                                                          to resize an individual bus's automatic shunt
                                                          bank (e.g. undersized so it cannot fully
                                                          compensate a sag alone) and optionally
                                                          pre-engage it at handover; empty if the
                                                          shift declares none
        initial_q_mvar       dict[str, float]          — optional {unit_label: q_mvar} from the shift
                                                          file's INITIAL_Q_MVAR, applied at handover
                                                          instead of every unit's default 0.0 MVAr;
                                                          empty if the shift declares none
        grid_source         str | None                — saved Grid Designer grid name
                                                          (assets/designer_grids/<grid_source>.json)
                                                          to use instead of topology.py/fleet.py,
                                                          or None for the normal campaign topology
        win_conditions      list[dict]                — optional WIN_CONDITIONS from the shift
                                                          file: declarative conditions (same schema
                                                          as a scripted-event condition, plus an
                                                          optional sustained_s) that must ALL hold at
                                                          shift end for the shift to be won. Empty
                                                          (the default) means the shift cannot be
                                                          lost on objectives — today's behaviour for
                                                          every existing shift
        fail_conditions     list[dict]                — optional FAIL_CONDITIONS from the shift file:
                                                          ANY one holding (for its sustained_s, if
                                                          given) ends the shift immediately as failed.
                                                          Evaluated every tick, unlike scripted-event
                                                          conditions which sample once
        uses_planning        bool                      — whether this shift routes through the
                                                          Phase 1 planning screen (GameState.PLANNING)
                                                          before Phase 2, from the shift file's
                                                          USES_PLANNING; False if the shift declares
                                                          none (goes straight to real-time play, as
                                                          every shift does today)
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
        'droop_enabled':           getattr(mod, 'DROOP_ENABLED',           False),
        'freq_tolerance_mult':     getattr(mod, 'FREQ_TOLERANCE_MULT',     1.0),
        'agc_eligible_types':      frozenset(getattr(mod, 'AGC_ELIGIBLE_TYPES', _AGC_ELIGIBLE_TYPES_DEFAULT)),
        'agc_speed_mult':          getattr(mod, 'AGC_SPEED_MULT',          1.0),
        'substation_load_mw':      substation_load_mw,
        'substation_types':        dict(getattr(mod, 'SUBSTATION_TYPES', {})),
        'shunt_bank_overrides':    dict(getattr(mod, 'SHUNT_BANK_OVERRIDES', {})),
        'initial_q_mvar':          dict(getattr(mod, 'INITIAL_Q_MVAR', {})),
        'grid_source':             grid_source,
        'uses_planning':           getattr(mod, 'USES_PLANNING', False),
        'win_conditions':          list(getattr(mod, 'WIN_CONDITIONS',  [])),
        'fail_conditions':         list(getattr(mod, 'FAIL_CONDITIONS', [])),
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
