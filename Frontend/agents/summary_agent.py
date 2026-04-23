"""SummaryAgent — compact editorial KPI overview panel."""

import customtkinter as ctk

from agents.base_agent import BaseAgent
from ui.theme import COLORS, font


class SummaryAgent(BaseAgent):

    def get_title(self) -> str:
        return "Conflict Snapshot"

    def get_kicker(self) -> str:
        return "Lead view"

    def get_accent_color(self) -> str:
        return COLORS["accent_purple"]

    def _build_header_controls(self) -> None:
        pass

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=4)
        body.grid_columnconfigure(1, weight=2)
        body.grid_columnconfigure(2, weight=2)

        hero = ctk.CTkFrame(
            body,
            fg_color=COLORS["highlight_soft"],
            corner_radius=22,
            border_width=1,
            border_color=COLORS["border"],
        )
        hero.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 5), pady=4)
        hero.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hero,
            text="Potential conflicts in view",
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, padx=16, pady=(16, 2), sticky="w")

        self._hero_value = ctk.CTkLabel(
            hero,
            text="—",
            font=font("metric", size=40),
            text_color=COLORS["danger"],
        )
        self._hero_value.grid(row=1, column=0, padx=16, sticky="w")

        self._hero_pct = ctk.CTkLabel(
            hero,
            text="0.0% flag rate in current view",
            font=font("section", size=12),
            text_color=COLORS["text_primary"],
        )
        self._hero_pct.grid(row=2, column=0, padx=16, pady=(0, 4), sticky="w")

        self._hero_note = ctk.CTkLabel(
            hero,
            text="Load data to begin reviewing conflict signals.",
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
            justify="left",
            wraplength=260,
        )
        self._hero_note.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="nw")

        self._dataset_val, self._dataset_sub = self._make_value_card(
            body,
            "Dataset size",
            "—",
            "records loaded",
            COLORS["accent_gold"],
            row=0,
            col=1,
            fill_color=COLORS["highlight_gold"],
        )
        self._high_val, self._high_sub = self._make_value_card(
            body,
            "High confidence",
            "—",
            "review first",
            COLORS["confidence_high"],
            row=0,
            col=2,
            fill_color=COLORS["highlight_soft"],
        )
        self._med_val, self._med_sub = self._make_value_card(
            body,
            "Medium confidence",
            "—",
            "secondary pass",
            COLORS["confidence_medium"],
            row=1,
            col=1,
            fill_color=COLORS["highlight_gold"],
        )
        self._low_val, self._low_sub = self._make_value_card(
            body,
            "Low confidence",
            "—",
            "monitoring trail",
            COLORS["confidence_low"],
            row=1,
            col=2,
            fill_color=COLORS["highlight_green"],
        )

    def update(self, aggregates: dict, filtered_aggregates: dict = None) -> None:
        agg = aggregates or {}
        fagg = filtered_aggregates or agg

        dataset_total = agg.get("total", 0)
        shown = fagg.get("total", dataset_total)
        flagged = fagg.get("flagged", 0)
        conf = fagg.get("by_confidence", {})
        high = conf.get("high", 0)
        medium = conf.get("medium", 0)
        low = conf.get("low", 0)

        self._hero_value.configure(text=f"{flagged:,}")
        self._dataset_val.configure(text=f"{dataset_total:,}")
        self._high_val.configure(text=f"{high:,}")
        self._med_val.configure(text=f"{medium:,}")
        self._low_val.configure(text=f"{low:,}")

        if filtered_aggregates and shown != dataset_total:
            self._dataset_sub.configure(text=f"{shown:,} currently in view")
        elif dataset_total:
            self._dataset_sub.configure(text="all loaded records visible")
        else:
            self._dataset_sub.configure(text="records loaded")

        flagged_share = (flagged / shown) if shown else 0.0
        self._hero_pct.configure(text=f"{flagged_share * 100:.1f}% flag rate in current view")

        dominant_conf = max(
            (("high", high), ("medium", medium), ("low", low)),
            key=lambda item: item[1],
        )[0]
        dominant_label = dominant_conf.title()

        if shown == 0:
            note = "No records match the current filters yet."
        elif flagged == 0:
            note = "The current slice is clear of conflict matches, so this is a good lens for comparison."
        elif filtered_aggregates and shown != dataset_total:
            note = (
                f"The active filters narrow the dataset to {shown:,} records. "
                f"{dominant_label} confidence currently leads this slice."
            )
        else:
            note = (
                f"The full dataset surfaces {flagged:,} matches across {shown:,} records, "
                f"with {dominant_label.lower()} confidence appearing most often."
            )
        self._hero_note.configure(text=note)
