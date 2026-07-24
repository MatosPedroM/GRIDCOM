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
  sagging, though for different reasons — one whose reactive support comes
  from a generator sitting idle up the line, the other with no nearby
  generation at all:

  Both sag from handover and both must be acted on early. Stavely's fix
  (raising Batherton's AVR setpoint) holds through the evening peak once
  done — a single decisive action. Fenshaw's manual SVC, by contrast, has
  no fixed setting: as demand climbs toward the 18:00 peak the first SVC
  raise is outgrown and a second (sometimes a third) is needed, so its
  lesson has a genuine second act about revisiting a device rather than
  setting it once and walking away.

  Stavely (STAV), reached via Hollowgate (HOLL) — the end of a long feed
  off the main grid. Its reactive support comes from Batherton (BATH), a
  400 kV hydro station (BATH-1) that reaches Stavely through the
  Batherton → Nettlecross (NETT) → Hollowgate chain. Batherton's AVR
  setpoint starts at 0.95 pu (the lowest the game allows) rather than the
  default 1.02 pu, so from handover Batherton sits back — absorbing rather
  than supplying reactive power — and Stavely sags into the WATCH band as
  evening load builds. Act 1's fix is to raise Batherton's setpoint (V key)
  toward its 1.05 pu ceiling, which turns Batherton from absorbing to
  injecting and pushes reactive support down the chain into Stavely. This
  is the shift's core lesson: a weak, remote bus is held up by a generator
  elsewhere on the same local network, worked through its AVR setpoint.
  Batherton has ample reactive reserve at the low setpoint, so the effect
  is immediate and clearly visible on Stavely's ring the moment the
  setpoint is raised.

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
  (baseline — Stavely's sag comes from Batherton's low AVR setpoint and the
  long feed through Hollowgate, not from power factor).

Teaching goal: voltage cannot be moved across the network the way MW can —
a weak, remote bus can only be supported by something local. A generator
elsewhere on the same local network, worked through its AVR setpoint, is
one lever; a dedicated compensation device is the other, for regions no
generator can reach. The two levers mirror each other in parallel across
Stavely and Fenshaw, and both need to be acted on early rather than waited
out.

Grid: RIVE (slack) --{L01}--> CLOV --{L02,L09}--> ASHC --{L04,L05}--> WREN
      --{L06,L10}--> OAKE, WREN --{L15,L16}--> GREY;
      CLOV --L11--> BATH --{L19,L21}--> NETT --{L20,L22}--> HOLL
      --{L12,L14}--> STAV; CLOV --L18--> SUTT --{L07,L08}--> RAVE,
      SUTT --L03--> FENN (13 buses; units: RIVE-1, RIVE-2,
      RIVE-3 (spare, offline), ASHC-1, LOVE-1, BATH-1)

GRID_SOURCE below points this shift at the hand-authored Grid Designer grid
(assets/designer_grids/shift4.json), an expansion of shift3.json — see
shift_02.py / shift_03.py for the same GRID_SOURCE pattern. Batherton (BATH)
is a 400 kV hydro station whose reactive output reaches Stavely through the
Nettlecross (NETT) → Hollowgate (HOLL) chain; NETT and HOLL are
pass-through transmission buses carrying no load of their own. Wrenfield
(WREN) is a plain redundant 150kV transmission bus carrying no load either —
pure topology reshaping how GREY/OAKE connect back to the main grid, with
no teaching role of its own this shift.
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
    'Batherton Hydro Unit 1 (BATH-1) on-line at 200 MW, AVR setpoint low at 0.95 pu.',
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
    'BATH-1': 200.0,   # Batherton Hydro Unit 1 — supports Stavely via NETT/HOLL
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
    'STAV': 'MIXED',        # sags from Batherton's low AVR setpoint + long feed, not power factor
}

# Fenshaw's automatic shunt bank is deliberately undersized (1 of its normal
# 4 steps, worth 40 MVAr), pre-engaged at that single step from handover —
# confirmed empirically that the campaign-default 4-step ceiling fully
# self-heals any reachable sag within a few sim-minutes (leaving no real use
# for the manual SVC), and that starting the bank at step 0 produces a
# brief, unplayable near-blackout transient before it first switches.
# Pre-engaging it at handover reads as "the automatic has already been
# holding routine drift," not a sudden fault; the single capped step leaves
# a real gap only the manual SVC can close, while still being large enough
# that Fenshaw holds a recoverable WATCH rather than collapsing if the
# player never touches the SVC.
SHUNT_BANK_OVERRIDES: dict[str, dict] = {
    'FENN': {'max_steps': 1, 'initial_step': 1, 'mvar_per_step': 40.0},
}

# Batherton starts near its AVR floor rather than the campaign default
# (1.02 pu) — at the low setpoint it absorbs reactive power rather than
# supplying it, so Stavely sags into WATCH; confirmed empirically that
# Stavely cannot be made to sag at all while Batherton holds a healthy
# default setpoint. Raising it toward 1.05 flips Batherton to injecting and
# is what lifts Stavely back to healthy.
INITIAL_VOLTAGE_SETPOINTS: dict[str, float] = {
    'BATH-1': 0.95,
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

# Act 2 — continued pressure as demand climbs toward the 18:00 peak.
# Same VOLTAGE_PU/bus checks as Act 1. For FENN this is a genuine second
# act: the first SVC raise is outgrown and needs revisiting. For STAV the
# late-shift check simply catches a player who never raised Batherton's
# setpoint in Act 1 — the same one-time fix still applies.
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
        'message':     'Stavely is sagging. Batherton can support it from up the line.',
        'detail':      ('Batherton (BATH-1) feeds Stavely through Nettlecross and '
                        'Hollowgate, but its AVR setpoint is currently low, so it is '
                        'absorbing reactive power rather than supplying it. Select the '
                        'unit, press V, and enter a higher voltage setpoint — that flips '
                        'Batherton to injecting and pushes reactive support down the line '
                        'into Stavely. Reactive power cannot travel far on its own; this '
                        'is the first tool.'),
        'element':     'BATH-1',
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
        'detail':      ('Stavely has not recovered. Raise Batherton\'s AVR setpoint — it '
                        'is the source of reactive support for this bus.'),
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
        'message':     'Stavely still sagging. Batherton\'s setpoint has not been touched.',
        'detail':      ('Select BATH-1, press V, and raise its voltage setpoint toward '
                        '1.05 pu. Batherton is the lever that reaches Stavely.'),
        'element':     'STAV',
        'condition':   _STAV_STILL_BELOW_WATCH,
    },
    {
        'trigger_min': 80.0,
        'priority':    'TUTOR',
        'message':     'Stavely voltage holding. Batherton is supporting it from up the line.',
        'detail':      ('Raising Batherton\'s voltage setpoint flipped it to injecting '
                        'reactive power and lifted Stavely back to healthy. That is local '
                        'support from generation — the first of two tools.'),
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
        'message':     'Stavely sagging into the peak. Batherton\'s setpoint is still low.',
        'detail':      ('Demand has climbed toward the 18:00 peak and Stavely is still in '
                        'the watch band. Batherton has plenty of reactive reserve to give '
                        '— raise its AVR setpoint (select BATH-1, press V) and Stavely '
                        'will lift straight away.'),
        'element':     'STAV',
        'condition':   _STAV_SAGGING_AGAIN,
    },
    {
        'trigger_min': 150.0,
        'priority':    'CRITICAL',
        'message':     'Stavely still sagging through the peak. Raise Batherton now.',
        'detail':      ('Batherton is the lever for this bus and it has the reserve to '
                        'fix it — select BATH-1, press V, and raise its setpoint toward '
                        '1.05 pu. Demand starts easing after 18:00, but do not wait it '
                        'out: act on the setpoint.'),
        'element':     'STAV',
        'condition':   _STAV_SAGGING_AGAIN,
    },
    {
        'trigger_min': 190.0,
        'priority':    'TUTOR',
        'message':     'Stavely holding through the peak on Batherton\'s support.',
        'detail':      ('With Batherton\'s setpoint raised, Stavely rode through the '
                        'evening peak in the healthy band — reactive support from a '
                        'generator up the line, worked through its AVR setpoint, is the '
                        'first of this shift\'s two tools.'),
        'element':     'STAV',
        'condition':   _STAV_HOLDING_ACT2,
    },
]
