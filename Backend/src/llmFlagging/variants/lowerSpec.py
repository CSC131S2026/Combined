import ollama
from src.web_scrapers.preprocess import cleanup, read_texts
import pandas as pd
import json
import re
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

cleanup()
pages = read_texts()
results = []

KEYWORDS = [
    'contract', 'vendor', 'award', 'approve', 'bid', 'grant',
    'donation', 'family', 'spouse', 'partner', 'ownership',
    'financial interest', 'board member', 'consultant', 'firm',
    'disclosure', 'recuse', 'conflict'
]

def has_keywords(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in KEYWORDS)

filtered_pages = [p for p in pages if has_keywords(p['text'])]
print(f"Filtered {len(pages)} pages down to {len(filtered_pages)} for analysis")

def _extract_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise

def analyze_page(page):
    try:
        response = ollama.chat(
            model='llama3.2:3b',
            format='json',
            messages=[{
                'role': 'user',
                'content': (
                    f"Analyze the following text for potential conflicts of interest. "
                    f"Identify who is involved if any conflict is found. "
                    f"Respond ONLY with a JSON object using these exact keys: "
                    f"'match' (true or false), 'reasoning' (string), 'confidence' (low/medium/high).\n\n{page['text']}"
                )
            }],
            options={
                'num_gpu': 99,
                'num_thread': 4,
                'num_ctx': 8192,
                'num_batch': 512,
            }
        )
        raw = _extract_json(response['message']['content'])
        match = raw.get('match')
        if isinstance(match, str):
            match = match.strip().lower() == 'true'
        confidence = str(raw.get('confidence', 'low')).lower()
        if confidence not in ('low', 'medium', 'high'):
            confidence = 'low'
        return {
            'match': match,
            'reasoning': raw.get('reasoning'),
            'confidence': confidence,
            'file': page['file'],
            'page': page['page'],
        }
    except Exception as e:
        print(f"Error analyzing {page['file']} p{page['page']}: {e}")
        return None

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {executor.submit(analyze_page, page): page for page in filtered_pages}
    for future in tqdm(as_completed(futures), total=len(filtered_pages), desc='Analyzing pages'):
        result = future.result()
        if result:
            results.append(result)

df = pd.DataFrame(results)
df.to_csv('conflict_flags.csv', index=False)
