"""
ConflictDashboard — main orchestrator.

Coordinates:
  - editorial header / overview shell
  - sidebar controls for data, filters, and exports
  - asymmetric agent board for summary, confidence, people, and record review
  - background data loading via DataLoader
"""

import csv
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from agents.browser_agent import BrowserAgent
from agents.confidence_agent import ConfidenceAgent
from agents.officials_agent import OfficialsAgent
from agents.summary_agent import SummaryAgent
from core.data_loader import DataLoader, DEFAULT_PATH, BACKEND_DIR
from core.filter_engine import FilterEngine
from ui.email_dialog import EmailDialog
from ui.theme import COLORS, font, resolve_color


class ConflictDashboard:

    def __init__(self, root: ctk.CTk):
        self.root = root
        self._loader = DataLoader()
        self._engine = FilterEngine()

        self._all_records: list = []
        self._filtered_records: list = []
        self._meta: dict = {}
        self._all_agg: dict = {}
        self._filtered_agg: dict = {}

        self._json_files: dict[str, Path] = {}
        self._loaded_path: Path | None = None

        self._configure_root()
        self._build_header()
        self._build_body()

        self.root.after(100, self._initial_scan_and_load)

    # ------------------------------------------------------------------
    # Root configuration
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        self.root.title("Sacramento County — Conflict Signals Dashboard")
        self.root.geometry("1640x980")
        self.root.minsize(1260, 840)
        self.root.configure(fg_color=COLORS["bg_primary"])
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        hdr = ctk.CTkFrame(
            self.root,
            fg_color=COLORS["bg_secondary"],
            corner_radius=30,
            border_width=1,
            border_color=COLORS["border"],
        )
        hdr.grid(row=0, column=0, padx=20, pady=(20, 12), sticky="ew")
        hdr.grid_columnconfigure(0, weight=3)
        hdr.grid_columnconfigure(1, weight=2)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.grid(row=0, column=0, padx=(22, 18), pady=22, sticky="nsew")

        ctk.CTkLabel(
            left,
            text="Sacramento County ethics review",
            font=font("label_bold"),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            left,
            text="Conflict Signals Dashboard",
            font=font("hero"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(4, 6))

        self._header_desc_lbl = ctk.CTkLabel(
            left,
            text=(
                "A warmer, more legible analyst workspace for reviewing Form 700 matches, "
                "agenda packets, and the reasoning behind each flagged record."
            ),
            font=font("body"),
            text_color=COLORS["text_secondary"],
            justify="left",
            wraplength=620,
        )
        self._header_desc_lbl.pack(anchor="w")

        pill_row = ctk.CTkFrame(left, fg_color="transparent")
        pill_row.pack(anchor="w", pady=(16, 0))

        self._header_file_pill = ctk.CTkLabel(
            pill_row,
            text="Source · waiting for data",
            font=font("label_bold"),
            text_color=COLORS["text_primary"],
            fg_color=COLORS["highlight_gold"],
            corner_radius=999,
            padx=16,
            height=32,
        )
        self._header_file_pill.pack(side="left", padx=(0, 8))

        self._header_view_pill = ctk.CTkLabel(
            pill_row,
            text="0 in view",
            font=font("label_bold"),
            text_color=COLORS["text_inverse"],
            fg_color=COLORS["accent_purple"],
            corner_radius=999,
            padx=16,
            height=32,
        )
        self._header_view_pill.pack(side="left")

        stats = ctk.CTkFrame(hdr, fg_color="transparent")
        stats.grid(row=0, column=1, padx=(0, 22), pady=22, sticky="nsew")
        stats.grid_columnconfigure(0, weight=1)
        stats.grid_columnconfigure(1, weight=1)
        stats.grid_rowconfigure(1, weight=1)
        stats.grid_rowconfigure(2, weight=1)

        header_actions = ctk.CTkFrame(stats, fg_color="transparent")
        header_actions.grid(row=0, column=0, columnspan=2, sticky="e", padx=6, pady=(0, 4))

        ctk.CTkLabel(
            header_actions,
            text="Appearance",
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).pack(side="left", padx=(0, 8))

        self._appearance_var = ctk.BooleanVar(
            value=ctk.get_appearance_mode().lower() == "dark"
        )
        self._appearance_switch = ctk.CTkSwitch(
            header_actions,
            text="Dark mode",
            variable=self._appearance_var,
            onvalue=True,
            offvalue=False,
            command=self._on_appearance_change,
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
            button_color=COLORS["accent_purple"],
            button_hover_color=COLORS["accent_violet"],
            progress_color=COLORS["accent_purple"],
        )
        self._appearance_switch.pack(side="left")

        self._header_dataset_value, self._header_dataset_sub = self._make_stat_card(
            stats, row=1, col=0, title="Loaded records"
        )
        self._header_pages_value, self._header_pages_sub = self._make_stat_card(
            stats, row=1, col=1, title="Pages analyzed"
        )
        self._header_model_value, self._header_model_sub = self._make_stat_card(
            stats, row=2, col=0, title="Provider / model"
        )
        self._header_generated_value, self._header_generated_sub = self._make_stat_card(
            stats, row=2, col=1, title="Generated"
        )

    def _make_stat_card(self, parent, row: int, col: int, title: str) -> tuple[ctk.CTkLabel, ctk.CTkLabel]:
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=22,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text=title,
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, padx=14, pady=(14, 2), sticky="w")

        value = ctk.CTkLabel(
            card,
            text="—",
            font=font("headline", size=18),
            text_color=COLORS["text_primary"],
            justify="left",
        )
        value.grid(row=1, column=0, padx=14, sticky="w")

        sub = ctk.CTkLabel(
            card,
            text="",
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
            justify="left",
            wraplength=220,
        )
        sub.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="w")

        return value, sub

    def _on_appearance_change(self) -> None:
        mode = "dark" if self._appearance_var.get() else "light"
        ctk.set_appearance_mode(mode)
        if hasattr(self, "_browser_agent"):
            self._browser_agent.refresh_theme()

    def _update_header_meta(self) -> None:
        meta = self._meta
        loaded_total = self._all_agg.get("total", len(self._all_records))
        flagged_total = self._all_agg.get("flagged", 0)
        shown = self._filtered_agg.get("total", len(self._filtered_records))

        pages_analyzed = meta.get("total_pages_analyzed", loaded_total)
        pages_scanned = meta.get("total_pages_scanned", pages_analyzed)
        provider = meta.get("provider", "dataset")
        model = meta.get("model", "—")
        prompt_version = meta.get("prompt_version")
        generated = self._format_generated_at(meta.get("generated_at"))
        current_name = self._loaded_path.name if self._loaded_path else DEFAULT_PATH.name

        self._header_file_pill.configure(text=f"Source · {current_name}")
        self._header_view_pill.configure(text=f"{shown:,} in view")

        self._header_dataset_value.configure(text=f"{loaded_total:,}")
        self._header_dataset_sub.configure(text=f"{flagged_total:,} flagged for follow-up")

        self._header_pages_value.configure(text=f"{pages_analyzed:,}")
        self._header_pages_sub.configure(text=f"{pages_scanned:,} pages scanned overall")

        self._header_model_value.configure(text=f"{provider.upper()} / {model}")
        if prompt_version:
            self._header_model_sub.configure(text=prompt_version)
        else:
            self._header_model_sub.configure(text="Current analysis configuration")

        self._header_generated_value.configure(text=generated)
        if meta.get("mixed_provenance"):
            self._header_generated_sub.configure(text="Mixed provenance across providers")
        else:
            self._header_generated_sub.configure(text="Single-provider output")

    # ------------------------------------------------------------------
    # Body layout
    # ------------------------------------------------------------------

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self.root, fg_color="transparent")
        body.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)

        self._build_sidebar(body)
        self._build_content(body)

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _build_sidebar(self, parent) -> None:
        sidebar = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_secondary"],
            corner_radius=28,
            width=312,
            border_width=1,
            border_color=COLORS["border"],
        )
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        sidebar.grid_propagate(False)

        scroll = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["border_strong"],
        )
        scroll.pack(fill="both", expand=True, padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        intro = ctk.CTkFrame(
            scroll,
            fg_color=COLORS["highlight_gold"],
            corner_radius=22,
            border_width=1,
            border_color=COLORS["border"],
        )
        intro.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            intro,
            text="Control rail",
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=14, pady=(14, 2))
        ctk.CTkLabel(
            intro,
            text="Choose a source, shape the lens, then export or email the filtered record set.",
            font=font("body_small"),
            text_color=COLORS["text_primary"],
            justify="left",
            wraplength=250,
        ).pack(anchor="w", padx=14, pady=(0, 14))

        self._section_header(scroll, "Data source", "The dashboard opens on the latest OpenAI export when available.")

        file_row = ctk.CTkFrame(scroll, fg_color="transparent")
        file_row.pack(fill="x", padx=16, pady=(4, 4))
        file_row.grid_columnconfigure(0, weight=1)

        self._file_var = ctk.StringVar(value="Scanning...")
        self._file_cb = ctk.CTkComboBox(
            file_row,
            variable=self._file_var,
            values=["Scanning..."],
            font=font("body_small"),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["shadow"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["highlight_soft"],
            text_color=COLORS["text_primary"],
            height=36,
            corner_radius=14,
            command=self._on_file_selected,
        )
        self._file_cb.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            file_row,
            text="Refresh",
            font=font("label_bold"),
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["shadow"],
            text_color=COLORS["text_primary"],
            width=72,
            height=36,
            corner_radius=14,
            command=self._refresh_json_dropdown,
        ).grid(row=0, column=1)

        self._load_status_lbl = ctk.CTkLabel(
            scroll,
            text="No file loaded",
            font=font("body_small"),
            text_color=COLORS["text_muted"],
            wraplength=250,
            justify="left",
            anchor="w",
        )
        self._load_status_lbl.pack(fill="x", padx=16, pady=(0, 12))

        self._divider(scroll)

        self._section_header(scroll, "Filters", "Use confidence, names, and entities to create a tighter review slice.")

        ctk.CTkLabel(
            scroll,
            text="Confidence",
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=16, pady=(6, 2))

        self._conf_var = ctk.StringVar(value="All")
        self._conf_seg = ctk.CTkSegmentedButton(
            scroll,
            values=["All", "High", "Med", "Low"],
            variable=self._conf_var,
            font=font("body_small"),
            fg_color=COLORS["bg_card"],
            selected_color=COLORS["accent_purple"],
            selected_hover_color=COLORS["accent_violet"],
            unselected_color=COLORS["bg_elevated"],
            unselected_hover_color=COLORS["shadow"],
            text_color=COLORS["text_inverse"],
            corner_radius=14,
            height=32,
        )
        self._conf_seg.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(
            scroll,
            text="Official / role",
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=16, pady=(0, 2))

        self._official_var = ctk.StringVar(value="All Officials")
        self._official_cb = ctk.CTkComboBox(
            scroll,
            variable=self._official_var,
            values=["All Officials"],
            font=font("body_small"),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["shadow"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["highlight_soft"],
            text_color=COLORS["text_primary"],
            height=36,
            corner_radius=14,
        )
        self._official_cb.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(
            scroll,
            text="Entity",
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=16, pady=(0, 2))

        self._entity_var = ctk.StringVar(value="All Entities")
        self._entity_cb = ctk.CTkComboBox(
            scroll,
            variable=self._entity_var,
            values=["All Entities"],
            font=font("body_small"),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["shadow"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["highlight_teal"],
            text_color=COLORS["text_primary"],
            height=36,
            corner_radius=14,
        )
        self._entity_cb.pack(fill="x", padx=16, pady=(0, 10))

        self._match_only_var = ctk.BooleanVar(value=True)
        self._match_switch = ctk.CTkSwitch(
            scroll,
            text="Conflicts only",
            variable=self._match_only_var,
            font=font("body_small"),
            text_color=COLORS["text_primary"],
            button_color=COLORS["accent_green"],
            button_hover_color=COLORS["accent_emerald"],
            progress_color=COLORS["accent_green"],
            onvalue=True,
            offvalue=False,
        )
        self._match_switch.pack(anchor="w", padx=16, pady=(2, 14))

        ctk.CTkButton(
            scroll,
            text="Apply filters",
            font=font("section"),
            fg_color=COLORS["accent_purple"],
            hover_color=COLORS["accent_violet"],
            text_color=COLORS["text_inverse"],
            height=38,
            corner_radius=16,
            command=self._apply_filters,
        ).pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkButton(
            scroll,
            text="Reset view",
            font=font("body_small"),
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["shadow"],
            text_color=COLORS["text_primary"],
            height=36,
            corner_radius=16,
            command=self._reset_filters,
        ).pack(fill="x", padx=16, pady=(0, 12))

        self._divider(scroll)

        self._section_header(scroll, "Share", "Export the current view or send the filtered records by email.")

        export_row = ctk.CTkFrame(scroll, fg_color="transparent")
        export_row.pack(fill="x", padx=16, pady=(6, 10))
        export_row.grid_columnconfigure(0, weight=1)
        export_row.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            export_row,
            text="CSV export",
            font=font("section"),
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_emerald"],
            text_color=COLORS["text_inverse"],
            height=38,
            corner_radius=16,
            command=self._export_csv,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))

        ctk.CTkButton(
            export_row,
            text="PDF export",
            font=font("section"),
            fg_color=COLORS["accent_purple"],
            hover_color=COLORS["accent_violet"],
            text_color=COLORS["text_inverse"],
            height=38,
            corner_radius=16,
            command=self._export_pdf,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        ctk.CTkButton(
            scroll,
            text="Email report",
            font=font("section"),
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["highlight_gold"],
            text_color=COLORS["text_primary"],
            border_width=1,
            border_color=COLORS["border"],
            height=38,
            corner_radius=16,
            command=self._open_email_dialog,
        ).pack(fill="x", padx=16, pady=(2, 16))

    def _section_header(self, parent, text: str, description: str) -> None:
        block = ctk.CTkFrame(parent, fg_color="transparent")
        block.pack(fill="x", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            block,
            text=text,
            font=font("section"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            block,
            text=description,
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
            justify="left",
            wraplength=250,
        ).pack(anchor="w", pady=(2, 0))

    @staticmethod
    def _divider(parent) -> None:
        ctk.CTkFrame(parent, fg_color=COLORS["border"], height=1).pack(fill="x", padx=16, pady=6)

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    def _build_content(self, parent) -> None:
        content = ctk.CTkFrame(parent, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self._build_overview_band(content)

        board = ctk.CTkFrame(content, fg_color="transparent")
        board.grid(row=1, column=0, sticky="nsew")
        board.grid_rowconfigure(0, weight=0, minsize=300)
        board.grid_rowconfigure(1, weight=1)
        board.grid_columnconfigure(0, weight=10)
        board.grid_columnconfigure(1, weight=11)
        board.grid_columnconfigure(2, weight=14)

        self._summary_agent = SummaryAgent(board, row=0, col=0, colspan=2)
        self._confidence_agent = ConfidenceAgent(board, row=0, col=2)
        self._officials_agent = OfficialsAgent(
            board,
            row=1,
            col=0,
            on_filter_click=self._on_filter_click_from_list,
        )
        self._browser_agent = BrowserAgent(board, row=1, col=1, colspan=2)

    def _build_overview_band(self, parent) -> None:
        band = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_secondary"],
            corner_radius=30,
            border_width=1,
            border_color=COLORS["border"],
        )
        band.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        band.grid_columnconfigure(0, weight=3)
        band.grid_columnconfigure(1, weight=2)
        band.grid_columnconfigure(2, weight=2)

        left = ctk.CTkFrame(band, fg_color="transparent")
        left.grid(row=0, column=0, padx=(20, 12), pady=20, sticky="nsew")

        self._overview_badge = ctk.CTkLabel(
            left,
            text="Awaiting dataset",
            font=font("label_bold"),
            text_color=COLORS["text_primary"],
            fg_color=COLORS["highlight_soft"],
            corner_radius=999,
            padx=14,
            height=28,
        )
        self._overview_badge.pack(anchor="w")

        self._overview_title = ctk.CTkLabel(
            left,
            text="Load a dataset to begin reviewing conflict signals",
            font=font("headline", size=22),
            text_color=COLORS["text_primary"],
            justify="left",
            wraplength=560,
        )
        self._overview_title.pack(anchor="w", pady=(10, 6))

        self._overview_body = ctk.CTkLabel(
            left,
            text="The overview will summarize the current lens, the active filters, and the strongest signals in the file.",
            font=font("body"),
            text_color=COLORS["text_secondary"],
            justify="left",
            wraplength=620,
        )
        self._overview_body.pack(anchor="w")

        filter_card = self._make_overview_card(
            band,
            column=1,
            title="Active lens",
            fill=COLORS["highlight_gold"],
        )
        self._overview_filters_lbl = ctk.CTkLabel(
            filter_card,
            text="No filters applied yet.",
            font=font("body_small"),
            text_color=COLORS["text_primary"],
            justify="left",
            wraplength=250,
        )
        self._overview_filters_lbl.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="w")

        standouts_card = self._make_overview_card(
            band,
            column=2,
            title="Standouts",
            fill=COLORS["highlight_teal"],
        )
        self._overview_source_lbl = ctk.CTkLabel(
            standouts_card,
            text="Top source: —",
            font=font("body_small"),
            text_color=COLORS["text_primary"],
            justify="left",
            wraplength=250,
        )
        self._overview_source_lbl.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        self._overview_people_lbl = ctk.CTkLabel(
            standouts_card,
            text="Top official / entity: —",
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
            justify="left",
            wraplength=250,
        )
        self._overview_people_lbl.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="w")

    def _make_overview_card(self, parent, column: int, title: str, fill: str):
        card = ctk.CTkFrame(
            parent,
            fg_color=fill,
            corner_radius=24,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=0, column=column, sticky="nsew", padx=6, pady=16)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text=title,
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="w")
        return card

    def _update_overview_band(self) -> None:
        meta = self._meta
        provider = meta.get("provider", "dataset").upper()
        model = meta.get("model", "—")
        shown = self._filtered_agg.get("total", len(self._filtered_records))
        dataset_total = self._all_agg.get("total", len(self._all_records))
        flagged = self._filtered_agg.get("flagged", 0)
        share = (flagged / shown) if shown else 0.0

        self._overview_badge.configure(text=f"{provider} · {model}")

        if shown == 0:
            title = "No records are visible in the current lens"
            body = "Try broadening the filters or load a different JSON export to continue the review."
        elif shown == dataset_total:
            title = f"{flagged:,} potential conflicts across the full dataset"
            body = (
                f"The current view includes all {shown:,} loaded records. "
                f"About {share * 100:.1f}% of them are flagged for follow-up."
            )
        else:
            title = f"{flagged:,} potential conflicts in the current lens"
            body = (
                f"The filters narrow the dataset to {shown:,} records out of {dataset_total:,}. "
                f"About {share * 100:.1f}% of this slice is flagged."
            )
        self._overview_title.configure(text=title)
        self._overview_body.configure(text=body)

        self._overview_filters_lbl.configure(text=self._format_active_filters())

        top_files = self._filtered_agg.get("top_files", [])
        if top_files:
            top_file, top_count = top_files[0]
            source_text = f"Top source: {Path(top_file).name} ({top_count:,})"
        else:
            source_text = "Top source: no records in view"
        self._overview_source_lbl.configure(text=source_text)

        official_text = self._top_label(self._filtered_agg.get("officials_counts", {}), "Official")
        entity_text = self._top_label(self._filtered_agg.get("entities_counts", {}), "Entity")
        self._overview_people_lbl.configure(text=f"{official_text}\n{entity_text}")

    def _format_active_filters(self) -> str:
        parts = []
        conf = self._conf_var.get()
        if conf != "All":
            parts.append(f"Confidence: {conf}")
        official = self._official_var.get()
        if official not in ("All Officials", ""):
            parts.append(f"Official: {official}")
        entity = self._entity_var.get()
        if entity not in ("All Entities", ""):
            parts.append(f"Entity: {entity}")
        parts.append("Conflicts only" if self._match_only_var.get() else "Matches and non-matches")

        return " • ".join(parts) if parts else "Full dataset with no additional filters."

    @staticmethod
    def _top_label(counts: dict, prefix: str) -> str:
        if not counts:
            return f"{prefix}: none in this view"
        name, count = max(counts.items(), key=lambda item: item[1])
        return f"{prefix}: {name} ({count:,})"

    @staticmethod
    def _format_generated_at(raw_value: str | None) -> str:
        if not raw_value:
            return "—"
        try:
            dt = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y %I:%M %p UTC")
        except Exception:
            return raw_value

    # ------------------------------------------------------------------
    # JSON file discovery / loading
    # ------------------------------------------------------------------

    def _scan_json_files(self) -> dict[str, Path]:
        found: dict[str, Path] = {}
        if BACKEND_DIR.is_dir():
            for path in sorted(BACKEND_DIR.glob("*.json")):
                found[path.name] = path
        return found

    def _preferred_data_name(self) -> str | None:
        for candidate in ("conflict_flags_openai.json", "conflict_flags.json"):
            if candidate in self._json_files:
                return candidate
        return next(iter(self._json_files), None)

    def _refresh_json_dropdown(self) -> None:
        self._json_files = self._scan_json_files()
        names = list(self._json_files.keys()) or ["(no JSON files found)"]
        self._file_cb.configure(values=names)
        current = self._file_var.get()
        if current not in self._json_files:
            preferred = self._preferred_data_name()
            self._file_var.set(preferred or names[0])

    def _initial_scan_and_load(self) -> None:
        self._json_files = self._scan_json_files()
        if not self._json_files:
            self._file_var.set("(no JSON files found)")
            self._file_cb.configure(values=["(no JSON files found)"])
            self._load_status_lbl.configure(text="No JSON files were found in Backend/", text_color=COLORS["danger"])
            return

        names = list(self._json_files.keys())
        self._file_cb.configure(values=names)

        default_name = self._preferred_data_name()
        if not default_name:
            return

        self._file_var.set(default_name)
        self._load_data(self._json_files[default_name])

    def _on_file_selected(self, selection: str) -> None:
        path = self._json_files.get(selection)
        if path:
            self._load_data(path)

    def _load_data(self, path=None) -> None:
        load_path = Path(path) if path else DEFAULT_PATH
        self._loaded_path = load_path
        self._load_status_lbl.configure(
            text=f"Loading {load_path.name}...",
            text_color=COLORS["text_secondary"],
        )
        self._header_file_pill.configure(text=f"Source · {load_path.name}")

        def _on_success(records, meta):
            self._all_records = records
            self._meta = meta
            self.root.after(0, self._on_load_complete)

        def _on_error(exc):
            self.root.after(0, lambda: messagebox.showerror("Load Error", str(exc)))

        self._loader.load(path=load_path, on_success=_on_success, on_error=_on_error)
        self.root.after(100, self._poll_loader)

    def _poll_loader(self) -> None:
        drain = self._loader.get_pending_drain()
        if drain:
            drain()

    def _on_load_complete(self) -> None:
        self._populate_filter_combos()
        self._apply_filters()

        if self._loaded_path:
            self._load_status_lbl.configure(
                text=f"Loaded {self._loaded_path.name} · {len(self._all_records):,} records ready for review",
                text_color=COLORS["success"],
            )

    def _populate_filter_combos(self) -> None:
        officials: dict[str, str] = {}
        entities: dict[str, str] = {}
        for rec in self._all_records:
            for official in self._engine.extract_official_names(rec):
                officials.setdefault(official.casefold(), official)
            for entity in self._engine.extract_entity_names(rec):
                entities.setdefault(entity.casefold(), entity)

        sorted_officials = ["All Officials"] + sorted(officials.values(), key=str.casefold)
        sorted_entities = ["All Entities"] + sorted(entities.values(), key=str.casefold)

        self._official_cb.configure(values=sorted_officials)
        self._official_var.set("All Officials")
        self._entity_cb.configure(values=sorted_entities)
        self._entity_var.set("All Entities")

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _build_filter_state(self) -> dict:
        conf_val = self._conf_var.get()
        conf_map = {"High": ["high"], "Med": ["medium"], "Low": ["low"]}
        conf_list = conf_map.get(conf_val, None)

        official = self._official_var.get()
        if official in ("All Officials", ""):
            official = None

        entity = self._entity_var.get()
        if entity in ("All Entities", ""):
            entity = None

        return {
            "confidence": conf_list,
            "official": official,
            "entity": entity,
            "keyword": None,
            "match_only": self._match_only_var.get(),
        }

    def _apply_filters(self) -> None:
        filters = self._build_filter_state()
        self._filtered_records = self._engine.apply(self._all_records, filters)
        self._all_agg = self._engine.compute_aggregates(self._all_records)
        self._filtered_agg = self._engine.compute_aggregates(self._filtered_records)
        self._refresh_all()

    def _reset_filters(self) -> None:
        self._conf_var.set("All")
        self._official_var.set("All Officials")
        self._entity_var.set("All Entities")
        self._match_only_var.set(True)
        self._apply_filters()

    def _on_filter_click_from_list(self, kind: str, name: str) -> None:
        if kind == "official":
            self._official_var.set(name)
        elif kind == "entity":
            self._entity_var.set(name)
        self._apply_filters()

    # ------------------------------------------------------------------
    # Refresh all agents
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        agg = self._all_agg
        fagg = self._filtered_agg

        self._summary_agent.update(agg, fagg)
        self._confidence_agent.update(agg, fagg)
        self._officials_agent.update(
            fagg.get("officials_counts", {}),
            fagg.get("entities_counts", {}),
        )
        self._browser_agent.update(self._filtered_records)
        self._update_header_meta()
        self._update_overview_band()

    def _record_officials(self, rec: dict) -> list[str]:
        return self._engine.extract_official_names(rec)

    def _record_entities(self, rec: dict) -> list[str]:
        return self._engine.extract_entity_names(rec)

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------

    def _export_csv(self) -> None:
        if not self._filtered_records:
            messagebox.showinfo("No Data", "No records to export.")
            return

        path = filedialog.asksaveasfilename(
            title="Save CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        fields = [
            "id", "confidence", "match", "reasoning",
            "source_file", "page", "officials", "entities", "keywords",
        ]

        def _write():
            try:
                with open(path, "w", newline="", encoding="utf-8") as fh:
                    writer = csv.DictWriter(fh, fieldnames=fields)
                    writer.writeheader()
                    for rec in self._filtered_records:
                        conflict = rec.get("conflict", {})
                        source = rec.get("source", {})
                        officials = self._record_officials(rec)
                        entities = self._record_entities(rec)
                        writer.writerow({
                            "id": rec.get("id", ""),
                            "confidence": conflict.get("confidence", ""),
                            "match": conflict.get("match", ""),
                            "reasoning": conflict.get("reasoning", ""),
                            "source_file": source.get("file", ""),
                            "page": source.get("page", ""),
                            "officials": "; ".join(officials),
                            "entities": "; ".join(entities),
                            "keywords": "; ".join(rec.get("keywords_matched", [])),
                        })
                self.root.after(0, lambda: messagebox.showinfo("Saved", f"CSV saved to:\n{path}"))
            except Exception as exc:  # noqa: BLE001
                self.root.after(0, lambda: messagebox.showerror("Export Error", str(exc)))

        threading.Thread(target=_write, daemon=True).start()

    # ------------------------------------------------------------------
    # PDF export
    # ------------------------------------------------------------------

    def _export_pdf(self) -> None:
        if not self._filtered_records:
            messagebox.showinfo("No Data", "No records to export.")
            return

        path = filedialog.asksaveasfilename(
            title="Save PDF Report",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return

        agg = self._filtered_agg
        loaded_name = self._loaded_path.name if self._loaded_path else "unknown"
        total = len(self._all_records)
        shown = len(self._filtered_records)

        def _write():
            try:
                from reportlab.lib import colors as rl_colors
                from reportlab.lib.pagesizes import letter
                from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
                from reportlab.lib.units import inch
                from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

                doc = SimpleDocTemplate(
                    path,
                    pagesize=letter,
                    leftMargin=0.75 * inch,
                    rightMargin=0.75 * inch,
                    topMargin=0.75 * inch,
                    bottomMargin=0.75 * inch,
                )

                styles = getSampleStyleSheet()
                rc = lambda name: resolve_color(name, mode="light")
                title_style = ParagraphStyle(
                    "CoITitle",
                    parent=styles["Title"],
                    fontSize=18,
                    spaceAfter=6,
                    textColor=rl_colors.HexColor(rc("accent_purple")),
                )
                sub_style = ParagraphStyle(
                    "CoISub",
                    parent=styles["Normal"],
                    fontSize=9,
                    textColor=rl_colors.HexColor(rc("text_secondary")),
                    spaceAfter=16,
                )
                body_style = ParagraphStyle(
                    "CoIBody",
                    parent=styles["Normal"],
                    fontSize=8,
                    leading=11,
                    wordWrap="CJK",
                )
                section_style = ParagraphStyle(
                    "CoISection",
                    parent=styles["Heading2"],
                    fontSize=11,
                    textColor=rl_colors.HexColor(rc("accent_green")),
                    spaceBefore=14,
                    spaceAfter=6,
                )

                conf_colors = {
                    "high": rl_colors.HexColor(rc("confidence_high")),
                    "medium": rl_colors.HexColor(rc("confidence_medium")),
                    "low": rl_colors.HexColor(rc("confidence_low")),
                }

                story = []
                story.append(Paragraph("Sacramento County", title_style))
                story.append(Paragraph("Conflict Signals Report", title_style))
                story.append(Paragraph(
                    f"Source: {loaded_name}  ·  "
                    f"Showing {shown:,} of {total:,} records  ·  "
                    f"High: {agg.get('by_confidence', {}).get('high', 0):,}  "
                    f"Medium: {agg.get('by_confidence', {}).get('medium', 0):,}  "
                    f"Low: {agg.get('by_confidence', {}).get('low', 0):,}",
                    sub_style,
                ))

                story.append(Paragraph("Flagged Records", section_style))

                col_widths = [0.7 * inch, 1.2 * inch, 0.4 * inch, 1.4 * inch, 1.3 * inch, 2.3 * inch]
                header_row = ["Confidence", "Source File", "Pg", "Officials", "Entities", "Reasoning"]
                table_data = [header_row]

                for rec in self._filtered_records[:2000]:
                    conflict = rec.get("conflict", {})
                    source = rec.get("source", {})
                    officials = self._record_officials(rec)
                    entities = self._record_entities(rec)
                    fname = source.get("file", "")
                    fname_short = fname[:28] + "..." if len(fname) > 30 else fname
                    reasoning = conflict.get("reasoning", "")
                    reasoning = reasoning[:220] + "..." if len(reasoning) > 220 else reasoning
                    table_data.append([
                        Paragraph(conflict.get("confidence", "").upper(), body_style),
                        Paragraph(fname_short, body_style),
                        str(source.get("page", "")),
                        Paragraph("; ".join(officials) or "—", body_style),
                        Paragraph("; ".join(entities) or "—", body_style),
                        Paragraph(reasoning, body_style),
                    ])

                tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor(rc("bg_inverse"))),
                    ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.HexColor(rc("text_inverse"))),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("FONTSIZE", (0, 1), (-1, -1), 7),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [rl_colors.HexColor(rc("bg_card")), rl_colors.HexColor(rc("bg_secondary"))]),
                    ("TEXTCOLOR", (0, 1), (-1, -1), rl_colors.HexColor(rc("text_primary"))),
                    ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.HexColor(rc("border"))),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))

                for i, rec in enumerate(self._filtered_records[:2000], start=1):
                    conf = rec.get("conflict", {}).get("confidence", "low")
                    color = conf_colors.get(conf, rl_colors.gray)
                    tbl.setStyle(TableStyle([
                        ("TEXTCOLOR", (0, i), (0, i), color),
                        ("FONTSIZE", (0, i), (0, i), 7),
                    ]))

                story.append(tbl)

                if shown > 2000:
                    story.append(Spacer(1, 0.15 * inch))
                    story.append(Paragraph(
                        f"Report capped at 2,000 rows. Full dataset: {shown:,} records. Use CSV export for complete data.",
                        sub_style,
                    ))

                doc.build(story)
                self.root.after(0, lambda: messagebox.showinfo("Saved", f"PDF saved to:\n{path}"))
            except ImportError:
                self.root.after(0, lambda: messagebox.showerror(
                    "Missing Dependency",
                    "reportlab is required for PDF export.\n\nRun:\n  pip install reportlab",
                ))
            except Exception as exc:  # noqa: BLE001
                self.root.after(0, lambda: messagebox.showerror("Export Error", str(exc)))

        threading.Thread(target=_write, daemon=True).start()

    # ------------------------------------------------------------------
    # Email export
    # ------------------------------------------------------------------

    def _open_email_dialog(self) -> None:
        officials_counts: dict = self._filtered_agg.get("officials_counts", {})
        officials: list[str] = sorted(officials_counts.keys()) if officials_counts else []

        dialog = EmailDialog(
            parent=self.root,
            records=self._filtered_records,
            officials=officials,
        )
        dialog.lift()
