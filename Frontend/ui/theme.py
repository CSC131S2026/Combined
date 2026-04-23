"""
Editorial design tokens for the Conflict of Interest Dashboard.

The palette now supports both light and dark appearance modes. CTk widgets
consume tuple colors directly, while ttk / tk code can use resolve_color()
to get the active hex value.
"""

import customtkinter as ctk


LIGHT_COLORS = {
    "bg_primary": "#f4ede2",
    "bg_secondary": "#fbf5eb",
    "bg_card": "#fffaf2",
    "bg_elevated": "#efe3d3",
    "bg_inverse": "#1d2935",
    "border": "#dbc8b4",
    "border_strong": "#baa087",
    "shadow": "#e8d8c7",
    "text_primary": "#1f2830",
    "text_secondary": "#59625c",
    "text_muted": "#877d72",
    "text_inverse": "#fff8ef",
    "accent_purple": "#c76845",
    "accent_green": "#2f6f6c",
    "accent_violet": "#aa5638",
    "accent_emerald": "#275e5b",
    "accent_gold": "#b98939",
    "accent_rose": "#8b5667",
    "highlight_soft": "#f7e1d9",
    "highlight_teal": "#deece8",
    "highlight_gold": "#f3e4c6",
    "highlight_green": "#deebdf",
    "success": "#357a58",
    "warning": "#b07d32",
    "danger": "#af4b49",
    "info": "#2f6f6c",
    "confidence_high": "#af4b49",
    "confidence_medium": "#b98939",
    "confidence_low": "#357a58",
}


DARK_COLORS = {
    "bg_primary": "#171a1d",
    "bg_secondary": "#20252a",
    "bg_card": "#262c31",
    "bg_elevated": "#30373d",
    "bg_inverse": "#fff7ee",
    "border": "#4a433d",
    "border_strong": "#64584d",
    "shadow": "#3a332d",
    "text_primary": "#f5eee5",
    "text_secondary": "#c8bba9",
    "text_muted": "#96897b",
    "text_inverse": "#1a1f24",
    "accent_purple": "#d98a68",
    "accent_green": "#6cb8b0",
    "accent_violet": "#b96c4e",
    "accent_emerald": "#4f9890",
    "accent_gold": "#d2a55d",
    "accent_rose": "#c98ba0",
    "highlight_soft": "#3a2d2f",
    "highlight_teal": "#253735",
    "highlight_gold": "#3b3327",
    "highlight_green": "#27342b",
    "success": "#68b785",
    "warning": "#d2a05b",
    "danger": "#e07d76",
    "info": "#6cb8b0",
    "confidence_high": "#e07d76",
    "confidence_medium": "#d2a05b",
    "confidence_low": "#68b785",
}


COLORS = {
    key: (LIGHT_COLORS[key], DARK_COLORS[key])
    for key in LIGHT_COLORS
}


FONT_FAMILIES = {
    "display": "Avenir Next",
    "body": "Avenir Next",
    "mono": "SF Mono",
}


FONT_ROLES = {
    "hero": {"family": FONT_FAMILIES["display"], "size": 30, "weight": "bold"},
    "headline": {"family": FONT_FAMILIES["display"], "size": 20, "weight": "bold"},
    "title": {"family": FONT_FAMILIES["display"], "size": 16, "weight": "bold"},
    "section": {"family": FONT_FAMILIES["display"], "size": 13, "weight": "bold"},
    "body": {"family": FONT_FAMILIES["body"], "size": 12, "weight": "normal"},
    "body_small": {"family": FONT_FAMILIES["body"], "size": 11, "weight": "normal"},
    "label": {"family": FONT_FAMILIES["mono"], "size": 10, "weight": "normal"},
    "label_bold": {"family": FONT_FAMILIES["mono"], "size": 10, "weight": "bold"},
    "metric": {"family": FONT_FAMILIES["display"], "size": 34, "weight": "bold"},
    "metric_small": {"family": FONT_FAMILIES["display"], "size": 22, "weight": "bold"},
}


def font(role: str, size: int | None = None, weight: str | None = None) -> ctk.CTkFont:
    """Return a CTk font using the shared typography system."""
    spec = FONT_ROLES[role]
    return ctk.CTkFont(
        family=spec["family"],
        size=size or spec["size"],
        weight=weight or spec["weight"],
    )


def resolve_color(value_or_name: str | tuple[str, str], mode: str | None = None) -> str:
    """Resolve a color token or tuple into a concrete hex string."""
    value = COLORS.get(value_or_name, value_or_name)
    if isinstance(value, tuple):
        active_mode = (mode or ctk.get_appearance_mode()).lower()
        return value[1] if active_mode == "dark" else value[0]
    return value
