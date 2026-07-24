# Shift 4 Redesign Notes — voltage/reactive-power tutorial

Status: implemented (`src/gameplay/shifts/shift_04.py`), pending live
playtest tuning of exact `peak_load_mw` / event-trigger numbers.

## Context

Across several tuning passes, Shift 4 had been treated as a numbers
problem (STAV/FENN too severe, then too mild). The actual issue was
bigger: as originally built, the shift only exercised "nudge one SVC to
+50 MVAr once" — everything else the simulation supports for teaching
voltage/reactive power was absent. This was a scope/design problem, not a
tuning problem, requiring a structural rework of what the shift asks the
player to do.

## What the design docs say Shift 4 should be teaching

Per `VOLTAGE_REACTIVE_PLAN.md` (the authoritative design doc for this
system) and the live code:

**The game deliberately gives the player exactly two manual levers** —
this is a locked design decision, not a gap:
> "Manual player levers (the two things the operator actively works):
> generator voltage setpoints... and a manual continuous SVC/STATCOM..."

Automatic shunt banks and transformer taps are intentionally
player-invisible-as-controls ("player sees the result, does NOT
control"). Shift 4 already uses the correct two levers — the problem was
*how thin* each demonstration was, and one explicitly-designed teaching
moment that was never shown at all:

**Generator Q-exhaustion (PV→PQ conversion)** is explicitly called out in
the design doc as one of the most important phenomena to teach, and was
demonstrated by no shift in the entire campaign (confirmed by grepping
all of `shift_01.py`–`shift_10.py`). It is fully built and visible in the
UI (`src/display/context.py:177-216`): the unit context panel shows an
AVR setpoint field (editable), a "Voltage ctrl: PV/PQ" row (flips from
green PV to amber PQ the instant a generator's Q output hits its
`q_max_mvar`/`q_min_mvar` ceiling), and a "Q: output / reserve" row
(headroom to the limit). None of this machinery was exercised by Shift 4
before this redesign.

Line MVAr flows and numeric power-factor readouts are deliberately out of
scope (no such display fields exist anywhere; the design doc frames
reactive load as something the player *feels* through voltage sag, not
reads as a number) — not a gap, by design.

## Diagnosis: why the original shift felt thin

1. Only one lever was really exercised per bus — FENN's SVC once, STAV's
   Stagshaw setpoint once (both units, but functionally one action).
2. No generator was ever pushed to Q-exhaustion — Stagshaw's combined
   `q_max_mvar` (48 MVAr) was never approached.
3. No second round of pressure — demand profile peaked at 18:00 (the old
   `START_HOUR`) and eased from there, so once the player fixed each bus
   once, nothing else happened for the remaining ~3.5 hours.

## Redesign shape: two acts per bus

- **Act 1 (handover, first ~20-30 min):** same opening beats. STAV sags
  because Stagshaw's setpoints start at the 0.95 pu floor; FENN sags
  because its shunt bank is undersized. Player raises Stagshaw's
  setpoints and FENN's SVC.
- **Act 2 (mid-shift, as demand climbs toward its peak):** pressure
  continues past what Act 1's fixes cover. For STAV: Stagshaw reaches
  Q-exhaustion (PV→PQ flip) even with both setpoints at 1.05 pu — a new
  scripted TUTOR/WARNING/CRITICAL sequence calls this out explicitly,
  teaching the player to read the PV/PQ + Q-reserve rows rather than keep
  pressing the setpoint key. For FENN: a second (and possibly third) SVC
  raise is needed as pressure builds.
- **Resolution (final ~1 hour):** demand eases as the window passes its
  peak; both buses recover even if imperfectly managed, preserving the
  "act early, don't just wait" design intent.

## Key mechanism: moved the shift onto the rising part of the demand curve

`DEMAND_PROFILE_NORMALISED` (`src/data/profiles.py`) interpolates linearly
between whole-hour keys: `15:00=0.870, 16:00=0.910, 17:00=0.960,
18:00=1.000, 19:00=0.980, 20:00=0.930`. The shift originally ran
18:00-22:00 — entirely on the *falling* side of the curve (peak exactly
at handover) — which is why "wait for more load" never worked and every
fix only had to survive a fixed, one-time deficit.

**Changed `START_HOUR` from 18.0 to 16.0** (kept `DURATION_HOURS = 4.0`),
so the shift now plays 16:00-20:00: demand climbs 0.910 → 1.000 (peak, at
~2h in) → eases to 0.930 by shift end. This gives genuine organic
mid-shift demand growth for Act 2 to bite on, with zero new engine work
required.

**Engine capability confirmed for reference** (in case growth alone isn't
enough and a scripted contingency is wanted later): `SCRIPTED_EVENTS`
supports an `action` field executed by `_execute_action()`
(`simulation.py:1072-1086`) with existing types `LINE_OPEN`, `LINE_CLOSE`,
`UNIT_TRIP`, `UNIT_DERATE` (MW cap only) — precedent in
`shift_03.py:167,210`. There is **no** action type or mutator for reducing
a unit's `q_max_mvar` mid-shift — that would be new engine capability, not
just shift data. Not needed for this redesign since the `START_HOUR` move
achieves the Q-exhaustion beat organically.

## Why exact numbers were left as a starting point, not finalized

Two prior tuning rounds were each based on a hand-calculated B'⁻¹Q
estimate that missed real network effects (once underestimating support
and landing STAV in WARNING/collapse; once overestimating the fix and
landing both buses fully healthy with no stress at all). A sanity check
during this redesign found STAV's isolated reactive demand at its then-
current 225 MW (`225 × tan(acos(0.85)) ≈ 139 MVAr`) already far exceeds
Stagshaw's 48 MVAr combined ceiling — if Stagshaw had to cover that alone
it would already be Q-exhausted, which contradicted the last live
playtest (both buses healthy). This confirmed a large share of support
comes from the rest of the network in a way a 2-bus hand calculation
can't capture — so exact `peak_load_mw` values should be set empirically,
by playtesting with `DEBUG_SIMULATION` on, not by another hand estimate.

**Decision:** implement the structural change (time window, new Act 2
events, docstring rewrite) using the current `peak_load_mw` values (STAV
225, FENN 175) as a starting point, then tune from observed play.

## Implementation summary (`src/gameplay/shifts/shift_04.py`)

1. `START_HOUR: float = 18.0` → `16.0`.
2. `HANDOVER_NOTES` first line: "Evening handover." → "Afternoon
   handover, ahead of the evening peak."
3. Added Act 2 conditions (`_STAV_SAGGING_AGAIN`, `_STAV_HOLDING_ACT2`,
   `_FENN_SAGGING_AGAIN`, `_FENN_HOLDING_ACT2`) and six new
   `SCRIPTED_EVENTS` entries at `trigger_min` 130/135/145/150/150/190,
   covering FENN's second SVC-raise beat and STAV's Q-exhaustion beat
   (WARNING → CRITICAL → TUTOR-on-recovery pattern, matching the existing
   Act 1 structure).
4. Rewrote the docstring's Narrative and Teaching-goal sections to
   describe the two-act structure per bus and the new 16:00-20:00 window.
5. `MAINTENANCE_LINES` comment and other minor text adjusted for
   consistency.

No changes to `shift4.json`, `SUBSTATION_TYPES`, `SHUNT_BANK_OVERRIDES`
values, `INITIAL_VOLTAGE_SETPOINTS`, `INITIAL_SCHEDULE`,
`MAINTENANCE_UNITS`/`MAINTENANCE_LINES` membership.

## Outstanding: live playtest verification

- Confirm Act 1 still works: both STAV and FENN sag at handover; both
  fixes (Stagshaw setpoints, FENN's SVC) work as before.
- Confirm Act 2 actually triggers: does Stagshaw's combined Q output
  approach/hit 48 MVAr as demand climbs toward the 18:00 peak, flipping
  "Voltage ctrl" from PV to PQ? Does STAV dip again despite maxed
  setpoints? Does FENN need a second SVC raise?
- If Act 2 doesn't trigger with current `peak_load_mw` values, raise
  STAV/FENN's `peak_load_mw` (or adjust event trigger thresholds) based on
  what's actually observed — this is the expected next step, not a sign
  of a design error.
- Confirm the shift still ends recoverable by 20:00 even if the player
  never intervenes past Act 1.
- Confirm new event `trigger_min` values don't collide with or
  immediately follow the existing Act 1 events confusingly.
