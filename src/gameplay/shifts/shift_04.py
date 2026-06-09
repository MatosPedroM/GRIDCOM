"""
src/gameplay/shifts/shift_04.py

Shift 4 scenario definition — placeholder.
"""

from __future__ import annotations


SHIFT_DATE: str = 'MON 07 NOV 1994'

DIFFICULTY_LABEL: str = 'Standard'

HANDOVER_NOTES: tuple[str, ...] = (
    'Evening / overnight shift.',
    'Demand falling after 21:00. Low overnight valley.',
    'Load shedding controls unlocked this shift.',
    'Two units due for overnight maintenance windows.',
)

INITIAL_SCHEDULE: dict[str, float] = {}

MAINTENANCE_UNITS: set[str] = set()

AGC_ENABLED: bool = False

# Per-bus hourly load table (MW). Shift 4: LD01+LD02+LD06, peak 3200 MW.
# Evening fall and overnight trough.
SUBSTATION_LOAD_MW: dict[str, dict[float, float]] = {
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
}

SCRIPTED_EVENTS: list[dict] = []
