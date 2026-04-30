"""Shared Form 700 workbook path resolution."""
import os
import pathlib


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]
_DEFAULT_FORM700_XLSX = _BACKEND_ROOT / "src" / "700Parse" / "sac700.xlsx"


def resolve_form700_path(*, require_exists: bool = True) -> pathlib.Path:
    override = os.getenv("FORM700_XLSX_PATH", "").strip()
    path = pathlib.Path(override) if override else _DEFAULT_FORM700_XLSX
    path = path if path.is_absolute() else (_BACKEND_ROOT / path)
    path = path.resolve()
    if require_exists and not path.exists():
        raise FileNotFoundError(
            f"Form 700 workbook not found at {path}. "
            "Set FORM700_XLSX_PATH or place sac700.xlsx at Backend/src/700Parse/sac700.xlsx."
        )
    return path
