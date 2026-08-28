"""
src/utils/save_paths.py

Writable, persistent save-file locations for GRIDCOM. Distinct from
resource_path() (helpers.py), which resolves read-only bundled assets
under a PyInstaller build's extraction folder — player save data must
live somewhere that survives across runs and is writable regardless of
where the game is installed.
"""

import os
from pathlib import Path


def save_dir() -> Path:
    """
    Resolve (and create if missing) the writable, per-user directory
    GRIDCOM save files live in.

    Windows: %APPDATA%/GRIDCOM. This project targets Windows as its
    primary platform (see CLAUDE.md); a cross-platform fallback is not
    needed today.
    """
    base = Path(os.environ['APPDATA'])
    path = base / 'GRIDCOM'
    path.mkdir(parents=True, exist_ok=True)
    return path


def campaign_save_path(slot: int = 0) -> Path:
    """Path to a campaign save file for the given slot (default 0)."""
    return save_dir() / f'campaign_save_{slot}.json'
