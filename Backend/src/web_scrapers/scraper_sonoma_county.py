try:
    from src.web_scrapers.useful_functions import (
        cleanup_stale_partials,
        get_chrome_driver,
        save_files,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"src", "src.web_scrapers", "src.web_scrapers.useful_functions"}:
        raise
    try:
        from .useful_functions import cleanup_stale_partials, get_chrome_driver, save_files
    except ImportError as rel_exc:  # pragma: no cover - keeps direct script execution working.
        if "attempted relative import" not in str(rel_exc):
            raise
        from useful_functions import cleanup_stale_partials, get_chrome_driver, save_files

from urllib.parse import urljoin

from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Column
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = (
    "https://sonoma-county.legistar.com/DepartmentDetail.aspx?"
    "ID=38109&GUID=91355EAA-E9D2-4248-A798-D64E98D90389&Mode=MainBody"
)
DEFAULT_SCRAPE_YEAR = 2021
YEAR_MENU_SELECTOR = "a.rmLink.rmRootLink.time-menu-item"
YEAR_OPTION_SELECTOR = ".rmItem a"
DOCUMENT_LINK_TEXTS = ("Agenda", "Minutes")

text_col = TextColumn("{task.description}", table_column=Column(ratio=1), style="blink white")
bar_col = BarColumn(bar_width=None, table_column=Column(ratio=2), style="blink bold blue")
progress = Progress(text_col, bar_col, expand=True)


def _ordered_unique(values):
    seen = set()
    unique_values = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _element_text(element):
    text = element.text.strip()
    if text:
        return text
    return (element.get_attribute("textContent") or "").strip()


def _select_year(driver, year=DEFAULT_SCRAPE_YEAR):
    target_year = str(year).strip() or str(DEFAULT_SCRAPE_YEAR)
    menu = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, YEAR_MENU_SELECTOR))
    )
    menu.click()

    def find_option(current_driver):
        for option in current_driver.find_elements(By.CSS_SELECTOR, YEAR_OPTION_SELECTOR):
            if _element_text(option) == target_year:
                return option
        return False

    option = WebDriverWait(driver, 20).until(find_option)
    option.click()
    try:
        WebDriverWait(driver, 5).until(EC.staleness_of(option))
    except TimeoutException:
        pass
    WebDriverWait(driver, 20).until(
        lambda current_driver: _document_hrefs(current_driver) or False
    )


def _document_hrefs(driver):
    hrefs = []
    for link_text in DOCUMENT_LINK_TEXTS:
        for link in driver.find_elements(By.PARTIAL_LINK_TEXT, link_text):
            text = _element_text(link)
            if not any(label.lower() in text.lower() for label in DOCUMENT_LINK_TEXTS):
                continue
            href = link.get_attribute("href")
            if href:
                hrefs.append(urljoin(BASE_URL, href))
    return _ordered_unique(hrefs)


def scrape(year=DEFAULT_SCRAPE_YEAR):
    cleanup_stale_partials()
    driver = get_chrome_driver()
    try:
        driver.get(BASE_URL)
        _select_year(driver, year)

        hrefs = _document_hrefs(driver)
        if not hrefs:
            print(f"No Sonoma County agenda/minutes links found for {year}.")
            return

        print(f"Found {len(hrefs)} unique Sonoma County document links")

        with progress:
            for href in progress.track(hrefs, description="Processing Sonoma packets.."):
                try:
                    save_files(href, file_type="pdf", driver=driver, year=year)
                except WebDriverException as e:
                    print(f"Failed to download {href}: {e}")
    except TimeoutException:
        print(f"Timed out loading Sonoma County documents for {year}.")
    finally:
        driver.quit()


if __name__ == "__main__":
    scrape()
