import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.web_scrapers import county_registry


class CountyRegistryContractTests(unittest.TestCase):
    def test_sacramento_county_is_available(self):
        counties = county_registry.supported_counties()

        self.assertEqual(counties[0].key, "sacramento")
        self.assertEqual(counties[0].label, "Sacramento County")
        self.assertIn("sonoma", [county.key for county in counties])

    def test_output_dir_honors_scraper_output_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"CONFLICT_SCRAPER_OUTPUT_DIR": tmp}):
                output_dir = county_registry.output_dir_for_county("Sacramento County", 2024)

        self.assertEqual(output_dir, Path(tmp).resolve() / "2024")

    def test_sonoma_output_dir_is_county_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"CONFLICT_SCRAPER_OUTPUT_DIR": tmp}):
                output_dir = county_registry.output_dir_for_county("Sonoma County", 2024)

        self.assertEqual(output_dir, Path(tmp).resolve() / "sonoma" / "2024")

    def test_scrape_county_dispatches_to_registered_scraper(self):
        calls = []
        fake_module = SimpleNamespace(scrape=lambda year: calls.append(year))

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"CONFLICT_SCRAPER_OUTPUT_DIR": tmp}):
                with patch.object(county_registry.importlib, "import_module", return_value=fake_module):
                    output_dir = county_registry.scrape_county("sacramento", "2025")

        self.assertEqual(calls, ["2025"])
        self.assertEqual(output_dir, Path(tmp).resolve() / "2025")

    def test_scrape_county_uses_county_scoped_output_root(self):
        seen_output_roots = []

        def fake_scrape(year):
            seen_output_roots.append(os.environ.get("CONFLICT_SCRAPER_OUTPUT_DIR"))

        fake_module = SimpleNamespace(scrape=fake_scrape)

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"CONFLICT_SCRAPER_OUTPUT_DIR": tmp}):
                with patch.object(county_registry.importlib, "import_module", return_value=fake_module):
                    output_dir = county_registry.scrape_county("sonoma", "2025")

        self.assertEqual(seen_output_roots, [str(Path(tmp).resolve() / "sonoma")])
        self.assertEqual(output_dir, Path(tmp).resolve() / "sonoma" / "2025")

    def test_unknown_county_raises_clear_error(self):
        with self.assertRaisesRegex(ValueError, "Unsupported county scraper"):
            county_registry.get_county_scraper("narnia")


if __name__ == "__main__":
    unittest.main()
