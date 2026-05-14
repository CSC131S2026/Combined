import datetime
import hashlib
import json
import pathlib
import sqlite3
import uuid


SCHEMA_VERSION = "1"


def utc_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def page_key(page):
    return str(page)


def parse_page_key(value):
    text = "" if value is None else str(value)
    if text.isdigit():
        return int(text)
    return text


def _json_dumps(value):
    return json.dumps(value if value is not None else {}, sort_keys=True)


def _json_loads(value, default):
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _coerce_bool(value):
    if value is None:
        return None
    return bool(value)


def _token_usage(value):
    usage = _json_loads(value, {})
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "total_tokens": int(
            usage.get("total_tokens")
            or ((usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0))
        ),
    }


class SQLiteStore:
    """Small sqlite3 persistence layer for conflict-analysis runs."""

    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.initialize_schema()

    def close(self):
        self.conn.close()

    def initialize_schema(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                input_year TEXT,
                input_dir TEXT NOT NULL,
                input_source TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                output_stem TEXT,
                source_checkpoint TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                total_pages_scanned INTEGER NOT NULL DEFAULT 0,
                total_pages_analyzed INTEGER NOT NULL DEFAULT 0,
                total_results INTEGER NOT NULL DEFAULT 0,
                failed_pages INTEGER NOT NULL DEFAULT 0,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pages (
                input_dir TEXT NOT NULL,
                file TEXT NOT NULL,
                page TEXT NOT NULL,
                text TEXT NOT NULL,
                text_hash TEXT NOT NULL,
                source_metadata TEXT NOT NULL DEFAULT '{}',
                extracted_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (input_dir, file, page)
            );

            CREATE TABLE IF NOT EXISTS analysis_results (
                run_id TEXT NOT NULL,
                input_dir TEXT NOT NULL,
                file TEXT NOT NULL,
                page TEXT NOT NULL,
                match INTEGER,
                confidence TEXT,
                reasoning TEXT,
                form700_officials TEXT,
                form700_entities TEXT,
                responsible_party TEXT,
                responsible_party_type TEXT,
                responsible_party_role TEXT,
                responsibility_source TEXT,
                responsibility_entity TEXT,
                accountability_candidates TEXT NOT NULL DEFAULT '[]',
                keywords_matched TEXT NOT NULL DEFAULT '[]',
                analysis_provider TEXT,
                analysis_model TEXT,
                analysis_prompt_version TEXT,
                token_usage TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL,
                error_message TEXT,
                analyzed_at TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (run_id, file, page),
                FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_runs_resume
                ON runs (input_dir, input_source, input_year, provider, model, prompt_version, started_at);

            CREATE INDEX IF NOT EXISTS idx_analysis_status
                ON analysis_results (run_id, status);
            """
        )
        self.conn.execute(
            """
            INSERT INTO schema_meta (key, value)
            VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (SCHEMA_VERSION,),
        )
        self.conn.commit()

    def start_run(
        self,
        *,
        input_year,
        input_dir,
        input_source,
        provider,
        model,
        prompt_version,
        output_stem,
        total_pages_scanned=0,
        total_pages_analyzed=0,
        source_checkpoint=None,
        run_id=None,
    ):
        run_id = run_id or str(uuid.uuid4())
        now = utc_now_iso()
        self.conn.execute(
            """
            INSERT INTO runs (
                run_id, input_year, input_dir, input_source, provider, model, prompt_version,
                output_stem, source_checkpoint, started_at, completed_at, status,
                total_pages_scanned, total_pages_analyzed, total_results, failed_pages,
                input_tokens, output_tokens, total_tokens, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'running', ?, ?, 0, 0, 0, 0, 0, ?)
            """,
            (
                run_id,
                str(input_year or ""),
                str(input_dir),
                input_source,
                provider,
                model,
                prompt_version,
                output_stem,
                str(source_checkpoint) if source_checkpoint else None,
                now,
                int(total_pages_scanned or 0),
                int(total_pages_analyzed or 0),
                now,
            ),
        )
        self.conn.commit()
        return run_id

    def update_run(
        self,
        run_id,
        *,
        status=None,
        completed_at=None,
        total_pages_scanned=None,
        total_pages_analyzed=None,
        total_results=None,
        failed_pages=None,
        token_usage=None,
        source_checkpoint=None,
    ):
        usage = token_usage or {}
        now = utc_now_iso()
        self.conn.execute(
            """
            UPDATE runs
            SET status = COALESCE(?, status),
                completed_at = COALESCE(?, completed_at),
                total_pages_scanned = COALESCE(?, total_pages_scanned),
                total_pages_analyzed = COALESCE(?, total_pages_analyzed),
                total_results = COALESCE(?, total_results),
                failed_pages = COALESCE(?, failed_pages),
                input_tokens = COALESCE(?, input_tokens),
                output_tokens = COALESCE(?, output_tokens),
                total_tokens = COALESCE(?, total_tokens),
                source_checkpoint = COALESCE(?, source_checkpoint),
                updated_at = ?
            WHERE run_id = ?
            """,
            (
                status,
                completed_at,
                total_pages_scanned,
                total_pages_analyzed,
                total_results,
                failed_pages,
                usage.get("input_tokens") if token_usage is not None else None,
                usage.get("output_tokens") if token_usage is not None else None,
                usage.get("total_tokens") if token_usage is not None else None,
                str(source_checkpoint) if source_checkpoint else None,
                now,
                run_id,
            ),
        )
        self.conn.commit()

    def upsert_pages(self, input_dir, pages, source_metadata=None):
        now = utc_now_iso()
        rows = []
        metadata = source_metadata or {}
        for page in pages:
            text = page.get("text") or ""
            rows.append(
                (
                    str(input_dir),
                    page.get("file") or "",
                    page_key(page.get("page")),
                    text,
                    hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    _json_dumps(metadata),
                    now,
                    now,
                )
            )
        self.conn.executemany(
            """
            INSERT INTO pages (
                input_dir, file, page, text, text_hash, source_metadata, extracted_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(input_dir, file, page) DO UPDATE SET
                text = excluded.text,
                text_hash = excluded.text_hash,
                source_metadata = excluded.source_metadata,
                updated_at = excluded.updated_at
            """,
            rows,
        )
        self.conn.commit()

    def upsert_analysis_result(self, run_id, input_dir, result, *, status="completed", error_message=None):
        now = utc_now_iso()
        analyzed_at = result.get("analyzed_at") or now
        raw_match = result.get("match")
        match_value = None if raw_match is None else (1 if raw_match else 0)
        self.conn.execute(
            """
            INSERT INTO analysis_results (
                run_id, input_dir, file, page, match, confidence, reasoning, form700_officials,
                form700_entities, responsible_party, responsible_party_type, responsible_party_role,
                responsibility_source, responsibility_entity, accountability_candidates,
                keywords_matched, analysis_provider, analysis_model, analysis_prompt_version,
                token_usage, status, error_message, analyzed_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, file, page) DO UPDATE SET
                input_dir = excluded.input_dir,
                match = excluded.match,
                confidence = excluded.confidence,
                reasoning = excluded.reasoning,
                form700_officials = excluded.form700_officials,
                form700_entities = excluded.form700_entities,
                responsible_party = excluded.responsible_party,
                responsible_party_type = excluded.responsible_party_type,
                responsible_party_role = excluded.responsible_party_role,
                responsibility_source = excluded.responsibility_source,
                responsibility_entity = excluded.responsibility_entity,
                accountability_candidates = excluded.accountability_candidates,
                keywords_matched = excluded.keywords_matched,
                analysis_provider = excluded.analysis_provider,
                analysis_model = excluded.analysis_model,
                analysis_prompt_version = excluded.analysis_prompt_version,
                token_usage = excluded.token_usage,
                status = excluded.status,
                error_message = excluded.error_message,
                analyzed_at = excluded.analyzed_at,
                updated_at = excluded.updated_at
            """,
            (
                run_id,
                str(input_dir),
                result.get("file") or "",
                page_key(result.get("page")),
                match_value,
                result.get("confidence") or "",
                result.get("reasoning") or "",
                result.get("form700_officials") or "",
                result.get("form700_entities") or "",
                result.get("responsible_party") or "",
                result.get("responsible_party_type") or "unknown",
                result.get("responsible_party_role") or "",
                result.get("responsibility_source") or "",
                result.get("responsibility_entity") or "",
                _json_dumps(result.get("accountability_candidates") or []),
                _json_dumps(result.get("keywords_matched") or []),
                result.get("analysis_provider") or "",
                result.get("analysis_model") or "",
                result.get("analysis_prompt_version") or "",
                _json_dumps(result.get("token_usage") or {}),
                status,
                error_message,
                analyzed_at,
                now,
            ),
        )
        self.conn.commit()

    def upsert_failed_result(self, run_id, input_dir, file_name, page, *, token_usage=None, error_message=None):
        result = {
            "file": file_name,
            "page": page,
            "match": None,
            "confidence": "",
            "reasoning": "",
            "token_usage": token_usage or {},
        }
        self.upsert_analysis_result(
            run_id,
            input_dir,
            result,
            status="failed",
            error_message=error_message or "",
        )

    def latest_resume_state(
        self,
        *,
        input_year,
        input_dir,
        input_source,
        provider,
        model,
        prompt_version,
        exclude_run_id=None,
    ):
        params = [
            str(input_dir),
            input_source,
            provider,
            model,
            prompt_version,
        ]
        year_clause = ""
        if input_source == "year":
            year_clause = "AND input_year = ?"
            params.insert(2, str(input_year or ""))
        exclude_clause = ""
        if exclude_run_id:
            exclude_clause = "AND run_id != ?"
            params.append(exclude_run_id)
        rows = self.conn.execute(
            f"""
            SELECT *
            FROM runs
            WHERE input_dir = ?
              AND input_source = ?
              {year_clause}
              AND provider = ?
              AND model = ?
              AND prompt_version = ?
              {exclude_clause}
            ORDER BY datetime(started_at) DESC, started_at DESC
            """,
            params,
        ).fetchall()
        for row in rows:
            resume_state = self._resume_state_for_run(row)
            if resume_state is not None:
                return resume_state
        return None

    def list_runs(self, limit=10):
        rows = self.conn.execute(
            """
            SELECT *
            FROM runs
            ORDER BY datetime(started_at) DESC, started_at DESC
            LIMIT ?
            """,
            (int(limit or 10),),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id):
        row = self.conn.execute(
            """
            SELECT *
            FROM runs
            WHERE run_id = ?
            """,
            (str(run_id),),
        ).fetchone()
        return dict(row) if row else None

    def failed_pages_for_run(self, run_id):
        rows = self.conn.execute(
            """
            SELECT file, page, error_message, analyzed_at, token_usage
            FROM analysis_results
            WHERE run_id = ?
              AND status = 'failed'
            ORDER BY file, page
            """,
            (str(run_id),),
        ).fetchall()
        return [
            {
                "file": row["file"],
                "page": parse_page_key(row["page"]),
                "error_message": row["error_message"] or "",
                "analyzed_at": row["analyzed_at"] or "",
                "token_usage": _token_usage(row["token_usage"]),
            }
            for row in rows
        ]

    def _resume_state_for_run(self, row):
        result_rows = self.conn.execute(
            """
            SELECT *
            FROM analysis_results
            WHERE run_id = ?
            ORDER BY file, page
            """,
            (row["run_id"],),
        ).fetchall()
        if not result_rows:
            return None

        completed = []
        processed = set()
        failed = set()
        failed_details = []
        token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        for result_row in result_rows:
            usage = _token_usage(result_row["token_usage"])
            token_usage["input_tokens"] += usage["input_tokens"]
            token_usage["output_tokens"] += usage["output_tokens"]
            token_usage["total_tokens"] += usage["total_tokens"]
            key = (result_row["file"], parse_page_key(result_row["page"]))
            if result_row["status"] == "completed":
                completed.append(self._row_to_result(result_row))
                processed.add(key)
            elif result_row["status"] == "failed":
                failed.add(key)
                failed_details.append(
                    {
                        "file": result_row["file"],
                        "page": parse_page_key(result_row["page"]),
                        "error_message": result_row["error_message"] or "",
                        "analyzed_at": result_row["analyzed_at"] or "",
                        "token_usage": usage,
                    }
                )

        if not processed and not failed:
            return None

        return {
            "run": dict(row),
            "results": completed,
            "processed": processed,
            "failed": failed,
            "failed_details": failed_details,
            "token_usage": token_usage,
        }

    def _row_to_result(self, row):
        return {
            "match": _coerce_bool(row["match"]),
            "reasoning": row["reasoning"] or "",
            "confidence": row["confidence"] or "",
            "file": row["file"],
            "page": parse_page_key(row["page"]),
            "form700_officials": row["form700_officials"] or "",
            "form700_entities": row["form700_entities"] or "",
            "responsible_party": row["responsible_party"] or "",
            "responsible_party_type": row["responsible_party_type"] or "unknown",
            "responsible_party_role": row["responsible_party_role"] or "",
            "responsibility_source": row["responsibility_source"] or "",
            "responsibility_entity": row["responsibility_entity"] or "",
            "accountability_candidates": _json_loads(row["accountability_candidates"], []),
            "keywords_matched": _json_loads(row["keywords_matched"], []),
            "analysis_provider": row["analysis_provider"] or "",
            "analysis_model": row["analysis_model"] or "",
            "analysis_prompt_version": row["analysis_prompt_version"] or "",
            "token_usage": _token_usage(row["token_usage"]),
            "analyzed_at": row["analyzed_at"] or utc_now_iso(),
        }
