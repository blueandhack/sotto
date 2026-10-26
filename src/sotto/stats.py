"""Counters for the stats feed the Mac app reads. Counts, types and timestamps only.

Nothing here may ever hold a value or a placeholder: the feed is read by another process.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from collections import Counter, deque
from pathlib import Path

TOKEN_FILE = Path.home() / ".config" / "sotto" / "stats-token"


def stats_token(path: Path = TOKEN_FILE) -> str:
    """A bearer token for the stats endpoint, in a file only this user can read."""
    if path.exists():
        return path.read_text().strip()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    token = secrets.token_urlsafe(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token)
    return token


class Stats:
    def __init__(self, recent: int = 200):
        self._lock = threading.Lock()
        self.started = time.time()
        self.requests = Counter()  # by outcome: forwarded, blocked, rejected, upstream_error
        self.redacted = Counter()  # by type
        self.restored = Counter()  # by type
        self.scan_ms: deque[float] = deque(maxlen=1000)
        self.events: deque[dict] = deque(maxlen=recent)
        self.scanned = 0  # requests that went through the detectors
        self.with_findings = 0  # of those, requests where something was masked
        self.minutes: deque[dict] = deque(maxlen=180)  # per-minute buckets for the timeline

    def record(self, path: str, outcome: str, status: int, scan_ms: float | None = None,
               redacted: Counter | None = None, restored: Counter | None = None) -> None:
        with self._lock:
            self.requests[outcome] += 1
            self.redacted.update(redacted or {})
            self.restored.update(restored or {})
            if scan_ms is not None:
                self.scan_ms.append(scan_ms)
                self.scanned += 1
                self.with_findings += bool(redacted)
            minute = int(time.time() // 60) * 60
            if not self.minutes or self.minutes[-1]["t"] != minute:
                self.minutes.append({"t": minute, "requests": 0, "masked": Counter(), "restored": 0, "blocked": 0})
            bucket = self.minutes[-1]
            bucket["requests"] += 1
            bucket["masked"].update(redacted or {})
            bucket["restored"] += sum((restored or {}).values())
            bucket["blocked"] += outcome in ("blocked", "rejected")
            self.events.append({
                "ts": round(time.time(), 3), "path": path, "outcome": outcome, "status": status,
                "scan_ms": None if scan_ms is None else round(scan_ms, 1),
                "redacted": dict(redacted or {}), "restored": dict(restored or {}),
            })

    def snapshot(self, **extra) -> dict:
        with self._lock:
            lat = sorted(self.scan_ms)

            def pct(q):
                return round(lat[min(len(lat) - 1, int(q * len(lat)))], 1) if lat else None

            return {
                "started": self.started, "uptime_s": round(time.time() - self.started, 1),
                "requests": dict(self.requests), "redacted": dict(self.redacted), "restored": dict(self.restored),
                "funnel": {"requests": sum(self.requests.values()), "scanned": self.scanned,
                           "with_findings": self.with_findings, "masked": sum(self.redacted.values()),
                           "restored": sum(self.restored.values())},
                "timeline": [{**b, "masked": dict(b["masked"])} for b in self.minutes],
                "scan_ms": {"p50": pct(0.5), "p95": pct(0.95), "n": len(lat)},
                "recent": list(self.events), **extra,
            }
