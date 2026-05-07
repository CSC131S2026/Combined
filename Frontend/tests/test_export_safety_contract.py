import csv
import io
import sys
import unittest
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = FRONTEND_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from shared.export_safety import neutralize_csv_row, neutralize_spreadsheet_formula


class FrontendExportSafetyContractTests(unittest.TestCase):
    def test_formula_like_text_is_neutralized_for_csv_rows(self):
        dangerous_values = [
            "=HYPERLINK(\"https://example.test\")",
            "+SUM(1,1)",
            "-2+3",
            "@cmd",
            "\t=cmd",
            "\r=cmd",
            "\n=cmd",
            "  =cmd",
        ]

        for value in dangerous_values:
            with self.subTest(value=value):
                self.assertEqual(neutralize_spreadsheet_formula(value), "'" + value)

    def test_csv_row_copy_preserves_safe_and_non_string_values(self):
        row = {
            "reasoning": "=cmd",
            "safe": "plain text",
            "count": -3,
            "empty": "",
            "none": None,
        }

        neutralized = neutralize_csv_row(row)

        self.assertEqual(neutralized["reasoning"], "'=cmd")
        self.assertEqual(neutralized["safe"], "plain text")
        self.assertEqual(neutralized["count"], -3)
        self.assertEqual(neutralized["empty"], "")
        self.assertIsNone(neutralized["none"])
        self.assertEqual(row["reasoning"], "=cmd")

    def test_dict_writer_emits_neutralized_formula_text(self):
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["reasoning"])
        writer.writeheader()
        writer.writerow(neutralize_csv_row({"reasoning": "=cmd"}))

        self.assertIn("'=cmd", output.getvalue())


if __name__ == "__main__":
    unittest.main()
