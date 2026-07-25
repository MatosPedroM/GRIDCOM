# GRIDCOM — Gameplayability Analysis

**Date:** 2026-07-25
**Basis:** Source code only (`src/simulation/`, `src/gameplay/`, `src/display/`, `src/data/`, `src/main.py`). Design and status documents were deliberately not consulted.
**Perspective:** Written from two seats — a game designer's, and a player's who has just finished all five playable shifts.

---

# PART I — WHAT THIS GAME ACTUALLY IS

## 1.1 The honest one-line description

> **GRIDCOM is a 1990s-terminal-aesthetic *observation* game about a power grid, which wants to be a real-time management game about a power grid.**

That gap is the whole story of this analysis. Everything below explains why the gap exists and how to close it — and the answer is not "more content".

## 1.2 What the code says the game is

Reading the code cold, without the design documents, a clear shape emerges:

**Genre:** Real-time systems-management / "competence fantasy" sim. The closest relatives are *Kerbal Space Program*'s mission control, *Papers, Please*'s procedural pressure, *Mini Metro*'s escalating load, and the specific niche of *"terminal games"* — *TIS-100*, *Duskers*, *Uplink*, *Signal Simulator*.

**Core fantasy:** You are the person who keeps the lights on. Nobody notices when you succeed. Everyone notices when you fail. The chair matters more than the person in it.

**Session shape:** Discrete "shifts". Briefing → (optionally) plan → real-time session → debrief → grade. This is a strong, professional structure — it mirrors an actual dispatcher's day and gives natural save points, natural difficulty gating and natural narrative beats.

**Verbs the player has** (7 grid-affecting, confirmed in `renderer.py`):

| Verb | Input | Domain |
|---|---|---|
| Set unit MW target | select → type digits → Enter | Active power |
| Start unit | `S` | Active power |
| Stop unit | `X` | Active power |
| Return unit to AUTO | `M` | Active power |
| Set AVR voltage setpoint | `V` → digits → Enter | Reactive power |
| Adjust SVC | `,` / `.` (±10 MVAr) | Reactive power |
| Trip / close line | `T` / `C` | Topology |

Plus non-grid verbs: acknowledge alarms, select/cycle, pause, toggle AGC, toggle view.

**That is a good verb set.** Seven verbs across three domains is plenty — *Into the Breach* ships with fewer. The problem is never the vocabulary. It is that the player is almost never given a reason or an opportunity to use it.

## 1.3 Key characteristics — the fingerprint of this project

**1. It is a genuinely good simulation.** DC load flow, decoupled voltage with PV→PQ conversion, inertia-weighted swing equation, BFS islanding, per-substation power factors driving reactive draw. It is honest, it is numpy-only, and it runs inside budget. This is the hardest part of the project and it is essentially done.

**2. It has world-class authoring tooling — disproportionately so.** The Grid Designer (`display/designer.py`, 1978 lines), Shift Builder (677 lines), designer I/O (560 lines) and — remarkably — an AST-based round-trip that writes mechanical constants *back into `shift_NN.py` source files* while byte-preserving docstrings, comments and line endings (`shift_io.py:208-408`). This is more infrastructure than most shipped indie games have.

**3. It has almost no game layer.** Five of seven `src/gameplay/` modules are 0 bytes:

```
src/gameplay/autopilot.py    0 bytes
src/gameplay/campaign.py     0 bytes
src/gameplay/debrief.py      0 bytes
src/gameplay/phase2.py       0 bytes
src/gameplay/scoring.py      0 bytes
src/simulation/events.py     0 bytes
src/gameplay/phase1.py       20,524 bytes   ← the only real one
```

**4. The aesthetic is committed and coherent.** Procedural drawing, no sprite sheets, Terminus/VGA fonts, colour-tiered readouts, blink conventions, 1994 framing, "Frequency nominal. For now." The visual identity is not a placeholder — it is a decision, and it is a good one.

**5. The project's centre of gravity is in the wrong place.** Roughly 4,000 lines of editor tooling against 0 lines of scoring, campaign and save/load. The project has been building the *factory* rather than the *product*.

## 1.4 The developer's own diagnosis, found in the source

Three comments in the code are more candid than most postmortems:

`shift_03.py:47-50` —
> *"INITIAL_SCHEDULE dispatches 545 MW against a 14:00 demand checkpoint of 425 MW — a ~120 MW oversupply at shift start... Not rebalanced here; flagged for a separate gameplay-balance pass."*

`shift_04.py:58-61` — concedes that after the demand peak eases,
> *"even a player who never gets past Act 1 will see both buses recover on their own before shift end."*

`shift_02.py:16-18` — documents that demand runs 348→356→352→344→340 MW against an initial 350 MW dispatch.

The developer already knows. These are not blind spots; they are deferred items. This report's contribution is mostly to argue that **one of the deferred items is load-bearing for all the others.**

---

# PART II — GAME MECHANICS AS IMPLEMENTED

## 2.1 The three mechanical pillars

### Pillar 1 — Frequency / active power (the intended core)

The loop is: demand moves → generation doesn't → imbalance → frequency drifts → player and/or AGC dispatch MW → frequency returns.

Implemented: swing equation with inertia weighting (`frequency.py:121-126`), per-type ramp rates and cold starts, PID AGC on HYDRO+CCGT (`simulation.py:865`), AUTO/MANUAL dispatch modes, hourly plan execution.

**Status: mechanically present, experientially broken.** See §3.1 — the timescale makes it unplayable rather than merely hard.

### Pillar 2 — Voltage / reactive power (the intended second act)

The loop is: industrial buses draw reactive power at PF 0.85 → voltage sags locally → player raises AVR setpoints or SVC output → voltage recovers.

Implemented: decoupled `ΔV = B'⁻¹Q` solve, PV bus correction with Q-limit conversion, per-substation-type power factors (`PF_INDUSTRIAL 0.85` / `PF_MIXED 0.92` / `PF_RESIDENTIAL 0.97`), automatic shunt banks, one manual SVC, generator AVR setpoints, VSI tiers and halo rendering.

*Precision on "decoupled", because it is easy to overstate:* the PV correction at [voltage.py:190-230](src/simulation/voltage.py#L190) iterates to a bounded fixed point with sticky PV→PQ conversion at Q limits. **That is real reactive behaviour with real gameplay consequence** — a generator hitting `q_max` genuinely stops holding its bus. What is absent is narrower than "no reactive/active coupling": there is **no coupling between the two solvers** (voltage does not affect MW flows, and MW flows do not affect voltage), and **no reactive losses** (`I²X`), so reactive support is attenuated by distance through `B'` but never *consumed* by it. Part VIII addresses both.

**Status: the physics is there; the *agency* is not.** One SVC per grid, read-only shunts, and a collapse curve that is a cliff rather than a slope.

### Pillar 3 — Topology / contingency (the implied third act)

The loop is: a line trips → flow redistributes → another line overloads → 60 s timer → cascade.

Implemented: overload timers, sustained-overload trips, matrix rebuild and re-solve within the same tick, BFS island detection, blackout zones, manual trip/close.

**Status: this is the best-implemented pillar and the *least* used.** Exactly one shift (Shift 3, the L09 spare-circuit decision) builds a scenario on it — and it is the single best moment in the game.

## 2.2 The moment-to-moment loop, as a player experiences it

1. Read handover briefing (typewriter, ~15–30 s, skippable).
2. *(Shift 5 only)* Plan on a 24×12 grid — or press `Ctrl+A` and let the heuristic do it. `F10`.
3. Land in PLAYING at 1×. A 4-sim-hour shift is **5 real minutes**. No fast-forward.
4. Wait for a `TUTOR`/`WARNING` alarm that names the element *and the exact key to press*.
5. Tab or click the element. Press the key, or type the number and Enter.
6. Wait ~2–4 real minutes for the next beat.
7. Debrief typewriter → one of four grades → Enter → next shift.

**Measured decision density:**

| Shift | Real duration | Genuine decisions | Decisions/min |
|---|---|---|---|
| 1 | 3.75 min | 2–4 (ramp ASHC-1) | ~0.8 |
| 2 | 5.0 min | **0** (flat demand by design) | **0** |
| 3 | 5.0 min | 2 (close L09, raise RIVE-1) | 0.4 |
| 4 | 5.0 min | 3–4 (AVR, SVC, SVC again) | 0.7 |
| 5 | 5.0 min | ~1 in-shift, plus the plan | 0.2 |

**The player acts for roughly 5% of the runtime and watches for 95%.** And decision density *declines* from Shift 4 to Shift 5, despite the grid tripling in size.

## 2.3 What is measured versus what is scored

The full scoring system, verified at `main.py:150-157`:

```python
if freq_pct >= 95.0 and state.load_shed_events == 0 and state.cascade_events == 0:
    assessment = 'EXCELLENT'
elif freq_pct >= 80.0 and state.load_shed_events <= 1:
    assessment = 'SATISFACTORY'
elif freq_pct >= 60.0:
    assessment = 'MARGINAL'
else:
    assessment = 'UNSATISFACTORY'
```

| Metric | Tracked | Displayed | **Scored** |
|---|---|---|---|
| Frequency in ±0.2 Hz % | ✅ | ✅ | ✅ |
| Load shed events | ✅ | ✅ | ✅ |
| Cascade events | ✅ | ✅ | ✅ |
| **Minimum bus voltage** | ✅ | ✅ | ❌ |
| **Max line loading** | ✅ | ✅ | ❌ |
| Unit trips | ✅ | ✅ | ❌ |
| Alarm count | ✅ | ✅ | ❌ |
| Fuel cost / efficiency | ❌ | ❌ | ❌ |
| Plan quality | ❌ | ❌ | ❌ |
| Response time | ❌ | ❌ | ❌ |

**Shift 4 is entirely about voltage. Voltage does not affect the grade.** A player who nails the AVR and SVC work and one who ignores both receive identical assessments. This is the clearest single example of the game layer not having been built.

Campaign completion passes `grade='A'` as a hardcoded literal (`main.py:1062-1067`).

---

# PART III — WHY IT ISN'T FUN YET

## 3.1 The fundamental problem: consequences outrun the player

This is the root cause of nearly every fun deficit in the game.

**Finding A — frequency integrates in real time while everything else runs 48× compressed.**

`frequency.py:123`:
```python
self._frequency_hz += (df_dt * dt_sim_seconds) / TIME_COMPRESSION
```

`dt_sim_seconds` already carries the ×48 applied at `main.py:1023`. Dividing it out means frequency evolves at wall-clock rate while demand, ramps, and the clock run 48× faster.

With `S_BASE=1000`, `H_sys≈5`, a 100 MW imbalance yields `df_dt = 0.5 Hz per real second`. A 500 MW unit trip reaches `F_CRITICAL_LOW` in **~0.2 real seconds** and the 45 Hz clamp in **~2 real seconds**.

The player's corrective action is ramp-limited: a 300 MW CCGT at 8 %/min delivers **~19 MW per real second**.

> **The disturbance is roughly 100× faster than the response.**

**Finding B — `TRIP_DELAY_S = 60.0` is 60 *simulated* seconds ≈ 1.25 real seconds.**

`cascade.py:115-153` accumulates in sim seconds. From overload alarm to line trip the player has about **thirteen ticks**. The alarm text at `simulation.py:1276` reads *"Protection trips in 60s if sustained"* — which any player will read as a minute. It is wrong by 48×.

**The designer's read:** this single pair of constants converts an action game into a spectator game. Every dramatic beat resolves before the player's hand reaches the keyboard. The player is not *bad at the game* — the player is **not in the game**. And crucially, they will not diagnose this; they will conclude either "the game is unfair" or "nothing I do matters". Both are churn.

**The gamer's read:** *"I saw the alarm. I clicked the unit. By the time I'd typed '250' the frequency was already pinned and there was nothing on screen suggesting I could have done anything differently. So I stopped trying."*

## 3.2 No primary response, and an AGC that mathematically cannot settle

Real grids arrest a frequency excursion in **seconds** via governor droop, then restore it over **minutes** via AGC. GRIDCOM implements only the second half.

`DROOP_R = 0.04` is defined at `constants.py:122` and **never imported anywhere in the codebase**. `frequency.py:119-120` is explicit: *"Governor/droop response is handled externally."* Nothing arrests anything.

And AGC cannot finish the job either. `AGC_KI = 0.01` against `AGC_INTEGRAL_MAX = 5.0` caps the integral term at **0.05 MW**. Integral action is numerically absent — this is a **PD controller**, and a PD controller has no steady-state error rejection by construction. A persistent 200 MW gap parks frequency at roughly a 0.2 Hz offset, which is *exactly* `F_IN_BOUNDS_TOL` — the only thing scored.

`AGC_KD = 1000` then dominates, differentiating a signal already moving at 0.5 Hz/s. That is a twitchy, oscillation-prone configuration.

**Silent saturation:** `apply_agc_signal` returns `{}` when every AGC unit is at its limit (`units.py:595`) — with no alarm, no state flag, no indication. The player watches frequency drift with AGC displaying "ON" and no way to learn why. **This is the single most player-hostile behaviour in the codebase**, because it is a failure the game actively conceals.

## 3.3 Voltage is a cliff, not a fight

Verified at `simulation.py:1294-1317`:
```python
accel = severity ** 2 * V_COLLAPSE_GAIN       # gain 2.0
offset -= accel * dt_sim_seconds               # decay
offset = min(0.0, offset + V_COLLAPSE_RECOVERY_PU_S * dt_sim_seconds)   # recovery 0.02
```

At 0.75 pu: severity 0.667, accel ≈ 0.89 pu **per simulated second**. One normal-speed tick is 4.8 sim s, so the bus drops ~4.3 pu and floors at zero **in a single tick**. Recovery runs 44× slower at equal severity.

A good tension mechanic gives the player a losing battle they can *fight* — a slow slide they might arrest with the right action at the right moment. This gives them a binary: fine, then gone. There is no middle, and therefore no drama and no skill expression.

Worse, the collapse overlay feeds alarms, scoring and display but **not the solver** — so the most dramatic event in the game is cosmetic.

## 3.4 The player often has no lever at all

`seed_default_reactive_devices` (`simulation.py:596`) places **exactly one SVC**, at `sorted(load_bus_labels - gen_bus_labels)[0]` — the alphabetically first generation-free load bus. Shunt banks are explicitly automatic and read-only (`reactive_devices.py:40`). Transformer taps are retired. `set_unit_q_target` is overwritten by the PV correction reflected back in `_build_state`.

> **If a sagging bus has no online generator nearby and is not the one SVC bus, the player has no reactive lever whatsoever.**

The only remaining action is shedding load — and `demand.clear_shed` exists in `demand.py:205` but **is not exposed on `GridSimulation`**, so shedding is permanent. The one emergency tool in the game is a one-way door.

Being asked to solve a problem you have no tool for is the most demoralising state a game can put a player in. It is worse than losing.

## 3.5 You cannot fail, so nothing matters

`is_shift_complete()` (`simulation.py:561`):
```python
def is_shift_complete(self) -> bool:
    return self._sim_time_min >= self._duration_minutes
```

A clock check. Black out the entire national grid and the shift ends exactly as it would have. `blackout_zones` is tracked and rendered, and nothing in the game reacts to it beyond alarm text.

**No fail state means no stakes; no stakes means no tension; no tension means the 95% spent watching is dead air.** Tension in a management game is manufactured almost entirely by the credible threat of loss.

Compounding it: there is **no save/load anywhere**. `saves/` is empty, nothing in `src/` writes a save, and MAIN MENU → CONTINUE is a literal `pass` (`main.py:547`). A player who wants to improve a grade cannot replay a shift. A player who stops cannot resume.

## 3.6 Difficulty scale rises; difficulty pressure does not

Scale escalates genuinely: 3→4→6→13→25 buses, 1→2→3→4→12 dispatchable units, 100→1540 MW.

Pressure does not:

- Every shift is 3–4 sim hours at fixed 1× — about **5 real minutes**, every time.
- `DIFFICULTY_LABEL` is `'Tutorial'` for all five shifts, including Shift 5.
- Every problem is announced by name, with the fix key spelled out, roughly 10 sim-minutes before it can hurt.
- Shift 2's optimal play is genuinely **zero actions**.
- Shift 4's two problems self-resolve if ignored, by its own docstring.
- Shift 5 has *fewer* in-shift decisions than Shift 4.

The campaign teaches **breadth** (manual → two units → AGC + N-1 → voltage → planning) but never **depth**. The player is never asked to do a thing they already know how to do, faster, or under load, or with something else going wrong simultaneously. That second axis is where mastery — and therefore fun — actually lives.

And it stops at 5: `shift_06.py` through `shift_10.py` are 305-byte docstring stubs. Loading Shift 6 yields a zero-demand grid, and `main.py:1057` still gates `if shift < 10`, so a player receives **five consecutive empty shifts** before "CAMPAIGN END".

## 3.7 One demand curve, and no uncertainty at all

`loader.py:84-93` derives every shift's demand by scaling the **single shared** `DEMAND_PROFILE_NORMALISED`. One demand shape for the entire game. No day-type, no season, no weather.

And demand has **zero forecast error** (`demand.py:57-58`): `get_forecast_mw` and the live path call the same function.

> **Forecast-versus-actual is the defining daily uncertainty of real dispatch, and it is not a mechanic.**

The only divergence in the whole campaign is Shift 5's single hand-authored `DEMAND_OVERRIDE`. This is why Phase 1 planning is a solved puzzle: with a perfect forecast and no noise, `Ctrl+A` is provably optimal and hand-planning is strictly wasted effort. It is also the deepest reason replay value is near zero — a second run of a shift is *identical*, because the only stochastic input in the entire simulation is ±3% wind noise (`renewables.py:251`, unseeded).

## 3.8 Interface and feedback deficits

- **No fast-forward in the game.** `P` toggles pause/1× and that is the entire speed control (`main.py:978-984`). `SPEED_SLOW/FAST/VERY_FAST` are imported at `main.py:62` and never used there. `DESIGNER_TEST` *does* have F1/F2/F3 speed control (`main.py:1275-1280`) — **the dev mode is better equipped than the shipping game.** Meanwhile F1/F3/F5 in PLAYING hot-swap the entire shift, destroying progress without confirmation.
- **The buttons are lies.** `[ START S ]`, `[ STOP X ]`, `[ T ] TRIP` are drawn as bordered rects, but `Renderer.on_click` (`renderer.py:1022`) returns early for anything below the canvas and never hit-tests a button rect. `_cmd_active` is only ever set to `False`. Every player will click them. Nothing will happen.
- **Silent command rejection.** `on_start_unit`, `on_stop_unit`, `on_trip_line`, `on_close_line`, `on_toggle_auto_mode` all `return` silently on precondition failure. Press `S` on a maintenance unit: nothing happens, no explanation. Ironically the *planning* screen has a proper `_set_status()` toast (`planning.py:287`) — the good pattern exists and was never carried into the live game.
- **No help screen, no keybinding overlay, no `?` key.** The authoritative binding list is a docstring at `main.py:9-29` that no player ever sees, and it is already stale. Thirteen bindings — `S X M T C V , . L Tab P Space Ctrl+A` — are undiscoverable.
- **One trend in the entire HUD.** The 60-real-second frequency strip chart, sampled per *rendered frame* rather than per tick, so its time axis stretches with FPS. No voltage trend, no loading trend, no MW trend.
- **No what-if tooling.** No N-1 contingency view — the marquee situational-awareness instrument of real dispatch, and a perfect fit for the aesthetic.
- **Alarms don't point.** `Alarm.element_label` exists and is populated; the canvas never reads it. A tripped-line alarm does not highlight the line.
- `Q` / `Esc` quits the shift with no confirmation.
- 400 kV and 220 kV lines render at identical 2px thickness (`symbols.py:744-747`) despite the docstring claiming 4px/3px/2px.

## 3.9 Bugs that will read as unfairness

**The hour-boundary snap-back.** `_apply_hourly_schedule` (`simulation.py:541-554`) advances every ONLINE+AUTO unit to its planned MW at each integer hour. AGC dispatches via `_set_target_internal`, which does *not* drop a unit out of AUTO. So AGC regulates an AUTO hydro unit for an hour, and at the boundary **the entire accumulated correction is discarded in one step** — injecting a step imbalance into a swing equation moving at 0.5 Hz/s per 100 MW.

Players will experience this as the game randomly punishing them on the hour, with no visible cause. This is the kind of bug that generates "this game is broken" reviews.

**Others found:**
- `_cascade_events` increments once per *tick*, not per tripped line (`simulation.py:472`) — the scored metric undercounts simultaneous trips.
- `LinAlgError` in the load flow silently returns zero flows *and zero loadings* (`loadflow.py:165-170`) — a singular matrix renders as a perfectly healthy grid, with logging suppressed because `DEBUG_SIMULATION = False`.
- `_trip_frequency_runaway_islands` (`simulation.py:1085`) is unreachable — `_trip_isolated_units` runs first and has already tripped every non-slack-island unit.
- `COOLDOWN_MIN_*` and `MIN_UP/DOWN_HOURS_*` are defined but never enforced; a coal unit can be stopped and restarted instantly.
- MVAr capability is flat `q_min/q_max` with no P-Q coupling — a unit at 10 MW has the same reactive range as at rated, so reactive support is free. *(Addressed by C5 / G4 — see Part VIII.)*
- Interconnectors fold straight into the slack bus (`p['MDBY'] += mw`) with **no locational effect on load flow**. *(Addressed by G5 — see Part VIII.)*
- Unseeded RNG (`renewables.py:72`) — runs are not reproducible, which will make balance testing and bug reports painful.
- Magic numbers at `simulation.py:820` (`0.08`) and `:829` (`0.92`) violate the project's own Rule 1.
- Stale docstrings: `frequency.py:60` says AGC is out of scope (it isn't), `units.py:26` says SHUTDOWN→OFFLINE at `min_mw` (code goes to 0), `constants.py:127` says AGC "starts disabled" (it's `True`).

---

# PART IV — WHAT IS ALREADY GOOD

It would be a serious misreading of this report to conclude the project is in trouble. The hard, load-bearing, hard-to-outsource work is **done**. What remains is comparatively tractable.

**1. The simulation is genuinely good.** Honest swing equation, inertia weighting, decoupled voltage with PV→PQ conversion, BFS islanding, per-substation power factors driving reactive draw, matrix rebuild-and-re-solve within a tick. It is numpy-only and it runs inside budget. Nothing in this report asks for it to be rewritten.

**2. Shift 3's L09 decision is the best moment in the game — and a template.** A spare circuit sits open at handover. L01 hard-trips at T+60. Two mutually exclusive branches keyed on `_L09_STILL_OPEN` vs `_L09_CLOSED` produce genuinely different worlds: total blackout, or no interruption at all. It is *pre-positioning rewarded*, it is discoverable, it is fair, and it teaches N-1 thinking by consequence rather than instruction. **This is what all thirty-odd shift beats should look like.**

**3. Phase 1 planning is the most sophisticated screen in the project.** 24×N spreadsheet, stacked-bar generation plot by fuel with a load-forecast overlay, `DIFF` and `REG BAND` summaries, a hard +5% reserve gate with a two-press +20% override, and a competent 100-line `auto_schedule()` heuristic honouring ramp rates and min-up/min-down. It is used in exactly one shift, and — because the forecast is perfect — it is a solved puzzle. Enormous latent value.

**4. The authoring pipeline is a genuine strategic asset.** Grid Designer, Shift Builder, and AST round-trip editing of `shift_NN.py` with byte-preserved comments. **Shifts 6–10 are not blocked by tooling.** They are blocked by nothing but authoring time.

**5. Large authored grids already exist** — `shift10.json` (60 buses, 129 lines, 34 units, 4400 MW, nuclear + solar + wind + pumped storage) and `Alpha.json` (57 buses), both orphaned since `shift_10.py` became a stub.

*Caveat (2026-07-25):* the developer intends to **rebuild Shift 10 rather than adopt this grid as-is**, and its final scale is undecided — possibly closer to 30 buses than 60. So this is a **reference grid and a starting point, not a drop-in content win.** Its enduring value is as the largest topology in the repo: it and `Alpha.json` remain the right performance-ceiling fixtures for solver work (see §8.4), independent of whatever Shift 10 eventually ships as.

**6. The aesthetic is committed and coherent.** Procedural drawing throughout, no sprite sheets, consistent colour ramps and blink conventions, 1994 framing. The `[ START S ]` button convention — embedding the key in the label — is a smart discoverability idea that just needs to be real.

**7. The alarm system is well-built.** Priority tiers, dedup sets, word-wrapped detail, 2 Hz blink on unacked criticals, reserved audio channels, silence-with-auto-clear-on-new-critical. It is a better alarm system than most shipped games have. It just needs to point at things.

---

# PART V — DOES IT PUT YOU IN A TSO OPERATOR'S SHOES?

The stated goal is the dispatcher fantasy. Scored honestly:

| Dimension of the fantasy | Verdict | Why |
|---|---|---|
| **Looks like the job** | ★★★★★ | Instrument strip, alarm feed, schematic, 1994 terminal framing. Excellent. |
| **Vocabulary of the job** | ★★★★☆ | Correct terms used correctly — VSI, AVR, SVC, AGC, spinning reserve, N-1. Domain literacy is real. |
| **Rhythm of the job** | ★★★☆☆ | Shift/briefing/handover/debrief structure is exactly right. Undermined by every shift being 5 minutes at one speed. |
| **Anxiety of the job** | ★☆☆☆☆ | You cannot fail. Nothing is at stake. The defining emotion of the role is absent. |
| **Vigilance of the job** | ★★☆☆☆ | 95% watching is *accurate* — but real vigilance is watching for something that might happen. Here nothing can, until an alarm names it and tells you which key to press. |
| **Judgement of the job** | ★★☆☆☆ | The good moments exist (L09; Shift 5's override) but are rare. Most beats are instruction-following, not decisions. |
| **Foresight of the job** | ★★☆☆☆ | Planning exists and is well-built, but a perfect forecast makes it a solved puzzle. No N-1 tooling during play. |
| **Consequence of the job** | ★☆☆☆☆ | Voltage isn't scored. Blackout doesn't fail you. Campaign end hardcodes grade 'A'. |

**Where it succeeds:** the *texture* is right. Handover notes, the alarm feed, spinning-reserve readouts, the AUTO/MANUAL distinction, the deliberate feel of a night shift. Someone who has done this job would recognise the room.

**Where it fails:** a dispatcher's actual job is **managing risk you cannot see against a future you cannot predict**. GRIDCOM currently has no hidden risk (everything is announced), no unpredictable future (the forecast is exact), and no consequence (you cannot fail). What remains is a guided tour of a very well-modelled grid.

**The paradox worth naming:** GRIDCOM is *too realistic in exactly the wrong dimension*. Its physics timescale is closer to real than most simulators — a 500 MW trip really does hit 49.5 Hz in a fraction of a second. But real dispatchers do not react to that; automatic systems do, and the human manages the *hours around it*. By modelling the sub-second physics faithfully while asking the player to respond to it manually, the game lands in the one gap where neither the human nor the automation has a role.

> **The fix is not more realism or less. It is putting the player on the timescale where the real job actually happens.**

---

# PART VI — FIVE IMPROVEMENTS, ORDERED BY IMPACT

Ordered strictly by fun-per-unit-of-work. Each is independently shippable and independently testable.

---

## ⭐ #1 — Put the player back on the clock

**Impact: transformative. Effort: low — a handful of constants and one new term.**
**Files:** `simulation/frequency.py`, `units.py`, `simulation.py`, `cascade.py`, `constants.py`

Nothing else in this list matters until this is done. Every other fun deficit is downstream of the fact that consequences arrive ~100× faster than the player can respond.

**1a. Decouple physics timescale from clock timescale.** Replace the implicit `/ TIME_COMPRESSION` cancellation at `frequency.py:123` with an explicit, named, tunable game-design constant:

```python
TIME_COMPRESSION:     float = 48.0   # clock / demand / ramp compression
FREQ_DYNAMICS_SCALE:  float = 1.0    # explicit multiplier on frequency dynamics
```

Pass real elapsed seconds explicitly so the speed multiplier does not silently change physics *character* — currently at 3× and 10× the multiplier is not cancelled, so frequency moves 3×/10× faster while the clock moves 144×/480×. Tune to the **10–20 real second** response window (developer decision, 2026-07-25).

**1b. Add primary/droop response.** `DROOP_R = 0.04` already exists at `constants.py:122`, unused. Implement it in `units.py` on synchronous units, applied before AGC.

This is the highest-value single change in the entire report, because it is simultaneously **more physically honest and more forgiving**. Droop arrests the excursion in seconds; AGC and the player then restore it over the following minute. Every frequency event converts from a cliff into a recoverable situation — which is precisely the "fun first, real second" brief. It also creates the game's best teaching moment: the player *watches* the grid save itself, then learns they must restore the reserve it just consumed.

**1c. Retune AGC into a working PI controller.** Raise `AGC_KI` by ~3 orders of magnitude; cut `AGC_KD` drastically; make the rate clamp per *real* second. Add an `agc_saturated` flag to the state snapshot and raise a WARNING when `apply_agc_signal` returns `{}`. **Never let the game conceal a failure from the player.**

**1d. Rescale `TRIP_DELAY_S` and fix its alarm text.** Then put a **visible countdown on the overloaded line**. This single UI addition converts an invisible timer into the best tension mechanic in the game — a ticking clock on a specific object the player can act on. Cheap, dramatic, legible.

**1e. Soften the voltage collapse cliff.** Reduce `V_COLLAPSE_GAIN`, raise `V_COLLAPSE_RECOVERY_PU_S`, target ~10–20 real seconds from warning to unrecoverable. Aim for roughly 3:1 decay-to-recovery asymmetry rather than 44:1. Add a per-bus time-to-collapse indication. Give the player a fight.

**1f. Fix the hour-boundary snap-back.** Carry the AGC offset across the boundary, or ramp AUTO units to the new plan value rather than stepping them.

**Playtest:** trigger Shift 3's RIVE-2 derate. Confirm ≥10 real seconds before frequency leaves the alert band, that it settles to ~50.00 Hz rather than a 0.2 Hz offset, and that behaviour is identical in character at 1× and 3×.

**Expected result:** the game becomes playable. Not finished — *playable*. Every subsequent balance judgement depends on this, which is why nothing else should be tuned first.

---

## ⭐ #2 — Make it matter: stakes, scoring, persistence

**Impact: very high. Effort: medium — three modules that are currently 0 bytes.**
**Files:** new `gameplay/scoring.py`, `gameplay/campaign.py`, `gameplay/debrief.py`; `main.py`

Fixing the physics gives the player agency. This gives them a *reason to use it*.

**2a. Real failure conditions.** A shift must be losable: system blackout, sustained frequency outside limits, or shedding beyond a threshold ends it as FAILED. Currently `is_shift_complete()` is a clock check and blacking out the national grid ends the shift identically to a perfect run. **No fail state means no tension, and the 95% spent watching stays dead air.**

**2b. Write `scoring.py` — score what the game teaches.** Move the 4-line if/elif out of `main.py` into a weighted model over: frequency band %, **minimum voltage and time-in-voltage-band** (currently displayed but not scored — this alone makes Shift 4 count for the first time), max line loading, cascade/shed events, unit trips, and an efficiency term (fuel cost or unit-starts) so an elegant solution beats a brute-force one. Emit a numeric score plus a letter grade.

**2c. Write `campaign.py` with real save/load — and a session loop serving both modes.** JSON to `saves/`. Wire the CONTINUE entry that is currently a literal `pass` at `main.py:547`. **Allow shift replay for a better grade** — with per-shift scores this is where replay value comes from, and it costs almost nothing once scoring exists.

Take a `mode` parameter and write the shift-to-shift loop once. CONTINUOUS needs exactly the same cycle (run → score → advance) with a rotation policy — random, carousel or repeat — instead of a fixed order. It currently has no such loop and borrows `DESIGNER_TEST` instead (§8b.5). One implementation serves both modes and avoids a second `main.py` if/elif branch.

**2d. Write `debrief.py` with an event timeline.** Not just a grade: a chronological list of what happened and how long the player took to respond to each. Post-shift feedback is where a management game does its actual teaching, and it turns a grade from a judgement into a lesson.

**Expected result:** the game acquires stakes, memory, and a reason to play a shift twice.

---

## ⭐ #3 — Give the player real levers, especially on voltage

**Impact: high. Effort: low-to-medium.**
**Files:** `simulation/simulation.py`, `reactive_devices.py`, `units.py`, `data/designer_io.py`, `main.py`

Voltage is meant to be the second pillar. Right now the player frequently has *no tool at all*.

**3a. Seed multiple SVCs.** Replace the single alphabetical placement in `seed_default_reactive_devices` with per-grid authored locations — add an SVC field to the designer grid JSON. **Voltage cannot be a skill while there is one lever on one bus.**

**3b. Expose manual shunt-bank control.** The banks already exist, step correctly, and have a dwell timer. Add a manual/auto toggle so the player can pre-position them ahead of the evening peak. This roughly triples the reactive toolkit for very little code — and pre-positioning is exactly the skill the pillar should be teaching.

**3c. Expose `demand.clear_shed`** on `GridSimulation`. It already exists at `demand.py:205`. Load shedding should be a reversible tactical choice — "shed now, restore in twenty minutes" is a real dispatcher decision — not a permanent scar.

**3d. Add P-Q capability coupling** in `units.py` so reactive support costs active headroom. This is the trade-off that turns reactive management into a genuine decision rather than a free action, and it links the two pillars into one system instead of two parallel minigames.

**3e. Restore speed controls in PLAYING.** `SPEED_SLOW/FAST/VERY_FAST` are already imported at `main.py:62`; the `DESIGNER_TEST` branch already wires them at `main.py:1275-1280`. Move the F1/F3/F5 shift hot-swap behind a debug guard — it currently destroys progress with no confirmation.

**Expected result:** the second pillar becomes playable, and the two pillars start interacting.

---

## ⭐ #4 — Introduce uncertainty; make the campaign escalate

**Impact: high — this is where replay value comes from. Effort: medium-to-high, mostly authoring.**
**Files:** `simulation/demand.py`, `data/profiles.py`, `gameplay/shifts/shift_02.py`, `shift_06..10.py`, `gameplay/phase1.py`

**4a. Add forecast error — the highest-leverage item here.** Give `demand.py` a bounded stochastic divergence from `get_forecast_mw`, with magnitude scaling by shift difficulty. **Seed the RNG per shift-run and store the seed** so runs are reproducible for debugging and balance work (the renewables RNG at `renewables.py:72` is currently unseeded).

This single change does three things at once: it makes every shift replayable, it converts Phase 1 planning from a solved puzzle into genuine risk management, and it creates the actual dispatcher fantasy — *managing a future you cannot predict*. Right now `Ctrl+A` is provably optimal and hand-planning is strictly wasted effort.

**For CONTINUOUS mode this is not one improvement among several — it is the mode's load-bearing mechanic (§8b.4).** Without it, repeat and carousel rotations replay a *bit-identical* shift: same demand, same events, same optimal play. With it, one authored scenario becomes a different shift every time it comes round. Nothing else in this report buys replay value as cheaply.

**4b. Build Shift 10.** The developer intends to author this fresh rather than adopt the orphaned `shift10.json` (60 buses, 34 units, 4400 MW), and its final scale is undecided — possibly nearer 30 buses. Treat the existing grid as a **reference to draw from**, not a drop-in.

Whatever the scale, the escalation argument in 4c holds: **grid size is the weakest difficulty axis available.** If the rebuild comes in smaller for legibility, nothing about the campaign's pressure curve is lost — it was never going to come from bus count.

**4c. Author Shifts 6–9 with a real pressure curve.** The tooling is excellent and this is blocked only by authoring time. Escalate on the axis the campaign currently ignores: **not more buses, but less time, less warning, and overlapping problems.** Target ~3–4 decisions/minute by Shift 9 against Shift 1's 0.8. Set `DIFFICULTY_LABEL` honestly — currently everything including Shift 5 is `'Tutorial'`.

Use Shift 3's L09 as the template for every beat: pre-position or pay, discoverable, fair, no hand-holding alarm naming the key.

**4c-bis. Author a CONTINUOUS scenario library.** A different job against the same tooling: **self-contained situations at varied difficulty, none assuming what came before.** `src/assets/shifts/` currently holds one test fixture (§8b.3), so the mode is a menu with a single entry.

Campaign shifts are not directly reusable — they carry tutorial framing and a fixed position in a curve. But `shift10.json` and `Alpha.json` are (§8b.4): large, fully authored, and needing no campaign position at all. They are closer to shippable content here than anywhere else in the project.

**4d. Rebalance Shift 2** so inaction is not optimal. Move the played window onto a ramping part of the curve, or author an override.

**4e. Add demand-curve variety.** Multiple named profiles in `profiles.py` — weekday, weekend, cold-snap — selected per shift, instead of one shared curve for the entire game.

**4f. Give planning a payoff.** Score plan quality in 2b (reserve adequacy, cost) so hand-planning beats `Ctrl+A`. Also relax the reserve gate to check only the **played** hours — it currently validates all 24 even though only 4 are ever played.

**Expected result:** a campaign that keeps escalating, and shifts worth replaying.

---

## ⭐ #5 — Close the feedback loop

**Impact: moderate but broad — this is the polish that makes everything above legible. Effort: low.**
**Files:** `display/renderer.py`, `context.py`, `panels.py`, `canvas.py`, `symbols.py`

The player cannot play well what they cannot see.

**5a. Add a help / keybinding overlay** on `?` or `F1`. Thirteen bindings are currently undiscoverable, documented only in a stale docstring at `main.py:9-29`.

**5b. Make the context-panel buttons real.** Hit-test the rects in `Renderer.on_click` — or stop drawing them as buttons. Every player will click `[ START S ]`. Right now nothing happens.

**5c. Add command feedback.** Port the planning screen's `_set_status()` toast (`planning.py:287`) into the live game. **A rejected command must always explain itself.** Silent failure teaches players that the game is broken.

**5d. Make alarms point.** `Alarm.element_label` is already populated and the canvas already ignores it. Flash the referenced element. One of the cheapest legibility wins available.

**5e. Add trends for voltage and line loading**, and fix the frequency chart to sample per sim-tick rather than per rendered frame (its time axis currently stretches with FPS).

**5f. Add an N-1 contingency indicator.** "Which line kills me if it goes?" is the marquee situational-awareness tool of real dispatch, a perfect thematic fit, and it makes pre-positioning — the skill the whole game should be teaching — visible and learnable.

**5g. Small fixes:** confirmation prompt on `Q`/`Esc` quit; differentiate 400 kV / 220 kV line thickness in `symbols.py`.

**Expected result:** the depth added by #1–#4 becomes visible to the player.

---

# PART VII — SUMMARY

## The one-paragraph verdict

GRIDCOM has an excellent simulation, outstanding authoring tooling, a committed and coherent aesthetic, and a genuinely good structural idea in the shift/briefing/debrief loop. What it does not yet have is a *game*: five of seven gameplay modules are empty, there is no save system, no fail state, no meaningful scoring, and — most importantly — two timing constants that make every consequence arrive roughly a hundred times faster than the player can act on it. The result is a well-modelled grid the player watches rather than operates. **The good news is that the expensive work is done and the remaining work is mostly tractable.** Fixing the timescale alone (Improvement #1) would do more for the experience than every other item on this list combined, because every other fun deficit is downstream of it.

**Stated more sharply (see Part IX):** the problem is not too little realism, and it is not too much. It is **realism aimed at the wrong layer** — sub-second physics modelled faithfully, while the layer the player actually inhabits (the shift, the plan, the judgement call) is empty. The fix is not to add or remove fidelity but to move the player to where the decisions are.

**Both modes depend on the same fix.** GRIDCOM ships CAMPAIGN and CONTINUOUS (Part VIII-B); the second is architecturally real but has one authored scenario, no session loop, and no scoring. It inherits every core-loop defect above, so nothing below changes in priority — but two items gain weight: **forecast error (#4a)**, which is what stops a repeat rotation replaying a bit-identical shift, and **the session loop in #2c**, which CONTINUOUS needs and does not have.

## Priority order

| # | Improvement | Impact | Effort | Do it because |
|---|---|---|---|---|
| 1 | Put the player back on the clock | Transformative | Low | Nothing else matters until this is fixed |
| 2 | Stakes, scoring, persistence | Very high | Medium | Gives the player a reason to use their agency |
| 3 | Real levers, especially voltage | High | Low-Med | Makes the second pillar playable at all |
| 4 | Uncertainty + campaign escalation | High | Med-High | Where replay value and the real fantasy live |
| 5 | Close the feedback loop | Moderate/broad | Low | Makes everything above legible |
| G | Physical fidelity (Part VIII) | Moderate | Med | **After #1.** Closes the AC gaps that cost gameplay — but adding physics before the timescale fix only deepens a model the player still cannot reach |

## Recommended immediate next step

Implement **#1 only**. Then replay Shift 3 and re-evaluate everything else in this document against how the game actually feels.

This sequencing is deliberate, not cautious. The balance judgements in #2–#5 — how harsh a fail state should be, how much forecast error is fair, how many SVCs a grid needs — all depend on how the core loop plays once the player can genuinely participate in it. Tuning them against the current physics would mean tuning them twice.

---

# PART VIII — PHYSICAL FIDELITY (PHASE G)

*Added 2026-07-25, after a closer read of the solvers. **Sequenced after Improvement #1.***

## 8.1 Triage — separating two different lists

When the simulation's approximations are listed as a single set, they look like one problem. They are not. Some cost the player gameplay; others are deliberate abstractions that Rule 6 exists to protect. Only the first list is worth acting on.

**Genuinely worth fixing — these cost you gameplay:**

| Point | Why it matters *as a game* | Effort |
|---|---|---|
| No droop | The single best fix in the analysis. More honest *and* more forgiving. | Low |
| No P-Q capability curves | Makes reactive support free — kills the tradeoff that would link your two pillars | Low |
| Interconnectors have no locational effect | They're a lie on the schematic; `p['MDBY'] += mw` means they don't do the thing they look like they do | Low |
| One demand curve / no forecast error | Where replay value lives; makes planning a solved puzzle | Medium |
| Collapse overlay doesn't feed the solver | Your most dramatic event is cosmetic | Medium |
| Fixed 2.5% losses | Fine as a game abstraction — but **G2** replaces it with real `I²R` essentially for free once **G1** lands | Low |

Where each is handled:

| Point | Handled by |
|---|---|
| No droop | **#1b** (Part VI) — stays in the timescale work, where it belongs |
| No P-Q capability curves | **#3d / G4** |
| Interconnectors locational | **G5** |
| Demand curve / forecast error | **#4a / #4e** |
| Collapse overlay not in solver | **#1e**, and partly dissolved by **G6** — with FDLF converging, voltage collapse becomes emergent rather than an authored overlay |
| Fixed 2.5% losses | **G2** |

Note that droop is listed here but implemented in Improvement #1. It is a timescale fix wearing a fidelity costume: its value is that it arrests an excursion within the player's reaction window, not that it is more physically complete.

**Deliberate abstractions to keep:** no AC losses in the DC path (superseded by G2 rather than "fixed"), no angle limits, simplified cascade, fixed 24:1 time compression. Rule 6 covers these.

## 8.2 The finding that changed the scope

The initial assessment — that AC power flow was out of reach — was wrong. A closer read of [voltage.py:95-300](src/simulation/voltage.py#L95) shows the project is most of the way there already:

- [`loadflow.solve()`](src/simulation/loadflow.py#L142) computes `Δθ = B⁻¹P`. **This is FDLF's B′**, already built, reduced and slack-removed.
- [`voltage._solve_delta_v()`](src/simulation/voltage.py#L251) computes `ΔV = B'⁻¹Q`. **This is FDLF's B″**, likewise.
- Both matrices are **constant**, rebuilt only on topology change via `rebuild()` — exactly the property that makes Fast-Decoupled Load Flow cheap and robust relative to Newton-Raphson.
- [`voltage.solve()`](src/simulation/voltage.py#L190-230) already runs a **bounded iteration to a fixed point**, with a convergence tolerance (`PV_CORRECTION_Q_TOL_MVAR`) and a hard cap (`PV_CORRECTION_MAX_ITERS`).

FDLF is those two solves alternated, with nonlinear mismatch recomputed between them. **Both halves and the iteration scaffolding already exist.** What is missing is the outer loop and the mismatch functions — roughly 120 lines, most of it restructuring rather than new algorithm.

## 8.3 The work

**G1. Add line resistance.** `Line` carries `reactance_pu` only ([topology.py:107-137](src/data/topology.py#L107)), derived from `length_km × reactance_pu_per_km(voltage_kv)`. Add a `resistance_pu_per_km()` helper mirroring [designer.py:68-74](src/display/designer.py#L68), with three per-tier constants beside `REACTANCE_PU_PER_KM_*`.

Derive R rather than storing it: `length_km` and `voltage_kv` are already on every line, so **no designer grid JSON needs re-authoring and every existing grid stays valid untouched**. Real X/R ratios run ~10:1 at 400 kV down to ~3:1 at 150 kV — that spread is itself gameplay, making the regional network visibly lossier than the backbone.

*Prerequisite for G2 and G6.*

**G2. Loss-compensated DC (`I²R`).** Replace the flat `LOSSES_FRACTION = 0.025` at [demand.py:174](src/simulation/demand.py#L174) with per-line losses estimated from the DC flow and the voltage solver's V:

```
loss_mw[k] ≈ r_pu[k] × (P_mw[k] / (V_pu[k] × S_BASE))² × S_BASE
```

Add half of each line's loss to each endpoint, then re-solve **once** to redistribute. Cap at one pass — an uncapped loop reintroduces the non-determinism this path exists to avoid. Keep `LOSSES_FRACTION` for the singular-matrix fallback.

*Player-visible:* losses rise with loading and with low voltage. A heavily-loaded grid genuinely costs more to run, giving the efficiency term in **#2b** something real to measure.

**G3. Voltage-dependent load (ZIP).** The highest gameplay-per-line item here — ~20 lines, no new solve:

```
P = P₀ × (V / V₀) ^ ALPHA_P        # ALPHA_P ≈ 1.0–1.5, new constant
```

*Player-visible:* low voltage reduces load, which is self-stabilising and is physically why brownouts work. It also creates a genuine dispatcher dilemma — **fixing a voltage sag raises MW demand**, so the reactive fix carries an active-power cost. That is the tradeoff that turns two parallel minigames into one system.

Interacts with the collapse overlay (**#1e**): ZIP load provides real negative feedback that partially self-arrests a sag, so tune them together.

**G4. P-Q capability coupling.** Same item as **#3d**; noted here as the third leg. With G3 the coupling runs both directions — reactive support costs MW headroom, and voltage changes MW demand.

**G5. Interconnector locational effect.** Currently folded into the slack bus (`p['MDBY'] += mw`, [simulation.py:846-847](src/simulation/simulation.py#L846)), so INTC-N and INTC-S have **no effect on load flow at all** despite being drawn as real network endpoints. Inject at their actual connection buses. Small change; removes a visible lie and makes interconnector scheduling a locational decision.

## 8.4 G6 — the hybrid: FDLF as a flagged refinement

New module `src/simulation/acloadflow.py`, wrapping the two existing solvers:

```
V ← 1.0, θ ← 0          (or the previous tick's converged state as a warm start)
repeat, cap AC_MAX_ITERS (~10):
    ΔP = P_scheduled − P_calculated(θ, V)      ← new: nonlinear mismatch
    Δθ = B′⁻¹ (ΔP / V)                          ← existing loadflow solve
    ΔQ = Q_scheduled − Q_calculated(θ, V)      ← new: nonlinear mismatch
    ΔV = B″⁻¹ (ΔQ / V)                          ← existing voltage solve
    converged when max|ΔP|, max|ΔQ| < AC_MISMATCH_TOL_PU
```

The new code is the two mismatch functions, computing injections from the full AC line equations (`P_ij = V_i V_j (G cos θ_ij + B sin θ_ij)` and its Q counterpart). `_compute_line_flows` already has the per-line iteration shape to build on.

**The contract:**

1. DC + G2/G3 remain, and remain **always solvable**. They are the floor, not a legacy path.
2. FDLF runs each tick. **If it converges, its result is used** — real losses, real P-Q coupling, emergent `I²X` reactive losses, voltage-dependent flows.
3. **If it does not converge within the cap, fall back to DC and set a `solver_stressed` flag on the state snapshot.**
4. Warm-start from the previous converged state; steady operation should converge in 2–4 iterations.

**Why the flag is the whole design.** The original objection to FDLF was never the algorithm — it was that a non-convergence fallback would silently show the player wrong state, the same failure already sitting at [loadflow.py:165-170](src/simulation/loadflow.py#L165). **A surfaced fallback is not a lie.**

And it converts a technical limitation into gameplay. Non-convergence clusters exactly where the grid is genuinely stressed — buses approaching 0.7 pu, heavy loading, weak post-trip topology — so `solver_stressed` reads as **the control room's instruments losing confidence**. That is a real and dramatic thing to show a dispatcher, in the same family as the AGC-saturation warning in **#1c**. Surface it in the instrument strip, not just the debug overlay.

**What it preserves:** the cascade's rebuild-and-re-solve-twice-inside-one-tick ([simulation.py:471-490](src/simulation/simulation.py#L471)) never stutters, because the DC floor underneath is unchanged and unconditional.

**What it costs:** G2 and G3 are still built, as the fallback path — so this is additive rather than a replacement. **Budget the tick carefully:** FDLF at 2–4 warm-started iterations must fit the 5 ms budget alongside everything else, and the cascade can invoke a solve twice per tick. This is the hard gate on the whole phase.

*On grid size:* benchmark against the **largest topology in the repo** — currently `shift10.json` (60 buses) and `Alpha.json` (57) — rather than against whatever Shift 10 eventually ships as, since its scale is undecided and may land nearer 30 buses. Keeping the ceiling fixture independent of the content decision means the budget result stays valid however Shift 10 is authored.

If the shipped campaign does top out around 30 buses, this gate gets substantially easier: the solve is dominated by the `n×n` matrix work, so halving the bus count more than halves the cost. The gate is worth keeping at the higher figure regardless — passing it at 60 buys headroom for anything later.

## 8.5 G7 — recorded decision: no Newton-Raphson

Rejected on gameplay grounds, not difficulty. NR rebuilds a Jacobian per iteration and, while quadratically convergent when it converges, is markedly **less robust than FDLF near voltage collapse** — precisely where the game is most dramatic and where **#1e**'s mechanic operates. FDLF's constant B′/B″, already built here, is the property that makes the hybrid viable at all.

This keeps the project consistent with Rule 6 and with the framing that GRIDCOM is a game built on a real power-system model rather than a simulator.

## 8.6 G8 — reactive loss injection (fallback path only)

With G6 converging, `I²X` losses are emergent and this is unnecessary. But the DC fallback still under-models them, so reactive support does not decay with distance and loading — supporting a remote bus from a strong generator is too effective, and the "reactive power doesn't travel" lesson is under-taught in exactly the stressed conditions where the fallback engages. Compute `I²X` alongside `I²R` in G2 and inject it as additional Q draw at line endpoints (~10 lines, same loop, same data).

*Open question:* confirm an extra per-bus Q term feeds `q_injections` without disturbing the PV correction's fixed point at [voltage.py:190-230](src/simulation/voltage.py#L190). Check before committing to that estimate.

## 8.7 Does this make GRIDCOM a simulator?

The earlier answer in this report — *no, and you shouldn't want it to be* — leaned on "no AC power flow" harder than the codebase warranted. With G6 converging, **GRIDCOM has genuine AC power flow**: real losses, real P-Q coupling, emergent reactive losses, voltage-dependent flows.

The honest remaining caveats become:

- the DC fallback path (surfaced, not hidden);
- the tunable collapse overlay, retained deliberately because a *designed* collapse curve serves **#1e**'s 10–20 second fightable slide better than an emergent one;
- the timescale decisions in Improvement #1.

All three are **game-design choices rather than modelling gaps** — which is a materially stronger position than "DC approximation". The recommended framing is unchanged (*a strategy game built on a real power-system model*), but it can now be said without the caveat that the physics is approximate where it counts.

---

# PART VIII-B — THE TWO GAME MODES

*Added 2026-07-25. The analysis above was written as though GRIDCOM were campaign-only; it is not.*

## 8b.1 The intended structure

GRIDCOM ships **two modes**:

- **CAMPAIGN** — the authored 10-shift progression, played in order, with difficulty selection.
- **CONTINUOUS** — the player picks from a set of scenarios and plays shift after shift indefinitely: **random, carousel, or repeat**.

Everything in Parts I–VII was written against the campaign. That was an incomplete reading, and it under-weighted several findings. This part corrects them.

## 8b.2 What is already built

More than expected, and the plumbing is sound:

- `MODE_SELECT` offers both modes ([main.py:659-667](src/main.py#L659)); CONTINUOUS routes to `SHIFT_SELECT_JSON`.
- `SHIFT_SELECT_JSON` ([main.py:721-752](src/main.py#L721)) lists authored shifts from `list_shift_names()` and launches the chosen one.
- `load_shift_config_from_json()` ([loader.py:115](src/gameplay/shifts/loader.py#L115)) is the parallel load path, already written and already producing the same config dict `GridSimulation` consumes.
- The **Shift Builder** (`display/shift_builder.py`, 677 lines) authors these scenarios, and `ShiftDefinition` ([shift_io.py:91](src/data/shift_io.py#L91)) already carries grid reference, start hour, duration, initial schedule, maintenance sets, per-bus demand and a scripted event timeline.

**The mode is architecturally real.** It is not a stub.

## 8b.3 What is missing

**1. There is one authored scenario.** `src/assets/shifts/` contains exactly `shift1_fixture.json`. CONTINUOUS mode is a menu with a single entry, and that entry is a test fixture rather than designed content.

**2. There is no continuity.** CONTINUOUS launches into `DESIGNER_TEST` ([main.py:739](src/main.py#L739)) — the *developer test harness* — not into a session loop. When the shift ends the player returns to the picker. There is no shift-after-shift progression, and therefore **none of random / carousel / repeat is implemented.** The word "continuous" does not yet describe the behaviour.

**3. It inherits every core-loop defect.** Same simulation, same timescale, same absent scoring. CONTINUOUS cannot be better than the loop underneath it.

**4. It has no scoring at all** — `DESIGNER_TEST` bypasses even the four-line campaign assessment (§2.3), so a CONTINUOUS shift produces no grade, no record, nothing.

## 8b.4 How this changes the analysis

Four weightings shift, and one changes category entirely.

**Forecast error (#4a) is promoted again — it is now the mode's load-bearing mechanic.** §9.3 already called uncertainty the substrate of a tension machine. For CONTINUOUS it is more than that: **it is the only thing standing between "endless replayability" and "the same five scenarios on a loop."** A repeat-mode shift with a deterministic forecast is *identical* every time — same demand, same events, same optimal play. With per-run seeded forecast error and renewable noise, the same authored scenario becomes a different shift each time it comes round. Nothing else in this report generates replay value as cheaply.

**Scenario authoring changes shape.** §4c argues for an escalating pressure curve across Shifts 6–9. CONTINUOUS wants something different: **a library of self-contained situations at varied difficulty**, none of which assume what came before. These are different authoring jobs against the same tooling. The Shift Builder already supports both; the campaign shifts are simply not reusable as CONTINUOUS scenarios without decoupling them from their tutorial framing.

**Scoring (#2b) needs a second consumer.** A weighted score is more valuable here than in the campaign — CONTINUOUS has no narrative arc, so **the score is the progression.** Per-scenario bests, streaks across a carousel, and cumulative run stats are what give the mode a reason to continue. Design `scoring.py` to serve both modes from the start rather than retrofitting.

**The orphaned grids find their real use.** §4b downgraded `shift10.json` and `Alpha.json` to reference material once the developer decided to rebuild Shift 10. In CONTINUOUS they are **directly valuable again** — large, fully-authored, and needing no tutorial framing or campaign position. They are closer to shippable content here than anywhere else in the project.

## 8b.5 The one structural gap worth naming

CONTINUOUS launching into `DESIGNER_TEST` is the thing to fix first in this mode, and it is not cosmetic. The dev harness has different keybindings (§3.8: it has the speed controls the real game lacks), no scoring, no debrief, and no concept of a next shift. **The mode currently borrows a debug path because the session loop it needs does not exist.**

That session loop — pick a rotation policy, run a shift, score it, advance — is properly part of `campaign.py` (#2c), which is currently 0 bytes. Writing it once, with a `mode` parameter, serves both modes and avoids a second `main.py` if/elif branch of the kind that has already made the campaign path hard to follow.

---

# PART IX — GRIDCOM AS A *FUN* SIMULATOR

*The question this part answers: not "is the model accurate?" but "does it feel like the job?" — a game that puts you in the chair, rather than one that reproduces the physics.*

## 9.1 The genre's actual rule

Games that succeed at this — *Kerbal Space Program*, *Cities: Skylines*, *Papers, Please*, *Football Manager* — all work the same way:

> **Model the system honestly enough that the player builds a real mental model, then put them at the timescale where their decisions are the interesting variable.**

None of them simulate the fastest layer of their domain. Kerbal does not model turbopump cavitation. Football Manager does not simulate individual passes at 30 Hz. They abstract **below** the player's decision layer and stay honest **at and above** it.

**GRIDCOM currently does the opposite.** Sub-second swing dynamics are faithful (§3.1); the layer above — the shift, the plan, the judgement call — is where the game is empty (§1.3, §3.5). That is this entire report compressed into one sentence: *the fidelity is real, it is just aimed below where the player lives.*

This reframes the central finding. The problem was never too little realism, and it was never too much. It is **realism pointed at the wrong layer**.

## 9.2 What already works

Part V scored the texture honestly and the texture is good: correct vocabulary used correctly, the handover/briefing/debrief rhythm mirroring a real shift, an alarm feed and instrument strip that look like the room. Someone who has done this job would recognise it.

**Shift 3's L09 is a genuine fun-simulator moment** — pre-position or pay, no hand-holding, two materially different worlds depending on one decision made an hour earlier. That is exactly the genre working.

This is not a small foundation. **The hard-to-fake part is done.**

## 9.3 The three things standing in the way

**1. The player is not at the decision layer.** Consequences arrive ~100× faster than any response (§3.1). In fun-simulator terms this is the cardinal sin: the game simulates a layer the player cannot inhabit. Every other deficit is downstream of it.

**2. Nothing is at stake.** You cannot fail, voltage is not scored, campaign end hardcodes grade `'A'` (§2.3, §3.5). Fun simulators are almost entirely tension-driven — **the credible threat of loss is the product.** Without it, the 95% spent watching is dead air rather than vigilance.

**3. The future is known.** Zero forecast error, one demand curve (§3.7). A fun simulator is fundamentally about **deciding under uncertainty**. With a perfect forecast, `Ctrl+A` is provably optimal and the best screen in the game — the planning grid — is a solved puzzle.

**The third is the most under-weighted item in this entire report.** Uncertainty is not a feature of this genre; it is the substrate. Everything the player does becomes interesting only because the future is not known.

## 9.4 What this means for Phase G

Worth stating plainly, given how much of the analysis Part VIII occupies:

> **Phase G does not move GRIDCOM toward being a fun simulator.**

Real `I²R` losses and FDLF convergence are invisible to a player who still cannot participate in the loop. Two exceptions, both already correctly placed:

- **Droop (#1b)** — filed under fidelity, but it is really a *reaction-window* fix. It buys the player time, which is why it sits in Improvement #1 rather than Phase G.
- **ZIP load (G3)** — creates the dilemma where fixing a voltage sag raises MW demand. That is a **decision**, not a number.

Everything else in Phase G is craftsmanship: worth doing, correctly sequenced after #1, and **not what makes the game fun.** Sequencing it first would be the most expensive mistake available in this document.

## 9.5 The conversion

GRIDCOM is roughly **one-third of a fun simulator**: the texture and the model are there, the stakes and the timescale are not. The distance is smaller than it looks, because the expensive part — a grid model a player can build genuine intuition about — is already built and does not need rewriting.

| Has | Needs | Delivered by |
|---|---|---|
| A grid that behaves plausibly | A grid the player can *act on in time* | **#1** |
| Correct professional texture | Consequence attached to it | **#2** |
| Systems that interact | Interactions the player must *trade off* | **#3**, G3 |
| A campaign that grows in scale | A campaign that grows in *pressure* | **#4** |
| An honest model | An *uncertain future* to apply it to | **#4a** |

The right-hand column is what the genre is. The priority order in Part VII already targets it — **#1 through #4 are exactly this conversion, in exactly this sequence.** Part IX does not add work; it explains why that ordering is right.

## 9.6 Design intent — resolved

**GRIDCOM is a tension machine** *(developer decision, 2026-07-25)*.

This was the open question in the first draft of this part: tension-driven crisis management, or a contemplative night-shift piece where competence is expressed as calm and vigilance is rewarded with uneventfulness. Both are legitimate; they demand different games. **The answer is the former**, and §9.3's stakes argument applies in full rather than needing reinterpretation.

Four consequences follow directly, and they sharpen the plan rather than change it:

**1. Improvement #2 is not optional, and its failure conditions should bite.** A tension machine without a credible threat of loss is a contradiction. `is_shift_complete()` being a clock check (§3.5) is the single most anti-tension line in the codebase — it guarantees that nothing the player does can matter. Blackout, sustained frequency excursion and excessive shedding should all end a shift as FAILED, and the debrief should say so plainly.

**2. The 95%-watching figure (§2.2) is now unambiguously a defect.** Under the contemplative reading it could have been defended as atmosphere. It cannot be here: tension requires either action or the *imminent possibility* of action, and Shift 2 — where optimal play is provably zero inputs (§3.6) — is the clearest failure. Decision density is a primary metric, not a secondary one.

**3. Uncertainty (§9.3 item 3) becomes the highest-value content work.** Tension is manufactured almost entirely by *not knowing*. With a perfect forecast the player is executing a solved plan, which is the emotional opposite of the target. This promotes **#4a (forecast error)** from "where replay value lives" to a core-loop requirement — arguably it should be pulled forward within Improvement #4.

**4. The reaction window is a tension dial, not just a playability fix.** The 10–20 second target (see Appendix) is now doing double duty: long enough to act, short enough to be frightening. When tuning #1a, err toward the **lower** end of that range. A 20-second window is comfortable; a 12-second one is a tension machine. This is worth revisiting empirically once Improvement #1 lands.

**What does not change:** the priority ordering in Part VII, and §9.4's warning that Phase G is craftsmanship rather than fun. If anything the tension framing strengthens that warning — `I²R` losses generate no tension whatsoever, while the `solver_stressed` flag (§8.4) and the overload countdown (#1d) generate a great deal. **Prefer, throughout, the items that make the player nervous.**

---

## Appendix — Design decision recorded

**Target reaction window: 10–20 real seconds** to respond to a large unit trip before frequency leaves the alert band *(developer decision, 2026-07-25)*.

Tuning target for #1a (`FREQ_DYNAMICS_SCALE`), #1b (droop), #1d (`TRIP_DELAY_S`), and by extension #1e (voltage collapse).

Rationale: tense but actionable — enough time to read the alarm, select a unit and type a target, but only if the player already knows what they are doing. Real grids arrest an excursion in seconds via governor droop; this preserves that shape while giving human hands a chance. Deliberately not simulator-accurate, per the "fun first, real second" brief.

**AC power flow scope: hybrid — DC floor plus FDLF refinement, with a surfaced `solver_stressed` fallback** *(developer decision, 2026-07-25)*.

Newton-Raphson rejected (§8.5). Phase G sequenced after Improvement #1, so the added fidelity lands on a loop the player can actually reach. See Part VIII.

**Design intent: GRIDCOM is a tension machine** *(developer decision, 2026-07-25)*.

Not a contemplative night-shift piece. Resolves the open question in §9.6. Consequences: failure conditions in #2 are required and should bite; decision density is a primary metric; forecast error (#4a) is promoted to a core-loop requirement; and the reaction window should be tuned toward the **lower** end of 10–20 s. Throughout, prefer the items that make the player nervous.

---

*Analysis derived from source code only. No design or status documents were consulted, so any divergence between this report and the design documentation reflects a divergence between documentation and implementation.*
