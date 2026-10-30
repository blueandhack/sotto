"""Union spans from all layers. When in doubt, redact: overlaps merge into the widest span."""

from __future__ import annotations

from . import PRIORITY, Span


def merge(spans: list[Span]) -> list[Span]:
    """Merge overlapping spans; the result keeps the highest-priority type and confidence."""
    out: list[Span] = []
    for s in sorted(spans, key=lambda s: (s.start, -s.end)):
        if out and s.start < out[-1].end:
            cur = out[-1]
            sources = cur.source if s.source in cur.source.split("|") else f"{cur.source}|{s.source}"
            out[-1] = Span(
                cur.start,
                max(cur.end, s.end),
                min(cur.type, s.type, key=PRIORITY.__getitem__),
                max(cur.confidence, s.confidence),
                sources,
            )
        else:
            out.append(s)
    return out
