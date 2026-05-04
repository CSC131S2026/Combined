import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND_DIR / "src" / "llmFlagging" / "higherSpec_openai.py"


class HigherSpecOpenAIInputSelectionTests(unittest.TestCase):
    def _run_without_api_key(self, *args, **env_updates):
        env = os.environ.copy()
        env.pop("OPENAI_API_KEY", None)
        env.pop("CONFLICT_INPUT_YEAR", None)
        env.pop("CONFLICT_INPUT_DIR", None)
        env.update(env_updates)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=BACKEND_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def _run_with_env(self, *args, **env_updates):
        env = os.environ.copy()
        env.pop("CONFLICT_INPUT_YEAR", None)
        env.pop("CONFLICT_INPUT_DIR", None)
        env.update(env_updates)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=BACKEND_DIR,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_defaults_to_2019_input_year_before_openai_work(self):
        result = self._run_without_api_key()

        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("output_data/2019", output)
        self.assertIn("conflict_flags_openai_2019", output)
        self.assertIn("year=", output)
        self.assertIn("2019", output)
        self.assertIn("OPENAI_API_KEY is not set", output)

    def test_cli_input_dir_overrides_year_directory(self):
        result = self._run_without_api_key("--year", "2020", "--input-dir", "custom_inputs")

        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn(str(BACKEND_DIR / "custom_inputs"), output)
        self.assertIn("source=", output)
        self.assertIn("custom", output)
        self.assertNotIn("output_data/2020", output)

    def test_env_year_is_used_when_cli_year_is_absent(self):
        result = self._run_without_api_key(CONFLICT_INPUT_YEAR="2021")

        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("output_data/2021", output)
        self.assertIn("2021", output)

    def test_cli_year_overrides_env_year(self):
        result = self._run_without_api_key("--year", "2022", CONFLICT_INPUT_YEAR="2021")

        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("output_data/2022", output)
        self.assertNotIn("output_data/2021", output)

    def test_empty_custom_input_run_writes_input_metadata_without_openai_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "empty_inputs"
            input_dir.mkdir()
            json_output = tmp_path / "flags.json"

            result = self._run_with_env(
                "--input-dir",
                str(input_dir),
                OPENAI_API_KEY="sk-test",
                CONFLICT_CSV_PATH=str(tmp_path / "flags.csv"),
                CONFLICT_JSON_PATH=str(json_output),
                CONFLICT_CHECKPOINT_PATH=str(tmp_path / "flags_checkpoint.json"),
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(json_output.read_text())
            self.assertEqual(payload["meta"]["input_dir"], str(input_dir.resolve()))
            self.assertEqual(payload["meta"]["input_source"], "custom")
            self.assertEqual(payload["meta"]["total_pages_scanned"], 0)
            self.assertEqual(payload["meta"]["total_results"], 0)

    def test_mismatched_checkpoint_is_ignored_and_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "current_inputs"
            input_dir.mkdir()
            checkpoint = tmp_path / "flags_checkpoint.json"
            checkpoint.write_text(
                json.dumps(
                    {
                        "meta": {
                            "input_year": "2020",
                            "input_dir": str((tmp_path / "other_inputs").resolve()),
                            "input_source": "year",
                        },
                        "results": [
                            {
                                "file": "stale.pdf.txt",
                                "page": 1,
                                "match": True,
                                "confidence": "high",
                                "reasoning": "stale",
                            }
                        ],
                        "processed": [{"file": "stale.pdf.txt", "page": 1}],
                        "failed": [],
                    }
                ),
                encoding="utf-8",
            )
            json_output = tmp_path / "flags.json"

            result = self._run_with_env(
                "--input-dir",
                str(input_dir),
                OPENAI_API_KEY="sk-test",
                CONFLICT_CSV_PATH=str(tmp_path / "flags.csv"),
                CONFLICT_JSON_PATH=str(json_output),
                CONFLICT_CHECKPOINT_PATH=str(checkpoint),
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Ignoring checkpoint with mismatched input metadata", result.stdout + result.stderr)
            payload = json.loads(json_output.read_text())
            self.assertEqual(payload["meta"]["total_results"], 0)
            self.assertTrue(checkpoint.exists())

    def test_matching_checkpoint_is_resumed_and_removed_after_clean_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "current_inputs"
            input_dir.mkdir()
            checkpoint = tmp_path / "flags_checkpoint.json"
            checkpoint.write_text(
                json.dumps(
                    {
                        "meta": {
                            "input_year": "2019",
                            "input_dir": str(input_dir.resolve()),
                            "input_source": "custom",
                            "provider": "openai",
                            "model": "gpt-5.4-mini",
                            "prompt_version": "test",
                        },
                        "results": [
                            {
                                "file": "resumed.pdf.txt",
                                "page": 1,
                                "match": False,
                                "confidence": "low",
                                "reasoning": "resumed cleanly",
                                "form700_officials": "",
                                "form700_entities": "",
                                "analysis_provider": "openai",
                                "analysis_model": "gpt-5.4-mini",
                                "analysis_prompt_version": "test",
                                "token_usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                            }
                        ],
                        "processed": [{"file": "resumed.pdf.txt", "page": 1}],
                        "failed": [],
                    }
                ),
                encoding="utf-8",
            )
            json_output = tmp_path / "flags.json"

            result = self._run_with_env(
                "--input-dir",
                str(input_dir),
                OPENAI_API_KEY="sk-test",
                CONFLICT_CSV_PATH=str(tmp_path / "flags.csv"),
                CONFLICT_JSON_PATH=str(json_output),
                CONFLICT_CHECKPOINT_PATH=str(checkpoint),
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Resuming from checkpoint", result.stdout + result.stderr)
            payload = json.loads(json_output.read_text())
            self.assertEqual(payload["meta"]["total_results"], 1)
            self.assertFalse(checkpoint.exists())


if __name__ == "__main__":
    unittest.main()
