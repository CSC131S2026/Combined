import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.web_scrapers import scraper_sonoma_county as scraper


class FakeElement:
    def __init__(self, text="", attrs=None):
        self.text = text
        self._attrs = attrs or {}

    def get_attribute(self, name):
        return self._attrs.get(name)


class FakeDriver:
    def __init__(self, elements_by_link_text):
        self._elements_by_link_text = elements_by_link_text

    def find_elements(self, by, selector):
        return self._elements_by_link_text.get(selector, [])


class SonomaScraperContractTests(unittest.TestCase):
    def test_default_scrape_year_matches_original_script(self):
        self.assertEqual(scraper.DEFAULT_SCRAPE_YEAR, 2021)
        self.assertEqual(scraper.scrape.__defaults__, (2021,))

    def test_document_hrefs_collects_agenda_and_minutes_links_once(self):
        agenda = FakeElement(
            text="Agenda",
            attrs={"href": "/View.ashx?ID=123&M=A"},
        )
        duplicate_agenda = FakeElement(
            text="Agenda",
            attrs={"href": "/View.ashx?ID=123&M=A"},
        )
        minutes = FakeElement(
            text="Minutes",
            attrs={"href": "https://sonoma-county.legistar.com/View.ashx?ID=456&M=M"},
        )
        missing_href = FakeElement(text="Minutes", attrs={})

        hrefs = scraper._document_hrefs(
            FakeDriver(
                {
                    "Agenda": [agenda, duplicate_agenda],
                    "Minutes": [minutes, missing_href],
                }
            )
        )

        self.assertEqual(
            hrefs,
            [
                "https://sonoma-county.legistar.com/View.ashx?ID=123&M=A",
                "https://sonoma-county.legistar.com/View.ashx?ID=456&M=M",
            ],
        )


if __name__ == "__main__":
    unittest.main()
