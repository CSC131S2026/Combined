"""Resource path resolution that works in dev and inside PyInstaller bundles."""
from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running inside a PyInstaller-built bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def resource_root() -> Path:
    """
    Root directory for bundled resources.

    - In a PyInstaller bundle: sys._MEIPASS (the temp extraction dir).
    - In dev: the project root (the directory containing Frontend/, Backend/, shared/).
    """
    if is_frozen():
        return Path(sys._MEIPASS)
    # shared/ is a sibling of Frontend/ and Backend/, so the project root is parent.
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Join a path under the resource root. Example: resource_path('Backend', 'conflict_flags_openai.json')."""
    return resource_root().joinpath(*parts)
