"""
ConflictDashboard — main orchestrator.

Coordinates:
  - Sidebar (data source, filters, export)
  - 2x2 agent grid (SummaryAgent, ConfidenceAgent, OfficialsAgent, BrowserAgent)
  - Background data loading via DataLoader
  - Filter state → FilterEngine → agent refresh
"""

import csv
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from agents.browser_agent    import BrowserAgent
from agents.confidence_agent import ConfidenceAgent
from agents.officials_agent  import OfficialsAgent
from agents.summary_agent    import SummaryAgent
from core.data_loader        import DataLoader, DEFAULT_PATH, BACKEND_DIR
from core.filter_engine      import FilterEngine
from ui.email_dialog         import EmailDialog
from ui.theme                import COLORS


class ConflictDashboard:

    def __init__(self, root: ctk.CTk):
        self.root          = root
        self._loader       = DataLoader()
        self._engine       = FilterEngine()

        # Live data
        self._all_records:      list = []
        self._filtered_records: list = []
        self._meta:             dict = {}
        self._all_agg:          dict = {}
        self._filtered_agg:     dict = {}

        # JSON discovery: display-name → Path
        self._json_files:  dict[str, Path] = {}
        self._loaded_path: Path | None     = None

        self._configure_root()
        self._build_header()
        self._build_body()

        # Scan for JSON files, populate dropdown, then auto-load first result
        self.root.after(100, self._initial_scan_and_load)

    # ------------------------------------------------------------------
    # Root configuration
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        self.root.title("Sacramento County — Conflict of Interest Dashboard")
        self.root.geometry("1600x960")
        self.root.minsize(1200, 780)
        self.root.configure(fg_color=COLORS["bg_primary"])
        self.root.grid_rowconfigure(0, weight=0)  # header
        self.root.grid_rowconfigure(1, weight=1)  # body
        self.root.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        hdr = ctk.CTkFrame(
            self.root,
            fg_color=COLORS["bg_secondary"],
            corner_radius=0,
            height=64,
        )
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)

        # Left: title + subtitle
        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.grid(row=0, column=0, padx=20, pady=0, sticky="w")

        ctk.CTkLabel(
            left,
            text="◈  SACRAMENTO COUNTY",
            font=ctk.CTkFont("Andale Mono", 18, "bold"),
            text_color=COLORS["accent_purple"],
        ).pack(side="left")
        ctk.CTkLabel(
            left,
            text="  |  Conflict of Interest Dashboard",
            font=ctk.CTkFont("Andale Mono", 13),
            text_color=COLORS["text_secondary"],
        ).pack(side="left", pady=(4, 0))

        # Subtitle
        sub_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        sub_frame.grid(row=0, column=1, padx=10, pady=0, sticky="w")
        ctk.CTkLabel(
            sub_frame,
            text="Form 700 / Agenda Analysis",
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_muted"],
        ).pack(side="left")

        # Right: meta info
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.grid(row=0, column=2, padx=20, pady=0, sticky="e")

        self._meta_total_lbl = ctk.CTkLabel(
            right,
            text="",
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        )
        self._meta_total_lbl.pack(side="right", padx=(6, 0))

        self._meta_model_lbl = ctk.CTkLabel(
            right,
            text="",
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_muted"],
        )
        self._meta_model_lbl.pack(side="right", padx=(0, 8))

        # Accent underline
        accent_bar = ctk.CTkFrame(self.root, fg_color=COLORS["accent_purple"], height=2, corner_radius=0)
        accent_bar.grid(row=0, column=0, sticky="ews")

    def _update_header_meta(self) -> None:
        meta = self._meta
        model   = meta.get("model", "—")
        gen_at  = meta.get("generated_at", "")
        total   = meta.get("total_pages_analyzed", len(self._all_records))
        self._meta_total_lbl.configure(
            text=f"{len(self._all_records):,} results  |  {total:,} pages analyzed"
        )
        if gen_at:
            try:
                dt = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
                gen_str = dt.strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                gen_str = gen_at[:16]
        else:
            gen_str = "—"
        self._meta_model_lbl.configure(text=f"Model: {model}  |  Generated: {gen_str}")

    # ------------------------------------------------------------------
    # Body layout
    # ------------------------------------------------------------------

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self.root, fg_color="transparent", corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=0)  # sidebar
        body.grid_columnconfigure(1, weight=1)  # content

        self._build_sidebar(body)
        self._build_content(body)

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _build_sidebar(self, parent) -> None:
        sidebar = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_secondary"],
            corner_radius=0,
            width=264,
            border_width=0,
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(10, weight=1)  # spacer

        scroll = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["text_muted"],
        )
        scroll.pack(fill="both", expand=True, padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        pad = {"padx": 14}

        # ── DATA section ──────────────────────────────
        self._section_header(scroll, "DATA")

        # ComboBox + Refresh button row
        file_row = ctk.CTkFrame(scroll, fg_color="transparent")
        file_row.pack(fill="x", padx=14, pady=(4, 4))
        file_row.grid_columnconfigure(0, weight=1)

        self._file_var = ctk.StringVar(value="Scanning…")
        self._file_cb = ctk.CTkComboBox(
            file_row,
            variable=self._file_var,
            values=["Scanning…"],
            font=ctk.CTkFont("Andale Mono", 10),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["accent_purple"],
            dropdown_fg_color=COLORS["bg_elevated"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["accent_purple"],
            text_color=COLORS["text_primary"],
            height=30,
            corner_radius=6,
            command=self._on_file_selected,
        )
        self._file_cb.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        ctk.CTkButton(
            file_row,
            text="↺",
            font=ctk.CTkFont("Andale Mono", 13, "bold"),
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            width=30,
            height=30,
            corner_radius=6,
            command=self._refresh_json_dropdown,
        ).grid(row=0, column=1)

        # Status label: "Loaded: conflict_flags.json · 11,483 records"
        self._load_status_lbl = ctk.CTkLabel(
            scroll,
            text="No file loaded",
            font=ctk.CTkFont("Andale Mono", 9),
            text_color=COLORS["text_muted"],
            wraplength=220,
            anchor="w",
        )
        self._load_status_lbl.pack(fill="x", padx=14, pady=(0, 10))

        self._divider(scroll)

        # ── FILTERS section ───────────────────────────
        self._section_header(scroll, "FILTERS")

        # Confidence segmented button
        ctk.CTkLabel(
            scroll, text="Confidence",
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", **pad, pady=(6, 2))

        self._conf_var = ctk.StringVar(value="All")
        self._conf_seg = ctk.CTkSegmentedButton(
            scroll,
            values=["All", "High", "Med", "Low"],
            variable=self._conf_var,
            font=ctk.CTkFont("Andale Mono", 10),
            fg_color=COLORS["bg_card"],
            selected_color=COLORS["accent_purple"],
            selected_hover_color="#7c4fc4",
            unselected_color=COLORS["bg_elevated"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            corner_radius=6,
            height=28,
        )
        self._conf_seg.pack(fill="x", **pad, pady=(0, 8))

        # Official combobox
        ctk.CTkLabel(
            scroll, text="Official",
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", **pad, pady=(0, 2))

        self._official_var = ctk.StringVar(value="All Officials")
        self._official_cb = ctk.CTkComboBox(
            scroll,
            variable=self._official_var,
            values=["All Officials"],
            font=ctk.CTkFont("Andale Mono", 10),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["accent_purple"],
            dropdown_fg_color=COLORS["bg_elevated"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["accent_purple"],
            text_color=COLORS["text_primary"],
            height=30,
            corner_radius=6,
        )
        self._official_cb.pack(fill="x", **pad, pady=(0, 8))

        # Entity combobox
        ctk.CTkLabel(
            scroll, text="Entity",
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", **pad, pady=(0, 2))

        self._entity_var = ctk.StringVar(value="All Entities")
        self._entity_cb = ctk.CTkComboBox(
            scroll,
            variable=self._entity_var,
            values=["All Entities"],
            font=ctk.CTkFont("Andale Mono", 10),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["accent_purple"],
            dropdown_fg_color=COLORS["bg_elevated"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["accent_purple"],
            text_color=COLORS["text_primary"],
            height=30,
            corner_radius=6,
        )
        self._entity_cb.pack(fill="x", **pad, pady=(0, 8))

        # Match only switch
        self._match_only_var = ctk.BooleanVar(value=True)
        self._match_switch = ctk.CTkSwitch(
            scroll,
            text="Conflicts only",
            variable=self._match_only_var,
            font=ctk.CTkFont("Andale Mono", 11),
            text_color=COLORS["text_primary"],
            button_color=COLORS["accent_purple"],
            button_hover_color="#7c4fc4",
            progress_color=COLORS["accent_purple"],
            onvalue=True,
            offvalue=False,
        )
        self._match_switch.pack(anchor="w", **pad, pady=(0, 12))

        # Apply / Reset buttons
        ctk.CTkButton(
            scroll,
            text="Apply Filters",
            font=ctk.CTkFont("Andale Mono", 11, "bold"),
            fg_color=COLORS["accent_purple"],
            hover_color="#7c4fc4",
            text_color="#ffffff",
            height=32,
            corner_radius=6,
            command=self._apply_filters,
        ).pack(fill="x", **pad, pady=(0, 6))

        ctk.CTkButton(
            scroll,
            text="Reset",
            font=ctk.CTkFont("Andale Mono", 11),
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            height=30,
            corner_radius=6,
            command=self._reset_filters,
        ).pack(fill="x", **pad, pady=(0, 10))

        self._divider(scroll)

        # ── EXPORT section ────────────────────────────
        self._section_header(scroll, "EXPORT")

        export_row = ctk.CTkFrame(scroll, fg_color="transparent")
        export_row.pack(fill="x", padx=14, pady=(6, 10))
        export_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            export_row,
            text="CSV",
            font=ctk.CTkFont("Andale Mono", 11, "bold"),
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["success"],
            text_color="#ffffff",
            height=32,
            corner_radius=6,
            command=self._export_csv,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))

        ctk.CTkButton(
            export_row,
            text="PDF",
            font=ctk.CTkFont("Andale Mono", 11, "bold"),
            fg_color=COLORS["accent_purple"],
            hover_color="#7c4fc4",
            text_color="#ffffff",
            height=32,
            corner_radius=6,
            command=self._export_pdf,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        # Divider + Email button
        self._divider(scroll)

        ctk.CTkButton(
            scroll,
            text="Email Report",
            font=ctk.CTkFont("Andale Mono", 11, "bold"),
            fg_color=COLORS["accent_green"],
            hover_color="#b8821e",
            text_color="#ffffff",
            height=32,
            corner_radius=6,
            command=self._open_email_dialog,
        ).pack(fill="x", padx=14, pady=(6, 14))

    def _section_header(self, parent, text: str) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            frame,
            text=text,
            font=ctk.CTkFont("Andale Mono", 9, "bold"),
            text_color=COLORS["text_muted"],
        ).pack(side="left")
        ctk.CTkFrame(frame, fg_color=COLORS["border"], height=1).pack(
            side="left", fill="x", expand=True, padx=(8, 0), pady=(2, 0)
        )

    @staticmethod
    def _divider(parent) -> None:
        ctk.CTkFrame(parent, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=14, pady=4
        )

    # ------------------------------------------------------------------
    # Content grid
    # ------------------------------------------------------------------

    def _build_content(self, parent) -> None:
        content = ctk.CTkFrame(parent, fg_color=COLORS["bg_primary"], corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        content.grid_rowconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=2)   # bottom row gets more height
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)

        self._summary_agent    = SummaryAgent(content, row=0, col=0)
        self._confidence_agent = ConfidenceAgent(content, row=0, col=1)
        self._officials_agent  = OfficialsAgent(
            content, row=1, col=0,
            on_filter_click=self._on_filter_click_from_list,
        )
        self._browser_agent    = BrowserAgent(content, row=1, col=1)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # JSON file discovery
    # ------------------------------------------------------------------

    def _scan_json_files(self) -> dict[str, Path]:
        """Return {display_name: full_path} for every *.json in BACKEND_DIR."""
        found: dict[str, Path] = {}
        if BACKEND_DIR.is_dir():
            for p in sorted(BACKEND_DIR.glob("*.json")):
                found[p.name] = p
        return found

    def _refresh_json_dropdown(self) -> None:
        """Re-scan Backend dir and repopulate the file ComboBox."""
        self._json_files = self._scan_json_files()
        names = list(self._json_files.keys()) or ["(no JSON files found)"]
        self._file_cb.configure(values=names)
        # Keep current selection if still valid, otherwise reset to first
        current = self._file_var.get()
        if current not in self._json_files:
            self._file_var.set(names[0])

    def _initial_scan_and_load(self) -> None:
        """Run once at startup: scan, populate dropdown, load first file."""
        self._json_files = self._scan_json_files()
        if not self._json_files:
            self._file_var.set("(no JSON files found)")
            self._file_cb.configure(values=["(no JSON files found)"])
            return

        names = list(self._json_files.keys())
        self._file_cb.configure(values=names)

        # Prefer conflict_flags.json if present, otherwise first file
        default_name = "conflict_flags.json" if "conflict_flags.json" in self._json_files else names[0]
        self._file_var.set(default_name)
        self._load_data(self._json_files[default_name])

    def _on_file_selected(self, selection: str) -> None:
        """Called by ComboBox command= when the user picks a different file."""
        path = self._json_files.get(selection)
        if path:
            self._load_data(path)

    def _browse_and_load(self) -> None:
        path = filedialog.askopenfilename(
            title="Select conflict JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._data_path_lbl.configure(text=Path(path).name)
            self._load_data(path)

    def _load_data(self, path=None) -> None:
        """Load JSON in a background thread; refresh UI on completion."""
        load_path = Path(path) if path else DEFAULT_PATH
        self._loaded_path = load_path
        self._load_status_lbl.configure(text=f"Loading {load_path.name}…")

        def _on_success(records, meta):
            self._all_records = records
            self._meta        = meta
            self.root.after(0, self._on_load_complete)

        def _on_error(exc):
            self.root.after(
                0,
                lambda: messagebox.showerror("Load Error", str(exc)),
            )

        self._loader.load(
            path=load_path,
            on_success=_on_success,
            on_error=_on_error,
        )

        # Poll the drain queue every 100ms
        self.root.after(100, self._poll_loader)

    def _poll_loader(self) -> None:
        drain = self._loader.get_pending_drain()
        if drain:
            drain()

    def _on_load_complete(self) -> None:
        self._populate_filter_combos()
        self._update_header_meta()
        self._apply_filters()
        # Update status label
        if self._loaded_path:
            self._load_status_lbl.configure(
                text=f"Loaded: {self._loaded_path.name}  ·  {len(self._all_records):,} records",
                text_color=COLORS["success"],
            )

    def _populate_filter_combos(self) -> None:
        """Populate Official and Entity comboboxes from loaded data."""
        officials: set = set()
        entities:  set = set()
        for rec in self._all_records:
            f700 = rec.get("form700", {})
            for o in f700.get("officials", []):
                if o:
                    officials.add(o)
            for e in f700.get("entities", []):
                if e:
                    entities.add(e)

        sorted_officials = ["All Officials"] + sorted(officials)
        sorted_entities  = ["All Entities"]  + sorted(entities)

        self._official_cb.configure(values=sorted_officials)
        self._official_var.set("All Officials")
        self._entity_cb.configure(values=sorted_entities)
        self._entity_var.set("All Entities")

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _build_filter_state(self) -> dict:
        conf_val  = self._conf_var.get()
        conf_map  = {"High": ["high"], "Med": ["medium"], "Low": ["low"]}
        conf_list = conf_map.get(conf_val, None)  # None means All

        official = self._official_var.get()
        if official in ("All Officials", ""):
            official = None

        entity = self._entity_var.get()
        if entity in ("All Entities", ""):
            entity = None

        return {
            "confidence": conf_list,
            "official":   official,
            "entity":     entity,
            "keyword":    None,
            "match_only": self._match_only_var.get(),
        }

    def _apply_filters(self) -> None:
        filters = self._build_filter_state()
        self._filtered_records = self._engine.apply(self._all_records, filters)
        self._all_agg      = self._engine.compute_aggregates(self._all_records)
        self._filtered_agg = self._engine.compute_aggregates(self._filtered_records)
        self._refresh_all()

    def _reset_filters(self) -> None:
        self._conf_var.set("All")
        self._official_var.set("All Officials")
        self._entity_var.set("All Entities")
        self._match_only_var.set(True)
        self._apply_filters()

    def _on_filter_click_from_list(self, kind: str, name: str) -> None:
        """Called when user clicks an official/entity in the OfficialsAgent."""
        if kind == "official":
            self._official_var.set(name)
        elif kind == "entity":
            self._entity_var.set(name)
        self._apply_filters()

    # ------------------------------------------------------------------
    # Refresh all agents
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        agg  = self._all_agg
        fagg = self._filtered_agg

        self._summary_agent.update(agg, fagg)
        self._confidence_agent.update(agg, fagg)
        self._officials_agent.update(
            fagg.get("officials_counts", {}),
            fagg.get("entities_counts",  {}),
        )
        self._browser_agent.update(self._filtered_records)

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
                        source   = rec.get("source",   {})
                        f700     = rec.get("form700",   {})
                        writer.writerow({
                            "id":          rec.get("id", ""),
                            "confidence":  conflict.get("confidence", ""),
                            "match":       conflict.get("match", ""),
                            "reasoning":   conflict.get("reasoning", ""),
                            "source_file": source.get("file", ""),
                            "page":        source.get("page", ""),
                            "officials":   "; ".join(f700.get("officials", [])),
                            "entities":    "; ".join(f700.get("entities",  [])),
                            "keywords":    "; ".join(rec.get("keywords_matched", [])),
                        })
                self.root.after(
                    0, lambda: messagebox.showinfo("Saved", f"CSV saved to:\n{path}")
                )
            except Exception as exc:  # noqa: BLE001
                self.root.after(
                    0, lambda: messagebox.showerror("Export Error", str(exc))
                )

        threading.Thread(target=_write, daemon=True).start()

    # ------------------------------------------------------------------
    # PDF export (see below)
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

        agg          = self._filtered_agg
        loaded_name  = self._loaded_path.name if self._loaded_path else "unknown"
        total        = len(self._all_records)
        shown        = len(self._filtered_records)

        def _write():
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.lib import colors as rl_colors
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import inch
                from reportlab.platypus import (
                    SimpleDocTemplate, Table, TableStyle,
                    Paragraph, Spacer,
                )

                doc = SimpleDocTemplate(
                    path,
                    pagesize=letter,
                    leftMargin=0.75 * inch,
                    rightMargin=0.75 * inch,
                    topMargin=0.75 * inch,
                    bottomMargin=0.75 * inch,
                )

                styles = getSampleStyleSheet()
                title_style = ParagraphStyle(
                    "CoITitle",
                    parent=styles["Title"],
                    fontSize=18,
                    spaceAfter=6,
                    textColor=rl_colors.HexColor("#9d6fe8"),
                )
                sub_style = ParagraphStyle(
                    "CoISub",
                    parent=styles["Normal"],
                    fontSize=9,
                    textColor=rl_colors.HexColor("#9b93b8"),
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
                    textColor=rl_colors.HexColor("#b07af5"),
                    spaceBefore=14,
                    spaceAfter=6,
                )

                conf_colors = {
                    "high":   rl_colors.HexColor("#e05878"),
                    "medium": rl_colors.HexColor("#b07af5"),
                    "low":    rl_colors.HexColor("#34c97a"),
                }

                story = []

                # Title block
                story.append(Paragraph("Sacramento County", title_style))
                story.append(Paragraph("Conflict of Interest — Flagged Records Report", title_style))
                story.append(Paragraph(
                    f"Source: {loaded_name}  ·  "
                    f"Showing {shown:,} of {total:,} records  ·  "
                    f"High: {agg.get('by_confidence', {}).get('high', 0):,}  "
                    f"Medium: {agg.get('by_confidence', {}).get('medium', 0):,}  "
                    f"Low: {agg.get('by_confidence', {}).get('low', 0):,}",
                    sub_style,
                ))

                # Records table
                story.append(Paragraph("Flagged Records", section_style))

                col_widths = [0.7*inch, 1.2*inch, 0.4*inch, 1.4*inch, 1.3*inch, 2.3*inch]
                header_row = ["Confidence", "Source File", "Pg", "Officials", "Entities", "Reasoning"]
                table_data = [header_row]

                for rec in self._filtered_records[:2000]:   # cap at 2000 rows for PDF size
                    conflict = rec.get("conflict", {})
                    source   = rec.get("source", {})
                    f700     = rec.get("form700", {})
                    fname    = source.get("file", "")
                    # Truncate long filenames
                    fname_short = fname[:28] + "…" if len(fname) > 30 else fname
                    reasoning   = conflict.get("reasoning", "")
                    reasoning   = reasoning[:220] + "…" if len(reasoning) > 220 else reasoning
                    table_data.append([
                        Paragraph(conflict.get("confidence", "").upper(), body_style),
                        Paragraph(fname_short, body_style),
                        str(source.get("page", "")),
                        Paragraph("; ".join(f700.get("officials", [])) or "—", body_style),
                        Paragraph("; ".join(f700.get("entities",  [])) or "—", body_style),
                        Paragraph(reasoning, body_style),
                    ])

                tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ("BACKGROUND",  (0, 0), (-1, 0), rl_colors.HexColor("#131020")),
                    ("TEXTCOLOR",   (0, 0), (-1, 0), rl_colors.HexColor("#e4dff5")),
                    ("FONTSIZE",    (0, 0), (-1, 0), 8),
                    ("FONTSIZE",    (0, 1), (-1, -1), 7),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [rl_colors.HexColor("#1a1630"), rl_colors.HexColor("#221e38")]),
                    ("TEXTCOLOR",   (0, 1), (-1, -1), rl_colors.HexColor("#e4dff5")),
                    ("GRID",        (0, 0), (-1, -1), 0.3, rl_colors.HexColor("#3d3560")),
                    ("VALIGN",      (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING",  (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))

                # Colour-code the confidence column per row
                for i, rec in enumerate(self._filtered_records[:2000], start=1):
                    conf  = rec.get("conflict", {}).get("confidence", "low")
                    color = conf_colors.get(conf, rl_colors.gray)
                    tbl.setStyle(TableStyle([
                        ("TEXTCOLOR", (0, i), (0, i), color),
                        ("FONTSIZE",  (0, i), (0, i), 7),
                    ]))

                story.append(tbl)

                if shown > 2000:
                    story.append(Spacer(1, 0.15 * inch))
                    story.append(Paragraph(
                        f"⚠  Report capped at 2,000 rows. Full dataset: {shown:,} records. "
                        "Use CSV export for complete data.",
                        sub_style,
                    ))

                doc.build(story)
                self.root.after(
                    0, lambda: messagebox.showinfo("Saved", f"PDF saved to:\n{path}")
                )
            except ImportError:
                self.root.after(0, lambda: messagebox.showerror(
                    "Missing Dependency",
                    "reportlab is required for PDF export.\n\nRun:\n  pip install reportlab",
                ))
            except Exception as exc:
                self.root.after(
                    0, lambda: messagebox.showerror("Export Error", str(exc))
                )

        threading.Thread(target=_write, daemon=True).start()

    # ------------------------------------------------------------------
    # Email export
    # ------------------------------------------------------------------

    def _open_email_dialog(self) -> None:
        """Open the EmailDialog pre-populated with the current filtered records."""
        # Collect unique official names from filtered aggregates
        officials_counts: dict = self._filtered_agg.get("officials_counts", {})
        officials: list[str] = sorted(officials_counts.keys()) if officials_counts else []

        dialog = EmailDialog(
            parent    = self.root,
            records   = self._filtered_records,
            officials = officials,
        )
        dialog.lift()
