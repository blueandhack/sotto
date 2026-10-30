# keepmum Phase 0 benchmark — 20261029-131850

Machine: Apple M5 Pro, 64 GB, macOS 27.2, Python 3.12.15. .

Dataset (estimated at 4 characters per token): secrets 98 records / 113 spans / 9–442 tokens; pii 46 records / 128 spans / 6–52 tokens; long 20 records / 76 spans / 948–7796 tokens; negatives 40 records / 0 spans / 23–112 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 1 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.783 | 0.755 | 1.000 | 0.878 | 0/40 (0.00) | 0.0 ms | 5.7 ms | 10.8 ms | 0.0 s | 28 MB | ❌ ✅ ✅ |
| `rules:pii` | 0.783 | 0.755 | 1.000 | 0.878 | 0/40 (0.00) | 0.0 ms | 5.7 ms | 10.7 ms | 0.0 s | 28 MB | ❌ ✅ ✅ |
| `rules+pf-serve` | 0.902 | 0.881 | 0.863 | 0.882 | 1/40 (0.03) | 5.5 ms | 221 ms | 459 ms | 0.6 s | 29 MB | ❌ ✅ ❌ |
| `rules+pf-serve:pii` | 0.902 | 0.881 | 0.856 | 0.879 | 1/40 (0.03) | 5.5 ms | 221 ms | 445 ms | 0.6 s | 29 MB | ❌ ✅ ❌ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules:pii` | 0.391 | 0.379 | 1.000 | 0.562 | 0/40 (0.00) |
| `rules+pf-serve:pii` | 0.965 | 0.943 | 0.894 | 0.928 | 3/40 (0.07) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.78 / 1.00 | 0.92 / 1.00 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules:pii` | 0.78 / 1.00 | 0.92 / 1.00 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve` | 0.90 / 0.86 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve:pii` | 0.92 / 0.86 | 1.00 / 0.93 | 1.00 / 0.94 | 1.00 / 0.92 | 1.00 / 1.00 | 1.00 / 0.82 | 1.00 / 0.57 | 1.00 / 1.00 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.0 / 0.2 ms | 1.3 / 1.6 ms | 5.1 / 5.7 ms | 10.2 / 10.8 ms | 749,959 | 0.0 s | 0.1 ms | — |
| `rules:pii` | 0.0 / 0.2 ms | 1.3 / 1.6 ms | 5.0 / 5.7 ms | 10.2 / 10.7 ms | 749,427 | 0.0 s | 0.1 ms | — |
| `rules+pf-serve` | 5.5 / 8.0 ms | 36.0 / 41.6 ms | 177 / 221 ms | 434 / 459 ms | 16,810 | 0.5 s | 5.0 ms | — |
| `rules+pf-serve:pii` | 5.5 / 7.9 ms | 36.1 / 42.1 ms | 173 / 221 ms | 432 / 445 ms | 16,954 | 0.5 s | 4.9 ms | — |

## Missed secrets

- `rules`: 31 missed: extra-000 (groq, ctx:bare) gsk_… (56 chars); extra-002 (openrouter, ctx:bare) sk-o… (73 chars); extra-004 (supabase, ctx:bare) sbp_… (44 chars); extra-006 (langsmith, ctx:bare) lsv2… (51 chars); extra-008 (shopify, ctx:bare) shpa… (38 chars); extra-011 (pypi, ctx:bare) pypi… (90 chars); extra-012 (doppler, ctx:bare) dp.p… (49 chars); extra-013 (pulumi, ctx:bare) pul-… (44 chars); extra-014 (postman, ctx:bare) PMAK… (64 chars); extra-015 (databricks, ctx:bare) dapi… (36 chars); extra-017 (new-relic, ctx:bare) NRAK… (32 chars); extra-018 (sentry, ctx:bare) sntr… (71 chars)
- `rules:pii`: 31 missed: extra-000 (groq, ctx:bare) gsk_… (56 chars); extra-002 (openrouter, ctx:bare) sk-o… (73 chars); extra-004 (supabase, ctx:bare) sbp_… (44 chars); extra-006 (langsmith, ctx:bare) lsv2… (51 chars); extra-008 (shopify, ctx:bare) shpa… (38 chars); extra-011 (pypi, ctx:bare) pypi… (90 chars); extra-012 (doppler, ctx:bare) dp.p… (49 chars); extra-013 (pulumi, ctx:bare) pul-… (44 chars); extra-014 (postman, ctx:bare) PMAK… (64 chars); extra-015 (databricks, ctx:bare) dapi… (36 chars); extra-017 (new-relic, ctx:bare) NRAK… (32 chars); extra-018 (sentry, ctx:bare) sntr… (71 chars)
- `rules+pf-serve`: 14 missed: extra-000 (groq, ctx:bare) gsk_… (56 chars); extra-002 (openrouter, ctx:bare) sk-o… (73 chars); extra-004 (supabase, ctx:bare) sbp_… (44 chars); extra-012 (doppler, ctx:bare) dp.p… (49 chars); extra-014 (postman, ctx:bare) PMAK… (64 chars); extra-015 (databricks, ctx:bare) dapi… (36 chars); extra-017 (new-relic, ctx:bare) NRAK… (32 chars); extra-026 (slack-app, ctx:bare) xapp… (97 chars); extra-027 (square, ctx:bare) EAAA… (64 chars); extra-029 (telegram, ctx:bare) 2373… (46 chars); extra-030 (dynatrace, ctx:bare) dt0c… (96 chars); extra-035 (huggingface-org, ctx:bare) api_… (42 chars)
- `rules+pf-serve:pii`: 14 missed: extra-000 (groq, ctx:bare) gsk_… (56 chars); extra-002 (openrouter, ctx:bare) sk-o… (73 chars); extra-004 (supabase, ctx:bare) sbp_… (44 chars); extra-012 (doppler, ctx:bare) dp.p… (49 chars); extra-014 (postman, ctx:bare) PMAK… (64 chars); extra-015 (databricks, ctx:bare) dapi… (36 chars); extra-017 (new-relic, ctx:bare) NRAK… (32 chars); extra-026 (slack-app, ctx:bare) xapp… (97 chars); extra-027 (square, ctx:bare) EAAA… (64 chars); extra-029 (telegram, ctx:bare) 2373… (46 chars); extra-030 (dynatrace, ctx:bare) dt0c… (96 chars); extra-035 (huggingface-org, ctx:bare) api_… (42 chars)

## Flagged hard negatives (secrets scope)

- `rules`: 0 spans
- `rules:pii`: 0 spans
- `rules+pf-serve`: 1 spans: neg-039 pf-serve eyJv… (76 chars)
- `rules+pf-serve:pii`: 1 spans: neg-039 pf-serve eyJv… (76 chars)
