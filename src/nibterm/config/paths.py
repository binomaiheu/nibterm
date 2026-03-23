"""Resolve resource paths, with PyInstaller bundle support."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def static_dir() -> Path:
    """Return the path to the ``static/`` resource directory.

    Resolution order:
    1. PyInstaller bundle (``sys._MEIPASS / "static"``).
    2. Repository root (three levels up from this file).
    3. Package-local fallback (``nibterm/static``).
    """
    # PyInstaller --onefile extracts to a temp dir exposed as sys._MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        p = Path(meipass) / "static"
        if p.exists():
            return p

    # Running from source: <repo>/src/nibterm/config/paths.py → <repo>/static
    repo_static = Path(__file__).resolve().parent.parent.parent.parent / "static"
    if repo_static.exists():
        return repo_static

    # Installed package fallback
    return Path(__file__).resolve().parent.parent / "static"
