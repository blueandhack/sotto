"""Moving over from sotto, keepmum's earlier name, once.

The first keepmum command on a Mac that ran sotto moves ~/.config/sotto (the salt, settings,
history, exclusions) and sotto's data folder (pf-serve and the model) to keepmum's, and
rewrites what `sotto protect` wrote into the Codex, pi and opencode configs so it names keepmum.
Claude Code's setting holds only the proxy's address, which did not change. Once
~/.config/sotto is gone, or keepmum's folder exists, this does nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

OLD = "sotto"
OLD_HEADER = "x-sotto-client"
OLD_CODEX_BEGIN = "# >>> sotto protect: routes Codex through sotto; `sotto protect off` removes this block"
OLD_CODEX_END = "# <<< sotto protect"
OLD_CODEX_MARK = "# sotto protect"


def migrate() -> list[str]:
    """Move sotto's folders and client settings to keepmum's; what was moved, for the log."""
    old = Path.home() / ".config" / OLD
    new = Path.home() / ".config" / "keepmum"
    if not old.is_dir() or new.exists():
        return []
    new.parent.mkdir(parents=True, exist_ok=True)
    old.rename(new)
    if (new / "sotto.log").exists():
        (new / "sotto.log").rename(new / "keepmum.log")
    moved = [f"{old} -> {new}"]

    from .detect.pfserve import data_dir

    old_data = data_dir().with_name(OLD)
    if old_data.is_dir() and not data_dir().exists():
        old_data.rename(data_dir())
        moved.append(f"{old_data} -> {data_dir()}")
    for name, fn in (("Codex", _codex), ("pi", _pi), ("opencode", _opencode)):
        try:
            if fn():
                moved.append(f"{name} settings now name keepmum")
        except (OSError, ValueError):
            pass  # left as it was; `keepmum protect` reports it
    return moved


def _codex() -> bool:
    from . import clients

    path = clients.codex_home() / "config.toml"
    if not path.exists() or OLD_CODEX_BEGIN not in (text := path.read_text()):
        return False
    out, skipping = [], False
    port = None
    for line in text.splitlines():
        if line.strip() == OLD_CODEX_BEGIN:
            skipping = True
        elif skipping:
            skipping = line.strip() != OLD_CODEX_END
            if line.startswith("base_url"):
                port = _port(json.loads(line.split("=", 1)[1].strip()))
        elif not (line.rstrip().endswith(OLD_CODEX_MARK) and line.lstrip().startswith("model_provider")):
            out.append(line)
    clients._write_text(path, "\n".join(out).rstrip("\n") + "\n" if out else "")
    if port:
        clients.codex_enable(port)
    return True


def _port(url: str) -> int | None:
    from urllib.parse import urlsplit

    return urlsplit(url).port


def _rename_header(path: Path, entries) -> bool:
    from .protect import _write

    if not path.exists():
        return False
    data = json.loads(path.read_text())
    changed = False
    for headers in entries(data):
        if isinstance(headers, dict) and OLD_HEADER in headers:
            headers["x-keepmum-client"] = headers.pop(OLD_HEADER)
            changed = True
    if changed:
        _write(path, data)
    return changed


def _pi() -> bool:
    from .clients import pi_dir

    return _rename_header(pi_dir() / "models.json", lambda d: [
        p.get("headers") for p in (d.get("providers") or {}).values() if isinstance(p, dict)])


def _opencode() -> bool:
    from .clients import opencode_dir

    return _rename_header(opencode_dir() / "opencode.json", lambda d: [
        (p.get("options") or {}).get("headers") for p in (d.get("provider") or {}).values() if isinstance(p, dict)])


def migrate_quietly() -> None:
    """migrate(), saying on stderr what moved; never stops the command that runs it."""
    import sys

    try:
        moved = migrate()
    except OSError as e:
        print(f"keepmum: could not move sotto's settings: {e}", file=sys.stderr)
        return
    for line in moved:
        print(f"keepmum: moved from sotto: {line}", file=sys.stderr)
