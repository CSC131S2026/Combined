import pymupdf
import os
import pathlib
import pandas as pd

def cleanup():
    output_dir = "src/web_scrapers/output_data"
    pages_for_later = []

    for file in os.listdir(output_dir):
        file_path = os.path.join(output_dir, file)
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
            pathlib.Path(file_path + ".txt").write_text(chr(12).join(page_texts), encoding='utf-8')

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

def read_texts():
    pages = []
    output_dir = "src/web_scrapers/output_data"
    for file in os.listdir(output_dir):
        if file.lower().endswith('.txt'):
            file_path = os.path.join(output_dir, file)
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
