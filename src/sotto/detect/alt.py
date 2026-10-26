"""Alternative detectors, for the benchmark only: GLiNER-family PII models and CredSweeper.

None of these is part of the request path. Their libraries are not dependencies of sotto;
install them next to it (`uv pip install gliner gliner2 credsweeper`) to benchmark them.
"""

from __future__ import annotations

import os

from . import Span

# Label sets passed to the zero-shot GLiNER models, mapped to sotto types.
GLINER2_LABELS = {
    "person": "PERSON", "full_name": "PERSON",
    "email": "EMAIL", "phone_number": "PHONE",
    "address": "ADDRESS", "street_address": "ADDRESS",
    "date_of_birth": "DATE",
    "account_number": "ACCOUNT", "bank_account": "ACCOUNT", "iban": "ACCOUNT", "card_number": "ACCOUNT",
    "password": "SECRET", "secret": "SECRET", "api_key": "SECRET", "access_token": "SECRET",
}
GLINER_NVIDIA_LABELS = {
    "first_name": "PERSON", "last_name": "PERSON", "name": "PERSON",
    "email": "EMAIL", "phone_number": "PHONE",
    "street_address": "ADDRESS", "date_of_birth": "DATE",
    "account_number": "ACCOUNT", "credit_debit_card": "ACCOUNT", "iban": "ACCOUNT",
    "password": "SECRET", "api_key": "SECRET", "access_token": "SECRET",
    "url": "URL",
}


def _chunks(text: str, size: int = 1500, overlap: int = 200):
    """Character windows on line boundaries where possible; GLiNER encoders take ~384 words."""
    start, n = 0, len(text)
    while start < n:
        end = min(n, start + size)
        if end < n:
            cut = text.rfind("\n", start + size // 2, end)
            end = cut + 1 if cut > 0 else end
        yield start, text[start:end]
        if end >= n:
            break
        start = max(end - overlap, start + 1)


class GLiNER2Detector:
    name = "gliner2"

    def __init__(self, repo: str = "fastino/gliner2-privacy-filter-PII-multi", threshold: float = 0.5):
        from gliner2 import GLiNER2

        self.model = GLiNER2.from_pretrained(repo)
        self.threshold = threshold
        self.labels = list(GLINER2_LABELS)

    def detect(self, text: str) -> list[Span]:
        spans = []
        for offset, chunk in _chunks(text):
            out = self.model.extract_entities(chunk, self.labels, threshold=self.threshold,
                                              include_spans=True, include_confidence=True)
            for label, items in out.get("entities", {}).items():
                for it in items:
                    if isinstance(it, dict) and "start" in it:
                        spans.append(Span(offset + it["start"], offset + it["end"], GLINER2_LABELS.get(label, "SECRET"),
                                          float(it.get("confidence", 1.0)), self.name))
        return spans


class GLiNERDetector:
    name = "gliner-nvidia"

    def __init__(self, repo: str = "nvidia/gliner-PII", threshold: float = 0.5):
        import torch
        from gliner import GLiNER

        self.model = GLiNER.from_pretrained(repo)
        if torch.backends.mps.is_available():
            self.model = self.model.to("mps")
        self.threshold = threshold
        self.labels = list(GLINER_NVIDIA_LABELS)

    def detect(self, text: str) -> list[Span]:
        spans = []
        for offset, chunk in _chunks(text):
            for e in self.model.predict_entities(chunk, self.labels, threshold=self.threshold):
                spans.append(Span(offset + e["start"], offset + e["end"], GLINER_NVIDIA_LABELS.get(e["label"], "SECRET"),
                                  float(e["score"]), self.name))
        return spans


class CredSweeperDetector:
    """CredSweeper's rules plus its ML validator. Secrets only."""

    name = "credsweeper"

    def __init__(self, threshold: str = "medium"):
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        from credsweeper.app import CredSweeper
        from credsweeper.file_handler.string_content_provider import StringContentProvider

        self._provider = StringContentProvider
        self.cs = CredSweeper(ml_threshold=threshold)

    def detect(self, text: str) -> list[Span]:
        lines = text.splitlines(keepends=True)
        starts, pos = [], 0
        for line in lines:
            starts.append(pos)
            pos += len(line)
        self.cs.credential_manager.clear_credentials()
        # A neutral file name: CredSweeper picks rules by extension, and requests mix formats.
        self.cs.scan([self._provider([l.rstrip("\r\n") for l in lines], file_path="snippet.txt")], None)
        self.cs.post_processing(None)
        spans = []
        for cred in self.cs.credential_manager.get_credentials():
            for ld in cred.line_data_list:
                if ld.value_start is None or ld.value_start < 0 or not ld.value:
                    continue
                start = starts[ld.line_num - 1] + ld.value_start
                spans.append(Span(start, start + len(ld.value), "SECRET", float(cred.ml_probability or 0.99), self.name))
        return spans


PIIRANHA_LABELS = {
    "GIVENNAME": "PERSON", "SURNAME": "PERSON", "EMAIL": "EMAIL", "TELEPHONENUM": "PHONE",
    "STREET": "ADDRESS", "BUILDINGNUM": "ADDRESS", "CITY": "ADDRESS", "ZIPCODE": "ADDRESS",
    "DATEOFBIRTH": "DATE", "ACCOUNTNUM": "ACCOUNT", "CREDITCARDNUMBER": "ACCOUNT",
    "SOCIALNUM": "ACCOUNT", "TAXNUM": "ACCOUNT", "IDCARDNUM": "ACCOUNT", "DRIVERLICENSENUM": "ACCOUNT",
    "PASSWORD": "SECRET",
}


class PiiranhaDetector:
    """iiiorg/piiranha-v1-detect-personal-information: DeBERTa-v3 (280M), 17 PII labels."""

    name = "piiranha"

    def __init__(self, repo: str = "iiiorg/piiranha-v1-detect-personal-information", threshold: float = 0.5):
        import torch
        from transformers import pipeline

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.pipe = pipeline("token-classification", model=repo, aggregation_strategy="simple", device=device)
        self.threshold = threshold

    def detect(self, text: str) -> list[Span]:
        spans = []
        # DeBERTa reads 512 tokens at most; 1,500-character windows stay well under it.
        for offset, chunk in _chunks(text):
            for e in self.pipe(chunk):
                kind = PIIRANHA_LABELS.get(e["entity_group"].removeprefix("I-").removeprefix("B-"))
                if kind and e["score"] >= self.threshold:
                    a, b = e["start"], e["end"]
                    while a < b and chunk[a].isspace():
                        a += 1
                    while b > a and chunk[b - 1].isspace():
                        b -= 1
                    spans.append(Span(offset + a, offset + b, kind, float(e["score"]), self.name))
        return spans
