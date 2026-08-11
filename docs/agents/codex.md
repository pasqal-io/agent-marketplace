# OpenAI Codex (App & CLI)

The Codex manifest lives at `.codex-plugin/plugin.json`. It points Codex at the
shared `skills/` directory and provides the marketplace interface metadata.

## Install

Codex installs plugins through the
[official Codex plugin marketplace](https://github.com/openai/plugins):

- **Codex App**: Plugins sidebar → search "Neutral Atom Toolkit" → install.
- **Codex CLI**: `/plugins` → search "Neutral Atom Toolkit" → install.

**Availability caveat**: marketplace listing requires this repository to be
public and submitted to `openai/plugins`. While the repository is private, the
manifest is in place but the toolkit is not yet discoverable in Codex — check
Codex's documentation for custom/private plugin sources, or use Claude Code /
Kimi Code in the meantime.
