# Phase 0 results and recommendation

Oct 25, 2026. Machine: Apple M5 Pro, 64 GB, macOS 27.0.1. The spec's reference machine is an M4 with 48 GB; expect somewhat slower numbers there.
Full tables: [`bench-20261025-013218.md`](bench-20261025-013218.md) (dev set) and [`holdout-20261025-015203.md`](holdout-20261025-015203.md) (held-out).

## Recommendation

**The default pipeline is `rules + pf` (L1 rules plus Privacy Filter on MLX, with L2 span refinement), with `pii = false` and no AFM.**

| | Dev set (150 records) | Held-out (seed 8, 15 unseen negatives) | Target |
| --- | --- | --- | --- |
| Secret recall | 0.989 | 1.000 | ≥ 0.98 ✅ |
| Hard negatives flagged | 1/40 (3%) | 3/15 (20%) | < 5% — ❌ held-out |
| p95, inputs ≤ 4K tokens | 87 ms | 83 ms | ≤ 150 ms ✅ |
| p95, 8K tokens | 199 ms | 199 ms | (no target) |
| Secret precision | 0.78 | 0.58 | — |

The false-positive target passes only on data I tuned against. Treat 20% as the honest number until the fixes below are validated on a third, fresh set.

## Findings

1. **The two layers cover each other's misses.** L1 rules alone reach 0.968 recall at 4 ms (p95 at 4K tokens) and flag no dev negatives, but they miss secrets that only context reveals: a hex key in prose, or a token passed as a CLI flag. L2 alone reaches only 0.895 recall: it misses Slack webhooks, base64-encoded Kubernetes secrets and some provider keys inside long files. Combined, only one secret was missed in 190 labeled secret spans across both sets: a password written in prose ("it's WAVC…").
2. **L2 needs post-processing.** Raw L2 secret precision is 0.27. The model tags UUIDs, hashes, request IDs and nearby `key=value` log fields as secrets. The model itself does this (the per-token argmax agrees), so the decoder isn't the cause. Refinement in `detect/pipeline.py` raises pipeline precision from 0.30 to 0.78 with no recall loss: it splits at whitespace, strips `label=` prefixes, narrows URLs to their password, and drops identifier shapes with no keyword before them. magpie arrived at the same filter independently (its `internal/redact/ids.go`).
3. **AFM is out of the default pipeline.**
   - *As a span extractor* (`afm-cli` / `afm-sdk`): recall 0.84–0.90, 25 of 40 negatives flagged, p95 27–29 s at 4K tokens, and it missed every PEM private key. It flags `${VAR}` references and docs example keys as secrets.
   - *As a judge on ambiguous spans*: 10 calls on the dev set, none cleared. It didn't clear the one remaining false positive (a base64 test fixture) either. It adds 1.5 s to the p95 at 4K tokens. With PII on it cleared 1 of 81 spans.
   - It never refused and never overflowed (the extractor works in 6,000-character chunks); there was one timeout in 176 CLI calls. The SDK is only about 10% faster than spawning `fm` for each call.
   - Keep it as an opt-in flag at most. Dropping L3 from the v1 scope would also be reasonable.
4. **MLX is the backend; PyTorch on MPS is not viable.** The accuracy is identical, but PyTorch runs 20–60× slower (p95 1.96 s against 83 ms at 4K tokens).
5. **8-bit weights.** `pf-8bit` matches bf16 on recall and latency and uses 1.25 GB less memory (2.5 GB against 3.8 GB peak RSS). Its precision is a little lower on the dev set (0.73 against 0.78) and equal on the held-out set. Because the model stays warm all day, I lean toward 8-bit, possibly in its own process as magpie does, so idle memory can be released.
6. **PII should stay off by default.** With PII on, 7 of 40 dev negatives and 4 of 15 held-out negatives are flagged. Precision is low for ACCOUNT (0.13), URL (0.31) and DATE (0.32); those flags are mostly timestamps and IDs. PERSON, EMAIL, PHONE and ADDRESS are good: recall 1.0 and precision 0.82–0.94. This answers the spec's open question.
7. **Latency fits the budget.** The cost grows quadratically with input length (dense band mask in the MLX port). The 8K-token p95 of 199 ms is over 150 ms, but the per-block cache means only new content is scanned each turn, which is usually far under 4K tokens. Cold start is 2.7 s, paid once when the proxy starts.

## Fixes before M1 (validate on a fresh seed plus new negatives)

From the held-out false positives:
- **L2 spans that start inside an identifier** (about 60 of 68 held-out false positives). Widen to the surrounding hex/UUID run, then drop it when that run is a UUID or 32+ hex digits. URL path segments get the same treatment.
- **Placeholders ending in `...`** (`sk-...`, `sk-ant-...`) in commented `.env` samples.
- **`0x…` addresses** assigned to a `*_TOKEN_*` name (e.g. `TOKEN_CONTRACT`). An `0x`-prefixed 40-hex value is an address, not a secret.
- **Entropy hits on URL paths** (`distributions/gradle-…`).

Lessons from magpie to adopt in M1/M2:
- Skip signed thinking blocks and protocol ids (`toolu_…`, tool names).
- A "known values" pass: once a value is masked, exact-match it everywhere in later requests.
- Never let a rule match a fragment of an ID.

## Caveats

- The dataset is synthetic. The held-out positives come from the same templates with new values, so they test generalization to new values, not new formats. A sample of real (scrubbed) Claude Code traffic would be the next step up.
- I fixed L1 rules after the first dev run. The dev numbers are optimistic; the held-out numbers are the ones to trust.
- AFM memory is not measured: the model runs in a system process.
- `mlx-embeddings` must be pinned to a git commit, because Privacy Filter support is unreleased on PyPI. That blocks Homebrew distribution until it ships.

## Update: v1 detection locked (Oct 25, later)

v1 is `rules + pf-8bit`, with secret and personal-data refinement and no LLM in the request path. The fixes listed above are applied:
- identifier runs around model spans,
- `...` placeholders,
- `0x` + 40-hex public addresses,
- entropy hits on key names.

Results: [`v1-data.md`](v1-data.md), [`v1-holdout.md`](v1-holdout.md), [`v1-holdout2.md`](v1-holdout2.md).

| Dataset | Secret recall | Secret precision | Hard negatives flagged | PII recall / precision (`pii = true`) | p95 ≤ 4K tokens |
| --- | --- | --- | --- | --- | --- |
| Dev (tuned on) | 0.989 | 0.85 | 1/40 | 1.000 / 0.93 | 86 ms |
| Held-out 1 (tuned on after the first review) | 1.000 | 0.77 | 0/15 | 1.000 / 0.89 | 86 ms |
| **Held-out 2 (fresh: seed 9, 15 new negatives, never tuned on)** | **1.000** | **0.80** | **9/15** | **1.000 / 0.92** | **82 ms** |

Held-out 2 is the honest number. Recall holds everywhere; no secret or personal value has been missed on any held-out set. But 9 of 15 fresh hard negatives are flagged, and each is a new identifier shape the rules have never seen:
- Python memory addresses (`0x7f…`), Azure subscription and resource IDs,
- Stripe object IDs (`ch_…`, `pi_…`), git short-SHA ranges (`1f2e3d4..5a6b7c8`),
- Kubernetes pod hashes, CI cache keys, Cloudflare ray IDs.

Fixing these one rule at a time doesn't converge: every held-out set has surfaced a new family. The secret-false-positive problem is now a classifier problem: "credential or identifier?" for a candidate span in context. See the training proposal.
