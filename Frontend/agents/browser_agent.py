"""
BrowserAgent — filterable Treeview of all conflict records.

Uses ttk.Treeview for performance with 11k+ rows.
Rows are colored by confidence level.
Selecting a row shows its reasoning in a CTkTextbox below.
Batch-inserts rows using root.after() to keep UI responsive.
"""

import customtkinter as ctk
from tkinter import ttk
import tkinter as tk
from agents.base_agent import BaseAgent
from ui.theme import COLORS

_BATCH_SIZE = 500  # rows per after() batch


class BrowserAgent(BaseAgent):

    def get_title(self) -> str:
        return "RECORD BROWSER"

    def get_accent_color(self) -> str:
        return COLORS["accent_purple"]

    def _build_header_controls(self) -> None:
        self._status_var = tk.StringVar(value="No data loaded")
        self._status_lbl = ctk.CTkLabel(
            self.header_frame,
            textvariable=self._status_var,
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        )
        self._status_lbl.grid(row=0, column=1, padx=12, pady=6, sticky="e")
        self.header_frame.grid_columnconfigure(1, weight=0)

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self.frame, fg_color="transparent")
        body.grid(row=1, column=0, padx=8, pady=(4, 8), sticky="nsew")
        body.grid_rowconfigure(0, weight=3)
        body.grid_rowconfigure(1, weight=0)
        body.grid_rowconfigure(2, weight=1)
        body.grid_columnconfigure(0, weight=1)

        # --- Treeview container ---
        tree_frame = tk.Frame(body, bg=COLORS["bg_card"])
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self._style_treeview()

        cols = ("Confidence", "Source File", "Page", "Officials", "Entities", "Keywords")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            selectmode="browse",
            style="Dark.Treeview",
        )

        # Column headings
        for col in cols:
            self.tree.heading(col, text=col)

        self.tree.column("Confidence", width=90,  minwidth=70,  anchor="center", stretch=False)
        self.tree.column("Source File", width=200, minwidth=120)
        self.tree.column("Page",        width=55,  minwidth=40,  anchor="center", stretch=False)
        self.tree.column("Officials",   width=160, minwidth=80)
        self.tree.column("Entities",    width=160, minwidth=80)
        self.tree.column("Keywords",    width=130, minwidth=80)

        # Row color tags
        self.tree.tag_configure("high",   foreground=COLORS["confidence_high"])
        self.tree.tag_configure("medium", foreground=COLORS["confidence_medium"])
        self.tree.tag_configure("low",    foreground=COLORS["confidence_low"])
        self.tree.tag_configure("alt",    background="#1e1a34")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)

        # --- Separator ---
        sep = ctk.CTkFrame(body, height=1, fg_color=COLORS["border"])
        sep.grid(row=1, column=0, sticky="ew", pady=(4, 4))

        # --- Reasoning detail ---
        detail_frame = ctk.CTkFrame(body, fg_color=COLORS["bg_elevated"], corner_radius=8)
        detail_frame.grid(row=2, column=0, sticky="nsew")
        detail_frame.grid_rowconfigure(1, weight=1)
        detail_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            detail_frame, text="REASONING",
            font=ctk.CTkFont("Andale Mono", 10),
            text_color=COLORS["text_secondary"],
        ).grid(row=0, column=0, padx=10, pady=(6, 0), sticky="w")

        self._detail_box = ctk.CTkTextbox(
            detail_frame,
            fg_color=COLORS["bg_elevated"],
            text_color=COLORS["text_primary"],
            font=ctk.CTkFont("Andale Mono", 11),
            wrap="word",
            state="disabled",
            corner_radius=6,
            height=80,
            border_width=0,
        )
        self._detail_box.grid(row=1, column=0, padx=8, pady=(2, 8), sticky="nsew")

        # Internal state
        self._reasoning_map: dict[str, str] = {}
        self._pending_records: list | None  = None
        self._pending_offset: int           = 0
        self._total_pending: int            = 0

    # ------------------------------------------------------------------
    # Public update API
    # ------------------------------------------------------------------

    def update(self, records: list) -> None:
        """Clear and repopulate the treeview using batched after() inserts."""
        # Cancel any in-progress batch
        self._pending_records = None

        # Clear existing rows
        self.tree.delete(*self.tree.get_children())
        self._reasoning_map.clear()
        self._detail_box.configure(state="normal")
        self._detail_box.delete("1.0", "end")
        self._detail_box.configure(state="disabled")

        if not records:
            self._status_var.set("No records to show")
            return

        self._pending_records = records
        self._pending_offset  = 0
        self._total_pending   = len(records)
        self._status_var.set(f"Loading {self._total_pending:,} records…")
        self._insert_batch()

    # ------------------------------------------------------------------
    # Batch insert
    # ------------------------------------------------------------------

    def _insert_batch(self) -> None:
        records = self._pending_records
        if records is None:
            return

        offset = self._pending_offset
        batch  = records[offset : offset + _BATCH_SIZE]

        for i, rec in enumerate(batch):
            abs_i  = offset + i
            conf   = rec.get("conflict", {}).get("confidence", "").lower()
            source = rec.get("source", {})
            fname  = source.get("file", "")
            fname_short = (fname[-45:] + "…") if len(fname) > 46 else fname
            page   = source.get("page", "")
            f700   = rec.get("form700", {})
            officials = ", ".join(f700.get("officials", []))
            entities  = ", ".join(f700.get("entities",  []))
            keywords  = ", ".join(rec.get("keywords_matched", []))

            tags = [conf] if conf else []
            if abs_i % 2 == 1:
                tags.append("alt")

            iid = str(abs_i)
            self.tree.insert(
                "", "end", iid=iid,
                values=(conf.capitalize(), fname_short, page, officials, entities, keywords),
                tags=tuple(tags),
            )
            reasoning = rec.get("conflict", {}).get("reasoning", "")
            if reasoning:
                self._reasoning_map[iid] = reasoning

        self._pending_offset += len(batch)

        if self._pending_offset < self._total_pending:
            # Schedule next batch; keep UI responsive
            self.frame.after(10, self._insert_batch)
        else:
            self._pending_records = None
            self._status_var.set(
                f"Showing {self._total_pending:,} records"
            )

    # ------------------------------------------------------------------
    # Row selection
    # ------------------------------------------------------------------

    def _on_row_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        reasoning = self._reasoning_map.get(iid, "No reasoning recorded.")
        self._detail_box.configure(state="normal")
        self._detail_box.delete("1.0", "end")
        self._detail_box.insert("end", reasoning)
        self._detail_box.configure(state="disabled")

    # ------------------------------------------------------------------
    # Treeview dark styling
    # ------------------------------------------------------------------

    @staticmethod
    def _style_treeview() -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        bg    = COLORS["bg_card"]
        fg    = COLORS["text_primary"]
        panel = COLORS["bg_elevated"]
        sel   = COLORS["accent_purple"]
        bdr   = COLORS["border"]

        style.configure(
            "Dark.Treeview",
            background=bg,
            foreground=fg,
            fieldbackground=bg,
            borderwidth=0,
            font=("Andale Mono", 10),
            rowheight=24,
        )
        style.configure(
            "Dark.Treeview.Heading",
            background=panel,
            foreground=COLORS["accent_purple"],
            relief="flat",
            font=("Andale Mono", 10, "bold"),
        )
        style.map(
            "Dark.Treeview",
            background=[("selected", sel)],
            foreground=[("selected", "#ffffff")],
        )
        style.map(
            "Dark.Treeview.Heading",
            background=[("active", bdr)],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=panel,
            troughcolor=bg,
            borderwidth=0,
            arrowcolor=COLORS["text_muted"],
        )
        style.configure(
            "Horizontal.TScrollbar",
            background=panel,
            troughcolor=bg,
            borderwidth=0,
            arrowcolor=COLORS["text_muted"],
        )
