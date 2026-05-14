# Frontend

Tkinter dashboard for triaging conflict-of-interest flags produced by the Backend pipeline. See the [root README](../README.md) for full project context.

## Run

```bash
python main.py
```

Requires Python 3.10+; `tkinter` ships with the standard library on standard CPython builds.

The Pipeline tab includes a county selector, a scrape-before-analysis switch,
and a Form 700 `.xlsx` picker for running county-specific filings against the
matching disclosure workbook.

## Layout

- `main.py` — entry point
- `app.py` — `ConflictDashboard` orchestrator
- `core/` — data loading, filter engine, email config + sender
- `agents/` — per-pane agents (browser, officials, selection, summary, confidence)
- `ui/` — theme and dialogs (e.g. email composer)
- `tests/` — `unittest` contracts for the data loader and filter engine

## Tests

```bash
python3 -m unittest discover tests
```
