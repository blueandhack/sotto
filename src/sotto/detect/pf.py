"""L2: OpenAI Privacy Filter, a token classifier over 8 privacy labels with BIOES tags.

Backends: MLX (mlx-community ports, via mlx-embeddings) or PyTorch on MPS (transformers).
Both produce per-token logits; span decoding is shared and runs in numpy.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from . import Span

SOURCE = "pf"

MODELS = {
    "mlx": "mlx-community/openai-privacy-filter-bf16",
    "mlx-8bit": "mlx-community/openai-privacy-filter-8bit",
    "torch": "openai/privacy-filter",
}

LABEL_TYPES = {
    "account_number": "ACCOUNT",
    "private_address": "ADDRESS",
    "private_date": "DATE",
    "private_email": "EMAIL",
    "private_person": "PERSON",
    "private_phone": "PHONE",
    "private_url": "URL",
    "secret": "SECRET",
    # OpenMed/privacy-filter-nemotron's 55 fine-grained labels; the rest are not sensitive here.
    "api_key": "SECRET", "password": "SECRET", "pin": "SECRET", "cvv": "SECRET", "http_cookie": "SECRET",
    "credit_debit_card": "ACCOUNT", "bank_routing_number": "ACCOUNT", "ssn": "ACCOUNT", "tax_id": "ACCOUNT",
    "national_id": "ACCOUNT", "swift_bic": "ACCOUNT",
    "first_name": "PERSON", "last_name": "PERSON",
    "email": "EMAIL", "phone_number": "PHONE", "fax_number": "PHONE",
    "street_address": "ADDRESS", "city": "ADDRESS", "state": "ADDRESS", "postcode": "ADDRESS", "county": "ADDRESS",
    "url": "URL", "date_of_birth": "DATE",
}

# Receptive field: 8 layers x 128-token attention band on each side.
RECEPTIVE_FIELD = 8 * 128


class BIOESDecoder:
    """Constrained Viterbi over BIOES tags, following the model card's decoding rules.

    Tokens whose best label is O with high probability pin the path to O, which splits
    the sequence into short segments; each segment is decoded exactly.
    """

    BIAS_KEYS = (
        "transition_bias_background_stay",
        "transition_bias_background_to_start",
        "transition_bias_end_to_background",
        "transition_bias_end_to_start",
        "transition_bias_inside_to_continue",
        "transition_bias_inside_to_end",
    )

    def __init__(self, id2label: dict[int, str], biases: dict[str, float] | None = None, pin_o: float = 0.995):
        self.labels = sorted({lab.split("-", 1)[1] for lab in id2label.values() if lab != "O"})
        index = {lab: i for i, lab in id2label.items()}
        self.o = index["O"]
        self.tag = {t: np.array([index[f"{t}-{lab}"] for lab in self.labels]) for t in "BIES"}
        b = biases or {}
        (self.bg_stay, self.bg_start, self.end_bg, self.end_start, self.in_cont, self.in_end) = (
            float(b.get(k, 0.0)) for k in self.BIAS_KEYS
        )
        self.log_pin = float(np.log(pin_o))

    def decode(self, logp: np.ndarray) -> list[tuple[int, int, str, float]]:
        """logp: [T, C] log-probabilities. Returns (first_token, last_token, label, confidence)."""
        pinned = logp[:, self.o] >= self.log_pin
        spans = []
        t, n = 0, len(logp)
        while t < n:
            if pinned[t]:
                t += 1
                continue
            end = t
            while end < n and not pinned[end]:
                end += 1
            spans.extend(self._segment(logp, t, end))
            t = end
        return spans

    def _segment(self, logp: np.ndarray, lo: int, hi: int):
        # Compact states: 0 = O, then B, I, E, S blocks of k labels each. A segment is
        # bounded by pinned O tokens (or the sequence edge), so it starts and ends outside a span.
        k = len(self.labels)
        B0, I0, E0, S0 = 1, 1 + k, 1 + 2 * k, 1 + 3 * k
        labels = np.arange(k)
        cols = np.concatenate([[self.o], self.tag["B"], self.tag["I"], self.tag["E"], self.tag["S"]])
        emit = logp[lo:hi][:, cols]
        T = hi - lo
        bp = np.zeros((T, 1 + 4 * k), dtype=np.int16)
        score = np.full(1 + 4 * k, -np.inf)
        score[0] = 0.0
        for j in range(T):
            prev = score
            es = prev[E0:]  # E and S blocks are contiguous
            best_es = E0 + int(np.argmax(es))
            cur = np.empty_like(prev)
            # Into O.
            a, b = prev[0] + self.bg_stay, prev[best_es] + self.end_bg
            cur[0], bp[j, 0] = (b, best_es) if b > a else (a, 0)
            # Into B or S: a new span starts after O or after a span end.
            a, b = prev[0] + self.bg_start, prev[best_es] + self.end_start
            start, src = (b, best_es) if b > a else (a, 0)
            cur[B0:I0] = start
            cur[S0:] = start
            bp[j, B0:I0] = src
            bp[j, S0:] = src
            # Into I or E: continue an open span of the same label (from its B or I).
            from_i = prev[I0:E0] > prev[B0:I0]
            inside = np.where(from_i, prev[I0:E0], prev[B0:I0])
            src_in = np.where(from_i, I0 + labels, B0 + labels)
            cur[I0:E0] = inside + self.in_cont
            cur[E0:S0] = inside + self.in_end
            bp[j, I0:E0] = src_in
            bp[j, E0:S0] = src_in
            score = cur + emit[j]
        # Finish in O, E or S.
        finals = np.concatenate([[score[0]], score[E0:]])
        i = int(np.argmax(finals))
        state = 0 if i == 0 else E0 + i - 1
        path = np.empty(T, dtype=np.int16)
        for j in range(T - 1, -1, -1):
            path[j] = state
            state = bp[j, state]
        out, open_at = [], None
        for j, st in enumerate(path.tolist()):
            if st == 0:
                continue
            block, lab = divmod(st - 1, k)
            if block == 3:  # S
                out.append((j, j, lab))
            elif block == 0:  # B
                open_at = j
            elif block == 2 and open_at is not None:  # E
                out.append((open_at, j, lab))
                open_at = None
        result = []
        for a, b, lab in out:
            type_cols = np.array([self.tag[t][lab] for t in "BIES"])
            conf = float(np.exp(logp[lo + a : lo + b + 1][:, type_cols]).sum(axis=1).mean())
            result.append((lo + a, lo + b, self.labels[lab], conf))
        return result


def _log_softmax(x: np.ndarray) -> np.ndarray:
    x = x - x.max(axis=-1, keepdims=True)
    return x - np.log(np.exp(x).sum(axis=-1, keepdims=True))


class PrivacyFilter:
    """Loads the model once and keeps it warm. `detect` runs one forward pass per window."""

    # 8-bit by default: Phase 0 measured the same recall and latency as bf16 with 1.25 GB less memory.
    def __init__(self, backend: str = "mlx-8bit", model: str | None = None, window: int | None = None, name: str | None = None):
        if backend not in MODELS:
            raise ValueError(f"unknown pf backend {backend!r}; choose from {', '.join(MODELS)}")
        self.backend = backend
        self.name = name or (SOURCE if backend == "mlx" else f"{SOURCE}-{backend}")
        self.repo = model or MODELS[backend]
        # None: one pass over the whole input. Otherwise: windows of `window` tokens plus
        # RECEPTIVE_FIELD tokens of context on each side, which gives identical logits.
        self.window = window
        # MLX GPU streams belong to the thread that created them: one thread loads the model
        # and runs every forward pass, whichever thread calls detect().
        self._thread = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sotto-pf")
        self._thread.submit(self._load).result()

    def _load(self) -> None:
        from huggingface_hub import snapshot_download
        from tokenizers import Tokenizer

        # Detection never touches the network: the model must already be downloaded.
        files = ["config.json", "tokenizer.json", "tokenizer_config.json", "viterbi_calibration.json", "model.safetensors*"]
        path = Path(snapshot_download(self.repo, local_files_only=True, allow_patterns=files))
        self.tokenizer = Tokenizer.from_file(str(path / "tokenizer.json"))
        config = json.loads((path / "config.json").read_text())
        id2label = {int(i): lab for i, lab in config["id2label"].items()}
        biases = None
        calib = path / "viterbi_calibration.json"
        if calib.exists():
            biases = json.loads(calib.read_text())["operating_points"]["default"]["biases"]
        self.decoder = BIOESDecoder(id2label, biases)
        if self.backend.startswith("mlx"):
            from mlx_embeddings.utils import load

            self.model, _ = load(str(path))
        else:
            os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
            import torch
            from transformers import AutoModelForTokenClassification

            self._torch = torch
            self.device = "mps" if torch.backends.mps.is_available() else "cpu"
            self.model = AutoModelForTokenClassification.from_pretrained(str(path), dtype=torch.bfloat16).to(self.device)
            self.model.eval()

    def logits(self, ids: list[int]) -> np.ndarray:
        return self._thread.submit(self._logits, ids).result()

    def _logits(self, ids: list[int]) -> np.ndarray:
        if self.backend.startswith("mlx"):
            import mlx.core as mx

            out = self.model(mx.array([ids]))
            return np.array(out.logits[0].astype(mx.float32))
        torch = self._torch
        with torch.inference_mode():
            out = self.model(input_ids=torch.tensor([ids], device=self.device))
            return out.logits[0].float().cpu().numpy()

    def _windowed_logits(self, ids: list[int]) -> np.ndarray:
        n = len(ids)
        if self.window is None or n <= self.window + 2 * RECEPTIVE_FIELD:
            return self.logits(ids)
        parts = []
        for core in range(0, n, self.window):
            lo = max(0, core - RECEPTIVE_FIELD)
            hi = min(n, core + self.window + RECEPTIVE_FIELD)
            lg = self.logits(ids[lo:hi])
            parts.append(lg[core - lo : core - lo + min(self.window, n - core)])
        return np.concatenate(parts)

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False).ids)

    def detect(self, text: str) -> list[Span]:
        if not text.strip():
            return []
        enc = self.tokenizer.encode(text, add_special_tokens=False)
        logp = _log_softmax(self._windowed_logits(enc.ids))
        spans = []
        for a, b, label, conf in self.decoder.decode(logp):
            start, end = enc.offsets[a][0], enc.offsets[b][1]
            # Byte-level BPE tokens carry their leading space; trim it off the span.
            while start < end and text[start].isspace():
                start += 1
            while end > start and text[end - 1].isspace():
                end -= 1
            kind = LABEL_TYPES.get(label)
            if kind and start < end:
                spans.append(Span(start, end, kind, conf, self.name))
        return spans
