"""`sotto protect`: route every Claude Code session through `sotto serve`.

Sets `env.ANTHROPIC_BASE_URL` in Claude Code's user settings file. Claude Code reads that file in
the terminal, VS Code, JetBrains and the desktop app, and a value there replaces the same
variable exported in the shell. A running session picks up the change when the file is saved;
removing it reaches only sessions started afterwards. Project settings can still override it,
which `bypass_risks` reports.

Only that one key is touched. The file is strict JSON, written atomically, with a backup of the
previous version next to it.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

KEY = "ANTHROPIC_BASE_URL"


class ProtectError(RuntimeError):
    pass


def settings_path() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "settings.json"


def sotto_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def is_sotto_url(value: str, port: int) -> bool:
    """Our own proxy: loopback on sotto's port, with no path."""
    try:
        u = urlsplit(value)
        return (u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost") and u.port == port
                and u.path in ("", "/"))
    except ValueError:
        return False


@dataclass
class Status:
    path: Path
    on: bool
    value: str | None  # what the user settings file sets ANTHROPIC_BASE_URL to, if anything

    def as_dict(self) -> dict:
        return {"settings": str(self.path), "on": self.on, "base_url": self.value}


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except ValueError as e:
        raise ProtectError(f"{path} is not valid JSON ({e}); fix it first") from e
    if not isinstance(data, dict) or not isinstance(data.get("env", {}), dict):
        raise ProtectError(f"{path} does not hold a settings object with an env object")
    return data


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".sotto-backup"))
    tmp = path.with_name(path.name + ".sotto-tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    if path.exists():
        os.chmod(tmp, path.stat().st_mode & 0o777)
    tmp.replace(path)


def status(port: int) -> Status:
    path = settings_path()
    value = _read(path).get("env", {}).get(KEY)
    return Status(path, isinstance(value, str) and is_sotto_url(value, port), value)


def enable(port: int) -> Status:
    path = settings_path()
    data = _read(path)
    env = data.setdefault("env", {})
    current = env.get(KEY)
    if current is not None and not (isinstance(current, str) and is_sotto_url(current, port)):
        raise ProtectError(f"{path} already sends Claude Code to {current}; set it as sotto's upstream "
                           "([server] upstream in ~/.config/sotto/config.toml) and remove it there first")
    if current != sotto_url(port):
        env[KEY] = sotto_url(port)
        _write(path, data)
    return status(port)


def disable(port: int) -> Status:
    path = settings_path()
    data = _read(path)
    env = data.get("env", {})
    current = env.get(KEY)
    if current is not None and isinstance(current, str) and is_sotto_url(current, port):
        del env[KEY]
        if not env:
            data.pop("env")
        _write(path, data)
    return status(port)
