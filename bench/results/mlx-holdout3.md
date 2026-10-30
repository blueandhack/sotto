# keepmum Phase 0 benchmark — 20261026-000213

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.20.2, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 74 spans / 550–7888 tokens; negatives 15 records / 0 spans / 53–231 tokens; pii 40 records / 120 spans / 29–71 tokens; secrets 50 records / 65 spans / 24–1168 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.

> **rules+pf-serve** failed: worker exited with 1
> **rules+pf-serve:pii** failed: worker exited with 1

## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit` | 0.989 | 0.989 | 0.868 | 0.925 | 3/15 (0.20) | 8.4 ms | 196 ms | 458 ms | 3.3 s | 2,544 MB | ✅ ❌ ❌ |
| `rules+pf-8bit:pii` | 0.989 | 0.989 | 0.858 | 0.919 | 3/15 (0.20) | 8.0 ms | 92.8 ms | 222 ms | 4.4 s | 2,553 MB | ✅ ❌ ✅ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit:pii` | 0.992 | 0.969 | 0.921 | 0.955 | 3/15 (0.20) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit` | 0.99 / 0.87 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-8bit:pii` | 0.99 / 0.86 | 1.00 / 0.93 | 0.98 / 1.00 | 1.00 / 0.94 | 1.00 / 1.00 | 1.00 / 0.92 | 1.00 / 0.80 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit` | 8.4 / 16.7 ms | 24.0 / 31.3 ms | 82.4 / 196 ms | 224 / 458 ms | 26,286 | 3.3 s | 24.5 ms | 2,248 MB |
| `rules+pf-8bit:pii` | 8.0 / 16.7 ms | 24.6 / 29.3 ms | 81.4 / 92.8 ms | 208 / 222 ms | 29,136 | 4.3 s | 29.1 ms | 2,248 MB |

## Missed secrets

- `rules+pf-8bit`: 1 missed: secret-046 (contextual, hex) cc19… (32 chars)
- `rules+pf-8bit:pii`: 1 missed: secret-046 (contextual, hex) cc19… (32 chars)

## Flagged hard negatives (secrets scope)

- `rules+pf-8bit`: 4 spans: neg-000 pf-mlx-8bit @3d3… (41 chars); neg-002 pf-mlx-8bit sg-0… (20 chars); neg-002 pf-mlx-8bit vpc-… (21 chars); neg-012 pf-mlx-8bit -bxk… (29 chars)
- `rules+pf-8bit:pii`: 4 spans: neg-000 pf-mlx-8bit @3d3… (41 chars); neg-002 pf-mlx-8bit sg-0… (20 chars); neg-002 pf-mlx-8bit vpc-… (21 chars); neg-012 pf-mlx-8bit -bxk… (29 chars)
