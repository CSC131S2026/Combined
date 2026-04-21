"""
Abstract base class for all conflict-of-interest dashboard agents.

Provides:
  - Standardised two-row frame layout (header + body)
  - Visual alert / highlight state (border colour + width)
  - Shared helper: _make_value_card()

Subclasses must implement:
  get_title(), get_accent_color(), _build_header_controls(),
  _build_body(), update(...)
"""

from abc import ABC, abstractmethod
import customtkinter as ctk
from ui.theme import COLORS


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

        # Outer card frame
        self.frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.frame.grid(
            row=row, column=col,
            rowspan=rowspan, columnspan=colspan,
            padx=8, pady=8,
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
            fg_color=COLORS["bg_elevated"],
            corner_radius=8,
            height=46,
        )
        self.header_frame.grid(
            row=0, column=0,
            padx=8, pady=(8, 4),
            sticky="ew",
        )
        self.header_frame.grid_propagate(False)
        self.header_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text=self.get_title(),
            font=ctk.CTkFont("Andale Mono", 13, "bold"),
            text_color=self.get_accent_color(),
        )
        self.title_label.grid(row=0, column=0, padx=12, pady=6, sticky="w")

        self._build_header_controls()

    @abstractmethod
    def get_title(self) -> str:
        ...

    @abstractmethod
    def get_accent_color(self) -> str:
        ...

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
    ) -> tuple:
        """
        Create a compact labelled card with a large value and subtitle.
        Returns (value_label, sub_label) so callers can update them.
        """
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_elevated"], corner_radius=8)
        card.grid(
            row=row, column=col,
            rowspan=rowspan, columnspan=colspan,
            padx=4, pady=4, sticky="nsew",
        )
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text=heading,
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        ).grid(row=0, column=0, pady=(10, 0))

        val_lbl = ctk.CTkLabel(
            card, text=value_text,
            font=ctk.CTkFont("Andale Mono", 32, "bold"),
            text_color=color,
        )
        val_lbl.grid(row=1, column=0, pady=(2, 0))

        sub_lbl = ctk.CTkLabel(
            card, text=sub_text,
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        )
        sub_lbl.grid(row=2, column=0, pady=(0, 10))

        return val_lbl, sub_lbl
