"""
src/gameplay/shifts/shift_03.py

Shift 3 scenario — N-1 line redundancy.

Narrative:
  The centre grid expands to 10 buses. HART-1 nuclear (680 MW) is the dominant
  source at CNTR, feeding the Wrentham area via L09 (CNTR↔WRNT transformer, very
  low reactance). A scheduled maintenance outage on L09 at 16:00 forces all
  CNTR→WRNT power onto the 220kV ring (L12–L13). Without pre-emptive redispatch,
  L13 reaches ~87% loading — a high-load alarm. Ramping WRNG-1 before 16:00 keeps
  the ring below 55% and the grid N-1 secure.

Teaching goal: N-1 security. The player must pre-position generation near load
(WRNG-1 at WRNT) before a planned outage removes the dominant supply path (L09).

MAINTENANCE_LINES: L48 (DUND↔LD02) starts this shift open. LD02 is now fed
exclusively via STAN/L38. Campaign code must open L48 at shift initialisation
before the first load-flow solve. L48 will close again in Shift 4 when DUNM
comes online and DUND reconnects through the proper 220kV ring.
"""

from __future__ import annotations


SHIFT_DATE: str = 'MON 07 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

HANDOVER_NOTES: tuple[str, ...] = (
    'Afternoon handover, 14:00.',
    'Centre grid expansion energised. CNTR 400kV backbone online.',
    'HART-1 nuclear on-line at 680 MW. HART-2 on planned outage (relay checks).',
    'RVSD-1 200 MW, RVSD-2 returned from maintenance at 50 MW.',
    'ASHG-1 on-line at 80 MW (connected at ASHF 220kV bus).',
    'WRNG-1 on-line at 80 MW. WRNG-2 available — cold start 60 min.',
    'DUND-1 hydro on-line at 30 MW (fast regulation reserve).',
    'DUNH-1 hydro on-line at 80 MW at STHW (fast regulation reserve).',
    'SLST-1 solar generating approximately 576 MW, declining through afternoon.',
    'LD01 load centre active at ~350 MW (via DUND/L47 path).',
    'LD02 main load at 1200 MW (via STAN/L38 path).',
    'AGC active.',
    'L09 CNTR↔WRNT: SCHEDULED MAINTENANCE at 16:00. Outage window 16:00–19:00.',
    'Action required: ramp WRNG-1 before 16:00 to pre-position generation at WRNT.',
)

# Units on planned outage at shift start.
MAINTENANCE_UNITS: set[str] = {'HART-2', 'WRNG-2', 'ASHG-2'}

# Lines that start this shift electrically OPEN (maintenance/outage).
# Campaign code must apply these before the first load-flow solve.
# L48 DUND↔LD02: LD02 now served via STAN/L38 exclusively. L48 re-closes in Shift 4.
MAINTENANCE_LINES: set[str] = {'L48'}

AGC_ENABLED: bool = True

# Per-bus hourly load table (MW).
# LD02: main central/eastern load centre, served via CNTR→WRNT→STAN path.
# LD01: northern load centre, served via MDBY→DUND→LD01 path.
SUBSTATION_LOAD_MW: dict[str, dict[float, float]] = {
    'LD02': {
         0.0:   600,  1.0:   570,  2.0:   550,  3.0:   540,  4.0:   545,
         5.0:   570,  6.0:   650,  7.0:   780,  8.0:   920,  9.0:  1020,
        10.0:  1080, 11.0:  1120, 12.0:  1160, 13.0:  1190, 14.0:  1200,
        15.0:  1260, 16.0:  1300, 17.0:  1400, 18.0:  1480, 19.0:  1420,
        20.0:  1320, 21.0:  1200, 22.0:  1060, 23.0:   880, 24.0:   720,
    },
    'LD01': {
         0.0:   200,  1.0:   190,  2.0:   183,  3.0:   180,  4.0:   182,
         5.0:   190,  6.0:   217,  7.0:   260,  8.0:   307,  9.0:   340,
        10.0:   360, 11.0:   373, 12.0:   387, 13.0:   395, 14.0:   350,
        15.0:   375, 16.0:   400, 17.0:   425, 18.0:   450, 19.0:   435,
        20.0:   410, 21.0:   390, 22.0:   350, 23.0:   290, 24.0:   240,
    },
}

# Starting dispatch — units absent from this dict start OFFLINE.
# SLST-1 is a solar unit; its output is computed by the renewables model,
# not set here. At 14:00 it contributes ~576 MW declining through the afternoon.
# DUND-1 and DUNH-1 are dispatched below rated capacity to provide regulation
# headroom (±35 MW and ±120 MW respectively).
INITIAL_SCHEDULE: dict[str, float] = {
    'HART-1':  680.0,   # Hartwell Nuclear 1 — baseload, primary L09 source
    'RVSD-1':  200.0,   # Riverside Coal 1   — carry-forward from Shift 2
    'RVSD-2':   50.0,   # Riverside Coal 2   — reduced; solar covers more at start
    'ASHG-1':   80.0,   # Ashford CCGT 1     — spinning reserve at ASHF
    'WRNG-1':   80.0,   # Wrentham CCGT 1    — key redispatch tool at WRNT
    'DUND-1':   30.0,   # Dunmore Lower Hydro 1 — fast regulation, headroom ±35 MW
    'DUNH-1':   80.0,   # Dunmore Upper Hydro 1 — fast regulation, headroom ±120 MW
}


# ── Condition helpers ──────────────────────────────────────────────────────────

def _wrng1_below_200mw(fleet) -> bool:
    """True when WRNG-1 output is still below 200 MW at the 30-min warning."""
    return fleet.get_output_mw('WRNG-1') < 200.0


def _l13_high_load(grid) -> bool:
    """True when L13 loading exceeds 85% immediately after L09 opens."""
    return grid.get_line_loading_pct('L13') > 85.0


# ── Scripted events ────────────────────────────────────────────────────────────

SCRIPTED_EVENTS: list[dict] = [
    {
        # T+0 (14:00) — shift start briefing
        'trigger_min':  0.0,
        'priority':    'INFO',
        'message':     'Centre grid energised. L09 carrying HART-1 output to Wrentham.',
        'detail':      ('CNTR 400kV backbone is now live. HART-1 nuclear (680 MW) '
                        'is the dominant generator. L09 (CNTR↔WRNT transformer) '
                        'carries ~94% of the CNTR→WRNT flow due to its very low '
                        'reactance. L13 and L12 are lightly loaded in normal operation.'),
        'element':     'L09',
        'condition':   None,
    },
    {
        # T+60 (15:00) — one-hour maintenance warning
        'trigger_min':  60.0,
        'priority':    'WARNING',
        'message':     'L09 CNTR↔WRNT: scheduled maintenance at 16:00.',
        'detail':      ('L09 will open at 16:00 for transformer inspection '
                        '(window 16:00–19:00). When L09 opens, all CNTR→WRNT '
                        'power must reroute via the 220kV ring (L12→FAIR→L13). '
                        'If HART-1 continues at 680 MW, L13 will reach ~87% loading. '
                        'Ramp WRNG-1 now to pre-position generation at WRNT and '
                        'reduce what must reroute through the ring.'),
        'element':     'L09',
        'condition':   None,
    },
    {
        # T+90 (15:30) — conditional 30-min reminder if player has not acted
        'trigger_min':  90.0,
        'priority':    'WARNING',
        'message':     '30 min to L09 outage. WRNG-1 still below 200 MW.',
        'detail':      ('L09 opens in 30 minutes. WRNG-1 output is currently low. '
                        'Ramp WRNG-1 toward 300–350 MW to reduce the load that must '
                        'reroute through L12 and L13. Each additional 100 MW at '
                        'WRNG-1 reduces L13 loading by approximately 12% post-trip.'),
        'element':     'WRNG-1',
        'condition':   _wrng1_below_200mw,
    },
    {
        # T+120 (16:00) — open L09 for maintenance
        'trigger_min': 120.0,
        'priority':    'MAINTENANCE',
        'message':     'L09 CNTR↔WRNT: opening for scheduled maintenance.',
        'detail':      ('L09 is now open. Maintenance window: 16:00–19:00. '
                        'Monitor L12 and L13 loading. If either exceeds 85%, '
                        'reduce HART-1 output or ramp WRNG-1 further. '
                        'L09 will return to service at 19:00.'),
        'element':     'L09',
        'condition':   None,
        'action':      {'type': 'LINE_OPEN', 'line': 'L09'},
    },
    {
        # T+120 (16:00) — alarm branch: ring overloaded
        'trigger_min': 120.0,
        'priority':    'ALARM',
        'message':     'L13 FAIR↔WRNT — HIGH LOAD. Ramp WRNG to reduce ring loading.',
        'detail':      ('L13 is above 85% loading following the L09 opening. '
                        'Ramp WRNG-1 to shift generation from CNTR to WRNT and '
                        'reduce the power transiting L12→L13. Alternatively, reduce '
                        'HART-1 output — but note its very slow ramp rate (1%/min). '
                        'Act quickly to restore N-1 security before demand rises further.'),
        'element':     'L13',
        'condition':   _l13_high_load,
    },
    {
        # T+120 (16:00) — nominal branch: player prepared correctly
        'trigger_min': 120.0,
        'priority':    'INFO',
        'message':     'L09 open. Ring loading nominal.',
        'detail':      ('L09 is open for maintenance. WRNG pre-dispatch has kept '
                        'L12 and L13 within normal limits. The grid is operating '
                        'N-1 secure. L09 returns at 19:00.'),
        'element':     'L09',
        'condition':   lambda grid: not _l13_high_load(grid),
    },
    {
        # T+300 (19:00) — restore L09
        'trigger_min': 300.0,
        'priority':    'INFO',
        'message':     'L09 CNTR↔WRNT: returned to service.',
        'detail':      ('L09 maintenance is complete. The transformer is back in '
                        'service and taking load. L12 and L13 loading will reduce '
                        'as flow reverts to the low-reactance L09 path. '
                        'You may ramp WRNG-1 back down if desired.'),
        'element':     'L09',
        'condition':   None,
        'action':      {'type': 'LINE_CLOSE', 'line': 'L09'},
    },
]


# ── Scoring hooks ──────────────────────────────────────────────────────────────
#
# BONUS_N1_SECURE: awarded if L12 and L13 never exceed 80% during the L09 outage
#   window (16:00–19:00, sim minutes 120–300).
#
# PENALTY_RING_CONGESTION: applied per simulated minute that L12 or L13 is above
#   85% during the L09 outage window.
#
# Standard KPIs also apply: frequency deviation, max line loading, min VSI.

SCORING_HOOKS: dict = {
    'bonus_n1_secure': {
        'description': 'L12 and L13 never exceed 80% during L09 outage window',
        'window_min':  (120.0, 300.0),
        'lines':       ('L12', 'L13'),
        'threshold':   80.0,
        'points':      200,
    },
    'penalty_ring_congestion': {
        'description': 'Per-minute penalty when L12 or L13 exceeds 85%',
        'window_min':  (120.0, 300.0),
        'lines':       ('L12', 'L13'),
        'threshold':   85.0,
        'points_per_minute': -15,
    },
}
