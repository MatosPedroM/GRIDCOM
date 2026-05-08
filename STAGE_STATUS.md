# STAGE_STATUS.md — GRIDCOM Development State
### Updated at the end of every Claude Code session.
### Read at the start of every Claude Code session.

---

## Current Stage

**STAGE 6 — Cascade Detection and Island Finding**

## Current Status

**COMPLETE** — CascadeModel written and validation tests passing.

## Session Log

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
  ✓ src/data/topology.py       — Bus + Line dataclasses, 40 buses, 29 lines
  ✓ src/data/fleet.py          — GenerationUnit dataclass, 47 units
  ✓ src/data/profiles.py       — demand/wind/solar profiles, 10 ShiftSpecs
  ✓ src/simulation/grid.py     — Grid class (full public interface per API contract)
  ✓ tests/test_simulation.py   — test_grid_loads() — PASS

  Grid sizes by shift:
    Shift 1: 15 buses, 8 lines, 9 units
    Shift 3: 26 buses, 14 lines, 23 units
    Shift 5: 40 buses, 29 lines, 47 units

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

SOURCE FILES (empty placeholders — no working code)
  src/main.py
  src/simulation/loadflow.py
  src/simulation/units.py
  src/simulation/demand.py
  src/simulation/renewables.py
  src/simulation/events.py
  src/simulation/simulation.py
  src/display/renderer.py
  src/display/canvas.py
  src/display/symbols.py
  src/display/animation.py
  src/display/panels.py
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

Nothing. Stage 6 complete. Ready to begin Stage 7.

---

## What Is NOT Yet Built

**Stages 7-14 have empty placeholder files only.**

Do not reference any simulation, display, or gameplay module as if it
contains working code unless listed above as complete.

Specifically — these classes and functions DO NOT EXIST YET:
- `GridSimulation` (src/simulation/simulation.py)
- `SimulationState` (src/simulation/simulation.py)
- `EventSystem` / `ScriptedEvent` (src/simulation/events.py)
- Any display classes (src/display/*)
- Any gameplay classes (src/gameplay/*)

---

## Next Session Objective

**Stage 7 — Scripted Event System**

Goal: Implement `EventSystem` and `ScriptedEvent` in `src/simulation/events.py`.
Loads scripted events for a shift, applies timing jitter at load time,
fires events at the correct sim time, and marks them as fired to prevent
re-triggering.

Files to write:
1. `src/simulation/events.py` — EventSystem + ScriptedEvent

Validation tests (add to tests/test_simulation.py):
```
test_event_system...
  Events fire at correct sim time — PASS
  Jitter is applied and bounded — PASS
  Events fire at most once — PASS
  Difficulty filter excludes events not for current difficulty — PASS
4/4 tests passed
```

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
