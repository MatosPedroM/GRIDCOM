"""
src/display/context.py

Unit context overlay for GRIDCOM.

draw_unit_context() renders a fixed-position panel at the top-left of the
canvas surface when a generation unit is selected. Pure drawing function —
all state (selection, input buffer) is owned by Renderer.
"""

from __future__ import annotations

import pygame
import pygame.freetype

from display.palette import (
    COL_PANEL_BG, COL_PANEL_BORDER,
    COL_TEXT_PRIMARY, COL_TEXT_VALUE, COL_TEXT_DIM, COL_TEXT_HEADING,
    COL_UNIT_ONLINE, COL_UNIT_STARTING, COL_UNIT_SHUTDOWN, COL_UNIT_OFFLINE,
    COL_CONTEXT_FIELD_BG, COL_CONTEXT_FIELD_ACTIVE, COL_CONTEXT_CURSOR,
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
    """
    x   = CONTEXT_OVERLAY_X
    y   = CONTEXT_OVERLAY_Y
    w   = CONTEXT_OVERLAY_W
    pad = CONTEXT_OVERLAY_PAD
    sz  = FONT_SIZE_CONTEXT

    is_dispatchable = unit_state in ('ONLINE', 'STARTING', 'SHUTDOWN')
    n_rows  = 4 if is_dispatchable else 3
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

    else:
        # ── Row 1: Not dispatchable ───────────────────────────────────────────
        font.render_to(surf, (x + pad, _ry(1)),
                       '(unit not dispatchable)', COL_TEXT_DIM, size=sz)
