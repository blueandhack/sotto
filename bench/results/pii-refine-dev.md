# sotto Phase 0 benchmark — 20261025-143820

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.16.1, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 70 spans / 785–7793 tokens; negatives 40 records / 0 spans / 23–273 tokens; pii 40 records / 120 spans / 29–72 tokens; secrets 50 records / 65 spans / 24–1131 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `piiranha` | 0.116 | 0.105 | 1.000 | 0.208 | 0/40 (0.00) | 18.0 ms | 894 ms | 1,705 ms | 2.2 s | 1,510 MB | ❌ ✅ ❌ |
| `rules+pf:pii:rawpii` | 0.989 | 0.989 | 0.776 | 0.870 | 1/40 (0.03) | 7.4 ms | 87.4 ms | 198 ms | 2.9 s | 3,791 MB | ✅ ✅ ✅ |
| `rules+pf:pii` | 0.989 | 0.989 | 0.776 | 0.870 | 1/40 (0.03) | 7.6 ms | 88.1 ms | 199 ms | 2.8 s | 3,792 MB | ✅ ✅ ✅ |
| `rules+pf+piiranha:pii:rawpii` | 0.989 | 0.989 | 0.784 | 0.875 | 1/40 (0.03) | 25.4 ms | 964 ms | 1,902 ms | 3.5 s | 4,396 MB | ✅ ✅ ❌ |
| `rules+pf+piiranha:pii` | 0.989 | 0.989 | 0.784 | 0.875 | 1/40 (0.03) | 25.5 ms | 965 ms | 1,904 ms | 4.2 s | 4,398 MB | ✅ ✅ ❌ |
| `rules+pf+qwen:pii` | 0.989 | 0.989 | 0.776 | 0.870 | 1/40 (0.03) | 9.3 ms | 1,421 ms | 1,009 ms | 4.0 s | 5,806 MB | ✅ ✅ ❌ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `piiranha` | 0.506 | 0.369 | 0.911 | 0.650 | 5/40 (0.12) |
| `rules+pf:pii:rawpii` | 0.996 | 0.988 | 0.615 | 0.761 | 7/40 (0.17) |
| `rules+pf:pii` | 0.996 | 0.988 | 0.866 | 0.926 | 3/40 (0.07) |
| `rules+pf+piiranha:pii:rawpii` | 0.843 | 0.710 | 0.860 | 0.851 | 6/40 (0.15) |
| `rules+pf+piiranha:pii` | 0.839 | 0.710 | 0.871 | 0.855 | 4/40 (0.10) |
| `rules+pf+qwen:pii` | 0.996 | 0.988 | 0.866 | 0.926 | 3/40 (0.07) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `piiranha` | 0.12 / 1.00 | 0.42 / 0.69 | 0.48 / 0.98 | 1.00 / 0.97 | 0.88 / 1.00 | 1.00 / 0.74 | 0.00 / — | 1.00 / 1.00 |
| `rules+pf:pii:rawpii` | 0.99 / 0.78 | 1.00 / 0.13 | 1.00 / 0.86 | 1.00 / 0.90 | 1.00 / 0.94 | 1.00 / 0.82 | 1.00 / 0.31 | 1.00 / 0.32 |
| `rules+pf:pii` | 0.99 / 0.78 | 1.00 / 0.93 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.82 | 1.00 / 0.57 | 1.00 / 1.00 |
| `rules+pf+piiranha:pii:rawpii` | 0.99 / 0.78 | 0.67 / 0.71 | 0.48 / 0.98 | 1.00 / 0.97 | 0.88 / 1.00 | 1.00 / 0.74 | 0.00 / — | 1.00 / 1.00 |
| `rules+pf+piiranha:pii` | 0.99 / 0.78 | 0.67 / 1.00 | 0.46 / 0.98 | 1.00 / 0.97 | 0.88 / 1.00 | 1.00 / 0.74 | 0.00 / — | 1.00 / 1.00 |
| `rules+pf+qwen:pii` | 0.99 / 0.78 | 1.00 / 0.93 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.82 | 1.00 / 0.57 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `piiranha` | 18.0 / 43.8 ms | 199 / 240 ms | 825 / 894 ms | 1,609 / 1,705 ms | 4,490 | 2.1 s | 109 ms | — |
| `rules+pf:pii:rawpii` | 7.4 / 11.4 ms | 24.2 / 31.1 ms | 79.4 / 87.4 ms | 178 / 198 ms | 32,113 | 2.9 s | 42.7 ms | 3,474 MB |
| `rules+pf:pii` | 7.6 / 11.6 ms | 24.5 / 31.7 ms | 79.9 / 88.1 ms | 178 / 199 ms | 31,827 | 2.8 s | 40.1 ms | 3,474 MB |
| `rules+pf+piiranha:pii:rawpii` | 25.4 / 47.1 ms | 222 / 267 ms | 898 / 964 ms | 1,808 / 1,902 ms | 3,959 | 3.5 s | 155 ms | 3,474 MB |
| `rules+pf+piiranha:pii` | 25.5 / 46.5 ms | 222 / 269 ms | 896 / 965 ms | 1,818 / 1,904 ms | 3,958 | 4.2 s | 143 ms | 3,474 MB |
| `rules+pf+qwen:pii` | 9.3 / 1,015 ms | 938 / 1,421 ms | 85.1 / 1,081 ms | 693 / 1,009 ms | 2,177 | 4.0 s | 29.6 ms | 5,663 MB |

## LLM outcomes (Apple model, Qwen judge)

| Detector | Counter | Count |
| --- | --- | --- |
| `rules+pf+qwen:pii` | judge-qwen3-4b.calls | 174 |

## Missed secrets

- `piiranha`: 84 missed: long-001 (size:1k, secrets:1) xoxb… (56 chars); long-002 (size:1k, secrets:2) gith… (93 chars); long-002 (size:1k, secrets:2) sk-p… (132 chars); long-003 (size:1k, secrets:3) hf_v… (37 chars); long-003 (size:1k, secrets:3) xoxb… (56 chars); long-003 (size:1k, secrets:3) npm_… (40 chars); long-005 (size:1k, secrets:1) hf_u… (37 chars); long-006 (size:1k, secrets:2) ghp_… (40 chars); long-006 (size:1k, secrets:2) SG.G… (69 chars); long-007 (size:4k, secrets:3) AIza… (39 chars); long-007 (size:4k, secrets:3) http… (79 chars); long-007 (size:4k, secrets:3) AWdW… (40 chars)
- `rules+pf:pii:rawpii`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+pf:pii`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+pf+piiranha:pii:rawpii`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+pf+piiranha:pii`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+pf+qwen:pii`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)

## Flagged hard negatives (secrets scope)

- `piiranha`: 0 spans
- `rules+pf:pii:rawpii`: 1 spans: neg-039 pf eyJv… (76 chars)
- `rules+pf:pii`: 1 spans: neg-039 pf eyJv… (76 chars)
- `rules+pf+piiranha:pii:rawpii`: 1 spans: neg-039 pf eyJv… (76 chars)
- `rules+pf+piiranha:pii`: 1 spans: neg-039 pf eyJv… (76 chars)
- `rules+pf+qwen:pii`: 1 spans: neg-039 pf eyJv… (76 chars)
