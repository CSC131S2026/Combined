"""
PipelineAgent — UI for running the Backend conflict-flagging pipeline.

Exposes inputs for the OpenAI API key, year / input directory, optional sample
limit, and a "Run" button (paired with a "Cancel" button). Streams log output
into a scrolling textbox, shows a real progress bar driven by
:meth:`PipelineRunner.on_progress`, and — on success — offers to load the
produced JSON into the Dashboard.

All cross-thread communication funnels through a single typed event queue
(``self._events``) drained from the Tk main loop via ``parent.after``.
"""

from __future__ import annotations

import queue
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from core.pipeline_runner import PipelineRunner
from shared.resource_path import is_frozen
from ui.theme import COLORS, font


# Log line cap: trim oldest lines once we exceed MAX_LOG_LINES, leaving TRIM_TO
# behind so we don't pay the trim cost on every append.
MAX_LOG_LINES = 5000
TRIM_TO = 4500


class PipelineAgent:
    """Pipeline-tab controller. Owns its own widgets and runner."""

    def __init__(
        self,
        parent,
        *,
        on_results_ready: Callable[[Path], None] | None = None,
    ) -> None:
        self.parent = parent
        self._on_results_ready = on_results_ready

        self._runner = PipelineRunner()
        # Single typed event queue: ('log', str) | ('progress', int, int, str|None) | ('done', bool, str|None, str|None)
        self._events: queue.Queue[tuple] = queue.Queue()
        self._last_output_path: Path | None = None
        self._pump_running = False
        self._progress_total = 0

        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        outer = ctk.CTkFrame(self.parent, fg_color="transparent")
        outer.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        controls = ctk.CTkFrame(
            outer,
            fg_color=COLORS["bg_card"],
            corner_radius=20,
            border_width=1,
            border_color=COLORS["border"],
        )
        controls.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 8))
        controls.grid_columnconfigure(1, weight=1)
        controls.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            controls,
            text="Run conflict-flagging pipeline",
            font=font("headline", size=16),
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(14, 0))

        ctk.CTkLabel(
            controls,
            text="Runs Backend/src/llmFlagging/higherSpec_openai.py in-process and writes a JSON you can load below.",
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
            wraplength=900,
            justify="left",
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=16, pady=(2, 10))

        # API key row
        self._api_key_var = ctk.StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        ctk.CTkLabel(
            controls, text="OpenAI API key", font=font("label"), text_color=COLORS["text_muted"]
        ).grid(row=2, column=0, sticky="w", padx=(16, 8), pady=(4, 2))

        self._api_key_entry = ctk.CTkEntry(
            controls,
            textvariable=self._api_key_var,
            placeholder_text="sk-...",
            show="•",
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            height=34,
            corner_radius=12,
        )
        self._api_key_entry.grid(row=2, column=1, columnspan=3, sticky="ew", padx=(0, 16), pady=(4, 2))

        # Note shown after the key is auto-cleared on a successful run. Empty
        # by default so it occupies no visual space until needed. Sits at row=3
        # directly under the masked entry; downstream rows shifted accordingly.
        self._api_key_note_lbl = ctk.CTkLabel(
            controls,
            text="",
            font=font("body_small"),
            text_color=COLORS["text_muted"],
            anchor="w",
            justify="left",
        )
        self._api_key_note_lbl.grid(
            row=3, column=1, columnspan=3, sticky="w", padx=(0, 16), pady=(0, 4)
        )

        # Year + model row
        ctk.CTkLabel(
            controls, text="Year", font=font("label"), text_color=COLORS["text_muted"]
        ).grid(row=4, column=0, sticky="w", padx=(16, 8), pady=(8, 2))

        self._year_var = ctk.StringVar(value="2019")
        ctk.CTkEntry(
            controls,
            textvariable=self._year_var,
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            height=34,
            corner_radius=12,
            width=120,
        ).grid(row=4, column=1, sticky="w", padx=(0, 16), pady=(8, 2))

        ctk.CTkLabel(
            controls, text="Model", font=font("label"), text_color=COLORS["text_muted"]
        ).grid(row=4, column=2, sticky="w", padx=(0, 8), pady=(8, 2))

        self._model_var = ctk.StringVar(value=os.environ.get("OPENAI_CONFLICT_MODEL", "gpt-5.4-mini"))
        ctk.CTkEntry(
            controls,
            textvariable=self._model_var,
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            height=34,
            corner_radius=12,
        ).grid(row=4, column=3, sticky="ew", padx=(0, 16), pady=(8, 2))

        # Input dir override row
        ctk.CTkLabel(
            controls, text="Input dir (optional)", font=font("label"), text_color=COLORS["text_muted"]
        ).grid(row=5, column=0, sticky="w", padx=(16, 8), pady=(8, 2))

        self._input_dir_var = ctk.StringVar(value="")
        ctk.CTkEntry(
            controls,
            textvariable=self._input_dir_var,
            placeholder_text="Defaults to Backend/src/web_scrapers/output_data/<year>",
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            height=34,
            corner_radius=12,
        ).grid(row=5, column=1, columnspan=2, sticky="ew", padx=(0, 8), pady=(8, 2))

        ctk.CTkButton(
            controls,
            text="Browse...",
            font=font("label_bold"),
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["shadow"],
            text_color=COLORS["text_primary"],
            height=34,
            corner_radius=12,
            command=self._browse_input_dir,
        ).grid(row=5, column=3, sticky="ew", padx=(0, 16), pady=(8, 2))

        # Sample limit row + buttons
        ctk.CTkLabel(
            controls, text="Sample limit", font=font("label"), text_color=COLORS["text_muted"]
        ).grid(row=6, column=0, sticky="w", padx=(16, 8), pady=(8, 14))

        self._sample_var = ctk.StringVar(value="0")
        ctk.CTkEntry(
            controls,
            textvariable=self._sample_var,
            fg_color=COLORS["bg_secondary"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            height=34,
            corner_radius=12,
            width=120,
        ).grid(row=6, column=1, sticky="w", padx=(0, 16), pady=(8, 14))

        ctk.CTkLabel(
            controls,
            text="0 = no cap",
            font=font("body_small"),
            text_color=COLORS["text_muted"],
        ).grid(row=6, column=2, sticky="w", padx=(0, 16), pady=(8, 14))

        button_row = ctk.CTkFrame(controls, fg_color="transparent")
        button_row.grid(row=6, column=3, sticky="e", padx=(0, 16), pady=(8, 14))

        self._cancel_btn = ctk.CTkButton(
            button_row,
            text="Cancel",
            font=font("section"),
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["shadow"],
            text_color=COLORS["text_primary"],
            height=36,
            corner_radius=14,
            width=96,
            command=self._on_cancel_clicked,
            state="disabled",
        )
        self._cancel_btn.pack(side="right", padx=(8, 0))

        self._run_btn = ctk.CTkButton(
            button_row,
            text="Run pipeline",
            font=font("section"),
            fg_color=COLORS["accent_purple"],
            hover_color=COLORS["accent_violet"],
            text_color=COLORS["text_inverse"],
            height=36,
            corner_radius=14,
            command=self._on_run_clicked,
        )
        self._run_btn.pack(side="right")

        # Status + log
        log_card = ctk.CTkFrame(
            outer,
            fg_color=COLORS["bg_card"],
            corner_radius=20,
            border_width=1,
            border_color=COLORS["border"],
        )
        log_card.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        log_card.grid_rowconfigure(3, weight=1)
        log_card.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(log_card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Output",
            font=font("section"),
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=0, sticky="w")

        self._status_lbl = ctk.CTkLabel(
            header,
            text="Idle",
            font=font("body_small"),
            text_color=COLORS["text_secondary"],
        )
        self._status_lbl.grid(row=0, column=1, sticky="e")

        # Progress bar + counter label
        progress_row = ctk.CTkFrame(log_card, fg_color="transparent")
        progress_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 4))
        progress_row.grid_columnconfigure(0, weight=1)

        self._progress_bar = ctk.CTkProgressBar(
            progress_row,
            height=10,
            corner_radius=8,
            progress_color=COLORS["accent_purple"],
            fg_color=COLORS["bg_secondary"],
        )
        self._progress_bar.set(0)
        self._progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self._progress_lbl = ctk.CTkLabel(
            progress_row,
            text="0 / 0 pages",
            font=font("body_small"),
            text_color=COLORS["text_muted"],
        )
        self._progress_lbl.grid(row=0, column=1, sticky="e")

        actions = ctk.CTkFrame(log_card, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 6))
        actions.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            actions,
            text="Clear log",
            font=font("label_bold"),
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["shadow"],
            text_color=COLORS["text_primary"],
            height=30,
            corner_radius=12,
            width=90,
            command=self._clear_log,
        ).grid(row=0, column=1, sticky="e", padx=(0, 6))

        self._load_btn = ctk.CTkButton(
            actions,
            text="Load result into Dashboard",
            font=font("label_bold"),
            fg_color=COLORS["accent_green"],
            hover_color=COLORS["accent_emerald"],
            text_color=COLORS["text_inverse"],
            height=30,
            corner_radius=12,
            command=self._load_into_dashboard,
            state="disabled",
        )
        self._load_btn.grid(row=0, column=2, sticky="e")

        self._log_widget = ctk.CTkTextbox(
            log_card,
            fg_color=COLORS["bg_secondary"],
            text_color=COLORS["text_primary"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=14,
            font=("Menlo", 11),
            wrap="word",
        )
        self._log_widget.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self._log_widget.configure(state="disabled")

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _browse_input_dir(self) -> None:
        chosen = filedialog.askdirectory(title="Select input directory of PDFs/CSVs/TXTs")
        if chosen:
            self._input_dir_var.set(chosen)

    def _clear_log(self) -> None:
        self._log_widget.configure(state="normal")
        self._log_widget.delete("1.0", "end")
        self._log_widget.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        self._log_widget.configure(state="normal")
        self._log_widget.insert("end", text)
        self._log_widget.see("end")
        # Enforce a soft cap on retained log lines so long runs don't bloat
        # the Tk Text widget. Trim down to TRIM_TO so we don't pay the cost
        # on every call.
        total = int(self._log_widget.index("end-1c").split('.')[0])
        if total > MAX_LOG_LINES:
            excess = total - TRIM_TO
            self._log_widget.delete("1.0", f"{excess + 1}.0")
        self._log_widget.configure(state="disabled")

    def _on_run_clicked(self) -> None:
        if self._runner.is_running():
            return

        api_key = self._api_key_var.get().strip()
        if not api_key:
            self._append_log("[error] OpenAI API key is required.\n")
            return

        try:
            sample_limit = int(self._sample_var.get().strip() or "0")
        except ValueError:
            sample_limit = 0

        input_dir_raw = self._input_dir_var.get().strip()
        input_dir = input_dir_raw or None
        year = self._year_var.get().strip() or None
        model = self._model_var.get().strip() or None

        # In packaged builds the backend default for input_dir lives inside the
        # read-only bundle, so preprocess.cleanup() crashes trying to write
        # .txt sidecars next to PDFs. Force the user to pick a writable dir.
        if is_frozen() and not input_dir_raw:
            messagebox.showwarning(
                "Input directory required",
                "When running from the packaged app, you must pick an Input dir "
                "with the PDFs/.txt files to analyze. The default location is read-only "
                "inside the bundle and the preprocessor cannot write text sidecars there.",
            )
            return

        self._last_output_path = None
        self._load_btn.configure(state="disabled")
        self._run_btn.configure(state="disabled", text="Running...")
        self._cancel_btn.configure(state="normal")
        self._status_lbl.configure(
            text="Running...", text_color=COLORS["accent_purple"]
        )

        # Reset progress on each run.
        self._progress_total = 0
        self._progress_bar.set(0)
        self._progress_lbl.configure(text="0 / 0 pages")

        started = self._runner.start(
            year=year,
            input_dir=input_dir,
            sample_limit=sample_limit,
            api_key=api_key,
            model=model,
            on_log=self._on_log_event,
            on_progress=self._on_progress_event,
            on_finished=self._on_finished_event,
        )
        if not started:
            self._run_btn.configure(state="normal", text="Run pipeline")
            self._cancel_btn.configure(state="disabled")
            self._status_lbl.configure(text="Already running", text_color=COLORS["warning"])
            return

        # Wipe the API key from the entry once the run has been accepted so a
        # stale key isn't sitting on screen. The note label is revealed the
        # first time this happens so users understand why it disappeared.
        self._api_key_var.set("")
        self._api_key_note_lbl.configure(
            text="Cleared on run for safety — re-enter to run again."
        )

        if not self._pump_running:
            self._pump_running = True
            self._poll_events()

    def _on_cancel_clicked(self) -> None:
        if not self._runner.is_running():
            return
        self._runner.cancel()
        self._cancel_btn.configure(state="disabled")
        self._run_btn.configure(text="Cancelling...")
        self._status_lbl.configure(
            text="Cancelling...", text_color=COLORS["warning"]
        )

    # ------------------------------------------------------------------
    # Background → UI plumbing (single typed event queue)
    # ------------------------------------------------------------------

    def _on_log_event(self, line: str) -> None:
        self._events.put(("log", line))

    def _on_progress_event(self, completed: int, total: int, last_file: str | None) -> None:
        self._events.put(("progress", completed, total, last_file))

    def _on_finished_event(self, ok: bool, output_path: str | None, error: str | None) -> None:
        self._events.put(("done", ok, output_path, error))

    def _poll_events(self) -> None:
        try:
            while True:
                item = self._events.get_nowait()
                kind = item[0]
                if kind == "log":
                    self._append_log(item[1])
                elif kind == "progress":
                    _, completed, total, last_file = item
                    self._apply_progress(completed, total, last_file)
                elif kind == "done":
                    _, ok, output_path, error = item
                    self._handle_finished(ok, output_path, error)
        except queue.Empty:
            pass

        if self._runner.is_running() or not self._events.empty():
            self.parent.after(120, self._poll_events)
        else:
            self._pump_running = False

    def _apply_progress(self, completed: int, total: int, last_file: str | None) -> None:
        self._progress_total = total
        if total > 0:
            self._progress_bar.set(max(0.0, min(1.0, completed / total)))
        else:
            self._progress_bar.set(0)
        if last_file:
            self._progress_lbl.configure(text=f"{completed} / {total} pages — {last_file}")
        else:
            self._progress_lbl.configure(text=f"{completed} / {total} pages")

    def _handle_finished(self, ok: bool, output_path: str | None, error: str | None) -> None:
        self._run_btn.configure(state="normal", text="Run pipeline")
        self._cancel_btn.configure(state="disabled")
        if ok:
            self._status_lbl.configure(
                text="Pipeline finished successfully", text_color=COLORS["success"]
            )
            if self._progress_total > 0:
                self._progress_bar.set(1.0)
            if output_path:
                self._last_output_path = Path(output_path)
                self._append_log(f"\n[done] Output JSON: {output_path}\n")
                if self._last_output_path.exists():
                    self._load_btn.configure(state="normal")
        else:
            cancel_text = (error or "").lower()
            if "cancel" in cancel_text:
                self._status_lbl.configure(
                    text="Cancelled", text_color=COLORS["warning"]
                )
            else:
                self._status_lbl.configure(
                    text="Pipeline failed", text_color=COLORS["danger"]
                )
            if error:
                self._append_log(f"\n[error] {error}\n")

    def _load_into_dashboard(self) -> None:
        if not self._last_output_path or not self._last_output_path.exists():
            return
        if self._on_results_ready is not None:
            try:
                self._on_results_ready(self._last_output_path)
            except Exception as exc:  # noqa: BLE001
                self._append_log(f"\n[error] Failed to load results into dashboard: {exc}\n")
