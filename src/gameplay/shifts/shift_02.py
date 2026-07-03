"""
src/gameplay/shifts/shift_02.py

Shift 2 scenario definition — AGC regulation band tutorial.

Narrative:
  Riverside Coal is commissioned onto the Midbury busbar this shift.
  RVSD-1 is online; RVSD-2 is out of service (planned relay maintenance —
  the COALCOM easter egg) and RVSD-3 remains available for cold start.
  DUND-1 is the sole AGC unit (max 65 MW); DUND-2 is on planned maintenance.
  Demand rises through the shift, pushing DUND-1 toward saturation.
  The player must ramp RVSD-1 to relieve DUND-1 and maintain regulation headroom.

Grid: MDBY ──L11──► DUND ──L49──► LD01, ──L50──► LD02   (4 buses, 3 lines)
"""

from __future__ import annotations


SHIFT_DATE: str = 'MON 07 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

HANDOVER_NOTES: tuple[str, ...] = (
    'Mid-morning handover.',
    'Riverside Coal commissioned at Midbury this shift.',
    'RVSD-1 on-line at 200 MW. RVSD-2 out of service — planned relay maintenance.',
    'RVSD-3 available, cold start 240 min.',
    'DUND-1 on-line at 40 MW. DUND-2 on planned maintenance outage.',
    'Demand rising. DUND-1 is the sole AGC unit — headroom is limited.',
    'AGC active — ramp RVSD-1 as load grows to keep DUND-1 in its band.',
)

MAINTENANCE_UNITS: set[str] = {'RVSD-2', 'DUND-2'}

AGC_ENABLED: bool = True

# Per-bus hourly load table (MW). Shift 2: LD01 + LD02, peak 315 MW.
# RVSD-1 at 200 MW coal, DUND-1 at 40 MW = 240 MW initial.
# Load rises above 265 MW (200 MW coal + 65 MW DUND-1 max) to force RVSD ramping.
# LD01 (55%): peak ≈ 173 MW. LD02 (45%): peak ≈ 142 MW.
SUBSTATION_LOAD_MW: dict[str, dict[float, float]] = {
    'LD01': {
         0.0:  55,  1.0:  52,  2.0:  50,  3.0:  48,  4.0:  50,
         5.0:  54,  6.0:  66,  7.0:  85,  8.0: 102,  9.0: 116,
        10.0: 118, 11.0: 135, 12.0: 147, 13.0: 161, 14.0: 173,
        15.0: 172, 16.0: 168, 17.0: 164, 18.0: 160, 19.0: 153,
        20.0: 144, 21.0: 131, 22.0: 114, 23.0:  91, 24.0:  67,
    },
    'LD02': {
         0.0:  45,  1.0:  43,  2.0:  40,  3.0:  40,  4.0:  40,
         5.0:  44,  6.0:  54,  7.0:  70,  8.0:  83,  9.0:  94,
        10.0:  97, 11.0: 110, 12.0: 121, 13.0: 131, 14.0: 142,
        15.0: 140, 16.0: 137, 17.0: 134, 18.0: 130, 19.0: 125,
        20.0: 118, 21.0: 107, 22.0:  94, 23.0:  74, 24.0:  55,
    },
}

# Starting dispatch — units absent from this dict start OFFLINE.
INITIAL_SCHEDULE: dict[str, float] = {
    'RVSD-1': 200.0,   # Riverside Coal 1 — 200 MW at handover
    'DUND-1': 40.0,    # Dunmore Lower 1  — AGC, regulating
    # RVSD-2 absent → OFFLINE (relay maintenance — COALCOM easter egg)
    # RVSD-3 absent → OFFLINE (available, cold start)
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
        'message':     'RVSD-2 on relay maintenance. AGC active on DUND-1 only.',
        'detail':      ('RVSD-2 is unavailable for this shift (planned relay '
                        'maintenance). DUND-1 is the sole AGC unit with a maximum '
                        'of 65 MW. Monitor the REG BAND panel — as demand rises, '
                        'DUND-1 will need headroom to respond.'),
        'element':     'RVSD-2',
        'condition':   None,
    },
    {
        'trigger_min': 30.0,
        'priority':    'INFO',
        'message':     'Demand rising. Ramp RVSD before DUND-1 saturates.',
        'detail':      ('Load is climbing toward the DUND-1 ceiling. Increase '
                        'RVSD-1 output target (or cold-start RVSD-3) so DUND-1 '
                        'can settle lower in its band and retain upward headroom '
                        'for AGC.'),
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
