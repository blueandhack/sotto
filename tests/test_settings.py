"""What gets masked: types passed through, your own rules, your exceptions, applied while running."""

import json
import secrets
import textwrap

import anyio
import httpx
import pytest

from sotto import config as config_mod
from sotto import selftest
from sotto.detect import Span
from sotto.detect.pipeline import Pipeline
from sotto.detect.rules import RulesDetector
from sotto.redact import Redactor
from sotto.vault import Vault


class FakeModel:
    """Finds a fixed name as PERSON, like the model would."""
    name = "pf"

    def detect(self, text):
        i = text.find("Priya Raman")
        return [Span(i, i + 11, "PERSON", 0.9, "pf")] if i >= 0 else []


def values(text, spans):
    return [text[s.start:s.end] for s in spans]


def test_passed_types_are_counted_but_not_masked():
    p = Pipeline(RulesDetector(), FakeModel(), pii=True)
    p.apply_settings(pass_types=["PERSON"])
    token = "ghp_" + "Zq8vX2mN4pL7kR9tY3wB6cF1hJ5dG0sAe7Qw"
    text = f"Priya Raman set GITHUB_TOKEN={token}"
    assert values(text, p.detect(text)) == [token]
    report = p.report()
    assert report["types"]["PERSON"] == {"found": 1, "allowed": 0, "passed": 1, "masked": 0}
    assert report["types"]["SECRET"]["masked"] == 1 and report["pass"] == ["PERSON"]


def test_known_values_of_a_passed_type_are_not_masked_again():
    p = Pipeline(RulesDetector(), FakeModel(), pii=True)
    r = Redactor(p, Vault(secrets.token_bytes(32)))
    assert "Priya" not in r.redact_text("ask Priya Raman")
    p.apply_settings(pass_types=["PERSON"])
    assert r.redact_text("Priya Raman again, and ask Priya Raman") == "Priya Raman again, and ask Priya Raman"


def test_user_rules_mask_even_with_personal_data_off_and_exceptions_win():
    p = Pipeline(RulesDetector(), None, pii=False)
    p.apply_settings(mask_rules=[{"name": "Employee ID", "pattern": r"EMP-(\d{6})", "type": "ACCOUNT"}],
                     allow_strings=["424242"])
    text = "EMP-123456 and EMP-424242"
    spans = p.detect(text)
    assert values(text, spans) == ["123456"] and spans[0].source == "user:Employee ID"
    assert p.report()["rules"] == [{"rule": "Employee ID", "user": True, "n": 1}]
    assert p.report()["types"]["ACCOUNT"]["masked"] == 1  # the exception is dropped before counting


def test_settings_change_while_running(tmp_path):
    from sotto import launch

    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("[detect]\npii = true\n")
    cfg = config_mod.load(cfg_path)
    proxy = launch.build_proxy(cfg, rules_only=True, upstream="http://up")
    mock = selftest.MockUpstream()
    proxy.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=mock.app), base_url="http://up")
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=proxy.app), base_url="http://127.0.0.1:7788")
    body = {"model": "m", "max_tokens": 8, "messages": [{"role": "user", "content": "badge EMP-123456"}]}

    async def send():
        await client.post("/v1/messages", json=body)

    anyio.run(send)
    assert b"EMP-123456" in mock.received[-1]
    config_mod.set_value("rules", "mask", [{"name": "Employee ID", "pattern": r"EMP-\d{6}", "type": "ACCOUNT"}], cfg_path)
    anyio.run(send)  # same text again: the redactor's cache must not hide the new rule
    assert b"EMP-123456" not in mock.received[-1]


def test_set_value_keeps_the_rest_and_rejects_bad_values(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(textwrap.dedent("""\
        # my settings
        [server]
        port = 9000

        [detect]
        pii = true
        pass = [
          "DATE",
        ]
    """))
    config_mod.set_value("detect", "pass", ["PERSON", "DATE"], path)
    config_mod.set_value("rules", "mask", [{"name": "q", "pattern": 'a"b\\d', "type": "SECRET"}], path)
    cfg = config_mod.load(path)
    assert cfg.port == 9000 and cfg.pii and cfg.pass_types == ["PERSON", "DATE"]
    assert cfg.mask_rules == [{"name": "q", "pattern": 'a"b\\d', "type": "SECRET"}]
    assert path.read_text().startswith("# my settings")
    before = path.read_text()
    with pytest.raises(config_mod.ConfigError):
        config_mod.set_value("detect", "pass", ["NOPE"], path)
    assert path.read_text() == before


def test_cli_types_needs_yes_for_secrets(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from sotto.cli import app

    monkeypatch.setenv("HOME", str(tmp_path))
    run = lambda *a: CliRunner().invoke(app, list(a))
    assert run("types", "pass", "SECRET").exit_code == 2
    assert run("types", "pass", "person").exit_code == 0
    assert config_mod.load(tmp_path / ".config" / "sotto" / "config.toml").pass_types == ["PERSON"]
    assert run("rules", "mask", "EMP-\\d{6}", "--name", "Employee ID", "--type", "account").exit_code == 0
    assert run("rules", "allow", "acme-test-key").exit_code == 0
    data = json.loads(run("rules", "list", "--json").stdout)
    assert data["mask"][0]["type"] == "ACCOUNT" and data["allow_strings"] == ["acme-test-key"]
    assert run("rules", "remove", "mask", "0").exit_code == 0
    assert config_mod.load(tmp_path / ".config" / "sotto" / "config.toml").mask_rules == []
