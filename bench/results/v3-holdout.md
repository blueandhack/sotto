# sotto Phase 0 benchmark — 20261026-001208

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.20.2, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 62 spans / 562–7896 tokens; negatives 15 records / 0 spans / 32–141 tokens; pii 40 records / 120 spans / 29–73 tokens; secrets 50 records / 65 spans / 24–1182 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 1.000 | 1.000 | 0.782 | 0.877 | 0/15 (0.00) | 6.1 ms | 100 ms | 278 ms | 0.6 s | 29 MB | ✅ ✅ ✅ |
| `rules+pf-serve:pii` | 1.000 | 1.000 | 0.773 | 0.872 | 0/15 (0.00) | 6.0 ms | 103 ms | 284 ms | 0.6 s | 28 MB | ✅ ✅ ✅ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules+pf-serve:pii` | 1.000 | 0.968 | 0.852 | 0.920 | 2/15 (0.13) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 1.00 / 0.78 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve:pii` | 1.00 / 0.77 | 1.00 / 0.67 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.86 | 1.00 / 0.80 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 6.1 / 8.6 ms | 22.1 / 25.5 ms | 92.8 / 100 ms | 274 / 278 ms | 28,350 | 0.6 s | 5.2 ms | — |
| `rules+pf-serve:pii` | 6.0 / 10.0 ms | 22.4 / 26.3 ms | 96.5 / 103 ms | 276 / 284 ms | 27,980 | 0.6 s | 5.2 ms | — |

## Missed secrets

- `rules+pf-serve`: 0 missed
- `rules+pf-serve:pii`: 0 missed

## Flagged hard negatives (secrets scope)

- `rules+pf-serve`: 0 spans
- `rules+pf-serve:pii`: 0 spans
