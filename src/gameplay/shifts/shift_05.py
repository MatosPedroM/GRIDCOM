"""
src/gameplay/shifts/shift_05.py

Shift 5 scenario definition — "The Plan": Phase 1 planning introduced.

Narrative:
  For the first time, the shift does not open straight into real-time play.
  After the handover briefing, the dispatcher builds an hourly generation
  schedule on the Planning screen — deciding, hour by hour, which units run
  and at what output — before the shift clock starts. Confirming the plan
  (F10) seeds the 07:00 handover dispatch and hands every scheduled unit to
  the grid in AUTO dispatch mode: each unit follows the planned programme
  on its own as the hour advances, exactly as written, until the player
  intervenes. Touching a unit's MW target directly (the same digit-key +
  Enter dispatch from Shifts 1-2) drops that one unit to MANUAL — the
  player is now flying it by hand, same as every shift before this one.
  Pressing M on a MANUAL unit returns it to AUTO, handing it back to the
  plan.

  RIVE-1/RIVE-2 (coal), BATH-1/BATH-2 (hydro), PIKE-1/PIKE-2 (hydro),
  SHEL-1/SHEL-2 (CCGT) and ASHC-1/2/3 (small hydro) are all available to
  schedule; RIVE-3 is visible but on maintenance this shift — a reminder
  that not every spare can be leaned on (coal's cold start is four hours,
  longer than the shift itself). SUTT-1 (wind) is never scheduled by the
  player — its forecast is shown on the planning screen as a locked row,
  the campaign's first look at a non-dispatchable source feeding into the
  balance.

  The played window is 07:00-11:00, the steepest part of the morning ramp
  (forecast demand climbs from ~890 MW to ~1370 MW across the four hours —
  peak system demand is 1540 MW). A plan that tracks the forecast closely,
  hour by hour, leaves little spinning reserve in AUTO; a plan that leaves
  headroom above forecast on the fast-ramping hydro (BATH/PIKE, 100%/min)
  rides out what happens next comfortably.

  Mid-shift (T+90, ~08:30), actual demand jumps to roughly 12% above what
  the planning screen's forecast showed for that hour — a cold snap the
  forecast didn't catch — and holds there for the rest of the shift. This
  is the lesson made visceral: the planning screen cannot see everything,
  and a schedule with no slack in it means AUTO alone cannot keep frequency
  nominal once reality diverges from forecast. The fix is exactly Shift
  1-3's muscle memory — raise a unit's output by hand — except now it
  means deliberately pulling that unit out of AUTO to do it. Hydro
  (BATH-1/2, PIKE-1/2, ASHC-1/2/3) is the fast lever, per Shift 3's
  regulation-margin lesson; coal (RIVE-1/2) barely moves in the time
  available.

  Demand is derived at load time from every LOAD bus's saved peak_load_mw
  in shift5.json, scaled by the campaign's shared DEMAND_PROFILE_NORMALISED
  curve (src/data/profiles.py), exactly as Shifts 1-4 — the Planning
  screen's own forecast is built from the same bottom-up figures, so
  in-shift demand and the number the player planned against start
  identical; only the scripted DEMAND_OVERRIDE at T+90 makes them diverge.

  Fenshaw (FENN) and Yewbarrow (YEWB) are both single-radial dead ends off
  Marchden (MARC — SUTT --{L29,L30}--> MARC --L03--> FENN, MARC --L31-->
  YEWB), the same weak-tie pattern Shift 4 already taught. Both carry an
  automatic shunt capacitor bank (SUBSTATION_TYPES below) that switches on
  its own as reactive demand climbs, holding both buses in the HEALTHY
  band unattended for the full shift — this shift's voltage lesson was
  taught explicitly in Shift 4, so here the fix is present but silent,
  not a puzzle to solve.

Grid: RIVE (slack, 400kV) --{L01}--> CLOV --{L02,L09}--> ASHC --{L04,L05}-->
      WREN --{L06,L10}--> OAKE, WREN --{L15,L16}--> GREY; CLOV --L11-->
      BATH --{L19,L21}--> NETT --{L20,L22}--> HOLL --{L12,L14}--> STAV;
      CLOV --{L18,L41}--> SUTT (wind, SUTT-1) --{L07,L08}--> RAVE,
      SUTT --{L29,L30}--> MARC --L03--> FENN, MARC --L31--> YEWB;
      RIVE --L23--> SHEL --L24--> WARR --L32--> CRAN --{L34,L35}--> WREN,
      WARR --L33--> PIKE --{L36,L37}--> UNDE --{L38,L39}--> FARL,
      UNDE --L40--> HAZE; NETT --{L25,L26}--> LARK --L27--> THOR,
      LARK --L28--> APPL (24 buses, 41 lines; units: RIVE-1, RIVE-2,
      RIVE-3 (spare, maintenance), BATH-1, BATH-2, PIKE-1, PIKE-2,
      SHEL-1, SHEL-2, ASHC-1, ASHC-2, ASHC-3, SUTT-1 (wind)). L41
      (CLOV<->SUTT) is a second parallel circuit alongside L18, giving
      Sutterleigh — and the Marchden/Fenshaw/Yewbarrow branch beyond it —
      a stronger tie back to the backbone than the single-circuit L18
      alone provided.

GRID_SOURCE below points this shift at the hand-authored Grid Designer grid
(assets/designer_grids/shift5.json) — see shift_01.py..shift_04.py for the
same pattern. USES_PLANNING routes the campaign through GameState.PLANNING
after the briefing, before real-time play — see gameplay/phase1.py and
display/planning.py.
"""

from __future__ import annotations


GRID_SOURCE: str = 'shift5'

USES_PLANNING: bool = True

SHIFT_DATE: str = 'THU 10 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

START_HOUR: float = 7.0

DURATION_HOURS: float = 4.0

HANDOVER_NOTES: tuple[str, ...] = (
    'Morning handover, ahead of the mid-morning ramp.',
    'Plan the day on the Planning screen before the shift starts.',
    'Riverside Coal Unit 3 (RIVE-3) on planned maintenance — unavailable.',
    'Every unit you schedule starts in AUTO, following your plan.',
    'AGC on.',
    'Sutterleigh Wind (SUTT-1) forecast is shown on the plan — not yours to schedule.',
)

# Fallback starting dispatch — seeds the Planning screen's flat 24h default
# before the player edits it (see gameplay/phase1.py::_default_init_schedule()).
# Roughly tracks the 07:00 forecast (~893 MW) with headroom held back on the
# fast hydro so an under-read plan still has somewhere to turn once demand
# jumps — the player is free to overwrite all of this in Planning.
INITIAL_SCHEDULE: dict[str, float] = {
    'RIVE-1': 270.0,   # Riverside Coal Unit 1
    'RIVE-2': 270.0,   # Riverside Coal Unit 2
    'BATH-1': 120.0,   # Batherton Hydro Unit 1 — headroom held back
    'BATH-2': 120.0,   # Batherton Hydro Unit 2 — headroom held back
    'PIKE-1': 60.0,    # Pikestead Hydro Unit 1 — headroom held back
    'PIKE-2': 60.0,    # Pikestead Hydro Unit 2 — headroom held back
    'SHEL-1': 200.0,   # Sheldwick CCGT Unit 1
    'ASHC-1': 25.0,    # Ashcombe Hydro Unit 1
    'ASHC-2': 25.0,    # Ashcombe Hydro Unit 2
}

# RIVE-3 is on maintenance — visible on canvas, cannot be started this
# shift. Its cold start (240 min) is longer than the shift itself: not a
# lever the player can pull mid-shift, deliberately.
MAINTENANCE_UNITS: set[str] = {'RIVE-3'}

MAINTENANCE_LINES: set[str] = set()

AGC_ENABLED: bool = True

# Per-bus substation type — drives reactive load (power factor) and which
# buses get an automatic shunt bank / the manual SVC (see
# GridSimulation.seed_default_reactive_devices()). FENN and YEWB are both
# single-radial dead ends off MARC and sag without support; both are
# INDUSTRIAL so each gets its own automatic shunt bank — confirmed
# empirically this alone holds both HEALTHY unattended for the full shift,
# no manual SVC or SHUNT_BANK_OVERRIDES needed. STAV/FARL/THOR mirror the
# substation_type already saved on these buses in shift5.json; YEWB is
# reclassified INDUSTRIAL here (shift5.json saves it MIXED, which was
# never deliberately tuned) specifically to fix its sag.
SUBSTATION_TYPES: dict[str, str] = {
    'FENN': 'INDUSTRIAL',   # dead-end spur off MARC — gets an auto shunt bank
    'YEWB': 'INDUSTRIAL',   # sibling dead-end spur off MARC — same fix
    'STAV': 'INDUSTRIAL',   # matches shift5.json's saved substation_type
    'FARL': 'INDUSTRIAL',   # matches shift5.json's saved substation_type
    'THOR': 'RESIDENTIAL',  # matches shift5.json's saved substation_type
    'GREY': 'MIXED',
    'OAKE': 'MIXED',
    'RAVE': 'MIXED',
    'APPL': 'MIXED',
    'HAZE': 'MIXED',
}


# ── Conditions (declarative — see src/data/shift_io.py for the schema) ────────

_RESERVE_THIN: dict = {
    'metric': 'SPINNING_RESERVE_MW', 'op': '<', 'value': 250.0,
}
_RESERVE_STILL_THIN: dict = {
    'metric': 'SPINNING_RESERVE_MW', 'op': '<', 'value': 200.0,
}
_RESERVE_RECOVERED: dict = {
    'metric': 'SPINNING_RESERVE_MW', 'op': '>=', 'value': 250.0,
}
_FREQ_LOW: dict = {
    'metric': 'FREQUENCY_HZ', 'op': '<', 'value': 49.85,
}


# ── Scripted events ────────────────────────────────────────────────────────────

SCRIPTED_EVENTS: list[dict] = [
    {
        'trigger_min': 0.0,
        'priority':    'TUTOR',
        'message':     'Real-time play begins. Every unit you scheduled is running in AUTO.',
        'detail':      ('The plan you confirmed is now live — each scheduled unit is '
                        'following its own hourly programme without you touching it. '
                        'Watch a unit\'s context panel: it shows AUTO in green. Select '
                        'any unit and change its target directly (type a number, Enter) '
                        'to take manual control of it — that drops it to MANUAL. Press M '
                        'to hand a MANUAL unit back to AUTO.'),
        'element':     None,
        'condition':   None,
    },
    {
        'trigger_min': 5.0,
        'priority':    'TUTOR',
        'message':     'Sutterleigh Wind (SUTT-1) is not on your plan — its output is forecast, not scheduled.',
        'detail':      ('SUTT-1 was shown on the Planning screen as a locked row: you '
                        'could see its forecast and count it toward covering demand, but '
                        'you could never set its output. Wind runs on its own from here, '
                        'same as every shift.'),
        'element':     'SUTT-1',
        'condition':   None,
    },
    {
        'trigger_min': 90.0,
        'priority':    'WARNING',
        'message':     'Demand has jumped well above this morning\'s forecast.',
        'detail':      ('Actual demand just stepped up past what the Planning screen '
                        'showed for this hour — the forecast did not see this coming. '
                        'AUTO units will keep following the plan you wrote, not this new '
                        'demand. If your plan left headroom, spinning reserve absorbs it. '
                        'If not, frequency will start to sag.'),
        'element':     None,
        'condition':   None,
        'action':      {
            'type': 'DEMAND_OVERRIDE',
            'schedule': {
                7.0:  893.2,
                8.0:  1108.8,
                9.0:  1414.3,
                10.0: 1501.0,
                11.0: 1370.6,
            },
        },
    },
    {
        'trigger_min': 95.0,
        'priority':    'WARNING',
        'message':     'Spinning reserve running thin.',
        'detail':      ('Reserve has dropped below a comfortable margin. If a hydro unit '
                        '(BATH, PIKE, ASHC) still has headroom, raise its target by hand — '
                        'that pulls it out of AUTO and gives you direct control while the '
                        'demand step holds.'),
        'element':     None,
        'condition':   _RESERVE_THIN,
    },
    {
        'trigger_min': 110.0,
        'priority':    'CRITICAL',
        'message':     'Reserve critically low and frequency sagging. Raise a fast unit now.',
        'detail':      ('Select a hydro unit with headroom left, type a higher MW target, '
                        'Enter. Hydro responds almost immediately — this is the same '
                        'lever Shift 1 taught, just reached through AUTO this time.'),
        'element':     None,
        'condition':   _RESERVE_STILL_THIN,
    },
    {
        'trigger_min': 115.0,
        'priority':    'CRITICAL',
        'message':     'Frequency below 49.85 Hz.',
        'detail':      ('Generation is falling behind actual demand. Raise a hydro unit\'s '
                        'target by hand without waiting for AGC alone to find the margin.'),
        'element':     None,
        'condition':   _FREQ_LOW,
    },
    {
        'trigger_min': 140.0,
        'priority':    'TUTOR',
        'message':     'Reserve recovered. A plan is a starting point, not the whole shift.',
        'detail':      ('Raising a unit by hand pulled it out of AUTO and covered what the '
                        'forecast missed. The plan gets the shift started on the right '
                        'footing; watching it and stepping in when reality diverges is '
                        'still the dispatcher\'s job — that does not go away.'),
        'element':     None,
        'condition':   _RESERVE_RECOVERED,
    },
]
