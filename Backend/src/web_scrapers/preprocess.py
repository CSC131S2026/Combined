import pymupdf
import os
import pathlib
import pandas as pd

OUTPUT_DIR = pathlib.Path(__file__).resolve().parent / "output_data"


def _resolve_output_dir(output_dir=None):
    return pathlib.Path(output_dir) if output_dir else OUTPUT_DIR


def cleanup(output_dir=None):
    output_dir = _resolve_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pages_for_later = []

    for file in os.listdir(output_dir):
        file_path = output_dir / file
        ext = os.path.splitext(file)[1].lower()

        if ext == '.pdf':
            try:
                doc = pymupdf.open(file_path)
            except Exception as e:
                print(f"Failed to open PDF {file}: {e}")
                continue
            page_texts = []
            for page_num, page in enumerate(doc):
                page_text = page.get_text().strip()
                if page_text:
                    pages_for_later.append({
                        'file': file,
                        'page': page_num + 1,
                        'text': page_text
                    })
                page_texts.append(page.get_text())
            pathlib.Path(str(file_path) + ".txt").write_text(chr(12).join(page_texts), encoding='utf-8')

        elif ext == '.csv':
            try:
                breakdown = pd.read_csv(file_path)
            except Exception as e:
                print(f"Failed to read CSV {file}: {e}")
                continue
            pages_for_later.append({
                'file': file,
                'page': 'CSV',
                'text': breakdown.to_string()
            })

    return pages_for_later

def read_texts(output_dir=None):
    pages = []
    output_dir = _resolve_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for file in os.listdir(output_dir):
        if file.lower().endswith('.txt'):
            file_path = output_dir / file
            full_text = pathlib.Path(file_path).read_text(errors='ignore')
            for page_num, page_text in enumerate(full_text.split(chr(12))):
                page_text = page_text.strip()
                if page_text:
                    pages.append({
                        'file': file,
                        'page': page_num + 1,
                        'text': page_text
                    })
    return pages
