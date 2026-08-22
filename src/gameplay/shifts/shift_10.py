"""
src/gameplay/shifts/shift_10.py

Shift 10 scenario definition — "The Cold Snap": the campaign finale storm,
rebuilt against the morning demand ramp.

Narrative:
  A hard overnight frost has pushed heating demand into the morning ramp
  earlier and harder than the forecast assumed. An electrical storm system
  is tracking in behind the cold front, expected to cross the
  Howegate/Galeholt/Sandmere corridor — the spine feeding every new
  renewable station added this expansion (Kelmore, Barleigh, Dunwich
  hydro; Cairnholt, Braeholt wind; Feldrise, Stanmere solar) — during the
  worst of the ramp, not after it. Two direct strikes are expected on that
  corridor's exposed circuits; the redundancy each corridor carries is
  exactly what lets the grid survive losing one circuit, not both, if the
  spare capacity elsewhere has already been brought on in time.

  This shift replaces the old overnight-downslope design entirely. That
  version ran through the demand curve's calm downslope, where automatic
  regulation alone could absorb the whole night — verified by headless
  trace, frequency stayed within 0.01 Hz of nominal for over five real
  minutes before anything required a decision. The morning ramp is the
  steepest, most sustained rise anywhere in DEMAND_PROFILE_NORMALISED
  (src/data/profiles.py) — over the shift's own window, demand climbs from
  ~1400 MW at handover to beyond 3200 MW by the ramp's peak, while wind
  output is falling (WIND_PROFILE_NORMALISED) and solar has barely begun
  (SOLAR_PROFILE_NORMALISED still near zero at handover) — nothing is
  covering that gap automatically. This is deliberately not a "one
  scripted crisis" shift: the ramp itself, unassisted, is the pressure,
  and the storm compounds it rather than being the whole story.

  Fleet and grid were also grown for this rebuild (see
  assets/designer_grids/shift10.json): Hartwell nuclear is now 2x1000MW
  (was 1x700MW), Brackby coal resized to 3x250MW (was 2x300MW) with a new
  sister station, Stourbrook (3x250MW, on its own 400kV bus off Midfield),
  and Ashgrove CCGT (2x400MW, unchanged) gained a sister station, Welbeck
  (2x400MW). Total anchor (firm) capacity: 5100 MW. Seven new small
  renewable stations (three hydro 30-50MW, two wind 35-45MW, both at
  220kV; two solar 15-18MW at 150kV) were added clustered on the storm
  corridor, replacing the old single large wind/solar stations entirely —
  Galeholt and Sandmere keep their buses and corridor role but no longer
  generate. Total nameplate ~5333 MW against ~4003 MW peak demand (75%),
  deliberately generous under calm conditions (matching how real grids
  carry reserve margin) but tight once the storm removes a meaningful
  slice of it mid-ramp — verified by trace: a player who fails to start
  Stourbrook (240-min cold start, effectively the whole ramp window) in
  time is left with only ~356 MW of margin at peak even before any storm
  event, and a single further large-unit loss during peak pushes that
  negative.

  Unit commitment is therefore the shift's central, immediate task, not a
  slow-burn lesson eased into over an act: Stourbrook's 240-minute cold
  start means the decision to start it has to be made at or near handover
  to matter at all — there is no "wait and see" once real-time play begins.
  That decision is now made explicitly in the Phase 1 planning screen
  (USES_PLANNING, below) before handover: the player lays out the full
  24-hour schedule against the actual load/renewable forecast, committing
  Stourbrook/Welbeck start times (or not) ahead of time, and Phase 2 plays
  out the consequences of that plan in real time. Welbeck's CCGT (60-min
  cold start) is the second lever, useful for closing whatever gap remains
  once the ramp is underway. Every other prior shift's "commitment plant,
  start it early or not at all" lesson is here taken to its limit: get it
  wrong in the plan and there is no recovering the lost capacity later in
  the shift.

  Reactive power/voltage is a real mechanic this time, not absent: several
  of the load buses behind the storm corridor and the grid's biggest
  substations (Carrow, Sedgemere, Portreath, Millbrook, Wreklow, Draymoor,
  Trussington) are INDUSTRIAL — their reactive draw scales directly with
  live MW demand (Q = P * tan(power-factor angle), see demand.py), so as
  the ramp climbs, voltage genuinely sags at these buses without the
  player ever touching a line. This is a deliberate use of an existing,
  previously idle mechanism (the decoupled voltage solver has no coupling
  to line loading at all — src/simulation/voltage.py, a documented,
  intentional approximation — so Q only ever moves if something explicitly
  forces it to; INDUSTRIAL load growth is that force here).

  The storm itself lands mid-ramp: two lightning strikes, each taking one
  circuit of a redundant 220kV pair (Howegate-Galeholt, then
  Galeholt-Sandmere) rather than blacking out the corridor outright — the
  point is congestion and risk on the surviving circuit, not an instant
  loss, and a NEW mechanic (LINE_RECLOSE_COOLDOWN_S_BY_DIFFICULTY, see
  constants.py) means neither strike can simply be switched back the
  instant it trips: a line can't be switched again until a real-seconds
  cooldown elapses, scaled by the trainee/standard/dispatcher difficulty
  selection (not a per-shift setting — every shift gets it automatically)
  — this shift is also this mechanic's first real use. One generation
  unit trip (a storm-adjacent coal fault,
  not nuclear — Hartwell is deliberately never put at risk this shift, the
  fixed "wall" every prior shift already established it to be) lands
  during the ramp's steepest stretch, when the margin from a slow start is
  already thinnest.

  A short LANDING_FREEZE_S window (5 real seconds, the constants.py
  default) holds the sim clock at handover before anything moves, purely
  so the player can read the handover notes and the Power Balance panel
  before the ramp starts — not an easing of the difficulty itself, which
  begins in earnest from the first tick that follows.

  Difficulty target (developer directive): brutal, with no eased-in
  opening stretch — only a well-prepared, attentive player should expect
  to finish with minimal alarms and no unsupplied load. A do-nothing
  player is expected to fail this shift; deliberately does NOT resemble
  earlier shifts' "quiet act, then one crisis" shape.
"""

from __future__ import annotations


GRID_SOURCE: str = 'shift10'

SHIFT_DATE: str = 'THU 8 FEB 1996'

DIFFICULTY_LABEL: str = 'Extreme'

START_HOUR: float = 5.0

DURATION_HOURS: float = 5.5

# Routes BRIEFING -> PLANNING (Phase 1 unit-commitment scheduling) before
# PLAYING — Stourbrook/Welbeck's start-or-not decision (see module
# docstring) is made here, against the full-day forecast, rather than
# implicitly at handover.
USES_PLANNING: bool = True

HANDOVER_NOTES: tuple[str, ...] = (
    'Hard overnight frost. Heating demand is already running ahead of the forecast '
    'ramp — check the load before you do anything else.',
    'Electrical storm tracking in behind the cold front. Expected to cross the '
    'Howegate/Galeholt/Sandmere corridor mid-morning — every new renewable station '
    'sits behind that corridor.',
    'Stourbrook (STOR) is cold. 240-minute start. If it is not started in the next '
    'few minutes, it will not be ready for the peak — there is no second chance on '
    'this one.',
    'Welbeck (WELB) is cold. 60-minute start — useful once the ramp is properly under way.',
    'Hartwell Nuclear is the wall this shift, same as always — it cannot help you either.',
    'Several substations behind the storm corridor and two of the grid\'s biggest '
    'loads are industrial-heavy. Watch voltage as demand climbs, not just frequency.',
    'A tripped line will not reclose instantly — switching gear needs time to reset '
    'before it can be operated again.',
)

# No hardcoded handover dispatch — this shift routes through Phase 1
# (USES_PLANNING, above) before real-time play begins, so the actual
# handover MW/online state for every unit comes entirely from whatever the
# player's confirmed plan holds at start_hour, not a shift-authored
# default. The Planning screen itself seeds blank (every dispatchable unit
# OFFLINE at 0 MW) rather than any per-shift starting point — see
# gameplay/phase1.py's _default_init_schedule().
MAINTENANCE_UNITS: set[str] = set()

MAINTENANCE_LINES: set[str] = set()

AGC_ENABLED: bool = True

# AGC eligibility (CCGT + HYDRO) is fixed campaign-wide — see
# AGC_ELIGIBLE_TYPES in constants.py; no longer a per-shift setting.
# Response speed is still tunable per shift, though: halved here so AGC
# alone can't out-pace the ramp even with both eligible types online.
AGC_SPEED_MULT: float = 0.5

# Line reclose cooldown (a line can't be switched again until it elapses,
# either direction, manual or automatic/scripted) is no longer a per-shift
# setting — it scales with the trainee/standard/dispatcher difficulty
# selection instead (LINE_RECLOSE_COOLDOWN_S_BY_DIFFICULTY, constants.py),
# same as DIFFICULTY_MULT. Every shift gets it automatically at whatever
# level the player chose; nothing to declare here.

# New mechanic (see constants.py) — real seconds the sim clock holds at
# T+0 before anything moves, purely so the player can read the handover
# and the Power Balance panel first. Kept at the constants.py default
# (5.0) — this is a UX courtesy, not a difficulty concession, so it is not
# lengthened just because this shift is hard.
LANDING_FREEZE_S: float = 5.0

# INDUSTRIAL substations behind the storm corridor (WREK, MILL, DRAY) and
# the grid's biggest loads elsewhere (CARR, SEDG, PORT, TRUS) draw
# reactive power proportional to their live MW demand — as the ramp
# climbs, voltage genuinely sags at these buses without any scripted
# event forcing it (see module docstring). Every other bus is MIXED.
SUBSTATION_TYPES: dict[str, str] = {
    'RUSH': 'MIXED', 'ELDB': 'MIXED', 'STOK': 'MIXED', 'WYLD': 'MIXED',
    'CARR': 'INDUSTRIAL', 'BLAK': 'MIXED', 'NORT': 'MIXED', 'SEDG': 'INDUSTRIAL',
    'AVEN': 'MIXED', 'PORT': 'INDUSTRIAL', 'MILL': 'INDUSTRIAL', 'GREN': 'MIXED',
    'HALE': 'MIXED', 'COMB': 'MIXED', 'LYDD': 'MIXED', 'WREK': 'INDUSTRIAL',
    'ODEN': 'MIXED', 'KELT': 'MIXED', 'FAWN': 'MIXED', 'DRAY': 'INDUSTRIAL',
    'ORME': 'MIXED', 'BECK': 'MIXED', 'TRUS': 'INDUSTRIAL',
}

# No non-default reactive targets at handover — every generator starts at
# 0.0 MVAr (direct-Q default).
INITIAL_Q_MVAR: dict[str, float] = {}


# ── Scripted events ────────────────────────────────────────────────────────────
#
# Cleared out while the grid itself is still being reworked — the storm/
# unit-commitment/voltage beats described in the module docstring above
# (Stourbrook's start-now-or-never window, the two lightning strikes on
# the Howegate-Galeholt/Galeholt-Sandmere corridors, the Brackby 2 trip,
# the reserve/frequency/voltage warnings through the peak) are the intended
# shape to rebuild once the grid settles — not abandoned, just paused.
SCRIPTED_EVENTS: list[dict] = []

WIN_CONDITIONS: list[dict] = [
    {'metric': 'FREQUENCY_HZ', 'op': '>=', 'value': 49.2},
    {'metric': 'FREQUENCY_HZ', 'op': '<=', 'value': 50.8},
]

# Any one holding (for its sustained_s) ends the shift as a loss. Frequency
# bounds cover both a stalled ramp (under-frequency, the shift's primary
# risk) and any overcorrection (over-frequency). Voltage entries cover the
# storm-corridor and biggest-load INDUSTRIAL buses specifically, since
# those are where this shift's reactive-power mechanic actually bites.
FAIL_CONDITIONS: list[dict] = [
    {'metric': 'FREQUENCY_HZ', 'op': '<', 'value': 47.5, 'sustained_s': 10.0,
     'message': 'Frequency collapse — protective systems isolated the network.'},
    {'metric': 'FREQUENCY_HZ', 'op': '>', 'value': 52.5, 'sustained_s': 10.0,
     'message': 'Over-frequency — protective systems isolated the network.'},
    {'metric': 'VOLTAGE_PU', 'target': 'PORT', 'op': '<', 'value': 0.55, 'sustained_s': 20.0,
     'message': 'Portreath voltage collapse — cascade uncontained.'},
    {'metric': 'VOLTAGE_PU', 'target': 'TRUS', 'op': '<', 'value': 0.55, 'sustained_s': 20.0,
     'message': 'Trussington voltage collapse — cascade uncontained.'},
]
