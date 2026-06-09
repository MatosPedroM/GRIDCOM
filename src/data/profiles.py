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
    """
    shift_number:     int
    start_hour:       float
    duration_hours:   float
    grid_size:        int
    has_phase1:       bool
    peak_demand_mw:   float


SHIFT_SPECS: dict[int, ShiftSpec] = {

    1:  ShiftSpec(shift_number=1,  start_hour=4.0,  duration_hours=3.0,  grid_size=3,  has_phase1=False, peak_demand_mw=55.0),
    2:  ShiftSpec(shift_number=2,  start_hour=10.0, duration_hours=4.0,  grid_size=3,  has_phase1=False, peak_demand_mw=315.0),
    3:  ShiftSpec(shift_number=3,  start_hour=14.0, duration_hours=6.0,  grid_size=20, has_phase1=False, peak_demand_mw=3800.0),
    4:  ShiftSpec(shift_number=4,  start_hour=20.0, duration_hours=8.0,  grid_size=20, has_phase1=False, peak_demand_mw=3200.0),
    5:  ShiftSpec(shift_number=5,  start_hour=6.0,  duration_hours=8.0,  grid_size=32, has_phase1=True,  peak_demand_mw=5800.0),
    6:  ShiftSpec(shift_number=6,  start_hour=12.0, duration_hours=8.0,  grid_size=32, has_phase1=True,  peak_demand_mw=6200.0),
    7:  ShiftSpec(shift_number=7,  start_hour=6.0,  duration_hours=10.0, grid_size=32, has_phase1=True,  peak_demand_mw=7200.0),
    8:  ShiftSpec(shift_number=8,  start_hour=0.0,  duration_hours=8.0,  grid_size=32, has_phase1=True,  peak_demand_mw=4800.0),
    9:  ShiftSpec(shift_number=9,  start_hour=8.0,  duration_hours=12.0, grid_size=32, has_phase1=True,  peak_demand_mw=7800.0),
    10: ShiftSpec(shift_number=10, start_hour=6.0,  duration_hours=12.0, grid_size=32, has_phase1=True,  peak_demand_mw=8000.0),
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


def get_substation_demand_specs(mw_table: dict) -> dict[str, SubstationDemandSpec]:
    """
    Build SubstationDemandSpec objects from a per-bus hourly MW table.

    Args:
        mw_table: {bus_label: {hour: mw}} — raw MW values per bus per hour.
                  Typically comes from the shift file's SUBSTATION_LOAD_MW.

    Returns:
        {bus_label: SubstationDemandSpec} where peak_mw is the max hourly value
        and profile is the normalised shape derived from it.
    """
    result: dict[str, SubstationDemandSpec] = {}
    for label, hourly in mw_table.items():
        peak = float(max(hourly.values()))
        profile = {h: v / peak for h, v in hourly.items()}
        result[label] = SubstationDemandSpec(peak_mw=peak, profile=profile)
    return result
