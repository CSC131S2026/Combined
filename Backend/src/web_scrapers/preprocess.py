import pymupdf
import os
import pathlib
import pandas as pd

OUTPUT_DIR = pathlib.Path(__file__).resolve().parent / "output_data"


def _resolve_output_dir(output_dir=None):
    return pathlib.Path(output_dir) if output_dir else OUTPUT_DIR


def _read_page_texts(txt_path, source_file):
    full_text = pathlib.Path(txt_path).read_text(errors='ignore')
    pages = []
    for page_num, page_text in enumerate(full_text.split(chr(12))):
        page_text = page_text.strip()
        if page_text:
            pages.append({
                'file': source_file,
                'page': page_num + 1,
                'text': page_text
            })
    return pages


def cleanup(output_dir=None, *, force=False, progress=None):
    output_dir = _resolve_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pages_for_later = []
    progress = progress or (lambda _message: None)

    files = sorted(os.listdir(output_dir))
    for index, file in enumerate(files, start=1):
        file_path = output_dir / file
        ext = os.path.splitext(file)[1].lower()

        if ext == '.pdf':
            txt_path = pathlib.Path(str(file_path) + ".txt")
            if not force and txt_path.exists() and txt_path.stat().st_mtime >= file_path.stat().st_mtime:
                progress(f"Skipping current text extract {index}/{len(files)}: {file}")
                pages_for_later.extend(_read_page_texts(txt_path, file))
                continue

            progress(f"Extracting PDF text {index}/{len(files)}: {file}")
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
            txt_path.write_text(chr(12).join(page_texts), encoding='utf-8')

        elif ext == '.csv':
            progress(f"Reading CSV {index}/{len(files)}: {file}")
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
    for file in sorted(os.listdir(output_dir)):
        if file.lower().endswith('.txt'):
            file_path = output_dir / file
            pages.extend(_read_page_texts(file_path, file))
    return pages
