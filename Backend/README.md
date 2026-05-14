# Backend

Scraping, parsing, and LLM-flagging pipeline. See the [root README](../README.md) for project overview, install, and full run instructions.

## Layout

- `src/form700_parse/` — Form 700 XLSX → structured filer records (`seven.py::normalize_shf`). Canonical workbook: `sac700.xlsx`.
- `src/llmFlagging/` — conflict matchers:
  - `higherSpec.py` — base matcher
  - `higherSpec_chatollama.py` — local Ollama variant
  - `higherSpec_openai.py` — OpenAI variant (resumable, with checkpointing)
  - `lowerSpec.py` — narrower scoring helpers
  - `form700_paths.py` — shared path resolver, honors `FORM700_XLSX_PATH`
- `src/web_scrapers/` — county scraper registry, Selenium-driven Sacramento/Sonoma packet scrapers, and `preprocess.py` tokenization.
- `src/docuAgent/` — document-writing agent helpers.
- `tests/` — `unittest` contract tests (parser, scraper helpers, preprocess).

## Quick reference

```bash
# Tests
python3 -m unittest discover tests

# Parser smoke
python3 src/form700_parse/seven.py

# OpenAI matcher (dry run)
OPENAI_API_KEY=sk-... CONFLICT_INPUT_YEAR=2019 OPENAI_CONFLICT_SAMPLE_LIMIT=5 \
    python3 src/llmFlagging/higherSpec_openai.py
python3 src/llmFlagging/higherSpec_openai.py --year 2019
python3 src/llmFlagging/higherSpec_openai.py --input-dir src/web_scrapers/output_data/2019
python3 src/llmFlagging/higherSpec_openai.py --db-path conflict_checker.sqlite3
python3 src/llmFlagging/higherSpec_openai.py --list-runs
python3 src/llmFlagging/higherSpec_openai.py --show-run <run-id>
python3 src/llmFlagging/higherSpec_openai.py --resume-status
```

## Outputs

- `conflict_checker.sqlite3` — durable OpenAI matcher run metadata, extracted page text, and analysis results
- `conflict_flags_openai_<year>.csv` / `.json` — compatibility exports consumed by the frontend
- `conflict_flags_openai_<year>_failed_pages.csv` — written only when pages fail analysis
- `conflict_flags_openai_<year>_checkpoint.json` — legacy resumable run state retained during analysis
- `src/web_scrapers/output_data/<year>/*.pdf` — downloaded Sacramento packets
- `src/web_scrapers/output_data/sonoma/<year>/*.pdf` — downloaded Sonoma packets

`higherSpec_openai.py` defaults to `src/web_scrapers/output_data/2019`; `--year` / `CONFLICT_INPUT_YEAR` select a different year folder, and `--input-dir` / `CONFLICT_INPUT_DIR` select a custom folder. CLI flags take precedence over env vars. Custom input folders use `conflict_flags_openai_<input-dir-name>` as the default output stem unless output path env vars override it.

County scrapers write to `src/web_scrapers/output_data` by default. Set
`CONFLICT_SCRAPER_OUTPUT_DIR` to redirect downloads, which is how packaged GUI
runs avoid writing into the read-only bundled backend.

The OpenAI matcher uses SQLite by default at `Backend/conflict_checker.sqlite3`. Use `CONFLICT_DB_PATH` or `--db-path` for another database path, or set `CONFLICT_DISABLE_DB=1` to keep the older JSON/CSV/checkpoint-only behavior. `--list-runs` / `--run-history` show recent SQLite runs without requiring an API key, `--show-run <run-id>` prints full provenance and failed pages for one run, and `--resume-status` reports how many current pages can be skipped before any OpenAI calls. JSON and CSV files remain part of the workflow for dashboard compatibility; SQLite is the preferred resume/history source when present.

## Notes on `preprocess.py`

Returns a list of `{"file", "page", "text"}` dicts so downstream LLM calls can reference text by source. PDFs / XLSX / CSV files are not directly readable by the LLM — `preprocess` is the bridge that extracts text per page before flagging.
