# STAGE_STATUS.md — GRIDCOM Development State
### Updated at the end of every Claude Code session.
### Read at the start of every Claude Code session.

---

## Current Stage

**STAGE 29 — Regional Topology Restructuring (Spine-Only Inter-Region Ties) + Obstacle-Avoiding Line Router**

## Current Status

**PARTIAL** — Topology, fleet, and profiles fully redesigned (36 buses, 50 lines, 47 units, Portuguese-grid-inspired structure, full size at Shift 8). Shifts 1-3 scenario files re-tuned and playable. Shift 10 is the campaign finale on a capacity-expanded, N-1-secure, decluttered, and now **regionally-zoned** grid (see Sessions 31, 33, 34, 35, and 36): the network reads as a 400kV spine (WEST-MDBY-STHW-CNTR-NRTH-EAST) connecting 5 regions (CAP, WEST, SOUTH-MESH, EAST-POCKET, EAST-MESH) that only reach each other via the spine — no direct lower-voltage tie bypasses it. Each region hosts exactly one consolidated load substation, dual-fed from that region's own spine-anchor buses (CAP additionally has a 3rd spine tap for N-1 margin — see Session 36). All schematic lines route through a general obstacle-avoiding router instead of a blind single bend, so no line crosses an unrelated substation. Every load substation and cascade-hydro bus has a proper place name. **Shifts 4-9 scenario files remain stale** — same issue as before (written for the old topology, per-bus peak MW values don't match `peak_demand_mw` targets) — and inherit both the flat-rating change from Session 31 and the STAN/BRCK/FLDN/CO01 voltage promotion from Session 36, neither re-tuned for them. **Shift 3's N-1 lesson is confirmed at risk of regression** — see Known Issues. **Shifts 7-9 have a disconnected island** (EAST-MESH) — see Known Issues. 9/9 automated tests pass.

## Session Log

### Session 42 (Display — Instrument Strip: Full-Fleet Dispatch Grid + Frequency History Plot)

- **Problem reported**: the UNIT DISPATCH panel (280px wide, single-column, 18px rows) only showed ~12 of up to 47 units (Shift 10) at once, forcing constant mouse-wheel scrolling to see the rest of the fleet. Separately, the FREQUENCY panel showed only the live instantaneous Hz value/bar with no way to see recent trend — no frequency history was tracked anywhere in the codebase (confirmed via exploration: not in `FrequencyModel`, not in `SimulationState`, not in any display module).
- **Panel widths rebalanced**: FORECAST and GENMIX — both wider than their content needed — shrunk 50% (360→180px, 260→130px) to free 310px, all given to UNIT DISPATCH (280→590px). FREQUENCY/POWER BALANCE/ALARMS unchanged. The 6-panel row still sums to exactly `NATIVE_WIDTH` (1920px), same invariant as before.
- **UNIT DISPATCH is now a multi-column grid, no scrolling**: `draw_dispatch_panel()` (`panels.py`) computes `rows_per_col` from live panel height/row-height (unchanged formula) and derives `num_cols = ceil(total_units / rows_per_col)` fresh each draw — at Shift 10 (47 units, ~12 rows/col) this yields 4 columns; at Shift 1 (2 units) it correctly collapses to 1 column rather than stretching across empty columns. Units fill column-major (top-to-bottom, then wrap). Per-unit row content unchanged in kind (label/state abbrev/mini bar/MW) but compacted to fit ~147px columns: mini bar 120px→28px, MW readout dropped the `/rated` suffix (now just output MW — rated capacity is implicit in the bar fill and already shown elsewhere). Removed `scroll_row` parameter, the scroll-clamping logic, and the `↑↓ start-end/total` indicator entirely (nothing scrolls now). `Renderer._dispatch_scroll` and its `on_scroll()` branch and `PANEL_DISPATCH_X`/`_W` bounds check removed — only the alarm panel still scrolls.
- **Frequency history plot added, renderer-owned** (display-only concern, simulation.py untouched, consistent with the sim/display separation in `CLAUDE.md`): new `FREQ_HISTORY_WINDOW_S = 60.0` constant (`constants.py`); `Renderer` holds `self._freq_history: deque[float]` sized `FREQ_HISTORY_WINDOW_S * TARGET_FPS`, appended once per rendered frame from `state.frequency_hz`. `draw_frequency_panel()` gained a `freq_history` parameter and draws a **bottom-to-top strip chart** below the existing trend/clock line: each sample's Hz value maps to an X position using the same `_fill_frac()` the live bar already uses (so the plot's X-axis lines up with the bar above it), and recency maps to Y — most recent sample nearest the top (closest to the live bar), oldest at the bottom, drawn as a single connected line via `pygame.draw.lines`. Vertical guide lines at 49.5/50.0/50.5 reuse `COL_METER_TICK`. To make room, the trend text and sim-clock (previously two stacked lines) now share one row (trend left-aligned, clock right-aligned).
- **Pre-existing bug fixed in passing** (confirmed present before this session via `git diff` — not introduced by the above): the frequency bar's tick labels (`49.5`/`50.0`/`50.5`) always overlapped into unreadable text, since those three values are only 1Hz apart on a bar spanning a 10Hz range and the label draw code centered each label on its tick with a fixed offset regardless of neighbor spacing. Widened the labeled range to the bar's actual min/center/max (`45`/`50`/`55`) so the three labels spread across the full bar width; each label's draw position is now computed from its own text-rect width (clamped to stay inside the bar) instead of a fixed offset. Confirmed via a synthetic-oscillation offscreen render (not just the degenerate flat-45Hz smoke test) that labels no longer overlap at any frequency value.
- **GENMIX simplified at the new narrower width**: the per-fuel mini bar (`_BAR_MAX_W`) is removed — at 130px there was no room left for it once label+MW+% were laid out (the old fixed offsets placed the bar's start position past the panel's right edge, i.e. it was already being drawn off-panel once the width shrank). MW and % are now right-aligned from the panel's right edge, computed from each string's actual rendered width rather than fixed offsets.
- **FORECAST column math made width-aware**: TIME previously took a fixed 36%-of-width fraction, which put LOAD's right-aligned text on a collision course with TIME's own text once the panel narrowed to 180px. TIME's column width is now sized to its actual content (`"00:00"` text rect + padding); LOAD/WIND/SOLAR evenly split whatever width remains. No change to the auto-scroll/current-slot-highlight logic, only the horizontal column split.
- Edited: `src/simulation/constants.py` (panel X/W constants, new `FREQ_HISTORY_WINDOW_S`), `src/display/panels.py` (`draw_frequency_panel`, `draw_dispatch_panel`, `draw_genmix_panel`, `draw_forecast_panel`), `src/display/renderer.py` (`__init__` freq-history deque, `on_scroll`, `tick()` dirty-key/sampling/draw-call updates).
- Verified: 15/15 automated tests pass (no simulation code touched, matching every panel-only session before this). Offscreen (pygame dummy driver) smoke tests built real `Grid`/`GridSimulation` instances for Shift 10 (47 units) and Shift 1 (2 units), ran the render loop, and saved individual panel surfaces plus a full-strip composite to inspect directly: confirmed all 6 panels tile 1920px with no gaps/overlaps at both shift sizes; confirmed UNIT DISPATCH shows all 47 units across 4 columns at Shift 10 with legible label/state/bar/MW and correctly collapses to 1 column (no empty stretch) at Shift 1's 2 units; confirmed FORECAST and GENMIX render cleanly at their new half widths with no clipped/overlapping text; confirmed the frequency plot — tested separately with a synthetic sine-wave history and with Shift 1's real (undispatched, frequency-decaying) simulation output — renders as a coherent bottom-to-top trace whose top point sits at the live bar/reading and whose shape visibly matches the frequency's recent movement.
- **Not done this session**: no in-game manual playtest (all verification was offscreen/programmatic per the dummy-driver pattern established in prior display sessions) — recommend a manual visual pass before relying on this further, particularly to judge whether the compacted dispatch-panel bar width (28px) and dropped `/rated` MW suffix feel readable at a glance during real play.

### Session 41 (Performance — Render Timing Diagnostics)

- **Problem reported**: FPS drops to ~4 on a laptop during gameplay (target 50-60, `TARGET_FPS = 60`). User also asked whether the 10Hz simulation tick rate could be reduced to save time.
- **Investigation (read-only, no simulation code touched)**: two parallel research passes over `src/display/` and `src/simulation/` concluded the simulation tick is not a plausible cause — at Shift 10 scale (41 buses/62 lines/47 units) the DC load-flow and voltage solves are sub-millisecond dense 40×40 `np.linalg.solve()` calls, correctly cached (B-matrix rebuilds only on topology change), and the `main.py` sim/render loop already decouples ticks from frames via an `if sim_accum >= SIM_TICK_INTERVAL_S` accumulator (not `while`, so no catch-up/spiral-of-death risk). Per user decision, tick-rate changes are out of scope for this pass. The laptop's screen was confirmed to be exactly 1920×1080 (native match, `Renderer._scale == 1.0`), ruling out the render-at-output-resolution overdraw-multiplier hypothesis that would apply on a higher-res/high-DPI panel — so the cost is raw per-frame CPU work in the draw pipeline, not a resolution artifact. Static analysis flagged several likely-uncached/unconditional per-frame costs (`GridCanvas._redraw_to()` firing very often due to a fine-grained loading/output quantisation in `_build_canvas_key()`, `draw_load_triangles()` running unconditionally every frame with no cache gate, `context.py`'s selection overlays having zero dirty-key caching unlike every panel in `panels.py`) — but this is inference from reading code, not a measurement on the failing hardware.
- **Per user decision, this session ships diagnostics only** (Phase 1 of a 2-phase plan) — real per-section timing measurement on the actual laptop is required before applying targeted fixes, rather than optimizing blind based on static analysis alone. Phase 2 (the actual fixes: coarser canvas dirty-key + tier-bucket caching in `canvas.py`, folding `draw_load_triangles` into the cached canvas redraw, adding dirty-key caching to `context.py`) is deferred to a follow-up session once Phase 1 data is captured.
- **Diagnostics added**: new `DEBUG_PERF` flag (`constants.py`, default `False`, same on/off convention as `DEBUG_SIMULATION`/`DEBUG_DISPLAY`) plus `PERF_DEBUG_LOG`/`PERF_LOG_INTERVAL_S` constants. `Renderer.tick()` (`renderer.py`) now wraps 5 sections in `time.perf_counter()` timers when `DEBUG_PERF` is on: canvas draw, load triangles, instrument panels, context overlay, final native→display blit (plus overall frame time via the existing `dt_real_s`) — stored in `self._perf_last_ms` each frame. Two consumers: (1) `_draw_debug()` (already gated by `DEBUG_DISPLAY`, `D` key) gained a 4th overlay line showing the current frame's section timings in ms, live on-screen; (2) a new `_perf_tick_log()` helper accumulates per-section totals and flushes one summary line (avg fps + avg ms per section) to `logs/perf_debug.log` roughly once per `PERF_LOG_INTERVAL_S` (1s) via a `logging.FileHandler` set up once in `__init__`, mirroring the exact existing `DEBUG_SIMULATION`/`SIM_DEBUG_LOG` pattern in `simulation.py:278-288` rather than inventing a new logging convention. When `DEBUG_PERF` is `False` (default/shipped), the only added cost is a handful of `if` checks — the `perf_counter()` calls themselves are skipped, not just their display.
- Edited: `src/simulation/constants.py` (`DEBUG_PERF`, `PERF_DEBUG_LOG`, `PERF_LOG_INTERVAL_S`), `src/display/renderer.py` (`__init__` perf-logger setup, `tick()` section timers, `_perf_tick_log()`, `_draw_debug()` perf overlay line).
- Verified: 15/15 automated tests pass (renamed from the previously-tracked 9/9 — the suite grew across recent sessions, e.g. `test_designer_analysis.py`; noting the current true count here since `Current Status` above was stale). Offscreen (pygame dummy driver) smoke test: built a real Shift 10 `Grid`/`GridSimulation`, ran 300 ticks with `DEBUG_PERF` and `DEBUG_DISPLAY` both on (including a mid-run selection change to exercise the context-overlay path), confirmed no exceptions, confirmed `self._perf_last_ms` populated with all 5 expected keys, and confirmed `logs/perf_debug.log` received correctly-formatted periodic summary lines. Confirmed via direct code read that `DEBUG_PERF = False` (shipped default) takes the same code path as before this session (all timer calls behind `if _perf:`).
- **Not done this session (deferred to Phase 2, pending real laptop data)**: no actual rendering optimizations applied yet. Next session should build with `DEBUG_PERF = True`, reproduce the 4 FPS drop on the affected laptop, capture which section(s) actually dominate (on-screen via `D` key or via `logs/perf_debug.log`), and use that to confirm or redirect the static-analysis-based fix list before implementing it. See the approved plan `do-an-extensive-revison-synchronous-teapot.md` for the full Phase 2 fix list (canvas dirty-key coarsening + tier-bucket caching, triangle-draw gating, context-overlay caching, minor `main.py` display-flag cleanup).

### Session 40 (Grid Designer — Independent Station Drag + 20px Default Offset)

- **Problem found (using the Designer)**: generation units had no canvas position of their own — `DesignerUnit` carried no `canvas_x`/`canvas_y` fields, so `GridCanvas.load_designer_topology()` always drew a station's unit squares centered horizontally on its bus and at exactly the bus's own Y, recomputed every frame. Units visually sat on top of/straddling the bus symbol, and there was no way to move a station without moving its bus (dragging was bus-only — no unit/station hit-testing or drag state existed anywhere in `designer.py`). The real campaign grid already solves this for its own hand-authored topology via `fleet.py`'s `STATION_POSITIONS` (an independent `station_label -> (x, y)` anchor dict), and a separate in-game tool (`editor.py`'s `GridEditor`, campaign-only) already drags both bus and station positions independently — but neither was wired into the Designer.
- **Station position now independently stored and draggable**: `DesignerUnit` gained `station_x: int = -1` / `station_y: int = -1` (sentinel = "not yet set, derive from bus"), redundantly stored per-unit like `bus_label` already is — no new `DesignerStation` type. New `GridDesigner._dragging_station`/`_station_anchor()`/`_hit_station()` mirror the existing bus-drag pattern exactly (same `DESIGNER_HIT_RADIUS` Chebyshev hit-test, same single shared `_drag_offset`, same "no `_mark_dirty()` during drag, cheap ghost overlay instead, full resync deferred to `on_mouse_up`" performance strategy already established for bus-drag). `on_mouse_down` checks a station hit before a bus hit. Dragging a station never touches its bus's `canvas_x`/`canvas_y`, and vice versa.
- **20px default offset**: `_finish_place_units()` now sets every newly placed unit's `station_x`/`station_y` to `(bus.canvas_x, max(0, bus.canvas_y - 20))` at creation time (Y increases downward, so `-20` is visually above the bus, matching `STATION_POSITIONS`' own convention of placing stations above their spine buses).
- **Rendering**: `GridCanvas.load_designer_topology()` gained a new `station_positions: dict[str, tuple[int,int]] | None` parameter; when a station has a stored position it's used as the unit-square row anchor, otherwise the same 20px-above-bus fallback is computed on the fly (covers pre-feature save files and the separate `DESIGNER_TEST` preview path, which doesn't thread live Designer positions through since it consumes `DesignerGrid.get_active_units()` → `GenerationUnit`, deliberately kept position-free just like the real campaign's `UNITS` list). `GridDesigner._sync_canvas()` builds this dict from `self._units` and passes it through.
- Edited: `src/data/designer_io.py` (`DesignerUnit.station_x`/`station_y` fields), `src/display/designer.py` (`_finish_place_units`, `on_mouse_down`/`on_mouse_move`/`on_mouse_up`, new `_station_anchor`/`_hit_station` helpers, `_draw_canvas_overlays` station-drag ghost, `_sync_canvas`), `src/display/canvas.py` (`load_designer_topology` new parameter + fallback logic).
- Verified: 15/15 automated tests pass (no simulation code touched). Offscreen (pygame dummy driver) checks: a newly placed station lands exactly 20px above its bus; simulated drag (`on_mouse_down`/`on_mouse_move`/`on_mouse_up`) moves the station's stored position while the bus's `canvas_x`/`canvas_y` stay untouched; mid-drag ghost-overlay draw and post-drag full-resync draw both render without error; station position round-trips through save/load unchanged; loading the pre-feature `grid1.json` (units with no `station_x`/`station_y` in the file) yields the `-1` sentinel and correctly falls back to the bus-derived anchor with no crash; `shift10.json` (41 buses/47 units) still loads and renders, and dragging a bus that has units attached still starts a bus-drag (not a false-positive station hit) since the 20px offset exceeds the 14px hit radius.

### Session 39 (Grid Designer — Remove 60kV Tier, Standard Line Ratings)

- **Problem found (using the Designer)**: the Designer's bus palette offered a "60 kV (LOAD)" voltage tier that has never existed in the real game — per `CLAUDE.md`/`topology.py`, all load substations are 150kV, and no 60kV bus or line exists in any shipped shift. `bus_type` was derived from `voltage_kv == 60.0`, meaning a LOAD bus could *only* be created at the fictitious 60kV tier. Separately, manual line placement let the user free-pick a rating from a flat, voltage-agnostic preset list (100-2000 MW in 13 steps) before placing, and free-type any value afterward via the properties panel — neither was tied to the real game's standard per-tier rating table (`LINE_RATING_MW_BY_VOLTAGE = {400: 2250, 220: 400, 150: 175}` MW), so Designer-built lines could end up with ratings inconsistent with their voltage class.
- **60kV tier removed**: the "60 kV (LOAD)" bus button is gone. A new `LOAD (150kV)` toggle button sits alongside the 3 remaining voltage buttons (400/220/150); toggling it on and clicking the canvas places a bus fixed at 150.0 kV with `bus_type='LOAD'`, keeping the existing "Peak load MW" prompt dialog. `_place_bus()` now takes an explicit `bus_type` parameter instead of inferring it from voltage. Non-150kV LOAD buses are disallowed by design, matching reality.
- **Line ratings now fully tier-derived**: removed `DESIGNER_LINE_RATING_PRESETS`, `DESIGNER_DEFAULT_RATING`, `_cycle_line_rating()`, `_palette_line_rating`, the sidebar "LINE RATING:" [-]/[+] selector, and the `edit_rating_mw` free-text click-to-edit affordance. Both manual placement (`_place_line`) and auto-route (`make_line`) now call `LINE_RATING_MW_BY_VOLTAGE[vkv]` directly — one source of truth, shared with the real game. The properties-panel RATING field is now a read-only label (there is exactly one valid rating per tier, so a cycle/edit control would have nothing meaningful to do).
- Also removed the now-fully-unused `V_NOMINAL_60` constant and `COL_60KV` palette colour (confirmed via grep to have no other consumers). Left `COL_VVIEW_60KV`/`COL_BUS_60KV`/`COL_FLOW_60KV` untouched — those belong to the separate, already-shipped real-gameplay voltage-colour-view feature (Session 37), out of scope here; updated `COL_VVIEW_60KV`'s comment since it referenced the now-deleted `COL_60KV`.
- Edited: `src/simulation/constants.py` (removed `V_NOMINAL_60`, `DESIGNER_DEFAULT_RATING`, `DESIGNER_LINE_RATING_PRESETS`), `src/display/palette.py` (removed `COL_60KV`, fixed `COL_VVIEW_60KV` comment), `src/display/designer.py` (bus placement, line placement, auto-route, sidebar action handling, dead rating-cycle code all updated/removed), `src/display/designer_panels.py` (bus palette button list, new LOAD toggle button, removed LINE RATING selector, RATING field now read-only).
- Verified: 15/15 automated tests pass (no simulation code touched). Offscreen (pygame dummy driver) checks: placing a TRANSMISSION bus and a LOAD-toggled bus both work and store the correct `bus_type`/`voltage_kv`; a manually placed line between a 400kV and a 150kV bus rates at 175 MW (150kV standard) and a 400/220kV line rates at 400 MW (220kV standard); auto-route produces lines with the same tier-derived ratings; the legacy `grid1.json` (which contains 4 stray 60kV buses and old non-standard ratings from before this session) still loads and renders without crashing, confirming graceful backward-compatible loading with no migration needed; `shift10.json` re-confirmed to contain zero non-standard-tier buses; sidebar LOAD-toggle button hit-tests correctly and both toggle states render without error.

### Session 38 (Grid Designer — Rendering Parity, Static Analysis Panel, Shift 10 Import, Designer Boot)

- **Problem found (using the Designer to design the finale grid)**: the Designer's own edit-mode canvas drew plain straight bus-to-bus lines with no 8-point ports or obstacle-avoiding routing — visually inconsistent with `DESIGNER_TEST` mode and production gameplay, both already on the routed/ported renderer since Session 32/36 (flagged as out-of-scope in Session 32, picked up here). The Designer also had no way to test power-flow feasibility or N-1 security without leaving into a full live `DESIGNER_TEST` simulation session, and no way to load the real Shift 10 campaign grid for editing. User also requested the game boot directly into the Designer (skipping SPLASH/BRIEFING/MAIN_MENU) and the sidebar moved from the right edge to the left with the canvas expanded to fill most of the screen.
- **Sidebar relocation + canvas expansion**: `DESIGNER_SIDEBAR_W` 320→208px, now anchored at the **left** edge (`x=[0,208)`); canvas grows to `DESIGNER_CANVAS_W` = `NATIVE_WIDTH - DESIGNER_SIDEBAR_W` = 1712px (89.2% of native width) on the right. Palette (BUS/UNIT buttons) redesigned from a 2-column to single-column grid (`BTN_W` recomputed from the new sidebar width) since the old 296px-wide 2-column layout no longer fit; line-rating selector restacked to two rows. Coordinate space kept native (0-1920), not canvas-local — confirmed via `grid1.json`'s existing bus positions (range x=144-1241) and production `Renderer`'s own full-width `GridCanvas` usage that this was already the convention, so no save-format migration was needed, only a placement-bounds change.
- **Rendering parity**: `GridDesigner` now owns a `GridCanvas` instance internally (`_sync_canvas()`), fed via the previously-written-but-dead `designer_buses_to_topology`/`designer_lines_to_topology`/`designer_units_to_fleet` helpers in `designer_io.py` (their first real call site) and `GridCanvas.load_designer_topology()` — the exact same method `DESIGNER_TEST` mode already used. `_canvas_dirty` flag (set via a new `_mark_dirty()` helper that replaced all 18 `self._dirty = True` call sites) governs rebuild timing; live bus drag re-routes lines in real time except at full Shift-10 scale (41 buses/62 lines), where a full resync per drag-frame measured ~30-50ms (over budget) — the drag path now draws a cheap straight-line ghost for the dragged bus's own lines and defers the full resync to `on_mouse_up`. `_hit_line()` rewritten to walk `GridCanvas`'s routed waypoints via the shared `display.geometry.point_segment_dist` (replacing designer.py's private duplicate, now deleted), matching `renderer.py`'s production click hit-test exactly — confirmed clicking mid-bend on a detoured line now hits correctly. Selected-line highlighting (no equivalent in `GridCanvas`, which only supports gameplay's click-to-trip, not line-select) drawn as a designer-only overlay stroke along the same cached waypoints.
- **Static power-flow analysis panel**: new `src/simulation/designer_analysis.py` (pure functions, no pygame dependency) — `build_p_injections()`, `run_static_solve()` (one DC load flow via `DCLoadFlow`, honoring per-line in-service state), `run_n1_sweep()` (trips each in-service line in turn, re-solves via `DCLoadFlow.rebuild()`, and checks for islanding via `CascadeModel.find_islands()`/`get_blackout_zones()` — composes existing solvers, no new solver math, following the exact "static dispatch → P-injections → `DCLoadFlow.rebuild()` per contingency" methodology Sessions 35/36 used ad hoc), and `run_full_analysis()` (top-level: base-case solve + N-1 sweep + balance summary). Reuses `DesignerGrid` as-is (already fully `Grid`-duck-typed) and the previously-orphaned `DESIGNER_N1_OVERLOAD_PCT` constant (now its first real use). New `'analysis'` sidebar mode (`Ctrl+A`, mirrors the existing `save_dialog`/`load_browser` overlay pattern): shows DISPATCHED/LOAD/SLACK, INSTALLED/HEADROOM, and N-1 WORST/pass-count; RUN button triggers a solve. Per-unit dispatch MW and per-bus load MW are edited inline via the existing `_start_edit`/`_commit_edit` text-field pattern (new field names `analysis_unit_mw`/`analysis_bus_load_mw`, dispatch MW clamped to `[min_mw, rated_mw]`); per-unit availability and per-line in-service are single-click toggles in the properties panel. All four inputs are session-only parallel dicts on `GridDesigner` (`_analysis_unit_mw`/`_analysis_unit_available`/`_analysis_bus_load_mw`/`_analysis_line_in_service`), never persisted to the saved grid JSON. Canvas overlay shows colour-coded loading % per line (now importing `OVERLOAD_WARN_PCT`/`OVERLOAD_CRIT_PCT` instead of the old hardcoded 70/90 literals) and a dashed overstroke for out-of-service lines. The old `EXPORT PREVIEW` button/`_export_preview()` method (a strict subset of the new panel — flat rated_mw injection, no unit/line control) removed; `_auto_route_lines()`'s internal iterative solve switched from a bespoke duplicate DC load-flow (`_run_loadflow_on`, raw numpy B-matrix, ~90 lines) to the real `DCLoadFlow` via a throwaway `DesignerGrid` + `run_static_solve()`.
- **Shift 10 campaign grid import**: new `designer_io.py` functions `topology_buses_to_designer`/`topology_lines_to_designer`/`fleet_units_to_designer` (mirror direction of the existing dead-until-now Designer→real converters) and `import_shift_as_designer_grid(shift_number, name)`, which pulls the real `get_buses_by_shift()`/`get_lines_by_shift()`/`get_units_by_shift()` plus that shift's `SUBSTATION_LOAD_MW` table (via `load_shift_config()`) to compute per-bus `peak_load_mw` (topology.Bus itself carries no load value) and saves a named Designer grid. `DesignerLine` gained a `parallel: int = 0` field (previously dropped on conversion, meaning Shift 10's double-circuit spine segments would have rendered as visually collapsed single lines post-rendering-parity — caught before it became a real bug). New `IMPORT SHIFT 10` sidebar button (confirmation-gated if `shift10.json` already exists, the one genuinely destructive action this session added) generates and immediately loads `assets/designer_grids/shift10.json`.
- **Designer boot**: `src/main.py`'s non-debug boot branch now sets `game_state = GameState.DESIGNER` directly instead of unconditionally building a campaign sim and going to SPLASH/BRIEFING — unconditional per user direction (development-phase default, not gated behind a new debug flag), reverting to the normal campaign boot is a one-line change when needed. `_designer` stays `None` at boot (not pre-constructed) so the `DESIGNER` state handler's own lazy-init still runs and wires `on_test_request` correctly — pre-constructing it directly was tried first and found to silently break `TEST SAVED GRID` from a boot-time session (the callback wiring lives inside `if _designer is None:`). `shift = 10` kept as an unconditional default (previously only set inside the removed `else` branch) since a later unconditional line (`SHIFT_SPECS.get(shift)` for the briefing-state setup, run regardless of initial `game_state`) would otherwise raise `UnboundLocalError` — caught via an offscreen `main()` smoke test with a monkeypatched `pygame.event.get()`, not by manual play-testing.
- Added: `src/simulation/designer_analysis.py`, `tests/test_designer_analysis.py`, `src/assets/designer_grids/shift10.json`.
- Edited: `src/simulation/constants.py` (`DESIGNER_SIDEBAR_W`/`DESIGNER_CANVAS_W`), `src/display/designer.py` (rendering parity, analysis panel, import trigger, dead-code cleanup — `_VOLT_COLOUR`, `_point_segment_dist`, `_label_pos`, `_run_loadflow_on`/`_run_loadflow`/`_build_p_injections`, several now-unused palette/symbol imports all removed), `src/display/designer_panels.py` (single-column palette, analysis panel, properties-panel analysis rows), `src/data/designer_io.py` (`DesignerLine.parallel`, campaign→Designer conversion functions), `src/main.py` (boot change).
- Verified: 9/9 existing automated tests pass (no simulation code touched) + 6/6 new `test_designer_analysis.py` tests pass, including a cross-check against Session 36's own documented Shift 10 N-1 figures — built the real Shift-10 `Grid` with an independently-reconstructed water-filling dispatch and confirmed `run_n1_sweep()` reproduces the exact same worst-case contingency pair (L10 trip → L16 overload) at a magnitude consistent with the documented 182.3% (177.7-178.0% depending on dispatch-reconstruction rounding — the original exact dispatch was never committed to the repo, only described in prose), and confirmed the 10 substation-feed contingencies all stay well clear of that overall worst case (consistent with the documented 88.0% ceiling). Re-ran the identical sweep against the newly-imported `shift10.json` through `DesignerGrid` and got the same result (178.0%, same line pair), validating the import end-to-end. Offscreen (pygame dummy driver) checks: all 10 campaign shifts still render via `GridCanvas` with no exceptions (confirms the sidebar-width constant change didn't affect production rendering, which has no sidebar concept); Designer construction/draw/place/select/delete/undo/drag/auto-route/analysis-run/import-then-load all exercised directly with no exceptions across single-bus, empty, star-topology (5-line hub), and full Shift-10-scale (41/62/47) grids; a full `main()` boot-to-Designer smoke test (monkeypatched event queue, dummy video driver) confirmed the game reaches `GameState.DESIGNER` and constructs exactly one `GridDesigner` instance with no exceptions before a simulated QUIT.
- Not done this session (flagged, not started): no automated screenshot/pixel-diff verification of the rendering-parity visual match (relies on the offscreen exception-free checks above plus the shared `GridCanvas` code path already being proven via `DESIGNER_TEST`) — recommend a manual visual check (open Designer, build/load a grid, Ctrl+T into `DESIGNER_TEST`, compare) before relying on this further.

### Session 37 (Display — Voltage-Tier Colour View Toggle)

- **Feature added**: new `L` keyboard shortcut (Phase 2 real-time and Designer Test mode) toggles transmission lines and substation symbols between the existing load-state colouring (green→yellow→red by loading %) and a new voltage-tier colouring — 400kV bright cyan, 220kV bright red, 150kV bright green, 60kV yellow (60kV unused in current topology, colour included for completeness). Blacked-out, tripped, and selected visual states are unaffected and still take precedence in both modes.
- Added: `src/display/palette.py` — `COL_VVIEW_400KV/220KV/150KV/60KV` (new section, distinct from the pre-existing `COL_400KV`/`COL_220KV`/`COL_150KV` collector-line constants, which keep their original cyan/green/yellow values for their own unrelated use).
- Added: `src/simulation/constants.py` — `VOLTAGE_COLOUR_VIEW: bool = False`, toggled at runtime exactly like `AGC_ENABLED`.
- Edited: `src/display/symbols.py` — `draw_transmission_line()`, `draw_substation()`, `draw_load_substation()` each gained a `voltage_view: bool = False` parameter; when `True`, colour is looked up by voltage tier instead of computed from loading %. `draw_substation()`/`draw_load_substation()` also gained a `voltage_kv` parameter (previously not passed to either). Repointed the pre-existing but previously-unused `_VOLTAGE_COLOUR` dict at the new `COL_VVIEW_*` constants (was pointed at `COL_BUS_*KV`, itself dead code).
- Edited: `src/display/canvas.py` — `_redraw_to()` reads `simulation.constants.VOLTAGE_COLOUR_VIEW` (module-qualified import, so the runtime toggle is actually observed) and threads it into the line/substation draw calls, also now passing `bus.voltage_kv` to the substation calls. `_build_canvas_key()` includes the flag so the cached canvas surface invalidates immediately on toggle instead of waiting for unrelated state changes.
- Edited: `src/main.py` — added `L` handler in both the `PLAYING` and `DESIGNER_TEST` KEYDOWN blocks (gated by `not EDITOR_MODE and not renderer._input_active`, matching the S/X/T/C/A/Tab pattern); updated the controls docstring.
- Edited: `CLAUDE.md` — added `L` to the documented Phase 2 keyboard shortcut list.
- Verified: 9/9 automated tests pass (no simulation code touched). Offscreen render (pygame dummy driver) on the full Shift 10 schematic confirmed: toggling `VOLTAGE_COLOUR_VIEW` produces a different `_canvas_key` (forces redraw) each time it flips, reverts to an identical key when toggled back off, and pixel-sampled a 400kV bus (cyan), a 220kV bus (red), a 150kV bus (green), and a 400kV line segment (cyan) all render the expected colour in voltage view.

### Session 36 (Stage 28-29 — Regional Topology Restructuring + Obstacle-Avoiding Line Router)

- **Prompted by a reference photo** of a real national grid control room schematic (REN "Despacho Nacional", Portugal). Two design directives followed, both explicitly the "thorough" option over cheaper alternatives: (1) no diagonal lines, and lines must route around substations they don't connect to — a general obstacle-avoiding router, not hand-patches for known trouble spots; (2) regional zoning — the network should read as a 400kV spine connecting several distinct regions, where each region's 220kV/150kV mesh only reaches other regions via the spine, never via a direct lower-voltage tie that bypasses it — a real topology change, not just a visual reorganization, accepting the need for load-flow/N-1 re-verification. Per user direction, Shifts 1-3 were explicitly out of scope for this pass — design the best Shift 10 grid first, reconcile earlier shifts later.
- **Part 1 — six-region restructuring (Stage 28)**: promoted STAN, BRCK, FLDN, CO01 from 150kV to 220kV so SOUTH-MESH (STAN/BRCK/LD01-03, River Brent cascade) and EAST-MESH (FLDN/CO01-03/LD04-06, River Coln cascade) could each get their own pair of 400kV spine taps, exactly mirroring how CAP/WEST/EAST-POCKET already reach the spine. Deleted 8 lines that bypassed the spine (L18, L26, L27+L92, L29, L30, L31, L32); added 4 new spine taps (L155-L158) and 1 WEST-internal Arden loop-closer (L159, replacing L18's old role). This is a permanent `Bus` fact, so it also ripples into Shifts 3-9 wherever these buses already appear — tracked as follow-up, not fixed this session (same as prior sessions' precedent for out-of-scope shift reconciliation).
- **Part 1b — substation count 8→5 (discovered mid-session, not in the original plan)**: N-1 testing of the original 8-substation LD07-LD14 mapping (each region hosting up to 3 substations off only 2 spine-anchor buses) found a systemic problem, not a one-off: **any** region hosting 2+ substations off just 2 anchors overloads its internal ring/pocket under N-1, confirmed independently for both CAP (up to 325.7% on a feed trip) and WEST (198.7%), and structurally impossible to avoid in EAST-POCKET (only 1 usable non-anchor bus exists there). Per user direction, consolidated to **5 substations, one per non-SPINE region**, each dual-fed only from that region's own 2 spine-anchor buses: LD07 (CAP, merged former LD07+LD08, 1988 MW, on ASHF+FAIR), LD09 (WEST, merged former LD09+LD10+LD14, 2591 MW, on DUND+RDST), LD11/LD12/LD13 unchanged (EAST-POCKET/EAST-MESH/SOUTH-MESH). Verified numerically sound for both merged substations (CAP baseline 12.7%/worst N-1 81.2%; WEST baseline 45.7%/worst N-1 94.7%) before implementing.
- **Part 1c — CAP third spine tap (found during final re-verification)**: re-running the full N-1 sweep against the actual merged 1988 MW LD07 found a new overload the smaller-substation spot-check hadn't caught: tripping LD07's ASHF-side feed (L93) pushed the CAP ring (L15/L91/L16, all 220kV-tier lines rated 400 MW) to 160-176% carrying the full merged load through FAIR. User chose to give CAP a 3rd dedicated spine tap (L160, STHW→FAIR, 400kV/2250MW) rather than uprate the ring or split the substation back apart — re-verified this drops the worst case to 88.0% on L16. CAP is now the only region with 3 spine taps (all others still have exactly 2) — an accepted, documented asymmetry.
- **Part 2 — obstacle-avoiding line router**: added `src/display/geometry.py` (`point_segment_dist()`, shared by `canvas.py`'s router and `renderer.py`'s click hit-test — needed its own module because `renderer.py` imports `canvas.py`, not the reverse). Added `route_line()`/`_segment_clips_bus()` to `canvas.py`: tries the default vertical-then-horizontal bend, then the mirror bend, then one of 4 fixed 3-segment detour shapes offset around the clipping bus, falling back to the (cosmetically clipped) default bend only if nothing clears — deterministic, never raises, never loops unboundedly. Routing runs once per topology load (same cadence as `assign_line_ports()`), cached as `self._line_waypoints: dict[label -> [(x,y),...]]`, built in both `GridCanvas.__init__` and `load_designer_topology()` immediately after parallel-circuit offsetting (offsetting must happen first, per the original design constraint, so each double-circuit line routes independently from its own shifted position).
- All 5 previously-duplicated bend-point call sites now consume the cached waypoints instead of recomputing geometry: `canvas.py`'s tripped-line pre-bake (both campaign and designer variants) and main redraw loop; `symbols.py`'s `draw_transmission_line()` (signature changed to take a waypoint list, loops over consecutive pairs); `animation.py`'s `FlowAnimator.draw()` (parameter renamed `line_ports`→`line_waypoints`, its own `_parallel_offset_endpoints()` call removed since offsetting is now baked into the cache — critically, this function runs every frame and must never call the router itself, confirmed it doesn't); `renderer.py`'s click hit-test (now walks `zip(waypoints, waypoints[1:])`, imports `point_segment_dist` from `display.geometry` instead of a local duplicate definition, which was deleted).
- Edited: `src/simulation/constants.py` — removed `CONSOLIDATED_FEED_RATING_MW_PAIR`/`_QUAD` (no longer needed post-merge), kept `CONSOLIDATED_FEED_RATING_MW_TRIPLE = 1250.0` (LD11-LD13, unchanged), added `CONSOLIDATED_FEED_RATING_MW_CAP = 2400.0` (LD07, ~1988 MW peak) and `CONSOLIDATED_FEED_RATING_MW_WEST = 3100.0` (LD09, ~2591 MW peak).
- Edited: `src/data/topology.py` — promoted STAN/BRCK/FLDN/CO01 to 220kV; deleted L18/L26/L27/L92/L29/L30/L31/L32 (8 cross-region bypass lines); added L155-L159 (4 spine taps + 1 WEST loop-closer) and L160 (CAP's 3rd spine tap); deleted LD08/LD10/LD14 buses and their feed lines (L94/L131, L96/L133, L100/L137); re-sourced/re-rated L93/L130 (LD07, now `_RCAP`) and L95/L132 (LD09, now `_RWEST`, L132 re-sourced from AR01→RDST since RDST is WEST's other anchor); added `route_line()`/`_segment_clips_bus()`; updated module docstring throughout (41 buses, 62 lines at Shift 10, down from 44/70 pre-session but +1 net line vs. the mid-session 41/61 figure due to L160).
- Edited: `src/gameplay/shifts/shift_10.py` — merged LD08's hourly `SUBSTATION_LOAD_MW` curve into LD07 (sum per hour, verified peak still 1988 MW at 16:00), merged LD10+LD14's curves into LD09 (verified peak 2591 MW), deleted the LD08/LD10/LD14 entries; updated docstring, `HANDOVER_NOTES`, and T+0 scripted-event text for the 5-substation, 41-bus, 62-line finale. Total system peak unchanged at exactly 8,001 MW at hour 16:00 (pure aggregation, no demand added or removed).
- Added: `src/display/geometry.py` (new file) — `point_segment_dist()`.
- Edited: `src/display/canvas.py`, `src/display/symbols.py`, `src/display/animation.py`, `src/display/renderer.py` — see Part 2 above.
- **Methodology note**: continued using the deterministic water-filling-dispatch + direct `DCLoadFlow.solve()` verification method from Session 35 (via the real `Grid`/`DCLoadFlow` classes this time, not raw bus/line lists) — confirmed reliable again for reproducing exact N-1 loading percentages without frequency-runaway artifacts.
- Verified: 9/9 automated tests pass. Bus/line counts confirmed directly (41 buses, 62 lines at Shift 10). Full N-1 sweep across all 10 feed lines for the 5 final substations plus CAP's 3 spine taps: no blackouts, no islanding, worst case 88.0% (all substation-related trips); the grid's actual worst N-1 case overall is a **pre-existing, unrelated** WRNG-export issue (tripping L10 pushes L16 to 182.3% carrying WRNT's 800 MW of CCGT generation with no local demand) — confirmed present in the same form before this session's changes, tracked as a Known Issue, not fixed here. Offscreen render (pygame dummy driver) of the full Shift 10 schematic and targeted crops of every line the router detoured (6 of 62: L38, L157, L95, L99, L132, L136) — all detours visually clear their obstacle bus with no clipping; also verified the tripped-line (dashed) rendering path on 2 detoured/spine-tap lines. Constructed `GridCanvas` for all 10 shifts and confirmed a waypoint entry exists for every line with no mismatches.

### Session 35 (Stage 27 — Shift 10 Further Consolidation + West Hydro Pocket Re-layout)

- **Problem found (playtesting)**: after Session 34's 23→9 substation consolidation, the user reported the grid was "yet to[o] cluttered" and asked to reduce load substations further, and — on follow-up — confirmed the complaint was about the whole Shift 10 mesh, not just the load-substation layer. Two changes followed.
- **Part A — substation count 9→8 (attempted 7, partially reverted)**: the two remaining 2-way splits from Session 34 (LD07+LD14 on ASHF+AR01, LD08+LD15 on FAIR+AR02) were fully re-merged back to one substation each, landing on 7 total (LD07-LD13), needing 4 fewer buses and 4 fewer lines. A new `CONSOLIDATED_FEED_RATING_MW_QUAD = 1600.0` constant was added for the larger (~1303-1344 MW) merged loads. **Offscreen N-1 verification caught a real problem**: tripping the merged LD07's ASHF-side feed pushed the ASHF-FAIR ring circuits (L15/L91) to 119.5% loading — a genuine overload, not present at the smaller 9-substation size — because losing one feed of a ~1344 MW substation forces proportionally more of ASHF's total throughput onto the ring. LD08's equivalent check came back clean (FAIR's ring loading stayed at 1-3% after its own feed trip), confirming the problem was specific to ASHF's situation, not universal. **Reverted the LD07/LD14 merge** (kept the LD08/LD15 merge) — final count is 8 substations (LD07-LD14). Re-verification with a corrected N-1 impact showed the ring overshoot dropped to a marginal 104.8% (baseline 81.3%), accepted as a normal playable N-1 risk in the same spirit as the existing Shift 3 N-1 ring-congestion lesson, rather than requiring a further rating bump.
- **Part B — west hydro pocket re-layout (pure canvas positions, no electrical change)**: the base 36-bus grid's own west hydro pocket (DUND, RDST, KELD, AR01-AR04 — the River Arden cascade) was packed into a ~300×320px box, already violating the project's own documented layout rule (`GRID_TOPOLOGY_AND_DISPLAY.md` §8.1 Rule 4: max 4 nodes per 200×200px, min 80px spacing). Repositioned RDST, KELD, AR01, AR02, AR03, AR04 across a wider ~640×300px footprint (DUND and DUNM kept fixed — both anchor other regions). Verified by direct pairwise-distance computation against every other bus on the map (not just within the pocket): all distances clear 80px with real margin (worst case 92px). Also checked and ruled out two other candidate fixes: removing the Shift-10-only ring reinforcements L91/L92 (both confirmed load-bearing — removing either overloads its sibling circuit under *normal* operation, not just N-1) and repositioning STHW (its degree-6 connection count is 6 legitimate, non-redundant electrical roles with 2 slots of headroom under the 8-port render cap — not a fixable layout problem).
- Edited: `src/data/topology.py` — deleted `LD15` bus/lines permanently (Part A's LD08 merge), restored `LD14` bus and its 2 feed lines (`L100` BARD→LD14, `L137` KELD→LD14, both `_RPAIR`-rated) after the revert; re-rated `L94`/`L131` (LD08's feeds) to `_RQUAD`; repositioned the 6 west-pocket buses; updated module docstring and section comments throughout (44 buses, 70 lines at Shift 10).
- Edited: `src/gameplay/shifts/shift_10.py` — merged `LD08`+`LD15`'s hourly load curves, restored `LD07`/`LD14` as separate curves; updated docstring, narrative, `HANDOVER_NOTES`, and T+0 scripted-event text for the new counts (44 buses, 70 lines, 8 substations).
- Edited: `src/simulation/constants.py` — re-added `CONSOLIDATED_FEED_RATING_MW_PAIR = 800.0` (needed again for LD07/LD14 after the revert) alongside the new `CONSOLIDATED_FEED_RATING_MW_QUAD = 1600.0`.
- Edited: `src/data/fleet.py` — updated `STATION_POSITIONS` for KELD/AR01/AR02/AR03/AR04 to match the re-spaced bus positions, preserving each station square's visual offset from its bus.
- Edited: `src/assets/layout.json` — cleared entirely (was carrying live position overrides for RDST/AR02/AR03 plus stale orphaned entries for buses retired in Session 34) — matches the precedent set the last time the base grid's bus layout was redesigned.
- **Methodology note for future sessions**: offscreen N-1 verification via `GridSimulation.tick()` with a naive per-tick proportional rebalancer proved unreliable for this session's checks — `AGC_ENABLED=False` (Shift 10's deliberate manual-dispatch design) plus ramp-rate limits on thermal units let frequency run away to the 45 Hz floor within ~20 ticks regardless of RNG seed, after which the dispatch driving the load-flow numbers is no longer representative (confirmed via 3 different random seeds giving 3 different "worst line" results, none related to actual topology). Switched to a deterministic, non-tick-based check instead: build P-injections directly from a converged water-filling dispatch (starting from `INITIAL_SCHEDULE`, iteratively distributing the gen/demand gap proportional to headroom until converged) and solve `DCLoadFlow` directly — this avoids frequency dynamics entirely and gives reproducible, methodology-independent loading numbers. Recommend this approach (or an equivalent non-tick static solve) for any future Shift-10 offscreen verification.
- Verified: 9/9 automated tests pass. Bus/line counts confirmed directly (44 buses, 70 lines). Hub-bus degree recomputed: max degree 6 (ASHF, DUNM, STHW), all comfortably under the 8-port cap. West-pocket layout collision check: all repositioned buses clear the 80px minimum spacing rule against every other bus on the map, worst case 92px. N-1 sweep across all 8 substations (deterministic method): no blackouts, no islanding, all secondary feeds land in the 76-85% range. ASHF ring-circuit check after the LD07/LD14 revert: baseline 81.3%, N-1 (L93 trip) 104.8% — accepted as a playable risk per user decision.

### Session 34 (Stage 26 — Shift 10 Load Substation Consolidation)

- **Problem found (playtesting)**: after Session 33's dual-feed N-1 fix, the user reported "I have too many load substations - we need to concentrate some for gameplayability sake. The current grid mesh on the screen is a huge confusion." Investigation confirmed a real structural cause, not just a rendering nitpick: the 8-point substation connection port system (Session 32, `src/display/symbols.py`/`src/display/canvas.py`) hard-caps each bus at 8 usable line attachment points. Session 33's dual-feed fix (46 feed lines across 23 substations, sourced from only 14 hub buses) had pushed ASHF to degree 9 — already over the port cap — and DUNM to degree 8, with DUND/RDST/COAL/SLST/FAIR all at 7.
- **Root cause / opportunity**: direct inspection of the source-bus assignments in `src/data/topology.py` showed the 23 substations already fell into 7 natural groups sharing an identical (primary, secondary) source-bus pair (e.g. LD07/LD14/LD21/LD28 all fed from ASHF+AR01). Two groups had 4 members, five had 3. Consolidating same-group substations needs no new lines — duplicate feed pairs are simply deleted.
- **User-directed target**: rather than the maximal 7-substation merge (which would have pushed the two largest merged loads to ~1,300+ MW under N-1) or a forced ~12-substation split (which the natural grouping doesn't support without leaving wasteful unmerged "solo" leftovers), the user chose a 9-substation plan: split the two 4-member groups (ASHF/AR01, FAIR/AR02) into two pairs each (~650-690 MW), and fully merge the five 3-member groups (~950-1035 MW each).
- **Consolidation**: retired 14 of the 23 Shift-10 load substation buses (LD16-LD29), keeping LD07-LD15 as the 9 survivors, each carrying the exact hour-by-hour sum of its retired members' `SUBSTATION_LOAD_MW` curves (pure aggregation, system total unchanged at exactly 8,000 MW at hour 16:00). Deleted 28 now-redundant feed lines (14 retired substations × 2 feeds); kept and re-rated the 18 surviving feed lines.
- **New rating constants**: added `CONSOLIDATED_FEED_RATING_MW_PAIR = 800.0` and `CONSOLIDATED_FEED_RATING_MW_TRIPLE = 1250.0` to `src/simulation/constants.py`, following the same override pattern as `GENERATOR_CONNECTOR_RATING_MW` — a merged substation's surviving feed line must be able to carry the whole group's load alone under N-1, which the flat 400 MW 220kV tier cannot support once substations are merged.
- **N-1 coupling bug found and fixed during verification**: offscreen N-1 testing initially showed LD07 and LD08 (the two-way splits) blacking out when their primary feed was tripped, even though their secondary feed showed near-zero post-trip loading — not a stale-state artifact (confirmed by re-ticking after the trip). Root cause: LD14 and LD15 (their "sibling" substations from the same original 4-member group) still shared the exact same ASHF/AR01 and FAIR/AR02 source-bus pairs. Under DC load flow, tripping LD07's primary (L93, ASHF→LD07) shifted enough angle at the shared ASHF bus that LD14's own feed line (L137, also off ASHF) spiked to 113% and cascaded — the two "split" substations were never truly independent under N-1, just nominally on different lines. **Fixed** by re-sourcing LD14 to KELD+BARD and LD15 to WRNT+AR04 (both previously-unused-as-a-pair combinations, chosen from the lowest-degree hub buses) instead of reusing ASHF/AR01 and FAIR/AR02 — re-verified offscreen that tripping LD07's or LD08's primary feed no longer affects LD14/LD15 at all.
- Edited: `src/data/topology.py` — removed 14 `Bus` entries, removed 28 `Line` entries, re-rated 18 surviving feed lines (8 at `_RPAIR`, 10 at `_RTRIPLE`), re-sourced `L100`/`L137` (LD14) and `L101`/`L138` (LD15) away from the shared ASHF/AR01 and FAIR/AR02 pairs; updated module docstring and section comments (45 buses, 72 lines at Shift 10, down from 59/100).
- Edited: `src/gameplay/shifts/shift_10.py` — replaced 23 `SUBSTATION_LOAD_MW` entries with 9 summed entries; updated module docstring, `HANDOVER_NOTES`, and the T+0 scripted-event message text.
- Edited: `src/simulation/constants.py` — added `CONSOLIDATED_FEED_RATING_MW_PAIR`/`CONSOLIDATED_FEED_RATING_MW_TRIPLE`.
- Edited: `CLAUDE.md` — updated the Bus Labels note (LD07-LD15 in use, LD16-LD29 retired) and Line Labels note (gaps in the L91-L154 range are expected and permanent, labels are not recycled).
- Verified: 9/9 automated tests pass (Shift 10 changes don't touch any tested code path). Recomputed hub-bus degree directly from the final line list: ASHF 9→6, DUNM 8→6, DUND/RDST/COAL/SLST 7→5, FAIR 7→4, WRNT 6→5 — every hub bus now clears the 8-port render cap with real margin. Offscreen peak-hour (16:00) load-flow check: 7,729-7,999 MW generation/load balance under a naive proportional balancer, max line loading in the 91-98% range (no single line saturating). N-1 spot checks on all 9 substations (both 2-way splits and all five 3-way merges) confirmed no blackouts and no cross-substation cascade after the LD14/LD15 re-sourcing fix.

### Session 33 (Stage 25 — Shift 10 Redundancy Fix + Renewables Smoothing + Substation Naming)

- **Problem found (playtesting)**: mid-shift on Shift 10, many lines saturate with no way to resolve the congestion. Root cause confirmed by direct topology inspection: (1) all 23 Stage-24 load substations (LD07-LD29) had exactly one 220kV feed line each — a single point of failure, each carrying 290-360 MW at peak; (2) the River Brent (BRCK→BR01→BR02→BR03) and River Coln (FLDN→CO01→CO02→CO03) cascades are dead-end radial strings with no loop closure, unlike River Arden which is tied at both ends (DUND and DUNM) and is not a single point of failure; (3) Shift 10's new LD14/LD15/LD16/LD17/LD28/LD29 feeders tap directly off the Arden cascade buses (AR01-AR04), pushing new load through-flow across lines that also carry the cascade's own generation egress.
- User also requested: less erratic wind/solar output (previously resampled independent Gaussian noise every simulation tick, 10×/second, no smoothing); a handful of lines that are purely a hydro station's own connection to the grid rated generously (5000 MW) so generation dispatch itself is never the bottleneck; and real place names for load substations (LD01-29) and cascade-station buses (AR01-04, BR01-03, CO01-03), which previously only had generic ('Load Sub N') or station-code ('Arden 1') names, unlike every other bus in the grid.
- **Redundancy fix — dual-feed for LD07-LD29**: added 23 new 220kV lines (`L130`-`L152`), one per substation, each sourced from a different 220kV bus than the substation's existing primary feed (`L93`-`L115`). Source-bus assignment offsets the existing 14-bus source cycle by 7 (half the cycle) so each substation's two sources are electrically distant. This mirrors real transmission practice (dual-fed distribution substations from independent sources) rather than a cheaper tie-line-between-siblings approach that was considered and rejected as less realistic.
- **Redundancy fix — cascade loop closures**: added `L153` (BR03→LD03) and `L154` (CO03→LD05), both Shift-10-only, 150kV, closing the Brent and Coln cascades into loops the same way Arden already works. Earlier shifts (4-9) keep the original radial strings as their intentional N-1 teaching moment; only Shift 10's capacity-expanded grid gets the fix.
- **Generator connector lines**: added `GENERATOR_CONNECTOR_RATING_MW = 5000.0` to `constants.py`. Applied to exactly 7 lines confirmed as pure generation-egress (never carrying load through-flow in any shift): `L19` (RDST→KELD), `L39`/`L40`/`L41` (River Brent string), `L46`/`L47`/`L48` (River Coln string). Explicitly excluded `L20`-`L23` (Arden string — carries Shift-10 load taps, no longer pure generator egress) and `L25` (COAL→WNCN — an intentionally tight wind-gameplay constraint per existing code comment).
- **Renewables noise smoothing**: `RenewablesModel._apply_noise()` (`src/simulation/renewables.py`) changed from a stateless per-tick i.i.d. Gaussian resample to a rate-limited random walk — each tick samples a fresh Gaussian target as before, but the actual noise offset only moves toward that target at a bounded rate, mirroring the thermal ramp limiter in `UnitModel._tick_online()`. Added persistent per-unit noise state (`_wind_noise_state`, `_solar_noise_state`) to `RenewablesModel`. Added `WIND_NOISE_RAMP_PCT_MIN = 20.0` and `SOLAR_NOISE_RAMP_PCT_MIN = 30.0` to `constants.py`, and renamed the existing `# DEMAND NOISE` section header to `# RENEWABLES NOISE` (it was mislabeled — `demand.py` has no noise of its own; the two existing constants there are exclusively used by `renewables.py`). `RenewablesModel.update()` now requires a `dt_sim_seconds` argument; updated all call sites (`src/simulation/simulation.py` main tick, forecast-mode snapshot, and Phase-1 preview loop) and all test call sites in `tests/test_simulation.py`.
- **Substation naming**: gave all 29 load substations (LD01-LD29) and all 10 cascade-hydro buses (AR01-AR04, BR01-BR03, CO01-CO03) distinct fictional place names in the `Bus.name` field (e.g. `AR01` bus renamed to `'Ardenbridge'`, `LD07` to `'Ottermead'`), matching the convention used everywhere else in the grid. Only `Bus.name` changed — `label` fields (`LD07`, `AR01`, etc.) and `GenerationUnit.station_label`/unit labels (`AR01-1`, etc.) are untouched, since labels are the stable identifier used throughout code, save files, `layout.json` overrides, and scripted-event/scoring hooks. Confirmed via grep that `Bus.name` is only read in the Grid Designer sidebar (`src/display/designer_panels.py`), so this is a purely cosmetic, low-risk rename.
- Edited: `src/data/topology.py` — module docstring and section comments updated for the new Shift 10 totals (59 buses, 100 lines); import of `GENERATOR_CONNECTOR_RATING_MW` added alongside `LINE_RATING_MW_BY_VOLTAGE`.
- Edited: `src/gameplay/shifts/shift_10.py` — module docstring updated (100 lines, mentions dual-feed + cascade loop closures).
- Edited: `CLAUDE.md` — Bus Labels convention extended to cover LD07-LD29 and the cascade connection buses' new place-name pattern; Line Labels convention extended past L45 to the current L01-L154 range.
- Verified: 9/9 automated tests pass (updated 3 test call sites in `test_renewables_model` for the new `RenewablesModel.update()` signature — behavior itself unchanged in deterministic mode, confirmed exact match against `get_wind_mw`/`get_solar_mw`). Offscreen load-flow check at Shift 10's 16:00 peak hour (8,001 MW load, ~7,806 MW generation under a naive proportional balancer) — max line loading 93.4%, no line over 94%. N-1 spot checks: tripping `L93` (LD07's old sole feed) no longer blacks out LD07 — secondary feed `L130` picks up the load at 85.5% loading; tripping `L39` (River Brent's old sole egress) no longer blacks out BR01/BR02/BR03 — loop closure `L153` carries the reroute at 85.7% loading; tripping `L46` (River Coln's old sole egress) no longer blacks out CO01/CO02/CO03 — loop closure `L154` carries the reroute at 78.9% loading. Confirmed renewables noise is now smooth tick-to-tick (e.g. a 300 MW wind unit moves at most ~0.1 MW per 0.1s tick, vs. previously being able to jump by its full ±3σ range instantly).

### Session 32 (Display — 8-Point Substation Connection Ports)

- **Problem**: every transmission line connected bus-centre-to-bus-centre with no attachment-point concept at all — at busy substations (ASHF and DUNM both reach degree 7 by Shift 10; STHW, DUND, RDST reach degree 6) many lines converged on the exact same pixel, making it hard to trace which line is which. Requested improvement: expand to 8 distinct connection points per substation (roughly clock positions), assigning each line to the point closest to its bearing toward the other bus.
- Design constraint: `GRID_TOPOLOGY_AND_DISPLAY.md` §8.1 Rule 3 mandates no diagonal line segments. The 8 points are therefore 2 per side of the substation square (N/S/E/W, not true 45° compass points) so every line still departs strictly horizontally or vertically before the existing single-bend routing takes over.
- Added: `src/display/symbols.py` — `PORT_EDGE_INSET_FRAC`, `PORT_OFFSETS` (8 fixed `(side, slot) → (dx_frac, dy_frac)` offsets in units of `BUS_SIZE`), `get_port_point()` helper. `BUS_SIZE` increased 12→18px so the 8 points are visually distinguishable (this also resizes substation squares in `draw_substation`/`draw_load_substation` and in `src/display/designer.py`'s own bus-square rendering, which imports `BUS_SIZE` directly — confirmed as an acceptable, desired global visual bump, not a regression).
- Added: `src/display/canvas.py` — `assign_line_ports()`: for each bus, buckets its connected lines into N/S/E/W by the dominant axis of the bearing to the line's other (raw) endpoint, then orders same-side lines by the secondary coordinate and assigns the 2 slots on that side (closest first). Ties break toward N/S, then by line label, for determinism. Buses with >2 lines on one side (never occurs in shipped topology — max degree is 7) stack the overflow onto the nearest of the 2 slots rather than erroring. Result is cached once per canvas build as `self._line_ports: dict[line_label, (fx, fy, tx, ty)]`, called from both `GridCanvas.__init__` and `load_designer_topology()`.
- Edited: `src/display/canvas.py` — main redraw loop, tripped-line pre-bake (campaign and designer-topology variants) now look up `self._line_ports[line.label]` instead of raw `self._bus_pos` centres; `_parallel_offset_endpoints()` (double-circuit pixel offset) applies unchanged on top of the resolved ports.
- Edited: `src/display/renderer.py` — `on_click()` line hit-testing now uses `self._canvas._line_ports` instead of raw bus centres, so click targets track the new port positions.
- Edited: `src/display/animation.py` — `FlowAnimator.draw()` signature changed from `(surf, state, bus_map, lines)` to `(surf, state, line_ports, lines)`. This was also a pre-existing correctness fix: the old code computed marker paths as a straight diagonal from **unscaled** `Bus.canvas_x/canvas_y` onto the display-scaled canvas surface (misaligned at any non-1.0 display scale) and ignored the orthogonal bend entirely. Markers now walk the same scaled, bend-aware two-segment path as the drawn line. Updated call site in `src/display/renderer.py` (`self._flow.draw(self._canvas_surf, state, self._canvas._line_ports, self._canvas._lines)`).
- Verified: 9/9 automated tests still pass (display-only change, no simulation code touched). Offscreen render (pygame dummy driver) across Shifts 1, 3, 7, 10 — all render without error, every line resolves a port entry. Confirmed ASHF (Shift 10, degree 7) fans its 7 lines across 6 distinct points (1 documented 3-way overflow on the N side, resolved deterministically) instead of all converging on the bus centre — screenshot-checked. Verified line-click hit-testing selects the correct line at its new offset position (and still selects the bus, not a line, when clicking the bus centre). Verified `load_designer_topology()` also resolves ports correctly with a hand-built 5-line star topology (two lines sharing a side split into distinct slots).
- Out of scope (flagged, not changed): `src/display/designer.py`'s own live in-editor canvas draws independent straight bus-to-bus lines (`pygame.draw.line`, no bend, no ports) — a separate, simpler rendering path used only while placing buses/lines in the Grid Designer, not the topology-preview path exercised above.

### Session 31 (Stage 24 — Shift 10 Capacity Expansion + Finale Rewrite)

- **Problem found**: while writing Shift 10's dispatch/demand tables, an offscreen `GridSimulation` smoke test showed the existing topology could not deliver the campaign's own 8,000 MW Shift-10 peak — all demand terminates at 6 load buses (LD01-LD06) fed through only 5 transformer links (combined ~3,600 MW safe capacity). Individual buses like LD01 (peak 2,106 MW) and LD03 (peak 1,466 MW) vastly exceeded their single feed line's rating. Confirmed the true simultaneous system peak (all 6 buses at hour 16:00) is exactly 8,000 MW — this is the shift's designed climax, not an edge case.
- User directed a full fix rather than a workaround: (1) redesign the 150kV load layer with more substations, (2) normalize every line's rating to one flat value per voltage tier (not per-role as before), using new values **400kV=2250 MW, 220kV=400 MW, 150kV=175 MW**.
- Added: `src/simulation/constants.py` — `LINE_RATING_MW_BY_VOLTAGE: dict = {400.0: 2250.0, 220.0: 400.0, 150.0: 175.0}`.
- Edited: `src/data/topology.py` — every one of the 50 existing `Line` entries now sources `rating_mw` from `LINE_RATING_MW_BY_VOLTAGE[voltage_kv]` instead of a per-line literal (imported as `_R400`/`_R220`/`_R150` module constants). Added 23 new `Bus` entries (LD07-LD29, `bus_type='LOAD'`, `active_from_shift=10`) with hand-placed non-colliding canvas positions across previously-open map regions. Added 23 new `Line` entries (L93-L115, one dedicated 220kV feed per new substation, cycling through 14 existing 220kV source buses). Added 2 new parallel-circuit `Line` entries (L91 second ASHF↔FAIR circuit, L92 second RDST↔DUNM circuit) — both `active_from_shift=10` — after an automated convergence search (see below) found these two pre-existing 220kV ring lines remain the binding constraint even after the load layer is redistributed.
- **Methodology**: hand-guessing the new substation count repeatedly failed (5 → 12 → 19 new links, each round revealing a new bottleneck one layer up: 150kV feed → 220kV ring → 400kV spine). Converged instead with a scratch automated search script (not part of the codebase, run from the session scratchpad) that built candidate topologies, ran the real `GridSimulation` against Shift 10's actual 8,000 MW peak-hour demand with the fleet dispatched near rated capacity, found the worst-loaded line each round, and either added more load-feed links or a parallel circuit to the specific bottleneck line. Converged in 4 rounds to 23 new links + 2 ring reinforcements, max line loading 82.6% at the true peak hour.
- Rewritten: `src/gameplay/shifts/shift_10.py` — full finale scenario. `INITIAL_SCHEDULE` dispatches ~3,230 MW at 06:00 across nuclear/coal/CCGT/hydro tiers (THNF-3 on planned maintenance) with deliberate reserve headroom for the day's ramp. `SUBSTATION_LOAD_MW` now covers all 29 load buses — LD01-LD06 keep a small ~5% residual of their old standalone curves, the remaining ~95% is redistributed (with slight per-bus variance, not a flat split) across the 23 new substations, preserving the exact 8,000 MW system peak at hour 16:00. `SCRIPTED_EVENTS`: shift-start briefing, a wind-lull/solar-ramp warning with a reserve-margin-conditional follow-up (`_reserve_below_600mw`/`_reserve_at_or_above_600mw` helpers using `fleet.spinning_reserve_mw()`), an L03 (MDBY-STHW second circuit) scheduled-maintenance N-1 test window, and an evening-peak CCGT-staging warning (`_ccgt_below_1000mw` helper using `fleet.get_unit(label).current_mw` — the correct, existing `FleetModel` API, not the broken pattern in shift_03.py, see Known Issues). `SCORING_HOOKS`: bonus/penalty tied to L02 loading during the L03 outage window, mirroring the shift_03.py pattern.
- Verified: offscreen load-flow check at 06:00 (max loading 89.7%, freq stable 50 Hz) and a 600-simulated-minute gradual-tick run to the 16:00 peak under several different naive auto-balancing strategies — **line loading stayed under ~97% throughout every test**, confirming the topology fix works. Frequency instability/cascade events seen in these naive tests were confirmed to be a **pre-existing simulation characteristic, not a regression** — the same immediate frequency saturation (df/dt runaway to the 45/55 Hz hard clamp within 1-2 minutes) reproduces identically on unmodified Shift 8 with its own existing dispatch, whenever generation and load aren't kept in close proportional balance every tick. This is expected given `AGC_ENABLED=False` (the deliberate "manual dispatch finale" design) — a human player continuously trims output; a naive scripted balancer does not. Not something this session's topology change caused or could fix.
- Verified: offscreen render (pygame dummy driver) — all 59 buses / 75 lines draw without error or exceptions; screenshot-checked the 06:00 layout for gross collisions (minor crowding near HART/ASHG and DUND, no unreadable overlaps).
- Validated: 9/9 tests pass (no simulation-code changes, only data/constants — `tests/test_simulation.py` untouched and unaffected).

## Known Issues (new/updated this session)

- **Shifts 7-9 have a disconnected island (new this session, deferred by user request)**: deleting the old L18/L26/L27/L31/L32 cross-region ties as part of Session 36's regional restructuring stranded EAST-MESH (FLDN/CO01-03/LD04-06, 7 buses) at Shifts 7-9 — its replacement spine taps (L157/L158) are `active_from_shift=10` only, so between the region's Shift-7 introduction and Shift 10's capacity expansion it has no path to the rest of the grid. Confirmed directly via `test_cascade_model` (`Grid(7)` now partitions into 2 islands instead of 1) and by re-running the island check standalone. Shift 10 itself is fully connected (1 island, 41 buses). **User explicitly directed deferring this** ("Focus on Shift10 - ignore any issue with other Shifts. Will take care of that later.") — tracked here as a blocker for Shifts 7-9 being playable as currently written, not fixed this session.
- **Pre-existing WRNG-export N-1 issue (found during this session's verification, not caused by it)**: tripping L10 (CNTR→WRNT, one of CAP's 2 original spine taps) pushes L16 (FAIR-WRNT ring segment, 220kV/400MW-rated) to 182.3% loading. Root cause: WRNT hosts 800 MW of CCGT generation (WRNG-1/2) with zero local demand, so losing its only spine tap forces the entire generation export through the ring instead. Confirmed via direct comparison that this reproduces identically on the pre-session committed topology (i.e., it predates Session 36's substation/spine-tap changes entirely) — out of scope for this session's substation-focused redesign, but worth a dedicated look (likely fix: a 2nd spine tap for WRNT specifically, or accept as a Shift-10 N-1 teaching moment the way Shift 3's ring congestion already works).
- **Shift 3's N-1 lesson is confirmed at risk of regression** from the Session 31 rating normalization. L15/L16 (the capital ring lines Shift 3's `_l15_high_load`/`bonus_n1_secure`/`penalty_ring_congestion` are tuned around) drop from 800 MW to 400 MW; L09 (the STHW↔ASHF tap that carries ~90% of flow before the outage) rises from 1200 MW to 2250 MW. Both changes shift the MW flow needed to cross the existing 80%/85%/90% percentage thresholds substantially, in opposite directions from each other. **Attempted to verify directly and could not**: `shift_03.py`'s own condition helpers (`_ashg1_below_250mw`, `_l15_high_load`) call `fleet.get_output_mw(...)` and expect a `grid` object — neither matches the real `FleetModel`/`GridSimulation._process_scripted_events()` API (which only ever calls `cond(self._fleet)`, and `FleetModel` has no `get_output_mw` method, only `get_unit(label).current_mw`). This is a **pre-existing bug**, not introduced this session — it crashes Shift 3 with an `AttributeError` as soon as sim time reaches the T+90 event (confirmed via direct reproduction). Shift 3 has therefore likely been unplayable past minute 90 since it was written, independent of this session's changes. Spot-checked L15/L16 loading up to that point (~3.3%, far below the ~90% the tutorial expects) but the result is inconclusive because frequency had already run away for unrelated reasons (see above) by the time of measurement. **Follow-up required**: fix the `shift_03.py` condition-helper API mismatch first, then re-verify/re-tune the N-1 lesson's thresholds against the new L09/L15/L16 ratings.
- Shifts 4-9 scenario files remain stale (pre-existing, unchanged this session) and now additionally inherit the flat per-voltage-tier line ratings from Session 31, which were not re-tuned for them specifically — tracked as part of the existing Stage-24-adjacent follow-up (rewrite Shifts 4-9), now with the added note that their line-rating assumptions (if any were hand-tuned per-role) need re-checking too.

### Session 30 (Stage 23 — Full Grid Topology Redesign)
- Full clean-sheet redesign of the campaign grid and fleet, inspired by the structure of a small European transmission system (400/220/150kV ladder, hydro-heavy west, thermal/nuclear spine, wind+solar east) while keeping the existing fictional world and station names.
- Rewritten: `src/data/topology.py` — 36 buses (30 transmission + 6 load), 50 lines. 400kV spine (WEST-MDBY-STHW-CNTR-NRTH-EAST) with double circuits on the two middle segments (`Line.parallel` field, new) and a Shift-8 southern sag (STHW-EAST). Three 220kV pockets (capital ring, west hydro, east). Two meshed 150kV rings whose members include the load substations (LD01-06), so a feeder trip reroutes instead of instant-blackout. Grid completes at Shift 8 (was Shift 5); slack bus remains MDBY, active from Shift 1 as required.
- Rewritten: `src/data/fleet.py` — all 47 units re-sited proportionally to the new regions (HART moved CNTR→STHW, BARR moved EAST→NRTH, DUNH moved STHW→MDBY, WNCN split 1×500→2×250 so wind trips are partial, CO03 gained a 2nd unit for cascade symmetry); `STATION_POSITIONS` rewritten to match.
- Edited: `src/data/profiles.py` — `SHIFT_SPECS` grid_size/peak_demand_mw re-staged for all 10 shifts (55MW → 8,000MW), matching the new unlock table.
- Rewritten: `src/gameplay/shifts/shift_01.py`, `shift_02.py`, `shift_03.py` — re-tuned on the new topology (new line labels L11/L49/L50 replacing old L46/L47/L48; Shift 3's N-1 lesson rebuilt around L09 STHW↔ASHF and the capital ring instead of the old L09 CNTR↔WRNT).
- Edited: `src/data/topology.py` `Line` dataclass — added `parallel: int = 0` field (display-only, no electrical meaning) marking which side of a double-circuit pair a line is drawn on.
- Edited: `src/display/symbols.py` — added `PARALLEL_LINE_OFFSET_PX = 10` constant.
- Edited: `src/display/canvas.py` — added `_parallel_offset_endpoints()` helper (perpendicular pixel offset based on `Line.parallel`); applied at both the pre-baked tripped-line surface and the live transmission-line draw call. Fixed `_HYDRAULIC_CONNECTORS` (stale from old topology: was STHW↔DUND/WEST↔KELD/EAST↔BARD; corrected to MDBY↔DUND/WEST↔KELD/NRTH↔BARD to match the new upper/lower pumped-storage station siting).
- Edited: `src/display/renderer.py` — line hit-testing (`on_click`) now applies the same parallel offset so clicks land on the visually-offset circuit.
- Edited: `src/display/animation.py` — `FlowAnimator.draw()` applies the same offset to flow-marker paths so markers track the offset line instead of the raw bus-to-bus segment.
- Fixed: `src/simulation/grid.py` — `get_load_at_bus()` was calling `get_substation_demand_specs(self._shift_number)` (an int) when the function expects a `{bus_label: {hour: mw}}` table; this is the pre-existing regression noted in Known Issues. Fixed by loading `SUBSTATION_LOAD_MW` via `load_shift_config()` once in `__init__` and caching the built specs.
- Reset: `src/assets/layout.json` — cleared (backed up to `layout.json.pre-redesign-backup`); all manual position overrides were keyed to the old bus layout and would have mis-placed or silently no-op'd against the new one.
- Edited: `tests/test_simulation.py` — updated all hardcoded bus/line labels and shift numbers to match the new topology (L46/L47/L48→L11/L49/L50; CNTR→STHW for HART; Shift-5-is-full-grid→Shift-7-is-full-grid; WNCN-1 rated_mw 500→250; cascade-model transformer cut set L08-L11→L09/L10/L11/L12/L13/L14). Also fixed the same `get_substation_demand_specs()` signature bug directly in `test_demand_model`. All 9 tests now pass (previously 3/9 pre-existing failures, per Known Issues below — those are now resolved as a side effect).
- Verified: per-shift adequacy (firm capacity vs peak demand) matches the design table for Shifts 1-8; N-1 spot checks confirm Shift 8 double-circuit reroute (16%→28% on remaining circuit) and Shift 3 ring reroute (5%→24% on L15/L16) behave as designed; offscreen render check (pygame dummy driver) confirms Shifts 1, 3, 4, 7, 8 draw without error and double circuits are visually distinct.
- Validated: 9/9 tests pass.

### Session 27 (Shift 3 Design — N-1 Redundancy)
- Designed Shift 3 as a 10-bus intermediate grid teaching N-1 security (L09 planned maintenance at 16:00)
- Edited: `src/data/topology.py` — deferred EAST, WEST, RDST, COAL, DUNM, KELM, BARR, BARD, KELD, WNCN, ASHG, BRCK, BR01-BR03, LD06 from Shift 3→4; deferred associated lines (L07, L11, L14-L18, L21, L22, L25, L28, L30, L31, L37, L42-L45) from Shift 3→4; fixed L23 (FLDN→STAN) from Shift 3→5 (FLDN is Shift 5); upgraded L38 (STAN→LD02) from 400→1200 MW; removed `active_until_shift=2` from L46, L47, L48 (now permanent); updated docstring, bus section comments
- Edited: `src/data/fleet.py` — ASHG-1, ASHG-2: `bus_label` 'ASHG'→'ASHF' (ASHG bus deferred to Shift 4; units connect at ASHF 220kV bus in Shift 3)
- Edited: `src/data/profiles.py` — ShiftSpec[3]: grid_size 20→10, peak_demand_mw 3800→1480; ShiftSpec[4]: grid_size 20→28
- Written: `src/gameplay/shifts/shift_03.py` — full scenario: HART-1 680 MW baseload, L09 opens 16:00 (MAINTENANCE_LINES action), WRNG-1 key redispatch tool, SLST-1 declining solar; MAINTENANCE_LINES = {'L48'} (L48 must be opened at shift init to prevent DUND→LD02 shortcut); scripted events T+0/+60/+90/+120/+300; SCORING_HOOKS for N-1 bonus and ring congestion penalty

Shift 3 active set (10 buses, 10 lines):
  Buses: MDBY, CNTR, STHW (400kV) | ASHF, FAIR, WRNT, SLST, WRNG (220kV) | STAN, LD02 (150kV)
  Lines: L01, L06, L08, L09, L12, L13, L19, L20, L29, L38 (+ L46/L47 visible, L48 open)

MAINTENANCE_LINES implementation complete (Session 28):
  L48 is opened before the first load-flow solve in Shift 3 via the new MAINTENANCE_LINES mechanism.

### Session 28 (MAINTENANCE_LINES implementation)
- Edited: `src/gameplay/shifts/loader.py` — added `'maintenance_lines': getattr(mod, 'MAINTENANCE_LINES', set())` to `load_shift_config()` return dict
- Edited: `src/main.py` — added `maintenance_lines=cfg['maintenance_lines']` to `GridSimulation()` call in `_make_sim_and_renderer()`
- Edited: `src/simulation/simulation.py` — added `maintenance_lines: set | None = None` parameter to `GridSimulation.__init__`; after `_line_in_service` is built, stores as `_maintenance_lines` frozenset, applies to `_line_in_service`, and calls `_loadflow.rebuild()` + `_voltage.rebuild()` before `_solve_and_snapshot()`; rebuild is guarded by `if self._maintenance_lines:` to skip on shifts with no maintenance lines
- Validated: 9/9 tests pass

### Session 29 (Shift 3 — four playtesting corrections)
- Edited: `src/data/topology.py` — L29 (SLST→STAN) rating_mw 500→700 (was overloaded by SLST-1's 576 MW solar output at 14:00); L47 (DUND→LD01) rating_mw 200→500 (LD01 now carries 350–450 MW in Shift 3)
- Edited: `src/data/profiles.py` — ShiftSpec[3]: peak_demand_mw 1480→1930 (combined LD01+LD02 peak)
- Rewritten: `src/gameplay/shifts/shift_03.py` — INITIAL_SCHEDULE: added DUND-1 (30 MW), DUNH-1 (80 MW), reduced RVSD-2 90→50 MW; AGC_ENABLED: False→True; SUBSTATION_LOAD_MW: added LD01 profile (350 MW at 14:00, peaking 450 MW at 18:00); HANDOVER_NOTES updated to reflect actual SLST-1 output (~576 MW), new hydro units, LD01 load, AGC active
- Root cause of "L40 trips": L40 (STAN→LD04, active_from_shift=5) is inactive in Shift 3. Actual culprit was L29 overloaded by solar. Fixed by L29 rating upgrade and LD01 load addition.
- Validated: 9/9 tests pass

### Session 26 (Shift 1-2 Tutorial Grid Topology Redesign)
- Edited: `src/data/topology.py` — L46 rating 300→500 MW (400kV standard); L47 changed from 150kV/350MW/0.120pu to 220kV/200MW/0.080pu; new L48 added (DUND→LD02, 220kV, 200MW, 0.080pu, active_until_shift=2); LD02 active_from_shift 3→1; module docstring and section comments updated
- Edited: `src/data/profiles.py` — Shift 2 demand split 55%/45% between LD01 (peak 173MW) and LD02 (peak 142MW); total unchanged at 315MW peak
- Edited: `tests/test_simulation.py` — fixed expected_lines_3/5 to filter by active_until_shift; updated test_loadflow_solves to use Grid(1) L47/L48 instead of removed Grid(1) lines L08/L14; updated test_unit_model FleetModel and test_simulation_model set_unit_target to use units in the active grid (pre-existing failures from Session 24 when CNTR/HART moved to Shift 3)
- Validated: 9/9 tests pass

New Shift 1-2 topology:
  MDBY (400kV) ──L46 (500MW)──► DUND (220kV) ──L47 (200MW)──► LD01 (150kV)
                                               └──L48 (200MW)──► LD02 (150kV)

### Session 25 (Canvas Load Substation Fix + Live Load in Context)
- Edited: `src/display/canvas.py` — Layer 6 now dispatches `draw_load_substation()` for `bus_type == 'LOAD'` buses and `draw_substation()` for all others; fixes LD01 rendering with downward-triangle symbol and reveals DUND/DUND-1 as a proper transmission node
- Edited: `src/simulation/simulation.py` — added `bus_loads: dict` field to `SimulationState`; populated in `_build_state()` from `self._demand.get_bus_demand_mw()`
- Edited: `src/display/context.py` — `draw_bus_context()`: header tag changes to 'LOAD' for load buses; panel grows to 3 rows; third row shows live demand MW
- Validated: 9/9 tests pass

### Session 24 (Shift 1 Rewrite — Minimal Tutorial Grid)
- Edited: `src/data/topology.py` — added `active_until_shift: int = 99` field to `Line` dataclass; updated `get_lines_by_shift()` to filter on both bounds; pushed 6 buses (CNTR, STHW, ASHF, RDST, DUNM, BRCK) and 8 lines (L01, L06, L08, L14, L15, L22, L28, L37) from `active_from_shift=1` to `active_from_shift=2`; added tutorial-only lines L46 (MDBY↔DUND, 400kV transformer link) and L47 (DUND↔LD01, 150kV feeder), both `active_until_shift=1`; updated docstring comment
- Edited: `src/data/profiles.py` — ShiftSpec[1]: start_hour=4.0, duration_hours=3.0, grid_size=3, peak_demand_mw=55.0, difficulty_label='Tutorial', new handover_notes; SUBSTATION_LOAD_MW[1]['LD01']: rescaled entire 0–24h table from 2200 MW to 55 MW peak
- Edited: `src/main.py` — `_SHIFT_SCHEDULES[1]`: replaced multi-unit handover with single entry `'DUND-1': 18.0`
- Validated: 9/9 tests pass

### Session 23 (Stage 22 — Load-State Line Colouring)
- Edited: `src/display/palette.py` — added `COL_LINE_ENERGISED` (40,160,80); updated `COL_LINE_NORMAL` comment
- Edited: `src/display/symbols.py` — `draw_transmission_line()`: removed voltage→colour lookup dict; `base_col` is now always `COL_LINE_ENERGISED`; updated import and docstring
- Validated: 9/9 tests pass

### Session 22 (Stage 21 — Line Trip/Close Commands)
- Edited: `src/display/context.py` — added `cmd_active` param to `draw_line_context()`; added row 6 TRIP/CLOSE button (red/green border matching line status); panel height dynamic (+1 row when status is known)
- Edited: `src/display/renderer.py` — added `_line_cmd_active` flag; added `_get_selected_line()`; added `on_trip_line()` and `on_close_line()` methods (guard: correct status, calls sim); updated `clear_selection()`, `on_escape()`, and `tick()` line context call
- Edited: `src/main.py` — T=trip line, C=close line key handlers; updated module docstring
- Validated: 9/9 tests pass

### Session 21 (Stage 20 — Generation Mix Panel + Forecast Load Overlay)
- Edited: `src/simulation/constants.py` — resized PANEL_FREQ/POWER/DISPATCH/ALARM_W to make room; added PANEL_GENMIX_X/W (1000/260); added FORECAST_OVERLAY_W/H/PAD constants
- Edited: `src/simulation/simulation.py` — added `gen_mix_mw: dict` field to `SimulationState`; populated in `_build_state()` by summing ONLINE unit outputs per fuel type
- Edited: `src/display/palette.py` — added `COL_FORECAST_DEMAND` and `COL_FORECAST_NETLOAD`
- Edited: `src/display/panels.py` — added `draw_genmix_panel()`: one row per active fuel type (NUCLEAR/COAL/CCGT/HYDRO/ROR/PUMP/WIND/SOLAR), MW + % + mini coloured bar; reuses existing COL_UNIT_* type colours
- Edited: `src/display/renderer.py` — added PANEL_GENMIX_* and FORECAST_OVERLAY_* imports; added GEN MIX subsurface + draw call in strip; added `_draw_forecast_overlay()` method drawing demand bars + net-load bars + current-time cursor + legend on canvas top-right
- Validated: 9/9 tests pass; visual check confirms both panels render correctly

### Session 20 (Stage 19 — AGC Debug Indicator + Input Fix + Demand Noise Smoothing)
- Edited: `src/simulation/constants.py` — added `DEMAND_NOISE_UPDATE_S = 60.0` (simulated seconds between noise re-samples)
- Edited: `src/simulation/demand.py` — added `_noise_fraction` and `_noise_timer_s` state; `update()` gains `dt_sim_seconds` param; noise re-sampled only when timer exceeds `DEMAND_NOISE_UPDATE_S` instead of every tick
- Edited: `src/simulation/simulation.py` — pass `dt_sim_seconds` to `demand.update()`
- Edited: `src/display/renderer.py` — add `COL_TEXT_DIM` import; add AGC ON/OFF indicator to `_draw_debug()` (top-right, second line)
- Edited: `src/main.py` — remove K_1–K_4 speed shortcuts; P/Space now toggle pause/resume; F12 added as editor mode shortcut; digit input block moved before pause key and conditioned on unit selected or input active
- Validated: 9/9 tests pass

### Session 19 (Stage 18 — Fix Frequency Oscillation + AGC)
- Edited: `src/simulation/frequency.py` — removed phantom droop correction from `update()`; removed `DROOP_R` import; swing equation is now honest: `df/dt = (f0 / 2H) × P_net_pu`
- Edited: `src/simulation/constants.py` — added AGC section: `AGC_ENABLED` (default False), `AGC_KI = 0.3`, `AGC_MAX_RATE_MW_S = 20.0`, `AGC_DEADBAND_HZ = 0.02`
- Edited: `src/simulation/units.py` — added `_AGC_UNIT_TYPES` frozenset (HYDRO, HYDRO_ROR, CCGT); added `FleetModel.apply_agc_signal(delta_mw)` distributing correction proportional to headroom/regulating range
- Edited: `src/simulation/simulation.py` — added `_agc_integral` to `__init__`; added `_apply_agc()` method (integral-only PI loop, rate-limited, deadband); added step 5b call after frequency update when `AGC_ENABLED`
- Edited: `src/main.py` — added `Ctrl+A` handler to toggle `_const.AGC_ENABLED`; added `and not ctrl` guard to plain `A` ack handler; updated module docstring
- Edited: `tests/test_simulation.py` — updated `test_frequency_model` droop check to verify constant `df/dt` under constant imbalance (correct behaviour for honest swing equation)
- Validated: 9/9 tests pass

### Session 18 (Stage 17 — Stable Starting State for Gameplay Testing)
- Edited: `src/main.py` — added `_SHIFT_SCHEDULES` dict with Shift 1 handover (HART×2 at 680 MW, RVSD-1/3 at 200 MW, DUNH×2 at 100 MW, DUND×2 at 40 MW, BR01×2 at 30 MW); `_make_sim_and_renderer()` passes `initial_schedule`
- Edited: `src/simulation/simulation.py` — added `_seen_v_warn`, `_seen_v_crit`, `_freq_alarm_state` state to `__init__`; refactored `_update_voltage_alarms()` to edge-trigger (fires only on 0→1 transition, clears on recovery); refactored `_update_frequency_alarms()` to edge-trigger via `_freq_alarm_state`
- Validated: 9/9 tests pass

### Session 17 (Stage 16 — Line Context Panel + Line Hit Detection)
- Edited: `src/display/context.py` — added `draw_line_context()`: read-only panel showing route (from→to), voltage kV, rating MW, flow MW with direction arrow (▶/◀), loading % with colour coding, status (IN SERVICE/TRIPPED); added `COL_LOAD_WARN/HIGH/CRIT/LINE_TRIPPED` imports
- Edited: `src/display/renderer.py` — added `_point_segment_dist()` module helper; added `_LINE_HIT_PX = 6` constant; extended `on_click()` with line segment proximity test (only fires when no bus/unit hit); extended `_selectable_labels()` to append line labels after buses; added `draw_line_context` import; added third `elif` branch in `tick()` for line context overlay
- Validated: 9/9 tests pass

### Session 16 (Stage 15 — ACK Alarm Shortcut + Tab/Escape Navigation)
- Edited: `src/display/context.py` — added `draw_bus_context()`: read-only panel showing bus label, voltage level (kV), live V (pu); reuses all existing `CONTEXT_OVERLAY_*` constants
- Edited: `src/display/renderer.py` — `on_ack_alarm()`, `on_ack_all_alarms()`, `_selectable_labels()`, `on_tab()`; bus context overlay `elif` branch in `tick()`; updated import
- Edited: `src/main.py` — `A` → ack top alarm; `Shift+A` → ack all; `Tab` → cycle selection; updated docstring
- Validated: 9/9 tests pass

### Session 15 (Stage 14 — Unit Start/Stop Commands)
- Edited: `src/display/context.py` — added `cmd_active` param; START/STOP button row (green/red border); `starting…`/`shutting down…` transition status; helper `_draw_cmd_row()`; panel height grows by one row when button shown
- Edited: `src/display/renderer.py` — `_cmd_active` flag; `on_start_unit()`, `on_stop_unit()` methods; updated `on_escape()` (clears cmd focus before deselecting); updated `clear_selection()` and `tick()` context overlay call
- Edited: `src/main.py` — `S` key → `on_start_unit(sim)`; `X` key → `on_stop_unit(sim)`; updated docstring
- Validated: 9/9 tests pass

### Session 14 (Stage 13 — Unit Output Control)
- Written: `src/display/context.py` — draw_unit_context(): fixed top-left panel with header (label/type/state), output row, target input field with cursor and range hint, non-dispatchable fallback
- Edited: `src/simulation/constants.py` — CONTEXT_OVERLAY_X/Y/W/PAD/ROW_H/HDR_H, FONT_SIZE_CONTEXT
- Edited: `src/display/palette.py` — COL_CONTEXT_FIELD_BG, COL_CONTEXT_FIELD_ACTIVE, COL_CONTEXT_CURSOR
- Edited: `src/display/renderer.py` — _input_buffer/_input_active state; _get_selected_unit(); on_key_digit(), on_backspace(), on_enter(), on_escape(); context overlay in tick(); updated clear_selection() and on_click()
- Edited: `src/main.py` — Escape → on_escape(); speed keys guarded by not _input_active; digit/backspace/enter routed to renderer
- Validated: 9/9 tests pass

### Session 13 (Stage 12 — Canvas Selection)
- Edited: `src/display/renderer.py` — added `_HIT_RADIUS = 10`, `self._selected_label`, `clear_selection()`; replaced on_click() stub with full Chebyshev hit detection (units first, then buses); removed `selected_label` parameter from `tick()` — selection now owned internally
- Edited: `src/main.py` — Escape key checks `renderer._selected_label is not None` before quitting; calls `clear_selection()` to deselect
- Validated: 9/9 tests pass

### Session 12 (Stage 11 — Simulation to Display Connection)
- Written: `src/display/animation.py` — FlowAnimator: directional flow markers on all active lines (speed ∝ loading, direction from flow sign, colour by voltage level)
- Edited: `src/display/panels.py` — all four functions accept live state; static fallbacks preserved for state=None
- Edited: `src/display/renderer.py` — set_grid(), on_scroll(); tick() accepts speed_mult; FlowAnimator driven after canvas draw
- Edited: `src/main.py` — GridSimulation instantiated per session; speed keys 0-4; shift-switch F1/F3/F5; mouse wheel scroll
- Fixed: `src/display/canvas.py` — state.blackout_buses → state.blackout_zones
- Validated: simulation runs live; all panels update each frame; 9/9 tests pass

### Session 11 (Stage 10 — Instrument Strip Panels)
- Written: `src/display/panels.py` — four draw functions: frequency (large Hz readout, analog bar, trend), power balance (6-row MW summary), unit dispatch (scrollable list with state colours, output bars), alarm feed (scrollable list, 2Hz blink on unacked)
- Edited: `src/display/renderer.py` — replace plain strip fill with four panel subsurfaces; add 2Hz blink timer and dispatch/alarm scroll offsets
- Edited: `src/simulation/constants.py` — add FONT_SIZE_PANEL, FONT_SIZE_PANEL_LARGE, PANEL_FREQ_X/W, PANEL_POWER_X/W, PANEL_DISPATCH_X/W, PANEL_ALARM_X/W
- Stage 10 uses static test constants (marked # TEST DATA); Stage 11 swaps to live SimulationState fields
- Validated: window opens, strip draws all four panels; 9/9 tests still pass

### Session 10 (Stage 9 — Static Grid Renderer)
- Written: `src/display/symbols.py` — all procedural drawing functions (substation, unit squares, collector lines, transmission lines, hydraulic connectors, interconnector markers)
- Written: `src/display/canvas.py` — GridCanvas: draws all buses, lines, and unit squares by shift onto the 1920×844 canvas surface
- Written: `src/display/renderer.py` — Renderer: native 1920×1080 surface, layer compositing, blink phase, debug overlay, scales to display
- Written: `src/main.py` — pygame init, window, main loop; keys 1/3/5 switch shift, D toggles debug overlay
- Fixed: `src/utils/helpers.py` — `resource_path()` base was `src/utils/` instead of `src/`; corrected to `Path(__file__).parent.parent`
- Added: font fallback in Renderer — uses `pygame.freetype.SysFont('monospace', 11)` when JetBrainsMono is not yet installed
- Validated: window opens clean; 9/9 tests still pass
- Note: Stage 7 (events.py scripted event system) remains deferred until after rendering is complete

### Session 9 (Stage 8 — Master Simulation Loop)
- Written: `src/simulation/simulation.py` — Alarm, SimulationState, ForecastResult dataclasses + GridSimulation
- Fixed: `FleetModel.get_state_snapshot()` returns per-unit dicts; `_build_state()` now transposes to per-field dicts
- Fixed: `DCLoadFlow.rebuild()` and `VoltageModel.rebuild()` updated to accept optional `lines_in_service` list; `_build_b_matrix/_build_b_prime` now read from `_active_lines` instead of calling `grid.get_active_lines()` directly
- Added: `test_simulation_model()` — 6 sub-checks, all PASS
- Validation: 9/9 tests passed
- Note: Stage 7 (events.py scripted event system) deferred until after rendering is complete

### Session 8 (Stage 6 — Cascade Detection and Island Finding)
- Written: `src/simulation/cascade.py` — CascadeModel (BFS island finding, overload timers, blackout zones)
- Added: `test_cascade_model()` — 4 sub-checks, all PASS
- Validation: 8/8 tests passed
- Note: discovered topology has intentionally isolated buses (cascade stations, BARD, KELD, WNCN are radial generation buses with no looped transmission connections; load substations have no 60kV lines modelled)

### Session 1 (Setup)
- Created directory structure (`src/` tree, all packages, all placeholder files)
- Configured `.gitignore`, `.gitattributes`, `.claudeignore`
- Created `requirements.txt` (pygame-ce, numpy)
- Created placeholder `CLAUDE.md`, `CODING_STANDARDS.md`, `DOMAIN_GLOSSARY.md`, `SIMULATION_API.md`
- Created this `STAGE_STATUS.md`
- Made first git commit

### Session 2 (Configuration Documents)
- Written: `CLAUDE.md` (complete)
- Written: `CODING_STANDARDS.md` (complete)
- Written: `DOMAIN_GLOSSARY.md` (complete)
- Written: `SIMULATION_API.md` (complete)
- Status: All Stage 0 configuration complete

### Session 7 (Stage 5 — Demand, Renewables, and Losses)
- Written: `src/simulation/demand.py` — DemandModel (profile + noise + load shed + losses)
- Written: `src/simulation/renewables.py` — RenewablesModel (wind/solar with noise, deterministic mode)
- Added: `test_demand_model()` — 5 sub-checks, all PASS
- Added: `test_renewables_model()` — 4 sub-checks, all PASS
- Validation: 7/7 tests passed

### Session 6 (Stage 4 — Generation Unit State Machine)
- Written: `src/simulation/units.py` — UnitModel + FleetModel
- Added: `test_unit_model()` — 9 sub-checks, all PASS
- Validation: 5/5 tests passed

### Session 5 (Stage 3 — Frequency and Voltage Models)
- Written: `src/simulation/frequency.py` — FrequencyModel (swing equation + droop)
- Written: `src/simulation/voltage.py` — VoltageModel (decoupled ΔV = B'⁻¹ × Q)
- Added: `VSHUNT_REG = 0.1` to `constants.py` for voltage B' matrix stability (isolated load buses)
- Added: `test_frequency_model()` — 4 sub-checks, all PASS
- Added: `test_voltage_model()` — 3 sub-checks, all PASS
- Validation: 4/4 tests passed

### Session 4 (Stage 2 — DC Load Flow Solver)
- Written: `src/simulation/loadflow.py` — DCLoadFlow class + LoadFlowResult
- Fixed: L10, L11, L29 active_from_shift mismatches (bus/line activation consistency)
- Added: `test_loadflow_solves()` — 5 sub-checks, all PASS
- Validation: 2/2 tests passed

### Session 3 (Stage 1 — Network Data Model)
- Written: `src/utils/helpers.py` — resource_path() for dev + PyInstaller builds
- Written: `src/simulation/constants.py` — all numeric constants, thresholds, timings
- Written: `src/display/palette.py` — all RGB colour constants
- Written: `src/data/topology.py` — Bus + Line dataclasses, 40 buses, 29 lines
- Written: `src/data/fleet.py` — GenerationUnit dataclass, 47 units across all stations
- Written: `src/data/profiles.py` — demand/wind/solar profiles, ShiftSpec for all 10 shifts
- Written: `src/simulation/grid.py` — Grid class with full public interface
- Written: `tests/test_simulation.py` — test_grid_loads() with 8 sub-checks
- Fixed: corrupted UTF-16 __init__.py placeholders → empty UTF-8
- Validation: 1/1 tests passed

---

## What Is Built and Validated

```
CONFIGURATION
  ✓ Directory structure created (all directories and placeholder files)
  ✓ .gitignore configured (Windows Python + PyInstaller)
  ✓ .gitattributes configured (LF line endings)
  ✓ .claudeignore configured
  ✓ requirements.txt (pygame-ce>=2.4.0, numpy>=1.24.0)
  ✓ CLAUDE.md written
  ✓ CODING_STANDARDS.md written
  ✓ DOMAIN_GLOSSARY.md written
  ✓ SIMULATION_API.md written

STAGE 1 — NETWORK DATA MODEL (complete, validated)
  ✓ src/utils/helpers.py       — resource_path()
  ✓ src/simulation/constants.py — all constants (debug, physics, display, timing)
  ✓ src/display/palette.py     — all colour constants
  ✓ src/data/topology.py       — Bus + Line dataclasses (Line.parallel added Stage 23), 36 buses, 50 lines
  ✓ src/data/fleet.py          — GenerationUnit dataclass, 47 units
  ✓ src/data/profiles.py       — demand/wind/solar profiles, 10 ShiftSpecs
  ✓ src/simulation/grid.py     — Grid class (full public interface per API contract)
  ✓ tests/test_simulation.py   — test_grid_loads() — PASS

  Grid sizes by shift (redesigned Stage 23 — Portuguese-grid-inspired structure;
  Stage 24 added a Shift-10-only capacity expansion, see below):
    Shift 1:  3 buses,  2 lines,  2 active units (tutorial)
    Shift 2:  4 buses,  3 lines,  5 units
    Shift 3: 10 buses, 11 lines, 13 units (N-1 lesson, capital ring)
    Shift 4: 16 buses, 21 lines, 20 units (south 150kV mesh)
    Shift 5: 23 buses, 30 lines, 30 units (west hydro pocket)
    Shift 6: 27 buses, 34 lines, 39 units (north spine, INTC-N)
    Shift 7: 36 buses, 47 lines, 47 units (full grid — east pocket, INTC-S)
    Shift 8-9: 36 buses, 50 lines, 47 units (second circuits + southern sag)
    Shift 10: 44 buses, 70 lines, 47 units (Stage 24: +23 load substations,
              +2 ring parallel circuits, full 8,000 MW peak deliverable;
              Stage 25: +23 secondary feed lines (dual-feed N-1 security)
              +2 River Brent/Coln loop closures; Stage 26: consolidated
              23 load substations -> 9 (LD07-LD15); Stage 27: further
              consolidated 9 -> 8 (LD07-LD14) and re-spaced the west hydro
              pocket bus layout for less on-screen clutter)

STAGE 2 — DC LOAD FLOW SOLVER (complete, validated)
  ✓ src/simulation/loadflow.py — DCLoadFlow class + LoadFlowResult
  ✓ tests/test_simulation.py   — test_loadflow_solves() — PASS

STAGE 3 — FREQUENCY AND VOLTAGE MODELS (complete, validated)
  ✓ src/simulation/frequency.py — FrequencyModel (swing equation + droop)
  ✓ src/simulation/voltage.py   — VoltageModel (decoupled ΔV = B'⁻¹ × Q)
  ✓ src/simulation/constants.py — VSHUNT_REG added
  ✓ tests/test_simulation.py    — test_frequency_model(), test_voltage_model() — PASS

STAGE 4 — GENERATION UNIT STATE MACHINE (complete, validated)
  ✓ src/simulation/units.py — UnitModel (OFFLINE/STARTING/ONLINE/SHUTDOWN)
                             — FleetModel (aggregate queries, command routing)
  ✓ tests/test_simulation.py — test_unit_model() — PASS

STAGE 5 — DEMAND, RENEWABLES, AND LOSSES (complete, validated)
  ✓ src/simulation/demand.py     — DemandModel (profile + noise + load shed + losses)
  ✓ src/simulation/renewables.py — RenewablesModel (wind/solar + noise, deterministic mode)
  ✓ tests/test_simulation.py     — test_demand_model(), test_renewables_model() — PASS

STAGE 6 — CASCADE DETECTION AND ISLAND FINDING (complete, validated)
  ✓ src/simulation/cascade.py    — CascadeModel (BFS island finding, overload timers, blackout zones)
  ✓ tests/test_simulation.py     — test_cascade_model() — PASS

STAGE 8 — MASTER SIMULATION LOOP (complete, validated)
  ✓ src/simulation/simulation.py — Alarm, SimulationState, ForecastResult, GridSimulation
  ✓ src/simulation/loadflow.py   — rebuild() updated to accept optional lines_in_service list
  ✓ src/simulation/voltage.py    — rebuild() updated to accept optional lines_in_service list
  ✓ tests/test_simulation.py     — test_simulation_model() — PASS

STAGE 9 — STATIC GRID RENDERER (complete, validated)
  ✓ src/display/symbols.py  — draw_substation, draw_load_substation, draw_unit_square,
                               draw_station_collector, draw_transmission_line,
                               draw_hydraulic_connector, draw_interconnector
  ✓ src/display/canvas.py   — GridCanvas: layer-ordered schematic render, shift-aware
  ✓ src/display/renderer.py — Renderer: native 1920×1080, blink, debug overlay, display scaling
  ✓ src/main.py             — pygame init, main loop, 1/3/5 shift keys, D debug toggle
  ✓ src/utils/helpers.py    — resource_path() base path corrected to src/

STAGE 10 — INSTRUMENT STRIP PANELS (complete, validated)
  ✓ src/display/panels.py       — draw_frequency_panel, draw_power_panel,
                                   draw_dispatch_panel, draw_alarm_panel
  ✓ src/display/renderer.py     — four panel subsurfaces; 2Hz alarm blink; scroll offsets
  ✓ src/simulation/constants.py — FONT_SIZE_PANEL, FONT_SIZE_PANEL_LARGE, PANEL_* layout constants

STAGE 11 — SIMULATION TO DISPLAY CONNECTION (complete, validated)
  ✓ src/display/animation.py  — FlowAnimator: directional flow markers on active lines
  ✓ src/display/panels.py     — live state wired; static fallback preserved for state=None
  ✓ src/display/renderer.py   — set_grid(), on_scroll(), speed_mult; FlowAnimator integrated
  ✓ src/display/canvas.py     — fix blackout_buses → blackout_zones
  ✓ src/main.py               — GridSimulation per session; speed keys 0-4; F1/F3/F5 shift

STAGE 12 — CANVAS SELECTION (complete, validated)
  ✓ src/display/renderer.py   — hit detection in on_click() (Chebyshev, units before buses);
                                 _selected_label state; clear_selection(); tick() uses internal state
  ✓ src/main.py               — Escape clears selection before quitting

STAGE 13 — UNIT OUTPUT CONTROL (complete, validated)
  ✓ src/display/context.py    — draw_unit_context(): panel with output, target field, range hint
  ✓ src/simulation/constants.py — CONTEXT_OVERLAY_* layout constants; FONT_SIZE_CONTEXT
  ✓ src/display/palette.py    — COL_CONTEXT_FIELD_BG, COL_CONTEXT_FIELD_ACTIVE, COL_CONTEXT_CURSOR
  ✓ src/display/renderer.py   — input state; on_key_digit/on_backspace/on_enter/on_escape;
                                 _get_selected_unit(); context overlay in tick()
  ✓ src/main.py               — digit/backspace/enter routed; speed keys guarded by _input_active

STAGE 14 — UNIT START/STOP COMMANDS (complete, validated)
  ✓ src/display/context.py    — START/STOP button row; transition status; cmd_active highlight;
                                 _draw_cmd_row() helper; panel height dynamic
  ✓ src/display/renderer.py   — _cmd_active flag; on_start_unit(); on_stop_unit();
                                 on_escape() clears cmd focus; clear_selection() clears cmd
  ✓ src/main.py               — S=start unit; X=stop unit; both guarded by EDITOR_MODE/_input_active

STAGE 15 — ACK ALARM SHORTCUT + TAB/ESCAPE NAVIGATION (complete, validated)
  ✓ src/display/context.py    — draw_bus_context(): read-only panel; bus label, voltage kV, live V pu
  ✓ src/display/renderer.py   — on_ack_alarm(); on_ack_all_alarms(); _selectable_labels(); on_tab();
                                 bus context overlay elif branch in tick()
  ✓ src/main.py               — A=ack top alarm; Shift+A=ack all; Tab=cycle selection

STAGE 16 — LINE CONTEXT PANEL + LINE HIT DETECTION (complete, validated)
  ✓ src/display/context.py    — draw_line_context(): read-only panel; route, voltage kV, rating MW,
                                 flow MW with direction arrow, loading % colour-coded, status
  ✓ src/display/renderer.py   — _point_segment_dist() helper; _LINE_HIT_PX constant;
                                 on_click() line segment proximity test; _selectable_labels()
                                 includes lines; tick() third elif branch for line context overlay

STAGE 17 — STABLE STARTING STATE FOR GAMEPLAY TESTING (complete, validated)
  ✓ src/main.py               — _SHIFT_SCHEDULES dict; Shift 1 handover schedule passed to GridSimulation
  ✓ src/simulation/simulation.py — _seen_v_warn/_seen_v_crit/_freq_alarm_state state;
                                   _update_voltage_alarms() edge-triggered; _update_frequency_alarms()
                                   edge-triggered via state machine

STAGE 22 — LOAD-STATE LINE COLOURING (complete, validated)
  ✓ src/display/palette.py    — COL_LINE_ENERGISED (40,160,80) added
  ✓ src/display/symbols.py    — draw_transmission_line(): colour = load state only;
                                 thickness = voltage tier only; voltage colour lookup removed

STAGE 21 — LINE TRIP/CLOSE COMMANDS (complete, validated)
  ✓ src/display/context.py    — draw_line_context() gains cmd_active param; TRIP/CLOSE button row;
                                 panel height grows by one row when button shown
  ✓ src/display/renderer.py   — _line_cmd_active flag; _get_selected_line(); on_trip_line();
                                 on_close_line(); clear_selection() and on_escape() updated
  ✓ src/main.py               — T=trip line; C=close line; updated docstring

STAGE 20 — GENERATION MIX PANEL + FORECAST LOAD OVERLAY (complete, validated)
  ✓ src/simulation/constants.py  — PANEL_GENMIX_X/W; FORECAST_OVERLAY_W/H/PAD; resized existing panels
  ✓ src/simulation/simulation.py — gen_mix_mw field in SimulationState; populated in _build_state()
  ✓ src/display/palette.py       — COL_FORECAST_DEMAND, COL_FORECAST_NETLOAD
  ✓ src/display/panels.py        — draw_genmix_panel(): fuel-type rows, MW + % + mini bars
  ✓ src/display/renderer.py      — GEN MIX subsurface in strip; _draw_forecast_overlay() on canvas

STAGE 19 — AGC DEBUG INDICATOR + INPUT FIX + DEMAND NOISE SMOOTHING (complete, validated)
  ✓ src/simulation/constants.py  — DEMAND_NOISE_UPDATE_S = 60.0 simulated seconds
  ✓ src/simulation/demand.py     — noise held constant between re-samples (every 60 sim-s)
  ✓ src/simulation/simulation.py — dt_sim_seconds passed to demand.update()
  ✓ src/display/renderer.py      — AGC ON/OFF in debug overlay (top-right, second line)
  ✓ src/main.py                  — K_1–K_4 removed; P/Space = pause toggle; F12 = editor mode;
                                   digit input moves before pause key, fires only when unit selected

STAGE 18 — FIX FREQUENCY OSCILLATION + AGC (complete, validated)
  ✓ src/simulation/frequency.py  — phantom droop removed; honest swing equation: df/dt = (f0/2H)×P_net_pu
  ✓ src/simulation/constants.py  — AGC_ENABLED (default False), AGC_KI, AGC_MAX_RATE_MW_S, AGC_DEADBAND_HZ
  ✓ src/simulation/units.py      — _AGC_UNIT_TYPES frozenset; FleetModel.apply_agc_signal()
  ✓ src/simulation/simulation.py — _agc_integral state; _apply_agc() method; step 5b in tick()
  ✓ src/main.py                  — Ctrl+A toggles AGC_ENABLED; plain A guarded with `and not ctrl`
  ✓ tests/test_simulation.py     — droop test updated: verifies constant df/dt (no phantom term)

SOURCE FILES (empty placeholders — no working code)
  src/simulation/events.py  (deferred — after rendering stage)
  src/display/context.py
  src/display/debug.py
  src/gameplay/campaign.py
  src/gameplay/phase1.py
  src/gameplay/phase2.py
  src/gameplay/debrief.py
  src/gameplay/scoring.py
  src/gameplay/autopilot.py
  src/gameplay/shifts/shift_01.py through shift_10.py
```

---

## What Is In Progress

Nothing. Stage 23 topology/fleet/profiles/display work is complete and validated. Stage 24
(Shift 10 capacity expansion + finale rewrite) is complete and validated this session. Shifts
4-9 scenario content is the remaining open follow-up (see Next Session Objective), plus the
Shift 3 N-1 lesson regression flagged in Known Issues.

---

## What Is NOT Yet Built

**Gameplay stages have empty placeholder files only** (except shift_01-03 and shift_10, which
are complete and tuned for the current topology; shift_04-09 exist as placeholder files but
their content is STALE against the redesigned grid — see Known Issues).
**Stage 7 (events.py) is deliberately deferred until after rendering is complete.**

Do not reference any display or gameplay module as if it
contains working code unless listed above as complete.

Specifically — these classes and functions DO NOT EXIST YET:
- `EventSystem` / `ScriptedEvent` (src/simulation/events.py) — deferred
- Any gameplay classes (src/gameplay/*)

---

## Next Session Objective

**Rewrite Shift 4-9 scenario files for the redesigned grid**

Shifts 1-3 and 10 are complete on the current topology. shift_04.py through shift_09.py exist
but were written for the old grid and are now stale (see Known Issues) — they need full
rewrites:
- New `SUBSTATION_LOAD_MW` tables matching each shift's actual active load buses
  (check `get_buses_by_shift(n)` for what's really on) and the new `peak_demand_mw` targets
  in `data/profiles.py`.
- New `INITIAL_SCHEDULE` / `MAINTENANCE_UNITS` reflecting the re-sited fleet (e.g. HART is now
  at STHW not CNTR, BARR is at NRTH not EAST).
- `MAINTENANCE_LINES` per the tutorial-feeder retirement plan: L49 (DUND↔LD01) should open at
  Shift 4 once the south 150kV mesh takes over LD01.
- New scripted events / scoring hooks per shift (wind variability at Shift 6, solar + second
  interconnector at Shift 7, parallel-path flow lesson at Shift 8, mastery scenario at 9).
- Also re-check each shift's line-loading assumptions against the Session-31 flat
  `LINE_RATING_MW_BY_VOLTAGE` ratings (400/220/150 kV = 2250/400/175 MW), which replaced the
  old per-line/per-role ratings these shifts may have been informally tuned around.

**Also required**: fix the pre-existing `shift_03.py` condition-helper bug (`_ashg1_below_250mw`
and `_l15_high_load` call a `fleet.get_output_mw(...)` method that does not exist, and
`_l15_high_load` expects a `grid` argument the engine never passes — see Known Issues), then
re-verify/re-tune Shift 3's N-1 lesson thresholds against the new L09/L15/L16 ratings.

---

## Open Decisions

None at this stage. All architectural decisions are locked in the reference documents.

---

## Known Issues

**Shift 3's N-1 lesson is at risk of regression from the Session 31 line-rating normalization**
(see Session 31 log above for full detail). L15/L16 dropped from 800→400 MW and L09 rose from
1200→2250 MW; the tutorial's 80/85/90% loading thresholds are unchanged but the MW flow needed
to reach them has shifted substantially. **Blocked on a separate pre-existing bug**: `shift_03.py`'s
own condition helpers (`_ashg1_below_250mw`, `_l15_high_load`) call a `FleetModel.get_output_mw()`
method that does not exist (the real API is `fleet.get_unit(label).current_mw`), and
`_l15_high_load` is written to take a `grid` argument, but `GridSimulation._process_scripted_events()`
only ever calls `cond(self._fleet)`. This crashes Shift 3 with an `AttributeError` once sim time
reaches minute 90 (T+90 in the shift's own event schedule) — confirmed via direct reproduction,
not introduced this session. Shift 3 has likely been unplayable past that point since it was
written. Fix the helper API mismatch first, then re-verify the N-1 lesson still teaches
convincingly at the new ratings.

**Shift 4-9 scenario files are stale against the Stage 23 topology redesign.**
`shift_04.py` through `shift_09.py` were written for the old 40-bus grid (full size at Shift 5).
Example: `shift_04.py`'s `SUBSTATION_LOAD_MW` includes `LD06`, which in the new grid is not
active until Shift 7; `shift_05.py`/`shift_06.py` reference all six load substations (LD01-06)
even though the new grid only activates them progressively through Shift 7. Per-bus peak MW
values were tuned to the old `peak_demand_mw` figures and no longer match the new targets in
`data/profiles.py`. These shifts will produce an unbalanced/overloaded grid until rewritten.
Shifts 1-3 and 10 do not have this problem — they were rewritten across Sessions 26-31.

---

## Validation History

| Stage | Test | Result | Date |
|-------|------|--------|------|
| 0 | Structure created, git committed | PASS | TBD |
| 1 | test_grid_loads() — 1/1 | PASS | 2026-05-07 |
| 2 | test_loadflow_solves() — 2/2 | PASS | 2026-05-07 |
| 3 | test_frequency_model() + test_voltage_model() — 4/4 | PASS | 2026-05-07 |
| 4 | test_unit_model() — 5/5 | PASS | 2026-05-07 |
| 5 | test_demand_model() + test_renewables_model() — 7/7 | PASS | 2026-05-07 |
| 6 | test_cascade_model() — 8/8 | PASS | 2026-05-08 |
| 8 | test_simulation_model() — 9/9 | PASS | 2026-05-08 |
| 9 | Window opens, 9/9 tests still pass | PASS | 2026-05-08 |
| 10 | Strip draws 4 panels, 9/9 tests still pass | PASS | 2026-05-09 |
| 11 | Live sim running, panels update, flow markers animate, 9/9 pass | PASS | 2026-05-09 |
| 12 | Click selects bus/unit, Escape deselects, 9/9 tests pass | PASS | 2026-05-09 |
| 13 | Unit context overlay, MW target input, Enter dispatches, 9/9 pass | PASS | 2026-05-09 |
| 14 | START/STOP buttons in context panel, S/X shortcuts, 9/9 pass | PASS | 2026-05-10 |
| 15 | A/Shift+A ACK alarms, Tab cycles selection, bus context panel, 9/9 pass | PASS | 2026-05-27 |
| 16 | Line click/Tab selection, line context panel (flow/loading/status), 9/9 pass | PASS | 2026-05-27 |
| 17 | Shift 1 handover schedule; voltage/frequency alarm deduplication; 9/9 pass | PASS | 2026-05-27 |
| 18 | Phantom droop removed; AGC integrator + Ctrl+A toggle; 9/9 pass | PASS | 2026-05-27 |
| 19 | AGC debug indicator; digit input fix; demand noise smoothed; P=pause toggle; 9/9 pass | PASS | 2026-05-27 |
| 20 | GEN MIX strip panel; FORECAST LOAD canvas overlay; 9/9 pass | PASS | 2026-05-28 |
| 21 | Line trip (T) and close (C) commands; TRIP/CLOSE button in context panel; 9/9 pass | PASS | 2026-05-29 |
| 23 | Full grid/fleet redesign (36 buses, 50 lines, 47 units); Shifts 1-3 re-tuned; N-1 spot checks + offscreen render check; 9/9 pass | PASS | 2026-07-03 |
| 24 | Shift 10 capacity expansion (59 buses, 75 lines) + finale rewrite; flat per-voltage-tier line ratings; offscreen load-flow + gradual-tick + render checks; 9/9 pass | PASS | 2026-07-07 |
| — | 8-point substation connection ports (Session 32); offscreen render Shifts 1/3/7/10; ASHF degree-7 fan-out + hit-test + designer-topology screenshot checks; 9/9 pass | PASS | 2026-07-08 |
| 25 | Shift 10 dual-feed N-1 fix (59 buses, 100 lines) + Brent/Coln loop closures + generator connector ratings + renewables noise smoothing + substation place names; offscreen peak-hour load-flow (93.4% max loading) + 3 N-1 trip checks (LD07/Brent/Coln all stay energized) + renewables smoothing check; 9/9 pass | PASS | 2026-07-11 |
| 26 | Shift 10 load substation consolidation, 23 -> 9 substations (45 buses, 72 lines); found and fixed an N-1 coupling bug (re-sourced LD14/LD15 off shared source buses); hub-bus degree recomputed (ASHF 9->6, DUNM 8->6); offscreen peak-hour load-flow + full N-1 sweep across all 9 substations, no blackouts or cross-substation cascades; 9/9 pass | PASS | 2026-07-11 |
| 27 | Shift 10 further consolidation 9 -> 8 substations (44 buses, 70 lines) + west hydro pocket re-layout; found and reverted an N-1 ring-overload from over-merging LD07/LD14; deterministic (non-tick) N-1 sweep across all 8 substations + west-pocket collision check, no blackouts, all spacing >=92px; 9/9 pass | PASS | 2026-07-11 |

---

## How To Update This File

At the end of every Claude Code session:

1. Move completed items from "In Progress" to "Built and Validated"
2. Update "What Is NOT Yet Built" — remove things that now exist
3. Set the new "Next Session Objective"
4. Add a row to Validation History
5. Note any Open Decisions or Known Issues
6. Commit: `git commit -m "Stage X: [description] — update STAGE_STATUS.md"`

This file is the memory between sessions. Keep it accurate.
