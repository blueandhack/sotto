import json
import os
import stat
import subprocess
import sys

import pytest

from sotto import config as config_mod
from sotto import launch, protect
from sotto.protect import ProtectError


@pytest.fixture
def claude_dir(tmp_path, monkeypatch):
    d = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(d))
    for k in launch.BYPASS_KEYS:
        monkeypatch.delenv(k, raising=False)
    return d


def settings(d):
    return json.loads((d / "settings.json").read_text())


def test_on_creates_the_setting_and_off_removes_it(claude_dir):
    st = protect.enable(7788)
    assert st.on and settings(claude_dir) == {"env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:7788"}}
    assert protect.enable(7788).on  # again: nothing changes
    st = protect.disable(7788)
    assert not st.on and settings(claude_dir) == {}


def test_other_keys_are_kept_and_a_backup_is_made(claude_dir):
    claude_dir.mkdir()
    original = {"model": "opus", "env": {"API_TIMEOUT_MS": "60000"}, "permissions": {"allow": ["Bash(ls)"]}}
    (claude_dir / "settings.json").write_text(json.dumps(original))
    os.chmod(claude_dir / "settings.json", 0o600)
    protect.enable(7788)
    s = settings(claude_dir)
    assert s["model"] == "opus" and s["permissions"] == original["permissions"]
    assert s["env"] == {"API_TIMEOUT_MS": "60000", "ANTHROPIC_BASE_URL": "http://127.0.0.1:7788"}
    assert json.loads((claude_dir / "settings.json.sotto-backup").read_text()) == original
    assert stat.S_IMODE((claude_dir / "settings.json").stat().st_mode) == 0o600
    protect.disable(7788)
    assert settings(claude_dir) == original


def test_another_gateway_is_not_replaced(claude_dir):
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(json.dumps({"env": {"ANTHROPIC_BASE_URL": "https://gateway.corp.internal"}}))
    with pytest.raises(ProtectError, match="already sends Claude Code to https://gateway.corp.internal"):
        protect.enable(7788)
    assert not protect.disable(7788).on  # off leaves someone else's value alone
    assert settings(claude_dir)["env"]["ANTHROPIC_BASE_URL"] == "https://gateway.corp.internal"


def test_a_broken_file_is_never_rewritten(claude_dir):
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text('{"model": "opus",}')
    with pytest.raises(ProtectError, match="not valid JSON"):
        protect.enable(7788)
    assert (claude_dir / "settings.json").read_text() == '{"model": "opus",}'


@pytest.mark.parametrize("value, ours", [
    ("http://127.0.0.1:7788", True), ("http://localhost:7788/", True),
    ("http://127.0.0.1:7789", False), ("https://127.0.0.1:7788", False),
    ("http://127.0.0.1:7788/v1", False), ("http://evil.example:7788", False), ("not a url", False),
])
def test_is_sotto_url(value, ours):
    assert protect.is_sotto_url(value, 7788) == ours


def test_our_own_url_is_not_a_bypass(claude_dir, tmp_path):
    protect.enable(7788)
    project = tmp_path / "proj"
    project.mkdir()
    assert launch.bypass_risks(project, 7788) == []
    assert any("ANTHROPIC_BASE_URL" in r for r in launch.bypass_risks(project, 9999))  # another port is
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.json").write_text(json.dumps({"env": {"ANTHROPIC_BASE_URL": "https://elsewhere"}}))
    assert any("proj/.claude/settings.json" in r for r in launch.bypass_risks(project, 7788))


def test_upstream_pointing_at_ourselves_is_dropped(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "RUNTIME_FILE", tmp_path / "runtime.json")
    cfg = config_mod.load(tmp_path / "none.toml")
    proxy = launch.build_proxy(cfg, rules_only=True, upstream=f"http://127.0.0.1:{cfg.port}")
    assert proxy.upstream == cfg.upstream


def test_sotto_claude_refuses_when_protected_and_the_service_is_down(claude_dir, tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from sotto.cli import app

    monkeypatch.setenv("HOME", str(tmp_path))
    protect.enable(7788)
    monkeypatch.setattr(launch, "shared_serve_port", lambda cfg: None)
    r = CliRunner().invoke(app, ["claude", "-p", "hi"])
    assert r.exit_code == 2 and "not running" in r.output


def test_sotto_claude_uses_the_service_when_protected(claude_dir, tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from sotto.cli import app

    monkeypatch.setenv("HOME", str(tmp_path))
    protect.enable(7788)
    monkeypatch.setattr(launch, "shared_serve_port", lambda cfg: 7788)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(f"#!{sys.executable}\nimport os, sys\nopen(os.environ['OUT'], 'w').write(os.environ['ANTHROPIC_BASE_URL'] + ' ' + ' '.join(sys.argv[1:]))\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("OUT", str(tmp_path / "out"))
    r = CliRunner().invoke(app, ["claude", "-p", "hi"])
    assert r.exit_code == 0 and (tmp_path / "out").read_text() == "http://127.0.0.1:7788 -p hi"


def test_wrapper_refuses_when_protected_and_the_service_is_down(tmp_path):
    home = tmp_path / "home"
    (home / ".config" / "sotto").mkdir(parents=True)
    (home / ".config" / "sotto" / "config.toml").write_text("[server]\nport = 1\n")  # nothing listens on port 1
    (home / ".claude").mkdir()
    (home / ".claude" / "settings.json").write_text(json.dumps({"env": {"ANTHROPIC_BASE_URL": "http://127.0.0.1:1"}}))
    env = {k: v for k, v in os.environ.items() if k not in launch.BYPASS_KEYS and k != "CLAUDE_CONFIG_DIR"}
    env["HOME"] = str(home)
    wrapper = os.path.join(os.path.dirname(sys.executable), "sotto-claude-wrapper")
    r = subprocess.run([wrapper, sys.executable, "-c", "print('started')"], env=env, cwd=home,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "protection is on" in r.stderr and r.stdout == ""
