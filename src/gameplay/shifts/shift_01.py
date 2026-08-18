"""
src/gameplay/shifts/shift_01.py

Shift 1 scenario definition — "First Watch": the whole Phase 2 tutorial
arc as one continuous shift. AGC-first dispatch + spinning reserve, then
voltage/AVR + topology/N-1, then a closing beat — one shift, one
demand ramp, no mode switches.

Narrative:
  AGC is on from handover — explained immediately, not introduced
  mid-shift. Riverside Coal Unit 1 (RIVE-1) and Riverside Coal Unit 2
  (RIVE-2) both sit at their 105 MW technical minimum; Ashcombe Hydro
  Unit 1 (ASHC-1, 250 MW) is the only AGC-eligible unit on-line at
  handover — Holt Hydro (HOLT-1, 150 MW) starts OFFLINE. AGC only ever
  touches HYDRO/CCGT (ASHC-1, later HOLT-1) — COAL never moves on its
  own; RIVE-1/RIVE-2 only change because the player changes them.

  As the morning ramp climbs, ASHC-1 alone cannot cover the forecast
  peak (its 250 MW ceiling against a ~515 MW peak, with RIVE-1/RIVE-2
  fixed at their 210 MW combined floor) — confirmed via headless trace:
  a do-nothing player's ASHC-1 saturates at 250 MW around T+150 and
  frequency collapses to the 45 Hz floor by T+180. The player has two
  independent fixes, either is sufficient: raise RIVE-1's setpoint
  toward ~165 MW, or start Holt Hydro (a 5-minute cold start) to bring a
  second AGC-eligible unit online. A margin WARNING fires once ASHC-1
  crosses 200 MW (confirmed via trace: T+84 for a do-nothing player) and
  again once total spinning reserve drops under 430 MW (T+91) — genuine
  ongoing feedback on whether the player is on the correct path, not a
  single one-shot instruction.

  Starting Holt Hydro brings its own lesson: HOLT-1's AVR setpoint is
  pre-configured low (0.95 pu, the campaign floor) via
  INITIAL_VOLTAGE_SETPOINTS even though it starts OFFLINE — the setpoint
  is stored and takes effect the moment the unit comes online (see
  UnitModel.set_voltage_setpoint()'s state-independent behaviour, fixed
  this session — it previously silently no-op'd on an OFFLINE unit).
  Once started, Holt is absorbing reactive power rather than supplying
  it, and Fenwick (FENW), at the end of the Holt branch, sags into WATCH
  within minutes (confirmed: crosses 0.92 pu at T+95, five minutes after
  a T+90 start). The fix is the same AVR-setpoint lesson as before:
  raise Holt's setpoint (V key) toward 1.05 pu.

  Separately, a spare circuit (L09, parallel to L01, the only path from
  Riverside to Ashcombe and everything behind it) sits open at handover.
  Later, L01 trips. With L09 still open, the trip blacks out Ashcombe
  and every load behind it; with L09 already closed, flow shifts onto
  it immediately and the trip barely registers. Line charging (the
  Ferranti effect) means leaving L09 closed for the rest of the shift
  once the trip risk has passed carries a small ongoing voltage cost
  too, not just being narratively wasteful.

  Demand is derived at load time from all four LOAD buses (GREY, OAKE,
  RAVE, FENW — 620 MW combined peak) in tutorial.json, scaled by the
  campaign's shared DEMAND_PROFILE_NORMALISED curve. The 06:00-09:12
  played window (3.2 sim-hours = 8 real minutes at TIME_COMPRESSION=24)
  climbs 273 -> 515 MW.

Teaching goal: AGC handles small deviations automatically on fast-
response units and spends spinning reserve doing it — it has no concept
of "running low," so the dispatcher has to watch the margin and make the
big moves (raising a slow thermal unit, or starting a second fast unit)
by hand. Voltage cannot be moved across the network the way MW can — a
weak, remote bus can only be supported by generation local to it.
Redundancy that sits idle protects nothing, and leaving it closed
forever isn't free either.

Grid: RIVE (slack) --{L01,L09}--> ASHC --{L02,L03}--> GREY,
      ASHC --{L04,L05}--> OAKE, RIVE --L06--> SUTT --{L07,L08}--> RAVE,
      RIVE --L10--> HOLT --L11--> FENW
      (all 8 buses, 11 lines, 4 units — the full shared tutorial grid)

GRID_SOURCE below points this shift at the hand-authored Grid Designer
grid (assets/designer_grids/tutorial.json).
"""

from __future__ import annotations


GRID_SOURCE: str = 'tutorial'

SHIFT_DATE: str = 'MON 07 NOV 1994'

DIFFICULTY_LABEL: str = 'Tutorial'

START_HOUR: float = 6.0

DURATION_HOURS: float = 3.2

HANDOVER_NOTES: tuple[str, ...] = (
    'Morning handover from R. Ferris.',
    'Riverside Coal Unit 1 (RIVE-1) and Unit 2 (RIVE-2) on-line at their 105 MW minimum.',
    'Ashcombe Hydro Unit 1 (ASHC-1) on-line at 60 MW.',
    'Holt Hydro Unit 1 (HOLT-1) is OFFLINE — spare capacity if you need it.',
    'AGC on — it automatically corrects small frequency deviations on ASHC-1 (and Holt, once started).',
    'AGC never touches Riverside\'s coal units — those only move if you move them.',
    'Demand climbing fast through the morning ramp toward the forecast peak.',
    'A spare circuit (L09, parallel to L01) sits open at handover — yours to close.',
)

# Starting dispatch — units absent from this dict start OFFLINE.
INITIAL_SCHEDULE: dict[str, float] = {
    'RIVE-1': 105.0,   # Riverside Coal Unit 1 — technical minimum, manual/scheduled only
    'RIVE-2': 105.0,   # Riverside Coal Unit 2 — technical minimum, manual/scheduled only
    'ASHC-1': 60.0,    # Ashcombe Hydro Unit 1 — the only AGC-eligible unit on-line at handover
}

# Units on planned maintenance — visible on canvas but cannot be started.
MAINTENANCE_UNITS: set[str] = set()

# L09 is a spare circuit in parallel with L01 (RIVE -> ASHC) — the player
# may close it at any time via the C key / line context panel.
MAINTENANCE_LINES: set[str] = {'L09'}

AGC_ENABLED: bool = True

# DROOP_ENABLED not declared — defaults to False (constants.py). AGC alone
# handles fast correction on HYDRO/CCGT; droop's continuous non-ramp-
# limited re-anchoring of target_mw on every synchronous unit (including
# slow-ramping COAL) made a player's manual RIVE setpoint read as broken
# during playtesting, even though manual dispatch was mechanically
# unrestricted the whole time.

# Roughly doubles the alarm/crisis band (~+-0.4 Hz alert, +-1.0 Hz critical
# instead of the default +-0.2/+-0.5 Hz) — a first-time player needs more
# room to react manually than the standard shifts allow. F_MIN/F_MAX (the
# hard 45/55 Hz clamp) are not affected by this multiplier.
FREQ_TOLERANCE_MULT: float = 2.0

# Per-bus substation type — drives reactive load (power factor) and which
# buses get an automatic shunt bank.
SUBSTATION_TYPES: dict[str, str] = {
    'FENW': 'INDUSTRIAL',   # worst PF — heaviest Q draw, deepens the sag
    'GREY': 'MIXED',
    'OAKE': 'MIXED',
    'RAVE': 'RESIDENTIAL',  # best PF — stays healthy without intervention
}

# Fenwick's automatic shunt bank is deliberately undersized (1 of its
# normal 4 steps) — the campaign-default 4-step ceiling would fully
# self-heal the sag caused by Holt's low AVR setpoint before the player
# ever sees it.
SHUNT_BANK_OVERRIDES: dict[str, dict] = {
    'FENW': {'max_steps': 1, 'initial_step': 1, 'mvar_per_step': 10.0},
}

# Holt starts near its AVR floor rather than the campaign default
# (1.02 pu) even though it is OFFLINE at handover — the setpoint is
# stored and takes effect the moment the player starts it, so Fenwick
# sags immediately once Holt comes online rather than needing a second
# manual step.
INITIAL_VOLTAGE_SETPOINTS: dict[str, float] = {
    'HOLT-1': 0.95,
}


# ── Conditions (declarative — see src/data/shift_io.py for the schema) ────────

_ASHC1_ABOVE_200MW: dict = {
    'metric': 'UNIT_OUTPUT_MW', 'target': 'ASHC-1', 'op': '>', 'value': 200.0,
}
_RESERVE_LOW: dict = {
    'metric': 'SPINNING_RESERVE_MW', 'op': '<', 'value': 445.0,
}
_FENW_BELOW_WATCH: dict = {
    'metric': 'VOLTAGE_PU', 'target': 'FENW', 'op': '<', 'value': 0.92,
}
_FENW_IMPROVING: dict = {
    'metric': 'VOLTAGE_PU', 'target': 'FENW', 'op': '>=', 'value': 0.98,
}
_L09_STILL_OPEN: dict = {
    'metric': 'LINE_LOADING', 'target': 'L09', 'op': '<=', 'value': 0.0,
}
_L09_CLOSED: dict = {
    'metric': 'LINE_LOADING', 'target': 'L09', 'op': '>', 'value': 0.0,
}


SCRIPTED_EVENTS: list[dict] = [
    # ── Act 1: AGC + spinning reserve ──────────────────────────────────
    {
        'trigger_min': 0.0,
        'priority':    'TUTOR',
        'message':     'AGC is on. It only touches Ashcombe (and Holt, if started) — never Riverside.',
        'detail':      ('Automatic Generation Control is active from the start of this shift. '
                        'It automatically nudges fast-response units — Ashcombe Hydro (ASHC-1) '
                        'now, Holt Hydro (HOLT-1) if you bring it on-line — to correct small '
                        'frequency deviations. Riverside\'s coal units (RIVE-1, RIVE-2) never '
                        'move on their own; they only change when you set their target directly.'),
        'element':     'ASHC-1',
        'condition':   None,
    },
    {
        'trigger_min': 3.0,
        'priority':    'TUTOR',
        'message':     'Demand is forecast to peak around 515 MW this shift. Ashcombe alone tops out at 250.',
        'detail':      ('Riverside\'s two units are parked at their 105 MW minimum — a combined '
                        '210 MW floor that never moves on its own. Ashcombe can cover the rest '
                        'up to its 250 MW ceiling, but that is not enough for the forecast peak. '
                        'You will need to raise Riverside Unit 1 toward roughly 165 MW, or start '
                        'Holt Hydro, before Ashcombe runs out of room. Watch the reserve figure — '
                        'it will warn you as the margin tightens.'),
        'element':     'RIVE-1',
        'condition':   None,
    },
    {
        'trigger_min': 86.0,
        'priority':    'WARNING',
        'message':     'Ashcombe past 200 MW. Raise Riverside Unit 1 or start Holt now.',
        'detail':      ('Ashcombe is closing in on its 250 MW ceiling. Select RIVE-1, press G, '
                        'hold Up — coal ramps slowly (about 9 MW/min), so start now, not when '
                        'Ashcombe is already pinned. Starting Holt Hydro instead is a 5-minute '
                        'cold start and responds much faster once on-line.'),
        'element':     'RIVE-1',
        'condition':   _ASHC1_ABOVE_200MW,
    },
    {
        'trigger_min': 87.0,
        'priority':    'WARNING',
        'message':     'Spinning reserve tightening. Confirm you are covering the forecast peak.',
        'detail':      ('Reserve is the headroom left across every on-line unit — it is dropping '
                        'as Ashcombe climbs toward its ceiling. If you have not already started '
                        'raising Riverside Unit 1 or bringing Holt Hydro on-line, do it now.'),
        'element':     None,
        'condition':   _RESERVE_LOW,
    },
    # ── Act 2: voltage/AVR + topology/N-1 ──────────────────────────────
    {
        'trigger_min': 20.0,
        'priority':    'TUTOR',
        'message':     'L09 (Riverside-Ashcombe spare circuit) sitting open. Yours to close.',
        'detail':      ('L09 runs parallel to L01, the only line carrying power from Riverside '
                        'to Ashcombe — and from there to every load behind it, including the '
                        'Holt/Fenwick branch. It starts open. Nothing requires you to close it, '
                        'but if L01 is ever lost with L09 still open, everything downstream goes '
                        'dark. Close it via the line context panel whenever you choose.'),
        'element':     'L09',
        'condition':   None,
    },
    {
        'trigger_min': 96.0,
        'priority':    'WARNING',
        'message':     'Fenwick sagging now that Holt is on-line. Raise Holt\'s AVR setpoint.',
        'detail':      ('If you started Holt Hydro to help with reserve, its AVR setpoint starts '
                        'low — it is absorbing reactive power rather than supplying it, and '
                        'Fenwick, at the end of its branch, is sagging as a result. Select '
                        'HOLT-1, press V, then Up to raise its voltage setpoint toward 1.05 pu.'),
        'element':     'HOLT-1',
        'condition':   _FENW_BELOW_WATCH,
    },
    {
        'trigger_min': 115.0,
        'priority':    'TUTOR',
        'message':     'Fenwick recovering. Holt\'s setpoint is doing its job.',
        'detail':      ('Raising a nearby generator\'s AVR setpoint is the lever for supporting '
                        'a weak, remote bus — reactive power cannot be moved across the network '
                        'the way MW can.'),
        'element':     'FENW',
        'condition':   _FENW_IMPROVING,
    },
    {
        'trigger_min': 152.0,
        'priority':    'WARNING',
        'message':     'L01 fault. Line tripped — Riverside-Ashcombe link lost.',
        'detail':      (''),
        'element':     'L01',
        'condition':   None,
        'action':      {'type': 'LINE_OPEN', 'line': 'L01'},
    },
    {
        'trigger_min': 153.0,
        'priority':    'CRITICAL',
        'message':     'L09 was never closed. Ashcombe and every load behind it is dark.',
        'detail':      ('With L09 still open, losing L01 severed the only path from Riverside '
                        'to Ashcombe. Greymoor, Oakendale and the Holt/Fenwick branch have all '
                        'lost supply. Close L09 now to restore the link.'),
        'element':     'ASHC',
        'condition':   _L09_STILL_OPEN,
    },
    {
        'trigger_min': 153.0,
        'priority':    'TUTOR',
        'message':     'L01 lost, but L09 already carried the load. No interruption.',
        'detail':      ('Because L09 was closed ahead of time, flow shifted onto it the moment '
                        'L01 tripped — everything behind it stayed fed without interruption. '
                        'That is what an idle spare is for.'),
        'element':     'L09',
        'condition':   _L09_CLOSED,
    },
    # ── Close ───────────────────────────────────────────────────────────
    {
        'trigger_min': 180.0,
        'priority':    'TUTOR',
        'message':     'Approaching handover. Confirm every instrument is holding.',
        'detail':      ('The shift is nearly over. Frequency, spinning reserve, Fenwick\'s '
                        'voltage, and line loading should all be settled before you hand over.'),
        'element':     None,
        'condition':   None,
    },
]
