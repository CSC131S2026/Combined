import csv
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.llmFlagging.estimate_api_cost import (
    CorpusEstimate,
    FileEstimate,
    TokenCounter,
    build_markdown_report,
    cost_for_tokens,
    estimate_corpus,
    estimate_file,
    has_conflict_keywords,
    write_csv_report,
)


class ApiCostEstimatorContractTests(unittest.TestCase):
    def test_keyword_filter_matches_high_signal_or_two_low_signals(self):
        self.assertTrue(has_conflict_keywords("The official must recuse from this item."))
        self.assertTrue(has_conflict_keywords("Approve contract with vendor."))
        self.assertFalse(has_conflict_keywords("Approve consent calendar item."))

    def test_cost_for_tokens_uses_per_million_rates(self):
        self.assertEqual(cost_for_tokens(2_000_000, 1_000_000, 0.75, 4.50), 6.0)

    def test_text_file_estimate_counts_only_keyword_pages_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pages.txt"
            path.write_text(
                "Approve contract with vendor for services."
                + chr(12)
                + "Routine ceremonial resolution only.",
                encoding="utf-8",
            )
            counter = TokenCounter("test-model", chars_per_token=4)

            estimate = estimate_file(
                path,
                counter,
                prompt_overhead_tokens=10,
                expected_output_tokens=20,
                max_output_tokens=30,
                second_pass_rate=1.0,
            )

        self.assertEqual(estimate.pages, 2)
        self.assertEqual(estimate.text_pages, 2)
        self.assertEqual(estimate.keyword_pages, 1)
        self.assertGreater(estimate.expected_input_tokens, 10)
        self.assertEqual(estimate.expected_requests, 1.0)
        self.assertEqual(estimate.upper_output_tokens, 30)

    def test_corpus_estimate_includes_text_files_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp)
            (input_dir / "agenda.txt").write_text("Conflict of interest disclosure.", encoding="utf-8")

            estimate = estimate_corpus(
                input_dir,
                include_text=True,
                prompt_overhead_tokens=10,
                expected_output_tokens=20,
                max_output_tokens=30,
            )

        self.assertEqual(len(estimate.files), 1)
        self.assertEqual(estimate.total("pages"), 1)
        self.assertEqual(estimate.total("keyword_pages"), 1)

    def test_markdown_and_csv_reports_show_cost_and_inventory(self):
        estimate = CorpusEstimate(
            files=[
                FileEstimate(
                    path="agenda.txt",
                    bytes=100,
                    pages=1,
                    text_pages=1,
                    keyword_pages=1,
                    total_text_chars=40,
                    total_text_tokens=10,
                    expected_input_tokens=100,
                    expected_output_tokens=20,
                    upper_input_tokens=120,
                    upper_output_tokens=30,
                    expected_requests=1,
                    upper_requests=1,
                )
            ],
            model="gpt-test",
            token_method="test",
            input_price_per_million=1.0,
            output_price_per_million=10.0,
            batch_discount=0.5,
            prompt_overhead_tokens=10,
            expected_output_tokens_per_request=20,
            max_output_tokens_per_request=30,
            second_pass_rate=0.75,
            chunk_chars=800,
            max_chars_per_page=1600,
            keyword_filter_enabled=True,
        )

        markdown = build_markdown_report(estimate, Path("/tmp/input"))
        self.assertIn("OpenAI API Cost Estimate", markdown)
        self.assertIn("gpt-test", markdown)
        self.assertIn("Expected", markdown)

        with tempfile.TemporaryDirectory() as tmp:
            output_csv = Path(tmp) / "report.csv"
            write_csv_report(estimate, output_csv)
            with output_csv.open(newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))

        self.assertEqual(row["path"], "agenda.txt")
        self.assertEqual(row["keyword_pages"], "1")


if __name__ == "__main__":
    unittest.main()
