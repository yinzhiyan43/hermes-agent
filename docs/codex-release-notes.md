Personal Hermes distribution maintained at https://github.com/yinzhiyan43/hermes-agent.

- Codex uses the official `codex app-server` process. Run `codex login` before selecting Codex in Hermes.
- Installer downloads, desktop bootstrap and updates use this repository.
- Setup DMG: installs the Python runtime and desktop. Desktop ZIP: desktop bundle for existing installations.
- Apple Silicon macOS only for this initial release. Binaries are not Apple Developer ID signed or notarized.
- `install-stamp.json` identifies the exact desktop source commit; the setup application embeds the same commit. `SHA256SUMS` verifies downloaded files.

This is a personal fork, not an official Nous Research release. Existing user data is retained. Read `codex-distribution.md` for migration and maintenance.
