import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.storage.sqlite_store import SQLiteStore


def _sample_result(reasoning="found conflict"):
    return {
        "file": "packet.pdf.txt",
        "page": 1,
        "match": True,
        "confidence": "high",
        "reasoning": reasoning,
        "form700_officials": "Jane Doe",
        "form700_entities": "Acme Contracting",
        "responsible_party": "Jane Doe",
        "responsible_party_type": "person",
        "responsible_party_role": "Supervisor",
        "responsibility_source": "form700_entity",
        "responsibility_entity": "Acme Contracting",
        "accountability_candidates": [
            {
                "name": "Jane Doe",
                "type": "person",
                "role": "Supervisor",
                "entity": "Acme Contracting",
                "source": "form700_entity",
            }
        ],
        "keywords_matched": ["conflict of interest", "vendor"],
        "analysis_provider": "openai",
        "analysis_model": "gpt-5.4-mini",
        "analysis_prompt_version": "test",
        "token_usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
        "analyzed_at": "2026-05-13T00:00:00+00:00",
    }


class SQLiteStoreTests(unittest.TestCase):
    def test_schema_creation_records_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "conflicts.sqlite3"
            store = SQLiteStore(db_path)
            store.close()

            conn = sqlite3.connect(db_path)
            try:
                version = conn.execute(
                    "SELECT value FROM schema_meta WHERE key = 'schema_version'"
                ).fetchone()[0]
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            finally:
                conn.close()

        self.assertEqual(version, "1")
        self.assertTrue({"schema_meta", "runs", "pages", "analysis_results"} <= tables)

    def test_page_and_result_upserts_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "conflicts.sqlite3")
            run_id = store.start_run(
                input_year="2019",
                input_dir="/inputs",
                input_source="year",
                provider="openai",
                model="gpt-5.4-mini",
                prompt_version="test",
                output_stem="flags",
                total_pages_scanned=1,
                total_pages_analyzed=1,
            )
            store.upsert_pages("/inputs", [{"file": "packet.pdf.txt", "page": 1, "text": "first"}])
            store.upsert_pages("/inputs", [{"file": "packet.pdf.txt", "page": 1, "text": "second"}])
            store.upsert_analysis_result(run_id, "/inputs", _sample_result("first result"))
            store.upsert_analysis_result(run_id, "/inputs", _sample_result("updated result"))

            page_count = store.conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            result_rows = store.conn.execute(
                "SELECT reasoning FROM analysis_results WHERE run_id = ?",
                (run_id,),
            ).fetchall()
            stored_text = store.conn.execute("SELECT text FROM pages").fetchone()[0]
            store.close()

        self.assertEqual(page_count, 1)
        self.assertEqual(len(result_rows), 1)
        self.assertEqual(result_rows[0][0], "updated result")
        self.assertEqual(stored_text, "second")

    def test_resume_lookup_returns_processed_failed_and_token_totals(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "conflicts.sqlite3")
            run_id = store.start_run(
                input_year="2019",
                input_dir="/inputs",
                input_source="year",
                provider="openai",
                model="gpt-5.4-mini",
                prompt_version="test",
                output_stem="flags",
            )
            store.upsert_analysis_result(run_id, "/inputs", _sample_result())
            store.upsert_failed_result(
                run_id,
                "/inputs",
                "other.pdf.txt",
                2,
                token_usage={"input_tokens": 10, "output_tokens": 1, "total_tokens": 11},
                error_message="timeout",
            )

            resume = store.latest_resume_state(
                input_year="2019",
                input_dir="/inputs",
                input_source="year",
                provider="openai",
                model="gpt-5.4-mini",
                prompt_version="test",
            )
            store.close()

        self.assertEqual(resume["processed"], {("packet.pdf.txt", 1)})
        self.assertEqual(resume["failed"], {("other.pdf.txt", 2)})
        self.assertEqual(resume["token_usage"], {"input_tokens": 13, "output_tokens": 3, "total_tokens": 16})
        self.assertEqual(resume["results"][0]["reasoning"], "found conflict")

    def test_json_like_fields_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "conflicts.sqlite3")
            run_id = store.start_run(
                input_year="2019",
                input_dir="/inputs",
                input_source="year",
                provider="openai",
                model="gpt-5.4-mini",
                prompt_version="test",
                output_stem="flags",
            )
            store.upsert_analysis_result(run_id, "/inputs", _sample_result())
            resume = store.latest_resume_state(
                input_year="2019",
                input_dir="/inputs",
                input_source="year",
                provider="openai",
                model="gpt-5.4-mini",
                prompt_version="test",
            )
            store.close()

        result = resume["results"][0]
        self.assertEqual(result["accountability_candidates"][0]["name"], "Jane Doe")
        self.assertEqual(result["keywords_matched"], ["conflict of interest", "vendor"])
        self.assertEqual(result["token_usage"], {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5})

    def test_resume_lookup_skips_latest_empty_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "conflicts.sqlite3")
            populated_run = store.start_run(
                input_year="2019",
                input_dir="/inputs",
                input_source="year",
                provider="openai",
                model="gpt-5.4-mini",
                prompt_version="test",
                output_stem="flags",
            )
            empty_run = store.start_run(
                input_year="2019",
                input_dir="/inputs",
                input_source="year",
                provider="openai",
                model="gpt-5.4-mini",
                prompt_version="test",
                output_stem="flags",
            )
            store.conn.execute(
                "UPDATE runs SET started_at = ? WHERE run_id = ?",
                ("2026-05-13T00:00:00+00:00", populated_run),
            )
            store.conn.execute(
                "UPDATE runs SET started_at = ? WHERE run_id = ?",
                ("2026-05-14T00:00:00+00:00", empty_run),
            )
            store.conn.commit()
            store.upsert_analysis_result(populated_run, "/inputs", _sample_result("older result"))

            resume = store.latest_resume_state(
                input_year="2019",
                input_dir="/inputs",
                input_source="year",
                provider="openai",
                model="gpt-5.4-mini",
                prompt_version="test",
            )
            store.close()

        self.assertEqual(resume["run"]["run_id"], populated_run)
        self.assertEqual(resume["results"][0]["reasoning"], "older result")

    def test_custom_input_resume_ignores_input_year(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "conflicts.sqlite3")
            run_id = store.start_run(
                input_year="2019",
                input_dir="/custom-inputs",
                input_source="custom",
                provider="openai",
                model="gpt-5.4-mini",
                prompt_version="test",
                output_stem="flags",
            )
            store.upsert_analysis_result(run_id, "/custom-inputs", _sample_result("custom result"))

            resume = store.latest_resume_state(
                input_year="2024",
                input_dir="/custom-inputs",
                input_source="custom",
                provider="openai",
                model="gpt-5.4-mini",
                prompt_version="test",
            )
            store.close()

        self.assertEqual(resume["run"]["run_id"], run_id)
        self.assertEqual(resume["results"][0]["reasoning"], "custom result")


if __name__ == "__main__":
    unittest.main()
