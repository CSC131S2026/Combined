import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from core.data_loader import DataLoader


class DataLoaderContractTests(unittest.TestCase):
    def _write_json(self, payload):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        with handle:
            json.dump(payload, handle)
        return Path(handle.name)

    def _replace_json(self, path, payload):
        previous_mtime = path.stat().st_mtime_ns
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        bumped_mtime = previous_mtime + 1_000_000_000
        os.utime(path, ns=(bumped_mtime, bumped_mtime))

    def test_load_sync_accepts_legacy_list_payload(self):
        path = self._write_json([{
            "file": "packet.pdf.txt",
            "page": 2,
            "match": True,
            "confidence": "high",
            "reasoning": "Matched a disclosed entity.",
            "form700_officials": "Jane Doe",
            "form700_entities": "Acme LLC",
        }])

        records, meta = DataLoader().load_sync(path)

        self.assertEqual(records[0]["source"], {"file": "packet.pdf.txt", "page": 2})
        self.assertEqual(records[0]["conflict"]["confidence"], "high")
        self.assertEqual(records[0]["form700"]["officials"], ["Jane Doe"])
        self.assertEqual(meta, {})

    def test_load_sync_accepts_frontend_results_payload(self):
        record = {
            "id": "flag-1",
            "source": {"file": "packet.pdf.txt", "page": 1},
            "conflict": {"match": True, "confidence": "high", "reasoning": "reason"},
            "form700": {"officials": [], "entities": []},
        }
        payload = {
            "meta": {"provider": "openai", "model": "gpt-5.4-mini"},
            "summary": {"conflicts_flagged": 1},
            "results": [record],
        }
        path = self._write_json(payload)

        records, meta = DataLoader().load_sync(path)

        self.assertEqual(records, [record])
        self.assertEqual(meta["provider"], "openai")
        self.assertEqual(meta["summary"], {"conflicts_flagged": 1})

    def test_load_sync_reloads_regenerated_json_at_same_path(self):
        path = self._write_json([{
            "file": "packet.pdf.txt",
            "page": 1,
            "match": True,
            "confidence": "low",
            "reasoning": "Initial result.",
        }])
        loader = DataLoader()

        first_records, _ = loader.load_sync(path)
        self._replace_json(path, [{
            "file": "packet.pdf.txt",
            "page": 1,
            "match": True,
            "confidence": "high",
            "reasoning": "Regenerated result.",
        }])
        second_records, _ = loader.load_sync(path)

        self.assertEqual(first_records[0]["conflict"]["confidence"], "low")
        self.assertEqual(second_records[0]["conflict"]["confidence"], "high")
        self.assertEqual(second_records[0]["conflict"]["reasoning"], "Regenerated result.")

    def test_load_sync_bounds_cache_entries(self):
        loader = DataLoader()
        loader.MAX_CACHE_ENTRIES = 2
        paths = [
            self._write_json([{
                "file": f"packet-{index}.pdf.txt",
                "page": index,
                "match": False,
                "confidence": "low",
                "reasoning": "No conflict.",
            }])
            for index in range(3)
        ]

        for path in paths:
            loader.load_sync(path)

        self.assertEqual(len(loader._cache), 2)
        self.assertNotIn(str(paths[0]), loader._cache)

    def test_load_sync_ignores_malformed_meta_without_losing_records(self):
        record = {
            "source": {"file": "packet.pdf.txt", "page": 1},
            "conflict": {"match": True, "confidence": "high", "reasoning": "reason"},
        }
        path = self._write_json({"meta": "not-a-dict", "summary": {"total": 1}, "results": [record]})

        records, meta = DataLoader().load_sync(path)

        self.assertEqual(records, [record])
        self.assertEqual(meta, {"summary": {"total": 1}})

    def test_load_sync_rejects_unknown_dict_shape(self):
        path = self._write_json({"not_results": []})

        with self.assertRaises(ValueError):
            DataLoader().load_sync(path)

    def test_load_sync_rejects_unknown_list_records(self):
        path = self._write_json([{"match": True, "confidence": "high"}])

        with self.assertRaises(ValueError):
            DataLoader().load_sync(path)


if __name__ == "__main__":
    unittest.main()
