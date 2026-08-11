# Kimi Code

The Kimi manifest lives at `.kimi-plugin/plugin.json`. It points Kimi Code at
the shared `skills/` directory and adds Kimi-specific tool mapping via
`skillInstructions` (including how to resolve `${CLAUDE_PLUGIN_ROOT}` paths and
which tool to use for the noise-emulate backend question).

## Install

In Kimi Code:

```text
/plugins install https://github.com/pasqal-io/agent-marketplace
```

While the repository is private, your git must be authenticated to GitHub.
Kimi Code applies plugin changes to new sessions — after installing or
updating, start a fresh session with `/new`.

## Update

Reinstall with the same command (or use the `/plugins` manager), then `/new`.
