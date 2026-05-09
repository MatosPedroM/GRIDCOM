# STAGE_STATUS.md — GRIDCOM Development State
### Updated at the end of every Claude Code session.
### Read at the start of every Claude Code session.

---

## Current Stage

**STAGE 13 — Unit Output Control**

## Current Status

**COMPLETE** — Selected unit shows context overlay top-left; player types MW target, Enter dispatches; 9/9 tests pass.

## Session Log

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

Nothing. Stage 13 complete.

---

## What Is NOT Yet Built

**Gameplay stages have empty placeholder files only.**
**Stage 7 (events.py) is deliberately deferred until after rendering is complete.**

Do not reference any display or gameplay module as if it
contains working code unless listed above as complete.

Specifically — these classes and functions DO NOT EXIST YET:
- `EventSystem` / `ScriptedEvent` (src/simulation/events.py) — deferred
- Context panel (src/display/context.py)
- Any gameplay classes (src/gameplay/*)

---

## Next Session Objective

**Stage 14 — Unit Start/Stop Commands**

Goal: Player can start (online) and stop (shutdown) generation units from the context panel or keyboard shortcuts.

Files to write/extend:
1. `src/display/context.py`  — add START / STOP buttons to context panel for OFFLINE / ONLINE units
2. `src/display/renderer.py` — on_start_unit(), on_stop_unit() methods calling sim.start_unit/stop_unit
3. `src/main.py`             — keyboard shortcut routing (e.g. S = start, X = stop when unit selected)

Deferred:
- Tab/Arrow keyboard navigation
- Line selection and context panel
- ACK alarm shortcut (A)

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
