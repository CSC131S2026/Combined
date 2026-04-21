"""
ConfidenceAgent — horizontal bar chart showing confidence level breakdown.

Uses Matplotlib embedded via FigureCanvasTkAgg with a dark theme
matching the dashboard's color palette.
"""

import customtkinter as ctk
from agents.base_agent import BaseAgent
from ui.theme import COLORS

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _MATPLOTLIB_AVAILABLE = True
except ImportError:
    _MATPLOTLIB_AVAILABLE = False


class ConfidenceAgent(BaseAgent):

    def get_title(self) -> str:
        return "CONFIDENCE BREAKDOWN"

    def get_accent_color(self) -> str:
        return COLORS["accent_green"]

    def _build_header_controls(self) -> None:
        self._show_filtered = ctk.BooleanVar(value=True)
        self._toggle = ctk.CTkSwitch(
            self.header_frame,
            text="Show filtered",
            variable=self._show_filtered,
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
            button_color=COLORS["accent_green"],
            button_hover_color=COLORS["success"],
            progress_color=COLORS["accent_green"],
            onvalue=True,
            offvalue=False,
            command=self._on_toggle,
            width=80,
            height=20,
        )
        self._toggle.grid(row=0, column=1, padx=12, pady=6, sticky="e")
        self.header_frame.grid_columnconfigure(1, weight=0)

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.grid(row=1, column=0, padx=8, pady=(4, 8), sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        self._body = body

        self._full_agg    = None
        self._filter_agg  = None

        if _MATPLOTLIB_AVAILABLE:
            self._build_chart(body)
        else:
            ctk.CTkLabel(
                body,
                text="matplotlib not installed\npip install matplotlib",
                text_color=COLORS["text_muted"],
                font=ctk.CTkFont("Andale Mono", 11),
            ).grid(row=0, column=0, padx=20, pady=20)

    def _build_chart(self, parent) -> None:
        bg = COLORS["bg_elevated"]
        self._fig = Figure(figsize=(4, 2.4), facecolor=bg, tight_layout=True)
        self._ax  = self._fig.add_subplot(111)
        self._ax.set_facecolor(bg)

        self._canvas = FigureCanvasTkAgg(self._fig, master=parent)
        widget = self._canvas.get_tk_widget()
        widget.configure(bg=COLORS["bg_card"])
        widget.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        self._draw_chart({"high": 0, "medium": 0, "low": 0})

    def _draw_chart(self, by_confidence: dict) -> None:
        if not _MATPLOTLIB_AVAILABLE:
            return

        ax = self._ax
        ax.clear()
        bg = COLORS["bg_elevated"]
        ax.set_facecolor(bg)
        self._fig.patch.set_facecolor(bg)

        labels  = ["HIGH",   "MEDIUM",   "LOW"]
        values  = [
            by_confidence.get("high",   0),
            by_confidence.get("medium", 0),
            by_confidence.get("low",    0),
        ]
        bar_colors = [
            COLORS["confidence_high"],
            COLORS["confidence_medium"],
            COLORS["confidence_low"],
        ]

        bars = ax.barh(labels, values, color=bar_colors, height=0.55)

        # Style the axes
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(COLORS["border"])
        ax.spines["bottom"].set_color(COLORS["border"])
        ax.tick_params(axis="both", colors=COLORS["text_secondary"], labelsize=9)
        ax.set_xlabel("Record Count", color=COLORS["text_secondary"], fontsize=9)

        # Value labels on each bar
        max_v = max(values) if values else 1
        for bar, val in zip(bars, values):
            if val > 0:
                x_pos = bar.get_width() + max_v * 0.015
                ax.text(
                    x_pos,
                    bar.get_y() + bar.get_height() / 2,
                    f"{val:,}",
                    va="center", ha="left",
                    color=COLORS["text_primary"],
                    fontsize=9,
                    fontfamily="monospace",
                )

        ax.set_xlim(0, max(max_v * 1.15, 1))

        self._canvas.draw_idle()

    def _on_toggle(self) -> None:
        self._refresh_from_cache()

    def _refresh_from_cache(self) -> None:
        if self._show_filtered.get() and self._filter_agg:
            self._draw_chart(self._filter_agg.get("by_confidence", {}))
        elif self._full_agg:
            self._draw_chart(self._full_agg.get("by_confidence", {}))

    def update(self, aggregates: dict, filtered_aggregates: dict = None) -> None:
        self._full_agg   = aggregates
        self._filter_agg = filtered_aggregates
        self._refresh_from_cache()
