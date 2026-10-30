"""Judge benchmark: how well can a local LLM clear false positives without clearing real secrets?

Candidates are the spans the unrefined `rules+pf:pii` pipeline flags on the labeled datasets.
A candidate is *sensitive* when it covers at least half of a labeled span (clearing it leaks
that value) and a *false positive* when it touches no labeled span at all; partial overlaps
are left out. Each judge sees the span marked in ~200 characters of context.

    uv run python bench/judge.py --data bench/data --data /tmp/keepmum-holdout --judges afm-zero,afm-fewshot,qwen3-4b
Apple judges need `apple-fm-sdk` (the `afm` extra).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from keepmum.detect import Span
from keepmum.detect.pipeline import Pipeline
from keepmum.detect.rules import RulesDetector

from pf_mlx import PrivacyFilter  # noqa: E402  (bench/, the script's own directory)
from run import _covered, load_records, percentile  # noqa: E402

# The Qwen judge was briefly keepmum's opt-in L3. It was removed once the personal-data
# refinement made it redundant (it cleared 0 of 347 spans); it lives here for the record.

MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
CONTEXT_CHARS = 200

INSTRUCTIONS = (
    "You review one value that a secret scanner flagged. The value is marked with ⟦ and ⟧ in a short "
    "excerpt of a file or log. Decide whether it is a real secret or real personal data that must not "
    "leave this computer. Answer is_sensitive=false only when the value is clearly not sensitive: a "
    "placeholder, a documented example key, an obvious test fixture, a variable name, a hash or checksum, "
    "a UUID or other identifier, or a public value. When unsure, answer true."
)

# Hand-written, synthetic, and deliberately unlike any record in the benchmark datasets.
FEW_SHOT = [
    ('token = "⟦R7mQx2LwPz9vKd4TnB8sYh3F⟧"  # deploy bot', True, "random credential assigned to a token variable"),
    ("INFO GET /api/v1/invoices/⟦5b8e2c1a-7f3d-4e9b-a6c2-0d4f8e1b3a79⟧ 200", False, "a UUID in a URL path is a record id"),
    ("worker started request_id=⟦c41f9a07e2b3d856⟧ queue=emails", False, "a request id, not a credential"),
    ('"resolved": "...", "integrity": "⟦sha256-Qm9vYmFyYmF6cXV4cXV1eA==⟧"', False, "a package checksum"),
    ('STRIPE_KEY="⟦sk_live_REPLACE_ME⟧"', False, "a placeholder someone must replace"),
    ("the vpn password for the lab is ⟦Lk8!vQ2z#Rm4⟧, don't share it", True, "a password given in prose"),
    ("Contact: ⟦Priya Raman⟧ <priya.raman@corp.internal>, on-call this week", True, "a real person's name"),
    ('{"name": "⟦Jane Doe⟧", "email": "jane@example.com"}  // docs sample', False, "a placeholder name in a documented sample"),
]


def few_shot_text() -> str:
    lines = ["Examples:"]
    for excerpt, sensitive, why in FEW_SHOT:
        lines.append(f"Excerpt: {excerpt}\nis_sensitive: {str(sensitive).lower()} ({why})")
    return "\n\n".join(lines)


def excerpt(text: str, start: int, end: int) -> str:
    lo, hi = max(0, start - CONTEXT_CHARS), min(len(text), end + CONTEXT_CHARS)
    return f"{text[lo:start]}⟦{text[start:end]}⟧{text[end:hi]}"


SYSTEM_PROMPT = INSTRUCTIONS + "\n\n" + few_shot_text() + "\n\nReply with exactly one word: SENSITIVE or SAFE."


class LLMJudge:
    name = "judge-qwen3-4b"

    def __init__(self, repo: str = MODEL):
        from huggingface_hub import snapshot_download
        from mlx_lm import load

        # Like L2, the judge never touches the network: the model must already be downloaded.
        self.model, self.tokenizer = load(snapshot_download(repo, local_files_only=True))
        self.stats: Counter[str] = Counter()

    def ask(self, kind: str, snippet: str) -> bool | None:
        """True = sensitive, False = safe, None = no usable answer."""
        from mlx_lm import generate

        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Scanner type: {kind}\nExcerpt:\n{snippet}"}]
        prompt = self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False, enable_thinking=False)
        answer = generate(self.model, self.tokenizer, prompt=prompt, max_tokens=6, verbose=False).strip().upper()
        if answer.startswith("SENSITIVE"):
            return True
        if answer.startswith("SAFE"):
            return False
        return None

    def is_sensitive(self, text: str, span: Span) -> bool:
        self.stats["calls"] += 1
        try:
            verdict = self.ask(span.type, excerpt(text, span.start, span.end))
        except Exception:
            verdict = None
        if verdict is None:
            self.stats["no_answer"] += 1
            return True
        if not verdict:
            self.stats["cleared"] += 1
        return verdict


# --- Candidates -----------------------------------------------------------------------


def build_candidates(data_dirs: list[Path], per_class: int, seed: int) -> list[dict]:
    pipe = Pipeline(RulesDetector(), PrivacyFilter("mlx"), pii=True, refine=False)
    pools: dict[str, list[dict]] = {"secret+": [], "secret-": [], "pii+": [], "pii-": []}
    for d in data_dirs:
        for rec in load_records(d):
            text = rec["text"]
            gold = [(s["start"], s["end"]) for s in rec["spans"]]
            for s in pipe.detect(text):
                covers_gold = any(_covered(g0, g1, [(s.start, s.end)]) >= 0.5 * (g1 - g0) for g0, g1 in gold)
                touches = _covered(s.start, s.end, gold) > 0
                if covers_gold:
                    label = True
                elif not touches:
                    label = False
                else:
                    continue
                kind = "secret" if s.type == "SECRET" else "pii"
                pools[f"{kind}{'+' if label else '-'}"].append({
                    "id": f"{d.name}/{rec['id']}@{s.start}", "group": rec["tags"][0], "type": s.type,
                    "sensitive": label, "excerpt": excerpt(text, s.start, s.end), "value_len": s.end - s.start,
                })
    rng = random.Random(seed)
    out = []
    for key, pool in pools.items():
        # Keep every hard-negative false positive; sample the rest.
        must = [c for c in pool if c["group"] == "negatives"]
        rest = [c for c in pool if c["group"] != "negatives"]
        rng.shuffle(rest)
        out += (must + rest)[: max(per_class, len(must))]
        print(f"candidates {key}: {len(pool)} found, {min(len(pool), max(per_class, len(must)))} used", file=sys.stderr)
    return out


# --- Judges ---------------------------------------------------------------------------


class AppleJudge:
    def __init__(self, variant: str):
        import apple_fm_sdk as fm

        self.fm = fm
        self.variant = variant
        use_case = fm.SystemLanguageModelUseCase.CONTENT_TAGGING if "tagging" in variant else fm.SystemLanguageModelUseCase.GENERAL
        self.model = fm.SystemLanguageModel(use_case=use_case, guardrails=fm.SystemLanguageModelGuardrails.PERMISSIVE_CONTENT_TRANSFORMATIONS)
        self.options = fm.GenerationOptions(sampling=fm.SamplingMode.greedy())
        self.instructions = INSTRUCTIONS + ("\n\n" + few_shot_text() if "fewshot" in variant or "batch" in variant else "")
        self.batch = 8 if "batch" in variant else 1
        props = {"is_sensitive": {"type": "boolean"}}
        order = ["is_sensitive"]
        if "reason" in variant:
            props = {"reason": {"type": "string", "description": "one short sentence"}, **props}
            order = ["reason", "is_sensitive"]
        verdict = {"title": "Verdict", "type": "object", "additionalProperties": False, "required": order, "x-order": order, "properties": props}
        if self.batch > 1:
            item = {**verdict, "required": ["id", *order], "x-order": ["id", *order], "properties": {"id": {"type": "integer"}, **props}}
            self.schema = {"title": "Verdicts", "type": "object", "additionalProperties": False, "required": ["verdicts"],
                           "x-order": ["verdicts"], "properties": {"verdicts": {"type": "array", "items": item}}}
        else:
            self.schema = verdict
        self.loop = asyncio.new_event_loop()
        self.errors = 0

    async def _ask(self, prompt: str):
        session = self.fm.LanguageModelSession(instructions=self.instructions, model=self.model)
        return await session.respond(prompt, json_schema=self.schema, options=self.options)

    def judge(self, cands: list[dict]) -> list[bool | None]:
        if self.batch == 1:
            prompt = f"Scanner type: {cands[0]['type']}\nExcerpt:\n{cands[0]['excerpt']}"
        else:
            prompt = "Judge each numbered excerpt separately.\n\n" + "\n\n".join(
                f"[{i}] Scanner type: {c['type']}\nExcerpt:\n{c['excerpt']}" for i, c in enumerate(cands))
        try:
            content = self.loop.run_until_complete(asyncio.wait_for(self._ask(prompt), 30))
            data = json.loads(content.to_json())
        except Exception:
            self.errors += 1
            return [None] * len(cands)
        if self.batch == 1:
            return [data.get("is_sensitive")]
        got = {v.get("id"): v.get("is_sensitive") for v in data.get("verdicts", [])}
        return [got.get(i) for i in range(len(cands))]


class QwenJudge:
    """The production judge (keepmum.detect.judge), asked directly."""

    def __init__(self, repo: str):
        self.judge = LLMJudge(repo)
        self.errors = 0
        self.batch = 1

    def judge_spans(self, cands):
        c = cands[0]
        verdict = self.judge.ask(c["type"], c["excerpt"])
        self.errors += verdict is None
        return [verdict]


def make_judge(name: str):
    if name.startswith("afm-"):
        return AppleJudge(name)
    repos = {"qwen3-4b": "mlx-community/Qwen3-4B-Instruct-2507-4bit", "qwen3-1.7b": "mlx-community/Qwen3-1.7B-4bit"}
    return QwenJudge(repos[name])


# --- Run ------------------------------------------------------------------------------


def evaluate(name: str, cands: list[dict]) -> dict:
    judge = make_judge(name)
    ask = judge.judge_spans if isinstance(judge, QwenJudge) else judge.judge
    ask(cands[:1])  # warm up
    verdicts, per_span_ms = [], []
    for i in range(0, len(cands), judge.batch):
        group = cands[i : i + judge.batch]
        t = time.perf_counter()
        verdicts += ask(group)
        per_span_ms += [(time.perf_counter() - t) * 1000 / len(group)] * len(group)
    res = {"judge": name, "errors": judge.errors, "unanswered": sum(v is None for v in verdicts),
           "p50_ms": percentile(per_span_ms, 0.5), "p95_ms": percentile(per_span_ms, 0.95)}
    for kind in ("secret", "pii"):
        in_kind = [((c["type"] == "SECRET") == (kind == "secret"), c["sensitive"], v) for c, v in zip(cands, verdicts)]
        pos = [v for ok, sens, v in in_kind if ok and sens]
        neg = [v for ok, sens, v in in_kind if ok and not sens]
        # None (error, refusal, timeout) counts as sensitive: the judge fails closed.
        res[kind] = {"sensitive": len(pos), "leaked": sum(v is False for v in pos),
                     "false_pos": len(neg), "cleared": sum(v is False for v in neg)}
    misses = [c["id"] for c, v in zip(cands, verdicts) if c["sensitive"] and v is False]
    res["leaked_ids"] = misses
    return res


def render(results: list[dict], n: int) -> str:
    L = [f"# Judge benchmark — {datetime.now():%Y-%m-%d %H:%M}", "",
         f"{n} candidate spans. *Leaked* = real secrets or personal data the judge cleared (must be ~0). "
         "*FP cleared* = false positives it correctly removed. Errors count as sensitive (fail closed).", "",
         "| Judge | Secrets leaked | Secret FPs cleared | PII leaked | PII FPs cleared | Errors | p50 / p95 per span |",
         "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in results:
        s, p = r["secret"], r["pii"]
        L.append(f"| `{r['judge']}` | {s['leaked']}/{s['sensitive']} | {s['cleared']}/{s['false_pos']} ({s['cleared'] / max(1, s['false_pos']):.0%}) "
                 f"| {p['leaked']}/{p['sensitive']} | {p['cleared']}/{p['false_pos']} ({p['cleared'] / max(1, p['false_pos']):.0%}) "
                 f"| {r['unanswered']} | {r['p50_ms']:.0f} / {r['p95_ms']:.0f} ms |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, action="append", required=True)
    ap.add_argument("--judges", default="afm-zero,afm-tagging,afm-fewshot,afm-reason,afm-batch,qwen3-4b,qwen3-1.7b")
    ap.add_argument("--per-class", type=int, default=100)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--out", type=Path, default=Path("bench/results"))
    args = ap.parse_args()
    cands = build_candidates(args.data, args.per_class, args.seed)
    results = []
    for name in args.judges.split(","):
        print(f"[judge] {name}", file=sys.stderr, flush=True)
        results.append(evaluate(name, cands))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"judge-{stamp}.json").write_text(json.dumps({"candidates": len(cands), "results": results}, indent=2))
    md = render(results, len(cands))
    (args.out / f"judge-{stamp}.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
