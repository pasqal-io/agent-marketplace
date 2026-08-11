# Claude Code

## Install from the marketplace

```
/plugin marketplace add pasqal-io/agent-marketplace
/plugin install pasqal-agent@pasqal
```

While the repository is private, your git must be able to reach GitHub
(SSH key or `gh auth login`). Organizations on Claude Enterprise can instead
distribute the plugin to everyone via **Organization settings → Plugins**
(uses the Claude GitHub App; no per-user setup).

## Dry-run without installing

```bash
claude --plugin-dir /path/to/agent-marketplace
```

Then in the session: check the skills appear under `/pasqal-agent:*`, try a
trigger phrase ("run a noise emulation"), and `/reload-plugins` after edits.

## Update

```
/plugin marketplace update pasqal
```
