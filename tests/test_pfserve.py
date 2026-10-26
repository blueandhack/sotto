import stat
import sys

import pytest

from sotto.detect.pfserve import PfServe, PfServeError

# A stand-in for pf-serve that speaks its protocol: it reports " Priya Raman" (with the leading
# space a BPE token carries) as a person, "ghp_" tokens as secrets, and "kitten" with a label
# sotto does not map. MODE selects a failure.
FAKE = r'''#!{python}
import json, re, struct, sys
mode = "{mode}"
out = sys.stdout.buffer
if mode == "nohello":
    sys.exit(1)
if mode == "badload":
    out.write(b'{{"error":"the model didn\'t load"}}\n'); out.flush(); sys.exit(1)
out.write(b'{{"device":"Metal: fake","gpu":true,"ms":5}}\n'); out.flush()
inp = sys.stdin.buffer
def u32():
    b = inp.read(4)
    return struct.unpack("<I", b)[0] if len(b) == 4 else None
while True:
    n = u32()
    if n is None:
        break
    texts = [inp.read(u32()) for _ in range(n)]
    if mode == "error":
        msg = b"classify failed"
        out.write(struct.pack("<II", 1, len(msg)) + msg); out.flush(); continue
    if mode == "crash":
        sys.exit(3)
    reply = struct.pack("<I", 0)
    for t in texts:
        found = [(m.start(), m.end(), 0.97, b"private_person") for m in re.finditer(rb" Priya Raman", t)]
        found += [(m.start(), m.end(), 0.88, b"secret") for m in re.finditer(rb"ghp_[A-Za-z0-9]+", t)]
        found += [(m.start(), m.end(), 0.5, b"kitten") for m in re.finditer(rb"kitten", t)]
        reply += struct.pack("<I", len(found))
        for a, b, s, lab in found:
            reply += struct.pack("<iif", a, b, s) + bytes([len(lab)]) + lab
    out.write(reply); out.flush()
'''


def fake(tmp_path, mode="ok"):
    p = tmp_path / f"pf-serve-{mode}"
    p.write_text(FAKE.format(python=sys.executable, mode=mode))
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


def test_spans_use_str_offsets_after_multibyte_text(tmp_path):
    pf = PfServe(fake(tmp_path), "model.gguf")
    try:
        token = "ghp_" + "Zq8vX2mN4pL7kR9tY3wB6cF1hJ5dG0sAe7Qw"
        text = f"Café owner — 日本語 — is Priya Raman; token {token} kitten"
        spans = pf.detect(text)
        got = {(text[s.start:s.end], s.type, round(s.confidence, 2), s.source) for s in spans}
        assert got == {("Priya Raman", "PERSON", 0.97, "pf-serve"), (token, "SECRET", 0.88, "pf-serve")}
        assert pf.device == "Metal: fake"
        assert pf.detect("   ") == []  # nothing sent for blank text
    finally:
        pf.close()


def test_many_requests_on_one_process(tmp_path):
    pf = PfServe(fake(tmp_path), "model.gguf")
    try:
        for i in range(50):
            assert len(pf.detect(f"{i} ghp_abc{i}")) == 1
    finally:
        pf.close()


@pytest.mark.parametrize("mode, message", [("nohello", "no hello line"), ("badload", "the model didn't load")])
def test_start_failures_are_reported(tmp_path, mode, message):
    with pytest.raises(PfServeError, match=message):
        PfServe(fake(tmp_path, mode), "model.gguf")


def test_error_reply_raises(tmp_path):
    pf = PfServe(fake(tmp_path, "error"), "model.gguf")
    try:
        with pytest.raises(PfServeError, match="classify failed"):
            pf.detect("hello Priya Raman")
    finally:
        pf.close()


def test_a_crash_raises_and_stays_failed(tmp_path):
    pf = PfServe(fake(tmp_path, "crash"), "model.gguf")
    with pytest.raises(PfServeError):
        pf.detect("hello Priya Raman")
    with pytest.raises(PfServeError, match="exited"):
        pf.detect("again")
