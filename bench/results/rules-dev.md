# sotto Phase 0 benchmark — 20261029-132543

Machine: Apple M5 Pro, 64 GB, macOS 27.2, Python 3.12.15. .

Dataset (estimated at 4 characters per token): secrets 98 records / 114 spans / 9–442 tokens; pii 46 records / 128 spans / 6–52 tokens; long 20 records / 76 spans / 948–7796 tokens; negatives 40 records / 0 spans / 23–112 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.993 | 0.993 | 1.000 | 0.996 | 0/40 (0.00) | 0.0 ms | 7.8 ms | 14.9 ms | 0.0 s | 28 MB | ✅ ✅ ✅ |
| `rules:pii` | 0.993 | 0.993 | 0.993 | 0.993 | 0/40 (0.00) | 0.0 ms | 9.1 ms | 17.1 ms | 0.0 s | 28 MB | ✅ ✅ ✅ |
| `rules+pf-serve` | 0.993 | 0.993 | 0.874 | 0.930 | 1/40 (0.03) | 5.6 ms | 243 ms | 456 ms | 0.5 s | 30 MB | ✅ ✅ ❌ |
| `rules+pf-serve:pii` | 0.993 | 0.993 | 0.868 | 0.926 | 1/40 (0.03) | 5.7 ms | 233 ms | 465 ms | 0.6 s | 30 MB | ✅ ✅ ❌ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules:pii` | 0.770 | 0.770 | 0.996 | 0.869 | 0/40 (0.00) |
| `rules+pf-serve:pii` | 0.997 | 0.994 | 0.913 | 0.953 | 3/40 (0.07) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.99 / 1.00 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules:pii` | 0.99 / 0.99 | 1.00 / 1.00 | 0.00 / — | 1.00 / 1.00 | 1.00 / 1.00 | 0.00 / — | 0.00 / — | 1.00 / 1.00 |
| `rules+pf-serve` | 0.99 / 0.87 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve:pii` | 0.99 / 0.87 | 1.00 / 0.93 | 1.00 / 0.95 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 0.82 | 1.00 / 0.57 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.0 / 0.2 ms | 1.8 / 2.2 ms | 7.0 / 7.8 ms | 14.1 / 14.9 ms | 541,874 | 0.0 s | 0.1 ms | — |
| `rules:pii` | 0.0 / 0.3 ms | 2.1 / 2.5 ms | 8.1 / 9.1 ms | 16.5 / 17.1 ms | 469,079 | 0.0 s | 0.1 ms | — |
| `rules+pf-serve` | 5.6 / 7.9 ms | 36.7 / 43.2 ms | 176 / 243 ms | 438 / 456 ms | 16,704 | 0.5 s | 5.0 ms | — |
| `rules+pf-serve:pii` | 5.7 / 8.2 ms | 36.7 / 43.2 ms | 177 / 233 ms | 445 / 465 ms | 16,539 | 0.5 s | 5.0 ms | — |

## Missed secrets

- `rules`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules:pii`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+pf-serve`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+pf-serve:pii`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)

## Flagged hard negatives (secrets scope)

- `rules`: 0 spans
- `rules:pii`: 0 spans
- `rules+pf-serve`: 1 spans: neg-039 pf-serve eyJv… (76 chars)
- `rules+pf-serve:pii`: 1 spans: neg-039 pf-serve eyJv… (76 chars)
