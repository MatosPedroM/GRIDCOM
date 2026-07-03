"""
src/data/topology.py

Complete network definition for GRIDCOM.
Defines Bus and Line dataclasses plus all 36 buses (30 transmission +
6 load substations) and 50 transmission lines.

Grid structure (Portuguese-grid inspired):
  400kV: one west→east spine (WEST-MDBY-STHW-CNTR-NRTH-EAST) with double
         circuits on the two middle segments and a southern sag line
         (STHW-EAST) — the system backbone.
  220kV: three regional pockets — a meshed capital ring (ASHF/FAIR/WRNT),
         a west hydro pocket with the River Arden collector string, and an
         east pocket (COAL hub, wind, solar).
  150kV: two meshed sub-transmission rings whose members INCLUDE the load
         substations (a feeder trip reroutes flow instead of blacking out),
         plus the River Brent and River Coln radial cascade strings.

Canvas positions are in native 1920×844 pixels (the grid schematic area).
active_from_shift controls which shifts each element is available in:
  Shift 1:      3 buses,  2 lines  (tutorial: MDBY/DUND/LD01)
  Shift 2:      4 buses,  3 lines  (+LD02; RVSD coal added, AGC tutorial)
  Shift 3:     10 buses, 11 lines  (capital ring, N-1 lesson)
  Shift 4:     16 buses, 21 lines  (+south 150kV mesh, Brent string)
  Shift 5:     23 buses, 30 lines  (+west hydro pocket, Arden string)
  Shift 6:     27 buses, 34 lines  (+north spine, COAL hub, wind, INTC-N)
  Shift 7:     36 buses, 47 lines  (+east region, solar, Coln, INTC-S)
  Shift 8-10:  36 buses, 50 lines  (+second circuits and southern sag)

All lines have active_until_shift=99 (effectively permanent). Tutorial
feeders L49/L50 are part of the permanent topology; their per-shift
electrical state is controlled by MAINTENANCE_LINES in each shift file
(L50 opens from Shift 3, L49 from Shift 4, when the 150kV mesh takes over).

See GRID_TOPOLOGY_AND_DISPLAY.md for visual specification.
See DOMAIN_GLOSSARY.md for bus type definitions.
"""

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Bus:
    """
    A node in the electrical network.

    Attributes:
        label:            4-char uppercase identifier (e.g. 'MDBY', 'CNTR')
        name:             Human-readable name for display
        voltage_kv:       Nominal voltage level (400, 220, 150, or 60)
        bus_type:         'TRANSMISSION' or 'LOAD' (150kV load substations)
        canvas_x:         X coordinate in native 1920×844 canvas pixels
        canvas_y:         Y coordinate in native 1920×844 canvas pixels
        active_from_shift: First shift in which this bus is active
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
        label:             Line identifier (e.g. 'L01')
        from_bus:          Label of the originating bus
        to_bus:            Label of the destination bus
        reactance_pu:      Series reactance in per-unit on S_BASE = 1000 MVA
        rating_mw:         Thermal rating in MW (100% = trip threshold)
        active_from_shift: First shift in which this line is active
        active_until_shift: Last shift in which this line is active (99 = permanent)
        voltage_kv:        Voltage level (matches the higher-voltage endpoint)
        parallel:          Perpendicular draw offset direction for double-circuit
                           pairs (+1 / -1); 0 for single-circuit lines. Display
                           only — has no electrical meaning.
    """
    label:              str
    from_bus:           str
    to_bus:             str
    reactance_pu:       float
    rating_mw:          float
    active_from_shift:  int
    voltage_kv:         float
    active_until_shift: int = 99
    parallel:           int = 0


# ─────────────────────────────────────────────────────────────────────────────
# BUSES — 30 transmission nodes + 6 load substations
#
# Layout philosophy:
#   400kV spine:      y ≈ 140  (one horizontal corridor across the top)
#   220kV pockets:    y ≈ 300-560  (middle band)
#   150kV meshes:     y ≈ 540-770  (lower band; load subs are ring members)
#
# Horizontal regions: west hydro (x < 600), capital (600-1250), east (> 1250)
# ─────────────────────────────────────────────────────────────────────────────

BUSES: list[Bus] = [

    # ── 400kV SPINE (west → east) ─────────────────────────────────────────
    # Shift 1: MDBY  |  Shift 3: STHW, CNTR  |  Shift 5: WEST
    # Shift 6: NRTH  |  Shift 7: EAST
    Bus(label='WEST', name='Westham',      voltage_kv=400.0, bus_type='TRANSMISSION',
        canvas_x=180,  canvas_y=140, active_from_shift=5),

    Bus(label='MDBY', name='Midbury',      voltage_kv=400.0, bus_type='TRANSMISSION',
        canvas_x=480,  canvas_y=140, active_from_shift=1, is_slack=True),

    Bus(label='STHW', name='Southwick',    voltage_kv=400.0, bus_type='TRANSMISSION',
        canvas_x=800,  canvas_y=140, active_from_shift=3),

    Bus(label='CNTR', name='Centrefield',  voltage_kv=400.0, bus_type='TRANSMISSION',
        canvas_x=1120, canvas_y=140, active_from_shift=3),

    Bus(label='NRTH', name='Northgate',    voltage_kv=400.0, bus_type='TRANSMISSION',
        canvas_x=1420, canvas_y=140, active_from_shift=6),

    Bus(label='EAST', name='Eastmoor',     voltage_kv=400.0, bus_type='TRANSMISSION',
        canvas_x=1700, canvas_y=140, active_from_shift=7),

    # ── 220kV CAPITAL RING ────────────────────────────────────────────────
    # Anchored at two spine substations (STHW via ASHF, CNTR via WRNT).
    Bus(label='ASHF', name='Ashford',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=880,  canvas_y=320, active_from_shift=3),

    Bus(label='FAIR', name='Fairfield',    voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1020, canvas_y=440, active_from_shift=3),

    Bus(label='WRNT', name='Wrentham',     voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1180, canvas_y=320, active_from_shift=3),

    Bus(label='DUNM', name='Dunmore',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=700,  canvas_y=440, active_from_shift=4),

    # ── 220kV WEST HYDRO POCKET ───────────────────────────────────────────
    # DUND is the Shift 1 tutorial bus (Dunmore lower, hydraulically fed
    # from DUNH at MDBY). The Arden string DUND→AR01..AR04→DUNM is a
    # cascade collector tied at both ends (radial-looking, electrically a loop).
    Bus(label='DUND', name='Dunmore Lower',voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=560,  canvas_y=340, active_from_shift=1),

    Bus(label='RDST', name='Redstone',     voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=280,  canvas_y=340, active_from_shift=5),

    Bus(label='KELD', name='Kelmore Lower',voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=140,  canvas_y=460, active_from_shift=5),

    Bus(label='AR01', name='Arden 1',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=480,  canvas_y=440, active_from_shift=5),

    Bus(label='AR02', name='Arden 2',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=420,  canvas_y=520, active_from_shift=5),

    Bus(label='AR03', name='Arden 3',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=480,  canvas_y=600, active_from_shift=5),

    Bus(label='AR04', name='Arden 4',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=580,  canvas_y=560, active_from_shift=5),

    # ── 220kV EAST POCKET ─────────────────────────────────────────────────
    Bus(label='COAL', name='Coalton',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1420, canvas_y=300, active_from_shift=6),

    Bus(label='BARD', name='Barrow Lower', voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1560, canvas_y=440, active_from_shift=6),

    Bus(label='WNCN', name='Cairn Wind',   voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1300, canvas_y=460, active_from_shift=6),

    Bus(label='SLST', name='Stanton Solar',voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1660, canvas_y=360, active_from_shift=7),

    # ── 150kV SOUTH MESH (capital sub-transmission) ───────────────────────
    # Ring: STAN-LD01-BRCK-LD02-STAN, fed at STAN (from ASHF) and BRCK
    # (from DUNM). LD03 spurs off STAN with a back-tie to LD02.
    Bus(label='STAN', name='Stanton',      voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=1040, canvas_y=620, active_from_shift=3),

    Bus(label='BRCK', name='Brackley',     voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=760,  canvas_y=620, active_from_shift=4),

    # River Brent cascade string (radial, off BRCK)
    Bus(label='BR01', name='Brent 1',      voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=640,  canvas_y=680, active_from_shift=4),

    Bus(label='BR02', name='Brent 2',      voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=560,  canvas_y=720, active_from_shift=4),

    Bus(label='BR03', name='Brent 3',      voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=480,  canvas_y=760, active_from_shift=4),

    # ── 150kV EAST MESH ───────────────────────────────────────────────────
    # Ring: FLDN-LD04-LD05-LD06-FLDN, fed at FLDN (from COAL) and LD06
    # (from SLST).
    Bus(label='FLDN', name='Feldon',       voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=1500, canvas_y=580, active_from_shift=7),

    # River Coln cascade string (radial, off FLDN)
    Bus(label='CO01', name='Coln 1',       voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=1300, canvas_y=600, active_from_shift=7),

    Bus(label='CO02', name='Coln 2',       voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=1240, canvas_y=660, active_from_shift=7),

    Bus(label='CO03', name='Coln 3',       voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=1180, canvas_y=720, active_from_shift=7),

    # ── 150kV LOAD SUBSTATIONS (mesh ring members) ───────────────────────
    Bus(label='LD01', name='Load Sub 1',   voltage_kv=150.0, bus_type='LOAD',
        canvas_x=900,  canvas_y=700, active_from_shift=1),

    Bus(label='LD02', name='Load Sub 2',   voltage_kv=150.0, bus_type='LOAD',
        canvas_x=900,  canvas_y=560, active_from_shift=2),

    Bus(label='LD03', name='Load Sub 3',   voltage_kv=150.0, bus_type='LOAD',
        canvas_x=1040, canvas_y=720, active_from_shift=4),

    Bus(label='LD04', name='Load Sub 4',   voltage_kv=150.0, bus_type='LOAD',
        canvas_x=1400, canvas_y=680, active_from_shift=7),

    Bus(label='LD05', name='Load Sub 5',   voltage_kv=150.0, bus_type='LOAD',
        canvas_x=1500, canvas_y=740, active_from_shift=7),

    Bus(label='LD06', name='Load Sub 6',   voltage_kv=150.0, bus_type='LOAD',
        canvas_x=1640, canvas_y=660, active_from_shift=7),
]


# ─────────────────────────────────────────────────────────────────────────────
# LINES — 50 transmission lines
#
# Reactance values are in per-unit on S_BASE = 1000 MVA.
# Typical values: 400kV = 0.04-0.08 pu, 220kV = 0.09-0.15 pu,
# 150kV = 0.10-0.17 pu, transformer links = 0.020-0.040 pu.
# Ratings reflect thermal limits appropriate to voltage level and role.
# ─────────────────────────────────────────────────────────────────────────────

LINES: list[Line] = [

    # ── 400kV SPINE ───────────────────────────────────────────────────────
    Line(label='L01', from_bus='WEST', to_bus='MDBY',
         reactance_pu=0.050, rating_mw=1600.0, active_from_shift=5, voltage_kv=400.0),

    # Double circuit MDBY↔STHW: circuit 1 from Shift 3, circuit 2 from Shift 8.
    Line(label='L02', from_bus='MDBY', to_bus='STHW',
         reactance_pu=0.045, rating_mw=1400.0, active_from_shift=3, voltage_kv=400.0,
         parallel=+1),

    Line(label='L03', from_bus='MDBY', to_bus='STHW',
         reactance_pu=0.045, rating_mw=1400.0, active_from_shift=8, voltage_kv=400.0,
         parallel=-1),

    # Double circuit STHW↔CNTR: circuit 1 from Shift 3, circuit 2 from Shift 8.
    Line(label='L04', from_bus='STHW', to_bus='CNTR',
         reactance_pu=0.045, rating_mw=1400.0, active_from_shift=3, voltage_kv=400.0,
         parallel=+1),

    Line(label='L05', from_bus='STHW', to_bus='CNTR',
         reactance_pu=0.045, rating_mw=1400.0, active_from_shift=8, voltage_kv=400.0,
         parallel=-1),

    Line(label='L06', from_bus='CNTR', to_bus='NRTH',
         reactance_pu=0.055, rating_mw=1600.0, active_from_shift=6, voltage_kv=400.0),

    Line(label='L07', from_bus='NRTH', to_bus='EAST',
         reactance_pu=0.045, rating_mw=1600.0, active_from_shift=7, voltage_kv=400.0),

    # Southern sag — long 400kV loop closure, energised Shift 8.
    Line(label='L08', from_bus='STHW', to_bus='EAST',
         reactance_pu=0.080, rating_mw=1200.0, active_from_shift=8, voltage_kv=400.0),

    # ── 400kV ↔ 220kV TRANSFORMER LINKS (modelled as low-reactance lines) ─
    Line(label='L09', from_bus='STHW', to_bus='ASHF',
         reactance_pu=0.020, rating_mw=1200.0, active_from_shift=3, voltage_kv=400.0),

    Line(label='L10', from_bus='CNTR', to_bus='WRNT',
         reactance_pu=0.020, rating_mw=1200.0, active_from_shift=3, voltage_kv=400.0),

    Line(label='L11', from_bus='MDBY', to_bus='DUND',
         reactance_pu=0.025, rating_mw=500.0, active_from_shift=1, voltage_kv=400.0),

    Line(label='L12', from_bus='WEST', to_bus='RDST',
         reactance_pu=0.022, rating_mw=1000.0, active_from_shift=5, voltage_kv=400.0),

    Line(label='L13', from_bus='NRTH', to_bus='COAL',
         reactance_pu=0.022, rating_mw=1000.0, active_from_shift=6, voltage_kv=400.0),

    Line(label='L14', from_bus='EAST', to_bus='SLST',
         reactance_pu=0.022, rating_mw=900.0, active_from_shift=7, voltage_kv=400.0),

    # ── 220kV CAPITAL RING ────────────────────────────────────────────────
    Line(label='L15', from_bus='ASHF', to_bus='FAIR',
         reactance_pu=0.090, rating_mw=800.0, active_from_shift=3, voltage_kv=220.0),

    Line(label='L16', from_bus='FAIR', to_bus='WRNT',
         reactance_pu=0.095, rating_mw=800.0, active_from_shift=3, voltage_kv=220.0),

    Line(label='L17', from_bus='ASHF', to_bus='DUNM',
         reactance_pu=0.100, rating_mw=700.0, active_from_shift=4, voltage_kv=220.0),

    # ── 220kV WEST HYDRO POCKET ───────────────────────────────────────────
    # Arden collector string DUND→AR01→AR02→AR03→AR04→DUNM (looped both ends).
    Line(label='L18', from_bus='AR04', to_bus='DUNM',
         reactance_pu=0.130, rating_mw=400.0, active_from_shift=5, voltage_kv=220.0),

    Line(label='L19', from_bus='RDST', to_bus='KELD',
         reactance_pu=0.120, rating_mw=500.0, active_from_shift=5, voltage_kv=220.0),

    Line(label='L20', from_bus='DUND', to_bus='AR01',
         reactance_pu=0.140, rating_mw=400.0, active_from_shift=5, voltage_kv=220.0),

    Line(label='L21', from_bus='AR01', to_bus='AR02',
         reactance_pu=0.150, rating_mw=350.0, active_from_shift=5, voltage_kv=220.0),

    Line(label='L22', from_bus='AR02', to_bus='AR03',
         reactance_pu=0.150, rating_mw=350.0, active_from_shift=5, voltage_kv=220.0),

    Line(label='L23', from_bus='AR03', to_bus='AR04',
         reactance_pu=0.140, rating_mw=350.0, active_from_shift=5, voltage_kv=220.0),

    # West↔capital 220kV tie (second path out of the west pocket).
    Line(label='L27', from_bus='RDST', to_bus='DUNM',
         reactance_pu=0.140, rating_mw=500.0, active_from_shift=5, voltage_kv=220.0),

    # ── 220kV EAST POCKET ─────────────────────────────────────────────────
    Line(label='L24', from_bus='COAL', to_bus='BARD',
         reactance_pu=0.100, rating_mw=600.0, active_from_shift=6, voltage_kv=220.0),

    # Cairn Wind single collector feeder — its loading IS the wind gameplay.
    Line(label='L25', from_bus='COAL', to_bus='WNCN',
         reactance_pu=0.090, rating_mw=600.0, active_from_shift=6, voltage_kv=220.0),

    # East↔capital 220kV tie (meshes the east pocket into the ring).
    Line(label='L26', from_bus='SLST', to_bus='WRNT',
         reactance_pu=0.130, rating_mw=700.0, active_from_shift=7, voltage_kv=220.0),

    # East pocket loop closure.
    Line(label='L28', from_bus='BARD', to_bus='SLST',
         reactance_pu=0.110, rating_mw=400.0, active_from_shift=7, voltage_kv=220.0),

    # ── 220kV ↔ 150kV TRANSFORMER LINKS ──────────────────────────────────
    Line(label='L29', from_bus='ASHF', to_bus='STAN',
         reactance_pu=0.030, rating_mw=1200.0, active_from_shift=3, voltage_kv=220.0),

    Line(label='L30', from_bus='DUNM', to_bus='BRCK',
         reactance_pu=0.035, rating_mw=600.0, active_from_shift=4, voltage_kv=220.0),

    Line(label='L31', from_bus='COAL', to_bus='FLDN',
         reactance_pu=0.035, rating_mw=700.0, active_from_shift=7, voltage_kv=220.0),

    Line(label='L32', from_bus='SLST', to_bus='LD06',
         reactance_pu=0.040, rating_mw=600.0, active_from_shift=7, voltage_kv=220.0),

    # ── 150kV SOUTH MESH ─────────────────────────────────────────────────
    # L33 is LD02's sole feed in Shift 3 (ring closes in Shift 4).
    Line(label='L33', from_bus='STAN', to_bus='LD02',
         reactance_pu=0.110, rating_mw=1100.0, active_from_shift=3, voltage_kv=150.0),

    Line(label='L34', from_bus='STAN', to_bus='LD01',
         reactance_pu=0.120, rating_mw=450.0, active_from_shift=4, voltage_kv=150.0),

    Line(label='L35', from_bus='LD01', to_bus='BRCK',
         reactance_pu=0.120, rating_mw=450.0, active_from_shift=4, voltage_kv=150.0),

    Line(label='L36', from_bus='BRCK', to_bus='LD02',
         reactance_pu=0.130, rating_mw=450.0, active_from_shift=4, voltage_kv=150.0),

    Line(label='L37', from_bus='STAN', to_bus='LD03',
         reactance_pu=0.100, rating_mw=400.0, active_from_shift=4, voltage_kv=150.0),

    Line(label='L38', from_bus='LD03', to_bus='LD02',
         reactance_pu=0.140, rating_mw=300.0, active_from_shift=4, voltage_kv=150.0),

    # River Brent cascade string
    Line(label='L39', from_bus='BRCK', to_bus='BR01',
         reactance_pu=0.150, rating_mw=300.0, active_from_shift=4, voltage_kv=150.0),

    Line(label='L40', from_bus='BR01', to_bus='BR02',
         reactance_pu=0.160, rating_mw=250.0, active_from_shift=4, voltage_kv=150.0),

    Line(label='L41', from_bus='BR02', to_bus='BR03',
         reactance_pu=0.170, rating_mw=200.0, active_from_shift=4, voltage_kv=150.0),

    # ── 150kV EAST MESH ──────────────────────────────────────────────────
    Line(label='L42', from_bus='FLDN', to_bus='LD04',
         reactance_pu=0.120, rating_mw=450.0, active_from_shift=7, voltage_kv=150.0),

    Line(label='L43', from_bus='LD04', to_bus='LD05',
         reactance_pu=0.130, rating_mw=400.0, active_from_shift=7, voltage_kv=150.0),

    Line(label='L44', from_bus='LD05', to_bus='LD06',
         reactance_pu=0.130, rating_mw=400.0, active_from_shift=7, voltage_kv=150.0),

    Line(label='L45', from_bus='LD06', to_bus='FLDN',
         reactance_pu=0.120, rating_mw=450.0, active_from_shift=7, voltage_kv=150.0),

    # River Coln cascade string
    Line(label='L46', from_bus='FLDN', to_bus='CO01',
         reactance_pu=0.150, rating_mw=300.0, active_from_shift=7, voltage_kv=150.0),

    Line(label='L47', from_bus='CO01', to_bus='CO02',
         reactance_pu=0.160, rating_mw=250.0, active_from_shift=7, voltage_kv=150.0),

    Line(label='L48', from_bus='CO02', to_bus='CO03',
         reactance_pu=0.170, rating_mw=200.0, active_from_shift=7, voltage_kv=150.0),

    # ── TUTORIAL FEEDERS (permanent) ─────────────────────────────────────
    # DUND feeds the load substations directly in Shifts 1-3. These lines
    # are electrically permanent; from Shift 3 (L50) and Shift 4 (L49) they
    # start in MAINTENANCE state (defined per shift file) once the 150kV
    # mesh takes over the load.
    Line(label='L49', from_bus='DUND', to_bus='LD01',
         reactance_pu=0.080, rating_mw=500.0, active_from_shift=1, voltage_kv=220.0),

    Line(label='L50', from_bus='DUND', to_bus='LD02',
         reactance_pu=0.080, rating_mw=400.0, active_from_shift=2, voltage_kv=220.0),
]


# ─────────────────────────────────────────────────────────────────────────────
# INTERCONNECTOR CANVAS POSITIONS
# These are display-only markers, not part of the electrical network topology.
# Both sit on the eastern border (the neighbouring system).
# ─────────────────────────────────────────────────────────────────────────────

INTERCONNECTOR_POSITIONS: dict[str, tuple[int, int]] = {
    'INTC-N': (1860, 100),  # Top-right — north interconnector (off NRTH)
    'INTC-S': (1860, 200),  # Right side — south interconnector (off EAST)
}


# ─────────────────────────────────────────────────────────────────────────────
# LOOKUP HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_buses_by_shift(shift_number: int) -> list[Bus]:
    """Return all buses active in the given shift number, with layout overrides applied."""
    from data.layout_override import get_bus_pos
    result = []
    for b in BUSES:
        if b.active_from_shift <= shift_number:
            x, y = get_bus_pos(b.label, b.canvas_x, b.canvas_y)
            if x != b.canvas_x or y != b.canvas_y:
                b = dataclasses.replace(b, canvas_x=x, canvas_y=y)
            result.append(b)
    return result


def get_lines_by_shift(shift_number: int) -> list[Line]:
    """Return all lines active in the given shift number."""
    return [l for l in LINES
            if l.active_from_shift <= shift_number <= l.active_until_shift]


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
