import sys
import unittest
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = FRONTEND_DIR.parent
for path in (FRONTEND_DIR, ROOT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core.pipeline_runner import PipelineRunner, output_paths_for_selection


class PipelineRunnerContractTests(unittest.TestCase):
    def test_supported_counties_includes_sacramento(self):
        counties = PipelineRunner.supported_counties()

        self.assertIn(("sacramento", "Sacramento County"), counties)
        self.assertIn(("sonoma", "Sonoma County"), counties)

    def test_output_paths_use_selected_year(self):
        workdir = Path("/tmp/conflict-checker")

        paths = output_paths_for_selection(workdir, year="2020", input_dir=None)

        self.assertEqual(paths["CONFLICT_JSON_PATH"], str(workdir / "conflict_flags_openai_2020.json"))
        self.assertEqual(paths["CONFLICT_CSV_PATH"], str(workdir / "conflict_flags_openai_2020.csv"))

    def test_output_paths_use_input_dir_year_and_county(self):
        workdir = Path("/tmp/conflict-checker")

        paths = output_paths_for_selection(
            workdir,
            year="2019",
            input_dir="/tmp/output_data/sonoma/2020",
        )

        self.assertEqual(
            paths["CONFLICT_JSON_PATH"],
            str(workdir / "conflict_flags_openai_sonoma_2020.json"),
        )


if __name__ == "__main__":
    unittest.main()
