"""L1: regex rules, Shannon entropy, and Luhn and IBAN checksums."""

from __future__ import annotations

import math
import re
import tomllib
from collections import Counter
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from . import Span

SOURCE = "rules"


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    regex: re.Pattern[str]
    group: int = 0
    keywords: tuple[str, ...] = ()
    confidence: float = 0.99
    type: str = "SECRET"
    filters: str | bool = "placeholder"
    prose_guard: bool = False


class Allowlist:
    def __init__(self, strings=(), patterns=()):
        self.strings = frozenset(strings)
        self.patterns = [re.compile(p) for p in patterns]

    def extend(self, strings=(), patterns=()) -> None:
        """Add user entries; the built-in ones always stay."""
        self.strings = self.strings | frozenset(strings)
        self.patterns += [re.compile(p) for p in patterns]

    def allows(self, value: str) -> bool:
        if value in self.strings:
            return True
        return any(p.fullmatch(value) for p in self.patterns)

    def filter(self, text: str, spans: list[Span]) -> list[Span]:
        return [s for s in spans if not self.allows(text[s.start : s.end])]


def shannon_entropy(value: str) -> float:
    n = len(value)
    if n == 0:
        return 0.0
    return -sum(c / n * math.log2(c / n) for c in Counter(value).values())


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = ord(ch) - 48
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def iban_valid(iban: str) -> bool:
    """ISO 13616 mod-97: move the first four characters to the end, letters become 10..35."""
    s = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in s)) % 97 == 1


# '=' only as trailing base64 padding, so `NAME=value` never becomes one candidate.
_PROSE_WORD = re.compile(r"[a-z]+")
_PROSE_NEXT = re.compile(r" [a-z]")
_ENTROPY_CANDIDATE = re.compile(r"[A-Za-z0-9+/_-]{20,}={0,2}")
_DIGEST_PREFIX = re.compile(r"(?i)(?:sha(?:1|224|256|384|512)|md5)[-:]")
_HEX = re.compile(r"[0-9a-fA-F]+")
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
# 13-19 digits, optionally grouped by single spaces or hyphens.
# Public keys and certificates are long base64 by design; entropy hits inside them are noise.
_PUBLIC_PEM = re.compile(r"-----BEGIN (?:PUBLIC KEY|RSA PUBLIC KEY|CERTIFICATE|X509 CRL|SSH2 PUBLIC KEY|PGP PUBLIC KEY BLOCK)-----[\s\S]*?-----END [A-Z0-9 ]+-----")
_CARD = re.compile(r"(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d-])")
# Issuer prefixes for Visa, Mastercard, Amex, Discover; cuts Luhn-valid noise like timestamps.
_CARD_IIN = re.compile(r"4|5[1-5]|2[2-7]|3[47]|6(?:011|5)")
# Country code, check digits, then the account part, compact or in groups of four.
_IBAN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?)(?![A-Za-z0-9])")
# Countries in the SWIFT IBAN registry.
_IBAN_COUNTRIES = frozenset(
    "AD AE AL AT AZ BA BE BG BH BI BR BY CH CR CY CZ DE DJ DK DO EE EG ES FI FK FO FR GB GE GI GL GR GT HN HR HU IE IL "
    "IQ IS IT JO KW KZ LB LC LI LT LU LV LY MC MD ME MK MN MR MT MU NI NL NO OM PK PL PS PT QA RO RS RU SA SC SD SE SI "
    "SK SM SO ST SV TL TN TR UA VA VG XK YE".split()
)


class RulesDetector:
    name = SOURCE

    def __init__(self, path: Path | None = None):
        if path is None:
            raw = resources.files("sotto.detect").joinpath("rules.toml").read_text()
        else:
            raw = path.read_text()
        cfg = tomllib.loads(raw)
        self.rules = [
            Rule(
                id=r["id"],
                regex=re.compile(r["regex"]),
                group=r.get("group", 0),
                keywords=tuple(k.lower() for k in r.get("keywords", ())),
                confidence=r.get("confidence", 0.99),
                type=r.get("type", "SECRET"),
                filters=r.get("filters", "placeholder"),
                prose_guard=r.get("prose_guard", False),
            )
            for r in cfg.get("rule", [])
        ]
        allow = cfg.get("allowlist", {})
        self.allowlist = Allowlist(allow.get("strings", ()), allow.get("patterns", ()))
        f = cfg.get("filters", {})
        self._placeholder_filters = [re.compile(f[k]) for k in ("stopwords", "placeholder", "repeated", "public") if k in f]
        self._all_filters = self._placeholder_filters + [re.compile(f[k]) for k in ("reference", "numeric") if k in f]
        self.entropy = cfg.get("entropy", {"enabled": False})
        if self.entropy.get("enabled"):
            self._skip_before = re.compile(self.entropy["skip_before"])
        self.luhn = cfg.get("luhn", {"enabled": False})
        self.iban = cfg.get("iban", {"enabled": False})

    def looks_like_placeholder(self, value: str, level: str | bool = "placeholder") -> bool:
        if not level:
            return False
        filters = self._all_filters if level == "all" else self._placeholder_filters
        return any(p.search(value) for p in filters)

    def detect(self, text: str) -> list[Span]:
        lowered = text.lower()
        spans: list[Span] = []
        for rule in self.rules:
            if rule.keywords and not any(k in lowered for k in rule.keywords):
                continue
            for m in rule.regex.finditer(text):
                start, end = m.span(rule.group)
                if start < 0 or start == end:
                    continue
                if self.looks_like_placeholder(m.group(rule.group), rule.filters):
                    continue
                if rule.prose_guard and _PROSE_WORD.fullmatch(m.group(rule.group)) and _PROSE_NEXT.match(text, end):
                    continue
                spans.append(Span(start, end, rule.type, rule.confidence, f"{SOURCE}:{rule.id}"))
        if self.entropy.get("enabled"):
            spans.extend(self._entropy_spans(text))
        if self.luhn.get("enabled"):
            spans.extend(self._card_spans(text))
        if self.iban.get("enabled"):
            spans.extend(self._iban_spans(text))
        return self.allowlist.filter(text, spans)

    def _entropy_spans(self, text: str) -> list[Span]:
        e = self.entropy
        out = []
        public = [m.span() for m in _PUBLIC_PEM.finditer(text)] if "-----BEGIN" in text else []
        for m in _ENTROPY_CANDIDATE.finditer(text):
            if any(a <= m.start() < b for a, b in public):
                continue
            value = m.group().strip("=-_")
            n = len(value)
            if n < e["min_len"] or n > e["max_len"]:
                continue
            if _HEX.fullmatch(value) or _UUID.search(value) or _DIGEST_PREFIX.match(value):
                continue
            has_lower = any(c.islower() for c in value)
            has_upper = any(c.isupper() for c in value)
            has_digit = any(c.isdigit() for c in value)
            classes = has_lower + has_upper + has_digit
            if classes < 2 or (classes == 2 and n < 32):
                continue
            if shannon_entropy(value) < e["min_ratio"] * math.log2(min(n, 64)):
                continue
            if self._skip_before.search(text, max(0, m.start() - 24), m.start()):
                continue
            after = text[m.end() : m.end() + 1]
            if after in ("=", ":") or (m.group().endswith("=") and after and not after.isspace() and after not in "\"'`,;)]}"):
                continue  # a key name (distributionSha256Sum=...), not a value; real padding ends the value
            if self.looks_like_placeholder(value, "all"):
                continue
            start = m.start() + m.group().index(value)
            out.append(Span(start, start + n, "SECRET", e["confidence"], f"{SOURCE}:entropy"))
        return out

    def _card_spans(self, text: str) -> list[Span]:
        out = []
        for m in _CARD.finditer(text):
            digits = re.sub(r"[ -]", "", m.group())
            if 13 <= len(digits) <= 19 and _CARD_IIN.match(digits) and luhn_valid(digits):
                out.append(Span(m.start(), m.end(), "ACCOUNT", self.luhn["confidence"], f"{SOURCE}:luhn"))
        return out

    def _iban_spans(self, text: str) -> list[Span]:
        out = []
        for m in _IBAN.finditer(text):
            iban = m.group(1).replace(" ", "")
            if 15 <= len(iban) <= 34 and iban[:2] in _IBAN_COUNTRIES and iban_valid(iban):
                out.append(Span(m.start(1), m.end(1), "ACCOUNT", self.iban["confidence"], f"{SOURCE}:iban"))
        return out
