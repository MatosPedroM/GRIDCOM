"""
src/gameplay/shifts/shift_03.py

Shift 3 scenario definition — placeholder.
"""

from __future__ import annotations


SHIFT_DATE: str = 'MON 07 NOV 1994'

DIFFICULTY_LABEL: str = 'Standard'

HANDOVER_NOTES: tuple[str, ...] = (
    'Afternoon shift. Centre grid now online.',
    'CCGT and pumped storage units now available.',
    'Afternoon demand peak expected 17:00-19:00.',
    'Wind forecast moderate. Solar declining from 15:00.',
)

INITIAL_SCHEDULE: dict[str, float] = {}

MAINTENANCE_UNITS: set[str] = set()

AGC_ENABLED: bool = False

# Per-bus hourly load table (MW). Shift 3: LD01+LD02+LD06, peak 3800 MW.
# Afternoon climb into evening peak. Proportions: LD01≈51%, LD02≈32%, LD06≈17%.
SUBSTATION_LOAD_MW: dict[str, dict[float, float]] = {
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
}

SCRIPTED_EVENTS: list[dict] = []
