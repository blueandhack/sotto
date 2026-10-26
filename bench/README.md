# Phase 0 benchmark

```sh
uv sync --all-extras
uv run python -c "from huggingface_hub import snapshot_download as d; d('mlx-community/openai-privacy-filter-bf16'); d('mlx-community/openai-privacy-filter-8bit')"
uv run python bench/gen.py                      # writes bench/data/*.jsonl (seed 7)
uv run sotto bench                               # all detectors -> bench/results/bench-<stamp>.{json,md}
uv run sotto bench --detectors rules,rules+pf    # a subset
```

Held-out check, with new values (seed 8) and hand-written negatives never used for tuning:

```sh
uv run python bench/gen.py --seed 8 --negatives holdout --out /tmp/sotto-holdout
uv run sotto bench --detectors rules,rules+pf --data /tmp/sotto-holdout
```

- `secrets.jsonl`, `pii.jsonl` and `long.jsonl` are generated: random values in provider formats. They are not committed, because provider-shaped strings trip GitHub push protection even when fake.
- `negatives.jsonl` comes from the hand-written list in `negatives.py`.
- Detection runs offline (`HF_HUB_OFFLINE=1`); models must already be downloaded.
- The PyTorch comparison (`pf-torch`) also needs `snapshot_download('openai/privacy-filter')`.

Detectors: `rules`, `pf` (MLX bf16), `pf-8bit`, `pf-torch`, `afm-cli`, `afm-sdk`, and pipelines such as `rules+pf`, `rules+pf+qwen:pii` (the opt-in Qwen judge reviews personal-data spans; it needs `snapshot_download("mlx-community/Qwen3-4B-Instruct-2507-4bit")`), with flags `:pii` (personal data on) and `:raw` (no L2 span refinement).
