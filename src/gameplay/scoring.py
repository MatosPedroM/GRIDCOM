"""
src/gameplay/scoring.py

Single source of truth for end-of-shift grading.

Before this module the rubric lived in two duplicated inline copies in
main.py (build_debrief_lines() and the DEBRIEF event loop), which meant
retuning one silently desynced the other — and the campaign rating was a
hardcoded 'A' that ignored all ten shift results.

The rubric grades on five axes, all of which SimulationState already
measures and four of which were previously computed and thrown away:

    frequency   frequency_in_bounds_pct   headline metric, as before
    security    max_line_loading_seen     was displayed, never scored
                min_voltage_seen          was displayed, never scored
                unit trips                was displayed, never scored
                load_shed_events          scored, but structurally always 0
                                          until load shedding was wired up

Bands are evaluated worst-first: a shift earns EXCELLENT only if it clears
every EXCELLENT gate, then SATISFACTORY, and so on. That means a run that
holds frequency perfectly while collapsing a bus to 0.6 pu no longer grades
the same as a genuinely clean run — which was the concrete symptom of the
frequency-only rubric (Shift 4 is entirely a voltage shift, and voltage did
not affect its result at all).

The efficiency axis from the design docs is deliberately absent: no cost
model exists anywhere in the codebase, so there is nothing to score.
"""

from __future__ import annotations

from simulation.constants import (
    SCORE_FREQ_PCT_EXCELLENT, SCORE_FREQ_PCT_SATISFACTORY, SCORE_FREQ_PCT_MARGINAL,
    SCORE_LOADING_PCT_EXCELLENT, SCORE_LOADING_PCT_SATISFACTORY,
    SCORE_VOLTAGE_PU_EXCELLENT, SCORE_VOLTAGE_PU_SATISFACTORY,
    SCORE_UNIT_TRIPS_EXCELLENT, SCORE_UNIT_TRIPS_SATISFACTORY,
    SCORE_SHED_EVENTS_EXCELLENT, SCORE_SHED_EVENTS_SATISFACTORY,
    SCORE_CAMPAIGN_FRACTION,
)

# Ordered best-to-worst. FAILED is not a band — it is set by the caller when
# the shift ended early (blackout or a FAIL_CONDITION) and overrides grading.
GRADE_EXCELLENT      = 'EXCELLENT'
GRADE_SATISFACTORY   = 'SATISFACTORY'
GRADE_MARGINAL       = 'MARGINAL'
GRADE_UNSATISFACTORY = 'UNSATISFACTORY'
GRADE_FAILED         = 'FAILED'

GRADE_ORDER = (
    GRADE_FAILED,
    GRADE_UNSATISFACTORY,
    GRADE_MARGINAL,
    GRADE_SATISFACTORY,
    GRADE_EXCELLENT,
)


def count_unit_trips(state) -> int:
    """Number of units in the TRIPPED state at shift end."""
    return sum(1 for s in state.unit_states.values() if s == 'TRIPPED')


def grade_shift(state, failed: bool = False, failed_objective: dict | None = None) -> dict:
    """
    Grade one completed shift.

    Args:
        state:            SimulationState snapshot at shift end.
        failed:           True if the shift ended early — a frequency
                          collapse/blackout, or a FAIL_CONDITION being met.
        failed_objective: The FAIL_CONDITION dict that ended the shift, if
                          any (GridSimulation.get_failed_objective()). Used
                          only to explain *why* in the returned reason.

    Returns a dict:
        grade    str              one of the GRADE_* words
        reason   str              short operator-facing explanation
        metrics  dict[str, ...]   the five scored axes, for display
        axes     dict[str, str]   per-axis grade, so a debrief can show
                                  which axis held the overall grade down
    """
    trips = count_unit_trips(state)

    metrics = {
        'frequency_in_bounds_pct': state.frequency_in_bounds_pct,
        'max_line_loading_pct':    state.max_line_loading_seen,
        'min_voltage_pu':          state.min_voltage_seen,
        'unit_trips':              trips,
        'load_shed_events':        state.load_shed_events,
        'cascade_events':          state.cascade_events,
        'derate_events':           state.derate_events,
        'drift_events':            state.drift_events,
    }

    if failed:
        if failed_objective is not None:
            reason = failed_objective.get(
                'message', 'Operating limit breached — shift terminated early.'
            )
        else:
            reason = ('System frequency remained outside safe limits until protective '
                      'systems isolated the network.')
        return {
            'grade':   GRADE_FAILED,
            'reason':  reason,
            'metrics': metrics,
            'axes':    {k: GRADE_FAILED for k in ('frequency', 'loading', 'voltage',
                                                  'trips', 'shedding')},
        }

    axes = {
        'frequency': _band(
            state.frequency_in_bounds_pct,
            SCORE_FREQ_PCT_EXCELLENT, SCORE_FREQ_PCT_SATISFACTORY,
            SCORE_FREQ_PCT_MARGINAL, higher_is_better=True,
        ),
        'loading': _band(
            state.max_line_loading_seen,
            SCORE_LOADING_PCT_EXCELLENT, SCORE_LOADING_PCT_SATISFACTORY,
            None, higher_is_better=False,
        ),
        'voltage': _band(
            state.min_voltage_seen,
            SCORE_VOLTAGE_PU_EXCELLENT, SCORE_VOLTAGE_PU_SATISFACTORY,
            None, higher_is_better=True,
        ),
        'trips': _band(
            trips,
            SCORE_UNIT_TRIPS_EXCELLENT, SCORE_UNIT_TRIPS_SATISFACTORY,
            None, higher_is_better=False,
        ),
        'shedding': _band(
            state.load_shed_events,
            SCORE_SHED_EVENTS_EXCELLENT, SCORE_SHED_EVENTS_SATISFACTORY,
            None, higher_is_better=False,
        ),
    }

    # A cascade is a security failure in its own right — it can never be part
    # of an EXCELLENT shift, matching the pre-existing rubric's intent.
    if state.cascade_events > 0 and axes['loading'] == GRADE_EXCELLENT:
        axes['loading'] = GRADE_SATISFACTORY

    grade = min(axes.values(), key=GRADE_ORDER.index)

    worst = [name for name, g in axes.items() if g == grade]
    if grade == GRADE_EXCELLENT:
        reason = 'Frequency, voltage and network security all within limits.'
    else:
        reason = f'Held back by: {", ".join(sorted(worst))}.'

    return {'grade': grade, 'reason': reason, 'metrics': metrics, 'axes': axes}


def grade_campaign(shift_grades: dict) -> str:
    """
    Roll ten shift grades up into one campaign rating.

    A campaign earns a grade when at least SCORE_CAMPAIGN_FRACTION of the
    completed shifts reach it — so a strong run with one disaster does not
    read as flawless, and one lucky shift does not carry a weak campaign.
    Any FAILED shift caps the campaign at MARGINAL.

    Returns a GRADE_* word, or GRADE_UNSATISFACTORY if nothing was completed.
    """
    grades = [g for g in shift_grades.values() if g in GRADE_ORDER]
    if not grades:
        return GRADE_UNSATISFACTORY

    needed = max(1, int(len(grades) * SCORE_CAMPAIGN_FRACTION))
    result = GRADE_UNSATISFACTORY
    for candidate in (GRADE_EXCELLENT, GRADE_SATISFACTORY, GRADE_MARGINAL):
        reached = sum(1 for g in grades
                      if GRADE_ORDER.index(g) >= GRADE_ORDER.index(candidate))
        if reached >= needed:
            result = candidate
            break

    if GRADE_FAILED in grades and GRADE_ORDER.index(result) > GRADE_ORDER.index(GRADE_MARGINAL):
        result = GRADE_MARGINAL
    return result


def _band(value, excellent, satisfactory, marginal, higher_is_better: bool) -> str:
    """
    Place one measured value into a grade band.

    marginal may be None for axes with only two meaningful gates (loading,
    voltage, trips, shedding) — anything past the SATISFACTORY gate on those
    is UNSATISFACTORY rather than MARGINAL.
    """
    def meets(threshold) -> bool:
        if threshold is None:
            return False
        return value >= threshold if higher_is_better else value <= threshold

    if meets(excellent):
        return GRADE_EXCELLENT
    if meets(satisfactory):
        return GRADE_SATISFACTORY
    if meets(marginal):
        return GRADE_MARGINAL
    return GRADE_UNSATISFACTORY
