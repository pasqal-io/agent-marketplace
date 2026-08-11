# Per-agent installation

The skills in this repository follow the [Agent Skills](https://agentskills.io)
open standard: each skill is a directory with a `SKILL.md` (YAML frontmatter +
instructions) plus supporting files. The standard is supported natively by
Claude Code and increasingly by other coding agents.

| Agent | Status | Notes |
|---|---|---|
| Claude Code | ✅ supported | [claude.md](claude.md) — marketplace install or `--plugin-dir` |
| Kimi Code | ✅ manifest + docs | [kimi.md](kimi.md) — `.kimi-plugin/plugin.json`, installs from the repo URL |
| OpenAI Codex | ⚠️ manifest ready, not yet discoverable | [codex.md](codex.md) — `.codex-plugin/plugin.json`; marketplace listing needs the repo public + submission to `openai/plugins` |
| Cursor | 🚧 planned | adapter dir + install docs to be added |
| Others (OpenCode, …) | 🚧 planned | contributions welcome |

## Notes for adapter authors

Some skill content currently uses Claude Code-specific mechanics that other
agents do not resolve:

- the `AskUserQuestion` interactive tool (used e.g. by `noise-emulate` for
  backend selection — other agents should fall back to asking in plain text),
- Claude-specific frontmatter extensions (`argument-hint`,
  `disable-model-invocation`), which other agents may ignore harmlessly.

An adapter should either translate these or document the graceful degradation.
Use [obra/superpowers](https://github.com/obra/superpowers) as the reference
for multi-agent adapter layouts.
