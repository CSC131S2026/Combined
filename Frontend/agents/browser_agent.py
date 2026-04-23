"""
BrowserAgent — review workspace for conflict records.

Pairs the high-volume treeview with a persistent detail well so the user
can skim rows and inspect reasoning without the layout collapsing into a
generic table-plus-footer pattern.
"""

from pathlib import Path
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from agents.base_agent import BaseAgent
from ui.theme import COLORS, font, resolve_color

_BATCH_SIZE = 400


class BrowserAgent(BaseAgent):

    def get_title(self) -> str:
        return "Record Browser"

    def get_kicker(self) -> str:
        return "Review workspace"

    def get_accent_color(self) -> str:
        return COLORS["accent_purple"]

    def _build_header_controls(self) -> None:
        self._status_var = tk.StringVar(value="No data loaded")
        self._status_lbl = ctk.CTkLabel(
            self.header_frame,
            textvariable=self._status_var,
            font=font("label"),
            text_color=COLORS["text_muted"],
        )
        self._status_lbl.grid(row=0, column=1, padx=4, pady=8, sticky="e")
        self.header_frame.grid_columnconfigure(1, weight=0)

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.grid(row=1, column=0, padx=14, pady=(2, 14), sticky="nsew")
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=4)
        body.grid_columnconfigure(1, weight=2)

        strip = ctk.CTkFrame(
            body,
            fg_color=COLORS["bg_secondary"],
            corner_radius=20,
            border_width=1,
            border_color=COLORS["border"],
        )
        strip.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        strip.grid_columnconfigure(0, weight=1)

        self._story_title = ctk.CTkLabel(
            strip,
            text="Browse the flagged record set",
            font=font("section", size=14),
            text_color=COLORS["text_primary"],
        )
        self._story_title.grid(row=0, column=0, padx=16, pady=(12, 2), sticky="w")

        self._story_note = ctk.CTkLabel(
            strip,
            text="Select a row to inspect source details, participants, and reasoning.",
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
            justify="left",
        )
        self._story_note.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        table_shell = ctk.CTkFrame(
            body,
            fg_color=COLORS["bg_secondary"],
            corner_radius=22,
            border_width=1,
            border_color=COLORS["border"],
        )
        table_shell.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        table_shell.grid_rowconfigure(0, weight=1)
        table_shell.grid_columnconfigure(0, weight=1)

        detail = ctk.CTkFrame(
            body,
            fg_color=COLORS["highlight_gold"],
            corner_radius=22,
            border_width=1,
            border_color=COLORS["border"],
        )
        detail.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        detail.grid_rowconfigure(7, weight=1)
        detail.grid_columnconfigure(0, weight=1)

        self._tree_frame = tk.Frame(table_shell, bg=resolve_color("bg_secondary"))
        self._tree_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self._tree_frame.grid_rowconfigure(0, weight=1)
        self._tree_frame.grid_columnconfigure(0, weight=1)

        self._style_treeview()

        cols = ("Confidence", "Source File", "Page", "Officials", "Entities", "Keywords")
        self.tree = ttk.Treeview(
            self._tree_frame,
            columns=cols,
            show="headings",
            selectmode="browse",
            style="Editorial.Treeview",
        )

        for col in cols:
            self.tree.heading(col, text=col)

        self.tree.column("Confidence", width=110, minwidth=88, anchor="center", stretch=False)
        self.tree.column("Source File", width=250, minwidth=160)
        self.tree.column("Page", width=64, minwidth=48, anchor="center", stretch=False)
        self.tree.column("Officials", width=180, minwidth=110)
        self.tree.column("Entities", width=180, minwidth=110)
        self.tree.column("Keywords", width=170, minwidth=100)

        self._apply_tree_tags()

        vsb = ttk.Scrollbar(self._tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self._tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)

        ctk.CTkLabel(
            detail,
            text="Selected record",
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, padx=16, pady=(16, 2), sticky="w")

        self._detail_source_lbl = ctk.CTkLabel(
            detail,
            text="Choose a record from the table",
            font=font("section", size=15),
            text_color=COLORS["text_primary"],
            justify="left",
            wraplength=300,
        )
        self._detail_source_lbl.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        meta_row = ctk.CTkFrame(detail, fg_color="transparent")
        meta_row.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="ew")
        meta_row.grid_columnconfigure(2, weight=1)

        self._detail_conf_lbl = ctk.CTkLabel(
            meta_row,
            text="No selection",
            font=font("label_bold"),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_secondary"],
            corner_radius=999,
            height=28,
            padx=12,
        )
        self._detail_conf_lbl.grid(row=0, column=0, sticky="w")

        self._detail_page_lbl = ctk.CTkLabel(
            meta_row,
            text="",
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
        )
        self._detail_page_lbl.grid(row=0, column=1, padx=(8, 0), sticky="w")

        self._detail_id_lbl = ctk.CTkLabel(
            meta_row,
            text="",
            font=font("label"),
            text_color=COLORS["text_muted"],
        )
        self._detail_id_lbl.grid(row=0, column=2, sticky="e")

        self._detail_officials = self._make_detail_field(detail, row=3, heading="Officials")
        self._detail_entities = self._make_detail_field(detail, row=4, heading="Entities")
        self._detail_keywords = self._make_detail_field(detail, row=5, heading="Keywords")

        ctk.CTkLabel(
            detail,
            text="Reasoning",
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).grid(row=6, column=0, padx=16, pady=(6, 4), sticky="w")

        self._detail_box = ctk.CTkTextbox(
            detail,
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            font=font("body_small"),
            wrap="word",
            state="disabled",
            corner_radius=16,
            border_width=1,
            border_color=COLORS["border"],
        )
        self._detail_box.grid(row=7, column=0, padx=16, pady=(0, 16), sticky="nsew")

        self._record_map: dict[str, dict] = {}
        self._pending_records: list | None = None
        self._pending_offset = 0
        self._total_pending = 0
        self._clear_detail()

    def _make_detail_field(self, parent, row: int, heading: str):
        shell = ctk.CTkFrame(parent, fg_color="transparent")
        shell.grid(row=row, column=0, padx=16, pady=(0, 8), sticky="ew")
        shell.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            shell,
            text=heading,
            font=font("label"),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w")

        value = ctk.CTkLabel(
            shell,
            text="—",
            font=font("body_small"),
            text_color=COLORS["text_primary"],
            justify="left",
            wraplength=300,
        )
        value.grid(row=1, column=0, sticky="w", pady=(1, 0))
        return value

    # ------------------------------------------------------------------
    # Public update API
    # ------------------------------------------------------------------

    def update(self, records: list) -> None:
        self._pending_records = None
        self.tree.delete(*self.tree.get_children())
        self._record_map.clear()
        self._clear_detail()

        if not records:
            self._status_var.set("No records to show")
            self._story_title.configure(text="No records in the current view")
            self._story_note.configure(text="Adjust the filters or load a different JSON file to inspect reasoning.")
            return

        self._pending_records = records
        self._pending_offset = 0
        self._total_pending = len(records)
        self._status_var.set(f"Loading {self._total_pending:,} records...")
        self._story_title.configure(text="Browse the flagged record set")
        self._story_note.configure(text=f"{self._total_pending:,} rows are loading into the review table.")
        self._insert_batch()

    # ------------------------------------------------------------------
    # Batch insert
    # ------------------------------------------------------------------

    def _insert_batch(self) -> None:
        records = self._pending_records
        if records is None:
            return

        offset = self._pending_offset
        batch = records[offset: offset + _BATCH_SIZE]

        for i, rec in enumerate(batch):
            abs_i = offset + i
            conf = (rec.get("conflict", {}).get("confidence") or "").lower()
            source = rec.get("source", {})
            file_name = source.get("file", "")
            display_name = Path(file_name).name if file_name else "Unknown source"
            file_short = display_name[:44] + "..." if len(display_name) > 47 else display_name
            page = source.get("page", "")
            f700 = rec.get("form700", {})
            officials = ", ".join(f700.get("officials", []))
            entities = ", ".join(f700.get("entities", []))
            keywords = ", ".join(rec.get("keywords_matched", []))

            tags = [conf] if conf else []
            if abs_i % 2 == 1:
                tags.append("alt")

            iid = str(abs_i)
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    conf.capitalize(),
                    file_short,
                    page,
                    officials,
                    entities,
                    keywords,
                ),
                tags=tuple(tags),
            )
            self._record_map[iid] = rec

        self._pending_offset += len(batch)

        if self._pending_offset < self._total_pending:
            self.frame.after(10, self._insert_batch)
            return

        self._pending_records = None
        self._status_var.set(f"Showing {self._total_pending:,} records")
        self._story_note.configure(text=f"{self._total_pending:,} rows are ready. Select a record to read its reasoning.")

    # ------------------------------------------------------------------
    # Row selection
    # ------------------------------------------------------------------

    def _on_row_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return

        iid = selection[0]
        rec = self._record_map.get(iid)
        if not rec:
            return

        source = rec.get("source", {})
        display_name = Path(source.get("file", "")).name if source.get("file") else "Unknown source"
        page = source.get("page", "—")
        conf = (rec.get("conflict", {}).get("confidence") or "unknown").lower()

        color_map = {
            "high": COLORS["confidence_high"],
            "medium": COLORS["confidence_medium"],
            "low": COLORS["confidence_low"],
        }
        conf_color = color_map.get(conf, COLORS["text_secondary"])

        self._story_title.configure(text=display_name)
        self._story_note.configure(text=f"Page {page} • {conf.title()} confidence • record {iid}")

        self._detail_source_lbl.configure(text=display_name)
        self._detail_conf_lbl.configure(
            text=f"{conf.title()} confidence",
            text_color=conf_color,
        )
        self._detail_page_lbl.configure(text=f"Page {page}")
        self._detail_id_lbl.configure(text=f"ID {rec.get('id', '—')[:8]}")

        officials = rec.get("form700", {}).get("officials", [])
        entities = rec.get("form700", {}).get("entities", [])
        keywords = rec.get("keywords_matched", [])
        self._detail_officials.configure(text=", ".join(officials) if officials else "None listed")
        self._detail_entities.configure(text=", ".join(entities) if entities else "None listed")
        self._detail_keywords.configure(text=", ".join(keywords) if keywords else "No keyword matches")

        reasoning = rec.get("conflict", {}).get("reasoning", "No reasoning recorded.")
        self._detail_box.configure(state="normal")
        self._detail_box.delete("1.0", "end")
        self._detail_box.insert("end", reasoning)
        self._detail_box.configure(state="disabled")

    def _clear_detail(self) -> None:
        self._story_title.configure(text="Browse the flagged record set")
        self._story_note.configure(text="Select a row to inspect source details, participants, and reasoning.")
        self._detail_source_lbl.configure(text="Choose a record from the table")
        self._detail_conf_lbl.configure(text="No selection", text_color=COLORS["text_secondary"])
        self._detail_page_lbl.configure(text="")
        self._detail_id_lbl.configure(text="")
        self._detail_officials.configure(text="—")
        self._detail_entities.configure(text="—")
        self._detail_keywords.configure(text="—")
        self._detail_box.configure(state="normal")
        self._detail_box.delete("1.0", "end")
        self._detail_box.insert("end", "Reasoning for the selected record will appear here.")
        self._detail_box.configure(state="disabled")

    def refresh_theme(self) -> None:
        """Refresh tk/ttk widgets that do not auto-update with CTk appearance mode."""
        if hasattr(self, "_tree_frame"):
            self._tree_frame.configure(bg=resolve_color("bg_secondary"))
        if hasattr(self, "tree"):
            self._style_treeview()
            self._apply_tree_tags()

    def _apply_tree_tags(self) -> None:
        self.tree.tag_configure("high", foreground=resolve_color("confidence_high"))
        self.tree.tag_configure("medium", foreground=resolve_color("confidence_medium"))
        self.tree.tag_configure("low", foreground=resolve_color("confidence_low"))
        self.tree.tag_configure("alt", background=resolve_color("bg_secondary"))

    # ------------------------------------------------------------------
    # Treeview styling
    # ------------------------------------------------------------------

    def _style_treeview(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        bg = resolve_color("bg_card")
        fg = resolve_color("text_primary")
        panel = resolve_color("bg_elevated")
        sel = resolve_color("highlight_soft")

        style.configure(
            "Editorial.Treeview",
            background=bg,
            foreground=fg,
            fieldbackground=bg,
            borderwidth=0,
            font=("Avenir Next", 11),
            rowheight=30,
        )
        style.configure(
            "Editorial.Treeview.Heading",
            background=panel,
            foreground=fg,
            relief="flat",
            borderwidth=0,
            font=("SF Mono", 10, "bold"),
        )
        style.map(
            "Editorial.Treeview",
            background=[("selected", sel)],
            foreground=[("selected", fg)],
        )
        style.map(
            "Editorial.Treeview.Heading",
            background=[("active", resolve_color("shadow"))],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=panel,
            troughcolor=bg,
            borderwidth=0,
            arrowcolor=resolve_color("text_muted"),
        )
        style.configure(
            "Horizontal.TScrollbar",
            background=panel,
            troughcolor=bg,
            borderwidth=0,
            arrowcolor=resolve_color("text_muted"),
        )
