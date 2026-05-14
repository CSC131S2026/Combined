import sys
import unittest
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = FRONTEND_DIR.parent
for path in (FRONTEND_DIR, ROOT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core.pipeline_runner import PipelineRunner


class PipelineRunnerContractTests(unittest.TestCase):
    def test_supported_counties_includes_sacramento(self):
        counties = PipelineRunner.supported_counties()

        self.assertIn(("sacramento", "Sacramento County"), counties)
        self.assertIn(("sonoma", "Sonoma County"), counties)


if __name__ == "__main__":
    unittest.main()
