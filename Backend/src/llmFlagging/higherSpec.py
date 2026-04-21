import sys, importlib.util, pathlib, re, json
from pydantic import BaseModel
from typing import Literal

class ConflictAnalysis(BaseModel):
    match: bool
    reasoning: str
    confidence: Literal['low', 'medium', 'high']

_repo_root = pathlib.Path(__file__).parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import ollama
from src.web_scrapers.preprocess import cleanup, read_texts

_spec = importlib.util.spec_from_file_location("seven", _repo_root / "src" / "700Parse" / "seven.py")
_mod = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_mod)
normalize_shf = _mod.normalize_shf

import pandas as pd
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

cleanup()
pages = read_texts()
filers = normalize_shf(str(_repo_root / "src" / "700Parse" / "county700.xlsx")) or []
results = []

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

def find_form700_context(page_text):
    text_lower = page_text.lower()
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

HIGH_SIGNAL = [
    'financial interest', 'conflict of interest', 'recuse', 'recusal',
    'board member', 'ownership interest', 'disclosure', 'disclose',
    'spouse', 'domestic partner',
]
LOW_SIGNAL = [
    'contract', 'vendor', 'bid', 'grant', 'donation',
    'family', 'partner', 'ownership', 'consultant', 'conflict', 'interest',
]

def has_keywords(text):
    t = text.lower()
    if any(kw in t for kw in HIGH_SIGNAL):
        return True
    return sum(1 for kw in LOW_SIGNAL if kw in t) >= 2

filtered_pages = [p for p in pages if has_keywords(p['text'])]
print(f"Filtered {len(pages)} pages down to {len(filtered_pages)} for analysis")

_STRICT_SCHEMA = (
    'Your response MUST be exactly this JSON structure and nothing else:\n'
    '{"match": true or false, "reasoning": "your explanation here", "confidence": "low" or "medium" or "high"}\n'
    'Do NOT wrap it in another object or add extra keys.'
)

def _parse_response(content):
    content = content.strip()
    if "<think>" in content:
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    raw = json.loads(content.strip())
    if 'confidence' in raw:
        raw['confidence'] = str(raw['confidence']).lower()
    return ConflictAnalysis.model_validate(raw)

def analyze_page(page):
    page_text = page['text'][:1600].strip()
    if not page_text:
        return None
    form700_ctx, officials, entities = find_form700_context(page_text)

    schema_instr = (
        "Respond ONLY with a JSON object using these exact keys: "
        "'match' (true or false), 'reasoning' (string), 'confidence' (low/medium/high)."
    )
    if form700_ctx:
        prompt = (
            f"{form700_ctx}\n\n"
            f"Using the above Form 700 disclosure context, analyze the following agenda page "
            f"for potential conflicts of interest. Identify who is involved if any conflict is found. "
            f"{schema_instr}\n\n{page_text}"
        )
    else:
        prompt = (
            f"Analyze the following text for potential conflicts of interest. "
            f"Identify who is involved if any conflict is found. "
            f"{schema_instr}\n\n{page_text}"
        )

    current_prompt = prompt
    for attempt in range(2):
        try:
            response = ollama.chat(
                model='gemma4:latest',
                format='json',
                messages=[{'role': 'user', 'content': current_prompt}],
                options={'num_gpu': 99, 'num_thread': 12, 'num_ctx': 16384, 'num_batch': 1024}
            )
            result = _parse_response(response['message']['content'])
            return {
                'match': result.match,
                'reasoning': result.reasoning,
                'confidence': result.confidence,
                'file': page['file'],
                'page': page['page'],
                'form700_officials': ', '.join(officials),
                'form700_entities': ', '.join(entities),
            }
        except Exception as e:
            if attempt == 1:
                print(f"Error analyzing {page['file']} p{page['page']}: {e}")
            else:
                current_prompt = f"{_STRICT_SCHEMA}\n\n{current_prompt}"
    return None

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {executor.submit(analyze_page, page): page for page in filtered_pages}
    for future in tqdm(as_completed(futures), total=len(filtered_pages), desc='Analyzing pages'):
        result = future.result()
        if result:
            results.append(result)

df = pd.DataFrame(results)
df.to_csv('conflict_flags.csv', index=False)
