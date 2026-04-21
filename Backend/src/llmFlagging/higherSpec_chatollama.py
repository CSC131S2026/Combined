"""
Prototype: higherSpec.py migrated to ChatOllama + Pydantic structured output.
"""
import sys, importlib.util, pathlib, re

_repo_root = pathlib.Path(__file__).parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from langchain_ollama import ChatOllama
from pydantic import BaseModel
from typing import Literal

from src.web_scrapers.preprocess import cleanup, read_texts

_spec = importlib.util.spec_from_file_location("seven", _repo_root / "src" / "700Parse" / "seven.py")
_mod = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_mod)
normalize_shf = _mod.normalize_shf

import json
import uuid
import datetime
from collections import deque
import pandas as pd
import asyncio
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn,
    TimeElapsedColumn, TimeRemainingColumn, MofNCompleteColumn,
)
from rich.table import Table
from rich.text import Text
from rich import box

_console = Console()

# Violet palette
_V6  = "#7c3aed"   # deep violet  — borders
_V5  = "#8b5cf6"   # violet       — primary
_V4  = "#a78bfa"   # soft violet  — labels
_V3  = "#c4b5fd"   # pale violet  — secondary text
_RED = "#f87171"   # rose         — conflict found
_GRN = "#4ade80"   # green        — no conflict
_AMB = "#f59e0b"   # amber        — medium confidence


# --- Structured output schema ---

class ConflictAnalysis(BaseModel):
    match: bool
    reasoning: str
    confidence: Literal['low', 'medium', 'high']


# --- LLM setup ---

# OLLAMA_NUM_PARALLEL=16 must be set when starting the Ollama server:
#   OLLAMA_NUM_PARALLEL=16 ollama serve
_llm = ChatOllama(
    model='llama3.1:8b',
    format='json',
    num_gpu=99,
    num_thread=12,
    num_ctx=2048,
    num_batch=512,
    num_predict=200,
    temperature=0,
)
# with_structured_output() uses Pydantic V1 compat layer — broken on Python 3.14+
# Instead: invoke directly and validate with Pydantic V2



# --- Data loading (unchanged) ---

cleanup()
pages = read_texts()
filers = normalize_shf(str(_repo_root / "src" / "700Parse" / "county700.xlsx")) or []

name_to_filer = {}
entity_index = {}

for filer in filers:
    full_name = f"{filer['first_name']} {filer['last_name']}".lower().strip()
    name_to_filer[full_name] = filer

    def _index_entity(entity_name, filer=filer):
        key = entity_name.lower().strip()
        if key:
            entity_index.setdefault(key, []).append(filer)

    for entry in filer['schedules'].get('A-1', []):
        _index_entity(entry.get('business_entity', ''))
    for entry in filer['schedules'].get('A-2', []):
        _index_entity(entry.get('business_entity', ''))
    for entry in filer['schedules'].get('C', []):
        _index_entity(entry.get('name_of_source', ''))
    for entry in filer['schedules'].get('D', []):
        _index_entity(entry.get('name_of_source', ''))


# --- Form 700 context (unchanged) ---

def find_form700_context(text_lower):
    hits = []

    matched_filers = {name: filer for name, filer in name_to_filer.items() if name in text_lower}

    for entity, disclosing_filers in entity_index.items():
        if entity in text_lower:
            for filer in disclosing_filers:
                hits.append((filer, entity))

    if not matched_filers and not hits:
        return None, [], []

    lines = ["[Form 700 Cross-Reference]"]
    officials_found = set()
    entities_found = set()

    for _, filer in matched_filers.items():
        display = f"{filer['first_name']} {filer['last_name']} ({filer['position']})"
        lines.append(f"  Official on this page: {display}")
        officials_found.add(f"{filer['first_name']} {filer['last_name']}")

    for filer, entity in hits:
        display = f"{filer['first_name']} {filer['last_name']} ({filer['position']})"
        lines.append(f"  {display} has a disclosed financial interest in: {entity.title()}")
        officials_found.add(f"{filer['first_name']} {filer['last_name']}")
        entities_found.add(entity.title())

    return "\n".join(lines), sorted(officials_found), sorted(entities_found)


# --- Keyword filter (unchanged) ---

# Single match on these is enough — specific to conflict-of-interest scenarios
HIGH_SIGNAL = [
    'financial interest', 'conflict of interest', 'recuse', 'recusal',
    'board member', 'ownership interest', 'disclosure', 'disclose',
    'spouse', 'domestic partner',
]

# Generic words — require 2+ to reduce noise
LOW_SIGNAL = [
    'contract', 'vendor', 'bid', 'grant', 'donation',
    'family', 'partner', 'ownership', 'consultant', 'conflict', 'interest',
]

_ALL_SIGNAL = HIGH_SIGNAL + LOW_SIGNAL

def has_keywords(text):
    t = text.lower()
    if any(kw in t for kw in HIGH_SIGNAL):
        return True
    return sum(1 for kw in LOW_SIGNAL if kw in t) >= 2

filtered_pages = [p for p in pages if has_keywords(p['text'])]
_console.print(
    f"[{_V4}]Filtered[/] [{_V3}]{len(pages)}[/] [{_V4}]pages →[/] "
    f"[bold {_V3}]{len(filtered_pages)}[/] [{_V4}]queued for analysis[/]"
)


# --- Analysis (structured output replaces manual JSON parsing) ---

_SCHEMA_INSTRUCTIONS = (
    "Respond ONLY with a JSON object using these exact keys: "
    "'match' (true or false), 'reasoning' (string), 'confidence' (low/medium/high)."
)
_STRICT_SCHEMA = (
    'Your response MUST be exactly this JSON structure and nothing else:\n'
    '{"match": true or false, "reasoning": "your explanation here", "confidence": "low" or "medium" or "high"}\n'
    'Do NOT wrap it in another object or add extra keys.'
)

async def _invoke_llm(prompt):
    current = prompt
    for attempt in range(2):
        try:
            response = await _llm.ainvoke(current)
            content = response.content.strip()
            if not content:
                raise ValueError("empty response from LLM")
            if "<think>" in content:
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            if not content:
                raise ValueError("empty after stripping")
            raw = json.loads(content)
            if 'confidence' in raw:
                raw['confidence'] = str(raw['confidence']).lower()
            return ConflictAnalysis.model_validate(raw)
        except Exception as e:
            if attempt == 1:
                raise RuntimeError(str(e))
            current = f"{_STRICT_SCHEMA}\n\n{current}"

async def analyze_page(page):
    full_text = page['text']
    chunks = [c.strip() for c in (full_text[:800], full_text[800:1600]) if c.strip()]
    if not chunks:
        return None

    analysis_text = full_text[:1600]
    analysis_lower = analysis_text.lower()
    form700_ctx, officials, entities = find_form700_context(analysis_lower)
    matched_keywords = [kw for kw in _ALL_SIGNAL if kw in analysis_lower]

    def _build_prompt(text):
        if form700_ctx:
            return (
                f"{form700_ctx}\n\n"
                f"Using the above Form 700 disclosure context, analyze the following agenda page "
                f"for potential conflicts of interest. Identify who is involved if any conflict is found. "
                f"{_SCHEMA_INSTRUCTIONS}\n\n{text}"
            )
        return (
            f"Analyze the following text for potential conflicts of interest. "
            f"Identify who is involved if any conflict is found. "
            f"{_SCHEMA_INSTRUCTIONS}\n\n{text}"
        )

    def _pack(result):
        return {
            'match': result.match,
            'reasoning': result.reasoning,
            'confidence': result.confidence,
            'file': page['file'],
            'page': page['page'],
            'form700_officials': ', '.join(officials),
            'form700_entities': ', '.join(entities),
            'keywords_matched': matched_keywords,
            'analyzed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    first = await _invoke_llm(_build_prompt(chunks[0]))
    if first and first.match:
        return _pack(first)

    if len(chunks) > 1:
        second = await _invoke_llm(_build_prompt(chunks[1]))
        if second and second.match:
            return _pack(second)
        if second and first is None:
            return _pack(second)

    return _pack(first) if first else None


# --- Frontend JSON payload ---

_CONFIDENCE_ORDER = {'high': 0, 'medium': 1, 'low': 2}


def build_frontend_payload(results, total_scanned, total_analyzed):
    """
    Builds a structured JSON payload intended for frontend consumption.

    Sections
    --------
    meta      — run provenance (model, timestamps, page counts)
    summary   — aggregated stats for dashboard cards/charts
    results   — per-page findings sorted by severity (flagged first,
                then descending confidence), each with a stable UUID
                so the frontend can use it as a React key or deep-link anchor
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    confidence_counts = {'high': 0, 'medium': 0, 'low': 0}
    officials_implicated: set[str] = set()
    entities_implicated: set[str] = set()
    flags = []

    for r in results:
        # Re-split comma-joined strings into lists for structured JSON;
        # the CSV output keeps the joined strings unchanged.
        officials = [o.strip() for o in r['form700_officials'].split(',') if o.strip()] \
                    if r['form700_officials'] else []
        entities  = [e.strip() for e in r['form700_entities'].split(',')  if e.strip()] \
                    if r['form700_entities']  else []

        conf = r['confidence']
        if conf in confidence_counts:
            confidence_counts[conf] += 1

        if r['match']:
            officials_implicated.update(officials)
            entities_implicated.update(entities)

        flags.append({
            'id': str(uuid.uuid4()),
            'analyzed_at': r.get('analyzed_at', now),
            'source': {
                'file': r['file'],
                'page': r['page'],
            },
            'conflict': {
                'match': r['match'],
                'confidence': conf,
                'reasoning': r['reasoning'],
            },
            'form700': {
                'officials': officials,
                'entities': entities,
            },
            'keywords_matched': r.get('keywords_matched', []),
        })

    # Flagged results first; within each group, highest confidence first;
    # tie-break alphabetically by file then page number.
    flags.sort(key=lambda f: (
        not f['conflict']['match'],
        _CONFIDENCE_ORDER.get(f['conflict']['confidence'], 3),
        f['source']['file'],
        f['source']['page'],
    ))

    conflicts_flagged = sum(1 for r in results if r['match'])

    return {
        'meta': {
            'generated_at': now,
            'model': _llm.model,
            'total_pages_scanned': total_scanned,
            'total_pages_analyzed': total_analyzed,
            'total_results': len(results),
        },
        'summary': {
            'conflicts_flagged': conflicts_flagged,
            'no_conflict_found': len(results) - conflicts_flagged,
            'by_confidence': confidence_counts,
            'officials_implicated': sorted(officials_implicated),
            'entities_implicated': sorted(entities_implicated),
        },
        'results': flags,
    }


# --- Rich UI (purple theme) ---

def _header() -> Panel:
    t = Text(justify="center")
    t.append("⬡  CONFLICT ANALYSIS ENGINE  ⬡\n", style=f"bold {_V3}")
    t.append(f"model · {_llm.model}", style=_V4)
    return Panel(t, border_style=_V6, box=box.DOUBLE_EDGE, padding=(0, 4))


def _stats_panel(analyzed: int, conflicts: int, by_conf: dict) -> Panel:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style=_V4, min_width=14)
    grid.add_column(justify="right", style="bold white", min_width=4)
    grid.add_row("Analyzed",  str(analyzed))
    grid.add_row(
        "Conflicts",
        Text(str(conflicts), style=f"bold {_RED}" if conflicts else f"bold {_GRN}"),
    )
    grid.add_row(Text("● High",   style=_RED), str(by_conf['high']))
    grid.add_row(Text("● Medium", style=_AMB), str(by_conf['medium']))
    grid.add_row(Text("● Low",    style=_V4),  str(by_conf['low']))
    return Panel(grid, title=f"[{_V3}]Stats[/]", border_style=_V5,
                 box=box.ROUNDED, padding=(1, 2))


def _recent_panel(recent) -> Panel:
    body = Text()
    for r in recent:
        if r['match']:
            conf_label = {'high': 'HIGH', 'medium': 'MED ', 'low': 'LOW '}.get(r['confidence'], '    ')
            conf_color = {'high': _RED, 'medium': _AMB, 'low': _V4}.get(r['confidence'], _V3)
            body.append("✗ ", style=f"bold {_RED}")
            body.append(f" {conf_label} ", style=f"bold {conf_color} on #1e1b4b")
        else:
            body.append("✓ ", style=f"bold {_GRN}")
            body.append(f" ——   ", style=f"{_V3} on #1e1b4b")
        body.append(f"  {r['file']} ", style=_V4)
        body.append(f"p{r['page']}\n", style=f"bold {_V3}")
        snippet = r['reasoning'][:72].replace('\n', ' ')
        body.append(f"   {snippet}…\n\n", style=_V3)

    content = body if len(body) else Text("Waiting for results…", style=_V4)
    return Panel(content, title=f"[{_V3}]Recent[/]", border_style=_V5,
                 box=box.ROUNDED, padding=(1, 2))


def _make_layout(progress: Progress, analyzed: int, conflicts: int, by_conf: dict, recent) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(_header(), name="header", size=5),
        Layout(Panel(progress, border_style=_V6, box=box.SIMPLE, padding=(0, 1)),
               name="prog", size=4),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(_stats_panel(analyzed, conflicts, by_conf), name="stats", ratio=2),
        Layout(_recent_panel(recent),                      name="recent", ratio=3),
    )
    return layout


# --- Checkpoint ---

_CHECKPOINT = pathlib.Path('conflict_flags_checkpoint.json')
_CHECKPOINT_INTERVAL = 50
_checkpoint_counter = 0

def _load_checkpoint():
    if not _CHECKPOINT.exists():
        return [], set(), set()
    with open(_CHECKPOINT) as fh:
        data = json.load(fh)
    if isinstance(data, list):
        results = data
        processed = {(r['file'], r['page']) for r in data}
        failed = set()
    else:
        results = data.get('results', [])
        raw = data.get('processed', [])
        processed = {(e[0], e[1]) if isinstance(e, list) else (e['file'], e['page']) for e in raw}
        raw_failed = data.get('failed', [])
        failed = {(e[0], e[1]) if isinstance(e, list) else (e['file'], e['page']) for e in raw_failed}
    _console.print(
        f"[{_V4}]Resuming from checkpoint:[/] [{_V3}]{len(processed)} processed, "
        f"{len(failed)} failed, {len(results)} results[/]"
    )
    return results, processed, failed

def _save_checkpoint(res, processed, failed):
    tmp = _CHECKPOINT.with_suffix('.tmp')
    with open(tmp, 'w') as fh:
        json.dump({'results': res, 'processed': list(processed), 'failed': list(failed)}, fh)
    tmp.replace(_CHECKPOINT)


# --- Execution ---

_prior_results, _done_set, _failed_set = _load_checkpoint()
_skip = _done_set | _failed_set
_remaining_pages = [p for p in filtered_pages if (p['file'], p['page']) not in _skip]

_progress = Progress(
    SpinnerColumn(style=_V5),
    TextColumn(f"[{_V4}]{{task.description}}[/]"),
    BarColumn(bar_width=36, style=_V6, complete_style=_V5, finished_style=_GRN),
    MofNCompleteColumn(),
    TimeElapsedColumn(),
    TimeRemainingColumn(),
    console=_console,
)
_already_done = len(_done_set)
_task    = _progress.add_task("Analyzing pages", total=_already_done + len(_remaining_pages), completed=_already_done)
_recent         = deque(maxlen=5)
results         = list(_prior_results)
_processed      = set(_done_set)
_failed         = set(_failed_set)
_conflicts_count = sum(1 for r in results if r['match'])
_conf_counts     = {
    'high':   sum(1 for r in results if r['confidence'] == 'high'),
    'medium': sum(1 for r in results if r['confidence'] == 'medium'),
    'low':    sum(1 for r in results if r['confidence'] == 'low'),
}

async def _run_analysis(live):
    global _checkpoint_counter, _conflicts_count, _conf_counts
    sem = asyncio.Semaphore(16)
    lock = asyncio.Lock()

    async def bounded(page):
        global _checkpoint_counter, _conflicts_count, _conf_counts
        key = (page['file'], page['page'])
        async with sem:
            try:
                result = await analyze_page(page)
            except Exception as e:
                print(f"Error analyzing {page['file']} p{page['page']}: {e}")
                result = None
            do_checkpoint = False
            async with lock:
                if result is None:
                    _failed.add(key)
                _processed.add(key)
                if result:
                    results.append(result)
                    _recent.appendleft(result)
                    if result['match']:
                        _conflicts_count += 1
                    if result['confidence'] in _conf_counts:
                        _conf_counts[result['confidence']] += 1
                _progress.advance(_task)
                _checkpoint_counter += 1
                if _checkpoint_counter % _CHECKPOINT_INTERVAL == 0:
                    do_checkpoint = True
            # UI update and checkpoint I/O outside the lock
            live.update(_make_layout(_progress, len(results), _conflicts_count, _conf_counts, _recent))
            if do_checkpoint:
                _save_checkpoint(results, _processed, _failed)

    await asyncio.gather(*[bounded(p) for p in _remaining_pages])

with Live(_make_layout(_progress, len(results), _conflicts_count, _conf_counts, _recent),
          console=_console, refresh_per_second=6) as live:
    asyncio.run(_run_analysis(live))

_save_checkpoint(results, _processed, _failed)

# --- Final summary table ---

summary = Table(
    title=f"[bold {_V3}]Analysis Complete[/]",
    box=box.ROUNDED, border_style=_V6,
    header_style=f"bold {_V4}",
    show_lines=True,
)
summary.add_column("File",       style=_V3,           no_wrap=True)
summary.add_column("Pg",         style=_V4,           justify="right", min_width=3)
summary.add_column("Match",      justify="center",    min_width=5)
summary.add_column("Confidence", justify="center",    min_width=10)
summary.add_column("Reasoning",  style=_V3,           no_wrap=False, max_width=55)

_conf_color = {'high': _RED, 'medium': _AMB, 'low': _V4}
for r in sorted(results, key=lambda x: (not x['match'], _CONFIDENCE_ORDER.get(x['confidence'], 3))):
    summary.add_row(
        r['file'],
        str(r['page']),
        Text("✗ YES", style=f"bold {_RED}") if r['match'] else Text("✓ NO", style=_GRN),
        Text(r['confidence'].upper(), style=_conf_color.get(r['confidence'], _V3)),
        r['reasoning'][:120],
    )

_console.print()
_console.print(summary)
_console.print()

df = pd.DataFrame(results)
df.to_csv('conflict_flags.csv', index=False)

payload = build_frontend_payload(results, len(pages), len(filtered_pages))
with open('conflict_flags.json', 'w') as fh:
    json.dump(payload, fh, indent=2)

# Clean up checkpoint now that final outputs are written
for _f in (_CHECKPOINT, _CHECKPOINT.with_suffix('.tmp')):
    if _f.exists():
        _f.unlink()
_console.print(f"[{_V4}]Checkpoint removed.[/]")

_console.print(
    f"[{_V4}]Written →[/] [{_V3}]conflict_flags.csv[/]  [{_V4}]·[/]  [{_V3}]conflict_flags.json[/]  "
    f"[{_V4}]({payload['summary']['conflicts_flagged']} conflict(s) / "
    f"{payload['meta']['total_results']} analyzed)[/]"
)
