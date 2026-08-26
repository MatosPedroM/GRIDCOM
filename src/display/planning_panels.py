"""
src/display/planning_panels.py

Drawing for PlanningScreen — a single full-screen form: a stacked
generation-vs-load plot over the full 24h planning day, and below it an
editable units x hours table grouped by technology, with summary rows
(wind forecast, total gen, load forecast, diff, regulation band).

All drawing coordinates in this file are expressed in LOGICAL (unscaled)
1920x1080 native-space pixels — the same space PlanningScreen's hit-testing
(on_click, to_native) operates in. _label()/_rect()/_line() are the only
places that convert to the surf's actual (scaled) pixel space, at the point
of drawing — surf itself is sized at real display resolution (see
PlanningScreen.tick()).
"""

from __future__ import annotations

import pygame
import pygame.freetype

from config.palette import (
    COL_BACKGROUND, COL_PANEL_BORDER,
    COL_TEXT_PRIMARY, COL_TEXT_SECONDARY, COL_TEXT_DIM, COL_TEXT_VALUE,
    COL_TEXT_HEADING, COL_TEXT_WARN, COL_TEXT_CRIT, COL_TEXT_GOOD,
    COL_SELECTION, COL_DESIGNER_STATUS_INFO,
    COL_PLAN_LOAD_LINE, COL_PLAN_GRID_LINE, COL_PLAN_CELL_SEL,
    COL_PLAN_OFFLINE, COL_PLAN_WINDOW_MARK,
)
from display.panels import FUEL_ORDER, FUEL_LABELS, FUEL_COLOURS
from config.constants import (
    NATIVE_WIDTH, NATIVE_HEIGHT,
    PLANNING_LEFT_MARGIN, PLANNING_TOP_MARGIN,
    PLANNING_LABEL_COL_W, PLANNING_HOUR_COL_W,
    PLANNING_ROW_H, PLANNING_PLOT_H, PLANNING_PLOT_Y_HEADROOM_FRAC,
    PLANNING_TABLE_GROUP_GAP, PLANNING_TABLE_VISIBLE_H,
    PLANNING_KEY_EDIT, PLANNING_KEY_TECH_MIN, PLANNING_KEY_TECH_MAX,
    PLANNING_KEY_ZERO, PLANNING_KEY_TOGGLE_ONLINE, PLANNING_KEY_TOGGLE_AGC,
    PLANNING_KEY_RESET,
    PLANNING_KEY_AUTO, PLANNING_KEY_CONFIRM, PLANNING_KEY_BACK,
    PLANNING_AGC_RESERVE_MW,
)

_scale: float = 1.0

# Dispatchable-only fuel order (WIND/SOLAR are shown as locked, read-only
# rows instead — see _RENEWABLE_FUEL_ORDER — even though they appear in
# the stacked plot and summary forecast rows).
_DISPATCHABLE_FUEL_ORDER = tuple(f for f in FUEL_ORDER if f not in ('WIND', 'SOLAR'))

# Renewable fuel order for the locked, informational table rows.
_RENEWABLE_FUEL_ORDER = ('WIND', 'SOLAR')


def _label(surf, font, x, y, text, colour) -> None:
    sc = _scale
    font.render_to(surf, (int(x * sc), int(y * sc)), text, colour,
                   size=int(font.size * sc))


def _label_right(surf, font, right_x, y, text, colour) -> None:
    sc = _scale
    rect = font.get_rect(text, size=int(font.size * sc))
    font.render_to(surf, (int(right_x * sc) - rect.width, int(y * sc)), text, colour,
                   size=int(font.size * sc))


def _rect(surf, colour, x, y, w, h, width: int = 0) -> None:
    sc = _scale
    pygame.draw.rect(surf, colour,
                     (int(x * sc), int(y * sc), int(w * sc), int(h * sc)), width)


def _line(surf, colour, p1, p2, width: int = 1) -> None:
    sc = _scale
    pygame.draw.line(surf, colour,
                     (int(p1[0] * sc), int(p1[1] * sc)),
                     (int(p2[0] * sc), int(p2[1] * sc)), width)


def _hour_col_x(col: int) -> float:
    return PLANNING_LEFT_MARGIN + PLANNING_LABEL_COL_W + col * PLANNING_HOUR_COL_W


def draw_planning(surf: pygame.Surface, screen, font, font_large, scale: float = 1.0) -> None:
    global _scale
    _scale = scale
    surf.fill(COL_BACKGROUND)

    model = screen._model

    _label(surf, font_large, PLANNING_LEFT_MARGIN, 2,
           f'SHIFT {screen._shift_number} PLANNING — 24H UNIT SCHEDULE', COL_TEXT_HEADING)

    remaining = model.remaining_budget()
    budget_colour = COL_TEXT_CRIT if remaining < 0.0 else COL_TEXT_VALUE
    budget_text = (
        f'PLAN COST: EUR {model.total_cost():,.0f}   '
        f'BUDGET: EUR {model.budget_eur:,.0f}   '
        f'REMAINING: EUR {remaining:,.0f}'
    )
    _label_right(surf, font, NATIVE_WIDTH - PLANNING_LEFT_MARGIN, 6, budget_text, budget_colour)

    plot_top = PLANNING_TOP_MARGIN
    _draw_plot(surf, screen, font, plot_top)

    table_top = plot_top + PLANNING_PLOT_H + 16
    table_bottom = _draw_table(surf, screen, font, table_top)

    _draw_summary_rows(surf, screen, font, table_bottom + PLANNING_TABLE_GROUP_GAP)

    _draw_footer(surf, screen, font)

    if screen._editing:
        _draw_edit_overlay(surf, screen, font, font_large)


# ─────────────────────────────────────────────────────────────────────────────
# PLOT
# ─────────────────────────────────────────────────────────────────────────────

def _draw_plot(surf, screen, font, y0) -> None:
    model = screen._model
    plot_x0 = PLANNING_LEFT_MARGIN + PLANNING_LABEL_COL_W
    plot_w  = PLANNING_HOUR_COL_W * len(model.hours)
    plot_h  = PLANNING_PLOT_H - 20
    plot_y0 = y0 + 4

    peak = 1.0
    for h in model.hours:
        peak = max(peak, model.total_gen(h), model.load_forecast.get(h, 0.0))
    y_max = peak * PLANNING_PLOT_Y_HEADROOM_FRAC

    _rect(surf, COL_PLAN_GRID_LINE, plot_x0, plot_y0, plot_w, plot_h, width=1)

    # Shift-window bracket on the x-axis.
    win_x0 = plot_x0 + PLANNING_HOUR_COL_W * _hour_index(model, model.start_hour)
    win_x1 = plot_x0 + PLANNING_HOUR_COL_W * _hour_index(model, model.start_hour + model.duration_hours)
    _line(surf, COL_PLAN_WINDOW_MARK, (win_x0, plot_y0 + plot_h + 2), (win_x1, plot_y0 + plot_h + 2), width=3)
    _label(surf, font, win_x0, plot_y0 + plot_h + 5, 'SHIFT WINDOW', COL_PLAN_WINDOW_MARK)

    # Stacked generation bars, one column per hour.
    for i, h in enumerate(model.hours):
        cx = plot_x0 + i * PLANNING_HOUR_COL_W
        stack = model.stacked_by_tech(h)
        y_cursor = plot_y0 + plot_h
        for fuel in FUEL_ORDER:
            mw = stack.get(fuel, 0.0)
            if mw <= 0.0:
                continue
            bar_h = (mw / y_max) * plot_h
            colour = FUEL_COLOURS.get(fuel, COL_TEXT_SECONDARY)
            _rect(surf, colour, cx + 1, y_cursor - bar_h, PLANNING_HOUR_COL_W - 2, bar_h)
            y_cursor -= bar_h

    # Load forecast overlay polyline.
    points = []
    for i, h in enumerate(model.hours):
        cx = plot_x0 + i * PLANNING_HOUR_COL_W + PLANNING_HOUR_COL_W / 2
        load_mw = model.load_forecast.get(h, 0.0)
        cy = plot_y0 + plot_h - (load_mw / y_max) * plot_h
        points.append((cx, cy))
    if len(points) >= 2:
        sc = _scale
        scaled_points = [(int(px * sc), int(py * sc)) for px, py in points]
        pygame.draw.lines(surf, COL_PLAN_LOAD_LINE, False, scaled_points, 2)

    # Legend.
    legend_y = plot_y0 - 16
    lx = plot_x0
    for fuel in FUEL_ORDER:
        colour = FUEL_COLOURS.get(fuel, COL_TEXT_SECONDARY)
        _rect(surf, colour, lx, legend_y + 2, 10, 10)
        _label(surf, font, lx + 14, legend_y, FUEL_LABELS.get(fuel, fuel[:4]), COL_TEXT_SECONDARY)
        lx += 70
    _line(surf, COL_PLAN_LOAD_LINE, (lx, legend_y + 7), (lx + 20, legend_y + 7), width=2)
    _label(surf, font, lx + 24, legend_y, 'LOAD', COL_TEXT_SECONDARY)


def _hour_index(model, hour: float) -> int:
    for i, h in enumerate(model.hours):
        if h >= hour:
            return i
    return len(model.hours)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE
# ─────────────────────────────────────────────────────────────────────────────

def _draw_table(surf, screen, font, y0) -> float:
    model = screen._model
    x0 = PLANNING_LEFT_MARGIN
    y = y0

    screen._hit_rects.clear()
    screen._row_index.clear()

    # Hour column headers.
    for i, h in enumerate(model.hours):
        cx = x0 + PLANNING_LABEL_COL_W + i * PLANNING_HOUR_COL_W
        in_window = model.in_shift_window(h)
        colour = COL_PLAN_WINDOW_MARK if in_window else COL_TEXT_DIM
        _label(surf, font, cx + 4, y, f'{int(h):02d}', colour)
    y += PLANNING_ROW_H

    header_bottom = y
    _line(surf, COL_PANEL_BORDER, (x0, y), (x0 + PLANNING_LABEL_COL_W + PLANNING_HOUR_COL_W * len(model.hours), y))
    y += 2
    viewport_top = y
    viewport_h = PLANNING_TABLE_VISIBLE_H
    viewport_bottom = viewport_top + viewport_h

    # Build the full flattened row list (group headers + unit rows) first, so
    # scroll offset can be computed from the selected unit's row position.
    units_by_type: dict[str, list] = {}
    for unit in model.unit_specs:
        units_by_type.setdefault(unit.unit_type, []).append(unit)

    renewables_by_type: dict[str, list] = {}
    for unit in model.renewable_specs:
        renewables_by_type.setdefault(unit.unit_type, []).append(unit)

    # ('group', fuel) | ('unit', unit) | ('readonly_group', fuel) | ('readonly_unit', unit)
    flat_rows: list[tuple[str, object]] = []

    # Locked, informational WIND/SOLAR rows first — never added to
    # screen._row_index (so cursor navigation skips them) and given no
    # hit-rects (so clicking them does nothing). Their MW already feeds
    # into total_gen()/stacked_by_tech() via renewable_forecast.
    for fuel in _RENEWABLE_FUEL_ORDER:
        units = renewables_by_type.get(fuel)
        if not units:
            continue
        flat_rows.append(('readonly_group', fuel))
        for unit in units:
            flat_rows.append(('readonly_unit', unit))

    for fuel in _DISPATCHABLE_FUEL_ORDER:
        units = units_by_type.get(fuel)
        if not units:
            continue
        flat_rows.append(('group', fuel))
        for unit in units:
            flat_rows.append(('unit', unit))
            screen._row_index.append(unit.label)

    # Scroll so the selected unit's row stays inside the viewport.
    sel_label = screen._row_index[screen._sel_row] if screen._row_index else None
    sel_flat_idx = next(
        (i for i, (kind, v) in enumerate(flat_rows) if kind == 'unit' and v.label == sel_label),
        0,
    )
    visible_rows = max(1, viewport_h // PLANNING_ROW_H)
    scroll_start = max(0, min(len(flat_rows) - visible_rows, sel_flat_idx - visible_rows // 2))
    scroll_start = max(0, scroll_start)

    # Clip drawing to the viewport rect so scrolled-off rows don't bleed
    # into the summary rows below.
    sc = _scale
    viewport_rect = pygame.Rect(
        int(x0 * sc), int(viewport_top * sc),
        int((PLANNING_LABEL_COL_W + PLANNING_HOUR_COL_W * len(model.hours)) * sc),
        int(viewport_h * sc),
    )
    old_clip = surf.get_clip()
    surf.set_clip(viewport_rect)

    row_idx = 0
    y = viewport_top
    for kind, value in flat_rows[scroll_start:]:
        if y >= viewport_bottom:
            break
        if kind in ('group', 'readonly_group'):
            fuel = value
            label = FUEL_LABELS.get(fuel, fuel)
            if kind == 'readonly_group':
                label += ' (forecast, locked)'
            _label(surf, font, x0, y, label, FUEL_COLOURS.get(fuel, COL_TEXT_HEADING))
            y += PLANNING_ROW_H
            continue

        if kind == 'readonly_unit':
            unit = value
            _label(surf, font, x0 + 40, y, f'{unit.label:<8}', COL_TEXT_DIM)
            for i, h in enumerate(model.hours):
                cx = x0 + PLANNING_LABEL_COL_W + i * PLANNING_HOUR_COL_W
                mw = model.renewable_forecast.get(unit.label, {}).get(h, 0.0)
                _label_right(surf, font, cx + PLANNING_HOUR_COL_W - 4, y, f'{mw:.0f}', COL_TEXT_DIM)
            y += PLANNING_ROW_H
            continue

        unit = value
        row_idx = screen._row_index.index(unit.label)
        selected_row = (row_idx == screen._sel_row)
        online = model.is_online(unit.label, model.hours[0])
        label_colour = COL_TEXT_VALUE if online else COL_PLAN_OFFLINE

        toggle_rect = pygame.Rect(x0, y, 34, PLANNING_ROW_H)
        screen._hit_rects.append((f'toggle:{unit.label}', toggle_rect))
        _label(surf, font, x0, y, '[ON]' if online else '[OFF]', label_colour)

        if model.is_agc_eligible(unit.label):
            agc_colour = COL_TEXT_GOOD if model.is_agc_enrolled(unit.label) else COL_TEXT_DIM
            _label(surf, font, x0 + 38, y, '[A]', agc_colour)

        _label(surf, font, x0 + 62, y, f'{unit.label:<8}', label_colour)

        for i, h in enumerate(model.hours):
            cx = x0 + PLANNING_LABEL_COL_W + i * PLANNING_HOUR_COL_W
            mw = model.schedule.get(unit.label, {}).get(h, 0.0)
            hour_online = model.is_online(unit.label, h)
            is_sel = selected_row and (i == screen._sel_col)
            cell_rect = pygame.Rect(cx, y, PLANNING_HOUR_COL_W, PLANNING_ROW_H)
            screen._hit_rects.append((f'cell:{unit.label}:{h}', cell_rect))
            if is_sel:
                _rect(surf, COL_PLAN_CELL_SEL, cx, y, PLANNING_HOUR_COL_W, PLANNING_ROW_H, width=1)
            # A column can be OFFLINE but still show a nonzero MW — the
            # auto-scheduler's shutdown ramp (and total_gen()/DIFF) count a
            # decommitting unit's residual output until it actually reaches
            # 0, so the cell must show that value rather than a bare '-'
            # once it's mid-ramp-down.
            text = f'{mw:.0f}' if (hour_online or mw != 0.0) else '-'
            colour = COL_TEXT_VALUE if hour_online else COL_PLAN_OFFLINE
            _label_right(surf, font, cx + PLANNING_HOUR_COL_W - 4, y, text, colour)

        y += PLANNING_ROW_H

    surf.set_clip(old_clip)

    if len(flat_rows) > visible_rows:
        _label(surf, font, NATIVE_WIDTH - 140, 4,
               f'ROW {sel_flat_idx + 1}/{len(flat_rows)}', COL_TEXT_DIM)

    return viewport_bottom


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY ROWS
# ─────────────────────────────────────────────────────────────────────────────

def _draw_summary_rows(surf, screen, font, y0) -> None:
    model = screen._model
    x0 = PLANNING_LEFT_MARGIN
    y = y0

    _line(surf, COL_PANEL_BORDER, (x0, y), (x0 + PLANNING_LABEL_COL_W + PLANNING_HOUR_COL_W * len(model.hours), y))
    y += 4

    def _diff_colour(h, val):
        abs_val = abs(val)
        if abs_val < 0.02 * max(1.0, model.load_forecast.get(h, 1.0)):
            return COL_TEXT_GOOD
        elif abs_val < 0.05 * max(1.0, model.load_forecast.get(h, 1.0)):
            return COL_TEXT_WARN
        return COL_TEXT_CRIT

    def _reserve_colour(h, val):
        # Below the auto-scheduler's own reserve target is a real gap
        # (either a capacity-scarce hour or a hand-edited plan) — red,
        # same alert weight as DIFF's own worst tier.
        return COL_TEXT_CRIT if val < PLANNING_AGC_RESERVE_MW else COL_TEXT_GOOD

    rows = (
        ('WIND FCST', lambda h: model.renewable_total(h, 'WIND'), COL_TEXT_SECONDARY),
        ('SOLAR FCST', lambda h: model.renewable_total(h, 'SOLAR'), COL_TEXT_SECONDARY),
        ('TOTAL GEN', lambda h: model.total_gen(h), COL_TEXT_VALUE),
        ('LOAD FCST', lambda h: model.load_forecast.get(h, 0.0), COL_TEXT_VALUE),
        ('DIFF',      lambda h: model.difference(h), _diff_colour),
        ('REG UP',    lambda h: model.reg_band_up(h), _reserve_colour),
        ('REG DOWN',  lambda h: model.reg_band_down(h), _reserve_colour),
        ('COST EUR',  lambda h: model.hourly_cost(h), COL_TEXT_SECONDARY),
    )

    for label, fn, colour_spec in rows:
        _label(surf, font, x0, y, label, COL_TEXT_HEADING)
        for i, h in enumerate(model.hours):
            cx = x0 + PLANNING_LABEL_COL_W + i * PLANNING_HOUR_COL_W
            val = fn(h)
            colour = colour_spec(h, val) if callable(colour_spec) else colour_spec
            _label_right(surf, font, cx + PLANNING_HOUR_COL_W - 4, y, f'{val:.0f}', colour)
        y += PLANNING_ROW_H


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER / STATUS
# ─────────────────────────────────────────────────────────────────────────────

def _key_label(key: int) -> str:
    """Human-readable label for a pygame key constant, e.g. K_LEFTBRACKET -> '['."""
    return pygame.key.name(key).upper()


def _draw_footer(surf, screen, font) -> None:
    y = NATIVE_HEIGHT - PLANNING_ROW_H - 4
    tech_min = _key_label(PLANNING_KEY_TECH_MIN)
    tech_max = _key_label(PLANNING_KEY_TECH_MAX)
    zero_key = _key_label(PLANNING_KEY_ZERO)
    hint = (
        f'[Arrows] move  [{_key_label(PLANNING_KEY_EDIT)}] edit  '
        f'[{tech_min}/{tech_max}] tech min/max  [Shift+{tech_min}/{tech_max}] fill row  '
        f'[{zero_key}] zero  [Shift+{zero_key}] zero row  '
        f'[{_key_label(PLANNING_KEY_TOGGLE_ONLINE)}] online/off  '
        f'[{_key_label(PLANNING_KEY_TOGGLE_AGC)}] AGC enroll  '
        f'[{_key_label(PLANNING_KEY_RESET)}] reset  '
        f'[Ctrl+{_key_label(PLANNING_KEY_AUTO)}] auto-schedule  '
        f'[{_key_label(PLANNING_KEY_CONFIRM)}] confirm plan  '
        f'[{_key_label(PLANNING_KEY_BACK)}] back'
    )
    _label(surf, font, PLANNING_LEFT_MARGIN, y, hint, COL_TEXT_PRIMARY)

    if screen._status_timer > 0.0 and screen._status_text:
        _label(surf, font, PLANNING_LEFT_MARGIN, y - PLANNING_ROW_H,
               screen._status_text, screen._status_colour)


def _draw_edit_overlay(surf, screen, font, font_large) -> None:
    w, h = 420, 90
    x = (NATIVE_WIDTH - w) // 2
    y = (NATIVE_HEIGHT - h) // 2
    _rect(surf, COL_BACKGROUND, x, y, w, h)
    _rect(surf, COL_PANEL_BORDER, x, y, w, h, width=2)
    _label(surf, font, x + 12, y + 10, f'EDIT: {screen._editing}', COL_TEXT_SECONDARY)
    _label(surf, font_large, x + 12, y + 36, screen._edit_buffer + '_', COL_SELECTION)
