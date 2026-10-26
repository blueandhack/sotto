"""sotto command line."""

from __future__ import annotations

import bisect
from pathlib import Path

import typer

app = typer.Typer(help="Local secret and PII redaction for Claude Code.", no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    pass


@app.command()
def scan(
    paths: list[str] = typer.Argument(..., help="Files to scan, or - for stdin."),
    pii: bool = typer.Option(False, help="Also report personal data."),
    rules_only: bool = typer.Option(False, help="L1 rules only: fast, no model, lower recall."),
) -> None:
    """Report secrets in files without showing them. Exits 1 if anything is found."""
    import sys

    pipeline = _pipeline_or_exit(pii, rules_only, "scan")
    found = 0
    for path in paths:
        try:
            raw = sys.stdin.buffer.read() if path == "-" else Path(path).read_bytes()
        except OSError as e:
            typer.echo(f"sotto scan: {path}: {e.strerror}", err=True)
            raise typer.Exit(2)
        if b"\0" in raw[:8192]:
            continue  # binary
        text = raw.decode("utf-8", errors="replace")
        line_starts = [0] + [i + 1 for i, ch in enumerate(text) if ch == "\n"]
        for s in pipeline.detect(text):
            line = bisect.bisect_right(line_starts, s.start)
            col = s.start - line_starts[line - 1] + 1
            # Never print the value, or any part of it: only where it is and what it is.
            typer.echo(f"{'<stdin>' if path == '-' else path}:{line}:{col}  {s.type}  {s.source}  [{s.end - s.start} chars]")
            found += 1
    if found:
        typer.echo(f"{found} finding{'s' if found != 1 else ''}", err=True)
        raise typer.Exit(1)


def _config():
    from .config import ConfigError, load

    try:
        return load()
    except ConfigError as e:
        typer.echo(f"sotto: bad config: {e}", err=True)
        raise typer.Exit(2)


def _pipeline_or_exit(pii: bool, rules_only: bool, who: str):
    from .detect.pipeline import ModelUnavailable, default_pipeline

    cfg = _config()
    try:
        return default_pipeline(pii=pii or cfg.pii, rules_only=rules_only,
                                allow_strings=cfg.allow_strings, allow_patterns=cfg.allow_patterns)
    except ModelUnavailable as e:
        typer.echo(f"sotto {who}: {e}", err=True)
        raise typer.Exit(2)


def _proxy_or_exit(pii, rules_only, upstream, who):  # who: "serve" or "claude", also the stats mode
    from .detect.pipeline import ModelUnavailable
    from .launch import build_proxy

    cfg = _config()
    try:
        return cfg, build_proxy(cfg, pii=pii, rules_only=rules_only, upstream=upstream, mode=who)
    except ModelUnavailable as e:
        typer.echo(f"sotto {who}: {e}", err=True)
        raise typer.Exit(2)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def claude(ctx: typer.Context) -> None:
    """Start Claude Code with every request scanned. Arguments go to `claude` unchanged."""
    import os

    from .launch import bypass_risks, log_to_file, run_claude

    risks = bypass_risks(Path.cwd())
    if risks:
        typer.echo("sotto: refusing to start, Claude Code could bypass the proxy:\n  " + "\n  ".join(risks), err=True)
        raise typer.Exit(2)
    # An existing ANTHROPIC_BASE_URL (another gateway) becomes sotto's upstream, never a bypass.
    upstream = os.environ.get("ANTHROPIC_BASE_URL")
    cfg, proxy = _proxy_or_exit(None, False, upstream, "claude")
    log_to_file(cfg.log_level)
    try:
        code = run_claude(proxy, ctx.args)
    except (FileNotFoundError, RuntimeError) as e:
        typer.echo(f"sotto claude: {e}", err=True)
        raise typer.Exit(2)
    raise typer.Exit(code)


@app.command()
def serve(
    port: int = typer.Option(None, help="Port on 127.0.0.1 (default: config, else 7788)."),
    upstream: str = typer.Option(None, help="Where scanned requests go (default: config, else api.anthropic.com)."),
    pii: bool = typer.Option(None, "--pii/--no-pii", help="Also mask personal data (default: config)."),
    rules_only: bool = typer.Option(False, help="L1 rules only (lower recall; for debugging)."),
) -> None:
    """Run the proxy on 127.0.0.1. Point Claude Code at it with ANTHROPIC_BASE_URL."""
    import logging

    from .launch import BackgroundServer

    cfg, proxy = _proxy_or_exit(pii, rules_only, upstream, "serve")
    logging.basicConfig(level=cfg.log_level.upper(), format="sotto: %(message)s")
    # Only sotto decides what is logged: libraries would print URLs and request details.
    for name in ("httpx", "httpcore", "uvicorn", "uvicorn.error"):
        logging.getLogger(name).setLevel(logging.WARNING)
    server = BackgroundServer(proxy, port or cfg.port)
    server.start()
    typer.echo(f"sotto: listening on http://127.0.0.1:{server.port} -> {proxy.upstream}", err=True)
    try:
        server.thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


@app.command()
def selftest(rules_only: bool = typer.Option(False, help="Test with L1 rules only.")) -> None:
    """Send a canary secret through the proxy to a local mock upstream; fail if it leaks."""
    import anyio

    from . import selftest as st

    pipeline = _pipeline_or_exit(False, rules_only, "selftest")
    ok = anyio.run(st.run, pipeline)
    typer.echo("selftest passed" if ok else "SELFTEST FAILED", err=True)
    raise typer.Exit(0 if ok else 1)


@app.command()
def setup() -> None:
    """Download the Privacy Filter model (1.6 GB, once), checked against its pinned SHA-256."""
    from .detect.pfserve import MODEL_URL, PfServeError, download_model, find_binary

    typer.echo(f"model: {MODEL_URL}", err=True)
    last = [-1]

    def progress(done: int, total: int) -> None:
        pct = done * 100 // total
        if pct != last[0]:
            last[0] = pct
            typer.echo(f"\r  {pct}% of {total / 1e9:.1f} GB", nl=False, err=True)

    try:
        path = download_model(progress)
    except (PfServeError, OSError) as e:
        typer.echo(f"\nsotto setup: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"\nmodel ready: {path}", err=True)
    if find_binary() is None:
        typer.echo("pf-serve is not installed yet: run native/pf-serve/build.sh", err=True)
        raise typer.Exit(1)


@app.command()
def doctor() -> None:
    """Check that this Mac can run sotto, and that nothing routes around it."""
    from .doctor import run

    raise typer.Exit(run())
