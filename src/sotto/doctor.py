"""`sotto doctor`: read-only checks. It creates nothing (no salt, no token, no files)."""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

OK, WARN, FAIL = "✓", "!", "✗"


def _check(results, status, text):
    results.append((status, text))


def run() -> int:
    from . import launch
    from .config import ConfigError, load

    r: list[tuple[str, str]] = []
    mac = platform.mac_ver()[0]
    major = int(mac.split(".")[0]) if mac else 0
    _check(r, OK if major >= 14 else FAIL, f"macOS {mac or 'unknown'} (14 or later)")
    _check(r, OK if platform.machine() == "arm64" else FAIL, f"CPU {platform.machine()} (Apple silicon required)")
    _check(r, OK if sys.version_info >= (3, 12) else FAIL, f"Python {platform.python_version()}")

    try:
        cfg = load()
        _check(r, OK, f"config {cfg.path or '(none: defaults)'}; pii={'on' if cfg.pii else 'off'}")
    except ConfigError as e:
        cfg = None
        _check(r, FAIL, f"config: {e}")

    from .detect.pfserve import PfServe, find_binary, find_model

    binary, model = find_binary(), find_model()
    _check(r, OK if binary else FAIL, f"pf-serve {binary}" if binary else "pf-serve missing: run native/pf-serve/build.sh")
    _check(r, OK if model else FAIL, f"model {model}" if model else "model missing: run `sotto setup`")
    if binary and model:
        pf = None
        try:
            pf = PfServe(binary, model)
            # Synthetic canary in a prose sentence, where only the model (not a rule) can catch it.
            canary = "Zq8vX2mN4pL7kR9t"
            text = f"the vpn password for the lab is {canary}, don't share it"
            found = any(text[s.start : s.end] == canary for s in pf.detect(text))
            _check(r, OK if found else FAIL, f"model runs on {pf.device} and catches a canary" if found
                   else "model loaded but missed the canary")
        except Exception as e:
            _check(r, FAIL, f"model did not run ({e})")
        finally:
            if pf:
                pf.close()

    try:
        import keyring

        from .vault import KEYCHAIN_ACCOUNT, KEYCHAIN_SERVICE, SALT_FILE, _keychain_usable

        if _keychain_usable() and keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT):
            _check(r, OK, "install salt in the Keychain")
        elif SALT_FILE.exists():
            mode = SALT_FILE.stat().st_mode & 0o777
            _check(r, OK if mode == 0o600 else FAIL, f"install salt in {SALT_FILE} (mode {mode:o})")
        else:
            _check(r, OK, "install salt not created yet (created on first run)")
    except Exception as e:
        _check(r, WARN, f"Keychain not readable ({type(e).__name__}); sotto falls back to a 0600 file")

    for f in (Path.home() / ".config" / "sotto" / "stats-token", launch.LOG_FILE, launch.RUNTIME_FILE):
        if f.exists() and f.stat().st_mode & 0o077:
            _check(r, FAIL, f"{f} is readable by other users (mode {f.stat().st_mode & 0o777:o})")

    claude = shutil.which("claude")
    if claude:
        version = subprocess.run([claude, "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
        _check(r, OK, f"Claude Code {version or 'found'}")
    else:
        _check(r, FAIL, "`claude` not on PATH")

    risks = launch.bypass_risks(Path.cwd())
    _check(r, FAIL if risks else OK, "routes around sotto: " + "; ".join(risks) if risks else "nothing routes Claude Code around sotto")
    if os.environ.get("ANTHROPIC_BASE_URL"):
        _check(r, WARN, "ANTHROPIC_BASE_URL is set: `sotto claude` will use it as its upstream")

    port = cfg.port if cfg else 7788
    with socket.socket() as s:
        free = s.connect_ex(("127.0.0.1", port)) != 0
    try:
        running = json.loads(launch.RUNTIME_FILE.read_text())
    except (OSError, ValueError):
        running = None
    if running:
        _check(r, OK, f"sotto running (pid {running.get('pid')}, port {running.get('port')})")
    _check(r, OK if free else WARN, f"port {port} {'free' if free else 'in use'} for `sotto serve`")

    for status, text in r:
        print(f"  {status} {text}")
    failed = sum(1 for s, _ in r if s == FAIL)
    print("all checks passed" if not failed else f"{failed} check(s) failed")
    return 1 if failed else 0
