from src.web_scrapers.useful_functions import get_chrome_driver, save_files
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from urllib.parse import urlencode
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Column

BASE_URL = "https://agendanet.saccounty.gov/OnBaseAgendaOnline/Meetings/Search"

text_col = TextColumn("{task.description}", table_column=Column(ratio=1), style="blink white")
bar_col = BarColumn(bar_width=None, table_column=Column(ratio=2), style="blink bold blue")
progress = Progress(text_col, bar_col, expand=True)


def build_meeting_url(year=None):
    params = {"dropid": "4", "mtids": "106"}
    if year is not None:
        year = int(year)
        params["dropid"] = 11
        params["dropsv"] = f"01/01/{year} 00:00:00"
        params["dropev"] = f"01/01/{year + 1} 00:00:00"
    return f"{BASE_URL}?{urlencode(params)}"


def sacramento_reNav(driver, year=None):
    driver.get(build_meeting_url(year))


def scrape(year=None):
    driver = get_chrome_driver()
    try:
        sacramento_reNav(driver, year)

        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[id*='lnkAgendaPacket']"))
            )
        except TimeoutException:
            print("No agenda packet links found on page within timeout.")
            return

        links = driver.find_elements(By.CSS_SELECTOR, "[id*='lnkAgendaPacket']")
        hrefs = [link.get_attribute("href") for link in links if link.get_attribute("href")]
        print(f"Found {len(hrefs)} agenda packet links")

        with progress:
            for href in progress.track(hrefs, description="Processing packets.."):
                try:
                    save_files(href, file_type="pdf", driver=driver)
                except WebDriverException as e:
                    print(f"Failed to download {href}: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    scrape(2021)
