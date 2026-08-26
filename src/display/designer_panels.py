"""
src/display/designer_panels.py

Bottom strip + top panel + modal drawing for the Grid Designer mode.

The bottom strip is DESIGNER_STRIP_HEIGHT (192px) tall and spans the full
1920px width of the native surface, positioned directly below the canvas —
matching the in-game instrument strip's footprint exactly. It is split
into four fixed-width side-by-side columns, left to right:
  Balance | Palette | Properties | Actions
Each column is independent — content in one never affects another's
position (unlike the old single-column sidebar, where every section
pushed the next one down).

The top panel (DESIGNER_TITLE_BAR_HEIGHT + DESIGNER_TOPBAR_HEIGHT, 82px)
sits above the canvas: row 1 shows the grid name + dirty/unsaved
indicator, row 2 is reserved (framed only, no content yet).

Save/Load/Test-grid-browser and Analysis mode are drawn as a centered
modal dialog over the canvas (see modal_bounds_for / draw_modal_content)
rather than living in the bottom strip.

All drawing is done to subsurfaces passed by GridDesigner.draw().
"""

from __future__ import annotations

import pygame
import pygame.freetype

from config.palette import (
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
from config.constants import (
    NATIVE_WIDTH, DESIGNER_FONT_SIZE,
    DESIGNER_TITLE_BAR_HEIGHT, DESIGNER_TOPBAR_HEIGHT, DESIGNER_STRIP_HEIGHT,
    DESIGNER_PANEL_BALANCE_X, DESIGNER_PANEL_BALANCE_W,
    DESIGNER_PANEL_PALETTE_X, DESIGNER_PANEL_PALETTE_W,
    DESIGNER_PANEL_PROPERTIES_X, DESIGNER_PANEL_PROPERTIES_W,
    DESIGNER_PANEL_ACTIONS_X, DESIGNER_PANEL_ACTIONS_W,
    DESIGNER_PROPS_COL_W, DESIGNER_PROPS_COL_GAP,
    DESIGNER_MODAL_W, DESIGNER_MODAL_BROWSER_W,
    DESIGNER_MODAL_ROW_H, DESIGNER_MODAL_MAX_ROWS,
)


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT CONSTANTS
# PAD/ROW_H/BTN_H are shared micro-layout units used inside every column and
# modal. Column x-origins/widths and modal sizing come from constants.py.
# ─────────────────────────────────────────────────────────────────────────────

PAD = 8
ROW_H = 18
BTN_H = 22


# ─────────────────────────────────────────────────────────────────────────────
# BUTTON REGISTRY
# _hit_rects holds (action_string, pygame.Rect) per frame; rebuilt each
# draw_bottom_strip() call. _modal_rects same for the active modal, rebuilt
# each draw_modal_content() call. Rects are stored in LOGICAL (unscaled)
# native-space pixels (strip columns are native-x-relative; modal rects are
# modal-local) — callers must pass logical (sx, sy) in the matching space.
# _r() converts a logical rect to actual surf pixels only at draw time.
# ─────────────────────────────────────────────────────────────────────────────

_hit_rects:   list[tuple[str, pygame.Rect]] = []
_modal_rects: list[tuple[str, pygame.Rect]] = []
_scale: float = 1.0

# "Measuring" mode — see _properties_height(): runs _draw_properties with
# all actual surface/hit-rect writes suppressed, just tracking the lowest
# y-extent reached, so modal sizing can never drift out of sync with the
# real drawing code (a hand-maintained parallel height calculation would).
_measuring: bool = False
_measured_max_y: int = 0


def strip_button_at(sx: int, sy: int, designer) -> str | None:
    """Return the action string for a click at (sx, sy) in logical strip space."""
    for action, rect in _hit_rects:
        if rect.collidepoint(sx, sy):
            return action
    return None


def modal_click_at(sx: int, sy: int, designer) -> str | None:
    """Return the action string for a click inside the active modal (modal-local logical space)."""
    for action, rect in _modal_rects:
        if rect.collidepoint(sx, sy):
            return action
    return None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN DRAW ENTRIES
# ─────────────────────────────────────────────────────────────────────────────

def draw_bottom_strip(
    surf: pygame.Surface,
    designer,
    font: pygame.freetype.Font,
    font_bold: pygame.freetype.Font,
    scale: float = 1.0,
) -> None:
    """
    Draw the complete bottom strip. surf is the scaled full-width ×
    DESIGNER_STRIP_HEIGHT subsurface. Always draws the four normal columns,
    even while a modal (save/load/test/analysis) is open over the canvas
    above, so the screen doesn't look broken behind the modal. While in
    'analysis' mode, the Properties column shows a placeholder instead of
    live editable fields, since the analysis modal hosts its own live
    properties view for the selected element.
    """
    global _hit_rects, _scale
    _hit_rects = []
    _scale = scale

    surf.fill(COL_DESIGNER_SIDEBAR_BG)

    _draw_balance(surf, font, font_bold, designer,
                  DESIGNER_PANEL_BALANCE_X, DESIGNER_PANEL_BALANCE_W)
    _vsep(surf, DESIGNER_PANEL_PALETTE_X)
    _draw_palette(surf, font, font_bold, designer,
                  DESIGNER_PANEL_PALETTE_X, DESIGNER_PANEL_PALETTE_W)
    _vsep(surf, DESIGNER_PANEL_PROPERTIES_X)
    if designer._sidebar_mode == 'analysis':
        _draw_properties_placeholder(surf, font, font_bold,
                                     DESIGNER_PANEL_PROPERTIES_X, DESIGNER_PANEL_PROPERTIES_W)
    else:
        _draw_properties(surf, font, font_bold, designer,
                         DESIGNER_PANEL_PROPERTIES_X, DESIGNER_PANEL_PROPERTIES_W)
    _vsep(surf, DESIGNER_PANEL_ACTIONS_X)
    _draw_actions(surf, font, font_bold, designer,
                  DESIGNER_PANEL_ACTIONS_X, DESIGNER_PANEL_ACTIONS_W)


def draw_top_panel(
    surf: pygame.Surface,
    designer,
    font: pygame.freetype.Font,
    font_bold: pygame.freetype.Font,
    scale: float = 1.0,
) -> None:
    """Draw the top panel. surf is the scaled full-width × top-panel-height subsurface."""
    global _scale
    _scale = scale

    surf.fill(COL_DESIGNER_SIDEBAR_BG)

    # Row 1 — grid name + dirty/unsaved indicator, centered.
    name_str  = designer._grid_name if designer._grid_name else '(unnamed)'
    dirty_text = f'* {name_str}  UNSAVED' if designer._dirty else f'{name_str}'
    dirty_col  = COL_TEXT_WARN if designer._dirty else COL_TEXT_DIM
    text_w = len(dirty_text) * 7  # approximate monospace advance at DESIGNER_FONT_SIZE
    _label(surf, font_bold, (NATIVE_WIDTH - text_w) // 2, (DESIGNER_TITLE_BAR_HEIGHT - ROW_H) // 2,
           dirty_text, dirty_col)
    _hline(surf, DESIGNER_TITLE_BAR_HEIGHT)

    # Row 2 — reserved, framed only for now.
    _hline(surf, DESIGNER_TITLE_BAR_HEIGHT + DESIGNER_TOPBAR_HEIGHT - 1)


def draw_hint_bar(
    surf: pygame.Surface,
    designer,
    font: pygame.freetype.Font,
    scale: float = 1.0,
) -> None:
    """Draw the full-width keyboard-shortcut hint row."""
    global _scale
    _scale = scale
    surf.fill(COL_DESIGNER_SIDEBAR_BG)
    _label(surf, font, PAD, 2,
           'ESC: deselect/exit  DEL: delete  E: edit label  '
           'R: rotate anchor / line port (select endpoint bus first)  '
           'Ctrl+L: line colour view',
           COL_TEXT_PRIMARY)


# ─────────────────────────────────────────────────────────────────────────────
# SECTIONS
# Each section function is called with its column's (x0, w); x0=0 is the
# strip's own left edge (native-space, since the strip spans full width).
# ─────────────────────────────────────────────────────────────────────────────

def _draw_balance(surf, font, font_bold, designer, x0: int, w: int) -> None:
    x = x0 + PAD
    y = PAD
    _label(surf, font_bold, x, y, 'POWER BALANCE', COL_TEXT_HEADING)
    y += ROW_H + 2

    gen  = designer.gen_capacity_mw()
    load = designer.peak_load_mw()
    surplus = gen - load
    s_col   = COL_DESIGNER_SURPLUS_POS if surplus >= 0 else COL_DESIGNER_SURPLUS_NEG

    _label(surf, font, x, y,    f'GEN CAPACITY   {gen:>8,.0f} MW', COL_TEXT_VALUE)
    y += ROW_H
    _label(surf, font, x, y,    f'PEAK LOAD      {load:>8,.0f} MW', COL_TEXT_SECONDARY)
    y += ROW_H
    sign = '+' if surplus >= 0 else ''
    _label(surf, font, x, y,    f'SURPLUS        {sign}{surplus:>7,.0f} MW', s_col)


def _draw_palette(surf, font, font_bold, designer, x0: int, w: int) -> None:
    from display.designer import (
        MODE_SELECT, MODE_BUS, MODE_UNIT, MODE_LINE, MODE_DELETE,
    )

    _label(surf, font_bold, x0 + PAD, PAD, 'PALETTE', COL_TEXT_HEADING)

    # Two side-by-side sub-columns — BUS (+ LOAD + DEL/LINE) on the left,
    # UNIT types on the right — since the strip's fixed 192px height can't
    # fit a single stacked column of 4+8+1 buttons.
    col_w  = (w - 3 * PAD) // 2
    bus_x  = x0 + PAD
    unit_x = x0 + PAD + col_w + PAD

    # --- BUS sub-column -----------------------------------------------
    y = PAD + ROW_H + 2
    _label(surf, font, bus_x, y, 'BUS', COL_TEXT_SECONDARY)
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
        rect = _r(bus_x, y, col_w, BTN_H)
        _draw_rect(surf, (0, 0, 0), rect)
        _draw_rect(surf, btn_col, rect, 1)
        _label(surf, font, bus_x + 4, y + 4, lbl, btn_col)
        _hit_rects.append((action, rect))
        y += BTN_H + 2

    # LOAD toggle — always places at the standard 150kV load-substation tier
    load_active = (designer._palette_mode == MODE_BUS and
                   designer._palette_load_toggle)
    load_col = COL_150KV if load_active else COL_DESIGNER_PALETTE_BTN
    load_rect = _r(bus_x, y, col_w, BTN_H)
    _draw_rect(surf, (0, 0, 0), load_rect)
    _draw_rect(surf, load_col, load_rect, 1)
    _label(surf, font, bus_x + 4, y + 4, 'LOAD (150kV)', load_col)
    _hit_rects.append(('bus_load_toggle', load_rect))
    y += BTN_H + 4

    # Delete + LINE buttons — short labels, stay side-by-side at half width
    del_active  = designer._palette_mode == MODE_DELETE
    line_active = designer._palette_mode == MODE_LINE
    del_col  = COL_DESIGNER_DELETE_CURSOR if del_active  else COL_DESIGNER_PALETTE_BTN
    line_col = COL_SELECTION              if line_active else COL_DESIGNER_PALETTE_BTN

    half_w = (col_w - 4) // 2
    del_rect  = _r(bus_x, y, half_w, BTN_H)
    line_rect = _r(bus_x + half_w + 4, y, half_w, BTN_H)
    for rect, col, lbl, act in (
        (del_rect,  del_col,  'DEL (D)',  'delete'),
        (line_rect, line_col, 'LINE (L)', 'line_mode'),
    ):
        _draw_rect(surf, (0, 0, 0), rect)
        _draw_rect(surf, col, rect, 1)
        _label(surf, font, rect.x + 4, y + 4, lbl, col)
        _hit_rects.append((act, rect))

    # --- UNIT sub-column ---------------------------------------------------
    # 8 unit types don't fit a single stack at BTN_H in 192px, so this
    # sub-column itself splits into 2 button columns (4 rows each).
    y = PAD + ROW_H + 2
    _label(surf, font, unit_x, y, 'UNIT', COL_TEXT_SECONDARY)
    y += ROW_H
    unit_y0 = y

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
    u_half_w = (col_w - 4) // 2
    for i, (utype, col) in enumerate(unit_types):
        action = f'unit_{utype}'
        active = (designer._palette_mode == MODE_UNIT and
                  designer._palette_unit_type == utype)
        btn_col = col if active else COL_DESIGNER_PALETTE_BTN
        sub_col, row = divmod(i, 4)
        bx = unit_x + sub_col * (u_half_w + 4)
        by = unit_y0 + row * (BTN_H + 2)
        rect = _r(bx, by, u_half_w, BTN_H)
        _draw_rect(surf, (0, 0, 0), rect)
        _draw_rect(surf, btn_col, rect, 1)
        _label(surf, font, bx + 3, by + 4, utype[:9], btn_col)
        _hit_rects.append((action, rect))


def _props_col_w(w: int) -> int:
    """Field-column width that fits 3 columns in region width w, capped at
    the preferred DESIGNER_PROPS_COL_W (the strip's 900px Properties region
    fits it exactly; the narrower analysis modal shrinks it to fit)."""
    fitted = (w - 2 * PAD - 2 * DESIGNER_PROPS_COL_GAP) // 3
    return min(DESIGNER_PROPS_COL_W, max(120, fitted))


def _props_col_x(x0: int, i: int, col_w: int) -> int:
    """x-origin of the i-th (0-based) field column within a Properties region."""
    return x0 + PAD + i * (col_w + DESIGNER_PROPS_COL_GAP)


def _draw_properties_placeholder(surf, font, font_bold, x0: int, w: int) -> None:
    """Shown in the strip's Properties column while the analysis modal is
    open — the modal hosts the live editable properties view instead, so
    this avoids two simultaneous editable hit-rect sets for the same field."""
    _label(surf, font_bold, x0 + PAD, PAD, 'PROPERTIES', COL_TEXT_HEADING)
    _label(surf, font, x0 + PAD, PAD + ROW_H + 4, 'Editing in Analysis dialog', COL_TEXT_DIM)


def _draw_properties(surf, font, font_bold, designer, x0: int, w: int, y_offset: int = 0) -> None:
    _label(surf, font_bold, x0 + PAD, y_offset + PAD, 'PROPERTIES', COL_TEXT_HEADING)
    y0 = y_offset + PAD + ROW_H + 4
    col_w = _props_col_w(w)

    bus  = designer._selected_bus
    line = designer._selected_line
    unit = designer._selected_unit

    group_n = (len(designer._selected_buses) + len(designer._selected_lines) +
               len(designer._selected_stations))
    if bus is None and line is None and unit is None:
        x = _props_col_x(x0, 0, col_w)
        y = y0
        if group_n:
            _label(surf, font, x, y, f'{group_n} elements selected', COL_TEXT_VALUE)
            y += ROW_H
            _label(surf, font, x, y, 'Drag to move, Del to remove', COL_TEXT_DIM)
        else:
            _label(surf, font, x, y, 'No element selected', COL_TEXT_DIM)
        return

    if bus is not None:
        # --- Column 1: identity ---------------------------------------
        x = _props_col_x(x0, 0, col_w)
        y = y0
        editing_label = (designer._editing_field == 'label')
        lbl_disp = designer._edit_buffer if editing_label else bus.label
        field_col = COL_DESIGNER_FIELD_ACTIVE if editing_label else COL_PANEL_BORDER
        _label(surf, font, x, y, 'LABEL:', COL_TEXT_SECONDARY)
        field_rect = _r(x + 72, y - 2, 100, ROW_H + 2)
        _draw_rect(surf, (0, 0, 0), field_rect)
        _draw_rect(surf, field_col, field_rect, 1)
        _label(surf, font, x + 76, y,
               (lbl_disp + '_') if editing_label else lbl_disp,
               COL_TEXT_VALUE)
        y += ROW_H + 2
        _label(surf, font, x, y, f'NAME:    {bus.name}',     COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, x, y, f'VOLTAGE: {bus.voltage_kv:.0f} kV', COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, x, y, f'TYPE:    {bus.bus_type}', COL_TEXT_SECONDARY)

        # --- Column 2: load-specific (LOAD buses only) -------------------
        x = _props_col_x(x0, 1, col_w)
        y = y0
        if bus.bus_type == 'LOAD':
            editing_pk = (designer._editing_field == 'peak_load_mw')
            pk_disp = designer._edit_buffer if editing_pk else f'{bus.peak_load_mw:.0f}'
            field_col = COL_DESIGNER_FIELD_ACTIVE if editing_pk else COL_PANEL_BORDER
            _label(surf, font, x, y, 'PK LOAD:', COL_TEXT_SECONDARY)
            pk_rect = _r(x + 72, y - 2, 90, ROW_H + 2)
            _draw_rect(surf, (0, 0, 0), pk_rect)
            _draw_rect(surf, field_col, pk_rect, 1)
            _label(surf, font, x + 76, y,
                   (pk_disp + '_') if editing_pk else (pk_disp + ' MW'), COL_TEXT_VALUE)
            if not editing_pk:
                _hit_rects.append(('edit_peak_load_mw', pk_rect))
            y += ROW_H + 4

            # Substation type — click-to-cycle MIXED -> INDUSTRIAL -> RESIDENTIAL
            type_rect = _r(x, y, col_w, ROW_H + 2)
            _draw_rect(surf, (0, 0, 0), type_rect)
            _draw_rect(surf, COL_PANEL_BORDER, type_rect, 1)
            _label(surf, font, x + 4, y + 2,
                   f'TYPE: {bus.substation_type}', COL_TEXT_VALUE)
            _hit_rects.append(('prop_substation_type_toggle', type_rect))
            y += ROW_H + 6

            if designer._sidebar_mode == 'analysis':
                editing_al = (designer._editing_field == 'analysis_bus_load_mw')
                al_mw = designer._analysis_bus_load_mw.get(bus.label, bus.peak_load_mw)
                al_disp = designer._edit_buffer if editing_al else f'{al_mw:.0f}'
                field_col = COL_DESIGNER_FIELD_ACTIVE if editing_al else COL_PANEL_BORDER
                _label(surf, font, x, y, 'ANALYSIS LOAD:', COL_TEXT_SECONDARY)
                y += ROW_H
                al_rect = _r(x, y - 2, 90, ROW_H + 2)
                _draw_rect(surf, (0, 0, 0), al_rect)
                _draw_rect(surf, field_col, al_rect, 1)
                _label(surf, font, x + 4, y,
                       (al_disp + '_') if editing_al else (al_disp + ' MW'), COL_TEXT_VALUE)
                if not editing_al:
                    _hit_rects.append(('edit_analysis_bus_load_mw', al_rect))

        # --- Column 3: behaviour -----------------------------------------
        x = _props_col_x(x0, 2, col_w)
        y = y0
        _label(surf, font, x, y, f'SHIFT FROM: {bus.active_from_shift}', COL_TEXT_SECONDARY)
        minus_r = _r(x + 150, y - 2, 22, ROW_H)
        plus_r  = _r(x + 176, y - 2, 22, ROW_H)
        _draw_rect(surf, (30, 30, 30), minus_r)
        _draw_rect(surf, COL_PANEL_BORDER, minus_r, 1)
        _draw_rect(surf, (30, 30, 30), plus_r)
        _draw_rect(surf, COL_PANEL_BORDER, plus_r, 1)
        _label(surf, font, minus_r.x + 5, minus_r.y + 2, '-', COL_TEXT_PRIMARY)
        _label(surf, font, plus_r.x  + 5, plus_r.y  + 2, '+', COL_TEXT_PRIMARY)
        _hit_rects.append(('prop_shift_minus', minus_r))
        _hit_rects.append(('prop_shift_plus',  plus_r))
        y += ROW_H + 4

        _label(surf, font, x, y,
               f'ANCHOR:  {bus.label_anchor}  (R to rotate)', COL_TEXT_DIM)
        y += ROW_H + 2

        slack_col = COL_TEXT_GOOD if bus.is_slack else COL_TEXT_DIM
        slack_rect = _r(x, y, 140, ROW_H + 2)
        _draw_rect(surf, (0, 0, 0), slack_rect)
        _draw_rect(surf, slack_col, slack_rect, 1)
        _label(surf, font, x + 4, y + 2,
               'SLACK BUS' if bus.is_slack else 'Set as slack', slack_col)
        _hit_rects.append(('prop_slack_toggle', slack_rect))

    elif line is not None:
        # --- Column 1: identity + electrical ------------------------------
        x = _props_col_x(x0, 0, col_w)
        y = y0
        _label(surf, font, x, y, f'LINE:    {line.label}',          COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, x, y, f'ROUTE:   {line.from_bus}→{line.to_bus}',
               COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, x, y, f'VOLTAGE: {line.voltage_kv:.0f} kV',
               COL_TEXT_SECONDARY)
        y += ROW_H

        # Editable length (km) — the primary electrical-span field; reactance_pu
        # is derived from it and shown read-only just below.
        editing_len = (designer._editing_field == 'length_km')
        len_val = line.length_km if line.length_km is not None else 0.0
        len_disp = designer._edit_buffer if editing_len else f'{len_val:.1f}'
        field_col = COL_DESIGNER_FIELD_ACTIVE if editing_len else COL_PANEL_BORDER
        _label(surf, font, x, y, 'LENGTH KM:', COL_TEXT_SECONDARY)
        lf_rect = _r(x + 92, y - 2, 70, ROW_H + 2)
        _draw_rect(surf, (0, 0, 0), lf_rect)
        _draw_rect(surf, field_col, lf_rect, 1)
        _label(surf, font, x + 96, y,
               (len_disp + '_') if editing_len else len_disp, COL_TEXT_VALUE)
        if not editing_len:
            _hit_rects.append(('edit_length_km', lf_rect))
        y += ROW_H + 2

        _label(surf, font, x, y, f'X PU:    {line.reactance_pu:.4f}',
               COL_TEXT_DIM)
        y += ROW_H

        _label(surf, font, x, y, f'RATING:  {line.rating_mw:.0f} MW',
               COL_TEXT_SECONDARY)

        # --- Column 2: behaviour -------------------------------------------
        x = _props_col_x(x0, 1, col_w)
        y = y0
        _label(surf, font, x, y, f'SHIFT FROM: {line.active_from_shift}',
               COL_TEXT_SECONDARY)
        minus_r = _r(x + 150, y - 2, 22, ROW_H)
        plus_r  = _r(x + 176, y - 2, 22, ROW_H)
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
            svc_rect = _r(x, y, col_w, ROW_H + 2)
            _draw_rect(surf, (0, 0, 0), svc_rect)
            _draw_rect(surf, svc_col, svc_rect, 1)
            _label(surf, font, x + 4, y + 2,
                   'IN SERVICE' if in_svc else 'OUT OF SERVICE', svc_col)
            _hit_rects.append(('analysis_line_toggle_service', svc_rect))

    elif unit is not None:
        # --- Column 1: identity ---------------------------------------
        x = _props_col_x(x0, 0, col_w)
        y = y0
        _label(surf, font, x, y, f'UNIT:    {unit.label}',     COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, x, y,
               f'STATION: {unit.station_name or unit.station_label}', COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, x, y, f'TYPE:    {unit.unit_type}', COL_TEXT_SECONDARY)
        y += ROW_H
        _label(surf, font, x, y, f'RATED:   {unit.rated_mw:.0f} MW', COL_TEXT_VALUE)
        y += ROW_H
        _label(surf, font, x, y, f'MIN:     {unit.min_mw:.0f} MW',   COL_TEXT_SECONDARY)

        # --- Column 2: dispatch / session --------------------------------
        x = _props_col_x(x0, 1, col_w)
        y = y0
        sibs = designer._units_at_station(unit.station_label)
        if len(sibs) > 1:
            idx = sibs.index(unit)
            _label(surf, font, x, y, f'UNIT {idx + 1}/{len(sibs)}', COL_TEXT_SECONDARY)
            prev_r = _r(x + 150, y - 2, 22, ROW_H)
            next_r = _r(x + 176, y - 2, 22, ROW_H)
            _draw_rect(surf, (30, 30, 30), prev_r)
            _draw_rect(surf, COL_PANEL_BORDER, prev_r, 1)
            _draw_rect(surf, (30, 30, 30), next_r)
            _draw_rect(surf, COL_PANEL_BORDER, next_r, 1)
            _label(surf, font, prev_r.x + 6, prev_r.y + 2, '<', COL_TEXT_PRIMARY)
            _label(surf, font, next_r.x + 6, next_r.y + 2, '>', COL_TEXT_PRIMARY)
            _hit_rects.append(('prop_unit_cycle_prev', prev_r))
            _hit_rects.append(('prop_unit_cycle_next', next_r))
            y += ROW_H + 2

        editing_sm = (designer._editing_field == 'start_mw')
        sm_disp = designer._edit_buffer if editing_sm else (
            f'{unit.start_mw:.0f}' if unit.start_mw >= 0 else '(auto: 50%)')
        field_col = COL_DESIGNER_FIELD_ACTIVE if editing_sm else COL_PANEL_BORDER
        _label(surf, font, x, y, 'START MW:', COL_TEXT_SECONDARY)
        y += ROW_H
        sm_rect = _r(x, y - 2, 100, ROW_H + 2)
        _draw_rect(surf, (0, 0, 0), sm_rect)
        _draw_rect(surf, field_col, sm_rect, 1)
        _label(surf, font, x + 4, y,
               (sm_disp + '_') if editing_sm else sm_disp, COL_TEXT_VALUE)
        if not editing_sm:
            _hit_rects.append(('edit_start_mw', sm_rect))
        y += ROW_H + 4

        insvc = unit.in_service
        insvc_col = COL_TEXT_GOOD if insvc else COL_TEXT_CRIT
        insvc_rect = _r(x, y, col_w, ROW_H + 2)
        _draw_rect(surf, (0, 0, 0), insvc_rect)
        _draw_rect(surf, insvc_col, insvc_rect, 1)
        _label(surf, font, x + 4, y + 2,
               'IN SERVICE' if insvc else 'OUT OF SERVICE', insvc_col)
        _hit_rects.append(('prop_unit_in_service_toggle', insvc_rect))
        y += ROW_H + 6

        if designer._sidebar_mode == 'analysis':
            editing_um = (designer._editing_field == 'analysis_unit_mw')
            um_mw = designer._analysis_unit_mw.get(unit.label, unit.rated_mw)
            um_disp = designer._edit_buffer if editing_um else f'{um_mw:.0f}'
            field_col = COL_DESIGNER_FIELD_ACTIVE if editing_um else COL_PANEL_BORDER
            _label(surf, font, x, y, 'DISPATCH MW:', COL_TEXT_SECONDARY)
            y += ROW_H
            um_rect = _r(x, y - 2, 90, ROW_H + 2)
            _draw_rect(surf, (0, 0, 0), um_rect)
            _draw_rect(surf, field_col, um_rect, 1)
            _label(surf, font, x + 4, y,
                   (um_disp + '_') if editing_um else (um_disp + ' MW'), COL_TEXT_VALUE)
            if not editing_um:
                _hit_rects.append(('edit_analysis_unit_mw', um_rect))
            y += ROW_H + 4

            avail = designer._analysis_unit_available.get(unit.label, True)
            avail_col = COL_TEXT_GOOD if avail else COL_TEXT_CRIT
            avail_rect = _r(x, y, col_w, ROW_H + 2)
            _draw_rect(surf, (0, 0, 0), avail_rect)
            _draw_rect(surf, avail_col, avail_rect, 1)
            _label(surf, font, x + 4, y + 2,
                   'AVAILABLE' if avail else 'UNAVAILABLE', avail_col)
            _hit_rects.append(('analysis_unit_toggle_avail', avail_rect))

        # --- Column 3: behaviour -----------------------------------------
        x = _props_col_x(x0, 2, col_w)
        y = y0
        _label(surf, font, x, y, f'SHIFT FROM: {unit.active_from_shift}',
               COL_TEXT_SECONDARY)
        minus_r = _r(x + 150, y - 2, 22, ROW_H)
        plus_r  = _r(x + 176, y - 2, 22, ROW_H)
        _draw_rect(surf, (30, 30, 30), minus_r)
        _draw_rect(surf, COL_PANEL_BORDER, minus_r, 1)
        _draw_rect(surf, (30, 30, 30), plus_r)
        _draw_rect(surf, COL_PANEL_BORDER, plus_r, 1)
        _label(surf, font, minus_r.x + 5, minus_r.y + 2, '-', COL_TEXT_PRIMARY)
        _label(surf, font, plus_r.x  + 5, plus_r.y  + 2, '+', COL_TEXT_PRIMARY)
        _hit_rects.append(('prop_shift_minus', minus_r))
        _hit_rects.append(('prop_shift_plus',  plus_r))
        y += ROW_H + 4

        _label(surf, font, x, y,
               f'ANCHOR:  {unit.label_anchor}  (R to rotate)', COL_TEXT_DIM)


def _draw_actions(surf, font, font_bold, designer, x0: int, w: int) -> None:
    _label(surf, font_bold, x0 + PAD, PAD, 'ACTIONS', COL_TEXT_HEADING)
    y0 = PAD + ROW_H + 4

    actions = [
        ('auto_route',    'AUTO-ROUTE (Ctrl+R)', COL_TEXT_HEADING),
        ('clear_lines',   'CLEAR LINES',          COL_TEXT_WARN),
        ('analysis',      'ANALYSIS (Ctrl+A)',    COL_TEXT_SECONDARY),
        ('save',          'SAVE (Ctrl+S)',        COL_TEXT_GOOD),
        ('load',          'LOAD FROM FILE',       COL_TEXT_SECONDARY),
        ('test_grid',     'TEST GRID (Ctrl+T)',   COL_SELECTION),
    ]
    # 2-column x 3-row grid.
    col_w = (w - 3 * PAD) // 2
    for i, (action, label, col) in enumerate(actions):
        r, c = divmod(i, 2)
        bx = x0 + PAD + c * (col_w + PAD)
        by = y0 + r * (BTN_H + 4)
        rect = _r(bx, by, col_w, BTN_H)
        _draw_rect(surf, (0, 0, 0), rect)
        _draw_rect(surf, col, rect, 1)
        _label(surf, font, bx + 6, by + 4, label, col)
        _hit_rects.append((action, rect))


def _draw_analysis_panel(surf, font, font_bold, designer, w: int) -> int:
    """
    Static power-flow analysis: balance summary + N-1 headline, RUN/CLOSE
    buttons. Returns the height consumed, so the modal orchestrator can
    stack the (selected element's) properties panel directly below it.
    Per-unit/per-bus/per-line editing happens via that properties panel,
    not here, since 40+ units won't fit this summary block.
    """
    from config.constants import DESIGNER_N1_OVERLOAD_PCT

    y = PAD
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

    half_w = (w - 3 * PAD) // 2
    run_rect = _r(PAD, y, half_w, BTN_H)
    _draw_rect(surf, (0, 0, 0), run_rect)
    _draw_rect(surf, COL_TEXT_GOOD, run_rect, 1)
    _label(surf, font, PAD + 6, y + 4, 'RUN  [Enter]', COL_TEXT_GOOD)
    _modal_rects.append(('analysis_run', run_rect))

    close_rect = _r(PAD + half_w + PAD, y, half_w, BTN_H)
    _draw_rect(surf, (0, 0, 0), close_rect)
    _draw_rect(surf, COL_TEXT_SECONDARY, close_rect, 1)
    _label(surf, font, PAD + half_w + PAD + 6, y + 4, 'CLOSE  [Esc]', COL_TEXT_SECONDARY)
    _modal_rects.append(('analysis_close', close_rect))
    y += BTN_H + PAD

    return y


def _draw_save_dialog(surf, font, font_bold, designer, w: int) -> None:
    """Modal shows a name-input box for saving."""
    y = PAD + 20
    _label(surf, font_bold, PAD, y, 'SAVE GRID', COL_TEXT_HEADING)
    y += ROW_H + 8

    _label(surf, font, PAD, y, 'Grid name:', COL_TEXT_SECONDARY)
    y += ROW_H + 4

    field_rect = _r(PAD, y, w - 2 * PAD, BTN_H + 4)
    _draw_rect(surf, (0, 30, 0), field_rect)
    _draw_rect(surf, COL_TEXT_GOOD, field_rect, 1)
    _label(surf, font, PAD + 6, y + 6, designer._save_dialog_buf + '_', COL_TEXT_GOOD)
    y += BTN_H + 12

    _label(surf, font, PAD, y, '(alphanumeric + underscore)', COL_TEXT_DIM)
    y += ROW_H + 12

    commit_rect = _r(PAD, y, w - 2 * PAD, BTN_H)
    _draw_rect(surf, (0, 0, 0), commit_rect)
    _draw_rect(surf, COL_TEXT_GOOD, commit_rect, 1)
    _label(surf, font, PAD + 6, y + 4, 'SAVE  [Enter]', COL_TEXT_GOOD)
    _modal_rects.append(('save_dialog_commit', commit_rect))
    y += BTN_H + 6

    cancel_rect = _r(PAD, y, w - 2 * PAD, BTN_H)
    _draw_rect(surf, (0, 0, 0), cancel_rect)
    _draw_rect(surf, COL_TEXT_SECONDARY, cancel_rect, 1)
    _label(surf, font, PAD + 6, y + 4, 'CANCEL  [Esc]', COL_TEXT_SECONDARY)
    _modal_rects.append(('overlay_cancel', cancel_rect))


def _save_dialog_height() -> int:
    return (PAD + 20) + (ROW_H + 8) + (ROW_H + 4) + (BTN_H + 12) + (ROW_H + 12) + (BTN_H + 6) + BTN_H + PAD


def _draw_load_browser(surf, font, font_bold, designer, w: int, test_mode: bool = False) -> None:
    """Modal shows a scrollable list of saved grids for load or test."""
    title = 'SELECT GRID — TEST' if test_mode else 'LOAD GRID'
    y = PAD + 20
    _label(surf, font_bold, PAD, y, title, COL_TEXT_HEADING)
    y += ROW_H + 8

    lst  = designer._load_browser_list
    if not lst:
        _label(surf, font, PAD, y, 'No saved grids found.', COL_TEXT_DIM)
        y += ROW_H + 8
        cancel_rect = _r(PAD, y, w - 2 * PAD, BTN_H)
        _draw_rect(surf, (0, 0, 0), cancel_rect)
        _draw_rect(surf, COL_TEXT_SECONDARY, cancel_rect, 1)
        _label(surf, font, PAD + 6, y + 4, 'CANCEL  [Esc]', COL_TEXT_SECONDARY)
        _modal_rects.append(('overlay_cancel', cancel_rect))
        return

    idx    = designer._load_browser_idx
    scroll = designer._load_browser_scroll

    # Clamp scroll so selected is visible
    if idx < scroll:
        designer._load_browser_scroll = idx
        scroll = idx
    elif idx >= scroll + DESIGNER_MODAL_MAX_ROWS:
        designer._load_browser_scroll = idx - DESIGNER_MODAL_MAX_ROWS + 1
        scroll = designer._load_browser_scroll

    visible = lst[scroll: scroll + DESIGNER_MODAL_MAX_ROWS]
    for i, name in enumerate(visible):
        real_idx = scroll + i
        is_sel   = (real_idx == idx)
        row_col  = COL_SELECTION if is_sel else COL_TEXT_SECONDARY
        bg_col   = (0, 40, 0) if is_sel else (0, 0, 0)
        row_rect = _r(PAD, y, w - 2 * PAD, DESIGNER_MODAL_ROW_H - 2)
        _draw_rect(surf, bg_col, row_rect)
        if is_sel:
            _draw_rect(surf, row_col, row_rect, 1)
        _label(surf, font, PAD + 6, y + 4, name, row_col)
        action = f'browser_select:{name}'
        _modal_rects.append((action, row_rect))
        y += DESIGNER_MODAL_ROW_H

    y += 8
    if len(lst) > DESIGNER_MODAL_MAX_ROWS:
        _label(surf, font, PAD, y,
               f'{scroll+1}-{min(scroll+DESIGNER_MODAL_MAX_ROWS, len(lst))} of {len(lst)}',
               COL_TEXT_DIM)
        y += ROW_H

    y += 4
    action_lbl = 'TEST  [Enter]' if test_mode else 'LOAD  [Enter]'
    load_rect  = _r(PAD, y, w - 2 * PAD, BTN_H)
    _draw_rect(surf, (0, 0, 0), load_rect)
    _draw_rect(surf, COL_SELECTION, load_rect, 1)
    _label(surf, font, PAD + 6, y + 4, action_lbl, COL_SELECTION)
    if lst:
        _modal_rects.append((f'browser_select:{lst[idx]}', load_rect))
    y += BTN_H + 6

    cancel_rect = _r(PAD, y, w - 2 * PAD, BTN_H)
    _draw_rect(surf, (0, 0, 0), cancel_rect)
    _draw_rect(surf, COL_TEXT_SECONDARY, cancel_rect, 1)
    _label(surf, font, PAD + 6, y + 4, 'CANCEL  [Esc]', COL_TEXT_SECONDARY)
    _modal_rects.append(('overlay_cancel', cancel_rect))


def _load_browser_height(designer) -> int:
    lst = designer._load_browser_list
    y = (PAD + 20) + (ROW_H + 8)
    if not lst:
        return y + (ROW_H + 8) + BTN_H + PAD
    n_visible = min(len(lst), DESIGNER_MODAL_MAX_ROWS)
    y += n_visible * DESIGNER_MODAL_ROW_H + 8
    if len(lst) > DESIGNER_MODAL_MAX_ROWS:
        y += ROW_H
    y += 4 + (BTN_H + 6) + BTN_H + PAD
    return y


# ─────────────────────────────────────────────────────────────────────────────
# MODAL ORCHESTRATION
# Centered modal geometry + content dispatch for save/load/test/analysis
# overlays. modal_bounds_for() is the single source of truth for a modal's
# (x, y, w, h) — used both to draw the modal box and to hit-test clicks
# against it, so the two can't drift out of sync.
# ─────────────────────────────────────────────────────────────────────────────

def modal_bounds_for(mode: str, designer) -> tuple[int, int, int, int]:
    from config.constants import CANVAS_HEIGHT
    if mode in ('load_browser', 'test_browser'):
        w = DESIGNER_MODAL_BROWSER_W
        h = _load_browser_height(designer)
    elif mode == 'save_dialog':
        w = DESIGNER_MODAL_W
        h = _save_dialog_height()
    elif mode == 'analysis':
        w = DESIGNER_MODAL_W
        h = _analysis_modal_height(designer)
    else:
        return (0, 0, 0, 0)
    x = (NATIVE_WIDTH - w) // 2
    y = designer._canvas_y0 + (CANVAS_HEIGHT - h) // 2
    return (x, y, w, h)


def _analysis_modal_height(designer) -> int:
    # Mirrors _draw_analysis_panel's own y-cursor progression without
    # drawing, plus the properties panel's height when an element is
    # selected (see _properties_height, which mirrors _draw_properties).
    from config.constants import DESIGNER_N1_OVERLOAD_PCT
    y = PAD + (ROW_H + 6)
    result = designer._analysis_result
    if result is None:
        y += (ROW_H + 2) + ROW_H + (ROW_H + 8)
    elif result.solver_error:
        y += ROW_H + (ROW_H + 8)
    else:
        y += ROW_H + ROW_H + (ROW_H + 6) + ROW_H + (ROW_H + 6) + ROW_H + (ROW_H + 8)
    y += BTN_H + PAD
    if (designer._selected_bus is not None or designer._selected_line is not None
            or designer._selected_unit is not None):
        y += 4 + _properties_height(designer, DESIGNER_MODAL_W)
    return y


def _properties_height(designer, w: int) -> int:
    """
    Tallest column's height for the current Properties selection, measured
    by actually running _draw_properties in a no-op "measure" pass (real
    drawing/hit-rect calls are stubbed out — see _measuring flag below)
    rather than a hand-maintained parallel calculation, which is exactly
    the kind of thing that silently drifts out of sync with the real
    drawing code and causes clipped/overlapping content.
    """
    global _measuring, _measured_max_y, _hit_rects
    saved_hit_rects = _hit_rects
    _hit_rects = []
    _measuring, prev_max_y = True, _measured_max_y
    _measured_max_y = 0
    try:
        _draw_properties(None, None, None, designer, 0, w)
        return _measured_max_y + PAD
    finally:
        _measuring = False
        _measured_max_y = prev_max_y
        _hit_rects = saved_hit_rects


def draw_modal_content(surf, designer, font, font_bold, scale, mode: str) -> None:
    """Draw the active modal's content into its subsurface (modal-local coords)."""
    global _modal_rects, _scale
    _modal_rects = []
    _scale = scale

    _, _, w, _ = modal_bounds_for(mode, designer)

    if mode == 'save_dialog':
        _draw_save_dialog(surf, font, font_bold, designer, w)
    elif mode in ('load_browser', 'test_browser'):
        _draw_load_browser(surf, font, font_bold, designer, w, test_mode=(mode == 'test_browser'))
    elif mode == 'analysis':
        y = _draw_analysis_panel(surf, font, font_bold, designer, w)
        if (designer._selected_bus is not None or designer._selected_line is not None
                or designer._selected_unit is not None):
            _hline_span(surf, y, w)
            _draw_properties(surf, font, font_bold, designer, 0, w, y_offset=y + 4)


# ─────────────────────────────────────────────────────────────────────────────
# DRAWING HELPERS
#
# All layout constants and coordinates in this file (PAD, ROW_H, BTN_H, the
# DESIGNER_PANEL_*/DESIGNER_PROPS_*/DESIGNER_MODAL_* constants, and every
# literal passed to _r()/_label() throughout, including arithmetic on a
# previously-built rect's .x/.y) are expressed in LOGICAL (unscaled) pixels
# — the same space hit-testing operates in. _r() returns a logical Rect
# (used both for hit-testing and as the input to _draw_rect); only
# _draw_rect()/_label()/_vsep()/_hline() convert to the surf's actual
# scaled pixel space, at the point of drawing.
# ─────────────────────────────────────────────────────────────────────────────

def _r(x, y, w, h) -> pygame.Rect:
    """Build a logical (unscaled) sidebar Rect — used for hit-testing and layout."""
    rect = pygame.Rect(x, y, w, h)
    if _measuring:
        global _measured_max_y
        _measured_max_y = max(_measured_max_y, rect.bottom)
    return rect


def _draw_rect(surf, colour, rect: pygame.Rect, width: int = 0) -> None:
    """Draw a logical-space Rect, scaling it to surf's actual pixel space."""
    if _measuring:
        return
    sc = _scale
    scaled = pygame.Rect(int(rect.x * sc), int(rect.y * sc),
                         int(rect.width * sc), int(rect.height * sc))
    pygame.draw.rect(surf, colour, scaled, width)


def _label(surf, font, x, y, text, colour):
    if _measuring:
        global _measured_max_y
        _measured_max_y = max(_measured_max_y, y + ROW_H)
        return
    sc = _scale
    font.render_to(surf, (int(x * sc), int(y * sc)), text, colour,
                   size=int(DESIGNER_FONT_SIZE * sc))


def _vsep(surf, x: int) -> None:
    """Full-strip-height vertical separator between two bottom-strip columns."""
    sc = _scale
    pygame.draw.line(surf, COL_DESIGNER_SIDEBAR_SEP,
                     (int(x * sc), 0), (int(x * sc), int(DESIGNER_STRIP_HEIGHT * sc)), 1)


def _hline(surf, y: int) -> None:
    """Full native-width horizontal separator (used by the top panel)."""
    sc = _scale
    pygame.draw.line(surf, COL_DESIGNER_SIDEBAR_SEP,
                     (0, int(y * sc)), (int(NATIVE_WIDTH * sc), int(y * sc)), 1)


def _hline_span(surf, y: int, w: int) -> None:
    """Horizontal separator spanning logical width w from x=0 (used inside a modal)."""
    sc = _scale
    pygame.draw.line(surf, COL_DESIGNER_SIDEBAR_SEP,
                     (0, int(y * sc)), (int(w * sc), int(y * sc)), 1)
