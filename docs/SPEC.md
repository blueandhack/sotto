# sotto — Local Secret & PII Redaction for Claude Code (Build Spec)

Oct 25, 2026 · @Yujia Lin

## Summary

sotto is a local proxy that removes secrets and personal data from Claude Code requests before they leave the Mac, then restores the real values locally. Nothing is sent to any third party: detection runs fully on-device. The name comes from *sotto voce*, "in a low voice."

Build order: **Phase 0 is a benchmark** that measures which detectors are fast and accurate enough. The real proxy is built only after those numbers are in.

**Instructions for Claude Code**

- Treat this doc as the spec. Work one phase at a time and stop for review at the end of each phase.
- Anything marked **VERIFY** is an assumption about an external API (Apple `fm`, the Apple Foundation Models Python SDK, OpenAI Privacy Filter). Check the real docs or `--help` output before writing code against it, and update this doc if it is wrong.
- Never write a real secret into code, tests, fixtures, logs or commit messages. Use synthetic test values only.
- Keep it simple. Prefer the standard library and a few well-known dependencies over frameworks.

## Goals, non-goals, constraints

The goal is a one-command tool: `sotto claude` starts Claude Code with every request scrubbed, and the user notices nothing else.

**Goals**

1. No raw secret (API key, token, password, private key, connection string) reaches api.anthropic.com.
2. Personal data (names, emails, phones, addresses, account numbers) is redacted when enabled.
3. Claude can still edit files that contain secrets: placeholders are restored before tools run locally.
4. Fail closed: if sotto is down or a detector errors, the request is blocked, never sent raw.
5. Added latency stays small enough to be unnoticeable. Phase 0 sets the actual budget.

**Non-goals (v1)**

- Other AI clients (Codex, Cursor, Gemini CLI). The design should not block them later.
- Linux, Windows, or Intel Macs.
- Compliance certification. sotto is a safety layer, not an anonymization guarantee.
- Rewriting Claude Code's local transcript files.

**Hard constraints**

| Constraint | Value |
| --- | --- |
| OS | macOS 27 or later (ships the `fm` command and the 8,192-token on-device model) |
| Hardware | Apple silicon; reference machine is an M4 with 48 GB |
| Network | Detection fully offline; the only outbound connection is the forwarded request to api.anthropic.com |
| Language | Python 3.12+, managed with `uv`; the model runs in pf-serve, a native program (C++ on ggml) |
| Distribution | Homebrew tap later; `uv tool install` during development |
| Name | `sotto` — check GitHub, PyPI and Homebrew before first publish; fall back to `sotto-redact` if taken |

## Architecture

sotto is a local HTTP proxy: Claude Code talks to it through `ANTHROPIC_BASE_URL`, and it is the only thing that talks to Anthropic.

&#91;embedded content: sotto architecture · request and response paths\]

Requests flow left to right through Redact; responses flow right to left through Restore. Detection and the vault never touch the network, and if the proxy is down, Claude Code's requests fail instead of going out raw.

## Detection layers

Detection runs in two layers, cheapest first, followed by deterministic refinement of the model's spans. No LLM runs in the request path. Each layer returns spans (`start`, `end`, `type`, `confidence`), never rewritten text, so a model can never silently change code.

| Layer | Catches | Engine | Expected cost |
| --- | --- | --- | --- |
| L1 Rules | API keys, tokens, JWTs, private keys, connection strings, `password=` assignments, high-entropy strings | Regex rules (gitleaks-style) + Shannon entropy + checksums (Luhn for cards) | Microseconds; always on |
| L2 PII model | Names, addresses, emails, phones, URLs, dates, account numbers, secrets in context | OpenAI Privacy Filter (open-weight, Apache 2.0, 1.5B total / 50M active params, token classifier), q8 GGUF on pf-serve | One forward pass: p95 ≈ 100–145 ms at 4K tokens |
| Refinement | Model spans that are log noise: UUIDs, hashes, request ids, timestamps, API paths, placeholders, reserved example values | Deterministic rules in `detect/pipeline.py` | Microseconds |

**Rules for each layer**

- **L1** ships a default rule file (`rules.toml`) and supports user rules plus an allowlist (exact strings and regexes). Known example keys from docs, such as AWS's `AKIAIOSFODNN7EXAMPLE`, are allowlisted by default.
- **L2** is off for PII by default and on for secrets-in-context. Users enable PII with `pii = true`. Load the model once at startup and keep it warm. **VERIFIED (Oct 25, 2026):** the model id is `openai/privacy-filter`. It has 8 labels (`account_number`, `private_address`, `private_date`, `private_email`, `private_person`, `private_phone`, `private_url`, `secret`), tagged BIOES (33 classes) and decoded with constrained Viterbi; the default operating point has all six transition biases at 0. MLX ports exist (`mlx-community/openai-privacy-filter-bf16`, `-8bit`, others) and run through `mlx-embeddings`. That support is on its GitHub `main` only (PyPI 0.1.0 lacks it), so sotto pins a commit and also needs `mlx-lm`. Transformers on MPS works but is about 10× slower; MLX is the backend. The model tags UUIDs, hashes and neighboring `key=value` log fields as `secret`, so sotto refines its secret spans (see `detect/pipeline.py`). With `pii = true` it also refines personal-data spans (`Pipeline.keep_pii`): IDs tagged as accounts, timestamps tagged as dates, API paths tagged as URLs, reserved example emails and phones, and lowercase identifiers tagged as names are dropped. That raised PII precision from 0.55–0.61 to 0.90–0.93 with no recall loss.
- **Runtime: pf-serve (Oct 25, 2026).** The model runs in pf-serve (`native/pf-serve`, from magpie, MIT), built on privacy-filter.cpp (MIT) and ggml: a 2.4 MB binary using Metal on macOS, and Vulkan or the CPU on Windows and Linux. It replaces MLX so sotto needs no Python ML packages and can be packaged for other systems. The weights are `LocalAI-io/privacy-filter-GGUF` `privacy-filter-q8.gguf` at revision `935d868`, SHA-256 `80efc180…998c`, downloaded by `sotto setup`. Measured against MLX on all three datasets (`bench/results/PFSERVE.md`): the same secret recall and the same flagged negatives, 1.7 GB instead of 2.2–2.5 GB, and 0.7 s to load instead of 3–6 s. One IBAN was missed with `pii = true`; IBANs are now an L1 checksum rule. pf-serve runs as a child process: a request that errors or exceeds 30 s + 1 s per 4 KB is blocked, and the next request starts a new process. MLX stays in the benchmark as `sotto[mlx]`.
- **No LLM judge in v1 (Oct 25, 2026).** Phase 0 tested two judges on 400 labeled spans. The Apple on-device model could not clear false positives without clearing real values. Qwen3-4B on MLX cleared some at first, but once personal-data refinement existed it cleared 0 of 347 spans while adding 2.2 GB and 1–1.5 s per turn. Both experiments are kept in `bench/judge.py` and `bench/results/MODELS.md`.
- **Apple on-device model: dropped from v1 (Oct 25, 2026).** Phase 0 measured it as a span extractor and as a judge (`bench/results/MODELS.md`). As an extractor it had p95 27 s at 4K tokens and flagged 62% of hard negatives. As a judge, no prompting setup cleared false positives without also clearing real values: zero-shot cleared 3% of false positives and leaked 4 of 100 real secrets, and content-tagging mode leaked 69. Custom adapters could change this, but they are Swift-only and need Apple's entitlement. `detect/afm.py` stays for the benchmark. API notes from the VERIFY pass: `fm respond --no-stream -g -i <instructions> --schema <file> [--guardrails permissive-content-transformations]`; the SDK is PyPI `apple-fm-sdk` (`apple_fm_sdk`), with `SystemLanguageModel(...).context_size` (8192) and `LanguageModelSession(instructions=, model=).respond(prompt, json_schema=, options=)`.

**Merge policy**

Union all spans, merge overlaps, keep the widest span and the highest-priority type (secret > PII). When in doubt, redact: a false positive costs a placeholder; a false negative leaks.

## Placeholders, vault, restore

Every sensitive value becomes a deterministic placeholder, so the same secret always maps to the same text. This keeps Anthropic's prompt cache valid across turns and makes re-redacting history consistent.

**Placeholder format**

- `SOTTO_<TYPE>_<id>`, for example `SOTTO_SECRET_7f3a9c2e` or `SOTTO_EMAIL_01b44d90`. It looks like an identifier, so Claude copies it verbatim instead of "fixing" it.
- `<id>` = first 8 hex chars of HMAC-SHA256(install salt, type + value). On a collision, extend to 12 chars.
- Types: `SECRET`, `PERSON`, `EMAIL`, `PHONE`, `ADDRESS`, `ACCOUNT`, `URL`, `DATE`.
- The install salt is generated once and stored in the macOS Keychain (fallback: `~/.config/sotto/salt`, mode 0600).

**Vault**

- In-memory map `placeholder → value` inside the proxy process. No persistence in v1: because responses are restored before Claude Code saves them, the local transcript holds real values, and they re-redact to the same placeholders on the next request.
- The vault is never logged, never written to disk, and cleared on exit.

**What gets scanned (request side)**

- Endpoints: `POST /v1/messages` and `POST /v1/messages/count_tokens` are scanned. Any other request that carries a body is **blocked** (403, API-style error), because forwarding it would send content out unscanned. Bodyless `GET`/`HEAD`/`OPTIONS` requests are forwarded and logged by path only. Review the paths Claude Code actually calls during M4.
- Fields: `system` (string or text blocks); `messages[].content` as a string or blocks: `text`, every string inside `tool_use.input` (recursively), and `tool_result.content` (string or blocks). Images and documents pass through in v1 (listed as a risk).
- Skip the `tools` array (Claude Code's own tool definitions) for speed.
- Never touch protocol fields the API checks: block ids (`toolu_…`), tool names, `tool_use_id`, the keys of `tool_use.input` (only its string values are scanned), `thinking` and `redacted_thinking` blocks, and anything with a `signature`. Changing a signed thinking block gets a 400 "Invalid signature". Thinking blocks are model output produced from already-redacted input, so they hold placeholders, not values, and are never restored either (see Restore).
- Known values: once a value is masked, every later exact occurrence of it is masked too, even where the detectors would miss it in a different context. The vault drives this by exact match, longest value first.
- Cache scan results per text block by SHA-256 in an LRU. Claude Code resends the whole history every turn, so only new blocks should hit the detectors.
- Auth headers (`x-api-key`, `authorization`) are forwarded unchanged so both API-key and subscription logins work. They are never logged.

**Restore (response side)**

| Where the placeholder appears | v1 default |
| --- | --- |
| Assistant text | Restore |
| `thinking` blocks | Keep placeholder (signed; must be resent unchanged) |
| `tool_use` input for Edit, Write, MultiEdit, NotebookEdit | Restore |
| `tool_use` input for Bash | Restore (open question below) |
| `tool_use` input for WebFetch, WebSearch, and every MCP tool (`mcp__*`) | Keep placeholder. sotto cannot tell which MCP servers reach the network, so all of them keep placeholders unless the config says otherwise |

The policy lives in config (`[restore]` per tool name), so it can be tightened without code changes.

**Streaming (the tricky part)**

Claude Code uses server-sent events. Placeholders can be split across deltas, so restore needs buffering.

1. `content_block_delta` with `text_delta`: keep a tail buffer. If the end of the buffered text could be the start of a placeholder (matches a prefix of `SOTTO_`), hold it until the next delta or `content_block_stop`; otherwise flush.
2. `content_block_delta` with `input_json_delta`: buffer the whole tool input until `content_block_stop`, restore, then emit it as one delta. Tool inputs are not shown progressively, so the delay is invisible.
3. When restoring inside JSON (`partial_json`), JSON-escape the real value. Secrets often contain quotes or backslashes.
4. Non-streaming responses: parse the JSON, restore, re-serialize.
5. Pass all other events (`message_start`, `message_delta`, `ping`, `error`) through untouched and in order.

## Phase 0: benchmark first

Phase 0 answers one question: which detector combination catches enough secrets, fast enough, to sit in front of every request? No proxy code is written until this phase is reviewed.

**Labeled dataset** (`bench/data/*.jsonl`)

Each record: `{"id", "text", "spans": [{"start", "end", "type"}], "tags": [...]}`. Target about 150 records to start:

| Group | Records | Examples |
| --- | --- | --- |
| Secrets | 50 | AWS, GitHub, Anthropic, OpenAI, Stripe, Slack keys; JWTs; PEM private keys; `.env` files; Postgres/Redis URLs with passwords |
| PII | 40 | Names, emails, phones, addresses inside code comments, logs, JSON fixtures, commit messages |
| Hard negatives | 40 | UUIDs, git SHAs, base64 test data, hashes in lockfiles, docs example keys, `user@example.com`, Kubernetes ports |
| Long, realistic | 20 | Claude-Code-like payloads: a source file or log of 1K, 4K and 8K tokens with 0–3 secrets buried inside |

- Generate secrets with a script (`bench/gen.py`) that produces random values in each provider's format. Never use or paste real keys.
- Use Faker for PII. Hand-write the hard negatives; they matter as much as the positives.

**Detectors under test**

1. `rules` — L1 only.
2. `pf` — OpenAI Privacy Filter only.
3. `afm-cli` — Apple on-device model via `fm respond` subprocess, asked to return spans as JSON.
4. `afm-sdk` — same prompt via the Python SDK (measures subprocess overhead vs. in-process).
5. `rules+pf` and `rules+pf+afm` — the layered pipeline, with AFM judging only ambiguous spans.

**Metrics** (per detector, per type, per input size)

- Span precision, recall, F1. A detected span counts as a hit if it overlaps a labeled span by at least 50%.
- Latency p50 and p95 per input at 1K, 4K and 8K tokens; cold start; tokens per second.
- Peak memory (RSS).
- AFM only: refusals, schema failures, and context-overflow errors, as counts.

**Command**

`sotto bench --detectors rules,pf,afm-cli,afm-sdk --data bench/data --out bench/results/` writes a JSON file and a Markdown summary table.

**Decision rules (starting targets; adjust after the first run)**

- Secrets recall must be at least 0.98 for the default pipeline. Leaks are worse than noise.
- Hard-negative false positives below 5%.
- Added p95 latency per turn at or below 150 ms when new content is 4K tokens or less.
- Keep AFM in the default pipeline only if it measurably improves precision on ambiguous spans within that budget. Otherwise ship it as an opt-in flag.
- **Outcome (Oct 25, 2026):** the pipeline is `rules + pf` (8-bit MLX at the time; pf-serve since, same results) with secret and personal-data refinement, and `pii = false` by default. No LLM judge: the Apple model and Qwen3-4B were both measured and dropped. See `bench/results/PHASE0.md` and `MODELS.md`.

## CLI, config, layout, milestones

The whole user experience is one command: `sotto claude`. Everything else exists for setup, debugging and CI.

**Commands**

| Command | What it does |
| --- | --- |
| `sotto claude [args]` | Starts the proxy on a free local port, runs `claude` with `ANTHROPIC_BASE_URL` pointing at it, stops the proxy when Claude exits. Passes all args through. |
| `sotto serve` | Runs the proxy standalone on `127.0.0.1:7788` (configurable). Binds to localhost only. |
| `sotto scan <file or ->` | Prints findings with values masked; exits 1 if anything is found. Usable as a pre-commit hook. |
| `sotto bench` | Phase 0 benchmark. |
| `sotto doctor` | Checks macOS version, Apple silicon, L2 model present, port free. |
| `sotto selftest` | Sends a synthetic canary secret through the proxy to a local mock upstream and fails unless it arrives redacted. |

**Config** (`~/.config/sotto/config.toml`, all optional; unknown keys and bad values are errors)

```toml
[server]
port = 7788                          # for `sotto serve`; `sotto claude` picks a free port
upstream = "https://api.anthropic.com"

[detect]
pii = false          # also mask personal data (L1 rules and L2 secrets are always on)

[allowlist]          # added to the built-in allowlist, never replacing it
strings = []
patterns = []

[restore]            # per tool: "restore" or "keep"; prefixes like "mcp__files__*" allowed
default = "restore"
WebFetch = "keep"
WebSearch = "keep"
"mcp__*" = "keep"

[log]
level = "info"       # never logs values, only type + counts
```

`sotto claude` writes logs to `~/.config/sotto/sotto.log` (mode 0600), because the terminal belongs to Claude Code, and records its port in `~/.config/sotto/runtime.json` (0600) for the Mac app. It refuses to start if any Claude Code settings file sets `ANTHROPIC_BASE_URL` or a Bedrock/Vertex/Foundry switch, or if such a switch is in the environment, since that could route traffic around the proxy. An `ANTHROPIC_BASE_URL` already in the environment (another gateway) becomes sotto's upstream.

**Stack**

Python 3.12, `uv`, Typer (CLI), Starlette + uvicorn (proxy server), httpx (async streaming upstream), pytest. L2 needs no Python packages: pf-serve is a separate binary (`native/pf-serve/build.sh`) and `sotto setup` downloads its model. `sotto[mlx]`, `sotto[pf-torch]` and `sotto[afm]` exist for the benchmark only.

**Repo layout**

```
sotto/
  pyproject.toml
  src/sotto/
    cli.py          # Typer entry point
    proxy.py        # Starlette app, request/response rewrite, SSE handling
    redact.py       # walk Messages API payloads, apply spans, placeholders
    restore.py      # vault lookup, streaming tail buffer, JSON escaping
    vault.py        # in-memory map, HMAC ids, Keychain salt
    detect/
      rules.py      # L1 regex + entropy + checksums
      rules.toml    # default rule set
      pf.py         # L2 OpenAI Privacy Filter
      afm.py        # Apple on-device model (benchmark only)
      merge.py      # span union and priority
      pipeline.py   # layers, plus refinement of model spans
    config.py
  bench/
    gen.py  data/  results/
  tests/
```

**Milestones** (stop for review after each)

- [x] **M0 Benchmark.** Dataset, `sotto bench`, first results table. Done when the default pipeline is chosen from real numbers. *Done Oct 25, 2026: `rules + pf-8bit` with refinement and no LLM (`bench/results/PHASE0.md`).*
- [x] **M1 Scanner.** `detect/` + `redact.py` + `sotto scan`. Done when every dataset record round-trips: redact, then restore, gives the original text byte-for-byte.
- [x] **M2 Proxy, non-streaming.** `/v1/messages` and `count_tokens` rewrite, fail-closed errors, `sotto selftest`, and the local stats feed the Mac app reads (counts, types and timestamps only, never values). Done when the canary never reaches the mock upstream.
- [x] **M3 Streaming restore.** SSE tail buffer and tool-input buffering. Done when placeholders split at every possible byte offset are restored correctly (property test).
- [x] **M4 `sotto claude`.** Wrapper, config file, restore policy, `sotto doctor`. Done when a real Claude Code session edits a file containing a fake secret and the file ends up with the real value. *Passed Oct 25, 2026 (Claude Code 2.1.273): the file ended with the real value, and a recording relay between sotto and Anthropic saw 0 copies of either fake secret. Claude Code only called `HEAD /api/hello` and `POST /v1/messages`.*
- [ ] **M4.5 Secret classifier — on hold (Oct 25, 2026).** A small encoder that labels candidate spans as credential, identifier, placeholder or personal data, replacing hand-written refinement as the main filter for false positives. The trigger is fresh held-out set 2: 9 of 15 hard negatives were flagged, each a new identifier shape. Candidate data: Samsung CredData (Apache-2.0) plus synthetic positives and harvested public identifiers. Never train on the hand-written negative sets.
- [ ] **M5 Mac app.** A SwiftUI menu-bar app with a dashboard window and Swift Charts. It shows a live flow diagram (Claude Code → sotto → Anthropic) with counts, redactions over time by type, restores, fail-closed blocks, detection latency and model health, plus start/stop and a PII toggle. It reads M2's stats feed over a local socket guarded by a 0600 token file. It never receives a sensitive value, sends no telemetry and checks for no updates. Signed with Developer ID and notarized; ships as a Homebrew cask.
- [ ] **M6 Ship.** README, Homebrew tap, name check on GitHub, PyPI and Homebrew.

## Testing, safety rules, risks

The one test that must never fail: a canary secret sent through sotto never appears in any byte that reaches the upstream.

**Testing**

- Unit tests per detector, against the benchmark dataset.
- Round-trip property test: for any text, `restore(redact(text)) == text`.
- Streaming property test: split SSE events at every byte offset; output must equal the non-streamed restore.
- Proxy tests against a local mock upstream that records every byte received and asserts no canary is present.
- Fail-closed tests: kill L2 mid-request, make L2 return garbage, send malformed JSON. Each must return an error to Claude Code, never forward the raw body.

**Safety rules for the code**

- Logs contain only type, placeholder and counts. Never values, request bodies or auth headers.
- Bind to `127.0.0.1` only. Reject requests with a non-local `Host` header.
- Third-party loggers (httpx, httpcore, uvicorn) are capped at WARNING so they cannot print URLs or request details; uvicorn's access log is off.
- **Stats feed** (`GET /_sotto/stats`, for the Mac app): request counts by outcome, masked and restored counts by type, scan latency, and the last 200 events (time, path, status, counts). It never holds a value or a placeholder. It requires `Authorization: Bearer <token>`, with the token in `~/.config/sotto/stats-token` (mode 0600).
- No telemetry, no update checks, no network calls except the forwarded request.
- Synthetic secrets only in the repo. Add `sotto scan` as a pre-commit hook on the sotto repo itself.

**Risks**

| Risk | Mitigation |
| --- | --- |
| Missed secret (false negative) | Layered detection; redact-when-in-doubt merge; recall target in Phase 0 |
| Over-redaction breaks Claude's work | Allowlist; hard-negative tests; restore in edits so files stay correct |
| Prompt injection asks Claude to send a placeholder somewhere, and restore leaks it | Per-tool restore policy; network tools keep placeholders |
| Secrets inside images or PDFs | Out of scope for v1; documented in README |
| Local transcript files keep real values | Out of scope for v1; documented in README |
| Refinement drops a real value | Each refinement rule is tested and measured on held-out data for recall loss (none so far); refinement never touches L1 rule hits |
| Claude Code changes its request format | Walk payloads generically by block type; selftest in CI |

**Open questions**

- Should Bash tool inputs get restored values? Restoring lets commands like `curl -H "Authorization: ..."` work, but it is also the easiest exfiltration path.
- ~~Should `pii` default to on?~~ No (Phase 0): with PII on, 17–27% of hard negatives are flagged, and ACCOUNT, URL and DATE precision is 0.13–0.36.
- With the Apple model dropped, nothing in v1 needs macOS 27 (pf-serve is built for macOS 14+). Should the OS floor come down?
- Is a Swift binary worth it later for distribution, or does Python plus Homebrew stay simple enough?
