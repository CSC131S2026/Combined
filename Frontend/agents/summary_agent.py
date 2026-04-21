"""
SummaryAgent — KPI summary panel.

Displays 4 value cards (Total Analyzed, Conflicts Flagged,
High Confidence, Medium/Low) plus a progress bar for % flagged.
"""

import customtkinter as ctk
from agents.base_agent import BaseAgent
from ui.theme import COLORS


class SummaryAgent(BaseAgent):

    def get_title(self) -> str:
        return "CONFLICT SUMMARY"

    def get_accent_color(self) -> str:
        return COLORS["accent_purple"]

    def _build_header_controls(self) -> None:
        pass  # No controls for this agent

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.grid(row=1, column=0, padx=8, pady=(4, 8), sticky="nsew")
        body.grid_rowconfigure((0, 1), weight=1)
        body.grid_columnconfigure((0, 1), weight=1)
        self._body = body

        # 4 value cards in a 2x2 grid
        self._total_val, self._total_sub = self._make_value_card(
            body, "TOTAL ANALYZED", "—", "records",
            COLORS["accent_purple"], row=0, col=0,
        )
        self._flagged_val, self._flagged_sub = self._make_value_card(
            body, "CONFLICTS FLAGGED", "—", "flagged",
            COLORS["danger"], row=0, col=1,
        )
        self._high_val, self._high_sub = self._make_value_card(
            body, "HIGH CONFIDENCE", "—", "conflicts",
            COLORS["confidence_high"], row=1, col=0,
        )
        self._medlow_val, self._medlow_sub = self._make_value_card(
            body, "MEDIUM / LOW", "— / —", "conflicts",
            COLORS["warning"], row=1, col=1,
        )

        # Progress bar frame below the cards
        prog_frame = ctk.CTkFrame(self.frame, fg_color=COLORS["bg_elevated"], corner_radius=8)
        prog_frame.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="ew")
        prog_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            prog_frame, text="FLAGGED %",
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        ).grid(row=0, column=0, padx=(10, 8), pady=8)

        self._progress_bar = ctk.CTkProgressBar(
            prog_frame,
            progress_color=COLORS["danger"],
            fg_color=COLORS["bg_card"],
            height=12,
            corner_radius=6,
        )
        self._progress_bar.set(0)
        self._progress_bar.grid(row=0, column=1, padx=(0, 8), pady=8, sticky="ew")

        self._pct_label = ctk.CTkLabel(
            prog_frame, text="0%",
            font=ctk.CTkFont("Andale Mono", 11, "bold"),
            text_color=COLORS["danger"],
            width=42,
        )
        self._pct_label.grid(row=0, column=2, padx=(0, 10), pady=8)

        # Extend frame layout to accommodate the progress row
        self.frame.grid_rowconfigure(2, weight=0)

    def update(self, aggregates: dict, filtered_aggregates: dict = None) -> None:
        """
        Update the KPI cards.
        aggregates         — full dataset stats
        filtered_aggregates — stats for the current filter (optional)
        """
        agg  = aggregates or {}
        fagg = filtered_aggregates or agg

        total   = agg.get("total",   0)
        flagged = fagg.get("flagged", 0)
        conf    = fagg.get("by_confidence", {})
        high    = conf.get("high",   0)
        med     = conf.get("medium", 0)
        low     = conf.get("low",    0)

        self._total_val.configure(text=f"{total:,}")
        self._flagged_val.configure(text=f"{flagged:,}")
        self._high_val.configure(text=f"{high:,}")
        self._medlow_val.configure(text=f"{med:,} / {low:,}")

        # Show filtered count as sub-text if different from total
        f_total = fagg.get("total", total)
        if filtered_aggregates and f_total != total:
            self._total_sub.configure(text=f"({f_total:,} shown)")
        else:
            self._total_sub.configure(text="records")

        pct = (flagged / f_total) if f_total > 0 else 0.0
        self._progress_bar.set(pct)
        self._pct_label.configure(text=f"{pct * 100:.1f}%")
