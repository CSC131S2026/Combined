"""
PipelineRunner — runs the Backend conflict-flagging pipeline in-process.

Re-implements the analysis loop from
``Backend/src/llmFlagging/higherSpec_openai.py`` so we can:

* bypass the Rich ``Live`` display (which dumps a refreshing layout into our
  log textbox) while keeping the one-shot Rich summary table,
* surface real progress events to the UI via ``on_progress``, and
* cooperatively cancel between pages via :class:`threading.Event`.

The runner emits three kinds of callbacks, all of which are invoked from a
background thread and must be made thread-safe by the caller:

* ``on_log(line: str)`` — a single line of captured stdout/stderr.
* ``on_progress(completed: int, total: int, last_file: str | None)`` — fired
  once per finished page.
* ``on_finished(ok: bool, output_path: str | None, error: str | None)`` —
  fired exactly once when the worker thread exits.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Callable

from shared.resource_path import is_frozen, resource_root


_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _backend_root() -> Path:
    """Filesystem location of the bundled Backend folder (dev or frozen)."""
    if is_frozen():
        return resource_root() / "Backend"
    return Path(__file__).resolve().parents[2] / "Backend"


def _ensure_backend_on_path() -> Path:
    """Make Backend importable so `src.llmFlagging.higherSpec_openai` resolves."""
    backend = _backend_root()
    backend_str = str(backend)
    if backend.is_dir() and backend_str not in sys.path:
        sys.path.insert(0, backend_str)
    return backend


def user_workdir() -> Path:
    """
    User-writable directory the pipeline can chdir into and drop outputs in.

    - Dev: ``Backend/`` so existing behavior (relative outputs land there) holds.
    - Frozen: ``~/Documents/ConflictChecker`` (created if missing) so writes do
      not target the read-only app bundle.
    """
    if is_frozen():
        base = Path.home() / "Documents" / "ConflictChecker"
        base.mkdir(parents=True, exist_ok=True)
        return base
    return _backend_root()


class _QueueWriter:
    """File-like object that pushes whole lines straight to ``on_log``."""

    def __init__(self, on_log: Callable[[str], None] | None, prefix: str = "") -> None:
        self._on_log = on_log
        self._buf = ""
        self._prefix = prefix

    def write(self, data) -> int:
        if not data:
            return 0
        text = data if isinstance(data, str) else str(data)
        text = _strip_ansi(text)
        self._buf += text
        while True:
            idx = self._buf.find("\n")
            if idx < 0:
                break
            line, self._buf = self._buf[: idx + 1], self._buf[idx + 1 :]
            self._emit(self._prefix + line)
        return len(text)

    def flush(self) -> None:
        if self._buf:
            self._emit(self._prefix + self._buf)
            self._buf = ""

    def isatty(self) -> bool:
        return False

    def _emit(self, line: str) -> None:
        if self._on_log is None:
            return
        try:
            self._on_log(line)
        except Exception:  # noqa: BLE001
            pass


class PipelineRunner:
    """
    Run the backend conflict-flagging pipeline in a background thread.

    Usage::

        runner = PipelineRunner()
        runner.start(
            year="2019",
            api_key="sk-...",
            on_log=lambda line: ...,
            on_progress=lambda c, t, f: ...,
            on_finished=lambda ok, output_path, error: ...,
        )
        # ...later...
        runner.cancel()
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def cancel(self) -> None:
        """Request cooperative cancellation. Safe to call from any thread."""
        self._cancel_event.set()

    def is_cancelling(self) -> bool:
        return self._cancel_event.is_set()

    def start(
        self,
        *,
        year: str | None = None,
        input_dir: str | Path | None = None,
        sample_limit: int = 0,
        api_key: str | None = None,
        model: str | None = None,
        on_log: Callable[[str], None] | None = None,
        on_progress: Callable[[int, int, str | None], None] | None = None,
        on_finished: Callable[[bool, str | None, str | None], None] | None = None,
    ) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._cancel_event = threading.Event()
            self._thread = threading.Thread(
                target=self._run,
                name="PipelineRunner",
                kwargs={
                    "year": year,
                    "input_dir": input_dir,
                    "sample_limit": sample_limit,
                    "api_key": api_key,
                    "model": model,
                    "on_log": on_log,
                    "on_progress": on_progress,
                    "on_finished": on_finished,
                },
                daemon=True,
            )
            self._thread.start()
            return True

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _emit(self, on_log: Callable[[str], None] | None, message: str) -> None:
        if on_log is None:
            return
        try:
            on_log(message if message.endswith("\n") else message + "\n")
        except Exception:  # noqa: BLE001
            pass

    def _run(
        self,
        *,
        year: str | None,
        input_dir: str | Path | None,
        sample_limit: int,
        api_key: str | None,
        model: str | None,
        on_log: Callable[[str], None] | None,
        on_progress: Callable[[int, int, str | None], None] | None,
        on_finished: Callable[[bool, str | None, str | None], None] | None,
    ) -> None:
        backend = _ensure_backend_on_path()
        workdir = user_workdir()
        prev_cwd = os.getcwd()
        prev_stdout = sys.stdout
        prev_stderr = sys.stderr
        prev_env: dict[str, str | None] = {}
        output_json: str | None = None
        error_message: str | None = None
        success = False
        cancelled = False

        env_overrides: dict[str, str] = {}
        if api_key:
            env_overrides["OPENAI_API_KEY"] = api_key
        if model:
            env_overrides["OPENAI_CONFLICT_MODEL"] = model
        if sample_limit and sample_limit > 0:
            env_overrides["OPENAI_CONFLICT_SAMPLE_LIMIT"] = str(sample_limit)

        if is_frozen():
            stem_year = (year or "default").strip() or "default"
            output_stem = f"conflict_flags_openai_{stem_year}"
            env_overrides.setdefault("CONFLICT_CSV_PATH", str(workdir / f"{output_stem}.csv"))
            env_overrides.setdefault("CONFLICT_JSON_PATH", str(workdir / f"{output_stem}.json"))
            env_overrides.setdefault(
                "CONFLICT_CHECKPOINT_PATH", str(workdir / f"{output_stem}_checkpoint.json")
            )
            bundled_form700 = backend / "src" / "form700_parse" / "sac700.xlsx"
            if bundled_form700.exists():
                env_overrides.setdefault("FORM700_XLSX_PATH", str(bundled_form700))

        argv: list[str] = []
        if input_dir:
            argv += ["--input-dir", str(input_dir)]
        elif year:
            argv += ["--year", str(year)]

        writer: _QueueWriter | None = None
        try:
            for key, value in env_overrides.items():
                prev_env[key] = os.environ.get(key)
                os.environ[key] = value

            try:
                os.chdir(workdir)
            except Exception:  # noqa: BLE001
                if backend.is_dir():
                    os.chdir(backend)

            writer = _QueueWriter(on_log)
            sys.stdout = writer
            sys.stderr = writer

            self._emit(on_log, f"[runner] Backend root: {backend}")
            self._emit(on_log, f"[runner] argv: {argv or '(defaults)'}")

            try:
                from src.llmFlagging import higherSpec_openai as backend_mod  # type: ignore

                # Force the backend's Rich console to write into our textbox.
                try:
                    from rich.console import Console as _RichConsole  # type: ignore

                    backend_mod._console = _RichConsole(
                        file=writer, force_terminal=False, width=120
                    )
                except Exception:  # noqa: BLE001
                    pass

                # Re-implemented main loop. We deliberately do NOT call
                # backend_mod.main() because it wraps the analysis in a Rich
                # Live display that floods our log textbox with ANSI noise.
                success, cancelled, output_json = self._run_pipeline(
                    backend_mod, argv, on_progress
                )
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
                if code == 0:
                    success = True
                else:
                    error_message = f"Pipeline exited with code {code}"
            except Exception as exc:  # noqa: BLE001
                import traceback

                error_message = f"{type(exc).__name__}: {exc}"
                try:
                    writer.write(traceback.format_exc())
                except Exception:  # noqa: BLE001
                    pass
            finally:
                if writer is not None:
                    writer.flush()
        finally:
            sys.stdout = prev_stdout
            sys.stderr = prev_stderr
            try:
                os.chdir(prev_cwd)
            except Exception:  # noqa: BLE001
                pass
            for key, prev in prev_env.items():
                if prev is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = prev
            with self._lock:
                self._thread = None

        if cancelled:
            success = False
            if not error_message:
                error_message = "Cancelled by user"

        if on_finished is not None:
            try:
                on_finished(success, output_json, error_message)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # Reimplemented pipeline (mirrors backend._analyze_pages / _run_analysis)
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        backend_mod,
        argv: list[str],
        on_progress: Callable[[int, int, str | None], None] | None,
    ) -> tuple[bool, bool, str | None]:
        """Run initialize → analyze (without Rich Live) → write outputs.

        Returns ``(success, cancelled, output_json_path)``.
        """
        cancel_event = self._cancel_event

        backend_mod._initialize_runtime(argv)

        (
            prior_results,
            done_set,
            failed_set,
            token_usage_totals,
            checkpoint_source,
        ) = backend_mod._load_checkpoint()

        remaining = [
            p for p in backend_mod.filtered_pages
            if (p["file"], p["page"]) not in done_set
        ]

        results = list(prior_results)
        state = {
            "results": results,
            "processed": set(done_set),
            "failed": set(failed_set),
            "recent": deque(maxlen=5),
            "conflicts_count": sum(1 for r in results if r.get("match")),
            "conf_counts": {
                "high": sum(1 for r in results if r.get("confidence") == "high"),
                "medium": sum(1 for r in results if r.get("confidence") == "medium"),
                "low": sum(1 for r in results if r.get("confidence") == "low"),
            },
            "token_usage_totals": token_usage_totals,
            "checkpoint_source": checkpoint_source,
        }

        total = len(done_set) + len(remaining)
        if on_progress is not None:
            try:
                on_progress(len(done_set), total, None)
            except Exception:  # noqa: BLE001
                pass

        cancelled = False

        async def _run_loop() -> None:
            nonlocal cancelled
            concurrency = getattr(backend_mod, "_REQUEST_CONCURRENCY", 16) or 16
            checkpoint_interval = getattr(backend_mod, "_CHECKPOINT_INTERVAL", 10) or 10
            sem = asyncio.Semaphore(concurrency)
            lock = asyncio.Lock()
            counter = {"n": 0, "completed": len(done_set)}

            async def bounded(page):
                if cancel_event.is_set():
                    return
                key = (page["file"], page["page"])
                page_token_usage = backend_mod._empty_token_usage()
                async with sem:
                    if cancel_event.is_set():
                        return
                    try:
                        result, page_token_usage = await backend_mod.analyze_page(page)
                    except Exception as e:  # noqa: BLE001
                        legacy = getattr(backend_mod, "_AnalyzePageError", None)
                        if legacy is not None and isinstance(e, legacy):
                            backend_mod._merge_token_usage(page_token_usage, e.token_usage)
                        print(f"Error analyzing {page['file']} p{page['page']}: {e}")
                        result = None

                    do_checkpoint = False
                    async with lock:
                        backend_mod._merge_token_usage(
                            state["token_usage_totals"], page_token_usage
                        )
                        if result is None:
                            state["failed"].add(key)
                            do_checkpoint = True
                        else:
                            state["processed"].add(key)
                            state["failed"].discard(key)
                            state["results"].append(result)
                            state["recent"].appendleft(result)
                            if result.get("match"):
                                state["conflicts_count"] += 1
                            conf = result.get("confidence")
                            if conf in state["conf_counts"]:
                                state["conf_counts"][conf] += 1
                        counter["n"] += 1
                        counter["completed"] += 1
                        if counter["n"] % checkpoint_interval == 0:
                            do_checkpoint = True
                        completed_now = counter["completed"]

                    if on_progress is not None:
                        try:
                            on_progress(completed_now, total, page.get("file"))
                        except Exception:  # noqa: BLE001
                            pass

                    if do_checkpoint:
                        backend_mod._save_checkpoint(
                            state["results"],
                            state["processed"],
                            state["failed"],
                            state["token_usage_totals"],
                            state["checkpoint_source"],
                        )

            # Launch in small batches so cancellation can stop scheduling new
            # pages while letting any in-flight ones drain naturally via the
            # cancel_event check at the head of bounded().
            for page in remaining:
                if cancel_event.is_set():
                    cancelled = True
                    break
            tasks = [asyncio.create_task(bounded(p)) for p in remaining]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=False)
            if cancel_event.is_set():
                cancelled = True

        try:
            asyncio.run(_run_loop())
        finally:
            # Always persist checkpoint on exit (success, cancel, or error).
            try:
                backend_mod._save_checkpoint(
                    state["results"],
                    state["processed"],
                    state["failed"],
                    state["token_usage_totals"],
                    state["checkpoint_source"],
                )
            except Exception:  # noqa: BLE001
                pass

        output_json: str | None = None
        if not cancelled:
            try:
                backend_mod._write_outputs(state)
            except Exception:  # noqa: BLE001
                raise
            try:
                output_json = str(backend_mod._JSON_OUTPUT)
            except Exception:  # noqa: BLE001
                output_json = None
            return True, False, output_json
        else:
            print("[runner] Cancellation requested — checkpoint saved, exiting.")
            return False, True, None
