"""Replace sensitive spans with placeholders, in plain text and in Messages API payloads."""

from __future__ import annotations

import hashlib
from collections import Counter, OrderedDict

from .detect import Span
from .detect.merge import merge
from .vault import Vault

# Signed or binary blocks are resent exactly as the API produced them.
PASS_THROUGH = frozenset({"thinking", "redacted_thinking", "image"})
# For block types sotto does not know, only these fields are scanned. Ids, names, signatures
# and every other protocol field stay as they are.
CONTENT_KEYS = ("text", "content", "input")

# Appended to every request's system prompt, always the same text, so the prompt cache stays
# valid. Without it Claude sees SOTTO_SECRET_... and concludes the file holds a fake value.
PLACEHOLDER_HINT = (
    "Note from sotto, a local privacy proxy on this machine: values of the form "
    "SOTTO_<TYPE>_<8 hex digits> (SOTTO_SECRET_xxxxxxxx, SOTTO_PERSON_xxxxxxxx, SOTTO_EMAIL_xxxxxxxx, "
    "and so on) are placeholders for real values that were redacted before this request left "
    "the user's computer. Treat each one as the real value: copy it exactly when a value is "
    "needed, and do not call it fake, masked or a placeholder. Real values are restored locally "
    "in your replies and tool calls."
)


class Redactor:
    def __init__(self, detector, vault: Vault, cache_size: int = 4096):
        self.detector = detector
        self.vault = vault
        self._cache: OrderedDict[bytes, tuple[Span, ...]] = OrderedDict()
        self._cache_size = cache_size
        self.counts: Counter[str] = Counter()  # spans masked per type since the last reset

    def _detect(self, text: str) -> tuple[Span, ...]:
        """Detector spans, cached per text: the conversation history is resent every turn."""
        key = hashlib.sha256(text.encode("utf-8", "surrogatepass")).digest()
        hit = self._cache.get(key)
        if hit is not None:
            self._cache.move_to_end(key)
            return hit
        spans = tuple(self.detector.detect(text))
        self._cache[key] = spans
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return spans

    def spans(self, text: str) -> list[Span]:
        """Detector spans plus every exact occurrence of a value masked before."""
        spans = list(self._detect(text))
        known = self.vault.known_values()
        if known is not None:
            spans += [Span(m.start(), m.end(), self.vault.kind_of(m.group()), 1.0, "known") for m in known.finditer(text)]
        return merge(spans)

    def redact_text(self, text: str) -> str:
        if not text:
            return text
        spans = self.spans(text)
        if not spans:
            return text
        out, pos = [], 0
        for s in spans:
            out.append(text[pos : s.start])
            out.append(self.vault.placeholder(s.type, text[s.start : s.end]))
            self.counts[s.type] += 1
            pos = s.end
        out.append(text[pos:])
        return "".join(out)

    # --- Messages API payloads ----------------------------------------------------

    def redact_request(self, body: dict) -> dict:
        """A copy of a /v1/messages (or count_tokens) body with system and messages masked.

        `tools`, `metadata` and every other top-level field pass through unchanged.
        """
        out = dict(body)
        if "system" in out:
            out["system"] = self._content(out["system"])
        out["system"] = self._with_hint(out.get("system"))
        if isinstance(out.get("messages"), list):
            out["messages"] = [
                {**m, "content": self._content(m.get("content"))} if isinstance(m, dict) else m
                for m in out["messages"]
            ]
        return out

    @staticmethod
    def _with_hint(system):
        """The system prompt with the placeholder hint as a last, separate text block."""
        hint = {"type": "text", "text": PLACEHOLDER_HINT}
        if isinstance(system, list):
            return [*system, hint]
        if isinstance(system, str) and system:
            return [{"type": "text", "text": system}, hint]
        return [hint]

    def _content(self, content):
        if isinstance(content, str):
            return self.redact_text(content)
        if isinstance(content, list):
            return [self._block(b) for b in content]
        return content

    def _block(self, block):
        if not isinstance(block, dict):
            return self._content(block)
        kind = block.get("type")
        if kind in PASS_THROUGH:
            return block
        if kind == "text":
            return {**block, "text": self.redact_text(block.get("text", ""))}
        if kind == "tool_use":
            return {**block, "input": self._values(block.get("input"))}
        if kind == "tool_result":
            return {**block, "content": self._content(block.get("content"))}
        if kind == "document":
            source = block.get("source")
            if isinstance(source, dict) and source.get("type") == "text":
                return {**block, "source": {**source, "data": self.redact_text(source.get("data", ""))}}
            if isinstance(source, dict) and source.get("type") == "content":
                return {**block, "source": {**source, "content": self._content(source.get("content"))}}
            return block  # PDFs and other binary sources pass through (a v1 risk)
        # Unknown block type: scan its content fields, leave protocol fields alone.
        return {k: (self._values(v) if k in CONTENT_KEYS else v) for k, v in block.items()}

    def _values(self, value):
        """Every string value in a JSON tree, recursively. Keys are never changed."""
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, dict):
            return {k: self._values(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._values(v) for v in value]
        return value
