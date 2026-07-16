"""
src/gameplay/shifts/shift_10.py

Shift 10 scenario — the campaign finale on the complete, capacity-expanded
grid: 41 buses (36 original + 5 consolidated load substations), 61 lines
(43 permanent + 18 Shift-10-only: 1 ring reinforcement, 5 primary feed
links, 5 secondary feed links, 2 cascade loop closures, 4 new regional
spine taps, 1 WEST-internal loop closer), 47 units.

Narrative:
  Final shift, peak demand day, 06:00-18:00. Every station in the network
  is live and dispatchable at once — the first shift where the full fleet
  and full 8,000 MW campaign peak both apply simultaneously. Stage 24
  commissioned 23 new 150kV distribution substations this season, each on
  its own dedicated 220kV feed. Stage 25 dual-fed all 23 substations from
  independent source buses and closed the River Brent and River Coln
  cascade strings into loops (matching how River Arden already ties at
  both ends), removing several single-point-of-failure radial tails.
  Stage 26 then consolidated substations that shared an identical pair of
  feed sources down to 9 larger substations, splitting the two biggest
  groups (ASHF+AR01, FAIR+AR02) in two apiece to keep individual
  substation size down. Stage 27 also re-laid-out the west hydro pocket
  (DUND/RDST/KELD/AR01-04) across a wider footprint, since the pocket had
  become dense enough to violate the schematic's own minimum node-spacing
  guidance. Stage 28 reorganised the whole grid into 6 regions
  (CAP, WEST, SOUTH-MESH, EAST-POCKET, EAST-MESH, plus the SPINE itself)
  that only reach each other via the 400kV spine — removing every direct
  lower-voltage tie that used to bypass it (the old L18, L26, L27, L29,
  L30, L31, L32) and adding 4 new regional spine taps plus a WEST-internal
  loop closer. Offscreen N-1 testing then showed that ANY region hosting
  2+ substations off only its 2 spine-anchor buses overloads its internal
  220/150kV ring on a feed trip, regardless of which buses were chosen —
  so Stage 29 consolidated down to 5 substations, exactly one per
  non-SPINE region, each dual-fed only from that region's own 2
  spine-anchor buses (LD07 merges the old LD07+LD08 into CAP's ASHF+FAIR
  pair; LD09 merges the old LD09+LD10+LD14 into WEST's DUND+RDST pair;
  LD11-LD13 are unchanged). See STAGE_STATUS.md Stage 24-29 for the full
  rationale. Firm capacity (nuclear + coal + CCGT + pumped storage +
  lower hydro) is ~6,650 MW against the 8,000 MW peak; run-of-river, wind,
  and solar output plus reserve margin management make up the difference,
  not any single silver-bullet unit. THNF-3 is on planned outage, trimming
  available firm capacity below its nameplate ceiling for the whole shift.

  AGC is off — this is the manual-dispatch finale, no automatic
  frequency regulation to fall back on. Two teaching beats punctuate the
  day: a late-morning wind lull that coincides with the solar ramp
  (net-load swings hard in a two-hour window), and an early-afternoon
  test of the reinforced grid's N-1 security when one circuit of the
  MDBY-STHW double circuit is pulled for inspection.
"""

from __future__ import annotations


SHIFT_DATE: str = 'THU 10 NOV 1994'

DIFFICULTY_LABEL: str = 'Expert'

HANDOVER_NOTES: tuple[str, ...] = (
    'Final shift, 06:00. Full grid energised — 41 buses, 61 lines, 47 units live.',
    'Peak demand forecast 8,000 MW this evening. System at full stretch.',
    'Distribution network complete: 5 substations (LD07, LD09, LD11-LD13) '
        'commissioned this season, each dual-fed from its own region\'s two '
        'spine-anchor buses.',
    'Grid reorganised into 6 regions this season, each reaching the rest '
        'of the network only via the 400kV spine — second circuit energised '
        'on L15 (ASHF-FAIR) for extra capital-ring N-1 margin.',
    'HART-1/2 nuclear online at rated 700 MW each — baseload, do not touch.',
    'RVSD-1/2/3 and THNF-1/2 coal online at partial load, ramp headroom held for the day.',
    'THNF-3 out of service — planned inspection, back next shift.',
    'ASHG-1/2 and WRNG-1/2 CCGT at morning minimum, held in reserve for the peaks.',
    'DUNH, KELM, BARR pumped storage and DUND/KELD/BARD lower hydro held low — fast regulation reserve.',
    'River cascades (Arden, Brent, Coln) running at available flow.',
    'Cairn Wind (WNCN) strong this morning; forecast shows a lull approaching midday.',
    'Stanton and Feldon solar (SLST, SLFD) will ramp up through the morning as normal.',
    'AGC is OFF. No automatic frequency regulation — every MW is your call.',
    'MDBY-STHW circuit 2 (L03) scheduled for brief inspection outage early afternoon.',
    'Frequency nominal. For now.',
)

# Units on planned outage at shift start.
MAINTENANCE_UNITS: set[str] = {'THNF-3'}

# No lines start open — full N-1/N-2 mesh intact at shift start.
MAINTENANCE_LINES: set[str] = set()

AGC_ENABLED: bool = False

# Per-bus hourly load table (MW). Full grid: 11 load buses.
# LD01-LD06 retain a small residual (~5% of their old standalone curve) —
# the bulk of what they used to carry now routes through 5 dedicated
# substations (LD07, LD09, LD11-LD13), each dual-fed from its own region's
# 2 spine-anchor buses (see the region table in topology.py's BUSES
# comment). These were originally 23 separate single-feed substations
# (Stage 24), then 23 dual-fed substations (Stage 25); Stage 26
# consolidated same-source-pair groups into 9 substations; Stage 28
# re-sourced every substation to be same-region (8 substations, LD07-LD14).
# Offscreen N-1 testing then found that ANY region hosting 2+ substations
# off only its 2 spine-anchor buses overloads its internal ring on a feed
# trip — so Stage 29 consolidated to 5 substations, one per region:
# LD07 (CAP) absorbs the old LD08; LD09 (WEST) absorbs the old LD10 and
# LD14; LD11-LD13 are unchanged. Every hourly value below is the exact
# sum of its retired members' curves, so system total still peaks at
# exactly 8,000 MW at hour 16:00, matching ShiftSpec.peak_demand_mw.
SUBSTATION_LOAD_MW: dict[str, dict[float, float]] = {
    'LD01': {
          0.0:    19,  1.0:    17,  2.0:    15,  3.0:    14,  4.0:    15,
          5.0:    18,  6.0:    30,  7.0:    47,  8.0:    67,  9.0:    85,
         10.0:    96, 11.0:   100, 12.0:    98, 13.0:    95, 14.0:    94,
         15.0:    97, 16.0:   104, 17.0:   104, 18.0:   105, 19.0:   103,
         20.0:    96, 21.0:    83, 22.0:    64, 23.0:    41, 24.0:    23,
    },
    'LD02': {
          0.0:    26,  1.0:    24,  2.0:    22,  3.0:    21,  4.0:    22,
          5.0:    24,  6.0:    31,  7.0:    40,  8.0:    51,  9.0:    60,
         10.0:    66, 11.0:    70, 12.0:    72, 13.0:    73, 14.0:    72,
         15.0:    71, 16.0:    70, 17.0:    72, 18.0:    75, 19.0:    74,
         20.0:    67, 21.0:    60, 22.0:    48, 23.0:    35, 24.0:    26,
    },
    'LD03': {
          0.0:    12,  1.0:    12,  2.0:    11,  3.0:    11,  4.0:    12,
          5.0:    14,  6.0:    25,  7.0:    52,  8.0:    66,  9.0:    70,
         10.0:    73, 11.0:    73, 12.0:    72, 13.0:    71, 14.0:    72,
         15.0:    73, 16.0:    72, 17.0:    68, 18.0:    58, 19.0:    41,
         20.0:    26, 21.0:    19, 22.0:    16, 23.0:    16, 24.0:    14,
    },
    'LD04': {
          0.0:    15,  1.0:    14,  2.0:    13,  3.0:    13,  4.0:    13,
          5.0:    15,  6.0:    24,  7.0:    36,  8.0:    49,  9.0:    58,
         10.0:    63, 11.0:    66, 12.0:    66, 13.0:    66, 14.0:    66,
         15.0:    65, 16.0:    65, 17.0:    66, 18.0:    65, 19.0:    60,
         20.0:    52, 21.0:    44, 22.0:    34, 23.0:    23, 24.0:    16,
    },
    'LD05': {
          0.0:    17,  1.0:    16,  2.0:    15,  3.0:    14,  4.0:    14,
          5.0:    16,  6.0:    20,  7.0:    28,  8.0:    37,  9.0:    44,
         10.0:    48, 11.0:    49, 12.0:    48, 13.0:    47, 14.0:    47,
         15.0:    48, 16.0:    50, 17.0:    52, 18.0:    57, 19.0:    55,
         20.0:    51, 21.0:    48, 22.0:    40, 23.0:    28, 24.0:    20,
    },
    'LD06': {
          0.0:    12,  1.0:    11,  2.0:    10,  3.0:    10,  4.0:    10,
          5.0:    11,  6.0:    15,  7.0:    20,  8.0:    25,  9.0:    30,
         10.0:    33, 11.0:    34, 12.0:    35, 13.0:    34, 14.0:    35,
         15.0:    37, 16.0:    39, 17.0:    37, 18.0:    39, 19.0:    39,
         20.0:    35, 21.0:    31, 22.0:    25, 23.0:    19, 24.0:    14,
    },
    'LD07': {
          0.0:   502,  1.0:   464,  2.0:   431,  3.0:   413,  4.0:   425,
          5.0:   490,  6.0:   719,  7.0:  1105,  8.0:  1469,  9.0:  1730,
         10.0:  1879, 11.0:  1949, 12.0:  1946, 13.0:  1922, 14.0:  1913,
         15.0:  1941, 16.0:  1988, 17.0:  1986, 18.0:  1980, 19.0:  1850,
         20.0:  1628, 21.0:  1414, 22.0:  1131, 23.0:   806, 24.0:   561,
    },
    'LD09': {
          0.0:   655,  1.0:   603,  2.0:   561,  3.0:   540,  4.0:   552,
          5.0:   639,  6.0:   936,  7.0:  1440,  8.0:  1912,  9.0:  2255,
         10.0:  2449, 11.0:  2539, 12.0:  2534, 13.0:  2502, 14.0:  2492,
         15.0:  2527, 16.0:  2591, 17.0:  2585, 18.0:  2577, 19.0:  2408,
         20.0:  2120, 21.0:  1840, 22.0:  1473, 23.0:  1048, 24.0:   730,
    },
    'LD11': {
          0.0:   262,  1.0:   241,  2.0:   224,  3.0:   215,  4.0:   221,
          5.0:   256,  6.0:   373,  7.0:   574,  8.0:   765,  9.0:   901,
         10.0:   978, 11.0:  1015, 12.0:  1012, 13.0:  1000, 14.0:   994,
         15.0:  1009, 16.0:  1035, 17.0:  1033, 18.0:  1030, 19.0:   962,
         20.0:   846, 21.0:   735, 22.0:   589, 23.0:   419, 24.0:   292,
    },
    'LD12': {
          0.0:   243,  1.0:   224,  2.0:   209,  3.0:   200,  4.0:   205,
          5.0:   237,  6.0:   347,  7.0:   534,  8.0:   711,  9.0:   837,
         10.0:   909, 11.0:   942, 12.0:   942, 13.0:   930, 14.0:   926,
         15.0:   939, 16.0:   961, 17.0:   961, 18.0:   958, 19.0:   895,
         20.0:   787, 21.0:   684, 22.0:   547, 23.0:   389, 24.0:   271,
    },
    'LD13': {
          0.0:   260,  1.0:   239,  2.0:   222,  3.0:   213,  4.0:   219,
          5.0:   254,  6.0:   371,  7.0:   570,  8.0:   758,  9.0:   893,
         10.0:   969, 11.0:  1005, 12.0:  1004, 13.0:   991, 14.0:   987,
         15.0:  1001, 16.0:  1026, 17.0:  1024, 18.0:  1021, 19.0:   955,
         20.0:   839, 21.0:   730, 22.0:   583, 23.0:   415, 24.0:   289,
    },
}

# Starting dispatch at 06:00 — units absent from this dict start OFFLINE.
# Total ≈ 2,940 MW against ~2,890 MW demand (+~2% losses) at 06:00.
# CCGT and fast hydro/pumped units held low deliberately — reserve for the
# midday wind lull and the evening peak ramp.
INITIAL_SCHEDULE: dict[str, float] = {
    'HART-1':  700.0,   # Hartwell Nuclear 1 — rated baseload
    'HART-2':  700.0,   # Hartwell Nuclear 2 — rated baseload
    'RVSD-1':  140.0,   # Riverside Coal 1 — ramp headroom held
    'RVSD-2':  140.0,   # Riverside Coal 2 — ramp headroom held
    'RVSD-3':  140.0,   # Riverside Coal 3 — ramp headroom held
    'THNF-1':  140.0,   # Thornfield Coal 1 — ramp headroom held
    'THNF-2':  140.0,   # Thornfield Coal 2 — ramp headroom held
    'ASHG-1':  100.0,   # Ashford CCGT 1 — reserve for peaks
    'ASHG-2':   80.0,   # Ashford CCGT 2 — reserve for peaks
    'WRNG-1':  100.0,   # Wrentham CCGT 1 — reserve for peaks
    'WRNG-2':   80.0,   # Wrentham CCGT 2 — reserve for peaks
    'DUNH-1':   10.0,   # Dunmore Upper 1 — fast regulation reserve
    'DUNH-2':   10.0,   # Dunmore Upper 2 — fast regulation reserve
    'DUND-1':   10.0,   # Dunmore Lower 1 — fast regulation reserve
    'DUND-2':   10.0,   # Dunmore Lower 2 — fast regulation reserve
    'KELM-1':   20.0,   # Kelmore Upper 1 — fast regulation reserve
    'KELM-2':   20.0,   # Kelmore Upper 2 — fast regulation reserve
    'KELD-1':   30.0,   # Kelmore Lower 1 — fast regulation reserve
    'KELD-2':   30.0,   # Kelmore Lower 2 — fast regulation reserve
    'BARR-1':   30.0,   # Barrow Upper 1 — fast regulation reserve
    'BARR-2':   30.0,   # Barrow Upper 2 — fast regulation reserve
    'BARD-1':   50.0,   # Barrow Lower 1 — fast regulation reserve
    'BARD-2':   50.0,   # Barrow Lower 2 — fast regulation reserve
    # River cascades — run near available flow (no manual staging needed).
    'AR01-1':   38.0, 'AR01-2':  38.0,
    'AR02-1':   32.0, 'AR02-2':  32.0,
    'AR03-1':   55.0,
    'AR04-1':   45.0,
    'BR01-1':   28.0, 'BR01-2':  28.0,
    'BR02-1':   22.0, 'BR02-2':  22.0,
    'BR03-1':   18.0, 'BR03-2':  18.0,
    'CO01-1':   25.0, 'CO01-2':  25.0,
    'CO02-1':   20.0, 'CO02-2':  20.0,
    'CO03-1':   15.0, 'CO03-2':  15.0,
}


# ── Condition helpers ──────────────────────────────────────────────────────────
# Scripted-event conditions receive the live FleetModel (see
# GridSimulation._process_scripted_events — conditions are called as
# cond(fleet), never with the Grid object).

def _reserve_below_600mw(fleet) -> bool:
    """True when spinning reserve has fallen below 600 MW ahead of the wind lull."""
    return fleet.spinning_reserve_mw() < 600.0


def _reserve_at_or_above_600mw(fleet) -> bool:
    """True when spinning reserve is at or above 600 MW — player staged correctly."""
    return not _reserve_below_600mw(fleet)


def _ccgt_below_1000mw(fleet) -> bool:
    """True when combined CCGT output is still below 1000 MW ahead of the evening peak."""
    total = 0.0
    for label in ('ASHG-1', 'ASHG-2', 'WRNG-1', 'WRNG-2'):
        if fleet.has_unit(label):
            total += fleet.get_unit(label).current_mw
    return total < 1000.0


# ── Scripted events ────────────────────────────────────────────────────────────

SCRIPTED_EVENTS: list[dict] = [
    {
        # T+0 (06:00) — shift start briefing
        'trigger_min':  0.0,
        'priority':    'INFO',
        'message':     'Final shift. Full grid energised — 41 buses, 47 units.',
        'detail':      ('Every station in the network is live, and the '
                        'new distribution substations (LD07, LD09, LD11-LD13) '
                        'are carrying load for the first time. Firm capacity (nuclear, coal, '
                        'CCGT, pumped storage, lower hydro) covers roughly '
                        '6,650 MW against tonight\'s 8,000 MW peak — run-of-river, '
                        'wind, solar output, and your reserve margin make up the '
                        'rest. AGC is off: every regulation move is manual today.'),
        'element':     None,
        'condition':   None,
    },
    {
        # T+180 (09:00) — wind lull + solar ramp warning
        'trigger_min': 180.0,
        'priority':    'WARNING',
        'message':     'Cairn Wind lull approaching — solar ramping simultaneously.',
        'detail':      ('Forecast shows WNCN output falling sharply over the next '
                        'two hours as the morning breeze drops, at the same time '
                        'Stanton and Feldon solar are still climbing toward midday. '
                        'Net load swings both ways in this window. Build spinning '
                        'reserve now — ramp CCGT and stage pumped/lower hydro before '
                        'the lull lands.'),
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
        'condition':   _reserve_below_600mw,
    },
    {
        # T+270 (10:30) — nominal branch: player staged correctly
        'trigger_min': 270.0,
        'priority':    'INFO',
        'message':     'Reserve margin adequate ahead of the wind lull.',
        'detail':      ('Spinning reserve is holding above 600 MW as Cairn Wind '
                        'begins to fall. The grid is well positioned for the net-load '
                        'swing.'),
        'element':     'WNCN',
        'condition':   _reserve_at_or_above_600mw,
    },
    {
        # T+330 (11:30) — L03 opens for scheduled inspection (N-1 test)
        'trigger_min': 330.0,
        'priority':    'MAINTENANCE',
        'message':     'MDBY-STHW circuit 2 (L03) opening for scheduled inspection.',
        'detail':      ('L03 is now out for a short inspection window. The remaining '
                        'MDBY-STHW circuit (L02) and the full 400kV mesh carry the '
                        'spine flow. Watch L02 loading — this is the finale\'s N-1 '
                        'security test on the complete grid. L03 returns to service '
                        'within the hour.'),
        'element':     'L03',
        'condition':   None,
    },
    {
        # T+390 (12:30) — L03 restored
        'trigger_min': 390.0,
        'priority':    'INFO',
        'message':     'MDBY-STHW circuit 2 (L03) returned to service.',
        'detail':      ('Inspection complete. L03 is back in service; the spine is '
                        'back to full double-circuit strength between MDBY and STHW.'),
        'element':     'L03',
        'condition':   None,
    },
    {
        # T+600 (16:00) — evening peak warning, conditional on CCGT staging
        'trigger_min': 600.0,
        'priority':    'WARNING',
        'message':     'Evening peak approaching. Combined CCGT output below 1000 MW.',
        'detail':      ('Demand climbs toward the 8,000 MW peak over the next two '
                        'hours, and solar will be falling off as it does. Ramp ASHG '
                        'and WRNG toward full output now and bring the remaining '
                        'pumped storage online — firm capacity is thin against this '
                        'evening\'s peak.'),
        'element':     None,
        'condition':   _ccgt_below_1000mw,
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


# ── Scoring hooks ──────────────────────────────────────────────────────────────
#
# BONUS_N1_SECURE: awarded if L02 (the remaining MDBY-STHW circuit) never
#   exceeds 85% loading during the L03 inspection outage window (11:30-12:30,
#   sim minutes 330-390).
#
# PENALTY_SPINE_CONGESTION: applied per simulated minute L02 is above 90%
#   during the same window.
#
# Standard KPIs also apply: frequency deviation, max line loading, min VSI.

SCORING_HOOKS: dict = {
    'bonus_n1_secure': {
        'description': 'L02 never exceeds 85% during the L03 inspection outage',
        'window_min':  (330.0, 390.0),
        'lines':       ('L02',),
        'threshold':   85.0,
        'points':      250,
    },
    'penalty_spine_congestion': {
        'description': 'Per-minute penalty when L02 exceeds 90% during the L03 outage',
        'window_min':  (330.0, 390.0),
        'lines':       ('L02',),
        'threshold':   90.0,
        'points_per_minute': -20,
    },
}
