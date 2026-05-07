"""
src/simulation/frequency.py

Frequency model for the GRIDCOM transmission network.

Models system frequency using the swing equation:
    df/dt = (f_nominal / (2 × H_sys)) × (P_imbalance_pu)

Where:
    H_sys       = generation-weighted average inertia constant (seconds)
    P_imbalance = (total_generation - total_load) / S_BASE  [per-unit]

Governor droop response reduces frequency deviation each tick:
    ΔP_droop = -(Δf / f_nominal) / DROOP_R × P_online_pu

Frequency is hard-clamped to [F_MIN, F_MAX] after each update.

See DOMAIN_GLOSSARY.md — "Frequency" and "Inertia Constant H" for definitions.
See GRID_SIMULATION_MECHANICS.md Section 5 for physics detail.
"""

import numpy as np

from simulation.constants import (
    F_NOMINAL,
    F_MIN,
    F_MAX,
    F_STABLE_TOL,
    DROOP_R,
    S_BASE,
    H_COAL,
    H_CCGT,
    H_NUCLEAR,
    H_HYDRO,
)

# Minimum inertia H to avoid division-by-zero when no synchronous units online.
_H_FLOOR: float = 0.1

# Unit-type to inertia constant mapping.
_INERTIA_MAP: dict[str, float] = {
    'COAL':       H_COAL,
    'CCGT':       H_CCGT,
    'NUCLEAR':    H_NUCLEAR,
    'HYDRO':      H_HYDRO,
    'HYDRO_ROR':  H_HYDRO,
    'HYDRO_PUMP': H_HYDRO,
    'WIND':       0.0,
    'SOLAR':      0.0,
}


class FrequencyModel:
    """
    System frequency model using the swing equation with governor droop.

    Maintains system frequency as a scalar state variable updated each tick.
    Droop response is applied as a correction term — it reduces the rate
    of change of frequency but does not eliminate steady-state deviation
    (that requires an AGC model, which is out of scope here).

    Attributes:
        frequency_hz:   Current system frequency in Hz.
        frequency_trend: 'RISING', 'FALLING', or 'STABLE'.

    Usage:
        fm = FrequencyModel()
        # Each simulation tick:
        fm.update(
            dt_sim_seconds=dt,
            p_generation_mw=total_gen,
            p_load_mw=total_load,
            online_unit_types=[('COAL', 300.0), ('NUCLEAR', 700.0), ...],
        )
        f = fm.frequency_hz
    """

    def __init__(self) -> None:
        """Initialise at nominal frequency."""
        self._frequency_hz: float = F_NOMINAL
        self._prev_frequency_hz: float = F_NOMINAL
        self._trend: str = 'STABLE'

    # ─────── PUBLIC INTERFACE ─────────────────────────────────────────────

    @property
    def frequency_hz(self) -> float:
        """Current system frequency in Hz."""
        return self._frequency_hz

    @property
    def frequency_trend(self) -> str:
        """'RISING', 'FALLING', or 'STABLE'."""
        return self._trend

    def update(
        self,
        dt_sim_seconds: float,
        p_generation_mw: float,
        p_load_mw: float,
        online_unit_types: list[tuple[str, float]],
    ) -> None:
        """
        Advance frequency by one simulation tick.

        Args:
            dt_sim_seconds:   Elapsed simulated time this tick (seconds).
            p_generation_mw:  Total online generation (MW). Losses already added
                              to load before calling.
            p_load_mw:        Total system load including losses (MW).
            online_unit_types: List of (unit_type, current_mw) for all ONLINE
                               units. Used to compute weighted system inertia H.
                               Wind and solar contribute zero inertia.
        """
        self._prev_frequency_hz = self._frequency_hz

        h_sys = self._compute_system_inertia(online_unit_types)

        p_imbalance_pu = (p_generation_mw - p_load_mw) / S_BASE

        # Droop correction: governor response proportional to frequency deviation.
        # This partially counters imbalance; positive deviation → reduce generation.
        delta_f = self._frequency_hz - F_NOMINAL
        p_online_pu = p_generation_mw / S_BASE
        droop_correction_pu = -(delta_f / F_NOMINAL) / DROOP_R * p_online_pu

        # Net per-unit imbalance seen by the swing equation.
        p_net_pu = p_imbalance_pu + droop_correction_pu

        # Swing equation: df/dt = (f0 / 2H) × P_net
        df_dt = (F_NOMINAL / (2.0 * h_sys)) * p_net_pu
        self._frequency_hz += df_dt * dt_sim_seconds

        # Hard clamp to operational limits.
        self._frequency_hz = float(np.clip(self._frequency_hz, F_MIN, F_MAX))

        self._update_trend()

    def reset(self) -> None:
        """Reset frequency to nominal. Used between shifts."""
        self._frequency_hz = F_NOMINAL
        self._prev_frequency_hz = F_NOMINAL
        self._trend = 'STABLE'

    # ─────── HELPERS ──────────────────────────────────────────────────────

    def _compute_system_inertia(
        self,
        online_unit_types: list[tuple[str, float]],
    ) -> float:
        """
        Compute generation-weighted average H constant (seconds).

        H_sys = Σ(H_i × P_i) / Σ(P_i)  for all online synchronous units.

        Returns _H_FLOOR if no synchronous generation is online (all wind/solar),
        to prevent division-by-zero and make the system extremely sensitive to
        frequency disturbances (as it would be physically).
        """
        total_weighted_h = 0.0
        total_sync_mw = 0.0

        for unit_type, current_mw in online_unit_types:
            h = _INERTIA_MAP.get(unit_type, 0.0)
            if h > 0.0 and current_mw > 0.0:
                total_weighted_h += h * current_mw
                total_sync_mw += current_mw

        if total_sync_mw < 1.0:
            return _H_FLOOR

        return total_weighted_h / total_sync_mw

    def _update_trend(self) -> None:
        """Set trend based on frequency change since last tick."""
        delta = self._frequency_hz - self._prev_frequency_hz
        if delta > F_STABLE_TOL:
            self._trend = 'RISING'
        elif delta < -F_STABLE_TOL:
            self._trend = 'FALLING'
        else:
            self._trend = 'STABLE'
