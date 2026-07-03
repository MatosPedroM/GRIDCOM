"""
src/display/animation.py

FlowAnimator: directional flow markers on transmission lines.

Each active line with |loading| >= 5% gets a stream of small square markers
moving along its length. Speed is proportional to loading; direction reflects
the sign of the DC load flow (positive = from_bus → to_bus).

See CLAUDE.md Rule 2 — colours from palette.py only.
See CLAUDE.md Rule 1 — constants from constants.py only.
"""

from __future__ import annotations

import math
import pygame

from display.palette import (
    COL_FLOW_400KV, COL_FLOW_220KV, COL_FLOW_150KV, COL_FLOW_60KV,
)
from simulation.constants import (
    FLOW_MARKER_SIZE, FLOW_MARKER_SPACING,
    FLOW_SPEED_BASE, FLOW_SPEED_MAX,
)
from display.canvas import _parallel_offset_endpoints


_FLOW_THRESHOLD_PCT: float = 5.0    # minimum |loading %| to draw markers
_SPEED_MIN_MULT:     float = 0.1    # minimum speed as fraction of FLOW_SPEED_BASE


_VOLTAGE_FLOW_COL: dict[float, tuple] = {
    400.0: COL_FLOW_400KV,
    220.0: COL_FLOW_220KV,
    150.0: COL_FLOW_150KV,
    60.0:  COL_FLOW_60KV,
}


class FlowAnimator:
    """
    Animates directional flow markers on transmission lines.

    Usage:
        animator = FlowAnimator()
        # each frame:
        animator.update(dt_real_s, speed_mult)
        animator.draw(canvas_surf, state, bus_map, lines)
    """

    def __init__(self) -> None:
        # phase offset per line (in canvas pixels along the line)
        self._phases: dict[str, float] = {}

    def update(self, dt_real_s: float, speed_mult: float) -> None:
        """Advance all line phases by one frame. Called before draw()."""
        # Phases are advanced in draw() per-line since each line has a different speed.
        # update() is kept as a hook for future use (e.g. pause control from outside).
        self._dt = dt_real_s
        self._speed_mult = speed_mult

    def draw(
        self,
        surf:    pygame.Surface,
        state,
        bus_map: dict,
        lines:   list,
    ) -> None:
        """
        Draw flow markers for all active lines.

        Args:
            surf:    Canvas surface (1920×CANVAS_HEIGHT).
            state:   Current SimulationState.
            bus_map: dict[label → Bus] with canvas_x/canvas_y.
            lines:   list[Line] — active lines for this shift.
        """
        if state is None:
            return

        dt         = getattr(self, '_dt', 0.0)
        speed_mult = getattr(self, '_speed_mult', 1.0)

        for line in lines:
            lbl = line.label

            # Skip tripped lines
            status = state.line_status.get(lbl, 'IN_SERVICE')
            if status == 'TRIPPED':
                self._phases.pop(lbl, None)
                continue

            loading_pct = state.line_flows_mw.get(lbl, 0.0)
            abs_loading = abs(state.line_loading_pct.get(lbl, 0.0))

            if abs_loading < _FLOW_THRESHOLD_PCT:
                self._phases.pop(lbl, None)
                continue

            # Ensure phase entry exists
            if lbl not in self._phases:
                self._phases[lbl] = 0.0

            fb = bus_map.get(line.from_bus)
            tb = bus_map.get(line.to_bus)
            if fb is None or tb is None:
                continue

            x1, y1 = fb.canvas_x, fb.canvas_y
            x2, y2 = tb.canvas_x, tb.canvas_y
            x1, y1, x2, y2 = _parallel_offset_endpoints(x1, y1, x2, y2, line.parallel, 1.0)

            dx = x2 - x1
            dy = y2 - y1
            length = math.sqrt(dx * dx + dy * dy)
            if length < 1.0:
                continue

            # Speed proportional to loading
            load_frac = abs_loading / 100.0
            px_per_s  = FLOW_SPEED_BASE + load_frac * (FLOW_SPEED_MAX - FLOW_SPEED_BASE)
            px_per_s  = max(FLOW_SPEED_BASE * _SPEED_MIN_MULT, px_per_s)

            advance = px_per_s * dt * speed_mult
            if loading_pct >= 0.0:
                self._phases[lbl] = (self._phases[lbl] + advance) % FLOW_MARKER_SPACING
            else:
                self._phases[lbl] = (self._phases[lbl] - advance) % FLOW_MARKER_SPACING

            phase  = self._phases[lbl]
            col    = _VOLTAGE_FLOW_COL.get(line.voltage_kv, COL_FLOW_220KV)
            ux, uy = dx / length, dy / length   # unit vector along line

            # Draw markers spaced FLOW_MARKER_SPACING apart, starting at phase offset
            pos = phase
            half = FLOW_MARKER_SIZE // 2
            while pos < length:
                mx = int(x1 + ux * pos) - half
                my = int(y1 + uy * pos) - half
                pygame.draw.rect(surf, col,
                                 pygame.Rect(mx, my, FLOW_MARKER_SIZE, FLOW_MARKER_SIZE))
                pos += FLOW_MARKER_SPACING
