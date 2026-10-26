# sotto Phase 0 benchmark — 20261025-144303

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.16.1, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 62 spans / 562–7896 tokens; negatives 15 records / 0 spans / 32–141 tokens; pii 40 records / 120 spans / 29–73 tokens; secrets 50 records / 65 spans / 24–1182 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `piiranha` | 0.137 | 0.095 | 1.000 | 0.241 | 0/15 (0.00) | 17.8 ms | 904 ms | 1,747 ms | 2.3 s | 1,495 MB | ❌ ✅ ❌ |
| `rules+pf:pii:rawpii` | 1.000 | 1.000 | 0.569 | 0.725 | 3/15 (0.20) | 7.4 ms | 84.7 ms | 198 ms | 2.8 s | 3,792 MB | ✅ ❌ ✅ |
| `rules+pf:pii` | 1.000 | 1.000 | 0.569 | 0.725 | 3/15 (0.20) | 7.5 ms | 84.1 ms | 198 ms | 2.8 s | 3,792 MB | ✅ ❌ ✅ |
| `rules+pf+piiranha:pii:rawpii` | 1.000 | 1.000 | 0.575 | 0.730 | 3/15 (0.20) | 24.8 ms | 959 ms | 1,952 ms | 3.4 s | 4,375 MB | ✅ ❌ ❌ |
| `rules+pf+piiranha:pii` | 1.000 | 1.000 | 0.575 | 0.730 | 3/15 (0.20) | 24.9 ms | 965 ms | 1,948 ms | 4.2 s | 4,378 MB | ✅ ❌ ❌ |
| `rules+pf+qwen:pii` | 1.000 | 1.000 | 0.569 | 0.725 | 3/15 (0.20) | 10.1 ms | 1,259 ms | 1,059 ms | 4.0 s | 5,821 MB | ✅ ❌ ❌ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `piiranha` | 0.538 | 0.368 | 0.962 | 0.690 | 0/15 (0.00) |
| `rules+pf:pii:rawpii` | 1.000 | 0.992 | 0.595 | 0.746 | 4/15 (0.27) |
| `rules+pf:pii` | 1.000 | 0.992 | 0.742 | 0.852 | 4/15 (0.27) |
| `rules+pf+piiranha:pii:rawpii` | 0.887 | 0.733 | 0.780 | 0.830 | 3/15 (0.20) |
| `rules+pf+piiranha:pii` | 0.887 | 0.733 | 0.780 | 0.830 | 3/15 (0.20) |
| `rules+pf+qwen:pii` | 1.000 | 0.992 | 0.742 | 0.852 | 4/15 (0.27) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `piiranha` | 0.14 / 1.00 | 0.33 / 1.00 | 0.62 / 1.00 | 1.00 / 0.97 | 1.00 / 1.00 | 1.00 / 0.84 | 0.00 / — | 1.00 / 1.00 |
| `rules+pf:pii:rawpii` | 1.00 / 0.57 | 1.00 / 0.17 | 1.00 / 0.85 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.80 | 1.00 / 0.29 | 1.00 / 0.36 |
| `rules+pf:pii` | 1.00 / 0.57 | 1.00 / 0.67 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.80 | 1.00 / 0.80 | 1.00 / 1.00 |
| `rules+pf+piiranha:pii:rawpii` | 1.00 / 0.57 | 0.67 / 0.89 | 0.62 / 1.00 | 1.00 / 0.96 | 1.00 / 1.00 | 1.00 / 0.84 | 0.00 / — | 1.00 / 1.00 |
| `rules+pf+piiranha:pii` | 1.00 / 0.57 | 0.67 / 0.89 | 0.62 / 1.00 | 1.00 / 0.96 | 1.00 / 1.00 | 1.00 / 0.84 | 0.00 / — | 1.00 / 1.00 |
| `rules+pf+qwen:pii` | 1.00 / 0.57 | 1.00 / 0.67 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.80 | 1.00 / 0.80 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `piiranha` | 17.8 / 34.3 ms | 165 / 232 ms | 801 / 904 ms | 1,656 / 1,747 ms | 4,529 | 2.2 s | 110 ms | — |
| `rules+pf:pii:rawpii` | 7.4 / 11.0 ms | 23.5 / 27.5 ms | 78.0 / 84.7 ms | 187 / 198 ms | 33,448 | 2.8 s | 27.9 ms | 3,492 MB |
| `rules+pf:pii` | 7.5 / 11.0 ms | 23.2 / 28.3 ms | 77.6 / 84.1 ms | 187 / 198 ms | 33,522 | 2.8 s | 32.8 ms | 3,492 MB |
| `rules+pf+piiranha:pii:rawpii` | 24.8 / 44.4 ms | 187 / 256 ms | 889 / 959 ms | 1,859 / 1,952 ms | 3,975 | 3.4 s | 149 ms | 3,492 MB |
| `rules+pf+piiranha:pii` | 24.9 / 45.8 ms | 189 / 253 ms | 885 / 965 ms | 1,868 / 1,948 ms | 3,973 | 4.1 s | 140 ms | 3,492 MB |
| `rules+pf+qwen:pii` | 10.1 / 1,259 ms | 28.4 / 1,039 ms | 567 / 1,054 ms | 730 / 1,059 ms | 2,150 | 4.0 s | 29.6 ms | 5,655 MB |

## LLM outcomes (Apple model, Qwen judge)

| Detector | Counter | Count |
| --- | --- | --- |
| `rules+pf+qwen:pii` | judge-qwen3-4b.calls | 173 |

## Missed secrets

- `piiranha`: 82 missed: long-001 (size:1k, secrets:1) npm_… (40 chars); long-002 (size:1k, secrets:2) hf_C… (37 chars); long-002 (size:1k, secrets:2) npm_… (40 chars); long-003 (size:1k, secrets:3) eyJh… (153 chars); long-003 (size:1k, secrets:3) hf_k… (37 chars); long-003 (size:1k, secrets:3) gith… (93 chars); long-005 (size:1k, secrets:1) hf_O… (37 chars); long-006 (size:1k, secrets:2) hf_H… (37 chars); long-006 (size:1k, secrets:2) npm_… (40 chars); long-007 (size:4k, secrets:3) npm_… (40 chars); long-007 (size:4k, secrets:3) gith… (93 chars); long-007 (size:4k, secrets:3) SG.m… (69 chars)
- `rules+pf:pii:rawpii`: 0 missed
- `rules+pf:pii`: 0 missed
- `rules+pf+piiranha:pii:rawpii`: 0 missed
- `rules+pf+piiranha:pii`: 0 missed
- `rules+pf+qwen:pii`: 0 missed

## Flagged hard negatives (secrets scope)

- `piiranha`: 0 spans
- `rules+pf:pii:rawpii`: 4 spans: neg-000 rules:entropy dist… (21 chars); neg-008 rules:secret-assignment|pf 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment sk-a… (10 chars)
- `rules+pf:pii`: 4 spans: neg-000 rules:entropy dist… (21 chars); neg-008 rules:secret-assignment|pf 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment sk-a… (10 chars)
- `rules+pf+piiranha:pii:rawpii`: 4 spans: neg-000 rules:entropy dist… (21 chars); neg-008 rules:secret-assignment|pf 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment sk-a… (10 chars)
- `rules+pf+piiranha:pii`: 4 spans: neg-000 rules:entropy dist… (21 chars); neg-008 rules:secret-assignment|pf 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment sk-a… (10 chars)
- `rules+pf+qwen:pii`: 4 spans: neg-000 rules:entropy dist… (21 chars); neg-008 rules:secret-assignment|pf 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment sk-a… (10 chars)
