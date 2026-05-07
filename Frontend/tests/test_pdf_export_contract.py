import sys
import unittest
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from app import _escape_reportlab_markup


class PdfExportContractTests(unittest.TestCase):
    def test_reportlab_paragraph_text_escapes_markup_control_chars(self):
        text = '<b>Injected</b> & <font color="red">Styled</font>'

        escaped = _escape_reportlab_markup(text)

        self.assertEqual(
            escaped,
            '&lt;b&gt;Injected&lt;/b&gt; &amp; &lt;font color="red"&gt;Styled&lt;/font&gt;',
        )

    def test_reportlab_paragraph_text_accepts_none(self):
        self.assertEqual(_escape_reportlab_markup(None), "")


if __name__ == "__main__":
    unittest.main()
