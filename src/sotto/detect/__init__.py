"""Detectors return spans over the original text, never rewritten text."""

from dataclasses import dataclass

# Highest priority first: when spans of different types merge, the earlier type wins.
TYPES = ("SECRET", "ACCOUNT", "PERSON", "EMAIL", "PHONE", "ADDRESS", "URL", "DATE")
PRIORITY = {t: i for i, t in enumerate(TYPES)}


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int
    type: str
    confidence: float = 1.0
    source: str = ""

    def __len__(self) -> int:
        return self.end - self.start
