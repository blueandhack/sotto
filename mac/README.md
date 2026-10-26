<p align="center"><img src="docs/logo.png" width="128" alt="sotto logo: a line of text where one word became placeholders"></p>

# sotto for Mac

A menu-bar app and dashboard for sotto, in light and dark mode. The logo is a line of text where one word became placeholders: what sotto does to every request.

- **Overview:** key numbers, the live flow map (clean, sensitive, blocked and restored traffic, each on its own lane to its own destination, with the line between this Mac and Anthropic), recent requests, and the last hour. It fits one window without scrolling.
- **Activity:** recent requests with what was masked and restored, plus a per-minute chart.
- **Detection:** the request and detection funnels, and masked values by type.
- **Performance:** scan time against the 150 ms budget, and its distribution.
- **Settings:** appearance (System, Light or Dark), preview data, connection details.

![Overview, light](docs/overview-light.png)
![Overview, dark](docs/overview-dark.png)

**Privacy.** The app reads sotto's stats feed (`/_sotto/stats`), which carries counts, types and timestamps only: never a value or a placeholder. It finds the proxy through `~/.config/sotto/runtime.json` (written by `sotto claude` and `sotto serve`; port 7788 otherwise). It authenticates with the token in `~/.config/sotto/stats-token` (mode 0600). It talks only to 127.0.0.1, sends no telemetry, and checks for no updates.

```sh
./build-app.sh            # build/Sotto.app, signed with your Apple Development identity (or ad-hoc)
open build/Sotto.app
```

- **Preview** shows animated sample data, clearly labeled, when sotto is not running.
- `Sotto --snapshot dir` renders every page in light and dark to PNGs and exits; with `--live` it renders the overview from the running proxy.
- Distribution needs a *Developer ID Application* certificate and notarization (M6). Development-signed builds run only on this Mac.

**Logos.** Claude Code and the Anthropic API appear with their official logos (`Brand/`, from Anthropic's [press kit](https://www.anthropic.com/press-kit), used unmodified to identify those services; see [Brand/NOTICE.md](Brand/NOTICE.md)). Claude, Claude Code and Anthropic are trademarks of Anthropic, PBC; sotto is an independent project, not affiliated with or endorsed by Anthropic. "This Mac" shows a laptop or a Mac mini, depending on whether the Mac has a battery.

Requires macOS 14 or later.
