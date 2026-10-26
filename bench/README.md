# Benchmark

Accuracy, latency and memory per detector, on synthetic labeled data. The runtime is pf-serve; the
other detectors are earlier candidates, kept here so the results in `results/` can be re-run.

```sh
uv run python bench/gen.py                                   # writes bench/data/*.jsonl (seed 7)
uv run python bench/run.py                                   # rules, rules+pf-serve, rules+pf-serve:pii
uv run python bench/run.py --detectors rules,rules+pf-serve  # a subset; --data, --out, --repeat, --limit
```

Held-out checks use new values and hand-written negatives never used for tuning:

```sh
uv run python bench/gen.py --seed 11 --negatives holdout4 --out /tmp/sotto-holdout4
uv run python bench/run.py --data /tmp/sotto-holdout4
```

Earlier sets: `--seed 8 --negatives holdout`, `--seed 9 --negatives holdout2`, `--seed 10 --negatives holdout3`. Each was written before its first run; `results/PFSERVE.md` and `results/PHASE0.md` say which have been tuned on since.

- `secrets.jsonl`, `pii.jsonl` and `long.jsonl` are generated: random values in provider formats. They are not committed, because provider-shaped strings trip GitHub push protection even when fake.
- `negatives.jsonl` comes from the hand-written lists in `negatives.py`.
- `pf-serve` is found where sotto finds it (`SOTTO_PF_SERVE` and `SOTTO_PF_MODEL` override): run `native/pf-serve/build.sh` and `sotto setup` first.
- Detection runs offline (`HF_HUB_OFFLINE=1`); models must already be downloaded.

## Earlier candidates

Each needs its dependency group and its weights:

| Detectors | Setup |
| --- | --- |
| `pf` (MLX bf16), `pf-8bit`, `pf-nemotron` (`pf_mlx.py`) | `uv sync --group mlx`, then `snapshot_download` of `mlx-community/openai-privacy-filter-bf16` / `-8bit` |
| `pf-torch` (`pf_mlx.py`) | `uv sync --group torch`, then `snapshot_download('openai/privacy-filter')` |
| `afm-cli`, `afm-sdk` (`afm.py`) | macOS 27 with Apple Intelligence; `uv sync --group afm` for the SDK |
| `gliner2`, `gliner-nvidia`, `credsweeper`, `piiranha` (`alt.py`) | `uv pip install gliner gliner2 credsweeper` |
| LLM judges (`judge.py`) | `uv sync --group mlx --group afm`; the Qwen judge needs `mlx-community/Qwen3-4B-Instruct-2507-4bit` |

Pipelines combine detectors with `+`, for example `rules+pf-8bit`, with flags `:pii` (personal data on), `:raw` (no secret-span refinement) and `:rawpii` (no personal-data refinement).
