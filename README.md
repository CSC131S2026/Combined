# Sacramento County Conflict of Interest Dashboard

End-to-end pipeline for surfacing potential conflicts of interest in Sacramento County official filings. Scrapes packets from the county portal, extracts text, cross-references each filer against their Form 700 economic-interest disclosures, and uses an LLM to flag likely conflicts. A Tkinter dashboard lets a reviewer triage the results.

## Repo layout

```
.
├── Backend/
│   ├── src/
│   │   ├── 700Parse/           # Form 700 XLSX parser (sac700.xlsx is the canonical workbook)
│   │   ├── llmFlagging/        # Conflict matchers — OpenAI, ChatOllama, and base implementations
│   │   ├── web_scrapers/       # Selenium-based Sacramento County packet scraper + preprocess
│   │   └── docuAgent/          # Document-writing agent helpers
│   ├── tests/                  # Contract / regression tests (unittest)
│   └── requirements.txt
└── Frontend/
    ├── main.py                 # GUI entry point
    ├── app.py                  # ConflictDashboard orchestrator
    ├── agents/                 # Per-pane agents (browser, summary, selection, etc.)
    ├── core/                   # Data loader, filter engine, email
    ├── ui/                     # Theme + dialogs
    ├── tests/
    └── requirements.txt
```

## Requirements

- Python 3.10+
- Google Chrome (Selenium-driven; the scraper drives a real Chrome instance)
- Optional: an OpenAI API key, **or** a local [Ollama](https://ollama.com/) install for the offline matcher

## Install

```bash
# from the repo root
pip install -r Backend/requirements.txt
pip install -r Frontend/requirements.txt
```

## Running

### Frontend dashboard

```bash
cd Frontend
python main.py
```

### Scrape Sacramento County packets

Downloads filings into year-scoped folders under `Backend/src/web_scrapers/output_data/<year>/`. Already-downloaded packets are skipped on rerun, and stale `.crdownload` partials are cleaned up at startup.

```bash
cd Backend
python src/web_scrapers/scraper_sacramento_county.py
```

### Parse Form 700 disclosures (smoke run)

```bash
cd Backend
python src/700Parse/seven.py
```

### Conflict matching — OpenAI

```bash
cd Backend
export OPENAI_API_KEY="sk-..."
export CONFLICT_INPUT_YEAR=2019            # optional, defaults to 2019
export OPENAI_CONFLICT_SAMPLE_LIMIT=5     # optional, caps to first N pages for a dry run
python src/llmFlagging/higherSpec_openai.py
# or:
python src/llmFlagging/higherSpec_openai.py --year 2019
python src/llmFlagging/higherSpec_openai.py --input-dir src/web_scrapers/output_data/2019
```

Outputs land at `Backend/conflict_flags_openai_<year>.csv` and `.json`, with a `_checkpoint.json` for resumable runs. For `--input-dir` / `CONFLICT_INPUT_DIR`, the default output stem uses the input directory name instead; `CONFLICT_OUTPUT_STEM`, `CONFLICT_CSV_PATH`, `CONFLICT_JSON_PATH`, and `CONFLICT_CHECKPOINT_PATH` still override that.

### Conflict matching — local Ollama

```bash
cd Backend
python src/llmFlagging/higherSpec_chatollama.py
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `FORM700_XLSX_PATH` | `Backend/src/700Parse/sac700.xlsx` | Override the Form 700 workbook used by all matchers |
| `OPENAI_API_KEY` | — | Required for the OpenAI matcher |
| `OPENAI_CONFLICT_MODEL` | `gpt-5.4-mini` | Model used by the OpenAI matcher |
| `CONFLICT_INPUT_YEAR` | `2019` | Year folder under `Backend/src/web_scrapers/output_data/<year>` used by the OpenAI matcher |
| `CONFLICT_INPUT_DIR` | — | Override the OpenAI matcher input directory; takes precedence over `CONFLICT_INPUT_YEAR` |
| `OPENAI_CONFLICT_SAMPLE_LIMIT` | `0` (no cap) | Cap pages processed — handy for dry runs |
| `OPENAI_CONFLICT_CONCURRENCY` | `16` | Parallel API requests |
| `OPENAI_CONFLICT_MAX_OUTPUT_TOKENS` | `200` | Per-response token cap |
| `OPENAI_CONFLICT_TIMEOUT_SECONDS` | `60` | Per-request timeout |
| `OPENAI_CONFLICT_MAX_API_RETRIES` | `4` | Retry budget for transient errors |
| `CONFLICT_FORCE_PREPROCESS` | `false` | Re-extract PDF text even when a current `.txt` cache exists |
| `CONFLICT_OUTPUT_STEM` | `conflict_flags_openai_<year>` | Filename stem for CSV/JSON/checkpoint |

CLI flags `--year` and `--input-dir` mirror the input environment variables and take precedence over them.

## Tests

```bash
# Backend
python3 -m unittest discover Backend/tests

# Frontend
python3 -m unittest discover Frontend/tests
```

The Backend suite covers the Form 700 parser contract, the scraper helpers, and `preprocess`. Frontend covers the data loader and filter engine.

## Outputs

- `Backend/src/web_scrapers/output_data/<year>/*.pdf` — downloaded filing packets
- `Backend/conflict_flags_openai_<year>.csv` / `.json` — per-page conflict flags from the OpenAI matcher
- `Backend/conflict_flags_openai_<year>_checkpoint.json` — resumable run state

## Notes

- All three matchers (`higherSpec.py`, `higherSpec_chatollama.py`, `higherSpec_openai.py`) share Form 700 path resolution via `Backend/src/llmFlagging/form700_paths.py`. Set `FORM700_XLSX_PATH` to point them at a different workbook.
- The parser's `normalize_shf()` is silent by default; pass `verbose=True` for the per-sheet log lines.
- The OpenAI matcher gracefully continues if the Form 700 workbook is missing; the others raise.
Tidy
