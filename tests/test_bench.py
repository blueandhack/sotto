"""The benchmark's scoring (bench/run.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bench"))

from run import _covered, evaluate  # noqa: E402


def test_covered_counts_union_once():
    assert _covered(0, 10, [(0, 4), (2, 6), (8, 20)]) == 8
    assert _covered(5, 10, [(0, 3)]) == 0


def test_evaluate_hit_needs_half_the_span():
    records = [{"id": "r", "text": "x" * 40, "spans": [{"start": 10, "end": 30, "type": "SECRET"}], "tags": ["secrets"]}]

    def run(spans):
        return {"records": [{"id": "r", "latency_ms": [1.0], "spans": spans}], "cold_start_s": 0, "load_s": 0,
                "first_call_ms": 0, "peak_rss_bytes": 0, "peak_rss_children_bytes": 0, "stats": {}}

    hit = evaluate(records, run([[10, 20, "SECRET", 1.0, "t"]]), {"r": 10})
    miss = evaluate(records, run([[10, 19, "SECRET", 1.0, "t"]]), {"r": 10})
    assert hit["scopes"]["secrets"]["types"]["*"]["recall"] == 1.0
    assert miss["scopes"]["secrets"]["types"]["*"]["recall"] == 0.0
