import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.web_scrapers import scraper_sacramento_county as scraper


class FakeElement:
    def __init__(self, text="", attrs=None, children=None):
        self.text = text
        self._attrs = attrs or {}
        self._children = children or {}

    def get_attribute(self, name):
        return self._attrs.get(name)

    def find_elements(self, by, selector):
        return self._children.get(selector, [])


class FakeDriver:
    def __init__(self, rows):
        self._rows = rows

    def find_elements(self, by, selector):
        if selector == "tr.meeting-row":
            return self._rows
        return []


class SacramentoScraperContractTests(unittest.TestCase):
    def test_default_scrape_year_is_2019(self):
        self.assertEqual(scraper.DEFAULT_SCRAPE_YEAR, 2019)
        self.assertEqual(scraper.scrape.__defaults__, (2019,))

    def test_build_meeting_url_uses_filtered_recent_search_by_default(self):
        url = scraper.build_meeting_url()
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        self.assertEqual(parsed.path, "/OnBaseAgendaOnline/Meetings/Search")
        self.assertEqual(params["dropid"], [scraper.RECENT_UPCOMING_DATE_RANGE_ID])
        self.assertEqual(params["mtids"], [scraper.BOARD_OF_SUPERVISORS_MEETING_TYPE_ID])

    def test_build_meeting_url_encodes_board_search_for_year(self):
        url = scraper.build_meeting_url(2021)
        parsed = urlparse(url)

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "agendanet.saccounty.gov")
        self.assertEqual(parsed.path, "/OnBaseAgendaOnline/Meetings/Search")

        params = parse_qs(parsed.query)
        self.assertEqual(params["dropid"], [scraper.CUSTOM_DATE_RANGE_ID])
        self.assertEqual(params["mtids"], [scraper.BOARD_OF_SUPERVISORS_MEETING_TYPE_ID])
        self.assertEqual(params["dropsv"], ["1/1/2021 00:00:00"])
        self.assertEqual(params["dropev"], ["1/1/2022 00:00:00"])

    def test_build_meeting_url_encodes_board_search_for_2019(self):
        url = scraper.build_meeting_url(scraper.DEFAULT_SCRAPE_YEAR)
        params = parse_qs(urlparse(url).query)

        self.assertEqual(params["dropid"], [scraper.CUSTOM_DATE_RANGE_ID])
        self.assertEqual(params["mtids"], [scraper.BOARD_OF_SUPERVISORS_MEETING_TYPE_ID])
        self.assertEqual(params["dropsv"], ["1/1/2019 00:00:00"])
        self.assertEqual(params["dropev"], ["1/1/2020 00:00:00"])

    def test_sacramento_renav_defaults_to_2019_search(self):
        class FakeNavDriver:
            def __init__(self):
                self.urls = []
                self.script_args = None

            def get(self, url):
                self.urls.append(url)

            def find_element(self, by, selector):
                return object()

            def execute_script(self, script, *args):
                self.script_args = args

        driver = FakeNavDriver()
        scraper.sacramento_reNav(driver, scraper.DEFAULT_SCRAPE_YEAR)

        self.assertEqual(driver.urls, [scraper.SEARCH_URL])
        self.assertEqual(
            driver.script_args,
            (
                scraper.BOARD_OF_SUPERVISORS_MEETING_TYPE_ID,
                scraper.CUSTOM_DATE_RANGE_ID,
                "1/1/2019",
                "1/1/2020",
            ),
        )

    def test_agenda_packet_hrefs_filters_to_board_rows_and_dedupes(self):
        board_link = FakeElement(attrs={"href": "/OnBaseAgendaOnline/Documents/Downloadfile/board.pdf"})
        duplicate_board_link = FakeElement(attrs={"href": "/OnBaseAgendaOnline/Documents/Downloadfile/board.pdf"})
        other_link = FakeElement(attrs={"href": "/OnBaseAgendaOnline/Documents/Downloadfile/other.pdf"})

        board_row = FakeElement(children={
            "[data-sortable-type='mtgType']": [
                FakeElement(attrs={"textContent": "  board   of supervisors meeting  "})
            ],
            scraper.AGENDA_PACKET_SELECTOR: [board_link, duplicate_board_link],
        })
        other_row = FakeElement(children={
            "[data-sortable-type='mtgType']": [FakeElement(text="PLANNING COMMISSION")],
            scraper.AGENDA_PACKET_SELECTOR: [other_link],
        })

        hrefs = scraper._agenda_packet_hrefs(FakeDriver([other_row, board_row]))

        self.assertEqual(hrefs, [
            "https://agendanet.saccounty.gov/OnBaseAgendaOnline/Documents/Downloadfile/board.pdf"
        ])


if __name__ == "__main__":
    unittest.main()
