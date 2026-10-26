# sotto Phase 0 benchmark — 20261025-022626

Machine: Apple M5 Pro, 64 GB, macOS 27.0.1, Python 3.12.0. mlx 0.32.4, mlx-embeddings 0.1.1, torch 2.14.1, transformers 5.16.1, apple-fm-sdk 0.2.1, tokenizers 0.23.3.

Dataset (o200k (Privacy Filter tokenizer)): long 20 records / 62 spans / 562–7896 tokens; negatives 15 records / 0 spans / 32–141 tokens; pii 40 records / 120 spans / 29–73 tokens; secrets 50 records / 65 spans / 24–1182 tokens.
A labeled span is a hit when detections cover at least 50% of it; a detection is correct when at least half of it lies on labeled spans. *Full cover* counts labeled spans redacted completely. Latency repeats: 3 for local detectors, 1 for AFM.


## Secrets (default config: `pii = false`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `credsweeper` | 0.916 | 0.895 | 0.211 | 0.343 | 1/15 (0.07) | 0.1 ms | 36.3 ms | 28.9 ms | 0.7 s | 224 MB | ❌ ❌ ✅ |
| `gliner2` | 0.821 | 0.779 | 0.204 | 0.326 | 10/15 (0.67) | 50.9 ms | 2,149 ms | 4,375 ms | 5.3 s | 3,048 MB | ❌ ❌ ❌ |
| `gliner-nvidia` | 0.779 | 0.758 | 0.405 | 0.533 | 9/15 (0.60) | 54.7 ms | 3,231 ms | 6,571 ms | 5.9 s | 3,946 MB | ❌ ❌ ❌ |
| `pf-nemotron` | 0.811 | 0.705 | 0.199 | 0.319 | 3/15 (0.20) | 5.0 ms | 95.5 ms | 246 ms | 2.9 s | 3,800 MB | ❌ ❌ ✅ |
| `rules+pf` | 1.000 | 1.000 | 0.575 | 0.730 | 3/15 (0.20) | 7.4 ms | 84.6 ms | 198 ms | 3.0 s | 3,791 MB | ✅ ❌ ✅ |
| `rules+gliner2` | 1.000 | 1.000 | 0.879 | 0.935 | 7/15 (0.47) | 47.3 ms | 2,076 ms | 4,198 ms | 5.2 s | 3,048 MB | ✅ ❌ ❌ |
| `rules+pf-nemotron` | 0.989 | 0.989 | 0.392 | 0.561 | 4/15 (0.27) | 5.0 ms | 99.4 ms | 260 ms | 2.9 s | 3,798 MB | ✅ ❌ ✅ |
| `rules+gliner-nvidia` | 1.000 | 1.000 | 0.896 | 0.945 | 6/15 (0.40) | 55.0 ms | 3,331 ms | 6,748 ms | 5.9 s | 3,946 MB | ✅ ❌ ❌ |
| `rules+credsweeper+pf` | 1.000 | 1.000 | 0.121 | 0.216 | 3/15 (0.20) | 8.9 ms | 105 ms | 218 ms | 3.7 s | 3,899 MB | ✅ ❌ ✅ |
| `rules+pf:pii` | 1.000 | 1.000 | 0.569 | 0.725 | 3/15 (0.20) | 7.4 ms | 86.8 ms | 198 ms | 2.9 s | 3,792 MB | ✅ ❌ ✅ |
| `rules+gliner2:pii` | 1.000 | 1.000 | 0.869 | 0.930 | 7/15 (0.47) | 49.5 ms | 2,087 ms | 4,326 ms | 5.1 s | 3,044 MB | ✅ ❌ ❌ |
| `rules+pf-nemotron:pii` | 0.989 | 0.989 | 0.383 | 0.553 | 4/15 (0.27) | 5.2 ms | 100 ms | 265 ms | 3.0 s | 3,801 MB | ✅ ❌ ✅ |
| `rules+gliner-nvidia:pii` | 1.000 | 1.000 | 0.887 | 0.940 | 6/15 (0.40) | 55.1 ms | 3,247 ms | 6,493 ms | 6.0 s | 3,947 MB | ✅ ❌ ❌ |

Targets, in order: secret recall ≥ 0.98, negatives flagged < 5%, p95 ≤ 150 ms for inputs up to 4K tokens.

## All types (`pii = true`)

| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |
| --- | --- | --- | --- | --- | --- |
| `credsweeper` | 0.352 | 0.344 | 0.211 | 0.264 | 1/15 (0.07) |
| `gliner2` | 0.919 | 0.891 | 0.332 | 0.488 | 12/15 (0.80) |
| `gliner-nvidia` | 0.822 | 0.575 | 0.596 | 0.691 | 12/15 (0.80) |
| `pf-nemotron` | 0.895 | 0.611 | 0.384 | 0.537 | 8/15 (0.53) |
| `rules+pf:pii` | 1.000 | 0.992 | 0.595 | 0.746 | 4/15 (0.27) |
| `rules+gliner2:pii` | 0.984 | 0.972 | 0.639 | 0.775 | 10/15 (0.67) |
| `rules+pf-nemotron:pii` | 0.960 | 0.717 | 0.641 | 0.769 | 9/15 (0.60) |
| `rules+gliner-nvidia:pii` | 0.903 | 0.668 | 0.759 | 0.825 | 9/15 (0.60) |

## Recall / precision by type (all types)

| Detector | SECRET | ACCOUNT | PERSON | EMAIL | PHONE | ADDRESS | URL | DATE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `credsweeper` | 0.92 / 0.21 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `gliner2` | 0.83 / 0.20 | 1.00 / 0.13 | 1.00 / 0.93 | 1.00 / 0.89 | 1.00 / 1.00 | 1.00 / 1.00 | 0.00 / — | 1.00 / 0.40 |
| `gliner-nvidia` | 0.79 / 0.41 | 0.67 / 0.13 | 1.00 / 0.94 | 0.73 / 0.88 | 1.00 / 1.00 | 0.75 / 1.00 | 0.00 / 0.06 | 1.00 / 0.53 |
| `pf-nemotron` | 0.85 / 0.20 | 0.42 / 0.83 | 1.00 / 0.99 | 1.00 / 0.91 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 0.20 | 0.38 / 1.00 |
| `rules+pf` | 1.00 / 0.57 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+gliner2` | 1.00 / 0.88 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf-nemotron` | 0.99 / 0.39 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+gliner-nvidia` | 1.00 / 0.90 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+credsweeper+pf` | 1.00 / 0.12 | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — | 0.00 / — |
| `rules+pf:pii` | 1.00 / 0.57 | 1.00 / 0.17 | 1.00 / 0.85 | 1.00 / 0.93 | 1.00 / 1.00 | 1.00 / 0.80 | 1.00 / 0.29 | 1.00 / 0.36 |
| `rules+gliner2:pii` | 1.00 / 0.87 | 1.00 / 0.11 | 1.00 / 0.91 | 1.00 / 0.91 | 1.00 / 1.00 | 1.00 / 1.00 | 0.00 / — | 1.00 / 0.40 |
| `rules+pf-nemotron:pii` | 0.99 / 0.38 | 0.67 / 0.80 | 1.00 / 0.99 | 1.00 / 0.91 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 0.18 | 0.38 / 1.00 |
| `rules+gliner-nvidia:pii` | 1.00 / 0.89 | 0.67 / 0.14 | 1.00 / 0.94 | 0.73 / 0.86 | 1.00 / 1.00 | 0.75 / 1.00 | 0.00 / 0.00 | 1.00 / 0.53 |

Cells are recall / precision. Recall uses the labeled type, precision the detected type.

## Latency

| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `credsweeper` | 0.1 / 15.0 ms | 14.8 / 36.3 ms | 16.9 / 21.9 ms | 24.5 / 28.9 ms | 99,236 | 0.7 s | 30.3 ms | — |
| `gliner2` | 50.9 / 91.8 ms | 448 / 553 ms | 2,121 / 2,149 ms | 4,251 / 4,375 ms | 1,780 | 5.3 s | 65.9 ms | — |
| `gliner-nvidia` | 54.7 / 106 ms | 650 / 798 ms | 3,110 / 3,231 ms | 6,329 / 6,571 ms | 1,225 | 5.9 s | 149 ms | — |
| `pf-nemotron` | 5.0 / 7.8 ms | 18.9 / 23.4 ms | 86.3 / 95.5 ms | 238 / 246 ms | 31,383 | 2.8 s | 13.0 ms | 5,072 MB |
| `rules+pf` | 7.4 / 10.9 ms | 23.1 / 26.7 ms | 77.9 / 84.6 ms | 186 / 198 ms | 33,642 | 3.0 s | 27.7 ms | 3,492 MB |
| `rules+gliner2` | 47.3 / 80.8 ms | 432 / 540 ms | 2,029 / 2,076 ms | 4,036 / 4,198 ms | 1,863 | 5.1 s | 62.7 ms | — |
| `rules+pf-nemotron` | 5.0 / 8.9 ms | 19.7 / 21.3 ms | 92.9 / 99.4 ms | 252 / 260 ms | 30,982 | 2.9 s | 12.5 ms | 5,072 MB |
| `rules+gliner-nvidia` | 55.0 / 107 ms | 653 / 792 ms | 3,077 / 3,331 ms | 6,232 / 6,748 ms | 1,226 | 5.8 s | 149 ms | — |
| `rules+credsweeper+pf` | 8.9 / 26.3 ms | 35.2 / 40.5 ms | 87.8 / 105 ms | 210 / 218 ms | 25,223 | 3.6 s | 57.1 ms | 3,492 MB |
| `rules+pf:pii` | 7.4 / 10.7 ms | 22.9 / 26.7 ms | 76.9 / 86.8 ms | 187 / 198 ms | 33,701 | 2.9 s | 30.2 ms | 3,492 MB |
| `rules+gliner2:pii` | 49.5 / 81.8 ms | 433 / 541 ms | 2,047 / 2,087 ms | 4,136 / 4,326 ms | 1,830 | 5.1 s | 62.7 ms | — |
| `rules+pf-nemotron:pii` | 5.2 / 9.2 ms | 20.1 / 21.7 ms | 96.0 / 100 ms | 251 / 265 ms | 30,462 | 3.0 s | 12.5 ms | 5,072 MB |
| `rules+gliner-nvidia:pii` | 55.1 / 108 ms | 678 / 793 ms | 3,085 / 3,247 ms | 6,235 / 6,493 ms | 1,229 | 6.0 s | 152 ms | — |

## Missed secrets

- `credsweeper`: 8 missed: secret-023 (slack-webhook, ctx:k8s-b64) aHR0… (108 chars); secret-026 (private-key, ctx:file) ----… (1361 chars); secret-028 (private-key, ctx:yaml) ----… (960 chars); secret-043 (password, ctx:xml) 7M+R… (16 chars); secret-046 (contextual, hex) d17e… (32 chars); secret-047 (contextual, prose-password) bH1g… (17 chars); secret-048 (contextual, cli-flag) SZyQ… (40 chars); secret-049 (contextual, traceback) KSLY… (32 chars)
- `gliner2`: 17 missed: long-003 (size:1k, secrets:3) gith… (93 chars); long-007 (size:4k, secrets:3) gith… (93 chars); long-010 (size:4k, secrets:2) gith… (93 chars); long-010 (size:4k, secrets:2) gith… (93 chars); long-015 (size:8k, secrets:3) gith… (93 chars); secret-001 (aws-secret, ctx:python) zL+d… (40 chars); secret-008 (slack-webhook, ctx:compose) http… (79 chars); secret-023 (slack-webhook, ctx:k8s-b64) aHR0… (108 chars); secret-026 (private-key, ctx:file) ----… (1361 chars); secret-027 (private-key, ctx:file) ----… (1759 chars); secret-028 (private-key, ctx:yaml) ----… (960 chars); secret-029 (private-key, ctx:json) ----… (1704 chars)
- `gliner-nvidia`: 21 missed: long-006 (size:1k, secrets:2) hf_H… (37 chars); long-011 (size:4k, secrets:3) AKIA… (20 chars); long-011 (size:4k, secrets:3) UHuW… (40 chars); secret-008 (slack-webhook, ctx:compose) http… (79 chars); secret-026 (private-key, ctx:file) ----… (1361 chars); secret-027 (private-key, ctx:file) ----… (1759 chars); secret-028 (private-key, ctx:yaml) ----… (960 chars); secret-029 (private-key, ctx:json) ----… (1704 chars); secret-031 (env-file, google) eyJh… (153 chars); secret-032 (env-file, sendgrid) sk_l… (32 chars); secret-033 (env-file, jwt) eyJh… (153 chars); secret-033 (env-file, jwt) rk_l… (32 chars)
- `pf-nemotron`: 18 missed: long-011 (size:4k, secrets:3) AKIA… (20 chars); long-015 (size:8k, secrets:3) xoxb… (56 chars); secret-002 (github, ctx:js) ghp_… (40 chars); secret-007 (slack, ctx:terraform) xoxb… (56 chars); secret-008 (slack-webhook, ctx:compose) http… (79 chars); secret-013 (gitlab, ctx:python) glpa… (26 chars); secret-015 (aws, ctx:yaml) AKIA… (20 chars); secret-030 (env-file, github) ghs_… (40 chars); secret-030 (env-file, github) npm_… (40 chars); secret-032 (env-file, sendgrid) sk_l… (32 chars); secret-033 (env-file, jwt) rk_l… (32 chars); secret-035 (connection-string, postgres) cRcX… (13 chars)
- `rules+pf`: 0 missed
- `rules+gliner2`: 0 missed
- `rules+pf-nemotron`: 1 missed: secret-046 (contextual, hex) d17e… (32 chars)
- `rules+gliner-nvidia`: 0 missed
- `rules+credsweeper+pf`: 0 missed
- `rules+pf:pii`: 0 missed
- `rules+gliner2:pii`: 0 missed
- `rules+pf-nemotron:pii`: 1 missed: secret-046 (contextual, hex) d17e… (32 chars)
- `rules+gliner-nvidia:pii`: 0 missed

## Flagged hard negatives (secrets scope)

- `credsweeper`: 1 spans: neg-008 credsweeper 0x74… (42 chars)
- `gliner2`: 30 spans: neg-001 gliner2 ca89… (64 chars); neg-001 gliner2 7076… (64 chars); neg-001 gliner2 5536… (64 chars); neg-002 gliner2 ecf4… (64 chars); neg-002 gliner2 ecf4… (64 chars); neg-003 gliner2 fake… (10 chars); neg-003 gliner2 fake… (10 chars); neg-003 gliner2 fake… (22 chars); neg-003 gliner2 test… (9 chars); neg-003 gliner2 test… (9 chars); neg-003 gliner2 test… (10 chars); neg-003 gliner2 test… (9 chars)
- `gliner-nvidia`: 12 spans: neg-000 gliner-nvidia 31c5… (64 chars); neg-001 gliner-nvidia 7076… (64 chars); neg-002 gliner-nvidia ecf4… (64 chars); neg-003 gliner-nvidia test… (9 chars); neg-003 gliner-nvidia test… (9 chars); neg-003 gliner-nvidia fake… (10 chars); neg-004 gliner-nvidia YOUR… (17 chars); neg-007 gliner-nvidia sha3… (71 chars); neg-008 gliner-nvidia 0x74… (42 chars); neg-010 gliner-nvidia OPEN… (17 chars); neg-010 gliner-nvidia ANTH… (24 chars); neg-013 gliner-nvidia db-p… (11 chars)
- `pf-nemotron`: 3 spans: neg-000 pf-nemotron 3827… (46 chars); neg-001 pf-nemotron --ha… (78 chars); neg-010 pf-nemotron # LO… (16 chars)
- `rules+pf`: 4 spans: neg-000 rules:entropy dist… (21 chars); neg-008 rules:secret-assignment|pf 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment sk-a… (10 chars)
- `rules+gliner2`: 12 spans: neg-000 rules:entropy dist… (21 chars); neg-003 gliner2 test… (9 chars); neg-003 gliner2 test… (10 chars); neg-003 gliner2 test… (9 chars); neg-006 gliner2 secr… (17 chars); neg-006 gliner2 secr… (17 chars); neg-007 gliner2 sha3… (71 chars); neg-008 rules:secret-assignment|gliner2 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment|gliner2 sk-a… (10 chars); neg-013 gliner2 chec… (20 chars); neg-013 gliner2 db-p… (11 chars)
- `rules+pf-nemotron`: 5 spans: neg-000 rules:entropy dist… (21 chars); neg-001 pf-nemotron --ha… (78 chars); neg-008 rules:secret-assignment 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment sk-a… (10 chars)
- `rules+gliner-nvidia`: 8 spans: neg-000 rules:entropy dist… (21 chars); neg-003 gliner-nvidia test… (9 chars); neg-003 gliner-nvidia test… (9 chars); neg-007 gliner-nvidia sha3… (71 chars); neg-008 rules:secret-assignment|gliner-nvidia 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment sk-a… (10 chars); neg-013 gliner-nvidia db-p… (11 chars)
- `rules+credsweeper+pf`: 4 spans: neg-000 rules:entropy dist… (21 chars); neg-008 rules:secret-assignment|credsweeper|pf 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment sk-a… (10 chars)
- `rules+pf:pii`: 4 spans: neg-000 rules:entropy dist… (21 chars); neg-008 rules:secret-assignment|pf 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment sk-a… (10 chars)
- `rules+gliner2:pii`: 12 spans: neg-000 rules:entropy dist… (21 chars); neg-003 gliner2 test… (9 chars); neg-003 gliner2 test… (10 chars); neg-003 gliner2 test… (9 chars); neg-006 gliner2 secr… (17 chars); neg-006 gliner2 secr… (17 chars); neg-007 gliner2 sha3… (71 chars); neg-008 rules:secret-assignment|gliner2 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment|gliner2 sk-a… (10 chars); neg-013 gliner2 chec… (20 chars); neg-013 gliner2 db-p… (11 chars)
- `rules+pf-nemotron:pii`: 5 spans: neg-000 rules:entropy dist… (21 chars); neg-001 pf-nemotron --ha… (78 chars); neg-008 rules:secret-assignment 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment sk-a… (10 chars)
- `rules+gliner-nvidia:pii`: 8 spans: neg-000 rules:entropy dist… (21 chars); neg-003 gliner-nvidia test… (9 chars); neg-003 gliner-nvidia test… (9 chars); neg-007 gliner-nvidia sha3… (71 chars); neg-008 rules:secret-assignment|gliner-nvidia 0x74… (42 chars); neg-010 rules:secret-assignment s… (6 chars); neg-010 rules:secret-assignment sk-a… (10 chars); neg-013 gliner-nvidia db-p… (11 chars)
