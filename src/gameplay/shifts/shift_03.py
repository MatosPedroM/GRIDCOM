"""
src/gameplay/shifts/shift_03.py

Shift 3 scenario — N-1 line redundancy on the capital ring.

Narrative:
  The capital grid expands to 10 buses. HART-1 nuclear (680 MW) at STHW is
  the dominant source, feeding the Ashford area via L09 (STHW↔ASHF
  transformer, very low reactance). ASHF carries the LD02 load centre
  through the STAN 150kV substation. A scheduled maintenance outage on L09
  at 16:00 forces all STHW→ASHF power onto the 220kV capital ring
  (L10→WRNT, L16→FAIR, L15→ASHF). Without pre-emptive redispatch, L15/L16
  climb through 90% and overload as the evening ramp builds. Ramping
  ASHG-1 (the CCGT at ASHF itself) before 16:00 keeps the ring below ~70%
  and the grid N-1 secure.

Teaching goal: N-1 security. The player must pre-position generation near
load (ASHG-1 at ASHF) before a planned outage removes the dominant supply
path (L09).

MAINTENANCE_LINES: L50 (DUND↔LD02) starts this shift open. LD02 is now fed
exclusively via ASHF/STAN (L29→L33). Campaign code opens L50 at shift
initialisation before the first load-flow solve. L49 (DUND↔LD01) remains
in service — LD01 still hangs off DUND until the south mesh closes in
Shift 4.
"""

from __future__ import annotations


SHIFT_DATE: str = 'MON 07 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

HANDOVER_NOTES: tuple[str, ...] = (
    'Afternoon handover, 14:00.',
    'Capital grid expansion energised. STHW and CNTR 400kV on the spine.',
    'HART-1 nuclear on-line at 680 MW at STHW. HART-2 on planned outage (relay checks).',
    'RVSD-1 120 MW, RVSD-2 returned from maintenance at 50 MW.',
    'ASHG-1 on-line at 80 MW at ASHF — your key redispatch tool.',
    'WRNG-1 on-line at 80 MW at WRNT. Second CCGT units available — cold start 60 min.',
    'DUND-1/2 hydro on-line at 20 MW each (fast regulation reserve).',
    'DUNH-1/2 pumped hydro on-line at 15 MW each at MDBY (fast reserve).',
    'LD01 load centre active at ~350 MW (via DUND/L49 path).',
    'LD02 main load at ~700 MW via ASHF/STAN — evening ramp toward 950 MW.',
    'AGC active.',
    'L09 STHW↔ASHF: SCHEDULED MAINTENANCE at 16:00. Outage window 16:00–19:00.',
    'Action required: ramp ASHG-1 before 16:00 to pre-position generation at ASHF.',
)

# Units on planned outage at shift start.
MAINTENANCE_UNITS: set[str] = {'HART-2', 'ASHG-2', 'WRNG-2'}

# Lines that start this shift electrically OPEN (maintenance/outage).
# Campaign code applies these before the first load-flow solve.
# L50 DUND↔LD02: LD02 now served via ASHF/STAN exclusively. The south
# 150kV mesh takes over both load subs in Shift 4 (L49 opens then too).
MAINTENANCE_LINES: set[str] = {'L50'}

AGC_ENABLED: bool = True

# Per-bus hourly load table (MW).
# LD02: main capital load centre, served via STHW→ASHF→STAN path.
# LD01: western load centre, served via MDBY→DUND→LD01 path.
SUBSTATION_LOAD_MW: dict[str, dict[float, float]] = {
    'LD02': {
         0.0:   420,  1.0:   400,  2.0:   385,  3.0:   380,  4.0:   385,
         5.0:   400,  6.0:   460,  7.0:   550,  8.0:   640,  9.0:   700,
        10.0:   730, 11.0:   750, 12.0:   740, 13.0:   720, 14.0:   700,
        15.0:   760, 16.0:   820, 17.0:   880, 18.0:   950, 19.0:   920,
        20.0:   860, 21.0:   780, 22.0:   680, 23.0:   560, 24.0:   460,
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
# Total ≈ 1,080 MW against ~1,050 MW demand + losses at 14:00.
# DUND and DUNH units are dispatched low to provide regulation headroom.
INITIAL_SCHEDULE: dict[str, float] = {
    'HART-1':  680.0,   # Hartwell Nuclear 1 — baseload, primary L09 source
    'RVSD-1':  120.0,   # Riverside Coal 1   — carry-forward from Shift 2
    'RVSD-2':   50.0,   # Riverside Coal 2   — returned from relay maintenance
    'ASHG-1':   80.0,   # Ashford CCGT 1     — key redispatch tool at ASHF
    'WRNG-1':   80.0,   # Wrentham CCGT 1    — secondary tool at WRNT
    'DUND-1':   20.0,   # Dunmore Lower 1    — fast regulation
    'DUND-2':   20.0,   # Dunmore Lower 2    — fast regulation
    'DUNH-1':   15.0,   # Dunmore Upper 1    — fast regulation at MDBY
    'DUNH-2':   15.0,   # Dunmore Upper 2    — fast regulation at MDBY
}


# ── Conditions (declarative — see src/data/shift_io.py for the schema) ────────

_ASHG1_BELOW_250MW: dict = {
    'metric': 'UNIT_OUTPUT_MW', 'target': 'ASHG-1', 'op': '<', 'value': 250.0,
}
_L15_HIGH_LOAD: dict = {
    'metric': 'LINE_LOADING', 'target': 'L15', 'op': '>', 'value': 85.0,
}
_L15_NOT_HIGH_LOAD: dict = {
    'metric': 'LINE_LOADING', 'target': 'L15', 'op': '<=', 'value': 85.0,
}


# ── Scripted events ────────────────────────────────────────────────────────────

SCRIPTED_EVENTS: list[dict] = [
    {
        # T+0 (14:00) — shift start briefing
        'trigger_min':  0.0,
        'priority':    'INFO',
        'message':     'Capital ring energised. L09 carrying HART-1 output to Ashford.',
        'detail':      ('STHW and CNTR 400kV are now on the spine. HART-1 nuclear '
                        '(680 MW) is the dominant generator. L09 (STHW↔ASHF '
                        'transformer) carries ~90% of the STHW→ASHF flow due to '
                        'its very low reactance. The ring (L10, L16, L15) is '
                        'lightly loaded in normal operation.'),
        'element':     'L09',
        'condition':   None,
    },
    {
        # T+60 (15:00) — one-hour maintenance warning
        'trigger_min':  60.0,
        'priority':    'WARNING',
        'message':     'L09 STHW↔ASHF: scheduled maintenance at 16:00.',
        'detail':      ('L09 will open at 16:00 for transformer inspection '
                        '(window 16:00–19:00). When L09 opens, all STHW→ASHF '
                        'power must reroute via the 220kV ring '
                        '(L10→WRNT, L16→FAIR, L15→ASHF). With ASHG-1 at 80 MW '
                        'the ring will exceed 90% as the evening ramp builds. '
                        'Ramp ASHG-1 now — generation at ASHF directly reduces '
                        'what must transit the ring.'),
        'element':     'L09',
        'condition':   None,
    },
    {
        # T+90 (15:30) — conditional 30-min reminder if player has not acted
        'trigger_min':  90.0,
        'priority':    'WARNING',
        'message':     '30 min to L09 outage. ASHG-1 still below 250 MW.',
        'detail':      ('L09 opens in 30 minutes. ASHG-1 output is currently low. '
                        'Ramp ASHG-1 toward 350–400 MW to cover the LD02 load '
                        'locally at ASHF. Each additional 100 MW at ASHG-1 '
                        'reduces ring loading by approximately 12% post-outage.'),
        'element':     'ASHG-1',
        'condition':   _ASHG1_BELOW_250MW,
    },
    {
        # T+120 (16:00) — open L09 for maintenance
        'trigger_min': 120.0,
        'priority':    'MAINTENANCE',
        'message':     'L09 STHW↔ASHF: opening for scheduled maintenance.',
        'detail':      ('L09 is now open. Maintenance window: 16:00–19:00. '
                        'Monitor L15 and L16 loading. If either exceeds 85%, '
                        'ramp ASHG-1 further. Reducing HART-1 also helps, but '
                        'note its very slow ramp rate (1%/min). '
                        'L09 will return to service at 19:00.'),
        'element':     'L09',
        'condition':   None,
        'action':      {'type': 'LINE_OPEN', 'line': 'L09'},
    },
    {
        # T+120 (16:00) — alarm branch: ring overloaded
        'trigger_min': 120.0,
        'priority':    'ALARM',
        'message':     'L15 ASHF↔FAIR — HIGH LOAD. Ramp ASHG-1 to reduce ring loading.',
        'detail':      ('L15 is above 85% loading following the L09 opening. '
                        'Ramp ASHG-1 to supply the Ashford load locally and '
                        'reduce the power transiting WRNT→FAIR→ASHF. The evening '
                        'ramp will push the ring over 100% within the hour if '
                        'you do not act.'),
        'element':     'L15',
        'condition':   _L15_HIGH_LOAD,
    },
    {
        # T+120 (16:00) — nominal branch: player prepared correctly
        'trigger_min': 120.0,
        'priority':    'INFO',
        'message':     'L09 open. Ring loading nominal.',
        'detail':      ('L09 is open for maintenance. ASHG pre-dispatch has kept '
                        'L15 and L16 within normal limits. The grid is operating '
                        'N-1 secure. L09 returns at 19:00.'),
        'element':     'L09',
        'condition':   _L15_NOT_HIGH_LOAD,
    },
    {
        # T+300 (19:00) — restore L09
        'trigger_min': 300.0,
        'priority':    'INFO',
        'message':     'L09 STHW↔ASHF: returned to service.',
        'detail':      ('L09 maintenance is complete. The transformer is back in '
                        'service and taking load. L15 and L16 loading will reduce '
                        'as flow reverts to the low-reactance L09 path. '
                        'You may ramp ASHG-1 back down if desired.'),
        'element':     'L09',
        'condition':   None,
        'action':      {'type': 'LINE_CLOSE', 'line': 'L09'},
    },
]


# ── Scoring hooks ──────────────────────────────────────────────────────────────
#
# BONUS_N1_SECURE: awarded if L15 and L16 never exceed 80% during the L09
#   outage window (16:00–19:00, sim minutes 120–300).
#
# PENALTY_RING_CONGESTION: applied per simulated minute that L15 or L16 is
#   above 85% during the L09 outage window.
#
# Standard KPIs also apply: frequency deviation, max line loading, min VSI.

SCORING_HOOKS: dict = {
    'bonus_n1_secure': {
        'description': 'L15 and L16 never exceed 80% during L09 outage window',
        'window_min':  (120.0, 300.0),
        'lines':       ('L15', 'L16'),
        'threshold':   80.0,
        'points':      200,
    },
    'penalty_ring_congestion': {
        'description': 'Per-minute penalty when L15 or L16 exceeds 85%',
        'window_min':  (120.0, 300.0),
        'lines':       ('L15', 'L16'),
        'threshold':   85.0,
        'points_per_minute': -15,
    },
}
