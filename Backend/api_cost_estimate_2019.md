# OpenAI API Cost Estimate

Generated: 2026-05-07T19:28:21.129269+00:00

Input directory: `/Users/braylonparker/Combined/Combined/Backend/src/web_scrapers/output_data/2019`

Pricing source: https://openai.com/api/pricing/

## Corpus Inventory

| Metric | Value |
| --- | ---: |
| Files scanned | 18 |
| Raw bytes | 5,597,318,374 |
| Raw GiB | 5.21 |
| Pages | 45,131 |
| Pages with extractable text | 44,548 |
| Empty/scanned pages | 583 |
| Keyword-filtered pages sent to model | 8,969 |
| Extracted text characters | 98,773,710 |
| Extracted text tokens | 31,693,954 |

## Assumptions

| Setting | Value |
| --- | --- |
| Model | `gpt-5.4-mini` |
| Token counting | tiktoken encoding for gpt-5.4-mini |
| Keyword filter enabled | True |
| Prompt overhead per request | 500 tokens |
| Text analyzed per page | First 1,600 chars, split into 800-char chunks |
| Expected second-pass rate | 75% |
| Expected output per request | 120 tokens |
| Upper output per request | 200 tokens |
| Input price | $0.7500 / 1M tokens |
| Output price | $4.5000 / 1M tokens |
| Batch API multiplier | 50% of standard cost |

## Projected API Usage

| Scenario | Input Tokens | Output Tokens | Requests | Standard Cost | Batch Cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| Expected | 10,305,288 | 1,823,550 | 15,196 | $15.93 | $7.97 |
| Conservative Upper | 11,682,299 | 3,454,400 | 17,272 | $24.31 | $12.15 |

## Observed Dashboard Calibration

OpenAI dashboard screenshots captured on 2026-05-07 show 11,486 Responses/Chat Completions requests, 5,846,000 input tokens, and $9.85 total spend over the visible usage window.

| Calibration | Value |
| --- | ---: |
| Observed spend per request | $0.000858 |
| Observed input tokens per request | 509 |
| Estimator expected spend per request | $0.001048 |
| Estimator expected input tokens per request | 678 |
| Projected cost if scaled by observed requests | $13.03 |
| Projected cost if scaled by observed input tokens | $17.36 |

This observed usage lands close to the estimator's expected $15.93 standard-cost projection. The screenshot data is useful as a real-world sanity check, but it does not replace the token projection because the dashboard image does not show output-token volume or model-level price breakdown.

Dashboard evidence preserved:

- `Backend/proof_assets/openai_usage_requests_tokens_2026-05-07.png`
- `Backend/proof_assets/openai_usage_spend_2026-05-07.png`

## How To Present This Estimate

This estimate is based on local text extraction and token projection, not raw PDF size alone. The strongest proof is to pair it with a small paid sample run and compare the API-reported `input_tokens` and `output_tokens` against this projection.

> Warning: some pages had no extractable text. If these are scanned PDFs, OCR must be run before this estimate reflects the full corpus.
