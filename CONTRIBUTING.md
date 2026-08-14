# Contributing

## Repository layout

The repo root is the `neutral-atom-toolkit` plugin:

```
plugin.json           Agent Plugins 1.0 manifest (root; closed schema)
AGENTS.md             skill index for harnesses with no skill mechanism
GEMINI.md             one-line include of AGENTS.md, declared by the line below
gemini-extension.json Gemini CLI extension manifest
.claude-plugin/
  plugin.json         plugin manifest (bump `version` to publish an update)
  marketplace.json    marketplace catalog (this repo lists itself via source "./")
.codex-plugin/
  plugin.json         Codex manifest (`"hooks": {}` suppresses hook auto-discovery)
.agents/plugins/
  marketplace.json    Codex marketplace catalog — the path Codex actually reads
.kimi-plugin/
  plugin.json         Kimi Code manifest + `skillInstructions` tool mapping
skills/<name>/
  SKILL.md            frontmatter + instructions (the skill itself)
  support/            scripts the skill runs (Python/bash)
  templates/          files the skill instantiates
  references/         reference implementations the skill reads
examples/<name>/      worked experiments: a spec + sequence pair, as the
                      pipeline would produce them
scripts/check.sh      repo health checks (CI runs this)
docs/agents/          per-agent installation notes
docs/harness-compatibility.md      which agents work, and how
docs/porting-to-a-new-harness.md   how to add one
```

`skills/` is shared verbatim by every harness and **never forked**. Skills name
*actions* ("ask the user", "run this script"), never a harness's tool; a tool
mapping belongs in that harness's adapter manifest — see
`.kimi-plugin/plugin.json`'s `skillInstructions`. CI rejects proprietary tool
names, harness-specific variables and private config paths anywhere under
`skills/`, and rejects a skill missing from `AGENTS.md`.

Skills carry no experiment of their own. Physics belongs in `examples/`, reached
through the `experiment_spec.json` contract — see
`examples/square_lattice_eom_quench/README.md` for why.

Code shared between skills is **vendored**: one byte-identical copy per
`support/` directory (today, `pasqal_auth.py`). A skill has to keep working when
a harness installs it alone, and `support/` is what gets copied to a cluster, so
a single repo-level `lib/` would break both. Edit one copy, then copy it over the
others — `scripts/check.sh` fails while they differ and names the odd ones out.

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

3. **Paths**: reference bundled files **relative to the skill's directory**
   (`support/foo.py`, `templates/bar.sh`) with a note that they resolve against
   the skill's location — never absolute paths, never `~/.claude/skills/...`,
   and never harness-specific variables like `${CLAUDE_PLUGIN_ROOT}` (CI rejects
   them; they break Codex/Kimi/Cursor portability). Scripts locate siblings
   relative to themselves (`$(dirname "${BASH_SOURCE[0]}")` / `Path(__file__).parent`).

4. **Environment conventions**:
   - Python venv: `${PULSER_VENV:-$HOME/pulser-venv}`.
   - Pasqal Cloud credentials: **`from pasqal_auth import load_credentials`**,
     never a loader of your own — CI rejects a second one. It resolves each
     field from env vars, then the system keyring (password only), then
     `~/.pasqal_credentials.json` (chmod 600), and returns exactly the keyword
     arguments both clients take: `SDK(**load_credentials())`,
     `PasqalCloud(**load_credentials())`. Never hardcode a credential.
     The one exception is `submit-via-hpc/templates/submit_template.py`, which
     runs inside a container on a compute node where no keyring exists; it reads
     env vars only and says so in a comment.
   - Device selection: default `FRESNEL_CAN1`, always overridable (`--device` /
     `--device-name` / `spec["device"]`); region via `PASQAL_REGION` (`fr`
     default, `sa` for SA1). Never hardcode a device inside a script body.
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

The plugin version lives in **six** manifests and they must agree — `scripts/check.sh`
fails the build if they drift:

```
plugin.json                         version
.claude-plugin/plugin.json          version
.claude-plugin/marketplace.json     metadata.version
.codex-plugin/plugin.json           version
.kimi-plugin/plugin.json            version
gemini-extension.json               version
```

Bump all six in the same PR as the change; a new manifest goes into
`VERSION_FIELDS` in `scripts/check_manifests.py` in the same PR, or it ships
stale. Users receive the update via `/plugin marketplace update pasqal` (Claude
Code), a reinstall + `/new` (Kimi Code), `codex plugin marketplace update`
(Codex), or `gemini extensions update` (Gemini CLI).
