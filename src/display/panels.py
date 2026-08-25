"""
src/display/panels.py

Instrument strip and top-bar panel drawing functions for GRIDCOM.

The instrument strip occupies STRIP_HEIGHT px of the 1920×1080 native surface,
divided into panels defined by constants in simulation/constants.py. The top
bar (draw_topbar_panel) is a separate single-row-pair region above the canvas.
Below the strip sits a blank HINT_GAP_HEIGHT gap and then the HINT_BAR_HEIGHT
shortcut-hint row (drawn directly by Renderer, not a panel function here).

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
    COL_UNIT_ONLINE,
    COL_ALARM_CRIT, COL_ALARM_WARN, COL_ALARM_INFO, COL_ALARM_TUTOR, COL_ALARM_ACK,
    COL_UNIT_COAL, COL_UNIT_CCGT, COL_UNIT_NUCLEAR,
    COL_UNIT_HYDRO, COL_UNIT_WIND, COL_UNIT_SOLAR,
    COL_FORECAST_DEMAND, COL_FORECAST_NETLOAD, COL_FORECAST_NETDEMAND,
)
from simulation.constants import (
    FONT_SIZE_PANEL, FONT_SIZE_PANEL_LARGE,
    F_ALERT_LOW, F_ALERT_HIGH, F_CRITICAL_LOW, F_CRITICAL_HIGH,
    DISPATCH_NUM_COLS, DISPATCH_STATUS_X_OFFSET, DISPATCH_VALUE_X_OFFSET,
    SPEED_PAUSE, SPEED_SLOW, SPEED_NORMAL, SPEED_FAST, SPEED_VERY_FAST,
)


# ── Shared helpers ─────────────────────────────────────────────────────────────

_HEADER_H:  int = 20    # px — panel header row height
_PAD:       int = 6     # px — horizontal text padding
_ROW_H:     int = 22    # px — unit/alarm row height


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


# ── Panel 1 — Frequency ────────────────────────────────────────────────────────

def draw_frequency_panel(
    surf:         pygame.Surface,
    font:         pygame.freetype.Font,
    blink_on:     bool,
    state=None,
    freq_history=None,
    font_scale:   float = 1.0,
) -> None:
    """Frequency panel: large Hz readout and a vertical frequency history
    plot (time top-to-bottom, newest sample nearest the top), full panel
    width. The trend line (RISING/FALLING/STABLE) and the horizontal
    48-53 Hz analog bar were both removed — the vertical plot already
    shows the same range over time, so it sits directly under the Hz
    readout and extends down to fill the rest of the panel. The plot's
    frequency-to-x mapping is centred on 50 Hz (F_NOMINAL), so the 50 Hz
    gridline sits at the panel's horizontal midpoint rather than off to
    one side. The clock/speed readout lives in the topbar
    (draw_topbar_panel), not here."""

    freq_hz: float = state.frequency_hz if state else 49.85

    _fill_panel(surf)
    _right_border(surf)
    _header(surf, font, 'FREQUENCY', font_scale)

    fs  = font_scale
    w   = surf.get_width()
    h   = surf.get_height()
    sl  = int(FONT_SIZE_PANEL_LARGE * fs)
    hh  = int(_HEADER_H * fs)
    pad = int(_PAD      * fs)

    def _freq_col(f: float) -> tuple:
        if f < 49.0 or f > 51.0:
            return COL_FREQ_CRITICAL
        if not (F_ALERT_LOW <= f <= F_ALERT_HIGH):
            return COL_FREQ_ALERT
        return COL_FREQ_NOMINAL

    col = _freq_col(freq_hz)

    hz_str = f'{freq_hz:.2f}'
    rect = font.get_rect(hz_str, size=sl)
    tx = (w - rect.width) // 2
    hz_y = hh + max(1, int(6 * fs))
    font.render_to(surf, (tx, hz_y), hz_str, col, size=sl)

    bar_x = pad
    bar_w = w - pad * 2

    # Centred on 50 Hz (F_NOMINAL): 47.5-52.5 Hz, same 5 Hz span as
    # before but symmetric around nominal instead of offset, so the 50 Hz
    # gridline lands at the panel's horizontal midpoint (bar_x + bar_w/2).
    def _fill_frac(f: float) -> float:
        return (f - 47.5) / 5.0

    # ── Frequency history — vertical strip chart, newest sample nearest
    # the Hz readout, older samples toward the bottom of the panel. ──
    plot_top    = hz_y + rect.height + max(4, int(8 * fs))
    plot_bottom = h - pad
    plot_h      = plot_bottom - plot_top
    if freq_history and plot_h > 4:
        for hz_val in (49.0, 50.0, 51.0):
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

_TOPBAR_GAP:   int = 22   # px — horizontal gap between topbar label/value pairs


_SPEED_LABELS: dict[float, str] = {
    SPEED_PAUSE:     'PAUSE',
    SPEED_SLOW:      'x0.25',
    SPEED_NORMAL:    'x1',
    SPEED_FAST:      'x3',
    SPEED_VERY_FAST: 'x10',
}


def draw_topbar_panel(
    surf:       pygame.Surface,
    font:       pygame.freetype.Font,
    state=None,
    load_rate_history=None,
    speed_mult: float = SPEED_NORMAL,
    font_scale: float = 1.0,
) -> None:
    """Power balance bar plus clock/speed readout: one aligned table,
    row 1 = every field's label, row 2 = every field's value directly
    beneath it. Power Balance fields flow left to right; CLOCK and SPEED
    are right-aligned to the panel edge, the same corner the clock used
    to occupy in the Frequency panel. Spans the full native width above
    the canvas. Framed top and bottom by a green line each — the top
    line sits at the panel's outer edge (below the shift title row
    above it), the bottom line sits flush under the value row rather
    than the panel's outer edge."""

    gen_mw    = state.total_generation_mw  if state else 3420.0
    load_mw   = state.total_load_mw        if state else 3380.0
    bal_mw    = state.net_imbalance_mw     if state else 40.0
    spin_mw   = state.spinning_reserve_mw  if state else 640.0
    inertia_h = state.system_inertia_h     if state else 4.8
    losses_mw = state.losses_mw            if state else 85.0
    q_gen_mvar = state.total_q_generated_mvar if state else 0.0
    q_con_mvar = state.total_q_consumed_mvar  if state else 0.0
    q_bal_mvar = q_gen_mvar - q_con_mvar
    agc_cur   = state.agc_current_mw       if state else 40.0
    agc_max   = state.agc_max_mw           if state else 65.0
    agc_min   = state.agc_min_mw           if state else 6.5
    agc_saturated = state.agc_saturated    if state else False
    load_rate_mw_min = load_rate_history[-1] if load_rate_history else 0.0

    _fill_panel(surf)

    fs   = font_scale
    sp   = int(FONT_SIZE_PANEL * fs)
    pad  = int(_PAD * fs)
    rh   = int(_ROW_H * fs)   # matches the strip panels' row spacing (was a separate, larger topbar-only value)
    gap  = int(_TOPBAR_GAP * fs)

    has_agc = agc_max > 0.0

    def _reg_val(v: float) -> str:
        return f'{v:+.1f} MW' if has_agc else '--'

    # Recentre the regulation band around its own midpoint, so REG DN/UP read
    # as signed room-remaining-in-each-direction and REG NOW reads as
    # position relative to that centre, rather than absolute output levels.
    band_range = max(agc_max - agc_min, 1.0)
    headroom_up = agc_max - agc_cur
    headroom_dn = agc_cur - agc_min
    margin = min(headroom_up, headroom_dn) / band_range if has_agc else 0.0
    reg_col = COL_TEXT_GOOD if margin >= 0.20 else (COL_TEXT_WARN if margin >= 0.05 else COL_TEXT_CRIT)
    reg_now_col = COL_TEXT_CRIT if agc_saturated else reg_col

    center  = (agc_min + agc_max) / 2.0
    reg_dn  = agc_min - center
    reg_up  = agc_max - center
    reg_now = agc_cur - center

    columns: list[tuple[str, str, tuple]] = [
        ('GEN',             f'{gen_mw:,.0f} MW',           COL_TEXT_VALUE if gen_mw > 0 else COL_TEXT_DIM),
        ('LOAD',            f'{load_mw:,.0f} MW',          COL_TEXT_PRIMARY),
        ('BAL',             f'{bal_mw:+,.0f} MW',          COL_TEXT_GOOD if bal_mw >= 0 else COL_TEXT_CRIT),
        ('Q GEN',           f'{q_gen_mvar:,.0f} MVAr',     COL_TEXT_VALUE if q_gen_mvar > 0 else COL_TEXT_DIM),
        ('Q CON',           f'{q_con_mvar:,.0f} MVAr',     COL_TEXT_PRIMARY),
        ('Q BAL',           f'{q_bal_mvar:+,.0f} MVAr',    COL_TEXT_GOOD if q_bal_mvar >= 0 else COL_TEXT_CRIT),
        ('LOAD VAR (/MIN)', f'{load_rate_mw_min:+.1f} MW', COL_TEXT_SECONDARY),
        ('SPIN RES',        f'{spin_mw:,.0f} MW',          COL_TEXT_SECONDARY),
        ('INERTIA',         f'{inertia_h:.1f} s',          COL_TEXT_SECONDARY),
        ('LOSSES',          f'{losses_mw:.1f} MW',         COL_TEXT_DIM),
        ('REG DN',          _reg_val(reg_dn),              COL_TEXT_DIM),
        ('REG NOW',         (_reg_val(reg_now) + ' SAT') if agc_saturated else _reg_val(reg_now), reg_now_col),
        ('REG UP',          _reg_val(reg_up),              COL_TEXT_SECONDARY),
    ]

    row1_y = max(1, int(4 * fs))
    row2_y = row1_y + rh
    x = pad
    for lbl, val, col in columns:
        lbl_rect = font.get_rect(lbl, size=sp)
        val_rect = font.get_rect(val, size=sp)
        col_w = max(lbl_rect.width, val_rect.width)
        font.render_to(surf, (x, row1_y), lbl, COL_TEXT_SECONDARY, size=sp)
        font.render_to(surf, (x, row2_y), val, col, size=sp)
        x += col_w + gap

    # Clock/speed: right-aligned to the panel edge, same corner the clock
    # used to occupy in the Frequency panel before it moved here.
    paused = speed_mult <= SPEED_PAUSE
    if state is not None:
        hr = int(state.sim_hour) % 24
        mn = int((state.sim_hour % 1.0) * 60)
        clock_str = f'{hr:02d}:{mn:02d}'
    else:
        clock_str = '--:--'
    speed_str = _SPEED_LABELS.get(speed_mult, f'x{speed_mult:g}')
    speed_col = COL_TEXT_WARN if paused else COL_TEXT_GOOD

    w = surf.get_width()
    clock_rect = font.get_rect(clock_str, size=sp)
    speed_rect = font.get_rect(speed_str, size=sp)
    right_x = w - pad
    font.render_to(surf, (right_x - clock_rect.width, row1_y), clock_str, COL_TEXT_PRIMARY, size=sp)
    font.render_to(surf, (right_x - speed_rect.width, row2_y), speed_str, speed_col, size=sp)

    # Grid display zone framing: a green strip along the top edge of the
    # topbar, mirroring the bottom border below — the topbar reads as a
    # clearly bounded panel on both edges, not just the bottom.
    pygame.draw.line(surf, COL_PANEL_BORDER, (0, 0), (w, 0), 1)

    # Grid display zone framing: a table-style bottom border flush under
    # the value row, not the topbar surface's outer edge (TOPBAR_HEIGHT
    # leaves leftover blank space below the value row, same reasoning as
    # the strip panels' row layout).
    sep_y = row2_y + rh - 1
    pygame.draw.line(surf, COL_PANEL_BORDER, (0, sep_y), (w, sep_y), 1)


# ── Panel 3 — Unit Dispatch ────────────────────────────────────────────────────

_STATE_ABBREV: dict[str, str] = {
    'STARTING': 'STA',
    'OFFLINE':  'OFF',
    'TRIPPED':  'TRP',
    'SHUTDOWN': 'SDN',
}

# States that count as "out" — the whole row (label, abbreviation, values)
# renders red instead of green. STARTING is not "out": a unit actively
# coming online is still progressing toward service.
_OUT_STATES: frozenset[str] = frozenset({'OFFLINE', 'TRIPPED', 'SHUTDOWN'})

# (label, state, output_mw, rated_mw, start_pct, mode, target_mw,
#  q_actual_mvar, q_target_mvar, agc_enabled)
_FALLBACK_UNITS: list[tuple[str, str, float, float, float, str | None, float, float, float, bool]] = [
    ('HART-1', 'ONLINE',   680.0, 700.0, 0.0, None,  700.0,  120.0,  120.0, False),
    ('HART-2', 'ONLINE',   300.0, 700.0, 0.0, None,  300.0,   80.0,   80.0, False),
    ('RVSD-1', 'ONLINE',   900.0, 900.0, 0.0, None,  900.0,  150.0,  150.0, False),
    ('RVSD-2', 'OFFLINE',    0.0, 900.0, 0.0, None,    0.0,    0.0,    0.0, False),
    ('RVSD-3', 'STARTING',   0.0, 900.0, 45.0, None,   0.0,    0.0,    0.0, False),
    ('THNF-1', 'TRIPPED',    0.0, 900.0, 0.0, None,    0.0,    0.0,    0.0, False),
    ('THNF-2', 'SHUTDOWN',   0.0, 900.0, 0.0, None,    0.0,    0.0,    0.0, False),
    ('ASHG-1', 'ONLINE',   280.0, 400.0, 0.0, None,  245.0,   45.0,   50.0, True),
    ('ASHG-2', 'ONLINE',   400.0, 400.0, 0.0, None,  400.0,   90.0,   90.0, True),
    ('DUND-1', 'ONLINE',    65.0,  65.0, 0.0, None,   65.0,   10.0,   10.0, True),
]


def draw_dispatch_panel(
    surf:       pygame.Surface,
    font:       pygame.freetype.Font,
    blink_on:   bool,
    state,
    grid,
    font_scale: float = 1.0,
) -> None:
    """
    Unit dispatch panel: unit fleet as a fixed-size multi-column grid
    (DISPATCH_NUM_COLS columns, row count capped by panel height), one
    row per unit, sorted alphabetically by label and filling column by
    column (column 1 fills top-to-bottom before column 2 starts, etc.)
    rather than round-robin across columns. Each column starts with a
    'UNIT ST MW MVA' header row before its unit rows (abbreviated further
    than the data fields themselves — 'STAT'/'MVAr' are too wide to fit
    without overlapping the next field at this column width). Columns/
    rows never grow to fit a larger fleet — if the fleet exceeds
    capacity, the last slot shows a '+N MORE' indicator instead of a unit
    row. Row format (ONLINE units): 'LBL  ONL 1000 300' — actual MW
    (4-digit-wide), actual MVAr (3-digit-wide), both right-aligned (so
    the largest unit in the fleet, 1000 MW, never shifts columns out of
    alignment with smaller units) — worst-case 4-digit-MW rows run tight
    against or past the column separator at DISPATCH_NUM_COLS=4, a known
    and accepted tradeoff (see constants.py). The status abbreviation
    encodes
    dispatch mode for ONLINE units — 'AGC' if AGC-participating (takes
    priority), else 'MAN' for MANUAL dispatch, else 'ONL' — while
    OFFLINE/TRIPPED/SHUTDOWN/STARTING keep their own abbreviations
    (OFF/TRP/SDN/STA). The whole row (label, abbreviation, values) renders
    green for ONLINE/STARTING units, red for units that are "out"
    (OFFLINE/TRIPPED/SHUTDOWN) — a drifting/derated unit no longer gets
    its own amber highlight, since colour now encodes in/out-of-service
    status instead. Setpoint (target) values still aren't printed.
    """

    if state is not None and grid is not None:
        units: list[tuple[str, str, float, float, float, str | None, float, float, float, bool]] = []
        for unit in grid.get_active_units():
            lbl    = unit.label
            ust    = state.unit_states.get(lbl, 'OFFLINE')
            out    = state.unit_outputs_mw.get(lbl, 0.0)
            spct   = state.unit_start_progress.get(lbl, 0.0) * 100.0
            mode   = (state.unit_dispatch_modes.get(lbl)
                      if lbl in state.unit_has_schedule else None)
            target = state.unit_targets_mw.get(lbl, 0.0)
            q_act  = state.unit_q_injections_mvar.get(lbl, 0.0)
            q_tgt  = state.unit_q_target_mvar.get(lbl, 0.0)
            agc    = lbl in state.unit_agc_enabled
            units.append((lbl, ust, out, unit.rated_mw, spct, mode, target, q_act, q_tgt, agc))
    else:
        units = _FALLBACK_UNITS

    units = sorted(units, key=lambda u: u[0])

    _fill_panel(surf)
    _right_border(surf)
    _header(surf, font, 'UNIT DISPATCH', font_scale)

    fs   = font_scale
    sp   = int(FONT_SIZE_PANEL * fs)
    hh   = int(_HEADER_H * fs)
    rh   = max(1, int(_ROW_H * fs))
    pad  = int(_PAD * fs)

    w = surf.get_width()
    h = surf.get_height()

    total          = len(units)
    num_cols       = DISPATCH_NUM_COLS
    rows_per_col   = max(1, (h - hh) // rh)  # fixed by panel height, not unit count
    col_w          = w // num_cols
    # Row 0 of every column is the 'UNIT STAT MW MVAr' header, not a unit —
    # unit rows get whatever's left.
    unit_rows_per_col = max(0, rows_per_col - 1)
    capacity           = num_cols * unit_rows_per_col

    # Fixed columns/rows (developer directive) means a large fleet can
    # exceed what's visible. Reserve the last slot for a '+N MORE'
    # indicator rather than silently dropping units off the bottom.
    truncated = total > capacity
    visible   = units[:max(0, capacity - 1)] if truncated else units

    lbl_x_off  = 0
    sta_x_off  = int(DISPATCH_STATUS_X_OFFSET * fs)
    val_x_off  = int(DISPATCH_VALUE_X_OFFSET * fs)   # start of the MW/MVAr value block

    for c in range(num_cols):
        cx = c * col_w
        y  = _row_y(0, fs)
        font.render_to(surf, (cx + pad + lbl_x_off, y), 'UNIT', COL_TEXT_SECONDARY, size=sp)
        font.render_to(surf, (cx + pad + sta_x_off, y), 'ST', COL_TEXT_SECONDARY, size=sp)
        font.render_to(surf, (cx + pad + val_x_off, y), 'MW MVA', COL_TEXT_SECONDARY, size=sp)

    for i, (lbl, ust, out, rated, spct, mode, target, q_act, q_tgt, agc) in enumerate(visible):
        col_i = i // unit_rows_per_col
        row_i = i % unit_rows_per_col + 1  # +1: row 0 is the header
        cx    = col_i * col_w
        y     = _row_y(row_i, fs)

        if ust == 'ONLINE':
            abbr = 'AGC' if agc else ('MAN' if mode == 'MANUAL' else 'ONL')
        else:
            abbr = _STATE_ABBREV.get(ust, '???')

        row_col = COL_TEXT_CRIT if ust in _OUT_STATES else COL_UNIT_ONLINE

        font.render_to(surf, (cx + pad + lbl_x_off, y), lbl, row_col, size=sp)
        font.render_to(surf, (cx + pad + sta_x_off, y), abbr, row_col, size=sp)

        if ust == 'STARTING':
            val_str = f'{spct:.0f}%'
        elif ust == 'ONLINE':
            val_str = f'{out:4.0f} {q_act:3.0f}'
        else:
            val_str = ''

        if val_str:
            val_x = cx + pad + val_x_off
            font.render_to(surf, (val_x, y), val_str, row_col, size=sp)

    if truncated:
        hidden   = total - len(visible)
        more_str = f'+{hidden} MORE'
        col_i    = num_cols - 1
        row_i    = rows_per_col - 1
        cx       = col_i * col_w
        y        = _row_y(row_i, fs)
        font.render_to(surf, (cx + pad, y), more_str, COL_TEXT_DIM, size=sp)

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


def _wrap_text(
    font:      pygame.freetype.Font,
    text:      str,
    size:      int,
    max_width: int,
) -> list[str]:
    """Word-wrap text to fit max_width px at the given font size."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    line = words[0]
    for word in words[1:]:
        candidate = f'{line} {word}'
        if font.get_rect(candidate, size=size).width <= max_width:
            line = candidate
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def draw_alarm_panel(
    surf:       pygame.Surface,
    font:       pygame.freetype.Font,
    blink_on:   bool,
    state,
    scroll_row: int,
    font_scale: float = 1.0,
) -> None:
    """Alarm panel: scrollable alarm list with priority, timestamp, message.
    Alarms with non-empty detail text wrap it onto extra lines beneath the
    message; alarms with no detail render as a single line, as before."""

    if state is not None:
        alarms: list[tuple[str, str, str, bool, str]] = []
        for a in sorted(state.active_alarms, key=lambda x: x.alarm_id, reverse=True):
            h = int(a.timestamp_min // 60)
            m = int(a.timestamp_min % 60)
            alarms.append((a.priority, f'{h:02d}:{m:02d}', a.message, a.acknowledged, a.detail))
    else:
        alarms = [(pri, ts, msg, acked, '') for pri, ts, msg, acked in _FALLBACK_ALARMS]

    _fill_panel(surf)
    _header(surf, font, 'ALARMS', font_scale)

    fs   = font_scale
    sp   = int(FONT_SIZE_PANEL * fs)
    hh   = int(_HEADER_H * fs)
    rh   = max(1, int(_ROW_H * fs))
    pad  = int(_PAD * fs)

    w = surf.get_width()

    dot_x  = pad
    pri_x  = dot_x + int(14 * fs)
    time_x = pri_x + int(44 * fs)
    msg_x  = time_x + int(54 * fs)
    detail_max_w = max(1, w - msg_x - pad)

    # Pre-wrap detail text and compute each row's height (in row units) so
    # scroll/visibility math can work over variable-height entries.
    wrapped: list[list[str]] = []
    row_units: list[int] = []
    for pri, ts, msg, acked, detail in alarms:
        detail_lines = _wrap_text(font, detail, sp, detail_max_w) if detail else []
        wrapped.append(detail_lines)
        row_units.append(1 + len(detail_lines))

    total        = len(alarms)
    visible_units = max(1, (surf.get_height() - hh) // rh)
    max_start     = total
    for i in range(total):
        units = sum(row_units[i:])
        if units <= visible_units:
            max_start = i
            break
    start = max(0, min(scroll_row, max_start))

    y = hh + max(1, int(2 * fs))
    bottom_limit = surf.get_height()
    for i in range(start, total):
        pri, ts, msg, acked, _detail = alarms[i]
        detail_lines = wrapped[i]
        row_h = rh * row_units[i]
        if y + row_h > bottom_limit and i > start:
            break

        pri_col = _ALARM_DOT_COL.get(pri, COL_TEXT_DIM)
        if acked:
            pri_col = COL_ALARM_ACK
        elif not blink_on and pri in ('CRITICAL', 'WARNING'):
            pri_col = COL_METER_BG
        msg_col = pri_col

        dot_sym = '●' if not acked else '○'
        font.render_to(surf, (dot_x,  y), dot_sym,  pri_col,         size=sp)
        font.render_to(surf, (pri_x,  y), pri[:4],  pri_col,         size=sp)
        font.render_to(surf, (time_x, y), ts,        COL_TEXT_DIM,    size=sp)
        font.render_to(surf, (msg_x,  y), msg,       msg_col,         size=sp)

        detail_col = COL_ALARM_ACK if acked else COL_TEXT_PRIMARY
        for dline in detail_lines:
            y += rh
            font.render_to(surf, (msg_x, y), dline, detail_col, size=sp)

        y += rh

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
