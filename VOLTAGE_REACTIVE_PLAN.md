# Voltage & Reactive Power Regulation

## Context

GRIDCOM's core loop (dispatch, frequency, load flow, congestion, cascade) is well
resolved. The one designed pillar not yet playable is **voltage / reactive power**.

The surprising finding from exploration: the physics is **already built and running**.
`src/simulation/voltage.py` is a complete decoupled solver (`ΔV = B'⁻¹ × Q`) with a
working PV→PQ conversion pass, and it is genuinely called every tick. The problem is
it is **fed all-zero reactive inputs** — load buses draw no reactive power, generator
voltage setpoints are hardcoded to 1.0 pu, and there are no compensation devices — so
in normal play every bus solves to ~1.0 pu and voltage never moves. The voltage
alarms, crisis check, and `min_voltage_seen` are all wired but can never fire. The
`bus_vsi`, `unit_q_injections_mvar`, `unit_bus_types`, and `set_unit_q_target` API
surface already exists (per SIMULATION_API.md) but is dormant. VSI halo colours exist
in `palette.py` but are drawn nowhere.

So this is not a physics-build; it is a **forcing-function + gameplay/display** build.
The design docs (`GRID_SIMULATION_MECHANICS.md` §5) always intended voltage physics to
"run from day one" and be progressively exposed. This plan makes voltage a live
gameplay variable and gives the player the tools to manage it.

**Intended outcome:** heavily-loaded/weak buses visibly sag; generators auto-regulate
reactive power to hold voltage and can exhaust their Q reserve (PV→PQ); automatic
regulators (taps, shunt banks) absorb routine drift while the player works two manual
levers (generator setpoints, SVC); voltage can collapse if a region is mismanaged; all
of it is visible and controllable — exercisable end-to-end in `DESIGNER_TEST` without a
live window.

**The gameplay shift this creates (developer's framing):** with voltage/reactive live,
the grid must be managed **locally and carefully** by region, not as a
"connect-every-line, full-redundancy" network. Reactive compensation is local and
cannot be transported — so a sagging region must be supported by generation (or a
device) *in that region*. This reframes the whole game's later shifts around regional
awareness.

**Developer decisions locked in:**
- Physics depth: **reactive load + generator AVR** (most realistic forcing).
- **Automatic local regulators (player sees the result, does NOT control):**
  transformer taps (AVR-style ratio control at substations) and shunt capacitor/reactor
  banks (voltage-deadband auto-switching with hysteresis). These absorb the routine daily
  reactive drift.
- **Manual player levers (the two things the operator actively works):** generator
  voltage setpoints (support a sagging region from nearby generation, with PV/PQ and
  Q-reserve made visible) and a manual continuous SVC/STATCOM at weak buses (for regions
  with no nearby generation). `set_unit_q_target` (raw MVAr) stays callable but gets no UI.
- **Load-substation types:** 2-3 types (industrial / residential / mixed) with distinct
  active *and* reactive (power-factor) load profiles; some types carry auto shunt banks,
  some don't — the positioning of banks is part of the local-management texture.
- Delivery: **mechanic + display + tools, no campaign shift this pass** (testable in `DESIGNER_TEST`).
- Thresholds: **`constants.py` is authoritative** (0.90 watch / 0.85 warning / 0.70 critical); update the docs to match, not the reverse.

Project rules apply throughout: all numbers → `constants.py` (Rule 1); all colours →
`palette.py` (Rule 2); the simulation layer never imports display/gameplay/pygame; the
display reads only `SimulationState` and never recomputes what the sim provides.

---

## Key architectural decisions (resolving the hard questions)

1. **Generator setpoint on shared buses** — `units.pv_bus_constraints()` averages
   v_target across units at a bus (and sums their Q limits). Keep that; just change the
   averaged value from a hardcoded `1.0` to each unit's real per-unit setpoint. Player
   edits are per-unit; bus target = mean of its units' setpoints. Physically sound
   (paralleled AVRs share a bus voltage). No solver change.

2. **PV→PQ single correction pass** stays adequate (B' is diagonally dominant, the
   correction is linear). Add a headless assertion that PV buses hit target when Q
   reserve isn't exhausted; the contained fallback (only if violated) is a 2nd pass —
   do not redesign the solver.

3. **Collapse acceleration (trickiest)** — the solver is stateless and returns a fresh
   voltage each tick, so a per-tick decrement cannot live in it. It becomes a stateful
   **post-solve overlay owned by `GridSimulation`**: `self._v_collapse_offset:
   dict[bus, float]`. Each tick, after the solve, buses below `V_WARNING_LOW`
   accumulate a negative offset (per the documented nonlinear law); buses that recover
   decay the offset back toward 0. The value fed to alarms/crisis/snapshot is
   `v_eff = solved_v + offset`. Solver stays pure; runaway persists; it auto-heals when
   the operator fixes the Q deficiency. Reset a bus's offset to 0 on blackout entry.

4. **Devices as Q injections, not B' edits** — shunt banks, SVC, and (approximated)
   transformer taps are all modeled as Q injections at a bus. B', `VSHUNT_REG`, and
   `rebuild()` are untouched, so conditioning is unchanged and switching a bank never
   re-factorises the matrix. **Automatic regulators (taps, shunts) run inside the sim's
   tick as controllers** that read the last solved voltage and adjust their Q for the
   next solve — with hysteresis / a switch delay so they settle rather than hunt.

5. **Auto-regulator ordering / stability** — automatics act on the *previous* tick's
   solved voltage (one-tick lag), never inside the solve, so there is no algebraic loop.
   Deadband + hysteresis + a minimum dwell time (all constants) prevent step-hunting.
   Because the sim ticks at 10 Hz, a one-tick lag is imperceptible.

6. **Forecast mode** (`run_forecast_mode`) gets the same reactive-load forcing + real
   generator setpoints (so `voltage_risk` becomes meaningful) but **not** the collapse
   offset and **not** the manual SVC (live-control concepts). It *may* apply a simple
   static version of the auto shunts/taps (their steady-state setting) so the forecast
   voltage profile is representative; keep it simple.

---

## Phase A — Reactive forcing + substation types (make voltage move)

- **`constants.py`** — new REACTIVE block. Per-substation-type power factors instead of
  one global PF: e.g. `PF_INDUSTRIAL = 0.85`, `PF_RESIDENTIAL = 0.97`, `PF_MIXED = 0.92`
  (a `SUBSTATION_TYPE_PF` mapping). Generator setpoint edit range:
  `GEN_VOLTAGE_SETPOINT_DEFAULT_PU = 1.02`, `..._MIN_PU = 0.95`, `..._MAX_PU = 1.05`.
  Keep `V_COLLAPSE_GAIN = 2.0`; add named `V_COLLAPSE_SEVERITY_LOW = 0.85` /
  `V_COLLAPSE_SEVERITY_FLOOR = 0.70` for Phase B.
- **Substation types** — introduce a load-substation `type` field
  (`INDUSTRIAL`/`RESIDENTIAL`/`MIXED`). Runtime-seeded this pass (default helper used by
  `_make_designer_test`), not authored into the frozen Designer JSON yet. Each type
  determines its power factor (hence its reactive load) and whether it carries auto shunt
  banks. The `DemandModel` learns each load bus's type so it can compute per-bus Q.
- **`demand.py`** — add `q_load_injections() -> {bus: -q_mvar}` mirroring
  `p_load_injections()` (240-247): `q = _bus_demand[bus] * tan(acos(PF_for_type[bus]))`,
  returned negative (load absorbs Q). Cache each type's `tan(acos(PF))`.
- **`units.py`** — add `_v_setpoint_pu` (default from constants) to `UnitModel`,
  `set_voltage_setpoint(v_pu)` (ONLINE-only, clamped), `v_setpoint_pu` property. In
  `pv_bus_constraints()` (line 624) replace `.append(1.0)` with `.append(m.v_setpoint_pu)`.
- **`simulation.py::_build_q_injections`** (688-691, the key seam) — take
  `blackout_zones`, seed zeros, merge `self._demand.q_load_injections()` honoring
  blackout zones exactly like `_build_p_injections`. (Phase C adds auto-regulator + SVC Q
  here.) Thread the blackout arg through the init snapshot (1123-1126) and post-trip
  re-solve (430-432).
- **Forecast** (line 625) — feed `demand_fc.q_load_injections()` into the forecast solve;
  keep the now-real `pv_bus_constraints()`.

**Verify A:** new `tests/test_voltage_reactive.py` — build a `GridSimulation` (real Grid
shift 7/10, or a small DesignerGrid) with typed load buses, tick a few steps, assert ≥1
non-slack load bus voltage ≠ 1.000, low-PF (industrial) buses sag more than high-PF
(residential) buses under comparable MW, slack = 1.0, all finite. No pygame.

---

## Phase B — VSI tiers + collapse acceleration + alarm/crisis verify

- **`constants.py`** — add `V_COLLAPSE_RECOVERY_PU_S` (offset decay rate). Tier
  boundaries already exist (0.95/0.90/0.85/0.70) and are authoritative.
- **`simulation.py`** — init `self._v_collapse_offset = {}` (~264). New
  `_apply_collapse_acceleration(solved_v, dt) -> {bus: v_eff}` (decision 3):
  below `V_WARNING_LOW`, `severity = clamp((0.85 - v)/(0.85 - 0.70), 0, 1)`,
  `accel = severity² * V_COLLAPSE_GAIN`, `offset -= accel*dt`; else decay toward 0;
  `v_eff = max(0.0, v + offset)`. Call after each solve (403; and after the re-solve
  432). Feed **v_eff** into `_update_voltage_alarms`, `_update_crisis`, `min_voltage`
  tracking (461-462), and `_build_state` snapshot `bus_voltages`. Reset offset to 0 on
  blackout entry. (No separate per-bus voltage trip this pass — documented follow-up.)
- **`simulation.py::_build_state`** — keep `bus_vsi` numeric (= v_eff) for API compat;
  **add** `bus_vsi_tier: {bus: 'HEALTHY'|'WATCH'|'WARNING'|'CRITICAL'}` via a `_vsi_tier(v)`
  helper (so display never recomputes it). Optionally add a WATCH-tier INFO alarm at
  `V_WATCH_LOW` behind a `_seen_v_watch` set mirroring `_seen_v_warn`.

**Verify B:** DesignerGrid with a heavily-loaded, generation-poor bus so solved
v < 0.85; tick repeatedly and assert the offset accumulates (voltage keeps dropping
tick-over-tick), WARNING→CRITICAL alarms fire, `crisis_active` True, tiers transition
HEALTHY→WATCH→WARNING→CRITICAL; then relieve load and assert offset decays and voltage
recovers. Headless.

---

## Phase C — Devices: automatic regulators + two manual tools

**Authoring approach (least invasive):** do NOT extend the Designer JSON schema /
frozen `DesignerBus` this pass. Seed devices at **runtime** as a per-bus registry owned
by `GridSimulation`, populated by a default-seed helper used by `_make_designer_test`
(driven by substation type from Phase A). Leaves `designer_io.py`/`shift_io.py`/
DesignerGrid untouched; JSON authoring is a separable later change.

- **NEW `src/simulation/reactive_devices.py`** (no pygame) — dataclasses + a
  `ReactiveDevices` registry that owns both automatic and manual devices and exposes
  `q_injections() -> {bus: mvar}`:
  - `ShuntBank(bus, mvar_per_step, n_steps, step)` — **automatic**, +cap/−reactor.
  - `TransformerTap(label, regulated_bus, step, n_steps, step_ratio, neutral_step)` —
    **automatic**, Q approximation.
  - `SVC(bus, q_min, q_max, q_setpoint)` — **manual/continuous**, player-set.
  - `step_automatics(bus_voltages, dt)` — the auto-regulator controller (decisions 4-5):
    for each auto shunt/tap, read the last solved voltage at its regulated bus and, if
    outside its deadband and its dwell timer has elapsed, step toward the deadband
    (hysteresis + min dwell prevent hunting). Called once per tick *before*
    `_build_q_injections`, so it acts on the previous solve (one-tick lag, no algebraic
    loop).
- **`constants.py`** — sizing + control: `SHUNT_BANK_MVAR_PER_STEP = 50.0`,
  `SHUNT_BANK_MAX_STEPS = 4`, `SHUNT_DEADBAND_LOW_PU = 0.97`,
  `SHUNT_DEADBAND_HIGH_PU = 1.03`, `SHUNT_SWITCH_DWELL_S` (min time between switches),
  `TAP_STEP_RATIO = 0.0125`, `TAP_N_STEPS = 8`, `TAP_NEUTRAL_STEP = 0`,
  `TAP_DEADBAND_LOW_PU` / `TAP_DEADBAND_HIGH_PU`, `TAP_DWELL_S`,
  `SVC_Q_MIN_MVAR = -150.0`, `SVC_Q_MAX_MVAR = 150.0`, `SVC_Q_STEP_MVAR = 10.0`.
- **`simulation.py`** — the tick calls `self._reactive.step_automatics(prev_voltages, dt)`
  before building Q. Public control methods next to `set_unit_q_target` (489),
  bool-return convention — **only the two manual levers**:
  `set_generator_voltage_setpoint(unit, v_pu)` and `set_svc_setpoint(bus, q_mvar)`.
  No player method for taps or shunts (automatic). `set_unit_q_target` stays callable.
- **`_build_q_injections`** — after the load-Q merge, add `self._reactive.q_injections()`
  per bus (all devices are PQ injections; PV generators re-regulate against them — a cap
  bank raising local V lets a nearby gen back off its Q).
- **Transformer-tap MVP** — approximate a tap as corrective Q producing
  `ΔV ≈ tap_step * TAP_STEP_RATIO` at the regulated bus, via `ΔQ = B'_diag * ΔV * S_BASE`
  (same relation as `voltage.py:197-199`) through a small `VoltageModel` accessor.
  Discrete steps, B' untouched. Documented as an approximation.
- **`SimulationState` + `_build_state`** — new bus-keyed fields: `bus_vsi_tier`,
  `bus_shunt_step`, `bus_shunt_mvar` (auto, read-only to player), `bus_svc_mvar`,
  `bus_svc_limits` (manual), `transformer_taps` (auto, read-only), `bus_q_injection_mvar`
  (total device Q/bus), `unit_v_setpoint_pu`, plus per-unit `unit_q_reserve_mvar`
  (headroom to `q_max`) so the display can show which generators can still help.

**Verify C:** DesignerGrid seeded (via type) with auto shunts, an auto tap, and a manual
SVC. (i) Drive a slow load rise and assert the auto shunt steps up to hold voltage in its
deadband and does *not* hunt (bounded switch count over the run); (ii) assert the auto tap
holds its regulated bus near nominal; (iii) call `set_svc_setpoint`, tick, assert bus
voltage moves monotonically with setpoint and clamps at limits; (iv) `set_generator_voltage_setpoint`
raises a sagging region and a nearby generator's Q rises toward `q_max` then converts to
PQ when exhausted (`unit_bus_types` flips). Headless.

---

## Phase D — Display: VSI halos, MVAr readouts, two manual controls

Display reads only `SimulationState`. Taps and auto shunts are shown **read-only** (the
player sees what the automatics are doing but can't change them); only generator
setpoints and the SVC get controls.

- **`palette.py`** — `COL_VSI_HEALTHY` (dim/none); make CRITICAL visually distinct from
  WARNING (currently both red); `COL_SHUNT_CAP`, `COL_SHUNT_REACTOR`, `COL_SVC`, `COL_TAP`.
- **`canvas.py`** — VSI halo rings on substations at the per-bus draw seam (793-815),
  coloured by `bus_vsi_tier`, drawn only for WATCH/WARNING/CRITICAL; radius/width/blink
  from new constants (`VSI_HALO_RADIUS_PX`, `VSI_HALO_WIDTH_PX`, `VSI_HALO_BLINK_HZ`).
  First real use of `COL_VSI_*`. Plus small device glyphs at device-hosting buses:
  capacitor bars / reactor coil for auto shunts (glyph reflects current step), tap arrows
  for auto taps, SVC diamond for the manual device.
- **`context.py::draw_bus_context`** (180-240) — add VSI-tier row (coloured),
  `Q: X MVAr` (`bus_q_injection_mvar`), a read-only auto-shunt row (`step / mvar`) and
  read-only tap row where present, and — only for a bus hosting an SVC — an SVC row with
  `[-]/[+]` adjust affordances.
- **`context.py::draw_unit_context`** — add "AVR setpoint: X.XXX pu" row (editable), a
  PV/PQ indicator (`unit_bus_types`), current Q, and Q-reserve (`unit_q_reserve_mvar`) so
  the player can see which generators can still support voltage. Setpoint input affordance
  mirrors the existing MW buffer.
- **`renderer.py`** — new commands, keyboard **and** mouse (input rule), **manual tools
  only**: `_get_selected_bus()` (mirror `_get_selected_line` 314-321 via
  `_canvas._bus_map`); `on_svc_adjust(±)` for a selected SVC bus; generator setpoint via a
  dedicated `_setpoint_cmd_active` flag + `on_setpoint_enter` (must not collide with the
  MW buffer). Clickable `[-]/[+]` hit-rects for the SVC and setpoint (renderer owns
  hit-testing, as it does for line trip/close). No tap/shunt controls. Forward the new
  state dicts through `draw()` to canvas and context.

**Verify D:** render on an offscreen surface (`SDL_VIDEODRIVER=dummy`) with a sim that
has seeded devices and a sagging bus, `renderer.tick(dt, state=..., speed_mult=0)`, save
canvas to a PNG in the scratchpad, inspect halo / glyphs / context rows (including the
read-only auto-shunt/tap rows and the Q-reserve readout). No live window (established
project precedent).

---

## Phase E — DESIGNER_TEST wiring + verification + docs

- **`main.py::_make_designer_test`** (254-299) — after building `sim`, assign each LOAD
  bus a substation type and seed devices accordingly (`sim.seed_default_reactive_devices()`):
  industrial buses get auto shunt banks, residential don't, plus a manual SVC at a weak
  bus with no nearby generation. DESIGNER_TEST only.
- **`main.py` DESIGNER_TEST input block** (1166-1238) — non-colliding keys (existing:
  p, space, F1-3, s, x, t, c, a, Tab, l, digits), all guarded by `not _rend._input_active`
  — **manual tools only**: SVC `,`/`.` (adjust selected SVC bus), setpoint mode key (e.g.
  `v`) then digits + Enter (selected generator). No tap/shunt keys. Mouse covered by the
  D hit-rects.
- **Docs** (constants authoritative):
  - `GRID_SIMULATION_MECHANICS.md` §5.5/§5.6/§5.7 — VSI tiers to 0.90/0.85/0.70; document
    reactive load with per-substation-type power factors, AVR setpoint regulation, the
    persistent post-solve collapse offset, **automatic taps and auto-switching shunt
    banks** (deadband + hysteresis), and the two manual levers (gen setpoints, SVC).
    Reframe the section around local/regional voltage management.
  - `DOMAIN_GLOSSARY.md` — power factor, substation types, AVR setpoint, (auto) shunt
    bank, SVC/STATCOM, (auto) tap changer, VSI tiers, Q-reserve.
  - `SIMULATION_API.md` — new methods (`set_generator_voltage_setpoint`, `set_svc_setpoint`)
    and new `SimulationState` fields (including the read-only auto-shunt/tap state and
    `unit_q_reserve_mvar`); note `bus_voltages` now carries v_effective; that taps/shunts
    are automatic (no player method).
- **`STAGE_STATUS.md`** — new session entry per project convention.

**Verify E:** end-to-end headless smoke — build a `_make_designer_test`-style sim
directly (no renderer), seed typed load buses + devices, drive a regional sag, exercise
the two manual `set_*` and confirm the automatics act, tick ~1 sim-hour, assert the full
chain (voltage moves per substation type → auto shunts/taps hold their deadbands without
hunting → manual setpoint/SVC support a sagging region → tiers change → alarms/crisis
fire → collapse offset accumulates then recovers). Then `python -m pytest tests/`
(currently 15/15) plus the new `test_voltage_reactive.py`.

---

## Build / test order

Each phase green before the next: **A** (voltage moves; substation types) → **B**
(tiers/alarms/crisis/collapse offset) → **C** (auto shunts/taps regulate without hunting;
manual SVC + gen setpoint change Q & voltage; PV→PQ) → **D** (PNG render of
halos/glyphs/read-only auto rows/Q-reserve/manual controls) → **E** (DESIGNER_TEST keys,
typed seed, docs, full smoke).
Phases A/B/C and the E smoke need no pygame; D uses the offscreen-surface + PNG
precedent. No live fullscreen window at any point.

## Integration risks (watch these)

- `q_load_injections` **must** honor `blackout_zones` like `p_load_injections`, or
  blacked-out buses keep drawing reactive power.
- The collapse offset is the one stateful piece in an otherwise stateless voltage path —
  keep it strictly in `GridSimulation`, reset it on blackout, and only ever feed `v_eff`
  (never the raw solve) downstream.
- **Auto-regulator hunting** — auto shunts/taps must use a deadband + hysteresis + a
  minimum dwell time and act on the *previous* tick's solved voltage (one-tick lag). A
  bare "if below target, step" with no hysteresis will oscillate. The Phase C verify must
  explicitly bound the switch count over a slow load ramp.
- **Automatics masking player error** — because taps + shunts auto-correct routine drift,
  the player only feels voltage when a *region* exhausts its reactive reserve. Seed the
  DESIGNER_TEST grid with at least one weak, generation-poor region so the manual levers
  (setpoint / SVC) actually matter and the mechanic is demonstrable.
- Generator-setpoint editing is per-unit but the bus target is the mean — the unit panel
  should show the per-unit value and that co-located units share a bus target.
- Tap changer ships as a Q approximation; true voltage-ratio modelling is a flagged
  follow-up, not this pass.
- Substation types are runtime-seeded this pass (not in the Designer JSON) — authoring
  them into the grid schema is a deliberate later change, kept out of scope here.

## Critical files

- `src/simulation/simulation.py` — `_build_q_injections` seam, collapse overlay, `set_*` methods, `SimulationState` + `_build_state`
- `src/simulation/units.py` — v_setpoint plumbing, `pv_bus_constraints` v_target
- `src/simulation/demand.py` — `q_load_injections` + per-substation-type power factor
- `src/simulation/constants.py` — reactive / substation-type PF / device / auto-regulator / VSI-halo constants
- `src/simulation/reactive_devices.py` — **NEW**: auto shunt + auto tap + manual SVC models, `step_automatics`, registry
- `src/display/canvas.py`, `context.py`, `renderer.py`, `palette.py` — halos, device glyphs, read-only auto rows, Q-reserve, manual SVC + setpoint controls
- `src/main.py` — `_make_designer_test` seeding + DESIGNER_TEST key routes
- `tests/test_voltage_reactive.py` — **NEW**
- Docs: `GRID_SIMULATION_MECHANICS.md`, `DOMAIN_GLOSSARY.md`, `SIMULATION_API.md`, `STAGE_STATUS.md`
