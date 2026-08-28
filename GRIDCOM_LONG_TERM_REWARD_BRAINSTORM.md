# GRIDCOM Long-Term Reward System — Brainstorm

**Status:** Brainstorming draft, wide option space. Nothing below is locked or implemented. Companion document to `GRIDCOM_CAMPAIGN_BRAINSTORM.md` (narrative arc / event typology) — this document covers a different question: how the player's accumulated performance across shifts should persistently benefit them, specifically toward coping with Shift 10.

## Context and Constraints

The developer wants a system where (1) good shift performance generates something, and (2) the player genuinely manages or allocates that something across the campaign to improve their odds at Shift 10. Two earlier passes at this converged on variants of "campaign-wide points, spent on per-unit maintenance," modeled loosely on a points system from a prior project (COALCOM). Both were rejected as insufficiently disruptive — refinements of one idea, not real alternatives. This document instead lays out several **structurally different** systems, most of which abandon the "points you earn and spend" shape entirely.

**Confirmed facts grounding every option below** (direct code reads, 2026-08-27/28):

- **No persistence exists anywhere in GRIDCOM today.** `src/gameplay/campaign.py` is a 0-byte stub. `shift_grades` (`main.py:565`) is an in-memory dict, populated once per shift at debrief, lost entirely on quit. **Every option below requires building a real save file** — this is unavoidable engineering work regardless of which direction is chosen.
- **`grade_shift()`** (`src/gameplay/scoring.py:65-154`) already computes five graded axes per shift — frequency, loading, voltage, trips, shedding — each on a five-tier scale (EXCELLENT → FAILED), plus an overall grade (worst axis wins). This is the raw material every option below scores against; none of them need a new grading system, only new uses for the one that exists.
- **Phase 1's per-shift EUR budget was built with long-term budget management in mind and can be removed entirely if replaced.** Confirmed in code: `src/gameplay/phase1.py`'s `PlanningModel` already has `budget_eur` (reset to `PLANNING_INITIAL_BUDGET_EUR` every shift), and already charges real costs against it — `STARTUP_COST_EUR_BY_TYPE`, `VARIABLE_COST_EUR_PER_MWH_BY_TYPE`, and, notably, **`AGC_AVAILABILITY_COST_EUR_PER_HOUR`** paired with a per-unit `agc_enrolled: dict[str, bool]` toggle. In other words, "pay extra to run a unit under AGC" is *already implemented* — it just resets to zero memory every shift. This is real, working infrastructure, not a proposal.
- **RIVE-2/RIVE-3 (the mothballed Riverside coal units) are not available as a reward payoff.** Confirmed directly against the grid files: `grid_small.json` (Shifts 1-4) has both `in_service: false`; `grid_medium.json` (Shift 5 onward) already has both `in_service: true`. They return automatically at the Shift 5 grid switch as a consequence of the campaign's own grid-progression design — no mechanic is needed or should be built around this.
- **AGC eligibility is `unit_type`-only** (`{HYDRO, CCGT}`, fixed campaign-wide), with an existing per-unit exclusion mechanism (`_agc_excluded_units` in `units.py`) driven today only by a scripted action — available as a hook for any option that wants to gate AGC participation dynamically.

---

## Option 6 — The Budget Becomes the Campaign

**Concept:** Delete the idea of a second, invented resource entirely. Stop resetting `budget_eur` to its default every shift — let it become one running, campaign-wide number. At each debrief, `grade_shift()`'s outcome adjusts it directly: a clean shift adds a bonus, a mediocre one adds little or nothing, a FAILED shift or a unit trip fines it. Every cost the Phase 1 planner already charges — unit startup cost, variable per-MWh cost, and AGC availability cost — continues to draw from this same total, except now it has memory across the whole campaign instead of resetting.

**Gameplay mechanics impact:**
- *Phase 1 planning screen:* unchanged in interaction — the player still builds an hourly schedule and watches a budget number. The only change is that the number they start each shift with is no longer fixed; it's whatever they've earned or burned through so far.
- *Unit commitment decisions:* become genuinely different in Shift 8 versus Shift 2 — a tight campaign-wide budget means fewer startable units, less AGC coverage the player can afford, forcing harder commitment tradeoffs exactly where the campaign wants them (Act III).
- *AGC enrollment:* the existing per-unit `agc_enrolled` toggle and its EUR cost become a real, weighted decision instead of a checkbox the player can freely tick every shift — "can I actually afford AGC on this unit today" becomes literal.
- *Debrief screen:* gains one new line — the budget delta from this shift, shown alongside the existing grade.
- *No new UI screen, no new resource to explain* — the player already understands EUR/cost from Shift 10's existing planner.

**Build cost:** low relative to the alternatives — this is mostly *removing* a reset and adding one persistence hook, not building a new mechanic. The real work is tuning: how much a grade moves the budget, and how tight it needs to get by Shift 10 to matter without becoming unwinnable from an early stumble.

**Risk:** a "death spiral" — a few bad early shifts could make Shift 10 mechanically harder through budget scarcity alone, independent of the player's actual skill by that point. Needs either a floor, a rubber-band catch-up mechanism, or deliberately generous variance to avoid punishing improvement.

---

## Option 7 — Trust, Not Money

**Concept:** Abandon numeric resources entirely. Campaign performance moves the player along an invisible **trust/autonomy axis**, and that axis changes what the *game* does around the player, not what the player owns. Strong, consistent shifts mean TUTOR-tier guidance thins out, safety-net generosity (wide `FREQ_TOLERANCE_MULT`, forgiving `sustained_s` on fail conditions) tightens toward realism, and the player gets earlier or freer access to riskier scripted content. Weak shifts mean the opposite — the game keeps more guardrails active longer, stays more forgiving on timing, and may hold back harsher Weather Regime compounding until standing improves.

**Gameplay mechanics impact:**
- *Difficulty is no longer purely the developer's static per-shift tuning* — it becomes a function of a rolling read on the specific player's demonstrated competence, layered on top of (not replacing) the existing `DIFFICULTY_MULT` trainee/standard/dispatcher selection.
- *TUTOR alarm frequency and content* changes across a playthrough — a strong player's later shifts have visibly less hand-holding than the same shift would show a struggling player, which is a rare and distinctive mechanic for this genre.
- *Shift 10 itself becomes adaptive* — a struggling player arrives at the finale with more scaffolding still active (gentler fail-condition timing, more guidance), a strong player gets the full, harsher intended version — directly serving "increase the odds of coping with Shift 10" by adjusting the finale to what the player has actually earned, rather than a single fixed difficulty for everyone.
- *No new screen at all* — this system is entirely felt through how forgiving or strict the game plays, never displayed as a stat.

**Build cost:** moderate — needs a rolling "standing" scalar derived from grade history (a simple moving average would do), and several existing tunables need to read from that scalar instead of being hardcoded per shift.

**Risk:** invisible systems risk not registering as a reward at all — without at least one visible signal (a debrief-screen line, e.g. "Standing: Senior — full autonomy"), the player may never notice anything is happening. This option also offers no direct allocation decision — the "management" is indirect (how you play shapes your standing) rather than an explicit spend, which is a weaker match to the developer's stated requirement that the player manage/allocate something, compared to Options 6, 8, and 9.

---

## Option 8 — The Draft

**Concept:** Borrow the roguelike/deckbuilder pattern of a rare, discrete choice instead of an accumulating currency. At each act transition (after Shift 4, after Shift 7 — matching the existing act structure in `GRIDCOM_CAMPAIGN_BRAINSTORM.md`), the player is shown a small set of mutually exclusive, permanent campaign-level choices — pick exactly one. Example shape: "Choose one for Act II — a second maintained hydro unit joins Oakendale, OR a standing AGC-eligibility waiver for a coal unit's type, OR a wider baseline spinning-reserve margin." How well the preceding act went determines the quality or number of options offered — a poor act might offer one weaker option instead of three good ones, expressing scarcity through worse choices rather than a smaller number.

**Gameplay mechanics impact:**
- *A new, rare screen*: an act-transition choice moment, 2-3 times across the whole campaign — narratively framed (a logbook-style operational decision, not a shop).
- *Each choice permanently alters that act's grid/fleet/ruleset* — e.g. an extra unit added to the roster, a standing rule change (a coal unit gains AGC eligibility for the rest of the campaign), or a baseline parameter shift (reserve margin, difficulty tolerance) — all implemented as straightforward per-campaign-save overrides layered on top of the shift's normal `GRID_SOURCE`/config loading, not deep engine changes.
- *No numeric bookkeeping* — persistence needs are minimal (just which picks were made, a handful of enum values), far simpler than a running balance.
- *Content-heavy, not systems-heavy* — most of the design work is authoring good, meaningfully different draft options per transition, which is closer to the event-typology brainstorming already done than to new engine work.

**Build cost:** low-to-moderate on the systems side; the real cost is content authoring (each act transition needs 2-3 well-designed, genuinely different options).

**Risk:** only 2-3 decision points in the entire campaign is a much lower frequency of agency than a per-shift system — if frequent, recurring management is wanted, this undershoots it. Also the option most dependent on strong writing, since its whole weight rests on each choice feeling consequential.

---

## Option 9 — Standing Order

**Concept:** Invert the transaction direction. Instead of "earn now, spend later," the player declares a **standing priority for the whole act** at its start — e.g. "this act, I am prioritizing frequency discipline" or "minimizing load-shed events" — chosen from `grade_shift()`'s five existing axes. The campaign silently tracks adherence to that self-declared priority across every shift in the act, and the act-transition payoff (which could be any of Options 6-8's mechanisms) is keyed to whether the player kept their own stated priority, not just their generic overall grade.

**Gameplay mechanics impact:**
- *A single new decision at the start of each act* (3-4 times across the campaign): pick one of the five scoring axes to prioritize.
- *Reframes the existing, already-built five-axis scoring* as something the player actively engages with rather than a passive report card read once at debrief — the axes the player currently only sees after the fact become something they commit to in advance.
- *Needs no new resource or currency of its own* — it's a scoring lens, not a payoff mechanism, so it must be paired with a concrete reward drawn from another option (most naturally Option 6's budget or Option 8's draft).
- *Teaches self-directed goal-setting* inside an already-complex simulation, a distinct skill from general responsiveness, and one that scales naturally with the campaign's own escalating difficulty (an ambitious standing order in Act III means something harder than the same order in Act I).

**Build cost:** low mechanically — one enum choice per act, a running tally against an axis `grade_shift()` already computes — but it is not a complete system by itself; it needs a payoff borrowed from elsewhere.

**Risk:** the most conceptually novel option, hardest to predict without prototyping; also the only option that is explicitly a decision *shape* rather than a full reward system, so it can't be evaluated in isolation from whichever payoff it's paired with.

---

## Comparison Summary

| Option | What's earned | What's managed | New resource? | Build cost | Reuses existing code |
|---|---|---|---|---|---|
| 6 — Budget Becomes the Campaign | Persistent EUR | Spend planning EUR, now campaign-scarce | No — reuses Phase 1's existing budget | Low | Heavily (`phase1.py`'s cost model, nearly as-is) |
| 7 — Trust, Not Money | Game posture/autonomy | Nothing directly — emergent from play | No | Moderate | Existing tolerance/TUTOR constants, repurposed |
| 8 — The Draft | Better choice-sets | A single pick, 2-3 times total | No — discrete picks, not a currency | Low–moderate | Minimal — mostly new content |
| 9 — Standing Order | Self-set goal adherence | A declared priority per act | No — a tracked promise, not a currency | Low (needs a paired payoff) | `grade_shift()`'s axes, reused for a new purpose |

**The common thread across all four:** none invents a new numeric currency ("Maintenance Points" or similar). Three reuse resources or code that already exist (`grade_shift()`, Phase 1's cost model); the fourth (the Draft) replaces a currency with discrete, irreversible content choices. This is the actual departure from the two earlier, rejected passes — moving away from "a number you earn and spend" as the assumed shape entirely, rather than just changing what the number buys.

**Combinations worth considering, not just single picks:**
- *6 + 8:* Option 6's persistent budget as the underlying resource, but delivered in Option 8's rarer, act-transition lump sums rather than continuous per-shift dribbling — fewer, weightier budget decisions instead of one every shift.
- *9 + 6 or 9 + 8:* Option 9's declared-priority framing as the *decision layer* sitting on top of either Option 6's budget or Option 8's draft as the actual payoff mechanism — since Option 9 is explicitly a shape looking for a reward, not a complete system on its own.

---

## Open Questions

1. Which option (or combination) is worth developing further into a full spec?
2. If Option 6: how aggressively should grade move the budget, and does the campaign need a floor or catch-up mechanism to prevent an unrecoverable early-game death spiral?
3. If Option 7: what is the minimal visible signal needed so the player actually feels the trust/autonomy shift, given the risk that a fully invisible system reads as no system at all?
4. If Option 8: what are the actual draft options at each act transition? This is content-design work in its own right, likely a follow-on session once the systemic shape is chosen.
5. If Option 9: which payoff mechanism should it pair with?
6. Persistence is required by every option — still open whether the save system should be scoped narrowly to whichever option is chosen, or built as the general-purpose campaign save system GRIDCOM will eventually need regardless (shift progress, difficulty selection, etc. — all currently in-memory-only).

## Verification (once a direction is chosen)

- Confirm the chosen option's data needs against what `grade_shift()`/`SimulationState` already expose at shift-end; identify any new tracking required.
- Confirm persistence scope before writing any save/load code.
- Playtest-check legibility — Options 7 and 9 in particular risk being invisible in play; some debrief- or briefing-screen callout is likely needed regardless of direction, so the consequence of past performance is actually readable, not just mechanically real.
