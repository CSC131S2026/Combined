"""
ConflictDashboard — main orchestrator.

Coordinates:
  - sidebar controls for source selection, filters, and sharing
  - a single record browser workspace for conflict review
  - background data loading via DataLoader
"""

import csv
import html
import queue
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

PROJECT_DIR = Path(__file__).resolve().parents[1]
if not getattr(sys, "frozen", False):
    if str(PROJECT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_DIR))

import customtkinter as ctk

from agents.browser_agent import BrowserAgent
from core.data_loader import DataLoader, DEFAULT_PATH, BACKEND_DIR
from shared.export_safety import neutralize_csv_row
from core.filter_engine import FilterEngine
from core.filter_tasks import compute_filter_task, compute_full_aggregates
from ui.email_dialog import EmailDialog
from ui.theme import COLORS, font, resolve_color


def _escape_reportlab_markup(value) -> str:
    """Escape dynamic text before it is passed to ReportLab Paragraph."""
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


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
        self._load_generation = 0
        self._filter_generation = 0

        self._configure_root()
        self._build_body()

        self.root.after(100, self._initial_scan_and_load)

    # ------------------------------------------------------------------
    # Root configuration
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        self.root.title("Sacramento County — Conflict Signals Dashboard")
        self.root.geometry("1500x900")
        self.root.minsize(1120, 720)
        self.root.configure(fg_color=COLORS["bg_primary"])
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def _on_appearance_change(self) -> None:
        mode = "dark" if self._appearance_var.get() else "light"
        ctk.set_appearance_mode(mode)
        if hasattr(self, "_browser_agent"):
            self._browser_agent.refresh_theme()

    def _update_sidebar_meta(self) -> None:
        meta = self._meta
        loaded_total = self._all_agg.get("total", len(self._all_records))
        flagged_total = self._all_agg.get("flagged", 0)
        flagged_visible = self._filtered_agg.get("flagged", 0)
        shown = self._filtered_agg.get("total", len(self._filtered_records))

        provider = meta.get("provider", "dataset")
        model = meta.get("model", "—")

        self._sidebar_records_lbl.configure(text=f"{shown:,} in view / {loaded_total:,} loaded")
        self._sidebar_flags_lbl.configure(
            text=f"{flagged_visible:,} conflicts in current view · {flagged_total:,} total flagged"
        )
        self._sidebar_model_lbl.configure(text=f"{provider.upper()} / {model}")

    # ------------------------------------------------------------------
    # Body layout
    # ------------------------------------------------------------------

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self.root, fg_color="transparent")
        body.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
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
            corner_radius=18,
            width=316,
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

        self._section_header(scroll, "Filter settings", "Source, confidence, people, and entity filters.")

        ctk.CTkLabel(
            scroll,
            text="Source file",
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=16, pady=(6, 2))

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

        status = ctk.CTkFrame(
            scroll,
            fg_color=COLORS["bg_card"],
            corner_radius=14,
            border_width=1,
            border_color=COLORS["border"],
        )
        status.pack(fill="x", padx=16, pady=(0, 12))
        status.grid_columnconfigure(0, weight=1)

        self._sidebar_records_lbl = ctk.CTkLabel(
            status,
            text="0 in view / 0 loaded",
            font=font("section"),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self._sidebar_records_lbl.grid(row=0, column=0, padx=14, pady=(12, 1), sticky="ew")

        self._sidebar_flags_lbl = ctk.CTkLabel(
            status,
            text="0 conflicts in current view",
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self._sidebar_flags_lbl.grid(row=1, column=0, padx=14, pady=(0, 1), sticky="ew")

        self._sidebar_model_lbl = ctk.CTkLabel(
            status,
            text="Provider / model will appear after load",
            font=font("label"),
            text_color=COLORS["text_muted"],
            anchor="w",
            wraplength=250,
            justify="left",
        )
        self._sidebar_model_lbl.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="ew")

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

        self._appearance_var = ctk.BooleanVar(
            value=ctk.get_appearance_mode().lower() == "dark"
        )
        self._appearance_switch = ctk.CTkSwitch(
            scroll,
            text="Dark mode",
            variable=self._appearance_var,
            onvalue=True,
            offvalue=False,
            command=self._on_appearance_change,
            font=font("body_small"),
            text_color=COLORS["text_primary"],
            button_color=COLORS["accent_purple"],
            button_hover_color=COLORS["accent_violet"],
            progress_color=COLORS["accent_purple"],
        )
        self._appearance_switch.pack(anchor="w", padx=16, pady=(0, 14))

        self._divider(scroll)

        self._section_header(scroll, "Sharing settings", "Export or email the current filtered record set.")

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
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self._browser_agent = BrowserAgent(content, row=0, col=0)

    # ------------------------------------------------------------------
    # JSON file discovery / loading
    # ------------------------------------------------------------------

    def _scan_json_files(self) -> dict[str, Path]:
        found: dict[str, Path] = {}
        if BACKEND_DIR.is_dir():
            for pattern in ("conflict_flags*.json", "test_conflicts.json"):
                for path in sorted(BACKEND_DIR.glob(pattern)):
                    if "checkpoint" not in path.stem:
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
        self._load_generation += 1
        self._filter_generation += 1
        load_generation = self._load_generation
        self._loaded_path = load_path
        self._load_status_lbl.configure(
            text=f"Loading {load_path.name}...",
            text_color=COLORS["text_secondary"],
        )

        def _on_success(records, meta):
            if load_generation != self._load_generation:
                return
            self._prepare_loaded_records(load_generation, records, meta)

        def _on_error(exc):
            if load_generation != self._load_generation:
                return
            self.root.after(0, lambda: messagebox.showerror("Load Error", str(exc)))

        self._loader.load(path=load_path, on_success=_on_success, on_error=_on_error)
        self.root.after(100, self._poll_loader)

    def _poll_loader(self) -> None:
        drain = self._loader.get_pending_drain()
        if drain and not drain():
            self.root.after(100, self._poll_loader)

    def _prepare_loaded_records(self, generation: int, records: list, meta: dict) -> None:
        result_q: queue.Queue = queue.Queue(maxsize=1)

        def _worker() -> None:
            try:
                result_q.put(("ok", compute_full_aggregates(records, self._engine)))
            except Exception as exc:  # noqa: BLE001
                result_q.put(("err", exc))

        threading.Thread(target=_worker, daemon=True).start()
        self.root.after(50, lambda: self._poll_load_prepare(generation, records, meta, result_q))

    def _poll_load_prepare(
        self,
        generation: int,
        records: list,
        meta: dict,
        result_q: queue.Queue,
    ) -> None:
        if generation != self._load_generation:
            return

        try:
            item = result_q.get_nowait()
        except queue.Empty:
            self.root.after(50, lambda: self._poll_load_prepare(generation, records, meta, result_q))
            return

        kind = item[0]
        if kind == "err":
            _, exc = item
            messagebox.showerror("Load Error", str(exc))
            return

        _, all_agg = item
        self._on_load_complete(records, meta, all_agg)

    def _on_load_complete(self, records: list, meta: dict, all_agg: dict) -> None:
        self._all_records = records
        self._meta = meta
        self._all_agg = all_agg
        self._filtered_records = []
        self._filtered_agg = {}
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
        records = self._all_records
        all_agg = self._all_agg or None
        self._filter_generation += 1
        generation = self._filter_generation
        result_q: queue.Queue = queue.Queue(maxsize=1)

        def _worker() -> None:
            try:
                result_q.put(("ok", compute_filter_task(records, filters, all_agg, self._engine)))
            except Exception as exc:  # noqa: BLE001
                result_q.put(("err", exc))

        threading.Thread(target=_worker, daemon=True).start()
        self.root.after(50, lambda: self._poll_filter_result(generation, result_q))

    def _poll_filter_result(self, generation: int, result_q: queue.Queue) -> None:
        if generation != self._filter_generation:
            return

        try:
            item = result_q.get_nowait()
        except queue.Empty:
            self.root.after(50, lambda: self._poll_filter_result(generation, result_q))
            return

        if generation != self._filter_generation:
            return

        kind = item[0]
        if kind == "err":
            _, exc = item
            messagebox.showerror("Filter Error", str(exc))
            return

        _, result = item
        self._filtered_records = result.filtered_records
        self._filtered_agg = result.filtered_agg
        self._all_agg = result.all_agg
        self._refresh_all()

    def _reset_filters(self) -> None:
        self._conf_var.set("All")
        self._official_var.set("All Officials")
        self._entity_var.set("All Entities")
        self._match_only_var.set(True)
        self._apply_filters()

    # ------------------------------------------------------------------
    # Refresh all agents
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        self._browser_agent.update(self._filtered_records)
        self._update_sidebar_meta()

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
                        writer.writerow(neutralize_csv_row({
                            "id": rec.get("id", ""),
                            "confidence": conflict.get("confidence", ""),
                            "match": conflict.get("match", ""),
                            "reasoning": conflict.get("reasoning", ""),
                            "source_file": source.get("file", ""),
                            "page": source.get("page", ""),
                            "officials": "; ".join(officials),
                            "entities": "; ".join(entities),
                            "keywords": "; ".join(rec.get("keywords_matched", [])),
                        }))
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
                    _escape_reportlab_markup(
                        f"Source: {loaded_name}  ·  "
                        f"Showing {shown:,} of {total:,} records  ·  "
                        f"High: {agg.get('by_confidence', {}).get('high', 0):,}  "
                        f"Medium: {agg.get('by_confidence', {}).get('medium', 0):,}  "
                        f"Low: {agg.get('by_confidence', {}).get('low', 0):,}"
                    ),
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
                        Paragraph(
                            _escape_reportlab_markup(conflict.get("confidence", "").upper()),
                            body_style,
                        ),
                        Paragraph(_escape_reportlab_markup(fname_short), body_style),
                        Paragraph(_escape_reportlab_markup(source.get("page", "")), body_style),
                        Paragraph(_escape_reportlab_markup("; ".join(officials) or "—"), body_style),
                        Paragraph(_escape_reportlab_markup("; ".join(entities) or "—"), body_style),
                        Paragraph(_escape_reportlab_markup(reasoning), body_style),
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
                        _escape_reportlab_markup(
                            f"Report capped at 2,000 rows. Full dataset: {shown:,} records. Use CSV export for complete data."
                        ),
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
