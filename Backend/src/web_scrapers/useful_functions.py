from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from datetime import date
import pathlib
from urllib.parse import parse_qs, urlparse, unquote
import pandas as pd
import os
import shutil
import sys

PROJECT_DIR = pathlib.Path(__file__).resolve().parents[3]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from shared.export_safety import neutralize_dataframe_for_spreadsheet

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output_data')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def _download_dir():
    override = os.getenv("CONFLICT_SCRAPER_OUTPUT_DIR", "").strip()
    download_dir = override or DOWNLOAD_DIR
    download_dir = os.path.abspath(os.path.expanduser(download_dir))
    os.makedirs(download_dir, exist_ok=True)
    return download_dir


def _resolve_output_dir(year=None):
    base = _download_dir()
    if year is None:
        return base
    bucket = str(year) if str(year).strip() else "unknown"
    target = os.path.join(base, bucket)
    os.makedirs(target, exist_ok=True)
    return target


def _expected_filename_from_url(url):
    if not url:
        return None
    generated_name = _generated_filename_from_url(url)
    if generated_name:
        return generated_name
    path = urlparse(url).path
    name = unquote(os.path.basename(path))
    return name or None


def _generated_filename_from_url(url):
    parsed = urlparse(url)
    name = unquote(os.path.basename(parsed.path or ""))
    if name.lower() != "view.ashx":
        return None

    query = parse_qs(parsed.query)
    doc_id = (query.get("ID") or [""])[0].strip()
    if not doc_id:
        return None
    mode = (query.get("M") or [""])[0].strip().upper()
    label = {
        "A": "agenda",
        "M": "minutes",
        "P": "packet",
    }.get(mode, "document")
    return f"legistar_{label}_{doc_id}.pdf"


def cleanup_stale_partials(download_dir=None):
    targets = []
    if download_dir is None:
        base_dir = _download_dir()
        targets.append(base_dir)
        if os.path.isdir(base_dir):
            for entry in os.listdir(base_dir):
                full = os.path.join(base_dir, entry)
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
    download_dir = _download_dir()
    chrome_options = Options()
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(options=chrome_options)


def wait_for_download(timeout=40, before=None, download_dir=None):
    download_dir = download_dir or _download_dir()
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
        staging_dir = _download_dir()
        expected_name = _expected_filename_from_url(file)
        if expected_name:
            existing = os.path.join(target_dir, expected_name)
            if os.path.exists(existing):
                print(f"Skipping {expected_name}: already present in {target_dir}")
                return existing

        # Chrome's download dir is fixed per-session, so download into the
        # staging folder then relocate to the year-scoped bucket once complete.
        before = set(os.listdir(staging_dir))
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

            completed = wait_for_download(before=before, download_dir=staging_dir)
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

        after = set(os.listdir(staging_dir))
        new_files = [name for name in after - before if not name.endswith(".crdownload")]
        if new_files:
            downloaded = max(
                new_files,
                key=lambda name: os.path.getmtime(os.path.join(staging_dir, name)),
            )
            source_path = os.path.join(staging_dir, downloaded)
            final_name = _generated_filename_from_url(file) or downloaded
            final_path = os.path.join(target_dir, final_name)
            if os.path.abspath(source_path) != os.path.abspath(final_path):
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
        df = neutralize_dataframe_for_spreadsheet(pd.DataFrame(file))
        filepath = os.path.join(target_dir, f"{date.today().isoformat()}_Agenda.csv")
        df.to_csv(filepath, index=False)
        print(f"CSV saved to {filepath}")
        return filepath

    elif file_type == "xlsx":
        target_dir = _resolve_output_dir(year)
        df = neutralize_dataframe_for_spreadsheet(pd.DataFrame(file))
        filepath = os.path.join(target_dir, f"{date.today().isoformat()}_Agenda.xlsx")
        df.to_excel(filepath, index=False)
        print(f"Excel saved to {filepath}")
        return filepath
