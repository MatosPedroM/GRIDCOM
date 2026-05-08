"""
src/utils/helpers.py

Shared utility functions for GRIDCOM.
Provides resource_path() for resolving asset paths in both development
and PyInstaller single-folder builds.
"""

import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    """
    Resolve an asset path for both development and PyInstaller builds.

    In development, paths are resolved relative to the src/ directory.
    In a PyInstaller build, paths are resolved relative to sys._MEIPASS
    (the temporary extraction folder).

    Args:
        relative_path: Path relative to the assets root, e.g.
                       'assets/fonts/JetBrainsMono-Regular.ttf'

    Returns:
        Absolute Path object suitable for passing to pygame.freetype.Font,
        pygame.mixer.Sound, etc.
    """
    if hasattr(sys, '_MEIPASS'):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent.parent   # src/utils/ → src/
    return base / relative_path
