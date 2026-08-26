"""
src/display/shift_builder_panels.py

Drawing for ShiftBuilder — a single full-screen form panel, tab-switched
between META / GRID / SCHEDULE / DEMAND / EVENTS. No canvas; the grid is
referenced by name only (edited spatially in the Grid Designer instead).

All drawing coordinates in this file (SHIFT_BUILDER_*, TAB_W, and every
literal passed to _label()/_rect() below) are expressed in LOGICAL
(unscaled) 1920×1080 native-space pixels — the same space ShiftBuilder's
hit-testing (on_click, to_native) operates in. _label()/_rect() are the
only two places that convert to the surf's actual (scaled) pixel space,
at the point of drawing — surf itself is sized at real display resolution
(see ShiftBuilder.tick()).
"""

from __future__ import annotations

import pygame
import pygame.freetype

from config.palette import (
    COL_TEXT_PRIMARY, COL_TEXT_SECONDARY, COL_TEXT_DIM, COL_TEXT_VALUE,
    COL_TEXT_HEADING, COL_TEXT_WARN, COL_TEXT_CRIT, COL_TEXT_GOOD,
    COL_PANEL_BORDER, COL_SELECTION, COL_DESIGNER_STATUS_INFO,
    COL_DESIGNER_FIELD_ACTIVE,
)
from config.constants import (
    NATIVE_WIDTH, NATIVE_HEIGHT,
    SHIFT_BUILDER_ROW_H, SHIFT_BUILDER_LEFT_MARGIN, SHIFT_BUILDER_TOP_MARGIN,
)


TAB_W = 160

_scale: float = 1.0


def _label(surf, font, x, y, text, colour) -> None:
    sc = _scale
    font.render_to(surf, (int(x * sc), int(y * sc)), text, colour,
                   size=int(font.size * sc))


def _rect(surf, colour, x, y, w, h, width: int = 0) -> None:
    sc = _scale
    pygame.draw.rect(surf, colour,
                     (int(x * sc), int(y * sc), int(w * sc), int(h * sc)), width)


def _line(surf, colour, p1, p2, width: int = 1) -> None:
    sc = _scale
    pygame.draw.line(surf, colour,
                     (int(p1[0] * sc), int(p1[1] * sc)),
                     (int(p2[0] * sc), int(p2[1] * sc)), width)


def draw_shift_builder(surf: pygame.Surface, builder, font, font_large, scale: float = 1.0) -> None:
    from display.shift_builder import TABS
    global _scale
    _scale = scale

    _draw_tab_bar(surf, builder, font, TABS)
    _draw_shift_header(surf, builder, font)

    content_y = SHIFT_BUILDER_TOP_MARGIN + SHIFT_BUILDER_ROW_H * 2 + 12
    tab = TABS[builder._tab_idx]
    if tab == 'META':
        _draw_meta_tab(surf, builder, font, content_y)
    elif tab == 'GRID':
        _draw_grid_tab(surf, builder, font, content_y)
    elif tab == 'SCHEDULE':
        _draw_schedule_tab(surf, builder, font, content_y)
    elif tab == 'DEMAND':
        _draw_demand_tab(surf, builder, font, content_y)
    elif tab == 'EVENTS':
        _draw_events_tab(surf, builder, font, content_y)

    _draw_footer(surf, builder, font)

    if builder._mode == 'save_dialog':
        _draw_text_dialog(surf, font, 'SAVE SHIFT AS:', builder._dialog_buf)
    elif builder._mode == 'load_browser':
        _draw_browser(surf, font, 'LOAD SHIFT', builder._browser_list, builder._browser_idx)
    elif builder._mode == 'grid_browser':
        _draw_browser(surf, font, 'SELECT GRID', builder._browser_list, builder._browser_idx)
    elif builder._mode == 'campaign_browser':
        _draw_browser(surf, font, 'OPEN CAMPAIGN SHIFT', builder._browser_list, builder._browser_idx)
    elif builder._editing_field is not None:
        _draw_edit_overlay(surf, font, builder._editing_field, builder._edit_buffer)


def _draw_tab_bar(surf, builder, font, tabs) -> None:
    from display.shift_builder import TABS
    x = SHIFT_BUILDER_LEFT_MARGIN
    y = SHIFT_BUILDER_TOP_MARGIN
    for i, name in enumerate(tabs):
        colour = COL_TEXT_HEADING if i == builder._tab_idx else COL_TEXT_SECONDARY
        prefix = '> ' if i == builder._tab_idx else '  '
        _label(surf, font, x, y, f'{prefix}{name}', colour)
        x += TAB_W
    _line(surf, COL_PANEL_BORDER, (SHIFT_BUILDER_LEFT_MARGIN, y + SHIFT_BUILDER_ROW_H), (NATIVE_WIDTH - SHIFT_BUILDER_LEFT_MARGIN, y + SHIFT_BUILDER_ROW_H), 1)


def _draw_shift_header(surf, builder, font) -> None:
    y = SHIFT_BUILDER_TOP_MARGIN + SHIFT_BUILDER_ROW_H + 4
    shift = builder._shift
    dirty = ' *' if builder._dirty else ''
    grid = shift.grid or '(none)'
    if builder._campaign_shift_number is not None:
        name = f'CAMPAIGN SHIFT {builder._campaign_shift_number} (shift_{builder._campaign_shift_number:02d}.py)'
    else:
        name = builder._shift_file_name or '(unsaved)'
    text = f'EDITING: {name}{dirty}    GRID: {grid}    {shift.start_hour:.1f}h + {shift.duration_hours:.1f}h'
    _label(surf, font, SHIFT_BUILDER_LEFT_MARGIN, y, text, COL_TEXT_VALUE)


def _draw_footer(surf, builder, font) -> None:
    y = NATIVE_HEIGHT - 60
    hint = ('[TAB/←→] Tabs  [Ctrl+G] Grid  [Ctrl+S] Save  [Ctrl+O] Load  '
            '[Ctrl+Shift+O] Open Campaign  [Ctrl+T] Test  [ESC] Exit')
    _label(surf, font, SHIFT_BUILDER_LEFT_MARGIN, y, hint, COL_TEXT_PRIMARY)
    if builder._status_timer > 0.0 and builder._status_text:
        _label(surf, font, SHIFT_BUILDER_LEFT_MARGIN, y + SHIFT_BUILDER_ROW_H, builder._status_text, builder._status_colour)


# ─────────────────────────────────────────────────────────────────────────────
# META TAB
# ─────────────────────────────────────────────────────────────────────────────

def _draw_meta_tab(surf, builder, font, y0) -> None:
    shift = builder._shift
    is_campaign = builder._campaign_shift_number is not None
    x = SHIFT_BUILDER_LEFT_MARGIN
    y = y0

    if is_campaign:
        _label(surf, font, x, y,
               'Narrative fields below are read-only — edit shift_NN.py directly for these:',
               COL_TEXT_DIM)
        y += SHIFT_BUILDER_ROW_H

    dim_or_normal = COL_TEXT_DIM if is_campaign else COL_TEXT_SECONDARY
    rows = [
        ('1', 'Shift date',       shift.shift_date or '(unset)',       is_campaign),
        ('2', 'Difficulty label', shift.difficulty_label or '(unset)', is_campaign),
        ('3', 'Start hour',       f'{shift.start_hour:.1f}',           is_campaign),
        ('4', 'Duration (h)',     f'{shift.duration_hours:.1f}',       is_campaign),
        ('5', 'AGC enabled',      'ON' if shift.agc_enabled else 'OFF', False),
        ('6', 'Add handover note', '',                                  is_campaign),
    ]
    for key, label, value, locked in rows:
        key_colour = COL_TEXT_DIM if locked else COL_TEXT_DIM
        _label(surf, font, x, y, f'[{key}]' if not locked else '[ - ]', key_colour)
        _label(surf, font, x + 40, y, label, dim_or_normal if locked else COL_TEXT_SECONDARY)
        if value:
            _label(surf, font, x + 280, y, value, COL_TEXT_DIM if locked else COL_TEXT_VALUE)
        y += SHIFT_BUILDER_ROW_H

    y += SHIFT_BUILDER_ROW_H // 2
    notes_hint = 'HANDOVER NOTES  (read-only):' if is_campaign else 'HANDOVER NOTES  (Backspace removes last):'
    _label(surf, font, x, y, notes_hint, COL_TEXT_HEADING)
    y += SHIFT_BUILDER_ROW_H
    for note in shift.handover_notes:
        _label(surf, font, x + 20, y, f'- {note}', COL_TEXT_DIM if is_campaign else COL_TEXT_PRIMARY)
        y += SHIFT_BUILDER_ROW_H


# ─────────────────────────────────────────────────────────────────────────────
# GRID TAB
# ─────────────────────────────────────────────────────────────────────────────

def _draw_grid_tab(surf, builder, font, y0) -> None:
    x = SHIFT_BUILDER_LEFT_MARGIN
    y = y0
    shift = builder._shift
    is_campaign = builder._campaign_shift_number is not None

    if is_campaign:
        if shift.grid:
            grid_line = f'GRID: {shift.grid}  (read-only here — edit topology in the Grid Designer)'
        else:
            grid_line = 'GRID: campaign topology (topology.py/fleet.py) — not editable here'
        _label(surf, font, x, y, grid_line, COL_TEXT_DIM)
    else:
        _label(surf, font, x, y, f'GRID: {shift.grid or "(none — press G to select)"}',
                       COL_TEXT_HEADING)
    y += SHIFT_BUILDER_ROW_H * 2

    if not builder._grid_units:
        _label(surf, font, x, y, '(no grid loaded)', COL_TEXT_DIM)
        return

    _label(surf, font, x, y, 'MAINTENANCE UNITS  [SPACE] toggle  (units on maintenance start OFFLINE and locked):',
                   COL_TEXT_SECONDARY)
    y += SHIFT_BUILDER_ROW_H

    visible_rows = 24
    start = max(0, builder._maint_unit_cursor - visible_rows // 2)
    for i, unit in enumerate(builder._grid_units[start:start + visible_rows], start=start):
        selected = (i == builder._maint_unit_cursor)
        on_maint = unit.label in shift.maintenance_units
        colour = COL_SELECTION if selected else (COL_TEXT_WARN if on_maint else COL_TEXT_PRIMARY)
        prefix = '> ' if selected else '  '
        status = '[MAINTENANCE]' if on_maint else ''
        _label(surf, font, x + 20, y, f'{prefix}{unit.label:<10} {unit.unit_type:<10} {status}',
                       colour)
        y += SHIFT_BUILDER_ROW_H


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULE TAB
# ─────────────────────────────────────────────────────────────────────────────

def _draw_schedule_tab(surf, builder, font, y0) -> None:
    x = SHIFT_BUILDER_LEFT_MARGIN
    y = y0
    shift = builder._shift

    if not builder._grid_units:
        _label(surf, font, x, y, '(select a grid first — GRID tab)', COL_TEXT_DIM)
        return

    _label(surf, font, x, y,
                   'INITIAL DISPATCH  [ENTER] set MW  [M] tech min  [X] max  [Backspace] OFFLINE:',
                   COL_TEXT_SECONDARY)
    y += SHIFT_BUILDER_ROW_H

    visible_rows = 24
    start = max(0, builder._schedule_cursor - visible_rows // 2)
    for i, unit in enumerate(builder._grid_units[start:start + visible_rows], start=start):
        selected = (i == builder._schedule_cursor)
        mw = shift.initial_schedule.get(unit.label)
        state_str = f'{mw:.1f} MW' if mw is not None else 'OFFLINE'
        colour = COL_SELECTION if selected else (COL_TEXT_VALUE if mw is not None else COL_TEXT_DIM)
        prefix = '> ' if selected else '  '
        _label(surf, font, x + 20, y,
                       f'{prefix}{unit.label:<10} tech min {unit.min_mw:6.1f}  max {unit.rated_mw:6.1f} MW   {state_str}',
                       colour)
        y += SHIFT_BUILDER_ROW_H


# ─────────────────────────────────────────────────────────────────────────────
# DEMAND TAB
# ─────────────────────────────────────────────────────────────────────────────

def _draw_demand_tab(surf, builder, font, y0) -> None:
    x = SHIFT_BUILDER_LEFT_MARGIN
    y = y0
    shift = builder._shift
    load_buses = builder._load_buses()

    if not load_buses:
        _label(surf, font, x, y, '(select a grid with LOAD buses first)', COL_TEXT_DIM)
        return

    _label(surf, font, x, y, 'HOURLY DEMAND (MW)  [Up/Down] bus  [PgUp/PgDn] hour  [ENTER] set:',
                   COL_TEXT_SECONDARY)
    y += SHIFT_BUILDER_ROW_H

    bus = load_buses[builder._demand_bus_cursor]
    hour = builder._demand_hour_cursor
    hourly = shift.substation_load_mw.get(bus.label, {})

    _label(surf, font, x, y, f'BUS: {bus.label}  (peak {bus.peak_load_mw:.0f} MW)',
                   COL_TEXT_HEADING)
    y += SHIFT_BUILDER_ROW_H * 2

    cols = 6
    cell_w = 140
    for h in range(25):
        col = h % cols
        row = h // cols
        cx = x + col * cell_w
        cy = y + row * SHIFT_BUILDER_ROW_H
        mw = hourly.get(float(h))
        selected = (h == hour)
        colour = COL_SELECTION if selected else (COL_TEXT_VALUE if mw is not None else COL_TEXT_DIM)
        val_str = f'{mw:.0f}' if mw is not None else '--'
        prefix = '>' if selected else ' '
        _label(surf, font, cx, cy, f'{prefix}{h:02d}h: {val_str:>6}', colour)


# ─────────────────────────────────────────────────────────────────────────────
# EVENTS TAB
# ─────────────────────────────────────────────────────────────────────────────

def _draw_events_tab(surf, builder, font, y0) -> None:
    x = SHIFT_BUILDER_LEFT_MARGIN
    y = y0
    events = builder._shift.events

    _label(surf, font, x, y, 'EVENTS  [N] new  [Del] remove  [Up/Down] select:',
                   COL_TEXT_SECONDARY)
    y += SHIFT_BUILDER_ROW_H

    list_y = y
    for i, evt in enumerate(events[:12]):
        selected = (i == builder._events_cursor)
        colour = COL_SELECTION if selected else COL_TEXT_PRIMARY
        prefix = '> ' if selected else '  '
        _label(surf, font, x + 20, list_y, f'{prefix}T+{evt.trigger_min:>6.1f}min  {evt.priority:<11} {evt.message[:50]}',
                       colour)
        list_y += SHIFT_BUILDER_ROW_H

    if not events:
        _label(surf, font, x + 20, list_y, '(no events)', COL_TEXT_DIM)
        return

    # Detail editor for the selected event
    detail_y = y0 + SHIFT_BUILDER_ROW_H * 15
    evt = events[builder._events_cursor]
    _line(surf, COL_PANEL_BORDER, (x, detail_y - 8), (NATIVE_WIDTH - x, detail_y - 8), 1)

    cond_str = 'none'
    if evt.condition:
        cond_str = (f"{evt.condition.get('metric','')} "
                    f"{evt.condition.get('target') or evt.condition.get('targets','')} "
                    f"{evt.condition.get('op','')} {evt.condition.get('value','')}")
    action_str = 'none'
    if evt.action:
        target = evt.action.get('line') or evt.action.get('unit') or ''
        action_str = f"{evt.action['type']} {target}"

    detail_rows = [
        ('1', 'Trigger (min)', f'{evt.trigger_min:.1f}'),
        ('2', 'Priority',      evt.priority),
        ('3', 'Message',       evt.message),
        ('4', 'Detail',        (evt.detail[:60] + '...') if len(evt.detail) > 60 else evt.detail),
        ('5', 'Element',       evt.element or '(none)'),
        ('6', 'Condition (cycle metric)', cond_str),
        ('7', 'Action (cycle type)',      action_str),
    ]
    dy = detail_y
    for key, label, value in detail_rows:
        _label(surf, font, x, dy, f'[{key}]', COL_TEXT_DIM)
        _label(surf, font, x + 40, dy, label, COL_TEXT_SECONDARY)
        _label(surf, font, x + 340, dy, str(value), COL_TEXT_VALUE)
        dy += SHIFT_BUILDER_ROW_H


# ─────────────────────────────────────────────────────────────────────────────
# OVERLAYS
# ─────────────────────────────────────────────────────────────────────────────

def _draw_text_dialog(surf, font, prompt, buf) -> None:
    w, h = 600, 120
    x = (NATIVE_WIDTH - w) // 2
    y = (NATIVE_HEIGHT - h) // 2
    _rect(surf, (0, 0, 0), x, y, w, h)
    _rect(surf, COL_PANEL_BORDER, x, y, w, h, 2)
    _label(surf, font, x + 20, y + 20, prompt, COL_TEXT_HEADING)
    _label(surf, font, x + 20, y + 50, buf + '_', COL_DESIGNER_FIELD_ACTIVE)
    _label(surf, font, x + 20, y + 80, '[ENTER] confirm   [ESC] cancel', COL_TEXT_DIM)


def _draw_browser(surf, font, title, items, idx) -> None:
    w, h = 600, 500
    x = (NATIVE_WIDTH - w) // 2
    y = (NATIVE_HEIGHT - h) // 2
    _rect(surf, (0, 0, 0), x, y, w, h)
    _rect(surf, COL_PANEL_BORDER, x, y, w, h, 2)
    _label(surf, font, x + 20, y + 20, title, COL_TEXT_HEADING)
    if not items:
        _label(surf, font, x + 20, y + 60, '(none saved)', COL_TEXT_DIM)
    for i, name in enumerate(items):
        colour = COL_SELECTION if i == idx else COL_TEXT_PRIMARY
        prefix = '> ' if i == idx else '  '
        _label(surf, font, x + 20, y + 60 + i * 24, f'{prefix}{name}', colour)
    _label(surf, font, x + 20, y + h - 30, '[ENTER] select   [ESC] cancel', COL_TEXT_DIM)


def _draw_edit_overlay(surf, font, field, buf) -> None:
    w, h = 700, 100
    x = (NATIVE_WIDTH - w) // 2
    y = (NATIVE_HEIGHT - h) // 2
    _rect(surf, (0, 0, 0), x, y, w, h)
    _rect(surf, COL_PANEL_BORDER, x, y, w, h, 2)
    _label(surf, font, x + 20, y + 15, f'EDIT: {field}', COL_TEXT_HEADING)
    _label(surf, font, x + 20, y + 45, buf + '_', COL_DESIGNER_FIELD_ACTIVE)
    _label(surf, font, x + 20, y + 75, '[ENTER] confirm   [ESC] cancel', COL_TEXT_DIM)
