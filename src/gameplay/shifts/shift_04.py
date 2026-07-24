"""
src/gameplay/shifts/shift_04.py

Shift 4 scenario definition — "Local Support": voltage and reactive power.

Narrative:
  Same Riverside/Ashcombe units as Shift 3 (RIVE-1, RIVE-2, ASHC-1), carried
  forward a day later — RIVE-2's cooling fault has been repaired overnight,
  so both Riverside units are back to full availability. AGC remains on.
  Bus voltage is live for the first time this shift — every substation now
  carries a real Voltage Stability Index, shown as a coloured ring on the
  canvas.

  Two new substations have gone into service and both start the shift
  sagging, though for different reasons — one from a lack of local reactive
  support, the other from a lack of any nearby generation at all:

  Both buses play out in two acts, driven by the same rising evening
  demand: an opening sag the player learns to fix, then continued load
  growth that pushes the same fix to its limit and asks the player to
  recognize that, not just repeat it.

  Stavely (STAV), reached via Hollowgate (HOLL) — a single weak circuit
  with no parallel backup to the main grid. A new peaking station, Stagshaw
  (STAG, two 50 MW hydro units), sits one hop further out beyond Hollowgate
  and is Stavely's only source of support. Both Stagshaw units' AVR
  setpoints start at 0.95 pu (the lowest the game allows) rather than the
  default 1.02 pu, so Stavely sags into the WATCH band from handover as
  evening load builds — Act 1's fix is to raise both Stagshaw units'
  setpoints (V key) toward their 1.05 pu ceiling, pushing reactive support
  into Stavely from its dedicated, sole local generation. As demand keeps
  climbing toward the 18:00 peak (Act 2), Stagshaw's combined reactive
  capacity (q_max_mvar) can run out even with both setpoints already at
  their ceiling — the unit context panel's "Voltage ctrl" row flips from
  PV to PQ, meaning Stagshaw can no longer hold its own voltage target,
  let alone spare more for Stavely. There is no further setpoint to raise
  at that point — the lesson is recognizing a generator has exhausted its
  reactive reserve, not continuing to press the same key.

  Fenshaw (FENN), off Sutterleigh (SUTT) — no generation anywhere nearby.
  Fenshaw carries an automatic shunt capacitor bank (industrial-type load,
  heaviest reactive draw), already at its single working step at handover —
  but that bank is deliberately undersized (capped at 1 of the normal 4
  steps) so it holds part of the sag but cannot clear the watch threshold on
  its own. Act 1's fix is the manual SVC ([,]/[.] keys) — the tool for a
  region with no generator to call on. As demand climbs into Act 2, the
  first SVC raise stops being enough and a second (sometimes a third) raise
  is needed to hold Fenshaw clear of the watch threshold, rather than one
  adjustment being the whole answer.

  Both problems present together, close to handover, and mirror the same
  dispatcher choice in parallel: support a sagging region from nearby
  generation if one exists; use a dedicated device where none does.
  Reactive power cannot be moved across the network the way MW can. Demand
  eases naturally after the evening peak, so even a player who never gets
  past Act 1 will see both buses recover on their own before shift end —
  the point is to act early and keep watching, not to fix it once and
  stop paying attention.

  Demand is derived at load time from GREY/OAKE/RAVE/FENN/STAV's saved
  peak_load_mw in shift4.json scaled by the campaign's shared
  DEMAND_PROFILE_NORMALISED curve (src/data/profiles.py) — not authored
  here. The 16:00-20:00 played window sits on the rising evening ramp
  (0.910 at 16:00 climbing to the daily peak of 1.000 at 18:00, then
  easing to 0.930 by 20:00), which is what drives Act 2's extra pressure
  and the later recovery — unlike a window that starts at the peak, this
  one gives genuine mid-shift demand growth for Act 2 to bite on.

  SUBSTATION_TYPES assigns Fenshaw INDUSTRIAL (worst power factor, heaviest
  Q draw — gets the automatic shunt bank and, per
  seed_default_reactive_devices's existing placement rule, the manual SVC
  too, since it is the alphabetically-first load bus with no on-bus
  generation), Ravensmere RESIDENTIAL (best power factor, a healthy contrast
  case never addressed this shift), Greymoor/Oakendale/Stavely MIXED
  (baseline — Stavely's sag comes from Stagshaw's low setpoints and the
  weak, unbacked circuit to Hollowgate, not from power factor).

Teaching goal: voltage cannot be moved across the network the way MW can —
a weak, remote bus can only be supported by something local. A nearby
generator's reactive reserve is one lever; a dedicated compensation device
is the other, for regions no generator can reach. Neither lever is
unlimited: a generator's reactive reserve can run out (PV→PQ), and a
device can need more than one adjustment as pressure builds — recognizing
a limit is as much the lesson as knowing which lever to reach for.

Grid: RIVE (slack) --{L01,L09}--> ASHC --{L04,L05}--> WREN --{L06,L10}--> OAKE,
      WREN --{L15,L16}--> GREY, STAG --L11--> HOLL --{L12,L14}--> STAV,
      RIVE --L02--> SUTT --{L07,L08}--> RAVE, SUTT --L03--> FENN
      (11 buses, 15 lines, 5 units: RIVE-1, RIVE-2, RIVE-3 (spare, offline),
      ASHC-1, STAG-1, STAG-2)

GRID_SOURCE below points this shift at the hand-authored Grid Designer grid
(assets/designer_grids/shift4.json), an expansion of shift3.json with five
new buses (FENN, STAV, STAG, WREN, HOLL) and six new lines (L10, L11, L12,
L14, L15, L16), and three new units (STAG-1, STAG-2, RIVE-3) — see
shift_02.py / shift_03.py for the same GRID_SOURCE pattern. Wrenfield
(WREN) is a plain redundant 150kV transmission bus carrying no load of its
own — pure topology reshaping how GREY/OAKE connect back to the main grid,
with no teaching role of its own this shift. Hollowgate (HOLL) is a
pass-through bus between Stagshaw and Stavely, carrying no load either —
Stavely's only route to the grid runs entirely through it and Stagshaw.
"""

from __future__ import annotations


GRID_SOURCE: str = 'shift4'

SHIFT_DATE: str = 'WED 09 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

START_HOUR: float = 16.0

DURATION_HOURS: float = 4.0

HANDOVER_NOTES: tuple[str, ...] = (
    'Afternoon handover, ahead of the evening peak.',
    'Riverside Coal Unit 1 (RIVE-1) on-line at 270 MW.',
    'Riverside Coal Unit 2 (RIVE-2) on-line at 290 MW — cooling fault repaired overnight.',
    'Ashcombe Hydro Unit 1 (ASHC-1) on-line at 230 MW.',
    'Stagshaw Hydro Unit 1 (STAG-1) on-line at 60 MW, AVR setpoint low at 0.95 pu.',
    'Stagshaw Hydro Unit 2 (STAG-2) on-line at 50 MW, AVR setpoint low at 0.95 pu.',
    'AGC on.',
    'Stavely (STAV) and Fenshaw (FENN) are new connections, both already sagging.',
    'Bus voltage is live from this shift. Watch the coloured ring on each substation.',
)

# Units on planned maintenance — visible on canvas but cannot be started.
MAINTENANCE_UNITS: set[str] = set()

# Lines that start the shift electrically open. None this shift — the
# redundancy lesson was Shift 3's; every line here starts closed.
MAINTENANCE_LINES: set[str] = set()

AGC_ENABLED: bool = True

# Starting dispatch — units absent from this dict start OFFLINE.
INITIAL_SCHEDULE: dict[str, float] = {
    'RIVE-1': 270.0,   # Riverside Coal Unit 1
    'RIVE-2': 290.0,   # Riverside Coal Unit 2 — cooling fault repaired overnight
    'ASHC-1': 230.0,   # Ashcombe Hydro Unit 1
    'STAG-1': 60.0,    # Stagshaw Hydro Unit 1 — new, supports Stavely locally
    #'STAG-2': 50.0,    # Stagshaw Hydro Unit 2 — new, supports Stavely locally
}

# Per-bus substation type — drives reactive load (power factor) and which
# buses get an automatic shunt bank / the manual SVC. Opt-in: shifts that
# omit this constant default to all-MIXED with no reactive devices at all
# (see gameplay/shifts/loader.py / main.py::_make_sim_and_renderer()).
SUBSTATION_TYPES: dict[str, str] = {
    'FENN': 'INDUSTRIAL',   # worst PF — heaviest Q draw, gets the auto shunt bank + manual SVC
    'GREY': 'MIXED',        # baseline, no special role this shift
    'OAKE': 'MIXED',        # baseline, no special role this shift
    'RAVE': 'RESIDENTIAL',  # best PF — stays healthy without intervention
    'STAV': 'MIXED',        # sags from Stagshaw's low setpoint + weak lines, not power factor
}

# Fenshaw's automatic shunt bank is deliberately undersized (1 of its normal
# 4 steps, and each step worth half the campaign default 50 MVAr), pre-engaged
# at that single step from handover — confirmed empirically that both default
# step sizing and the campaign-default 4-step ceiling fully self-heal any
# reachable sag within a few sim-minutes (leaving no real use for the manual
# SVC), and that starting the bank at step 0 produces a brief, unplayable
# near-blackout transient before it first switches. Pre-engaging it at
# handover reads as "the automatic has already been holding routine drift,"
# not a sudden fault; the smaller step size leaves a real gap only the
# manual SVC can close.
SHUNT_BANK_OVERRIDES: dict[str, dict] = {
    'FENN': {'max_steps': 1, 'initial_step': 1, 'mvar_per_step': 25.0},
}

# Both Stagshaw units start near their AVR floor rather than the campaign
# default (1.02 pu) — confirmed empirically that Stavely cannot be made to
# sag at all while its local generation holds a healthy default setpoint.
INITIAL_VOLTAGE_SETPOINTS: dict[str, float] = {
    'STAG-1': 0.95,
    'STAG-2': 0.95,
}


# ── Conditions (declarative — see src/data/shift_io.py for the schema) ────────

_STAV_BELOW_WATCH: dict = {
    'metric': 'VOLTAGE_PU', 'target': 'STAV', 'op': '<', 'value': 0.90,
}
_STAV_STILL_BELOW_WATCH: dict = {
    'metric': 'VOLTAGE_PU', 'target': 'STAV', 'op': '<', 'value': 0.90,
}
_STAV_RECOVERED: dict = {
    'metric': 'VOLTAGE_PU', 'target': 'STAV', 'op': '>=', 'value': 0.90,
}
_FENN_BELOW_WATCH: dict = {
    'metric': 'VOLTAGE_PU', 'target': 'FENN', 'op': '<', 'value': 0.90,
}
_FENN_STILL_BELOW_WATCH: dict = {
    'metric': 'VOLTAGE_PU', 'target': 'FENN', 'op': '<', 'value': 0.90,
}
_FENN_RECOVERED: dict = {
    'metric': 'VOLTAGE_PU', 'target': 'FENN', 'op': '>=', 'value': 0.90,
}

# Act 2 — second-round pressure as demand climbs toward the 18:00 peak.
# Same VOLTAGE_PU/bus checks as Act 1: a bus sagging again this late, after
# its Act 1 recovery event already fired, is the observable signature of
# "the fix that worked once is no longer enough" (Stagshaw's reactive
# reserve exhausted for STAV; the first SVC raise outgrown for FENN).
_STAV_SAGGING_AGAIN: dict = {
    'metric': 'VOLTAGE_PU', 'target': 'STAV', 'op': '<', 'value': 0.90,
}
_STAV_HOLDING_ACT2: dict = {
    'metric': 'VOLTAGE_PU', 'target': 'STAV', 'op': '>=', 'value': 0.90,
}
_FENN_SAGGING_AGAIN: dict = {
    'metric': 'VOLTAGE_PU', 'target': 'FENN', 'op': '<', 'value': 0.90,
}
_FENN_HOLDING_ACT2: dict = {
    'metric': 'VOLTAGE_PU', 'target': 'FENN', 'op': '>=', 'value': 0.90,
}


# ── Scripted events ────────────────────────────────────────────────────────────

SCRIPTED_EVENTS: list[dict] = [
    {
        'trigger_min': 0.0,
        'priority':    'TUTOR',
        'message':     'Bus voltage is live. Watch the coloured ring on each substation.',
        'detail':      ('Every bus on this grid now carries a real voltage, not just a '
                        'load and a flow. A coloured ring around a substation is its '
                        'Voltage Stability Index — green means healthy. Amber and red '
                        'mean a bus is sagging and needs support. Stavely and Fenshaw '
                        'are both already showing amber at handover.'),
        'element':     None,
        'condition':   None,
    },
    {
        'trigger_min': 10.0,
        'priority':    'TUTOR',
        'message':     'Stavely is sagging. Stagshaw can support it directly.',
        'detail':      ('Stagshaw was connected specifically to support Stavely, and both '
                        'STAG-1 and STAG-2\'s AVR setpoints are currently low. Select each '
                        'unit, press V, and enter a higher voltage setpoint — that pushes '
                        'reactive support into Stavely from its dedicated local generation. '
                        'Reactive power cannot travel far on its own; this is the first tool.'),
        'element':     'STAG-1',
        'condition':   None,
    },
    {
        'trigger_min': 15.0,
        'priority':    'TUTOR',
        'message':     'Fenshaw has no generator nearby. Its automatic shunt bank has a ceiling.',
        'detail':      ('Fenshaw carries an automatic capacitor bank that is already '
                        'holding routine drift — but it is small and cannot do more than '
                        'that alone. Fenshaw also carries a manual SVC. Select the bus '
                        'and use [,] and [.] to adjust its MVAr setpoint once the '
                        'automatic is no longer enough.'),
        'element':     'FENN',
        'condition':   None,
    },
    {
        'trigger_min': 30.0,
        'priority':    'WARNING',
        'message':     'Fenshaw voltage below 0.90 pu. The automatic shunt bank alone is not holding it.',
        'detail':      ('Fenshaw\'s automatic capacitor bank is at its ceiling. There is '
                        'no generator nearby to help. Bring the manual SVC up.'),
        'element':     'FENN',
        'condition':   _FENN_BELOW_WATCH,
    },
    {
        'trigger_min': 45.0,
        'priority':    'WARNING',
        'message':     'Stavely still below 0.90 pu.',
        'detail':      ('Stavely has not recovered. Raise Stagshaw\'s AVR setpoints — it '
                        'is the dedicated local source of support for this bus.'),
        'element':     'STAV',
        'condition':   _STAV_BELOW_WATCH,
    },
    {
        'trigger_min': 50.0,
        'priority':    'CRITICAL',
        'message':     'Fenshaw still sagging. The automatic bank is maxed — raise the SVC now.',
        'detail':      ('Nothing local is left to give unless the manual SVC is used. '
                        'Select Fenshaw and raise its SVC setpoint with [.].'),
        'element':     'FENN',
        'condition':   _FENN_STILL_BELOW_WATCH,
    },
    {
        'trigger_min': 50.0,
        'priority':    'TUTOR',
        'message':     'Fenshaw voltage holding. The SVC is doing the job the automatic could not finish.',
        'detail':      ('The automatic bank covers a small part of the routine drift; '
                        'the SVC covers what is left when demand outgrows it. That is '
                        'what local voltage support looks like when no generator is '
                        'close enough to help.'),
        'element':     'FENN',
        'condition':   _FENN_RECOVERED,
    },
    {
        'trigger_min': 80.0,
        'priority':    'CRITICAL',
        'message':     'Stavely still sagging. Stagshaw\'s setpoints have not been touched.',
        'detail':      ('Select STAG-1 and STAG-2, press V, and raise their voltage '
                        'setpoints. Stagshaw is the only lever that reaches Stavely.'),
        'element':     'STAV',
        'condition':   _STAV_STILL_BELOW_WATCH,
    },
    {
        'trigger_min': 80.0,
        'priority':    'TUTOR',
        'message':     'Stavely voltage holding. Stagshaw is supporting it directly.',
        'detail':      ('Raising Stagshaw\'s voltage setpoints pushed reactive power into '
                        'Stavely and held its voltage. That is local support from '
                        'generation — the first of two tools.'),
        'element':     'STAV',
        'condition':   _STAV_RECOVERED,
    },

    # ── Act 2: demand keeps climbing toward the 18:00 peak (minute 120) ────
    # Both fixes above can be outgrown — the lesson shifts from "which
    # lever" to "recognizing when a lever is spent."

    {
        'trigger_min': 130.0,
        'priority':    'WARNING',
        'message':     'Fenshaw sagging again. The earlier SVC setting is no longer enough.',
        'detail':      ('Demand has kept climbing toward the evening peak. The SVC '
                        'setpoint that held Fenshaw earlier is not doing the job any '
                        'more — raise it again with [.].'),
        'element':     'FENN',
        'condition':   _FENN_SAGGING_AGAIN,
    },
    {
        'trigger_min': 145.0,
        'priority':    'CRITICAL',
        'message':     'Fenshaw still sagging. Keep raising the SVC.',
        'detail':      ('One raise is not always enough as demand keeps building — '
                        'check Fenshaw\'s voltage again and continue raising the SVC '
                        'with [.] until it clears 0.90 pu.'),
        'element':     'FENN',
        'condition':   _FENN_SAGGING_AGAIN,
    },
    {
        'trigger_min': 150.0,
        'priority':    'TUTOR',
        'message':     'Fenshaw holding through the peak. That took more than one adjustment.',
        'detail':      ('The SVC has no fixed "done" setting — it has to be revisited '
                        'as the load it is compensating for changes. That is what '
                        'managing a device (rather than a generator) looks like.'),
        'element':     'FENN',
        'condition':   _FENN_HOLDING_ACT2,
    },
    {
        'trigger_min': 135.0,
        'priority':    'WARNING',
        'message':     'Stavely sagging again, even with Stagshaw\'s setpoints raised.',
        'detail':      ('Check Stagshaw\'s unit panel: if "Voltage ctrl" reads PQ instead '
                        'of PV, Stagshaw has run out of reactive reserve (Q) and can no '
                        'longer hold its own voltage target, let alone spare more for '
                        'Stavely. There is no further setpoint to raise — this is a '
                        'different kind of limit.'),
        'element':     'STAV',
        'condition':   _STAV_SAGGING_AGAIN,
    },
    {
        'trigger_min': 150.0,
        'priority':    'CRITICAL',
        'message':     'Stavely still sagging through the peak.',
        'detail':      ('If Stagshaw\'s setpoints are already at their 1.05 pu ceiling and '
                        'this is still happening, check the "Voltage ctrl" row — Stagshaw\'s '
                        'combined Q output has likely hit its limit and there is nothing '
                        'more to give locally. If the setpoints were never raised, that is '
                        'still the fix. Demand starts easing after 18:00 either way.'),
        'element':     'STAV',
        'condition':   _STAV_SAGGING_AGAIN,
    },
    {
        'trigger_min': 190.0,
        'priority':    'TUTOR',
        'message':     'Stavely recovering as demand eases past the peak.',
        'detail':      ('Stagshaw\'s reactive reserve is unchanged — the recovery is '
                        'coming from lower demand, not a new lever. Recognizing that a '
                        'generator has run out of reserve, rather than continuing to '
                        'press its setpoint, is the lesson this bus carries.'),
        'element':     'STAV',
        'condition':   _STAV_HOLDING_ACT2,
    },
]
