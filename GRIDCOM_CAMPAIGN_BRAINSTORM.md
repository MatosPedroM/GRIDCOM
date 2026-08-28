# GRIDCOM Campaign Brainstorm — Narrative Arc & Event Typology

**Status:** Brainstorming draft, not locked. Feeds into future per-shift design sessions (starting with Shifts 1-2, already scoped separately). Nothing in this document is implemented yet.

**Scope decisions locked for this brainstorm** (from developer Q&A, 2026-08-27):
- Campaign spans weeks/months of in-fiction time (a career arc), not one continuous day.
- Drama stays purely operational — no institutional/political subplot. VPC/NECC stay background flavor.
- Difficulty escalates on *time pressure and overlapping problems*, not just grid size — the event typology below is designed with explicit compounding in mind.
- Designer-grid names (RIVE/CLOV/OAKE/Riverside/Cloverstead/Oakendale, etc.) are canonical going forward. `GRIDCOM_INTRO_STORY.md`'s short-story place names (Centrefield-Midbury, Kelmore, Wrentham, RVSD) and `shift10.json`'s finale-only names (Hartwell, Stourbrook, Portreath) are both superseded — treat as a documentation cleanup to do later, not a code change now.
- Shifts 8-10 will run on `grid_large.json` (fixing the current `GRID_SOURCE='grid_big'` dead reference). `shift10.json` is retired as a source of truth for buses/units; its narrative beats (storm corridor, nuclear-as-wall, industrial voltage risk) get re-expressed against `grid_large.json`'s actual buses.
- A new `LINE_DERATE` scripted action is planned (small engine addition, not yet built) to close the one real gap found in this session's follow-up: line thermal ratings are currently static (`rating_mw` is read once, straight off the `Line` object, only inside `loadflow.py`'s solve — no per-tick override path and no scripted action touches it today, unlike generation units which already have `UNIT_DERATE`). See Part 2's B5 entry and Part 2.5's Weather Regime tier for its exact shape.
- A new **Weather Regime** typology tier is added (Part 2.5): single authored causes (heatwave, cold snap, wind storm, calm/still system) that bundle 2-3 existing single-target archetypes under one handover-notes narrative, giving physically-motivated compounding for free rather than hand-stitching unrelated events together.
- **Correction:** Phase 1 planning (the pre-shift unit-scheduling screen) is confirmed to be wired to Shift 10 only today — `shift_05.py` is still a stub and does not set `USES_PLANNING`. The original draft of this document stated planning "is introduced" at the Shift 5 jump as though that wiring already existed; it doesn't. The developer confirmed Shift 5 remains the intended home for it (see Part 1) — this is scoped future work, not a correction to the plan itself.

---

## Part 1 — Campaign Narrative Arc

### The shape of the career

Not a single day — a dispatcher's first season at NECC, told in ten shifts spaced across weeks. Time passes between shifts (a line in the handover notes or logbook can mark this: "first shift back after four days off," "three weeks in," etc.) without needing a calendar UI. The throughline is competence, earned in public view of no one but the player — every past shift's near-miss is a thing *only the player remembers*, which is its own quiet stakes.

**Act I — Small Grid, First Weeks (Shifts 1-4, `grid_small`)**
The player is still new. RIVE-1 and two Oakendale hydro units are the whole world. The two out-of-service Riverside units (RVSD-2/3 easter egg territory) are a fixture of the handover notes — "still not signed off" — a running joke/texture item that never resolves, because it never needs to. Each shift adds one real new capability (per `GRID_SIMULATION_MECHANICS.md`'s Level 1→2 progression) and one new *kind* of problem, in isolation, cleanly resolved. By Shift 4 the player has independently handled: manual frequency correction, a cold start, a working N-1 contingency, and a real overload threat. Nothing here should be able to fail catastrophically — the stakes are competence, not survival.

**The Jump — Shift 5 (`grid_medium`, first shift on the new grid)**
A promotion/reassignment beat, told entirely through the handover notes and boot sequence (new topology loading, more units, unfamiliar bus names) — no cutscene needed, the terminal boot screen *is* the narrative device (as established in the intro). This is deliberately disorienting in a *good* way: same skills, much bigger board. Phase 1 planning (the pre-shift unit-scheduling screen, `display/planning.py` + `gameplay/phase1.py`) is intended to be introduced here — a board this size can no longer be safely improvised from a cold start, so the game teaches the player to plan because the grid itself now demands it — but **this is not yet wired up**: `USES_PLANNING` is currently `True` only on `shift_10.py`; `shift_05.py` is still a stub with no such flag declared, and `planning.py`'s own module docstring claiming "currently Shift 5" is stale leftover text from an earlier design pass. Setting `USES_PLANNING = True` on `shift_05.py` (confirmed by the developer as the intended home for this, 2026-08-27) is real, scoped future work — Shift 10 already proves the planning screen works end-to-end, so this is a wiring/content task, not new engine work.

**Act II — Full Competence, Real Stakes (Shifts 5-7, `grid_medium`)**
The player is now a working dispatcher on real infrastructure: nuclear baseload (Cloverstead), CCGT, a wind and solar farm, more hydro. This act is where uncertainty enters for real (renewables noise was always present, but at this scale it matters) and where the random derate/drift mechanism starts being narratively meaningful rather than a curiosity. Voltage/reactive management (Level 3) and regional/islanding awareness (Level 4) land here. By Shift 7 the player has independently carried a full shift with overlapping minor problems — not one clean lesson each, but two or three low-grade issues at once.

**The Jump — Shift 8 (`grid_large`, first shift on the big grid)**
Same device again — a bigger board, more of everything, told through the boot sequence. Narratively this can be framed as the player now trusted with the *whole* network (INTC-N/INTC-S interconnectors become real here, not flavor), or a second promotion. No institutional reason needs to be given — the grid grows because the player has earned the grid growing.

**Act III — Mastery Under Pressure (Shifts 8-10, `grid_large`)**
Full market-adjacent complexity (multi-reservoir hydro coordination, full merit-order-adjacent judgment calls even without a real cost model) and — critically — this is where events start to *compound* rather than arrive one at a time. Shift 9 in particular should feel like "a normal hard day," proving the player can carry sustained, unglamorous competence, not just handle one big scripted crisis. Shift 10 is the storm finale: not a new kind of problem, but every problem type the player has learned, arriving faster and overlapping, on the biggest board, during weather. The win condition is not "solve something new" — it's "everything you already know, all at once, without enough time to think about each thing individually." This matches the existing shift_10.py docstring's stated intent almost exactly; it just needs to run on `grid_large.json`'s real buses instead of the orphaned `shift10.json`/dead `grid_big` reference.

### Per-shift narrative one-liners (replacing the existing single-day-framed lines)

These replace `GRIDCOM_INTRO_STORY.md` §7's `SHIFT_INTROS` dict, keeping the terse logbook-entry format but reframing for a multi-week career instead of one day:

```
SHIFT 1   "First night alone. Commenced watch."
SHIFT 2   "Second night. Same board, thinner margin."
SHIFT 3   "Three weeks in. First real contingency you'll call yourself."
SHIFT 4   "A month in. They're trusting you with the board when it's not quiet."
SHIFT 5   "New assignment. Full board. Everything is bigger than it looks on paper."
SHIFT 6   "Getting the feel of it. Islands and restoration — know your sequence."
SHIFT 7   "Reactive power doesn't forgive guesswork. Neither do the substations."
SHIFT 8   "Second promotion. The interconnectors are yours now too."
SHIFT 9   "An ordinary hard day. No fireworks — just don't let anything slip."
SHIFT 10  "Storm inbound. Everything you know. All at once."
```

---

## Part 2 — Event Typology

Every archetype below is built from existing engine primitives (confirmed this session): the deterministic `SCRIPTED_EVENTS` list (`trigger_min` + optional `condition` + `action`, sampled once, does not re-arm), the always-on random derate/drift roller (independent per-unit dice roll, seeded, tunable via `DIFFICULTY_MULT`), and `DEMAND_OVERRIDE` (a deterministic, pre-authored demand curve override) — **with one exception**: B5 (line thermal derating, below) needs one small new action type, `LINE_DERATE`, since nothing in the engine today makes a line's rating dynamic. Every other archetype is a pure authoring exercise against what already exists, no engine changes needed.

Each archetype lists: what it teaches/stresses, which engine mechanism realizes it, a difficulty/grid-size note, and its compounding potential (per the developer's chosen "overlapping problems" difficulty axis).

### A. Generation-Unit Events

**A1 — Unplanned Derate**
A unit silently loses part of its capacity mid-shift (mechanical fault, fuel-quality issue, fuel-type-flavored reason text already exists in `constants.py`'s `RANDOM_DERATE_REASONS_*` pools).
- *Mechanism:* the existing random-derate roller (free, already fires probabilistically) for organic/background texture; a scripted `UNIT_DERATE` action for a *guaranteed, story-important* derate (e.g. "this must happen in Shift 3 for the lesson to land").
- *Teaches:* reserve margin awareness, redispatch under a shrinking ceiling.
- *Scales by grid:* trivial on `grid_small` (2-3 online units, an obvious redispatch target); becomes a real judgment call on `grid_large` (which of 8 online units do you lean on instead, given fuel type / ramp rate / Q headroom).
- *Compounds with:* B-series line events (derate one corridor's supply while its parallel line is also stressed) or C1 demand spikes (less capacity right when you need more).

**A2 — Forced Trip**
A unit drops to zero instantly (protective trip, not a graceful derate).
- *Mechanism:* scripted `UNIT_TRIP` action (deterministic, for narrative moments); can be condition-gated (e.g. only trips if the unit was already running hot/near its limit, using `UNIT_OUTPUT_MW` as the condition) so the player's own dispatch choices determine whether it happens.
- *Teaches:* the sharpest version of "AGC/frequency response under sudden loss," spinning reserve as a real number rather than an abstraction.
- *Scales by grid:* on `grid_small`, losing RIVE-1 is existential (it's 75%+ of the fleet) — reserve this for a deliberately dramatic single beat, not routine use. On `grid_medium`/`grid_large`, losing one CCGT or coal unit among many is exactly the "can the fleet absorb this" lesson Level 1-2 vs. Level 4 difficulty is meant to separate.
- *Compounds with:* almost everything — the classic "second problem lands while you're still recovering from the first" anchor event for late-campaign shifts.

**A3 — Slow-Motion Commitment Deadline**
A cold, offline unit with a long `cold_start_min` (CCGT 60min, COAL 240min, NUCLEAR 480min) is telegraphed as *necessary later this shift* well in advance, and the player must decide when to start it.
- *Mechanism:* pure `HANDOVER_NOTES`/`INITIAL_SCHEDULE` authoring (start the unit offline, tell the player why in the notes) plus a `DEMAND_OVERRIDE` or natural profile ramp that makes the deadline real; optionally a `TIME_MIN`-conditioned TUTOR/WARNING alarm as a countdown reminder.
- *Teaches:* forward planning, the actual cost of "I'll deal with it later" — this is the purest expression of unit-commitment-as-a-decision (Level 2) and, at `grid_large` scale, of Phase 1 planning mattering (get the timing wrong in the plan, live with it in real-time).
- *Scales by grid:* the natural site for RIVE-2/3's 240-min start once they're ever un-mothballed (a satisfying long-term payoff for the running easter-egg joke); at `grid_large`, Stourbrook/Downside-class coal or Hartwell-class nuclear-equivalent commitment decisions carry the whole shift's planning stakes.
- *Compounds with:* A1/A2 elsewhere in the fleet (a derate or trip that eats into the margin you were counting on to cover the gap before the slow unit lands).

**A4 — Renewables Collapse**
Wind or solar output drops sharply and stays low (not the ambient noise — a real, sustained forecast miss).
- *Mechanism:* `DEMAND_OVERRIDE` doesn't apply to generation directly, but a scripted `UNIT_DERATE` on the wind/solar unit (capped near zero, held for the rest of the shift) achieves the same effect deterministically; ambient renewables noise (already always-on, 3%/1% std with smoothed random walk) provides the background texture version for free on any shift with wind/solar in the fleet.
- *Teaches:* the gap between forecast and reality, thermal/hydro backup as insurance rather than backup-in-name-only.
- *Scales by grid:* not present until `grid_medium` (first wind/solar units); becomes a headline mechanic by `grid_large` where wind/solar are large enough (100-165 MW combined) that their loss is a first-order event, not a rounding error.
- *Compounds with:* A3 (the slow unit you were slow-rolling now needed to start ten minutes ago) and C1 (a solar collapse at the exact moment evening demand ramps — the literal "duck curve" problem).

**A5 — Reactive/Voltage-Support Failure**
A generator hits its Q_max/Q_min limit and PV→PQ-converts, and voltage at a nearby bus starts sagging with no warning beyond the number itself.
- *Mechanism:* no scripted action needed — this is an emergent consequence of the existing decoupled voltage solver once a unit's Q output is pushed to its limit (by the player's own dispatch, or by a scripted `DEMAND_OVERRIDE` on a nearby INDUSTRIAL bus that raises reactive draw). A `VOLTAGE_PU` condition on the exposed bus is the natural WARNING/TUTOR trigger.
- *Teaches:* reactive power isn't free or infinite — Level 3 material, the mechanic `SHIFT4_VOLTAGE_INVESTIGATION.md` was originally built around.
- *Scales by grid:* first meaningful use once INDUSTRIAL-type substations with real reactive draw exist (`grid_small`'s BATH already qualifies); becomes acute at `grid_large` scale where several INDUSTRIAL buses (per the research, load-heavy substations analogous to shift10.json's Carrow/Sedgemere/Portreath/Trussington) can be scripted to stress different generators' Q reserves simultaneously.
- *Compounds with:* B1 (a line loss that changes which generator is electrically closest/responsible for supporting a given bus's voltage) — a strong late-campaign combination.

### B. Line Events

**B1 — Contingency Trip (N-1 Test)**
A single line trips — either on a redundant (parallel) corridor, where the lesson is "redundancy works, don't panic," or on a radial single-feed spur, where the lesson is "this bus is now islanded/at risk and you have limited time."
- *Mechanism:* scripted `LINE_OPEN` action, `trigger_min`-timed for a clean single-cause lesson, or condition-gated on `LINE_LOADING` of a *different* line to simulate a loading-triggered protective trip.
- *Teaches:* N-1 security literacy — the single most reusable lesson in the whole catalog, since every grid at every scale has both redundant pairs and single-feed spurs (confirmed: grid_small has 4 single-feed load buses, grid_medium has 10, grid_large has 18).
- *Scales by grid:* directly by count of single-feed buses available to threaten — trivial to keep re-using this archetype from Shift 2 through Shift 10 against a *different* bus each time without it ever feeling repeated, since the consequence (which loads go dark, which generator must respond) changes completely with grid position.
- *Compounds with:* almost anything — this is the connective tissue of "overlapping problems," since a line loss changes the whole board's power-flow picture and makes every other concurrent event harder to reason about.

**B2 — Weather-Driven Corridor Risk**
A named "storm corridor" or "high-wind corridor" telegraphed in the handover notes threatens a *specific pair* of parallel lines, and the player knows (from the notes) that the second circuit is now the only thing standing between a bus and islanding — then it may or may not actually trip.
- *Mechanism:* `HANDOVER_NOTES` sets up the tension; a scripted `LINE_OPEN` on the first circuit of a known parallel pair, `trigger_min`-timed, optionally followed by a second condition-gated `LINE_OPEN` on the surviving circuit later in the shift if the player hasn't redispatched away from relying on that corridor (condition on `LINE_LOADING` of the survivor).
- *Teaches:* proactive risk management under a warning, not just reactive response after the fact — a step up in maturity from B1 alone.
- *Scales by grid:* needs a real parallel-pair corridor with a clear "far side" load dependency — present at all three grid sizes, but most dramatic at `grid_large` (69 parallel pairs to choose from) where a whole regional cluster can depend on one corridor.
- *Compounds with:* the line-reclose-cooldown mechanic already built (`LINE_RECLOSE_COOLDOWN_S_BY_DIFFICULTY`) — a second strike on the same corridor while the first circuit is still in its cooldown window is the shift_10.py docstring's original two-lightning-strikes idea, and remains a strong late-campaign set piece.

**B3 — Sustained Overload (Player-Caused or Scripted)**
A line creeps toward and past 100% loading — either because the player's own dispatch choices routed too much power through it, or because a scripted event (a nearby trip, or a demand override on a bus behind it) forces more flow onto it.
- *Mechanism:* emergent from existing inverse-time/severity-scaled overload-trip logic (Session 35's F6) — no new mechanism needed; scripted events just need to create the *conditions* (e.g. B1 or C1 elsewhere in the network) that redirect flow onto the target line. A `LINE_LOADING` WARNING alarm is the natural player-facing signal.
- *Teaches:* reading F3's loading-bar report as an early-warning tool, not just a curiosity screen — directly validates the Shift 1 F3-teaching beat already planned.
- *Scales by grid:* present everywhere; difficulty comes from how much time the player has to notice and correct versus how fast the situation was set up to develop.
- *Compounds with:* B1 (the classic "trip elsewhere pushes a surviving line past its limit" cascade-precursor) — this pairing is the natural on-ramp to a controlled cascade/islanding teaching moment without an actual uncontrolled cascade needing to occur.

**B4 — Reclose Discipline**
After any line trip (scripted or player-caused), the player is tested on whether they wait out the reclose cooldown or attempt to force it early — teaching that closing a line back in is itself a decision with a timing cost, not a free undo.
- *Mechanism:* purely emergent from the existing `LINE_RECLOSE_COOLDOWN_S_BY_DIFFICULTY` mechanic once any B1/B2 event has fired; no new scripting needed beyond making sure a shift's pacing gives the cooldown window real weight (e.g. don't let a later scripted event resolve trivially fast if the player is mid-cooldown on the line that would have helped).
- *Teaches:* patience/discipline as a real operational constraint, first properly introduced (per its own docstring) in shift_10 — worth pulling earlier, into `grid_medium`, so it's not a brand-new mechanic sprung on the player in the finale.
- *Scales by grid:* cooldown duration itself already scales by voltage tier and difficulty; no change needed per grid.
- *Compounds with:* B1/B3 directly (you can't just reclose your way out of an overload the instant it's inconvenient).

**B5 — Thermal Derate (engine gap — needs `LINE_DERATE`)**
Sustained high ambient temperature reduces a line's real carrying capacity below its nameplate rating — the "same line, less headroom" version of A1's generator derate.
- *Mechanism:* **does not exist yet.** Confirmed this session: `rating_mw` is a fixed value read directly off the static `Line` object, only inside `loadflow.py`'s load-flow solve — there is no per-tick override, and no scripted action touches it (unlike generation units, which already have `UNIT_DERATE`/`FleetModel.derate_unit()`). Needs one small, scoped addition mirroring the existing generator pattern exactly:
  - A new scripted action `{'type': 'LINE_DERATE', 'line': <label>, 'cap_mw': <absolute value>}`, handled in `_execute_action()` alongside `UNIT_DERATE`.
  - A `derate_line(label, cap_mw)` method on whatever owns line state (mirrors `FleetModel.derate_unit()`), storing a per-line effective-rating override.
  - `loadflow.py`'s solve reads the effective (possibly overridden) rating instead of `line.rating_mw` directly wherever it currently reads `rating_mw` — same shape as `derate_unit()`'s "stays online, ceiling reduced" behavior, just for a line's rating instead of a unit's output.
  - Matching scripted `UNIT_DERATE` precedent: a scripted `LINE_DERATE` should be **permanent for the shift** unless explicitly cleared — so a `LINE_RESTORE` counterpart (mirroring `LOAD_RESTORE`) is worth adding at the same time, for shifts that want to signal "the heat's broken, headroom is back."
- *Teaches:* that a line's rating isn't a fixed number to memorize once — the same corridor can mean different things on a cold night versus a heatwave afternoon, and F3's loading-bar reading habit (already taught early) pays off differently when the ceiling itself has moved.
- *Scales by grid:* works at any scale; most legible when paired with C4's residential heat-driven load spike on the far side of the same derated line (see Part 2.5) so the player feels both ends of the squeeze at once.
- *Compounds with:* C4 directly (same cause, two channels) and B3 (a derated line reaches its now-lower ceiling far sooner than the player's mental model of its nameplate rating expects) — this is the flagship example of why the Weather Regime tier (Part 2.5) exists.

### C. Load-Bus (Demand) Events

**C1 — Demand Spike/Miss**
Actual demand at one or more buses departs sharply from the deterministic profile curve — an industrial customer's unscheduled large draw, a scripted local squeeze not tied to a specific weather cause.
- *Mechanism:* `DEMAND_OVERRIDE` scripted action — a sparse hour→MW table, linearly interpolated, exactly the mechanism designed for this. Since base demand has zero built-in forecast error (confirmed: `demand.py` is fully deterministic), this is the *only* way to create a demand surprise, which makes it a clean, fully author-controlled lever.
- *Teaches:* the most basic "the plan met reality" lesson — ideal as an early-campaign beat (Shift 1's spine beat is already exactly this shape) and still valid at any later scale as a compounding pressure.
- *Scales by grid:* scales trivially — override one bus for a local effect (single substation squeeze) or override system-wide peak for a global one (a real test of total fleet headroom).
- *Compounds with:* A1/A3 (less capacity available right as demand needs more) and B3 (a local spike that pushes the feeding line toward overload) — C1 is probably the single most compounding-friendly archetype in the whole catalog, since it's the one thing that can be dialed to affect the *whole board* rather than one element.

**C4 — Temperature-Driven Residential Load Spike**
Both extreme cold *and* extreme heat push residential demand well above the normal profile curve at the same time — cold snaps via heating load, heatwaves via air-conditioning load — a genuinely two-tailed effect rather than a single-direction miss.
- *Mechanism:* `DEMAND_OVERRIDE`, same primitive as C1, but authored specifically against RESIDENTIAL-type buses and specifically framed (in handover notes and in the shift's temperature-regime label) as a *temperature* effect rather than a generic "unscheduled draw" — the distinction from C1 is purely narrative/targeting discipline, not a new mechanism, but worth cataloging separately because it is the load-side half of a Weather Regime (Part 2.5) and should always be authored paired with something on the generation or line side, never alone.
- *Teaches:* residential load's sensitivity to weather specifically (as opposed to C1's generic "a customer changed their behavior" framing) — sets up the intuition that weather is a system-wide variable touching multiple things at once, which the Weather Regime tier then pays off directly.
- *Scales by grid:* trivial at any scale — more RESIDENTIAL buses exist at `grid_medium`/`grid_large`, giving room to hit several at once for a system-wide heat/cold event rather than one local bus.
- *Compounds with:* B5 (the flagship pairing — heat raises AC load on residential buses while simultaneously derating the line that feeds them) and A1 (cold snaps stressing thermal units' own output at the exact moment heating load peaks).

**C2 — Load Shed Under Duress (the "no good options" beat)**
A genuine supply shortfall (stacked A2+A1+C1, for instance) leaves the player needing to shed load deliberately rather than finding a way to avoid it — a lesson that sometimes the correct action is triage, not heroics.
- *Mechanism:* no new scripting primitive — this is a *consequence* state reached by compounding other archetypes tightly enough that total online capacity genuinely cannot cover demand; the existing `LOAD_SHED`/`LOAD_RESTORE` player actions and scoring's `load_shed_events` axis are what make this legible and gradable. A shift can optionally pre-author a `LOAD_RESTORE`-timed scripted event once the crisis window passes, to signal "you're through it," rather than leaving restoration entirely manual.
- *Teaches:* triage judgment and the maturity to accept a bounded loss rather than risk an uncontrolled one — this is arguably the campaign's terminal lesson, appropriate for Shift 9 or 10 rather than anything earlier, since `grade_shift()` treats any shed event as a real demerit and it shouldn't be trained as a routine response.
- *Scales by grid:* needs a big enough fleet/demand base that "shed 25% of one substation" is a meaningful, boundable choice rather than an instant fail state — safest at `grid_medium`+ scale.
- *Compounds with:* is itself the compounding *result* of A1/A2/A3/C1 stacked together, more than a standalone archetype — treat it as the deliberate "boss fight" payoff state that heavy compounding is building toward in Acts II-III.

**C3 — Substation Reactive Character (Industrial vs. Residential)**
Distinguishing WARN/INDUSTRIAL-type buses (poor power factor, high reactive draw) from RESIDENTIAL ones as a standing, ambient difficulty texture rather than a discrete "event."
- *Mechanism:* already fully live via `substation_type`/`SUBSTATION_TYPE_PF` — no scripting needed, but worth deliberately *choosing* which buses a shift stresses (via C1 or A5) based on their type, so INDUSTRIAL buses are the natural target whenever a voltage-support lesson (A5) is wanted, and RESIDENTIAL buses are the natural target for a pure-MW demand lesson (C1) without the added reactive complication.
- *Teaches:* reading the bus type as informative before an event ever happens — rewards attentiveness.
- *Scales by grid:* more INDUSTRIAL buses appear at larger scale (BATH alone on `grid_small`; several more by `grid_large`), giving late-campaign shifts room to stress multiple industrial buses at once as a compounding voltage-management challenge.

---

## Part 2.5 — Weather Regimes (multi-target compounding, by design)

Everything in Part 2 targets one unit, one line, or one bus. A **Weather Regime** is a single authored cause — telegraphed once, in the handover notes, as a named condition rather than a discrete event — that touches two or three targets at once through genuinely different physical channels. This is not a new mechanism; it's a naming/authoring discipline that bundles existing archetypes (plus the one new `LINE_DERATE` primitive) so that compounding arises from *one real-world cause* rather than from two unrelated scripted events happening to land near each other. This is the most direct answer to the developer's "the difficulty curve should be overlapping problems, not just bigger grids" instruction from the original brainstorm.

**Heatwave**
- C4 (residential AC-driven load spike, on RESIDENTIAL buses) + B5 (thermal derate on the line(s) feeding the hottest area, or on the longest/most exposed corridor) fired together, same `trigger_min`, one shared handover-notes paragraph ("ridge of high pressure... expect demand 10-15% over profile on residential load, and treat the [corridor] as running at reduced capacity").
- Optional third layer at higher difficulty: A1 (thermal unit derate — coal/CCGT cooling-water or ambient-derate flavor text already exists in `RANDOM_DERATE_REASONS_COAL`/`_CCGT`) on a generator near the affected corridor, making the supply side *and* both demand-side channels squeeze at once.
- *Best fit:* Act II onward (`grid_medium`+) once RESIDENTIAL buses and a meaningful corridor exist together; a strong Shift 7-9 candidate.

**Cold Snap**
- C4 (residential heating-driven load spike) + A1 (thermal/hydro unit derate — cold intake water, frozen instrumentation, or similar flavor text) — no line-derate channel needed here (cold doesn't reduce line rating the way heat does), so this regime is deliberately a *two*-channel one, slightly gentler than Heatwave's three-channel version.
- *Best fit:* earlier than Heatwave — works even at `grid_small` scale (Shift 1's own spine beat is already halfway to this shape; a future revision of Shift 1/2 could explicitly reframe it as "first cold snap" for free narrative coherence).

**High-Wind Storm**
- A4 (wind generation collapse — paradoxically, turbines cut out entirely above their design wind speed, not just underperform; worth noting explicitly in flavor text as "turbines feathered/shut down for their own protection above cut-out speed" so the player learns this isn't a forecast miss but a real operational limit) + B2 (elevated line-trip risk on exposed corridors, already cataloged) fired together under one storm-front narrative.
- This is the existing shift_10.py docstring's storm concept, generalized into a reusable regime rather than a one-off finale idea — usable earlier (`grid_medium`, once wind exists) at lower intensity (one corridor, one wind farm) before the finale's full-intensity version (multiple corridors, reclose-cooldown chaining via B4).
- *Best fit:* any shift with wind generation once introduced; intensity scales with act.

**Calm / Still System (low-wind lull)**
- The quiet-seeming twin of the storm: A4's *other* tail — wind output drops to near zero not from a storm but from a persistent lull, with no dramatic trip to react to, just a slow, sustained hole in generation that must be covered by dispatch alone (A3's "slow unit must be started in time" pressure is the natural partner, since a calm system is forecastable hours ahead, unlike a sudden trip).
- Deliberately the *low-drama* weather regime — good for teaching that not every problem announces itself with an alarm; some are just "the number on the wind farm's panel quietly staying low all shift."
- *Best fit:* Act II, as a contrast beat against the louder storm/heatwave regimes — a good candidate for whichever `grid_medium` shift is meant to feel like "an ordinary day with one real planning lesson," rather than a crisis shift.

**Authoring note:** a Weather Regime should always be introduced through `HANDOVER_NOTES` as a *forecast*, before any of its component archetypes fire — the player should know a heatwave/storm/cold snap/calm system is expected for the shift before the first scripted event lands, exactly as B2 already does for a single corridor. This is what separates a regime from a coincidence: the player had the information and the compounding was, in principle, plannable for.

---

## Part 3 — Compounding Guidance (the difficulty curve itself)

Since the developer chose to design explicitly for overlapping/compounding events rather than pure grid-size scaling, here is the shape that implies act-by-act:

- **Act I (Shifts 1-4):** exactly one archetype active at a time, always resolved before the next begins. `trigger_min`-spaced with generous gaps. This is deliberate — the lesson is the archetype itself, not the overlap.
- **Act II (Shifts 5-7):** two archetypes may be live at once by Shift 6-7, but one is always the "headline" (scripted, clearly signposted) and the other is ambient/background (renewables noise, an A1 random derate rolling naturally) — the player starts learning to triage attention, not yet under acute time pressure.
- **Act III (Shifts 8-10):** deliberate compounding chains become the content itself — B1→B3 (trip redirects flow, pushes another line toward overload), A4→A3 (a renewables collapse forces an early commitment decision on a slow unit), C1→A5 (a demand spike exposes a reactive-support gap), and full Weather Regimes (Part 2.5) rather than hand-paired single archetypes — a three-channel Heatwave or full-intensity High-Wind Storm is the natural Shift 10 shape. Shift 10 is the only shift that should stack three or more archetypes within a short window with minimal warning, matching its existing "brutal, no eased-in opening" design intent.

A practical authoring rule this suggests: **every event beat from Shift 6 onward should be designed by picking two archetypes from the catalog and asking "what does the second one make harder about responding to the first," not by inventing a new standalone scenario.** This keeps the catalog genuinely reusable rather than needing a fresh idea per shift.

---

## Open Items for Next Session

1. This document does not yet assign specific archetypes to specific shifts beyond the act-level shape above — that mapping (and all `trigger_min`/threshold tuning) is the natural next step, likely per-shift or per-act rather than all at once.
2. The `grid_large.json` → `GRID_SOURCE='grid_big'` reference fix (Part 1's locked scope decision) is a real, small code/config fix independent of narrative content — worth doing early since Shifts 8-10 are unplayable until it happens.
3. The `LINE_DERATE`/`LINE_RESTORE` engine addition (B5, Part 2) is a real, small, scoped engine task — mirrors `UNIT_DERATE`'s existing pattern closely enough that it should be quick, but it is genuine code, not just authoring, and is a prerequisite for B5 and any Heatwave/Weather-Regime content that relies on it. Worth doing as its own small session before it's needed by a specific shift, the same way F1-F6 preceded Shift 10's authoring in `SHIFT10_BAD_NIGHT_PLAN.md`.
4. Renaming/retconning `GRIDCOM_INTRO_STORY.md`'s short-story place names and `shift10.json`'s finale names onto the designer-grid naming universe is a documentation cleanup, not urgent, but should happen before those docs are used as a reference again to avoid re-confusing a future session.
5. The per-shift narrative one-liners in Part 1 are a first draft matching the new career-arc framing — worth revisiting once actual per-shift content is designed, since the real events chosen may suggest better lines than these placeholders.
6. Wiring `USES_PLANNING = True` into `shift_05.py` (and building whatever `INITIAL_SCHEDULE`-equivalent Phase 1 flow that shift needs) is real, scoped work distinct from the event-typology content — Shift 10 already proves the planning screen end-to-end, so this is authoring/wiring, not new engine work, but it hasn't been done yet and shouldn't be assumed present when designing Shift 5's content.
