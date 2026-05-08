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

from dataclasses import dataclass, field


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
# LOAD DISTRIBUTION
#
# Fraction of total system demand at each load substation.
# Must sum to 1.0.
# ─────────────────────────────────────────────────────────────────────────────

# Shifts 1-2: south sub-grid only — load distributed to active 220kV buses
_LOAD_DIST_SHIFT1: dict[str, float] = {
    'ASHF': 0.30,
    'WRNT': 0.25,
    'FAIR': 0.25,
    'DUNM': 0.20,
}

# Shifts 3-4: south + centre — load spread across expanded 220kV network
_LOAD_DIST_SHIFT3: dict[str, float] = {
    'ASHF': 0.20,
    'WRNT': 0.20,
    'FAIR': 0.18,
    'DUNM': 0.12,
    'RDST': 0.12,
    'COAL': 0.10,
    'BARR': 0.08,
}

# Shifts 5-10: full grid with dedicated 150kV load substations
_LOAD_DIST_SHIFT5: dict[str, float] = {
    'LD01': 0.18,
    'LD02': 0.22,
    'LD03': 0.20,
    'LD04': 0.16,
    'LD05': 0.14,
    'LD06': 0.10,
}

# Backwards-compatible alias — points to the full-grid distribution
LOAD_DISTRIBUTION: dict[str, float] = _LOAD_DIST_SHIFT5


def get_load_distribution(shift: int) -> dict[str, float]:
    """Return the load distribution dict appropriate for the given shift."""
    if shift >= 5:
        return _LOAD_DIST_SHIFT5
    elif shift >= 3:
        return _LOAD_DIST_SHIFT3
    else:
        return _LOAD_DIST_SHIFT1


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
