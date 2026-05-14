import sys
import unittest
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from app import _escape_reportlab_markup, _format_meta_timestamp, _format_token_usage_summary


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

    def test_generated_from_helpers_format_meta(self):
        self.assertEqual(
            _format_meta_timestamp("2026-05-13T12:34:56+00:00"),
            "2026-05-13 12:34:56 UTC",
        )
        self.assertEqual(
            _format_token_usage_summary({"input_tokens": 1000, "output_tokens": 25, "total_tokens": 1025}),
            "1,025 total (1,000 in / 25 out)",
        )


if __name__ == "__main__":
    unittest.main()
