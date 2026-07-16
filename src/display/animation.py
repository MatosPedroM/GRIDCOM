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
        animator.draw(canvas_surf, state, line_ports, lines)
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
        surf:            pygame.Surface,
        state,
        line_waypoints:  dict,
        lines:           list,
    ) -> None:
        """
        Draw flow markers for all active lines.

        Args:
            surf:           Canvas surface (1920×CANVAS_HEIGHT, already display-scaled).
            state:          Current SimulationState.
            line_waypoints: dict[line_label -> [(x,y), ...]] — GridCanvas's
                            precomputed, scaled, obstacle-avoiding waypoint path
                            per line (see canvas.GridCanvas._line_waypoints).
                            Never computes routing itself — this runs every frame.
            lines:          list[Line] — active lines for this shift.
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

            waypoints = line_waypoints.get(lbl)
            if waypoints is None or len(waypoints) < 2:
                continue

            segments = list(zip(waypoints, waypoints[1:]))
            seg_lengths = [
                math.sqrt((sx2 - sx1) ** 2 + (sy2 - sy1) ** 2)
                for (sx1, sy1), (sx2, sy2) in segments
            ]
            length = sum(seg_lengths)
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

            # Draw markers spaced FLOW_MARKER_SPACING apart, starting at phase
            # offset, walking along the routed waypoint path segment by segment.
            half = FLOW_MARKER_SIZE // 2
            pos = phase
            while pos < length:
                remaining = pos
                for ((sx1, sy1), (sx2, sy2)), seg_len in zip(segments, seg_lengths):
                    if remaining <= seg_len or seg_len < 1e-6:
                        t = remaining / seg_len if seg_len >= 1e-6 else 0.0
                        mx = int(sx1 + (sx2 - sx1) * t) - half
                        my = int(sy1 + (sy2 - sy1) * t) - half
                        pygame.draw.rect(surf, col,
                                         pygame.Rect(mx, my, FLOW_MARKER_SIZE, FLOW_MARKER_SIZE))
                        break
                    remaining -= seg_len
                pos += FLOW_MARKER_SPACING
