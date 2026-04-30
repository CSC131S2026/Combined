from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from datetime import date
from urllib.parse import urlparse, unquote
import pandas as pd
import os
import shutil

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output_data')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def _resolve_output_dir(year=None):
    base = DOWNLOAD_DIR
    if year is None:
        return base
    bucket = str(year) if str(year).strip() else "unknown"
    target = os.path.join(base, bucket)
    os.makedirs(target, exist_ok=True)
    return target


def _expected_filename_from_url(url):
    if not url:
        return None
    path = urlparse(url).path
    name = unquote(os.path.basename(path))
    return name or None


def cleanup_stale_partials(download_dir=None):
    targets = []
    if download_dir is None:
        targets.append(DOWNLOAD_DIR)
        if os.path.isdir(DOWNLOAD_DIR):
            for entry in os.listdir(DOWNLOAD_DIR):
                full = os.path.join(DOWNLOAD_DIR, entry)
                if os.path.isdir(full):
                    targets.append(full)
    else:
        targets.append(download_dir)

    removed = 0
    for directory in targets:
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            if name.endswith(".crdownload"):
                try:
                    os.remove(os.path.join(directory, name))
                    removed += 1
                except OSError:
                    pass
    return removed


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


def wait_for_download(timeout=40, before=None, download_dir=DOWNLOAD_DIR):
    before = set(os.listdir(download_dir)) if before is None else set(before)
    end_time = time.time() + timeout
    while time.time() < end_time:
        current = set(os.listdir(download_dir))
        new_files = current - before
        new_partial_files = [name for name in new_files if name.endswith(".crdownload")]
        new_completed_files = [name for name in new_files if not name.endswith(".crdownload")]
        if new_completed_files and not new_partial_files:
            return True
        time.sleep(1)
    print("Warning: Download may not have completed within timeout")
    return False


def save_files(file, file_type="pdf", driver=None, year=None):
    if file_type == "pdf":
        if not driver:
            print("error!!: driver is required for PDF downloads")
            return None

        target_dir = _resolve_output_dir(year)
        expected_name = _expected_filename_from_url(file)
        if expected_name:
            existing = os.path.join(target_dir, expected_name)
            if os.path.exists(existing):
                print(f"Skipping {expected_name}: already present in {target_dir}")
                return existing

        # Chrome's download dir is fixed per-session, so download into DOWNLOAD_DIR
        # then relocate to the year-scoped bucket once the file is complete.
        before = set(os.listdir(DOWNLOAD_DIR))
        original_window = driver.current_window_handle
        download_window = None

        try:
            driver.execute_script("window.open(arguments[0], '_blank');", file)
            time.sleep(2)
            new_windows = [handle for handle in driver.window_handles if handle != original_window]
            download_window = new_windows[-1] if new_windows else None
            if download_window:
                driver.switch_to.window(download_window)
            time.sleep(1)

            completed = wait_for_download(before=before, download_dir=DOWNLOAD_DIR)
        finally:
            try:
                if download_window and download_window in driver.window_handles:
                    driver.switch_to.window(download_window)
                    driver.close()
            finally:
                if original_window in driver.window_handles:
                    driver.switch_to.window(original_window)

        if not completed:
            print(f"Warning: Download timed out for {file}")
            return None

        after = set(os.listdir(DOWNLOAD_DIR))
        new_files = [name for name in after - before if not name.endswith(".crdownload")]
        if new_files:
            downloaded = max(
                new_files,
                key=lambda name: os.path.getmtime(os.path.join(DOWNLOAD_DIR, name)),
            )
            source_path = os.path.join(DOWNLOAD_DIR, downloaded)
            if target_dir != DOWNLOAD_DIR:
                final_path = os.path.join(target_dir, downloaded)
                if os.path.exists(final_path):
                    try:
                        os.remove(source_path)
                    except OSError:
                        pass
                    print(f"PDF already existed at {final_path}; removed duplicate from staging")
                    return final_path
                shutil.move(source_path, final_path)
                print(f"PDF saved to {final_path}")
                return final_path
            print(f"PDF saved to {source_path}")
            return source_path
        print(f"Warning: No new file detected for {file}")
        return None

    elif file_type == "csv":
        target_dir = _resolve_output_dir(year)
        df = pd.DataFrame(file)
        filepath = os.path.join(target_dir, f"{date.today().isoformat()}_Agenda.csv")
        df.to_csv(filepath, index=False)
        print(f"CSV saved to {filepath}")
        return filepath

    elif file_type == "xlsx":
        target_dir = _resolve_output_dir(year)
        df = pd.DataFrame(file)
        filepath = os.path.join(target_dir, f"{date.today().isoformat()}_Agenda.xlsx")
        df.to_excel(filepath, index=False)
        print(f"Excel saved to {filepath}")
        return filepath
