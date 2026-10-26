# sotto Phase 0 benchmark — 20261026-001146

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.20.2, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 70 spans / 785–7793 tokens; negatives 40 records / 0 spans / 23–273 tokens; pii 40 records / 120 spans / 29–72 tokens; secrets 50 records / 65 spans / 24–1131 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 0.989 | 0.989 | 0.867 | 0.924 | 1/40 (0.03) | 6.1 ms | 102 ms | 295 ms | 0.6 s | 28 MB | ✅ ✅ ✅ |
| `rules+pf-serve:pii` | 0.989 | 0.989 | 0.857 | 0.919 | 1/40 (0.03) | 6.1 ms | 102 ms | 287 ms | 0.6 s | 29 MB | ✅ ✅ ✅ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules+pf-serve:pii` | 0.996 | 0.980 | 0.903 | 0.947 | 3/40 (0.07) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 0.99 / 0.87 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve:pii` | 0.99 / 0.86 | 1.00 / 1.00 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.82 | 1.00 / 0.57 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 6.1 / 8.5 ms | 24.1 / 29.3 ms | 95.5 / 102 ms | 271 / 295 ms | 27,492 | 0.6 s | 5.1 ms | — |
| `rules+pf-serve:pii` | 6.1 / 8.8 ms | 23.8 / 29.7 ms | 95.1 / 102 ms | 279 / 287 ms | 27,204 | 0.6 s | 5.3 ms | — |

## Missed secrets

- `rules+pf-serve`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+pf-serve:pii`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)

## Flagged hard negatives (secrets scope)

- `rules+pf-serve`: 1 spans: neg-039 pf-serve eyJv… (76 chars)
- `rules+pf-serve:pii`: 1 spans: neg-039 pf-serve eyJv… (76 chars)
