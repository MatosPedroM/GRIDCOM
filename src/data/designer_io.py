"""
src/data/designer_io.py

Load / save the Grid Designer JSON file (assets/designer_grid.json).
Also holds the label pools used when auto-assigning names during placement.

JSON schema version 1:
  {
    "version": 1,
    "buses": [ { label, name, voltage_kv, bus_type, canvas_x, canvas_y,
                 active_from_shift, is_slack, peak_load_mw, label_anchor,
                 substation_type } ],
    "lines": [ { label, from_bus, to_bus, reactance_pu, rating_mw,
                 active_from_shift, active_until_shift, voltage_kv, parallel,
                 from_port_override, to_port_override, length_km } ],
    "units": [ { label, station_label, bus_label, unit_type, rated_mw, min_mw,
                 ramp_pct_per_min, inertia_h, cold_start_min,
                 q_max_mvar, q_min_mvar, can_pump, active_from_shift, description,
                 station_x, station_y, start_mw, in_service,
                 min_up_time_h, min_down_time_h, station_name } ]
  }

  start_mw: test-session starting dispatch, MW. -1.0 (default) means "not
  explicitly set" — test-session launch falls back to rated_mw * 0.5.
  in_service: whether the unit is available at test-session start (False
  behaves like being placed on that session's maintenance list). Both
  fields are consumed only by the Grid Designer's "test in shift" launch
  path, not by campaign topology/fleet data.

  substation_type: 'MIXED' (default) | 'INDUSTRIAL' | 'RESIDENTIAL' — only
  meaningful for LOAD buses; drives per-bus power factor / reactive load and
  automatic-shunt-bank eligibility (see simulation.constants.SUBSTATION_TYPE_PF,
  GridSimulation.seed_default_reactive_devices()). TRANSMISSION buses carry
  the field (dataclass default) but it has no effect for them.

  length_km: physical span in km — the basis reactance_pu is derived from
  (see simulation.constants.reactance_pu_per_km() / display.designer's
  reactance_pu_per_km() helper). None only for legacy data predating this
  field.
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
# NAME POOL
#
# Human-readable substation/place names, auto-assigned when a new bus is
# placed. The 4-letter code (label) for both buses and generation stations
# is mechanically derived from the chosen name — see label_from_name()
# below — so there is a single source of truth for identity, not a
# separate flat code pool. A generation station has no name pool of its
# own: it simply takes the name of the bus it is connected to.
#
# Must not reuse: topology.py's hand-authored bus names (Westham, Midbury,
# Southwick, Centrefield, Northgate, Eastmoor, Ashford, Fairfield, Wrentham,
# Dunmore, Dunmore Lower, Redstone, Kelmore Lower, Ardenbridge, Millhaven,
# Weirfield, Ardenmouth, Coalton, Barrow Lower, Cairn Wind, Stanton Solar,
# Stanton, Brackley, Brentford, Brentwell, Brentmoor, Feldon, Colnbrook,
# Colnhurst, Colnstead, Hallowmere, Pemberton, Thistledown, Elmscroft,
# Farringstone, Rushbourne, Ottermead, Bramleigh, Hartsdene, Rowancroft,
# Wychmoor) or fleet.py's station name-roots (Riverside, Thornfield, Ashford,
# Wrentham, Hartwell, Barrow, Kelmore, Dunmore, Cairn, Brackley, Stanton,
# Feldon, Ardenbridge, Millhaven, Weirfield, Ardenmouth, Brentford, Brentwell,
# Brentmoor, Colnbrook, Colnhurst, Colnstead) — see CLAUDE.md "Naming
# Conventions" and topology.py/fleet.py for the authoritative campaign list.
# ─────────────────────────────────────────────────────────────────────────────

SUBSTATION_NAME_POOL: tuple[str, ...] = (
    'Riverside',    'Ashcombe',     'Greymoor',     'Oakendale',    'Sutterleigh',
    'Ravensmere',   'Hollowgate',   'Wrenfield',    'Batherton',    'Cloverstead',
    'Nettlecross',  'Sheldwick',    'Warrengate',   'Foxholt',      'Larkspur Cross',
    'Thornbury',    'Applecroft',   'Marchden',     'Yewbarrow',    'Cranmere',
    'Pikestead',    'Longacre',     'Underwold',    'Farleigh',     'Studcombe',
    'Hazelbourne',  'Whinmoor',     'Alderthorpe',  'Buryhurst',    'Kestrelford',
    'Netherwick',   'Odcombe',      'Sparrowdene',  'Elmshaw',      'Priorsgate',
    'Merryhurst',   'Bracknell End','Ferngate',     'Southmere',    'Highbourne',
    'Gorsecombe',   'Wexfield',     'Ledgemoor',    'Hartswell',    'Stourbridge Fen',
    'Chalkdown',    'Rivenholt',    'Downside',     'Aldergate',    'Marrowfield',
    'Cobbleford',   'Wintermoor',   'Faulkhurst',   'Reedcroft',    'Ashendene',
    'Barnstead',    'Cinderleigh',  'Draycombe',    'Emberholt',    'Fenwold',
    'Grimsdyke',    'Hollyford',    'Iverbourne',   'Juniperleigh', 'Kirkstead',
    'Lambhurst',    'Mossgate',     'Norbrook',     'Oxendene',     'Pennywold',
    'Quernmore',    'Ridgeholt',    'Silverdale',   'Tallowcross',  'Ulverwick',
    'Vinecombe',    'Waltham Fen',  'Yarnfield',    'Zennorwick',   'Ambercroft',
    'Blackthorn End','Cragwell',    'Dunstable Row','Elderholt',    'Fallowmere',
    'Grovehaven',   'Hartledene',   'Ivythorpe',    'Jackdaw Cross','Knollside',
    'Larchmoor',    'Mistover',     'Newfold',      'Oatlands',     'Peverell',
    'Quarrymoor',   'Rushgate',     'Stonewick',    'Thistlecombe', 'Woolhurst',
)

# Default unit parameters by type
UNIT_DEFAULTS: dict[str, dict] = {
    'COAL':       {'rated_mw': 300.0, 'min_mw': 105.0, 'ramp_pct_per_min': 3.0,
                   'inertia_h': 5.0, 'cold_start_min': 240.0,
                   'q_max_mvar': 150.0, 'q_min_mvar': -50.0,
                   'min_up_time_h': 6.0, 'min_down_time_h': 8.0},
    'CCGT':       {'rated_mw': 400.0, 'min_mw': 100.0, 'ramp_pct_per_min': 8.0,
                   'inertia_h': 4.0, 'cold_start_min': 60.0,
                   'q_max_mvar': 180.0, 'q_min_mvar': -60.0,
                   'min_up_time_h': 2.0, 'min_down_time_h': 2.0},
    'NUCLEAR':    {'rated_mw': 700.0, 'min_mw': 420.0, 'ramp_pct_per_min': 1.0,
                   'inertia_h': 6.0, 'cold_start_min': 480.0,
                   'q_max_mvar': 300.0, 'q_min_mvar': -100.0,
                   'min_up_time_h': 24.0, 'min_down_time_h': 24.0},
    'HYDRO':      {'rated_mw': 250.0, 'min_mw': 25.0,  'ramp_pct_per_min': 100.0,
                   'inertia_h': 3.0, 'cold_start_min': 5.0,
                   'q_max_mvar': 120.0, 'q_min_mvar': -40.0,
                   'min_up_time_h': 0.0, 'min_down_time_h': 0.0},
    'HYDRO_ROR':  {'rated_mw': 30.0,  'min_mw': 0.0,   'ramp_pct_per_min': 100.0,
                   'inertia_h': 3.0, 'cold_start_min': 5.0,
                   'q_max_mvar': 15.0, 'q_min_mvar': -5.0,
                   'min_up_time_h': 0.0, 'min_down_time_h': 0.0},
    'HYDRO_PUMP': {'rated_mw': 250.0, 'min_mw': 25.0,  'ramp_pct_per_min': 100.0,
                   'inertia_h': 3.0, 'cold_start_min': 8.0,
                   'q_max_mvar': 120.0, 'q_min_mvar': -40.0,
                   'min_up_time_h': 0.0, 'min_down_time_h': 0.0},
    'WIND':       {'rated_mw': 300.0, 'min_mw': 0.0,   'ramp_pct_per_min': 100.0,
                   'inertia_h': 0.0, 'cold_start_min': 0.0,
                   'q_max_mvar': 0.0,  'q_min_mvar': 0.0,
                   'min_up_time_h': 0.0, 'min_down_time_h': 0.0},
    'SOLAR':      {'rated_mw': 400.0, 'min_mw': 0.0,   'ramp_pct_per_min': 100.0,
                   'inertia_h': 0.0, 'cold_start_min': 0.0,
                   'q_max_mvar': 0.0,  'q_min_mvar': 0.0,
                   'min_up_time_h': 0.0, 'min_down_time_h': 0.0},
}

# Size variants for the plain HYDRO palette entry (not HYDRO_ROR/HYDRO_PUMP,
# which are already distinct fixed-size types). Only rated_mw/min_mw/
# q_max_mvar/q_min_mvar vary by size — ramp_pct_per_min, inertia_h,
# cold_start_min, min_up_time_h, min_down_time_h are shared, taken from
# UNIT_DEFAULTS['HYDRO']. LARGE matches UNIT_DEFAULTS['HYDRO'] exactly, so
# an untouched HYDRO placement (default size) is unchanged from before this
# was added.
HYDRO_SIZE_DEFAULTS: dict[str, dict] = {
    'SMALL':  {'rated_mw': 50.0,  'min_mw': 5.0,  'q_max_mvar': 24.0,  'q_min_mvar': -8.0},
    'MEDIUM': {'rated_mw': 150.0, 'min_mw': 15.0, 'q_max_mvar': 72.0,  'q_min_mvar': -24.0},
    'LARGE':  {'rated_mw': 250.0, 'min_mw': 25.0, 'q_max_mvar': 120.0, 'q_min_mvar': -40.0},
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
    # 'MIXED' | 'INDUSTRIAL' | 'RESIDENTIAL' — only meaningful for LOAD buses;
    # drives per-bus power factor / reactive load and automatic shunt-bank
    # eligibility. See seed_default_reactive_devices() / SUBSTATION_TYPE_PF.
    substation_type:   str = 'MIXED'


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
    # Manual attachment-port override, set via the designer's line-rotate (R)
    # feature — (side, slot) e.g. ('N', 0), or None for the automatic
    # bearing-derived port. Cosmetic only; never affects topology/solving.
    from_port_override: tuple[str, int] | None = None
    to_port_override:   tuple[str, int] | None = None
    # Physical span in km — the basis reactance_pu is derived from (see
    # simulation.constants.reactance_pu_per_km()). None only for legacy/
    # hand-edited files predating this field; never solved on directly.
    length_km:          float | None = None


def _normalise_line_dict(d: dict) -> dict:
    """JSON round-trips tuples as lists — restore the (side, slot) tuple
    shape for the port-override fields before constructing a DesignerLine."""
    d = dict(d)
    for key in ('from_port_override', 'to_port_override'):
        val = d.get(key)
        if val is not None:
            d[key] = tuple(val)
    return d


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
    start_mw:          float = -1.0  # test-session starting dispatch, -1 = auto (rated_mw * 0.5)
    in_service:        bool = True   # test-session availability, False = starts on maintenance
    label_anchor:      str = 'right'  # station label position, one per station_label
    # Phase 1 planning-layer constraints (see GenerationUnit) — fallback
    # defaults only used when loading a saved grid predating this field.
    min_up_time_h:     float = 1.0
    min_down_time_h:   float = 1.0
    # Human-readable station name, e.g. 'Millbrook' (technology-flavoured
    # pool). '' = pre-existing saved grid predating this field — falls back
    # to station_label for display, same pattern as min_up_time_h above.
    station_name:      str = ''


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
    lines = [DesignerLine(**_normalise_line_dict(l)) for l in data.get('lines', [])]
    units = [DesignerUnit(**u) for u in data.get('units', [])]
    return buses, lines, units


# ─────────────────────────────────────────────────────────────────────────────
# NAMED FILE SAVE / LOAD
# Multiple designer grids stored in assets/designer_grids/<name>.json.
#
# Naming convention: names of the form 'shift<N>' (e.g. 'shift10') are
# reserved for campaign use — they're the GRID_SOURCE a shift_NN.py module
# points at. Player scratch designs should avoid that pattern so they don't
# collide with (or get mistaken for) campaign-owned grids.
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
    lines = [DesignerLine(**_normalise_line_dict(l)) for l in data.get('lines', [])]
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
            from_port_override=l.from_port_override,
            to_port_override=l.to_port_override,
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
            min_up_time_h=u.min_up_time_h,
            min_down_time_h=u.min_down_time_h,
        ))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# LABEL & NAME POOL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def next_bus_name(used_names: set[str]) -> str:
    """Return the next unused human-readable bus/substation name from the pool."""
    for name in SUBSTATION_NAME_POOL:
        if name not in used_names:
            return name
    idx = len(used_names)
    return f'Substation {idx}'


def label_from_name(name: str, used_labels: set[str]) -> str:
    """Derive a 4-letter uppercase code from a human-readable name (bus or
    station), resolving collisions against used_labels. Used for both bus
    labels and station labels — there is no separate code pool; the code
    always comes from whichever name was already assigned.

    First word only (for multi-word pool entries like 'Windrush Fell'),
    letters only, uppercased. Station/bus labels never carry a numeric
    suffix. On collision (two different names sharing the same first four
    letters, e.g. 'Riverside' / 'Rivenholt'), slide the 4-letter window
    further into the same name (letters only, across the full name — not
    just the first word — so short first words still have room to slide)
    until a free code is found. This keeps the code visibly derived from
    the real name rather than resorting to digits or an unrelated word.
    """
    all_letters = ''.join(ch for ch in name if ch.isalpha()).upper()
    if not all_letters:
        all_letters = 'GRID'
    padded = (all_letters + 'XXXX')

    for start in range(0, len(padded) - 3):
        candidate = padded[start:start + 4]
        if candidate not in used_labels:
            return candidate

    idx = len(used_labels)
    return f'X{idx:03d}'


def next_line_label(used_labels: set[str]) -> str:
    """Return the next line label (L01, L02, …)."""
    for i in range(1, 999):
        lbl = f'L{i:02d}'
        if lbl not in used_labels:
            return lbl
    return 'L999'
