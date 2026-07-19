"""
src/gameplay/shifts/shift_10.py

Shift 10 scenario — the campaign finale, run on a grid built in the Grid
Designer and saved as its own campaign-owned file
(src/assets/designer_grids/shift10.json) instead of the shared
topology.py/fleet.py subset every other shift uses: 57 buses, 115 lines,
30 units across 14 stations. Kept separate from any player scratch design
in the Grid Designer (e.g. "Alpha", the grid this was originally built as)
so player edits there can never affect the campaign. See GRID_SOURCE below
and gameplay/shifts/loader.py for how this is wired in.

Narrative:
  Final shift, peak demand day, 06:00-18:00. Every station on Alpha's grid
  is live and dispatchable at once, with demand scaled to hit the
  campaign's signature 8,000 MW evening peak. Alpha's fleet is smaller and
  differently-shaped than the original 47-unit Shift 10 fleet — 14
  stations, no nuclear baseload and no solar, split across coal (RVSD,
  THNF), CCGT (ASHG, WRNG), pumped-storage and run-of-river hydro (BARR,
  KELM, DUNH upper stations; BARD, DUND, KELD lower stations; AR01, AR03
  cascade), and wind (WNCN, WNBR). Firm capacity (coal + CCGT + pumped
  storage + lower hydro) is a little over 5,100 MW against the 8,000 MW
  peak — noticeably tighter than the original fleet's ~6,650 MW margin,
  so run-of-river and wind output plus careful reserve-margin management
  matter even more today. RVSD-3 is on planned outage, trimming available
  firm capacity below its nameplate ceiling for the whole shift.

  AGC is off — this is the manual-dispatch finale, no automatic
  frequency regulation to fall back on. A late-morning wind lull tests
  reserve staging discipline, and the evening ramp tests whether CCGT and
  pumped storage were held back far enough to cover the peak.
"""

from __future__ import annotations


SHIFT_DATE: str = 'THU 10 NOV 1994'

DIFFICULTY_LABEL: str = 'Expert'

# Names the saved Grid Designer grid this shift runs on, in place of the
# shared topology.py/fleet.py subset every other campaign shift uses. See
# gameplay/shifts/loader.py:load_shift_config() and
# main._make_sim_and_renderer() for how this is resolved.
GRID_SOURCE: str = 'shift10'

HANDOVER_NOTES: tuple[str, ...] = (
    'Final shift, 06:00. Full Alpha grid energised — 57 buses, 115 lines, 30 units live.',
    'Peak demand forecast 8,000 MW this evening. System at full stretch.',
    'RVSD-1/2 and THNF-1/2 coal online at partial load, ramp headroom held for the day.',
    'RVSD-3 out of service — planned inspection, back next shift.',
    'ASHG-1/2 and WRNG-1/2 CCGT at morning minimum, held in reserve for the peaks.',
    'DUNH, KELM, BARR pumped storage and DUND/KELD/BARD lower hydro held low — fast regulation reserve.',
    'River Arden cascade (AR01, AR03) running at available flow.',
    'Cairn Wind (WNCN) and Brackley Wind (WNBR) strong this morning; forecast shows a lull approaching midday.',
    'No nuclear or solar on this grid — firm capacity margin is tighter than usual, watch it.',
    'AGC is OFF. No automatic frequency regulation — every MW is your call.',
    'Frequency nominal. For now.',
)

# Units on planned outage at shift start.
MAINTENANCE_UNITS: set[str] = set()

# No lines start open — full mesh intact at shift start.
MAINTENANCE_LINES: set[str] = set()

AGC_ENABLED: bool = True

# Per-bus hourly load table (MW). Full grid: 11 load buses.
# LD01-LD06 retain a small residual (~5% of their old standalone curve) —
# the bulk of what they used to carry now routes through 5 dedicated
# substations (LD07, LD09, LD11-LD13), each dual-fed from its own region's
# 2 spine-anchor buses (see the region table in topology.py's BUSES
# comment). These were originally 23 separate single-feed substations
# Per-bus hourly load table (MW). Alpha grid: 24 load buses. Each bus's
# peak MW (from Alpha.json) is scaled by a uniform factor so the system
# total lands on the campaign's signature 8,000 MW peak at hour 18:00,
# then shaped across the day with the same normalised demand curve every
# other shift uses (data.profiles.DEMAND_PROFILE_NORMALISED). Generated
# from the Grid Designer's saved Alpha grid — see STAGE_STATUS.md.
SUBSTATION_LOAD_MW: dict[str, dict[float, float]] = {
    'BREN': {
           0.0:    131,   1.0:    124,   2.0:    118,   3.0:    115,   4.0:    116,
           5.0:    127,   6.0:    160,   7.0:    211,   8.0:    262,   9.0:    298,
          10.0:    316,  11.0:    324,  12.0:    320,  13.0:    313,  14.0:    309,
          15.0:    316,  16.0:    331,  17.0:    349,  18.0:    364,  19.0:    356,
          20.0:    338,  21.0:    313,  22.0:    269,  23.0:    196,  24.0:    142,
    },
    'BRID': {
           0.0:     98,   1.0:     93,   2.0:     89,   3.0:     86,   4.0:     87,
           5.0:     95,   6.0:    120,   7.0:    158,   8.0:    196,   9.0:    224,
          10.0:    237,  11.0:    243,  12.0:    240,  13.0:    235,  14.0:    232,
          15.0:    237,  16.0:    248,  17.0:    262,  18.0:    273,  19.0:    267,
          20.0:    254,  21.0:    235,  22.0:    202,  23.0:    147,  24.0:    106,
    },
    'BURN': {
           0.0:     65,   1.0:     62,   2.0:     59,   3.0:     57,   4.0:     58,
           5.0:     64,   6.0:     80,   7.0:    105,   8.0:    131,   9.0:    149,
          10.0:    158,  11.0:    162,  12.0:    160,  13.0:    156,  14.0:    155,
          15.0:    158,  16.0:    165,  17.0:    175,  18.0:    182,  19.0:    178,
          20.0:    169,  21.0:    156,  22.0:    135,  23.0:     98,  24.0:     71,
    },
    'COVE': {
           0.0:    131,   1.0:    124,   2.0:    118,   3.0:    115,   4.0:    116,
           5.0:    127,   6.0:    160,   7.0:    211,   8.0:    262,   9.0:    298,
          10.0:    316,  11.0:    324,  12.0:    320,  13.0:    313,  14.0:    309,
          15.0:    316,  16.0:    331,  17.0:    349,  18.0:    364,  19.0:    356,
          20.0:    338,  21.0:    313,  22.0:    269,  23.0:    196,  24.0:    142,
    },
    'CRAG': {
           0.0:    131,   1.0:    124,   2.0:    118,   3.0:    115,   4.0:    116,
           5.0:    127,   6.0:    160,   7.0:    211,   8.0:    262,   9.0:    298,
          10.0:    316,  11.0:    324,  12.0:    320,  13.0:    313,  14.0:    309,
          15.0:    316,  16.0:    331,  17.0:    349,  18.0:    364,  19.0:    356,
          20.0:    338,  21.0:    313,  22.0:    269,  23.0:    196,  24.0:    142,
    },
    'DALE': {
           0.0:    196,   1.0:    185,   2.0:    177,   3.0:    172,   4.0:    175,
           5.0:    191,   6.0:    240,   7.0:    316,   8.0:    393,   9.0:    447,
          10.0:    475,  11.0:    485,  12.0:    480,  13.0:    469,  14.0:    464,
          15.0:    475,  16.0:    496,  17.0:    524,  18.0:    545,  19.0:    535,
          20.0:    507,  21.0:    469,  22.0:    404,  23.0:    295,  24.0:    213,
    },
    'ELMR': {
           0.0:     65,   1.0:     62,   2.0:     59,   3.0:     57,   4.0:     58,
           5.0:     64,   6.0:     80,   7.0:    105,   8.0:    131,   9.0:    149,
          10.0:    158,  11.0:    162,  12.0:    160,  13.0:    156,  14.0:    155,
          15.0:    158,  16.0:    165,  17.0:    175,  18.0:    182,  19.0:    178,
          20.0:    169,  21.0:    156,  22.0:    135,  23.0:     98,  24.0:     71,
    },
    'FELL': {
           0.0:    131,   1.0:    124,   2.0:    118,   3.0:    115,   4.0:    116,
           5.0:    127,   6.0:    160,   7.0:    211,   8.0:    262,   9.0:    298,
          10.0:    316,  11.0:    324,  12.0:    320,  13.0:    313,  14.0:    309,
          15.0:    316,  16.0:    331,  17.0:    349,  18.0:    364,  19.0:    356,
          20.0:    338,  21.0:    313,  22.0:    269,  23.0:    196,  24.0:    142,
    },
    'FORD': {
           0.0:     65,   1.0:     62,   2.0:     59,   3.0:     57,   4.0:     58,
           5.0:     64,   6.0:     80,   7.0:    105,   8.0:    131,   9.0:    149,
          10.0:    158,  11.0:    162,  12.0:    160,  13.0:    156,  14.0:    155,
          15.0:    158,  16.0:    165,  17.0:    175,  18.0:    182,  19.0:    178,
          20.0:    169,  21.0:    156,  22.0:    135,  23.0:     98,  24.0:     71,
    },
    'GLEN': {
           0.0:    131,   1.0:    124,   2.0:    118,   3.0:    115,   4.0:    116,
           5.0:    127,   6.0:    160,   7.0:    211,   8.0:    262,   9.0:    298,
          10.0:    316,  11.0:    324,  12.0:    320,  13.0:    313,  14.0:    309,
          15.0:    316,  16.0:    331,  17.0:    349,  18.0:    364,  19.0:    356,
          20.0:    338,  21.0:    313,  22.0:    269,  23.0:    196,  24.0:    142,
    },
    'HALE': {
           0.0:    131,   1.0:    124,   2.0:    118,   3.0:    115,   4.0:    116,
           5.0:    127,   6.0:    160,   7.0:    211,   8.0:    262,   9.0:    298,
          10.0:    316,  11.0:    324,  12.0:    320,  13.0:    313,  14.0:    309,
          15.0:    316,  16.0:    331,  17.0:    349,  18.0:    364,  19.0:    356,
          20.0:    338,  21.0:    313,  22.0:    269,  23.0:    196,  24.0:    142,
    },
    'HOLM': {
           0.0:     98,   1.0:     93,   2.0:     89,   3.0:     86,   4.0:     87,
           5.0:     95,   6.0:    120,   7.0:    158,   8.0:    196,   9.0:    224,
          10.0:    237,  11.0:    243,  12.0:    240,  13.0:    235,  14.0:    232,
          15.0:    237,  16.0:    248,  17.0:    262,  18.0:    273,  19.0:    267,
          20.0:    254,  21.0:    235,  22.0:    202,  23.0:    147,  24.0:    106,
    },
    'HRBR': {
           0.0:     65,   1.0:     62,   2.0:     59,   3.0:     57,   4.0:     58,
           5.0:     64,   6.0:     80,   7.0:    105,   8.0:    131,   9.0:    149,
          10.0:    158,  11.0:    162,  12.0:    160,  13.0:    156,  14.0:    155,
          15.0:    158,  16.0:    165,  17.0:    175,  18.0:    182,  19.0:    178,
          20.0:    169,  21.0:    156,  22.0:    135,  23.0:     98,  24.0:     71,
    },
    'KNOB': {
           0.0:    196,   1.0:    185,   2.0:    177,   3.0:    172,   4.0:    175,
           5.0:    191,   6.0:    240,   7.0:    316,   8.0:    393,   9.0:    447,
          10.0:    475,  11.0:    485,  12.0:    480,  13.0:    469,  14.0:    464,
          15.0:    475,  16.0:    496,  17.0:    524,  18.0:    545,  19.0:    535,
          20.0:    507,  21.0:    469,  22.0:    404,  23.0:    295,  24.0:    213,
    },
    'LAKE': {
           0.0:    131,   1.0:    124,   2.0:    118,   3.0:    115,   4.0:    116,
           5.0:    127,   6.0:    160,   7.0:    211,   8.0:    262,   9.0:    298,
          10.0:    316,  11.0:    324,  12.0:    320,  13.0:    313,  14.0:    309,
          15.0:    316,  16.0:    331,  17.0:    349,  18.0:    364,  19.0:    356,
          20.0:    338,  21.0:    313,  22.0:    269,  23.0:    196,  24.0:    142,
    },
    'MERE': {
           0.0:     65,   1.0:     62,   2.0:     59,   3.0:     57,   4.0:     58,
           5.0:     64,   6.0:     80,   7.0:    105,   8.0:    131,   9.0:    149,
          10.0:    158,  11.0:    162,  12.0:    160,  13.0:    156,  14.0:    155,
          15.0:    158,  16.0:    165,  17.0:    175,  18.0:    182,  19.0:    178,
          20.0:    169,  21.0:    156,  22.0:    135,  23.0:     98,  24.0:     71,
    },
    'MNTN': {
           0.0:    131,   1.0:    124,   2.0:    118,   3.0:    115,   4.0:    116,
           5.0:    127,   6.0:    160,   7.0:    211,   8.0:    262,   9.0:    298,
          10.0:    316,  11.0:    324,  12.0:    320,  13.0:    313,  14.0:    309,
          15.0:    316,  16.0:    331,  17.0:    349,  18.0:    364,  19.0:    356,
          20.0:    338,  21.0:    313,  22.0:    269,  23.0:    196,  24.0:    142,
    },
    'MOOR': {
           0.0:    196,   1.0:    185,   2.0:    177,   3.0:    172,   4.0:    175,
           5.0:    191,   6.0:    240,   7.0:    316,   8.0:    393,   9.0:    447,
          10.0:    475,  11.0:    485,  12.0:    480,  13.0:    469,  14.0:    464,
          15.0:    475,  16.0:    496,  17.0:    524,  18.0:    545,  19.0:    535,
          20.0:    507,  21.0:    469,  22.0:    404,  23.0:    295,  24.0:    213,
    },
    'PEAK': {
           0.0:     98,   1.0:     93,   2.0:     89,   3.0:     86,   4.0:     87,
           5.0:     95,   6.0:    120,   7.0:    158,   8.0:    196,   9.0:    224,
          10.0:    237,  11.0:    243,  12.0:    240,  13.0:    235,  14.0:    232,
          15.0:    237,  16.0:    248,  17.0:    262,  18.0:    273,  19.0:    267,
          20.0:    254,  21.0:    235,  22.0:    202,  23.0:    147,  24.0:    106,
    },
    'PORT': {
           0.0:     65,   1.0:     62,   2.0:     59,   3.0:     57,   4.0:     58,
           5.0:     64,   6.0:     80,   7.0:    105,   8.0:    131,   9.0:    149,
          10.0:    158,  11.0:    162,  12.0:    160,  13.0:    156,  14.0:    155,
          15.0:    158,  16.0:    165,  17.0:    175,  18.0:    182,  19.0:    178,
          20.0:    169,  21.0:    156,  22.0:    135,  23.0:     98,  24.0:     71,
    },
    'ROOK': {
           0.0:    196,   1.0:    185,   2.0:    177,   3.0:    172,   4.0:    175,
           5.0:    191,   6.0:    240,   7.0:    316,   8.0:    393,   9.0:    447,
          10.0:    475,  11.0:    485,  12.0:    480,  13.0:    469,  14.0:    464,
          15.0:    475,  16.0:    496,  17.0:    524,  18.0:    545,  19.0:    535,
          20.0:    507,  21.0:    469,  22.0:    404,  23.0:    295,  24.0:    213,
    },
    'SCAR': {
           0.0:    196,   1.0:    185,   2.0:    177,   3.0:    172,   4.0:    175,
           5.0:    191,   6.0:    240,   7.0:    316,   8.0:    393,   9.0:    447,
          10.0:    475,  11.0:    485,  12.0:    480,  13.0:    469,  14.0:    464,
          15.0:    475,  16.0:    496,  17.0:    524,  18.0:    545,  19.0:    535,
          20.0:    507,  21.0:    469,  22.0:    404,  23.0:    295,  24.0:    213,
    },
    'SHAW': {
           0.0:     65,   1.0:     62,   2.0:     59,   3.0:     57,   4.0:     58,
           5.0:     64,   6.0:     80,   7.0:    105,   8.0:    131,   9.0:    149,
          10.0:    158,  11.0:    162,  12.0:    160,  13.0:    156,  14.0:    155,
          15.0:    158,  16.0:    165,  17.0:    175,  18.0:    182,  19.0:    178,
          20.0:    169,  21.0:    156,  22.0:    135,  23.0:     98,  24.0:     71,
    },
    'WICK': {
           0.0:     98,   1.0:     93,   2.0:     89,   3.0:     86,   4.0:     87,
           5.0:     95,   6.0:    120,   7.0:    158,   8.0:    196,   9.0:    224,
          10.0:    237,  11.0:    243,  12.0:    240,  13.0:    235,  14.0:    232,
          15.0:    237,  16.0:    248,  17.0:    262,  18.0:    273,  19.0:    267,
          20.0:    254,  21.0:    235,  22.0:    202,  23.0:    147,  24.0:    106,
    },
}

# Starting dispatch at 06:00 — units absent from this dict start OFFLINE.
# CCGT and pumped/lower hydro held low deliberately — reserve for the
# midday wind lull and the evening peak ramp. RVSD-3 omitted: on
# maintenance for the whole shift (see MAINTENANCE_UNITS above).
INITIAL_SCHEDULE: dict[str, float] = {
    'DUNH-1': 0.0,
    'DUNH-2': 0.0,
    'KELM-1': 0.0,
    'BARR-1': 0.0,
    'DUND-1': 0.0,
    'DUND-2': 0.0,
    'DUND-3': 0.0,
    'DUND-4': 0.0,
    'KELD-1': 0.0,
    'KELD-2': 0.0,
    'BARD-1': 0.0,
    'BARD-2': 0.0,
    'BARD-3': 0.0,
    'AR01-1': 25.0,
    'AR01-2': 25.0,
    'AR03-1': 0.0,
    'AR03-2': 0.0,
    'AR03-3': 0.0,
}


# ── Conditions (declarative — see src/data/shift_io.py for the schema) ────────

_RESERVE_BELOW_600MW: dict = {
    'metric': 'SPINNING_RESERVE_MW', 'op': '<', 'value': 600.0,
}
_RESERVE_AT_OR_ABOVE_600MW: dict = {
    'metric': 'SPINNING_RESERVE_MW', 'op': '>=', 'value': 600.0,
}
_CCGT_BELOW_1000MW: dict = {
    'metric': 'UNIT_OUTPUT_MW_SUM', 'targets': ['ASHG-1', 'ASHG-2', 'WRNG-1', 'WRNG-2'],
    'op': '<', 'value': 1000.0,
}


# ── Scripted events ────────────────────────────────────────────────────────────

SCRIPTED_EVENTS: list[dict] = [
    {
        # T+0 (06:00) — shift start briefing
        'trigger_min':  0.0,
        'priority':    'INFO',
        'message':     'Final shift. Full Alpha grid energised — 57 buses, 30 units.',
        'detail':      ('Every station on the grid is live. Firm capacity (coal, '
                        'CCGT, pumped storage, lower hydro) covers a little over '
                        '5,100 MW against tonight\'s 8,000 MW peak — run-of-river '
                        'and wind output plus your reserve margin make up the '
                        'rest. AGC is off: every regulation move is manual today.'),
        'element':     None,
        'condition':   None,
    },
    {
        # T+180 (09:00) — wind lull warning
        'trigger_min': 180.0,
        'priority':    'WARNING',
        'message':     'Cairn Wind and Brackley Wind lull approaching.',
        'detail':      ('Forecast shows WNCN and WNBR output falling sharply over '
                        'the next two hours as the morning breeze drops. Build '
                        'spinning reserve now — ramp CCGT and stage pumped/lower '
                        'hydro before the lull lands.'),
        'element':     'WNCN',
        'condition':   None,
    },
    {
        # T+240 (10:00) — 30-min reminder, conditional on reserve staged
        'trigger_min': 240.0,
        'priority':    'WARNING',
        'message':     'Wind lull in 30 minutes. Spinning reserve below 600 MW.',
        'detail':      ('Cairn Wind will drop within the half hour. Current spinning '
                        'reserve is thin. Ramp ASHG/WRNG and bring pumped storage '
                        'units up toward their regulation band now — this is the '
                        'last comfortable window to stage before the swing hits.'),
        'element':     'WNCN',
        'condition':   _RESERVE_BELOW_600MW,
    },
    {
        # T+270 (10:30) — nominal branch: player staged correctly
        'trigger_min': 270.0,
        'priority':    'INFO',
        'message':     'Reserve margin adequate ahead of the wind lull.',
        'detail':      ('Spinning reserve is holding above 600 MW as the wind '
                        'begins to fall. The grid is well positioned for the '
                        'net-load swing.'),
        'element':     'WNCN',
        'condition':   _RESERVE_AT_OR_ABOVE_600MW,
    },
    {
        # T+600 (16:00) — evening peak warning, conditional on CCGT staging
        'trigger_min': 600.0,
        'priority':    'WARNING',
        'message':     'Evening peak approaching. Combined CCGT output below 1000 MW.',
        'detail':      ('Demand climbs toward the 8,000 MW peak over the next two '
                        'hours. Ramp ASHG and WRNG toward full output now and bring '
                        'the remaining pumped storage online — firm capacity is '
                        'thin against this evening\'s peak.'),
        'element':     None,
        'condition':   _CCGT_BELOW_1000MW,
    },
    {
        # T+660 (17:00) — peak window info
        'trigger_min': 660.0,
        'priority':    'INFO',
        'message':     'Approaching peak demand — system at full stretch.',
        'detail':      ('Demand is near its 8,000 MW forecast peak. Hold frequency '
                        'and line loading within limits through the evening ramp-down. '
                        'Frequency nominal. For now.'),
        'element':     None,
        'condition':   None,
    },
]
