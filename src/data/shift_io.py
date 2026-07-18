"""
src/data/shift_io.py

Load / save authored Shift Builder JSON (assets/shifts/<name>.json).

A shift definition bundles everything gameplay/shifts/shift_NN.py + a
SHIFT_SPECS entry provide today — the grid it runs on, starting
conditions, per-bus hourly demand, and a scripted event timeline — into
one self-contained, player-authorable file. shift_def_to_config() returns
the same dict shape gameplay/shifts/loader.load_shift_config() produces,
so both the hardcoded campaign shifts and authored JSON shifts feed
GridSimulation identically.

JSON schema version 1:
  {
    "version": 1,
    "name": str,
    "grid": str,                     -- stem of assets/designer_grids/<grid>.json
    "shift_date": str,
    "difficulty_label": str,
    "start_hour": float,
    "duration_hours": float,
    "agc_enabled": bool,
    "handover_notes": [str, ...],
    "initial_schedule": {unit_label: mw},
    "maintenance_units": [unit_label, ...],
    "maintenance_lines": [line_label, ...],
    "substation_load_mw": {bus_label: {hour_str: mw}},
    "events": [ { trigger_min, priority, message, detail, element,
                  condition, action } ]
  }

Event 'condition' is a declarative dict (JSON-safe — no Python callables):
  { "metric": "LINE_LOADING", "target": "L15", "op": ">=", "value": 90.0 }
Supported metrics: LINE_LOADING (target=line label), UNIT_OUTPUT_MW
(target=unit label), UNIT_OUTPUT_MW_SUM (targets=[unit label, ...] —
sum of current_mw across all listed units), UNIT_ONLINE (target=unit
label), SPINNING_RESERVE_MW (target ignored), FREQUENCY_HZ (target
ignored), TIME_MIN (target ignored).
Supported ops: '<', '<=', '>', '>=', '==', '!='.
condition may be None (unconditional).

Event 'action' is a declarative dict or None:
  { "type": "LINE_OPEN", "line": "L09" }
  { "type": "LINE_CLOSE", "line": "L09" }
  { "type": "UNIT_TRIP", "unit": "RVSD-1" }
Executed by GridSimulation._process_scripted_events() after the alarm
for that event fires.
"""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict


_ASSETS_DIR = Path(__file__).parent.parent / 'assets'
SHIFTS_DIR = _ASSETS_DIR / 'shifts'


# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ShiftEvent:
    trigger_min: float
    priority:    str                  # INFO | WARNING | ALARM | CRITICAL | MAINTENANCE
    message:     str
    detail:      str = ''
    element:     str | None = None
    condition:   dict | None = None   # declarative condition, see module docstring
    action:      dict | None = None   # declarative action, see module docstring


@dataclass
class ShiftDefinition:
    name:               str
    grid:               str
    shift_date:         str = ''
    difficulty_label:   str = ''
    start_hour:         float = 0.0
    duration_hours:     float = 8.0
    agc_enabled:        bool = False
    handover_notes:     list[str] = field(default_factory=list)
    initial_schedule:   dict[str, float] = field(default_factory=dict)
    maintenance_units:  list[str] = field(default_factory=list)
    maintenance_lines:  list[str] = field(default_factory=list)
    substation_load_mw: dict[str, dict[float, float]] = field(default_factory=dict)
    events:             list[ShiftEvent] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# SAVE / LOAD
# ─────────────────────────────────────────────────────────────────────────────

def list_shift_names() -> list[str]:
    """Return sorted list of saved shift names (filenames without .json)."""
    if not SHIFTS_DIR.exists():
        return []
    return sorted(p.stem for p in SHIFTS_DIR.glob('*.json'))


def save_shift_named(shift_def: ShiftDefinition, name: str) -> None:
    """Save to assets/shifts/<name>.json."""
    SHIFTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SHIFTS_DIR / f'{name}.json'
    data = {
        'version':            1,
        'name':               shift_def.name,
        'grid':               shift_def.grid,
        'shift_date':         shift_def.shift_date,
        'difficulty_label':   shift_def.difficulty_label,
        'start_hour':         shift_def.start_hour,
        'duration_hours':     shift_def.duration_hours,
        'agc_enabled':        shift_def.agc_enabled,
        'handover_notes':     list(shift_def.handover_notes),
        'initial_schedule':   dict(shift_def.initial_schedule),
        'maintenance_units':  list(shift_def.maintenance_units),
        'maintenance_lines':  list(shift_def.maintenance_lines),
        'substation_load_mw': {
            bus: {str(h): mw for h, mw in hourly.items()}
            for bus, hourly in shift_def.substation_load_mw.items()
        },
        'events': [asdict(e) for e in shift_def.events],
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def load_shift_named(name: str) -> ShiftDefinition:
    """Load from assets/shifts/<name>.json. Raises FileNotFoundError if absent."""
    path = SHIFTS_DIR / f'{name}.json'
    if not path.exists():
        raise FileNotFoundError(f"Shift not found: {name!r}")
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    substation_load_mw = {
        bus: {float(h): float(mw) for h, mw in hourly.items()}
        for bus, hourly in data.get('substation_load_mw', {}).items()
    }
    events = [ShiftEvent(**e) for e in data.get('events', [])]

    return ShiftDefinition(
        name=data.get('name', name),
        grid=data['grid'],
        shift_date=data.get('shift_date', ''),
        difficulty_label=data.get('difficulty_label', ''),
        start_hour=data.get('start_hour', 0.0),
        duration_hours=data.get('duration_hours', 8.0),
        agc_enabled=data.get('agc_enabled', False),
        handover_notes=list(data.get('handover_notes', [])),
        initial_schedule=dict(data.get('initial_schedule', {})),
        maintenance_units=list(data.get('maintenance_units', [])),
        maintenance_lines=list(data.get('maintenance_lines', [])),
        substation_load_mw=substation_load_mw,
        events=events,
    )


def delete_shift(name: str) -> None:
    """Delete assets/shifts/<name>.json. Silently ignores missing file."""
    path = SHIFTS_DIR / f'{name}.json'
    if path.exists():
        path.unlink()


# ─────────────────────────────────────────────────────────────────────────────
# RUNTIME CONVERSION
# ─────────────────────────────────────────────────────────────────────────────

def shift_def_to_config(shift_def: ShiftDefinition) -> dict:
    """
    Return the same dict shape gameplay.shifts.loader.load_shift_config()
    produces, plus 'scripted_events' (raw event dicts, fired-flag added by
    GridSimulation). Lets authored JSON shifts and hardcoded shift_NN.py
    shifts feed GridSimulation through one contract.
    """
    return {
        'shift_date':         shift_def.shift_date,
        'difficulty_label':   shift_def.difficulty_label,
        'handover_notes':     tuple(shift_def.handover_notes),
        'initial_schedule':   dict(shift_def.initial_schedule),
        'maintenance_units':  set(shift_def.maintenance_units),
        'maintenance_lines':  set(shift_def.maintenance_lines),
        'agc_enabled':        shift_def.agc_enabled,
        'substation_load_mw': shift_def.substation_load_mw,
        'scripted_events':    [asdict(e) for e in shift_def.events],
    }
