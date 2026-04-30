import sys
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
