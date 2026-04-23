"""
Abstract base class for all conflict-of-interest dashboard agents.

Provides:
  - a shared editorial card shell
  - visual alert state handling
  - helper for compact metric cards
"""

from abc import ABC, abstractmethod

import customtkinter as ctk

from ui.theme import COLORS, font


class BaseAgent(ABC):

    def __init__(
        self,
        parent,
        row: int,
        col: int,
        rowspan: int = 1,
        colspan: int = 1,
    ):
        self.parent = parent
        self._alert_active = False

        self.frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=26,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.frame.grid(
            row=row,
            column=col,
            rowspan=rowspan,
            columnspan=colspan,
            padx=10,
            pady=10,
            sticky="nsew",
        )
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_body()

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        self.header_frame = ctk.CTkFrame(
            self.frame,
            fg_color="transparent",
            height=64,
        )
        self.header_frame.grid(
            row=0,
            column=0,
            padx=16,
            pady=(14, 4),
            sticky="ew",
        )
        self.header_frame.grid_propagate(False)
        self.header_frame.grid_columnconfigure(0, weight=1)

        title_stack = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_stack.grid(row=0, column=0, sticky="w")

        meta_row = ctk.CTkFrame(title_stack, fg_color="transparent")
        meta_row.pack(anchor="w", pady=(0, 2))

        ctk.CTkFrame(
            meta_row,
            fg_color=self.get_accent_color(),
            width=34,
            height=6,
            corner_radius=999,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            meta_row,
            text=self.get_kicker(),
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).pack(side="left")

        self.title_label = ctk.CTkLabel(
            title_stack,
            text=self.get_title(),
            font=font("headline", size=17),
            text_color=COLORS["text_primary"],
        )
        self.title_label.pack(anchor="w")

        self._build_header_controls()

    @abstractmethod
    def get_title(self) -> str:
        ...

    @abstractmethod
    def get_accent_color(self) -> str:
        ...

    def get_kicker(self) -> str:
        return "Panel"

    def _build_header_controls(self) -> None:
        """Override to add widgets to the right side of the header."""

    @abstractmethod
    def _build_body(self) -> None:
        ...

    # ------------------------------------------------------------------
    # Alert / highlight state
    # ------------------------------------------------------------------

    def set_alert(self, active: bool, color: str = None) -> None:
        if active == self._alert_active:
            return

        self._alert_active = active
        if active:
            self.frame.configure(
                border_color=color or COLORS["danger"],
                border_width=2,
            )
        else:
            self.frame.configure(
                border_color=COLORS["border"],
                border_width=1,
            )

    # ------------------------------------------------------------------
    # Shared widget helpers
    # ------------------------------------------------------------------

    def _make_value_card(
        self,
        parent,
        heading: str,
        value_text: str,
        sub_text: str,
        color: str,
        row: int = 0,
        col: int = 0,
        rowspan: int = 1,
        colspan: int = 1,
        fill_color: str | None = None,
    ) -> tuple:
        """
        Create a compact metric card with a subtle accent rail.
        Returns (value_label, sub_label) so callers can update them.
        """
        card = ctk.CTkFrame(
            parent,
            fg_color=fill_color or COLORS["bg_secondary"],
            corner_radius=20,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(
            row=row,
            column=col,
            rowspan=rowspan,
            columnspan=colspan,
            padx=5,
            pady=5,
            sticky="nsew",
        )
        card.grid_columnconfigure(1, weight=1)

        accent = ctk.CTkFrame(
            card,
            fg_color=color,
            width=8,
            corner_radius=999,
        )
        accent.grid(row=0, column=0, rowspan=3, sticky="ns", padx=(12, 10), pady=14)

        ctk.CTkLabel(
            card,
            text=heading,
            font=font("label"),
            text_color=COLORS["text_muted"],
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(0, 14), pady=(14, 0))

        val_lbl = ctk.CTkLabel(
            card,
            text=value_text,
            font=font("metric_small", size=28),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        val_lbl.grid(row=1, column=1, sticky="w", padx=(0, 14), pady=(1, 0))

        sub_lbl = ctk.CTkLabel(
            card,
            text=sub_text,
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
            anchor="w",
            justify="left",
        )
        sub_lbl.grid(row=2, column=1, sticky="w", padx=(0, 14), pady=(0, 14))

        return val_lbl, sub_lbl
