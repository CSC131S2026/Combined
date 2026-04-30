try:
    from src.web_scrapers.useful_functions import get_chrome_driver, save_files, cleanup_stale_partials
except ModuleNotFoundError as exc:
    if exc.name not in {"src", "src.web_scrapers", "src.web_scrapers.useful_functions"}:
        raise
    try:
        from .useful_functions import get_chrome_driver, save_files, cleanup_stale_partials
    except ImportError as rel_exc:  # pragma: no cover - keeps direct script execution working.
        if "attempted relative import" not in str(rel_exc):
            raise
        from useful_functions import get_chrome_driver, save_files, cleanup_stale_partials
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from urllib.parse import urlencode, urljoin
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Column

BASE_URL = "https://agendanet.saccounty.gov"
MEETINGS_URL = f"{BASE_URL}/OnBaseAgendaOnline"
SEARCH_URL = f"{MEETINGS_URL}/Meetings"
BOARD_OF_SUPERVISORS_MEETING_TYPE_ID = "106"
BOARD_OF_SUPERVISORS_MEETING_TYPE = "BOARD OF SUPERVISORS MEETING"
RECENT_UPCOMING_DATE_RANGE_ID = "4"
CUSTOM_DATE_RANGE_ID = "11"
AGENDA_PACKET_SELECTOR = "a[id^='lnkAgendaPacket']"
DEFAULT_SCRAPE_YEAR = 2019

text_col = TextColumn("{task.description}", table_column=Column(ratio=1), style="blink white")
bar_col = BarColumn(bar_width=None, table_column=Column(ratio=2), style="blink bold blue")
progress = Progress(text_col, bar_col, expand=True)


def build_meeting_url(year=None):
    params = {
        "dropid": RECENT_UPCOMING_DATE_RANGE_ID,
        "mtids": BOARD_OF_SUPERVISORS_MEETING_TYPE_ID,
    }
    if year is not None:
        start_date, end_date = _date_range_for_year(year)
        params.update({
            "dropid": CUSTOM_DATE_RANGE_ID,
            "dropsv": f"{start_date} 00:00:00",
            "dropev": f"{end_date} 00:00:00",
        })
    return f"{SEARCH_URL}/Search?{urlencode(params)}"


def _date_range_for_year(year):
    year = int(year)
    return f"1/1/{year}", f"1/1/{year + 1}"


def _ordered_unique(values):
    seen = set()
    unique_values = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _submit_search(driver, year=None):
    driver.get(SEARCH_URL)

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "form[action$='/Meetings']"))
    )

    date_range_id = RECENT_UPCOMING_DATE_RANGE_ID
    start_date = ""
    end_date = ""
    if year is not None:
        date_range_id = CUSTOM_DATE_RANGE_ID
        start_date, end_date = _date_range_for_year(year)

    driver.execute_script(
        """
        const form = document.querySelector("form[action$='/Meetings']");
        const setValue = (name, value) => {
            let field = form.querySelector(`[name="${name}"]`);
            if (field && !["INPUT", "SELECT", "TEXTAREA"].includes(field.tagName)) {
                field.removeAttribute("name");
                field = null;
            }
            if (!field) {
                field = document.createElement("input");
                field.type = "hidden";
                field.name = name;
                form.appendChild(field);
            }
            field.value = value;
        };

        setValue("Keywords", "");
        setValue("MeetingTypeIDs", arguments[0]);
        setValue("DateRangeOptionID", arguments[1]);
        setValue("DateRangeCustomStartDate", arguments[2]);
        setValue("DateRangeCustomEndDate", arguments[3]);
        form.submit();
        """,
        BOARD_OF_SUPERVISORS_MEETING_TYPE_ID,
        date_range_id,
        start_date,
        end_date,
    )


def _element_text(element):
    text = element.text.strip()
    if text:
        return text
    return (element.get_attribute("textContent") or "").strip()


def _is_board_of_supervisors_meeting(meeting_type):
    return " ".join((meeting_type or "").split()).casefold() == BOARD_OF_SUPERVISORS_MEETING_TYPE.casefold()


def _agenda_packet_hrefs(driver):
    links = []
    rows = driver.find_elements(By.CSS_SELECTOR, "tr.meeting-row")
    for row in rows:
        meeting_type_cells = row.find_elements(By.CSS_SELECTOR, "[data-sortable-type='mtgType']")
        if meeting_type_cells:
            meeting_type = _element_text(meeting_type_cells[0])
            if not _is_board_of_supervisors_meeting(meeting_type):
                continue
        links.extend(row.find_elements(By.CSS_SELECTOR, AGENDA_PACKET_SELECTOR))

    if not rows:
        links = driver.find_elements(By.CSS_SELECTOR, AGENDA_PACKET_SELECTOR)

    hrefs = []
    for link in links:
        href = link.get_attribute("href")
        if href:
            hrefs.append(urljoin(MEETINGS_URL, href))
    return _ordered_unique(hrefs)


def _wait_for_agenda_packet_hrefs(driver, timeout=20):
    return WebDriverWait(driver, timeout).until(lambda current_driver: _agenda_packet_hrefs(current_driver) or False)


def sacramento_reNav(driver, year=None):
    if year is None:
        driver.get(build_meeting_url())
    else:
        _submit_search(driver, year)


def scrape(year=DEFAULT_SCRAPE_YEAR):
    cleanup_stale_partials()
    driver = get_chrome_driver()
    try:
        sacramento_reNav(driver, year)

        try:
            hrefs = _wait_for_agenda_packet_hrefs(driver)
        except TimeoutException:
            print("No Board of Supervisors agenda packet links found on page within timeout.")
            return

        print(f"Found {len(hrefs)} unique agenda packet links")

        with progress:
            for href in progress.track(hrefs, description="Processing packets.."):
                try:
                    save_files(href, file_type="pdf", driver=driver, year=year)
                except WebDriverException as e:
                    print(f"Failed to download {href}: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    scrape()
