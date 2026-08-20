# SHIFT 10 — "THE BAD NIGHT" IMPLEMENTATION PLAN

**Date:** 2026-08-19
**Status:** Planned, not started. No code written.
**Source:** `FUN_FACTOR_BRAINSTORM.md` (2026-08-18), Build C — "The Bad Night" (§3.2)
**Decisions taken:** foundation-first sequencing; new ~30-bus grid (both confirmed by developer)

---

## Context

**The ask:** build the last shift of the campaign first, at maximum difficulty, with
enough grid, fleet and mechanics to find out what "The Bad Night" actually feels like.

**This is the right instinct.** It matches the brainstorm's own closing argument —
*"the resistance, the agency, and the scoring come first — then the content."*
Building the hardest shift first is a **vertical slice**: it forces every missing
mechanic to surface at once, against real content, instead of being speculated about.
It also avoids the trap the brainstorm explicitly warns against — authoring Shifts 6-9
in the current structure would produce "more of something that isn't yet fun."

**But codebase exploration found one blocking fact that reshapes the plan:**

> **GRIDCOM has no win conditions, no fail conditions, and no scoring beyond
> frequency-%.** `is_shift_complete()` (`src/simulation/simulation.py:600`) returns
> true when the clock runs out or a total blackout occurs. That is the entire outcome
> space. A grep for `win_condition|fail_condition|SCORING_HOOKS|objectives` across
> `src/` returns **zero matches**.

Consequence: **today a "hardest shift" can only be made *noisier*, not *stricter*.**
More events can be thrown at the player, but the game cannot express that they lost.
The grade (`src/main.py:1084-1091`) reads only frequency-in-bounds %, load-shed count,
and cascade count. Shift 4 is entirely a voltage shift and voltage does not affect its
result. The campaign-end grade is hardcoded `'A'` (`src/main.py:1103`).

So this plan builds Shift 10 in **two movements**: a thin mechanical foundation that
makes difficulty expressible at all, then the shift itself. The foundation is six
small items — mostly the brainstorm's own §4 "Foundation" list — and is the difference
between a slice that teaches us something and one that just makes noise.

---

## What already exists (verified — do not rebuild)

The expensive parts are done. Reuse these:

| Asset | Location | Note |
|---|---|---|
| Scripted event engine | `simulation.py:1312` `_process_scripted_events` | Works |
| Condition evaluator | `simulation.py:1246-1286` | 8 metrics incl. `VOLTAGE_PU` |
| **Action dispatcher** | `simulation.py:1288-1310` | `LINE_OPEN/CLOSE`, `UNIT_TRIP`, **`UNIT_DERATE`**, **`DEMAND_OVERRIDE`**, **`AGC_SET`** |
| Cascade / islanding | `src/simulation/cascade.py` | BFS islanding, overload timers, blackout zones — all real |
| Player line control | `simulation.py:699` `trip_line`, `:715` `close_line` | Bound to **T**/**C** (`main.py:938`). Deliberate islanding is *already possible* |
| Grid Designer | `src/display/designer.py` (1978 lines) | Visual topology editor |
| Shift Builder + AST writer | `src/data/shift_io.py:363-435` | Splices into `shift_NN.py`, preserves docstrings byte-for-byte |
| Reference grid | `src/assets/designer_grids/shift10.json` | 60 buses, 129 lines, 34 units, 4400 MW |

> **`AGC_SET` already existing is the single luckiest find.** Engine 2.10 ("sabotage
> the automation" — the authored AGC-failure crisis, which the brainstorm calls the
> way to get manual-control fun *without* the realism objection) is authorable
> **today, with zero new code**. It is the spine of this shift.

### What does NOT exist (corrections to the brainstorm's assumptions)

- **Pumped storage is not implemented — at all.** `set_pumped_storage_mode()` is
  literally `return False` (`simulation.py:696`); `reservoir_levels` and
  `pumped_storage_modes` are hardcoded `{}` (`simulation.py:1713-1714`); negative MW is
  structurally impossible (output clamped non-negative at `units.py:306,344,418,490`).
  `can_pump` is read only by serialisation code. `src/debug_scenario.py:55` states:
  *"reservoir_levels: placeholder — no-op until UnitModel gains set_reservoir_level()."*
  **Brainstorm §2.2 ("make pumped storage the star") is a ground-up feature build, not
  a content decision.** Deferred out of this slice.
- `campaign.py`, `scoring.py`, `debrief.py`, `phase2.py`, `autopilot.py`, and
  `src/simulation/events.py` are **0-byte files**. The state machine is an inline
  `if/elif` chain over a 17-member enum in `src/main.py`.
- **Conditions sample once at `trigger_min` and never re-arm** (`simulation.py:1319-1326`).
  If a condition is false at that instant, the event is marked fired and skipped
  forever. This is why `shift_04.py` needs 15 events and two byte-identical condition
  dicts. **Critical authoring constraint.**
- **No RNG is ever seeded.** `renewables.py:72` accepts an optional generator but
  `simulation.py:289` constructs `RenewablesModel(grid)` bare. **Runs are not
  reproducible**, so a hard shift cannot be fairly tuned or replayed. (`demand.py` has
  no RNG at all — demand is already deterministic.)
- **`SPEED_FAST`/`SPEED_VERY_FAST` are unreachable in `GameState.PLAYING`.** Only
  pause/normal are bound (`main.py:1017-1020`); the F1/F2/F3 block at `:1312-1317` is
  the *Shift Builder test session*, not campaign play. `SPEED_VERY_FAST` (10×) is bound
  to no key anywhere — dead constant.
- **Load shedding is entirely dead code.** `simulation.py:730` wraps `shed_load`, but
  `grep -rn "shed_load" src/main.py src/display/` returns **nothing** — no keybinding,
  no renderer handler, not in the event action dispatcher. `clear_shed`
  (`demand.py:205`) is not wrapped at all. **Consequence: `load_shed_events`, one of
  only three metrics the grade reads, is structurally always 0.** The grade really
  reads two numbers.
- **Overload is a severity-blind countdown, not a thermal state.** `cascade.py:140-151`
  hard-resets the timer to 0.0 the instant loading drops below 100%; a line at 101% and
  one at 180% trip on the same 720 s clock.
- **Min-up/min-down ARE enforced — but only in the Phase 1 planner**
  (`phase1.py:311-325`), never in real time. `constants.py:535-537` says so explicitly.
  The brainstorm's §1.4 claim that they are "never enforced" is wrong for the planner
  and right for the live shift.
- **`GAMEPLAY_REFERENCE.md` does not exist in the repo.** `GRIDCOM_ROADMAP_v2.md:1914`
  cites it for the Storm's eight scripted events. That spec is lost; the event design
  below is new work, not recovery.

---

## Decision: which grid?

`src/assets/designer_grids/shift10.json` exists (60 buses / 129 lines / 34 units /
4400 MW peak). **Do not adopt it as-is.** It is auto-generated and semantically
incoherent — the labels contradict the unit types:

```
WNCN-1/2/3    ("Cairn Wind")      -> unit_type HYDRO_ROR
WNBR-1        ("Brackley Wind")   -> unit_type SOLAR
KELM-1/KELD-1 ("Kelmore Hydro")   -> unit_type WIND
can_pump: []                       -> zero pumped-storage units
```

`GAMEPLAY_ANALYSIS.md:334,460` independently records the same conclusion and the prior
intent to rebuild rather than adopt, "possibly closer to 30 buses than 60."

**Decision (confirmed): author a new `shift10.json` in the Grid Designer at ~28-32
buses, seeded by copying `shift5.json` and growing it.** This follows brainstorm §2.1
("compress the fleet, not the grid" — rated ⭐⭐, *"the single most under-considered
idea in this document"*). A 60-bus board is more to **read**, not more to **decide**.
Keep the old file as the solver performance-ceiling fixture only.

Target fleet — ~10-12 units, each with a distinct personality:

| Role | Spec | Character |
|---|---|---|
| NUCLEAR ×1-2 | 700 MW, 1%/min, 480 min cold start | The wall you build around. Cannot help you. |
| COAL ×2 | 300 MW, 3%/min, 240 min cold start | Commitment. Start it early or not at all. |
| CCGT ×2-3 | 400 MW, 8%/min | The workhorse. |
| HYDRO ×3-4 | 65-250 MW, 100%/min | Instant, precious, finite. |
| WIND ×1 + SOLAR ×1 | non-dispatchable | The storm's victims. |

---

## Movement 1 — Foundation

**Confirmed: do this first, before any content. ~1-2 sessions.**

Each item is small and is a prerequisite for the shift being *tunable* rather than
merely noisy.

### F1 — Seeded RNG (reproducibility)
`renewables.py:72` already accepts `rng`. Thread a per-shift seed from
`_make_sim_and_renderer()` (`main.py:215-290`) through `GridSimulation` into
`RenewablesModel` (`simulation.py:289`, and the forecast instance at `:790`). Add
`SHIFT_RNG_SEED_BASE` to `constants.py`.
**Why first:** without it every playtest is a different grid — a hard shift cannot be
tuned, and replay/scoring are meaningless.

### F2 — Speed control in PLAYING
Bind `SPEED_SLOW/NORMAL/FAST/VERY_FAST` (`constants.py:409-413`) to keys `1-4` in the
`GameState.PLAYING` handler at `main.py:876`, mirroring the block at `main.py:1312-1317`.
`CLAUDE.md`'s input spec already documents `1/2/3/4` as the Phase 2 bindings — **this
is a spec-conformance fix, not a new feature.**
**Why:** a long shift at `TIME_COMPRESSION=24` is a 30-minute unskippable sit at a
fixed 1×. Unshippable for iteration or for players.

### F3 — Win/fail conditions *(the load-bearing item)*
Add two optional module constants, read by `loader.py` alongside the existing 17:

```python
WIN_CONDITIONS:  list[dict]   # all must hold at shift end
FAIL_CONDITIONS: list[dict]   # any one ends the shift immediately
```

Reuse the **existing** condition schema and evaluator verbatim
(`simulation.py:1246-1286`) — `{'metric', 'target', 'op', 'value'}`. Evaluate
`FAIL_CONDITIONS` each tick inside `is_shift_complete()` (`simulation.py:600`);
evaluate `WIN_CONDITIONS` once at shift end. Add a `sustained_s` key so *"hold X above
Y for N seconds"* is expressible — this also sidesteps the once-only sampling problem
for objectives.

Extend `CAMPAIGN_EDITABLE_FIELDS` (`shift_io.py:242-246`) so the Shift Builder can
round-trip them.
**Why:** this is the difference between a hard shift and a noisy one. Without it,
Shift 10 cannot be lost.

### F4 — Scoring that counts what the game teaches
Fill the 0-byte `src/gameplay/scoring.py` with a single `grade_shift(state) -> dict`.
Move the rubric out of its **two duplicated inline copies** (`main.py:157-165` and
`main.py:1084-1091` — retuning one today silently desyncs the other) and widen it past
frequency-only toward brainstorm §5.1's axes: **dispatch compliance / system security**
(drop the efficiency axis for now — no cost model exists anywhere). Include voltage,
max line loading, and unit trips — all already computed in `SimulationState` and
currently thrown away. Replace the hardcoded `grade='A'` at `main.py:1103`.

### F5 — Make load shedding exist at all
Bigger than the brainstorm assumed: shedding is not "one-way", it is **unreachable**.
`simulation.py:730` wraps `shed_load` but nothing calls it; `clear_shed`
(`demand.py:205`) has no wrapper. Needs:
- a `GridSimulation.clear_shed()` wrapper,
- `on_shed_load` / `on_clear_shed` renderer handlers (mirror `on_trip_line`,
  `renderer.py:370`),
- a keybinding acting on the selected bus,
- a `LOAD_SHED` action in `_execute_action` (`simulation.py:1288`) so the storm can
  shed autonomously.

**Why:** it is the player's only emergency tool and Act 4 needs it. It also un-breaks
the grade — `load_shed_events` currently *cannot* be non-zero, so one of three scored
metrics is inert.

### F6 — Severity-scaled overload accumulation *(~10 lines, recommended)*
`cascade.py:140-151` ticks a flat timer above 100% and **hard-resets to 0.0** below it.
Make the accumulation rate proportional to overload severity, and make the timer
*decay* rather than reset. Brainstorm §1.6 (thermal ratings, rated ⭐) in its cheapest
possible form, confined to one function.
**Why here:** Act 4 is a cascade fight. Today a line at 101% and one at 180% trip on
the same 720 s clock, so the player cannot triage. The countdown UI already exists
(`canvas.py:662-683`) and immediately becomes more meaningful.

### Explicitly deferred from this slice
P-Q coupling, ZIP load, fuel cost / merit order, full thermal line ratings, real-time
min-up/min-down enforcement, pumped storage, per-island frequency, reputation meter,
telemetry failures.

> **Note on P-Q coupling.** The brainstorm rates it the highest-value change in the
> game, and it is genuinely cheap — three read sites (`units.py:814,815,852`), since
> `voltage.py` merely consumes the limits. It is deferred here **only** because it
> changes tuning under the whole campaign, and Shift 10 is easier to tune against a
> stable baseline. Strong candidate for immediately after this slice.

---

## Movement 2 — Author Shift 10 "The Bad Night"

**Frame:** the roadmap already names Shift 10 *"The Storm"* (`GRIDCOM_ROADMAP_v2.md:1912`),
with the intro line at `:1732`:

> *"Storm system forecast from the west. Twelve hours. Everything you know. All at once."*

This matches brainstorm §2.7 (the weather front) exactly. Use it.

**Scale down from 12 h to ~5-6 h.** With F2 speed controls that is ~8-12 real minutes
at 3×.

### The four-act structure

Each act pairs an engine from the brainstorm with mechanics that exist after Movement 1.
All four are authorable with the current action set.

**Act 1 — Quiet (DREAD).**
Storm forecast in `HANDOVER_NOTES`, hours away. One or two lines start open in
`MAINTENANCE_LINES`; closing them early is cheap, later is impossible. Generalises the
L09 beat the brainstorm calls *"the best thing in the game."* Nothing announces it.
**One latent risk deliberately never fires** — per §3.2, that gap is what makes covering
a *bet* rather than a delayed instruction.

**Act 2 — The front arrives (TEMPO).**
Staggered `UNIT_DERATE` on wind as the front crosses; `DEMAND_OVERRIDE` steps demand up
behind it as temperature drops. Wind surges, then collapses. The player must
pre-position on slow plant — COAL at 3%/min cannot react, only anticipate (§2.3).

**Act 3 — AGC fails (AGENCY).**
`{'type': 'AGC_SET', 'enabled': False}` mid-storm, delivered as a teleprinter-style
in-fiction message (§4.4). **The player hand-flies frequency through the worst of it.**
This is Engine 2 delivered as an authored crisis (§2.10) — it sidesteps the realism
objection entirely, and it costs **zero new code**.

**Act 4 — The cascade (fightable boss, §2.4).**
A line trips under storm loading. Overload countdowns are already rendered
(`renderer.py:818`). The player can `trip_line` to deliberately island a region, or
shed load (now live and reversible via F5) and restore afterwards. `FAIL_CONDITIONS`
from F3 make this genuinely losable.

### Files to create / modify

| File | Change |
|---|---|
| `src/assets/designer_grids/shift10.json` | **Rebuild** ~28-32 buses via Grid Designer (seed from `shift5.json`) |
| `src/gameplay/shifts/shift_10.py` | Replace 9-line stub. ~350-400 lines, following `shift_04.py` / `shift_05.py` structure |
| `src/gameplay/scoring.py` | F4 — currently 0 bytes |
| `src/simulation/simulation.py` | F1 pass `rng`; F3 win/fail eval; F5 `clear_shed` wrapper + `LOAD_SHED` action |
| `src/simulation/cascade.py` | F6 — severity-scaled accumulation, `:140-151` only |
| `src/display/renderer.py` | F5 — shed/restore handlers (mirror `on_trip_line`, `:370`) |
| `src/gameplay/shifts/loader.py` | F3 — read the two new constants |
| `src/main.py` | F2 speed keys; F4 call scoring instead of the two inline rubrics; F5 keybinding |
| `src/simulation/constants.py` | New constants only (Rule 1) |
| `src/data/shift_io.py` | F3 — extend `CAMPAIGN_EDITABLE_FIELDS` |

### Authoring constraints to respect

- Constants only in `constants.py` (Rule 1); colours only in `palette.py` (Rule 2).
- `DIFFICULTY_LABEL` must **not** be `'Tutorial'` — everything through Shift 5
  currently is. Use `'Severe'` or similar.
- Demand is **never** hand-authored: it derives from each LOAD bus's `peak_load_mw` ×
  `DEMAND_PROFILE_NORMALISED` (`loader.py:95-104`). Shape it by editing bus loads in the
  grid file, or with `DEMAND_OVERRIDE` events.
- Conditions fire once at `trigger_min` and never re-arm — stagger near-duplicate events
  deliberately, exactly as `shift_04.py:188-223` does.
- **Do not save Shift 10's events through the Shift Builder EVENTS tab.** `_METRIC_CYCLE`
  omits `VOLTAGE_PU` and `_ACTION_TYPE_CYCLE` omits `UNIT_DERATE` / `DEMAND_OVERRIDE` /
  `AGC_SET` (`shift_builder.py:51-56`) — a round-trip would silently destroy exactly the
  actions this shift is built on. Hand-edit the file.

---

## Verification

**Per foundation item:**

- **F1** — run the same shift twice with a fixed seed; assert identical
  `frequency_in_bounds_pct` and renewable output traces.
- **F2** — in campaign PLAYING, press `1/2/3/4`; confirm the sim clock rate changes and
  the speed indicator updates.
- **F3** — a headless run that deliberately violates a `FAIL_CONDITION` must end early
  with the shift marked failed; a clean run must satisfy `WIN_CONDITIONS`.
- **F4** — `pytest` over `grade_shift()`: a voltage-collapse run and a line-overload run
  must both grade below a clean run. **Under today's rubric they grade identically —
  that regression test is the point.**
- **F5** — shed a bus from the UI; confirm demand drops **and `load_shed_events`
  increments from a real playthrough for the first time**; clear it, confirm demand
  restores.
- **F6** — a line at 180% must trip materially sooner than one at 101%; a line that dips
  below 100% briefly must retain accumulated time rather than resetting to zero.

**Whole slice:**

1. Headless full-shift run of Shift 10 (pattern: existing `scripts/verify_reaction_window.py`)
   — no exceptions, all four acts fire in order, tick time still < 5 ms.
2. `pytest` — the suite is currently 28/28 (plus one known pre-existing failure).
3. **Play it end to end at 3×.** Ctrl+T from the Shift Builder runs the real campaign
   bootstrap for a campaign shift.
4. **Play it again trying to lose** — confirm losing is possible and legible.
5. Update `STAGE_STATUS.md`: new stage row, validation history, next objective. Note its
   "What Is NOT Yet Built" section (`:1037-1050`) is **currently stale** — it claims
   `events.py` and all gameplay modules don't exist, which contradicts the Session 77
   log; correct this while there.

---

## The question this slice answers

> **Does the Act 3 AGC-failure stretch — hand-flying frequency through a storm — carry
> the shift?**

- **If yes**, Engine 2 (Agency) is the campaign's spine, and Shifts 6-9 escalate toward
  it: *"I can fly this thing."*
- **If instead the Act 1 latent-risk beat is what sticks**, Engine 3 (Dread) wins, and
  the campaign is quieter and more judgement-driven: *"I saw that coming."*

Build one shift, learn which, then author 6-9 pointed at the answer — rather than
committing to a fun model in the abstract.

---

## Risks

- **Movement 1 is real engineering, not content.** If it is skipped, Shift 10 will be
  noisy but unlosable and ungradeable, and will not answer the question above.
- **Grid rebuild is hand work.** The Grid Designer is good, but authoring ~30 buses plus
  a coherent fleet is a session on its own.
- **Voltage tuning is empirical, not derived.** `SHIFT4_VOLTAGE_INVESTIGATION.md`
  (313 lines) is the precedent — budget for it if the storm drives voltage hard.
- **Out-of-order content.** Shift 10 will assume mechanics that Shifts 6-9 were meant to
  teach. Acceptable for a vertical slice, but 6-9 must later be authored as the ramp
  *into* it, and Shift 10 revisited once they exist.
