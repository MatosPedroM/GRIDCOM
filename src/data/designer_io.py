"""
src/data/designer_io.py

Load / save the Grid Designer JSON file (assets/designer_grid.json).
Also holds the label pools used when auto-assigning names during placement.

JSON schema version 1:
  {
    "version": 1,
    "buses": [ { label, name, voltage_kv, bus_type, canvas_x, canvas_y,
                 active_from_shift, is_slack, peak_load_mw } ],
    "lines": [ { label, from_bus, to_bus, reactance_pu, rating_mw,
                 active_from_shift, active_until_shift, voltage_kv, parallel } ],
    "units": [ { label, station_label, bus_label, unit_type, rated_mw, min_mw,
                 ramp_pct_per_min, inertia_h, cold_start_min,
                 q_max_mvar, q_min_mvar, can_pump, active_from_shift, description } ]
  }
"""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict


# ─────────────────────────────────────────────────────────────────────────────
# FILE PATHS
# ─────────────────────────────────────────────────────────────────────────────

_ASSETS_DIR = Path(__file__).parent.parent / 'assets'
DESIGNER_JSON_PATH  = _ASSETS_DIR / 'designer_grid.json'  # legacy single-file path
DESIGNER_GRIDS_DIR  = _ASSETS_DIR / 'designer_grids'


# ─────────────────────────────────────────────────────────────────────────────
# LABEL POOLS
# ─────────────────────────────────────────────────────────────────────────────

BUS_LABEL_POOL: tuple[str, ...] = (
    'MDBY', 'CNTR', 'NRTH', 'EAST', 'WEST', 'STHW', 'ASHF', 'WRNT', 'RDST', 'FAIR',
    'COAL', 'DUNM', 'BRCK', 'STAN', 'FLDN', 'RIVR', 'VALE', 'CRES', 'HRBR', 'PORT',
    'MNTN', 'LAKE', 'GLEN', 'MOOR', 'HOLM', 'FORD', 'DALE', 'PEAK', 'WICK', 'SHAW',
    'BRID', 'COVE', 'HOLT', 'FELD', 'GATE', 'MERE', 'BURN', 'HALE', 'ROOK', 'WOLD',
    'AVEN', 'TARN', 'SCAR', 'KNOB', 'FELL', 'CRAG', 'DENE', 'BURY', 'CLEY', 'WREN',
)

STATION_LABEL_POOL: tuple[str, ...] = (
    'RVSD', 'THNF', 'ASHG', 'WRNG', 'HART', 'BARR', 'KELM', 'DUNH', 'DUND', 'KELD',
    'BARD', 'WNCN', 'WNBR', 'SLST', 'SLFD', 'AR01', 'AR02', 'AR03', 'AR04', 'BR01',
    'BR02', 'BR03', 'CO01', 'CO02', 'CO03', 'COLM', 'GRBY', 'ASHN', 'PNWY', 'ELMS',
    'CORB', 'DKWD', 'GLSM', 'RDSG', 'BRKG', 'STNG', 'FLDG', 'CRSG', 'VLEG', 'GLNG',
    'LKNG', 'STEN', 'PENT', 'HOLW', 'BRYN', 'CORS', 'WNST', 'WNFD', 'SLSH', 'SLMR',
)

# Default unit parameters by type
UNIT_DEFAULTS: dict[str, dict] = {
    'COAL':       {'rated_mw': 300.0, 'min_mw': 105.0, 'ramp_pct_per_min': 3.0,
                   'inertia_h': 5.0, 'cold_start_min': 240.0,
                   'q_max_mvar': 150.0, 'q_min_mvar': -50.0},
    'CCGT':       {'rated_mw': 400.0, 'min_mw': 100.0, 'ramp_pct_per_min': 8.0,
                   'inertia_h': 4.0, 'cold_start_min': 60.0,
                   'q_max_mvar': 180.0, 'q_min_mvar': -60.0},
    'NUCLEAR':    {'rated_mw': 700.0, 'min_mw': 420.0, 'ramp_pct_per_min': 1.0,
                   'inertia_h': 6.0, 'cold_start_min': 480.0,
                   'q_max_mvar': 300.0, 'q_min_mvar': -100.0},
    'HYDRO':      {'rated_mw': 250.0, 'min_mw': 25.0,  'ramp_pct_per_min': 100.0,
                   'inertia_h': 3.0, 'cold_start_min': 5.0,
                   'q_max_mvar': 120.0, 'q_min_mvar': -40.0},
    'HYDRO_ROR':  {'rated_mw': 30.0,  'min_mw': 0.0,   'ramp_pct_per_min': 100.0,
                   'inertia_h': 3.0, 'cold_start_min': 5.0,
                   'q_max_mvar': 15.0, 'q_min_mvar': -5.0},
    'HYDRO_PUMP': {'rated_mw': 250.0, 'min_mw': 25.0,  'ramp_pct_per_min': 100.0,
                   'inertia_h': 3.0, 'cold_start_min': 8.0,
                   'q_max_mvar': 120.0, 'q_min_mvar': -40.0},
    'WIND':       {'rated_mw': 300.0, 'min_mw': 0.0,   'ramp_pct_per_min': 100.0,
                   'inertia_h': 0.0, 'cold_start_min': 0.0,
                   'q_max_mvar': 0.0,  'q_min_mvar': 0.0},
    'SOLAR':      {'rated_mw': 400.0, 'min_mw': 0.0,   'ramp_pct_per_min': 100.0,
                   'inertia_h': 0.0, 'cold_start_min': 0.0,
                   'q_max_mvar': 0.0,  'q_min_mvar': 0.0},
}


# ─────────────────────────────────────────────────────────────────────────────
# DESIGNER DATA STRUCTURES
# These are mutable dicts used inside GridDesigner, distinct from the frozen
# dataclasses in topology.py / fleet.py.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DesignerBus:
    label:             str
    name:              str
    voltage_kv:        float
    bus_type:          str          # 'TRANSMISSION' or 'LOAD'
    canvas_x:          int
    canvas_y:          int
    active_from_shift: int = 1
    is_slack:          bool = False
    peak_load_mw:      float = 0.0  # only for LOAD buses; 0 for transmission
    label_anchor:      str = 'right'


@dataclass
class DesignerLine:
    label:              str
    from_bus:           str
    to_bus:             str
    reactance_pu:       float
    rating_mw:          float
    voltage_kv:         float
    active_from_shift:  int = 1
    active_until_shift: int = 99
    parallel:           int = 0   # double-circuit draw offset (+1/-1/0), display-only


@dataclass
class DesignerUnit:
    label:             str
    station_label:     str
    bus_label:         str
    unit_type:         str
    rated_mw:          float
    min_mw:            float
    ramp_pct_per_min:  float
    inertia_h:         float
    cold_start_min:    float
    q_max_mvar:        float
    q_min_mvar:        float
    can_pump:          bool
    active_from_shift: int
    description:       str
    station_x:         int = -1   # canvas position, -1 = not yet set, derive from bus
    station_y:         int = -1


# ─────────────────────────────────────────────────────────────────────────────
# SAVE / LOAD
# ─────────────────────────────────────────────────────────────────────────────

def save_designer_grid(
    buses: list[DesignerBus],
    lines: list[DesignerLine],
    units: list[DesignerUnit],
    path: Path = DESIGNER_JSON_PATH,
) -> None:
    """Serialise designer state to JSON."""
    data = {
        'version': 1,
        'buses': [asdict(b) for b in buses],
        'lines': [asdict(l) for l in lines],
        'units': [asdict(u) for u in units],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def load_designer_grid(
    path: Path = DESIGNER_JSON_PATH,
) -> tuple[list[DesignerBus], list[DesignerLine], list[DesignerUnit]]:
    """Load designer state from JSON. Returns empty lists if file absent."""
    if not path.exists():
        return [], [], []
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    buses = [DesignerBus(**b) for b in data.get('buses', [])]
    lines = [DesignerLine(**l) for l in data.get('lines', [])]
    units = [DesignerUnit(**u) for u in data.get('units', [])]
    return buses, lines, units


# ─────────────────────────────────────────────────────────────────────────────
# NAMED FILE SAVE / LOAD
# Multiple designer grids stored in assets/designer_grids/<name>.json
# ─────────────────────────────────────────────────────────────────────────────

def list_designer_grids() -> list[str]:
    """Return sorted list of saved grid names (filenames without .json)."""
    if not DESIGNER_GRIDS_DIR.exists():
        return []
    return sorted(p.stem for p in DESIGNER_GRIDS_DIR.glob('*.json'))


def save_designer_grid_named(
    buses: list[DesignerBus],
    lines: list[DesignerLine],
    units: list[DesignerUnit],
    name: str,
) -> None:
    """Save to assets/designer_grids/<name>.json."""
    DESIGNER_GRIDS_DIR.mkdir(parents=True, exist_ok=True)
    path = DESIGNER_GRIDS_DIR / f'{name}.json'
    data = {
        'version': 1,
        'name': name,
        'buses': [asdict(b) for b in buses],
        'lines': [asdict(l) for l in lines],
        'units': [asdict(u) for u in units],
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def load_designer_grid_named(
    name: str,
) -> tuple[list[DesignerBus], list[DesignerLine], list[DesignerUnit]]:
    """Load from assets/designer_grids/<name>.json. Raises FileNotFoundError if absent."""
    path = DESIGNER_GRIDS_DIR / f'{name}.json'
    if not path.exists():
        raise FileNotFoundError(f"Designer grid not found: {name!r}")
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    buses = [DesignerBus(**b) for b in data.get('buses', [])]
    lines = [DesignerLine(**l) for l in data.get('lines', [])]
    units = [DesignerUnit(**u) for u in data.get('units', [])]
    return buses, lines, units


def delete_designer_grid(name: str) -> None:
    """Delete assets/designer_grids/<name>.json. Silently ignores missing file."""
    path = DESIGNER_GRIDS_DIR / f'{name}.json'
    if path.exists():
        path.unlink()


# ─────────────────────────────────────────────────────────────────────────────
# CONVERSION TO topology.py / fleet.py DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

def designer_buses_to_topology(buses: list[DesignerBus]):
    """Convert DesignerBus list to topology.Bus instances."""
    from data.topology import Bus
    result = []
    for b in buses:
        result.append(Bus(
            label=b.label,
            name=b.name,
            voltage_kv=b.voltage_kv,
            bus_type=b.bus_type,
            canvas_x=b.canvas_x,
            canvas_y=b.canvas_y,
            active_from_shift=b.active_from_shift,
            is_slack=b.is_slack,
        ))
    return result


def designer_lines_to_topology(lines: list[DesignerLine]):
    """Convert DesignerLine list to topology.Line instances."""
    from data.topology import Line
    result = []
    for l in lines:
        result.append(Line(
            label=l.label,
            from_bus=l.from_bus,
            to_bus=l.to_bus,
            reactance_pu=l.reactance_pu,
            rating_mw=l.rating_mw,
            active_from_shift=l.active_from_shift,
            voltage_kv=l.voltage_kv,
            active_until_shift=l.active_until_shift,
            parallel=l.parallel,
        ))
    return result


def designer_units_to_fleet(units: list[DesignerUnit]):
    """Convert DesignerUnit list to fleet.GenerationUnit instances."""
    from data.fleet import GenerationUnit
    result = []
    for u in units:
        result.append(GenerationUnit(
            label=u.label,
            station_label=u.station_label,
            bus_label=u.bus_label,
            unit_type=u.unit_type,
            rated_mw=u.rated_mw,
            min_mw=u.min_mw,
            ramp_pct_per_min=u.ramp_pct_per_min,
            inertia_h=u.inertia_h,
            cold_start_min=u.cold_start_min,
            q_max_mvar=u.q_max_mvar,
            q_min_mvar=u.q_min_mvar,
            can_pump=u.can_pump,
            active_from_shift=u.active_from_shift,
            description=u.description,
        ))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# CONVERSION FROM topology.py / fleet.py DATACLASSES (campaign -> Designer)
# ─────────────────────────────────────────────────────────────────────────────

def topology_buses_to_designer(
    buses: list,
    peak_load_by_bus: dict[str, float],
) -> list['DesignerBus']:
    """
    Convert topology.Bus list to DesignerBus instances.

    peak_load_by_bus: {bus_label: peak_mw}, only consulted for LOAD buses
    (typically max(SUBSTATION_LOAD_MW[label].values()) for the shift being
    imported). Missing entries default to 0.0 rather than raising.
    """
    result = []
    for b in buses:
        peak_mw = peak_load_by_bus.get(b.label, 0.0) if b.bus_type == 'LOAD' else 0.0
        result.append(DesignerBus(
            label=b.label,
            name=b.name,
            voltage_kv=b.voltage_kv,
            bus_type=b.bus_type,
            canvas_x=b.canvas_x,
            canvas_y=b.canvas_y,
            active_from_shift=b.active_from_shift,
            is_slack=b.is_slack,
            peak_load_mw=peak_mw,
        ))
    return result


def topology_lines_to_designer(lines: list) -> list['DesignerLine']:
    """Convert topology.Line list to DesignerLine instances."""
    result = []
    for l in lines:
        result.append(DesignerLine(
            label=l.label,
            from_bus=l.from_bus,
            to_bus=l.to_bus,
            reactance_pu=l.reactance_pu,
            rating_mw=l.rating_mw,
            voltage_kv=l.voltage_kv,
            active_from_shift=l.active_from_shift,
            active_until_shift=l.active_until_shift,
            parallel=l.parallel,
        ))
    return result


def fleet_units_to_designer(units: list) -> list['DesignerUnit']:
    """Convert fleet.GenerationUnit list to DesignerUnit instances."""
    result = []
    for u in units:
        result.append(DesignerUnit(
            label=u.label,
            station_label=u.station_label,
            bus_label=u.bus_label,
            unit_type=u.unit_type,
            rated_mw=u.rated_mw,
            min_mw=u.min_mw,
            ramp_pct_per_min=u.ramp_pct_per_min,
            inertia_h=u.inertia_h,
            cold_start_min=u.cold_start_min,
            q_max_mvar=u.q_max_mvar,
            q_min_mvar=u.q_min_mvar,
            can_pump=u.can_pump,
            active_from_shift=u.active_from_shift,
            description=u.description,
        ))
    return result


def import_shift_as_designer_grid(shift_number: int, name: str) -> None:
    """
    Build a named Designer grid from the given shift's active campaign
    topology/fleet and save it via save_designer_grid_named().

    Per-bus peak_load_mw is computed from that shift's SUBSTATION_LOAD_MW
    table (max over the hourly curve), since topology.Bus itself carries no
    load value. One-shot conversion utility — not called during normal
    Designer editing.
    """
    from data.topology import get_buses_by_shift, get_lines_by_shift
    from data.fleet import get_units_by_shift
    from gameplay.shifts.loader import load_shift_config

    real_buses = get_buses_by_shift(shift_number)
    real_lines = get_lines_by_shift(shift_number)
    real_units = get_units_by_shift(shift_number)

    cfg = load_shift_config(shift_number)
    sub_load = cfg.get('substation_load_mw', {})
    peak_load_by_bus = {
        bus_label: max(table.values()) if table else 0.0
        for bus_label, table in sub_load.items()
    }

    d_buses = topology_buses_to_designer(real_buses, peak_load_by_bus)
    d_lines = topology_lines_to_designer(real_lines)
    d_units = fleet_units_to_designer(real_units)

    save_designer_grid_named(d_buses, d_lines, d_units, name)


# ─────────────────────────────────────────────────────────────────────────────
# LABEL POOL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def next_bus_label(used_labels: set[str]) -> str:
    """Return the next unused bus label from the pool."""
    for lbl in BUS_LABEL_POOL:
        if lbl not in used_labels:
            return lbl
    idx = len(used_labels)
    return f'B{idx:03d}'


def next_station_label(used_stations: set[str]) -> str:
    """Return the next unused station label from the pool."""
    for lbl in STATION_LABEL_POOL:
        if lbl not in used_stations:
            return lbl
    idx = len(used_stations)
    return f'S{idx:03d}'


def next_line_label(used_labels: set[str]) -> str:
    """Return the next line label (L01, L02, …)."""
    for i in range(1, 999):
        lbl = f'L{i:02d}'
        if lbl not in used_labels:
            return lbl
    return 'L999'
