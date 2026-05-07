"""Spreadsheet export safety helpers."""

from collections.abc import Mapping


_FORMULA_PREFIXES = ("=", "+", "-", "@")
_DANGEROUS_LEADING_CHARS = _FORMULA_PREFIXES + ("\t", "\r", "\n")


def neutralize_spreadsheet_formula(value):
    """Prefix text that spreadsheet apps could interpret as a formula."""
    if not isinstance(value, str) or not value:
        return value

    stripped = value.lstrip(" \t\r\n")
    if value[0] in _DANGEROUS_LEADING_CHARS or (
        stripped and stripped[0] in _FORMULA_PREFIXES
    ):
        return "'" + value
    return value


def neutralize_csv_row(row):
    """Return a copy of a CSV row mapping with formula-like text neutralized."""
    if not isinstance(row, Mapping):
        raise TypeError("row must be a mapping")
    return {key: neutralize_spreadsheet_formula(value) for key, value in row.items()}


def neutralize_dataframe_for_spreadsheet(dataframe):
    """Return a DataFrame copy with formula-like string cells neutralized."""
    safe = dataframe.copy()
    for column in safe.columns:
        safe[column] = safe[column].map(neutralize_spreadsheet_formula)
    return safe
