"""L2 through pf-serve: OpenAI Privacy Filter on privacy-filter.cpp (ggml), in a process of its own.

pf-serve runs on Metal on a Mac and on Vulkan or the CPU elsewhere, so this backend needs no
Python ML packages. Protocol (little-endian), after one JSON hello line on stdout:

    request: u32 n, then n times: u32 len, len bytes of UTF-8
    reply:   u32 0, then per text: u32 count, count times: i32 start, i32 end (byte offsets),
             f32 score, u8 len, the label; or u32 1, u32 len, an error message

pf-serve and its protocol come from magpie (MIT): https://github.com/yetone/magpie
"""

from __future__ import annotations

import json
import struct
import subprocess
import threading
from pathlib import Path

from . import Span

SOURCE = "pf-serve"

LABEL_TYPES = {
    "account_number": "ACCOUNT",
    "private_address": "ADDRESS",
    "private_date": "DATE",
    "private_email": "EMAIL",
    "private_person": "PERSON",
    "private_phone": "PHONE",
    "private_url": "URL",
    "secret": "SECRET",
}


class PfServeError(RuntimeError):
    pass


class PfServe:
    """Starts pf-serve once and keeps it warm. `detect` is one request; calls are serialized."""

    # 0: every decoded span comes back, as with the MLX backend; the pipeline's refinement decides.
    def __init__(self, binary: str | Path, model: str | Path, threshold: float = 0.0, name: str = SOURCE):
        self.name = name
        self._lock = threading.Lock()
        self._proc = subprocess.Popen([str(binary), str(model), repr(threshold)], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        line = self._proc.stdout.readline()
        try:
            hello = json.loads(line)
        except ValueError:
            hello = {"error": "no hello line" if not line else "unreadable hello line"}
        if hello.get("error") or not hello.get("device"):
            self.close()
            raise PfServeError(f"pf-serve did not start: {hello.get('error', 'no device')}")
        self.device = hello["device"]
        self.load_ms = hello.get("ms")

    def detect(self, text: str) -> list[Span]:
        if not text.strip():
            return []
        raw = text.encode("utf-8")
        with self._lock:
            found = self._classify(raw)
        spans = []
        for start, end, score, label in found:
            # Byte offsets to str offsets; a model span always ends on a character boundary.
            a = len(raw[:start].decode("utf-8", "ignore"))
            b = a + len(raw[start:end].decode("utf-8", "ignore"))
            while a < b and text[a].isspace():
                a += 1
            while b > a and text[b - 1].isspace():
                b -= 1
            kind = LABEL_TYPES.get(label)
            if kind and a < b:
                spans.append(Span(a, b, kind, score, self.name))
        return spans

    def _classify(self, raw: bytes) -> list[tuple[int, int, float, str]]:
        if self._proc.poll() is not None:
            raise PfServeError(f"pf-serve exited ({self._proc.returncode})")
        try:
            self._proc.stdin.write(struct.pack("<II", 1, len(raw)) + raw)
            self._proc.stdin.flush()
            status = self._u32()
            if status != 0:
                raise PfServeError(f"pf-serve: {self._read(self._u32()).decode('utf-8', 'replace')}")
            out = []
            for _ in range(self._u32()):
                start, end, score = struct.unpack("<iif", self._read(12))
                label = self._read(self._read(1)[0]).decode("ascii", "replace")
                if not 0 <= start < end <= len(raw):
                    raise PfServeError(f"pf-serve sent span {start}..{end} for {len(raw)} bytes")
                out.append((start, end, score, label))
            return out
        except (OSError, struct.error) as e:
            self.close()
            raise PfServeError(f"pf-serve stopped responding ({type(e).__name__})") from e

    def _u32(self) -> int:
        return struct.unpack("<I", self._read(4))[0]

    def _read(self, n: int) -> bytes:
        b = self._proc.stdout.read(n)
        if len(b) != n:
            raise PfServeError("pf-serve closed its output")
        return b

    def close(self) -> None:
        if self._proc.poll() is None:
            self._proc.stdin.close()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
