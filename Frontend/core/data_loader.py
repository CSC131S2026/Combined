"""
DataLoader — loads conflict JSON from disk.

Provides:
  • load_sync(path)  — blocking load, returns list of result dicts
  • load(path, callback)  — background-thread load; calls callback(records, meta) on completion
"""

import json
import queue
import threading
from pathlib import Path

# Resolve default paths relative to this file's location
FRONTEND_DIR = Path(__file__).parent.parent       # Frontend/
BACKEND_DIR  = FRONTEND_DIR.parent / "Backend"
DEFAULT_PATH = (
    BACKEND_DIR / "conflict_flags_openai.json"
    if (BACKEND_DIR / "conflict_flags_openai.json").exists()
    else BACKEND_DIR / "conflict_flags.json"
)


class DataLoader:
    """Loads and caches conflict JSON data."""

    def __init__(self):
        self._cache: dict[str, list] = {}
        self._meta_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Synchronous load
    # ------------------------------------------------------------------

    def load_sync(self, path: str | Path = None) -> tuple[list, dict]:
        """
        Blocking load. Returns (records, meta) where records is a list of
        raw dicts and meta is the top-level metadata dict.
        """
        path = Path(path) if path else DEFAULT_PATH
        key  = str(path)

        if key in self._cache:
            return self._cache[key], self._meta_cache.get(key, {})

        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        records = self._extract_records(data)
        meta    = data.get("meta", {})
        meta["summary"] = data.get("summary", {})

        self._cache[key]      = records
        self._meta_cache[key] = meta
        return records, meta

    # ------------------------------------------------------------------
    # Asynchronous load
    # ------------------------------------------------------------------

    def load(
        self,
        path: str | Path = None,
        on_success=None,
        on_error=None,
    ) -> None:
        """
        Load in a background daemon thread.
        Calls on_success(records, meta) or on_error(exc) when done.
        """
        path = Path(path) if path else DEFAULT_PATH
        result_q: queue.Queue = queue.Queue()

        def _worker():
            try:
                records, meta = self.load_sync(path)
                result_q.put(("ok", records, meta))
            except Exception as exc:  # noqa: BLE001
                result_q.put(("err", exc))

        def _drain():
            try:
                item = result_q.get_nowait()
            except queue.Empty:
                return
            kind = item[0]
            if kind == "ok":
                _, records, meta = item
                if on_success:
                    on_success(records, meta)
            else:
                _, exc = item
                if on_error:
                    on_error(exc)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

        # Poll the queue from the caller's thread (GUI must call this via after())
        # We expose the drain callable so the orchestrator can schedule it.
        self._pending_drain = _drain

    def get_pending_drain(self):
        """Return the drain callable from the most recent async load."""
        return getattr(self, "_pending_drain", None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_records(data: dict | list) -> list:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("results", [])
        raise ValueError("Unexpected JSON structure: expected list or dict with 'results' key")
