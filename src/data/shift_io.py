"""
src/data/shift_io.py

Load / save authored Shift Builder JSON (assets/shifts/<name>.json).

A shift definition bundles everything gameplay/shifts/shift_NN.py provides
today — the grid it runs on, starting conditions, per-bus hourly demand,
and a scripted event timeline — into one self-contained, player-authorable
file. shift_def_to_config() returns the same dict shape
gameplay/shifts/loader.load_shift_config() produces, so both the hardcoded
campaign shifts and authored JSON shifts feed GridSimulation identically.

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
ignored), TIME_MIN (target ignored), VOLTAGE_PU (target=bus label —
reads the collapse-adjusted effective voltage, SimulationState.bus_voltages).
Supported ops: '<', '<=', '>', '>=', '==', '!='.
condition may be None (unconditional).

Event 'action' is a declarative dict or None:
  { "type": "LINE_OPEN", "line": "L09" }
  { "type": "LINE_CLOSE", "line": "L09" }
  { "type": "UNIT_TRIP", "unit": "RVSD-1" }
  { "type": "UNIT_DERATE", "unit": "RVSD-1", "cap_mw": 105.0 }
UNIT_DERATE reduces the unit's dispatch ceiling to cap_mw and holds it
there — unlike UNIT_TRIP, the unit stays ONLINE and keeps producing, just
below its nameplate rating (e.g. a cooling fault). Output snaps down
immediately if currently above the new cap.
Executed by GridSimulation._process_scripted_events() after the alarm
for that event fires.
"""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict


_ASSETS_DIR = Path(__file__).parent.parent / 'assets'
SHIFTS_DIR = _ASSETS_DIR / 'shifts'
_SHIFTS_PKG_DIR = Path(__file__).parent.parent / 'gameplay' / 'shifts'


# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ShiftEvent:
    trigger_min: float
    priority:    str                  # INFO | TUTOR | WARNING | ALARM | CRITICAL | MAINTENANCE
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


# ─────────────────────────────────────────────────────────────────────────────
# CAMPAIGN SHIFT DEV-TOOL BRIDGE
#
# Lets Shift Builder open and fine-tune an existing campaign shift
# (shift_01.py..shift_10.py) instead of only authoring new JSON shifts.
# Narrative fields (module docstring, HANDOVER_NOTES prose, SHIFT_DATE,
# DIFFICULTY_LABEL) are read for display only and are never written back
# here — only the mechanical/tabular constants Shift Builder actually
# edits (INITIAL_SCHEDULE, MAINTENANCE_UNITS, MAINTENANCE_LINES,
# SUBSTATION_LOAD_MW, AGC_ENABLED, SCRIPTED_EVENTS) are round-tripped, via
# a targeted AST-located source-text splice that replaces only the exact
# line span of each edited constant and leaves every other byte of the
# file — docstrings, comments, unedited constants — untouched.
# ─────────────────────────────────────────────────────────────────────────────

# Constants Shift Builder is allowed to write back via save_campaign_shift_fields.
CAMPAIGN_EDITABLE_FIELDS = (
    'initial_schedule', 'maintenance_units', 'maintenance_lines',
    'substation_load_mw', 'agc_enabled', 'events',
)

# Maps a ShiftDefinition field name to the shift_NN.py constant it round-trips to.
_FIELD_TO_CONSTANT = {
    'initial_schedule':   'INITIAL_SCHEDULE',
    'maintenance_units':  'MAINTENANCE_UNITS',
    'maintenance_lines':  'MAINTENANCE_LINES',
    'substation_load_mw': 'SUBSTATION_LOAD_MW',
    'agc_enabled':        'AGC_ENABLED',
    'events':             'SCRIPTED_EVENTS',
}


def list_campaign_shift_numbers() -> list[int]:
    """Return sorted shift numbers with a gameplay/shifts/shift_NN.py file."""
    if not _SHIFTS_PKG_DIR.exists():
        return []
    numbers = []
    for p in _SHIFTS_PKG_DIR.glob('shift_*.py'):
        stem = p.stem
        try:
            numbers.append(int(stem.split('_', 1)[1]))
        except (IndexError, ValueError):
            continue
    return sorted(numbers)


def load_campaign_shift_for_editing(shift_number: int) -> ShiftDefinition:
    """
    Load a campaign shift's mechanical fields into a ShiftDefinition, the
    same in-memory shape ShiftBuilder already edits for JSON shifts.

    Narrative fields (shift_date, difficulty_label, handover_notes) are
    populated for read-only display. 'grid' is set from the shift's
    GRID_SOURCE constant if present (e.g. Shift 10's 'shift10'), else left
    empty — shifts without GRID_SOURCE run on topology.py/fleet.py, which
    has no Designer-grid equivalent to show here.
    """
    from gameplay.shifts.loader import load_shift_config

    cfg = load_shift_config(shift_number)
    mod = importlib.import_module(f'gameplay.shifts.shift_{shift_number:02d}')
    raw_events = getattr(mod, 'SCRIPTED_EVENTS', [])
    events = [
        ShiftEvent(
            trigger_min=e['trigger_min'], priority=e['priority'],
            message=e['message'], detail=e.get('detail', ''),
            element=e.get('element'), condition=e.get('condition'),
            action=e.get('action'),
        )
        for e in raw_events
    ]

    return ShiftDefinition(
        name=f'shift_{shift_number:02d}',
        grid=cfg.get('grid_source') or '',
        shift_date=cfg['shift_date'],
        difficulty_label=cfg['difficulty_label'],
        start_hour=0.0,
        duration_hours=0.0,
        agc_enabled=cfg['agc_enabled'],
        handover_notes=list(cfg['handover_notes']),
        initial_schedule=dict(cfg['initial_schedule']),
        maintenance_units=sorted(cfg['maintenance_units']),
        maintenance_lines=sorted(cfg['maintenance_lines']),
        substation_load_mw=cfg['substation_load_mw'],
        events=events,
    )


def _format_value(value, indent: int = 0) -> str:
    """Pretty-print a Python literal for splicing into shift_NN.py source."""
    pad = '    ' * indent
    if isinstance(value, dict):
        if not value:
            return '{}'
        lines = ['{']
        for k, v in value.items():
            lines.append(f'{pad}    {k!r}: {_format_value(v, indent + 1)},')
        lines.append(f'{pad}}}')
        return '\n'.join(lines)
    if isinstance(value, (set, frozenset)):
        if not value:
            return 'set()'
        items = ', '.join(repr(v) for v in sorted(value))
        return '{' + items + '}'
    if isinstance(value, list):
        if not value:
            return '[]'
        items = ',\n'.join(f'{pad}    {_format_value(v, indent + 1)}' for v in value)
        return '[\n' + items + f',\n{pad}]'
    return repr(value)


def _constant_source(name: str, value) -> str:
    """Return the full 'NAME = value' (or 'NAME: type = value') source line(s)
    for one of the campaign-editable constants, matching each constant's
    existing type-annotation style in shift_NN.py."""
    annotations = {
        'INITIAL_SCHEDULE':   'dict[str, float]',
        'MAINTENANCE_UNITS':  'set[str]',
        'MAINTENANCE_LINES':  'set[str]',
        'SUBSTATION_LOAD_MW': 'dict[str, dict[float, float]]',
        'AGC_ENABLED':        'bool',
        'SCRIPTED_EVENTS':    'list[dict]',
    }
    ann = annotations.get(name)
    prefix = f'{name}: {ann} = ' if ann else f'{name} = '
    return prefix + _format_value(value)


def save_campaign_shift_fields(
    shift_number: int,
    shift_def: ShiftDefinition,
    edited_fields: set[str],
) -> None:
    """
    Splice the given edited fields' values back into shift_NN.py's source
    text, replacing only each constant's own line span (located via ast)
    and leaving every other byte of the file — module docstring,
    HANDOVER_NOTES prose, comments, unedited constants — untouched.

    edited_fields is a subset of CAMPAIGN_EDITABLE_FIELDS. Raises
    ValueError if a field name isn't recognised, or the target constant
    isn't found as a top-level assignment in the file (e.g. a shift file
    that has never declared MAINTENANCE_LINES yet).
    """
    unknown = edited_fields - set(CAMPAIGN_EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f'Not editable via the campaign dev tool: {sorted(unknown)}')
    if not edited_fields:
        return

    path = _SHIFTS_PKG_DIR / f'shift_{shift_number:02d}.py'
    # newline='' preserves the file's exact original line endings on both
    # read and write — without it, Python's universal-newline translation
    # rewrites every LF to the platform's line ending on write (CRLF on
    # Windows), turning a one-line change into a whole-file diff.
    with open(path, 'r', encoding='utf-8', newline='') as f:
        source = f.read()
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    values = {
        'INITIAL_SCHEDULE':   dict(shift_def.initial_schedule),
        'MAINTENANCE_UNITS':  set(shift_def.maintenance_units),
        'MAINTENANCE_LINES':  set(shift_def.maintenance_lines),
        'SUBSTATION_LOAD_MW': shift_def.substation_load_mw,
        'AGC_ENABLED':        shift_def.agc_enabled,
        'SCRIPTED_EVENTS':    [asdict(e) for e in shift_def.events],
    }

    targets = {_FIELD_TO_CONSTANT[f] for f in edited_fields}
    spans: dict[str, tuple[int, int]] = {}   # constant name -> (start_line, end_line), 1-indexed inclusive
    for node in tree.body:
        target_name = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
        if target_name in targets:
            spans[target_name] = (node.lineno, node.end_lineno)

    missing = targets - spans.keys()
    if missing:
        raise ValueError(
            f'Constant(s) not found as top-level assignments in shift_{shift_number:02d}.py: '
            f'{sorted(missing)}'
        )

    # Detect the file's line-ending convention from its own content so the
    # spliced-in text matches exactly (avoids mixed-EOL diffs).
    newline = '\r\n' if '\r\n' in source else '\n'

    # Replace bottom-up so earlier line numbers stay valid as we splice.
    for name, (start, end) in sorted(spans.items(), key=lambda kv: -kv[1][0]):
        new_src = _constant_source(name, values[name]).replace('\n', newline) + newline
        lines[start - 1:end] = [new_src]

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(''.join(lines))
