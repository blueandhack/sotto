import json
import os
import sys
import tomllib

import pytest

from sotto import clients
from sotto.protect import ProtectError

PORT = 7788


@pytest.fixture
def homes(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(tmp_path / "pi"))
    (tmp_path / "codex").mkdir()
    (tmp_path / "pi").mkdir()
    # Whether codex or pi is on this machine's PATH must not matter: a tool counts as installed
    # here only through the config files each test writes.
    monkeypatch.setattr(clients.shutil, "which", lambda name: None)
    return tmp_path


def test_codex_on_off_keeps_the_rest_of_the_config(homes):
    cfg = homes / "codex" / "config.toml"
    original = 'model = "gpt-5"\napproval_policy = "never"\n\n[mcp_servers.docs]\ncommand = "docs-mcp"\n'
    cfg.write_text(original)
    st = clients.codex_enable(PORT)
    data = tomllib.loads(cfg.read_text())
    assert st["on"] and data["model_provider"] == "sotto" and data["model"] == "gpt-5"
    assert data["mcp_servers"]["docs"]["command"] == "docs-mcp"
    prov = data["model_providers"]["sotto"]
    assert prov["base_url"] == "http://127.0.0.1:7788/chatgpt/backend-api/codex"  # no auth.json: ChatGPT login
    assert prov["supports_websockets"] is False and prov["requires_openai_auth"] is True
    assert prov["http_headers"] == {"x-sotto-client": "codex"}
    clients.codex_enable(PORT)  # twice: still one block
    assert cfg.read_text().count("[model_providers.sotto]") == 1
    assert not clients.codex_disable(PORT)["on"]
    assert cfg.read_text() == original


def test_codex_api_key_login_goes_to_the_openai_route(homes):
    (homes / "codex" / "auth.json").write_text(json.dumps({"auth_mode": "apikey", "OPENAI_API_KEY": "x"}))
    clients.codex_enable(PORT)
    prov = tomllib.loads((homes / "codex" / "config.toml").read_text())["model_providers"]["sotto"]
    assert prov["base_url"] == "http://127.0.0.1:7788/openai/v1"


def test_codex_leaves_another_provider_alone(homes):
    cfg = homes / "codex" / "config.toml"
    cfg.write_text('model_provider = "azure"\n')
    with pytest.raises(ProtectError, match="already selects model_provider 'azure'"):
        clients.codex_enable(PORT)
    assert cfg.read_text() == 'model_provider = "azure"\n'
    assert clients.codex_status(PORT)["other"] == "azure"


def test_pi_on_off_and_the_users_own_proxy(homes):
    models = homes / "pi" / "models.json"
    original = {"providers": {"openai": {"baseUrl": "https://my-gateway.corp.internal/v1"},
                              "ollama": {"baseUrl": "http://localhost:11434/v1", "api": "openai-completions"}}}
    models.write_text(json.dumps(original))
    st = clients.pi_enable(PORT)
    data = json.loads(models.read_text())["providers"]
    assert st["providers"] == ["anthropic", "openai-codex"] and st["other"] == ["openai"]
    assert data["anthropic"] == {"baseUrl": "http://127.0.0.1:7788", "headers": {"x-sotto-client": "pi"}}
    assert data["openai"] == original["providers"]["openai"]  # someone else's proxy: untouched
    clients.pi_disable(PORT)
    assert json.loads(models.read_text()) == original


def test_protect_reports_each_client(homes, monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    (homes / "codex" / "config.toml").write_text("not = [valid")
    (homes / "pi" / "models.json").write_text("{}")
    out = clients.protect_clients("on", PORT)
    assert out["claude"]["on"] and out["pi"]["on"]
    assert "not valid TOML" in out["codex"]["error"]  # one broken config never stops the others


def test_sotto_codex_runs_codex_through_the_proxy(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from sotto import launch
    from sotto.cli import app

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setattr(launch, "shared_serve_port", lambda cfg, need="messages": 7788)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "codex"
    fake.write_text(f"#!{sys.executable}\nimport json, os, sys\nopen(os.environ['OUT'], 'w').write(json.dumps(sys.argv[1:]))\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("OUT", str(tmp_path / "out"))
    r = CliRunner().invoke(app, ["codex", "exec", "hi"])
    args = json.loads((tmp_path / "out").read_text())
    assert r.exit_code == 0 and args[-2:] == ["exec", "hi"]
    assert 'model_provider="sotto"' in args and 'model_providers.sotto.supports_websockets=false' in args
    assert 'model_providers.sotto.base_url="http://127.0.0.1:7788/chatgpt/backend-api/codex"' in args


def test_a_tool_that_is_not_installed_is_skipped(homes):
    out = clients.protect_clients("on", PORT, ["codex", "pi"])
    assert out == {"codex": {"installed": False, "on": False}, "pi": {"installed": False, "on": False}}
    assert not (homes / "codex" / "config.toml").exists() and not (homes / "pi" / "models.json").exists()
