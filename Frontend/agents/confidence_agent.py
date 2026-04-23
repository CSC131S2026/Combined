"""
ConfidenceAgent — custom confidence distribution lanes.

Uses native CustomTkinter widgets so the breakdown feels visually
connected to the rest of the dashboard instead of like an embedded chart.
"""

import customtkinter as ctk

from agents.base_agent import BaseAgent
from ui.theme import COLORS, font


class ConfidenceAgent(BaseAgent):

    def get_title(self) -> str:
        return "Confidence Lanes"

    def get_kicker(self) -> str:
        return "Distribution"

    def get_accent_color(self) -> str:
        return COLORS["accent_green"]

    def _build_header_controls(self) -> None:
        self._show_filtered = ctk.BooleanVar(value=True)
        self._toggle = ctk.CTkSwitch(
            self.header_frame,
            text="Use current view",
            variable=self._show_filtered,
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
            button_color=COLORS["accent_green"],
            button_hover_color=COLORS["accent_emerald"],
            progress_color=COLORS["accent_green"],
            onvalue=True,
            offvalue=False,
            command=self._on_toggle,
        )
        self._toggle.grid(row=0, column=1, padx=4, pady=8, sticky="e")
        self.header_frame.grid_columnconfigure(1, weight=0)

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.grid(row=1, column=0, padx=14, pady=(2, 14), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)

        summary = ctk.CTkFrame(
            body,
            fg_color=COLORS["highlight_teal"],
            corner_radius=22,
            border_width=1,
            border_color=COLORS["border"],
        )
        summary.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        summary.grid_columnconfigure(0, weight=1)

        self._summary_title = ctk.CTkLabel(
            summary,
            text="Filtered view",
            font=font("section", size=14),
            text_color=COLORS["text_primary"],
        )
        self._summary_title.grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")

        self._summary_note = ctk.CTkLabel(
            summary,
            text="Confidence mix will appear here once data is loaded.",
            font=font("body"),
            text_color=COLORS["text_secondary"],
            justify="left",
            wraplength=260,
        )
        self._summary_note.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")

        self._lane_widgets: dict[str, dict] = {}
        lane_specs = [
            ("high", "High confidence", "Escalate first", COLORS["confidence_high"], COLORS["highlight_soft"]),
            ("medium", "Medium confidence", "Worth a second pass", COLORS["confidence_medium"], COLORS["highlight_gold"]),
            ("low", "Low confidence", "Background signal", COLORS["confidence_low"], COLORS["highlight_green"]),
        ]

        for row, (key, title, descriptor, color, fill) in enumerate(lane_specs, start=1):
            lane = ctk.CTkFrame(
                body,
                fg_color=fill,
                corner_radius=20,
                border_width=1,
                border_color=COLORS["border"],
            )
            lane.grid(row=row, column=0, sticky="ew", pady=5)
            lane.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                lane,
                text=title,
                font=font("section", size=13),
                text_color=COLORS["text_primary"],
            ).grid(row=0, column=0, padx=16, pady=(14, 0), sticky="w")

            ctk.CTkLabel(
                lane,
                text=descriptor,
                font=font("label"),
                text_color=COLORS["text_muted"],
            ).grid(row=1, column=0, padx=16, pady=(0, 2), sticky="w")

            count_lbl = ctk.CTkLabel(
                lane,
                text="—",
                font=font("metric_small", size=26),
                text_color=color,
            )
            count_lbl.grid(row=0, column=1, rowspan=2, padx=(12, 16), pady=(10, 0), sticky="e")

            progress = ctk.CTkProgressBar(
                lane,
                progress_color=color,
                fg_color=COLORS["bg_card"],
                height=12,
                corner_radius=999,
            )
            progress.grid(row=2, column=0, padx=(16, 10), pady=(8, 14), sticky="ew")
            progress.set(0)

            pct_lbl = ctk.CTkLabel(
                lane,
                text="0%",
                font=font("label_bold"),
                text_color=COLORS["text_secondary"],
                width=48,
            )
            pct_lbl.grid(row=2, column=1, padx=(0, 16), pady=(8, 14), sticky="e")

            self._lane_widgets[key] = {
                "count": count_lbl,
                "progress": progress,
                "pct": pct_lbl,
            }

        self._full_agg = None
        self._filter_agg = None

    def _on_toggle(self) -> None:
        self._refresh_from_cache()

    def _refresh_from_cache(self) -> None:
        current = self._filter_agg if self._show_filtered.get() and self._filter_agg else self._full_agg
        if not current:
            return

        conf = current.get("by_confidence", {})
        total = current.get("total", 0)
        if total <= 0:
            total = sum(conf.values())

        dominant_key, dominant_value = max(
            (("high", conf.get("high", 0)), ("medium", conf.get("medium", 0)), ("low", conf.get("low", 0))),
            key=lambda item: item[1],
        )

        lens_label = "current filtered view" if self._show_filtered.get() and self._filter_agg else "full dataset"
        self._summary_title.configure(text=f"Reading the {lens_label}")

        if total <= 0:
            note = "No records are available in this view yet."
        else:
            dominant_text = dominant_key.title()
            note = (
                f"{dominant_text} confidence leads with {dominant_value:,} records. "
                f"Use this mix to decide whether to escalate, review, or simply monitor."
            )
        self._summary_note.configure(text=note)

        for key, widgets in self._lane_widgets.items():
            count = conf.get(key, 0)
            share = (count / total) if total else 0.0
            widgets["count"].configure(text=f"{count:,}")
            widgets["pct"].configure(text=f"{share * 100:.1f}%")
            widgets["progress"].set(share)

    def update(self, aggregates: dict, filtered_aggregates: dict = None) -> None:
        self._full_agg = aggregates or {}
        self._filter_agg = filtered_aggregates or {}
        self._refresh_from_cache()
