"""The benchmark: which detectors are accurate and fast enough for the request path.

    uv run python bench/run.py --detectors rules,rules+pf-serve --data bench/data

Each detector runs in its own subprocess so cold start and peak memory are measured cleanly.
Results never contain sensitive values: spans are offsets, and reports show masked previews.
"""

from __future__ import annotations

import json
import os
import platform
import resource
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from importlib import metadata
from pathlib import Path

from sotto.detect import TYPES
from sotto.detect.pipeline import Pipeline

DEFAULT_DETECTORS = "rules,rules+pf-serve,rules+pf-serve:pii"

# Starting targets from the spec; adjust after the first run.
TARGET_SECRET_RECALL = 0.98
TARGET_NEGATIVE_FP = 0.05
TARGET_P95_MS = 150.0
MIN_OVERLAP = 0.5

SCOPES = ("secrets", "all")


# --- Detector construction (runs in the worker) -------------------------------------


class CandidatePipeline(Pipeline):
    """Benchmark candidates on top of the shipped pipeline: more secret detectors unioned in
    (`extra`), or a separate personal-data model that replaces the model's own (`pii_detector`)."""

    def __init__(self, rules, pf, extra=(), pii_detector=None, **kw):
        super().__init__(rules, pf, **kw)
        self.extra, self.pii_detector = list(extra), pii_detector
        base, _, flags = self.name.partition(":")
        parts = base.split("+")
        parts[1:1] = [d.name for d in self.extra]
        if pii_detector:
            parts.append(pii_detector.name)
        self.name = "+".join(parts) + (":" + flags if flags else "")

    def model_spans(self, text):
        out = [s for d in self.extra for s in d.detect(text)]
        if self.pii_detector is None:
            return out + super().model_spans(text)
        pii, self.pii = self.pii, False  # the model reports secrets only
        try:
            out += super().model_spans(text)
        finally:
            self.pii = pii
        if self.pii:
            found = [s for s in self.pii_detector.detect(text) if s.type != "SECRET"]
            self.funnel["candidates_model"] += len(found)
            out += found
        return out


def make_detector(spec: str):
    """`rules`, `pf[-8bit|-torch|-serve]`, `afm-cli`, `afm-sdk`, or a pipeline such as `rules+pf-8bit:pii`.

    Pipeline flags, each after a `:`: `pii` enables personal data, `raw` skips L2 secret-span refinement,
    `rawpii` skips personal-data refinement. `piiranha` in a pipeline replaces pf for personal data.
    """
    name, _, flags = spec.partition(":")
    parts = name.split("+")
    if len(parts) == 1:
        if name == "rules":
            from sotto.detect.rules import RulesDetector

            return RulesDetector()
        if name == "pf-nemotron":
            from pf_mlx import PrivacyFilter

            return PrivacyFilter("mlx", model="OpenMed/privacy-filter-nemotron", name="pf-nemotron")
        if name == "pf-serve":
            from sotto.detect.pfserve import PfServe, find_binary, find_model

            binary, model = find_binary(), find_model()
            if not (binary and model):
                raise RuntimeError("pf-serve or its model is missing: run native/pf-serve/build.sh and `sotto setup`")
            return PfServe(binary, model)
        if name.startswith("pf"):
            from pf_mlx import PrivacyFilter

            backend = {"pf": "mlx", "pf-8bit": "mlx-8bit", "pf-torch": "torch"}[name]
            return PrivacyFilter(backend)
        if name in ("gliner2", "gliner-nvidia", "credsweeper", "piiranha"):
            import alt

            return {"gliner2": alt.GLiNER2Detector, "gliner-nvidia": alt.GLiNERDetector, "credsweeper": alt.CredSweeperDetector, "piiranha": alt.PiiranhaDetector}[name]()
        if name in ("afm-cli", "afm-sdk"):
            from afm import AFMExtractor

            return AFMExtractor(name.removeprefix("afm-"))
        raise ValueError(f"unknown detector {spec!r}")
    from sotto.detect.rules import RulesDetector

    rules = pf = pii_detector = None
    extra = []
    for p in parts:
        if p == "rules":
            rules = RulesDetector()
        elif p == "credsweeper":
            extra.append(make_detector(p))
        elif p == "piiranha":
            pii_detector = make_detector(p)
        else:  # any L2 model: pf, pf-8bit, pf-nemotron, gliner2, gliner-nvidia
            pf = make_detector(p)
    flags = flags.split(":")
    return CandidatePipeline(rules, pf, extra=extra, pii_detector=pii_detector, pii="pii" in flags,
                             refine="raw" not in flags, refine_pii="rawpii" not in flags)


def _stats(det) -> dict:
    out = {}
    for obj in (det,):
        if hasattr(obj, "stats"):
            out.update({f"{getattr(obj, 'name', '')}.{k}": v for k, v in obj.stats.items()})
    return out


def worker(spec: str, data: Path, out: Path, repeat: int, limit: int | None) -> None:
    records = load_records(data, limit)
    t0 = time.perf_counter()
    det = make_detector(spec)
    load_s = time.perf_counter() - t0
    ready_wall = time.time()
    warm = "export API_TOKEN=Zq8vX2mN4pL7kR9tY3wB6cF1hJ5dG0sA\nMaintainer: Ada Example <ada@mail.test>\n"
    t = time.perf_counter()
    det.detect(warm)
    first_call_ms = (time.perf_counter() - t) * 1000
    results = []
    for i, rec in enumerate(records):
        lat = []
        for _ in range(repeat):
            t = time.perf_counter()
            spans = det.detect(rec["text"])
            lat.append((time.perf_counter() - t) * 1000)
        results.append({
            "id": rec["id"],
            "latency_ms": lat,
            "spans": [[s.start, s.end, s.type, round(s.confidence, 4), s.source] for s in spans],
        })
        if (i + 1) % 25 == 0:
            print(f"  {spec}: {i + 1}/{len(records)}", file=sys.stderr, flush=True)
    gpu_peak = None
    if "mlx" in sys.modules:
        import mlx.core as mx

        gpu_peak = mx.get_peak_memory()
    usage_self = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    usage_children = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    for obj in (det, getattr(det, "pf", None)):
        if obj is not None and hasattr(obj, "close"):
            obj.close()
    out.write_text(json.dumps({
        "detector": spec,
        "load_s": load_s,
        "ready_wall": ready_wall,
        "first_call_ms": first_call_ms,
        "peak_rss_bytes": usage_self,  # bytes on macOS
        "peak_rss_children_bytes": usage_children,
        "mlx_peak_bytes": gpu_peak,
        "stats": _stats(det),
        "records": results,
    }))


# --- Data ---------------------------------------------------------------------------


def load_records(data: Path, limit: int | None = None) -> list[dict]:
    files = sorted(data.glob("*.jsonl")) if data.is_dir() else [data]
    records = []
    for f in files:
        group = []
        for line in f.read_text().splitlines():
            if line.strip():
                group.append(json.loads(line))
        records.extend(group[:limit] if limit else group)
    if not records:
        raise SystemExit(f"no records in {data}; run `uv run python bench/gen.py` first")
    return records


def group_of(rec: dict) -> str:
    return rec["tags"][0]


def size_of(rec: dict) -> str:
    for t in rec["tags"]:
        if t.startswith("size:"):
            return t.removeprefix("size:")
    return "short"


def token_counter():
    try:
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        path = hf_hub_download("mlx-community/openai-privacy-filter-bf16", "tokenizer.json", local_files_only=True)
        tok = Tokenizer.from_file(path)
        return (lambda text: len(tok.encode(text, add_special_tokens=False).ids)), "o200k (Privacy Filter tokenizer)"
    except Exception:
        return (lambda text: len(text) // 4), "estimated at 4 characters per token"


# --- Metrics ------------------------------------------------------------------------


def _in_scope(kind: str, scope: str) -> bool:
    return scope == "all" or kind == "SECRET"


def _covered(a: int, b: int, intervals: list[tuple[int, int]]) -> int:
    """Characters of [a, b) covered by the union of intervals."""
    total, cur = 0, a
    for s, e in sorted(intervals):
        s, e = max(s, cur), min(e, b)
        if e > s:
            total += e - s
            cur = e
    return total


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def evaluate(records: list[dict], run: dict, tokens: dict[str, int]) -> dict:
    by_id = {r["id"]: r for r in run["records"]}
    scopes = {}
    for scope in SCOPES:
        gold_n = defaultdict(int)
        gold_hit = defaultdict(int)
        gold_full = defaultdict(int)
        pred_n = defaultdict(int)
        pred_tp = defaultdict(int)
        size_n = defaultdict(int)
        size_hit = defaultdict(int)
        neg_records = neg_flagged = neg_spans = 0
        misses, false_pos = [], []
        for rec in records:
            res = by_id.get(rec["id"])
            if res is None:
                continue
            text = rec["text"]
            gold = [(s["start"], s["end"], s["type"]) for s in rec["spans"] if _in_scope(s["type"], scope)]
            pred = [(s, e, t, src) for s, e, t, _, src in res["spans"] if _in_scope(t, scope)]
            gold_iv = [(s, e) for s, e, _ in gold]
            pred_iv = [(s, e) for s, e, _, _ in pred]
            for s, e, t in gold:
                cov = _covered(s, e, pred_iv)
                for key in (t, "*"):
                    gold_n[key] += 1
                    gold_hit[key] += cov >= MIN_OVERLAP * (e - s)
                    gold_full[key] += cov == e - s
                size_n[size_of(rec)] += 1
                size_hit[size_of(rec)] += cov >= MIN_OVERLAP * (e - s)
                if cov < MIN_OVERLAP * (e - s):
                    misses.append({"id": rec["id"], "tags": rec["tags"][1:], "type": t, "preview": mask(text[s:e])})
            for s, e, t, src in pred:
                ok = _covered(s, e, gold_iv) >= MIN_OVERLAP * (e - s)
                for key in (t, "*"):
                    pred_n[key] += 1
                    pred_tp[key] += ok
                if not ok:
                    false_pos.append({"id": rec["id"], "type": t, "source": src, "preview": mask(text[s:e])})
            if group_of(rec) == "negatives":
                neg_records += 1
                neg_flagged += bool(pred)
                neg_spans += len(pred)
        per_type = {}
        for key in ["*", *TYPES]:
            if not gold_n[key] and not pred_n[key]:
                continue
            r = gold_hit[key] / gold_n[key] if gold_n[key] else None
            p = pred_tp[key] / pred_n[key] if pred_n[key] else None
            f1 = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
            per_type[key] = {
                "gold": gold_n[key], "pred": pred_n[key],
                "recall": r, "full_cover": gold_full[key] / gold_n[key] if gold_n[key] else None,
                "precision": p, "f1": f1,
            }
        scopes[scope] = {
            "types": per_type,
            "recall_by_size": {k: size_hit[k] / size_n[k] for k in size_n},
            "negatives": {"records": neg_records, "flagged": neg_flagged, "spans": neg_spans,
                          "fp_rate": neg_flagged / neg_records if neg_records else None},
            "misses": misses,
            "false_positives": false_pos,
        }
    # Latency per size bucket.
    lat = defaultdict(list)
    tok_total = 0
    time_total = 0.0
    for rec in records:
        res = by_id.get(rec["id"])
        if res is None:
            continue
        lat[size_of(rec)].extend(res["latency_ms"])
        lat["all"].extend(res["latency_ms"])
        tok_total += tokens[rec["id"]] * len(res["latency_ms"])
        time_total += sum(res["latency_ms"]) / 1000
    latency = {k: {"n": len(v), "p50": percentile(v, 0.5), "p95": percentile(v, 0.95), "max": max(v)} for k, v in lat.items()}
    return {
        "scopes": scopes,
        "latency": latency,
        "tokens_per_s": tok_total / time_total if time_total else None,
        "cold_start_s": run["cold_start_s"],
        "load_s": run["load_s"],
        "first_call_ms": run["first_call_ms"],
        "peak_rss_mb": run["peak_rss_bytes"] / 2**20,
        "peak_rss_children_mb": run["peak_rss_children_bytes"] / 2**20,
        "mlx_peak_mb": run["mlx_peak_bytes"] / 2**20 if run.get("mlx_peak_bytes") else None,
        "stats": run["stats"],
    }


def mask(value: str) -> str:
    """Masked preview for reports: never the full value."""
    flat = value.replace("\n", "⏎")
    return f"{flat[:4]}… ({len(value)} chars)" if len(value) > 6 else f"{flat[:1]}… ({len(value)} chars)"


def checks(m: dict) -> dict:
    sec = m["scopes"]["secrets"]
    recall = sec["types"].get("*", {}).get("recall")
    fp = sec["negatives"]["fp_rate"]
    p95s = [m["latency"][b]["p95"] for b in ("short", "1k", "4k") if b in m["latency"]]
    p95 = max(p95s) if p95s else None
    return {
        "secret_recall": (recall, recall is not None and recall >= TARGET_SECRET_RECALL),
        "negative_fp_rate": (fp, fp is not None and fp < TARGET_NEGATIVE_FP),
        "p95_le_4k_ms": (p95, p95 is not None and p95 <= TARGET_P95_MS),
    }


# --- Orchestration ------------------------------------------------------------------


def environment() -> dict:
    def sysctl(key):
        try:
            return subprocess.run(["sysctl", "-n", key], capture_output=True, text=True).stdout.strip()
        except OSError:
            return ""

    versions = {}
    for pkg in ("mlx", "mlx-embeddings", "torch", "transformers", "apple-fm-sdk", "tokenizers"):
        try:
            versions[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            pass
    return {
        "chip": sysctl("machdep.cpu.brand_string"),
        "memory_gb": round(int(sysctl("hw.memsize") or 0) / 2**30),
        "macos": platform.mac_ver()[0],
        "python": platform.python_version(),
        "packages": versions,
    }


def run(detectors: list[str], data: Path, out: Path, repeat: int = 3, limit: int | None = None) -> tuple[Path, Path]:
    records = load_records(data, limit)
    count, tokenizer_note = token_counter()
    tokens = {r["id"]: count(r["text"]) for r in records}
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    runs = {}
    for spec in detectors:
        reps = 1 if "afm" in spec else repeat
        raw = out / f".worker-{stamp}-{spec.replace('+', '_').replace(':', '_')}.json"
        print(f"[bench] {spec} (repeat={reps})", file=sys.stderr, flush=True)
        spawn = time.time()
        cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", spec, str(data), str(raw), str(reps), str(limit or 0)]
        proc = subprocess.run(cmd, env=env)
        if proc.returncode != 0 or not raw.exists():
            print(f"[bench] {spec} failed (exit {proc.returncode}); skipping", file=sys.stderr)
            runs[spec] = {"error": f"worker exited with {proc.returncode}"}
            continue
        result = json.loads(raw.read_text())
        raw.unlink()
        result["cold_start_s"] = result["ready_wall"] - spawn
        runs[spec] = evaluate(records, result, tokens)
        runs[spec]["checks"] = checks(runs[spec])
        print(f"[bench] {spec} done", file=sys.stderr, flush=True)
    summary = {
        "created": stamp,
        "environment": environment(),
        "dataset": dataset_summary(records, tokens, tokenizer_note),
        "settings": {"repeat": repeat, "min_overlap": MIN_OVERLAP,
                     "targets": {"secret_recall": TARGET_SECRET_RECALL, "negative_fp_rate": TARGET_NEGATIVE_FP, "p95_ms_le_4k": TARGET_P95_MS}},
        "detectors": runs,
    }
    json_path = out / f"bench-{stamp}.json"
    md_path = out / f"bench-{stamp}.md"
    json_path.write_text(json.dumps(summary, indent=2))
    md_path.write_text(render_markdown(summary))
    return json_path, md_path


def dataset_summary(records, tokens, tokenizer_note) -> dict:
    groups = defaultdict(lambda: {"records": 0, "spans": 0, "tokens": []})
    for r in records:
        g = groups[group_of(r)]
        g["records"] += 1
        g["spans"] += len(r["spans"])
        g["tokens"].append(tokens[r["id"]])
    return {
        "tokenizer": tokenizer_note,
        "groups": {k: {"records": v["records"], "spans": v["spans"], "tokens_min": min(v["tokens"]), "tokens_max": max(v["tokens"])} for k, v in groups.items()},
    }


# --- Report -------------------------------------------------------------------------


def _f(x, digits=3):
    return "—" if x is None else f"{x:.{digits}f}"


def _ms(x):
    if x is None:
        return "—"
    return f"{x:.1f}" if x < 100 else f"{x:,.0f}"


def render_markdown(s: dict) -> str:
    env, ds = s["environment"], s["dataset"]
    ok = {k: v for k, v in s["detectors"].items() if "error" not in v}
    L = [f"# sotto Phase 0 benchmark — {s['created']}", ""]
    L.append(f"Machine: {env['chip']}, {env['memory_gb']} GB, macOS {env['macos']}, Python {env['python']}. "
             + ", ".join(f"{k} {v}" for k, v in env["packages"].items()) + ".")
    L.append("")
    L.append(f"Dataset ({ds['tokenizer']}): " + "; ".join(
        f"{g} {v['records']} records / {v['spans']} spans / {v['tokens_min']}–{v['tokens_max']} tokens" for g, v in ds["groups"].items()) + ".")
    L.append(f"A labeled span is a hit when detections cover at least {int(s['settings']['min_overlap'] * 100)}% of it; "
             "a detection is correct when at least half of it lies on labeled spans. "
             "*Full cover* counts labeled spans redacted completely. Latency repeats: "
             f"{s['settings']['repeat']} for local detectors, 1 for LLM-based ones.")
    L.append("")
    for name, v in s["detectors"].items():
        if "error" in v:
            L.append(f"> **{name}** failed: {v['error']}")
    L += ["", "## Secrets (default config: `pii = false`)", "",
          "| Detector | Recall | Full cover | Precision | F1 | Negatives flagged | p50 short | p95 ≤4K | p95 8K | Cold start | Peak RSS | Targets |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, m in ok.items():
        t = m["scopes"]["secrets"]["types"].get("*", {})
        neg = m["scopes"]["secrets"]["negatives"]
        c = m["checks"]
        lat = m["latency"]
        targets = " ".join("✅" if passed else "❌" for _, passed in c.values())
        L.append(f"| `{name}` | {_f(t.get('recall'))} | {_f(t.get('full_cover'))} | {_f(t.get('precision'))} | {_f(t.get('f1'))} "
                 f"| {neg['flagged']}/{neg['records']} ({_f(neg['fp_rate'], 2)}) | {_ms(lat.get('short', {}).get('p50'))} ms "
                 f"| {_ms(c['p95_le_4k_ms'][0])} ms | {_ms(lat.get('8k', {}).get('p95'))} ms | {m['cold_start_s']:.1f} s "
                 f"| {m['peak_rss_mb']:,.0f} MB | {targets} |")
    L += ["", f"Targets, in order: secret recall ≥ {TARGET_SECRET_RECALL}, negatives flagged < {TARGET_NEGATIVE_FP:.0%}, "
          f"p95 ≤ {TARGET_P95_MS:.0f} ms for inputs up to 4K tokens.", ""]
    L += ["## All types (`pii = true`)", "",
          "| Detector | Recall | Full cover | Precision | F1 | Negatives flagged |", "| --- | --- | --- | --- | --- | --- |"]
    for name, m in ok.items():
        # Only detectors that report personal data: single models, and pipelines with :pii.
        if ("+" in name or name == "rules") and "pii" not in name.split(":")[1:]:
            continue
        t = m["scopes"]["all"]["types"].get("*", {})
        neg = m["scopes"]["all"]["negatives"]
        L.append(f"| `{name}` | {_f(t.get('recall'))} | {_f(t.get('full_cover'))} | {_f(t.get('precision'))} | {_f(t.get('f1'))} | {neg['flagged']}/{neg['records']} ({_f(neg['fp_rate'], 2)}) |")
    L += ["", "## Recall / precision by type (all types)", "",
          "| Detector | " + " | ".join(TYPES) + " |", "| --- |" + " --- |" * len(TYPES)]
    for name, m in ok.items():
        types = m["scopes"]["all"]["types"]
        cells = []
        for t in TYPES:
            d = types.get(t)
            cells.append("—" if not d else f"{_f(d['recall'], 2)} / {_f(d['precision'], 2)}")
        L.append(f"| `{name}` | " + " | ".join(cells) + " |")
    L += ["", "Cells are recall / precision. Recall uses the labeled type, precision the detected type.", ""]
    L += ["## Latency", "",
          "| Detector | short p50 / p95 | 1K p50 / p95 | 4K p50 / p95 | 8K p50 / p95 | Tokens/s | Load | First call | MLX peak |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, m in ok.items():
        lat = m["latency"]
        cells = [f"{_ms(lat[b]['p50'])} / {_ms(lat[b]['p95'])} ms" if b in lat else "—" for b in ("short", "1k", "4k", "8k")]
        L.append(f"| `{name}` | " + " | ".join(cells) + f" | {m['tokens_per_s']:,.0f} | {m['load_s']:.1f} s | {_ms(m['first_call_ms'])} ms | "
                 + (f"{m['mlx_peak_mb']:,.0f} MB" if m["mlx_peak_mb"] else "—") + " |")
    afm = {n: m for n, m in ok.items() if m["stats"]}
    if afm:
        L += ["", "## Apple on-device model outcomes", "", "| Detector | Counter | Count |", "| --- | --- | --- |"]
        for name, m in afm.items():
            for k, v in sorted(m["stats"].items()):
                L.append(f"| `{name}` | {k} | {v} |")
    L += ["", "## Missed secrets", ""]
    for name, m in ok.items():
        misses = m["scopes"]["secrets"]["misses"]
        L.append(f"- `{name}`: {len(misses)} missed" + (": " + "; ".join(f"{x['id']} ({', '.join(x['tags'][:2])}) {x['preview']}" for x in misses[:12]) if misses else ""))
    L += ["", "## Flagged hard negatives (secrets scope)", ""]
    for name, m in ok.items():
        fps = [x for x in m["scopes"]["secrets"]["false_positives"] if x["id"].startswith("neg-")]
        L.append(f"- `{name}`: {len(fps)} spans" + (": " + "; ".join(f"{x['id']} {x['source']} {x['preview']}" for x in fps[:12]) if fps else ""))
    return "\n".join(L) + "\n"


def main() -> None:
    import argparse

    if sys.argv[1:2] == ["--worker"]:
        spec, data, out, reps, limit = sys.argv[2:7]
        worker(spec, Path(data), Path(out), int(reps), int(limit) or None)
        return
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--detectors", default=DEFAULT_DETECTORS, help="comma-separated detectors")
    ap.add_argument("--data", type=Path, default=Path(__file__).parent / "data", help="directory of labeled *.jsonl files, or one file")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "results", help="where to write the JSON and Markdown results")
    ap.add_argument("--repeat", type=int, default=3, help="timed runs per record for local detectors (AFM runs once)")
    ap.add_argument("--limit", type=int, default=0, help="use only the first N records of each file (0 = all)")
    args = ap.parse_args()
    names = [d.strip() for d in args.detectors.split(",") if d.strip()]
    json_path, md_path = run(names, args.data, args.out, repeat=args.repeat, limit=args.limit or None)
    print(md_path.read_text())
    print(f"Wrote {json_path} and {md_path}")


if __name__ == "__main__":
    main()
