"""
OfficialsAgent — side-by-side lists of officials and entities.

Each row remains clickable, but the panel is designed as a visual index
instead of a generic tabbed list.
"""

import customtkinter as ctk

from agents.base_agent import BaseAgent
from ui.theme import COLORS, font

_MAX_RENDERED_ROWS = 18


class OfficialsAgent(BaseAgent):

    def __init__(self, parent, row, col, on_filter_click=None, rowspan=1, colspan=1):
        self._on_filter_click = on_filter_click
        super().__init__(parent, row, col, rowspan=rowspan, colspan=colspan)

    def get_title(self) -> str:
        return "People and Entities"

    def get_kicker(self) -> str:
        return "Filter index"

    def get_accent_color(self) -> str:
        return COLORS["accent_green"]

    def _build_header_controls(self) -> None:
        pass

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.grid(row=1, column=0, padx=14, pady=(2, 14), sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        (
            self._official_panel,
            self._official_count_lbl,
            self._official_summary_lbl,
            self._officials_frame,
        ) = self._build_column(
            body,
            column=0,
            title="Officials",
            accent=COLORS["accent_purple"],
            fill=COLORS["highlight_soft"],
            subtitle="Click a name to pivot the full dashboard.",
        )
        (
            self._entity_panel,
            self._entity_count_lbl,
            self._entity_summary_lbl,
            self._entities_frame,
        ) = self._build_column(
            body,
            column=1,
            title="Entities",
            accent=COLORS["accent_green"],
            fill=COLORS["highlight_teal"],
            subtitle="A live index of organizations mentioned in view.",
        )

        self._placeholder("No data loaded", self._officials_frame)
        self._placeholder("No data loaded", self._entities_frame)

    def _build_column(self, parent, column: int, title: str, accent: str, fill: str, subtitle: str):
        panel = ctk.CTkFrame(
            parent,
            fg_color=fill,
            corner_radius=22,
            border_width=1,
            border_color=COLORS["border"],
        )
        panel.grid(row=0, column=column, sticky="nsew", padx=(0, 6) if column == 0 else (6, 0))
        panel.grid_rowconfigure(2, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 4))
        header.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            header,
            text=title,
            font=font("section", size=14),
            text_color=COLORS["text_primary"],
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        count_lbl = ctk.CTkLabel(
            header,
            text="0",
            font=font("label_bold"),
            text_color=accent,
            fg_color=COLORS["bg_card"],
            corner_radius=999,
            width=46,
            height=26,
        )
        count_lbl.grid(row=0, column=1, sticky="e")

        summary_lbl = ctk.CTkLabel(
            panel,
            text=subtitle,
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
            justify="left",
            wraplength=220,
        )
        summary_lbl.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 6))

        scroll = ctk.CTkFrame(
            panel,
            fg_color="transparent",
        )
        scroll.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        scroll.grid_columnconfigure(0, weight=1)

        return panel, count_lbl, summary_lbl, scroll

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(
        self,
        officials_counts: dict,
        entities_counts: dict,
        selected_kind: str | None = None,
        selected_name: str | None = None,
    ) -> None:
        self._official_panel.configure(
            border_color=COLORS["accent_purple"] if selected_kind == "official" and selected_name else COLORS["border"],
            border_width=2 if selected_kind == "official" and selected_name else 1,
        )
        self._entity_panel.configure(
            border_color=COLORS["accent_green"] if selected_kind == "entity" and selected_name else COLORS["border"],
            border_width=2 if selected_kind == "entity" and selected_name else 1,
        )
        self._update_column_summary(
            counts=officials_counts,
            badge=self._official_count_lbl,
            summary=self._official_summary_lbl,
            fallback="Click a name to pivot the full dashboard.",
            prefix="Top official",
        )
        self._update_column_summary(
            counts=entities_counts,
            badge=self._entity_count_lbl,
            summary=self._entity_summary_lbl,
            fallback="A live index of organizations mentioned in view.",
            prefix="Top entity",
        )
        self._rebuild_list(
            self._officials_frame,
            officials_counts,
            kind="official",
            accent=COLORS["accent_purple"],
            hover=COLORS["highlight_soft"],
            selected_name=selected_name if selected_kind == "official" else None,
        )
        self._rebuild_list(
            self._entities_frame,
            entities_counts,
            kind="entity",
            accent=COLORS["accent_green"],
            hover=COLORS["highlight_teal"],
            selected_name=selected_name if selected_kind == "entity" else None,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_column_summary(self, counts: dict, badge, summary, fallback: str, prefix: str) -> None:
        total = len(counts or {})
        badge.configure(text=str(total))
        if counts:
            name, count = max(counts.items(), key=lambda item: item[1])
            if total > _MAX_RENDERED_ROWS:
                summary.configure(
                    text=(
                        f"{prefix}: {name} ({count:,}) • "
                        f"showing top {_MAX_RENDERED_ROWS} of {total:,}; use the sidebar dropdown for the full set"
                    )
                )
            else:
                summary.configure(text=f"{prefix}: {name} ({count:,})")
        else:
            summary.configure(text=fallback)

    def _rebuild_list(
        self,
        container: ctk.CTkFrame,
        counts: dict,
        kind: str,
        accent: str,
        hover: str,
        selected_name: str | None = None,
    ) -> None:
        for child in container.winfo_children():
            child.destroy()

        if not counts:
            self._placeholder("No matches in this view", container)
            return

        sorted_items = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        rendered_items = sorted_items[:_MAX_RENDERED_ROWS]
        selected_key = selected_name.casefold() if selected_name else None

        for idx, (name, count) in enumerate(rendered_items):
            is_selected = selected_key == name.casefold()
            row = ctk.CTkFrame(
                container,
                fg_color=hover if is_selected else COLORS["bg_card"],
                corner_radius=16,
                border_width=2 if is_selected else 1,
                border_color=accent if is_selected else COLORS["border"],
            )
            row.grid(row=idx, column=0, sticky="ew", pady=4, padx=2)
            row.grid_columnconfigure(0, weight=1)

            btn = ctk.CTkButton(
                row,
                text=name,
                font=font("body_small"),
                fg_color=hover if is_selected else "transparent",
                hover_color=hover,
                text_color=accent if is_selected else COLORS["text_primary"],
                anchor="w",
                height=34,
                corner_radius=12,
                command=lambda n=name, k=kind: self._handle_click(k, n),
            )
            btn.grid(row=0, column=0, sticky="ew", padx=(8, 4), pady=6)

            badge = ctk.CTkLabel(
                row,
                text=f"{count:,}",
                font=font("label_bold"),
                fg_color=accent if is_selected else hover,
                corner_radius=999,
                text_color=COLORS["text_inverse"] if is_selected else accent,
                width=52,
                height=28,
            )
            badge.grid(row=0, column=1, padx=(0, 8), pady=6)

        container.grid_columnconfigure(0, weight=1)

    def _handle_click(self, kind: str, name: str) -> None:
        if self._on_filter_click:
            self._on_filter_click(kind, name)

    @staticmethod
    def _placeholder(text: str, parent) -> None:
        ctk.CTkLabel(
            parent,
            text=text,
            text_color=COLORS["text_muted"],
            font=font("body_small"),
        ).pack(anchor="w", padx=8, pady=12)
