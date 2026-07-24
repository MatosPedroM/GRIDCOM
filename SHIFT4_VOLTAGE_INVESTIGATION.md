# Shift 4 Voltage/Reactive Investigation — Session Report

Status: **unresolved**. Shift 4's two-act voltage/reactive redesign is
implemented but the Stavely (STAV) / Stagshaw (STAG) teaching mechanic
does not work on the current grid topology, for architectural reasons
found and confirmed this session. `shift4.json` was NOT modified as part
of this investigation — all testing was done via in-memory overrides in a
scratch driver script. Pick up from "Open next steps" below.

---

## 1. What was implemented and already committed to `shift_04.py`

The shift was restructured into a two-act tutorial (see
`SHIFT4_REDESIGN_NOTES.md` for the fuller writeup of this part):

- `START_HOUR` moved from 18.0 to **16.0** (`DURATION_HOURS` stays 4.0),
  so the shift plays 16:00-20:00 — on the *rising* part of
  `DEMAND_PROFILE_NORMALISED` (0.910→1.000→0.930) instead of starting at
  the daily peak and only falling. This gives genuine mid-shift demand
  growth for an "Act 2" beat to bite on, with no new engine capability
  needed.
- **Act 1** (existing, ~0-80 min): STAV sags because Stagshaw's AVR
  setpoints start at the game's floor (`GEN_VOLTAGE_SETPOINT_MIN_PU =
  0.95`, `constants.py:76`); the fix is raising STAG-1/STAG-2's setpoints
  toward the `GEN_VOLTAGE_SETPOINT_MAX_PU = 1.05` ceiling. FENN sags
  because its automatic shunt bank is deliberately undersized
  (`SHUNT_BANK_OVERRIDES` in `shift_04.py`); the fix is the manual SVC.
- **Act 2** (new, ~130-190 min): a second WARNING/CRITICAL/TUTOR event
  sequence for both buses, intended to demonstrate Stagshaw running out
  of reactive reserve entirely (PV→PQ) for STAV, and a second/third SVC
  raise being needed for FENN.

**This session's finding: Act 2 (and much of Act 1) for STAV does not
actually work** — see below. FENN's SVC mechanic was confirmed working
correctly throughout.

## 2. Tooling built this session

**`SIM_STATE_LOG`** — a new per-tick CSV logger, added specifically to
stop guessing at network behaviour by hand (two earlier tuning passes
this week were wrong when checked against real data).
- `src/simulation/constants.py`: `SIM_STATE_LOG: bool = False`,
  `SIM_STATE_LOG_PATH: str = 'logs/sim_state.csv'`.
- `src/simulation/simulation.py`: `_write_sim_state_log()` method
  (modeled on the existing `_write_agc_log()` CSV-writer pattern),
  called once per tick when `SIM_STATE_LOG` is true. Writes one row per
  tick with dynamic per-bus columns (`voltage_pu`, `vsi_tier`,
  `q_injection_mvar`, `shunt_step`, `shunt_mvar`, `svc_mvar`) and
  per-unit columns (`output_mw`, `target_mw`, `q_injection_mvar`,
  `v_setpoint_pu`, `bus_type` [PV/PQ], `q_reserve_mvar`), sourced from
  the same `SimulationState` snapshot the UI reads (`sim.get_state()`).
- A real bug was found and fixed here: the method had a leftover
  copy-pasted block from `_write_agc_log()` referencing
  `self._agc_log_file` (which is `None` when `AGC_LOG` is off), causing
  an `AttributeError` on every tick. Fixed; all 12 tests in
  `tests/test_voltage_reactive.py` still pass.

**Headless driver script** —
`shift4_headless_run.py` in the Claude scratchpad directory (not part of
the shipped codebase; a one-off diagnostic). Builds a real `GridSimulation`
for Shift 4 using the exact same construction sequence as
`main.py:218-267` (load `shift_04.py`'s config via `load_shift_config(4)`,
load the real `shift4.json` via `load_designer_grid_named`, seed reactive
devices, apply `SHUNT_BANK_OVERRIDES`/`INITIAL_VOLTAGE_SETPOINTS`), then
ticks it in a loop (`sim.tick(1.0)` per simulated second, no pygame
needed) while firing the manual-lever actions ( `set_generator_voltage_
setpoint`, `set_svc_setpoint`) at the times `SCRIPTED_EVENTS` implies a
player would act, and reports bus/unit state at each key `trigger_min`.

**Supports these env-var overrides, none of which touch real files** —
useful for resuming this investigation:
- `DEMAND_OVERRIDES="BUS=MW,BUS=MW"` — patches `peak_load_mw` on named
  buses and recomputes `substation_load_mw` the same way `loader.py` does.
- `LOVE1_TEST_MW=<mw>`, `STAG2_TEST_MW=<mw>` — dispatches these units
  from handover (both are OFFLINE in the real `INITIAL_SCHEDULE` today).
- `QMAX_OVERRIDES="UNIT=mvar,UNIT=mvar"` — patches a unit's `q_max_mvar`.
- `REACTANCE_OVERRIDES="LINE=x,LINE=x"` — patches a line's `reactance_pu`.
- `NEW_LINE="LABEL:FROM:TO:REACTANCE:RATING:KV"` — appends a brand-new
  `DesignerLine` to the in-memory grid before construction.
- `SETPOINT_OVERRIDES="UNIT=v_pu,UNIT=v_pu"` — forces a different initial
  AVR setpoint than `shift_04.py`'s `INITIAL_VOLTAGE_SETPOINTS`.

Run e.g.:
```
cd e:\Dropbox\GameDev\1.Projects\GRIDCOM
DEMAND_OVERRIDES="OAKE=100,FENN=125,STAV=300" LOVE1_TEST_MW=300 python <scratchpad>/shift4_headless_run.py
```
then read `logs/sim_state.csv` for the full per-tick trace, or the
script's own printed summary table.

## 3. The grid changed several times mid-session (by the developer)

`shift4.json` (untracked, not in git history) was edited directly by the
developer multiple times during this investigation. Current state as of
this report:
- **CLOV** (Cloverstead, 400kV, non-slack, no load) added between RIVE
  and ASHC/SUTT — replacing the old direct RIVE↔ASHC/RIVE↔SUTT lines with
  RIVE↔CLOV (L01) → CLOV↔ASHC (L02/L09 parallel) and CLOV↔SUTT (L18).
- **LOVE-1 / LOVE-2** added at CLOV: Cloverstead CCGT, 400MW rated,
  `q_max_mvar=180` each. `LOVE-1 in_service:true`, `LOVE-2 in_service:false`
  in the JSON — **note `in_service` has no effect on real campaign play**,
  only on the separate DESIGNER_TEST code path (`main.py:312,368`); real
  dispatch is controlled by `shift_04.py`'s `INITIAL_SCHEDULE`, which
  currently has **neither LOVE unit listed** (both start OFFLINE in real
  play and in the driver unless overridden).
- `shift_04.py`'s `INITIAL_SCHEDULE` has **`'STAG-2': 50.0` commented
  out** (line 144) — only STAG-1 is dispatched. `HANDOVER_NOTES` (line
  123) still claims STAG-2 is on-line — **stale, needs fixing regardless
  of what else changes**.
- Current `peak_load_mw` (last known): GREY 100, OAKE 200, RAVE 150,
  FENN 150, STAV 300 (has been raised and lowered several times this
  session — 300 is the value in the file as of this report).
- Lines L13/L17 (ASHC↔HOLL backup path) exist at a deliberately weak
  `reactance_pu=2.6445` each (170km) — added earlier in the week's work
  as a "very weak backup," per an earlier session.

## 4. Root cause chain (each step confirmed with `SIM_STATE_LOG` data, not hand math)

### 4.1 RIVE (slack bus) can never help — architectural, not a bug

`src/simulation/voltage.py:186-187`:
```python
for label, (v_target, q_max, q_min) in pv_buses.items():
    if label == self._slack_bus:
        continue
```
The slack bus is excluded from PV voltage correction (it's the fixed
voltage-magnitude/angle reference). Confirmed in every test this session:
RIVE-1/RIVE-2 sit at `q_injection_mvar=0.00` with 150 MVAr of reserve
each, unused, regardless of grid state. RIVE-3 similarly unused (also
`in_service:false`/uncommitted in `INITIAL_SCHEDULE` in the latest grid).

### 4.2 ASHC-1 (and now LOVE-1) end up permanently Q-exhausted from tick 0

With RIVE contributing nothing, **ASHC-1 (120 MVAr max)** was, in every
grid version before CLOV/LOVE-1 existed, the sole reactive source for
the entire downstream subnetwork (WREN/OAKE/GREY, SUTT/RAVE/FENN,
HOLL/STAG/STAV) — and was pegged at its ceiling (`bus_type=PQ`,
`q_reserve_mvar=0.00`) from tick 0 in every test, regardless of
`peak_load_mw` tuning.

Once LOVE-1 was added and dispatched (tested via `LOVE1_TEST_MW`),
**both ASHC-1 and LOVE-1 are typically pegged simultaneously** — the
combined reactive demand of the "background" network (GREY+OAKE+RAVE+FENN,
even excluding STAV) is large enough on its own to exhaust both, in most
of the demand configurations tested. A crude Q-budget calculation
(`Q = MW × tan(acos(PF))`, `PF_INDUSTRIAL=0.85`, `PF_MIXED=0.92`) is a
useful sanity check but **does not reliably predict the actual solved
voltage** — being Q-exhausted doesn't necessarily mean a bus sags; it
depends on the full B'⁻¹ network solve, not a scalar supply/demand
comparison. This was demonstrated directly: at OAKE=100/FENN=125/STAV=175
with LOVE-1 dispatched, both ASHC-1 and LOVE-1 were still pinned, yet
STAV sat comfortably HEALTHY (~0.93-0.96) the whole shift.

### 4.3 Demand-lowering DOES fix the "STAV collapses to 0.0" failure mode

At the grid state with STAG-2 offline and STAV=300 (no demand-lowering,
no LOVE-1 dispatched), the shift produced **a genuine, unrecoverable
voltage collapse**: STAV starts at WATCH (0.85 pu) at handover, crosses
into WARNING by minute 10, CRITICAL by minute 30, and hits literal
**0.0 pu (full local blackout) by minute 58 — never recovering for the
rest of the 4-hour shift**, even as demand eases post-peak. This is a
hard failure, not a recoverable tutorial sag.

Lowering demand (OAKE→100, FENN→125) and dispatching LOVE-1 (300MW)
reliably prevents this collapse — swept STAV from 175-350 MW with this
config and found STAV stays in a stable WATCH-tier band (never below
~0.85, never crossing into WARNING/CRITICAL) across the whole range.
**So the "no collapse" goal is solved and verified** — this part of the
fix is safe to apply whenever the rest is resolved.

### 4.4 But: Stagshaw's setpoint has NEVER produced an observable effect on STAV, in any configuration tested

This is the actual blocking problem. Checked tick-by-tick in multiple
configurations: STAG-1's setpoint jumping 0.95→1.05 at the scripted
Act-1 moment produces **bit-for-bit zero change** in STAV's voltage for
15+ ticks afterward, because STAG-1 is already `bus_type=PQ` (pinned at
its `q_max_mvar` ceiling) both before and after the setpoint change — a
PQ unit ignores its voltage-setpoint target entirely; it just outputs
whatever Q it can (its ceiling), so changing the target it's not
currently trying to reach does nothing.

**Confirmed STAG-1 is pinned regardless of STAV's demand level** — swept
STAV from 50 to 350 MW (with OAKE=100, FENN=125, LOVE-1 dispatched):
STAG-1 only shows real headroom (`bus_type=PV`, nonzero `q_reserve_mvar`)
at STAV=50-75 MW — but at that demand level **STAV itself sits at
1.00-1.005 pu, nowhere near sagging**. At STAV=100 MW and above, STAG-1
is fully pinned again. **There is no demand level where STAV visibly
sags AND Stagshaw still has spare capacity to respond with** — these two
conditions are mutually exclusive on this topology, because STAG and
STAV are electrically coupled through the same weak HOLL subnetwork:
whatever draws STAV's voltage down also exhausts Stagshaw at the same
instant, before the player can do anything.

**Also confirmed: raising STAG-1's `q_max_mvar` does not give it real
headroom either.** Swept 24→60→100→150 MVAr — at every level, STAG-1
injects *exactly* its new ceiling and remains `PQ` (zero reserve). It
never converges to some finite "satisfied" Q value below the cap; it
always wants more than whatever ceiling is given. STAV's voltage does
improve as the ceiling rises (since a bigger forced injection helps
regardless), but Stagshaw itself is never actually "done" — this is a
symptom of `voltage.py`'s single-pass linear PV correction
(`delta_q_pu = b_diag * v_error`, `voltage.py:198`) producing a runaway
estimate for a bus this electrically weak/remote, not a real physical
saturation.

**Also confirmed: strengthening L11 (STAG↔HOLL) doesn't help either.**
Swept `reactance_pu` from 0.5172 down to 0.04 (nearly shorted) — STAG-1
remained pinned at 24 MVAr throughout, and STAV barely moved. The real
constraint isn't L11's own strength — it's that STAV's own massive Q
draw pulls HOLL's voltage down hard (via L12/L14, which stay unchanged),
and that pull reaches STAG's bus too since they share HOLL as a common
node, regardless of how strong the STAG-HOLL leg itself is.

## 5. Attempted fix: decouple Stagshaw from STAV's shared weak node

**Hypothesis:** if Stagshaw's own bus voltage were anchored to the
strong backbone (ASHC/CLOV, where ASHC-1/LOVE-1 hold relatively healthy
voltage) instead of being governed by the same weak HOLL/STAV pocket, it
should retain real Q reserve — restoring the "raise the setpoint, watch
it help" lesson.

**Test 1 — strengthen the existing L13/L17 (ASHC↔HOLL) backup path:**
swept reactance 2.6445→1.0→0.5 pu. Did not decouple STAG at all — it
just made STAV healthier overall (both share HOLL, so strengthening any
path into HOLL helps both together, not STAG specifically). Ruled out.

**Test 2 — add a brand-new direct line from STAG to CLOV (or ASHC),
bypassing HOLL for STAG's own supply** (`NEW_LINE` override,
reactance tested at 0.15/0.3/0.6 pu): **found a real effect, but a
genuinely unstable one.** With this new tie:
- STAG-1's setpoint action, for the first time all session, produces a
  visible response: Q flips from -8 (absorbing, its `q_min`) to +24
  (injecting, its `q_max`) exactly when the setpoint rises, and STAV's
  voltage then climbs steadily afterward.
- **But the system goes unstable before the player even acts.** Traced
  tick-by-tick: STAV starts HEALTHY (0.92-0.93) at t=0, but around
  t≈1.7 minutes, STAG's own bus voltage — now pulled up by the strong new
  CLOV tie — overshoots *above* 1.0 pu, well past its 0.95 setpoint
  target. The correction logic responds by flipping STAG-1 to `q_min`
  (trying to absorb Q to pull its own voltage back down to 0.95), and
  that absorption drags STAV's voltage down hard. The game's
  collapse-acceleration mechanic (`simulation.py:_apply_collapse_
  acceleration`) then takes over: STAV free-falls to a full 0.0 pu
  blackout by minute 30-80 and stays there until ~minute 190 — regardless
  of the player's action at minute 10.
- **Confirmed this is not just about the 0.95 starting setpoint** — reran
  with STAG-1 forced to the healthy 1.02 default (`SETPOINT_OVERRIDES`)
  and the same instability occurred anyway.
- **Root cause of the instability:** giving STAG a second, comparably
  strong reactive path (the new CLOV tie) alongside its existing weak
  one (via HOLL/STAV) creates a bus with two competing pulls. The
  solver's single-pass linear correction — explicitly documented as
  "one iteration is sufficient for the decoupled approximation"
  (`voltage.py` comment near line 181) — cannot reconcile two
  conflicting strong influences on one bus; it produces a large,
  oscillating, wrong estimate rather than converging.

**Conclusion: the "add a new line to decouple STAG" approach, as tested,
trades one problem (STAG always pinned, setpoint is a no-op) for a worse
one (a genuinely unstable bus that blacks out on its own before the
player can act).** Not recommended to pursue further without also
addressing the single-pass correction's behavior on multi-path buses —
which is a simulation-engine change, not a shift-tuning change.

## 6. Open next steps (developer's call — not decided this session)

1. **Give STAV a device-based fix instead of a generator-based one** —
   drop the "nearby generator supports it" framing for STAV specifically,
   and give it a manual SVC (same mechanism already proven reliable for
   FENN) instead of relying on Stagshaw's setpoint. Stagshaw could remain
   in the grid narratively (a local station that also happens to sag
   with STAV — a legitimate, different lesson about generators too close
   to a heavy load) without being the fix mechanism.
2. **Search for a weaker (higher-reactance) new tie** between STAG and
   the backbone that gives *some* headroom without triggering the
   overshoot/instability — untested territory; the 3 reactance values
   tried (0.15/0.3/0.6 pu) all triggered it, and the pattern so far
   doesn't inspire confidence a stable middle ground exists, but it
   hasn't been exhaustively ruled out.
3. **Revisit whether STAG needs to be electrically coupled to STAV at
   all** — e.g., a redesigned topology where Stagshaw sits somewhere
   that is neither "sharing STAV's exact weak node" (today's problem)
   nor "freshly tied to a strong bus that creates a competing pull"
   (Section 5's problem), but something in between that a fresh topology
   sketch (rather than patching the existing HOLL arrangement) might
   find more easily than further reactance sweeps.
4. Regardless of which direction is chosen: `HANDOVER_NOTES` (line 123
   in `shift_04.py`) needs its stale STAG-2 claim fixed, and the
   docstring/`SCRIPTED_EVENTS` text will need updating to match whatever
   final mechanic is chosen (currently they describe "raise Stagshaw's
   setpoint" as the fix, which doesn't hold with any tested configuration
   so far).

## 7. Files touched this session (already committed to disk, not reverted)

- `src/simulation/constants.py` — added `SIM_STATE_LOG`,
  `SIM_STATE_LOG_PATH`.
- `src/simulation/simulation.py` — added `_write_sim_state_log()`, its
  state fields, the call site, and `__del__` cleanup; fixed the
  copy-paste bug described in Section 2.
- `src/gameplay/shifts/shift_04.py` — `START_HOUR` 18.0→16.0, new Act 2
  `SCRIPTED_EVENTS`/conditions, docstring rewritten for the two-act
  structure, `HANDOVER_NOTES` wording adjusted (STAG-2 line is now
  stale again after the developer's later `INITIAL_SCHEDULE` edit — see
  Section 3).
- `src/assets/designer_grids/shift4.json` — **not modified by me** at
  any point; all grid edits referenced in this report were made directly
  by the developer between rounds of headless verification.
- `SHIFT4_REDESIGN_NOTES.md` (project root) — written earlier this
  session, documents the two-act redesign in more narrative detail.
- This file (`SHIFT4_VOLTAGE_INVESTIGATION.md`) — this report.
