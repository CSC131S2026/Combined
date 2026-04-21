"""
OfficialsAgent — scrollable lists of officials and entities with record counts.

Each entry is a clickable button that triggers an external filter callback.
"""

import customtkinter as ctk
from agents.base_agent import BaseAgent
from ui.theme import COLORS


class OfficialsAgent(BaseAgent):

    def __init__(self, parent, row, col, on_filter_click=None, rowspan=1, colspan=1):
        self._on_filter_click = on_filter_click  # callable(type, name) or None
        super().__init__(parent, row, col, rowspan=rowspan, colspan=colspan)

    def get_title(self) -> str:
        return "OFFICIALS & ENTITIES"

    def get_accent_color(self) -> str:
        return COLORS["accent_green"]

    def _build_header_controls(self) -> None:
        pass

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.grid(row=1, column=0, padx=8, pady=(4, 8), sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self._tabs = ctk.CTkTabview(
            body,
            fg_color=COLORS["bg_elevated"],
            segmented_button_fg_color=COLORS["bg_card"],
            segmented_button_selected_color=COLORS["accent_green"],
            segmented_button_selected_hover_color=COLORS["warning"],
            segmented_button_unselected_color=COLORS["bg_card"],
            segmented_button_unselected_hover_color=COLORS["bg_elevated"],
            text_color=COLORS["text_primary"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=8,
        )
        self._tabs.grid(row=0, column=0, sticky="nsew")

        self._tabs.add("Officials")
        self._tabs.add("Entities")

        # Officials scrollable frame
        self._officials_frame = ctk.CTkScrollableFrame(
            self._tabs.tab("Officials"),
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["text_muted"],
        )
        self._officials_frame.pack(fill="both", expand=True)
        self._officials_frame.grid_columnconfigure(0, weight=1)

        # Entities scrollable frame
        self._entities_frame = ctk.CTkScrollableFrame(
            self._tabs.tab("Entities"),
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["text_muted"],
        )
        self._entities_frame.pack(fill="both", expand=True)
        self._entities_frame.grid_columnconfigure(0, weight=1)

        self._placeholder("No data loaded", self._officials_frame)
        self._placeholder("No data loaded", self._entities_frame)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, officials_counts: dict, entities_counts: dict) -> None:
        self._rebuild_list(
            self._officials_frame,
            officials_counts,
            kind="official",
        )
        self._rebuild_list(
            self._entities_frame,
            entities_counts,
            kind="entity",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rebuild_list(self, container: ctk.CTkScrollableFrame, counts: dict, kind: str) -> None:
        for child in container.winfo_children():
            child.destroy()

        if not counts:
            self._placeholder("No data", container)
            return

        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)

        for idx, (name, count) in enumerate(sorted_items):
            row_frame = ctk.CTkFrame(container, fg_color="transparent")
            row_frame.grid(row=idx, column=0, sticky="ew", pady=1)
            row_frame.grid_columnconfigure(0, weight=1)

            btn = ctk.CTkButton(
                row_frame,
                text=name,
                font=ctk.CTkFont("Andale Mono", 10),
                fg_color="transparent",
                hover_color=COLORS["bg_elevated"],
                text_color=COLORS["text_primary"],
                anchor="w",
                height=26,
                command=lambda n=name, k=kind: self._handle_click(k, n),
            )
            btn.grid(row=0, column=0, sticky="ew", padx=(4, 0))

            badge = ctk.CTkLabel(
                row_frame,
                text=str(count),
                font=ctk.CTkFont("Andale Mono", 10, "bold"),
                fg_color=COLORS["bg_card"],
                corner_radius=6,
                text_color=COLORS["accent_green"],
                width=36,
                height=22,
            )
            badge.grid(row=0, column=1, padx=4, pady=2)

        # Stretch column
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
            font=ctk.CTkFont("Andale Mono", 11),
        ).pack(anchor="w", padx=8, pady=12)
