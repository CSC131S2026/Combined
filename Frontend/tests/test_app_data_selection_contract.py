import json
import sys
import tempfile
import unittest
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from app import select_preferred_data_name


class AppDataSelectionContractTests(unittest.TestCase):
    def _write_payload(self, name: str, generated_at: str) -> Path:
        directory = Path(tempfile.mkdtemp())
        path = directory / name
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"meta": {"generated_at": generated_at}, "results": []}, handle)
        return path

    def test_prefers_newest_openai_result_over_legacy_default_name(self):
        old_default = self._write_payload(
            "conflict_flags_openai.json",
            "2026-04-22T23:20:03.830210+00:00",
        )
        fresh_year = self._write_payload(
            "conflict_flags_openai_2019.json",
            "2026-05-14T08:39:06.467906+00:00",
        )

        selected = select_preferred_data_name({
            old_default.name: old_default,
            fresh_year.name: fresh_year,
        })

        self.assertEqual(selected, "conflict_flags_openai_2019.json")


if __name__ == "__main__":
    unittest.main()
