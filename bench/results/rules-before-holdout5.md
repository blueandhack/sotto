# sotto Phase 0 benchmark — 20261029-131902

Machine: Apple M5 Pro, 64 GB, macOS 27.2, Python 3.12.15. .

Dataset (estimated at 4 characters per token): secrets 98 records / 113 spans / 9–404 tokens; pii 46 records / 128 spans / 6–52 tokens; long 20 records / 66 spans / 773–7835 tokens; negatives 15 records / 0 spans / 23–85 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 1 for local detectors, 1 for LLM-based ones.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.790 | 0.748 | 1.000 | 0.883 | 0/15 (0.00) | 0.0 ms | 5.5 ms | 10.8 ms | 0.0 s | 28 MB | ❌ ✅ ✅ |
| `rules:pii` | 0.790 | 0.748 | 1.000 | 0.883 | 0/15 (0.00) | 0.0 ms | 5.5 ms | 10.9 ms | 0.0 s | 28 MB | ❌ ✅ ✅ |
| `rules+pf-serve` | 0.930 | 0.902 | 0.824 | 0.874 | 1/15 (0.07) | 5.3 ms | 229 ms | 450 ms | 0.5 s | 30 MB | ❌ ❌ ❌ |
| `rules+pf-serve:pii` | 0.930 | 0.902 | 0.818 | 0.870 | 1/15 (0.07) | 5.4 ms | 229 ms | 451 ms | 0.6 s | 29 MB | ❌ ❌ ❌ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `rules:pii` | 0.407 | 0.388 | 1.000 | 0.579 | 0/15 (0.00) |
| `rules+pf-serve:pii` | 0.967 | 0.932 | 0.858 | 0.909 | 5/15 (0.33) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.79 / 1.00 | 0.92 / 1.00 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules:pii` | 0.79 / 1.00 | 0.92 / 1.00 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve` | 0.93 / 0.82 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-serve:pii` | 0.93 / 0.82 | 1.00 / 0.67 | 1.00 / 0.95 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.82 | 1.00 / 0.57 | 1.00 / 0.91 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `rules` | 0.0 / 0.2 ms | 1.3 / 1.8 ms | 5.2 / 5.5 ms | 10.1 / 10.8 ms | 760,082 | 0.0 s | 0.1 ms | — |
| `rules:pii` | 0.0 / 0.2 ms | 1.3 / 1.9 ms | 5.2 / 5.5 ms | 10.2 / 10.9 ms | 755,606 | 0.0 s | 0.1 ms | — |
| `rules+pf-serve` | 5.3 / 7.7 ms | 34.4 / 42.4 ms | 175 / 229 ms | 431 / 450 ms | 16,978 | 0.5 s | 4.9 ms | — |
| `rules+pf-serve:pii` | 5.4 / 7.7 ms | 33.4 / 42.6 ms | 175 / 229 ms | 430 / 451 ms | 16,962 | 0.5 s | 4.9 ms | — |

## Missed secrets

- `rules`: 30 missed: extra-000 (groq, ctx:bare) gsk_… (56 chars); extra-002 (openrouter, ctx:bare) sk-o… (73 chars); extra-004 (supabase, ctx:bare) sbp_… (44 chars); extra-005 (docker-hub, ctx:bare) dckr… (36 chars); extra-006 (langsmith, ctx:bare) lsv2… (51 chars); extra-008 (shopify, ctx:bare) shpa… (38 chars); extra-013 (pulumi, ctx:bare) pul-… (44 chars); extra-014 (postman, ctx:bare) PMAK… (64 chars); extra-015 (databricks, ctx:bare) dapi… (36 chars); extra-017 (new-relic, ctx:bare) NRAK… (32 chars); extra-018 (sentry, ctx:bare) sntr… (71 chars); extra-019 (age, ctx:bare) AGE-… (74 chars)
- `rules:pii`: 30 missed: extra-000 (groq, ctx:bare) gsk_… (56 chars); extra-002 (openrouter, ctx:bare) sk-o… (73 chars); extra-004 (supabase, ctx:bare) sbp_… (44 chars); extra-005 (docker-hub, ctx:bare) dckr… (36 chars); extra-006 (langsmith, ctx:bare) lsv2… (51 chars); extra-008 (shopify, ctx:bare) shpa… (38 chars); extra-013 (pulumi, ctx:bare) pul-… (44 chars); extra-014 (postman, ctx:bare) PMAK… (64 chars); extra-015 (databricks, ctx:bare) dapi… (36 chars); extra-017 (new-relic, ctx:bare) NRAK… (32 chars); extra-018 (sentry, ctx:bare) sntr… (71 chars); extra-019 (age, ctx:bare) AGE-… (74 chars)
- `rules+pf-serve`: 10 missed: extra-004 (supabase, ctx:bare) sbp_… (44 chars); extra-006 (langsmith, ctx:bare) lsv2… (51 chars); extra-014 (postman, ctx:bare) PMAK… (64 chars); extra-017 (new-relic, ctx:bare) NRAK… (32 chars); extra-022 (heroku, ctx:bare) HRKU… (65 chars); extra-027 (square, ctx:bare) EAAA… (64 chars); extra-030 (dynatrace, ctx:bare) dt0c… (96 chars); extra-032 (sendinblue, ctx:bare) xkey… (89 chars); extra-039 (flag) 0z+M… (13 chars); extra-045 (presigned-url) dabd… (64 chars)
- `rules+pf-serve:pii`: 10 missed: extra-004 (supabase, ctx:bare) sbp_… (44 chars); extra-006 (langsmith, ctx:bare) lsv2… (51 chars); extra-014 (postman, ctx:bare) PMAK… (64 chars); extra-017 (new-relic, ctx:bare) NRAK… (32 chars); extra-022 (heroku, ctx:bare) HRKU… (65 chars); extra-027 (square, ctx:bare) EAAA… (64 chars); extra-030 (dynatrace, ctx:bare) dt0c… (96 chars); extra-032 (sendinblue, ctx:bare) xkey… (89 chars); extra-039 (flag) 0z+M… (13 chars); extra-045 (presigned-url) dabd… (64 chars)

## Flagged hard negatives (secrets scope)

- `rules`: 0 spans
- `rules:pii`: 0 spans
- `rules+pf-serve`: 1 spans: neg-004 pf-serve @db.… (29 chars)
- `rules+pf-serve:pii`: 1 spans: neg-004 pf-serve @db.… (29 chars)
