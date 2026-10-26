# pf-serve vs MLX

Oct 25, 2026 · Apple M5 Pro, 64 GB, macOS 27.0.1. Raw tables: [`pfserve-data.md`](pfserve-data.md), [`pfserve-holdout.md`](pfserve-holdout.md), [`pfserve-holdout2.md`](pfserve-holdout2.md).

The question: can sotto run OpenAI Privacy Filter through pf-serve (privacy-filter.cpp on ggml, a separate process; see `native/pf-serve`) instead of MLX, without losing accuracy? pf-serve needs no Python ML packages and also builds for Windows and Linux.

Both runs use the same pipeline (rules, then the model, then sotto's refinement), the same datasets and the same machine, in the same session. MLX runs `mlx-community/openai-privacy-filter-8bit`. pf-serve runs `LocalAI-io/privacy-filter-GGUF` `privacy-filter-q8.gguf` at revision `935d868`, SHA-256 `80efc180…998c`, threshold 0.

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

| | MLX 8-bit (in the sotto process) | pf-serve (own process) |
| --- | --- | --- |
| Model load | 2.8 to 6.5 s | 0.6 to 0.7 s (the first run after a build: about 7 s, compiling Metal kernels) |
| Memory | 2.2 to 2.5 GB | 1.69 GB, measured with `ps` (the tables' "Peak RSS" counts only the Python side) |
| Install | `mlx`, `mlx-lm`, `mlx-embeddings`, `numpy`, `tokenizers`: about 500 MB | one 2.4 MB binary |
| Platforms | Apple silicon | macOS (Metal), Windows and Linux (Vulkan or CPU) |

Latency at 4K and 8K tokens differs by run in both directions (held-out 2 ran slower for MLX than in `v1-holdout2.md`), so the two are about even.
