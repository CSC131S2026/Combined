"""Naming helpers for conflict-analysis output files."""
from __future__ import annotations

import re
from pathlib import Path


DEFAULT_CONFLICT_OUTPUT_BASE = "conflict_flags_openai"

_YEAR_RE = re.compile(r"^\d{4}$")


def output_slug(value) -> str:
    """Return a filesystem-friendly slug for an output-name segment."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("_") or "default"


def conflict_output_stem(
    *,
    input_year: str | int | None,
    input_dir: str | Path | None,
    input_source: str,
    explicit_stem: str | None = None,
    output_base: str = DEFAULT_CONFLICT_OUTPUT_BASE,
) -> str:
    """
    Build the canonical stem for conflict-analysis CSV/JSON/checkpoint files.

    Naming convention:
      - year-selected runs: conflict_flags_openai_<year>
      - direct year folders: conflict_flags_openai_<year>
      - county year folders: conflict_flags_openai_<county>_<year>
      - other custom folders: conflict_flags_openai_custom_<folder>
    """
    if explicit_stem is not None:
        return explicit_stem or output_base

    base = output_slug(output_base)
    year_slug = output_slug(input_year)
    if input_source == "year":
        return f"{base}_{year_slug}"

    if input_dir:
        path = Path(input_dir).expanduser()
        folder = path.name or "custom"
        if _YEAR_RE.fullmatch(folder):
            parent = path.parent.name
            grandparent = path.parent.parent.name
            if parent and parent != "output_data" and grandparent == "output_data":
                return f"{base}_{output_slug(parent)}_{output_slug(folder)}"
            return f"{base}_{output_slug(folder)}"
        return f"{base}_custom_{output_slug(folder)}"

    return f"{base}_{year_slug}"
