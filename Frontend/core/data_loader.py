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
        raw_meta = data.get("meta", {}) if isinstance(data, dict) else {}
        meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
        if isinstance(data, dict):
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
                return False
            kind = item[0]
            self._pending_drain = None
            if kind == "ok":
                _, records, meta = item
                if on_success:
                    on_success(records, meta)
            else:
                _, exc = item
                if on_error:
                    on_error(exc)
            return True

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
            return DataLoader._normalize_records(data)
        if isinstance(data, dict):
            if "results" not in data:
                raise ValueError("Unexpected JSON structure: expected dict with a 'results' list")
            results = data["results"]
            if not isinstance(results, list):
                raise ValueError("Unexpected JSON structure: 'results' must be a list")
            return DataLoader._normalize_records(results)
        raise ValueError("Unexpected JSON structure: expected list or dict with 'results' key")

    @staticmethod
    def _normalize_records(records: list) -> list:
        normalized = []
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(f"Unexpected record at index {index}: expected object")
            normalized.append(DataLoader._normalize_record(record, index))
        return normalized

    @staticmethod
    def _normalize_record(record: dict, index: int) -> dict:
        if isinstance(record.get("source"), dict) and isinstance(record.get("conflict"), dict):
            return record

        flat_required = {"file", "page", "match", "confidence", "reasoning"}
        if flat_required.issubset(record):
            return DataLoader._normalize_flat_record(record)

        raise ValueError(
            "Unexpected record at index "
            f"{index}: expected frontend record with source/conflict or flat backend row"
        )

    @staticmethod
    def _split_labels(value) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if not value:
            return []
        return [item.strip() for item in str(value).split(",") if item.strip()]

    @staticmethod
    def _normalize_flat_record(record: dict) -> dict:
        provider = record.get("analysis_provider") or record.get("provider")
        model = record.get("analysis_model") or record.get("model")
        prompt_version = record.get("analysis_prompt_version") or record.get("prompt_version")
        responsible_party = record.get("responsible_party") or ""

        return {
            "id": record.get("id") or f"{record.get('file')}:{record.get('page')}",
            "analyzed_at": record.get("analyzed_at"),
            "source": {
                "file": record.get("file"),
                "page": record.get("page"),
            },
            "conflict": {
                "match": bool(record.get("match")),
                "confidence": str(record.get("confidence") or "").lower(),
                "reasoning": record.get("reasoning") or "",
            },
            "form700": {
                "officials": DataLoader._split_labels(record.get("form700_officials")),
                "entities": DataLoader._split_labels(record.get("form700_entities")),
            },
            "attribution": {
                "primary_party": {
                    "name": responsible_party or None,
                    "type": record.get("responsible_party_type") or "unknown",
                    "role": record.get("responsible_party_role") or record.get("responsible_role") or None,
                    "source": record.get("responsibility_source") or None,
                    "entity": record.get("responsibility_entity") or None,
                },
                "candidates": record.get("accountability_candidates") or [],
            },
            "keywords_matched": DataLoader._split_labels(record.get("keywords_matched")),
            "analysis": {
                "provider": provider,
                "model": model,
                "prompt_version": prompt_version,
                "token_usage": record.get("token_usage") or {},
            },
        }
