"""
src/data/profiles.py

Demand profiles, renewable generation profiles, and shift specifications
for the GRIDCOM 10-shift campaign.

Each 150kV load substation has an explicit per-shift hourly load table (MW).
Total system demand is the bottom-up sum of active substation demands.
Noise and stochastic variation are applied by the simulation layer.

See DOMAIN_GLOSSARY.md for campaign terms and shift definitions.
See GAMEPLAY_REFERENCE.md for campaign structure.
"""

from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────────────────
# SHIFT SPECIFICATION
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ShiftSpec:
    """
    Immutable specification for one shift.

    Attributes:
        shift_number:    1-10
        start_hour:      Shift start time (decimal hours, 24h clock)
        duration_hours:  Length of shift window in simulated hours
        grid_size:       Number of active buses (12, 20, or 32)
        has_phase1:      True if player does Phase 1 planning before Phase 2
        peak_demand_mw:  Peak system demand during this shift (MW)
        difficulty_label: Human-readable difficulty descriptor
        handover_notes:  List of bulletin lines shown at shift start
    """
    shift_number:     int
    start_hour:       float
    duration_hours:   float
    grid_size:        int
    has_phase1:       bool
    peak_demand_mw:   float
    difficulty_label: str
    handover_notes:   tuple[str, ...]


SHIFT_SPECS: dict[int, ShiftSpec] = {

    1: ShiftSpec(
        shift_number=1, start_hour=4.0, duration_hours=3.0,
        grid_size=3, has_phase1=False, peak_demand_mw=55.0,
        difficulty_label='Tutorial',
        handover_notes=(
            'Night handover from R. Ferris.',
            'Dunmore lower hydro unit 1 (DUND-1) on-line.',
            'All other units off-line.',
            'Demand very low — pre-dawn trough, gentle morning ramp ahead.',
            'Your task: keep frequency nominal as demand rises.',
        ),
    ),

    2: ShiftSpec(
        shift_number=2, start_hour=10.0, duration_hours=4.0,
        grid_size=3, has_phase1=False, peak_demand_mw=315.0,
        difficulty_label='Tutorial',
        handover_notes=(
            'Mid-morning handover.',
            'RVSD-1 and RVSD-3 on-line at technical minimum (90 MW each).',
            'DUND-1 on-line at 40 MW. DUND-2 on planned maintenance outage.',
            'Demand rising. DUND-1 is the sole AGC unit — headroom is limited.',
            'AGC active — ramp RVSD as load grows to keep DUND-1 in its band.',
        ),
    ),

    3: ShiftSpec(
        shift_number=3, start_hour=14.0, duration_hours=6.0,
        grid_size=20, has_phase1=False, peak_demand_mw=3800.0,
        difficulty_label='Standard',
        handover_notes=(
            'Afternoon shift. Centre grid now online.',
            'CCGT and pumped storage units now available.',
            'Afternoon demand peak expected 17:00-19:00.',
            'Wind forecast moderate. Solar declining from 15:00.',
        ),
    ),

    4: ShiftSpec(
        shift_number=4, start_hour=20.0, duration_hours=8.0,
        grid_size=20, has_phase1=False, peak_demand_mw=3200.0,
        difficulty_label='Standard',
        handover_notes=(
            'Evening / overnight shift.',
            'Demand falling after 21:00. Low overnight valley.',
            'Load shedding controls unlocked this shift.',
            'Two units due for overnight maintenance windows.',
        ),
    ),

    5: ShiftSpec(
        shift_number=5, start_hour=6.0, duration_hours=8.0,
        grid_size=32, has_phase1=True, peak_demand_mw=5800.0,
        difficulty_label='Standard',
        handover_notes=(
            'Full 32-node grid active from this shift.',
            'Phase 1 planning required before shift start.',
            'Interconnector scheduling now available.',
            'River cascade hydro available — check river flow forecast.',
        ),
    ),

    6: ShiftSpec(
        shift_number=6, start_hour=12.0, duration_hours=8.0,
        grid_size=32, has_phase1=True, peak_demand_mw=6200.0,
        difficulty_label='Challenging',
        handover_notes=(
            'Afternoon shift. High demand period.',
            'Line switching controls unlocked this shift.',
            'Thermal limits may bind on L07 and L16 during peak.',
            'BARR reservoir at 68%. KELM at 45%.',
        ),
    ),

    7: ShiftSpec(
        shift_number=7, start_hour=6.0, duration_hours=10.0,
        grid_size=32, has_phase1=True, peak_demand_mw=7200.0,
        difficulty_label='Challenging',
        handover_notes=(
            'High-demand summer shift.',
            'Voltage stability monitoring unlocked this shift.',
            'VSI halos now visible on canvas.',
            'Solar at peak — watch SLST reactive export.',
            'THNF-2 scheduled outage 10:00-14:00.',
        ),
    ),

    8: ShiftSpec(
        shift_number=8, start_hour=0.0, duration_hours=8.0,
        grid_size=32, has_phase1=True, peak_demand_mw=4800.0,
        difficulty_label='Challenging',
        handover_notes=(
            'Overnight shift. Storm warning in effect.',
            'Pumped storage mode switching unlocked.',
            'Wind forecast high but uncertain. Gusts may cause trip.',
            'Pump KELM and BARR overnight ready for morning peak.',
        ),
    ),

    9: ShiftSpec(
        shift_number=9, start_hour=8.0, duration_hours=12.0,
        grid_size=32, has_phase1=True, peak_demand_mw=7800.0,
        difficulty_label='Expert',
        handover_notes=(
            'Long summer day shift. Record demand possible.',
            'Two scripted contingency events this shift.',
            'Reserve margins will be tested.',
            'All pumped storage must be positioned by 06:00.',
        ),
    ),

    10: ShiftSpec(
        shift_number=10, start_hour=6.0, duration_hours=12.0,
        grid_size=32, has_phase1=True, peak_demand_mw=8000.0,
        difficulty_label='Expert',
        handover_notes=(
            'Final shift. Peak demand day.',
            'System at full stretch — no margin for error.',
            'Frequency nominal. For now.',
        ),
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# DEMAND PROFILE
#
# Normalised daily demand curve. 25 hourly values (0-24h inclusive).
# Used only by get_demand_mw() for legacy/forecast purposes.
# ─────────────────────────────────────────────────────────────────────────────

DEMAND_PROFILE_NORMALISED: dict[float, float] = {
     0.0: 0.360,
     1.0: 0.340,
     2.0: 0.325,
     3.0: 0.315,
     4.0: 0.320,
     5.0: 0.350,
     6.0: 0.440,
     7.0: 0.580,
     8.0: 0.720,
     9.0: 0.820,
    10.0: 0.870,
    11.0: 0.890,
    12.0: 0.880,
    13.0: 0.860,
    14.0: 0.850,
    15.0: 0.870,
    16.0: 0.910,
    17.0: 0.960,
    18.0: 1.000,
    19.0: 0.980,
    20.0: 0.930,
    21.0: 0.860,
    22.0: 0.740,
    23.0: 0.540,
    24.0: 0.390,
}


# ─────────────────────────────────────────────────────────────────────────────
# PER-SUBSTATION DEMAND SPECIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SubstationDemandSpec:
    """Demand specification for one 150kV load substation."""
    peak_mw: float
    profile: dict[float, float]   # 25 hourly values (0.0–24.0), normalised 0.0–1.0


# ─────────────────────────────────────────────────────────────────────────────
# PER-SHIFT PER-SUBSTATION HOURLY LOAD TABLE
#
# SUBSTATION_LOAD_MW[shift][bus][hour] = load in MW
#
# Only active buses are present for each shift:
#   Shifts 1-2:  LD01
#   Shifts 3-4:  LD01, LD02, LD06
#   Shifts 5-10: LD01, LD02, LD03, LD04, LD05, LD06
#
# Aggregate at peak hour ≈ ShiftSpec.peak_demand_mw (±1%).
# Each bus has a distinct load character that evolves across shifts:
#   LD01 residential  — double peak (morning + evening), gentle in S1-2
#   LD02 commercial   — broad midday plateau
#   LD03 industrial   — flat block 07-19h, steep in later shifts
#   LD04 retail       — sharp morning ramp, plateau, modest tail
#   LD05 urban        — follows system average shape
#   LD06 suburban     — evening-heavy, later peak (~19h)
#
# Steepness (max/min ratio) increases shift by shift:
#   S1-2: ~2.8   S3-4: ~3.3   S5-6: ~3.8   S7-9: ~4.3   S10: ~5.0
# ─────────────────────────────────────────────────────────────────────────────

SUBSTATION_LOAD_MW: dict[int, dict[str, dict[float, float]]] = {

    # ── SHIFT 1 ── 04:00-07:00, LD01 only, peak 55 MW ───────────────────────
    # Tutorial: pre-dawn trough into early morning ramp. Single hydro unit.
    # Values scaled from original 2200 MW shape (x55/2200). k~2.8.
    1: {
        'LD01': {
             0.0:  17,  1.0:  16,  2.0:  15,  3.0:  15,  4.0:  15,
             5.0:  17,  6.0:  21,  7.0:  27,  8.0:  36,  9.0:  44,
            10.0:  50, 11.0:  52, 12.0:  51, 13.0:  49, 14.0:  48,
            15.0:  50, 16.0:  52, 17.0:  54, 18.0:  55, 19.0:  54,
            20.0:  52, 21.0:  48, 22.0:  41, 23.0:  30, 24.0:  20,
        },
    },

    # ── SHIFT 2 ── 10:00-14:00, LD01 only, peak 315 MW ──────────────────────
    # RVSD-1 + RVSD-3 at TM (180 MW coal), DUND-1 at 40 MW = 220 MW initial.
    # DUND-2 on outage — DUND-1 max 65 MW is the ceiling. Load rises above
    # 245 MW (coal TM + DUND-1 max) to force RVSD ramping.
    2: {
        'LD01': {
             0.0: 100,  1.0:  95,  2.0:  90,  3.0:  88,  4.0:  90,
             5.0:  98,  6.0: 120,  7.0: 155,  8.0: 185,  9.0: 210,
            10.0: 215, 11.0: 245, 12.0: 268, 13.0: 292, 14.0: 315,
            15.0: 312, 16.0: 305, 17.0: 298, 18.0: 290, 19.0: 278,
            20.0: 262, 21.0: 238, 22.0: 208, 23.0: 165, 24.0: 122,
        },
    },

    # ── SHIFT 3 ── 14:00-20:00, LD01+LD02+LD06, peak 3800 MW ────────────────
    # Player sees afternoon climb into evening peak. k≈3.3.
    # Proportions: LD01≈51%, LD02≈32%, LD06≈17%
    # Peak MWs: LD01=1929, LD02=1215, LD06=657. Aggregate max ≈ 3800 MW at h18.
    3: {
        'LD01': {
             0.0:  540,  1.0:  502,  2.0:  477,  3.0:  463,  4.0:  473,
             5.0:  522,  6.0:  675,  7.0:  906,  8.0: 1166,  9.0: 1388,
            10.0: 1504, 11.0: 1561, 12.0: 1542, 13.0: 1504, 14.0: 1485,
            15.0: 1524, 16.0: 1658, 17.0: 1813, 18.0: 1929, 19.0: 1890,
            20.0: 1755, 21.0: 1581, 22.0: 1292, 23.0:  906, 24.0:  579,
        },
        'LD02': {
             0.0:  457,  1.0:  425,  2.0:  403,  3.0:  395,  4.0:  403,
             5.0:  441,  6.0:  547,  7.0:  684,  8.0:  851,  9.0:  988,
            10.0: 1080, 11.0: 1139, 12.0: 1169, 13.0: 1185, 14.0: 1169,
            15.0: 1154, 16.0: 1139, 17.0: 1169, 18.0: 1215, 19.0: 1200,
            20.0: 1109, 21.0: 1003, 22.0:  821, 23.0:  608, 24.0:  471,
        },
        'LD06': {
             0.0:  202,  1.0:  188,  2.0:  177,  3.0:  171,  4.0:  175,
             5.0:  194,  6.0:  247,  7.0:  322,  8.0:  407,  9.0:  478,
            10.0:  512, 11.0:  531, 12.0:  544, 13.0:  544, 14.0:  551,
            15.0:  583, 16.0:  623, 17.0:  630, 18.0:  657, 19.0:  650,
            20.0:  604, 21.0:  544, 22.0:  450, 23.0:  336, 24.0:  248,
        },
    },

    # ── SHIFT 4 ── 20:00-04:00, LD01+LD02+LD06, peak 3200 MW ────────────────
    # Player sees evening fall and overnight trough. k≈3.3.
    # Peak MWs: LD01=1624, LD02=1023, LD06=553. Aggregate max ≈ 3200 MW at h18.
    4: {
        'LD01': {
             0.0:  455,  1.0:  422,  2.0:  402,  3.0:  390,  4.0:  399,
             5.0:  438,  6.0:  568,  7.0:  762,  8.0:  982,  9.0: 1169,
            10.0: 1266, 11.0: 1314, 12.0: 1297, 13.0: 1266, 14.0: 1250,
            15.0: 1283, 16.0: 1395, 17.0: 1526, 18.0: 1624, 19.0: 1591,
            20.0: 1477, 21.0: 1331, 22.0: 1088, 23.0:  762, 24.0:  487,
        },
        'LD02': {
             0.0:  384,  1.0:  359,  2.0:  339,  3.0:  333,  4.0:  339,
             5.0:  370,  6.0:  461,  7.0:  576,  8.0:  716,  9.0:  832,
            10.0:  909, 11.0:  959, 12.0:  984, 13.0:  997, 14.0:  984,
            15.0:  972, 16.0:  959, 17.0:  984, 18.0: 1023, 19.0: 1010,
            20.0:  934, 21.0:  845, 22.0:  691, 23.0:  512, 24.0:  396,
        },
        'LD06': {
             0.0:  170,  1.0:  158,  2.0:  149,  3.0:  144,  4.0:  147,
             5.0:  163,  6.0:  208,  7.0:  271,  8.0:  342,  9.0:  403,
            10.0:  431, 11.0:  447, 12.0:  458, 13.0:  458, 14.0:  463,
            15.0:  491, 16.0:  525, 17.0:  530, 18.0:  553, 19.0:  548,
            20.0:  509, 21.0:  458, 22.0:  379, 23.0:  282, 24.0:  210,
        },
    },

    # ── SHIFT 5 ── 06:00-14:00, all 6 buses, peak 5800 MW ───────────────────
    # Full grid, player sees morning ramp to midday. k≈3.8.
    # Aggregate max ≈ 5800 MW (at h11, driven by LD03 industrial peak).
    5: {
        'LD01': {
             0.0:  366,  1.0:  336,  2.0:  313,  3.0:  298,  4.0:  305,
             5.0:  351,  6.0:  488,  7.0:  701,  8.0:  946,  9.0: 1144,
            10.0: 1251, 11.0: 1297, 12.0: 1267, 13.0: 1221, 14.0: 1206,
            15.0: 1251, 16.0: 1357, 17.0: 1464, 18.0: 1525, 19.0: 1494,
            20.0: 1373, 21.0: 1206, 22.0:  945, 23.0:  625, 24.0:  396,
        },
        'LD02': {
             0.0:  410,  1.0:  379,  2.0:  353,  3.0:  341,  4.0:  348,
             5.0:  385,  6.0:  484,  7.0:  620,  8.0:  782,  9.0:  924,
            10.0: 1020, 11.0: 1069, 12.0: 1094, 13.0: 1106, 14.0: 1094,
            15.0: 1081, 16.0: 1069, 17.0: 1094, 18.0: 1131, 19.0: 1119,
            20.0: 1020, 21.0:  911, 22.0:  732, 23.0:  534, 24.0:  410,
        },
        'LD03': {
             0.0:  192,  1.0:  181,  2.0:  177,  3.0:  177,  4.0:  181,
             5.0:  214,  6.0:  361,  7.0:  731,  8.0:  969,  9.0: 1025,
            10.0: 1061, 11.0: 1073, 12.0: 1050, 13.0: 1038, 14.0: 1050,
            15.0: 1073, 16.0: 1050, 17.0:  993, 18.0:  844, 19.0:  610,
            20.0:  384, 21.0:  282, 22.0:  248, 23.0:  237, 24.0:  214,
        },
        'LD04': {
             0.0:  236,  1.0:  215,  2.0:  202,  3.0:  195,  4.0:  202,
             5.0:  236,  6.0:  346,  7.0:  508,  8.0:  691,  9.0:  822,
            10.0:  889, 11.0:  930, 12.0:  943, 13.0:  943, 14.0:  930,
            15.0:  916, 16.0:  916, 17.0:  930, 18.0:  916, 19.0:  848,
            20.0:  739, 21.0:  616, 22.0:  481, 23.0:  331, 24.0:  242,
        },
        'LD05': {
             0.0:  253,  1.0:  234,  2.0:  219,  3.0:  209,  4.0:  212,
             5.0:  238,  6.0:  305,  7.0:  417,  8.0:  541,  9.0:  638,
            10.0:  688, 11.0:  709, 12.0:  701, 13.0:  683, 14.0:  674,
            15.0:  688, 16.0:  721, 17.0:  762, 18.0:  819, 19.0:  794,
            20.0:  745, 21.0:  688, 22.0:  574, 23.0:  410, 24.0:  295,
        },
        'LD06': {
             0.0:  172,  1.0:  159,  2.0:  148,  3.0:  142,  4.0:  145,
             5.0:  165,  6.0:  214,  7.0:  282,  8.0:  364,  9.0:  438,
            10.0:  474, 11.0:  491, 12.0:  502, 13.0:  497, 14.0:  502,
            15.0:  531, 16.0:  565, 17.0:  537, 18.0:  565, 19.0:  559,
            20.0:  502, 21.0:  449, 22.0:  367, 23.0:  271, 24.0:  201,
        },
    },

    # ── SHIFT 6 ── 12:00-20:00, all 6 buses, peak 6200 MW ───────────────────
    # Midday to evening peak, more pronounced. k≈3.8.
    # Aggregate max ≈ 6200 MW.
    6: {
        'LD01': {
             0.0:  390,  1.0:  358,  2.0:  334,  3.0:  317,  4.0:  325,
             5.0:  374,  6.0:  521,  7.0:  749,  8.0: 1010,  9.0: 1222,
            10.0: 1337, 11.0: 1386, 12.0: 1352, 13.0: 1304, 14.0: 1287,
            15.0: 1337, 16.0: 1451, 17.0: 1564, 18.0: 1629, 19.0: 1596,
            20.0: 1466, 21.0: 1287, 22.0: 1010, 23.0:  667, 24.0:  423,
        },
        'LD02': {
             0.0:  438,  1.0:  405,  2.0:  378,  3.0:  365,  4.0:  372,
             5.0:  412,  6.0:  518,  7.0:  664,  8.0:  836,  9.0:  988,
            10.0: 1089, 11.0: 1142, 12.0: 1169, 13.0: 1182, 14.0: 1169,
            15.0: 1156, 16.0: 1142, 17.0: 1169, 18.0: 1208, 19.0: 1195,
            20.0: 1089, 21.0:  974, 22.0:  783, 23.0:  571, 24.0:  438,
        },
        'LD03': {
             0.0:  205,  1.0:  193,  2.0:  188,  3.0:  188,  4.0:  193,
             5.0:  230,  6.0:  386,  7.0:  784,  8.0: 1037,  9.0: 1098,
            10.0: 1134, 11.0: 1146, 12.0: 1122, 13.0: 1109, 14.0: 1122,
            15.0: 1146, 16.0: 1122, 17.0: 1062, 18.0:  905, 19.0:  652,
            20.0:  411, 21.0:  302, 22.0:  266, 23.0:  254, 24.0:  230,
        },
        'LD04': {
             0.0:  251,  1.0:  231,  2.0:  215,  3.0:  207,  4.0:  215,
             5.0:  251,  6.0:  369,  7.0:  543,  8.0:  739,  9.0:  878,
            10.0:  950, 11.0:  992, 12.0: 1006, 13.0: 1006, 14.0:  992,
            15.0:  980, 16.0:  980, 17.0:  992, 18.0:  980, 19.0:  907,
            20.0:  790, 21.0:  659, 22.0:  514, 23.0:  353, 24.0:  259,
        },
        'LD05': {
             0.0:  270,  1.0:  251,  2.0:  234,  3.0:  224,  4.0:  228,
             5.0:  254,  6.0:  326,  7.0:  446,  8.0:  579,  9.0:  682,
            10.0:  735, 11.0:  757, 12.0:  749, 13.0:  730, 14.0:  722,
            15.0:  735, 16.0:  770, 17.0:  814, 18.0:  875, 19.0:  848,
            20.0:  796, 21.0:  735, 22.0:  612, 23.0:  438, 24.0:  314,
        },
        'LD06': {
             0.0:  184,  1.0:  170,  2.0:  159,  3.0:  153,  4.0:  156,
             5.0:  176,  6.0:  230,  7.0:  303,  8.0:  389,  9.0:  469,
            10.0:  507, 11.0:  525, 12.0:  537, 13.0:  531, 14.0:  537,
            15.0:  567, 16.0:  603, 17.0:  573, 18.0:  603, 19.0:  597,
            20.0:  537, 21.0:  481, 22.0:  393, 23.0:  290, 24.0:  214,
        },
    },

    # ── SHIFT 7 ── 06:00-16:00, all 6 buses, peak 7200 MW ───────────────────
    # Full morning to afternoon, steep transitions. k≈4.3.
    # Aggregate max ≈ 7200 MW.
    7: {
        'LD01': {
             0.0:  380,  1.0:  343,  2.0:  314,  3.0:  295,  4.0:  304,
             5.0:  361,  6.0:  552,  7.0:  836,  8.0: 1161,  9.0: 1465,
            10.0: 1637, 11.0: 1713, 12.0: 1675, 13.0: 1618, 14.0: 1598,
            15.0: 1655, 16.0: 1807, 17.0: 1865, 18.0: 1903, 19.0: 1865,
            20.0: 1713, 21.0: 1503, 22.0: 1161, 23.0:  741, 24.0:  438,
        },
        'LD02': {
             0.0:  466,  1.0:  435,  2.0:  403,  3.0:  388,  4.0:  395,
             5.0:  435,  6.0:  559,  7.0:  714,  8.0:  915,  9.0: 1086,
            10.0: 1203, 11.0: 1272, 12.0: 1304, 13.0: 1319, 14.0: 1304,
            15.0: 1288, 16.0: 1272, 17.0: 1304, 18.0: 1350, 19.0: 1335,
            20.0: 1219, 21.0: 1087, 22.0:  869, 23.0:  636, 24.0:  466,
        },
        'LD03': {
             0.0:  225,  1.0:  211,  2.0:  205,  3.0:  205,  4.0:  211,
             5.0:  254,  6.0:  451,  7.0:  945,  8.0: 1198,  9.0: 1269,
            10.0: 1311, 11.0: 1324, 12.0: 1297, 13.0: 1282, 14.0: 1297,
            15.0: 1324, 16.0: 1297, 17.0: 1226, 18.0: 1042, 19.0:  747,
            20.0:  465, 21.0:  339, 22.0:  296, 23.0:  282, 24.0:  254,
        },
        'LD04': {
             0.0:  275,  1.0:  251,  2.0:  233,  3.0:  227,  4.0:  233,
             5.0:  275,  6.0:  432,  7.0:  643,  8.0:  887,  9.0: 1054,
            10.0: 1138, 11.0: 1186, 12.0: 1198, 13.0: 1198, 14.0: 1186,
            15.0: 1175, 16.0: 1175, 17.0: 1186, 18.0: 1175, 19.0: 1090,
            20.0:  946, 21.0:  789, 22.0:  611, 23.0:  419, 24.0:  287,
        },
        'LD05': {
             0.0:  306,  1.0:  287,  2.0:  266,  3.0:  254,  4.0:  258,
             5.0:  289,  6.0:  368,  7.0:  511,  8.0:  675,  9.0:  798,
            10.0:  859, 11.0:  885, 12.0:  878, 13.0:  857, 14.0:  848,
            15.0:  859, 16.0:  899, 17.0:  949, 18.0: 1022, 19.0:  992,
            20.0:  931, 21.0:  859, 22.0:  715, 23.0:  511, 24.0:  368,
        },
        'LD06': {
             0.0:  211,  1.0:  197,  2.0:  183,  3.0:  176,  4.0:  180,
             5.0:  205,  6.0:  268,  7.0:  352,  8.0:  451,  9.0:  546,
            10.0:  592, 11.0:  613, 12.0:  626, 13.0:  621, 14.0:  626,
            15.0:  663, 16.0:  705, 17.0:  669, 18.0:  705, 19.0:  698,
            20.0:  626, 21.0:  564, 22.0:  458, 23.0:  339, 24.0:  247,
        },
    },

    # ── SHIFT 8 ── 00:00-08:00, all 6 buses, peak 4800 MW ───────────────────
    # Overnight minimum rising to morning start. k≈4.3.
    # Aggregate max ≈ 4800 MW.
    8: {
        'LD01': {
             0.0:  254,  1.0:  229,  2.0:  209,  3.0:  197,  4.0:  203,
             5.0:  241,  6.0:  368,  7.0:  557,  8.0:  774,  9.0:  977,
            10.0: 1091, 11.0: 1142, 12.0: 1117, 13.0: 1079, 14.0: 1066,
            15.0: 1104, 16.0: 1205, 17.0: 1243, 18.0: 1269, 19.0: 1243,
            20.0: 1142, 21.0: 1002, 22.0:  774, 23.0:  493, 24.0:  292,
        },
        'LD02': {
             0.0:  310,  1.0:  290,  2.0:  269,  3.0:  258,  4.0:  263,
             5.0:  290,  6.0:  373,  7.0:  477,  8.0:  611,  9.0:  724,
            10.0:  802, 11.0:  849, 12.0:  869, 13.0:  880, 14.0:  869,
            15.0:  859, 16.0:  849, 17.0:  869, 18.0:  900, 19.0:  890,
            20.0:  812, 21.0:  725, 22.0:  579, 23.0:  424, 24.0:  310,
        },
        'LD03': {
             0.0:  151,  1.0:  141,  2.0:  136,  3.0:  136,  4.0:  141,
             5.0:  169,  6.0:  300,  7.0:  629,  8.0:  799,  9.0:  846,
            10.0:  874, 11.0:  883, 12.0:  864, 13.0:  855, 14.0:  864,
            15.0:  883, 16.0:  864, 17.0:  817, 18.0:  695, 19.0:  498,
            20.0:  310, 21.0:  225, 22.0:  198, 23.0:  188, 24.0:  169,
        },
        'LD04': {
             0.0:  183,  1.0:  167,  2.0:  156,  3.0:  151,  4.0:  156,
             5.0:  183,  6.0:  288,  7.0:  429,  8.0:  591,  9.0:  703,
            10.0:  759, 11.0:  791, 12.0:  799, 13.0:  799, 14.0:  791,
            15.0:  783, 16.0:  783, 17.0:  791, 18.0:  783, 19.0:  727,
            20.0:  631, 21.0:  526, 22.0:  407, 23.0:  279, 24.0:  192,
        },
        'LD05': {
             0.0:  205,  1.0:  191,  2.0:  177,  3.0:  170,  4.0:  173,
             5.0:  192,  6.0:  246,  7.0:  341,  8.0:  450,  9.0:  531,
            10.0:  573, 11.0:  590, 12.0:  584, 13.0:  572, 14.0:  565,
            15.0:  573, 16.0:  599, 17.0:  633, 18.0:  681, 19.0:  661,
            20.0:  621, 21.0:  573, 22.0:  477, 23.0:  341, 24.0:  246,
        },
        'LD06': {
             0.0:  141,  1.0:  131,  2.0:  122,  3.0:  117,  4.0:  119,
             5.0:  136,  6.0:  178,  7.0:  235,  8.0:  300,  9.0:  364,
            10.0:  394, 11.0:  409, 12.0:  418, 13.0:  413, 14.0:  418,
            15.0:  441, 16.0:  470, 17.0:  446, 18.0:  470, 19.0:  465,
            20.0:  418, 21.0:  376, 22.0:  305, 23.0:  225, 24.0:  164,
        },
    },

    # ── SHIFT 9 ── 08:00-20:00, all 6 buses, peak 7800 MW ───────────────────
    # Full day — demanding. k≈4.3.
    # Aggregate max ≈ 7800 MW.
    9: {
        'LD01': {
             0.0:  412,  1.0:  372,  2.0:  342,  3.0:  319,  4.0:  330,
             5.0:  392,  6.0:  599,  7.0:  908,  8.0: 1258,  9.0: 1587,
            10.0: 1773, 11.0: 1855, 12.0: 1814, 13.0: 1752, 14.0: 1732,
            15.0: 1794, 16.0: 1958, 17.0: 2021, 18.0: 2062, 19.0: 2021,
            20.0: 1855, 21.0: 1629, 22.0: 1258, 23.0:  805, 24.0:  474,
        },
        'LD02': {
             0.0:  504,  1.0:  470,  2.0:  437,  3.0:  420,  4.0:  428,
             5.0:  470,  6.0:  605,  7.0:  773,  8.0:  991,  9.0: 1176,
            10.0: 1302, 11.0: 1378, 12.0: 1412, 13.0: 1428, 14.0: 1412,
            15.0: 1395, 16.0: 1378, 17.0: 1412, 18.0: 1462, 19.0: 1445,
            20.0: 1320, 21.0: 1176, 22.0:  941, 23.0:  689, 24.0:  504,
        },
        'LD03': {
             0.0:  245,  1.0:  229,  2.0:  221,  3.0:  221,  4.0:  229,
             5.0:  274,  6.0:  489,  7.0: 1023,  8.0: 1298,  9.0: 1375,
            10.0: 1421, 11.0: 1436, 12.0: 1405, 13.0: 1389, 14.0: 1405,
            15.0: 1436, 16.0: 1405, 17.0: 1330, 18.0: 1130, 19.0:  810,
            20.0:  504, 21.0:  367, 22.0:  321, 23.0:  305, 24.0:  274,
        },
        'LD04': {
             0.0:  299,  1.0:  272,  2.0:  253,  3.0:  247,  4.0:  253,
             5.0:  299,  6.0:  467,  7.0:  695,  8.0:  959,  9.0: 1142,
            10.0: 1233, 11.0: 1284, 12.0: 1298, 13.0: 1298, 14.0: 1284,
            15.0: 1272, 16.0: 1272, 17.0: 1284, 18.0: 1272, 19.0: 1181,
            20.0: 1025, 21.0:  855, 22.0:  663, 23.0:  454, 24.0:  311,
        },
        'LD05': {
             0.0:  332,  1.0:  310,  2.0:  288,  3.0:  276,  4.0:  280,
             5.0:  312,  6.0:  398,  7.0:  553,  8.0:  731,  9.0:  864,
            10.0:  931, 11.0:  957, 12.0:  950, 13.0:  928, 14.0:  918,
            15.0:  931, 16.0:  973, 17.0: 1028, 18.0: 1107, 19.0: 1074,
            20.0: 1007, 21.0:  931, 22.0:  775, 23.0:  553, 24.0:  398,
        },
        'LD06': {
             0.0:  229,  1.0:  213,  2.0:  199,  3.0:  191,  4.0:  195,
             5.0:  221,  6.0:  290,  7.0:  382,  8.0:  489,  9.0:  591,
            10.0:  641, 11.0:  664, 12.0:  679, 13.0:  672, 14.0:  679,
            15.0:  718, 16.0:  764, 17.0:  725, 18.0:  764, 19.0:  757,
            20.0:  679, 21.0:  611, 22.0:  496, 23.0:  367, 24.0:  267,
        },
    },

    # ── SHIFT 10 ── 06:00-18:00, all 6 buses, peak 8000 MW ──────────────────
    # Final shift, sharpest transitions. k≈5.0.
    # Aggregate max ≈ 8000 MW.
    10: {
        'LD01': {
             0.0:  378,  1.0:  337,  2.0:  305,  3.0:  281,  4.0:  292,
             5.0:  360,  6.0:  590,  7.0:  948,  8.0: 1347,  9.0: 1706,
            10.0: 1916, 11.0: 2000, 12.0: 1959, 13.0: 1894, 14.0: 1874,
            15.0: 1936, 16.0: 2084, 17.0: 2084, 18.0: 2106, 19.0: 2064,
            20.0: 1916, 21.0: 1663, 22.0: 1284, 23.0:  821, 24.0:  463,
        },
        'LD02': {
             0.0:  515,  1.0:  481,  2.0:  447,  3.0:  429,  4.0:  438,
             5.0:  481,  6.0:  618,  7.0:  790,  8.0: 1012,  9.0: 1201,
            10.0: 1330, 11.0: 1408, 12.0: 1442, 13.0: 1458, 14.0: 1442,
            15.0: 1425, 16.0: 1408, 17.0: 1442, 18.0: 1493, 19.0: 1476,
            20.0: 1347, 21.0: 1201, 22.0:  961, 23.0:  704, 24.0:  515,
        },
        'LD03': {
             0.0:  250,  1.0:  234,  2.0:  226,  3.0:  226,  4.0:  234,
             5.0:  281,  6.0:  499,  7.0: 1045,  8.0: 1326,  9.0: 1404,
            10.0: 1451, 11.0: 1466, 12.0: 1435, 13.0: 1419, 14.0: 1435,
            15.0: 1466, 16.0: 1435, 17.0: 1357, 18.0: 1154, 19.0:  827,
            20.0:  515, 21.0:  374, 22.0:  328, 23.0:  312, 24.0:  281,
        },
        'LD04': {
             0.0:  305,  1.0:  278,  2.0:  258,  3.0:  252,  4.0:  258,
             5.0:  305,  6.0:  478,  7.0:  710,  8.0:  980,  9.0: 1167,
            10.0: 1260, 11.0: 1312, 12.0: 1326, 13.0: 1326, 14.0: 1312,
            15.0: 1300, 16.0: 1300, 17.0: 1312, 18.0: 1300, 19.0: 1207,
            20.0: 1047, 21.0:  874, 22.0:  677, 23.0:  464, 24.0:  318,
        },
        'LD05': {
             0.0:  339,  1.0:  317,  2.0:  294,  3.0:  283,  4.0:  286,
             5.0:  320,  6.0:  408,  7.0:  565,  8.0:  747,  9.0:  882,
            10.0:  951, 11.0:  978, 12.0:  969, 13.0:  948, 14.0:  938,
            15.0:  951, 16.0:  993, 17.0: 1050, 18.0: 1131, 19.0: 1097,
            20.0: 1029, 21.0:  951, 22.0:  792, 23.0:  565, 24.0:  408,
        },
        'LD06': {
             0.0:  234,  1.0:  217,  2.0:  203,  3.0:  195,  4.0:  199,
             5.0:  225,  6.0:  296,  7.0:  390,  8.0:  499,  9.0:  604,
            10.0:  655, 11.0:  679, 12.0:  694, 13.0:  686, 14.0:  694,
            15.0:  733, 16.0:  780, 17.0:  741, 18.0:  780, 19.0:  772,
            20.0:  694, 21.0:  624, 22.0:  507, 23.0:  374, 24.0:  273,
        },
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# WIND PROFILE
#
# Normalised wind generation curve by hour. Scaled by rated_mw at runtime.
# ─────────────────────────────────────────────────────────────────────────────

WIND_PROFILE_NORMALISED: dict[float, float] = {
     0.0: 0.55,
     1.0: 0.58,
     2.0: 0.60,
     3.0: 0.62,
     4.0: 0.65,
     5.0: 0.63,
     6.0: 0.60,
     7.0: 0.55,
     8.0: 0.48,
     9.0: 0.42,
    10.0: 0.38,
    11.0: 0.35,
    12.0: 0.33,
    13.0: 0.32,
    14.0: 0.34,
    15.0: 0.38,
    16.0: 0.44,
    17.0: 0.50,
    18.0: 0.56,
    19.0: 0.60,
    20.0: 0.63,
    21.0: 0.65,
    22.0: 0.62,
    23.0: 0.58,
    24.0: 0.55,
}


# ─────────────────────────────────────────────────────────────────────────────
# SOLAR PROFILE
#
# Normalised solar generation curve by hour.
# ─────────────────────────────────────────────────────────────────────────────

SOLAR_PROFILE_NORMALISED: dict[float, float] = {
     0.0: 0.000,
     1.0: 0.000,
     2.0: 0.000,
     3.0: 0.000,
     4.0: 0.000,
     5.0: 0.000,
     6.0: 0.020,
     7.0: 0.120,
     8.0: 0.310,
     9.0: 0.520,
    10.0: 0.700,
    11.0: 0.850,
    12.0: 0.940,
    13.0: 1.000,
    14.0: 0.960,
    15.0: 0.880,
    16.0: 0.740,
    17.0: 0.560,
    18.0: 0.370,
    19.0: 0.190,
    20.0: 0.060,
    21.0: 0.005,
    22.0: 0.000,
    23.0: 0.000,
    24.0: 0.000,
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: INTERPOLATED PROFILE LOOKUP
# ─────────────────────────────────────────────────────────────────────────────

def get_profile_value(profile: dict[float, float], hour: float) -> float:
    """
    Interpolate a profile value at a given hour using linear interpolation.

    Args:
        profile: Dict mapping integer hours (0.0-24.0) to normalised values.
        hour:    Decimal hour to evaluate (e.g. 14.5 = 14:30).
                 Clamped to [0.0, 24.0].

    Returns:
        Linearly interpolated normalised value in [0.0, 1.0].
    """
    hour = max(0.0, min(24.0, hour))
    h_low = float(int(hour))
    h_high = h_low + 1.0
    if h_high > 24.0:
        return profile[24.0]
    t = hour - h_low
    return profile[h_low] * (1.0 - t) + profile.get(h_high, profile[24.0]) * t


def get_demand_mw(sim_hour: float, peak_demand_mw: float) -> float:
    """
    Return forecast demand in MW at a given simulation hour.

    Args:
        sim_hour:        Current time of day (decimal hours).
        peak_demand_mw:  Peak demand for this shift (from ShiftSpec).

    Returns:
        Forecast demand in MW (deterministic, no noise).
    """
    return get_profile_value(DEMAND_PROFILE_NORMALISED, sim_hour) * peak_demand_mw


def get_wind_mw(sim_hour: float, rated_mw: float) -> float:
    """Return forecast wind output in MW at a given simulation hour."""
    return get_profile_value(WIND_PROFILE_NORMALISED, sim_hour) * rated_mw


def get_solar_mw(sim_hour: float, rated_mw: float) -> float:
    """Return forecast solar output in MW at a given simulation hour."""
    return get_profile_value(SOLAR_PROFILE_NORMALISED, sim_hour) * rated_mw


def get_substation_demand_specs(shift: int) -> dict[str, SubstationDemandSpec]:
    """
    Return SubstationDemandSpec for each LD bus active at the given shift.

    Builds specs from the explicit per-shift hourly MW table in SUBSTATION_LOAD_MW.
    peak_mw is the maximum hourly value; profile is the normalised shape derived from it.
    """
    shift_table = SUBSTATION_LOAD_MW[shift]
    result: dict[str, SubstationDemandSpec] = {}
    for label, mw_table in shift_table.items():
        peak = float(max(mw_table.values()))
        profile = {h: v / peak for h, v in mw_table.items()}
        result[label] = SubstationDemandSpec(peak_mw=peak, profile=profile)
    return result
