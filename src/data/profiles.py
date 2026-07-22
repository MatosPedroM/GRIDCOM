"""
src/data/profiles.py

Demand profiles and renewable generation profiles for the GRIDCOM campaign.

Each 150kV load substation has an explicit per-shift hourly load table (MW).
Total system demand is the bottom-up sum of active substation demands.
Noise and stochastic variation are applied by the simulation layer.

See DOMAIN_GLOSSARY.md for campaign terms and shift definitions.
See GAMEPLAY_REFERENCE.md for campaign structure.
"""

from dataclasses import dataclass


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
    substation_type: str = 'MIXED'   # 'INDUSTRIAL' | 'RESIDENTIAL' | 'MIXED' — determines power factor



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
        hour:    Decimal hour to evaluate (e.g. 14.5 = 14:30). Elapsed sim
                 hours beyond 24.0 (test sessions starting late in the day)
                 wrap around to the same daily curve rather than flatlining
                 at the hour-24 value.

    Returns:
        Linearly interpolated normalised value in [0.0, 1.0].
    """
    hour = hour % 24.0
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
        peak_demand_mw:  Peak demand for this shift (sum of its grid's LOAD bus
                         peak_load_mw values, from load_shift_config()).

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


def get_substation_demand_specs(
    mw_table: dict,
    substation_types: dict[str, str] | None = None,
) -> dict[str, SubstationDemandSpec]:
    """
    Build SubstationDemandSpec objects from a per-bus hourly MW table.

    Args:
        mw_table: {bus_label: {hour: mw}} — raw MW values per bus per hour.
                  Typically comes from the shift file's SUBSTATION_LOAD_MW.
        substation_types: Optional {bus_label: 'INDUSTRIAL'|'RESIDENTIAL'|'MIXED'}.
                  Buses not present default to 'MIXED'.

    Returns:
        {bus_label: SubstationDemandSpec} where peak_mw is the max hourly value
        and profile is the normalised shape derived from it.
    """
    substation_types = substation_types or {}
    result: dict[str, SubstationDemandSpec] = {}
    for label, hourly in mw_table.items():
        peak = float(max(hourly.values()))
        profile = {h: v / peak for h, v in hourly.items()}
        result[label] = SubstationDemandSpec(
            peak_mw=peak,
            profile=profile,
            substation_type=substation_types.get(label, 'MIXED'),
        )
    return result


def default_substation_types(bus_labels) -> dict[str, str]:
    """
    Deterministically assign a substation type to each load bus label,
    cycling INDUSTRIAL / RESIDENTIAL / MIXED in sorted label order.

    Runtime-seeding helper for sessions with no authored substation types
    (Designer/DESIGNER_TEST grids) — not used for campaign shifts, which
    may author types explicitly in the shift file in a future pass.
    """
    cycle = ('INDUSTRIAL', 'RESIDENTIAL', 'MIXED')
    return {
        label: cycle[i % len(cycle)]
        for i, label in enumerate(sorted(bus_labels))
    }
