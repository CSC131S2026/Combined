from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import glob
from datetime import date
import pandas as pd
import os

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output_data')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def get_chrome_driver():
    chrome_options = Options()
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=chrome_options)


def wait_for_download(timeout=40):
    end_time = time.time() + timeout
    while time.time() < end_time:
        time.sleep(1)
        downloading = glob.glob(os.path.join(DOWNLOAD_DIR, "*.crdownload"))
        if not downloading:
            return True
    print("Warning: Download may not have completed within timeout")
    return False


def save_files(file, file_type="pdf", driver=None):
    if file_type == "pdf":
        if not driver:
            print("error!!: driver is required for PDF downloads")
            return None

        before = set(os.listdir(DOWNLOAD_DIR))

        driver.execute_script(f"window.open('{file}', '_blank');")
        time.sleep(2)
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(1)

        completed = wait_for_download()
        driver.close()
        driver.switch_to.window(driver.window_handles[0])

        if not completed:
            print(f"Warning: Download timed out for {file}")
            return None

        after = set(os.listdir(DOWNLOAD_DIR))
        new_files = after - before
        if new_files:
            downloaded = new_files.pop()
            filepath = os.path.join(DOWNLOAD_DIR, downloaded)
            print(f"PDF saved to {filepath}")
            return filepath
        print(f"Warning: No new file detected for {file}")
        return None

    elif file_type == "csv":
        df = pd.DataFrame(file)
        filepath = os.path.join(DOWNLOAD_DIR, f"{date.today().isoformat()}_Agenda.csv")
        df.to_csv(filepath, index=False)
        print(f"CSV saved to {filepath}")
        return filepath

    elif file_type == "xlsx":
        df = pd.DataFrame(file)
        filepath = os.path.join(DOWNLOAD_DIR, f"{date.today().isoformat()}_Agenda.xlsx")
        df.to_excel(filepath, index=False)
        print(f"Excel saved to {filepath}")
        return filepath
