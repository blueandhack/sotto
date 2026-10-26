# Security policy

sotto exists to keep secrets from leaving your Mac, so a leak is the most serious kind of bug it can have.

## Reporting a vulnerability

Please report privately through GitHub: **Security → Report a vulnerability** on this repository. Do not open a public issue.

Useful reports include:

- A request shape that reaches the upstream with a real value in it (a leak).
- A way to make sotto forward a request it should have blocked (fail-open).
- A way to make sotto write a value to disk, a log, or the stats feed.
- A way for a model reply to send a restored value to a network tool.

Please use synthetic secrets in your report, never real ones. A minimal payload plus the `sotto` version and `sotto doctor` output is ideal.

## What is out of scope

These are known limits, documented in the README:

- Detection misses on secret formats with no rule and no context the local model recognizes. Please still report them as regular issues; they become new rules.
- Images and PDFs, which pass through unscanned.
- Real values in Claude Code's local transcripts, and in shell commands Claude runs on your Mac.

## Supported versions

sotto is pre-release. Only the latest commit on `main` gets fixes.
