# keepmum Phase 0 benchmark — 20261026-001310

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.20.2, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 70 spans / 843–7939 tokens; negatives 15 records / 0 spans / 25–109 tokens; pii 40 records / 120 spans / 29–76 tokens; secrets 50 records / 65 spans / 25–1034 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 1.000 | 0.989 | 0.845 | 0.916 | 3/15 (0.20) | 6.0 ms | 94.5 ms | 282 ms | 0.6 s | 29 MB | ✅ ❌ ✅ |
| `rules+pf-serve:pii` | 1.000 | 0.989 | 0.845 | 0.916 | 3/15 (0.20) | 6.3 ms | 98.0 ms | 292 ms | 0.6 s | 29 MB | ✅ ❌ ✅ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules+pf-serve:pii` | 1.000 | 0.980 | 0.900 | 0.948 | 4/15 (0.27) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 1.00 / 0.85 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve:pii` | 1.00 / 0.85 | 1.00 / 0.76 | 1.00 / 0.98 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.89 | 1.00 / 0.80 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 6.0 / 8.2 ms | 24.2 / 27.7 ms | 89.2 / 94.5 ms | 275 / 282 ms | 28,353 | 0.6 s | 5.2 ms | — |
| `rules+pf-serve:pii` | 6.3 / 8.5 ms | 24.4 / 27.9 ms | 89.4 / 98.0 ms | 273 / 292 ms | 28,068 | 0.6 s | 5.3 ms | — |

## Missed secrets

- `rules+pf-serve`: 0 missed
- `rules+pf-serve:pii`: 0 missed

## Flagged hard negatives (secrets scope)

- `rules+pf-serve`: 3 spans: neg-000 pf-serve 5d41… (36 chars); neg-009 pf-serve "d6q… (44 chars); neg-013 pf-serve 1c9e… (64 chars)
- `rules+pf-serve:pii`: 3 spans: neg-000 pf-serve 5d41… (36 chars); neg-009 pf-serve "d6q… (44 chars); neg-013 pf-serve 1c9e… (64 chars)
