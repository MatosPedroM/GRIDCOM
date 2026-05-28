"""
src/display/context.py

Context overlays for GRIDCOM.

draw_unit_context() renders a fixed-position panel at the top-left of the
canvas surface when a generation unit is selected. draw_bus_context() renders
a read-only panel when a bus is selected. Pure drawing functions — all state
(selection, input buffer) is owned by Renderer.
"""

from __future__ import annotations

import pygame
import pygame.freetype

from display.palette import (
    COL_PANEL_BG, COL_PANEL_BORDER,
    COL_TEXT_PRIMARY, COL_TEXT_VALUE, COL_TEXT_DIM, COL_TEXT_HEADING,
    COL_UNIT_ONLINE, COL_UNIT_STARTING, COL_UNIT_SHUTDOWN, COL_UNIT_OFFLINE,
    COL_CONTEXT_FIELD_BG, COL_CONTEXT_FIELD_ACTIVE, COL_CONTEXT_CURSOR,
    COL_ALARM_CRIT,
    COL_LOAD_WARN, COL_LOAD_HIGH, COL_LOAD_CRIT, COL_LINE_TRIPPED,
)
from simulation.constants import (
    CONTEXT_OVERLAY_X, CONTEXT_OVERLAY_Y,
    CONTEXT_OVERLAY_W, CONTEXT_OVERLAY_PAD,
    CONTEXT_OVERLAY_ROW_H, CONTEXT_OVERLAY_HDR_H,
    FONT_SIZE_CONTEXT,
)

_STATE_COL: dict[str, tuple] = {
    'ONLINE':   COL_UNIT_ONLINE,
    'STARTING': COL_UNIT_STARTING,
    'SHUTDOWN': COL_UNIT_SHUTDOWN,
    'OFFLINE':  COL_UNIT_OFFLINE,
}


def draw_unit_context(
    surf:         pygame.Surface,
    font:         pygame.freetype.Font,
    unit,
    unit_state:   str,
    output_mw:    float,
    target_mw:    float,
    input_buffer: str,
    input_active: bool,
    blink_on:     bool,
    cmd_active:   bool = False,
) -> None:
    """
    Draw the unit context panel at the top-left of the canvas surface.

    Args:
        surf:         Canvas surface (1920×CANVAS_HEIGHT).
        font:         Shared freetype font.
        unit:         GenerationUnit dataclass for the selected unit.
        unit_state:   Current state string.
        output_mw:    Current output in MW.
        target_mw:    Current dispatch target in MW.
        input_buffer: Digits typed so far (empty when not editing).
        input_active: Whether the player is editing the target field.
        blink_on:     Current 1Hz blink phase (for cursor).
        cmd_active:   Whether the START/STOP button has keyboard focus.
    """
    x   = CONTEXT_OVERLAY_X
    y   = CONTEXT_OVERLAY_Y
    w   = CONTEXT_OVERLAY_W
    pad = CONTEXT_OVERLAY_PAD
    sz  = FONT_SIZE_CONTEXT

    is_dispatchable = unit_state in ('ONLINE', 'STARTING', 'SHUTDOWN')
    is_renewable    = unit.unit_type in ('WIND', 'SOLAR')

    show_start      = unit_state == 'OFFLINE' and not is_renewable
    show_stop       = unit_state == 'ONLINE'  and not is_renewable
    # STARTING/SHUTDOWN: show status text row instead of a button
    show_transition = unit_state in ('STARTING', 'SHUTDOWN') and not is_renewable

    if is_dispatchable:
        n_rows = 4  # output + target field + range hint + cmd/transition row
    elif show_start or show_transition:
        n_rows = 3  # output + not-dispatchable msg + cmd row
    else:
        n_rows = 2  # output + not-dispatchable msg (renewable ONLINE)

    panel_h = CONTEXT_OVERLAY_HDR_H + n_rows * CONTEXT_OVERLAY_ROW_H + pad * 2

    panel_rect = pygame.Rect(x, y, w, panel_h)
    pygame.draw.rect(surf, COL_PANEL_BG, panel_rect)
    pygame.draw.rect(surf, COL_PANEL_BORDER, panel_rect, 1)

    sep_y = y + CONTEXT_OVERLAY_HDR_H
    pygame.draw.line(surf, COL_PANEL_BORDER, (x + 1, sep_y), (x + w - 2, sep_y), 1)

    def _ry(n: int) -> int:
        return y + CONTEXT_OVERLAY_HDR_H + pad + n * CONTEXT_OVERLAY_ROW_H

    # ── Header row ────────────────────────────────────────────────────────────
    hdr_y = y + pad + 2
    font.render_to(surf, (x + pad, hdr_y), unit.label, COL_TEXT_HEADING, size=sz)

    state_str  = unit_state
    state_col  = _STATE_COL.get(unit_state, COL_UNIT_OFFLINE)
    state_rect = font.get_rect(state_str, size=sz)
    font.render_to(surf, (x + w - pad - state_rect.width, hdr_y),
                   state_str, state_col, size=sz)

    type_str  = unit.unit_type.replace('_PUMP', '').replace('_ROR', '')
    type_rect = font.get_rect(type_str, size=sz)
    font.render_to(surf, (x + (w - type_rect.width) // 2, hdr_y),
                   type_str, COL_TEXT_DIM, size=sz)

    # ── Row 0: Output ─────────────────────────────────────────────────────────
    row0_y    = _ry(0)
    rated_str  = f'/{unit.rated_mw:.0f} MW'
    rated_rect = font.get_rect(rated_str, size=sz)
    out_str    = f'{output_mw:.0f}'
    out_rect   = font.get_rect(out_str, size=sz)

    font.render_to(surf, (x + pad, row0_y), 'Output:', COL_TEXT_PRIMARY, size=sz)
    font.render_to(surf, (x + w - pad - rated_rect.width, row0_y),
                   rated_str, COL_TEXT_DIM, size=sz)
    font.render_to(surf, (x + w - pad - rated_rect.width - out_rect.width, row0_y),
                   out_str, COL_TEXT_VALUE, size=sz)

    if is_dispatchable:
        # ── Row 1: Target input field ─────────────────────────────────────────
        row1_y  = _ry(1)
        label_w = font.get_rect('Target: ', size=sz).width
        mw_str  = ' MW'
        mw_w    = font.get_rect(mw_str, size=sz).width
        field_x = x + pad + label_w
        field_w = w - pad - (field_x - x) - mw_w - pad
        field_h = CONTEXT_OVERLAY_ROW_H - 2

        font.render_to(surf, (x + pad, row1_y), 'Target:', COL_TEXT_PRIMARY, size=sz)

        field_rect = pygame.Rect(field_x, row1_y - 1, field_w, field_h)
        pygame.draw.rect(surf, COL_CONTEXT_FIELD_BG, field_rect)
        border_col = COL_CONTEXT_FIELD_ACTIVE if input_active else COL_PANEL_BORDER
        pygame.draw.rect(surf, border_col, field_rect, 1)

        display_text = input_buffer if input_active else f'{target_mw:.0f}'
        if display_text:
            font.render_to(surf, (field_x + 2, row1_y), display_text, COL_TEXT_VALUE, size=sz)

        if input_active and blink_on:
            text_w   = font.get_rect(display_text, size=sz).width if display_text else 0
            cur_rect = pygame.Rect(field_x + 2 + text_w, row1_y, 1, field_h - 2)
            pygame.draw.rect(surf, COL_CONTEXT_CURSOR, cur_rect)

        font.render_to(surf, (field_x + field_w + 2, row1_y), mw_str, COL_TEXT_DIM, size=sz)

        # ── Row 2: Range hint ─────────────────────────────────────────────────
        hint = f'[{unit.min_mw:.0f} – {unit.rated_mw:.0f} MW]'
        font.render_to(surf, (x + pad, _ry(2)), hint, COL_TEXT_DIM, size=sz)

        # ── Row 3: START / STOP button or transition status ───────────────────
        _draw_cmd_row(surf, font, x, w, pad, sz, _ry(3),
                      show_start, show_stop, show_transition,
                      unit_state, cmd_active)

    else:
        # ── Row 1: Not dispatchable ───────────────────────────────────────────
        font.render_to(surf, (x + pad, _ry(1)),
                       '(unit not dispatchable)', COL_TEXT_DIM, size=sz)

        # ── Row 2: START button (OFFLINE non-renewable) ───────────────────────
        if show_start:
            _draw_cmd_row(surf, font, x, w, pad, sz, _ry(2),
                          show_start=True, show_stop=False,
                          show_transition=False,
                          unit_state=unit_state, cmd_active=cmd_active)


def draw_bus_context(
    surf:  pygame.Surface,
    font:  pygame.freetype.Font,
    bus,
    state,
) -> None:
    """
    Draw a read-only bus context panel at the top-left of the canvas surface.

    Args:
        surf:  Canvas surface (1920×CANVAS_HEIGHT).
        font:  Shared freetype font.
        bus:   Bus dataclass for the selected bus.
        state: Current SimulationState, or None.
    """
    x   = CONTEXT_OVERLAY_X
    y   = CONTEXT_OVERLAY_Y
    w   = CONTEXT_OVERLAY_W
    pad = CONTEXT_OVERLAY_PAD
    sz  = FONT_SIZE_CONTEXT

    n_rows  = 2  # voltage row + kV label row
    panel_h = CONTEXT_OVERLAY_HDR_H + n_rows * CONTEXT_OVERLAY_ROW_H + pad * 2

    panel_rect = pygame.Rect(x, y, w, panel_h)
    pygame.draw.rect(surf, COL_PANEL_BG, panel_rect)
    pygame.draw.rect(surf, COL_PANEL_BORDER, panel_rect, 1)

    sep_y = y + CONTEXT_OVERLAY_HDR_H
    pygame.draw.line(surf, COL_PANEL_BORDER, (x + 1, sep_y), (x + w - 2, sep_y), 1)

    def _ry(n: int) -> int:
        return y + CONTEXT_OVERLAY_HDR_H + pad + n * CONTEXT_OVERLAY_ROW_H

    # ── Header: bus label left, "BUS" right ───────────────────────────────────
    hdr_y = y + pad + 2
    font.render_to(surf, (x + pad, hdr_y), bus.label, COL_TEXT_HEADING, size=sz)
    type_rect = font.get_rect('BUS', size=sz)
    font.render_to(surf, (x + w - pad - type_rect.width, hdr_y), 'BUS', COL_TEXT_DIM, size=sz)

    # ── Row 0: Voltage level ──────────────────────────────────────────────────
    kv_str = f'{bus.voltage_kv:.0f} kV'
    font.render_to(surf, (x + pad, _ry(0)), 'Voltage level:', COL_TEXT_PRIMARY, size=sz)
    kv_rect = font.get_rect(kv_str, size=sz)
    font.render_to(surf, (x + w - pad - kv_rect.width, _ry(0)), kv_str, COL_TEXT_DIM, size=sz)

    # ── Row 1: Live voltage pu ────────────────────────────────────────────────
    font.render_to(surf, (x + pad, _ry(1)), 'V:', COL_TEXT_PRIMARY, size=sz)
    if state is not None:
        v_pu = state.bus_voltages.get(bus.label)
        v_str = f'{v_pu:.3f} pu' if v_pu is not None else '--'
    else:
        v_str = '--'
    v_rect = font.get_rect(v_str, size=sz)
    font.render_to(surf, (x + w - pad - v_rect.width, _ry(1)), v_str, COL_TEXT_VALUE, size=sz)


def draw_line_context(
    surf:       pygame.Surface,
    font:       pygame.freetype.Font,
    line,
    state,
    cmd_active: bool = False,
) -> None:
    """
    Draw the line context panel at the top-left of the canvas surface.

    Args:
        surf:       Canvas surface (1920×CANVAS_HEIGHT).
        font:       Shared freetype font.
        line:       Line dataclass for the selected line.
        state:      Current SimulationState, or None.
        cmd_active: Whether the TRIP/CLOSE button has keyboard focus.
    """
    x   = CONTEXT_OVERLAY_X
    y   = CONTEXT_OVERLAY_Y
    w   = CONTEXT_OVERLAY_W
    pad = CONTEXT_OVERLAY_PAD
    sz  = FONT_SIZE_CONTEXT

    if state is not None:
        line_status = state.line_status.get(line.label, 'IN_SERVICE')
    else:
        line_status = None

    # Button row shown when status is known (IN SERVICE → TRIP, TRIPPED → CLOSE)
    show_btn = line_status in ('IN_SERVICE', 'TRIPPED')
    n_rows   = 6 + (1 if show_btn else 0)  # from/to + voltage + rating + flow + loading + status [+ button]
    panel_h  = CONTEXT_OVERLAY_HDR_H + n_rows * CONTEXT_OVERLAY_ROW_H + pad * 2

    panel_rect = pygame.Rect(x, y, w, panel_h)
    pygame.draw.rect(surf, COL_PANEL_BG, panel_rect)
    pygame.draw.rect(surf, COL_PANEL_BORDER, panel_rect, 1)

    sep_y = y + CONTEXT_OVERLAY_HDR_H
    pygame.draw.line(surf, COL_PANEL_BORDER, (x + 1, sep_y), (x + w - 2, sep_y), 1)

    def _ry(n: int) -> int:
        return y + CONTEXT_OVERLAY_HDR_H + pad + n * CONTEXT_OVERLAY_ROW_H

    # ── Header: line label left, "LINE" right ─────────────────────────────────
    hdr_y = y + pad + 2
    font.render_to(surf, (x + pad, hdr_y), line.label, COL_TEXT_HEADING, size=sz)
    type_rect = font.get_rect('LINE', size=sz)
    font.render_to(surf, (x + w - pad - type_rect.width, hdr_y), 'LINE', COL_TEXT_DIM, size=sz)

    # ── Row 0: From bus → To bus ──────────────────────────────────────────────
    route_str = f'{line.from_bus} → {line.to_bus}'
    font.render_to(surf, (x + pad, _ry(0)), route_str, COL_TEXT_VALUE, size=sz)

    # ── Row 1: Voltage level ──────────────────────────────────────────────────
    kv_str = f'{line.voltage_kv:.0f} kV'
    font.render_to(surf, (x + pad, _ry(1)), 'Voltage:', COL_TEXT_PRIMARY, size=sz)
    kv_rect = font.get_rect(kv_str, size=sz)
    font.render_to(surf, (x + w - pad - kv_rect.width, _ry(1)), kv_str, COL_TEXT_DIM, size=sz)

    # ── Row 2: Thermal rating ─────────────────────────────────────────────────
    rating_str = f'{line.rating_mw:.0f} MW'
    font.render_to(surf, (x + pad, _ry(2)), 'Rating:', COL_TEXT_PRIMARY, size=sz)
    rating_rect = font.get_rect(rating_str, size=sz)
    font.render_to(surf, (x + w - pad - rating_rect.width, _ry(2)), rating_str, COL_TEXT_DIM, size=sz)

    # ── Row 3: Flow with direction ────────────────────────────────────────────
    font.render_to(surf, (x + pad, _ry(3)), 'Flow:', COL_TEXT_PRIMARY, size=sz)
    if state is not None:
        flow_mw = state.line_flows_mw.get(line.label)
        if flow_mw is not None:
            arrow   = '▶' if flow_mw >= 0 else '◀'
            flow_str = f'{arrow} {abs(flow_mw):.0f} MW'
        else:
            flow_str = '--'
    else:
        flow_str = '--'
    flow_rect = font.get_rect(flow_str, size=sz)
    font.render_to(surf, (x + w - pad - flow_rect.width, _ry(3)), flow_str, COL_TEXT_VALUE, size=sz)

    # ── Row 4: Loading % with colour ──────────────────────────────────────────
    font.render_to(surf, (x + pad, _ry(4)), 'Loading:', COL_TEXT_PRIMARY, size=sz)
    if state is not None:
        loading = state.line_loading_pct.get(line.label)
        if loading is not None:
            loading_str = f'{loading:.1f}%'
            if loading >= 95.0:
                loading_col = COL_LOAD_CRIT
            elif loading >= 80.0:
                loading_col = COL_LOAD_HIGH
            elif loading >= 60.0:
                loading_col = COL_LOAD_WARN
            else:
                loading_col = COL_UNIT_ONLINE
        else:
            loading_str = '--'
            loading_col = COL_TEXT_DIM
    else:
        loading_str = '--'
        loading_col = COL_TEXT_DIM
    load_rect = font.get_rect(loading_str, size=sz)
    font.render_to(surf, (x + w - pad - load_rect.width, _ry(4)), loading_str, loading_col, size=sz)

    # ── Row 5: Status ─────────────────────────────────────────────────────────
    font.render_to(surf, (x + pad, _ry(5)), 'Status:', COL_TEXT_PRIMARY, size=sz)
    status_raw = line_status if line_status is not None else '--'
    if status_raw == 'TRIPPED':
        status_col  = COL_LINE_TRIPPED
        status_disp = 'TRIPPED'
    elif status_raw == 'IN_SERVICE':
        status_col  = COL_UNIT_ONLINE
        status_disp = 'IN SERVICE'
    else:
        status_col  = COL_TEXT_DIM
        status_disp = status_raw
    status_rect = font.get_rect(status_disp, size=sz)
    font.render_to(surf, (x + w - pad - status_rect.width, _ry(5)), status_disp, status_col, size=sz)

    # ── Row 6: TRIP / CLOSE button ────────────────────────────────────────────
    if show_btn:
        if line_status == 'IN_SERVICE':
            btn_label  = '[ T ] TRIP'
            border_col = COL_ALARM_CRIT if cmd_active else COL_PANEL_BORDER
            text_col   = COL_ALARM_CRIT
        else:
            btn_label  = '[ C ] CLOSE'
            border_col = COL_UNIT_ONLINE if cmd_active else COL_PANEL_BORDER
            text_col   = COL_UNIT_ONLINE

        btn_h    = CONTEXT_OVERLAY_ROW_H - 2
        btn_w    = w - pad * 2
        btn_rect = pygame.Rect(x + pad, _ry(6) - 1, btn_w, btn_h)
        pygame.draw.rect(surf, COL_PANEL_BG, btn_rect)
        pygame.draw.rect(surf, border_col, btn_rect, 1)

        lbl_rect = font.get_rect(btn_label, size=sz)
        lx = x + pad + (btn_w - lbl_rect.width) // 2
        font.render_to(surf, (lx, _ry(6)), btn_label, text_col, size=sz)


def _draw_cmd_row(
    surf, font, x: int, w: int, pad: int, sz: int, row_y: int,
    show_start: bool, show_stop: bool, show_transition: bool,
    unit_state: str, cmd_active: bool,
) -> None:
    """Draw the START/STOP button or transition status line at row_y."""
    if show_start:
        label      = '[ START ]'
        border_col = COL_UNIT_ONLINE if cmd_active else COL_PANEL_BORDER
        text_col   = COL_UNIT_ONLINE
    elif show_stop:
        label      = '[ STOP ]'
        border_col = COL_ALARM_CRIT if cmd_active else COL_PANEL_BORDER
        text_col   = COL_ALARM_CRIT
    elif show_transition:
        status = 'starting…' if unit_state == 'STARTING' else 'shutting down…'
        font.render_to(surf, (x + pad, row_y), status, COL_TEXT_DIM, size=sz)
        return
    else:
        return

    btn_h = CONTEXT_OVERLAY_ROW_H - 2
    btn_w = w - pad * 2
    btn_rect = pygame.Rect(x + pad, row_y - 1, btn_w, btn_h)
    pygame.draw.rect(surf, COL_PANEL_BG, btn_rect)
    pygame.draw.rect(surf, border_col, btn_rect, 1)

    lbl_rect = font.get_rect(label, size=sz)
    lx = x + pad + (btn_w - lbl_rect.width) // 2
    font.render_to(surf, (lx, row_y), label, text_col, size=sz)
