# sotto Phase 0 benchmark — 20261029-132617

Machine: Apple M5 Pro, 64 GB, macOS 27.2, Python 3.12.15. .

Dataset (estimated at 4 characters per token): secrets 98 records / 114 spans / 9–404 tokens; pii 46 records / 128 spans / 6–52 tokens; long 20 records / 66 spans / 773–7835 tokens; negatives 15 records / 0 spans / 23–85 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.993 | 0.993 | 1.000 | 0.996 | 0/15 (0.00) | 0.0 ms | 9.3 ms | 15.9 ms | 0.0 s | 28 MB | ✅ ✅ ✅ |
| `rules:pii` | 0.993 | 0.993 | 0.993 | 0.993 | 0/15 (0.00) | 0.0 ms | 9.0 ms | 19.1 ms | 0.0 s | 28 MB | ✅ ✅ ✅ |
| `rules+pf-serve` | 1.000 | 1.000 | 0.834 | 0.910 | 1/15 (0.07) | 5.3 ms | 237 ms | 461 ms | 0.6 s | 30 MB | ✅ ❌ ❌ |
| `rules+pf-serve:pii` | 1.000 | 1.000 | 0.822 | 0.903 | 1/15 (0.07) | 5.3 ms | 233 ms | 463 ms | 0.6 s | 30 MB | ✅ ❌ ❌ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules:pii` | 0.779 | 0.779 | 0.996 | 0.874 | 0/15 (0.00) |
| `rules+pf-serve:pii` | 1.000 | 0.997 | 0.871 | 0.931 | 5/15 (0.33) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.99 / 1.00 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules:pii` | 0.99 / 0.99 | 1.00 / 1.00 | 0.00 / — | 1.00 / 1.00 | 1.00 / 1.00 | 0.00 / — | 0.00 / — | 1.00 / 1.00 |
| `rules+pf-serve` | 1.00 / 0.83 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve:pii` | 1.00 / 0.82 | 1.00 / 0.67 | 1.00 / 0.96 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 0.82 | 1.00 / 0.57 | 1.00 / 0.91 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.0 / 0.3 ms | 1.8 / 2.6 ms | 7.8 / 9.3 ms | 14.9 / 15.9 ms | 512,388 | 0.0 s | 0.1 ms | — |
| `rules:pii` | 0.0 / 0.3 ms | 2.1 / 2.8 ms | 8.7 / 9.0 ms | 16.7 / 19.1 ms | 452,321 | 0.0 s | 0.1 ms | — |
| `rules+pf-serve` | 5.3 / 8.0 ms | 36.1 / 45.7 ms | 179 / 237 ms | 437 / 461 ms | 16,637 | 0.5 s | 5.0 ms | — |
| `rules+pf-serve:pii` | 5.3 / 7.9 ms | 34.3 / 45.9 ms | 179 / 233 ms | 443 / 463 ms | 16,618 | 0.6 s | 5.0 ms | — |

## Missed secrets

- `rules`: 1 missed: secret-047 (contextual, prose-password) Bg3j… (20 chars)
- `rules:pii`: 1 missed: secret-047 (contextual, prose-password) Bg3j… (20 chars)
- `rules+pf-serve`: 0 missed
- `rules+pf-serve:pii`: 0 missed

## Flagged hard negatives (secrets scope)

- `rules`: 0 spans
- `rules:pii`: 0 spans
- `rules+pf-serve`: 1 spans: neg-004 pf-serve @db.… (29 chars)
- `rules+pf-serve:pii`: 1 spans: neg-004 pf-serve @db.… (29 chars)
