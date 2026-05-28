# STAGE_STATUS.md — GRIDCOM Development State
### Updated at the end of every Claude Code session.
### Read at the start of every Claude Code session.

---

## Current Stage

**STAGE 20 — Generation Mix Panel + Forecast Load Overlay**

## Current Status

**COMPLETE** — GEN MIX panel added to strip (between DISPATCH and ALARMS); FORECAST LOAD chart drawn as fixed canvas overlay top-right; 9/9 tests pass.

## Session Log

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
  ✓ src/data/topology.py       — Bus + Line dataclasses, 40 buses, 45 lines
  ✓ src/data/fleet.py          — GenerationUnit dataclass, 47 units
  ✓ src/data/profiles.py       — demand/wind/solar profiles, 10 ShiftSpecs
  ✓ src/simulation/grid.py     — Grid class (full public interface per API contract)
  ✓ tests/test_simulation.py   — test_grid_loads() — PASS

  Grid sizes by shift:
    Shift 1:  9 buses,  8 lines, 11 units
    Shift 3: 28 buses, 29 lines, 29 units
    Shift 5: 40 buses, 45 lines, 47 units

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

Nothing. Stage 20 complete.

---

## What Is NOT Yet Built

**Gameplay stages have empty placeholder files only.**
**Stage 7 (events.py) is deliberately deferred until after rendering is complete.**

Do not reference any display or gameplay module as if it
contains working code unless listed above as complete.

Specifically — these classes and functions DO NOT EXIST YET:
- `EventSystem` / `ScriptedEvent` (src/simulation/events.py) — deferred
- Any gameplay classes (src/gameplay/*)

---

## Next Session Objective

**Stage 21 — TBD**

Grid now shows generation mix and forecast load at all times.
Suggested candidates for Stage 21:
- Line trip/close commands (operator-initiated outage management — T/C keys on selected line)
- Crisis auto-forcing (speed forced to slow when crisis condition triggers)
- Interconnector flow display and target control

---

## Open Decisions

None at this stage. All architectural decisions are locked in the reference documents.

---

## Known Issues

None.

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
