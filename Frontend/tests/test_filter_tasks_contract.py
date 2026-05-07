import sys
import unittest
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from core.filter_engine import FilterEngine
from core.filter_tasks import compute_filter_task, compute_full_aggregates


class SpyFilterEngine(FilterEngine):
    def __init__(self):
        self.aggregate_lengths = []

    def compute_aggregates(self, records: list) -> dict:
        self.aggregate_lengths.append(len(records))
        return super().compute_aggregates(records)


class FilterTasksContractTests(unittest.TestCase):
    def test_full_aggregates_are_computed_for_loaded_records(self):
        records = [
            {"conflict": {"match": True, "confidence": "high"}, "source": {"file": "a.pdf"}},
            {"conflict": {"match": False, "confidence": "low"}, "source": {"file": "b.pdf"}},
        ]

        agg = compute_full_aggregates(records)

        self.assertEqual(agg["total"], 2)
        self.assertEqual(agg["flagged"], 1)
        self.assertEqual(agg["by_confidence"]["high"], 1)
        self.assertEqual(agg["by_confidence"]["low"], 1)

    def test_filter_task_reuses_cached_full_aggregates(self):
        records = [
            {"conflict": {"match": True, "confidence": "high"}, "source": {"file": "a.pdf"}},
            {"conflict": {"match": False, "confidence": "low"}, "source": {"file": "b.pdf"}},
        ]
        cached_all_agg = {"total": 2, "flagged": 1}
        engine = SpyFilterEngine()

        result = compute_filter_task(
            records,
            {"match_only": True},
            cached_all_agg,
            engine,
        )

        self.assertIs(result.all_agg, cached_all_agg)
        self.assertEqual(len(result.filtered_records), 1)
        self.assertEqual(result.filtered_agg["total"], 1)
        self.assertEqual(engine.aggregate_lengths, [1])


if __name__ == "__main__":
    unittest.main()
