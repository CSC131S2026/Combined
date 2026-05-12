"""
Estimate OpenAI API cost for a PDF/text corpus before running analysis.

This is intentionally a dry-run estimator: it extracts/counts text locally,
applies the same broad conflict keyword gate used by the OpenAI analyzer, and
projects token spend from documented model prices and explicit assumptions.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pymupdf


PRICE_SOURCE_URL = "https://openai.com/api/pricing/"
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_INPUT_PRICE_PER_MILLION = 0.75
DEFAULT_OUTPUT_PRICE_PER_MILLION = 4.50
DEFAULT_BATCH_DISCOUNT = 0.50
DEFAULT_CHARS_PER_TOKEN = 4.0
DEFAULT_CHUNK_CHARS = 800
DEFAULT_MAX_CHARS_PER_PAGE = 1600
DEFAULT_PROMPT_OVERHEAD_TOKENS = 500
DEFAULT_EXPECTED_OUTPUT_TOKENS = 120
DEFAULT_MAX_OUTPUT_TOKENS = 200
DEFAULT_SECOND_PASS_RATE = 0.75


HIGH_SIGNAL = [
    "financial interest",
    "conflict of interest",
    "recuse",
    "recusal",
    "board member",
    "ownership interest",
    "disclosure",
    "disclose",
    "spouse",
    "domestic partner",
]

LOW_SIGNAL = [
    "contract",
    "vendor",
    "bid",
    "grant",
    "donation",
    "family",
    "partner",
    "ownership",
    "consultant",
    "conflict",
    "interest",
]


def has_conflict_keywords(text: str) -> bool:
    """Match the analyzer's coarse pre-filter: one high signal or two low signals."""
    text_lower = (text or "").lower()
    if any(keyword in text_lower for keyword in HIGH_SIGNAL):
        return True
    return sum(1 for keyword in LOW_SIGNAL if keyword in text_lower) >= 2


def _load_tokenizer(model: str):
    try:
        import tiktoken  # type: ignore
    except Exception:
        return None

    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        pass

    # Some tiktoken installs lazily fetch encoding data the first time an
    # encoding is requested. Estimation must still work offline, so failures
    # here intentionally fall back to the documented character approximation.
    for encoding_name in ("o200k_base", "cl100k_base"):
        try:
            return tiktoken.get_encoding(encoding_name)
        except Exception:
            continue
    return None


class TokenCounter:
    """Token counter that uses tiktoken when available, else a documented estimate."""

    def __init__(self, model: str, chars_per_token: float = DEFAULT_CHARS_PER_TOKEN):
        self.model = model
        self.chars_per_token = chars_per_token
        self._encoding = _load_tokenizer(model)

    @property
    def method(self) -> str:
        if self._encoding is not None:
            return f"tiktoken encoding for {self.model}"
        return f"character estimate: ceil(chars / {self.chars_per_token:g})"

    def count(self, text: str) -> int:
        text = text or ""
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        if not text:
            return 0
        return math.ceil(len(text) / self.chars_per_token)


@dataclass
class FileEstimate:
    path: str
    bytes: int = 0
    pages: int = 0
    text_pages: int = 0
    empty_pages: int = 0
    keyword_pages: int = 0
    total_text_chars: int = 0
    total_text_tokens: int = 0
    expected_input_tokens: float = 0.0
    expected_output_tokens: float = 0.0
    upper_input_tokens: int = 0
    upper_output_tokens: int = 0
    expected_requests: float = 0.0
    upper_requests: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class CorpusEstimate:
    files: list[FileEstimate]
    model: str
    token_method: str
    input_price_per_million: float
    output_price_per_million: float
    batch_discount: float
    prompt_overhead_tokens: int
    expected_output_tokens_per_request: int
    max_output_tokens_per_request: int
    second_pass_rate: float
    chunk_chars: int
    max_chars_per_page: int
    keyword_filter_enabled: bool
    generated_at: str = field(default_factory=lambda: _dt.datetime.now(_dt.timezone.utc).isoformat())

    def total(self, attr: str):
        return sum(getattr(file_estimate, attr) for file_estimate in self.files)

    @property
    def standard_expected_cost(self) -> float:
        return cost_for_tokens(
            self.total("expected_input_tokens"),
            self.total("expected_output_tokens"),
            self.input_price_per_million,
            self.output_price_per_million,
        )

    @property
    def standard_upper_cost(self) -> float:
        return cost_for_tokens(
            self.total("upper_input_tokens"),
            self.total("upper_output_tokens"),
            self.input_price_per_million,
            self.output_price_per_million,
        )

    @property
    def batch_expected_cost(self) -> float:
        return self.standard_expected_cost * self.batch_discount

    @property
    def batch_upper_cost(self) -> float:
        return self.standard_upper_cost * self.batch_discount


def cost_for_tokens(
    input_tokens: float,
    output_tokens: float,
    input_price_per_million: float,
    output_price_per_million: float,
) -> float:
    return (
        (input_tokens / 1_000_000) * input_price_per_million
        + (output_tokens / 1_000_000) * output_price_per_million
    )


def _iter_input_files(input_dir: Path, include_text: bool) -> list[Path]:
    suffixes = {".pdf"}
    if include_text:
        suffixes.update({".txt", ".text"})
    return sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes
    )


def _page_texts_from_pdf(path: Path) -> Iterable[str]:
    with pymupdf.open(path) as doc:
        for page in doc:
            yield page.get_text()


def _page_texts_from_text_file(path: Path) -> Iterable[str]:
    yield from path.read_text(encoding="utf-8", errors="ignore").split(chr(12))


def _estimate_text_page(
    text: str,
    token_counter: TokenCounter,
    *,
    keyword_filter_enabled: bool,
    chunk_chars: int,
    max_chars_per_page: int,
    prompt_overhead_tokens: int,
    expected_output_tokens: int,
    max_output_tokens: int,
    second_pass_rate: float,
) -> dict:
    page_text = (text or "").strip()
    text_tokens = token_counter.count(page_text)
    keyword_match = (not keyword_filter_enabled) or has_conflict_keywords(page_text)

    result = {
        "text_chars": len(page_text),
        "text_tokens": text_tokens,
        "has_text": bool(page_text),
        "keyword_match": keyword_match if page_text else False,
        "expected_input_tokens": 0.0,
        "expected_output_tokens": 0.0,
        "upper_input_tokens": 0,
        "upper_output_tokens": 0,
        "expected_requests": 0.0,
        "upper_requests": 0,
    }

    if not page_text or not keyword_match:
        return result

    analysis_text = page_text[:max_chars_per_page]
    chunks = [
        analysis_text[index:index + chunk_chars]
        for index in range(0, len(analysis_text), chunk_chars)
        if analysis_text[index:index + chunk_chars].strip()
    ]
    chunks = chunks[:2]
    if not chunks:
        return result

    first_input = token_counter.count(chunks[0]) + prompt_overhead_tokens
    second_input = (
        token_counter.count(chunks[1]) + prompt_overhead_tokens
        if len(chunks) > 1
        else 0
    )
    second_weight = second_pass_rate if second_input else 0.0

    result["expected_input_tokens"] = first_input + second_weight * second_input
    result["expected_output_tokens"] = expected_output_tokens * (1.0 + second_weight)
    result["upper_input_tokens"] = first_input + second_input
    result["upper_output_tokens"] = max_output_tokens * len(chunks)
    result["expected_requests"] = 1.0 + second_weight
    result["upper_requests"] = len(chunks)
    return result


def estimate_file(
    path: Path,
    token_counter: TokenCounter,
    *,
    keyword_filter_enabled: bool = True,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    max_chars_per_page: int = DEFAULT_MAX_CHARS_PER_PAGE,
    prompt_overhead_tokens: int = DEFAULT_PROMPT_OVERHEAD_TOKENS,
    expected_output_tokens: int = DEFAULT_EXPECTED_OUTPUT_TOKENS,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    second_pass_rate: float = DEFAULT_SECOND_PASS_RATE,
) -> FileEstimate:
    estimate = FileEstimate(path=str(path), bytes=path.stat().st_size if path.exists() else 0)

    if path.suffix.lower() == ".pdf":
        page_iter = _page_texts_from_pdf(path)
    else:
        page_iter = _page_texts_from_text_file(path)

    try:
        for page_text in page_iter:
            estimate.pages += 1
            page_estimate = _estimate_text_page(
                page_text,
                token_counter,
                keyword_filter_enabled=keyword_filter_enabled,
                chunk_chars=chunk_chars,
                max_chars_per_page=max_chars_per_page,
                prompt_overhead_tokens=prompt_overhead_tokens,
                expected_output_tokens=expected_output_tokens,
                max_output_tokens=max_output_tokens,
                second_pass_rate=second_pass_rate,
            )
            estimate.total_text_chars += page_estimate["text_chars"]
            estimate.total_text_tokens += page_estimate["text_tokens"]
            estimate.expected_input_tokens += page_estimate["expected_input_tokens"]
            estimate.expected_output_tokens += page_estimate["expected_output_tokens"]
            estimate.upper_input_tokens += page_estimate["upper_input_tokens"]
            estimate.upper_output_tokens += page_estimate["upper_output_tokens"]
            estimate.expected_requests += page_estimate["expected_requests"]
            estimate.upper_requests += page_estimate["upper_requests"]

            if page_estimate["has_text"]:
                estimate.text_pages += 1
            else:
                estimate.empty_pages += 1
            if page_estimate["keyword_match"]:
                estimate.keyword_pages += 1
    except Exception as exc:  # noqa: BLE001
        estimate.errors.append(str(exc))

    return estimate


def estimate_corpus(
    input_dir: Path,
    *,
    model: str = DEFAULT_MODEL,
    include_text: bool = False,
    keyword_filter_enabled: bool = True,
    max_files: int | None = None,
    input_price_per_million: float = DEFAULT_INPUT_PRICE_PER_MILLION,
    output_price_per_million: float = DEFAULT_OUTPUT_PRICE_PER_MILLION,
    batch_discount: float = DEFAULT_BATCH_DISCOUNT,
    chars_per_token: float = DEFAULT_CHARS_PER_TOKEN,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    max_chars_per_page: int = DEFAULT_MAX_CHARS_PER_PAGE,
    prompt_overhead_tokens: int = DEFAULT_PROMPT_OVERHEAD_TOKENS,
    expected_output_tokens: int = DEFAULT_EXPECTED_OUTPUT_TOKENS,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    second_pass_rate: float = DEFAULT_SECOND_PASS_RATE,
) -> CorpusEstimate:
    token_counter = TokenCounter(model, chars_per_token=chars_per_token)
    files = _iter_input_files(input_dir, include_text=include_text)
    if max_files is not None:
        files = files[:max_files]

    file_estimates = [
        estimate_file(
            path,
            token_counter,
            keyword_filter_enabled=keyword_filter_enabled,
            chunk_chars=chunk_chars,
            max_chars_per_page=max_chars_per_page,
            prompt_overhead_tokens=prompt_overhead_tokens,
            expected_output_tokens=expected_output_tokens,
            max_output_tokens=max_output_tokens,
            second_pass_rate=second_pass_rate,
        )
        for path in files
    ]

    return CorpusEstimate(
        files=file_estimates,
        model=model,
        token_method=token_counter.method,
        input_price_per_million=input_price_per_million,
        output_price_per_million=output_price_per_million,
        batch_discount=batch_discount,
        prompt_overhead_tokens=prompt_overhead_tokens,
        expected_output_tokens_per_request=expected_output_tokens,
        max_output_tokens_per_request=max_output_tokens,
        second_pass_rate=second_pass_rate,
        chunk_chars=chunk_chars,
        max_chars_per_page=max_chars_per_page,
        keyword_filter_enabled=keyword_filter_enabled,
    )


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _intish(value: float) -> str:
    return f"{round(value):,}"


def build_markdown_report(estimate: CorpusEstimate, input_dir: Path) -> str:
    total_bytes = estimate.total("bytes")
    total_gib = total_bytes / (1024 ** 3) if total_bytes else 0
    warning = ""
    if estimate.total("empty_pages"):
        warning = (
            "\n\n> Warning: some pages had no extractable text. If these are scanned PDFs, "
            "OCR must be run before this estimate reflects the full corpus."
        )

    return f"""# OpenAI API Cost Estimate

Generated: {estimate.generated_at}

Input directory: `{input_dir}`

Pricing source: {PRICE_SOURCE_URL}

## Corpus Inventory

| Metric | Value |
| --- | ---: |
| Files scanned | {len(estimate.files):,} |
| Raw bytes | {total_bytes:,} |
| Raw GiB | {total_gib:,.2f} |
| Pages | {estimate.total("pages"):,} |
| Pages with extractable text | {estimate.total("text_pages"):,} |
| Empty/scanned pages | {estimate.total("empty_pages"):,} |
| Keyword-filtered pages sent to model | {estimate.total("keyword_pages"):,} |
| Extracted text characters | {estimate.total("total_text_chars"):,} |
| Extracted text tokens | {estimate.total("total_text_tokens"):,} |

## Assumptions

| Setting | Value |
| --- | --- |
| Model | `{estimate.model}` |
| Token counting | {estimate.token_method} |
| Keyword filter enabled | {estimate.keyword_filter_enabled} |
| Prompt overhead per request | {estimate.prompt_overhead_tokens:,} tokens |
| Text analyzed per page | First {estimate.max_chars_per_page:,} chars, split into {estimate.chunk_chars:,}-char chunks |
| Expected second-pass rate | {estimate.second_pass_rate:.0%} |
| Expected output per request | {estimate.expected_output_tokens_per_request:,} tokens |
| Upper output per request | {estimate.max_output_tokens_per_request:,} tokens |
| Input price | ${estimate.input_price_per_million:,.4f} / 1M tokens |
| Output price | ${estimate.output_price_per_million:,.4f} / 1M tokens |
| Batch API multiplier | {estimate.batch_discount:.0%} of standard cost |

## Projected API Usage

| Scenario | Input Tokens | Output Tokens | Requests | Standard Cost | Batch Cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| Expected | {_intish(estimate.total("expected_input_tokens"))} | {_intish(estimate.total("expected_output_tokens"))} | {_intish(estimate.total("expected_requests"))} | {_money(estimate.standard_expected_cost)} | {_money(estimate.batch_expected_cost)} |
| Conservative Upper | {estimate.total("upper_input_tokens"):,} | {estimate.total("upper_output_tokens"):,} | {estimate.total("upper_requests"):,} | {_money(estimate.standard_upper_cost)} | {_money(estimate.batch_upper_cost)} |

## How To Present This Estimate

This estimate is based on local text extraction and token projection, not raw PDF size alone. The strongest proof is to pair it with a small paid sample run and compare the API-reported `input_tokens` and `output_tokens` against this projection.
{warning}
"""


def write_csv_report(estimate: CorpusEstimate, output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "path",
        "bytes",
        "pages",
        "text_pages",
        "empty_pages",
        "keyword_pages",
        "total_text_chars",
        "total_text_tokens",
        "expected_input_tokens",
        "expected_output_tokens",
        "upper_input_tokens",
        "upper_output_tokens",
        "expected_requests",
        "upper_requests",
        "errors",
    ]
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for file_estimate in estimate.files:
            writer.writerow({
                "path": file_estimate.path,
                "bytes": file_estimate.bytes,
                "pages": file_estimate.pages,
                "text_pages": file_estimate.text_pages,
                "empty_pages": file_estimate.empty_pages,
                "keyword_pages": file_estimate.keyword_pages,
                "total_text_chars": file_estimate.total_text_chars,
                "total_text_tokens": file_estimate.total_text_tokens,
                "expected_input_tokens": round(file_estimate.expected_input_tokens),
                "expected_output_tokens": round(file_estimate.expected_output_tokens),
                "upper_input_tokens": file_estimate.upper_input_tokens,
                "upper_output_tokens": file_estimate.upper_output_tokens,
                "expected_requests": round(file_estimate.expected_requests, 2),
                "upper_requests": file_estimate.upper_requests,
                "errors": " | ".join(file_estimate.errors),
            })


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Estimate OpenAI token/cost usage for conflict analysis over PDFs.",
    )
    parser.add_argument("input_dir", type=Path, help="Directory containing PDFs, or text caches with --include-text.")
    parser.add_argument("--output-md", type=Path, default=Path("api_cost_estimate.md"))
    parser.add_argument("--output-csv", type=Path, default=Path("api_cost_estimate_by_file.csv"))
    parser.add_argument("--include-text", action="store_true", help="Also scan .txt/.text files as pre-extracted pages.")
    parser.add_argument("--include-all-pages", action="store_true", help="Estimate sending every text page, not only keyword matches.")
    parser.add_argument("--max-files", type=int, default=None, help="Limit files for a representative sample run.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--input-price-per-million", type=float, default=DEFAULT_INPUT_PRICE_PER_MILLION)
    parser.add_argument("--output-price-per-million", type=float, default=DEFAULT_OUTPUT_PRICE_PER_MILLION)
    parser.add_argument("--batch-discount", type=float, default=DEFAULT_BATCH_DISCOUNT)
    parser.add_argument("--chars-per-token", type=float, default=DEFAULT_CHARS_PER_TOKEN)
    parser.add_argument("--chunk-chars", type=int, default=DEFAULT_CHUNK_CHARS)
    parser.add_argument("--max-chars-per-page", type=int, default=DEFAULT_MAX_CHARS_PER_PAGE)
    parser.add_argument("--prompt-overhead-tokens", type=int, default=DEFAULT_PROMPT_OVERHEAD_TOKENS)
    parser.add_argument("--expected-output-tokens", type=int, default=DEFAULT_EXPECTED_OUTPUT_TOKENS)
    parser.add_argument("--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    parser.add_argument("--second-pass-rate", type=float, default=DEFAULT_SECOND_PASS_RATE)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if not args.input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    estimate = estimate_corpus(
        args.input_dir,
        model=args.model,
        include_text=args.include_text,
        keyword_filter_enabled=not args.include_all_pages,
        max_files=args.max_files,
        input_price_per_million=args.input_price_per_million,
        output_price_per_million=args.output_price_per_million,
        batch_discount=args.batch_discount,
        chars_per_token=args.chars_per_token,
        chunk_chars=args.chunk_chars,
        max_chars_per_page=args.max_chars_per_page,
        prompt_overhead_tokens=args.prompt_overhead_tokens,
        expected_output_tokens=args.expected_output_tokens,
        max_output_tokens=args.max_output_tokens,
        second_pass_rate=args.second_pass_rate,
    )
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(build_markdown_report(estimate, args.input_dir.resolve()), encoding="utf-8")
    write_csv_report(estimate, args.output_csv)

    print(f"Wrote Markdown estimate: {args.output_md}")
    print(f"Wrote per-file CSV: {args.output_csv}")
    print(f"Expected standard cost: {_money(estimate.standard_expected_cost)}")
    print(f"Conservative upper standard cost: {_money(estimate.standard_upper_cost)}")
    print(f"Expected Batch API cost: {_money(estimate.batch_expected_cost)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
