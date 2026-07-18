"""
src/display/shift_builder_panels.py

Drawing for ShiftBuilder — a single full-screen form panel, tab-switched
between META / GRID / SCHEDULE / DEMAND / EVENTS. No canvas; the grid is
referenced by name only (edited spatially in the Grid Designer instead).

All drawing is done to the native 1920×1080 surface passed by
ShiftBuilder.tick().
"""

from __future__ import annotations

import pygame
import pygame.freetype

from display.palette import (
    COL_TEXT_PRIMARY, COL_TEXT_SECONDARY, COL_TEXT_DIM, COL_TEXT_VALUE,
    COL_TEXT_HEADING, COL_TEXT_WARN, COL_TEXT_CRIT, COL_TEXT_GOOD,
    COL_PANEL_BORDER, COL_SELECTION, COL_DESIGNER_STATUS_INFO,
    COL_DESIGNER_FIELD_ACTIVE,
)
from simulation.constants import (
    NATIVE_WIDTH, NATIVE_HEIGHT,
    SHIFT_BUILDER_ROW_H, SHIFT_BUILDER_LEFT_MARGIN, SHIFT_BUILDER_TOP_MARGIN,
)


TAB_W = 160


def draw_shift_builder(surf: pygame.Surface, builder, font, font_large) -> None:
    from display.shift_builder import TABS

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
    elif builder._editing_field is not None:
        _draw_edit_overlay(surf, font, builder._editing_field, builder._edit_buffer)


def _draw_tab_bar(surf, builder, font, tabs) -> None:
    from display.shift_builder import TABS
    x = SHIFT_BUILDER_LEFT_MARGIN
    y = SHIFT_BUILDER_TOP_MARGIN
    for i, name in enumerate(tabs):
        colour = COL_TEXT_HEADING if i == builder._tab_idx else COL_TEXT_SECONDARY
        prefix = '> ' if i == builder._tab_idx else '  '
        font.render_to(surf, (x, y), f'{prefix}{name}', colour, size=font.size)
        x += TAB_W
    pygame.draw.line(surf, COL_PANEL_BORDER,
                     (SHIFT_BUILDER_LEFT_MARGIN, y + SHIFT_BUILDER_ROW_H),
                     (NATIVE_WIDTH - SHIFT_BUILDER_LEFT_MARGIN, y + SHIFT_BUILDER_ROW_H), 1)


def _draw_shift_header(surf, builder, font) -> None:
    y = SHIFT_BUILDER_TOP_MARGIN + SHIFT_BUILDER_ROW_H + 4
    shift = builder._shift
    name = builder._shift_file_name or '(unsaved)'
    dirty = ' *' if builder._dirty else ''
    grid = shift.grid or '(none)'
    text = f'SHIFT: {name}{dirty}    GRID: {grid}    {shift.start_hour:.1f}h + {shift.duration_hours:.1f}h'
    font.render_to(surf, (SHIFT_BUILDER_LEFT_MARGIN, y), text, COL_TEXT_VALUE, size=font.size)


def _draw_footer(surf, builder, font) -> None:
    y = NATIVE_HEIGHT - 60
    hint = ('[TAB/←→] Tabs  [Ctrl+G] Grid  [Ctrl+S] Save  [Ctrl+O] Load  '
            '[Ctrl+T] Test  [ESC] Exit')
    font.render_to(surf, (SHIFT_BUILDER_LEFT_MARGIN, y), hint, COL_TEXT_DIM, size=font.size)
    if builder._status_timer > 0.0 and builder._status_text:
        font.render_to(surf, (SHIFT_BUILDER_LEFT_MARGIN, y + SHIFT_BUILDER_ROW_H),
                       builder._status_text, builder._status_colour, size=font.size)


# ─────────────────────────────────────────────────────────────────────────────
# META TAB
# ─────────────────────────────────────────────────────────────────────────────

def _draw_meta_tab(surf, builder, font, y0) -> None:
    shift = builder._shift
    x = SHIFT_BUILDER_LEFT_MARGIN
    y = y0
    rows = [
        ('1', 'Shift date',       shift.shift_date or '(unset)'),
        ('2', 'Difficulty label', shift.difficulty_label or '(unset)'),
        ('3', 'Start hour',       f'{shift.start_hour:.1f}'),
        ('4', 'Duration (h)',     f'{shift.duration_hours:.1f}'),
        ('5', 'AGC enabled',      'ON' if shift.agc_enabled else 'OFF'),
        ('6', 'Add handover note', ''),
    ]
    for key, label, value in rows:
        font.render_to(surf, (x, y), f'[{key}]', COL_TEXT_DIM, size=font.size)
        font.render_to(surf, (x + 40, y), label, COL_TEXT_SECONDARY, size=font.size)
        if value:
            font.render_to(surf, (x + 280, y), value, COL_TEXT_VALUE, size=font.size)
        y += SHIFT_BUILDER_ROW_H

    y += SHIFT_BUILDER_ROW_H // 2
    font.render_to(surf, (x, y), 'HANDOVER NOTES  (Backspace removes last):', COL_TEXT_HEADING, size=font.size)
    y += SHIFT_BUILDER_ROW_H
    for note in shift.handover_notes:
        font.render_to(surf, (x + 20, y), f'- {note}', COL_TEXT_PRIMARY, size=font.size)
        y += SHIFT_BUILDER_ROW_H


# ─────────────────────────────────────────────────────────────────────────────
# GRID TAB
# ─────────────────────────────────────────────────────────────────────────────

def _draw_grid_tab(surf, builder, font, y0) -> None:
    x = SHIFT_BUILDER_LEFT_MARGIN
    y = y0
    shift = builder._shift
    font.render_to(surf, (x, y), f'GRID: {shift.grid or "(none — press G to select)"}',
                   COL_TEXT_HEADING, size=font.size)
    y += SHIFT_BUILDER_ROW_H * 2

    if not builder._grid_units:
        font.render_to(surf, (x, y), '(no grid loaded)', COL_TEXT_DIM, size=font.size)
        return

    font.render_to(surf, (x, y),
                   'MAINTENANCE UNITS  [SPACE] toggle  (units on maintenance start OFFLINE and locked):',
                   COL_TEXT_SECONDARY, size=font.size)
    y += SHIFT_BUILDER_ROW_H

    visible_rows = 24
    start = max(0, builder._maint_unit_cursor - visible_rows // 2)
    for i, unit in enumerate(builder._grid_units[start:start + visible_rows], start=start):
        selected = (i == builder._maint_unit_cursor)
        on_maint = unit.label in shift.maintenance_units
        colour = COL_SELECTION if selected else (COL_TEXT_WARN if on_maint else COL_TEXT_PRIMARY)
        prefix = '> ' if selected else '  '
        status = '[MAINTENANCE]' if on_maint else ''
        font.render_to(surf, (x + 20, y), f'{prefix}{unit.label:<10} {unit.unit_type:<10} {status}',
                       colour, size=font.size)
        y += SHIFT_BUILDER_ROW_H


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULE TAB
# ─────────────────────────────────────────────────────────────────────────────

def _draw_schedule_tab(surf, builder, font, y0) -> None:
    x = SHIFT_BUILDER_LEFT_MARGIN
    y = y0
    shift = builder._shift

    if not builder._grid_units:
        font.render_to(surf, (x, y), '(select a grid first — GRID tab)', COL_TEXT_DIM, size=font.size)
        return

    font.render_to(surf, (x, y),
                   'INITIAL DISPATCH  [ENTER] set MW  [Backspace] clear (unit starts OFFLINE):',
                   COL_TEXT_SECONDARY, size=font.size)
    y += SHIFT_BUILDER_ROW_H

    visible_rows = 24
    start = max(0, builder._schedule_cursor - visible_rows // 2)
    for i, unit in enumerate(builder._grid_units[start:start + visible_rows], start=start):
        selected = (i == builder._schedule_cursor)
        mw = shift.initial_schedule.get(unit.label)
        state_str = f'{mw:.1f} MW' if mw is not None else 'OFFLINE'
        colour = COL_SELECTION if selected else (COL_TEXT_VALUE if mw is not None else COL_TEXT_DIM)
        prefix = '> ' if selected else '  '
        font.render_to(surf, (x + 20, y),
                       f'{prefix}{unit.label:<10} rated {unit.rated_mw:6.1f} MW   {state_str}',
                       colour, size=font.size)
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
        font.render_to(surf, (x, y), '(select a grid with LOAD buses first)', COL_TEXT_DIM, size=font.size)
        return

    font.render_to(surf, (x, y),
                   'HOURLY DEMAND (MW)  [Up/Down] bus  [PgUp/PgDn] hour  [ENTER] set:',
                   COL_TEXT_SECONDARY, size=font.size)
    y += SHIFT_BUILDER_ROW_H

    bus = load_buses[builder._demand_bus_cursor]
    hour = builder._demand_hour_cursor
    hourly = shift.substation_load_mw.get(bus.label, {})

    font.render_to(surf, (x, y), f'BUS: {bus.label}  (peak {bus.peak_load_mw:.0f} MW)',
                   COL_TEXT_HEADING, size=font.size)
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
        font.render_to(surf, (cx, cy), f'{prefix}{h:02d}h: {val_str:>6}', colour, size=font.size)


# ─────────────────────────────────────────────────────────────────────────────
# EVENTS TAB
# ─────────────────────────────────────────────────────────────────────────────

def _draw_events_tab(surf, builder, font, y0) -> None:
    x = SHIFT_BUILDER_LEFT_MARGIN
    y = y0
    events = builder._shift.events

    font.render_to(surf, (x, y),
                   'EVENTS  [N] new  [Del] remove  [Up/Down] select:',
                   COL_TEXT_SECONDARY, size=font.size)
    y += SHIFT_BUILDER_ROW_H

    list_y = y
    for i, evt in enumerate(events[:12]):
        selected = (i == builder._events_cursor)
        colour = COL_SELECTION if selected else COL_TEXT_PRIMARY
        prefix = '> ' if selected else '  '
        font.render_to(surf, (x + 20, list_y),
                       f'{prefix}T+{evt.trigger_min:>6.1f}min  {evt.priority:<11} {evt.message[:50]}',
                       colour, size=font.size)
        list_y += SHIFT_BUILDER_ROW_H

    if not events:
        font.render_to(surf, (x + 20, list_y), '(no events)', COL_TEXT_DIM, size=font.size)
        return

    # Detail editor for the selected event
    detail_y = y0 + SHIFT_BUILDER_ROW_H * 15
    evt = events[builder._events_cursor]
    pygame.draw.line(surf, COL_PANEL_BORDER, (x, detail_y - 8), (NATIVE_WIDTH - x, detail_y - 8), 1)

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
        font.render_to(surf, (x, dy), f'[{key}]', COL_TEXT_DIM, size=font.size)
        font.render_to(surf, (x + 40, dy), label, COL_TEXT_SECONDARY, size=font.size)
        font.render_to(surf, (x + 340, dy), str(value), COL_TEXT_VALUE, size=font.size)
        dy += SHIFT_BUILDER_ROW_H


# ─────────────────────────────────────────────────────────────────────────────
# OVERLAYS
# ─────────────────────────────────────────────────────────────────────────────

def _draw_text_dialog(surf, font, prompt, buf) -> None:
    w, h = 600, 120
    x = (NATIVE_WIDTH - w) // 2
    y = (NATIVE_HEIGHT - h) // 2
    pygame.draw.rect(surf, (0, 0, 0), (x, y, w, h))
    pygame.draw.rect(surf, COL_PANEL_BORDER, (x, y, w, h), 2)
    font.render_to(surf, (x + 20, y + 20), prompt, COL_TEXT_HEADING, size=font.size)
    font.render_to(surf, (x + 20, y + 50), buf + '_', COL_DESIGNER_FIELD_ACTIVE, size=font.size)
    font.render_to(surf, (x + 20, y + 80), '[ENTER] confirm   [ESC] cancel', COL_TEXT_DIM, size=font.size)


def _draw_browser(surf, font, title, items, idx) -> None:
    w, h = 600, 500
    x = (NATIVE_WIDTH - w) // 2
    y = (NATIVE_HEIGHT - h) // 2
    pygame.draw.rect(surf, (0, 0, 0), (x, y, w, h))
    pygame.draw.rect(surf, COL_PANEL_BORDER, (x, y, w, h), 2)
    font.render_to(surf, (x + 20, y + 20), title, COL_TEXT_HEADING, size=font.size)
    if not items:
        font.render_to(surf, (x + 20, y + 60), '(none saved)', COL_TEXT_DIM, size=font.size)
    for i, name in enumerate(items):
        colour = COL_SELECTION if i == idx else COL_TEXT_PRIMARY
        prefix = '> ' if i == idx else '  '
        font.render_to(surf, (x + 20, y + 60 + i * 24), f'{prefix}{name}', colour, size=font.size)
    font.render_to(surf, (x + 20, y + h - 30), '[ENTER] select   [ESC] cancel', COL_TEXT_DIM, size=font.size)


def _draw_edit_overlay(surf, font, field, buf) -> None:
    w, h = 700, 100
    x = (NATIVE_WIDTH - w) // 2
    y = (NATIVE_HEIGHT - h) // 2
    pygame.draw.rect(surf, (0, 0, 0), (x, y, w, h))
    pygame.draw.rect(surf, COL_PANEL_BORDER, (x, y, w, h), 2)
    font.render_to(surf, (x + 20, y + 15), f'EDIT: {field}', COL_TEXT_HEADING, size=font.size)
    font.render_to(surf, (x + 20, y + 45), buf + '_', COL_DESIGNER_FIELD_ACTIVE, size=font.size)
    font.render_to(surf, (x + 20, y + 75), '[ENTER] confirm   [ESC] cancel', COL_TEXT_DIM, size=font.size)
