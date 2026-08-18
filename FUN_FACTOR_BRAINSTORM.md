# GRIDCOM — Fun Factor Brainstorm

**Date:** 2026-08-18
**Brief:** *Fun is much more important than reality.* Push the envelope.
**Premise accepted:** GRIDCOM does not need to be COALCOM — but TSO operations
have real structural similarities to plant operations, and we are prepared to
distance ourselves from reality to find the game.

---

# PART 0 — THE HONEST STARTING POINT

## 0.1 What COALCOM's fun actually is

It is not the TSO order. The order is a **metronome** — a device that keeps a
task always live so there is never dead air. The fun is what the order *forces*:

```
ONE target (MW)  <-  turbine  <-  boiler  <-  coal  <-  air
                                    |          |
                                feedwater   cooling
```

Four load-bearing properties:

1. **One goal, reached through many subsystems.** Every route to MW passes
   through boiler, coal, feedwater, cooling.
2. **Every lever pushes back.** The valve moves power *and* upsets pressure
   *and* drum level. Coal adds heat *and* vibration *and* motor temperature.
   Pumps buy safety *and* cost 2.5 MW off the very number you are scored on.
   The manual's sharpest line: *"nearly 8 MW — enough to push a borderline TSO
   order into compliance."*
3. **The player is the only coordinator.** Nothing is automated. Mastery is a
   learned sequence: *valve, wait, coal, wait, feedwater.*
4. **Failure is a slow slide you can fight.** Drum level falls over ~10 s.
   Vibration climbs 60 → 80 → 95. You watch it coming and you act.

## 0.2 GRIDCOM measured against those four

| COALCOM property | GRIDCOM today |
|---|---|
| One goal via many subsystems | ✗ Three **parallel** goals (frequency / voltage / flows), each with its own dedicated lever |
| Levers push back | ✗ `set target → MW happens`. `q_max_mvar` is a flat spec value independent of MW output (`units.py:814,852`) — reactive support is **free**. No fuel cost exists anywhere |
| Player coordinates | ✗ **AGC does the minute-to-minute work.** `AGC_ENABLED=True` from Shift 1 line one |
| Slow fightable slide | ~ Partial. Overload countdowns exist (`renderer.py:818`); frequency is fast; voltage collapse is a cliff |

> **Diagnosis: GRIDCOM's levers don't resist, its goals don't interact, and the
> one continuous job it has is on autopilot.** In COALCOM terms, GRIDCOM ships
> with the boiler running itself.

## 0.3 The asset nobody is using

`src/data/fleet.py` defines 47 units with genuinely dramatic diversity:

| Type | Ramp | Cold start | Min stable | Character |
|---|---|---|---|---|
| NUCLEAR | **1 %/min** | 480 min | 490/700 MW | Immovable. A wall you build around |
| COAL | 3 %/min | 240 min | 90/300 MW | Slow, committed, cheap |
| CCGT | 8 %/min | 60 min | 80/400 MW | The workhorse |
| HYDRO | **100 %/min** | 5 min | 0 MW | Instant. Precious. Finite |
| HYDRO_PUMP | 100 %/min | 5 min | 0 MW | **Can consume power.** Storage |

**This is a fantastic toybox and the game barely opens it.** A fleet where one
unit takes eight hours to start and another takes five minutes is *already* a
puzzle about time and commitment. Shift 1 uses four units. Nothing in the game
yet makes the player feel the difference between a nuclear unit and a hydro
unit as a *decision*.

The pumped-storage units are the most under-used objects in the codebase.
A machine that turns surplus into stored energy and back is a **battery the
player manages** — that is a strategy game mechanic sitting unused.

---

# PART 1 — THE FIVE ENGINES OF FUN

Rather than three monolithic options, here are five independent *engines*.
Each generates fun by a different mechanism. They can be combined.

---

## ENGINE 1 — RESISTANCE
### *"Every lever costs you somewhere else"*

The most direct COALCOM translation. Today GRIDCOM's controls are one-way
functions. Make them trade against each other.

### 1.1 P-Q coupling — reactive support eats MW headroom ⭐

Today a unit at 10 MW has the same MVAr range as at rated output
(`units.py:814`). Real machines trade them on a capability curve.

**Consequence:** raise an AVR setpoint to hold a remote bus, and you consume
the spinning reserve you were saving for the demand ramp.

Shift 1's two lessons — *reserve margin* and *Holt's AVR sag* — stop being two
lessons and become **one decision with two costs**. This single change welds
the frequency pillar and the voltage pillar into one system.

*This is the highest-value mechanical change available in the entire game.*

### 1.2 Voltage-dependent load (ZIP) — fixing a sag raises demand

`P = P₀ × (V/V₀)^ALPHA_P`. ~20 lines, no new solver.

**Fixing a voltage sag increases MW demand**, which eats the reserve that 1.1
just made scarce. Physically why brownouts work; mechanically a genuine
dilemma with no free answer.

### 1.3 Fuel cost and merit order

No cost model exists. Add £/MWh per unit type and the fleet's diversity
becomes economic: cheap units are slow, fast units are expensive. Every "just
start another unit" reflex acquires a price.

### 1.4 Enforce the commitment constraints that already exist

`MIN_UP_HOURS_COAL=6.0`, `MIN_DOWN_HOURS_COAL=8.0`, `COOLDOWN_MIN_COAL=150.0`
are defined at `constants.py:539-554` and **never enforced** — a coal unit can
be stopped and restarted instantly. Enforcing them makes every start/stop a
commitment you live with for the rest of the shift.

**Free tension: the constants are already authored.**

### 1.5 Reversible load shedding

`demand.clear_shed` exists (`demand.py:205`) and is not wrapped on
`GridSimulation`. Shedding is currently a one-way door that permanently caps
your grade — the one emergency tool in the game and using it is pure
punishment. Wrapping it makes *"shed now, restore in twenty minutes"* a real
tactical choice rather than an admission of defeat.

### 1.6 Thermal line ratings — the "vibration" analogue ⭐

COALCOM's pulverizer vibration is its best pressure mechanic: a number that
climbs while you overuse something, warns at 60, alarms at 80, trips at 95.
**Lines should behave the same way.**

Today a line is either under its limit or accumulating toward a trip. Instead:
give every line a **thermal state** that heats with loading above ~90% and
cools below it. Overload it briefly — fine. Overload it for a while — it's
hot, and now it trips at a *lower* threshold, and it stays hot for minutes.

This converts topology from a binary into a resource you spend and recover,
and it gives the player the *slow fightable slide* COALCOM has and GRIDCOM
mostly lacks.

> **Engine 1 summary:** makes decisions **harder**. Does not by itself make
> them **more frequent**.

---

## ENGINE 2 — AGENCY
### *"You are the controller, not the supervisor"*

The deeper problem may not be the levers. It may be that **AGC plays the game
for you.**

### 2.1 The observation

AGC is a genuine PI controller (`AGC_KP=100`, `AGC_KI=5.0`, `AGC_KD=2000`) that
continuously tracks demand on every HYDRO/CCGT unit. Shift 1 enables it in the
first line of the handover notes. The player's job reduces to: *notice AGC is
running out of room, and give it more room.* One decision per shift.

**A telling precedent:** Stage 34 disabled droop (`DROOP_ENABLED=False`)
because it *"made a player's manual RIVE setpoint read as broken."* The
automation was fighting the player, and the fix was to remove the automation
that fought. **The identical logic applies one level up, to AGC.**

### 2.2 AGC as a resource, not a default ⭐

- **Per-unit enrolment**, off by default in early shifts.
- **Enrolling a unit spends its reserve.** AGC has no concept of "running low"
  — that is already true and it is the most interesting thing about it. Make
  it *visible*: enrolled units display the headroom AGC is consuming.
- **A regulation band**: AGC may move a unit only ±X MW from the player's
  setpoint. **The player sets the operating point; AGC only trims.** Now every
  demand movement is the player's problem again.
- **Automate everything** → perfectly regulated, nothing held in reserve, and
  the first contingency kills you.

The skill becomes *deciding what to automate and when* — which is both a real
dispatcher skill and a genuinely good game mechanic.

### 2.3 The anticipation game

COAL ramps at 3%/min — 9 MW/min on a 300 MW unit. Against a demand ramp
climbing 75 MW per sim-hour, **reacting is always too late.** The player must
move setpoints *before* they are needed.

This is COALCOM's *"move the valve, wait, then move coal"* in grid form, and
the fleet data already supports it perfectly. No new physics required — just
remove the autopilot that currently absorbs the consequence.

### 2.4 Manual frequency as a skill ceiling

With AGC off on a unit, holding frequency by hand against a moving demand
curve is a genuine skill that improves with practice. That is the *"increasing
mastery"* you named as central to COALCOM's appeal — and it is completely
absent today, because AGC is better at it than you and always will be.

> **Engine 2 summary:** the single biggest increase in **decision density**
> available. Costs dispatcher realism — accepted under the brief.

---

## ENGINE 3 — DREAD
### *"I saw that coming"*

GRIDCOM already has one genuinely excellent moment, and it is **not** a
COALCOM moment.

### 3.1 The L09 beat, and why it works

A spare circuit sits open at handover. At T+152, L01 trips. Closed it earlier →
nothing happens. Left it open → Ashcombe and every load behind it goes dark.

No dexterity. No coordination. **A judgement made an hour before it mattered,
against a risk that was never explicitly announced.** That is *dread*, and it
is a completely different emotion from COALCOM's busyness — arguably a better
fit for a 1990s night-shift control room.

**This is the best thing in the game and it is currently one beat in one
shift.**

### 3.2 Generalise it: the risk economy

Every shift carries 2–4 **latent risks**. Each is:
- cheap to cover early,
- expensive or impossible to fix late,
- **not announced** — inferable from the board if you are reading it,
- and **sometimes never fires.**

That last property is essential. If every covered risk pays off, covering is
just a delayed instruction. If some never fire, covering becomes a **bet**, and
the player who over-insures pays in efficiency while the one who under-insures
occasionally dies. **That gap is the game.**

### 3.3 N-1 as the primary instrument

*"Which line kills me if it goes?"* The analysis already exists offline in
`designer_analysis.py:137-184` and is entirely absent in-play — despite Shift 1
teaching an N-1 lesson.

In this engine it is not a convenience readout. It is **the lens you read all
shift**, the equivalent of COALCOM's Key Indicators box.

### 3.4 An untrustworthy forecast

`demand.py:57` states outright that the forecast is *identical* to live demand.
With bounded, seeded divergence, pre-positioning becomes a bet rather than a
calculation, and the excellent Phase 1 planning screen stops being a solved
puzzle where `Ctrl+A` is provably optimal.

Also seed the renewables RNG (`renewables.py:72`, currently unseeded — runs are
not even reproducible today, which makes fair scoring impossible).

> **Engine 3 summary:** maximum authenticity *and* it builds on the best thing
> already in the game. Risk is pacing — dread needs quiet, and quiet needs to
> not read as boredom.

---

## ENGINE 4 — TEMPO
### *"There is always something live"*

This is COALCOM's TSO order, correctly understood: **not the fun itself, but
the metronome that guarantees there is never dead air.**

### 4.1 Dispatch orders — the direct translation

A rolling series of grid targets the player must achieve and *hold*:

```
+-------- DISPATCH ORDER --------+
| HOLD INTC-N EXPORT             |
| Target: 250 MW  +/- 15         |
| Actual: 243 MW                 |
| IN RANGE                       |
| Hold:  ########..     71/90s   |
| Expiry:                  2:14  |
+--------------------------------+
```

Each has target, tolerance, hold duration, expiry, and a discrete
COMPLETE/EXPIRED outcome. Reuse the declarative condition schema already in
`src/data/shift_io.py` (`metric`/`target`/`op`/`value`) so the Shift Builder
authors them with **no new tooling**.

Order types the grid naturally supports:
- **Interconnector schedule** — hold INTC-N export at X MW ±tol
- **Reserve floor** — keep spinning reserve above X through the peak
- **Voltage hold** — keep a named bus above X pu for N minutes
- **Ramp compliance** — follow a demand ramp within a tolerance band
- **N-1 secure** — no single line loss may overload another
- **Economic** — meet demand under a cost ceiling

### 4.2 Why this matters more than it looks

COALCOM's genius is that **the order is always running.** There is no moment
where the player has nothing to attend to. GRIDCOM's quiet stretches are
currently *enforced* — there isn't even a fast-forward in PLAYING
(`SPEED_FAST`/`SPEED_VERY_FAST` exist at `constants.py:411-413` and are bound
**only** in CONTINUOUS at `main.py:1312-1317`).

### 4.3 Overlapping orders — the pressure dial

The real escalation axis. Not bigger grids — **overlapping obligations.**
Shift 2 has one order at a time. Shift 9 has three, and they conflict: the
interconnector schedule wants MW you need for the reserve floor, and the
voltage hold wants MVAr from the unit providing both.

**Difficulty comes from conflict between simultaneous goals, not from grid
size.** This is the axis the campaign currently ignores entirely.

### 4.4 The "phone call" — narrative pressure

1994 control room. A teleprinter chatters. **The order arrives as a message
from someone**, in-fiction — the system operator, a neighbouring control area,
a generator asking to come off early. Same mechanic, enormously more character,
and it costs nothing but writing.

> **Engine 4 summary:** guarantees the game is never dead air. Cheap, reuses
> existing tooling, composes with every other engine.

---

## ENGINE 5 — MASTERY
### *"I'm better at this than I was"*

You named this explicitly: *"the increased mastery that you gain by playing
more and more."* This engine is about making improvement **visible**.

### 5.1 Score what the game teaches

Today's grade (`main.py:157-165`, duplicated verbatim at `main.py:1084-1091`)
is frequency-% with binary gates. **Voltage, line loading, unit trips and
alarms are computed, printed on the debrief, and ignored by the grade.**
Shift 4 is entirely a voltage shift and voltage does not affect its result.

COALCOM's three-axis structure, mapped:

| Axis | Weight | Source |
|---|---|---|
| **Dispatch compliance** | 50% | orders completed / expired (Engine 4) |
| **System security** | 30% | frequency band %, min voltage, max loading, trips |
| **Operating efficiency** | 20% | fuel cost, unit starts, losses (Engine 1.3) |

The point is not the numbers. It is that **you cannot maximise all three** —
the tension is between the score components, exactly as in COALCOM.

### 5.2 Make the ceiling visible

A grade tells you *what* you got. Mastery needs *how much better is possible*:
- **Per-shift best score**, always shown — beat your own record.
- **A theoretical optimum** for the shift, computed offline. "Best possible:
  9,410. You: 7,220." Now the player knows there's room.
- **Medals for style**: no load shed, no unit trips, never left the band, under
  cost target. Orthogonal goals give expert players new things to chase in
  content they've already beaten.

### 5.3 The debrief as teacher

COALCOM teaches through §11 of its manual. GRIDCOM should teach through the
**debrief**: a chronological timeline of what happened, what you did, how long
you took, and — critically — **what the alternative was.**

> *"T+152 L01 tripped. L09 was open. 340 MW lost for 4 minutes.
> Closing L09 at any point before T+152 would have prevented this."*

That single line does more teaching than any tutorial alarm, and it makes the
next attempt feel like *your* idea.

### 5.4 Replay as a first-class feature

With seeded runs (Engine 3.4) and a real score, **replaying a shift to beat
your grade** is where mastery lives. It costs almost nothing once scoring
exists, and it is the entire reason people replay COALCOM shifts.

> **Engine 5 summary:** converts activity into progress. Without it, none of
> the other four engines are *legible* as improvement.

---

# PART 2 — PUSHING THE ENVELOPE

*Ideas that trade realism for fun, permitted by the brief. Ordered from
"clearly good" to "deliberately provocative."*

## 2.1 Compress the fleet, not the grid ⭐⭐

**The single most under-considered idea in this document.**

GRIDCOM's instinct so far has been to escalate difficulty by growing the grid:
9 buses → 28 → 40. But bus count is the **weakest** difficulty axis available —
more buses mean more to read, not more to decide.

Invert it. **Keep grids small and make every unit matter.** A shift with 6
units where each has a distinct personality — the immovable nuclear, the slow
cheap coal, the fast expensive hydro, the pumped-storage battery, the
unpredictable wind farm — is far more interesting than 25 interchangeable
units.

**Fewer, more characterful objects. This is how board games work, and it is
almost always right.**

## 2.2 Make pumped storage the star ⭐

Two `HYDRO_PUMP` units sit in the fleet, essentially unused. A machine that
**consumes** power to store it and **releases** it later is:

- a battery the player charges and discharges,
- a reason to care about *cheap hours* vs *expensive hours*,
- an instant reserve if you kept it charged,
- **and a resource you can run out of** — the best kind.

"Do I spend the reservoir now to cover this dip, or hold it for the evening
peak I can see coming?" **That is a great decision and the engine already
supports it.** This is the closest thing GRIDCOM has to a signature mechanic
nobody else in the genre uses.

## 2.3 Speed up the world, not the physics

`TIME_COMPRESSION = 24.0` means a 3.2-hour shift is 8 real minutes. But the
*interesting* events are sparse within it. Rather than slowing physics, **make
the world denser**: more orders, more contingencies, more decisions per
sim-hour than a real control room would ever see.

**A real dispatcher has a quiet shift. A GRIDCOM dispatcher should have the
worst shift of their career, every time.** That is the licence the brief grants,
and it is exactly what COALCOM does — no real plant has four faults in twelve
minutes.

## 2.4 The cascade as a boss fight

The cascade code is the best-implemented and least-used system in the project
(BFS islanding, rebuild-and-resolve within a tick, blackout zones). Today a
cascade is a fail state.

**Make it a fightable sequence instead.** Line trips. You have seconds before
the next overload trips. Shed load here, or trip that line deliberately to
island a section and save the rest. Each choice costs something permanent.

**Deliberate islanding as a *player tool*** — sacrificing a region to save the
system — is genuinely dramatic, genuinely what real operators do in extremis,
and completely absent. `trip_line` already exists (`simulation.py:699`).

## 2.5 The 30-second window

COALCOM's faults have a clock: *"Feedwater pump trip — approximately 10 seconds
before trip."* That number **is** the tension.

Give GRIDCOM's events explicit, visible countdowns wherever possible. The
overload countdown already exists (`renderer.py:818`) and is exactly right —
**it should be the template for everything.** A visible clock on a specific
object the player can act on is the cheapest, most reliable tension mechanic in
games.

## 2.6 Asymmetric information — the broken instrument

COALCOM has "Drum Level Sensor Malfunction — trust the trend, not the number."

**A dispatcher's nightmare is a telemetry failure.** A bus stops reporting.
A line's flow reading freezes. You must infer state from its neighbours. This
is thematically perfect for 1994, technically cheap (mask a value in the state
snapshot), and it makes the player *think about the network* rather than read
numbers off it.

## 2.7 The weather front

One authored, visible, moving event: a storm crossing the map. Wind output
surges then collapses. Lines trip probabilistically in its path. Demand rises
behind it as temperature drops.

**A single mechanic that creates a whole shift's arc**, telegraphed well in
advance so it is pre-positioning, not ambush. Extremely high fun-per-line-of-
code, and the renewables model already supports the wind half.

## 2.8 Named, persistent adversaries

A specific coal unit that trips more than it should. A line that is "known
dodgy." A neighbouring control area that under-delivers on schedule.

**Give the grid personality and memory.** Players remember characters, not
buses. "RIVE-2 again" is a better story than "unit trip event."

## 2.9 Deliberately unrealistic: the reputation meter

Push the envelope properly. **Blackouts have consequences beyond a grade.** A
persistent standing that opens or closes options: keep the lights on and you
earn discretion — the ability to refuse an order, request maintenance, decline
an interconnector schedule. Fail and you're micromanaged, forced to accept
every order at short notice.

Not remotely how a TSO works. **A great progression system**, and it makes the
campaign a story about a career rather than ten disconnected shifts.

## 2.10 Deliberately unrealistic: sabotage the automation

The 1994 framing invites it. **AGC itself becomes unreliable.** A shift where
the regulator is misbehaving — hunting, saturating silently, or off entirely
for maintenance — forces the player into full manual for a stretch.

This is Engine 2's manual-control fun **delivered as an authored crisis**
rather than a permanent design decision, which neatly sidesteps the whole
realism objection: AGC is normally on because that's real, and the drama comes
from the shift where it isn't.

---

# PART 3 — HOW THE ENGINES COMBINE

## 3.1 Compatibility

| | Resistance | Agency | Dread | Tempo | Mastery |
|---|---|---|---|---|---|
| **Resistance** | — | ✔✔ strong | ✔✔ strong | ✔ good | ✔✔ needs it |
| **Agency** | ✔✔ | — | ⚠ tension | ✔✔ strong | ✔✔ |
| **Dread** | ✔✔ | ⚠ tension | — | ⚠ tension | ✔✔ |
| **Tempo** | ✔ | ✔✔ | ⚠ tension | — | ✔✔ needs it |
| **Mastery** | ✔✔ | ✔✔ | ✔✔ | ✔✔ | — |

**The one real conflict: Agency/Tempo say *be busy*; Dread says *be watchful*.**
A shift cannot be both at once — but a *campaign* can alternate, and that
alternation is itself good pacing. Quiet dread-shifts make busy crisis-shifts
land harder.

**Resistance and Mastery are universal** — they improve every other engine and
conflict with nothing.

## 3.2 Three coherent games you could build

### Build A — "The Dispatcher" (Resistance + Dread + Mastery)
Small grids, characterful fleets, coupled levers, hidden risk, N-1 as the
primary lens, untrustworthy forecasts. Quiet, tense, judgement-driven. Most
authentic; builds directly on L09, the best thing already in the game.
**Fun is: *"I saw that coming."*** ✗ Will never feel like COALCOM.

### Build B — "The Control Room" (Agency + Tempo + Resistance + Mastery)
AGC as an opt-in tool, rolling dispatch orders, overlapping obligations,
coupled levers, hand-flown frequency. Busy, skill-based, mastery-driven.
**Fun is: *"I can fly this thing."*** ✗ Departs from dispatcher realism —
permitted by the brief.

### Build C — "The Bad Night" (all five, alternating) ⭐
The campaign alternates deliberately. Quiet foresight shifts where you
pre-position against risks that may never fire, punctuated by crisis shifts
where AGC fails, the storm arrives, and you hand-fly a cascade. **Resistance
and Mastery run throughout.**

**This is my recommendation.** It uses everything, it lets each shift have a
distinct identity, and *alternation is itself a pacing mechanic* — the thing
GRIDCOM most lacks. It also means the B-vs-C fork never has to be resolved in
the abstract: build one of each and playtest which one you enjoy authoring.

---

# PART 4 — SEQUENCING

**Nothing here is committed.** Rough dependency order if pushing forward:

### Foundation — do first regardless of direction
Every item is more physically honest, discards nothing, and is wanted under
all three builds.

1. **P-Q coupling** (1.1) — welds the two pillars into one system
2. **Scoring that counts voltage and loading** (5.1) — makes existing content
   matter; also de-duplicates the rubric currently living in two places
3. **Seeded RNG** (3.4) — reproducible runs; prerequisite for fair scoring
4. **Speed control in PLAYING** (4.2) — quiet stretches stop being enforced
5. **Enforce min-up/min-down** (1.4) — free, constants already authored

### Then — one experiment per engine, playtest before committing
6. **One dispatch order** in Shift 1 (Engine 4) — does the metronome help?
7. **One AGC-off stretch** (Engine 2.10, as an authored crisis) — is manual fun?
8. **One unannounced latent risk** (Engine 3.2) — does dread land?
9. **Pumped storage as a real decision** (2.2) — is the battery the signature?

### Then — build out whichever engine won
10. ZIP load, fuel cost, thermal line ratings, the risk economy, order
    overlapping, the debrief timeline, medals and replay.

**Author one shift per candidate engine before committing to any of them.**
The tooling (Grid Designer, Shift Builder, AST round-trip) is already
excellent and this is exactly what it's for. Playtesting three prototype
shifts is far cheaper than picking wrong and rebuilding.

---

# PART 5 — THE HONEST ANSWER TO "IS THIS POSSIBLE?"

Yes — and the reason is that **the expensive parts are already done.**

The simulation is good. The authoring tooling is exceptional. The aesthetic is
committed and coherent. Shift 1 is well-designed content with a genuinely
great beat in it. The fleet is a rich toybox that hasn't been opened.

What's missing is not simulation, not content volume, and not polish. It is
that **the player's decisions don't cost anything, don't conflict with each
other, and aren't measured.** All three are fixable, and none require touching
the physics you've already got right.

The reframe worth holding onto:

> **COALCOM's fun is *"I can fly this thing."***
> **GRIDCOM's L09 fun is *"I saw that coming."***

Both are real. Both are achievable here. And Build C says you don't actually
have to choose — a campaign has room for both, and the contrast between them
is itself the pacing GRIDCOM is missing.

The one thing I'd argue against is adding Shifts 6–10 in the current structure.
That would produce more of something that isn't yet fun. **The resistance,
the agency, and the scoring come first — then the content, built on top of a
loop that works.**
