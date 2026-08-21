"""
src/gameplay/shifts/shift_10.py

Shift 10 scenario definition — "The Bad Night": the campaign finale storm.

Narrative:
  A storm system is forecast from the west, hours out at handover — enough
  warning to prepare, not enough to know exactly where it will bite. The
  shift runs overnight (20:00-05:00): demand starts near the evening peak
  and falls hard through the small hours, the way it always does, except
  tonight the falling demand and the storm's own effects both need active
  management, not just watching.

  Four acts, each pairing a different kind of pressure:

  Act 1 — Quiet. Nothing happens for the first stretch. The storm is named
  in the handover notes but nothing about it is scripted yet. One of the two
  parallel circuits between Midfield (MDFD) and Tarnwick (TARN) — the spine
  tie toward the storm-facing branch — starts the shift open for maintenance.
  Closing it costs nothing. Left open, it becomes the single point of
  failure behind the whole Galeholt/Sandmere/Portreath corridor exactly when
  the storm arrives. Nothing announces this; it is a bet, not an
  instruction, in the spirit of the L09 lesson from Shift 3. A second risk —
  Wyldmarsh (WYLD), a single-radial dead end off Clunwell — is named as
  vulnerable in the handover notes and never actually threatened this
  shift. It is a bet that never resolves, deliberately: not every named
  risk in a real shift pays off, and a dispatcher who spends their whole
  night watching Wyldmarsh has missed the real story.

  Also starting in Act 1, and running the whole night regardless of the
  storm: AGC on this shift is HYDRO-only and sluggish (AGC_ELIGIBLE_TYPES/
  AGC_SPEED_MULT below — both CCGT units are the player's job all night,
  never AGC's, and even hydro's regulation is slow). Demand is also
  falling from its evening peak (~1670 MW at handover) toward an overnight
  trough below 600 MW. Every dispatchable unit's technical minimum, plus
  Galeholt's non-curtailable wind, adds up to more than the trough — a
  do-nothing player will overshoot on generation and pin frequency high
  near the bottom of the night. The fix is ordinary unit commitment, not a
  storm response: take hydro units fully offline in turn as the night
  deepens (Merefield and Clunwell's four units are the right ones — small,
  fast to restart, no cold-start penalty), and bring them back before the
  storm needs them in Act 2-4. This is deliberately the same shape as the
  storm crisis to come: falling demand at night is not exciting, but
  ignoring it fails the shift just as surely — and a player who is already
  hand-flying Ashgrove's CCGT output all night (since it was never
  AGC-covered) is already practising Act 3's skill before Act 3 even
  starts.

  Act 2 — The front arrives. Galeholt Wind (GALE-1) surges then collapses
  as the front crosses, staged as two UNIT_DERATE actions rather than one
  cliff. Behind the front, temperature drops and demand ticks back up
  against its natural overnight decline — a DEMAND_OVERRIDE schedule fights
  the falling curve for a few hours rather than reinforcing it. Brackby's
  coal units (BRCK-1/2, 3%/min) cannot react fast enough to either move;
  covering this falls to whichever hydro is still online (already
  mid-management from Act 1) and to Ashgrove's CCGT, which the player has
  been hand-flying since handover.

  Act 3 — Regulation thins further. Mid-storm, an AGC_EXCLUDE_UNITS action
  takes two more hydro units (Merefield 2, Clunwell 1 — roughly half the
  remaining eligible hydro fleet by capacity) off the AGC bus permanently,
  delivered as a CRITICAL control-room message. This is not a fault or an
  on/off flip — AGC was never fully on this shift to begin with; Act 3 is
  the same AGC_ELIGIBLE_TYPES-narrowing mechanism used a second time,
  mid-shift, on named units rather than a whole type. From this point even
  less regulation stands between the player and the storm's swings. A
  do-nothing player drifts slowly toward a frequency collapse (confirmed
  via headless trace: roughly 30 real minutes from this beat to the hard
  clamp at 1x speed, driven by the same standing generation/demand
  mismatch Act 1 already put in play) — slow enough to be fair, fast
  enough to matter. The exclusion holds for the rest of the shift; nothing
  restores itself on the hardest night.

  Act 4 — The cascade. Storm loading pushes the Sandmere-Portreath corridor
  (L15) toward its rating; a scripted trip takes it out under load. Because
  Portreath (PORT) is fed only by that one line, tripping it blacks
  Portreath out immediately — there is no N-1 fix available here, only
  triage: shed load elsewhere to protect the rest of the corridor, or
  accept the loss and hold everything else. FAIL_CONDITIONS give this
  shift a real floor: a sustained frequency excursion (either direction —
  Act 1's oversupply risk and Act 3's thinner-regulation risk are
  symmetric) or a
  sustained voltage collapse at Portreath both end the shift as a loss.

Grid: MDFD (slack, 400kV) --{L01}--> HART (nuclear), MDFD --{L02}--> BRCK
      (coal); MDFD --L03--> ASHG (CCGT), MDFD --L04--> MERE (hydro),
      BRCK --L05--> FENM, HART --L06--> NORT; MDFD --{L07,L08}--> TARN
      (L08 starts open — Act 1's spare-circuit bet), TARN --L09--> FENM
      (backbone loop closure), TARN --L10--> HOWE --> {CLUN --> WYLD
      (single-radial dead end), GALE --> SAND --> PORT (storm corridor),
      MILL, WREK}; MERE/ASHG/BRCK/FENM each feed 2-5 further 150kV load
      buses. 28 buses, 30 lines, 11 units (HART-1 nuclear 700MW, BRCK-1/2
      coal 300MW each, ASHG-1/2 CCGT 400MW each, MERE-1/2 hydro 200MW each,
      CLUN-1 hydro 100MW, CLUN-2 hydro 65MW, GALE-1 wind 200MW, SAND-1
      solar 250MW — dormant this shift, night storm, no output regardless
      of Act 2's derate).

GRID_SOURCE below points this shift at the hand-authored Grid Designer grid
(assets/designer_grids/shift10.json), built fresh for this shift (not the
old 60-bus auto-generated file, which was semantically incoherent — see
SHIFT10_BAD_NIGHT_PLAN.md). Reactive power is direct-Q (F9, Session
2026-08-21) — INITIAL_Q_MVAR sets a unit's starting MVAr target, not an
AVR voltage setpoint; voltage is a consequence of dispatch here, not
something set directly.

Teaching goal: difficulty here is not one big crisis, it is three ordinary
pressures overlapping — falling overnight demand, a storm's weather
effects, and automation that was already thin before the storm and thins
further mid-shift — none of which is individually hard, and all of which
are quietly connected: the same unit-commitment discipline Act 1 asks for
is the discipline that keeps things manageable once Act 3 narrows
regulation further, and the spare circuit Act 1 either closes or doesn't
decides whether Act 4's line trip is a triage problem or a catastrophe.
This is the campaign's AGC difficulty curve at its endpoint — early
shifts lean on fast, broad automatic regulation to teach the game without
constant manual correction; here automation covers a fraction of the
fleet and responds slowly, so the player is doing real, continuous
correction all night, not reacting to one scripted event.
"""

from __future__ import annotations


GRID_SOURCE: str = 'shift10'

SHIFT_DATE: str = 'SAT 19 NOV 1994'

DIFFICULTY_LABEL: str = 'Severe'

START_HOUR: float = 20.0

DURATION_HOURS: float = 9.0

HANDOVER_NOTES: tuple[str, ...] = (
    'Storm system forecast from the west. Hours out. Track expected to cross the '
    'Galeholt/Sandmere corridor.',
    'Overnight demand will fall hard, as always — from tonight, unit commitment '
    'is your job, not the automation\'s.',
    'Tarnwick spare circuit (L08) is open for maintenance — closing it is your call.',
    'Wyldmarsh (WYLD) is a single-radial feed off Clunwell — noted, not urgent.',
    'AGC on, hydro only tonight and running slow — Ashgrove\'s CCGT is yours to fly by hand.',
    'Hartwell Nuclear (HART-1) is the wall tonight — it cannot help you either.',
    'Portreath (PORT) has no second feed. If Sandmere goes, Portreath goes with it.',
)

# Handover dispatch. HART-1 near its 300 MW floor (nuclear cannot help
# overnight — cold_start/min-up/min-down make it fixed for the whole
# shift). Both CCGT online to cover the ~1670 MW evening-peak handover
# demand; ASHG-2 is the first unit a responsive player should stop as
# demand falls (verified via headless trace — stopping it around T+100min
# gives it time to actually ramp down before the trough arrives, not just
# a target change). Hydro started near its ceiling deliberately, so it has
# real room to be walked DOWN through the night rather than up — the
# opposite of every earlier shift's "raise a unit" lesson.
INITIAL_SCHEDULE: dict[str, float] = {
    'HART-1': 350.0,   # Hartwell Nuclear — floor is 300, not much room either way
    'ASHG-1': 380.0,   # Ashgrove CCGT 1 — stays online, tracks the whole night
    'ASHG-2': 380.0,   # Ashgrove CCGT 2 — stop this one first as demand falls
    'MERE-1': 180.0,   # Merefield Hydro 1 — walk this DOWN overnight
    'MERE-2': 180.0,   # Merefield Hydro 2 — walk this DOWN overnight
    'CLUN-1': 90.0,    # Clunwell Hydro 1 — walk this DOWN overnight
    'CLUN-2': 55.0,    # Clunwell Hydro 2 — walk this DOWN overnight
    # BRCK-1/2 (coal) start OFFLINE — deliberately. 240 min cold start is
    # longer than most of the shift; they are not a lever here at all,
    # matching every prior shift's "commitment plant" lesson, taken to its
    # conclusion: sometimes the right call is to never touch it.
}

MAINTENANCE_UNITS: set[str] = set()

# The Tarnwick spare circuit starts open — Act 1's central bet. Closing it
# before the storm reaches the corridor is free; leaving it open turns
# Act 4's line trip from a triage problem into a total corridor blackout.
MAINTENANCE_LINES: set[str] = {'L08'}

AGC_ENABLED: bool = True

# Campaign-wide AGC difficulty curve, endpoint: only plain HYDRO responds
# automatically (both CCGT units and, once excluded, part of the hydro
# fleet too — see Act 3 below), and even that responds sluggishly. Verified
# via headless trace: a responsive player who hand-flies ASHG-1/ASHG-2
# continuously (not just during a bounded crisis window) alongside the same
# overnight unit-commitment discipline Act 1 already asks for still
# completes the shift; a do-nothing player still fails mid-storm. CCGT
# being off AGC for the WHOLE shift, not just Act 3, is the point — the
# player is doing real, continuous manual correction on it all night, not
# reacting to one scripted fault.
AGC_ELIGIBLE_TYPES: frozenset[str] = frozenset({'HYDRO'})
AGC_SPEED_MULT: float = 0.35

# Every bus needs an entry or it gets no reactive devices at all. PORT and
# WREK are INDUSTRIAL (heaviest reactive draw, matching the grid file's own
# saved substation_type — the storm corridor and its neighbour both sag
# hardest under load, which is the point of Act 4). Everything else MIXED.
SUBSTATION_TYPES: dict[str, str] = {
    'RUSH': 'MIXED', 'ELDB': 'MIXED', 'STOK': 'MIXED', 'WYLD': 'MIXED',
    'CARR': 'MIXED', 'BLAK': 'MIXED', 'NORT': 'MIXED', 'SEDG': 'MIXED',
    'AVEN': 'MIXED', 'PORT': 'INDUSTRIAL', 'MILL': 'MIXED', 'GREN': 'MIXED',
    'HALE': 'MIXED', 'COMB': 'MIXED', 'LYDD': 'MIXED', 'WREK': 'INDUSTRIAL',
    'ODEN': 'MIXED',
}

# No non-default reactive targets at handover — every generator starts at
# 0.0 MVAr (direct-Q default), consequence of dispatch rather than a
# player-facing puzzle until the storm makes voltage worth watching.
INITIAL_Q_MVAR: dict[str, float] = {}


# ── Conditions (declarative — see src/data/shift_io.py for the schema) ────────

_ASHG2_STILL_ONLINE: dict = {
    'metric': 'UNIT_ONLINE', 'target': 'ASHG-2', 'op': '==', 'value': 1.0,
}
_RESERVE_THIN: dict = {
    'metric': 'SPINNING_RESERVE_MW', 'op': '<', 'value': 300.0,
}
_FREQ_HIGH: dict = {
    'metric': 'FREQUENCY_HZ', 'op': '>', 'value': 50.3,
}
_FREQ_STILL_HIGH: dict = {
    'metric': 'FREQUENCY_HZ', 'op': '>', 'value': 50.6,
}
_FREQ_LOW_ACT3: dict = {
    'metric': 'FREQUENCY_HZ', 'op': '<', 'value': 49.7,
}
_L15_STILL_UP: dict = {
    'metric': 'LINE_LOADING', 'target': 'L15', 'op': '>', 'value': 0.0,
}


# ── Scripted events ────────────────────────────────────────────────────────────

SCRIPTED_EVENTS: list[dict] = [
    # ── Act 1 — Quiet (T+0 to ~T+120) ───────────────────────────────────
    {
        'trigger_min': 0.0,
        'priority':    'TUTOR',
        'message':     'Storm forecast from the west. Hours out — prepare, don\'t react yet.',
        'detail':      ('The Tarnwick spare circuit (L08) is open for maintenance. Closing '
                        'it now costs nothing. If the storm reaches the Galeholt/Sandmere '
                        'corridor and L08 is still open, the single remaining tie becomes '
                        'the whole corridor\'s weak point.'),
        'element':     'L08',
        'condition':   None,
    },
    {
        'trigger_min': 15.0,
        'priority':    'TUTOR',
        'message':     'Overnight demand will fall hard from here. That is your job tonight, not just the storm.',
        'detail':      ('System demand will drop from tonight\'s ~1670 MW peak toward under '
                        '600 MW by the small hours. Every unit\'s technical minimum plus '
                        'Galeholt\'s wind adds up to more than that trough. Start bringing '
                        'hydro units (Merefield, Clunwell) fully offline in turn as the '
                        'night deepens — not just down, off. Bring them back before the '
                        'storm needs them.'),
        'element':     None,
        'condition':   None,
    },
    {
        'trigger_min': 90.0,
        'priority':    'WARNING',
        'message':     'Ashgrove CCGT 2 has real room to come off for the night.',
        'detail':      ('Demand has fallen well off the evening peak. Ashgrove 2 (ASHG-2) '
                        'is the first unit worth stopping entirely — it restarts in an hour '
                        'if the storm needs it back, well inside this shift\'s window.'),
        'element':     'ASHG-2',
        'condition':   _ASHG2_STILL_ONLINE,
    },

    # ── Act 2 — The front arrives (~T+150 to ~T+300) ────────────────────
    {
        'trigger_min': 150.0,
        'priority':    'WARNING',
        'message':     'Storm front crossing Galeholt. Wind output about to swing hard.',
        'detail':      ('Galeholt Wind (GALE-1) will surge then collapse as the front '
                        'passes. Brackby\'s coal units are still cold — nothing here can '
                        'react fast except Ashgrove and hydro with headroom.'),
        'element':     'GALE-1',
        'condition':   None,
        'action':      {'type': 'UNIT_DERATE', 'unit': 'GALE-1', 'cap_mw': 150.0},
    },
    {
        'trigger_min': 180.0,
        'priority':    'CRITICAL',
        'message':     'Wind has collapsed behind the front.',
        'detail':      ('Galeholt\'s output has dropped hard and temperature is falling '
                        'behind the storm — demand will not keep falling naturally for a '
                        'while. Cover the gap with whatever fast plant you still have '
                        'online.'),
        'element':     'GALE-1',
        'condition':   None,
        'action':      {'type': 'UNIT_DERATE', 'unit': 'GALE-1', 'cap_mw': 30.0},
    },
    {
        'trigger_min': 182.0,
        'priority':    'WARNING',
        'message':     'Cold front behind the storm is pushing demand back up.',
        'detail':      ('Demand will hold above its natural overnight curve for the next '
                        'few hours as temperature drops. Whatever units you took offline '
                        'in Act 1, check whether they need to come back now.'),
        'element':     None,
        'condition':   None,
        'action':      {
            # Hours keep incrementing past 24 for the rest of the shift
            # (GridSimulation's sim_hour is start_hour + elapsed, never
            # wrapped back to 0-24) — 25.0-29.0 here mean 01:00-05:00, not
            # 1.0-5.0. Values hold the natural overnight decline (see
            # DEMAND_PROFILE_NORMALISED) rather than falling all the way to
            # its ~565-650 MW trough, matching the cold front keeping
            # demand up.
            'type': 'DEMAND_OVERRIDE',
            'schedule': {
                20.0: 1669.4, 21.0: 1543.7, 22.0: 1328.3, 23.0: 969.3,
                24.0: 900.0, 25.0: 880.0, 26.0: 850.0, 27.0: 820.0,
                28.0: 780.0, 29.0: 700.0,
            },
        },
    },
    {
        'trigger_min': 260.0,
        'priority':    'WARNING',
        'message':     'Spinning reserve running thin against the cold front.',
        'detail':      ('Reserve has dropped below a comfortable margin with the front '
                        'still holding demand up. If a hydro unit has headroom, raise it '
                        'now rather than waiting for AGC alone to find the margin.'),
        'element':     None,
        'condition':   _RESERVE_THIN,
    },

    # ── Act 3 — AGC thins further (~T+300 onward) ───────────────────────
    # Not a fault — AGC was never fully on this shift (AGC_ELIGIBLE_TYPES
    # above is HYDRO-only, CCGT has been the player's job all night). This
    # is the same mechanism used a second time: two of the four remaining
    # hydro units drop off the AGC bus too, permanently for the rest of the
    # shift — nothing "fixes itself" on the hardest night. Roughly halves
    # what little automatic regulation was left (MERE-2 + CLUN-1 are ~53%
    # of the eligible hydro fleet's rated capacity).
    {
        'trigger_min': 300.0,
        'priority':    'CRITICAL',
        'message':     'CONTROL ROOM: two units dropping off the regulation bus.',
        'detail':      ('"Merefield 2 and Clunwell 1 are coming off the AGC bus — leave '
                        'them there, we need the headroom on standby elsewhere." Whatever '
                        'regulation was covering the storm just got thinner. Manual control '
                        'on those two from here: W arms MW, Up/Down steps it; Q arms MVAr if '
                        'voltage needs it too.'),
        'element':     None,
        'condition':   None,
        'action':      {'type': 'AGC_EXCLUDE_UNITS', 'units': ['MERE-2', 'CLUN-1']},
    },
    {
        'trigger_min': 320.0,
        'priority':    'WARNING',
        'message':     'Frequency drifting high with regulation this thin.',
        'detail':      ('Standing generation is running ahead of demand and there is far '
                        'less automatic correction to absorb it now. Lower a unit\'s target '
                        'by hand — this is an oversupply problem, not a shortage.'),
        'element':     None,
        'condition':   _FREQ_HIGH,
    },
    {
        'trigger_min': 340.0,
        'priority':    'CRITICAL',
        'message':     'Frequency still climbing. Manual correction needed now.',
        'detail':      ('Select an online unit with room to come down, type a lower MW '
                        'target, Enter. Left alone this keeps climbing toward the hard '
                        'limit.'),
        'element':     None,
        'condition':   _FREQ_STILL_HIGH,
    },
    {
        'trigger_min': 400.0,
        'priority':    'WARNING',
        'message':     'Frequency sagging — reserve may be thin again.',
        'detail':      ('If the storm\'s demand step has outpaced your manual correction, '
                        'raise a fast unit\'s target by hand. Regulation is thinner than it '
                        'was — this is on you.'),
        'element':     None,
        'condition':   _FREQ_LOW_ACT3,
    },

    # ── Act 4 — The cascade (~T+430 onward) ─────────────────────────────
    {
        'trigger_min': 430.0,
        'priority':    'CRITICAL',
        'message':     'Sandmere-Portreath line (L15) trips under storm loading.',
        'detail':      ('Portreath has no second feed — this line going down blacks it out '
                        'immediately. There is no N-1 fix here, only triage: shed load '
                        'elsewhere to protect the rest of the corridor, or hold and accept '
                        'the loss. If L08 was ever closed, the rest of the corridor is far '
                        'more defensible than if it was not.'),
        'element':     'L15',
        'condition':   None,
        'action':      {'type': 'LINE_OPEN', 'line': 'L15'},
    },
    {
        'trigger_min': 450.0,
        'priority':    'WARNING',
        'message':     'Portreath still dark. Shed load nearby if the corridor is straining.',
        'detail':      ('H sheds one block at the selected substation, Shift+H restores it. '
                        'A deliberate, reversible cut beats an involuntary one.'),
        'element':     'PORT',
        'condition':   _L15_STILL_UP,
    },
]

WIN_CONDITIONS: list[dict] = [
    {'metric': 'FREQUENCY_HZ', 'op': '>=', 'value': 49.0},
    {'metric': 'FREQUENCY_HZ', 'op': '<=', 'value': 51.0},
]

# Any one holding (for its sustained_s) ends the shift as a loss. The
# frequency entries cover both Act 1's overnight-oversupply risk and Act 3's
# thinned-regulation risk — they are the same failure mode in both
# directions. The voltage entry covers Act 4's cascade: Portreath
# collapsing and staying collapsed, not a momentary dip during the trip
# itself.
FAIL_CONDITIONS: list[dict] = [
    {'metric': 'FREQUENCY_HZ', 'op': '<', 'value': 47.0, 'sustained_s': 10.0,
     'message': 'Frequency collapse — protective systems isolated the network.'},
    {'metric': 'FREQUENCY_HZ', 'op': '>', 'value': 53.0, 'sustained_s': 10.0,
     'message': 'Over-frequency — protective systems isolated the network.'},
    {'metric': 'VOLTAGE_PU', 'target': 'PORT', 'op': '<', 'value': 0.5, 'sustained_s': 20.0,
     'message': 'Portreath voltage collapse — cascade uncontained.'},
]
