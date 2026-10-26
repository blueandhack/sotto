# sotto Phase 0 benchmark — 20261026-001250

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.20.2, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 74 spans / 550–7888 tokens; negatives 15 records / 0 spans / 53–231 tokens; pii 40 records / 120 spans / 29–71 tokens; secrets 50 records / 65 spans / 24–1168 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 1.000 | 1.000 | 0.869 | 0.930 | 3/15 (0.20) | 6.0 ms | 94.6 ms | 273 ms | 0.6 s | 29 MB | ✅ ❌ ✅ |
| `rules+pf-serve:pii` | 1.000 | 1.000 | 0.860 | 0.925 | 3/15 (0.20) | 6.0 ms | 94.3 ms | 275 ms | 0.6 s | 29 MB | ✅ ❌ ✅ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules+pf-serve:pii` | 0.996 | 0.973 | 0.928 | 0.961 | 3/15 (0.20) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 1.00 / 0.87 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve:pii` | 1.00 / 0.86 | 1.00 / 1.00 | 0.98 / 1.00 | 1.00 / 0.94 | 1.00 / 1.00 | 1.00 / 0.92 | 1.00 / 1.00 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 6.0 / 8.4 ms | 23.0 / 28.2 ms | 89.4 / 94.6 ms | 269 / 273 ms | 28,929 | 0.6 s | 5.1 ms | — |
| `rules+pf-serve:pii` | 6.0 / 8.3 ms | 23.8 / 28.6 ms | 89.6 / 94.3 ms | 270 / 275 ms | 28,733 | 0.6 s | 5.2 ms | — |

## Missed secrets

- `rules+pf-serve`: 0 missed
- `rules+pf-serve:pii`: 0 missed

## Flagged hard negatives (secrets scope)

- `rules+pf-serve`: 4 spans: neg-000 pf-serve chec… (49 chars); neg-002 pf-serve sg-0… (20 chars); neg-002 pf-serve vpc-… (21 chars); neg-012 pf-serve -bxk… (29 chars)
- `rules+pf-serve:pii`: 4 spans: neg-000 pf-serve chec… (49 chars); neg-002 pf-serve sg-0… (20 chars); neg-002 pf-serve vpc-… (21 chars); neg-012 pf-serve -bxk… (29 chars)
