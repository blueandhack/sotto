# sotto Phase 0 benchmark — 20261025-234549

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.20.2, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 70 spans / 785–7793 tokens; negatives 40 records / 0 spans / 23–273 tokens; pii 40 records / 120 spans / 29–72 tokens; secrets 50 records / 65 spans / 24–1131 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit` | 0.989 | 0.989 | 0.850 | 0.915 | 1/40 (0.03) | 7.2 ms | 86.3 ms | 272 ms | 2.9 s | 2,542 MB | ✅ ✅ ✅ |
| `rules+pf-serve` | 0.989 | 0.989 | 0.867 | 0.924 | 1/40 (0.03) | 6.4 ms | 110 ms | 298 ms | 0.6 s | 29 MB | ✅ ✅ ✅ |
| `rules+pf-8bit:pii` | 0.989 | 0.989 | 0.841 | 0.909 | 1/40 (0.03) | 7.3 ms | 90.4 ms | 215 ms | 3.2 s | 2,541 MB | ✅ ✅ ✅ |
| `rules+pf-serve:pii` | 0.989 | 0.989 | 0.857 | 0.919 | 1/40 (0.03) | 6.1 ms | 105 ms | 271 ms | 0.7 s | 29 MB | ✅ ✅ ✅ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit:pii` | 0.996 | 0.980 | 0.893 | 0.942 | 3/40 (0.07) |
| `rules+pf-serve:pii` | 0.996 | 0.980 | 0.903 | 0.947 | 3/40 (0.07) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit` | 0.99 / 0.85 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve` | 0.99 / 0.87 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-8bit:pii` | 0.99 / 0.84 | 1.00 / 0.93 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.82 | 1.00 / 0.57 | 1.00 / 1.00 |
| `rules+pf-serve:pii` | 0.99 / 0.86 | 1.00 / 1.00 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.82 | 1.00 / 0.57 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit` | 7.2 / 15.1 ms | 20.8 / 28.5 ms | 79.3 / 86.3 ms | 187 / 272 ms | 29,149 | 2.9 s | 22.2 ms | 2,233 MB |
| `rules+pf-serve` | 6.4 / 10.5 ms | 23.1 / 29.0 ms | 92.8 / 110 ms | 269 / 298 ms | 26,854 | 0.6 s | 5.2 ms | — |
| `rules+pf-8bit:pii` | 7.3 / 14.4 ms | 21.1 / 29.1 ms | 84.1 / 90.4 ms | 189 / 215 ms | 30,583 | 3.1 s | 21.9 ms | 2,233 MB |
| `rules+pf-serve:pii` | 6.1 / 8.4 ms | 23.5 / 29.4 ms | 93.1 / 105 ms | 267 / 271 ms | 27,891 | 0.6 s | 5.1 ms | — |

## Missed secrets

- `rules+pf-8bit`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+pf-serve`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+pf-8bit:pii`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+pf-serve:pii`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)

## Flagged hard negatives (secrets scope)

- `rules+pf-8bit`: 1 spans: neg-039 pf-mlx-8bit eyJv… (76 chars)
- `rules+pf-serve`: 1 spans: neg-039 pf-serve eyJv… (76 chars)
- `rules+pf-8bit:pii`: 1 spans: neg-039 pf-mlx-8bit eyJv… (76 chars)
- `rules+pf-serve:pii`: 1 spans: neg-039 pf-serve eyJv… (76 chars)
