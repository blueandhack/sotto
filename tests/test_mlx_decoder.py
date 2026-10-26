"""The MLX backend's BIOES decoder, kept for benchmark comparisons (`uv sync --group mlx`)."""

import itertools
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

sys.path.insert(0, str(Path(__file__).parent.parent / "bench"))

from pf_mlx import BIOESDecoder  # noqa: E402


def _brute_force(decoder, logp):
    """Best valid BIOES path by enumeration (zero transition biases)."""
    k = len(decoder.labels)
    states = [("O", None)] + [(t, lab) for t in "BIES" for lab in range(k)]

    def col(state):
        t, lab = state
        return decoder.o if t == "O" else decoder.tag[t][lab]

    def valid(path):
        prev = ("O", None)
        for st in path:
            t, lab = st
            open_span = prev[0] in "BI"
            if open_span and not (t in "IE" and lab == prev[1]):
                return False
            if not open_span and t in "IE":
                return False
            prev = st
        return prev[0] not in "BI"

    best, best_path = -np.inf, None
    for path in itertools.product(states, repeat=len(logp)):
        if valid(path):
            score = sum(logp[j, col(st)] for j, st in enumerate(path))
            if score > best:
                best, best_path = score, path
    return best_path


def test_decoder_matches_brute_force():
    id2label = {0: "O", 1: "B-a", 2: "I-a", 3: "E-a", 4: "S-a", 5: "B-b", 6: "I-b", 7: "E-b", 8: "S-b"}
    decoder = BIOESDecoder(id2label, pin_o=1.0)  # no pinning: one exact segment
    rng = np.random.default_rng(0)
    for _ in range(25):
        logits = rng.normal(size=(5, 9)) * 3
        logp = logits - np.log(np.exp(logits).sum(axis=1, keepdims=True))
        expected = _brute_force(decoder, logp)
        exp_spans, start = [], None
        for j, (t, lab) in enumerate(expected):
            if t == "S":
                exp_spans.append((j, j, decoder.labels[lab]))
            elif t == "B":
                start = j
            elif t == "E":
                exp_spans.append((start, j, decoder.labels[lab]))
        got = [(a, b, lab) for a, b, lab, _ in decoder.decode(logp)]
        assert got == exp_spans
