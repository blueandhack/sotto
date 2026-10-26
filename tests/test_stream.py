import hashlib
import hmac
import json
import random

import anyio
import httpx
import pytest

from sotto import selftest
from sotto.detect.pipeline import Pipeline
from sotto.detect.rules import RulesDetector
from sotto.proxy import Proxy
from sotto.redact import Redactor
from sotto.restore import StreamRestorer, restore_response
from sotto.vault import Vault

SALT = bytes(range(32))


def make_vault():
    v = Vault(SALT)
    # Synthetic values. One contains quotes and backslashes to test JSON escaping.
    p_short = v.placeholder("SECRET", 'Xk2"9f\\Lq8vPz')
    # Force a 12-digit placeholder for a second value.
    short = "SOTTO_SECRET_" + hmac.new(SALT, b"SECRET\0Rt5mQ2wZ", hashlib.sha256).hexdigest()[:8]
    v._values.setdefault(short, "someone else")
    p_long = v.placeholder("SECRET", "Rt5mQ2wZ")
    p_name = v.placeholder("PERSON", "Ada Lovelace")
    assert len(p_long.rsplit("_", 1)[1]) == 12
    return v, p_short, p_long, p_name


def sse(name, data):
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


def build_stream(text, tool_json, fetch_json, thinking, text_cuts=(), json_cuts=()):
    def pieces(s, cuts):
        bounds = [0, *sorted(set(c for c in cuts if 0 < c < len(s))), len(s)]
        return [s[a:b] for a, b in zip(bounds, bounds[1:])] or [""]

    ev = [sse("message_start", {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant", "content": []}})]
    ev.append(sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}}))
    ev.append(sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": thinking}}))
    ev.append(sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "c2ln"}}))
    ev.append(sse("content_block_stop", {"type": "content_block_stop", "index": 0}))
    ev.append(sse("content_block_start", {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}}))
    for p in pieces(text, text_cuts):
        ev.append(sse("content_block_delta", {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": p}}))
    ev.append("event: ping\ndata: {\"type\": \"ping\"}\n\n")
    ev.append(sse("content_block_stop", {"type": "content_block_stop", "index": 1}))
    for idx, name, js in ((2, "Write", tool_json), (3, "WebFetch", fetch_json)):
        ev.append(sse("content_block_start", {"type": "content_block_start", "index": idx, "content_block": {"type": "tool_use", "id": f"toolu_{idx}", "name": name, "input": {}}}))
        for p in pieces(js, json_cuts):
            ev.append(sse("content_block_delta", {"type": "content_block_delta", "index": idx, "delta": {"type": "input_json_delta", "partial_json": p}}))
        ev.append(sse("content_block_stop", {"type": "content_block_stop", "index": idx}))
    ev.append(sse("some_future_event", {"type": "some_future_event", "x": 1}))
    ev.append(sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 9}}))
    ev.append(sse("message_stop", {"type": "message_stop"}))
    return "".join(ev).encode()


def assemble(stream: bytes) -> tuple[dict, list[str]]:
    """Accumulate an SSE stream into a message, the way an SDK would; also the event order."""
    blocks, order = {}, []
    for raw in stream.decode().split("\n\n"):
        data = next((line[5:].strip() for line in raw.splitlines() if line.startswith("data:")), None)
        if not data:
            continue
        d = json.loads(data)
        order.append(d["type"] if d["type"] != "content_block_delta" else f"delta:{d['index']}")
        if d["type"] == "content_block_start":
            blocks[d["index"]] = {**d["content_block"], "_json": ""}
        elif d["type"] == "content_block_delta":
            b, delta = blocks[d["index"]], d["delta"]
            if delta["type"] == "text_delta":
                b["text"] = b.get("text", "") + delta["text"]
            elif delta["type"] == "thinking_delta":
                b["thinking"] += delta["thinking"]
            elif delta["type"] == "signature_delta":
                b["signature"] = delta["signature"]
            elif delta["type"] == "input_json_delta":
                b["_json"] += delta["partial_json"]
    content = []
    for i in sorted(blocks):
        b = dict(blocks[i])
        js = b.pop("_json")
        if b["type"] == "tool_use":
            b["input"] = json.loads(js)
        content.append(b)
    # Deltas per block collapse to one marker: buffering may merge or split them.
    collapsed = [o for j, o in enumerate(order) if not (o.startswith("delta:") and j and order[j - 1] == o)]
    return {"content": content}, collapsed


def restore_stream(vault, stream: bytes, cuts) -> bytes:
    r = StreamRestorer(vault)
    bounds = [0, *sorted(set(cuts)), len(stream)]
    out = b"".join(r.feed(stream[a:b]) for a, b in zip(bounds, bounds[1:]))
    return out + r.close()


@pytest.fixture(scope="module")
def case():
    vault, p_short, p_long, p_name = make_vault()
    text = (f"Set it to {p_short} and call {p_name}. The other is {p_long}abc. "
            f"Literal SOTTO_SEC stays, so does SOTTO_SECRET_zz and {p_short}0123 ends")
    tool = json.dumps({"file_path": "/tmp/.env", "content": f"TOKEN={p_short}\nOWNER={p_name}\n"})
    fetch = json.dumps({"url": f"https://example.com/?t={p_short}"})
    thinking = f"the user wants {p_short} rotated"
    stream = build_stream(text, tool, fetch, thinking)
    original, order = assemble(stream)
    expected = restore_response(original, vault)
    return vault, stream, expected, order, (text, tool, fetch, thinking), p_short


def check(vault, stream, cuts, expected, order):
    got, got_order = assemble(restore_stream(vault, stream, cuts))
    assert got == expected
    assert got_order == order


def test_expected_restore_is_what_we_think(case):
    vault, _, expected, _, _, p_short = case
    text, write, fetch, thinking = expected["content"][1], expected["content"][2], expected["content"][3], expected["content"][0]
    assert 'Xk2"9f\\Lq8vPz' in text["text"] and "Ada Lovelace" in text["text"] and "Rt5mQ2wZabc" in text["text"]
    assert "SOTTO_SEC stays" in text["text"] and "SOTTO_SECRET_zz" in text["text"]
    assert write["input"]["content"] == 'TOKEN=Xk2"9f\\Lq8vPz\nOWNER=Ada Lovelace\n'
    assert p_short in fetch["input"]["url"]  # WebFetch keeps the placeholder
    assert p_short in thinking["thinking"]  # signed thinking is untouched


def test_every_single_byte_split(case):
    vault, stream, expected, order, _, _ = case
    for i in range(len(stream) + 1):
        check(vault, stream, [i], expected, order)


def test_random_multi_chunk_splits(case):
    vault, stream, expected, order, _, _ = case
    rng = random.Random(7)
    for _ in range(500):
        check(vault, stream, rng.sample(range(1, len(stream)), rng.randint(2, 40)), expected, order)


def test_placeholders_split_across_deltas_at_every_offset(case):
    vault, _, expected, _, (text, tool, fetch, thinking), _ = case
    for i in range(len(text) + 1):
        stream = build_stream(text, tool, fetch, thinking, text_cuts=[i, i + 7])
        check(vault, stream, [len(stream) // 3], expected, assemble(stream)[1])
    for i in range(len(tool) + 1):
        stream = build_stream(text, tool, fetch, thinking, json_cuts=[i])
        check(vault, stream, [], expected, assemble(stream)[1])


def test_crlf_separators_and_unknown_events_pass_through():
    vault, p_short, _, _ = make_vault()
    stream = (b'event: content_block_start\r\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\r\n\r\n'
              + f'event: content_block_delta\r\ndata: {{"type":"content_block_delta","index":0,"delta":{{"type":"text_delta","text":"{p_short}"}}}}\r\n\r\n'.encode()
              + b'event: content_block_stop\r\ndata: {"type":"content_block_stop","index":0}\r\n\r\n'
              + b"event: error\r\ndata: {\"type\": \"error\", \"error\": {\"type\": \"overloaded_error\"}}\r\n\r\n")
    out = restore_stream(vault, stream, [5, 80])
    assert b'Xk2\\"9f\\\\Lq8vPz' in out  # restored and JSON-escaped in the re-emitted event
    assert out.endswith(b"event: error\r\ndata: {\"type\": \"error\", \"error\": {\"type\": \"overloaded_error\"}}\r\n\r\n")


def test_proxy_restores_a_streamed_answer_end_to_end():
    canary = selftest.make_canary()

    async def go():
        mock = selftest.MockUpstream()
        up = httpx.AsyncClient(transport=httpx.ASGITransport(app=mock.app), base_url="http://up")
        proxy = Proxy(Redactor(Pipeline(RulesDetector(), None), Vault(SALT)), upstream="http://up", client=up)
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=proxy.app), base_url="http://127.0.0.1:7788")
        body = {"model": "m", "stream": True, "messages": [{"role": "user", "content": f"export GITHUB_TOKEN={canary}"}]}
        r = await client.post("/v1/messages", json=body)
        return r, mock

    r, mock = anyio.run(go)
    blocks = selftest._assemble_stream(r.text)
    assert r.status_code == 200 and canary in blocks[0] and canary in blocks[1]  # restored in the stream
    assert canary not in blocks[2]  # WebFetch keeps the placeholder
    assert not any(canary.encode() in b for b in mock.received)  # and never sent upstream
