# Backend

Scraping, parsing, and LLM-flagging pipeline. See the [root README](../README.md) for project overview, install, and full run instructions.

## Layout

- `src/700Parse/` — Form 700 XLSX → structured filer records (`seven.py::normalize_shf`). Canonical workbook: `sac700.xlsx`.
- `src/llmFlagging/` — conflict matchers:
  - `higherSpec.py` — base matcher
  - `higherSpec_chatollama.py` — local Ollama variant
  - `higherSpec_openai.py` — OpenAI variant (resumable, with checkpointing)
  - `lowerSpec.py` — narrower scoring helpers
  - `form700_paths.py` — shared path resolver, honors `FORM700_XLSX_PATH`
- `src/web_scrapers/` — Selenium-driven Sacramento County packet scraper plus `preprocess.py` tokenization.
- `src/docuAgent/` — document-writing agent helpers.
- `tests/` — `unittest` contract tests (parser, scraper helpers, preprocess).

## Quick reference

```bash
# Tests
python3 -m unittest discover tests

# Parser smoke
python3 src/700Parse/seven.py

# OpenAI matcher (dry run)
OPENAI_API_KEY=sk-... OPENAI_CONFLICT_SAMPLE_LIMIT=5 \
    python3 src/llmFlagging/higherSpec_openai.py
```

## Outputs

- `conflict_flags_openai.csv` / `.json` — per-page conflict flags
- `conflict_flags_openai_checkpoint.json` — resumable run state
- `src/web_scrapers/output_data/<year>/*.pdf` — downloaded packets

## Notes on `preprocess.py`

Returns a list of `{"file", "page", "text"}` dicts so downstream LLM calls can reference text by source. PDFs / XLSX / CSV files are not directly readable by the LLM — `preprocess` is the bridge that extracts text per page before flagging.
