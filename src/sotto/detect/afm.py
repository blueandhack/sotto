"""Apple's on-device foundation model, through the `fm` CLI or the Python SDK. Benchmark only.

Phase 0 measured it as a span extractor (`AFMExtractor`, here) and as a judge (bench/judge.py)
and dropped it from the request path: as an extractor it is slow and noisy, and as a judge no
prompting setup cleared false positives without also clearing real values. See
bench/results/MODELS.md. v1 has no LLM in the request path.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass

from . import TYPES, Span

EXTRACT_INSTRUCTIONS = (
    "You are a data-loss-prevention scanner. List every secret and every piece of personal data "
    "in the text. Secrets: API keys, access tokens, passwords, private keys, credentials inside "
    "connection strings. Personal data: names of people, email addresses, phone numbers, postal "
    "addresses, bank account or card numbers, personal URLs, dates of birth. Copy each value "
    "exactly as it appears in the text, character for character, without the variable name. "
    "Do not list placeholders, documented example values, hashes, UUIDs or version numbers. "
    "If there are none, return an empty list."
)

FINDINGS_SCHEMA = {
    "title": "Findings",
    "type": "object",
    "additionalProperties": False,
    "required": ["findings"],
    "x-order": ["findings"],
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "title": "Finding",
                "type": "object",
                "additionalProperties": False,
                "required": ["value", "type"],
                "x-order": ["value", "type"],
                "properties": {
                    "value": {"type": "string"},
                    "type": {"type": "string", "enum": list(TYPES)},
                },
            },
        }
    },
}

# Outcomes counted by the benchmark.
OK, REFUSAL, SCHEMA_FAILURE, OVERFLOW, TIMEOUT, ERROR = "ok", "refusal", "schema_failure", "overflow", "timeout", "error"


@dataclass
class Reply:
    status: str
    data: dict | None = None


class _CLIBackend:
    name = "afm-cli"

    def __init__(self, timeout: float):
        self.timeout = timeout
        self._schemas: dict[str, str] = {}
        self.env = {**os.environ, "NO_COLOR": "1"}

    def context_size(self) -> int:
        # The CLI has no query for it; the SDK reports 8192 on macOS 27.
        return 8192

    def _schema_file(self, schema: dict) -> str:
        key = schema["title"]
        if key not in self._schemas:
            f = tempfile.NamedTemporaryFile("w", suffix=".json", prefix="sotto-", delete=False)
            json.dump(schema, f)
            f.close()
            self._schemas[key] = f.name
        return self._schemas[key]

    def respond(self, instructions: str, prompt: str, schema: dict) -> Reply:
        cmd = ["fm", "respond", "--no-stream", "-g", "--guardrails", "permissive-content-transformations",
               "-i", instructions, "--schema", self._schema_file(schema)]
        try:
            p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=self.timeout, env=self.env)
        except subprocess.TimeoutExpired:
            return Reply(TIMEOUT)
        if p.returncode != 0:
            err = p.stderr.lower()
            if "guardrail" in err or "refus" in err or "unsafe" in err:
                return Reply(REFUSAL)
            if "context" in err and ("exceed" in err or "window" in err):
                return Reply(OVERFLOW)
            if "schema" in err or "decod" in err:
                return Reply(SCHEMA_FAILURE)
            return Reply(ERROR)
        try:
            return Reply(OK, json.loads(p.stdout))
        except json.JSONDecodeError:
            return Reply(SCHEMA_FAILURE)

    def close(self) -> None:
        for path in self._schemas.values():
            os.unlink(path)
        self._schemas.clear()


class _SDKBackend:
    name = "afm-sdk"

    def __init__(self, timeout: float, use_case: str = "general"):
        import apple_fm_sdk as fm

        self.fm = fm
        self.timeout = timeout
        self.model = fm.SystemLanguageModel(
            use_case=fm.SystemLanguageModelUseCase.CONTENT_TAGGING if use_case == "content-tagging" else fm.SystemLanguageModelUseCase.GENERAL,
            guardrails=fm.SystemLanguageModelGuardrails.PERMISSIVE_CONTENT_TRANSFORMATIONS,
        )
        ok, reason = self.model.is_available()
        if not ok:
            raise RuntimeError(f"Apple on-device model unavailable: {reason}")
        self.loop = asyncio.new_event_loop()
        self.options = fm.GenerationOptions(sampling=fm.SamplingMode.greedy())

    def context_size(self) -> int:
        return int(self.model.context_size)

    async def _respond(self, instructions: str, prompt: str, schema: dict):
        # A fresh session per call: sessions keep a transcript that would grow the context.
        session = self.fm.LanguageModelSession(instructions=instructions, model=self.model)
        return await session.respond(prompt, json_schema=schema, options=self.options)

    def respond(self, instructions: str, prompt: str, schema: dict) -> Reply:
        fm = self.fm
        try:
            content = self.loop.run_until_complete(asyncio.wait_for(self._respond(instructions, prompt, schema), self.timeout))
            return Reply(OK, json.loads(content.to_json()))
        except TimeoutError:
            return Reply(TIMEOUT)
        except (fm.RefusalError, fm.GuardrailViolationError):
            return Reply(REFUSAL)
        except fm.ExceededContextWindowSizeError:
            return Reply(OVERFLOW)
        except (fm.DecodingFailureError, fm.InvalidGenerationSchemaError, json.JSONDecodeError):
            return Reply(SCHEMA_FAILURE)
        except fm.FoundationModelsError:
            return Reply(ERROR)

    def close(self) -> None:
        self.loop.close()


def make_backend(kind: str, timeout: float = 30.0, use_case: str = "general"):
    if kind == "cli":
        return _CLIBackend(timeout)
    if kind == "sdk":
        return _SDKBackend(timeout, use_case)
    raise ValueError(f"unknown afm backend {kind!r}")


def _chunks(text: str, max_chars: int):
    """Split on line boundaries into chunks of at most max_chars (longer lines are cut)."""
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_chars)
        if end < n:
            cut = text.rfind("\n", start, end)
            if cut > start:
                end = cut + 1
        yield start, text[start:end]
        start = end


class AFMExtractor:
    """Asks the model for the sensitive values in each chunk and maps them back to offsets."""

    # Leave room for instructions, schema and the answer in the context window. Code and
    # random keys run 2-4 characters per token, so 6000 characters is roughly 1.5-3K tokens.
    CHUNK_CHARS = 6000

    def __init__(self, backend: str = "cli", timeout: float = 60.0):
        self.backend = make_backend(backend, timeout)
        self.name = self.backend.name
        self.stats: Counter[str] = Counter()

    def detect(self, text: str) -> list[Span]:
        spans = []
        for offset, chunk in _chunks(text, self.CHUNK_CHARS):
            if not chunk.strip():
                continue
            reply = self.backend.respond(EXTRACT_INSTRUCTIONS, f"Text:\n{chunk}", FINDINGS_SCHEMA)
            self.stats["calls"] += 1
            self.stats[reply.status] += 1
            if reply.status != OK:
                continue
            for f in reply.data.get("findings", []):
                value = str(f.get("value", "")).strip()
                kind = f.get("type") if f.get("type") in TYPES else "SECRET"
                if len(value) < 3:
                    continue
                found = False
                for m in re.finditer(re.escape(value), chunk):
                    spans.append(Span(offset + m.start(), offset + m.end(), kind, 0.7, self.name))
                    found = True
                if not found:
                    # The model rewrote or invented the value; it cannot be located in the text.
                    self.stats["unmatched_values"] += 1
        return spans

    def close(self) -> None:
        self.backend.close()
