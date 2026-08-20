"""
src/display/context.py

Context overlays for GRIDCOM.

draw_unit_context() renders a fixed-position panel at the top-left of the
canvas surface when a generation unit is selected. draw_bus_context() renders
a read-only panel when a bus is selected. Pure drawing functions — all state
(selection, input buffer) is owned by Renderer.
"""

from __future__ import annotations

import math

import pygame
import pygame.freetype

from display.palette import (
    COL_PANEL_BG, COL_PANEL_BORDER,
    COL_TEXT_PRIMARY, COL_TEXT_VALUE, COL_TEXT_DIM, COL_TEXT_HEADING,
    COL_UNIT_ONLINE, COL_UNIT_STARTING, COL_UNIT_SHUTDOWN, COL_UNIT_OFFLINE,
    COL_CONTEXT_FIELD_BG, COL_CONTEXT_FIELD_ACTIVE, COL_CONTEXT_CURSOR,
    COL_ALARM_CRIT, COL_ALARM_WARN,
    COL_LOAD_WARN, COL_LOAD_HIGH, COL_LOAD_CRIT, COL_LINE_TRIPPED,
    COL_VSI_WATCH, COL_VSI_WARNING, COL_VSI_CRITICAL, COL_SVC,
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
    surf:           pygame.Surface,
    font:           pygame.freetype.Font,
    unit,
    unit_state:     str,
    output_mw:      float,
    target_mw:      float,
    input_buffer:   str,
    input_active:   bool,
    blink_on:       bool,
    cmd_active:     bool  = False,
    font_scale:     float = 1.0,
    is_maintenance: bool  = False,
    v_setpoint_pu:  float | None = None,
    bus_type:       str | None   = None,
    q_mvar:         float | None = None,
    q_reserve_mvar: float | None = None,
    setpoint_buffer: str  = '',
    setpoint_active: bool = False,
    dispatch_mode:  str | None = None,
    mode_cmd_active: bool = False,
    adjust_active:  bool = False,
    setpoint_adjust_active: bool = False,
) -> None:
    """
    Draw the unit context panel at the top-left of the canvas surface.

    Args:
        surf:         Canvas surface.
        font:         Shared freetype font.
        unit:         GenerationUnit dataclass for the selected unit.
        unit_state:   Current state string.
        output_mw:    Current output in MW.
        target_mw:    Current dispatch target in MW.
        input_buffer: Digits typed so far (empty when not editing).
        input_active: Whether the player is editing the target field.
        blink_on:     Current 1Hz blink phase (for cursor).
        cmd_active:   Whether the START/STOP button has keyboard focus.
        font_scale:   Display scale factor.
        v_setpoint_pu:  AVR voltage setpoint (unit_v_setpoint_pu), None to hide the row.
        bus_type:       'PV' or 'PQ' (unit_bus_types) — voltage-control status.
        q_mvar:         Current reactive injection (unit_q_injections_mvar).
        q_reserve_mvar: Headroom to q_max_mvar (unit_q_reserve_mvar).
        setpoint_buffer: Digits typed so far for the AVR setpoint field.
        setpoint_active: Whether the AVR setpoint field has keyboard focus
                        (mirrors input_active/input_buffer for the MW target).
        dispatch_mode:  'AUTO'/'MANUAL' (unit_dispatch_modes), None to hide
                        the row entirely — only shown when this shift has a
                        Phase 1 hourly schedule covering the unit.
        mode_cmd_active: Whether the AUTO/MANUAL toggle button has keyboard focus.
        adjust_active:  Whether active-power nudge mode (W + Up/Down) is armed
        setpoint_adjust_active: Whether reactive-power/AVR nudge mode
                        (Q + Up/Down) is armed
                        for this unit — shown as a magenta Target field border,
                        distinct from input_active's green typed-entry border.
    """
    fs  = font_scale
    x   = int(CONTEXT_OVERLAY_X   * fs)
    y   = int(CONTEXT_OVERLAY_Y   * fs)
    w   = int(CONTEXT_OVERLAY_W   * fs)
    pad = int(CONTEXT_OVERLAY_PAD * fs)
    rh  = int(CONTEXT_OVERLAY_ROW_H * fs)
    hdh = int(CONTEXT_OVERLAY_HDR_H * fs)
    sz  = int(FONT_SIZE_CONTEXT * fs)

    is_dispatchable = unit_state in ('ONLINE', 'STARTING', 'SHUTDOWN')
    is_renewable    = unit.unit_type in ('WIND', 'SOLAR')
    show_avr        = is_dispatchable and not is_renewable and v_setpoint_pu is not None

    show_start      = unit_state == 'OFFLINE' and not is_renewable and not is_maintenance
    show_stop       = unit_state == 'ONLINE'  and not is_renewable
    show_transition = unit_state in ('STARTING', 'SHUTDOWN') and not is_renewable
    show_maintenance = is_maintenance and unit_state == 'OFFLINE'
    show_mode       = is_dispatchable and not is_renewable and dispatch_mode is not None

    if is_dispatchable:
        # AVR block is 4 rows: setpoint, voltage-control mode, Q, S (MVA).
        n_rows = 4 + (4 if show_avr else 0) + (1 if show_mode else 0)
    elif show_start or show_transition or show_maintenance:
        n_rows = 3
    else:
        n_rows = 2

    panel_h = hdh + n_rows * rh + pad * 2

    panel_rect = pygame.Rect(x, y, w, panel_h)
    pygame.draw.rect(surf, COL_PANEL_BG, panel_rect)
    pygame.draw.rect(surf, COL_PANEL_BORDER, panel_rect, 1)

    sep_y = y + hdh
    pygame.draw.line(surf, COL_PANEL_BORDER, (x + 1, sep_y), (x + w - 2, sep_y), 1)

    def _ry(n: int) -> int:
        return y + hdh + pad + n * rh

    hdr_y = y + pad + max(1, int(2 * fs))
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
        row1_y  = _ry(1)
        label_w = font.get_rect('Target: ', size=sz).width
        mw_str  = ' MW'
        mw_w    = font.get_rect(mw_str, size=sz).width
        field_x = x + pad + label_w
        field_w = w - pad - (field_x - x) - mw_w - pad
        field_h = rh - 2

        font.render_to(surf, (x + pad, row1_y), 'Target:', COL_TEXT_PRIMARY, size=sz)

        field_rect = pygame.Rect(field_x, row1_y - 1, field_w, field_h)
        pygame.draw.rect(surf, COL_CONTEXT_FIELD_BG, field_rect)
        if input_active:
            border_col = COL_CONTEXT_FIELD_ACTIVE
        elif adjust_active:
            border_col = COL_SVC
        else:
            border_col = COL_PANEL_BORDER
        pygame.draw.rect(surf, border_col, field_rect, 1)

        display_text = input_buffer if input_active else f'{target_mw:.0f}'
        if display_text:
            font.render_to(surf, (field_x + 2, row1_y), display_text, COL_TEXT_VALUE, size=sz)

        if input_active and blink_on:
            text_w   = font.get_rect(display_text, size=sz).width if display_text else 0
            cur_rect = pygame.Rect(field_x + 2 + text_w, row1_y, 1, field_h - 2)
            pygame.draw.rect(surf, COL_CONTEXT_CURSOR, cur_rect)

        font.render_to(surf, (field_x + field_w + 2, row1_y), mw_str, COL_TEXT_DIM, size=sz)

        if adjust_active:
            hint     = 'ADJUST ARMED — Up/Down step, Ctrl+Up/Down fast'
            hint_col = COL_SVC
        else:
            hint     = f'[{unit.min_mw:.0f} – {unit.rated_mw:.0f} MW]  (W to adjust)'
            hint_col = COL_TEXT_DIM
        font.render_to(surf, (x + pad, _ry(2)), hint, hint_col, size=sz)

        cmd_row = 3
        if show_avr:
            avr_row_y = _ry(3)
            # Label doubles as the keybinding cue, mirroring the MW row's
            # "(W to adjust)" hint — there is no spare row here for a hint line.
            avr_label = 'AVR [Q]:' if not setpoint_adjust_active else 'AVR [Q]* '
            avr_label_w = font.get_rect(avr_label + ' ', size=sz).width
            pu_str  = ' pu'
            pu_w    = font.get_rect(pu_str, size=sz).width
            avr_field_x = x + pad + avr_label_w
            avr_field_w = w - pad - (avr_field_x - x) - pu_w - pad
            avr_field_h = rh - 2

            font.render_to(surf, (x + pad, avr_row_y), avr_label,
                           COL_SVC if setpoint_adjust_active else COL_TEXT_PRIMARY, size=sz)

            avr_field_rect = pygame.Rect(avr_field_x, avr_row_y - 1, avr_field_w, avr_field_h)
            pygame.draw.rect(surf, COL_CONTEXT_FIELD_BG, avr_field_rect)
            if setpoint_active:
                avr_border_col = COL_CONTEXT_FIELD_ACTIVE
            elif setpoint_adjust_active:
                avr_border_col = COL_SVC          # armed, same cue as the MW field
            else:
                avr_border_col = COL_PANEL_BORDER
            pygame.draw.rect(surf, avr_border_col, avr_field_rect, 1)

            avr_display = setpoint_buffer if setpoint_active else f'{v_setpoint_pu:.3f}'
            if avr_display:
                font.render_to(surf, (avr_field_x + 2, avr_row_y), avr_display, COL_TEXT_VALUE, size=sz)
            if setpoint_active and blink_on:
                avr_text_w = font.get_rect(avr_display, size=sz).width if avr_display else 0
                avr_cur_rect = pygame.Rect(avr_field_x + 2 + avr_text_w, avr_row_y, 1, avr_field_h - 2)
                pygame.draw.rect(surf, COL_CONTEXT_CURSOR, avr_cur_rect)
            font.render_to(surf, (avr_field_x + avr_field_w + 2, avr_row_y), pu_str, COL_TEXT_DIM, size=sz)

            pv_pq_row_y = _ry(4)
            font.render_to(surf, (x + pad, pv_pq_row_y), 'Voltage ctrl:', COL_TEXT_PRIMARY, size=sz)
            bt = bus_type or 'PV'
            bt_col = COL_UNIT_ONLINE if bt == 'PV' else COL_ALARM_WARN
            bt_rect = font.get_rect(bt, size=sz)
            font.render_to(surf, (x + w - pad - bt_rect.width, pv_pq_row_y), bt, bt_col, size=sz)

            q_row_y = _ry(5)
            font.render_to(surf, (x + pad, q_row_y), 'Q:', COL_TEXT_PRIMARY, size=sz)
            q_str = f'{(q_mvar or 0.0):+.0f} / {(q_reserve_mvar or 0.0):.0f} rsv MVAr'
            q_rect = font.get_rect(q_str, size=sz)
            font.render_to(surf, (x + w - pad - q_rect.width, q_row_y), q_str, COL_TEXT_VALUE, size=sz)

            # Apparent power S = sqrt(P^2 + Q^2), in real MVA. Shown so the
            # machine's active and reactive output read as two components of
            # one quantity rather than two unrelated numbers. Derived for
            # display only — P and Q limits are independent in this model,
            # so there is no MVA capability circle constraining them.
            s_row_y = _ry(6)
            s_mva = math.hypot(output_mw, q_mvar or 0.0)
            font.render_to(surf, (x + pad, s_row_y), 'S:', COL_TEXT_PRIMARY, size=sz)
            s_str = f'{s_mva:.0f} MVA'
            s_rect = font.get_rect(s_str, size=sz)
            font.render_to(surf, (x + w - pad - s_rect.width, s_row_y), s_str, COL_TEXT_VALUE, size=sz)

            cmd_row = 7

        _draw_cmd_row(surf, font, x, w, pad, rh, sz, _ry(cmd_row),
                      show_start, show_stop, show_transition,
                      unit_state, cmd_active)

        if show_mode:
            _draw_mode_row(surf, font, x, w, pad, rh, sz, _ry(cmd_row + 1),
                          dispatch_mode, mode_cmd_active)

    else:
        font.render_to(surf, (x + pad, _ry(1)),
                       '(unit not dispatchable)', COL_TEXT_DIM, size=sz)

        if show_maintenance:
            font.render_to(surf, (x + pad, _ry(2)),
                           'PLANNED MAINTENANCE', COL_ALARM_WARN, size=sz)
        elif show_start:
            _draw_cmd_row(surf, font, x, w, pad, rh, sz, _ry(2),
                          show_start=True, show_stop=False,
                          show_transition=False,
                          unit_state=unit_state, cmd_active=cmd_active)


_VSI_TIER_TEXT_COL: dict[str, tuple] = {
    'HEALTHY':  COL_UNIT_ONLINE,
    'WATCH':    COL_VSI_WATCH,
    'WARNING':  COL_VSI_WARNING,
    'CRITICAL': COL_VSI_CRITICAL,
}


def draw_bus_context(
    surf:         pygame.Surface,
    font:         pygame.freetype.Font,
    bus,
    state,
    font_scale:   float = 1.0,
    svc_cmd_active: bool = False,
) -> None:
    """
    Draw a bus context panel at the top-left of the canvas surface. Mostly
    read-only (voltage, VSI tier, Q, auto shunt-bank state) — the SVC row is
    the one interactive affordance, shown only for a bus hosting one.

    Args:
        svc_cmd_active: Whether the SVC adjust command has keyboard focus
                        (mirrors the line TRIP/CLOSE cmd_active convention).
    """
    fs  = font_scale
    x   = int(CONTEXT_OVERLAY_X   * fs)
    y   = int(CONTEXT_OVERLAY_Y   * fs)
    w   = int(CONTEXT_OVERLAY_W   * fs)
    pad = int(CONTEXT_OVERLAY_PAD * fs)
    rh  = int(CONTEXT_OVERLAY_ROW_H * fs)
    hdh = int(CONTEXT_OVERLAY_HDR_H * fs)
    sz  = int(FONT_SIZE_CONTEXT * fs)

    is_load_bus = (bus.bus_type == 'LOAD')

    has_shunt = state is not None and state.bus_shunt_step.get(bus.label, 0) != 0
    has_svc = state is not None and bus.label in state.bus_svc_mvar

    # Rows: Voltage level, V, VSI tier, Q, [Load], [Shunt], [SVC]
    n_rows  = 4 + (1 if is_load_bus else 0) + (1 if has_shunt else 0) \
                + (1 if has_svc else 0)
    panel_h = hdh + n_rows * rh + pad * 2

    panel_rect = pygame.Rect(x, y, w, panel_h)
    pygame.draw.rect(surf, COL_PANEL_BG, panel_rect)
    pygame.draw.rect(surf, COL_PANEL_BORDER, panel_rect, 1)

    sep_y = y + hdh
    pygame.draw.line(surf, COL_PANEL_BORDER, (x + 1, sep_y), (x + w - 2, sep_y), 1)

    def _ry(n: int) -> int:
        return y + hdh + pad + n * rh

    hdr_y = y + pad + max(1, int(2 * fs))
    font.render_to(surf, (x + pad, hdr_y), bus.label, COL_TEXT_HEADING, size=sz)
    type_label = 'LOAD' if is_load_bus else 'BUS'
    type_rect = font.get_rect(type_label, size=sz)
    font.render_to(surf, (x + w - pad - type_rect.width, hdr_y), type_label, COL_TEXT_DIM, size=sz)

    kv_str = f'{bus.voltage_kv:.0f} kV'
    font.render_to(surf, (x + pad, _ry(0)), 'Voltage level:', COL_TEXT_PRIMARY, size=sz)
    kv_rect = font.get_rect(kv_str, size=sz)
    font.render_to(surf, (x + w - pad - kv_rect.width, _ry(0)), kv_str, COL_TEXT_DIM, size=sz)

    # Actual bus voltage in real kV (v_pu x this bus's nominal kV), with the
    # per-unit figure kept as a secondary reading. Operators read kV; per-unit
    # is the solver's internal representation.
    font.render_to(surf, (x + pad, _ry(1)), 'V:', COL_TEXT_PRIMARY, size=sz)
    if state is not None:
        v_pu = state.bus_voltages.get(bus.label)
        v_str = (f'{v_pu * bus.voltage_kv:.1f} kV  ({v_pu:.3f} pu)'
                 if v_pu is not None else '--')
    else:
        v_str = '--'
    v_rect = font.get_rect(v_str, size=sz)
    font.render_to(surf, (x + w - pad - v_rect.width, _ry(1)), v_str, COL_TEXT_VALUE, size=sz)

    font.render_to(surf, (x + pad, _ry(2)), 'VSI:', COL_TEXT_PRIMARY, size=sz)
    if state is not None:
        tier = state.bus_vsi_tier.get(bus.label, 'HEALTHY')
        tier_col = _VSI_TIER_TEXT_COL.get(tier, COL_TEXT_DIM)
    else:
        tier, tier_col = '--', COL_TEXT_DIM
    tier_rect = font.get_rect(tier, size=sz)
    font.render_to(surf, (x + w - pad - tier_rect.width, _ry(2)), tier, tier_col, size=sz)

    font.render_to(surf, (x + pad, _ry(3)), 'Q:', COL_TEXT_PRIMARY, size=sz)
    if state is not None:
        q_mvar = state.bus_q_injection_mvar.get(bus.label)
        q_str = f'{q_mvar:+.0f} MVAr' if q_mvar is not None else '--'
    else:
        q_str = '--'
    q_rect = font.get_rect(q_str, size=sz)
    font.render_to(surf, (x + w - pad - q_rect.width, _ry(3)), q_str, COL_TEXT_VALUE, size=sz)

    row = 4
    if is_load_bus:
        font.render_to(surf, (x + pad, _ry(row)), 'Load:', COL_TEXT_PRIMARY, size=sz)
        if state is not None:
            load_mw = state.bus_loads.get(bus.label)
            load_str = f'{load_mw:.1f} MW' if load_mw is not None else '--'
        else:
            load_str = '--'
        load_rect = font.get_rect(load_str, size=sz)
        font.render_to(surf, (x + w - pad - load_rect.width, _ry(row)),
                       load_str, COL_TEXT_VALUE, size=sz)
        row += 1

    if has_shunt:
        step, mvar = state.bus_shunt_step[bus.label], state.bus_shunt_mvar[bus.label]
        font.render_to(surf, (x + pad, _ry(row)), 'Shunt (auto):', COL_TEXT_PRIMARY, size=sz)
        shunt_str = f'step {step:+d} ({mvar:+.0f} MVAr)'
        shunt_rect = font.get_rect(shunt_str, size=sz)
        font.render_to(surf, (x + w - pad - shunt_rect.width, _ry(row)),
                       shunt_str, COL_TEXT_DIM, size=sz)
        row += 1

    if has_svc:
        q_setpoint = state.bus_svc_mvar.get(bus.label, 0.0)
        label_str = 'SVC [,/.]:'
        label_col = COL_SVC if svc_cmd_active else COL_TEXT_PRIMARY
        font.render_to(surf, (x + pad, _ry(row)), label_str, label_col, size=sz)
        svc_str = f'{q_setpoint:+.0f} MVAr'
        svc_rect = font.get_rect(svc_str, size=sz)
        font.render_to(surf, (x + w - pad - svc_rect.width, _ry(row)),
                       svc_str, COL_SVC, size=sz)


def draw_line_context(
    surf:       pygame.Surface,
    font:       pygame.freetype.Font,
    line,
    state,
    cmd_active: bool  = False,
    font_scale: float = 1.0,
) -> None:
    """Draw the line context panel at the top-left of the canvas surface."""
    fs  = font_scale
    x   = int(CONTEXT_OVERLAY_X   * fs)
    y   = int(CONTEXT_OVERLAY_Y   * fs)
    w   = int(CONTEXT_OVERLAY_W   * fs)
    pad = int(CONTEXT_OVERLAY_PAD * fs)
    rh  = int(CONTEXT_OVERLAY_ROW_H * fs)
    hdh = int(CONTEXT_OVERLAY_HDR_H * fs)
    sz  = int(FONT_SIZE_CONTEXT * fs)

    if state is not None:
        line_status = state.line_status.get(line.label, 'IN_SERVICE')
    else:
        line_status = None

    show_btn = line_status in ('IN_SERVICE', 'TRIPPED')
    n_rows   = 6 + (1 if show_btn else 0)
    panel_h  = hdh + n_rows * rh + pad * 2

    panel_rect = pygame.Rect(x, y, w, panel_h)
    pygame.draw.rect(surf, COL_PANEL_BG, panel_rect)
    pygame.draw.rect(surf, COL_PANEL_BORDER, panel_rect, 1)

    sep_y = y + hdh
    pygame.draw.line(surf, COL_PANEL_BORDER, (x + 1, sep_y), (x + w - 2, sep_y), 1)

    def _ry(n: int) -> int:
        return y + hdh + pad + n * rh

    hdr_y = y + pad + max(1, int(2 * fs))
    font.render_to(surf, (x + pad, hdr_y), line.label, COL_TEXT_HEADING, size=sz)
    type_rect = font.get_rect('LINE', size=sz)
    font.render_to(surf, (x + w - pad - type_rect.width, hdr_y), 'LINE', COL_TEXT_DIM, size=sz)

    route_str = f'{line.from_bus} → {line.to_bus}'
    font.render_to(surf, (x + pad, _ry(0)), route_str, COL_TEXT_VALUE, size=sz)

    kv_str = f'{line.voltage_kv:.0f} kV'
    font.render_to(surf, (x + pad, _ry(1)), 'Voltage:', COL_TEXT_PRIMARY, size=sz)
    kv_rect = font.get_rect(kv_str, size=sz)
    font.render_to(surf, (x + w - pad - kv_rect.width, _ry(1)), kv_str, COL_TEXT_DIM, size=sz)

    rating_str = f'{line.rating_mw:.0f} MW'
    font.render_to(surf, (x + pad, _ry(2)), 'Rating:', COL_TEXT_PRIMARY, size=sz)
    rating_rect = font.get_rect(rating_str, size=sz)
    font.render_to(surf, (x + w - pad - rating_rect.width, _ry(2)), rating_str, COL_TEXT_DIM, size=sz)

    font.render_to(surf, (x + pad, _ry(3)), 'Flow:', COL_TEXT_PRIMARY, size=sz)
    if state is not None:
        flow_mw = state.line_flows_mw.get(line.label)
        if flow_mw is not None:
            arrow    = '▶' if flow_mw >= 0 else '◀'
            flow_str = f'{arrow} {abs(flow_mw):.0f} MW'
        else:
            flow_str = '--'
    else:
        flow_str = '--'
    flow_rect = font.get_rect(flow_str, size=sz)
    font.render_to(surf, (x + w - pad - flow_rect.width, _ry(3)), flow_str, COL_TEXT_VALUE, size=sz)

    font.render_to(surf, (x + pad, _ry(4)), 'Loading:', COL_TEXT_PRIMARY, size=sz)
    if state is not None:
        loading = state.line_loading_pct.get(line.label)
        if loading is not None:
            loading_str = f'{loading:.1f}%'
            loading_col = (COL_LOAD_CRIT if loading >= 95.0 else
                           COL_LOAD_HIGH if loading >= 80.0 else
                           COL_LOAD_WARN if loading >= 60.0 else COL_UNIT_ONLINE)
        else:
            loading_str, loading_col = '--', COL_TEXT_DIM
    else:
        loading_str, loading_col = '--', COL_TEXT_DIM
    load_rect = font.get_rect(loading_str, size=sz)
    font.render_to(surf, (x + w - pad - load_rect.width, _ry(4)), loading_str, loading_col, size=sz)

    font.render_to(surf, (x + pad, _ry(5)), 'Status:', COL_TEXT_PRIMARY, size=sz)
    status_raw = line_status if line_status is not None else '--'
    if status_raw == 'TRIPPED':
        status_col, status_disp = COL_LINE_TRIPPED, 'TRIPPED'
    elif status_raw == 'IN_SERVICE':
        status_col, status_disp = COL_UNIT_ONLINE, 'IN SERVICE'
    else:
        status_col, status_disp = COL_TEXT_DIM, status_raw
    status_rect = font.get_rect(status_disp, size=sz)
    font.render_to(surf, (x + w - pad - status_rect.width, _ry(5)), status_disp, status_col, size=sz)

    if show_btn:
        if line_status == 'IN_SERVICE':
            btn_label  = '[ T ] TRIP'
            border_col = COL_ALARM_CRIT if cmd_active else COL_PANEL_BORDER
            text_col   = COL_ALARM_CRIT
        else:
            btn_label  = '[ C ] CLOSE'
            border_col = COL_UNIT_ONLINE if cmd_active else COL_PANEL_BORDER
            text_col   = COL_UNIT_ONLINE

        btn_h    = rh - 2
        btn_w    = w - pad * 2
        btn_rect = pygame.Rect(x + pad, _ry(6) - 1, btn_w, btn_h)
        pygame.draw.rect(surf, COL_PANEL_BG, btn_rect)
        pygame.draw.rect(surf, border_col, btn_rect, 1)

        lbl_rect = font.get_rect(btn_label, size=sz)
        lx = x + pad + (btn_w - lbl_rect.width) // 2
        font.render_to(surf, (lx, _ry(6)), btn_label, text_col, size=sz)


def _draw_cmd_row(
    surf, font, x: int, w: int, pad: int, rh: int, sz: int, row_y: int,
    show_start: bool, show_stop: bool, show_transition: bool,
    unit_state: str, cmd_active: bool,
) -> None:
    """Draw the START/STOP button or transition status line at row_y."""
    if show_start:
        label      = '[ START  S ]'
        border_col = COL_UNIT_ONLINE if cmd_active else COL_PANEL_BORDER
        text_col   = COL_UNIT_ONLINE
    elif show_stop:
        label      = '[ STOP  X ]'
        border_col = COL_ALARM_CRIT if cmd_active else COL_PANEL_BORDER
        text_col   = COL_ALARM_CRIT
    elif show_transition:
        status = 'starting…' if unit_state == 'STARTING' else 'shutting down…'
        font.render_to(surf, (x + pad, row_y), status, COL_TEXT_DIM, size=sz)
        return
    else:
        return

    btn_h = rh - 2
    btn_w = w - pad * 2
    btn_rect = pygame.Rect(x + pad, row_y - 1, btn_w, btn_h)
    pygame.draw.rect(surf, COL_PANEL_BG, btn_rect)
    pygame.draw.rect(surf, border_col, btn_rect, 1)

    lbl_rect = font.get_rect(label, size=sz)
    lx = x + pad + (btn_w - lbl_rect.width) // 2
    font.render_to(surf, (lx, row_y), label, text_col, size=sz)


def _draw_mode_row(
    surf, font, x: int, w: int, pad: int, rh: int, sz: int, row_y: int,
    dispatch_mode: str, mode_cmd_active: bool,
) -> None:
    """Draw the AUTO/MANUAL dispatch-mode toggle button at row_y. AUTO
    means the unit is following its Phase 1 planned schedule; MANUAL means
    it holds whatever target the player (or AGC) last set. Pressing the
    button while MANUAL returns the unit to AUTO — there is no button to
    leave AUTO, since setting a target manually (Target field / digit keys)
    already does that."""
    is_auto  = dispatch_mode == 'AUTO'
    label    = '[ AUTO ]' if is_auto else '[ MANUAL   M ]'
    text_col = COL_UNIT_ONLINE if is_auto else COL_ALARM_WARN
    border_col = text_col if mode_cmd_active else COL_PANEL_BORDER

    btn_h = rh - 2
    btn_w = w - pad * 2
    btn_rect = pygame.Rect(x + pad, row_y - 1, btn_w, btn_h)
    pygame.draw.rect(surf, COL_PANEL_BG, btn_rect)
    pygame.draw.rect(surf, border_col, btn_rect, 1)

    lbl_rect = font.get_rect(label, size=sz)
    lx = x + pad + (btn_w - lbl_rect.width) // 2
    font.render_to(surf, (lx, row_y), label, text_col, size=sz)
