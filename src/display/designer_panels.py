"""
src/display/designer_panels.py

Sidebar drawing for the Grid Designer mode.

The sidebar is 320px wide and occupies the right edge of the 1920×1080
native surface (from x=1600 to x=1920, full height 1080px).

Layout (top → bottom):
  [0–60]    Power balance summary
  [60–70]   Separator
  [70–310]  Palette — Bus types + Unit types + Delete
  [310–320] Separator
  [320–…]   Properties panel (selected element)
  [… –1050] Actions panel
  [1050–80] Footer hint

All drawing is done to a subsurface passed by GridDesigner.draw().
"""

from __future__ import annotations

import pygame
import pygame.freetype

from display.palette import (
    COL_BACKGROUND, COL_TEXT_PRIMARY, COL_TEXT_SECONDARY, COL_TEXT_DIM,
    COL_TEXT_VALUE, COL_TEXT_HEADING, COL_TEXT_WARN, COL_TEXT_CRIT,
    COL_TEXT_GOOD, COL_PANEL_BORDER,
    COL_400KV, COL_220KV, COL_150KV, COL_60KV,
    COL_UNIT_COAL, COL_UNIT_CCGT, COL_UNIT_NUCLEAR,
    COL_UNIT_HYDRO, COL_UNIT_WIND, COL_UNIT_SOLAR, COL_UNIT_HYDRO_PUMP,
    COL_DESIGNER_SIDEBAR_BG, COL_DESIGNER_SIDEBAR_SEP,
    COL_DESIGNER_PALETTE_SEL, COL_DESIGNER_PALETTE_BTN,
    COL_DESIGNER_SURPLUS_POS, COL_DESIGNER_SURPLUS_NEG,
    COL_DESIGNER_FIELD_ACTIVE, COL_DESIGNER_DELETE_CURSOR,
    COL_SELECTION,
)
from simulation.constants import DESIGNER_SIDEBAR_W, NATIVE_HEIGHT


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT CONSTANTS (relative to sidebar left=0, top=0)
# ─────────────────────────────────────────────────────────────────────────────

PAD = 8
ROW_H = 18
BTN_H = 22
BTN_W = 140

SECTION_BALANCE_Y  = 0
SECTION_PALETTE_Y  = 64
SECTION_PROPS_Y    = 320
SECTION_ACTIONS_Y  = 680
SECTION_FOOTER_Y   = NATIVE_HEIGHT - 30


# ─────────────────────────────────────────────────────────────────────────────
# BUTTON REGISTRY
# hit_rects holds (action_string, pygame.Rect) per frame; rebuilt each draw.
# _overlay_rects same for save/load overlay.
# ─────────────────────────────────────────────────────────────────────────────

_hit_rects:     list[tuple[str, pygame.Rect]] = []
_overlay_rects: list[tuple[str, pygame.Rect]] = []


def sidebar_button_at(sx: int, sy: int, designer) -> str | None:
    """Return the action string for a click at (sx, sy) in sidebar space."""
    for action, rect in _hit_rects:
        if rect.collidepoint(sx, sy):
            return action
    return None


def sidebar_overlay_click_at(sx: int, sy: int, designer) -> str | None:
    """Return the action string for a click inside the save/load overlay."""
    for action, rect in _overlay_rects:
        if rect.collidepoint(sx, sy):
            return action
    return None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN DRAW ENTRY
# ─────────────────────────────────────────────────────────────────────────────

def draw_sidebar(
    surf: pygame.Surface,
    designer,
    font: pygame.freetype.Font,
    font_bold: pygame.freetype.Font,
) -> None:
    """Draw the complete sidebar.  surf is the 320×1080 subsurface."""
    global _hit_rects, _overlay_rects
    _hit_rects    = []
    _overlay_rects = []

    surf.fill(COL_DESIGNER_SIDEBAR_BG)

    mode = designer._sidebar_mode

    if mode == 'save_dialog':
        _draw_save_dialog(surf, font, font_bold, designer)
        return

    if mode in ('load_browser', 'test_browser'):
        _draw_load_browser(surf, font, font_bold, designer, test_mode=(mode == 'test_browser'))
        return

    # Normal sidebar
    y = _draw_balance(surf, font, font_bold, designer, SECTION_BALANCE_Y)
    _hsep(surf, y)
    y = _draw_palette(surf, font, font_bold, designer, SECTION_PALETTE_Y)
    _hsep(surf, y)
    y = _draw_properties(surf, font, font_bold, designer, y + 4)
    _hsep(surf, y)
    _draw_actions(surf, font, font_bold, designer, y + 4)
    _draw_footer(surf, font, designer, SECTION_FOOTER_Y)


# ─────────────────────────────────────────────────────────────────────────────
# SECTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _draw_balance(surf, font, font_bold, designer, y0: int) -> int:
    y = y0 + PAD
    _label(surf, font_bold, PAD, y, 'POWER BALANCE', COL_TEXT_HEADING)
    y += ROW_H + 2

    gen  = designer.gen_capacity_mw()
    load = designer.peak_load_mw()
    surplus = gen - load
    s_col   = COL_DESIGNER_SURPLUS_POS if surplus >= 0 else COL_DESIGNER_SURPLUS_NEG

    _label(surf, font, PAD, y,    f'GEN CAPACITY   {gen:>8,.0f} MW', COL_TEXT_VALUE)
    y += ROW_H
    _label(surf, font, PAD, y,    f'PEAK LOAD      {load:>8,.0f} MW', COL_TEXT_SECONDARY)
    y += ROW_H
    sign = '+' if surplus >= 0 else ''
    _label(surf, font, PAD, y,    f'SURPLUS        {sign}{surplus:>7,.0f} MW', s_col)
    y += ROW_H + PAD
    return y


def _draw_palette(surf, font, font_bold, designer, y0: int) -> int:
    from display.designer import (
        MODE_SELECT, MODE_BUS, MODE_UNIT, MODE_LINE, MODE_DELETE,
    )

    y = y0 + PAD
    _label(surf, font_bold, PAD, y, 'PALETTE', COL_TEXT_HEADING)
    y += ROW_H + 2

    # Bus buttons
    _label(surf, font, PAD, y, 'BUS', COL_TEXT_SECONDARY)
    y += ROW_H

    bus_voltages = [
        ('400 kV', 400.0, COL_400KV),
        ('220 kV', 220.0, COL_220KV),
        ('150 kV', 150.0, COL_150KV),
        ('60 kV (LOAD)', 60.0, COL_60KV),
    ]
    x_left = PAD
    x_right = PAD + BTN_W + 8

    for i, (lbl, vkv, col) in enumerate(bus_voltages):
        action = f'bus_{vkv:.0f}'
        active = (designer._palette_mode == MODE_BUS and
                  designer._palette_voltage == vkv)
        btn_col = col if active else COL_DESIGNER_PALETTE_BTN
        bx = x_left if i % 2 == 0 else x_right
        bw = BTN_W
        rect = pygame.Rect(bx, y, bw, BTN_H)
        pygame.draw.rect(surf, (0, 0, 0), rect)
        pygame.draw.rect(surf, btn_col, rect, 1)
        _label(surf, font, bx + 4, y + 4, lbl, btn_col)
        _hit_rects.append((action, rect))
        if i % 2 == 1:
            y += BTN_H + 3

    y += BTN_H + 6

    # Unit buttons
    _label(surf, font, PAD, y, 'UNIT', COL_TEXT_SECONDARY)
    y += ROW_H

    unit_types = [
        ('COAL',      COL_UNIT_COAL),
        ('CCGT',      COL_UNIT_CCGT),
        ('NUCLEAR',   COL_UNIT_NUCLEAR),
        ('HYDRO',     COL_UNIT_HYDRO),
        ('HYDRO_ROR', COL_UNIT_HYDRO),
        ('HYDRO_PUMP',COL_UNIT_HYDRO_PUMP),
        ('WIND',      COL_UNIT_WIND),
        ('SOLAR',     COL_UNIT_SOLAR),
    ]
    for i, (utype, col) in enumerate(unit_types):
        action = f'unit_{utype}'
        active = (designer._palette_mode == MODE_UNIT and
                  designer._palette_unit_type == utype)
        btn_col = col if active else COL_DESIGNER_PALETTE_BTN
        bx = x_left if i % 2 == 0 else x_right
        bw = BTN_W
        rect = pygame.Rect(bx, y, bw, BTN_H)
        pygame.draw.rect(surf, (0, 0, 0), rect)
        pygame.draw.rect(surf, btn_col, rect, 1)
        _label(surf, font, bx + 4, y + 4, utype, btn_col)
        _hit_rects.append((action, rect))
        if i % 2 == 1:
            y += BTN_H + 3

    y += BTN_H + 6

    # Delete button (left) + LINE button (right)
    del_active  = designer._palette_mode == MODE_DELETE
    line_active = designer._palette_mode == MODE_LINE
    del_col  = COL_DESIGNER_DELETE_CURSOR if del_active  else COL_DESIGNER_PALETTE_BTN
    line_col = COL_SELECTION              if line_active else COL_DESIGNER_PALETTE_BTN

    del_rect  = pygame.Rect(x_left,  y, BTN_W, BTN_H)
    line_rect = pygame.Rect(x_right, y, BTN_W, BTN_H)
    for rect, col, lbl, act in (
        (del_rect,  del_col,  'DELETE (D)', 'delete'),
        (line_rect, line_col, 'LINE (L)',   'line_mode'),
    ):
        pygame.draw.rect(surf, (0, 0, 0), rect)
        pygame.draw.rect(surf, col, rect, 1)
        _label(surf, font, rect.x + 4, y + 4, lbl, col)
        _hit_rects.append((act, rect))

    y += BTN_H + 4

    # Line rating selector: [−]  1200 MW  [+]
    _label(surf, font, PAD, y + 4, 'LINE RATING:', COL_TEXT_SECONDARY)
    rating_str = f'{designer._palette_line_rating:.0f} MW'
    minus_r = pygame.Rect(PAD + 110, y, 22, BTN_H)
    plus_r  = pygame.Rect(PAD + 110 + 80, y, 22, BTN_H)
    for btn_r, act, lbl in ((minus_r, 'line_rating_down', '-'),
                             (plus_r,  'line_rating_up',   '+')):
        pygame.draw.rect(surf, (30, 30, 30), btn_r)
        pygame.draw.rect(surf, COL_PANEL_BORDER, btn_r, 1)
        _label(surf, font, btn_r.x + 5, btn_r.y + 4, lbl, COL_TEXT_PRIMARY)
        _hit_rects.append((act, btn_r))
    val_x = minus_r.right + 4
    _label(surf, font, val_x, y + 4, rating_str,
           COL_SELECTION if line_active else COL_TEXT_VALUE)

    y += BTN_H + PAD
    return y


def _draw_properties(surf, font, font_bold, designer, y0: int) -> int:
    y = y0
    _label(surf, font_bold, PAD, y, 'PROPERTIES', COL_TEXT_HEADING)
    y += ROW_H + 4

    bus  = designer._selected_bus
    line = designer._selected_line
    unit = designer._selected_unit

    if bus is None and line is None and unit is None:
        _label(surf, font, PAD, y, 'No element selected', COL_TEXT_DIM)
        y += ROW_H
        return y + PAD

    if bus is not None:
        # Editable label field
        editing_label = (designer._editing_field == 'label')
        lbl_disp = designer._edit_buffer if editing_label else bus.label
        field_col = COL_DESIGNER_FIELD_ACTIVE if editing_label else COL_PANEL_BORDER
        _label(surf, font, PAD, y, 'LABEL:', COL_TEXT_SECONDARY)
        field_rect = pygame.Rect(80, y - 2, 100, ROW_H + 2)
        pygame.draw.rect(surf, (0, 0, 0), field_rect)
        pygame.draw.rect(surf, field_col, field_rect, 1)
        _label(surf, font, 84, y,
               (lbl_disp + '_') if editing_label else lbl_disp,
               COL_TEXT_VALUE)
        y += ROW_H + 2
        _label(surf, font, PAD, y, f'NAME:    {bus.name}',     COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, PAD, y, f'VOLTAGE: {bus.voltage_kv:.0f} kV', COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, PAD, y, f'TYPE:    {bus.bus_type}', COL_TEXT_SECONDARY)
        y += ROW_H
        if bus.bus_type == 'LOAD':
            _label(surf, font, PAD, y, f'PK LOAD: {bus.peak_load_mw:.0f} MW',
                   COL_TEXT_SECONDARY)
            y += ROW_H

        # Shift
        y += 4
        _label(surf, font, PAD, y, f'SHIFT FROM: {bus.active_from_shift}', COL_TEXT_SECONDARY)
        # +/- buttons
        minus_r = pygame.Rect(150, y - 2, 22, ROW_H)
        plus_r  = pygame.Rect(176, y - 2, 22, ROW_H)
        pygame.draw.rect(surf, (30, 30, 30), minus_r)
        pygame.draw.rect(surf, COL_PANEL_BORDER, minus_r, 1)
        pygame.draw.rect(surf, (30, 30, 30), plus_r)
        pygame.draw.rect(surf, COL_PANEL_BORDER, plus_r, 1)
        _label(surf, font, minus_r.x + 5, minus_r.y + 2, '-', COL_TEXT_PRIMARY)
        _label(surf, font, plus_r.x  + 5, plus_r.y  + 2, '+', COL_TEXT_PRIMARY)
        _hit_rects.append(('prop_shift_minus', minus_r))
        _hit_rects.append(('prop_shift_plus',  plus_r))
        y += ROW_H + 2

        # Anchor
        _label(surf, font, PAD, y,
               f'ANCHOR:  {bus.label_anchor}  (R to rotate)', COL_TEXT_DIM)
        y += ROW_H

        # Slack toggle
        slack_col = COL_TEXT_GOOD if bus.is_slack else COL_TEXT_DIM
        slack_rect = pygame.Rect(PAD, y, 120, ROW_H + 2)
        pygame.draw.rect(surf, (0, 0, 0), slack_rect)
        pygame.draw.rect(surf, slack_col, slack_rect, 1)
        _label(surf, font, PAD + 4, y + 2,
               'SLACK BUS' if bus.is_slack else 'Set as slack', slack_col)
        _hit_rects.append(('prop_slack_toggle', slack_rect))
        y += ROW_H + 4

    elif line is not None:
        _label(surf, font, PAD, y, f'LINE:    {line.label}',          COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, PAD, y, f'ROUTE:   {line.from_bus}→{line.to_bus}',
               COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, PAD, y, f'VOLTAGE: {line.voltage_kv:.0f} kV',
               COL_TEXT_SECONDARY)
        y += ROW_H

        # Editable reactance
        editing_x = (designer._editing_field == 'reactance_pu')
        x_disp = designer._edit_buffer if editing_x else f'{line.reactance_pu:.4f}'
        field_col = COL_DESIGNER_FIELD_ACTIVE if editing_x else COL_PANEL_BORDER
        _label(surf, font, PAD, y, 'X PU:', COL_TEXT_SECONDARY)
        xf_rect = pygame.Rect(70, y - 2, 100, ROW_H + 2)
        pygame.draw.rect(surf, (0, 0, 0), xf_rect)
        pygame.draw.rect(surf, field_col, xf_rect, 1)
        _label(surf, font, 74, y,
               (x_disp + '_') if editing_x else x_disp, COL_TEXT_VALUE)
        if not editing_x:
            # Click → edit
            _hit_rects.append(('edit_reactance_pu', xf_rect))
        y += ROW_H + 2

        # Editable rating
        editing_r = (designer._editing_field == 'rating_mw')
        r_disp = designer._edit_buffer if editing_r else f'{line.rating_mw:.0f}'
        field_col = COL_DESIGNER_FIELD_ACTIVE if editing_r else COL_PANEL_BORDER
        _label(surf, font, PAD, y, 'RATING:', COL_TEXT_SECONDARY)
        rf_rect = pygame.Rect(80, y - 2, 90, ROW_H + 2)
        pygame.draw.rect(surf, (0, 0, 0), rf_rect)
        pygame.draw.rect(surf, field_col, rf_rect, 1)
        _label(surf, font, 84, y,
               (r_disp + '_') if editing_r else (r_disp + ' MW'), COL_TEXT_VALUE)
        if not editing_r:
            _hit_rects.append(('edit_rating_mw', rf_rect))
        y += ROW_H + 2

        # Shift
        _label(surf, font, PAD, y, f'SHIFT FROM: {line.active_from_shift}',
               COL_TEXT_SECONDARY)
        minus_r = pygame.Rect(150, y - 2, 22, ROW_H)
        plus_r  = pygame.Rect(176, y - 2, 22, ROW_H)
        pygame.draw.rect(surf, (30, 30, 30), minus_r)
        pygame.draw.rect(surf, COL_PANEL_BORDER, minus_r, 1)
        pygame.draw.rect(surf, (30, 30, 30), plus_r)
        pygame.draw.rect(surf, COL_PANEL_BORDER, plus_r, 1)
        _label(surf, font, minus_r.x + 5, minus_r.y + 2, '-', COL_TEXT_PRIMARY)
        _label(surf, font, plus_r.x  + 5, plus_r.y  + 2, '+', COL_TEXT_PRIMARY)
        _hit_rects.append(('prop_shift_minus', minus_r))
        _hit_rects.append(('prop_shift_plus',  plus_r))
        y += ROW_H + 4

    elif unit is not None:
        _label(surf, font, PAD, y, f'UNIT:    {unit.label}',     COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, PAD, y, f'STATION: {unit.station_label}', COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, PAD, y, f'TYPE:    {unit.unit_type}', COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, PAD, y, f'RATED:   {unit.rated_mw:.0f} MW', COL_TEXT_VALUE)
        y += ROW_H
        _label(surf, font, PAD, y, f'MIN:     {unit.min_mw:.0f} MW',   COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, PAD, y, f'SHIFT FROM: {unit.active_from_shift}',
               COL_TEXT_SECONDARY)
        minus_r = pygame.Rect(150, y - 2, 22, ROW_H)
        plus_r  = pygame.Rect(176, y - 2, 22, ROW_H)
        pygame.draw.rect(surf, (30, 30, 30), minus_r)
        pygame.draw.rect(surf, COL_PANEL_BORDER, minus_r, 1)
        pygame.draw.rect(surf, (30, 30, 30), plus_r)
        pygame.draw.rect(surf, COL_PANEL_BORDER, plus_r, 1)
        _label(surf, font, minus_r.x + 5, minus_r.y + 2, '-', COL_TEXT_PRIMARY)
        _label(surf, font, plus_r.x  + 5, plus_r.y  + 2, '+', COL_TEXT_PRIMARY)
        _hit_rects.append(('prop_shift_minus', minus_r))
        _hit_rects.append(('prop_shift_plus',  plus_r))
        y += ROW_H + 4

    return y + PAD


def _draw_actions(surf, font, font_bold, designer, y0: int) -> int:
    y = y0
    _label(surf, font_bold, PAD, y, 'ACTIONS', COL_TEXT_HEADING)
    y += ROW_H + 4

    actions = [
        ('auto_route',    'AUTO-ROUTE LINES  (Ctrl+R)', COL_TEXT_HEADING),
        ('clear_lines',   'CLEAR ALL LINES',             COL_TEXT_WARN),
        ('export_preview','EXPORT PREVIEW',               COL_TEXT_SECONDARY),
        ('save',          'SAVE (Ctrl+S)',                COL_TEXT_GOOD),
        ('load',          'LOAD FROM FILE',               COL_TEXT_SECONDARY),
        ('test_grid',     'TEST SAVED GRID  (Ctrl+T)',    COL_SELECTION),
    ]
    for action, label, col in actions:
        rect = pygame.Rect(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
        pygame.draw.rect(surf, (0, 0, 0), rect)
        pygame.draw.rect(surf, col, rect, 1)
        _label(surf, font, PAD + 6, y + 4, label, col)
        _hit_rects.append((action, rect))
        y += BTN_H + 4

    # Name + save indicator
    name_str  = designer._grid_name if designer._grid_name else '(unnamed)'
    dirty_text = f'* {name_str}  UNSAVED' if designer._dirty else f'{name_str}'
    dirty_col  = COL_TEXT_WARN if designer._dirty else COL_TEXT_DIM
    _label(surf, font, PAD, y + 4, dirty_text, dirty_col)
    y += ROW_H + PAD
    return y


def _draw_save_dialog(surf, font, font_bold, designer) -> None:
    """Sidebar shows a name-input box for saving."""
    global _overlay_rects
    _overlay_rects = []

    y = PAD + 20
    _label(surf, font_bold, PAD, y, 'SAVE GRID', COL_TEXT_HEADING)
    y += ROW_H + 8

    _label(surf, font, PAD, y, 'Grid name:', COL_TEXT_SECONDARY)
    y += ROW_H + 4

    field_rect = pygame.Rect(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H + 4)
    pygame.draw.rect(surf, (0, 30, 0), field_rect)
    pygame.draw.rect(surf, COL_TEXT_GOOD, field_rect, 1)
    _label(surf, font, PAD + 6, y + 6, designer._save_dialog_buf + '_', COL_TEXT_GOOD)
    y += BTN_H + 12

    _label(surf, font, PAD, y, '(alphanumeric + underscore)', COL_TEXT_DIM)
    y += ROW_H + 12

    # Commit button
    commit_rect = pygame.Rect(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
    pygame.draw.rect(surf, (0, 0, 0), commit_rect)
    pygame.draw.rect(surf, COL_TEXT_GOOD, commit_rect, 1)
    _label(surf, font, PAD + 6, y + 4, 'SAVE  [Enter]', COL_TEXT_GOOD)
    _overlay_rects.append(('save_dialog_commit', commit_rect))
    y += BTN_H + 6

    cancel_rect = pygame.Rect(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
    pygame.draw.rect(surf, (0, 0, 0), cancel_rect)
    pygame.draw.rect(surf, COL_TEXT_SECONDARY, cancel_rect, 1)
    _label(surf, font, PAD + 6, y + 4, 'CANCEL  [Esc]', COL_TEXT_SECONDARY)
    _overlay_rects.append(('overlay_cancel', cancel_rect))


_BROWSER_ROWS = 20
_BROWSER_ROW_H = 22


def _draw_load_browser(surf, font, font_bold, designer, test_mode: bool = False) -> None:
    """Sidebar shows a scrollable list of saved grids for load or test."""
    global _overlay_rects
    _overlay_rects = []

    title = 'SELECT GRID — TEST' if test_mode else 'LOAD GRID'
    y = PAD + 20
    _label(surf, font_bold, PAD, y, title, COL_TEXT_HEADING)
    y += ROW_H + 8

    lst  = designer._load_browser_list
    if not lst:
        _label(surf, font, PAD, y, 'No saved grids found.', COL_TEXT_DIM)
        y += ROW_H + 8
        cancel_rect = pygame.Rect(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
        pygame.draw.rect(surf, (0, 0, 0), cancel_rect)
        pygame.draw.rect(surf, COL_TEXT_SECONDARY, cancel_rect, 1)
        _label(surf, font, PAD + 6, y + 4, 'CANCEL  [Esc]', COL_TEXT_SECONDARY)
        _overlay_rects.append(('overlay_cancel', cancel_rect))
        return

    idx    = designer._load_browser_idx
    scroll = designer._load_browser_scroll

    # Clamp scroll so selected is visible
    if idx < scroll:
        designer._load_browser_scroll = idx
        scroll = idx
    elif idx >= scroll + _BROWSER_ROWS:
        designer._load_browser_scroll = idx - _BROWSER_ROWS + 1
        scroll = designer._load_browser_scroll

    visible = lst[scroll: scroll + _BROWSER_ROWS]
    for i, name in enumerate(visible):
        real_idx = scroll + i
        is_sel   = (real_idx == idx)
        row_col  = COL_SELECTION if is_sel else COL_TEXT_SECONDARY
        bg_col   = (0, 40, 0) if is_sel else (0, 0, 0)
        row_rect = pygame.Rect(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, _BROWSER_ROW_H - 2)
        pygame.draw.rect(surf, bg_col, row_rect)
        if is_sel:
            pygame.draw.rect(surf, row_col, row_rect, 1)
        _label(surf, font, PAD + 6, y + 4, name, row_col)
        action = f'browser_select:{name}'
        _overlay_rects.append((action, row_rect))
        y += _BROWSER_ROW_H

    y += 8
    # Scroll hint
    if len(lst) > _BROWSER_ROWS:
        _label(surf, font, PAD, y,
               f'{scroll+1}-{min(scroll+_BROWSER_ROWS, len(lst))} of {len(lst)}',
               COL_TEXT_DIM)
        y += ROW_H

    y += 4
    action_lbl = 'TEST  [Enter]' if test_mode else 'LOAD  [Enter]'
    load_rect  = pygame.Rect(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
    pygame.draw.rect(surf, (0, 0, 0), load_rect)
    pygame.draw.rect(surf, COL_SELECTION, load_rect, 1)
    _label(surf, font, PAD + 6, y + 4, action_lbl, COL_SELECTION)
    if lst:
        _overlay_rects.append((f'browser_select:{lst[idx]}', load_rect))
    y += BTN_H + 6

    cancel_rect = pygame.Rect(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
    pygame.draw.rect(surf, (0, 0, 0), cancel_rect)
    pygame.draw.rect(surf, COL_TEXT_SECONDARY, cancel_rect, 1)
    _label(surf, font, PAD + 6, y + 4, 'CANCEL  [Esc]', COL_TEXT_SECONDARY)
    _overlay_rects.append(('overlay_cancel', cancel_rect))


def _draw_footer(surf, font, designer, y0: int) -> None:
    _label(surf, font, PAD, y0,
           'ESC: deselect/exit  DEL: delete  E: edit label  R: rotate anchor',
           COL_TEXT_DIM)


# ─────────────────────────────────────────────────────────────────────────────
# DRAWING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _label(surf, font, x, y, text, colour):
    font.render_to(surf, (x, y), text, colour)


def _hsep(surf, y: int) -> None:
    pygame.draw.line(surf, COL_DESIGNER_SIDEBAR_SEP, (0, y), (DESIGNER_SIDEBAR_W, y), 1)
