"""
Dark purple + green design tokens for the Conflict of Interest Dashboard.
All color references live here so agents stay visually consistent.
"""

COLORS = {
    # ── Backgrounds (purple-tinted dark) ──────────────────────────────
    "bg_primary":     "#0c0a14",   # near-black with purple cast
    "bg_secondary":   "#131020",   # dark purple panel
    "bg_card":        "#1a1630",   # card surface
    "bg_elevated":    "#221e38",   # slightly raised surface

    # ── Structure ─────────────────────────────────────────────────────
    "border":         "#3d3560",   # muted purple rule

    # ── Text (lavender-tinted) ────────────────────────────────────────
    "text_primary":   "#e4dff5",   # near-white lavender
    "text_secondary": "#9b93b8",   # muted lavender
    "text_muted":     "#564e72",   # very muted purple-grey

    # ── Accent colors ─────────────────────────────────────────────────
    "accent_purple":  "#9d6fe8",   # primary — medium violet
    "accent_green":   "#34c97a",   # secondary — emerald green
    "accent_violet":  "#7c4fc4",   # deeper purple (hover states)
    "accent_emerald": "#1a9e5c",   # deeper green (hover states)

    # ── Semantic states ───────────────────────────────────────────────
    "success":        "#34c97a",   # green
    "warning":        "#b07af5",   # light purple (elevated concern)
    "danger":         "#e05878",   # muted rose-red (errors / high risk)
    "info":           "#9d6fe8",   # purple (informational)

    # ── Confidence-level colors ───────────────────────────────────────
    "confidence_high":   "#e05878",   # rose-red   — serious risk
    "confidence_medium": "#b07af5",   # light purple — moderate
    "confidence_low":    "#34c97a",   # green        — low risk
}
