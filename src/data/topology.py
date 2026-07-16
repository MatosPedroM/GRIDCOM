"""
src/data/topology.py

Complete network definition for GRIDCOM.
Defines Bus and Line dataclasses plus all 36 buses (30 transmission +
6 load substations) and 50 transmission lines.

Grid structure (Portuguese-grid inspired), reorganised in Stage 28 into 6
regions that only connect to each other via the 400kV spine — no direct
lower-voltage tie bypasses the spine:
  SPINE:       400kV backbone, WEST-MDBY-STHW-CNTR-NRTH-EAST, with double
               circuits on the two middle segments and a southern sag line
               (STHW-EAST).
  CAP:         220kV capital ring (ASHF/FAIR/WRNT/DUNM), 3 spine taps
               (L09 from STHW to ASHF, L10 from CNTR to WRNT, L160 from
               STHW to FAIR — the extra tap added in Stage 29 so LD07's
               1988 MW merged load doesn't overload the ring under N-1).
  WEST:        220kV hydro pocket (DUND/RDST/KELD/AR01-04, River Arden
               cascade, loop-closed entirely within the region via L159),
               2 spine taps (L11 from MDBY, L12 from WEST).
  SOUTH-MESH:  220/150kV mesh (STAN/BRCK/LD01-03, River Brent cascade),
               2 spine taps (L155 from STHW, L156 from CNTR).
  EAST-POCKET: 220kV pocket (COAL/BARD/WNCN/SLST), 2 spine taps (L13 from
               NRTH, L14 from EAST).
  EAST-MESH:   220/150kV mesh (FLDN/CO01-03/LD04-06, River Coln cascade),
               2 spine taps (L157 from NRTH, L158 from EAST).

Canvas positions are in native 1920×844 pixels (the grid schematic area).
active_from_shift controls which shifts each element is available in:
  Shift 1:      3 buses,  2 lines  (tutorial: MDBY/DUND/LD01)
  Shift 2:      4 buses,  3 lines  (+LD02; RVSD coal added, AGC tutorial)
  Shift 3:     10 buses, 11 lines  (capital ring, N-1 lesson)
  Shift 4:     16 buses, 21 lines  (+south 150kV mesh, Brent string)
  Shift 5:     23 buses, 30 lines  (+west hydro pocket, Arden string)
  Shift 6:     27 buses, 34 lines  (+north spine, COAL hub, wind, INTC-N)
  Shift 7:     36 buses, 47 lines  (+east region, solar, Coln, INTC-S)
  Shift 8-9:   36 buses, 50 lines  (+second circuits and southern sag)
  Shift 10:    41 buses, 62 lines  (Stage 24-29: +5 consolidated load
               substations, one per non-SPINE region, each dual-fed from
               that region's own 2 spine-anchor buses, +1 ring
               reinforcement, +Brent/Coln loop closures, +4 new spine taps
               for SOUTH-MESH/EAST-MESH, +1 WEST-internal Arden loop
               closer, +1 third CAP spine tap for LD07's N-1 margin)

Note: STAN, BRCK, FLDN, and CO01 were promoted from 150kV to 220kV in
Stage 28 so SOUTH-MESH/EAST-MESH could each get their own pair of spine
taps. This is a permanent bus fact and therefore also affects Shifts 3-9
where these buses already appear — Shifts 1-9 scenario reconciliation is
tracked as follow-up, not fixed in Stage 28.

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

from simulation.constants import (
    LINE_RATING_MW_BY_VOLTAGE,
    GENERATOR_CONNECTOR_RATING_MW,
    CONSOLIDATED_FEED_RATING_MW_TRIPLE,
    CONSOLIDATED_FEED_RATING_MW_CAP,
    CONSOLIDATED_FEED_RATING_MW_WEST,
)

_R400 = LINE_RATING_MW_BY_VOLTAGE[400.0]
_R220 = LINE_RATING_MW_BY_VOLTAGE[220.0]
_R150 = LINE_RATING_MW_BY_VOLTAGE[150.0]
_RGEN = GENERATOR_CONNECTOR_RATING_MW
_RTRIPLE = CONSOLIDATED_FEED_RATING_MW_TRIPLE
_RCAP = CONSOLIDATED_FEED_RATING_MW_CAP
_RWEST = CONSOLIDATED_FEED_RATING_MW_WEST


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
    # RDST/KELD/AR01-04 were re-spaced in Stage 27 across a wider footprint
    # (previously packed into a ~300x320px box, violating the schematic's
    # own minimum node-spacing guidance) — DUND and DUNM stay fixed since
    # both anchor other regions (DUND is the Shift-1 tutorial bus, DUNM
    # anchors the capital ring).
    Bus(label='DUND', name='Dunmore Lower',voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=560,  canvas_y=340, active_from_shift=1),

    Bus(label='RDST', name='Redstone',     voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=100,  canvas_y=420, active_from_shift=5),

    Bus(label='KELD', name='Kelmore Lower',voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=40,   canvas_y=620, active_from_shift=5),

    Bus(label='AR01', name='Ardenbridge',  voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=280,  canvas_y=520, active_from_shift=5),

    Bus(label='AR02', name='Millhaven',    voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=400,  canvas_y=640, active_from_shift=5),

    Bus(label='AR03', name='Weirfield',    voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=560,  canvas_y=620, active_from_shift=5),

    Bus(label='AR04', name='Ardenmouth',   voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=700,  canvas_y=550, active_from_shift=5),

    # ── 220kV EAST POCKET ─────────────────────────────────────────────────
    Bus(label='COAL', name='Coalton',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1420, canvas_y=300, active_from_shift=6),

    Bus(label='BARD', name='Barrow Lower', voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1560, canvas_y=440, active_from_shift=6),

    Bus(label='WNCN', name='Cairn Wind',   voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1300, canvas_y=460, active_from_shift=6),

    Bus(label='SLST', name='Stanton Solar',voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1660, canvas_y=360, active_from_shift=7),

    # ── SOUTH MESH (its own region as of Stage 28 — see LINES below) ──────
    # Ring: STAN-LD01-BRCK-LD02-STAN. STAN and BRCK were promoted from
    # 150kV to 220kV in Stage 28 so this region can carry its own pair of
    # 400kV spine taps (L155/L156) instead of reaching the network only
    # through CAP's ASHF/DUNM buses — this is a permanent grid fact, so it
    # also affects Shifts 3-9 where these buses already appear (accepted
    # side effect, tracked as follow-up, not fixed this stage). LD03 spurs
    # off STAN with a back-tie to LD02.
    Bus(label='STAN', name='Stanton',      voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1040, canvas_y=620, active_from_shift=3),

    Bus(label='BRCK', name='Brackley',     voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=760,  canvas_y=620, active_from_shift=4),

    # River Brent cascade string (radial, off BRCK)
    Bus(label='BR01', name='Brentford',    voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=640,  canvas_y=680, active_from_shift=4),

    Bus(label='BR02', name='Brentwell',    voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=560,  canvas_y=720, active_from_shift=4),

    Bus(label='BR03', name='Brentmoor',    voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=480,  canvas_y=760, active_from_shift=4),

    # ── EAST MESH (its own region as of Stage 28 — see LINES below) ───────
    # Ring: FLDN-LD04-LD05-LD06-FLDN. FLDN and CO01 were promoted from
    # 150kV to 220kV in Stage 28 so this region can carry its own pair of
    # 400kV spine taps (L157/L158) instead of reaching the network only
    # through EAST-POCKET's COAL/SLST buses — accepted side effect for
    # Shifts 7-9 where these buses already appear, same as STAN/BRCK above.
    Bus(label='FLDN', name='Feldon',       voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1500, canvas_y=580, active_from_shift=7),

    # River Coln cascade string (radial, off FLDN)
    Bus(label='CO01', name='Colnbrook',    voltage_kv=220.0, bus_type='TRANSMISSION',
        canvas_x=1300, canvas_y=600, active_from_shift=7),

    Bus(label='CO02', name='Colnhurst',    voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=1240, canvas_y=660, active_from_shift=7),

    Bus(label='CO03', name='Colnstead',    voltage_kv=150.0, bus_type='TRANSMISSION',
        canvas_x=1180, canvas_y=720, active_from_shift=7),

    # ── 150kV LOAD SUBSTATIONS (mesh ring members) ───────────────────────
    Bus(label='LD01', name='Hallowmere',   voltage_kv=150.0, bus_type='LOAD',
        canvas_x=900,  canvas_y=700, active_from_shift=1),

    Bus(label='LD02', name='Pemberton',    voltage_kv=150.0, bus_type='LOAD',
        canvas_x=900,  canvas_y=560, active_from_shift=2),

    Bus(label='LD03', name='Thistledown',  voltage_kv=150.0, bus_type='LOAD',
        canvas_x=1040, canvas_y=720, active_from_shift=4),

    Bus(label='LD04', name='Elmscroft',    voltage_kv=150.0, bus_type='LOAD',
        canvas_x=1400, canvas_y=680, active_from_shift=7),

    Bus(label='LD05', name='Farringstone', voltage_kv=150.0, bus_type='LOAD',
        canvas_x=1500, canvas_y=740, active_from_shift=7),

    Bus(label='LD06', name='Rushbourne',   voltage_kv=150.0, bus_type='LOAD',
        canvas_x=1640, canvas_y=660, active_from_shift=7),

    # ── STAGE 24-29: SHIFT 10 CAPACITY EXPANSION ──────────────────────────
    # 5 consolidated load substations, one per non-SPINE region, each
    # dual-fed by two dedicated 220kV lines from that region's own two
    # spine-anchor buses (see LINES below). Active from Shift 10 only.
    # Stage 29 found that a region hosting 2+ substations off only its 2
    # spine-anchor buses overloads its internal 220/150kV ring under N-1
    # (verified for both CAP and WEST) — so each region now hosts exactly
    # ONE substation, sized to the region's full former multi-substation
    # demand, fed directly from its own anchor pair:
    #   LD07 (CAP: ASHF+FAIR, merged former LD07+LD08, 1988 MW)
    #   LD09 (WEST: DUND+RDST, merged former LD09+LD10+LD14, 2591 MW)
    #   LD11 (EAST-POCKET: COAL+BARD, 1035 MW, unchanged)
    #   LD12 (EAST-MESH: FLDN+CO01, 961 MW, unchanged)
    #   LD13 (SOUTH-MESH: STAN+BRCK, 1026 MW, unchanged)
    # Every substation's 2-bus source set is unique — no two substations
    # share a bus, so there is no shared-pair N-2-adjacent risk.
    Bus(label='LD07', name='Ottermead',    voltage_kv=150.0, bus_type='LOAD',
        canvas_x=880,  canvas_y=100, active_from_shift=10),
    Bus(label='LD09', name='Bramleigh',    voltage_kv=150.0, bus_type='LOAD',
        canvas_x=1180, canvas_y=100, active_from_shift=10),
    Bus(label='LD11', name='Hartsdene',    voltage_kv=150.0, bus_type='LOAD',
        canvas_x=480,  canvas_y=180, active_from_shift=10),
    Bus(label='LD12', name='Rowancroft',   voltage_kv=150.0, bus_type='LOAD',
        canvas_x=130,  canvas_y=220, active_from_shift=10),
    Bus(label='LD13', name='Wychmoor',     voltage_kv=150.0, bus_type='LOAD',
        canvas_x=50,   canvas_y=520, active_from_shift=10),
]


# ─────────────────────────────────────────────────────────────────────────────
# LINES — 43 permanent lines (Shifts 1-9) + 19 Shift-10-only lines (62 total)
#
# Reactance values are in per-unit on S_BASE = 1000 MVA.
# Typical values: 400kV = 0.04-0.08 pu, 220kV = 0.09-0.15 pu,
# 150kV = 0.10-0.17 pu, transformer links = 0.020-0.040 pu.
# Ratings reflect thermal limits appropriate to voltage level and role, except
# for a small set of pure generator-egress lines rated at the flat
# GENERATOR_CONNECTOR_RATING_MW instead — see the River Brent/Coln cascade
# strings and the RDST-KELD line below.
# ─────────────────────────────────────────────────────────────────────────────

LINES: list[Line] = [

    # ── 400kV SPINE ───────────────────────────────────────────────────────
    # All line ratings are flat per nominal voltage tier — see
    # LINE_RATING_MW_BY_VOLTAGE in simulation/constants.py. Individual role
    # (spine/tap/ring/cascade) no longer varies the rating, only reactance
    # and topology do.
    Line(label='L01', from_bus='WEST', to_bus='MDBY',
         reactance_pu=0.050, rating_mw=_R400, active_from_shift=5, voltage_kv=400.0),

    # Double circuit MDBY↔STHW: circuit 1 from Shift 3, circuit 2 from Shift 8.
    Line(label='L02', from_bus='MDBY', to_bus='STHW',
         reactance_pu=0.045, rating_mw=_R400, active_from_shift=3, voltage_kv=400.0,
         parallel=+1),

    Line(label='L03', from_bus='MDBY', to_bus='STHW',
         reactance_pu=0.045, rating_mw=_R400, active_from_shift=8, voltage_kv=400.0,
         parallel=-1),

    # Double circuit STHW↔CNTR: circuit 1 from Shift 3, circuit 2 from Shift 8.
    Line(label='L04', from_bus='STHW', to_bus='CNTR',
         reactance_pu=0.045, rating_mw=_R400, active_from_shift=3, voltage_kv=400.0,
         parallel=+1),

    Line(label='L05', from_bus='STHW', to_bus='CNTR',
         reactance_pu=0.045, rating_mw=_R400, active_from_shift=8, voltage_kv=400.0,
         parallel=-1),

    Line(label='L06', from_bus='CNTR', to_bus='NRTH',
         reactance_pu=0.055, rating_mw=_R400, active_from_shift=6, voltage_kv=400.0),

    Line(label='L07', from_bus='NRTH', to_bus='EAST',
         reactance_pu=0.045, rating_mw=_R400, active_from_shift=7, voltage_kv=400.0),

    # Southern sag — long 400kV loop closure, energised Shift 8.
    Line(label='L08', from_bus='STHW', to_bus='EAST',
         reactance_pu=0.080, rating_mw=_R400, active_from_shift=8, voltage_kv=400.0),

    # ── 400kV ↔ 220kV TRANSFORMER LINKS (modelled as low-reactance lines) ─
    Line(label='L09', from_bus='STHW', to_bus='ASHF',
         reactance_pu=0.020, rating_mw=_R400, active_from_shift=3, voltage_kv=400.0),

    Line(label='L10', from_bus='CNTR', to_bus='WRNT',
         reactance_pu=0.020, rating_mw=_R400, active_from_shift=3, voltage_kv=400.0),

    Line(label='L11', from_bus='MDBY', to_bus='DUND',
         reactance_pu=0.025, rating_mw=_R400, active_from_shift=1, voltage_kv=400.0),

    Line(label='L12', from_bus='WEST', to_bus='RDST',
         reactance_pu=0.022, rating_mw=_R400, active_from_shift=5, voltage_kv=400.0),

    Line(label='L13', from_bus='NRTH', to_bus='COAL',
         reactance_pu=0.022, rating_mw=_R400, active_from_shift=6, voltage_kv=400.0),

    Line(label='L14', from_bus='EAST', to_bus='SLST',
         reactance_pu=0.022, rating_mw=_R400, active_from_shift=7, voltage_kv=400.0),

    # ── 220kV CAPITAL RING ────────────────────────────────────────────────
    # L15 gains a second parallel circuit (L91) — see Stage 24 topology note.
    Line(label='L15', from_bus='ASHF', to_bus='FAIR',
         reactance_pu=0.090, rating_mw=_R220, active_from_shift=3, voltage_kv=220.0,
         parallel=+1),

    Line(label='L16', from_bus='FAIR', to_bus='WRNT',
         reactance_pu=0.095, rating_mw=_R220, active_from_shift=3, voltage_kv=220.0),

    Line(label='L17', from_bus='ASHF', to_bus='DUNM',
         reactance_pu=0.100, rating_mw=_R220, active_from_shift=4, voltage_kv=220.0),

    # ── 220kV WEST HYDRO POCKET ───────────────────────────────────────────
    # Arden collector string DUND→AR01→AR02→AR03→AR04, loop-closed entirely
    # within WEST via L159 (AR04→RDST) — see below. The string previously
    # closed into DUNM (a CAP bus, via the old L18) but that made WEST
    # reachable from CAP without touching the spine; removed in Stage 28.

    # Kelmore Lower's sole connection to the grid — pure generation egress.
    Line(label='L19', from_bus='RDST', to_bus='KELD',
         reactance_pu=0.120, rating_mw=_RGEN, active_from_shift=5, voltage_kv=220.0),

    Line(label='L20', from_bus='DUND', to_bus='AR01',
         reactance_pu=0.140, rating_mw=_R220, active_from_shift=5, voltage_kv=220.0),

    Line(label='L21', from_bus='AR01', to_bus='AR02',
         reactance_pu=0.150, rating_mw=_R220, active_from_shift=5, voltage_kv=220.0),

    Line(label='L22', from_bus='AR02', to_bus='AR03',
         reactance_pu=0.150, rating_mw=_R220, active_from_shift=5, voltage_kv=220.0),

    Line(label='L23', from_bus='AR03', to_bus='AR04',
         reactance_pu=0.140, rating_mw=_R220, active_from_shift=5, voltage_kv=220.0),

    # ── 220kV EAST POCKET ─────────────────────────────────────────────────
    Line(label='L24', from_bus='COAL', to_bus='BARD',
         reactance_pu=0.100, rating_mw=_R220, active_from_shift=6, voltage_kv=220.0),

    # Cairn Wind single collector feeder — its loading IS the wind gameplay.
    Line(label='L25', from_bus='COAL', to_bus='WNCN',
         reactance_pu=0.090, rating_mw=_R220, active_from_shift=6, voltage_kv=220.0),

    # East pocket loop closure.
    Line(label='L28', from_bus='BARD', to_bus='SLST',
         reactance_pu=0.110, rating_mw=_R220, active_from_shift=7, voltage_kv=220.0),

    # Note: SOUTH-MESH (STAN/BRCK) and EAST-MESH (FLDN/CO01) no longer have
    # a 220/150kV transformer link into CAP/EAST-POCKET (the old L29, L30,
    # L31, L32) — both were promoted to their own 220kV regions in Stage 28
    # and now reach the spine directly via L155-L158 (see the Shift-10
    # section below). This removes the last non-spine cross-region ties.

    # ── SOUTH MESH — 220kV STAN/BRCK stepping down to 150kV load buses ────
    # (STAN/BRCK promoted from 150kV to 220kV in Stage 28 — see BUSES above.
    # voltage_kv on each line below now reflects the higher-voltage endpoint
    # per the Line convention; rating stays at the 150kV tier since these
    # still only carry the small legacy LD01-03 loads, not the region's
    # main substation feed, which now rides L99/L136 at the TRIPLE tier.)
    # L33 is LD02's sole feed in Shift 3 (ring closes in Shift 4).
    Line(label='L33', from_bus='STAN', to_bus='LD02',
         reactance_pu=0.110, rating_mw=_R150, active_from_shift=3, voltage_kv=220.0),

    Line(label='L34', from_bus='STAN', to_bus='LD01',
         reactance_pu=0.120, rating_mw=_R150, active_from_shift=4, voltage_kv=220.0),

    Line(label='L35', from_bus='LD01', to_bus='BRCK',
         reactance_pu=0.120, rating_mw=_R150, active_from_shift=4, voltage_kv=220.0),

    Line(label='L36', from_bus='BRCK', to_bus='LD02',
         reactance_pu=0.130, rating_mw=_R150, active_from_shift=4, voltage_kv=220.0),

    Line(label='L37', from_bus='STAN', to_bus='LD03',
         reactance_pu=0.100, rating_mw=_R150, active_from_shift=4, voltage_kv=220.0),

    Line(label='L38', from_bus='LD03', to_bus='LD02',
         reactance_pu=0.140, rating_mw=_R150, active_from_shift=4, voltage_kv=150.0),

    # River Brent cascade string — pure generation egress, rated as generator connectors.
    Line(label='L39', from_bus='BRCK', to_bus='BR01',
         reactance_pu=0.150, rating_mw=_RGEN, active_from_shift=4, voltage_kv=220.0),

    Line(label='L40', from_bus='BR01', to_bus='BR02',
         reactance_pu=0.160, rating_mw=_RGEN, active_from_shift=4, voltage_kv=150.0),

    Line(label='L41', from_bus='BR02', to_bus='BR03',
         reactance_pu=0.170, rating_mw=_RGEN, active_from_shift=4, voltage_kv=150.0),

    # ── EAST MESH — 220kV FLDN/CO01 stepping down to 150kV load buses ─────
    # (FLDN/CO01 promoted from 150kV to 220kV in Stage 28 — see BUSES above.
    # Same voltage_kv/rating reasoning as the SOUTH MESH note above.)
    Line(label='L42', from_bus='FLDN', to_bus='LD04',
         reactance_pu=0.120, rating_mw=_R150, active_from_shift=7, voltage_kv=220.0),

    Line(label='L43', from_bus='LD04', to_bus='LD05',
         reactance_pu=0.130, rating_mw=_R150, active_from_shift=7, voltage_kv=150.0),

    Line(label='L44', from_bus='LD05', to_bus='LD06',
         reactance_pu=0.130, rating_mw=_R150, active_from_shift=7, voltage_kv=150.0),

    Line(label='L45', from_bus='LD06', to_bus='FLDN',
         reactance_pu=0.120, rating_mw=_R150, active_from_shift=7, voltage_kv=220.0),

    # River Coln cascade string — pure generation egress, rated as generator connectors.
    Line(label='L46', from_bus='FLDN', to_bus='CO01',
         reactance_pu=0.150, rating_mw=_RGEN, active_from_shift=7, voltage_kv=220.0),

    Line(label='L47', from_bus='CO01', to_bus='CO02',
         reactance_pu=0.160, rating_mw=_RGEN, active_from_shift=7, voltage_kv=150.0),

    Line(label='L48', from_bus='CO02', to_bus='CO03',
         reactance_pu=0.170, rating_mw=_RGEN, active_from_shift=7, voltage_kv=150.0),

    # ── TUTORIAL FEEDERS (permanent) ─────────────────────────────────────
    # DUND feeds the load substations directly in Shifts 1-3. These lines
    # are electrically permanent; from Shift 3 (L50) and Shift 4 (L49) they
    # start in MAINTENANCE state (defined per shift file) once the 150kV
    # mesh takes over the load.
    Line(label='L49', from_bus='DUND', to_bus='LD01',
         reactance_pu=0.080, rating_mw=_R220, active_from_shift=1, voltage_kv=220.0),

    Line(label='L50', from_bus='DUND', to_bus='LD02',
         reactance_pu=0.080, rating_mw=_R220, active_from_shift=2, voltage_kv=220.0),

    # ── STAGE 24: SHIFT 10 CAPACITY EXPANSION ─────────────────────────────
    # Second parallel circuit for the capital ring's binding-constraint
    # segment once the 150kV load layer is fed in (see LD07 below). Active
    # from Shift 10 only — the ring lesson in Shift 3 uses the single L15
    # circuit as originally tuned. (RDST-DUNM no longer has a second
    # circuit — that direct WEST-CAP tie, L27/L92, was removed entirely in
    # Stage 28; WEST now reaches the spine only via L11/L12.)
    Line(label='L91', from_bus='ASHF', to_bus='FAIR',
         reactance_pu=0.090, rating_mw=_R220, active_from_shift=10, voltage_kv=220.0,
         parallel=-1),

    # ── STAGE 29: CAP THIRD SPINE TAP ──────────────────────────────────────
    # LD07 (merged former LD07+LD08, 1988 MW) landing its full load on the
    # ring under N-1 (losing L93, its ASHF feed) pushed L16 (FAIR-WRNT) to
    # 176.6% — the ring's 220kV-tier lines were never sized to carry a
    # whole substation's worth of through-flow. A dedicated 400kV tap
    # straight onto FAIR (mirroring L09's ASHF tap and L10's WRNT tap) fixes
    # this directly: losing L93 now caps out at 88.0% on L16. CAP is the
    # only region with 3 spine taps (WEST/EAST-POCKET/SOUTH-MESH/EAST-MESH
    # all still have exactly 2) — an accepted asymmetry since CAP's
    # substation load is more than double the next-largest region's.
    Line(label='L160', from_bus='STHW', to_bus='FAIR',
         reactance_pu=0.021, rating_mw=_R400, active_from_shift=10, voltage_kv=400.0),

    # ── STAGE 28: SIX-REGION SPINE TAPS ────────────────────────────────────
    # SOUTH-MESH (STAN/BRCK) and EAST-MESH (FLDN/CO01) each get their own
    # pair of 400kV spine taps, exactly mirroring how CAP/WEST/EAST-POCKET
    # already reach the spine (L09/L10, L11/L12, L13/L14 respectively).
    # This replaces the old L29/L30/L31/L32 transformer links, which routed
    # these regions through a neighbouring 220kV pocket instead of directly
    # to the spine — the last non-spine cross-region ties in the grid.
    Line(label='L155', from_bus='STHW', to_bus='BRCK',
         reactance_pu=0.023, rating_mw=_R400, active_from_shift=10, voltage_kv=400.0),

    Line(label='L156', from_bus='CNTR', to_bus='STAN',
         reactance_pu=0.024, rating_mw=_R400, active_from_shift=10, voltage_kv=400.0),

    Line(label='L157', from_bus='NRTH', to_bus='CO01',
         reactance_pu=0.023, rating_mw=_R400, active_from_shift=10, voltage_kv=400.0),

    Line(label='L158', from_bus='EAST', to_bus='FLDN',
         reactance_pu=0.024, rating_mw=_R400, active_from_shift=10, voltage_kv=400.0),

    # WEST-internal Arden loop closure, replacing the old L18 (AR04→DUNM,
    # which closed the loop into CAP instead of staying inside WEST).
    Line(label='L159', from_bus='AR04', to_bus='RDST',
         reactance_pu=0.135, rating_mw=_R220, active_from_shift=10, voltage_kv=220.0),

    # 5 dedicated 220kV feed links — the PRIMARY feed for each of the 5
    # consolidated load substations above (each also gets a SECOND,
    # independent feed from its region's other spine-anchor bus — see
    # L130-L137 near the end of this list). Stage 29 merged what were
    # 8 substations down to 5 (one per region, fed only from that region's
    # 2 spine-anchor buses) after N-1 testing showed any region hosting
    # 2+ substations off just 2 anchors overloads its internal ring.
    # LD07 (CAP, merged former LD07+LD08, 1988 MW) and LD09 (WEST, merged
    # former LD09+LD10+LD14, 2591 MW) use the new CAP/WEST feed tiers sized
    # for their larger merged loads. LD11-LD13 (unchanged, ~950-1035 MW
    # each) keep CONSOLIDATED_FEED_RATING_MW_TRIPLE.
    Line(label='L93',  from_bus='ASHF', to_bus='LD07', reactance_pu=0.040, rating_mw=_RCAP,    active_from_shift=10, voltage_kv=220.0),
    Line(label='L95',  from_bus='DUND', to_bus='LD09', reactance_pu=0.040, rating_mw=_RWEST,   active_from_shift=10, voltage_kv=220.0),
    Line(label='L97',  from_bus='COAL', to_bus='LD11', reactance_pu=0.040, rating_mw=_RTRIPLE, active_from_shift=10, voltage_kv=220.0),
    Line(label='L98',  from_bus='FLDN', to_bus='LD12', reactance_pu=0.040, rating_mw=_RTRIPLE, active_from_shift=10, voltage_kv=220.0),
    Line(label='L99',  from_bus='STAN', to_bus='LD13', reactance_pu=0.040, rating_mw=_RTRIPLE, active_from_shift=10, voltage_kv=220.0),

    # River Brent and River Coln loop closures — ties the far end of each
    # dead-end cascade string back into a nearby 150kV mesh bus, the same way
    # River Arden is already tied at both ends (DUND and DUNM). Without this,
    # a single line trip anywhere in the Brent/Coln strings islands everything
    # downstream. Active from Shift 10 only — earlier shifts keep the original
    # radial strings as their own N-1 teaching moment.
    Line(label='L153', from_bus='BR03', to_bus='LD03',
         reactance_pu=0.180, rating_mw=_R150, active_from_shift=10, voltage_kv=150.0),

    Line(label='L154', from_bus='CO03', to_bus='LD05',
         reactance_pu=0.180, rating_mw=_R150, active_from_shift=10, voltage_kv=150.0),

    # Second, independent 220kV feed for each of the 5 consolidated load
    # substations above (L93/L95/L97/L98/L99 are each substation's primary
    # feed). Each secondary feed below is sourced from the OTHER
    # spine-anchor bus in that substation's region — e.g. LD07 is ASHF
    # (primary, L93) + FAIR (secondary, L130), both CAP's own anchors.
    # Ratings mirror the primary feeds above.
    Line(label='L130', from_bus='FAIR', to_bus='LD07', reactance_pu=0.040, rating_mw=_RCAP,    active_from_shift=10, voltage_kv=220.0),
    Line(label='L132', from_bus='RDST', to_bus='LD09', reactance_pu=0.040, rating_mw=_RWEST,   active_from_shift=10, voltage_kv=220.0),
    Line(label='L134', from_bus='BARD', to_bus='LD11', reactance_pu=0.040, rating_mw=_RTRIPLE, active_from_shift=10, voltage_kv=220.0),
    Line(label='L135', from_bus='CO01', to_bus='LD12', reactance_pu=0.040, rating_mw=_RTRIPLE, active_from_shift=10, voltage_kv=220.0),
    Line(label='L136', from_bus='BRCK', to_bus='LD13', reactance_pu=0.040, rating_mw=_RTRIPLE, active_from_shift=10, voltage_kv=220.0),
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
