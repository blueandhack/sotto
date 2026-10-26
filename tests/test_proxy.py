import json
import logging
import secrets

import anyio
import httpx
import pytest

from sotto import selftest
from sotto.detect.pipeline import Pipeline
from sotto.detect.rules import RulesDetector
from sotto.proxy import Proxy
from sotto.redact import Redactor
from sotto.vault import Vault

API_KEY = "sk-ant-test-not-a-real-key"


def rules_pipeline():
    return Pipeline(RulesDetector(), None)


def test_selftest_canary_never_reaches_upstream():
    assert anyio.run(selftest.run, rules_pipeline(), False)


def make(upstream_app=None, transport=None):
    mock = selftest.MockUpstream()
    upstream = httpx.AsyncClient(transport=transport or httpx.ASGITransport(app=upstream_app or mock.app), base_url="http://up")
    proxy = Proxy(Redactor(rules_pipeline(), Vault(secrets.token_bytes(32))), upstream="http://up", client=upstream, stats_token="t")
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=proxy.app), base_url="http://127.0.0.1:7788")
    return mock, client


def body_with(canary):
    return {"model": "m", "max_tokens": 8, "messages": [{"role": "user", "content": f"export GITHUB_TOKEN={canary}"}]}


def test_logs_never_hold_values_or_auth(caplog):
    canary = selftest.make_canary()

    async def go():
        mock, client = make()
        await client.post("/v1/messages", json=body_with(canary), headers={"x-api-key": API_KEY})
        await client.post("/v1/files", content=canary.encode(), headers={"x-api-key": API_KEY})

    with caplog.at_level(logging.DEBUG):
        anyio.run(go)
    text = caplog.text
    assert "redacted" in text  # the request was logged...
    assert canary not in text and API_KEY not in text and "SOTTO_" not in text  # ...without values


def test_upstream_down_is_a_502_not_a_raw_send():
    def refuse(request):
        raise httpx.ConnectError("down")

    async def go():
        _, client = make(transport=httpx.MockTransport(refuse))
        return await client.post("/v1/messages", json=body_with(selftest.make_canary()))

    r = anyio.run(go)
    assert r.status_code == 502 and r.json()["type"] == "error"


def test_upstream_errors_pass_through():
    def overloaded(request):
        return httpx.Response(529, json={"type": "error", "error": {"type": "overloaded_error", "message": "busy"}})

    async def go():
        _, client = make(transport=httpx.MockTransport(overloaded))
        return await client.post("/v1/messages", json=body_with("x"))

    r = anyio.run(go)
    assert r.status_code == 529 and r.json()["error"]["type"] == "overloaded_error"


def test_bodyless_get_is_forwarded():
    async def go():
        mock, client = make()
        r = await client.get("/v1/models")
        return r, mock

    r, mock = anyio.run(go)
    assert r.status_code == 200 and mock.received and mock.received[0].startswith(b"/v1/models")


@pytest.mark.parametrize("host, ok", [("127.0.0.1:7788", True), ("localhost:7788", True), ("[::1]:7788", True),
                                      ("localhost.attacker.example", False), ("192.168.1.5:7788", False)])
def test_host_header(host, ok):
    async def go():
        _, client = make()
        return await client.get("/_sotto/health", headers={"host": host})

    assert (anyio.run(go).status_code == 200) is ok


def test_query_string_is_kept():
    async def go():
        mock, client = make()
        await client.post("/v1/messages?beta=true", json=body_with("x"))
        return mock

    assert anyio.run(go).received[0].startswith(b"/v1/messages?beta=true")


def test_unicode_survives_the_round_trip():
    async def go():
        _, client = make()
        r = await client.post("/v1/messages", json={"model": "m", "messages": [{"role": "user", "content": "héllo 漢字 🙂"}]})
        return r

    r = anyio.run(go)
    assert r.status_code == 200 and json.loads(r.content)["content"][0]["text"].startswith("The token")
