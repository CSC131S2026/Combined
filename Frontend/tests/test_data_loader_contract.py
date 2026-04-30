import json
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
