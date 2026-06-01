"""
src/data/profiles.py

Demand profiles, renewable generation profiles, and shift specifications
for the GRIDCOM 10-shift campaign.

Demand is modelled as a normalised daily curve (0.0-1.0) scaled to peak
demand for the shift. Noise and stochastic variation are applied by the
simulation layer — these are deterministic forecast values.

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
        shift_number=1, start_hour=6.0, duration_hours=4.0,
        grid_size=12, has_phase1=False, peak_demand_mw=2200.0,
        difficulty_label='Introductory',
        handover_notes=(
            'Morning handover from R. Ferris.',
            'RVSD-2 OOS — planned relay maintenance, returns 14:00.',
            'HART-1 and HART-2 online, both at 680MW.',
            'Demand building toward morning peak.',
            'No planned outages. Frequency nominal.',
        ),
    ),

    2: ShiftSpec(
        shift_number=2, start_hour=10.0, duration_hours=4.0,
        grid_size=12, has_phase1=False, peak_demand_mw=2400.0,
        difficulty_label='Introductory',
        handover_notes=(
            'Mid-morning handover.',
            'RVSD-2 returned to service 09:45.',
            'System normal. Demand at mid-morning plateau.',
            'Unit start/stop controls unlocked this shift.',
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
# Scaled by peak_demand_mw at runtime. 0.0 = midnight minimum, 1.0 = peak.
#
# Shape: overnight low ~35%, morning ramp 06-09h, mid-day plateau,
# evening peak 17-20h, decline to overnight minimum.
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
#
# Each 150kV load substation has its own normalised daily curve and peak MW.
# Total system demand is the bottom-up sum of active substation demands.
#
# Active substations by shift:
#   Shifts 1-2:  LD01
#   Shifts 3-4:  LD01, LD02, LD06
#   Shifts 5-10: LD01, LD02, LD03, LD04, LD05, LD06
#
# peak_mw is fixed across all shifts. Aggregate at Shift 5 peak ≈ 5800 MW.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SubstationDemandSpec:
    """Demand specification for one 150kV load substation."""
    peak_mw: float
    profile: dict[float, float]   # 25 hourly values (0.0–24.0), normalised 0.0–1.0


# LD01 — south-west, residential: double peak (morning 08h + evening 18h)
_PROFILE_LD01: dict[float, float] = {
     0.0: 0.310,  1.0: 0.285,  2.0: 0.270,  3.0: 0.260,  4.0: 0.268,
     5.0: 0.310,  6.0: 0.420,  7.0: 0.580,  8.0: 0.730,  9.0: 0.820,
    10.0: 0.840, 11.0: 0.830, 12.0: 0.810, 13.0: 0.790, 14.0: 0.800,
    15.0: 0.840, 16.0: 0.900, 17.0: 0.960, 18.0: 1.000, 19.0: 0.980,
    20.0: 0.920, 21.0: 0.840, 22.0: 0.700, 23.0: 0.510, 24.0: 0.350,
}

# LD02 — central, mixed commercial/residential: broad midday plateau
_PROFILE_LD02: dict[float, float] = {
     0.0: 0.370,  1.0: 0.350,  2.0: 0.335,  3.0: 0.325,  4.0: 0.330,
     5.0: 0.360,  6.0: 0.450,  7.0: 0.580,  8.0: 0.700,  9.0: 0.800,
    10.0: 0.870, 11.0: 0.910, 12.0: 0.930, 13.0: 0.940, 14.0: 0.930,
    15.0: 0.920, 16.0: 0.910, 17.0: 0.930, 18.0: 0.960, 19.0: 0.950,
    20.0: 0.890, 21.0: 0.800, 22.0: 0.660, 23.0: 0.490, 24.0: 0.380,
}

# LD03 — north-east, heavy industrial: strong flat block 07-19h, low overnight
_PROFILE_LD03: dict[float, float] = {
     0.0: 0.220,  1.0: 0.210,  2.0: 0.205,  3.0: 0.205,  4.0: 0.210,
     5.0: 0.240,  6.0: 0.380,  7.0: 0.750,  8.0: 0.940,  9.0: 0.980,
    10.0: 1.000, 11.0: 1.000, 12.0: 0.980, 13.0: 0.970, 14.0: 0.980,
    15.0: 1.000, 16.0: 0.980, 17.0: 0.920, 18.0: 0.780, 19.0: 0.560,
    20.0: 0.340, 21.0: 0.260, 22.0: 0.240, 23.0: 0.230, 24.0: 0.225,
}

# LD04 — east, commercial/retail: strong morning ramp, modest evening tail
_PROFILE_LD04: dict[float, float] = {
     0.0: 0.280,  1.0: 0.260,  2.0: 0.248,  3.0: 0.242,  4.0: 0.248,
     5.0: 0.280,  6.0: 0.400,  7.0: 0.580,  8.0: 0.760,  9.0: 0.880,
    10.0: 0.940, 11.0: 0.970, 12.0: 0.980, 13.0: 0.980, 14.0: 0.970,
    15.0: 0.960, 16.0: 0.960, 17.0: 0.970, 18.0: 0.960, 19.0: 0.900,
    20.0: 0.800, 21.0: 0.680, 22.0: 0.540, 23.0: 0.390, 24.0: 0.290,
}

# LD05 — north, mixed urban: follows system shape closely
_PROFILE_LD05: dict[float, float] = {
     0.0: 0.360,  1.0: 0.340,  2.0: 0.325,  3.0: 0.315,  4.0: 0.320,
     5.0: 0.350,  6.0: 0.440,  7.0: 0.580,  8.0: 0.720,  9.0: 0.820,
    10.0: 0.870, 11.0: 0.890, 12.0: 0.880, 13.0: 0.860, 14.0: 0.850,
    15.0: 0.870, 16.0: 0.910, 17.0: 0.960, 18.0: 1.000, 19.0: 0.980,
    20.0: 0.930, 21.0: 0.860, 22.0: 0.740, 23.0: 0.540, 24.0: 0.390,
}

# LD06 — south, smaller urban/suburban: evening-heavy, later peak
_PROFILE_LD06: dict[float, float] = {
     0.0: 0.330,  1.0: 0.308,  2.0: 0.293,  3.0: 0.284,  4.0: 0.290,
     5.0: 0.325,  6.0: 0.415,  7.0: 0.540,  8.0: 0.660,  9.0: 0.750,
    10.0: 0.790, 11.0: 0.810, 12.0: 0.820, 13.0: 0.810, 14.0: 0.820,
    15.0: 0.860, 16.0: 0.920, 17.0: 0.980, 18.0: 1.000, 19.0: 0.990,
    20.0: 0.950, 21.0: 0.890, 22.0: 0.780, 23.0: 0.600, 24.0: 0.420,
}

SUBSTATION_DEMAND: dict[str, SubstationDemandSpec] = {
    'LD01': SubstationDemandSpec(peak_mw=2200.0, profile=_PROFILE_LD01),
    'LD02': SubstationDemandSpec(peak_mw=1800.0, profile=_PROFILE_LD02),
    'LD03': SubstationDemandSpec(peak_mw=1600.0, profile=_PROFILE_LD03),
    'LD04': SubstationDemandSpec(peak_mw=1400.0, profile=_PROFILE_LD04),
    'LD05': SubstationDemandSpec(peak_mw=1200.0, profile=_PROFILE_LD05),
    'LD06': SubstationDemandSpec(peak_mw=800.0,  profile=_PROFILE_LD06),
}

# LD buses activated by shift number (cumulative — each shift includes all prior)
_ACTIVE_LD_BY_SHIFT: list[tuple[int, str]] = [
    (1, 'LD01'),
    (3, 'LD02'),
    (3, 'LD06'),
    (5, 'LD03'),
    (5, 'LD04'),
    (5, 'LD05'),
]


def get_substation_demand_specs(shift: int) -> dict[str, SubstationDemandSpec]:
    """Return SubstationDemandSpec for each LD bus active at the given shift."""
    return {
        label: SUBSTATION_DEMAND[label]
        for active_from, label in _ACTIVE_LD_BY_SHIFT
        if shift >= active_from
    }


# ─────────────────────────────────────────────────────────────────────────────
# WIND PROFILE
#
# Normalised wind generation curve by hour. Scaled by rated_mw at runtime.
# Represents a moderate wind day with afternoon lull and night strengthening.
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
# Zero at night (before ~06:30 and after ~20:30 in summer).
# Peak at solar noon (~13:00).
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
