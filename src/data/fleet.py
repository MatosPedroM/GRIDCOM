"""
src/data/fleet.py

Complete generation fleet definition for GRIDCOM.
Defines the GenerationUnit dataclass and all 47 generation units across
all stations in the fictional transmission network.

See DOMAIN_GLOSSARY.md for unit type definitions and ramp/inertia values.
See CLAUDE.md for station and unit naming conventions.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationUnit:
    """
    A single generation unit (one turbine-generator set).

    Attributes:
        label:             Unit identifier, e.g. 'RVSD-1', 'HART-2'
        station_label:     Parent station label, e.g. 'RVSD', 'HART'
        bus_label:         Bus this unit connects to (transmission bus label)
        unit_type:         'COAL', 'CCGT', 'NUCLEAR', 'HYDRO', 'HYDRO_ROR',
                           'HYDRO_PUMP', 'WIND', or 'SOLAR'
        rated_mw:          Maximum output at rated conditions (MW)
        min_mw:            Minimum stable output when online (MW)
        ramp_pct_per_min:  Max ramp rate as % of rated_mw per simulated minute
        inertia_h:         Inertia constant H in seconds (0.0 for wind/solar)
        cold_start_min:    Simulated minutes from OFFLINE to ONLINE
        q_max_mvar:        Maximum reactive power injection (MVAr)
        q_min_mvar:        Maximum reactive power absorption (MVAr, negative)
        can_pump:          True for pumped storage units (HYDRO_PUMP)
        active_from_shift: First shift where this unit is available
        description:       Human-readable description for context panel
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# GENERATION FLEET — 47 units
# ─────────────────────────────────────────────────────────────────────────────

UNITS: list[GenerationUnit] = [

    # ── RIVERSIDE COAL — RVSD (3×300MW, 400kV, bus MDBY) ─────────────────
    # COALCOM easter egg: RVSD-2 starts out of service in Shift 1 handover.
    GenerationUnit(
        label='RVSD-1', station_label='RVSD', bus_label='MDBY',
        unit_type='COAL', rated_mw=300.0, min_mw=90.0,
        ramp_pct_per_min=3.0, inertia_h=5.0, cold_start_min=240.0,
        q_max_mvar=150.0, q_min_mvar=-80.0,
        can_pump=False, active_from_shift=1,
        description='Riverside Coal Unit 1 — 300MW, 400kV. Slow ramp.'),

    GenerationUnit(
        label='RVSD-2', station_label='RVSD', bus_label='MDBY',
        unit_type='COAL', rated_mw=300.0, min_mw=90.0,
        ramp_pct_per_min=3.0, inertia_h=5.0, cold_start_min=240.0,
        q_max_mvar=150.0, q_min_mvar=-80.0,
        can_pump=False, active_from_shift=1,
        description='Riverside Coal Unit 2 — 300MW, 400kV. OOS Shift 1 (relay maintenance).'),

    GenerationUnit(
        label='RVSD-3', station_label='RVSD', bus_label='MDBY',
        unit_type='COAL', rated_mw=300.0, min_mw=90.0,
        ramp_pct_per_min=3.0, inertia_h=5.0, cold_start_min=240.0,
        q_max_mvar=150.0, q_min_mvar=-80.0,
        can_pump=False, active_from_shift=1,
        description='Riverside Coal Unit 3 — 300MW, 400kV. Slow ramp.'),

    # ── THORNFIELD COAL — THNF (3×300MW, 400kV, bus NRTH) ────────────────
    GenerationUnit(
        label='THNF-1', station_label='THNF', bus_label='NRTH',
        unit_type='COAL', rated_mw=300.0, min_mw=90.0,
        ramp_pct_per_min=3.0, inertia_h=5.0, cold_start_min=240.0,
        q_max_mvar=150.0, q_min_mvar=-80.0,
        can_pump=False, active_from_shift=5,
        description='Thornfield Coal Unit 1 — 300MW, 400kV.'),

    GenerationUnit(
        label='THNF-2', station_label='THNF', bus_label='NRTH',
        unit_type='COAL', rated_mw=300.0, min_mw=90.0,
        ramp_pct_per_min=3.0, inertia_h=5.0, cold_start_min=240.0,
        q_max_mvar=150.0, q_min_mvar=-80.0,
        can_pump=False, active_from_shift=5,
        description='Thornfield Coal Unit 2 — 300MW, 400kV.'),

    GenerationUnit(
        label='THNF-3', station_label='THNF', bus_label='NRTH',
        unit_type='COAL', rated_mw=300.0, min_mw=90.0,
        ramp_pct_per_min=3.0, inertia_h=5.0, cold_start_min=240.0,
        q_max_mvar=150.0, q_min_mvar=-80.0,
        can_pump=False, active_from_shift=5,
        description='Thornfield Coal Unit 3 — 300MW, 400kV.'),

    # ── HARTWELL NUCLEAR — HART (2×700MW, 400kV, bus CNTR) ───────────────
    GenerationUnit(
        label='HART-1', station_label='HART', bus_label='CNTR',
        unit_type='NUCLEAR', rated_mw=700.0, min_mw=490.0,
        ramp_pct_per_min=1.0, inertia_h=6.0, cold_start_min=480.0,
        q_max_mvar=300.0, q_min_mvar=-150.0,
        can_pump=False, active_from_shift=1,
        description='Hartwell Nuclear Unit 1 — 700MW, 400kV. Baseload, always online.'),

    GenerationUnit(
        label='HART-2', station_label='HART', bus_label='CNTR',
        unit_type='NUCLEAR', rated_mw=700.0, min_mw=490.0,
        ramp_pct_per_min=1.0, inertia_h=6.0, cold_start_min=480.0,
        q_max_mvar=300.0, q_min_mvar=-150.0,
        can_pump=False, active_from_shift=1,
        description='Hartwell Nuclear Unit 2 — 700MW, 400kV. Baseload, always online.'),

    # ── ASHFORD CCGT — ASHG (2×400MW, 220kV, bus ASHG) ───────────────────
    GenerationUnit(
        label='ASHG-1', station_label='ASHG', bus_label='ASHG',
        unit_type='CCGT', rated_mw=400.0, min_mw=80.0,
        ramp_pct_per_min=8.0, inertia_h=4.0, cold_start_min=60.0,
        q_max_mvar=180.0, q_min_mvar=-100.0,
        can_pump=False, active_from_shift=3,
        description='Ashford CCGT Unit 1 — 400MW, 220kV. Medium ramp.'),

    GenerationUnit(
        label='ASHG-2', station_label='ASHG', bus_label='ASHG',
        unit_type='CCGT', rated_mw=400.0, min_mw=80.0,
        ramp_pct_per_min=8.0, inertia_h=4.0, cold_start_min=60.0,
        q_max_mvar=180.0, q_min_mvar=-100.0,
        can_pump=False, active_from_shift=3,
        description='Ashford CCGT Unit 2 — 400MW, 220kV. Medium ramp.'),

    # ── WRENTHAM CCGT — WRNG (2×400MW, 220kV, bus WRNG) ──────────────────
    GenerationUnit(
        label='WRNG-1', station_label='WRNG', bus_label='WRNG',
        unit_type='CCGT', rated_mw=400.0, min_mw=80.0,
        ramp_pct_per_min=8.0, inertia_h=4.0, cold_start_min=60.0,
        q_max_mvar=180.0, q_min_mvar=-100.0,
        can_pump=False, active_from_shift=3,
        description='Wrentham CCGT Unit 1 — 400MW, 220kV. Medium ramp.'),

    GenerationUnit(
        label='WRNG-2', station_label='WRNG', bus_label='WRNG',
        unit_type='CCGT', rated_mw=400.0, min_mw=80.0,
        ramp_pct_per_min=8.0, inertia_h=4.0, cold_start_min=60.0,
        q_max_mvar=180.0, q_min_mvar=-100.0,
        can_pump=False, active_from_shift=3,
        description='Wrentham CCGT Unit 2 — 400MW, 220kV. Medium ramp.'),

    # ── BARROW HYDRO UPPER — BARR (2×250MW, 400kV, bus EAST) ─────────────
    GenerationUnit(
        label='BARR-1', station_label='BARR', bus_label='EAST',
        unit_type='HYDRO_PUMP', rated_mw=250.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=120.0, q_min_mvar=-60.0,
        can_pump=True, active_from_shift=3,
        description='Barrow Hydro Upper Unit 1 — 250MW pumped storage, 400kV.'),

    GenerationUnit(
        label='BARR-2', station_label='BARR', bus_label='EAST',
        unit_type='HYDRO_PUMP', rated_mw=250.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=120.0, q_min_mvar=-60.0,
        can_pump=True, active_from_shift=3,
        description='Barrow Hydro Upper Unit 2 — 250MW pumped storage, 400kV.'),

    # ── BARROW HYDRO LOWER — BARD (2×80MW, 220kV, bus BARD) ──────────────
    GenerationUnit(
        label='BARD-1', station_label='BARD', bus_label='BARD',
        unit_type='HYDRO', rated_mw=80.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=35.0, q_min_mvar=-20.0,
        can_pump=False, active_from_shift=3,
        description='Barrow Hydro Lower Unit 1 — 80MW downstream, 220kV.'),

    GenerationUnit(
        label='BARD-2', station_label='BARD', bus_label='BARD',
        unit_type='HYDRO', rated_mw=80.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=35.0, q_min_mvar=-20.0,
        can_pump=False, active_from_shift=3,
        description='Barrow Hydro Lower Unit 2 — 80MW downstream, 220kV.'),

    # ── KELMORE HYDRO UPPER — KELM (2×250MW, 400kV, bus WEST) ────────────
    GenerationUnit(
        label='KELM-1', station_label='KELM', bus_label='WEST',
        unit_type='HYDRO_PUMP', rated_mw=250.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=120.0, q_min_mvar=-60.0,
        can_pump=True, active_from_shift=3,
        description='Kelmore Hydro Upper Unit 1 — 250MW pumped storage, 400kV.'),

    GenerationUnit(
        label='KELM-2', station_label='KELM', bus_label='WEST',
        unit_type='HYDRO_PUMP', rated_mw=250.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=120.0, q_min_mvar=-60.0,
        can_pump=True, active_from_shift=3,
        description='Kelmore Hydro Upper Unit 2 — 250MW pumped storage, 400kV.'),

    # ── KELMORE HYDRO LOWER — KELD (2×80MW, 220kV, bus KELD) ─────────────
    GenerationUnit(
        label='KELD-1', station_label='KELD', bus_label='KELD',
        unit_type='HYDRO', rated_mw=80.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=35.0, q_min_mvar=-20.0,
        can_pump=False, active_from_shift=3,
        description='Kelmore Hydro Lower Unit 1 — 80MW downstream, 220kV.'),

    GenerationUnit(
        label='KELD-2', station_label='KELD', bus_label='KELD',
        unit_type='HYDRO', rated_mw=80.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=35.0, q_min_mvar=-20.0,
        can_pump=False, active_from_shift=3,
        description='Kelmore Hydro Lower Unit 2 — 80MW downstream, 220kV.'),

    # ── DUNMORE HYDRO UPPER — DUNH (2×200MW, 400kV, bus STHW) ────────────
    GenerationUnit(
        label='DUNH-1', station_label='DUNH', bus_label='STHW',
        unit_type='HYDRO_PUMP', rated_mw=200.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=90.0, q_min_mvar=-50.0,
        can_pump=True, active_from_shift=2,
        description='Dunmore Hydro Upper Unit 1 — 200MW pumped storage, 400kV.'),

    GenerationUnit(
        label='DUNH-2', station_label='DUNH', bus_label='STHW',
        unit_type='HYDRO_PUMP', rated_mw=200.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=90.0, q_min_mvar=-50.0,
        can_pump=True, active_from_shift=2,
        description='Dunmore Hydro Upper Unit 2 — 200MW pumped storage, 400kV.'),

    # ── DUNMORE HYDRO LOWER — DUND (2×65MW, 220kV, bus DUND) ─────────────
    GenerationUnit(
        label='DUND-1', station_label='DUND', bus_label='DUND',
        unit_type='HYDRO', rated_mw=65.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=28.0, q_min_mvar=-15.0,
        can_pump=False, active_from_shift=1,
        description='Dunmore Hydro Lower Unit 1 — 65MW downstream, 220kV.'),

    GenerationUnit(
        label='DUND-2', station_label='DUND', bus_label='DUND',
        unit_type='HYDRO', rated_mw=65.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=28.0, q_min_mvar=-15.0,
        can_pump=False, active_from_shift=1,
        description='Dunmore Hydro Lower Unit 2 — 65MW downstream, 220kV.'),

    # ── RIVER ARDEN CASCADE — AR01-AR04 (2×units each, 220kV, run-of-river) ─
    GenerationUnit(
        label='AR01-1', station_label='AR01', bus_label='AR01',
        unit_type='HYDRO_ROR', rated_mw=40.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=15.0, q_min_mvar=-8.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 1 Unit 1 — 40MW run-of-river, 220kV.'),

    GenerationUnit(
        label='AR01-2', station_label='AR01', bus_label='AR01',
        unit_type='HYDRO_ROR', rated_mw=40.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=15.0, q_min_mvar=-8.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 1 Unit 2 — 40MW run-of-river, 220kV.'),

    GenerationUnit(
        label='AR02-1', station_label='AR02', bus_label='AR02',
        unit_type='HYDRO_ROR', rated_mw=35.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=14.0, q_min_mvar=-7.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 2 Unit 1 — 35MW run-of-river, 220kV.'),

    GenerationUnit(
        label='AR02-2', station_label='AR02', bus_label='AR02',
        unit_type='HYDRO_ROR', rated_mw=35.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=14.0, q_min_mvar=-7.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 2 Unit 2 — 35MW run-of-river, 220kV.'),

    GenerationUnit(
        label='AR03-1', station_label='AR03', bus_label='AR03',
        unit_type='HYDRO_ROR', rated_mw=30.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=12.0, q_min_mvar=-6.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 3 Unit 1 — 30MW run-of-river, 220kV.'),

    GenerationUnit(
        label='AR03-2', station_label='AR03', bus_label='AR03',
        unit_type='HYDRO_ROR', rated_mw=30.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=12.0, q_min_mvar=-6.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 3 Unit 2 — 30MW run-of-river, 220kV.'),

    GenerationUnit(
        label='AR04-1', station_label='AR04', bus_label='AR04',
        unit_type='HYDRO_ROR', rated_mw=25.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=10.0, q_min_mvar=-5.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 4 Unit 1 — 25MW run-of-river, 220kV.'),

    GenerationUnit(
        label='AR04-2', station_label='AR04', bus_label='AR04',
        unit_type='HYDRO_ROR', rated_mw=25.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=10.0, q_min_mvar=-5.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 4 Unit 2 — 25MW run-of-river, 220kV.'),

    # ── RIVER BRENT CASCADE — BR01-BR03 (2×units each, 150kV, run-of-river) ─
    GenerationUnit(
        label='BR01-1', station_label='BR01', bus_label='BR01',
        unit_type='HYDRO_ROR', rated_mw=30.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=12.0, q_min_mvar=-6.0,
        can_pump=False, active_from_shift=1,
        description='River Brent Station 1 Unit 1 — 30MW run-of-river, 150kV.'),

    GenerationUnit(
        label='BR01-2', station_label='BR01', bus_label='BR01',
        unit_type='HYDRO_ROR', rated_mw=30.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=12.0, q_min_mvar=-6.0,
        can_pump=False, active_from_shift=1,
        description='River Brent Station 1 Unit 2 — 30MW run-of-river, 150kV.'),

    GenerationUnit(
        label='BR02-1', station_label='BR02', bus_label='BR02',
        unit_type='HYDRO_ROR', rated_mw=25.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=10.0, q_min_mvar=-5.0,
        can_pump=False, active_from_shift=3,
        description='River Brent Station 2 Unit 1 — 25MW run-of-river, 150kV.'),

    GenerationUnit(
        label='BR02-2', station_label='BR02', bus_label='BR02',
        unit_type='HYDRO_ROR', rated_mw=25.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=10.0, q_min_mvar=-5.0,
        can_pump=False, active_from_shift=3,
        description='River Brent Station 2 Unit 2 — 25MW run-of-river, 150kV.'),

    GenerationUnit(
        label='BR03-1', station_label='BR03', bus_label='BR03',
        unit_type='HYDRO_ROR', rated_mw=20.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=8.0, q_min_mvar=-4.0,
        can_pump=False, active_from_shift=3,
        description='River Brent Station 3 Unit 1 — 20MW run-of-river, 150kV.'),

    GenerationUnit(
        label='BR03-2', station_label='BR03', bus_label='BR03',
        unit_type='HYDRO_ROR', rated_mw=20.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=8.0, q_min_mvar=-4.0,
        can_pump=False, active_from_shift=3,
        description='River Brent Station 3 Unit 2 — 20MW run-of-river, 150kV.'),

    # ── RIVER COLN CASCADE — CO01-CO03 (150kV, run-of-river) ─────────────
    # CO01 and CO02 have 2 units; CO03 has 1 (smallest station).
    GenerationUnit(
        label='CO01-1', station_label='CO01', bus_label='CO01',
        unit_type='HYDRO_ROR', rated_mw=28.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=11.0, q_min_mvar=-6.0,
        can_pump=False, active_from_shift=5,
        description='River Coln Station 1 Unit 1 — 28MW run-of-river, 150kV.'),

    GenerationUnit(
        label='CO01-2', station_label='CO01', bus_label='CO01',
        unit_type='HYDRO_ROR', rated_mw=28.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=11.0, q_min_mvar=-6.0,
        can_pump=False, active_from_shift=5,
        description='River Coln Station 1 Unit 2 — 28MW run-of-river, 150kV.'),

    GenerationUnit(
        label='CO02-1', station_label='CO02', bus_label='CO02',
        unit_type='HYDRO_ROR', rated_mw=23.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=9.0, q_min_mvar=-5.0,
        can_pump=False, active_from_shift=5,
        description='River Coln Station 2 Unit 1 — 23MW run-of-river, 150kV.'),

    GenerationUnit(
        label='CO02-2', station_label='CO02', bus_label='CO02',
        unit_type='HYDRO_ROR', rated_mw=23.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=9.0, q_min_mvar=-5.0,
        can_pump=False, active_from_shift=5,
        description='River Coln Station 2 Unit 2 — 23MW run-of-river, 150kV.'),

    GenerationUnit(
        label='CO03-1', station_label='CO03', bus_label='CO03',
        unit_type='HYDRO_ROR', rated_mw=18.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=7.0, q_min_mvar=-4.0,
        can_pump=False, active_from_shift=5,
        description='River Coln Station 3 — 18MW run-of-river, 150kV.'),

    # ── CAIRN WIND — WNCN (500MW, 220kV, bus WNCN) ───────────────────────
    GenerationUnit(
        label='WNCN-1', station_label='WNCN', bus_label='WNCN',
        unit_type='WIND', rated_mw=500.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=0.0, cold_start_min=0.0,
        q_max_mvar=0.0, q_min_mvar=0.0,
        can_pump=False, active_from_shift=3,
        description='Cairn Wind Farm — 500MW aggregated, 220kV. Uncontrollable.'),

    # ── BRACKLEY WIND — WNBR (300MW, 150kV, bus BRCK) ────────────────────
    GenerationUnit(
        label='WNBR-1', station_label='WNBR', bus_label='BRCK',
        unit_type='WIND', rated_mw=300.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=0.0, cold_start_min=0.0,
        q_max_mvar=0.0, q_min_mvar=0.0,
        can_pump=False, active_from_shift=5,
        description='Brackley Wind Farm — 300MW aggregated, 150kV. Uncontrollable.'),

    # ── STANTON SOLAR — SLST (600MW, 220kV, bus SLST) ────────────────────
    GenerationUnit(
        label='SLST-1', station_label='SLST', bus_label='SLST',
        unit_type='SOLAR', rated_mw=600.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=0.0, cold_start_min=0.0,
        q_max_mvar=0.0, q_min_mvar=0.0,
        can_pump=False, active_from_shift=3,
        description='Stanton Solar Park — 600MW aggregated, 220kV. Zero output at night.'),

    # ── FELDON SOLAR — SLFD (400MW, 150kV, bus FLDN) ─────────────────────
    GenerationUnit(
        label='SLFD-1', station_label='SLFD', bus_label='FLDN',
        unit_type='SOLAR', rated_mw=400.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=0.0, cold_start_min=0.0,
        q_max_mvar=0.0, q_min_mvar=0.0,
        can_pump=False, active_from_shift=5,
        description='Feldon Solar Park — 400MW aggregated, 150kV. Zero output at night.'),
]


# ─────────────────────────────────────────────────────────────────────────────
# LOOKUP HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_units_by_shift(shift_number: int) -> list[GenerationUnit]:
    """Return all units active in the given shift number."""
    return [u for u in UNITS if u.active_from_shift <= shift_number]


def get_unit(label: str) -> GenerationUnit:
    """Return unit by label. Raises KeyError if not found."""
    for u in UNITS:
        if u.label == label:
            return u
    raise KeyError(f"Unit not found: {label!r}")


def get_units_at_bus(bus_label: str, shift_number: int) -> list[GenerationUnit]:
    """Return all units at the given bus that are active in shift_number."""
    return [u for u in UNITS
            if u.bus_label == bus_label and u.active_from_shift <= shift_number]


def get_units_at_station(station_label: str) -> list[GenerationUnit]:
    """Return all units belonging to the given station."""
    return [u for u in UNITS if u.station_label == station_label]


# ─────────────────────────────────────────────────────────────────────────────
# STATION CANVAS POSITIONS
# Separate from bus positions — stations draw as unit squares offset from bus.
# ─────────────────────────────────────────────────────────────────────────────

STATION_POSITIONS: dict[str, tuple[int, int]] = {
    'RVSD': (520,  220),
    'THNF': (1400, 220),
    'HART': (960,  180),
    'ASHG': (640,  320),
    'WRNG': (1120, 320),
    'BARR': (1640, 340),
    'BARD': (1700, 500),
    'KELM': (200,  340),
    'KELD': (100,  500),
    'DUNH': (760,  340),
    'DUND': (460,  600),
    'AR01': (440,  640),
    'AR02': (540,  680),
    'AR03': (640,  720),
    'AR04': (740,  680),
    'BR01': (300,  660),
    'BR02': (200,  700),
    'BR03': (140,  740),
    'CO01': (1360, 660),
    'CO02': (1460, 700),
    'CO03': (1540, 740),
    'WNCN': (1800, 460),
    'WNBR': (200,  560),
    'SLST': (1120, 560),
    'SLFD': (1480, 620),
}


def get_station_position(station_label: str) -> tuple[int, int]:
    """Return canvas position for a station, with layout overrides applied."""
    from data.layout_override import get_station_pos
    return get_station_pos(station_label, STATION_POSITIONS[station_label])
