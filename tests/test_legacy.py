"""Moving over from sotto, keepmum's earlier name: folders and client settings, once."""

import json
import tomllib

from keepmum import legacy

OLD_CODEX = """model = "gpt-5.5"
model_provider = "sotto"  # sotto protect

# >>> sotto protect: routes Codex through sotto; `sotto protect off` removes this block
[model_providers.sotto]
name = "sotto"
base_url = "http://127.0.0.1:7788/chatgpt/backend-api/codex"
wire_api = "responses"
requires_openai_auth = true
supports_websockets = false
http_headers = {"x-sotto-client" = "codex"}
# <<< sotto protect
"""


def home(tmp_path, monkeypatch):
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "CODEX_HOME", "PI_CODING_AGENT_DIR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_moves_sottos_folders_and_client_settings(tmp_path, monkeypatch):
    h = home(tmp_path, monkeypatch)
    old = h / ".config" / "sotto"
    old.mkdir(parents=True)
    (old / "salt").write_text("ab" * 32)
    (old / "sotto.log").write_text("log\n")
    (h / ".local" / "share" / "sotto" / "bin").mkdir(parents=True)
    (h / ".codex").mkdir()
    (h / ".codex" / "config.toml").write_text(OLD_CODEX)
    (h / ".pi" / "agent").mkdir(parents=True)
    (h / ".pi" / "agent" / "models.json").write_text(json.dumps(
        {"providers": {"anthropic": {"baseUrl": "http://127.0.0.1:7788", "headers": {"x-sotto-client": "pi"}}}}))
    (h / ".config" / "opencode").mkdir(parents=True)
    (h / ".config" / "opencode" / "opencode.json").write_text(json.dumps(
        {"provider": {"openai": {"options": {"baseURL": "http://127.0.0.1:7788/openai/v1",
                                             "headers": {"x-sotto-client": "opencode"}}}}}))

    moved = legacy.migrate()

    new = h / ".config" / "keepmum"
    assert len(moved) == 5 and not old.exists()
    assert (new / "salt").read_text() == "ab" * 32 and (new / "keepmum.log").exists()
    assert (h / ".local" / "share" / "keepmum" / "bin").is_dir()
    codex = tomllib.loads((h / ".codex" / "config.toml").read_text())
    assert codex["model"] == "gpt-5.5" and codex["model_provider"] == "keepmum" and "sotto" not in codex["model_providers"]
    assert codex["model_providers"]["keepmum"]["base_url"] == "http://127.0.0.1:7788/chatgpt/backend-api/codex"
    pi = json.loads((h / ".pi" / "agent" / "models.json").read_text())
    assert pi["providers"]["anthropic"]["headers"] == {"x-keepmum-client": "pi"}
    oc = json.loads((h / ".config" / "opencode" / "opencode.json").read_text())
    assert oc["provider"]["openai"]["options"]["headers"] == {"x-keepmum-client": "opencode"}
    assert legacy.migrate() == []  # once


def test_leaves_both_alone_when_keepmum_already_has_a_folder(tmp_path, monkeypatch):
    h = home(tmp_path, monkeypatch)
    (h / ".config" / "sotto").mkdir(parents=True)
    (h / ".config" / "keepmum").mkdir()
    assert legacy.migrate() == []
    assert (h / ".config" / "sotto").exists()
