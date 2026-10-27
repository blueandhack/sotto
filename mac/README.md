<p align="center"><img src="docs/logo.png" width="128" alt="sotto logo: a line of text where one word became placeholders"></p>

# sotto for Mac

A menu-bar app that sets sotto up, runs it in the background and shows what it does, in light and dark mode. The logo is a line of text where one word became placeholders: what sotto does to every request.

- **Overview:** key numbers and the live flow: two flow diagrams on shared columns, requests going out (client → sotto's scan → clean, masked, observed or blocked → provider) and replies coming back (provider → sotto's restore → client). Band width is the number of requests over the last hour, 24 hours or 7 days, and each live request travels its route as a dot. Each coding agent (Claude Code, Codex, pi) gets its own band, told apart by its User-Agent.
- **Activity:** recent requests with what was masked and restored, plus a per-minute chart.
- **Detection:** per type, how many values were found, allowed by an exception, passed through by your settings, and masked, with a switch to stop masking a type (names, dates…; secrets ask first); which detector found them (built-in rules, the local model, your rules) and the top rules; and your own rules: patterns always masked and exceptions never masked.
- **Performance:** scan time against the 150 ms budget, and its distribution.
- **Settings:** Setup (download the model, start the background service, protect Claude Code), excluded projects (`sotto exclude`), appearance (System, Light or Dark), preview data, connection details.

![Overview, light](docs/overview-light.png)
![Overview, dark](docs/overview-dark.png)

**Privacy.** The app reads sotto's stats feed (`/_sotto/stats`), which carries counts, types and timestamps only: never a value or a placeholder. It finds the proxy through `~/.config/sotto/runtime.json` (written by `sotto claude` and `sotto serve`; port 7788 otherwise). It authenticates with the token in `~/.config/sotto/stats-token` (mode 0600). It talks only to 127.0.0.1, sends no telemetry, and checks for no updates.

```sh
./build-app.sh            # build/Sotto.app with the engine, signed with your Apple Development identity (or ad-hoc)
SKIP_RUNTIME=1 ./build-app.sh   # the dashboard alone, for UI work
open build/Sotto.app
```

**What the app bundles** (`bundle-runtime.sh`, about 95 MB): a relocatable CPython 3.12 with sotto and its locked dependencies, pf-serve built from pinned sources, the `sotto` command the app runs for setup and protection, and a LaunchAgent (`Contents/Library/LaunchAgents/dev.sotto.agent.plist`) that runs `sotto serve` at login, registered with SMAppService. The bundled Python runs isolated (`-I`) and never writes into the signed bundle (`-B`; everything is compiled at build time). The model (1.6 GB) is downloaded on first use into `~/.local/share/sotto`, which the command line shares. The bundled sotto keeps its placeholder key in a 0600 file when it cannot read the Keychain item the command line created; placeholders then differ between the two, which only affects prompt-cache reuse.

**Setup**, in Settings, takes three steps, each also available on the command line: download the model (`sotto setup`), start the background service (macOS may ask you to allow it in System Settings › Login Items), and **Protect Claude Code** (`sotto protect on`). The switch turns on only while the service runs, and stopping the service turns protection off first, so Claude Code is never pointed at a proxy that is not there.

- **Preview** shows animated sample data, clearly labeled, when sotto is not running.
- `Sotto --snapshot dir` renders every page in light and dark to PNGs and exits; with `--live` it renders the overview from the running proxy.
- Development-signed builds run only on this Mac. For other Macs, see Releasing.

## Releasing

A release is a notarized `Sotto-<version>.dmg` on the repository's GitHub Releases page. Apple's notarization is what lets the app open on other Macs without a warning; it needs a paid Apple Developer membership.

**Once per Mac:**

1. **Developer ID certificate.** Xcode › Settings › Accounts › your team › Manage Certificates › **+** › *Developer ID Application* (only the account holder can create one). Check: `security find-identity -v -p codesigning` lists `Developer ID Application: …`.
2. **Notary credentials**, kept in the Keychain. Create an app-specific password at account.apple.com › Sign-In and Security, then:
   ```sh
   xcrun notarytool store-credentials sotto-notary --apple-id you@example.com --team-id ABCDE12345
   ```
   It asks for the password and checks it with Apple.

**Each release:**

```sh
# 1. bump `version` in pyproject.toml, commit
mac/release.sh                                  # tests, build, Developer ID signature, notarize, staple -> dist/
git tag -s v0.1.0 -m "sotto 0.1.0" && git push origin main v0.1.0
gh release create v0.1.0 dist/Sotto-0.1.0.dmg dist/Sotto-0.1.0.dmg.sha256 \
  --verify-tag --title "sotto 0.1.0" --generate-notes --prerelease
```

`release.sh` refuses an uncommitted tree, notarizes the app and then the DMG, staples both tickets (so the app opens offline after it is copied out), and ends by asking Gatekeeper (`spctl`) for the verdict another Mac would reach. A rejected submission prints Apple's log. `SKIP_NOTARIZE=1 ALLOW_DIRTY=1 mac/release.sh` runs every other step with your development identity, to test it.

Users download the DMG, drag Sotto into Applications, open it, and follow Settings › Setup. Drop `--prerelease` once sotto leaves pre-release. Release builds happen on a Mac you control rather than in CI, so the signing certificate never leaves it.

**Logos.** Claude Code and the Anthropic API appear with their official logos (`Brand/`, from Anthropic's [press kit](https://www.anthropic.com/press-kit), used unmodified to identify those services; see [Brand/NOTICE.md](Brand/NOTICE.md)). Claude, Claude Code and Anthropic are trademarks of Anthropic, PBC; sotto is an independent project, not affiliated with or endorsed by Anthropic. "This Mac" shows a laptop or a Mac mini, depending on whether the Mac has a battery.

Requires macOS 14 or later.
