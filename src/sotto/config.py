"""~/.config/sotto/config.toml. Every key is optional; unknown keys and bad values are errors.

    [server]
    port = 7788
    upstream = "https://api.anthropic.com"

    [detect]
    pii = false            # also mask personal data

    [allowlist]            # added to the built-in allowlist, never replacing it
    strings = []
    patterns = []

    [restore]              # per tool: "restore" or "keep"; "mcp__*" style prefixes allowed
    default = "restore"
    WebFetch = "keep"

    [log]
    level = "info"
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .restore import DEFAULT_POLICY

CONFIG_FILE = Path.home() / ".config" / "sotto" / "config.toml"

_SCHEMA = {
    "server": {"port": int, "upstream": str},
    "detect": {"pii": bool},
    "allowlist": {"strings": list, "patterns": list},
    "log": {"level": str},
}
LOG_LEVELS = ("debug", "info", "warning", "error")


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    port: int = 7788
    upstream: str = "https://api.anthropic.com"
    pii: bool = False
    allow_strings: list[str] = field(default_factory=list)
    allow_patterns: list[str] = field(default_factory=list)
    restore: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_POLICY))
    log_level: str = "info"
    path: Path | None = None


def load(path: Path = CONFIG_FILE) -> Config:
    cfg = Config(path=path if path.exists() else None)
    if not path.exists():
        return cfg
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e
    for section, values in raw.items():
        if section == "restore":
            continue
        if section not in _SCHEMA or not isinstance(values, dict):
            raise ConfigError(f"{path}: unknown section [{section}]")
        for key, value in values.items():
            want = _SCHEMA[section].get(key)
            if want is None:
                raise ConfigError(f"{path}: unknown key {section}.{key}")
            if not isinstance(value, want) or (want is int and isinstance(value, bool)):
                raise ConfigError(f"{path}: {section}.{key} must be {want.__name__}")
    server, detect, allow, log = (raw.get(k, {}) for k in ("server", "detect", "allowlist", "log"))
    cfg.port = server.get("port", cfg.port)
    if not 1 <= cfg.port <= 65535:
        raise ConfigError(f"{path}: server.port must be 1-65535")
    cfg.upstream = server.get("upstream", cfg.upstream)
    if not re.match(r"https?://", cfg.upstream):
        raise ConfigError(f"{path}: server.upstream must be an http(s) URL")
    cfg.pii = detect.get("pii", cfg.pii)
    cfg.allow_strings = [str(s) for s in allow.get("strings", [])]
    cfg.allow_patterns = [str(p) for p in allow.get("patterns", [])]
    for p in cfg.allow_patterns:
        try:
            re.compile(p)
        except re.error as e:
            raise ConfigError(f"{path}: allowlist pattern {p!r}: {e}") from e
    restore = raw.get("restore", {})
    if not isinstance(restore, dict):
        raise ConfigError(f"{path}: [restore] must be a table")
    for tool, action in restore.items():
        if action not in ("restore", "keep"):
            raise ConfigError(f"{path}: restore.{tool} must be \"restore\" or \"keep\"")
    cfg.restore = {**DEFAULT_POLICY, **restore}
    cfg.log_level = log.get("level", cfg.log_level)
    if cfg.log_level not in LOG_LEVELS:
        raise ConfigError(f"{path}: log.level must be one of {', '.join(LOG_LEVELS)}")
    return cfg
