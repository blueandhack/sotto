# keepmum Phase 0 benchmark — 20261025-152557

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.20.2, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 70 spans / 785–7793 tokens; negatives 40 records / 0 spans / 23–273 tokens; pii 40 records / 120 spans / 29–72 tokens; secrets 50 records / 65 spans / 24–1131 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.968 | 0.968 | 1.000 | 0.984 | 0/40 (0.00) | 0.0 ms | 4.1 ms | 7.3 ms | 0.0 s | 28 MB | ❌ ✅ ✅ |
| `rules+pf-8bit` | 0.989 | 0.989 | 0.850 | 0.915 | 1/40 (0.03) | 7.3 ms | 85.8 ms | 203 ms | 3.4 s | 2,541 MB | ✅ ✅ ✅ |
| `rules+pf-8bit:pii` | 0.989 | 0.989 | 0.841 | 0.909 | 1/40 (0.03) | 7.2 ms | 91.1 ms | 208 ms | 2.7 s | 2,540 MB | ✅ ✅ ✅ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit:pii` | 0.996 | 0.988 | 0.893 | 0.942 | 3/40 (0.07) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.97 / 1.00 | 0.67 / 1.00 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-8bit` | 0.99 / 0.85 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-8bit:pii` | 0.99 / 0.84 | 1.00 / 0.93 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.82 | 1.00 / 0.57 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.0 / 0.3 ms | 0.9 / 1.8 ms | 3.7 / 4.1 ms | 7.2 / 7.3 ms | 1,162,935 | 0.0 s | 0.1 ms | — |
| `rules+pf-8bit` | 7.3 / 14.2 ms | 20.9 / 30.5 ms | 81.9 / 85.8 ms | 183 / 203 ms | 31,881 | 3.4 s | 25.9 ms | 2,233 MB |
| `rules+pf-8bit:pii` | 7.2 / 13.9 ms | 22.1 / 31.3 ms | 80.6 / 91.1 ms | 185 / 208 ms | 31,913 | 2.7 s | 27.0 ms | 2,233 MB |

## Missed secrets

- `rules`: 3 missed: secret-046 (contextual, hex) b871… (32 chars); secret-047 (contextual, prose-password) WAVC… (16 chars); secret-048 (contextual, cli-flag) m1v9… (40 chars)
- `rules+pf-8bit`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+pf-8bit:pii`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)

## Flagged hard negatives (secrets scope)

- `rules`: 0 spans
- `rules+pf-8bit`: 1 spans: neg-039 pf-mlx-8bit eyJv… (76 chars)
- `rules+pf-8bit:pii`: 1 spans: neg-039 pf-mlx-8bit eyJv… (76 chars)
