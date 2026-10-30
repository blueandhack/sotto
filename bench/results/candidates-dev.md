# keepmum Phase 0 benchmark — 20261025-020557

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.16.1, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 70 spans / 785–7793 tokens; negatives 40 records / 0 spans / 23–273 tokens; pii 40 records / 120 spans / 29–72 tokens; secrets 50 records / 65 spans / 24–1131 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for AFM.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `credsweeper` | 0.916 | 0.842 | 0.196 | 0.323 | 3/40 (0.07) | 0.1 ms | 20.2 ms | 24.4 ms | 0.5 s | 224 MB | ❌ ❌ ✅ |
| `gliner2` | 0.747 | 0.684 | 0.170 | 0.276 | 26/40 (0.65) | 51.0 ms | 2,095 ms | 4,172 ms | 4.9 s | 3,048 MB | ❌ ❌ ❌ |
| `gliner-nvidia` | 0.726 | 0.726 | 0.332 | 0.456 | 21/40 (0.53) | 55.3 ms | 3,250 ms | 6,283 ms | 5.7 s | 3,946 MB | ❌ ❌ ❌ |
| `pf-nemotron` | 0.768 | 0.642 | 0.182 | 0.294 | 11/40 (0.28) | 4.9 ms | 103 ms | 249 ms | 2.9 s | 3,797 MB | ❌ ❌ ✅ |
| `rules+pf` | 0.989 | 0.989 | 0.784 | 0.875 | 1/40 (0.03) | 7.5 ms | 87.9 ms | 198 ms | 3.1 s | 3,792 MB | ✅ ✅ ✅ |
| `rules+gliner2` | 1.000 | 0.989 | 0.669 | 0.802 | 15/40 (0.38) | 51.2 ms | 2,070 ms | 4,167 ms | 5.2 s | 3,048 MB | ✅ ❌ ❌ |
| `rules+pf-nemotron` | 0.989 | 0.989 | 0.347 | 0.514 | 8/40 (0.20) | 5.2 ms | 105 ms | 257 ms | 3.0 s | 3,797 MB | ✅ ❌ ✅ |
| `rules+gliner-nvidia` | 1.000 | 1.000 | 0.792 | 0.884 | 13/40 (0.33) | 55.5 ms | 3,253 ms | 6,224 ms | 5.9 s | 3,946 MB | ✅ ❌ ❌ |
| `rules+credsweeper+pf` | 0.989 | 0.989 | 0.119 | 0.212 | 2/40 (0.05) | 9.0 ms | 109 ms | 223 ms | 3.7 s | 3,899 MB | ✅ ❌ ✅ |
| `rules+pf:pii` | 0.989 | 0.989 | 0.776 | 0.870 | 1/40 (0.03) | 7.5 ms | 87.3 ms | 203 ms | 2.9 s | 3,792 MB | ✅ ✅ ✅ |
| `rules+gliner2:pii` | 1.000 | 0.989 | 0.641 | 0.781 | 15/40 (0.38) | 51.1 ms | 2,072 ms | 4,169 ms | 5.2 s | 3,048 MB | ✅ ❌ ❌ |
| `rules+pf-nemotron:pii` | 0.989 | 0.989 | 0.339 | 0.506 | 8/40 (0.20) | 5.0 ms | 105 ms | 256 ms | 3.0 s | 3,798 MB | ✅ ❌ ✅ |
| `rules+gliner-nvidia:pii` | 1.000 | 1.000 | 0.792 | 0.884 | 13/40 (0.33) | 56.5 ms | 3,246 ms | 6,326 ms | 5.8 s | 3,946 MB | ✅ ❌ ❌ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `credsweeper` | 0.341 | 0.314 | 0.196 | 0.249 | 3/40 (0.07) |
| `gliner2` | 0.894 | 0.843 | 0.315 | 0.466 | 31/40 (0.78) |
| `gliner-nvidia` | 0.851 | 0.608 | 0.557 | 0.673 | 28/40 (0.70) |
| `pf-nemotron` | 0.894 | 0.592 | 0.371 | 0.524 | 18/40 (0.45) |
| `rules+pf:pii` | 0.996 | 0.988 | 0.615 | 0.761 | 7/40 (0.17) |
| `rules+gliner2:pii` | 0.980 | 0.957 | 0.660 | 0.789 | 23/40 (0.57) |
| `rules+pf-nemotron:pii` | 0.965 | 0.714 | 0.607 | 0.745 | 15/40 (0.38) |
| `rules+gliner-nvidia:pii` | 0.953 | 0.710 | 0.739 | 0.832 | 22/40 (0.55) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `credsweeper` | 0.92 / 0.20 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `gliner2` | 0.77 / 0.17 | 1.00 / 0.25 | 1.00 / 0.92 | 1.00 / 0.81 | 1.00 / 0.85 | 0.88 / 1.00 | 0.00 / — | 1.00 / 0.57 |
| `gliner-nvidia` | 0.73 / 0.34 | 0.83 / 0.16 | 1.00 / 0.90 | 0.93 / 0.83 | 0.88 / 0.93 | 1.00 / 1.00 | 0.00 / 0.12 | 1.00 / 0.57 |
| `pf-nemotron` | 0.85 / 0.18 | 0.42 / 0.75 | 1.00 / 0.97 | 1.00 / 0.84 | 1.00 / 1.00 | 1.00 / 0.97 | 1.00 / 0.38 | 0.25 / 1.00 |
| `rules+pf` | 0.99 / 0.78 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+gliner2` | 1.00 / 0.67 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-nemotron` | 0.99 / 0.35 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+gliner-nvidia` | 1.00 / 0.80 | 0.08 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+credsweeper+pf` | 0.99 / 0.12 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf:pii` | 0.99 / 0.78 | 1.00 / 0.13 | 1.00 / 0.86 | 1.00 / 0.90 | 1.00 / 0.94 | 1.00 / 0.82 | 1.00 / 0.31 | 1.00 / 0.32 |
| `rules+gliner2:pii` | 1.00 / 0.64 | 1.00 / 0.19 | 1.00 / 0.89 | 1.00 / 0.85 | 1.00 / 0.84 | 0.88 / 1.00 | 0.00 / — | 1.00 / 0.57 |
| `rules+pf-nemotron:pii` | 0.99 / 0.34 | 0.83 / 0.91 | 1.00 / 0.97 | 1.00 / 0.84 | 1.00 / 1.00 | 1.00 / 0.97 | 1.00 / 0.22 | 0.25 / 1.00 |
| `rules+gliner-nvidia:pii` | 1.00 / 0.80 | 0.83 / 0.17 | 1.00 / 0.90 | 0.93 / 0.82 | 0.88 / 0.93 | 1.00 / 1.00 | 0.00 / 0.00 | 1.00 / 0.57 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `credsweeper` | 0.1 / 14.3 ms | 13.4 / 16.1 ms | 17.0 / 20.2 ms | 22.4 / 24.4 ms | 102,547 | 0.4 s | 28.5 ms | — |
| `gliner2` | 51.0 / 84.2 ms | 526 / 591 ms | 1,995 / 2,095 ms | 4,081 / 4,172 ms | 1,842 | 4.9 s | 63.2 ms | — |
| `gliner-nvidia` | 55.3 / 127 ms | 770 / 881 ms | 3,099 / 3,250 ms | 6,131 / 6,283 ms | 1,239 | 5.7 s | 277 ms | — |
| `pf-nemotron` | 4.9 / 8.1 ms | 20.2 / 26.8 ms | 91.3 / 103 ms | 231 / 249 ms | 29,862 | 2.8 s | 12.7 ms | 5,072 MB |
| `rules+pf` | 7.5 / 11.5 ms | 24.5 / 31.3 ms | 79.1 / 87.9 ms | 178 / 198 ms | 32,115 | 3.1 s | 27.9 ms | 3,474 MB |
| `rules+gliner2` | 51.2 / 84.9 ms | 510 / 577 ms | 1,971 / 2,070 ms | 4,067 / 4,167 ms | 1,853 | 5.1 s | 63.0 ms | — |
| `rules+pf-nemotron` | 5.2 / 8.9 ms | 20.9 / 28.8 ms | 93.9 / 105 ms | 241 / 257 ms | 30,178 | 2.9 s | 12.8 ms | 5,072 MB |
| `rules+gliner-nvidia` | 55.5 / 106 ms | 754 / 892 ms | 3,137 / 3,253 ms | 6,133 / 6,224 ms | 1,245 | 5.9 s | 149 ms | — |
| `rules+credsweeper+pf` | 9.0 / 24.8 ms | 37.4 / 47.6 ms | 91.2 / 109 ms | 202 / 223 ms | 24,007 | 3.6 s | 79.5 ms | 3,474 MB |
| `rules+pf:pii` | 7.5 / 11.6 ms | 24.4 / 31.5 ms | 79.4 / 87.3 ms | 179 / 203 ms | 31,962 | 2.9 s | 27.8 ms | 3,474 MB |
| `rules+gliner2:pii` | 51.1 / 84.7 ms | 508 / 576 ms | 1,965 / 2,072 ms | 4,070 / 4,169 ms | 1,850 | 5.1 s | 62.3 ms | — |
| `rules+pf-nemotron:pii` | 5.0 / 8.4 ms | 21.2 / 27.5 ms | 92.8 / 105 ms | 240 / 256 ms | 30,468 | 2.9 s | 12.7 ms | 5,072 MB |
| `rules+gliner-nvidia:pii` | 56.5 / 108 ms | 749 / 885 ms | 3,103 / 3,246 ms | 6,143 / 6,326 ms | 1,239 | 5.7 s | 148 ms | — |

## Missed secrets

- `credsweeper`: 8 missed: secret-023 (slack-webhook, ctx:k8s-b64) aHR0… (108 chars); secret-026 (private-key, ctx:file) ----… (1036 chars); secret-028 (private-key, ctx:yaml) ----… (1719 chars); secret-043 (password, ctx:xml) 7Vq4… (14 chars); secret-046 (contextual, hex) b871… (32 chars); secret-047 (contextual, prose-password) WAVC… (16 chars); secret-048 (contextual, cli-flag) m1v9… (40 chars); secret-049 (contextual, traceback) ON6y… (32 chars)
- `gliner2`: 24 missed: long-007 (size:4k, secrets:3) http… (79 chars); long-009 (size:4k, secrets:1) eyJh… (153 chars); long-011 (size:4k, secrets:3) AKIA… (20 chars); long-014 (size:8k, secrets:2) http… (79 chars); long-015 (size:8k, secrets:3) NpXq… (40 chars); long-015 (size:8k, secrets:3) +TpG… (40 chars); long-015 (size:8k, secrets:3) +35I… (40 chars); long-018 (size:8k, secrets:2) AKIA… (20 chars); long-018 (size:8k, secrets:2) http… (79 chars); long-019 (size:8k, secrets:3) http… (79 chars); secret-001 (aws-secret, ctx:python) PcHy… (40 chars); secret-003 (github-fine, ctx:yaml) gith… (93 chars)
- `gliner-nvidia`: 26 missed: long-006 (size:1k, secrets:2) ghp_… (40 chars); long-007 (size:4k, secrets:3) http… (79 chars); long-010 (size:4k, secrets:2) ghp_… (40 chars); long-014 (size:8k, secrets:2) http… (79 chars); long-018 (size:8k, secrets:2) AKIA… (20 chars); long-018 (size:8k, secrets:2) http… (79 chars); long-019 (size:8k, secrets:3) http… (79 chars); secret-008 (slack-webhook, ctx:compose) http… (79 chars); secret-020 (openai, ctx:compose) sk-p… (132 chars); secret-026 (private-key, ctx:file) ----… (1036 chars); secret-027 (private-key, ctx:file) ----… (979 chars); secret-028 (private-key, ctx:yaml) ----… (1719 chars)
- `pf-nemotron`: 22 missed: long-001 (size:1k, secrets:1) xoxb… (56 chars); long-007 (size:4k, secrets:3) http… (79 chars); long-011 (size:4k, secrets:3) AKIA… (20 chars); long-017 (size:8k, secrets:1) ghp_… (40 chars); long-018 (size:8k, secrets:2) AKIA… (20 chars); long-018 (size:8k, secrets:2) http… (79 chars); long-019 (size:8k, secrets:3) http… (79 chars); long-019 (size:8k, secrets:3) sk_l… (32 chars); secret-000 (aws, ctx:shell) AKIA… (20 chars); secret-007 (slack, ctx:terraform) xoxb… (56 chars); secret-008 (slack-webhook, ctx:compose) http… (79 chars); secret-009 (google, ctx:diff) AIza… (39 chars)
- `rules+pf`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+gliner2`: 0 missed
- `rules+pf-nemotron`: 1 missed: secret-046 (contextual, hex) b871… (32 chars)
- `rules+gliner-nvidia`: 0 missed
- `rules+credsweeper+pf`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+pf:pii`: 1 missed: secret-047 (contextual, prose-password) WAVC… (16 chars)
- `rules+gliner2:pii`: 0 missed
- `rules+pf-nemotron:pii`: 1 missed: secret-046 (contextual, hex) b871… (32 chars)
- `rules+gliner-nvidia:pii`: 0 missed

## Flagged hard negatives (secrets scope)

- `credsweeper`: 6 spans: neg-000 credsweeper 3f2b… (36 chars); neg-000 credsweeper 3f2b… (36 chars); neg-000 credsweeper 3f2b… (36 chars); neg-026 credsweeper pk_t… (32 chars); neg-032 credsweeper eyJh… (155 chars); neg-032 credsweeper eyJh… (155 chars)
- `gliner2`: 98 spans: neg-002 gliner2 sha5… (54 chars); neg-003 gliner2 sha5… (17 chars); neg-003 gliner2 3TJX… (40 chars); neg-003 gliner2 184c… (34 chars); neg-003 gliner2 3TJX… (40 chars); neg-003 gliner2 sha5… (17 chars); neg-003 gliner2 184c… (34 chars); neg-004 gliner2 wBqf… (11 chars); neg-004 gliner2 Qqji… (14 chars); neg-004 gliner2 2P8g… (25 chars); neg-004 gliner2 68CP… (43 chars); neg-004 gliner2 n… (3 chars)
- `gliner-nvidia`: 35 spans: neg-000 gliner-nvidia 3f2b… (36 chars); neg-000 gliner-nvidia 3f2b… (36 chars); neg-001 gliner-nvidia 9fce… (40 chars); neg-001 gliner-nvidia e83c… (40 chars); neg-002 gliner-nvidia sha5… (95 chars); neg-004 gliner-nvidia P4fl… (44 chars); neg-004 gliner-nvidia wBqf… (44 chars); neg-007 gliner-nvidia aws_… (64 chars); neg-008 gliner-nvidia REDI… (14 chars); neg-008 gliner-nvidia REDI… (14 chars); neg-009 gliner-nvidia OPEN… (14 chars); neg-009 gliner-nvidia GITH… (12 chars)
- `pf-nemotron`: 14 spans: neg-000 pf-nemotron orde… (23 chars); neg-002 pf-nemotron GHVx… (37 chars); neg-003 pf-nemotron sha5… (93 chars); neg-004 pf-nemotron h1:w… (46 chars); neg-007 pf-nemotron wJal… (40 chars); neg-013 pf-nemotron api-… (9 chars); neg-016 pf-nemotron +qKh… (29 chars); neg-016 pf-nemotron kd3q… (64 chars); neg-016 pf-nemotron 0iT9… (64 chars); neg-016 pf-nemotron cKWT… (64 chars); neg-017 pf-nemotron VQQD… (64 chars); neg-028 pf-nemotron "<hi… (11 chars)
- `rules+pf`: 1 spans: neg-039 pf eyJv… (76 chars)
- `rules+gliner2`: 46 spans: neg-002 gliner2 sha5… (54 chars); neg-003 gliner2 sha5… (17 chars); neg-003 gliner2 3TJX… (40 chars); neg-003 gliner2 184c… (34 chars); neg-004 gliner2 68CP… (43 chars); neg-004 gliner2 P4fl… (25 chars); neg-004 gliner2 Qqji… (14 chars); neg-004 gliner2 wBqf… (11 chars); neg-004 gliner2 2P8g… (25 chars); neg-008 gliner2 DATA… (12 chars); neg-008 gliner2 DATA… (12 chars); neg-008 gliner2 STRI… (17 chars)
- `rules+pf-nemotron`: 11 spans: neg-000 pf-nemotron 3f2b… (17 chars); neg-002 pf-nemotron GHVx… (35 chars); neg-003 pf-nemotron sha5… (93 chars); neg-004 pf-nemotron h1:w… (46 chars); neg-013 pf-nemotron api-… (9 chars); neg-016 pf-nemotron +qKh… (29 chars); neg-016 pf-nemotron kd3q… (64 chars); neg-016 pf-nemotron 0iT9… (64 chars); neg-016 pf-nemotron cKWT… (64 chars); neg-017 pf-nemotron VQQD… (64 chars); neg-039 pf-nemotron eyJv… (76 chars)
- `rules+gliner-nvidia`: 22 spans: neg-002 gliner-nvidia sha5… (93 chars); neg-004 gliner-nvidia P4fl… (43 chars); neg-004 gliner-nvidia wBqf… (43 chars); neg-007 gliner-nvidia aws_… (21 chars); neg-008 gliner-nvidia REDI… (14 chars); neg-008 gliner-nvidia REDI… (14 chars); neg-009 gliner-nvidia OPEN… (14 chars); neg-009 gliner-nvidia GITH… (12 chars); neg-009 gliner-nvidia DATA… (17 chars); neg-010 gliner-nvidia OPEN… (14 chars); neg-013 gliner-nvidia DB_P… (11 chars); neg-013 gliner-nvidia API_… (9 chars)
- `rules+credsweeper+pf`: 3 spans: neg-000 credsweeper 3f2b… (36 chars); neg-000 credsweeper 3f2b… (36 chars); neg-039 pf eyJv… (76 chars)
- `rules+pf:pii`: 1 spans: neg-039 pf eyJv… (76 chars)
- `rules+gliner2:pii`: 46 spans: neg-002 gliner2 sha5… (54 chars); neg-003 gliner2 sha5… (17 chars); neg-003 gliner2 3TJX… (40 chars); neg-003 gliner2 184c… (34 chars); neg-004 gliner2 68CP… (43 chars); neg-004 gliner2 P4fl… (25 chars); neg-004 gliner2 Qqji… (14 chars); neg-004 gliner2 wBqf… (11 chars); neg-004 gliner2 2P8g… (25 chars); neg-008 gliner2 DATA… (12 chars); neg-008 gliner2 DATA… (12 chars); neg-008 gliner2 STRI… (17 chars)
- `rules+pf-nemotron:pii`: 11 spans: neg-000 pf-nemotron 3f2b… (17 chars); neg-002 pf-nemotron GHVx… (35 chars); neg-003 pf-nemotron sha5… (93 chars); neg-004 pf-nemotron h1:w… (46 chars); neg-013 pf-nemotron api-… (9 chars); neg-016 pf-nemotron +qKh… (29 chars); neg-016 pf-nemotron kd3q… (64 chars); neg-016 pf-nemotron 0iT9… (64 chars); neg-016 pf-nemotron cKWT… (64 chars); neg-017 pf-nemotron VQQD… (64 chars); neg-039 pf-nemotron eyJv… (76 chars)
- `rules+gliner-nvidia:pii`: 22 spans: neg-002 gliner-nvidia sha5… (93 chars); neg-004 gliner-nvidia P4fl… (43 chars); neg-004 gliner-nvidia wBqf… (43 chars); neg-007 gliner-nvidia aws_… (21 chars); neg-008 gliner-nvidia REDI… (14 chars); neg-008 gliner-nvidia REDI… (14 chars); neg-009 gliner-nvidia OPEN… (14 chars); neg-009 gliner-nvidia GITH… (12 chars); neg-009 gliner-nvidia DATA… (17 chars); neg-010 gliner-nvidia OPEN… (14 chars); neg-013 gliner-nvidia DB_P… (11 chars); neg-013 gliner-nvidia API_… (9 chars)
