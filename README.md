# Sacramento/Sonoma County Conflict of Interest Dashboard

End-to-end pipeline for surfacing potential conflicts of interest in Sacramento County official filings. Scrapes packets from the county portal, extracts text, cross-references each filer against their Form 700 economic-interest disclosures, and uses an LLM to flag likely conflicts. A Tkinter dashboard lets a reviewer triage the results.

## Quick start: download and use

```bash
# 1. Download the project
git clone https://github.com/CSC131S2026/Combined.git
cd Combined

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install the app dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 4. Start the dashboard
cd Frontend
python main.py
```

On Windows, activate the virtual environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

To use the app after it opens, go to the Pipeline tab, paste an OpenAI API key,
choose a county/year, set `Sample limit` to `5` for a small first run, click
`Run pipeline`, then click `Load result into Dashboard` when the run finishes.
For a full run, change `Sample limit` back to `0`.

If you do not use Git, download the repository as a ZIP from GitHub, unzip it,
open a terminal in the unzipped `Combined` folder, and run the same virtual
environment, install, and dashboard commands above.

## Repo layout

```
.
├── Backend/
│   ├── src/
│   │   ├── form700_parse/      # Form 700 XLSX parser (sac700.xlsx is the canonical workbook)
│   │   ├── llmFlagging/        # Conflict matchers — OpenAI, ChatOllama, and base implementations
│   │   ├── web_scrapers/       # Selenium-based Sacramento/Sonoma County packet scraper + preprocess
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
python -m pip install -r requirements.txt
```

The root `requirements.txt` installs everything needed for the dashboard,
backend pipeline, scraping, LLM matching, and packaging. If you only need one
side of the project, you can install the scoped dependencies instead:

```bash
python -m pip install -r Backend/requirements.txt
python -m pip install -r Frontend/requirements.txt
```

## Running

### Frontend dashboard

```bash
cd Frontend
python main.py
```

The Pipeline tab can optionally scrape a selected county before analysis and
can use a county-specific Form 700 `.xlsx` workbook selected from disk. If no
workbook is selected, it falls back to `Backend/src/form700_parse/sac700.xlsx`.

### Scrape county packets

Downloads filings into year-scoped folders under `Backend/src/web_scrapers/output_data/<year>/` for Sacramento and `Backend/src/web_scrapers/output_data/sonoma/<year>/` for Sonoma. Already-downloaded packets are skipped on rerun, and stale `.crdownload` partials are cleaned up at startup.

```bash
cd Backend
python src/web_scrapers/scraper_sacramento_county.py
python src/web_scrapers/scraper_sonoma_county.py
```

### Parse Form 700 disclosures (smoke run)

```bash
cd Backend
python src/form700_parse/seven.py
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
python src/llmFlagging/higherSpec_openai.py --db-path conflict_checker.sqlite3
python src/llmFlagging/higherSpec_openai.py --list-runs
python src/llmFlagging/higherSpec_openai.py --show-run <run-id>
python src/llmFlagging/higherSpec_openai.py --resume-status
```

Run history and resume state are stored in SQLite at `Backend/conflict_checker.sqlite3` by default. `CONFLICT_DB_PATH` or `--db-path` can point at another database, and `CONFLICT_DISABLE_DB=1` restores the older file-only behavior. `--list-runs` / `--run-history` show recent SQLite runs without requiring an API key; `--show-run <run-id>` prints full provenance and failed pages for one run; `--resume-status` scans the current input and reports how many pages SQLite can skip before any OpenAI calls. JSON/CSV outputs use the `conflict_flags_openai_<scope>` convention for frontend compatibility; treat them as exports from the backend run state. The `_checkpoint.json` file is still written during analysis as a compatibility fallback for older runs.

Default output stems are:

| Input selection | Output stem |
|---|---|
| `--year 2020` | `conflict_flags_openai_2020` |
| `--input-dir .../output_data/2020` | `conflict_flags_openai_2020` |
| `--input-dir .../output_data/sonoma/2020` | `conflict_flags_openai_sonoma_2020` |
| `--input-dir .../my_folder` | `conflict_flags_openai_custom_my_folder` |

`CONFLICT_OUTPUT_STEM`, `CONFLICT_CSV_PATH`, `CONFLICT_JSON_PATH`, `CONFLICT_FAILED_CSV_PATH`, and `CONFLICT_CHECKPOINT_PATH` still override those defaults.

### Conflict matching — local Ollama

```bash
cd Backend
python src/llmFlagging/higherSpec_chatollama.py
```

## Full tutorial

This tutorial starts from a fresh checkout and ends with conflict results loaded
in the dashboard. The examples assume macOS or Linux; on Windows, use PowerShell
and the Windows activation command shown in Quick start.

### 1. Prepare your machine

Install these first:

- Python 3.10 or newer.
- Google Chrome, required when scraping county packet PDFs.
- Git, if you want to clone the repository instead of downloading a ZIP.
- An OpenAI API key for the OpenAI matcher, or a local Ollama setup if you plan
  to run the local matcher instead.

Confirm Python is available:

```bash
python3 --version
```

If the command is missing or shows an older Python, install a current Python
release before continuing.

### 2. Download the repository

Recommended Git workflow:

```bash
git clone https://github.com/CSC131S2026/Combined.git
cd Combined
```

ZIP workflow:

1. Open `https://github.com/CSC131S2026/Combined`.
2. Choose `Code` > `Download ZIP`.
3. Unzip the download.
4. Open a terminal in the unzipped `Combined` folder.

All commands below assume your terminal is at the repository root, the folder
that contains `Backend/`, `Frontend/`, `README.md`, and `requirements.txt`.

### 3. Create an isolated Python environment

Create the environment once:

```bash
python3 -m venv .venv
```

Activate it each time you work on the project:

```bash
source .venv/bin/activate
```

Your shell prompt usually changes to show `(.venv)`. That means dependency
installs and Python commands will use this project-specific environment.

### 4. Install dependencies

With the virtual environment active:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Use the root requirements file for normal development. It includes both the
frontend GUI dependencies and backend pipeline dependencies. The separate
`Backend/requirements.txt` and `Frontend/requirements.txt` files are useful only
when you intentionally want a smaller install for one half of the project.

### 5. Launch the dashboard

```bash
cd Frontend
python main.py
```

The dashboard opens as a desktop Tkinter window. If it does not open, confirm
that the virtual environment is active and that the install command completed
without errors.

### 6. Run a small pipeline job from the GUI

Use a small sample run first so you can verify credentials, scraping/input
paths, and output loading before spending time or API credits on a full run.

1. Open the `Pipeline` tab.
2. Paste your OpenAI API key into `OpenAI API key`.
3. Choose the `County`.
4. Enter the `Year` to analyze.
5. Leave `Model` at the default unless you need a specific OpenAI model.
6. Leave `Form 700 XLSX` blank to use `Backend/src/form700_parse/sac700.xlsx`,
   or click `Browse...` to choose a county-specific `.xlsx` workbook.
7. Choose one input mode:
   - Turn on `Scrape before analysis` to download county packets for the
     selected county/year before matching.
   - Or leave scraping off and use `Input dir` to select an existing folder of
     PDFs, text files, or CSV inputs.
8. Set `Sample limit` to `5`.
9. Click `Run pipeline`.
10. Watch the log and progress counter.
11. When the run succeeds, click `Load result into Dashboard`.

The API key field is cleared after a run is accepted so the key is not left
visible in the dashboard. Re-enter it before starting another run.

### 7. Review results in the dashboard

After results are loaded, use the dashboard as the review workspace:

- Use the file selector or `Browse...` button to load a different JSON output.
- Use the filter controls to narrow by source, confidence, officials, or
  matched entities.
- Select a row in the record browser to inspect the source file, page,
  confidence, matched people/entities, and LLM reasoning.
- Start with high-confidence records, then review medium and low confidence as
  time allows.
- Use `CSV export` when you need the complete filtered dataset.
- Use `PDF export` when you need a formatted review report.
- Use the email workflow only after SMTP settings are configured for your
  account.

### 8. Run a full GUI pipeline job

Once the sample run looks correct:

1. Return to the `Pipeline` tab.
2. Re-enter the OpenAI API key.
3. Keep the same county, year, workbook, and input settings.
4. Change `Sample limit` to `0`.
5. Click `Run pipeline`.
6. Load the result into the dashboard after completion.

`0` means no cap, so the pipeline will process every available page in the
selected input. Long runs store state in SQLite and checkpoint/export files so
you can inspect prior runs and resume work more safely.

### 9. CLI workflow for scraping and matching

The GUI is the easiest path, but the backend can also be run directly.

Scrape Sacramento and Sonoma packets:

```bash
cd Backend
python src/web_scrapers/scraper_sacramento_county.py
python src/web_scrapers/scraper_sonoma_county.py
```

Run a parser smoke test:

```bash
python src/form700_parse/seven.py
```

Run a five-page OpenAI dry run:

```bash
export OPENAI_API_KEY="sk-..."
OPENAI_CONFLICT_SAMPLE_LIMIT=5 python src/llmFlagging/higherSpec_openai.py --year 2019
```

Run the same year without a sample cap:

```bash
python src/llmFlagging/higherSpec_openai.py --year 2019
```

Analyze a custom input folder:

```bash
python src/llmFlagging/higherSpec_openai.py --input-dir src/web_scrapers/output_data/2019
```

Use a custom Form 700 workbook:

```bash
FORM700_XLSX_PATH=/path/to/form700.xlsx python src/llmFlagging/higherSpec_openai.py --year 2019
```

Inspect previous SQLite-backed runs:

```bash
python src/llmFlagging/higherSpec_openai.py --list-runs
python src/llmFlagging/higherSpec_openai.py --show-run <run-id>
python src/llmFlagging/higherSpec_openai.py --resume-status
```

### 10. Find the generated files

Common output locations:

- Scraped Sacramento PDFs: `Backend/src/web_scrapers/output_data/<year>/`
- Scraped Sonoma PDFs: `Backend/src/web_scrapers/output_data/sonoma/<year>/`
- SQLite run history: `Backend/conflict_checker.sqlite3`
- Dashboard JSON export: `Backend/conflict_flags_openai_<scope>.json`
- CSV export: `Backend/conflict_flags_openai_<scope>.csv`
- Failed-page report: `Backend/conflict_flags_openai_<scope>_failed_pages.csv`

The dashboard can load the generated JSON directly. CSV files are useful for
spreadsheet review, and failed-page reports tell you which pages need reruns or
manual inspection.

### 11. Troubleshooting

- `OPENAI_API_KEY is not set`: provide the API key in the Pipeline tab or export
  it before running the CLI matcher.
- Dashboard opens but no results appear: run the pipeline first, or use
  `Browse...` to load an existing `conflict_flags_openai_*.json` file.
- Scraping fails immediately: confirm Google Chrome is installed and can open
  normally.
- A run is too slow or expensive: set `Sample limit` to a small number for a dry
  run, then use `0` only when ready for the full dataset.
- The wrong disclosure workbook is being used: choose a workbook in the GUI or
  set `FORM700_XLSX_PATH` for CLI runs.
- You need a clean rerun of extracted text: set `CONFLICT_FORCE_PREPROCESS=1`
  before running the backend matcher.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `FORM700_XLSX_PATH` | `Backend/src/form700_parse/sac700.xlsx` | Override the Form 700 workbook used by all matchers |
| `OPENAI_API_KEY` | — | Required for the OpenAI matcher |
| `OPENAI_CONFLICT_MODEL` | `gpt-5.4-mini` | Model used by the OpenAI matcher |
| `CONFLICT_INPUT_YEAR` | `2019` | Year folder under `Backend/src/web_scrapers/output_data/<year>` used by the OpenAI matcher |
| `CONFLICT_INPUT_DIR` | — | Override the OpenAI matcher input directory; takes precedence over `CONFLICT_INPUT_YEAR` |
| `CONFLICT_SCRAPER_OUTPUT_DIR` | `Backend/src/web_scrapers/output_data` | Override where county scrapers download packet PDFs |
| `OPENAI_CONFLICT_SAMPLE_LIMIT` | `0` (no cap) | Cap pages processed — handy for dry runs |
| `OPENAI_CONFLICT_CONCURRENCY` | `16` | Parallel API requests |
| `OPENAI_CONFLICT_MAX_OUTPUT_TOKENS` | `200` | Per-response token cap |
| `OPENAI_CONFLICT_TIMEOUT_SECONDS` | `60` | Per-request timeout |
| `OPENAI_CONFLICT_MAX_API_RETRIES` | `4` | Retry budget for transient errors |
| `CONFLICT_FORCE_PREPROCESS` | `false` | Re-extract PDF text even when a current `.txt` cache exists |
| `CONFLICT_OUTPUT_STEM` | `conflict_flags_openai_<scope>` | Filename stem for CSV/JSON/checkpoint |
| `CONFLICT_FAILED_CSV_PATH` | `Backend/conflict_flags_openai_<scope>_failed_pages.csv` | Failed-page report written when any page fails analysis |
| `CONFLICT_DB_PATH` | `Backend/conflict_checker.sqlite3` | SQLite database for run metadata, extracted page text, and analysis results |
| `CONFLICT_DISABLE_DB` | `false` | Set to `1`, `true`, `yes`, or `on` to use only JSON/CSV/checkpoint files |

CLI flags `--year`, `--input-dir`, and `--db-path` mirror the matching environment variables and take precedence over them. `--list-runs`, `--run-history`, `--show-run`, and `--resume-status` are read-only command modes.

## Tests

```bash
# Backend
python3 -m unittest discover Backend/tests

# Frontend
python3 -m unittest discover Frontend/tests
```

The Backend suite covers the Form 700 parser contract, the scraper helpers, and `preprocess`. Frontend covers the data loader and filter engine.

## Outputs

- `Backend/src/web_scrapers/output_data/<year>/*.pdf` — downloaded Sacramento filing packets
- `Backend/src/web_scrapers/output_data/sonoma/<year>/*.pdf` — downloaded Sonoma filing packets
- `Backend/conflict_checker.sqlite3` — durable OpenAI matcher run metadata, page text, and analysis results
- `Backend/conflict_flags_openai_<year>.csv` / `.json` — compatibility exports consumed by the dashboard
- `Backend/conflict_flags_openai_<year>_failed_pages.csv` — written only when pages fail analysis
- `Backend/conflict_flags_openai_<year>_checkpoint.json` — legacy resumable run state retained during analysis

## Notes

- All three matchers (`higherSpec.py`, `higherSpec_chatollama.py`, `higherSpec_openai.py`) share Form 700 path resolution via `Backend/src/llmFlagging/form700_paths.py`. Set `FORM700_XLSX_PATH` to point them at a different workbook.
- The parser's `normalize_shf()` is silent by default; pass `verbose=True` for the per-sheet log lines.
- The OpenAI matcher gracefully continues if the Form 700 workbook is missing; the others raise.
