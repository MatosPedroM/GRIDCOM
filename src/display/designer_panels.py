"""
src/display/designer_panels.py

Sidebar drawing for the Grid Designer mode.

The sidebar is DESIGNER_SIDEBAR_W (208px) wide and occupies the left edge
of the 1920×1080 native surface (from x=0 to x=208, full height 1080px).
The canvas fills the remaining width to the right of the sidebar.

Layout (top → bottom, approximate — palette is single-column so its exact
height depends on button count):
  Power balance summary
  Separator
  Palette — Bus types + Unit types + Delete/Line (single column)
  Separator
  Properties panel (selected element)
  Actions panel
  Footer hint

All drawing is done to a subsurface passed by GridDesigner.draw().
"""

from __future__ import annotations

import pygame
import pygame.freetype

from display.palette import (
    COL_BACKGROUND, COL_TEXT_PRIMARY, COL_TEXT_SECONDARY, COL_TEXT_DIM,
    COL_TEXT_VALUE, COL_TEXT_HEADING, COL_TEXT_WARN, COL_TEXT_CRIT,
    COL_TEXT_GOOD, COL_PANEL_BORDER,
    COL_400KV, COL_220KV, COL_150KV,
    COL_UNIT_COAL, COL_UNIT_CCGT, COL_UNIT_NUCLEAR,
    COL_UNIT_HYDRO, COL_UNIT_WIND, COL_UNIT_SOLAR, COL_UNIT_HYDRO_PUMP,
    COL_DESIGNER_SIDEBAR_BG, COL_DESIGNER_SIDEBAR_SEP,
    COL_DESIGNER_PALETTE_SEL, COL_DESIGNER_PALETTE_BTN,
    COL_DESIGNER_SURPLUS_POS, COL_DESIGNER_SURPLUS_NEG,
    COL_DESIGNER_FIELD_ACTIVE, COL_DESIGNER_DELETE_CURSOR,
    COL_SELECTION,
)
from simulation.constants import DESIGNER_SIDEBAR_W, NATIVE_HEIGHT, DESIGNER_FONT_SIZE


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT CONSTANTS (relative to sidebar left=0, top=0)
# ─────────────────────────────────────────────────────────────────────────────

PAD = 8
ROW_H = 18
BTN_H = 22
BTN_W = DESIGNER_SIDEBAR_W - 2 * PAD   # single-column button width

SECTION_BALANCE_Y  = 0
SECTION_PALETTE_Y  = 64
SECTION_PROPS_Y    = 320
SECTION_ACTIONS_Y  = 680
SECTION_FOOTER_Y   = NATIVE_HEIGHT - 30


# ─────────────────────────────────────────────────────────────────────────────
# BUTTON REGISTRY
# hit_rects holds (action_string, pygame.Rect) per frame; rebuilt each draw.
# _overlay_rects same for save/load overlay. Rects are stored in LOGICAL
# (unscaled) sidebar-local pixels — same space as PAD/ROW_H/BTN_H/etc — so
# callers must pass logical (sx, sy), matching the original contract.
# _r() converts a logical rect to actual surf pixels only at draw time.
# ─────────────────────────────────────────────────────────────────────────────

_hit_rects:     list[tuple[str, pygame.Rect]] = []
_overlay_rects: list[tuple[str, pygame.Rect]] = []
_scale: float = 1.0


def sidebar_button_at(sx: int, sy: int, designer) -> str | None:
    """Return the action string for a click at (sx, sy) in logical sidebar space."""
    for action, rect in _hit_rects:
        if rect.collidepoint(sx, sy):
            return action
    return None


def sidebar_overlay_click_at(sx: int, sy: int, designer) -> str | None:
    """Return the action string for a click inside the save/load overlay (logical space)."""
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
    scale: float = 1.0,
) -> None:
    """Draw the complete sidebar. surf is the scaled sidebar-width × full-height subsurface."""
    global _hit_rects, _overlay_rects, _scale
    _hit_rects    = []
    _overlay_rects = []
    _scale = scale

    surf.fill(COL_DESIGNER_SIDEBAR_BG)

    mode = designer._sidebar_mode

    if mode == 'save_dialog':
        _draw_save_dialog(surf, font, font_bold, designer)
        return

    if mode in ('load_browser', 'test_browser'):
        _draw_load_browser(surf, font, font_bold, designer, test_mode=(mode == 'test_browser'))
        return

    if mode == 'analysis':
        y = _draw_analysis_panel(surf, font, font_bold, designer, SECTION_BALANCE_Y)
        _hsep(surf, y)
        y = _draw_properties(surf, font, font_bold, designer, y + 4)
        _draw_footer(surf, font, designer, SECTION_FOOTER_Y)
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

    # Bus buttons — single column (sidebar too narrow for a 2-column grid)
    _label(surf, font, PAD, y, 'BUS', COL_TEXT_SECONDARY)
    y += ROW_H

    bus_voltages = [
        ('400 kV', 400.0, COL_400KV),
        ('220 kV', 220.0, COL_220KV),
        ('150 kV', 150.0, COL_150KV),
    ]

    for lbl, vkv, col in bus_voltages:
        action = f'bus_{vkv:.0f}'
        active = (designer._palette_mode == MODE_BUS and
                  not designer._palette_load_toggle and
                  designer._palette_voltage == vkv)
        btn_col = col if active else COL_DESIGNER_PALETTE_BTN
        rect = _r(PAD, y, BTN_W, BTN_H)
        _draw_rect(surf, (0, 0, 0), rect)
        _draw_rect(surf, btn_col, rect, 1)
        _label(surf, font, PAD + 4, y + 4, lbl, btn_col)
        _hit_rects.append((action, rect))
        y += BTN_H + 3

    # LOAD toggle — always places at the standard 150kV load-substation tier
    load_active = (designer._palette_mode == MODE_BUS and
                   designer._palette_load_toggle)
    load_col = COL_150KV if load_active else COL_DESIGNER_PALETTE_BTN
    load_rect = _r(PAD, y, BTN_W, BTN_H)
    _draw_rect(surf, (0, 0, 0), load_rect)
    _draw_rect(surf, load_col, load_rect, 1)
    _label(surf, font, PAD + 4, y + 4, 'LOAD (150kV)', load_col)
    _hit_rects.append(('bus_load_toggle', load_rect))
    y += BTN_H + 3

    y += 3

    # Unit buttons — single column
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
    for utype, col in unit_types:
        action = f'unit_{utype}'
        active = (designer._palette_mode == MODE_UNIT and
                  designer._palette_unit_type == utype)
        btn_col = col if active else COL_DESIGNER_PALETTE_BTN
        rect = _r(PAD, y, BTN_W, BTN_H)
        _draw_rect(surf, (0, 0, 0), rect)
        _draw_rect(surf, btn_col, rect, 1)
        _label(surf, font, PAD + 4, y + 4, utype, btn_col)
        _hit_rects.append((action, rect))
        y += BTN_H + 3

    y += 3

    # Delete + LINE buttons — short labels, stay side-by-side at half width
    del_active  = designer._palette_mode == MODE_DELETE
    line_active = designer._palette_mode == MODE_LINE
    del_col  = COL_DESIGNER_DELETE_CURSOR if del_active  else COL_DESIGNER_PALETTE_BTN
    line_col = COL_SELECTION              if line_active else COL_DESIGNER_PALETTE_BTN

    half_w = (BTN_W - 4) // 2
    del_rect  = _r(PAD, y, half_w, BTN_H)
    line_rect = _r(PAD + half_w + 4, y, half_w, BTN_H)
    for rect, col, lbl, act in (
        (del_rect,  del_col,  'DEL (D)',  'delete'),
        (line_rect, line_col, 'LINE (L)', 'line_mode'),
    ):
        _draw_rect(surf, (0, 0, 0), rect)
        _draw_rect(surf, col, rect, 1)
        _label(surf, font, rect.x + 4, y + 4, lbl, col)
        _hit_rects.append((act, rect))

    y += BTN_H + PAD
    return y


def _draw_properties(surf, font, font_bold, designer, y0: int) -> int:
    y = y0
    _label(surf, font_bold, PAD, y, 'PROPERTIES', COL_TEXT_HEADING)
    y += ROW_H + 4

    bus  = designer._selected_bus
    line = designer._selected_line
    unit = designer._selected_unit

    group_n = (len(designer._selected_buses) + len(designer._selected_lines) +
               len(designer._selected_stations))
    if bus is None and line is None and unit is None:
        if group_n:
            _label(surf, font, PAD, y, f'{group_n} elements selected', COL_TEXT_VALUE)
            y += ROW_H
            _label(surf, font, PAD, y, 'Drag to move, Del to remove', COL_TEXT_DIM)
            y += ROW_H
        else:
            _label(surf, font, PAD, y, 'No element selected', COL_TEXT_DIM)
            y += ROW_H
        return y + PAD

    if bus is not None:
        # Editable label field
        editing_label = (designer._editing_field == 'label')
        lbl_disp = designer._edit_buffer if editing_label else bus.label
        field_col = COL_DESIGNER_FIELD_ACTIVE if editing_label else COL_PANEL_BORDER
        _label(surf, font, PAD, y, 'LABEL:', COL_TEXT_SECONDARY)
        field_rect = _r(80, y - 2, 100, ROW_H + 2)
        _draw_rect(surf, (0, 0, 0), field_rect)
        _draw_rect(surf, field_col, field_rect, 1)
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
            editing_pk = (designer._editing_field == 'peak_load_mw')
            pk_disp = designer._edit_buffer if editing_pk else f'{bus.peak_load_mw:.0f}'
            field_col = COL_DESIGNER_FIELD_ACTIVE if editing_pk else COL_PANEL_BORDER
            _label(surf, font, PAD, y, 'PK LOAD:', COL_TEXT_SECONDARY)
            pk_rect = _r(80, y - 2, 90, ROW_H + 2)
            _draw_rect(surf, (0, 0, 0), pk_rect)
            _draw_rect(surf, field_col, pk_rect, 1)
            _label(surf, font, 84, y,
                   (pk_disp + '_') if editing_pk else (pk_disp + ' MW'), COL_TEXT_VALUE)
            if not editing_pk:
                _hit_rects.append(('edit_peak_load_mw', pk_rect))
            y += ROW_H + 2

            if designer._sidebar_mode == 'analysis':
                editing_al = (designer._editing_field == 'analysis_bus_load_mw')
                al_mw = designer._analysis_bus_load_mw.get(bus.label, bus.peak_load_mw)
                al_disp = designer._edit_buffer if editing_al else f'{al_mw:.0f}'
                field_col = COL_DESIGNER_FIELD_ACTIVE if editing_al else COL_PANEL_BORDER
                _label(surf, font, PAD, y, 'ANALYSIS LOAD:', COL_TEXT_SECONDARY)
                y += ROW_H
                al_rect = _r(PAD, y - 2, 90, ROW_H + 2)
                _draw_rect(surf, (0, 0, 0), al_rect)
                _draw_rect(surf, field_col, al_rect, 1)
                _label(surf, font, PAD + 4, y,
                       (al_disp + '_') if editing_al else (al_disp + ' MW'), COL_TEXT_VALUE)
                if not editing_al:
                    _hit_rects.append(('edit_analysis_bus_load_mw', al_rect))
                y += ROW_H + 2

        # Shift
        y += 4
        _label(surf, font, PAD, y, f'SHIFT FROM: {bus.active_from_shift}', COL_TEXT_SECONDARY)
        # +/- buttons
        minus_r = _r(150, y - 2, 22, ROW_H)
        plus_r  = _r(176, y - 2, 22, ROW_H)
        _draw_rect(surf, (30, 30, 30), minus_r)
        _draw_rect(surf, COL_PANEL_BORDER, minus_r, 1)
        _draw_rect(surf, (30, 30, 30), plus_r)
        _draw_rect(surf, COL_PANEL_BORDER, plus_r, 1)
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
        slack_rect = _r(PAD, y, 120, ROW_H + 2)
        _draw_rect(surf, (0, 0, 0), slack_rect)
        _draw_rect(surf, slack_col, slack_rect, 1)
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

        # Editable length (km) — the primary electrical-span field; reactance_pu
        # is derived from it and shown read-only just below.
        editing_len = (designer._editing_field == 'length_km')
        len_val = line.length_km if line.length_km is not None else 0.0
        len_disp = designer._edit_buffer if editing_len else f'{len_val:.1f}'
        field_col = COL_DESIGNER_FIELD_ACTIVE if editing_len else COL_PANEL_BORDER
        _label(surf, font, PAD, y, 'LENGTH KM:', COL_TEXT_SECONDARY)
        lf_rect = _r(100, y - 2, 70, ROW_H + 2)
        _draw_rect(surf, (0, 0, 0), lf_rect)
        _draw_rect(surf, field_col, lf_rect, 1)
        _label(surf, font, 104, y,
               (len_disp + '_') if editing_len else len_disp, COL_TEXT_VALUE)
        if not editing_len:
            # Click → edit
            _hit_rects.append(('edit_length_km', lf_rect))
        y += ROW_H + 2

        # Read-only derived reactance
        _label(surf, font, PAD, y, f'X PU:    {line.reactance_pu:.4f}',
               COL_TEXT_DIM)
        y += ROW_H

        _label(surf, font, PAD, y, f'RATING:  {line.rating_mw:.0f} MW',
               COL_TEXT_SECONDARY)
        y += ROW_H

        # Shift
        _label(surf, font, PAD, y, f'SHIFT FROM: {line.active_from_shift}',
               COL_TEXT_SECONDARY)
        minus_r = _r(150, y - 2, 22, ROW_H)
        plus_r  = _r(176, y - 2, 22, ROW_H)
        _draw_rect(surf, (30, 30, 30), minus_r)
        _draw_rect(surf, COL_PANEL_BORDER, minus_r, 1)
        _draw_rect(surf, (30, 30, 30), plus_r)
        _draw_rect(surf, COL_PANEL_BORDER, plus_r, 1)
        _label(surf, font, minus_r.x + 5, minus_r.y + 2, '-', COL_TEXT_PRIMARY)
        _label(surf, font, plus_r.x  + 5, plus_r.y  + 2, '+', COL_TEXT_PRIMARY)
        _hit_rects.append(('prop_shift_minus', minus_r))
        _hit_rects.append(('prop_shift_plus',  plus_r))
        y += ROW_H + 4

        if designer._sidebar_mode == 'analysis':
            in_svc = designer._analysis_line_in_service.get(line.label, True)
            svc_col = COL_TEXT_GOOD if in_svc else COL_TEXT_CRIT
            svc_rect = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, ROW_H + 2)
            _draw_rect(surf, (0, 0, 0), svc_rect)
            _draw_rect(surf, svc_col, svc_rect, 1)
            _label(surf, font, PAD + 4, y + 2,
                   'IN SERVICE' if in_svc else 'OUT OF SERVICE', svc_col)
            _hit_rects.append(('analysis_line_toggle_service', svc_rect))
            y += ROW_H + 4

    elif unit is not None:
        _label(surf, font, PAD, y, f'UNIT:    {unit.label}',     COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, PAD, y,
               f'STATION: {unit.station_name or unit.station_label}', COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, PAD, y, f'TYPE:    {unit.unit_type}', COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, PAD, y, f'RATED:   {unit.rated_mw:.0f} MW', COL_TEXT_VALUE)
        y += ROW_H
        _label(surf, font, PAD, y, f'MIN:     {unit.min_mw:.0f} MW',   COL_TEXT_SECONDARY)
        y += ROW_H

        sibs = designer._units_at_station(unit.station_label)
        if len(sibs) > 1:
            idx = sibs.index(unit)
            _label(surf, font, PAD, y, f'UNIT {idx + 1}/{len(sibs)}', COL_TEXT_SECONDARY)
            prev_r = _r(150, y - 2, 22, ROW_H)
            next_r = _r(176, y - 2, 22, ROW_H)
            _draw_rect(surf, (30, 30, 30), prev_r)
            _draw_rect(surf, COL_PANEL_BORDER, prev_r, 1)
            _draw_rect(surf, (30, 30, 30), next_r)
            _draw_rect(surf, COL_PANEL_BORDER, next_r, 1)
            _label(surf, font, prev_r.x + 6, prev_r.y + 2, '<', COL_TEXT_PRIMARY)
            _label(surf, font, next_r.x + 6, next_r.y + 2, '>', COL_TEXT_PRIMARY)
            _hit_rects.append(('prop_unit_cycle_prev', prev_r))
            _hit_rects.append(('prop_unit_cycle_next', next_r))
            y += ROW_H + 2

        # Editable starting dispatch (test-session default)
        editing_sm = (designer._editing_field == 'start_mw')
        sm_disp = designer._edit_buffer if editing_sm else (
            f'{unit.start_mw:.0f}' if unit.start_mw >= 0 else '(auto: 50%)')
        field_col = COL_DESIGNER_FIELD_ACTIVE if editing_sm else COL_PANEL_BORDER
        _label(surf, font, PAD, y, 'START MW:', COL_TEXT_SECONDARY)
        y += ROW_H
        sm_rect = _r(PAD, y - 2, 100, ROW_H + 2)
        _draw_rect(surf, (0, 0, 0), sm_rect)
        _draw_rect(surf, field_col, sm_rect, 1)
        _label(surf, font, PAD + 4, y,
               (sm_disp + '_') if editing_sm else sm_disp, COL_TEXT_VALUE)
        if not editing_sm:
            _hit_rects.append(('edit_start_mw', sm_rect))
        y += ROW_H + 2

        # In-service toggle (test-session availability, persisted)
        insvc = unit.in_service
        insvc_col = COL_TEXT_GOOD if insvc else COL_TEXT_CRIT
        insvc_rect = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, ROW_H + 2)
        _draw_rect(surf, (0, 0, 0), insvc_rect)
        _draw_rect(surf, insvc_col, insvc_rect, 1)
        _label(surf, font, PAD + 4, y + 2,
               'IN SERVICE' if insvc else 'OUT OF SERVICE', insvc_col)
        _hit_rects.append(('prop_unit_in_service_toggle', insvc_rect))
        y += ROW_H + 4

        _label(surf, font, PAD, y, f'SHIFT FROM: {unit.active_from_shift}',
               COL_TEXT_SECONDARY)
        minus_r = _r(150, y - 2, 22, ROW_H)
        plus_r  = _r(176, y - 2, 22, ROW_H)
        _draw_rect(surf, (30, 30, 30), minus_r)
        _draw_rect(surf, COL_PANEL_BORDER, minus_r, 1)
        _draw_rect(surf, (30, 30, 30), plus_r)
        _draw_rect(surf, COL_PANEL_BORDER, plus_r, 1)
        _label(surf, font, minus_r.x + 5, minus_r.y + 2, '-', COL_TEXT_PRIMARY)
        _label(surf, font, plus_r.x  + 5, plus_r.y  + 2, '+', COL_TEXT_PRIMARY)
        _hit_rects.append(('prop_shift_minus', minus_r))
        _hit_rects.append(('prop_shift_plus',  plus_r))
        y += ROW_H + 4

        # Anchor
        _label(surf, font, PAD, y,
               f'ANCHOR:  {unit.label_anchor}  (R to rotate)', COL_TEXT_DIM)
        y += ROW_H

        if designer._sidebar_mode == 'analysis':
            editing_um = (designer._editing_field == 'analysis_unit_mw')
            um_mw = designer._analysis_unit_mw.get(unit.label, unit.rated_mw)
            um_disp = designer._edit_buffer if editing_um else f'{um_mw:.0f}'
            field_col = COL_DESIGNER_FIELD_ACTIVE if editing_um else COL_PANEL_BORDER
            _label(surf, font, PAD, y, 'DISPATCH MW:', COL_TEXT_SECONDARY)
            y += ROW_H
            um_rect = _r(PAD, y - 2, 90, ROW_H + 2)
            _draw_rect(surf, (0, 0, 0), um_rect)
            _draw_rect(surf, field_col, um_rect, 1)
            _label(surf, font, PAD + 4, y,
                   (um_disp + '_') if editing_um else (um_disp + ' MW'), COL_TEXT_VALUE)
            if not editing_um:
                _hit_rects.append(('edit_analysis_unit_mw', um_rect))
            y += ROW_H + 4

            avail = designer._analysis_unit_available.get(unit.label, True)
            avail_col = COL_TEXT_GOOD if avail else COL_TEXT_CRIT
            avail_rect = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, ROW_H + 2)
            _draw_rect(surf, (0, 0, 0), avail_rect)
            _draw_rect(surf, avail_col, avail_rect, 1)
            _label(surf, font, PAD + 4, y + 2,
                   'AVAILABLE' if avail else 'UNAVAILABLE', avail_col)
            _hit_rects.append(('analysis_unit_toggle_avail', avail_rect))
            y += ROW_H + 4

    return y + PAD


def _draw_actions(surf, font, font_bold, designer, y0: int) -> int:
    y = y0
    _label(surf, font_bold, PAD, y, 'ACTIONS', COL_TEXT_HEADING)
    y += ROW_H + 4

    actions = [
        ('auto_route',    'AUTO-ROUTE LINES  (Ctrl+R)', COL_TEXT_HEADING),
        ('clear_lines',   'CLEAR ALL LINES',             COL_TEXT_WARN),
        ('analysis',      'ANALYSIS  (Ctrl+A)',          COL_TEXT_SECONDARY),
        ('save',          'SAVE (Ctrl+S)',                COL_TEXT_GOOD),
        ('load',          'LOAD FROM FILE',               COL_TEXT_SECONDARY),
        ('test_grid',     'TEST SAVED GRID  (Ctrl+T)',    COL_SELECTION),
        ('import_shift10','IMPORT SHIFT 10',              COL_TEXT_SECONDARY),
    ]
    for action, label, col in actions:
        rect = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
        _draw_rect(surf, (0, 0, 0), rect)
        _draw_rect(surf, col, rect, 1)
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


def _draw_analysis_panel(surf, font, font_bold, designer, y0: int) -> int:
    """
    Static power-flow analysis: balance summary + N-1 headline, RUN/CANCEL
    buttons. Per-unit/per-bus/per-line editing happens via the properties
    panel (drawn separately, below this) when an element is selected on
    canvas — not listed here, since 40+ units won't fit a sidebar column.
    """
    from simulation.constants import DESIGNER_N1_OVERLOAD_PCT

    y = y0 + PAD
    _label(surf, font_bold, PAD, y, 'ANALYSIS MODE', COL_TEXT_HEADING)
    y += ROW_H + 6

    result = designer._analysis_result
    if result is None:
        _label(surf, font, PAD, y, 'Press RUN to solve.', COL_TEXT_DIM)
        y += ROW_H + 2
        _label(surf, font, PAD, y, 'Click a bus/line/unit', COL_TEXT_DIM)
        y += ROW_H
        _label(surf, font, PAD, y, 'to edit its inputs.', COL_TEXT_DIM)
        y += ROW_H + 8
    elif result.solver_error:
        _label(surf, font, PAD, y, 'SOLVE FAILED:', COL_TEXT_CRIT)
        y += ROW_H
        _label(surf, font, PAD, y, result.solver_error[:26], COL_TEXT_CRIT)
        y += ROW_H + 8
    else:
        _label(surf, font, PAD, y, f'DISPATCHED  {result.total_dispatched_mw:>8,.0f} MW',
               COL_TEXT_VALUE)
        y += ROW_H
        _label(surf, font, PAD, y, f'LOAD        {result.total_load_mw:>8,.0f} MW',
               COL_TEXT_SECONDARY)
        y += ROW_H
        slack = result.slack_vs_load_mw
        s_col = COL_DESIGNER_SURPLUS_POS if slack >= 0 else COL_DESIGNER_SURPLUS_NEG
        sign  = '+' if slack >= 0 else ''
        _label(surf, font, PAD, y, f'SLACK (D-L) {sign}{slack:>7,.0f} MW', s_col)
        y += ROW_H + 6

        _label(surf, font, PAD, y, f'INSTALLED   {result.total_available_mw:>8,.0f} MW',
               COL_TEXT_SECONDARY)
        y += ROW_H
        headroom = result.headroom_vs_installed_mw
        h_col = COL_DESIGNER_SURPLUS_POS if headroom >= 0 else COL_DESIGNER_SURPLUS_NEG
        _label(surf, font, PAD, y, f'HEADROOM    {headroom:>8,.0f} MW', h_col)
        y += ROW_H + 6

        n1_col = COL_TEXT_GOOD if result.n1_all_passed else COL_TEXT_CRIT
        pass_str = 'PASS' if result.n1_all_passed else 'FAIL'
        _label(surf, font, PAD, y, f'N-1 WORST {result.n1_worst_pct:>6.1f}%  [{pass_str}]',
               n1_col)
        y += ROW_H
        n_passed = sum(1 for r in result.n1_results if r.passed)
        _label(surf, font, PAD, y,
               f'{n_passed}/{len(result.n1_results)} contingencies pass '
               f'(<= {DESIGNER_N1_OVERLOAD_PCT:.0f}%)',
               COL_TEXT_DIM)
        y += ROW_H + 8

    # RUN button
    run_rect = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
    _draw_rect(surf, (0, 0, 0), run_rect)
    _draw_rect(surf, COL_TEXT_GOOD, run_rect, 1)
    _label(surf, font, PAD + 6, y + 4, 'RUN ANALYSIS  [Enter]', COL_TEXT_GOOD)
    _hit_rects.append(('analysis_run', run_rect))
    y += BTN_H + 4

    # CANCEL/close button
    close_rect = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
    _draw_rect(surf, (0, 0, 0), close_rect)
    _draw_rect(surf, COL_TEXT_SECONDARY, close_rect, 1)
    _label(surf, font, PAD + 6, y + 4, 'CLOSE  [Esc]', COL_TEXT_SECONDARY)
    _hit_rects.append(('analysis_close', close_rect))
    y += BTN_H + PAD

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

    field_rect = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H + 4)
    _draw_rect(surf, (0, 30, 0), field_rect)
    _draw_rect(surf, COL_TEXT_GOOD, field_rect, 1)
    _label(surf, font, PAD + 6, y + 6, designer._save_dialog_buf + '_', COL_TEXT_GOOD)
    y += BTN_H + 12

    _label(surf, font, PAD, y, '(alphanumeric + underscore)', COL_TEXT_DIM)
    y += ROW_H + 12

    # Commit button
    commit_rect = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
    _draw_rect(surf, (0, 0, 0), commit_rect)
    _draw_rect(surf, COL_TEXT_GOOD, commit_rect, 1)
    _label(surf, font, PAD + 6, y + 4, 'SAVE  [Enter]', COL_TEXT_GOOD)
    _overlay_rects.append(('save_dialog_commit', commit_rect))
    y += BTN_H + 6

    cancel_rect = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
    _draw_rect(surf, (0, 0, 0), cancel_rect)
    _draw_rect(surf, COL_TEXT_SECONDARY, cancel_rect, 1)
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
        cancel_rect = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
        _draw_rect(surf, (0, 0, 0), cancel_rect)
        _draw_rect(surf, COL_TEXT_SECONDARY, cancel_rect, 1)
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
        row_rect = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, _BROWSER_ROW_H - 2)
        _draw_rect(surf, bg_col, row_rect)
        if is_sel:
            _draw_rect(surf, row_col, row_rect, 1)
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
    load_rect  = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
    _draw_rect(surf, (0, 0, 0), load_rect)
    _draw_rect(surf, COL_SELECTION, load_rect, 1)
    _label(surf, font, PAD + 6, y + 4, action_lbl, COL_SELECTION)
    if lst:
        _overlay_rects.append((f'browser_select:{lst[idx]}', load_rect))
    y += BTN_H + 6

    cancel_rect = _r(PAD, y, DESIGNER_SIDEBAR_W - 2 * PAD, BTN_H)
    _draw_rect(surf, (0, 0, 0), cancel_rect)
    _draw_rect(surf, COL_TEXT_SECONDARY, cancel_rect, 1)
    _label(surf, font, PAD + 6, y + 4, 'CANCEL  [Esc]', COL_TEXT_SECONDARY)
    _overlay_rects.append(('overlay_cancel', cancel_rect))


def _draw_footer(surf, font, designer, y0: int) -> None:
    _label(surf, font, PAD, y0,
           'ESC: deselect/exit  DEL: delete  E: edit label  '
           'R: rotate anchor / line port (select endpoint bus first)  '
           'Ctrl+L: line colour view',
           COL_TEXT_DIM)


# ─────────────────────────────────────────────────────────────────────────────
# DRAWING HELPERS
#
# All layout constants and coordinates in this file (PAD, ROW_H, BTN_H,
# BTN_W, SECTION_*_Y, and every literal passed to _r()/_label() throughout,
# including arithmetic on a previously-built rect's .x/.y) are expressed in
# LOGICAL (unscaled) sidebar pixels — the same space hit-testing operates
# in. _r() returns a logical Rect (used both for hit-testing and as the
# input to _draw_rect); only _draw_rect()/_label()/_hsep() convert to the
# surf's actual scaled pixel space, at the point of drawing.
# ─────────────────────────────────────────────────────────────────────────────

def _r(x, y, w, h) -> pygame.Rect:
    """Build a logical (unscaled) sidebar Rect — used for hit-testing and layout."""
    return pygame.Rect(x, y, w, h)


def _draw_rect(surf, colour, rect: pygame.Rect, width: int = 0) -> None:
    """Draw a logical-space Rect, scaling it to surf's actual pixel space."""
    sc = _scale
    scaled = pygame.Rect(int(rect.x * sc), int(rect.y * sc),
                         int(rect.width * sc), int(rect.height * sc))
    pygame.draw.rect(surf, colour, scaled, width)


def _label(surf, font, x, y, text, colour):
    sc = _scale
    font.render_to(surf, (int(x * sc), int(y * sc)), text, colour,
                   size=int(DESIGNER_FONT_SIZE * sc))


def _hsep(surf, y: int) -> None:
    sc = _scale
    pygame.draw.line(surf, COL_DESIGNER_SIDEBAR_SEP,
                     (0, int(y * sc)), (int(DESIGNER_SIDEBAR_W * sc), int(y * sc)), 1)
