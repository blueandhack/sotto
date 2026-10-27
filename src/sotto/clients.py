"""Point Codex and pi at sotto (`sotto protect`), and run Codex through it once (`sotto codex`).

Verified Oct 27, 2026 against Codex 0.147 and pi 0.84:

- Codex cannot override its built-in `openai` provider, so sotto adds a `sotto` provider in
  ~/.codex/config.toml (CODEX_HOME respected) and selects it with a top-level
  `model_provider`. `requires_openai_auth` keeps the user's ChatGPT or API-key login;
  `supports_websockets = false` skips the WebSocket transport sotto cannot scan, so Codex goes
  straight to HTTPS. A ChatGPT login is served by chatgpt.com/backend-api/codex, an API key
  by api.openai.com/v1.
- pi overrides a built-in provider's base URL in ~/.pi/agent/models.json
  (PI_CODING_AGENT_DIR respected). sotto sets it for anthropic, openai and openai-codex.

Both get an `x-sotto-client` header, so the dashboard can tell clients apart; the proxy drops
it before forwarding. Only what sotto added is ever removed, and a different base URL the user
already set is left alone and reported.
"""

from __future__ import annotations

import json
import os
import shutil
import tomllib
from pathlib import Path

from .protect import ProtectError, _read, _write, sotto_url

CODEX_MARK = "# sotto protect"
CODEX_BEGIN = "# >>> sotto protect: routes Codex through sotto; `sotto protect off` removes this block"
CODEX_END = "# <<< sotto protect"


# --- Codex --------------------------------------------------------------------------

def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def codex_auth_mode() -> str:
    """"chatgpt" or "apikey", from Codex's own auth file (default: chatgpt)."""
    try:
        data = json.loads((codex_home() / "auth.json").read_text())
    except (OSError, ValueError):
        return "chatgpt"
    mode = str(data.get("auth_mode") or "").lower()
    return "apikey" if mode in ("apikey", "api_key") or (not data.get("tokens") and data.get("OPENAI_API_KEY")) else "chatgpt"


def codex_base_url(port: int) -> str:
    base = sotto_url(port)
    return f"{base}/openai/v1" if codex_auth_mode() == "apikey" else f"{base}/chatgpt/backend-api/codex"


def codex_provider(port: int) -> dict:
    return {"name": "sotto", "base_url": codex_base_url(port), "wire_api": "responses",
            "requires_openai_auth": True, "supports_websockets": False,
            "http_headers": {"x-sotto-client": "codex"}}


def codex_args(port: int) -> list[str]:
    """`-c` overrides that send one Codex run through sotto, leaving its config file alone."""
    out = ["-c", 'model_provider="sotto"']
    for key, value in codex_provider(port).items():
        out += ["-c", f"model_providers.sotto.{key}={_toml(value)}"]
    return out


def _toml(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{json.dumps(k)} = {_toml(v)}" for k, v in value.items()) + "}"
    return json.dumps(value)


def _codex_config() -> Path:
    return codex_home() / "config.toml"


def _strip_codex(text: str) -> str:
    out, skipping = [], False
    for line in text.splitlines():
        if line.strip() == CODEX_BEGIN:
            skipping = True
            continue
        if skipping:
            if line.strip() == CODEX_END:
                skipping = False
            continue
        if line.rstrip().endswith(CODEX_MARK) and line.lstrip().startswith("model_provider"):
            continue
        out.append(line)
    return "\n".join(out).rstrip("\n") + "\n" if out else ""


def codex_status(port: int) -> dict:
    path = _codex_config()
    if not path.exists() and not shutil.which("codex"):
        return {"installed": False, "on": False}
    try:
        cfg = tomllib.loads(path.read_text()) if path.exists() else {}
    except tomllib.TOMLDecodeError as e:
        return {"installed": True, "on": False, "error": f"{path} is not valid TOML ({e})"}
    provider = (cfg.get("model_providers") or {}).get("sotto") or {}
    on = cfg.get("model_provider") == "sotto" and provider.get("base_url") == codex_base_url(port)
    other = cfg.get("model_provider") not in (None, "sotto") and cfg.get("model_provider")
    return {"installed": True, "on": on, "config": str(path), **({"other": other} if other else {})}


def codex_enable(port: int) -> dict:
    path = _codex_config()
    text = path.read_text() if path.exists() else ""
    try:
        current = tomllib.loads(text).get("model_provider")
    except tomllib.TOMLDecodeError as e:
        raise ProtectError(f"{path} is not valid TOML ({e}); fix it first") from e
    if current not in (None, "sotto") and CODEX_MARK not in text:
        raise ProtectError(f"{path} already selects model_provider {current!r}; sotto leaves it alone")
    base = _strip_codex(text)
    block = [CODEX_BEGIN, "[model_providers.sotto]"]
    block += [f"{k} = {_toml(v)}" for k, v in codex_provider(port).items()]
    block.append(CODEX_END)
    new = f'model_provider = "sotto"  {CODEX_MARK}\n' + base + ("\n" if base else "") + "\n".join(block) + "\n"
    tomllib.loads(new)  # never write a file Codex cannot read
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_text(path, new)
    return codex_status(port)


def codex_disable(port: int) -> dict:
    path = _codex_config()
    if path.exists():
        text = path.read_text()
        new = _strip_codex(text)
        if new != text:
            tomllib.loads(new)
            _write_text(path, new)
    return codex_status(port)


def _write_text(path: Path, text: str) -> None:
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".sotto-backup"))
    tmp = path.with_name(path.name + ".sotto-tmp")
    tmp.write_text(text)
    if path.exists():
        os.chmod(tmp, path.stat().st_mode & 0o777)
    tmp.replace(path)


# --- pi -----------------------------------------------------------------------------

def pi_dir() -> Path:
    return Path(os.environ.get("PI_CODING_AGENT_DIR") or Path.home() / ".pi" / "agent")


def pi_providers(port: int) -> dict[str, str]:
    base = sotto_url(port)
    return {"anthropic": base, "openai": f"{base}/openai/v1", "openai-codex": f"{base}/chatgpt/backend-api"}


def pi_status(port: int) -> dict:
    path = pi_dir() / "models.json"
    if not path.exists() and not shutil.which("pi"):
        return {"installed": False, "on": False}
    try:
        providers = _read(path).get("providers") or {}
    except ProtectError as e:
        return {"installed": True, "on": False, "error": str(e)}
    ours = {p for p, url in pi_providers(port).items() if (providers.get(p) or {}).get("baseUrl") == url}
    others = sorted(p for p in pi_providers(port) if p not in ours and (providers.get(p) or {}).get("baseUrl"))
    return {"installed": True, "on": bool(ours), "providers": sorted(ours), "config": str(path),
            **({"other": others} if others else {})}


def pi_enable(port: int) -> dict:
    path = pi_dir() / "models.json"
    data = _read(path)
    providers = data.setdefault("providers", {})
    if not isinstance(providers, dict):
        raise ProtectError(f"{path}: providers is not an object")
    for name, url in pi_providers(port).items():
        entry = providers.setdefault(name, {})
        if entry.get("baseUrl") not in (None, url):
            continue  # the user's own proxy for this provider: left alone, reported by status
        entry["baseUrl"] = url
        entry.setdefault("headers", {})["x-sotto-client"] = "pi"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, data)
    return pi_status(port)


def pi_disable(port: int) -> dict:
    path = pi_dir() / "models.json"
    if not path.exists():
        return pi_status(port)
    data = _read(path)
    providers = data.get("providers") or {}
    changed = False
    for name, url in pi_providers(port).items():
        entry = providers.get(name)
        if not isinstance(entry, dict) or entry.get("baseUrl") != url:
            continue
        entry.pop("baseUrl")
        headers = entry.get("headers") or {}
        headers.pop("x-sotto-client", None)
        if not headers:
            entry.pop("headers", None)
        if not entry:
            providers.pop(name)
        changed = True
    if changed:
        if not providers:
            data.pop("providers", None)
        _write(path, data)
    return pi_status(port)


# --- All clients ----------------------------------------------------------------------

CLIENTS = ("claude", "codex", "pi")


def protect_clients(action: str, port: int, only: list[str] | None = None) -> dict[str, dict]:
    """Run on, off or status for each client; one failing never stops the others."""
    from . import protect

    def claude(fn):
        st = fn(port)
        return {"installed": True, **st.as_dict()}

    table = {
        "claude": {"on": lambda: claude(protect.enable), "off": lambda: claude(protect.disable), "status": lambda: claude(protect.status)},
        "codex": {"on": lambda: codex_enable(port), "off": lambda: codex_disable(port), "status": lambda: codex_status(port)},
        "pi": {"on": lambda: pi_enable(port), "off": lambda: pi_disable(port), "status": lambda: pi_status(port)},
    }
    out = {}
    for name in only or CLIENTS:
        try:
            installed = name == "claude" or table[name]["status"]().get("installed")
            out[name] = table[name][action]() if installed or action == "status" else {"installed": False, "on": False}
        except ProtectError as e:
            out[name] = {"installed": True, "on": False, "error": str(e)}
    return out
