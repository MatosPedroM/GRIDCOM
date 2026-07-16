"""
src/display/geometry.py

Small shared geometry primitives used by both the click hit-test
(renderer.py) and the schematic line router (canvas.py). Kept in its own
module because renderer.py imports canvas.py (GridCanvas), so canvas.py
cannot import a primitive defined in renderer.py without a circular import.
"""


def point_segment_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Return the minimum distance from point (px,py) to segment (x1,y1)-(x2,y2)."""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    nx = x1 + t * dx
    ny = y1 + t * dy
    return ((px - nx) ** 2 + (py - ny) ** 2) ** 0.5
