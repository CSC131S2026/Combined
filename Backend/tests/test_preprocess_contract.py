import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.web_scrapers.preprocess import cleanup, read_texts


class PreprocessContractTests(unittest.TestCase):
    def test_read_texts_accepts_injected_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "packet.pdf.txt"
            path.write_text("page one\fpage two", encoding="utf-8")

            pages = read_texts(tmp)

        self.assertEqual(
            pages,
            [
                {"file": "packet.pdf.txt", "page": 1, "text": "page one"},
                {"file": "packet.pdf.txt", "page": 2, "text": "page two"},
            ],
        )

    def test_cleanup_accepts_injected_output_dir_for_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "agenda.csv"
            path.write_text("item,vendor\n1,Acme\n", encoding="utf-8")

            pages = cleanup(tmp)

        self.assertEqual(pages[0]["file"], "agenda.csv")
        self.assertEqual(pages[0]["page"], "CSV")
        self.assertIn("Acme", pages[0]["text"])

    def test_cleanup_skips_pdf_when_text_extract_is_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "packet.pdf"
            txt = Path(tmp) / "packet.pdf.txt"
            pdf.write_bytes(b"not a real pdf")
            txt.write_text("cached page", encoding="utf-8")
            events = []

            pages = cleanup(tmp, progress=events.append)

        self.assertEqual(pages, [{"file": "packet.pdf", "page": 1, "text": "cached page"}])
        self.assertTrue(any("Skipping current text extract" in event for event in events))

    def test_cleanup_closes_pdf_and_reads_each_page_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "packet.pdf"
            pdf.write_bytes(b"pdf bytes")
            page = MagicMock()
            page.get_text.return_value = " page text \n"
            doc = MagicMock()
            doc.__enter__.return_value = [page]

            with patch("src.web_scrapers.preprocess.pymupdf.open", return_value=doc) as open_pdf:
                pages = cleanup(tmp)

            open_pdf.assert_called_once_with(pdf)
            doc.__enter__.assert_called_once_with()
            doc.__exit__.assert_called_once()
            page.get_text.assert_called_once_with()
            self.assertEqual(pages, [{"file": "packet.pdf", "page": 1, "text": "page text"}])
            self.assertEqual((Path(tmp) / "packet.pdf.txt").read_text(encoding="utf-8"), " page text \n")


if __name__ == "__main__":
    unittest.main()
