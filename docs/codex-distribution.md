# Hermes Codex App Server distribution

Source and updates: https://github.com/yinzhiyan43/hermes-agent, branch `main`.
Upstream source: https://github.com/NousResearch/hermes-agent.

## Runtime contract

Codex always uses official `codex app-server`, including profiles created before this fork.
Authentication, model discovery and account usage belong to that process; Hermes does not
read or refresh Codex OAuth tokens. Install the official Codex CLI and run `codex login`.
Select **Codex App Server** in Hermes settings or `hermes model`. A missing account or failed
RPC is an error, not permission to fall back to a direct Responses API.

Hermes session IDs persist bindings to Codex threads. Resume errors propagate; they do not
silently create replacement threads. Codex auxiliary requests and Codex background reviews
are disabled until supported by the session runtime. Other providers remain available.

## Installation and updates

Download the Setup DMG from this repository's Releases for an Apple Silicon Mac.
This initial distribution is unsigned and not notarized. The setup binary embeds the
release commit and downloads its installation script and source from this repository.
The desktop ZIP is intended for an existing Hermes runtime installation.

For a source install, download and inspect this repository's `scripts/install.sh` and
run it with `bash scripts/install.sh --branch main`. Never use the Nous website installer
to maintain this distribution; that installer targets the official repository.

Before migrating an existing source install, back up uncommitted source changes and user
configuration. Set its `origin` to `https://github.com/yinzhiyan43/hermes-agent.git`, retain
upstream under a separate `nous-source` remote, and integrate the maintained `main`.
Normal `hermes update` and desktop checks follow `origin/main`; the Windows ZIP recovery
also targets this fork. Do not reset an installed checkout to NousResearch/main.

## Maintenance and release

1. Fetch NousResearch/main into a separate upstream remote in the development checkout.
2. Merge upstream into this repository's main; resolve conflicts while retaining the Codex
   runtime boundary and fork install/update URLs. Never use a hard reset or force-sync to
   erase the distribution commits.
3. Run the **Codex distribution** checks. The upstream CI orchestrator requires Nous-specific
   runners; this fork uses its own standard-runner regression workflow instead.
4. Run **Codex distribution → Run workflow** on main. Tests gate packaging; a draft release
   contains the Apple Silicon Setup DMG, desktop ZIP, provenance and checksums.
5. Verify the draft assets and commit, then publish the release. The initial macOS release
   has no signing secrets. Add your own signing/notarization credentials before distributing
   signed builds; never reuse Nous Research identity credentials.

The installation pins release source; later updates follow maintained main. Commit and test
all runtime changes before pushing main. Source code, not a post-update patch script, owns
the customization. Personal configuration, account credentials and session history must
never be committed to this public repository.
