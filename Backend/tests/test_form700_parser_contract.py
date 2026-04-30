import importlib.util
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SEVEN_PATH = BACKEND_DIR / "src" / "700Parse" / "seven.py"
SAC700_PATH = BACKEND_DIR / "src" / "700Parse" / "sac700.xlsx"

_spec = importlib.util.spec_from_file_location("seven", SEVEN_PATH)
seven = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seven)


class Form700ParserContractTests(unittest.TestCase):
    def test_sacramento_form700_workbook_parses_all_expected_schedules(self):
        filers = seven.normalize_shf(str(SAC700_PATH))
        self.assertGreater(len(filers), 0)

        schedule_counts = {
            schedule: sum(len(filer["schedules"][schedule]) for filer in filers)
            for schedule in ("A-1", "A-2", "B", "C", "D", "E")
        }

        for schedule, count in schedule_counts.items():
            self.assertGreater(count, 0, f"{schedule} should parse rows from sac700.xlsx")

    def test_sacramento_a1_and_e_headers_are_not_repromoted(self):
        filers = seven.normalize_shf(str(SAC700_PATH))

        a1_entities = [
            entry["business_entity"]
            for filer in filers
            for entry in filer["schedules"]["A-1"]
        ]
        e_sources = [
            entry["name_of_source"]
            for filer in filers
            for entry in filer["schedules"]["E"]
        ]

        self.assertIn("Equithotics Inc.", a1_entities)
        self.assertIn("Gordon Thomas Honeywell", e_sources)


if __name__ == "__main__":
    unittest.main()
