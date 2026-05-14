import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.web_scrapers import useful_functions


class FakeSwitchTo:
    def __init__(self, driver):
        self._driver = driver

    def window(self, handle):
        self._driver.current_window_handle = handle


class FakeDriver:
    def __init__(self, download_dir):
        self.download_dir = Path(download_dir)
        self.current_window_handle = "main"
        self.window_handles = ["main"]
        self.switch_to = FakeSwitchTo(self)
        self.scripts = []
        self.closed = []

    def execute_script(self, script, *args):
        self.scripts.append((script, args))
        self.window_handles.append("download")
        (self.download_dir / "packet.pdf").write_text("pdf", encoding="utf-8")

    def close(self):
        handle = self.current_window_handle
        self.closed.append(handle)
        if handle in self.window_handles and handle != "main":
            self.window_handles.remove(handle)
        self.current_window_handle = self.window_handles[0]


class UsefulFunctionsContractTests(unittest.TestCase):
    def test_wait_for_download_ignores_stale_partial_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            download_dir = Path(tmp)
            (download_dir / "stale.pdf.crdownload").write_text("", encoding="utf-8")
            before = set(p.name for p in download_dir.iterdir())
            (download_dir / "packet.pdf").write_text("pdf", encoding="utf-8")

            self.assertTrue(
                useful_functions.wait_for_download(
                    timeout=0.01,
                    before=before,
                    download_dir=str(download_dir),
                )
            )

    def test_save_files_uses_argumentized_script_and_restores_original_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            driver = FakeDriver(tmp)
            original_download_dir = useful_functions.DOWNLOAD_DIR
            useful_functions.DOWNLOAD_DIR = str(tmp)
            try:
                with patch.object(useful_functions.time, "sleep", return_value=None):
                    path = useful_functions.save_files("https://example.test/a'quoted.pdf", driver=driver)
            finally:
                useful_functions.DOWNLOAD_DIR = original_download_dir

        self.assertEqual(Path(path).name, "packet.pdf")
        self.assertEqual(driver.current_window_handle, "main")
        self.assertEqual(driver.closed, ["download"])
        self.assertEqual(driver.scripts[0][0], "window.open(arguments[0], '_blank');")
        self.assertEqual(driver.scripts[0][1], ("https://example.test/a'quoted.pdf",))

    def test_save_files_neutralizes_formula_cells_in_csv_and_xlsx_exports(self):
        rows = [
            {
                "title": "=HYPERLINK(\"https://example.test\")",
                "notes": "  +SUM(1,1)",
                "count": -3,
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            original_download_dir = useful_functions.DOWNLOAD_DIR
            useful_functions.DOWNLOAD_DIR = str(tmp)
            try:
                csv_path = useful_functions.save_files(rows, file_type="csv")
                xlsx_path = useful_functions.save_files(rows, file_type="xlsx")
            finally:
                useful_functions.DOWNLOAD_DIR = original_download_dir

            csv_text = Path(csv_path).read_text(encoding="utf-8")
            xlsx_df = useful_functions.pd.read_excel(xlsx_path, dtype=str)

        self.assertIn("'=HYPERLINK", csv_text)
        self.assertIn("'  +SUM", csv_text)
        self.assertEqual(xlsx_df.loc[0, "title"], "'=HYPERLINK(\"https://example.test\")")
        self.assertEqual(xlsx_df.loc[0, "notes"], "'  +SUM(1,1)")
        self.assertEqual(xlsx_df.loc[0, "count"], "-3")

    def test_scraper_output_env_overrides_default_download_dir(self):
        rows = [{"title": "Packet"}]

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"CONFLICT_SCRAPER_OUTPUT_DIR": tmp}):
                csv_path = useful_functions.save_files(rows, file_type="csv", year=2026)
                csv_path = Path(csv_path).resolve()
                self.assertEqual(csv_path.parent, Path(tmp).resolve() / "2026")
                self.assertTrue(csv_path.exists())

    def test_legistar_view_urls_get_stable_pdf_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            driver = FakeDriver(tmp)
            original_download_dir = useful_functions.DOWNLOAD_DIR
            useful_functions.DOWNLOAD_DIR = str(tmp)
            try:
                with patch.object(useful_functions.time, "sleep", return_value=None):
                    path = useful_functions.save_files(
                        "https://sonoma-county.legistar.com/View.ashx?ID=123&M=A",
                        driver=driver,
                        year=2026,
                    )
            finally:
                useful_functions.DOWNLOAD_DIR = original_download_dir

            saved_path = Path(path).resolve()
            self.assertEqual(saved_path.name, "legistar_agenda_123.pdf")
            self.assertEqual(saved_path.parent, Path(tmp).resolve() / "2026")
            self.assertTrue(saved_path.exists())


if __name__ == "__main__":
    unittest.main()
