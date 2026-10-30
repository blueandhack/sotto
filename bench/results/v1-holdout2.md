# keepmum Phase 0 benchmark — 20261025-152645

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.20.2, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 62 spans / 723–7854 tokens; negatives 15 records / 0 spans / 26–168 tokens; pii 40 records / 120 spans / 29–72 tokens; secrets 50 records / 65 spans / 24–1068 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.979 | 0.979 | 0.987 | 0.983 | 2/15 (0.13) | 0.0 ms | 4.0 ms | 7.9 ms | 0.0 s | 28 MB | ❌ ❌ ✅ |
| `rules+pf-8bit` | 1.000 | 1.000 | 0.797 | 0.887 | 9/15 (0.60) | 7.0 ms | 81.3 ms | 197 ms | 2.8 s | 2,540 MB | ✅ ❌ ✅ |
| `rules+pf-8bit:pii` | 1.000 | 1.000 | 0.797 | 0.887 | 9/15 (0.60) | 7.0 ms | 82.0 ms | 197 ms | 2.8 s | 2,540 MB | ✅ ❌ ✅ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules+pf-8bit:pii` | 1.000 | 1.000 | 0.869 | 0.930 | 9/15 (0.60) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.98 / 0.99 | 0.67 / 0.89 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-8bit` | 1.00 / 0.80 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-8bit:pii` | 1.00 / 0.80 | 1.00 / 0.80 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.80 | 1.00 / 0.80 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.0 / 0.3 ms | 0.9 / 1.4 ms | 3.9 / 4.0 ms | 7.5 / 7.9 ms | 1,023,293 | 0.0 s | 0.1 ms | — |
| `rules+pf-8bit` | 7.0 / 13.6 ms | 20.5 / 26.2 ms | 76.7 / 81.3 ms | 192 / 197 ms | 33,751 | 2.7 s | 24.3 ms | 2,234 MB |
| `rules+pf-8bit:pii` | 7.0 / 13.7 ms | 20.7 / 26.5 ms | 77.0 / 82.0 ms | 191 / 197 ms | 33,708 | 2.8 s | 24.9 ms | 2,234 MB |

## Missed secrets

- `rules`: 2 missed: secret-046 (contextual, hex) 4f1a… (32 chars); secret-047 (contextual, prose-password) Hkq7… (17 chars)
- `rules+pf-8bit`: 0 missed
- `rules+pf-8bit:pii`: 0 missed

## Flagged hard negatives (secrets scope)

- `rules`: 3 spans: neg-003 rules:entropy ch_3… (27 chars); neg-003 rules:entropy pi_3… (27 chars); neg-010 rules:entropy 8d2f… (20 chars)
- `rules+pf-8bit`: 11 spans: neg-001 pf-mlx-8bit 0x7f… (14 chars); neg-002 pf-mlx-8bit subs… (65 chars); neg-003 rules:entropy ch_3… (27 chars); neg-003 rules:entropy|pf-mlx-8bit pi_3… (27 chars); neg-007 pf-mlx-8bit 1f2e… (16 chars); neg-008 pf-mlx-8bit 7d9f… (16 chars); neg-009 pf-mlx-8bit v1-d… (40 chars); neg-010 rules:entropy|pf-mlx-8bit 8d2f… (20 chars); neg-010 pf-mlx-8bit 01JB… (26 chars); neg-012 pf-mlx-8bit chec… (23 chars); neg-013 pf-mlx-8bit 9d1c… (36 chars)
- `rules+pf-8bit:pii`: 11 spans: neg-001 pf-mlx-8bit 0x7f… (14 chars); neg-002 pf-mlx-8bit subs… (65 chars); neg-003 rules:entropy ch_3… (27 chars); neg-003 rules:entropy|pf-mlx-8bit pi_3… (27 chars); neg-007 pf-mlx-8bit 1f2e… (16 chars); neg-008 pf-mlx-8bit 7d9f… (16 chars); neg-009 pf-mlx-8bit v1-d… (40 chars); neg-010 rules:entropy|pf-mlx-8bit 8d2f… (20 chars); neg-010 pf-mlx-8bit 01JB… (26 chars); neg-012 pf-mlx-8bit chec… (23 chars); neg-013 pf-mlx-8bit 9d1c… (36 chars)
