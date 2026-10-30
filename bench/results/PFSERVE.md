# pf-serve vs MLX

Oct 25, 2026 · Apple M5 Pro, 64 GB, macOS 27.0.1. Raw tables: [`pfserve-data.md`](pfserve-data.md), [`pfserve-holdout.md`](pfserve-holdout.md), [`pfserve-holdout2.md`](pfserve-holdout2.md).

The question: can keepmum run OpenAI Privacy Filter through pf-serve (privacy-filter.cpp on ggml, a separate process; see `native/pf-serve`) instead of MLX, without losing accuracy? pf-serve needs no Python ML packages and also builds for Windows and Linux.

Both runs use the same pipeline (rules, then the model, then keepmum's refinement), the same datasets and the same machine, in the same session. MLX runs `mlx-community/openai-privacy-filter-8bit`. pf-serve runs `LocalAI-io/privacy-filter-GGUF` `privacy-filter-q8.gguf` at revision `935d868`, SHA-256 `80efc180…998c`, threshold 0.

## Secrets (`pii = false`)

| Dataset | Recall MLX / pf-serve | Precision MLX / pf-serve | Hard negatives flagged | p95 ≤ 4K tokens MLX / pf-serve |
| --- | --- | --- | --- | --- |
| Dev | 0.989 / 0.989 | 0.850 / 0.867 | 1/40 / 1/40 | 86 / 110 ms |
| Held-out 1 | 1.000 / 1.000 | 0.769 / 0.782 | 0/15 / 0/15 | 86 / 99 ms |
| Held-out 2 | 1.000 / 1.000 | 0.797 / 0.803 | 9/15 / 9/15 | 167 / 140 ms |

The same secrets are found and missed: the one dev miss (`secret-047`, a password in prose) is shared, and every flagged hard negative is the same span.

## Personal data (`pii = true`)

| Dataset | Recall MLX / pf-serve | Precision MLX / pf-serve | Hard negatives flagged |
| --- | --- | --- | --- |
| Dev | 0.996 / 0.996 | 0.893 / 0.903 | 3/40 / 3/40 |
| Held-out 1 | 1.000 / 1.000 | 0.838 / 0.852 | 3/15 / 2/15 |
| Held-out 2 | 1.000 / 0.996 | 0.869 / 0.878 | 9/15 / 9/15 |

One difference: on held-out 2, pf-serve misses a UK IBAN in prose (`pii-036`, "asking for the refund to go to GB32… instead of the card") that MLX finds. The cause is not calibration (the MLX model's Viterbi biases are all zero). It is the GGUF weights or privacy-filter.cpp's decoding. No rule covers IBANs.

## Resources

| | MLX 8-bit (in the keepmum process) | pf-serve (own process) |
| --- | --- | --- |
| Model load | 2.8 to 6.5 s | 0.6 to 0.7 s (the first run after a build: about 7 s, compiling Metal kernels) |
| Memory | 2.2 to 2.5 GB | 1.69 GB, measured with `ps` (the tables' "Peak RSS" counts only the Python side) |
| Install | `mlx`, `mlx-lm`, `mlx-embeddings`, `numpy`, `tokenizers`: about 500 MB | one 2.4 MB binary |
| Platforms | Apple silicon | macOS (Metal), Windows and Linux (Vulkan or CPU) |

Latency at 4K and 8K tokens differs by run in both directions (held-out 2 ran slower for MLX than in `v1-holdout2.md`), so the two are about even.

## After the switch: pf-serve with the IBAN rule, and held-out 3

Oct 26, 2026. Raw tables: [`v2-data.md`](v2-data.md), [`v2-holdout.md`](v2-holdout.md), [`v2-holdout2.md`](v2-holdout2.md), [`v2-holdout3.md`](v2-holdout3.md), and MLX on held-out 3 for reference: [`mlx-holdout3.md`](mlx-holdout3.md).

Held-out 3 is new: seed 10 and 15 hand-written hard negatives (`HOLDOUT3_NEGATIVES` in `bench/negatives.py`), written after the IBAN rule and before any run on it. Nothing has been tuned on it.

| Dataset | Secret recall | Secret precision | Hard negatives flagged | PII recall / precision (`pii = true`) | p95 ≤ 4K tokens |
| --- | --- | --- | --- | --- | --- |
| Dev | 0.989 | 0.867 | 1/40 | 0.996 / 0.903 | 97 ms |
| Held-out 1 | 1.000 | 0.782 | 0/15 | 1.000 / 0.852 | 97 ms |
| Held-out 2 | 1.000 | 0.803 | 9/15 | 1.000 / 0.879 | 102 ms |
| **Held-out 3 (fresh)** | **0.989** | **0.868** | **3/15** | **0.992 / 0.928** | **95 ms** |

- The IBAN rule fixes the held-out 2 miss: ACCOUNT recall there is 1.00 (0.92 before).
- On held-out 3, pf-serve and MLX miss the same two values and flag the same three negatives, so neither gap comes from the runtime:
  - `secret-046`: "the Datadog key for staging is ‹32 hex› - please rotate it". The model labels the key an account number, so it was dropped as personal data (and kept out by the account-number filter with `pii = true`). Fixed below.
  - A person's name in a commit message (`pii = true`).
  - Flagged: a GitHub Actions SHA pin, AWS `sg-` and `vpc-` IDs, and an Xcode DerivedData folder name.

## Keys the model calls account numbers, and held-out 4

Oct 26, 2026. Raw tables: [`v3-data.md`](v3-data.md), [`v3-holdout.md`](v3-holdout.md), [`v3-holdout2.md`](v3-holdout2.md), [`v3-holdout3.md`](v3-holdout3.md), [`v3-holdout4.md`](v3-holdout4.md).

The change: a model span labeled `account_number` becomes a secret when a secret keyword (key, token, secret, password, …) is in the 40 characters before it, it has a digit, and it is not shaped like card or bank digits. On dev, the first version also flagged the header name `X-API-Key`; the digit condition removed that.

Held-out 4 (seed 11, 15 new hard negatives in `HOLDOUT4_NEGATIVES`) was written after the change and before any run. Several of its negatives put a key or token word before an identifier that is not a secret (idempotency keys, cache keys, S3 object keys, partition keys, token counts), the case this change could get wrong.

| Dataset | Secret recall | Secret precision | Hard negatives flagged | PII recall / precision (`pii = true`) | p95 ≤ 4K tokens |
| --- | --- | --- | --- | --- | --- |
| Dev | 0.989 | 0.867 | 1/40 | 0.996 / 0.903 | 102 ms |
| Held-out 1 | 1.000 | 0.782 | 0/15 | 1.000 / 0.852 | 100 ms |
| Held-out 2 | 1.000 | 0.803 | 9/15 | 1.000 / 0.879 | 103 ms |
| Held-out 3 (now tuned on) | 1.000 | 0.869 | 3/15 | 0.996 / 0.928 | 95 ms |
| **Held-out 4 (fresh)** | **1.000** | **0.845** | **3/15** | **1.000 / 0.900** | **95 ms** |

- Held-out 3's Datadog key is found; nothing new is flagged on any set.
- On held-out 4, the change itself flags none of the 15 negatives (checked by running them with it off: the same three spans). The three come from refinement that keeps identifiers after a keyword, which predates this: an `Idempotency-Key` UUID, an HTTP public-key pin, and a Bazel action cache key.
