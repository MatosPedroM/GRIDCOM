"""
src/data/fleet.py

Complete generation fleet definition for GRIDCOM.
Defines the GenerationUnit dataclass and all 47 generation units across
all stations in the fictional transmission network.

Fleet design (proportional to the grid regions):
  West exports hydro eastward (KELM pumped @ WEST, KELD/DUND lowers,
  River Arden cascade). The capital is the big sink with local CCGT
  peakers (ASHG @ ASHF, WRNG @ WRNT). The spine carries coal + nuclear
  baseload (RVSD/DUNH @ MDBY, HART @ STHW, THNF/BARR @ NRTH). The east
  hosts wind and solar (WNCN, SLST, SLFD) plus the River Coln cascade.

Totals: ~8,980 MW installed vs 8,000 MW campaign peak. Firm capacity
(nuclear+coal+CCGT+pumped+lower hydro) ≈ 6,650 MW — the endgame peak
requires interconnector imports and pumped-storage strategy by design.

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
        min_up_time_h:     Minimum hours a unit must stay ONLINE once
                           committed (Phase 1 planning-layer constraint only —
                           not enforced by the real-time simulation)
        min_down_time_h:   Minimum hours a unit must stay OFFLINE before
                           restarting (Phase 1 planning-layer constraint only)

    Phase 1 scheduler economics (startup cost, fuel cost, AGC-availability
    cost) are NOT unit fields — they're looked up by unit_type from
    constants.py's STARTUP_COST_EUR_BY_TYPE / VARIABLE_COST_EUR_PER_MWH_BY_TYPE,
    scaled by DIFFICULTY_COST_MULT. Cost is a per-technology property, not a
    per-fleet-unit override.
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
    min_up_time_h:     float = 0.0
    min_down_time_h:   float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# GENERATION FLEET — 47 units
# ─────────────────────────────────────────────────────────────────────────────

UNITS: list[GenerationUnit] = [

    # ── DUNMORE HYDRO LOWER — DUND (2×65MW, 220kV, bus DUND) ─────────────
    # Shift 1 tutorial units — downstream of DUNH (penstock from MDBY).
    GenerationUnit(
        label='DUND-1', station_label='DUND', bus_label='DUND',
        unit_type='HYDRO', rated_mw=65.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=28.0, q_min_mvar=-15.0,
        can_pump=False, active_from_shift=1,
        description='Dunmore Hydro Lower Unit 1 — 65MW downstream, 220kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='DUND-2', station_label='DUND', bus_label='DUND',
        unit_type='HYDRO', rated_mw=65.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=28.0, q_min_mvar=-15.0,
        can_pump=False, active_from_shift=1,
        description='Dunmore Hydro Lower Unit 2 — 65MW downstream, 220kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    # ── RIVERSIDE COAL — RVSD (3×300MW, 400kV, bus MDBY) ─────────────────
    # COALCOM easter egg: RVSD-2 starts out of service in the Shift 2
    # handover (planned relay maintenance).
    GenerationUnit(
        label='RVSD-1', station_label='RVSD', bus_label='MDBY',
        unit_type='COAL', rated_mw=300.0, min_mw=90.0,
        ramp_pct_per_min=3.0, inertia_h=5.0, cold_start_min=240.0,
        q_max_mvar=150.0, q_min_mvar=-80.0,
        can_pump=False, active_from_shift=2,
        description='Riverside Coal Unit 1 — 300MW, 400kV. Slow ramp.',
        min_up_time_h=6.0, min_down_time_h=8.0),

    GenerationUnit(
        label='RVSD-2', station_label='RVSD', bus_label='MDBY',
        unit_type='COAL', rated_mw=300.0, min_mw=90.0,
        ramp_pct_per_min=3.0, inertia_h=5.0, cold_start_min=240.0,
        q_max_mvar=150.0, q_min_mvar=-80.0,
        can_pump=False, active_from_shift=2,
        description='Riverside Coal Unit 2 — 300MW, 400kV. OOS Shift 2 (relay maintenance).',
        min_up_time_h=6.0, min_down_time_h=8.0),

    GenerationUnit(
        label='RVSD-3', station_label='RVSD', bus_label='MDBY',
        unit_type='COAL', rated_mw=300.0, min_mw=90.0,
        ramp_pct_per_min=3.0, inertia_h=5.0, cold_start_min=240.0,
        q_max_mvar=150.0, q_min_mvar=-80.0,
        can_pump=False, active_from_shift=2,
        description='Riverside Coal Unit 3 — 300MW, 400kV. Slow ramp.',
        min_up_time_h=6.0, min_down_time_h=8.0),

    # ── DUNMORE HYDRO UPPER — DUNH (2×200MW, 400kV, bus MDBY) ────────────
    GenerationUnit(
        label='DUNH-1', station_label='DUNH', bus_label='MDBY',
        unit_type='HYDRO_PUMP', rated_mw=200.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=90.0, q_min_mvar=-50.0,
        can_pump=True, active_from_shift=3,
        description='Dunmore Hydro Upper Unit 1 — 200MW pumped storage, 400kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='DUNH-2', station_label='DUNH', bus_label='MDBY',
        unit_type='HYDRO_PUMP', rated_mw=200.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=90.0, q_min_mvar=-50.0,
        can_pump=True, active_from_shift=3,
        description='Dunmore Hydro Upper Unit 2 — 200MW pumped storage, 400kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    # ── HARTWELL NUCLEAR — HART (2×700MW, 400kV, bus STHW) ───────────────
    GenerationUnit(
        label='HART-1', station_label='HART', bus_label='STHW',
        unit_type='NUCLEAR', rated_mw=700.0, min_mw=490.0,
        ramp_pct_per_min=1.0, inertia_h=6.0, cold_start_min=480.0,
        q_max_mvar=300.0, q_min_mvar=-150.0,
        can_pump=False, active_from_shift=3,
        description='Hartwell Nuclear Unit 1 — 700MW, 400kV. Baseload, always online.',
        min_up_time_h=24.0, min_down_time_h=24.0),

    GenerationUnit(
        label='HART-2', station_label='HART', bus_label='STHW',
        unit_type='NUCLEAR', rated_mw=700.0, min_mw=490.0,
        ramp_pct_per_min=1.0, inertia_h=6.0, cold_start_min=480.0,
        q_max_mvar=300.0, q_min_mvar=-150.0,
        can_pump=False, active_from_shift=3,
        description='Hartwell Nuclear Unit 2 — 700MW, 400kV. Baseload, always online.',
        min_up_time_h=24.0, min_down_time_h=24.0),

    # ── ASHFORD CCGT — ASHG (2×400MW, 220kV, bus ASHF) ───────────────────
    GenerationUnit(
        label='ASHG-1', station_label='ASHG', bus_label='ASHF',
        unit_type='CCGT', rated_mw=400.0, min_mw=80.0,
        ramp_pct_per_min=8.0, inertia_h=4.0, cold_start_min=60.0,
        q_max_mvar=180.0, q_min_mvar=-100.0,
        can_pump=False, active_from_shift=3,
        description='Ashford CCGT Unit 1 — 400MW, 220kV. Medium ramp.',
        min_up_time_h=2.0, min_down_time_h=2.0),

    GenerationUnit(
        label='ASHG-2', station_label='ASHG', bus_label='ASHF',
        unit_type='CCGT', rated_mw=400.0, min_mw=80.0,
        ramp_pct_per_min=8.0, inertia_h=4.0, cold_start_min=60.0,
        q_max_mvar=180.0, q_min_mvar=-100.0,
        can_pump=False, active_from_shift=3,
        description='Ashford CCGT Unit 2 — 400MW, 220kV. Medium ramp.',
        min_up_time_h=2.0, min_down_time_h=2.0),

    # ── WRENTHAM CCGT — WRNG (2×400MW, 220kV, bus WRNT) ──────────────────
    GenerationUnit(
        label='WRNG-1', station_label='WRNG', bus_label='WRNT',
        unit_type='CCGT', rated_mw=400.0, min_mw=80.0,
        ramp_pct_per_min=8.0, inertia_h=4.0, cold_start_min=60.0,
        q_max_mvar=180.0, q_min_mvar=-100.0,
        can_pump=False, active_from_shift=3,
        description='Wrentham CCGT Unit 1 — 400MW, 220kV. Medium ramp.',
        min_up_time_h=2.0, min_down_time_h=2.0),

    GenerationUnit(
        label='WRNG-2', station_label='WRNG', bus_label='WRNT',
        unit_type='CCGT', rated_mw=400.0, min_mw=80.0,
        ramp_pct_per_min=8.0, inertia_h=4.0, cold_start_min=60.0,
        q_max_mvar=180.0, q_min_mvar=-100.0,
        can_pump=False, active_from_shift=3,
        description='Wrentham CCGT Unit 2 — 400MW, 220kV. Medium ramp.',
        min_up_time_h=2.0, min_down_time_h=2.0),

    # ── BRACKLEY WIND — WNBR (300MW, 150kV, bus BRCK) ────────────────────
    GenerationUnit(
        label='WNBR-1', station_label='WNBR', bus_label='BRCK',
        unit_type='WIND', rated_mw=300.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=0.0, cold_start_min=0.0,
        q_max_mvar=0.0, q_min_mvar=0.0,
        can_pump=False, active_from_shift=4,
        description='Brackley Wind Farm — 300MW aggregated, 150kV. Uncontrollable.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    # ── RIVER BRENT CASCADE — BR01-BR03 (2 units each, 150kV) ────────────
    GenerationUnit(
        label='BR01-1', station_label='BR01', bus_label='BR01',
        unit_type='HYDRO_ROR', rated_mw=30.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=12.0, q_min_mvar=-6.0,
        can_pump=False, active_from_shift=4,
        description='River Brent Station 1 Unit 1 — 30MW run-of-river, 150kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='BR01-2', station_label='BR01', bus_label='BR01',
        unit_type='HYDRO_ROR', rated_mw=30.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=12.0, q_min_mvar=-6.0,
        can_pump=False, active_from_shift=4,
        description='River Brent Station 1 Unit 2 — 30MW run-of-river, 150kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='BR02-1', station_label='BR02', bus_label='BR02',
        unit_type='HYDRO_ROR', rated_mw=25.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=10.0, q_min_mvar=-5.0,
        can_pump=False, active_from_shift=4,
        description='River Brent Station 2 Unit 1 — 25MW run-of-river, 150kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='BR02-2', station_label='BR02', bus_label='BR02',
        unit_type='HYDRO_ROR', rated_mw=25.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=10.0, q_min_mvar=-5.0,
        can_pump=False, active_from_shift=4,
        description='River Brent Station 2 Unit 2 — 25MW run-of-river, 150kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='BR03-1', station_label='BR03', bus_label='BR03',
        unit_type='HYDRO_ROR', rated_mw=20.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=8.0, q_min_mvar=-4.0,
        can_pump=False, active_from_shift=4,
        description='River Brent Station 3 Unit 1 — 20MW run-of-river, 150kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='BR03-2', station_label='BR03', bus_label='BR03',
        unit_type='HYDRO_ROR', rated_mw=20.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=8.0, q_min_mvar=-4.0,
        can_pump=False, active_from_shift=4,
        description='River Brent Station 3 Unit 2 — 20MW run-of-river, 150kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    # ── KELMORE HYDRO UPPER — KELM (2×250MW, 400kV, bus WEST) ────────────
    GenerationUnit(
        label='KELM-1', station_label='KELM', bus_label='WEST',
        unit_type='HYDRO_PUMP', rated_mw=250.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=120.0, q_min_mvar=-60.0,
        can_pump=True, active_from_shift=5,
        description='Kelmore Hydro Upper Unit 1 — 250MW pumped storage, 400kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='KELM-2', station_label='KELM', bus_label='WEST',
        unit_type='HYDRO_PUMP', rated_mw=250.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=120.0, q_min_mvar=-60.0,
        can_pump=True, active_from_shift=5,
        description='Kelmore Hydro Upper Unit 2 — 250MW pumped storage, 400kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    # ── KELMORE HYDRO LOWER — KELD (2×80MW, 220kV, bus KELD) ─────────────
    GenerationUnit(
        label='KELD-1', station_label='KELD', bus_label='KELD',
        unit_type='HYDRO', rated_mw=80.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=35.0, q_min_mvar=-20.0,
        can_pump=False, active_from_shift=5,
        description='Kelmore Hydro Lower Unit 1 — 80MW downstream, 220kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='KELD-2', station_label='KELD', bus_label='KELD',
        unit_type='HYDRO', rated_mw=80.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=35.0, q_min_mvar=-20.0,
        can_pump=False, active_from_shift=5,
        description='Kelmore Hydro Lower Unit 2 — 80MW downstream, 220kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    # ── RIVER ARDEN CASCADE — AR01-AR04 (260MW total, 220kV) ─────────────
    GenerationUnit(
        label='AR01-1', station_label='AR01', bus_label='AR01',
        unit_type='HYDRO_ROR', rated_mw=40.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=15.0, q_min_mvar=-8.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 1 Unit 1 — 40MW run-of-river, 220kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='AR01-2', station_label='AR01', bus_label='AR01',
        unit_type='HYDRO_ROR', rated_mw=40.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=15.0, q_min_mvar=-8.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 1 Unit 2 — 40MW run-of-river, 220kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='AR02-1', station_label='AR02', bus_label='AR02',
        unit_type='HYDRO_ROR', rated_mw=35.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=14.0, q_min_mvar=-7.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 2 Unit 1 — 35MW run-of-river, 220kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='AR02-2', station_label='AR02', bus_label='AR02',
        unit_type='HYDRO_ROR', rated_mw=35.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=14.0, q_min_mvar=-7.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 2 Unit 2 — 35MW run-of-river, 220kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='AR03-1', station_label='AR03', bus_label='AR03',
        unit_type='HYDRO_ROR', rated_mw=60.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=24.0, q_min_mvar=-12.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 3 — 60MW run-of-river, 220kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='AR04-1', station_label='AR04', bus_label='AR04',
        unit_type='HYDRO_ROR', rated_mw=50.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=20.0, q_min_mvar=-10.0,
        can_pump=False, active_from_shift=5,
        description='River Arden Station 4 — 50MW run-of-river, 220kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    # ── THORNFIELD COAL — THNF (3×300MW, 400kV, bus NRTH) ────────────────
    GenerationUnit(
        label='THNF-1', station_label='THNF', bus_label='NRTH',
        unit_type='COAL', rated_mw=300.0, min_mw=90.0,
        ramp_pct_per_min=3.0, inertia_h=5.0, cold_start_min=240.0,
        q_max_mvar=150.0, q_min_mvar=-80.0,
        can_pump=False, active_from_shift=6,
        description='Thornfield Coal Unit 1 — 300MW, 400kV.',
        min_up_time_h=6.0, min_down_time_h=8.0),

    GenerationUnit(
        label='THNF-2', station_label='THNF', bus_label='NRTH',
        unit_type='COAL', rated_mw=300.0, min_mw=90.0,
        ramp_pct_per_min=3.0, inertia_h=5.0, cold_start_min=240.0,
        q_max_mvar=150.0, q_min_mvar=-80.0,
        can_pump=False, active_from_shift=6,
        description='Thornfield Coal Unit 2 — 300MW, 400kV.',
        min_up_time_h=6.0, min_down_time_h=8.0),

    GenerationUnit(
        label='THNF-3', station_label='THNF', bus_label='NRTH',
        unit_type='COAL', rated_mw=300.0, min_mw=90.0,
        ramp_pct_per_min=3.0, inertia_h=5.0, cold_start_min=240.0,
        q_max_mvar=150.0, q_min_mvar=-80.0,
        can_pump=False, active_from_shift=6,
        description='Thornfield Coal Unit 3 — 300MW, 400kV.',
        min_up_time_h=6.0, min_down_time_h=8.0),

    # ── BARROW HYDRO UPPER — BARR (2×250MW, 400kV, bus NRTH) ─────────────
    GenerationUnit(
        label='BARR-1', station_label='BARR', bus_label='NRTH',
        unit_type='HYDRO_PUMP', rated_mw=250.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=120.0, q_min_mvar=-60.0,
        can_pump=True, active_from_shift=6,
        description='Barrow Hydro Upper Unit 1 — 250MW pumped storage, 400kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='BARR-2', station_label='BARR', bus_label='NRTH',
        unit_type='HYDRO_PUMP', rated_mw=250.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=120.0, q_min_mvar=-60.0,
        can_pump=True, active_from_shift=6,
        description='Barrow Hydro Upper Unit 2 — 250MW pumped storage, 400kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    # ── BARROW HYDRO LOWER — BARD (2×80MW, 220kV, bus BARD) ──────────────
    GenerationUnit(
        label='BARD-1', station_label='BARD', bus_label='BARD',
        unit_type='HYDRO', rated_mw=80.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=35.0, q_min_mvar=-20.0,
        can_pump=False, active_from_shift=6,
        description='Barrow Hydro Lower Unit 1 — 80MW downstream, 220kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='BARD-2', station_label='BARD', bus_label='BARD',
        unit_type='HYDRO', rated_mw=80.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=35.0, q_min_mvar=-20.0,
        can_pump=False, active_from_shift=6,
        description='Barrow Hydro Lower Unit 2 — 80MW downstream, 220kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    # ── CAIRN WIND — WNCN (2×250MW, 220kV, bus WNCN) ─────────────────────
    # Two aggregated blocks so wind trips are partial, not all-or-nothing.
    GenerationUnit(
        label='WNCN-1', station_label='WNCN', bus_label='WNCN',
        unit_type='WIND', rated_mw=250.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=0.0, cold_start_min=0.0,
        q_max_mvar=0.0, q_min_mvar=0.0,
        can_pump=False, active_from_shift=6,
        description='Cairn Wind Farm Block A — 250MW aggregated, 220kV. Uncontrollable.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='WNCN-2', station_label='WNCN', bus_label='WNCN',
        unit_type='WIND', rated_mw=250.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=0.0, cold_start_min=0.0,
        q_max_mvar=0.0, q_min_mvar=0.0,
        can_pump=False, active_from_shift=6,
        description='Cairn Wind Farm Block B — 250MW aggregated, 220kV. Uncontrollable.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    # ── STANTON SOLAR — SLST (600MW, 220kV, bus SLST) ────────────────────
    GenerationUnit(
        label='SLST-1', station_label='SLST', bus_label='SLST',
        unit_type='SOLAR', rated_mw=600.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=0.0, cold_start_min=0.0,
        q_max_mvar=0.0, q_min_mvar=0.0,
        can_pump=False, active_from_shift=7,
        description='Stanton Solar Park — 600MW aggregated, 220kV. Zero output at night.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    # ── FELDON SOLAR — SLFD (400MW, 150kV, bus FLDN) ─────────────────────
    GenerationUnit(
        label='SLFD-1', station_label='SLFD', bus_label='FLDN',
        unit_type='SOLAR', rated_mw=400.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=0.0, cold_start_min=0.0,
        q_max_mvar=0.0, q_min_mvar=0.0,
        can_pump=False, active_from_shift=7,
        description='Feldon Solar Park — 400MW aggregated, 150kV. Zero output at night.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    # ── RIVER COLN CASCADE — CO01-CO03 (2 units each, 150kV) ─────────────
    GenerationUnit(
        label='CO01-1', station_label='CO01', bus_label='CO01',
        unit_type='HYDRO_ROR', rated_mw=28.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=11.0, q_min_mvar=-6.0,
        can_pump=False, active_from_shift=7,
        description='River Coln Station 1 Unit 1 — 28MW run-of-river, 150kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='CO01-2', station_label='CO01', bus_label='CO01',
        unit_type='HYDRO_ROR', rated_mw=28.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=11.0, q_min_mvar=-6.0,
        can_pump=False, active_from_shift=7,
        description='River Coln Station 1 Unit 2 — 28MW run-of-river, 150kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='CO02-1', station_label='CO02', bus_label='CO02',
        unit_type='HYDRO_ROR', rated_mw=23.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=9.0, q_min_mvar=-5.0,
        can_pump=False, active_from_shift=7,
        description='River Coln Station 2 Unit 1 — 23MW run-of-river, 150kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='CO02-2', station_label='CO02', bus_label='CO02',
        unit_type='HYDRO_ROR', rated_mw=23.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=9.0, q_min_mvar=-5.0,
        can_pump=False, active_from_shift=7,
        description='River Coln Station 2 Unit 2 — 23MW run-of-river, 150kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='CO03-1', station_label='CO03', bus_label='CO03',
        unit_type='HYDRO_ROR', rated_mw=18.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=7.0, q_min_mvar=-4.0,
        can_pump=False, active_from_shift=7,
        description='River Coln Station 3 Unit 1 — 18MW run-of-river, 150kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),

    GenerationUnit(
        label='CO03-2', station_label='CO03', bus_label='CO03',
        unit_type='HYDRO_ROR', rated_mw=18.0, min_mw=0.0,
        ramp_pct_per_min=100.0, inertia_h=3.0, cold_start_min=5.0,
        q_max_mvar=7.0, q_min_mvar=-4.0,
        can_pump=False, active_from_shift=7,
        description='River Coln Station 3 Unit 2 — 18MW run-of-river, 150kV.',
        min_up_time_h=0.0, min_down_time_h=0.0),
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
    # 400kV spine stations (above the spine)
    'KELM': (180,  80),
    'RVSD': (400,  80),
    'DUNH': (570,  80),
    'HART': (800,  80),
    'THNF': (1350, 80),
    'BARR': (1500, 80),
    # Capital CCGT (above their 220kV buses)
    'ASHG': (880,  260),
    'WRNG': (1180, 260),
    # West hydro pocket (re-spaced Stage 27 — see topology.py bus comment)
    'DUND': (640,  380),
    'KELD': (40,   680),
    'AR01': (230,  480),
    'AR02': (340,  680),
    'AR03': (510,  670),
    'AR04': (760,  590),
    # East pocket
    'BARD': (1620, 490),
    'WNCN': (1300, 510),
    'SLST': (1740, 420),
    # 150kV south mesh
    'WNBR': (700,  670),
    'BR01': (590,  730),
    'BR02': (510,  770),
    'BR03': (420,  800),
    # 150kV east mesh
    'SLFD': (1570, 530),
    'CO01': (1250, 560),
    'CO02': (1190, 710),
    'CO03': (1120, 760),
}


def get_station_position(station_label: str) -> tuple[int, int]:
    """Return canvas position for a station, with layout overrides applied."""
    from data.layout_override import get_station_pos
    return get_station_pos(station_label, STATION_POSITIONS[station_label])
