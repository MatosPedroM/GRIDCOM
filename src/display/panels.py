"""
src/display/panels.py

Instrument strip panel drawing functions for GRIDCOM.

The instrument strip occupies the bottom 236px of the 1920×1080 native surface.
It is divided into four panels defined by constants in simulation/constants.py.

Each function receives the panel's subsurface (already correctly positioned)
and draws its content independently.

When state=None the panels render from static fallback values so the window
still opens correctly without a running simulation.
"""

from __future__ import annotations

import pygame
import pygame.freetype

from display.palette import (
    COL_PANEL_BG, COL_PANEL_BORDER,
    COL_TEXT_PRIMARY, COL_TEXT_SECONDARY, COL_TEXT_DIM, COL_TEXT_VALUE,
    COL_TEXT_HEADING, COL_TEXT_GOOD, COL_TEXT_WARN, COL_TEXT_CRIT,
    COL_FREQ_NOMINAL, COL_FREQ_ALERT, COL_FREQ_CRITICAL,
    COL_METER_BG, COL_METER_TICK,
    COL_UNIT_ONLINE, COL_UNIT_STARTING, COL_UNIT_OFFLINE,
    COL_UNIT_TRIPPED, COL_UNIT_SHUTDOWN,
    COL_ALARM_CRIT, COL_ALARM_WARN, COL_ALARM_INFO, COL_ALARM_ACK,
)
from simulation.constants import (
    STRIP_HEIGHT,
    FONT_SIZE_PANEL, FONT_SIZE_PANEL_LARGE,
    F_ALERT_LOW, F_ALERT_HIGH, F_CRITICAL_LOW, F_CRITICAL_HIGH,
)


# ── Shared helpers ─────────────────────────────────────────────────────────────

_HEADER_H:  int = 20    # px — panel header row height
_PAD:       int = 6     # px — horizontal text padding
_ROW_H:     int = 18    # px — unit/alarm row height
_BAR_H:     int = 8     # px — progress/loading bar height


def _fill_panel(surf: pygame.Surface) -> None:
    surf.fill(COL_PANEL_BG)


def _right_border(surf: pygame.Surface) -> None:
    w = surf.get_width()
    pygame.draw.line(surf, COL_PANEL_BORDER, (w - 1, 0), (w - 1, surf.get_height() - 1), 1)


def _header(surf: pygame.Surface, font: pygame.freetype.Font, label: str) -> None:
    font.render_to(surf, (_PAD, 4), label, COL_TEXT_HEADING, size=FONT_SIZE_PANEL)
    pygame.draw.line(surf, COL_PANEL_BORDER,
                     (0, _HEADER_H - 1), (surf.get_width(), _HEADER_H - 1), 1)


def _row_y(row: int) -> int:
    return _HEADER_H + row * _ROW_H + 2


def _bar(surf: pygame.Surface, x: int, y: int, w: int, fill_frac: float,
         col_fill: tuple, col_bg: tuple = COL_METER_BG) -> None:
    pygame.draw.rect(surf, col_bg,    pygame.Rect(x, y, w, _BAR_H))
    filled = max(0, min(w, int(w * fill_frac)))
    if filled > 0:
        pygame.draw.rect(surf, col_fill, pygame.Rect(x, y, filled, _BAR_H))


# ── Panel 1 — Frequency ────────────────────────────────────────────────────────

def draw_frequency_panel(
    surf:     pygame.Surface,
    font:     pygame.freetype.Font,
    blink_on: bool,
    state=None,
) -> None:
    """Frequency panel: large Hz readout, analog bar, trend indicator."""

    freq_hz: float = state.frequency_hz    if state else 49.85
    trend:   str   = state.frequency_trend if state else 'FALLING'

    _fill_panel(surf)
    _right_border(surf)
    _header(surf, font, 'FREQUENCY')

    w = surf.get_width()

    # Colour by frequency band
    if freq_hz < 49.0 or freq_hz > 51.0:
        col = COL_FREQ_CRITICAL
    elif not (F_ALERT_LOW <= freq_hz <= F_ALERT_HIGH):
        col = COL_FREQ_ALERT
    else:
        col = COL_FREQ_NOMINAL

    # Large Hz readout
    hz_str = f'{freq_hz:.3f} Hz'
    rect = font.get_rect(hz_str, size=FONT_SIZE_PANEL_LARGE)
    tx = (w - rect.width) // 2
    font.render_to(surf, (tx, _HEADER_H + 6), hz_str, col, size=FONT_SIZE_PANEL_LARGE)

    # Analog bar: 45-55 Hz maps to 0-100% width
    bar_y = _HEADER_H + 48
    bar_x = _PAD
    bar_w = w - _PAD * 2
    fill_frac = (freq_hz - 45.0) / 10.0
    _bar(surf, bar_x, bar_y, bar_w, fill_frac, col)

    # Centre tick mark (50 Hz)
    cx = bar_x + bar_w // 2
    pygame.draw.line(surf, COL_METER_TICK, (cx, bar_y - 3), (cx, bar_y + _BAR_H + 2), 1)

    # Tick labels
    label_y = bar_y + _BAR_H + 4
    for hz_val, label in [(49.5, '49.5'), (50.0, '50.0'), (50.5, '50.5')]:
        lx = bar_x + int((hz_val - 45.0) / 10.0 * bar_w)
        font.render_to(surf, (lx - 10, label_y), label, COL_TEXT_DIM, size=FONT_SIZE_PANEL)

    # Trend indicator
    trend_col = COL_TEXT_DIM if trend == 'STABLE' else col
    if trend == 'RISING':
        t_str = '▲ RISING'
    elif trend == 'FALLING':
        t_str = '▼ FALLING'
    else:
        t_str = '— STABLE'
    trend_y = label_y + 14
    font.render_to(surf, (_PAD, trend_y), t_str, trend_col, size=FONT_SIZE_PANEL)


# ── Panel 2 — Power Balance ────────────────────────────────────────────────────

def draw_power_panel(
    surf:  pygame.Surface,
    font:  pygame.freetype.Font,
    state=None,
) -> None:
    """Power balance panel: generation, load, imbalance, reserves, inertia, losses."""

    gen_mw    = state.total_generation_mw  if state else 3420.0
    load_mw   = state.total_load_mw        if state else 3380.0
    bal_mw    = state.net_imbalance_mw     if state else 40.0
    spin_mw   = state.spinning_reserve_mw  if state else 640.0
    inertia_h = state.system_inertia_h     if state else 4.8
    losses_mw = state.losses_mw            if state else 85.0

    _fill_panel(surf)
    _right_border(surf)
    _header(surf, font, 'POWER BALANCE')

    rows: list[tuple[str, str, tuple]] = [
        ('GEN',      f'{gen_mw:,.0f} MW',    COL_TEXT_VALUE if gen_mw > 0 else COL_TEXT_DIM),
        ('LOAD',     f'{load_mw:,.0f} MW',   COL_TEXT_PRIMARY),
        ('BAL',      f'{bal_mw:+,.0f} MW',   COL_TEXT_GOOD if bal_mw >= 0 else COL_TEXT_CRIT),
        ('SPIN RES', f'{spin_mw:,.0f} MW',   COL_TEXT_SECONDARY),
        ('INERTIA',  f'{inertia_h:.1f} s',   COL_TEXT_SECONDARY),
        ('LOSSES',   f'{losses_mw:,.0f} MW', COL_TEXT_DIM),
    ]

    lbl_x = _PAD
    val_x = surf.get_width() - _PAD
    for i, (lbl, val, col) in enumerate(rows):
        y = _row_y(i)
        font.render_to(surf, (lbl_x, y), lbl, COL_TEXT_SECONDARY, size=FONT_SIZE_PANEL)
        rect = font.get_rect(val, size=FONT_SIZE_PANEL)
        font.render_to(surf, (val_x - rect.width, y), val, col, size=FONT_SIZE_PANEL)


# ── Panel 3 — Unit Dispatch ────────────────────────────────────────────────────

_STATE_COL: dict[str, tuple] = {
    'ONLINE':   COL_UNIT_ONLINE,
    'STARTING': COL_UNIT_STARTING,
    'OFFLINE':  COL_UNIT_OFFLINE,
    'TRIPPED':  COL_UNIT_TRIPPED,
    'SHUTDOWN': COL_UNIT_SHUTDOWN,
}

_STATE_ABBREV: dict[str, str] = {
    'ONLINE':   'ONL',
    'STARTING': 'STA',
    'OFFLINE':  'OFF',
    'TRIPPED':  'TRP',
    'SHUTDOWN': 'SDN',
}

_FALLBACK_UNITS: list[tuple[str, str, float, float, float]] = [
    ('HART-1', 'ONLINE',   680.0, 700.0, 0.0),
    ('HART-2', 'ONLINE',   300.0, 700.0, 0.0),
    ('RVSD-1', 'ONLINE',   900.0, 900.0, 0.0),
    ('RVSD-2', 'OFFLINE',    0.0, 900.0, 0.0),
    ('RVSD-3', 'STARTING',   0.0, 900.0, 45.0),
    ('THNF-1', 'TRIPPED',    0.0, 900.0, 0.0),
    ('THNF-2', 'SHUTDOWN',   0.0, 900.0, 0.0),
    ('ASHG-1', 'ONLINE',   280.0, 400.0, 0.0),
    ('ASHG-2', 'ONLINE',   400.0, 400.0, 0.0),
    ('DUND-1', 'ONLINE',    65.0,  65.0, 0.0),
]


def draw_dispatch_panel(
    surf:       pygame.Surface,
    font:       pygame.freetype.Font,
    blink_on:   bool,
    state,
    grid,
    scroll_row: int,
) -> None:
    """Unit dispatch panel: scrollable list of units with state, bar, and MW output."""

    if state is not None and grid is not None:
        units: list[tuple[str, str, float, float, float]] = []
        for unit in grid.get_active_units():
            lbl  = unit.label
            ust  = state.unit_states.get(lbl, 'OFFLINE')
            out  = state.unit_outputs_mw.get(lbl, 0.0)
            spct = state.unit_start_progress.get(lbl, 0.0) * 100.0
            units.append((lbl, ust, out, unit.rated_mw, spct))
    else:
        units = _FALLBACK_UNITS

    _fill_panel(surf)
    _right_border(surf)
    _header(surf, font, 'UNIT DISPATCH')

    w            = surf.get_width()
    visible_rows = (STRIP_HEIGHT - _HEADER_H) // _ROW_H

    lbl_x  = _PAD
    sta_x  = lbl_x + 56
    bar_x  = sta_x + 30
    bar_w  = 120
    mw_x   = bar_x + bar_w + 6
    mw_end = w - _PAD

    total = len(units)
    start = max(0, min(scroll_row, max(0, total - visible_rows)))

    for i, (lbl, ust, out, rated, spct) in enumerate(units[start:start + visible_rows]):
        y    = _row_y(i)
        col  = _STATE_COL.get(ust, COL_TEXT_DIM)
        abbr = _STATE_ABBREV.get(ust, '???')

        font.render_to(surf, (lbl_x, y), lbl, COL_TEXT_PRIMARY, size=FONT_SIZE_PANEL)
        font.render_to(surf, (sta_x, y), abbr, col, size=FONT_SIZE_PANEL)

        if ust == 'STARTING':
            _bar(surf, bar_x, y + 1, bar_w, spct / 100.0, COL_UNIT_STARTING)
            pct_str = f'{spct:.0f}%'
            font.render_to(surf, (mw_x, y), pct_str, COL_UNIT_STARTING, size=FONT_SIZE_PANEL)
        elif ust == 'ONLINE':
            frac = out / rated if rated > 0 else 0.0
            _bar(surf, bar_x, y + 1, bar_w, frac, col)
            mw_str = f'{out:.0f}/{rated:.0f}'
            rect = font.get_rect(mw_str, size=FONT_SIZE_PANEL)
            font.render_to(surf, (mw_end - rect.width, y), mw_str,
                           COL_TEXT_PRIMARY, size=FONT_SIZE_PANEL)
        else:
            _bar(surf, bar_x, y + 1, bar_w, 0.0, COL_METER_BG)

    if total > visible_rows:
        ind_str = f'↑↓ {start + 1}-{min(start + visible_rows, total)}/{total}'
        rect = font.get_rect(ind_str, size=FONT_SIZE_PANEL)
        font.render_to(surf, (w - rect.width - _PAD, 4),
                       ind_str, COL_TEXT_DIM, size=FONT_SIZE_PANEL)


# ── Panel 4 — Alarm Feed ───────────────────────────────────────────────────────

_ALARM_DOT_COL: dict[str, tuple] = {
    'CRITICAL': COL_ALARM_CRIT,
    'WARNING':  COL_ALARM_WARN,
    'INFO':     COL_ALARM_INFO,
}

_FALLBACK_ALARMS: list[tuple[str, str, str, bool]] = [
    ('CRITICAL', '06:14', 'RVSD-2 TRIPPED — protection operated',   False),
    ('WARNING',  '06:12', 'L07 OVERLOAD 87% — watch thermal limit', True),
    ('INFO',     '06:10', 'Unit start initiated: HART-1',            True),
]


def draw_alarm_panel(
    surf:       pygame.Surface,
    font:       pygame.freetype.Font,
    blink_on:   bool,
    state,
    scroll_row: int,
) -> None:
    """Alarm panel: scrollable alarm list with priority, timestamp, message."""

    if state is not None:
        alarms: list[tuple[str, str, str, bool]] = []
        for a in sorted(state.active_alarms, key=lambda x: x.alarm_id, reverse=True):
            h = int(a.timestamp_min // 60)
            m = int(a.timestamp_min % 60)
            alarms.append((a.priority, f'{h:02d}:{m:02d}', a.message, a.acknowledged))
    else:
        alarms = _FALLBACK_ALARMS

    _fill_panel(surf)
    _header(surf, font, 'ALARMS')

    w            = surf.get_width()
    visible_rows = (STRIP_HEIGHT - _HEADER_H) // _ROW_H
    total        = len(alarms)
    start        = max(0, min(scroll_row, max(0, total - visible_rows)))

    dot_x  = _PAD
    pri_x  = dot_x + 12
    time_x = pri_x + 34
    msg_x  = time_x + 40

    for i, (pri, ts, msg, acked) in enumerate(alarms[start:start + visible_rows]):
        y = _row_y(i)

        pri_col = _ALARM_DOT_COL.get(pri, COL_TEXT_DIM)
        if acked:
            pri_col = COL_ALARM_ACK
            msg_col = COL_TEXT_DIM
        else:
            msg_col = COL_TEXT_PRIMARY
            if not blink_on and pri in ('CRITICAL', 'WARNING'):
                pri_col = COL_METER_BG
                msg_col = COL_TEXT_DIM

        dot_sym = '●' if not acked else '○'
        font.render_to(surf, (dot_x,  y), dot_sym,  pri_col,         size=FONT_SIZE_PANEL)
        font.render_to(surf, (pri_x,  y), pri[:4],  pri_col,         size=FONT_SIZE_PANEL)
        font.render_to(surf, (time_x, y), ts,        COL_TEXT_DIM,    size=FONT_SIZE_PANEL)
        font.render_to(surf, (msg_x,  y), msg,       msg_col,         size=FONT_SIZE_PANEL)

    hint = '[A] ACK  [AA] ALL'
    rect = font.get_rect(hint, size=FONT_SIZE_PANEL)
    font.render_to(surf, (w - rect.width - _PAD, 4),
                   hint, COL_TEXT_DIM, size=FONT_SIZE_PANEL)
