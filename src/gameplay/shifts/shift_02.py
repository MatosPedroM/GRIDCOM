"""
src/gameplay/shifts/shift_02.py

Shift 2 scenario definition — AGC regulation band tutorial.

Narrative:
  RVSD-1 and RVSD-3 are online at technical minimum (90 MW each).
  DUND-1 is the sole AGC unit (max 65 MW); DUND-2 is on planned maintenance.
  Demand rises through the shift, pushing DUND-1 toward saturation.
  The player must ramp RVSD to relieve DUND-1 and maintain regulation headroom.
"""

from __future__ import annotations


# Starting dispatch — units absent from this dict start OFFLINE.
INITIAL_SCHEDULE: dict[str, float] = {
    'RVSD-1': 90.0,   # Riverside Coal 1 — technical minimum (90 MW)
    'RVSD-3': 90.0,   # Riverside Coal 3 — technical minimum (90 MW)
    'DUND-1': 40.0,   # Dunmore Lower 1  — AGC, regulating
    # DUND-2 absent → OFFLINE (planned maintenance outage)
}


# ── Condition helpers ──────────────────────────────────────────────────────────

def _dund1_near_saturation(fleet) -> bool:
    """True when DUND-1 is being pushed above 55 MW — only ~10 MW headroom left."""
    cur, _, _ = fleet.agc_regulation_state()
    return cur > 55.0


def _reg_band_narrow(fleet) -> bool:
    """True when the available AGC bandwidth drops below 40 MW."""
    _, _min, _max = fleet.agc_regulation_state()
    return (_max - _min) < 40.0


# ── Scripted events ────────────────────────────────────────────────────────────

SCRIPTED_EVENTS: list[dict] = [
    {
        'trigger_min': 0.0,
        'priority':    'INFO',
        'message':     'DUND-2 on planned outage. AGC active on DUND-1 only.',
        'detail':      ('DUND-2 is unavailable for this shift (planned maintenance '
                        '09:00-17:00). DUND-1 is the sole AGC unit with a maximum '
                        'of 65 MW. Monitor the REG BAND panel — as demand rises, '
                        'DUND-1 will need headroom to respond.'),
        'element':     'DUND-2',
        'condition':   None,
    },
    {
        'trigger_min': 30.0,
        'priority':    'INFO',
        'message':     'Demand rising. Ramp RVSD before DUND-1 saturates.',
        'detail':      ('Load is climbing toward the DUND-1 ceiling. Increase '
                        'RVSD-1 or RVSD-3 output target so DUND-1 can settle '
                        'lower in its band and retain upward headroom for AGC.'),
        'element':     None,
        'condition':   None,
    },
    {
        'trigger_min': 60.0,
        'priority':    'WARNING',
        'message':     'DUND-1 nearing upper limit. Ramp RVSD to restore margin.',
        'detail':      ('AGC is holding DUND-1 above 55 MW. Only ~10 MW of upward '
                        'headroom remains. Ramp RVSD-1 or RVSD-3 to push DUND-1 '
                        'back toward mid-band and restore regulation capacity.'),
        'element':     'DUND-1',
        'condition':   _dund1_near_saturation,
    },
    {
        'trigger_min': 120.0,
        'priority':    'WARNING',
        'message':     'Regulation band narrow. Increase RVSD to relieve DUND-1.',
        'detail':      ('Available AGC bandwidth is below 40 MW. DUND-1 has '
                        'insufficient headroom to absorb further load increases. '
                        'Ramp RVSD-1 or RVSD-3 to allow DUND-1 to reduce output '
                        'and widen the regulation band.'),
        'element':     None,
        'condition':   _reg_band_narrow,
    },
]
