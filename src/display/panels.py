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
    COL_METER_BG, COL_METER_TICK, COL_FORECAST_CUR_BG,
    COL_UNIT_ONLINE, COL_UNIT_STARTING, COL_UNIT_OFFLINE,
    COL_UNIT_TRIPPED, COL_UNIT_SHUTDOWN,
    COL_ALARM_CRIT, COL_ALARM_WARN, COL_ALARM_INFO, COL_ALARM_TUTOR, COL_ALARM_ACK,
    COL_UNIT_COAL, COL_UNIT_CCGT, COL_UNIT_NUCLEAR,
    COL_UNIT_HYDRO, COL_UNIT_WIND, COL_UNIT_SOLAR,
    COL_FORECAST_DEMAND, COL_FORECAST_NETLOAD, COL_FORECAST_NETDEMAND,
)
from simulation.constants import (
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


def _header(surf: pygame.Surface, font: pygame.freetype.Font, label: str,
            font_scale: float = 1.0) -> None:
    hh  = int(_HEADER_H * font_scale)
    pad = int(_PAD      * font_scale)
    font.render_to(surf, (pad, max(1, int(4 * font_scale))), label, COL_TEXT_HEADING,
                   size=int(FONT_SIZE_PANEL * font_scale))
    pygame.draw.line(surf, COL_PANEL_BORDER,
                     (0, hh - 1), (surf.get_width(), hh - 1), 1)


def _row_y(row: int, font_scale: float = 1.0) -> int:
    hh = int(_HEADER_H * font_scale)
    rh = int(_ROW_H    * font_scale)
    return hh + row * rh + max(1, int(2 * font_scale))


def _bar(surf: pygame.Surface, x: int, y: int, w: int, fill_frac: float,
         col_fill: tuple, col_bg: tuple = COL_METER_BG,
         bar_h: int = _BAR_H) -> None:
    pygame.draw.rect(surf, col_bg,    pygame.Rect(x, y, w, bar_h))
    filled = max(0, min(w, int(w * fill_frac)))
    if filled > 0:
        pygame.draw.rect(surf, col_fill, pygame.Rect(x, y, filled, bar_h))


# ── Panel 1 — Frequency ────────────────────────────────────────────────────────

def draw_frequency_panel(
    surf:         pygame.Surface,
    font:         pygame.freetype.Font,
    blink_on:     bool,
    state=None,
    paused:       bool  = False,
    freq_history=None,
    font_scale:   float = 1.0,
) -> None:
    """Frequency panel: large Hz readout, analog bar, trend/clock line, history plot."""

    freq_hz: float = state.frequency_hz    if state else 49.85
    trend:   str   = state.frequency_trend if state else 'FALLING'

    _fill_panel(surf)
    _right_border(surf)
    _header(surf, font, 'FREQUENCY', font_scale)

    fs  = font_scale
    w   = surf.get_width()
    h   = surf.get_height()
    sp  = int(FONT_SIZE_PANEL       * fs)
    sl  = int(FONT_SIZE_PANEL_LARGE * fs)
    hh  = int(_HEADER_H * fs)
    pad = int(_PAD      * fs)
    bh  = max(2, int(_BAR_H * fs))

    def _freq_col(f: float) -> tuple:
        if f < 49.0 or f > 51.0:
            return COL_FREQ_CRITICAL
        if not (F_ALERT_LOW <= f <= F_ALERT_HIGH):
            return COL_FREQ_ALERT
        return COL_FREQ_NOMINAL

    col = _freq_col(freq_hz)

    hz_str = f'{freq_hz:.2f} Hz'
    rect = font.get_rect(hz_str, size=sl)
    tx = (w - rect.width) // 2
    font.render_to(surf, (tx, hh + max(1, int(6 * fs))), hz_str, col, size=sl)

    bar_y = hh + int(48 * fs)
    bar_x = pad
    bar_w = w - pad * 2

    def _fill_frac(f: float) -> float:
        return (f - 45.0) / 10.0

    _bar(surf, bar_x, bar_y, bar_w, _fill_frac(freq_hz), col, bar_h=bh)

    cx = bar_x + bar_w // 2
    pygame.draw.line(surf, COL_METER_TICK,
                     (cx, bar_y - max(1, int(3 * fs))),
                     (cx, bar_y + bh + max(1, int(2 * fs))), 1)

    label_y = bar_y + bh + max(1, int(4 * fs))
    for hz_val, label in [(45.0, '45'), (50.0, '50'), (55.0, '55')]:
        lx = bar_x + int(_fill_frac(hz_val) * bar_w)
        rect = font.get_rect(label, size=sp)
        lx = max(bar_x, min(bar_x + bar_w - rect.width, lx - rect.width // 2))
        font.render_to(surf, (lx, label_y), label, COL_TEXT_DIM, size=sp)

    # Trend + clock share a single row to leave more vertical room for the plot below.
    status_y = label_y + max(8, int(14 * fs))
    trend_col = COL_TEXT_DIM if trend == 'STABLE' else col
    t_str = '▲ RISING' if trend == 'RISING' else ('▼ FALLING' if trend == 'FALLING' else '— STABLE')
    font.render_to(surf, (pad, status_y), t_str, trend_col, size=sp)

    if state is not None:
        hr = int(state.sim_hour) % 24
        mn = int((state.sim_hour % 1.0) * 60)
        clock_str = f'{hr:02d}:{mn:02d}'
        if paused:
            clock_str += '  PAUSED'
        clock_col = COL_TEXT_WARN if paused else COL_TEXT_SECONDARY
        crect = font.get_rect(clock_str, size=sp)
        font.render_to(surf, (w - pad - crect.width, status_y), clock_str, clock_col, size=sp)

    # ── Frequency history — bottom-to-top strip chart, newest sample nearest the bar ──
    if freq_history:
        plot_top    = status_y + max(10, int(18 * fs))
        plot_bottom = h - pad
        plot_h      = plot_bottom - plot_top
        if plot_h > 4:
            for hz_val in (49.5, 50.0, 50.5):
                lx = bar_x + int(_fill_frac(hz_val) * bar_w)
                pygame.draw.line(surf, COL_METER_TICK,
                                 (lx, plot_top), (lx, plot_bottom), 1)

            samples = list(freq_history)
            n = len(samples)
            max_n = max(n, 1)
            points = []
            for i, f in enumerate(reversed(samples)):  # i=0 → most recent
                x = bar_x + int(max(0.0, min(1.0, _fill_frac(f))) * bar_w)
                y = plot_top + int((i / max_n) * plot_h)
                points.append((x, y))
            if len(points) >= 2:
                pygame.draw.lines(surf, col, False, points, 1)


# ── Panel 2 — Power Balance ────────────────────────────────────────────────────

def draw_power_panel(
    surf:       pygame.Surface,
    font:       pygame.freetype.Font,
    state=None,
    font_scale: float = 1.0,
) -> None:
    """Power balance panel: generation, load, imbalance, reserves, inertia, losses, regulation band."""

    gen_mw    = state.total_generation_mw  if state else 3420.0
    load_mw   = state.total_load_mw        if state else 3380.0
    bal_mw    = state.net_imbalance_mw     if state else 40.0
    spin_mw   = state.spinning_reserve_mw  if state else 640.0
    inertia_h = state.system_inertia_h     if state else 4.8
    losses_mw = state.losses_mw            if state else 85.0
    agc_cur   = state.agc_current_mw       if state else 40.0
    agc_max   = state.agc_max_mw           if state else 65.0
    agc_min   = state.agc_min_mw           if state else 6.5

    _fill_panel(surf)
    _right_border(surf)
    _header(surf, font, 'POWER BALANCE', font_scale)

    fs    = font_scale
    sp    = int(FONT_SIZE_PANEL * fs)
    pad   = int(_PAD * fs)

    rows: list[tuple[str, str, tuple]] = [
        ('GEN',      f'{gen_mw:,.0f} MW',    COL_TEXT_VALUE if gen_mw > 0 else COL_TEXT_DIM),
        ('LOAD',     f'{load_mw:,.0f} MW',   COL_TEXT_PRIMARY),
        ('BAL',      f'{bal_mw:+,.0f} MW',   COL_TEXT_GOOD if bal_mw >= 0 else COL_TEXT_CRIT),
        ('SPIN RES', f'{spin_mw:,.0f} MW',   COL_TEXT_SECONDARY),
        ('INERTIA',  f'{inertia_h:.1f} s',   COL_TEXT_SECONDARY),
        ('LOSSES',   f'{losses_mw:.1f} MW',  COL_TEXT_DIM),
    ]

    lbl_x = pad
    val_x = surf.get_width() - pad
    for i, (lbl, val, col) in enumerate(rows):
        y = _row_y(i, fs)
        font.render_to(surf, (lbl_x, y), lbl, COL_TEXT_SECONDARY, size=sp)
        rect = font.get_rect(val, size=sp)
        font.render_to(surf, (val_x - rect.width, y), val, col, size=sp)

    # ── Regulation band section ──────────────────────────────────────────────
    rh  = int(_ROW_H * fs)
    bh  = max(2, int(_BAR_H * fs))
    w   = surf.get_width()

    # Divider below LOSSES row
    div_y = _row_y(len(rows), fs) - max(2, int(4 * fs))
    pygame.draw.line(surf, COL_PANEL_BORDER, (pad, div_y), (w - pad, div_y), 1)

    # Sub-header
    sub_y = div_y + max(2, int(3 * fs))
    font.render_to(surf, (lbl_x, sub_y), 'REG BAND', COL_TEXT_HEADING, size=sp)

    # Three rows: REG MIN, REG NOW, REG MAX
    has_agc = agc_max > 0.0

    def _reg_val(v: float) -> str:
        return f'{v:.1f} MW' if has_agc else '--'

    band_range = max(agc_max - agc_min, 1.0)
    headroom_up = agc_max - agc_cur
    headroom_dn = agc_cur - agc_min
    margin = min(headroom_up, headroom_dn) / band_range if has_agc else 0.0
    reg_col = COL_TEXT_GOOD if margin >= 0.20 else (COL_TEXT_WARN if margin >= 0.05 else COL_TEXT_CRIT)

    reg_rows: list[tuple[str, str, tuple]] = [
        ('REG MIN', _reg_val(agc_min), COL_TEXT_DIM),
        ('REG NOW', _reg_val(agc_cur), reg_col),
        ('REG MAX', _reg_val(agc_max), COL_TEXT_SECONDARY),
    ]
    base_y = sub_y + rh
    for j, (lbl, val, col) in enumerate(reg_rows):
        y = base_y + j * rh
        font.render_to(surf, (lbl_x, y), lbl, COL_TEXT_SECONDARY, size=sp)
        rect = font.get_rect(val, size=sp)
        font.render_to(surf, (val_x - rect.width, y), val, col, size=sp)

    # Horizontal regulation band bar
    bar_x = pad
    bar_w = w - pad * 2
    bar_y = base_y + len(reg_rows) * rh + max(2, int(3 * fs))
    pygame.draw.rect(surf, COL_METER_BG, pygame.Rect(bar_x, bar_y, bar_w, bh))

    if has_agc and agc_max > 0.0:
        # Available band: min to max (highlighted)
        min_px = int(agc_min / agc_max * bar_w)
        pygame.draw.rect(surf, COL_TEXT_DIM,
                         pygame.Rect(bar_x + min_px, bar_y, bar_w - min_px, bh))
        # Filled: min to current
        cur_frac = max(0.0, min(1.0, (agc_cur - agc_min) / band_range))
        fill_w = int((bar_w - min_px) * cur_frac)
        if fill_w > 0:
            pygame.draw.rect(surf, reg_col,
                             pygame.Rect(bar_x + min_px, bar_y, fill_w, bh))
        # Tick at current
        cur_px = bar_x + int(agc_cur / agc_max * bar_w)
        pygame.draw.line(surf, reg_col,
                         (cur_px, bar_y - max(1, int(2 * fs))),
                         (cur_px, bar_y + bh + max(1, int(1 * fs))), 1)


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
    font_scale: float = 1.0,
) -> None:
    """Unit dispatch panel: full unit fleet as a multi-column grid, state/bar/MW per unit."""

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
    _header(surf, font, 'UNIT DISPATCH', font_scale)

    fs   = font_scale
    sp   = int(FONT_SIZE_PANEL * fs)
    hh   = int(_HEADER_H * fs)
    rh   = max(1, int(_ROW_H * fs))
    bh   = max(2, int(_BAR_H * fs))
    pad  = int(_PAD * fs)

    w = surf.get_width()
    h = surf.get_height()

    rows_per_col = max(1, (h - hh) // rh)
    total        = len(units)
    num_cols     = max(1, -(-total // rows_per_col))  # ceil division
    col_w        = w // num_cols

    lbl_x_off = 0
    sta_x_off = int(48 * fs)
    bar_x_off = sta_x_off + int(22 * fs)
    bar_w     = max(4, int(28 * fs))
    mw_x_off  = bar_x_off + bar_w + int(4 * fs)

    for i, (lbl, ust, out, rated, spct) in enumerate(units):
        col_i = i // rows_per_col
        row_i = i % rows_per_col
        cx    = col_i * col_w
        y     = _row_y(row_i, fs)

        col  = _STATE_COL.get(ust, COL_TEXT_DIM)
        abbr = _STATE_ABBREV.get(ust, '???')

        col_end = cx + col_w - pad

        font.render_to(surf, (cx + pad + lbl_x_off, y), lbl, COL_TEXT_PRIMARY, size=sp)
        font.render_to(surf, (cx + pad + sta_x_off, y), abbr, col, size=sp)

        bar_x = cx + pad + bar_x_off
        if ust == 'STARTING':
            _bar(surf, bar_x, y + 1, bar_w, spct / 100.0, COL_UNIT_STARTING, bar_h=bh)
        elif ust == 'ONLINE':
            frac = out / rated if rated > 0 else 0.0
            _bar(surf, bar_x, y + 1, bar_w, frac, col, bar_h=bh)
        else:
            _bar(surf, bar_x, y + 1, bar_w, 0.0, COL_METER_BG, bar_h=bh)

        if ust == 'STARTING':
            mw_str = f'{spct:.0f}%'
            mw_col = COL_UNIT_STARTING
        elif ust == 'ONLINE':
            mw_str = f'{out:.0f}'
            mw_col = COL_TEXT_PRIMARY
        else:
            mw_str = ''
            mw_col = COL_TEXT_DIM

        if mw_str:
            rect = font.get_rect(mw_str, size=sp)
            font.render_to(surf, (col_end - rect.width, y), mw_str, mw_col, size=sp)

    # Column separators
    for c in range(1, num_cols):
        sep_x = c * col_w
        pygame.draw.line(surf, COL_PANEL_BORDER, (sep_x, hh), (sep_x, h), 1)


# ── Panel 4 — Alarm Feed ───────────────────────────────────────────────────────

_ALARM_DOT_COL: dict[str, tuple] = {
    'CRITICAL': COL_ALARM_CRIT,
    'WARNING':  COL_ALARM_WARN,
    'INFO':     COL_ALARM_INFO,
    'TUTOR':    COL_ALARM_TUTOR,
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
    font_scale: float = 1.0,
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
    _header(surf, font, 'ALARMS', font_scale)

    fs   = font_scale
    sp   = int(FONT_SIZE_PANEL * fs)
    hh   = int(_HEADER_H * fs)
    rh   = max(1, int(_ROW_H * fs))
    pad  = int(_PAD * fs)

    w            = surf.get_width()
    visible_rows = max(1, (surf.get_height() - hh) // rh)
    total        = len(alarms)
    start        = max(0, min(scroll_row, max(0, total - visible_rows)))

    dot_x  = pad
    pri_x  = dot_x + int(12 * fs)
    time_x = pri_x + int(34 * fs)
    msg_x  = time_x + int(40 * fs)

    for i, (pri, ts, msg, acked) in enumerate(alarms[start:start + visible_rows]):
        y = _row_y(i, fs)

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
        font.render_to(surf, (dot_x,  y), dot_sym,  pri_col,         size=sp)
        font.render_to(surf, (pri_x,  y), pri[:4],  pri_col,         size=sp)
        font.render_to(surf, (time_x, y), ts,        COL_TEXT_DIM,    size=sp)
        font.render_to(surf, (msg_x,  y), msg,       msg_col,         size=sp)

    hint = '[A] ACK  [AA] ALL'
    rect = font.get_rect(hint, size=sp)
    font.render_to(surf, (w - rect.width - pad, max(1, int(4 * fs))),
                   hint, COL_TEXT_DIM, size=sp)


# ── Generation Mix panel ───────────────────────────────────────────────────────

_FUEL_ORDER = ('NUCLEAR', 'COAL', 'CCGT', 'HYDRO', 'HYDRO_ROR', 'HYDRO_PUMP', 'WIND', 'SOLAR')

_FUEL_LABELS = {
    'NUCLEAR':   'NUC',
    'COAL':      'COAL',
    'CCGT':      'CCGT',
    'HYDRO':     'HYD',
    'HYDRO_ROR': 'ROR',
    'HYDRO_PUMP':'PMP',
    'WIND':      'WIND',
    'SOLAR':     'SOL',
}

_FUEL_COLOURS = {
    'NUCLEAR':   COL_UNIT_NUCLEAR,
    'COAL':      COL_UNIT_COAL,
    'CCGT':      COL_UNIT_CCGT,
    'HYDRO':     COL_UNIT_HYDRO,
    'HYDRO_ROR': COL_UNIT_HYDRO,
    'HYDRO_PUMP':COL_UNIT_HYDRO,
    'WIND':      COL_UNIT_WIND,
    'SOLAR':     COL_UNIT_SOLAR,
}

# Public aliases — reused by display/planning_panels.py so fuel grouping/
# colours/labels stay single-sourced (CLAUDE.md Rule 2) instead of duplicated.
FUEL_ORDER   = _FUEL_ORDER
FUEL_LABELS  = _FUEL_LABELS
FUEL_COLOURS = _FUEL_COLOURS

_FALLBACK_MIX = {
    'NUCLEAR': 0.0,
    'COAL':    0.0,
    'CCGT':    0.0,
    'HYDRO':   0.0,
    'WIND':    0.0,
    'SOLAR':   0.0,
}


def draw_genmix_panel(
    surf:       pygame.Surface,
    font:       pygame.freetype.Font,
    state,
    font_scale: float = 1.0,
) -> None:
    """Generation mix panel: one row per active fuel type, MW + % + mini bar."""

    mix: dict = state.gen_mix_mw if state is not None else _FALLBACK_MIX
    total_mw = sum(mix.values())

    _fill_panel(surf)
    _header(surf, font, 'GEN MIX', font_scale)
    _right_border(surf)

    fs  = font_scale
    sp  = int(FONT_SIZE_PANEL * fs)
    pad = int(_PAD * fs)
    w   = surf.get_width()

    label_x = pad
    pct_end = w - pad

    for i, fuel in enumerate(_FUEL_ORDER):
        mw = mix.get(fuel, 0.0)
        if mw <= 0.0 and state is not None:
            continue
        y   = _row_y(i, fs)
        col = _FUEL_COLOURS.get(fuel, COL_TEXT_SECONDARY)

        lbl = _FUEL_LABELS.get(fuel, fuel[:4])
        font.render_to(surf, (label_x, y), lbl, col, size=sp)

        if state is not None:
            mw_str  = f'{mw:.0f}'
            pct     = (mw / total_mw * 100.0) if total_mw > 0.0 else 0.0
            pct_str = f'{pct:.0f}%'
        else:
            mw_str  = '---'
            pct_str = '--%'

        pct_rect = font.get_rect(pct_str, size=sp)
        pct_x    = pct_end - pct_rect.width
        mw_rect  = font.get_rect(mw_str, size=sp)
        mw_x     = pct_x - int(6 * fs) - mw_rect.width

        font.render_to(surf, (mw_x,  y), mw_str,  COL_TEXT_VALUE,     size=sp)
        font.render_to(surf, (pct_x, y), pct_str, COL_TEXT_SECONDARY, size=sp)


# ── Forecast Load panel ────────────────────────────────────────────────────────

def draw_forecast_panel(surf: pygame.Surface, font: pygame.freetype.Font, state,
                        font_scale: float = 1.0) -> None:
    """
    Draw the Forecast panel in the instrument strip.

    Four-column scrolling table: TIME | LOAD | WIND | SOLAR.
    Wind and solar show '--' when no units are active for the shift.
    Current time slot is highlighted; window auto-scrolls (2 past rows visible).
    """
    _fill_panel(surf)
    _right_border(surf)
    _header(surf, font, 'FORECAST', font_scale)

    if state is None:
        return

    demand_fc = state.demand_forecast_mw
    if not demand_fc:
        return

    fs  = font_scale
    sp  = int(FONT_SIZE_PANEL * fs)
    pad = int(_PAD * fs)
    hh  = int(_HEADER_H * fs)
    rh  = int(_ROW_H * fs)
    w   = surf.get_width()
    h   = surf.get_height()

    # Column right-edge x positions. TIME gets a fixed width sized to its content
    # ("00:00"); LOAD/WIND/SOLAR split the remaining width evenly, right-aligned.
    col_time_x   = pad
    time_col_w   = font.get_rect('00:00', size=sp).width + int(8 * fs)
    remaining_w  = w - pad - time_col_w
    col_w        = remaining_w // 3
    col_load_x   = pad + time_col_w + col_w
    col_wind_x   = col_load_x + col_w
    col_solar_x  = w - pad

    # Aggregate wind and solar forecasts by hour
    wind_by_hour: dict = {}
    for unit_data in state.wind_forecast_mw.values():
        for slot_h, mw in unit_data.items():
            wind_by_hour[slot_h] = wind_by_hour.get(slot_h, 0.0) + mw
    solar_by_hour: dict = {}
    for unit_data in state.solar_forecast_mw.values():
        for slot_h, mw in unit_data.items():
            solar_by_hour[slot_h] = solar_by_hour.get(slot_h, 0.0) + mw
    has_wind  = bool(wind_by_hour)
    has_solar = bool(solar_by_hour)

    # Column header row
    col_hdr_y = hh + max(1, int(2 * fs))
    font.render_to(surf, (col_time_x, col_hdr_y), 'TIME', COL_TEXT_HEADING, size=sp)
    for hdr_lbl, cx in (('LOAD', col_load_x), ('WIND', col_wind_x), ('SOLAR', col_solar_x)):
        r = font.get_rect(hdr_lbl, size=sp)
        font.render_to(surf, (cx - r.width, col_hdr_y), hdr_lbl, COL_TEXT_HEADING, size=sp)

    # Horizontal divider under column headers
    div_y = hh + rh - max(1, int(2 * fs))
    pygame.draw.line(surf, COL_PANEL_BORDER, (0, div_y), (w, div_y), 1)

    # Vertical column separators
    sep_bottom = h - pad
    for sep_x in (col_load_x + pad // 2, col_wind_x + pad // 2):
        pygame.draw.line(surf, COL_PANEL_BORDER, (sep_x, div_y), (sep_x, sep_bottom), 1)

    slots    = sorted(demand_fc.items())
    cur_hour = state.sim_hour

    # Current slot: last slot at or before cur_hour
    cur_idx = 0
    for i, (slot_h, _) in enumerate(slots):
        if slot_h <= cur_hour:
            cur_idx = i

    # Visible window: up to 2 past rows + current + future rows filling panel
    table_top = hh + rh
    max_rows  = max(1, (h - table_top - pad) // rh)
    past_rows = min(2, cur_idx)
    start_idx = cur_idx - past_rows
    visible   = slots[start_idx: start_idx + max_rows]

    for row_i, (slot_hour, load_mw) in enumerate(visible):
        row_y   = table_top + row_i * rh + max(1, int(2 * fs))
        is_cur  = (slot_hour == slots[cur_idx][0])
        is_past = (slot_hour < cur_hour - 0.25)

        if is_cur:
            pygame.draw.rect(surf, COL_FORECAST_CUR_BG,
                             pygame.Rect(1, row_y - max(1, int(2 * fs)), w - 2, rh))

        col = (COL_TEXT_PRIMARY   if is_cur  else
               COL_TEXT_DIM       if is_past else
               COL_TEXT_SECONDARY)

        # TIME column — left-aligned
        total_min = int(round(slot_hour * 60))
        time_str  = f'{total_min // 60:02d}:{total_min % 60:02d}'
        font.render_to(surf, (col_time_x, row_y), time_str, col, size=sp)

        # LOAD column — right-aligned
        load_str  = f'{load_mw:.0f}'
        load_rect = font.get_rect(load_str, size=sp)
        font.render_to(surf, (col_load_x - load_rect.width, row_y), load_str, col, size=sp)

        # WIND column — right-aligned
        wind_val  = wind_by_hour.get(slot_hour)
        wind_str  = f'{wind_val:.0f}' if (has_wind and wind_val is not None) else '--'
        wind_rect = font.get_rect(wind_str, size=sp)
        font.render_to(surf, (col_wind_x - wind_rect.width, row_y), wind_str, col, size=sp)

        # SOLAR column — right-aligned
        solar_val  = solar_by_hour.get(slot_hour)
        solar_str  = f'{solar_val:.0f}' if (has_solar and solar_val is not None) else '--'
        solar_rect = font.get_rect(solar_str, size=sp)
        font.render_to(surf, (col_solar_x - solar_rect.width, row_y), solar_str, col, size=sp)
