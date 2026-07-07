"""
src/gameplay/shifts/shift_10.py

Shift 10 scenario — the campaign finale on the complete, capacity-expanded
grid: 59 buses (36 original + 23 new load substations), 75 lines
(50 original + 2 ring reinforcements + 23 new feed links), 47 units.

Narrative:
  Final shift, peak demand day, 06:00-18:00. Every station in the network
  is live and dispatchable at once — the first shift where the full fleet
  and full 8,000 MW campaign peak both apply simultaneously. Stage 24
  commissioned 23 new 150kV distribution substations (LD07-LD29) this
  season, each with its own dedicated 220kV feed, plus a second parallel
  circuit on two 220kV ring segments (L15 ASHF-FAIR, L27 RDST-DUNM) that
  were becoming a bottleneck once load spread out — see STAGE_STATUS.md
  Stage 24 for the full capacity-planning rationale. Firm capacity
  (nuclear + coal + CCGT + pumped storage + lower hydro) is ~6,650 MW
  against the 8,000 MW peak; run-of-river, wind, and solar output plus
  reserve margin management make up the difference, not any single
  silver-bullet unit. THNF-3 is on planned outage, trimming available
  firm capacity below its nameplate ceiling for the whole shift.

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
    'Final shift, 06:00. Full grid energised — 59 buses, 75 lines, 47 units live.',
    'Peak demand forecast 8,000 MW this evening. System at full stretch.',
    'Stage 24 distribution network complete: 23 new substations (LD07-LD29) '
        'commissioned this season, each on its own dedicated 220kV feed.',
    'Second circuits energised on L15 (ASHF-FAIR) and L27 (RDST-DUNM) — the '
        'capital and west rings are now N-1 secure at full load.',
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

# Per-bus hourly load table (MW). Full grid: 29 load buses.
# LD01-LD06 retain a small residual (~5% of their old standalone curve) —
# the bulk of what they used to carry now routes through the new dedicated
# substations LD07-LD29, each on its own 220kV feed. System total still
# peaks at exactly 8,000 MW at hour 16:00, matching ShiftSpec.peak_demand_mw.
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
          0.0:    86,  1.0:    80,  2.0:    74,  3.0:    71,  4.0:    73,
          5.0:    84,  6.0:   124,  7.0:   190,  8.0:   253,  9.0:   298,
         10.0:   323, 11.0:   335, 12.0:   335, 13.0:   331, 14.0:   329,
         15.0:   334, 16.0:   342, 17.0:   342, 18.0:   341, 19.0:   318,
         20.0:   280, 21.0:   243, 22.0:   195, 23.0:   139, 24.0:    97,
    },
    'LD08': {
          0.0:    78,  1.0:    72,  2.0:    67,  3.0:    64,  4.0:    66,
          5.0:    76,  6.0:   112,  7.0:   172,  8.0:   229,  9.0:   269,
         10.0:   292, 11.0:   303, 12.0:   303, 13.0:   299, 14.0:   298,
         15.0:   302, 16.0:   309, 17.0:   309, 18.0:   308, 19.0:   288,
         20.0:   253, 21.0:   220, 22.0:   176, 23.0:   125, 24.0:    87,
    },
    'LD09': {
          0.0:    82,  1.0:    75,  2.0:    70,  3.0:    67,  4.0:    69,
          5.0:    80,  6.0:   117,  7.0:   179,  8.0:   238,  9.0:   281,
         10.0:   305, 11.0:   316, 12.0:   316, 13.0:   312, 14.0:   310,
         15.0:   315, 16.0:   323, 17.0:   322, 18.0:   321, 19.0:   300,
         20.0:   264, 21.0:   229, 22.0:   184, 23.0:   131, 24.0:    91,
    },
    'LD10': {
          0.0:    81,  1.0:    75,  2.0:    69,  3.0:    67,  4.0:    68,
          5.0:    79,  6.0:   116,  7.0:   178,  8.0:   236,  9.0:   279,
         10.0:   303, 11.0:   314, 12.0:   313, 13.0:   309, 14.0:   308,
         15.0:   313, 16.0:   320, 17.0:   320, 18.0:   319, 19.0:   298,
         20.0:   262, 21.0:   228, 22.0:   182, 23.0:   130, 24.0:    90,
    },
    'LD11': {
          0.0:    88,  1.0:    81,  2.0:    75,  3.0:    72,  4.0:    74,
          5.0:    86,  6.0:   125,  7.0:   193,  8.0:   257,  9.0:   303,
         10.0:   329, 11.0:   341, 12.0:   340, 13.0:   336, 14.0:   334,
         15.0:   339, 16.0:   348, 17.0:   347, 18.0:   346, 19.0:   323,
         20.0:   284, 21.0:   247, 22.0:   198, 23.0:   141, 24.0:    98,
    },
    'LD12': {
          0.0:    87,  1.0:    80,  2.0:    75,  3.0:    72,  4.0:    73,
          5.0:    85,  6.0:   124,  7.0:   191,  8.0:   254,  9.0:   300,
         10.0:   325, 11.0:   337, 12.0:   337, 13.0:   333, 14.0:   331,
         15.0:   336, 16.0:   344, 17.0:   344, 18.0:   343, 19.0:   320,
         20.0:   282, 21.0:   245, 22.0:   196, 23.0:   139, 24.0:    97,
    },
    'LD13': {
          0.0:    90,  1.0:    83,  2.0:    77,  3.0:    74,  4.0:    76,
          5.0:    88,  6.0:   129,  7.0:   198,  8.0:   263,  9.0:   310,
         10.0:   336, 11.0:   349, 12.0:   348, 13.0:   344, 14.0:   342,
         15.0:   347, 16.0:   356, 17.0:   355, 18.0:   354, 19.0:   331,
         20.0:   291, 21.0:   253, 22.0:   202, 23.0:   144, 24.0:   100,
    },
    'LD14': {
          0.0:    79,  1.0:    73,  2.0:    68,  3.0:    65,  4.0:    67,
          5.0:    77,  6.0:   113,  7.0:   174,  8.0:   231,  9.0:   272,
         10.0:   296, 11.0:   307, 12.0:   306, 13.0:   302, 14.0:   301,
         15.0:   305, 16.0:   313, 17.0:   312, 18.0:   311, 19.0:   291,
         20.0:   256, 21.0:   222, 22.0:   178, 23.0:   127, 24.0:    88,
    },
    'LD15': {
          0.0:    84,  1.0:    77,  2.0:    72,  3.0:    69,  4.0:    71,
          5.0:    82,  6.0:   119,  7.0:   184,  8.0:   244,  9.0:   288,
         10.0:   313, 11.0:   324, 12.0:   324, 13.0:   320, 14.0:   318,
         15.0:   323, 16.0:   331, 17.0:   330, 18.0:   329, 19.0:   308,
         20.0:   271, 21.0:   235, 22.0:   188, 23.0:   134, 24.0:    93,
    },
    'LD16': {
          0.0:    78,  1.0:    72,  2.0:    67,  3.0:    64,  4.0:    66,
          5.0:    76,  6.0:   112,  7.0:   172,  8.0:   229,  9.0:   270,
         10.0:   293, 11.0:   304, 12.0:   303, 13.0:   299, 14.0:   298,
         15.0:   302, 16.0:   310, 17.0:   309, 18.0:   308, 19.0:   288,
         20.0:   253, 21.0:   220, 22.0:   176, 23.0:   125, 24.0:    87,
    },
    'LD17': {
          0.0:    81,  1.0:    74,  2.0:    69,  3.0:    67,  4.0:    68,
          5.0:    79,  6.0:   115,  7.0:   178,  8.0:   236,  9.0:   278,
         10.0:   302, 11.0:   313, 12.0:   313, 13.0:   309, 14.0:   308,
         15.0:   312, 16.0:   320, 17.0:   319, 18.0:   318, 19.0:   297,
         20.0:   262, 21.0:   227, 22.0:   182, 23.0:   129, 24.0:    90,
    },
    'LD18': {
          0.0:    85,  1.0:    78,  2.0:    73,  3.0:    70,  4.0:    72,
          5.0:    83,  6.0:   121,  7.0:   186,  8.0:   248,  9.0:   292,
         10.0:   317, 11.0:   329, 12.0:   328, 13.0:   324, 14.0:   322,
         15.0:   327, 16.0:   335, 17.0:   335, 18.0:   334, 19.0:   312,
         20.0:   274, 21.0:   238, 22.0:   191, 23.0:   136, 24.0:    95,
    },
    'LD19': {
          0.0:    78,  1.0:    72,  2.0:    67,  3.0:    64,  4.0:    66,
          5.0:    76,  6.0:   112,  7.0:   172,  8.0:   229,  9.0:   269,
         10.0:   292, 11.0:   303, 12.0:   303, 13.0:   299, 14.0:   298,
         15.0:   302, 16.0:   309, 17.0:   309, 18.0:   308, 19.0:   288,
         20.0:   253, 21.0:   220, 22.0:   176, 23.0:   125, 24.0:    87,
    },
    'LD20': {
          0.0:    81,  1.0:    74,  2.0:    69,  3.0:    66,  4.0:    68,
          5.0:    79,  6.0:   115,  7.0:   177,  8.0:   236,  9.0:   277,
         10.0:   301, 11.0:   312, 12.0:   312, 13.0:   308, 14.0:   307,
         15.0:   311, 16.0:   319, 17.0:   318, 18.0:   317, 19.0:   297,
         20.0:   261, 21.0:   227, 22.0:   181, 23.0:   129, 24.0:    90,
    },
    'LD21': {
          0.0:    87,  1.0:    80,  2.0:    74,  3.0:    71,  4.0:    73,
          5.0:    85,  6.0:   124,  7.0:   191,  8.0:   253,  9.0:   298,
         10.0:   324, 11.0:   336, 12.0:   335, 13.0:   331, 14.0:   330,
         15.0:   335, 16.0:   343, 17.0:   342, 18.0:   341, 19.0:   319,
         20.0:   281, 21.0:   244, 22.0:   195, 23.0:   139, 24.0:    97,
    },
    'LD22': {
          0.0:    85,  1.0:    79,  2.0:    73,  3.0:    70,  4.0:    72,
          5.0:    83,  6.0:   122,  7.0:   187,  8.0:   249,  9.0:   293,
         10.0:   319, 11.0:   331, 12.0:   330, 13.0:   326, 14.0:   324,
         15.0:   329, 16.0:   337, 17.0:   337, 18.0:   336, 19.0:   314,
         20.0:   276, 21.0:   240, 22.0:   192, 23.0:   137, 24.0:    95,
    },
    'LD23': {
          0.0:    81,  1.0:    74,  2.0:    69,  3.0:    67,  4.0:    68,
          5.0:    79,  6.0:   115,  7.0:   178,  8.0:   236,  9.0:   278,
         10.0:   302, 11.0:   313, 12.0:   313, 13.0:   309, 14.0:   308,
         15.0:   312, 16.0:   320, 17.0:   319, 18.0:   318, 19.0:   297,
         20.0:   262, 21.0:   227, 22.0:   182, 23.0:   129, 24.0:    90,
    },
    'LD24': {
          0.0:    86,  1.0:    79,  2.0:    74,  3.0:    71,  4.0:    72,
          5.0:    84,  6.0:   123,  7.0:   189,  8.0:   251,  9.0:   296,
         10.0:   321, 11.0:   333, 12.0:   332, 13.0:   328, 14.0:   327,
         15.0:   331, 16.0:   339, 17.0:   339, 18.0:   338, 19.0:   316,
         20.0:   278, 21.0:   241, 22.0:   193, 23.0:   137, 24.0:    96,
    },
    'LD25': {
          0.0:    89,  1.0:    82,  2.0:    76,  3.0:    73,  4.0:    75,
          5.0:    87,  6.0:   127,  7.0:   195,  8.0:   260,  9.0:   306,
         10.0:   332, 11.0:   345, 12.0:   344, 13.0:   340, 14.0:   338,
         15.0:   343, 16.0:   352, 17.0:   351, 18.0:   350, 19.0:   327,
         20.0:   288, 21.0:   250, 22.0:   200, 23.0:   142, 24.0:    99,
    },
    'LD26': {
          0.0:    78,  1.0:    72,  2.0:    67,  3.0:    64,  4.0:    66,
          5.0:    76,  6.0:   111,  7.0:   171,  8.0:   228,  9.0:   268,
         10.0:   292, 11.0:   302, 12.0:   302, 13.0:   298, 14.0:   297,
         15.0:   301, 16.0:   308, 17.0:   308, 18.0:   307, 19.0:   287,
         20.0:   252, 21.0:   219, 22.0:   175, 23.0:   125, 24.0:    87,
    },
    'LD27': {
          0.0:    89,  1.0:    82,  2.0:    76,  3.0:    73,  4.0:    75,
          5.0:    87,  6.0:   127,  7.0:   195,  8.0:   259,  9.0:   306,
         10.0:   332, 11.0:   344, 12.0:   344, 13.0:   339, 14.0:   338,
         15.0:   343, 16.0:   351, 17.0:   351, 18.0:   350, 19.0:   327,
         20.0:   287, 21.0:   250, 22.0:   200, 23.0:   142, 24.0:    99,
    },
    'LD28': {
          0.0:    87,  1.0:    81,  2.0:    75,  3.0:    72,  4.0:    74,
          5.0:    85,  6.0:   125,  7.0:   192,  8.0:   255,  9.0:   301,
         10.0:   327, 11.0:   339, 12.0:   338, 13.0:   334, 14.0:   332,
         15.0:   337, 16.0:   346, 17.0:   345, 18.0:   344, 19.0:   321,
         20.0:   283, 21.0:   246, 22.0:   196, 23.0:   140, 24.0:    98,
    },
    'LD29': {
          0.0:    82,  1.0:    76,  2.0:    71,  3.0:    68,  4.0:    70,
          5.0:    80,  6.0:   118,  7.0:   181,  8.0:   241,  9.0:   284,
         10.0:   308, 11.0:   320, 12.0:   319, 13.0:   315, 14.0:   314,
         15.0:   318, 16.0:   326, 17.0:   326, 18.0:   325, 19.0:   303,
         20.0:   267, 21.0:   232, 22.0:   185, 23.0:   132, 24.0:    92,
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
        'message':     'Final shift. Full grid energised — 59 buses, 47 units.',
        'detail':      ('Every station in the network is live, and Stage 24\'s '
                        'new distribution substations (LD07-LD29) are carrying '
                        'load for the first time. Firm capacity (nuclear, coal, '
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
