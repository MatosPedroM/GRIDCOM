"""
src/data/layout_override.py

Runtime layout override layer for the grid layout editor.

Loads position overrides from src/assets/layout.json at startup.
topology.py and fleet.py query this module when building canvas positions,
so moved elements are reflected without editing source files.

Only elements that have been moved appear in layout.json.
Absent entries fall back to the hardcoded defaults in topology.py / fleet.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from utils.helpers import resource_path

_LAYOUT_PATH: Path = resource_path('assets/layout.json')

_bus_overrides:     dict[str, tuple[int, int]] = {}
_station_overrides: dict[str, tuple[int, int]] = {}
_label_anchors:     dict[str, str]             = {}   # label → 'top'|'right'|'bottom'|'left'


def load_layout() -> None:
    """Load layout.json if it exists. Safe to call at startup."""
    global _bus_overrides, _station_overrides, _label_anchors
    if not _LAYOUT_PATH.exists():
        return
    try:
        data = json.loads(_LAYOUT_PATH.read_text(encoding='utf-8'))
        _bus_overrides     = {k: (int(v[0]), int(v[1])) for k, v in data.get('buses', {}).items()}
        _station_overrides = {k: (int(v[0]), int(v[1])) for k, v in data.get('stations', {}).items()}
        _label_anchors     = {k: str(v) for k, v in data.get('label_anchors', {}).items()}
    except Exception:
        pass


def get_bus_pos(label: str, default_x: int, default_y: int) -> tuple[int, int]:
    """Return override position for a bus, or (default_x, default_y)."""
    return _bus_overrides.get(label, (default_x, default_y))


def get_station_pos(label: str, default: tuple[int, int]) -> tuple[int, int]:
    """Return override position for a station anchor, or default."""
    return _station_overrides.get(label, default)


def set_bus_pos(label: str, x: int, y: int) -> None:
    """Update in-memory override for a bus."""
    _bus_overrides[label] = (x, y)


def set_station_pos(label: str, x: int, y: int) -> None:
    """Update in-memory override for a station anchor."""
    _station_overrides[label] = (x, y)


def get_label_anchor(label: str) -> str:
    """Return label anchor for element, defaulting to 'right'."""
    return _label_anchors.get(label, 'right')


def set_label_anchor(label: str, anchor: str) -> None:
    """Update in-memory label anchor for a bus or station."""
    _label_anchors[label] = anchor


def save_layout() -> None:
    """Write current overrides to layout.json."""
    data = {
        'buses':         {k: list(v) for k, v in _bus_overrides.items()},
        'stations':      {k: list(v) for k, v in _station_overrides.items()},
        'label_anchors': dict(_label_anchors),
    }
    _LAYOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LAYOUT_PATH.write_text(json.dumps(data, indent=2), encoding='utf-8')


def get_all_overrides() -> tuple[dict[str, tuple[int, int]], dict[str, tuple[int, int]]]:
    """Return (bus_overrides, station_overrides) dicts for the editor."""
    return _bus_overrides, _station_overrides
