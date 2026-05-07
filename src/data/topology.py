"""
src/data/topology.py

Complete 32-node transmission network definition for GRIDCOM.
Defines Bus and Line dataclasses plus all 38 buses (32 transmission +
6 load substations) and 29 transmission lines.

Canvas positions are in native 1920×844 pixels (the grid schematic area).
active_from_shift controls which shifts each element is available in:
  Shifts 1-2: 12 nodes (south sub-grid)
  Shifts 3-4: 20 nodes (south + centre)
  Shifts 5-10: 32 nodes (full grid)

See GRID_TOPOLOGY_AND_DISPLAY.md for visual specification.
See DOMAIN_GLOSSARY.md for bus type definitions.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Bus:
    """
    A node in the electrical network.

    Attributes:
        label:            4-char uppercase identifier (e.g. 'MDBY', 'CNTR')
        name:             Human-readable name for display
        voltage_kv:       Nominal voltage level (400, 220, 150, or 60)
        bus_type:         'TRANSMISSION' or 'LOAD' (60kV load substations)
        canvas_x:         X coordinate in native 1920×844 canvas pixels
        canvas_y:         Y coordinate in native 1920×844 canvas pixels
        active_from_shift: First shift in which this bus is active (1, 3, or 5)
        is_slack:         True only for MDBY (Midbury 400kV)
    """
    label:             str
    name:              str
    voltage_kv:        float
    bus_type:          str
    canvas_x:          int
    canvas_y:          int
    active_from_shift: int
    is_slack:          bool = False


@dataclass(frozen=True)
class Line:
    """
    A transmission line connecting two buses.

    Attributes:
        label:            Line identifier (e.g. 'L01')
        from_bus:         Label of the originating bus
        to_bus:           Label of the destination bus
        reactance_pu:     Series reactance in per-unit on S_BASE = 1000 MVA
        rating_mw:        Thermal rating in MW (100% = trip threshold)
        active_from_shift: First shift in which this line is active
        voltage_kv:       Voltage level (matches the higher-voltage endpoint)
    """
    label:             str
    from_bus:          str
    to_bus:            str
    reactance_pu:      float
    rating_mw:         float
    active_from_shift: int
    voltage_kv:        float


# ─────────────────────────────────────────────────────────────────────────────
# BUSES — 32 transmission nodes
#
# Layout philosophy:
#   400kV backbone:  y ≈ 120-280  (top tier)
#   220kV ring:      y ≈ 320-520  (middle tier)
#   150kV regional:  y ≈ 560-700  (lower-middle tier)
#   60kV loads:      y ≈ 740-800  (bottom tier)
#
# Horizontal spread: x ≈ 80 (west) to 1840 (east)
# ─────────────────────────────────────────────────────────────────────────────

BUSES: list[Bus] = [

    # ── 400kV BACKBONE (Shifts 5-10) ──────────────────────────────────────
    Bus(label='MDBY', name='Midbury',      voltage_kv=400.0, bus_type='TRANSMISSION',
        canvas_x=520,  canvas_y=160, active_from_shift=1, is_slack=True),

    Bus(label='CNTR', name='Centrefield',  voltage_kv=400.0, bus_type='TRANSMISSION',
        canvas_x=960,  canvas_y=120, active_from_shift=1),

    Bus(label='NRTH', name='Northgate',    voltage_kv=400.0, bus_type='TRANSMISSION',
        canvas_x=1400, canvas_y=160, active_from_shift=5),

    Bus(label='EAST', name='Eastmoor',     voltage_kv=400.0, bus_type='TRANSMISSION',
        canvas_x=1640, canvas_y=280, active_from_shift=3),

    Bus(label='WEST', name='Westham',      voltage_kv=400.0, bus_type='TRANSMISSION',
        canvas_x=280,  canvas_y=280, active_from_shift=3),

    Bus(label='STHW', name='Southwick',    voltage_kv=400.0, bus_type='TRANSMISSION',
        canvas_x=760,  canvas_y=280, active_from_shift=1),

    # ── 220kV RING — South sub-grid (Shifts 1-2) ─────────────────────────
    Bus(label='ASHF', name='Ashford',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=640,  canvas_y=400, active_from_shift=1),

    Bus(label='WRNT', name='Wrentham',     voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1080, canvas_y=400, active_from_shift=1),

    Bus(label='RDST', name='Redstone',     voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=360,  canvas_y=500, active_from_shift=1),

    Bus(label='FAIR', name='Fairfield',    voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=860,  canvas_y=480, active_from_shift=1),

    Bus(label='COAL', name='Coalton',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1280, canvas_y=460, active_from_shift=1),

    Bus(label='DUNM', name='Dunmore',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=520,  canvas_y=520, active_from_shift=1),

    # ── 220kV — Centre expansion (Shifts 3-4) ────────────────────────────
    Bus(label='KELM', name='Kelmore',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=160,  canvas_y=360, active_from_shift=3),

    Bus(label='BARR', name='Barrow',       voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1560, canvas_y=360, active_from_shift=3),

    Bus(label='WNCN', name='Cairn Wind',   voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1760, canvas_y=420, active_from_shift=3),

    Bus(label='SLST', name='Stanton Solar',voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1160, canvas_y=520, active_from_shift=3),

    Bus(label='ASHG', name='Ashford CCGT', voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=680,  canvas_y=340, active_from_shift=3),

    Bus(label='WRNG', name='Wrentham CCGT',voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1180, canvas_y=340, active_from_shift=3),

    # ── 150kV REGIONAL (Shifts 5-10) ─────────────────────────────────────
    Bus(label='BRCK', name='Brackley',     voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=240,  canvas_y=580, active_from_shift=5),

    Bus(label='STAN', name='Stanton',      voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=1080, canvas_y=580, active_from_shift=5),

    Bus(label='FLDN', name='Feldon',       voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=1480, canvas_y=580, active_from_shift=5),

    # ── RUN-OF-RIVER CASCADE NODES (Shifts 5-10) ─────────────────────────
    # River Arden (220kV)
    Bus(label='AR01', name='Arden 1',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=440,  canvas_y=620, active_from_shift=5),

    Bus(label='AR02', name='Arden 2',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=540,  canvas_y=660, active_from_shift=5),

    Bus(label='AR03', name='Arden 3',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=640,  canvas_y=700, active_from_shift=5),

    Bus(label='AR04', name='Arden 4',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=740,  canvas_y=660, active_from_shift=5),

    # River Brent (150kV)
    Bus(label='BR01', name='Brent 1',      voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=300,  canvas_y=640, active_from_shift=5),

    Bus(label='BR02', name='Brent 2',      voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=200,  canvas_y=680, active_from_shift=5),

    Bus(label='BR03', name='Brent 3',      voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=140,  canvas_y=720, active_from_shift=5),

    # River Coln (150kV)
    Bus(label='CO01', name='Coln 1',       voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=1360, canvas_y=640, active_from_shift=5),

    Bus(label='CO02', name='Coln 2',       voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=1460, canvas_y=680, active_from_shift=5),

    Bus(label='CO03', name='Coln 3',       voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=1540, canvas_y=720, active_from_shift=5),

    # ── DOWNSTREAM HYDRO (220kV, Shifts 1-2 / 3-4) ───────────────────────
    Bus(label='BARD', name='Barrow Lower', voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1680, canvas_y=460, active_from_shift=3),

    Bus(label='KELD', name='Kelmore Lower',voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=120,  canvas_y=460, active_from_shift=3),

    Bus(label='DUND', name='Dunmore Lower',voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=460,  canvas_y=560, active_from_shift=1),

    # ── 60kV LOAD SUBSTATIONS (Shifts 1-2) ───────────────────────────────
    Bus(label='LD01', name='Load Sub 1',   voltage_kv=60.0, bus_type='LOAD',
        canvas_x=480,  canvas_y=760, active_from_shift=1),

    Bus(label='LD02', name='Load Sub 2',   voltage_kv=60.0, bus_type='LOAD',
        canvas_x=720,  canvas_y=780, active_from_shift=1),

    Bus(label='LD03', name='Load Sub 3',   voltage_kv=60.0, bus_type='LOAD',
        canvas_x=960,  canvas_y=760, active_from_shift=1),

    Bus(label='LD04', name='Load Sub 4',   voltage_kv=60.0, bus_type='LOAD',
        canvas_x=1200, canvas_y=780, active_from_shift=1),

    Bus(label='LD05', name='Load Sub 5',   voltage_kv=60.0, bus_type='LOAD',
        canvas_x=1440, canvas_y=760, active_from_shift=1),

    Bus(label='LD06', name='Load Sub 6',   voltage_kv=60.0, bus_type='LOAD',
        canvas_x=240,  canvas_y=760, active_from_shift=3),
]


# ─────────────────────────────────────────────────────────────────────────────
# LINES — 29 transmission lines
#
# Reactance values are in per-unit on S_BASE = 1000 MVA.
# Typical values: 400kV long = 0.05-0.10 pu, 220kV = 0.08-0.15 pu, 150kV = 0.12-0.20 pu
# Ratings reflect thermal limits appropriate to voltage level and line length.
# ─────────────────────────────────────────────────────────────────────────────

LINES: list[Line] = [

    # ── 400kV BACKBONE ────────────────────────────────────────────────────
    Line(label='L01', from_bus='MDBY', to_bus='CNTR',
         reactance_pu=0.050, rating_mw=2000.0, active_from_shift=5, voltage_kv=400.0),

    Line(label='L02', from_bus='CNTR', to_bus='NRTH',
         reactance_pu=0.055, rating_mw=1800.0, active_from_shift=5, voltage_kv=400.0),

    Line(label='L03', from_bus='NRTH', to_bus='EAST',
         reactance_pu=0.040, rating_mw=2000.0, active_from_shift=5, voltage_kv=400.0),

    Line(label='L04', from_bus='MDBY', to_bus='WEST',
         reactance_pu=0.045, rating_mw=1800.0, active_from_shift=5, voltage_kv=400.0),

    Line(label='L05', from_bus='WEST', to_bus='STHW',
         reactance_pu=0.050, rating_mw=1600.0, active_from_shift=5, voltage_kv=400.0),

    Line(label='L06', from_bus='STHW', to_bus='CNTR',
         reactance_pu=0.045, rating_mw=1800.0, active_from_shift=5, voltage_kv=400.0),

    Line(label='L07', from_bus='EAST', to_bus='STHW',
         reactance_pu=0.060, rating_mw=1600.0, active_from_shift=5, voltage_kv=400.0),

    # ── 400kV ↔ 220kV TRANSFORMER LINKS (modelled as low-reactance lines) ─
    Line(label='L08', from_bus='STHW', to_bus='ASHF',
         reactance_pu=0.020, rating_mw=1200.0, active_from_shift=1, voltage_kv=400.0),

    Line(label='L09', from_bus='CNTR', to_bus='WRNT',
         reactance_pu=0.020, rating_mw=1200.0, active_from_shift=1, voltage_kv=400.0),

    Line(label='L10', from_bus='NRTH', to_bus='COAL',
         reactance_pu=0.022, rating_mw=1000.0, active_from_shift=5, voltage_kv=400.0),

    Line(label='L11', from_bus='WEST', to_bus='RDST',
         reactance_pu=0.022, rating_mw=1000.0, active_from_shift=3, voltage_kv=400.0),

    # ── 220kV SOUTH SUB-GRID (Shifts 1-2) ────────────────────────────────
    Line(label='L12', from_bus='ASHF', to_bus='FAIR',
         reactance_pu=0.090, rating_mw=800.0, active_from_shift=1, voltage_kv=220.0),

    Line(label='L13', from_bus='FAIR', to_bus='WRNT',
         reactance_pu=0.095, rating_mw=800.0, active_from_shift=1, voltage_kv=220.0),

    Line(label='L14', from_bus='ASHF', to_bus='DUNM',
         reactance_pu=0.100, rating_mw=700.0, active_from_shift=1, voltage_kv=220.0),

    Line(label='L15', from_bus='DUNM', to_bus='RDST',
         reactance_pu=0.110, rating_mw=600.0, active_from_shift=1, voltage_kv=220.0),

    Line(label='L16', from_bus='WRNT', to_bus='COAL',
         reactance_pu=0.085, rating_mw=800.0, active_from_shift=1, voltage_kv=220.0),

    # ── 220kV CENTRE EXPANSION (Shifts 3-4) ──────────────────────────────
    Line(label='L17', from_bus='RDST', to_bus='KELM',
         reactance_pu=0.120, rating_mw=600.0, active_from_shift=3, voltage_kv=220.0),

    Line(label='L18', from_bus='COAL', to_bus='BARR',
         reactance_pu=0.100, rating_mw=700.0, active_from_shift=3, voltage_kv=220.0),

    Line(label='L19', from_bus='FAIR', to_bus='SLST',
         reactance_pu=0.095, rating_mw=700.0, active_from_shift=3, voltage_kv=220.0),

    Line(label='L20', from_bus='WRNT', to_bus='WRNG',
         reactance_pu=0.030, rating_mw=900.0, active_from_shift=3, voltage_kv=220.0),

    Line(label='L21', from_bus='ASHF', to_bus='ASHG',
         reactance_pu=0.025, rating_mw=900.0, active_from_shift=3, voltage_kv=220.0),

    # ── 150kV REGIONAL (Shifts 5-10) ─────────────────────────────────────
    Line(label='L22', from_bus='RDST', to_bus='BRCK',
         reactance_pu=0.150, rating_mw=450.0, active_from_shift=5, voltage_kv=150.0),

    Line(label='L23', from_bus='FAIR', to_bus='STAN',
         reactance_pu=0.140, rating_mw=450.0, active_from_shift=5, voltage_kv=150.0),

    Line(label='L24', from_bus='COAL', to_bus='FLDN',
         reactance_pu=0.145, rating_mw=400.0, active_from_shift=5, voltage_kv=150.0),

    # ── 150kV ↔ RIVER CASCADE FEEDERS (Shifts 5-10) ──────────────────────
    Line(label='L25', from_bus='BRCK', to_bus='BR01',
         reactance_pu=0.160, rating_mw=350.0, active_from_shift=5, voltage_kv=150.0),

    Line(label='L26', from_bus='STAN', to_bus='AR04',
         reactance_pu=0.130, rating_mw=400.0, active_from_shift=5, voltage_kv=150.0),

    Line(label='L27', from_bus='FLDN', to_bus='CO01',
         reactance_pu=0.155, rating_mw=350.0, active_from_shift=5, voltage_kv=150.0),

    # ── DOWNSTREAM HYDRO CONNECTIONS ─────────────────────────────────────
    Line(label='L28', from_bus='DUNM', to_bus='DUND',
         reactance_pu=0.080, rating_mw=200.0, active_from_shift=1, voltage_kv=220.0),

    Line(label='L29', from_bus='SLST', to_bus='STAN',
         reactance_pu=0.075, rating_mw=500.0, active_from_shift=5, voltage_kv=220.0),
]


# ─────────────────────────────────────────────────────────────────────────────
# INTERCONNECTOR CANVAS POSITIONS
# These are display-only markers, not part of the electrical network topology.
# ─────────────────────────────────────────────────────────────────────────────

INTERCONNECTOR_POSITIONS: dict[str, tuple[int, int]] = {
    'INTC-N': (1840, 120),  # Top-right corner — north interconnector
    'INTC-S': (1840, 300),  # Right side — south interconnector
}


# ─────────────────────────────────────────────────────────────────────────────
# LOOKUP HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_buses_by_shift(shift_number: int) -> list[Bus]:
    """Return all buses active in the given shift number."""
    return [b for b in BUSES if b.active_from_shift <= shift_number]


def get_lines_by_shift(shift_number: int) -> list[Line]:
    """Return all lines active in the given shift number."""
    return [l for l in LINES if l.active_from_shift <= shift_number]


def get_bus(label: str) -> Bus:
    """Return bus by label. Raises KeyError if not found."""
    for b in BUSES:
        if b.label == label:
            return b
    raise KeyError(f"Bus not found: {label!r}")


def get_line(label: str) -> Line:
    """Return line by label. Raises KeyError if not found."""
    for l in LINES:
        if l.label == label:
            return l
    raise KeyError(f"Line not found: {label!r}")
