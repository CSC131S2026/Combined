import sys
import unittest
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from core.filter_engine import FilterEngine


class FilterEngineContractTests(unittest.TestCase):
    def test_non_match_attribution_candidates_do_not_pollute_filter_labels(self):
        engine = FilterEngine()
        record = {
            "conflict": {"match": False, "confidence": "high", "reasoning": "No conflict."},
            "form700": {"officials": [], "entities": []},
            "attribution": {
                "primary_party": {"name": "County Risk Manager", "type": "role"},
                "candidates": [{"name": "Acme LLC", "type": "entity"}],
            },
        }

        self.assertEqual(engine.extract_official_names(record), [])
        self.assertEqual(engine.extract_entity_names(record), [])

    def test_match_attribution_candidates_remain_filterable(self):
        engine = FilterEngine()
        record = {
            "conflict": {"match": True, "confidence": "high", "reasoning": "Potential conflict."},
            "form700": {"officials": [], "entities": []},
            "attribution": {
                "primary_party": {"name": "County Risk Manager", "type": "role"},
                "candidates": [{"name": "Acme LLC", "type": "entity"}],
            },
        }

        self.assertEqual(engine.extract_official_names(record), ["County Risk Manager"])
        self.assertEqual(engine.extract_entity_names(record), ["Acme LLC"])


if __name__ == "__main__":
    unittest.main()
