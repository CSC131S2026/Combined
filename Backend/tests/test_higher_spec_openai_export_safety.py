import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND_DIR / "src" / "llmFlagging" / "higherSpec_openai.py"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_higher_spec_module():
    spec = importlib.util.spec_from_file_location("higher_spec_openai_export_probe", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HigherSpecOpenAIExportSafetyTests(unittest.TestCase):
    def test_write_outputs_neutralizes_formula_text_in_csv(self):
        module = _load_higher_spec_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            module._CSV_OUTPUT = tmp_path / "flags.csv"
            module._JSON_OUTPUT = tmp_path / "flags.json"
            module._CHECKPOINT = tmp_path / "flags_checkpoint.json"
            module._CHECKPOINT_WRITES_ENABLED = False
            module.pages = [{"file": "@packet.pdf.txt", "page": 1, "text": ""}]
            module.filtered_pages = list(module.pages)

            state = {
                "results": [
                    {
                        "file": "@packet.pdf.txt",
                        "page": 1,
                        "match": True,
                        "confidence": "high",
                        "reasoning": "=HYPERLINK(\"https://example.test\")",
                        "form700_officials": "",
                        "form700_entities": "",
                        "responsible_party": "",
                        "responsible_party_type": "unknown",
                        "responsible_party_role": "",
                        "responsibility_source": "",
                        "responsibility_entity": "",
                        "accountability_candidates": [],
                        "keywords_matched": ["conflict of interest"],
                        "analysis_provider": "openai",
                        "analysis_model": "gpt-5.4-mini",
                        "analysis_prompt_version": "test",
                        "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                    }
                ],
                "failed": set(),
                "token_usage_totals": module._empty_token_usage(),
            }

            module._write_outputs(state)

            with open(module._CSV_OUTPUT, newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))

        self.assertEqual(row["file"], "'@packet.pdf.txt")
        self.assertEqual(row["reasoning"], "'=HYPERLINK(\"https://example.test\")")


if __name__ == "__main__":
    unittest.main()
