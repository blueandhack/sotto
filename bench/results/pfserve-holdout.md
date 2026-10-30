# keepmum Phase 0 benchmark — 20261025-234637

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.20.2, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 62 spans / 562–7896 tokens; negatives 15 records / 0 spans / 32–141 tokens; pii 40 records / 120 spans / 29–73 tokens; secrets 50 records / 65 spans / 24–1182 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit` | 1.000 | 1.000 | 0.769 | 0.869 | 0/15 (0.00) | 6.9 ms | 86.4 ms | 206 ms | 3.1 s | 2,541 MB | ✅ ✅ ✅ |
| `rules+pf-serve` | 1.000 | 1.000 | 0.782 | 0.877 | 0/15 (0.00) | 6.0 ms | 99.4 ms | 283 ms | 0.6 s | 28 MB | ✅ ✅ ✅ |
| `rules+pf-8bit:pii` | 1.000 | 1.000 | 0.760 | 0.864 | 0/15 (0.00) | 7.0 ms | 84.1 ms | 206 ms | 2.8 s | 2,542 MB | ✅ ✅ ✅ |
| `rules+pf-serve:pii` | 1.000 | 1.000 | 0.773 | 0.872 | 0/15 (0.00) | 9.4 ms | 97.0 ms | 484 ms | 0.6 s | 28 MB | ✅ ✅ ✅ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit:pii` | 1.000 | 0.968 | 0.838 | 0.912 | 3/15 (0.20) |
| `rules+pf-serve:pii` | 1.000 | 0.968 | 0.852 | 0.920 | 2/15 (0.13) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit` | 1.00 / 0.77 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve` | 1.00 / 0.78 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-8bit:pii` | 1.00 / 0.76 | 1.00 / 0.67 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.80 | 1.00 / 0.57 | 1.00 / 1.00 |
| `rules+pf-serve:pii` | 1.00 / 0.77 | 1.00 / 0.67 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.86 | 1.00 / 0.80 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit` | 6.9 / 14.2 ms | 20.0 / 23.7 ms | 77.5 / 86.4 ms | 192 / 206 ms | 33,362 | 3.1 s | 21.6 ms | 2,249 MB |
| `rules+pf-serve` | 6.0 / 8.6 ms | 22.6 / 25.8 ms | 92.6 / 99.4 ms | 272 / 283 ms | 28,333 | 0.6 s | 5.2 ms | — |
| `rules+pf-8bit:pii` | 7.0 / 13.6 ms | 20.8 / 24.1 ms | 77.2 / 84.1 ms | 193 / 206 ms | 33,243 | 2.8 s | 25.0 ms | 2,249 MB |
| `rules+pf-serve:pii` | 9.4 / 28.0 ms | 21.8 / 25.0 ms | 91.7 / 97.0 ms | 403 / 484 ms | 20,783 | 0.6 s | 5.1 ms | — |

## Missed secrets

- `rules+pf-8bit`: 0 missed
- `rules+pf-serve`: 0 missed
- `rules+pf-8bit:pii`: 0 missed
- `rules+pf-serve:pii`: 0 missed

## Flagged hard negatives (secrets scope)

- `rules+pf-8bit`: 0 spans
- `rules+pf-serve`: 0 spans
- `rules+pf-8bit:pii`: 0 spans
- `rules+pf-serve:pii`: 0 spans
