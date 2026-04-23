"""
SelectionAgent — focused conflict trail for the active person or entity.

Replaces the generic confidence distribution with a panel that becomes
useful as soon as the reviewer clicks a name in the dashboard.
"""

from collections import Counter
from pathlib import Path

import customtkinter as ctk

from agents.base_agent import BaseAgent
from core.filter_engine import FilterEngine
from ui.theme import COLORS, font


class SelectionAgent(BaseAgent):

    def __init__(self, parent, row, col, rowspan=1, colspan=1):
        self._engine = FilterEngine()
        super().__init__(parent, row, col, rowspan=rowspan, colspan=colspan)

    def get_title(self) -> str:
        return "Selection Focus"

    def get_kicker(self) -> str:
        return "Current lens"

    def get_accent_color(self) -> str:
        return COLORS["accent_green"]

    def _build_header_controls(self) -> None:
        self._context_pill = ctk.CTkLabel(
            self.header_frame,
            text="Pick a name",
            font=font("label_bold"),
            text_color=COLORS["text_secondary"],
            fg_color=COLORS["bg_secondary"],
            corner_radius=999,
            padx=12,
            height=28,
        )
        self._context_pill.grid(row=0, column=1, padx=4, pady=8, sticky="e")
        self.header_frame.grid_columnconfigure(1, weight=0)

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        body.grid_rowconfigure(2, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self._hero = ctk.CTkFrame(
            body,
            fg_color=COLORS["highlight_teal"],
            corner_radius=22,
            border_width=1,
            border_color=COLORS["border"],
        )
        self._hero.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._hero.grid_columnconfigure(0, weight=1)

        self._focus_title = ctk.CTkLabel(
            self._hero,
            text="Choose an official or entity",
            font=font("headline", size=18),
            text_color=COLORS["text_primary"],
            justify="left",
            wraplength=250,
        )
        self._focus_title.grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")

        self._focus_meta = ctk.CTkLabel(
            self._hero,
            text="Click a name to open a focused conflict trail.",
            font=font("section", size=12),
            text_color=COLORS["text_primary"],
            justify="left",
            wraplength=250,
        )
        self._focus_meta.grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

        self._focus_note = ctk.CTkLabel(
            self._hero,
            text="This panel will summarize that selection and surface the related records.",
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
            justify="left",
            wraplength=250,
        )
        self._focus_note.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="w")

        stats = ctk.CTkFrame(body, fg_color="transparent")
        stats.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for col in range(3):
            stats.grid_columnconfigure(col, weight=1)

        self._high_value = self._make_stat_chip(stats, 0, "High", COLORS["confidence_high"])
        self._med_value = self._make_stat_chip(stats, 1, "Medium", COLORS["confidence_medium"])
        self._low_value = self._make_stat_chip(stats, 2, "Low", COLORS["confidence_low"])

        list_shell = ctk.CTkFrame(
            body,
            fg_color=COLORS["bg_secondary"],
            corner_radius=20,
            border_width=1,
            border_color=COLORS["border"],
        )
        list_shell.grid(row=2, column=0, sticky="nsew")
        list_shell.grid_rowconfigure(1, weight=1)
        list_shell.grid_columnconfigure(0, weight=1)

        self._list_heading = ctk.CTkLabel(
            list_shell,
            text="Standout names in the current view",
            font=font("section", size=13),
            text_color=COLORS["text_primary"],
        )
        self._list_heading.grid(row=0, column=0, padx=14, pady=(12, 4), sticky="w")

        self._list_frame = ctk.CTkFrame(
            list_shell,
            fg_color="transparent",
        )
        self._list_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self._list_frame.grid_columnconfigure(0, weight=1)

        self._show_suggestions({})

    def _make_stat_chip(self, parent, column: int, title: str, color: str):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_secondary"],
            corner_radius=18,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=0, column=column, sticky="ew", padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text=title,
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, padx=12, pady=(10, 0), sticky="w")

        value = ctk.CTkLabel(
            card,
            text="0",
            font=font("section", size=16),
            text_color=color,
        )
        value.grid(row=1, column=0, padx=12, pady=(1, 10), sticky="w")
        return value

    def update(self, focus: dict, records: list, aggregates: dict | None = None) -> None:
        focus = focus or {}
        kind = focus.get("kind")
        name = focus.get("name")
        secondary = focus.get("secondary")

        if not kind or not name:
            self.title_label.configure(text="Selection Focus")
            self._context_pill.configure(
                text="Pick a name",
                fg_color=COLORS["bg_secondary"],
                text_color=COLORS["text_secondary"],
            )
            self._hero.configure(fg_color=COLORS["highlight_teal"])
            self._focus_title.configure(text="Choose an official or entity")
            self._focus_meta.configure(text="Click a name to open a focused conflict trail.")
            self._focus_note.configure(
                text="This panel will summarize that selection and surface the related records."
            )
            self._set_confidence_counts({})
            self._show_suggestions(aggregates or {})
            return

        self.title_label.configure(text="Selected Conflicts")
        is_official = kind == "official"
        pill_color = COLORS["highlight_soft"] if is_official else COLORS["highlight_teal"]
        pill_text = "Official" if is_official else "Entity"
        hero_fill = COLORS["highlight_soft"] if is_official else COLORS["highlight_teal"]

        flagged_records = [rec for rec in records if rec.get("conflict", {}).get("match", False)]
        shown_records = flagged_records or records
        conf_counts = Counter(
            (rec.get("conflict", {}).get("confidence") or "").lower()
            for rec in flagged_records
        )

        self._context_pill.configure(
            text=pill_text,
            fg_color=pill_color,
            text_color=COLORS["text_primary"],
        )
        self._hero.configure(fg_color=hero_fill)
        self._focus_title.configure(text=self._label_text(name, limit=64))

        total_mentions = len(records)
        total_flagged = len(flagged_records)
        if total_flagged:
            meta_text = f"{total_flagged:,} flagged conflicts in the current view"
            if total_mentions > total_flagged:
                meta_text += f" • {total_mentions:,} mentions total"
        elif total_mentions:
            meta_text = f"No flagged conflicts right now • {total_mentions:,} mentions in view"
        else:
            meta_text = "No records are visible in the current lens"

        if secondary:
            note = f"Current lens is also narrowed by {secondary['kind']}: {secondary['name']}."
        elif total_flagged:
            note = "Use this strip to jump from the selected name into the underlying agenda pages."
        elif total_mentions:
            note = "This selection is present in view, but none of the visible records are currently flagged."
        else:
            note = "Broaden the filters or choose a different name to bring records back into view."

        self._focus_meta.configure(text=meta_text)
        self._focus_note.configure(text=note)
        self._set_confidence_counts(conf_counts)
        self._show_records(kind, shown_records, flagged=bool(flagged_records))

    def _set_confidence_counts(self, counts: dict) -> None:
        self._high_value.configure(text=str(counts.get("high", 0)))
        self._med_value.configure(text=str(counts.get("medium", 0)))
        self._low_value.configure(text=str(counts.get("low", 0)))

    def _show_suggestions(self, aggregates: dict) -> None:
        self._list_heading.configure(text="Standout names in the current view")
        self._clear_list()

        suggestions: list[tuple[str, str, int]] = []
        for name, count in (aggregates.get("officials_counts") or {}).items():
            suggestions.append(("Official", name, count))
        for name, count in (aggregates.get("entities_counts") or {}).items():
            suggestions.append(("Entity", name, count))

        suggestions.sort(key=lambda item: item[2], reverse=True)
        top_suggestions = suggestions[:6]

        if not top_suggestions:
            self._empty_list("No names are available in the current view yet.")
            return

        for idx, (kind, name, count) in enumerate(top_suggestions):
            card = ctk.CTkFrame(
                self._list_frame,
                fg_color=COLORS["bg_card"],
                corner_radius=16,
                border_width=1,
                border_color=COLORS["border"],
            )
            card.grid(row=idx, column=0, sticky="ew", padx=2, pady=4)
            card.grid_columnconfigure(1, weight=1)

            pill_fill = COLORS["highlight_soft"] if kind == "Official" else COLORS["highlight_teal"]
            ctk.CTkLabel(
                card,
                text=kind,
                font=font("label_bold"),
                text_color=COLORS["text_primary"],
                fg_color=pill_fill,
                corner_radius=999,
                padx=10,
                height=26,
            ).grid(row=0, column=0, padx=(10, 8), pady=10, sticky="w")

            ctk.CTkLabel(
                card,
                text=name,
                font=font("body_small"),
                text_color=COLORS["text_primary"],
                justify="left",
                wraplength=180,
            ).grid(row=0, column=1, padx=(0, 8), pady=10, sticky="w")

            ctk.CTkLabel(
                card,
                text=f"{count:,}",
                font=font("label_bold"),
                text_color=COLORS["text_secondary"],
            ).grid(row=0, column=2, padx=(0, 10), pady=10, sticky="e")

    def _show_records(self, focus_kind: str, records: list, flagged: bool) -> None:
        heading = "Flagged records for this selection" if flagged else "Visible mentions for this selection"
        self._list_heading.configure(text=heading)
        self._clear_list()

        if not records:
            self._empty_list("No related records are visible.")
            return

        limited = self._sort_records(records)[:6]
        counterpart_label = "Entities" if focus_kind == "official" else "Officials"

        for idx, rec in enumerate(limited):
            source = rec.get("source", {})
            display_name = Path(source.get("file", "")).name if source.get("file") else "Unknown source"
            page = source.get("page", "—")
            confidence = (rec.get("conflict", {}).get("confidence") or "mention").lower()
            badge_color = {
                "high": COLORS["confidence_high"],
                "medium": COLORS["confidence_medium"],
                "low": COLORS["confidence_low"],
            }.get(confidence, COLORS["text_secondary"])

            if focus_kind == "official":
                counterpart = self._engine.extract_entity_names(rec)
            else:
                counterpart = self._engine.extract_official_names(rec)
            counterpart_text = ", ".join(counterpart[:3]) if counterpart else f"No {counterpart_label.lower()} listed"

            keywords = ", ".join(rec.get("keywords_matched", [])[:4]) or "No keyword matches"
            reasoning = self._excerpt(rec.get("conflict", {}).get("reasoning", ""))

            card = ctk.CTkFrame(
                self._list_frame,
                fg_color=COLORS["bg_card"],
                corner_radius=16,
                border_width=1,
                border_color=COLORS["border"],
            )
            card.grid(row=idx, column=0, sticky="ew", padx=2, pady=4)
            card.grid_columnconfigure(0, weight=1)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
            top.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                top,
                text=display_name,
                font=font("section", size=12),
                text_color=COLORS["text_primary"],
                justify="left",
                wraplength=190,
            ).grid(row=0, column=0, sticky="w")

            ctk.CTkLabel(
                top,
                text=confidence.title(),
                font=font("label_bold"),
                text_color=badge_color,
                fg_color=COLORS["bg_secondary"],
                corner_radius=999,
                padx=10,
                height=24,
            ).grid(row=0, column=1, padx=(8, 0), sticky="e")

            ctk.CTkLabel(
                card,
                text=f"Page {page} • {counterpart_label}: {counterpart_text}",
                font=font("body_small"),
                text_color=COLORS["text_secondary"],
                justify="left",
                wraplength=270,
            ).grid(row=1, column=0, padx=12, pady=(0, 2), sticky="w")

            ctk.CTkLabel(
                card,
                text=f"Keywords: {keywords}",
                font=font("label"),
                text_color=COLORS["text_muted"],
                justify="left",
                wraplength=270,
            ).grid(row=2, column=0, padx=12, pady=(0, 2), sticky="w")

            ctk.CTkLabel(
                card,
                text=reasoning,
                font=font("body_small"),
                text_color=COLORS["text_primary"],
                justify="left",
                wraplength=270,
            ).grid(row=3, column=0, padx=12, pady=(0, 10), sticky="w")

    def _sort_records(self, records: list) -> list:
        order = {"high": 0, "medium": 1, "low": 2}
        return sorted(
            records,
            key=lambda rec: (
                order.get((rec.get("conflict", {}).get("confidence") or "").lower(), 3),
                Path(rec.get("source", {}).get("file", "")).name.casefold(),
                rec.get("source", {}).get("page", 0),
            ),
        )

    def _clear_list(self) -> None:
        for child in self._list_frame.winfo_children():
            child.destroy()

    def _empty_list(self, text: str) -> None:
        ctk.CTkLabel(
            self._list_frame,
            text=text,
            font=font("body_small"),
            text_color=COLORS["text_muted"],
            justify="left",
            wraplength=260,
        ).grid(row=0, column=0, padx=8, pady=12, sticky="w")

    @staticmethod
    def _excerpt(text: str, limit: int = 150) -> str:
        clean = " ".join((text or "").split())
        if not clean:
            return "Reasoning will appear here when available."
        if len(clean) <= limit:
            return clean
        return clean[: limit - 1].rstrip() + "…"

    @staticmethod
    def _label_text(text: str, limit: int = 64) -> str:
        clean = " ".join((text or "").split())
        if len(clean) <= limit:
            return clean
        return clean[: limit - 1].rstrip() + "…"
