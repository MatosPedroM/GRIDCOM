# Shift Builder — Editing Shift 10

### How to open, edit, save, and test the Shift 10 campaign scenario using the Shift Builder dev tool.

---

## 1. Open the Shift Builder

From the main menu, select **SHIFT BUILDER** (below GRID DESIGNER / TEST GRID).
This enters `GameState.SHIFT_BUILDER`.

## 2. Open Shift 10 for editing

Press **Ctrl+Shift+O** ("open campaign shift"). This is different from plain
**Ctrl+O**, which browses authored JSON shifts in `assets/shifts/` — Ctrl+Shift+O
instead lists the real campaign shifts, `shift_01.py` through `shift_10.py`.

A browser overlay appears listing `SHIFT 1` ... `SHIFT 10`. Use **Up/Down** to
select `SHIFT 10`, then press **Enter**.

The header at the top of the screen will now read:

```
EDITING: CAMPAIGN SHIFT 10 (shift_10.py)    GRID: Alpha    0.0h + 0.0h
```

This confirms you're editing the live campaign file, not a JSON scratch shift,
and that Shift 10 is running on the `Alpha` grid (see `GRID_SOURCE` in
`shift_10.py`).

## 3. Understand what you can and can't edit

Shift 10 (and every campaign shift) is a hand-written Python file with prose
docstrings and narrative text that the tool deliberately does not touch. Only
a specific set of *mechanical* fields are editable and saveable:

| Tab | Field | Editable for campaign shifts? |
|---|---|---|
| META | Shift date, difficulty label | No — read-only, dimmed. Edit `shift_10.py` directly. |
| META | AGC enabled | **Yes** |
| META | Handover notes | No — read-only, dimmed. |
| GRID | Grid reference | No — shown read-only (`Alpha` for Shift 10). Edit the grid itself in the Grid Designer. |
| GRID | Maintenance units | **Yes** |
| SCHEDULE | Initial dispatch (MW per unit) | **Yes** |
| DEMAND | Per-bus hourly load (MW) | **Yes** |
| EVENTS | Scripted event timeline | **Yes** |

Anything marked "No" is shown so you have context, but the tool won't let you
edit it here and won't touch it on save — this protects the module docstring,
`HANDOVER_NOTES` prose, `SHIFT_DATE`, and `DIFFICULTY_LABEL` from being
overwritten or reformatted.

## 4. Navigate tabs

**Tab** / **Right Arrow** — next tab
**Left Arrow** — previous tab

Tabs, in order: `META`, `GRID`, `SCHEDULE`, `DEMAND`, `EVENTS`.

## 5. Editing each tab

### META tab
- **[5]** — toggle AGC on/off.
- Everything else on this tab is read-only for a campaign shift.

### GRID tab
- Shows `GRID: Alpha (read-only here — edit topology in the Grid Designer)`.
- Lists all of Alpha's units. **Up/Down** moves the cursor, **Space** toggles
  a unit onto/off planned maintenance (`MAINTENANCE_UNITS`). A unit on
  maintenance starts the shift OFFLINE and locked.
- Pressing **G** or **Ctrl+G** here is blocked with a status message — Shift
  10's topology comes from the Alpha grid file, not from a pick-list.

### SCHEDULE tab
- Lists every unit in Alpha's fleet with its technical minimum, rated
  maximum, and current starting dispatch.
- **Up/Down** — move the cursor between units.
- **Enter** — edit the selected unit's starting MW to an exact custom value
  (type a number, Enter to confirm, Escape to cancel).
- **M** — set the unit's starting MW straight to its technical minimum
  (`min_mw`, as configured for that unit's technology in the grid).
- **X** — set the unit's starting MW straight to its rated maximum
  (`rated_mw`).
- **Backspace** — clear the unit's entry entirely; a unit with no entry
  starts the shift OFFLINE.

### DEMAND tab
- Shows one load bus's 25-hour demand table at a time (hours 0-24).
- **Up/Down** — switch which load bus you're viewing/editing.
- **PageUp/PageDown** — move the hour cursor left/right across the table.
- **Enter** — edit the MW value for the selected bus + hour.

### EVENTS tab
- Lists Shift 10's scripted event timeline (currently 6 events: shift-start
  briefing, wind-lull warning, staged-reserve branches, evening-peak warning,
  peak-window info).
- **Up/Down** — select an event. **N** or **Insert** — add a new event.
  **Delete** — remove the selected event.
- With an event selected, its detail fields are editable via number keys:
  - **[1]** trigger time (minutes from shift start)
  - **[2]** priority — cycles INFO → WARNING → ALARM → CRITICAL → MAINTENANCE
  - **[3]** message (short alarm-bar text)
  - **[4]** detail (longer popup text)
  - **[5]** element (bus/line/unit label this event is associated with, or blank)
  - **[6]** condition — cycles through metric types (LINE_LOADING,
    UNIT_OUTPUT_MW, UNIT_OUTPUT_MW_SUM, UNIT_ONLINE, SPINNING_RESERVE_MW,
    FREQUENCY_HZ, TIME_MIN), or clears the condition entirely
  - **[7]** action — cycles NONE → LINE_OPEN → LINE_CLOSE → UNIT_TRIP

## 6. Save your changes

Press **Ctrl+S**. Because you're editing a campaign shift, this does **not**
open the JSON save-as dialog — it writes your changes directly back into
`src/gameplay/shifts/shift_10.py`.

Only the specific constants you actually touched this session are rewritten
(`INITIAL_SCHEDULE`, `MAINTENANCE_UNITS`, `MAINTENANCE_LINES`,
`SUBSTATION_LOAD_MW`, `AGC_ENABLED`, `SCRIPTED_EVENTS`) — everything else in
the file, including the module docstring and `HANDOVER_NOTES`, is left
byte-for-byte untouched. If you haven't changed anything, Ctrl+S shows
"Nothing to save — no fields edited" and does not write the file.

**Note on formatting**: the constant you edit gets reformatted (one dict/list
entry per line) and loses any inline comment it had (e.g. a per-unit
`# Hartwell Nuclear 1 — rated baseload` note). This is a known, accepted
tradeoff of the save mechanism — it guarantees correctness and leaves
everything else in the file untouched, at the cost of that one constant's
original hand-formatting.

## 7. Test it live

Press **Ctrl+T** to launch a live test session. For a campaign shift, this
runs the *real* campaign bootstrap path — the same code that runs when a
player actually plays Shift 10 in the campaign, including loading the Alpha
grid via `GRID_SOURCE`. This is different from testing a JSON-authored shift,
which uses a generic preview path.

Inside the test session you get the normal Phase 2 controls: **P/Space**
pause, **1-4** speed, **S/X** start/stop a selected unit, **T/C** trip/close a
line, **A** acknowledge alarm, **Tab** cycle selection, etc.

Press **Escape** to return to the Shift Builder.

## 8. Exit

Press **Escape** from the Shift Builder's normal mode to return to the main
menu.

---

## Quick reference — keys specific to campaign-shift editing

| Key | Action |
|---|---|
| Ctrl+Shift+O | Open a campaign shift (shift_01.py .. shift_10.py) |
| Ctrl+O | Open a JSON-authored shift instead (unrelated to campaign shifts) |
| Ctrl+G | Blocked for campaign shifts — grid isn't editable here |
| Ctrl+S | Save — splices edited fields back into shift_NN.py |
| Ctrl+T | Test — runs the real campaign bootstrap for this shift |
| Tab / ←→ | Switch tabs |
| Esc | Exit Shift Builder (from normal mode) |
| M (SCHEDULE tab) | Set selected unit's starting MW to its technical minimum |
| X (SCHEDULE tab) | Set selected unit's starting MW to its rated maximum |

## What this does NOT let you do

- Rename, move, or add/remove buses, lines, or generation units on Alpha's
  grid — that's done in the **Grid Designer**, not here.
- Edit the shift's narrative text (handover notes, shift date, difficulty
  label, or the module docstring) — edit `shift_10.py` directly in a text
  editor for these.
- Edit `SCORING_HOOKS` — Shift 10 currently has none (dropped when it was
  moved onto the Alpha grid, since nothing in the game reads that field yet).
