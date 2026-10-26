"""The pipeline: L1 rules and L2 Privacy Filter, with deterministic refinement of model spans.

There is no LLM judge in v1: Phase 0 measured two (the Apple on-device model and Qwen3-4B) and
neither cleared anything the refinement rules did not already remove (bench/results/MODELS.md).
"""

from __future__ import annotations

import re
from collections import Counter

from . import Span
from .merge import merge
from .rules import RulesDetector, shannon_entropy

_PIECE = re.compile(r"\S+")
_EDGE = "/=:\"'`,;()[]{}<>"
# Used with Pattern.match(text, pos), which anchors at pos (a leading ^ would not).
_LABEL = re.compile(r"[A-Za-z_][\w.-]*=")
_DIGEST = re.compile(r"(?i)(?:[\w.-]+@)?sha(?:1|256|384|512):")
_URL = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://(?:[^\s:/@]*:([^\s@/]+)@)?[^\s/]*(\S*)")
_URL_SEGMENT = re.compile(r"[A-Za-z0-9_-]{16,}")
# Identifier shapes: UUIDs, hex (hashes, request and trace ids), digits.
_IDENTIFIER = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{7,}|[\d.:_-]+")
_HEX_RUN = frozenset("0123456789abcdefABCDEF-")
_KEYWORD_BEFORE = re.compile(r"(?i)\b(?:api[ _-]?key|key|token|secret|passw(?:or)?d|pwd|passphrase|auth|credentials?|bearer)\b")

# Personal-data refinement. Models tag log noise as personal data: request ids and UUIDs as
# account numbers, log timestamps as dates, API paths as URLs.
_ACCOUNT_SHAPE = re.compile(r"(?:\d[ -]?){8,19}|[A-Z]{2}\d{2}(?: ?[A-Z0-9]){10,30}")  # card/bank digits, IBAN
_ACCOUNT_KEYWORD = re.compile(r"(?i)\b(?:account|acct|iban|card|routing|bank|ssn|social security|tax id)\b")
_TIME_OF_DAY = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?")
_RESERVED_EMAIL = re.compile(r"(?i)@(?:[\w-]+\.)*(?:example\.(?:com|net|org)|test|invalid|localhost)$")  # RFC 2606
_ROLE_EMAIL = re.compile(r"(?i)^(?:no-?reply|do-?not-?reply|notifications?|postmaster|mailer-daemon)@")  # not a person
_FICTIONAL_PHONE = re.compile(r"555[-. ]?01\d\d$")  # NANP reserves 555-0100..0199 for fiction
_IDENTIFIER_WORD = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*")  # ops-admin, setup.sh, etl
_BIRTH_BEFORE = re.compile(r"(?i)(?<![a-z])(?:born|birth|birthday|dob|d\.o\.b)(?![a-z])")  # matches date_of_birth too
_PII_EDGE = "/\\:;,.'\"`()[]{}<>|="


class Pipeline:
    def __init__(self, rules: RulesDetector | None, pf=None, pii: bool = False, refine: bool = True,
                 refine_pii: bool = True):
        self.rules = rules
        self.pf = pf
        self.pii = pii
        # Turned off only to measure what refinement does (benchmark flags :raw and :rawpii).
        self.refine = refine
        self.refine_pii_spans = refine_pii
        self.allowlist = rules.allowlist if rules else None
        # Detection funnel for the stats feed: counts only, for newly scanned text.
        self.funnel: Counter[str] = Counter()
        parts = [p for p, on in (("rules", rules), (getattr(pf, "name", "pf"), pf)) if on]
        flags = [f for f, on in (("pii", pii), ("raw", not refine), ("rawpii", not refine_pii)) if on]
        self.name = "+".join(parts) + "".join(f":{f}" for f in flags)

    def detect(self, text: str) -> list[Span]:
        spans: list[Span] = []
        if self.rules:
            found = self.rules.detect(text)
            self.funnel["candidates_rules"] += len(found)
            spans += found
        self.funnel["candidates_model"] += 0
        spans += self.model_spans(text)
        if self.pii and self.refine_pii_spans:
            spans = [t for s in spans if (t := self.trim_pii(text, s)) is not None
                     and (t.type == "SECRET" or t.source.startswith("rules") or self.keep_pii(text, t))]
        if not self.pii:
            spans = [s for s in spans if s.type == "SECRET"]
        refined = len(spans)
        if self.allowlist:
            spans = self.allowlist.filter(text, spans)
        merged = merge(spans)
        # Stages: raw candidates -> after refinement -> after the allowlist -> masked (overlaps merged).
        self.funnel["after_refinement"] += refined
        self.funnel["after_allowlist"] += len(spans)
        self.funnel["masked"] += len(merged)
        return merged

    def model_spans(self, text: str) -> list[Span]:
        """The model's spans: secrets refined, personal data only when enabled."""
        out: list[Span] = []
        if not self.pf:
            return out
        for s in self.pf.detect(text):
            if s.type == "ACCOUNT" and self.refine and self.credential_not_account(text, s):
                s = Span(s.start, s.end, "SECRET", s.confidence, s.source)
            if s.type != "SECRET" and not self.pii:
                continue
            self.funnel["candidates_model"] += 1
            out += self.refine_secret(text, s) if self.refine and s.type == "SECRET" else [s]
        return out

    @staticmethod
    def credential_not_account(text: str, span: Span) -> bool:
        """The model sometimes labels an API key in prose an account number ("the Datadog key for
        staging is 3f9a…"). Not shaped like card or bank digits, with a digit (so not a name such as
        `X-API-Key`), after a secret keyword: a secret."""
        value = text[span.start : span.end]
        before = text[max(0, span.start - 40) : span.start]
        return (any(c.isdigit() for c in value) and not _ACCOUNT_SHAPE.fullmatch(value)
                and bool(_KEYWORD_BEFORE.search(before)))

    def refine_secret(self, text: str, span: Span) -> list[Span]:
        """Tighten a model SECRET span. The model tends to run spans across neighboring
        `key=value` fields in logs and to tag UUIDs and hashes as secrets.

        Secrets do not contain whitespace (private keys are L1's job), so the span splits
        into pieces. Each piece loses edge punctuation and a leading `label=`. Pieces shaped
        like identifiers survive only when a secret keyword precedes them in prose or an
        assignment (not as a URL path segment).
        """
        out = []
        for m in _PIECE.finditer(text, span.start, span.end):
            a, b = m.span()
            while a < b and text[a] in _EDGE:
                a += 1
            while b > a and text[b - 1] in _EDGE:
                b -= 1
            label = _LABEL.match(text, a, b)
            if label:
                a = label.end()
            digest = _DIGEST.match(text, a, b)
            if digest:
                a = digest.end()
            url = _URL.match(text, a, b)
            if url:
                # In a URL the secret is the password, or a token-like path segment (webhooks).
                if url.group(1):
                    a, b = url.span(1)
                elif not any(shannon_entropy(seg) > 3.5 for seg in _URL_SEGMENT.findall(url.group(2))):
                    continue
            value = text[a:b]
            if len(value) < 8:
                continue
            if self.rules and self.rules.looks_like_placeholder(value):
                continue
            # The model often starts a span partway into an id (".../accounts/e|65d2c19-..."):
            # judge the whole run of hex digits and hyphens around the piece.
            lo, hi = a, b
            while lo > 0 and text[lo - 1] in _HEX_RUN:
                lo -= 1
            while hi < len(text) and text[hi] in _HEX_RUN:
                hi += 1
            run = text[lo:hi]
            if _IDENTIFIER.fullmatch(value) or (run != value and _IDENTIFIER.fullmatch(run) and len(run.strip("-")) >= 16):
                before = text[max(0, lo - 40) : lo]
                if before.endswith("/") or not _KEYWORD_BEFORE.search(before):
                    continue
            out.append(Span(a, b, span.type, span.confidence, span.source))
        return out

    @staticmethod
    def trim_pii(text: str, span: Span) -> Span | None:
        """Model personal-data spans often carry punctuation at the edges ("/alex" in a path)."""
        if span.type == "SECRET" or span.source.startswith("rules"):
            return span
        a, b = span.start, span.end
        while a < b and text[a] in _PII_EDGE:
            a += 1
        while b > a and text[b - 1] in _PII_EDGE:
            b -= 1
        return Span(a, b, span.type, span.confidence, span.source) if a < b else None

    @staticmethod
    def keep_pii(text: str, span: Span) -> bool:
        """Drop model personal-data spans that are log noise or reserved example values."""
        value = text[span.start : span.end]
        before = text[max(0, span.start - 40) : span.start]
        if span.type == "ACCOUNT":
            return bool(_ACCOUNT_SHAPE.fullmatch(value) or _ACCOUNT_KEYWORD.search(before))
        if span.type == "DATE":
            # A personal date is a date of birth; today's date or a release date is not.
            return not _TIME_OF_DAY.search(value) and bool(_BIRTH_BEFORE.search(text[max(0, span.start - 60) : span.start]))
        if span.type == "URL":
            return "://" in value  # an API path is not a personal URL
        if span.type == "EMAIL":
            return not (_RESERVED_EMAIL.search(value) or _ROLE_EMAIL.match(value))
        if span.type == "PHONE":
            return not _FICTIONAL_PHONE.search(value)
        if span.type == "PERSON":
            return not _IDENTIFIER_WORD.fullmatch(value)  # a name has a capital or a space
        return True


class ModelUnavailable(RuntimeError):
    pass


def default_pipeline(pii: bool = False, rules_only: bool = False, allow_strings=(), allow_patterns=()) -> Pipeline:
    """The v1 pipeline. Fails loudly, never silently weaker, when the L2 model is missing."""
    rules = RulesDetector()
    rules.allowlist.extend(allow_strings, allow_patterns)
    if rules_only:
        return Pipeline(rules, None, pii=pii)
    from .pfserve import PfServe, PfServeError, find_binary, find_model

    binary, model = find_binary(), find_model()
    if binary is None:
        raise ModelUnavailable("pf-serve is not installed: build it with native/pf-serve/build.sh, or pass --rules-only.")
    if model is None:
        raise ModelUnavailable("the Privacy Filter model is not downloaded: run `sotto setup`, or pass --rules-only.")
    try:
        pf = PfServe(binary, model)
    except (PfServeError, OSError) as e:
        raise ModelUnavailable(f"the Privacy Filter model did not load ({e}); pass --rules-only to run without it.") from e
    return Pipeline(rules, pf, pii=pii)
