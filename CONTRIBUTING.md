# Contributing

## Repository layout

The repo root is the `pasqal-agent` plugin:

```
.claude-plugin/
  plugin.json         plugin manifest (bump `version` to publish an update)
  marketplace.json    marketplace catalog (this repo lists itself via source "./")
skills/<name>/
  SKILL.md            frontmatter + instructions (the skill itself)
  support/            scripts the skill runs (Python/bash)
  templates/          files the skill instantiates
  references/         reference implementations the skill reads
scripts/check.sh      repo health checks (CI runs this)
docs/agents/          per-agent installation notes
```

## Adding or changing a skill

1. **One skill = one user intent.** Split skills by what the user asks for,
   not by shared technology. Same intent with different backends = one skill
   with a mode question (see `noise-emulate`); different intents sharing a
   backend = separate skills (see `validate-emu` vs `noise-emulate`). If you
   cannot write the skill's description in one sentence without an "or", split it.

2. **Frontmatter rules** (`SKILL.md` header):
   - `name`: kebab-case, matches the directory name.
   - `description`: what it does + explicit trigger phrases ("Triggered by
     phrases like …"). This is the ONLY thing the model sees before invoking —
     make it specific. Keep it under ~500 characters.
   - `argument-hint`: **always quote the value.** Unquoted `[a] [b]` is invalid
     YAML (two flow sequences) and silently strips ALL metadata at runtime.
     CI rejects unquoted hints.

3. **Paths**: reference files inside the plugin as
   `${CLAUDE_PLUGIN_ROOT}/skills/<name>/...` — never absolute paths, never
   `~/.claude/skills/...`. Scripts locate siblings relative to themselves
   (`$(dirname "${BASH_SOURCE[0]}")` / `Path(__file__).parent`).

4. **Environment conventions**:
   - Python venv: `${PULSER_VENV:-$HOME/pulser-venv}`.
   - Pasqal Cloud credentials: `PASQAL_USERNAME` / `PASQAL_PASSWORD` /
     `PASQAL_PROJECT_ID` env vars, then `~/.pasqal_credentials.json` (chmod 600).
     Never any other mechanism, never hardcoded.
   - Cluster specifics (SLURM partition/account, remote hosts) are always
     user-supplied variables with neutral defaults — never bake in a site value.

5. **Pipeline contract**: skills interoperate through
   `experiment_spec.json` (produced by `idea-to-spec`) and sequence files
   exporting `build_sequence(device=None, **params)` +
   `compute_observable(counts) -> float` (produced by `spec-to-sequence`).
   New pipeline skills should consume/produce these, not invent parallel formats.

6. **No personal or site-specific information.** No usernames, personal
   hostnames, allocation codes, tokens, or paths from anyone's machine — this
   repo is Apache-2.0 licensed and intended for distribution. CI runs a secret
   scan; review your diff for the rest.

7. **Figures**: save `.png` only.

## Before opening a PR

```bash
bash scripts/check.sh          # validation + syntax + secret scan
claude --plugin-dir .          # dry-run: skills listed? descriptions present?
                               # trigger phrases invoke the right skill?
```

For behavior changes, smoke-test the touched path end-to-end where feasible
(e.g. noise-emulate cloud mode with `--t-list "[100,500]" --shots 100` costs
~1 min of emulator time).

## Releasing

Bump `version` in `.claude-plugin/plugin.json` in the same PR as the change.
Users receive the update via `/plugin marketplace update pasqal`.
