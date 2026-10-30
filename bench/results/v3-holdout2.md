# keepmum Phase 0 benchmark — 20261026-001229

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.20.2, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 62 spans / 723–7854 tokens; negatives 15 records / 0 spans / 26–168 tokens; pii 40 records / 120 spans / 29–72 tokens; secrets 50 records / 65 spans / 24–1068 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 1.000 | 1.000 | 0.803 | 0.891 | 9/15 (0.60) | 6.1 ms | 103 ms | 275 ms | 0.6 s | 29 MB | ✅ ❌ ✅ |
| `rules+pf-serve:pii` | 1.000 | 1.000 | 0.803 | 0.891 | 9/15 (0.60) | 6.1 ms | 102 ms | 281 ms | 0.6 s | 28 MB | ✅ ❌ ✅ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules+pf-serve:pii` | 1.000 | 0.988 | 0.879 | 0.935 | 9/15 (0.60) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 1.00 / 0.80 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve:pii` | 1.00 / 0.80 | 1.00 / 0.80 | 1.00 / 0.98 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.80 | 1.00 / 0.80 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules+pf-serve` | 6.1 / 8.8 ms | 21.7 / 28.5 ms | 92.6 / 103 ms | 270 / 275 ms | 28,429 | 0.6 s | 5.3 ms | — |
| `rules+pf-serve:pii` | 6.1 / 8.6 ms | 21.9 / 28.7 ms | 92.7 / 102 ms | 269 / 281 ms | 28,508 | 0.6 s | 5.2 ms | — |

## Missed secrets

- `rules+pf-serve`: 0 missed
- `rules+pf-serve:pii`: 0 missed

## Flagged hard negatives (secrets scope)

- `rules+pf-serve`: 11 spans: neg-001 pf-serve 0x7f… (14 chars); neg-002 pf-serve subs… (50 chars); neg-003 rules:entropy ch_3… (27 chars); neg-003 rules:entropy|pf-serve pi_3… (27 chars); neg-007 pf-serve 1f2e… (16 chars); neg-008 pf-serve 7d9f… (16 chars); neg-009 pf-serve v1-d… (40 chars); neg-010 rules:entropy|pf-serve 8d2f… (20 chars); neg-010 pf-serve 01JB… (26 chars); neg-012 pf-serve chec… (23 chars); neg-013 pf-serve 9d1c… (36 chars)
- `rules+pf-serve:pii`: 11 spans: neg-001 pf-serve 0x7f… (14 chars); neg-002 pf-serve subs… (50 chars); neg-003 rules:entropy ch_3… (27 chars); neg-003 rules:entropy|pf-serve pi_3… (27 chars); neg-007 pf-serve 1f2e… (16 chars); neg-008 pf-serve 7d9f… (16 chars); neg-009 pf-serve v1-d… (40 chars); neg-010 rules:entropy|pf-serve 8d2f… (20 chars); neg-010 pf-serve 01JB… (26 chars); neg-012 pf-serve chec… (23 chars); neg-013 pf-serve 9d1c… (36 chars)
