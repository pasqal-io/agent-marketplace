# OpenAI Codex (App & CLI)

Two files make this repo installable in Codex:

| File | Role |
|---|---|
| `.agents/plugins/marketplace.json` | the catalog Codex reads when you add this repo as a marketplace source |
| `.codex-plugin/plugin.json` | the plugin manifest — points Codex at the shared `skills/` directory and supplies the interface metadata |

## Install

No submission to any directory is required. Codex supports git-hosted
marketplaces, so this works as soon as the repository is reachable:

```bash
codex plugin marketplace add pasqal-io/agent-marketplace
```

Then install `neutral-atom-toolkit` from the Plugins view (Codex App sidebar, or
`/plugins` in the CLI). Pin a revision with `--ref <tag>` if you want a fixed
version rather than the tip of `main`.

## Notes for adapter authors

- **The catalog path matters.** Codex looks for `$REPO_ROOT/.agents/plugins/marketplace.json`
  (or `~/.agents/plugins/marketplace.json` for a personal catalog).
  `.claude-plugin/marketplace.json` is only a legacy fallback — do not rely on it.
- **`source.path` is `"."`** because the repository root *is* the plugin
  (superpowers-style layout). A repo hosting several plugins would use
  `"./plugins/<name>"` per entry instead.
- **`policy.authentication` is `ON_USE`**, not `ON_INSTALL`: nothing is
  authenticated at install time. Cloud credentials are read from the
  environment the first time a skill actually talks to a backend.
- **`"hooks": {}` in `.codex-plugin/plugin.json` is deliberate.** Exactly an
  empty object suppresses hook auto-discovery. Removing the field — or setting
  it to an empty array — makes Codex look for `hooks/hooks.json`, which this
  plugin does not ship.
- `policy.installation`, `policy.authentication`, `category` and
  `interface.displayName` are all required by the catalog schema; `category`
  must be one of the Codex enum values (`Developer Tools`,
  `Education & Research`, `Productivity`, …).

Reference: [Codex — Package your plugin](https://developers.openai.com/codex/plugins/build).
