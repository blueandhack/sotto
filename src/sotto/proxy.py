"""The local proxy: scan requests before they leave, restore responses before Claude Code sees them.

Fail closed everywhere. A request is forwarded only after it was scanned; if scanning fails,
the body is malformed, or the endpoint is one sotto does not scan, the request goes nowhere
and Claude Code gets an API-style error. Logs carry paths, statuses and counts, never bodies,
values or headers.

Observe mode (`detect.observe`) is the exception, chosen by the user: every request is scanned
and counted, then forwarded exactly as it came, unmasked, and nothing is blocked.
"""

from __future__ import annotations

import hmac
import json
import logging
import threading
import time
from collections import Counter

import anyio
import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from .redact import Redactor
from .restore import DEFAULT_POLICY, StreamRestorer, restore_response
from .stats import Stats, client_of, flows, provider_of

log = logging.getLogger("sotto")

UPSTREAM = "https://api.anthropic.com"
SCANNED = frozenset({"/v1/messages", "/v1/messages/count_tokens"})
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})
# Not forwarded upstream; accept-encoding is replaced so responses arrive uncompressed.
HOP_HEADERS = frozenset({"host", "content-length", "connection", "keep-alive", "proxy-connection", "transfer-encoding",
                         "te", "trailer", "upgrade", "accept-encoding"})
RESPONSE_DROP = frozenset({"content-length", "content-encoding", "transfer-encoding", "connection", "keep-alive"})


def api_error(status: int, kind: str, message: str) -> JSONResponse:
    """An error in the Anthropic API's shape, so Claude Code shows it instead of crashing."""
    return JSONResponse({"type": "error", "error": {"type": kind, "message": f"sotto: {message}"}}, status_code=status)


def _host_is_local(request: Request) -> bool:
    # Blocks DNS rebinding: a web page cannot reach the proxy through a name that resolves here.
    host = request.headers.get("host", "")
    name = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
    return name in LOCAL_HOSTS


class Proxy:
    def __init__(self, redactor: Redactor, upstream: str = UPSTREAM, policy: dict[str, str] | None = None,
                 client: httpx.AsyncClient | None = None, stats: Stats | None = None, stats_token: str | None = None,
                 info: dict | None = None, observe=None):
        self.redactor = redactor
        self.upstream = upstream.rstrip("/")
        self.policy = policy or DEFAULT_POLICY
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(600, connect=10))
        self.stats = stats or Stats()
        self.stats_token = stats_token
        self.info = info or {}  # shown in the stats feed: mode, pii, detector, version
        # A callable, re-checked per request (config.ObserveFlag), or a fixed bool.
        self._observe = observe if callable(observe) else (lambda: bool(observe))
        # The detectors and the vault are not thread-safe; scans run one at a time off the event loop.
        self._scan_lock = threading.Lock()
        self.app = Starlette(routes=[Route("/{path:path}", self.handle, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])])

    # --- Entry point --------------------------------------------------------------

    async def handle(self, request: Request) -> Response:
        path = request.url.path
        if not _host_is_local(request):
            return api_error(403, "permission_error", "requests must come from this machine")
        if path.startswith("/_sotto/"):
            return self._local(request, path)
        if path in SCANNED and request.method == "POST":
            return await self._scanned(request, path)
        body = await request.body()
        if self._observe():
            return await self._forward_raw(request, path, body, outcome="observed")
        if body or request.method not in ("GET", "HEAD", "OPTIONS"):
            # An endpoint sotto does not scan must not carry content out unscanned.
            log.warning("blocked %s %s: endpoint is not scanned", request.method, path)
            self.stats.record(path, "blocked", 403, origin=self._origin(request))
            return api_error(403, "permission_error", f"refusing to forward {request.method} {path}: sotto does not scan this endpoint")
        return await self._forward_raw(request, path)

    def _local(self, request: Request, path: str) -> Response:
        if path == "/_sotto/health":
            return JSONResponse({"ok": True})
        if path in ("/_sotto/stats", "/_sotto/history", "/_sotto/flows") and request.method == "GET":
            given = request.headers.get("authorization", "").removeprefix("Bearer ")
            if not self.stats_token or not hmac.compare_digest(given, self.stats_token):
                return api_error(401, "authentication_error", "missing or wrong stats token")
        if path == "/_sotto/flows" and request.method == "GET":
            try:
                window = max(60.0, min(float(request.query_params.get("window", 3600)), 30 * 86400))
            except ValueError:
                return api_error(400, "invalid_request_error", "window must be a number of seconds")
            history = self.stats.history
            events = history.events() if history else list(self.stats.events)
            return JSONResponse({"window": window, **flows(events, time.time() - window)})
        if path == "/_sotto/history" and request.method == "GET":
            q = request.query_params
            try:
                before = float(q["before"]) if "before" in q else None
                limit = max(1, min(int(q.get("limit", 100)), 500))
            except ValueError:
                return api_error(400, "invalid_request_error", "before and limit must be numbers")
            history = self.stats.history
            events = history.page(before, limit, q.get("kind")) if history else []
            return JSONResponse({"events": events})
        if path == "/_sotto/stats" and request.method == "GET":
            detection = dict(getattr(self.redactor.detector, "funnel", {}))
            return JSONResponse(self.stats.snapshot(upstream=self.upstream, vault_size=len(self.redactor.vault),
                                                    detection=detection, **self.info, observe=self._observe()))
        return api_error(404, "not_found_error", "no such sotto endpoint")

    # --- Scanned endpoints ----------------------------------------------------------

    async def _scanned(self, request: Request, path: str) -> Response:
        raw = await request.body()
        if self._observe():
            return await self._observed(request, path, raw)
        try:
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError("not an object")
        except (ValueError, UnicodeDecodeError):
            self.stats.record(path, "rejected", 400, origin=self._origin(request))
            return api_error(400, "invalid_request_error", "request body is not a JSON object; nothing was sent")
        started = time.perf_counter()
        try:
            masked, counts, new = await anyio.to_thread.run_sync(self._redact, body)
        except Exception as e:  # any detector or redaction failure: block, never send raw
            log.error("blocked %s: scan failed (%s)", path, type(e).__name__)
            self.stats.record(path, "blocked", 500, origin=self._origin(request))
            return api_error(500, "api_error", "could not scan this request, so it was not sent")
        scan_ms = (time.perf_counter() - started) * 1000
        payload = json.dumps(masked, ensure_ascii=False).encode()
        url = self.upstream + path + (f"?{request.url.query}" if request.url.query else "")
        headers = self._headers(request)
        try:
            if masked.get("stream") and path == "/v1/messages":
                return await self._stream(url, headers, payload, path, scan_ms, counts, new, origin=self._origin(request))
            resp = await self.client.post(url, headers=headers, content=payload)
        except httpx.HTTPError as e:
            log.error("upstream error on %s: %s", path, type(e).__name__)
            self.stats.record(path, "upstream_error", 502, scan_ms, counts, new=new, origin=self._origin(request))
            return api_error(502, "api_error", f"upstream request failed ({type(e).__name__})")
        restored = Counter()
        content = resp.content
        if path == "/v1/messages" and resp.status_code < 300:
            try:
                data = json.loads(content)
                content = json.dumps(await anyio.to_thread.run_sync(self._restore, data, restored), ensure_ascii=False).encode()
            except ValueError:
                pass  # not JSON: pass it through as it came
        self._warn_unresolved(path, restored)
        self.stats.record(path, "forwarded", resp.status_code, scan_ms, counts, restored, new=new, origin=self._origin(request))
        log.info("%s -> %d redacted=%s restored=%s scan=%.0fms", path, resp.status_code, dict(counts), dict(restored), scan_ms)
        return Response(content, status_code=resp.status_code, headers=self._response_headers(resp))

    async def _observed(self, request: Request, path: str, raw: bytes) -> Response:
        """Observe mode: count what masking would have done, then send the request unchanged."""
        counts, new, scan_ms, body = Counter(), 0, None, None
        try:
            body = json.loads(raw)
            if isinstance(body, dict):
                started = time.perf_counter()
                _, counts, new = await anyio.to_thread.run_sync(self._redact, body)
                scan_ms = (time.perf_counter() - started) * 1000
        except Exception as e:  # observing never stops a request
            log.warning("observe %s: not scanned (%s)", path, type(e).__name__)
        url = self.upstream + path + (f"?{request.url.query}" if request.url.query else "")
        headers = self._headers(request)
        try:
            if path == "/v1/messages" and isinstance(body, dict) and body.get("stream"):
                return await self._stream(url, headers, raw, path, scan_ms, counts, new, outcome="observed", origin=self._origin(request))
            resp = await self.client.post(url, headers=headers, content=raw)
        except httpx.HTTPError as e:
            self.stats.record(path, "upstream_error", 502, scan_ms, counts, new=new, origin=self._origin(request))
            return api_error(502, "api_error", f"upstream request failed ({type(e).__name__})")
        self.stats.record(path, "observed", resp.status_code, scan_ms, counts, new=new, origin=self._origin(request))
        log.info("%s -> %d (observe: sent unmasked) would mask=%s", path, resp.status_code, dict(counts))
        return Response(resp.content, status_code=resp.status_code, headers=self._response_headers(resp))

    def _origin(self, request: Request) -> tuple[str, str]:
        """(client, provider) for the stats: who sent the request, and where it goes."""
        return client_of(request.headers.get("user-agent", "")), provider_of(self.upstream)

    @staticmethod
    def _warn_unresolved(path: str, restored: Counter) -> None:
        if restored.get("unresolved"):
            log.warning("%s: %d placeholder(s) in the reply could not be restored (made by another sotto process, "
                        "or before a restart); they reach Claude Code as placeholders", path, restored["unresolved"])

    def _redact(self, body: dict) -> tuple[dict, Counter, int]:
        """The masked body, spans masked per type, and how many of them were in text this request
        brought (the rest are earlier turns, which Claude Code resends every time)."""
        with self._scan_lock:
            self.redactor.counts.clear()
            self.redactor.fresh = 0
            masked = self.redactor.redact_request(body)
            return masked, Counter(self.redactor.counts), self.redactor.fresh

    def _restore(self, data: dict, counts: Counter) -> dict:
        with self._scan_lock:
            return restore_response(data, self.redactor.vault, self.policy, counts)

    async def _stream(self, url, headers, payload, path, scan_ms, counts, new=0, outcome="forwarded", origin=None) -> Response:
        req = self.client.build_request("POST", url, headers=headers, content=payload)
        resp = await self.client.send(req, stream=True)
        restored = Counter()
        is_sse = resp.status_code < 300 and resp.headers.get("content-type", "").startswith("text/event-stream")
        # Observed requests went out unmasked: there is nothing to restore.
        restorer = StreamRestorer(self.redactor.vault, self.policy, restored) if is_sse and outcome != "observed" else None

        async def body():
            try:
                async for chunk in resp.aiter_raw():
                    out = restorer.feed(chunk) if restorer else chunk
                    if out:
                        yield out
                if restorer:
                    tail = restorer.close()
                    if tail:
                        yield tail
            finally:
                await resp.aclose()
                self._warn_unresolved(path, restored)
                self.stats.record(path, outcome, resp.status_code, scan_ms, counts, restored, new=new, origin=origin)
                log.info("%s -> %d (stream) redacted=%s restored=%s scan=%.0fms", path, resp.status_code,
                         dict(counts), dict(restored), scan_ms)

        return StreamingResponse(body(), status_code=resp.status_code, headers=self._response_headers(resp))

    # --- Plumbing -------------------------------------------------------------------

    async def _forward_raw(self, request: Request, path: str, body: bytes = b"", outcome: str = "forwarded") -> Response:
        url = self.upstream + path + (f"?{request.url.query}" if request.url.query else "")
        try:
            resp = await self.client.request(request.method, url, headers=self._headers(request), content=body or None)
        except httpx.HTTPError as e:
            return api_error(502, "api_error", f"upstream request failed ({type(e).__name__})")
        self.stats.record(path, outcome, resp.status_code, origin=self._origin(request))
        log.info("%s %s -> %d (not scanned: no body)", request.method, path, resp.status_code)
        return Response(resp.content, status_code=resp.status_code, headers=self._response_headers(resp))

    @staticmethod
    def _headers(request: Request) -> list[tuple[str, str]]:
        # Auth headers (x-api-key, authorization) pass through unchanged and are never logged.
        headers = [(k, v) for k, v in request.headers.items() if k.lower() not in HOP_HEADERS]
        headers.append(("accept-encoding", "identity"))
        return headers

    @staticmethod
    def _response_headers(resp: httpx.Response) -> dict[str, str]:
        return {k: v for k, v in resp.headers.items() if k.lower() not in RESPONSE_DROP}
