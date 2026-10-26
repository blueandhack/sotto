# Local models on macOS: which detector, and how to use the Apple model

Oct 25, 2026 · Apple M5 Pro, 64 GB, macOS 27.0.1. Raw tables: [`candidates-dev.md`](candidates-dev.md), [`candidates-holdout.md`](candidates-holdout.md), [`judge-*.md`](.).

## 1. Best local detector: OpenAI Privacy Filter (MLX), unchanged

Candidates were chosen from 2026 work on PII and secret detection. Each ran alone and behind our L1 rules, with the same L2 span refinement.

Secrets, default config (`pii = false`), behind L1 rules:

| L2 model | Recall (dev / held-out) | Negatives flagged (dev / held-out) | p95 ≤ 4K tokens | Memory |
| --- | --- | --- | --- | --- |
| **OpenAI Privacy Filter (MLX)** | 0.989 / 1.000 | **1/40 / 3/15** | **88 ms** | 3.8 GB (2.5 GB 8-bit) |
| GLiNER2-PII (fastino, 205M) | 1.000 / 1.000 | 15/40 / 7/15 | 2,070 ms | 3.0 GB |
| NVIDIA GLiNER-PII | 1.000 / 1.000 | 13/40 / 6/15 | 3,250 ms | 3.9 GB |
| OpenMed Privacy Filter Nemotron (fine-tune) | 0.989 / 0.989 | 8/40 / 4/15 | 105 ms | 3.8 GB |
| CredSweeper (rules + ML), added to rules + Privacy Filter | 0.989 / 1.000 | 2/40 / 3/15 | 109 ms | +0.1 GB |

- **GLiNER2-PII and NVIDIA GLiNER-PII** are the best published PII models. Behind our rules, their secret precision is higher (0.88–0.90 held-out). But they flag 40–47% of hard negatives (placeholders, hashes, IDs) and are 20–40× slower. Their encoders take about 384 words at a time, so long inputs need chunking, and they run on PyTorch with no MLX port. For personal data alone, GLiNER2 has the best PII precision (0.66 vs 0.62) but flags 57% of negatives, against 17% for Privacy Filter.
- **The Nemotron fine-tune** is better at people, phones and addresses (precision 0.97–1.00), worse at secrets (precision 0.18 alone), and misses most dates. It trades secret quality for PII granularity, which is the wrong trade for sotto.
- **CredSweeper** is fast (0.1 ms p50, 224 MB) and drops placeholders well. It adds no recall over our rules and Privacy Filter, but flags UUIDs as secrets (precision 0.12 in the pipeline). It isn't worth the dependency.

**Verdict:** keep OpenAI Privacy Filter on MLX. Nothing local beats it on the combination that matters here: secret recall, hard-negative noise and latency. The best upgrade to try later is a small-PII-model fallback (GLiNER2) only for the `pii = true` path, if users ask for more PII precision.

## 2. Best way to use the Apple on-device model

400 candidate spans from the unrefined pipeline on both datasets: 100 real secrets, 100 secret false positives, 100 real PII, 100 PII false positives. *Leaked* means a real value the judge cleared. That has to be about zero, because a judge that clears a real secret causes a leak.

| Judge | Secrets leaked | Secret FPs cleared | PII leaked | PII FPs cleared | Per span (p50) |
| --- | --- | --- | --- | --- | --- |
| Apple, zero-shot | 4 | 3% | 3 | 6% | 386 ms |
| Apple, few-shot (8 examples) | **1** | 3% | 1 | 15% | 560 ms |
| Apple, content-tagging use case | 69 | 91% | 84 | 99% | 442 ms |
| Apple, reason before verdict | 21 | 68% | 22 | 80% | 933 ms |
| Apple, 8 spans per call | 2 | 14% | 14 | 33% | 413 ms (47 unanswered) |
| **Qwen3-4B-Instruct (MLX 4-bit)** | **0** | **18%** | **0** | **27%** | **246 ms** |
| Qwen3-1.7B (MLX 4-bit) | 100 | 100% | 100 | 100% | 105 ms |

Findings:
- **Prompting doesn't fix the trade-off.** Each variant either clears almost nothing or leaks badly.
  - *Zero-shot and few-shot* are cautious and clear only 3% of secret false positives.
  - *Content-tagging mode and reasoning first* make it clear most spans, including real secrets: 21–69 leaked per 100.
  - *Batching* is cheaper per span, but in 47 cases the model didn't answer for every numbered span.
- **The best Apple setting** is general use case, few-shot, greedy, one span per call, a fresh session each time, and the permissive guardrail mode. Even so, it is only marginally useful. (Since dropped: the Apple judge was removed from sotto after this benchmark.)
- **Qwen3-4B on MLX beats the Apple model** on every axis: no leaks, more false positives cleared, and lower latency. It costs a 2.3 GB download and memory.
- **No judge comes close to the refinement rules.** The deterministic refinement removed 88% of false positives (207 → 25 on the dev set) with no recall loss, in microseconds. Rules are the right tool for "is this a UUID or a placeholder"; LLM judges aren't.
- **Custom adapters** (LoRA on the Apple model) could change the picture, but today they are Swift-only and need Apple's adapter-training entitlement. Neither the Python SDK (0.2.1) nor the `fm` CLI can load one.

**Verdict:**
- **Keep the Apple model off the request path.** That includes judging spans: it can't clear false positives without leaking.
- **Where it can still earn its place:** jobs where a wrong answer can't leak anything:
  - explaining findings in `sotto scan` and `sotto doctor`,
  - suggesting allowlist entries for the user to approve,
  - adding, never removing, spans in a slow offline audit of transcripts.
- **If a judge is wanted later,** use Qwen3-4B on MLX, opt-in only, for the `pii = true` path. That is where false positives are most frequent (17–27% of negatives flagged).

## Caveats

- The data is synthetic, and the judge candidates come from the same records. The few-shot examples are hand-written and deliberately unlike the dataset.
- GLiNER latency is with the reference PyTorch runtimes (`gliner`, `gliner2`). ONNX or CoreML exports might be 2–5× faster, but that wouldn't fix the false-positive rate.
- Qwen3-1.7B answered "SAFE" to everything, despite the instruction to answer SENSITIVE when unsure. Small models are not safe judges.

## 3. Personal-data precision (added later on Oct 25)

How to read it: **precision** is the share of flagged values that really were personal data. At 0.55, almost half of what sotto redacted with `pii = true` was unnecessary. Those values were mostly request IDs tagged as account numbers, log timestamps tagged as dates, and API paths tagged as URLs, which are exactly what Claude needs to read logs. **Recall** is the share of real personal data caught. A recall loss is a leak.

Raw tables: [`pii-refine-dev.md`](pii-refine-dev.md), [`pii-refine-holdout.md`](pii-refine-holdout.md). Personal-data types only (dev / held-out):

| Setup | PII recall | PII precision | False alarms | p95 ≤ 4K tokens |
| --- | --- | --- | --- | --- |
| rules + Privacy Filter, no PII refinement | 1.000 / 1.000 | 0.55 / 0.61 | 131 / 99 | 87 ms |
| **rules + Privacy Filter + PII refinement** | **1.000 / 1.000** | **0.93 / 0.90** | **13 / 17** | **88 ms** |
| + Qwen3-4B judge | 1.000 / 1.000 | 0.93 / 0.90 | 13 / 17 (cleared 0 of 347 reviewed) | 1.3–1.4 s |
| Piiranha (DeBERTa, 280M) for PII | 0.75 / 0.82 | 0.92 / 0.95 | 15 / 9 | 965 ms |

- **PII refinement** (`Pipeline.keep_pii`) is deterministic and costs nothing. It drops:
  - account numbers that are neither card/bank digits nor preceded by an account keyword,
  - dates with a time of day,
  - URLs without a scheme,
  - RFC 2606 example domains,
  - NANP fictional numbers (555-0100 to 555-0199),
  - lowercase identifiers tagged as names.

  It is on whenever `pii = true`.
- **Piiranha**, the most precise small model found, misses 18–25% of personal data (half of all names) and is 10× slower. No small model tested beats Privacy Filter plus refinement.
- **After refinement, the Qwen judge cleared nothing**: 0 of 347 spans across both sets. Everything it used to clear, the rules now remove first. It no longer earns its 2.2 GB and its seconds of latency.
- **Remaining false alarms** are mostly debatable: role addresses (`support@acme-shop.com`), placeholder people in fixtures ("John Doe"), and an order number read as an address.
