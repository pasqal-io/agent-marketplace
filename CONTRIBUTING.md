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
.github/
  workflows/ci.yml    the only workflow; read-only token, SHA-pinned actions
  CODEOWNERS          review routing (inert until a ruleset requires it)
  dependabot.yml      version updates for actions + the one requirements.txt
  rulesets/main.json  branch protection, to import — see "Repository protection"
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
A skill that asks for a separate (sub)agent or fresh context must say what to do
when the harness does not provide such access.

Skills carry no experiment of their own. Physics belongs in `examples/`, reached
through the `experiment_spec.json` contract — see
`examples/square_lattice_eom_quench/README.md` for why.

The dependency arrow runs one way: an example may cite a skill, never the
reverse. CI rejects an import or a script path from `skills/` into `examples/`,
because a skill installed on its own — the normal case — has no `examples/`
directory next to it. A Markdown link is documentation and is allowed.

Code shared between skills is **vendored**: one byte-identical copy per
`support/` directory (today `pasqal_auth.py`, `batch_tags.py` and
`spec_noise.py`). A skill has to keep working when
a harness installs it alone, and `support/` is what gets copied to a cluster, so
a single repo-level `lib/` would break both. Edit one copy, then copy it over the
others — `scripts/check.sh` fails while they differ and names the odd ones out.

## Adding or changing a skill

1. **One skill = one user intent.** Split skills by what the user asks for,
   not by shared technology. Same intent with different backends = one skill
   with a mode question (see `noise-emulate`); different intents sharing a
   backend = separate skills (see `validate-emu` vs `noise-emulate`). If you
   cannot write the skill's description in one sentence without an "or", split it.

2. **Local first, remote when it matters.** Whatever a skill does, there should
   be a way to run it on the user's own machine — smaller, rougher, free — before
   anything reaches a cloud emulator, a cluster or a QPU. Someone with no account
   should still get a real answer out of the toolkit, and someone with an account
   should have found their implementation errors before paying for shots. Where
   the local version is genuinely weaker, say so *in the artefact*, not just in
   prose: `validate-emu`'s local verdict carries `"gates_hardware": false`. A
   local mode that quietly claims the authority of the remote one is worse than
   no local mode.

3. **Frontmatter rules** (`SKILL.md` header):
   - `name`: kebab-case, matches the directory name.
   - `description`: what it does + explicit trigger phrases ("Triggered by
     phrases like …"). This is the ONLY thing the model sees before invoking —
     make it specific. Keep it under ~500 characters.
   - `argument-hint`: **always quote the value.** Unquoted `[a] [b]` is invalid
     YAML (two flow sequences) and silently strips ALL metadata at runtime.
     CI rejects unquoted hints.

4. **Paths**: reference bundled files **relative to the skill's directory**
   (`support/foo.py`, `templates/bar.sh`) with a note that they resolve against
   the skill's location — never absolute paths, never `~/.claude/skills/...`,
   and never harness-specific variables like `${CLAUDE_PLUGIN_ROOT}` (CI rejects
   them; they break Codex/Kimi/Cursor portability). Scripts locate siblings
   relative to themselves (`$(dirname "${BASH_SOURCE[0]}")` / `Path(__file__).parent`).

5. **A SKILL.md and the files it ships describe each other.** CI checks both
   directions: a cited `support/…` path must exist, and every file under
   `support/`, `templates/` or `references/` must be named somewhere in the
   SKILL.md. Nothing else indexes a skill's own files, so an undocumented one is
   invisible to the model that would use it. Delete it or document it — a
   template that contradicts the skill's own guidance is worse than no template.
   Paths written `<other-skill>/support/x.py` are placeholders for another
   skill's install location and are not checked.

6. **Environment conventions**:
   - Python venv: `${PULSER_VENV:-$HOME/pulser-venv}`.
   - Pasqal Cloud credentials: **`from pasqal_auth import load_credentials`**,
     never a loader of your own — CI rejects a second one. It resolves each
     field from env vars, then the system keyring (password only), then
     `~/.pasqal_credentials.json` (chmod 600), and returns `(creds, sources)`
     where `creds` is exactly the keyword arguments both clients take:

     ```python
     creds, _ = load_credentials()
     client = PasqalCloudClient(**creds)   # pasqal_cloud.pasqal_cloud_client
     conn   = PasqalCloudConnection(**creds)  # pasqal_cloud
     ```

     `sources` says where each field actually came from, which is what
     `--whoami` reports. Never hardcode a credential. Do not reach for `pasqal_cloud.SDK` or
     `pulser_pasqal.PasqalCloud`: both are deprecated aliases of those two, and
     pulser-pasqal pins an incompatible pasqal-cloud.
     A script that **spends** credits — QPU shots or emulator time — calls
     `ensure_credentials(project_id=args.project_id,
     require_explicit_project=True)` and exposes `--project-id`: an environment
     variable is not a decision, and `pasqal_auth.py --whoami` is the free,
     read-only way to show the user their projects and credits first. Both
     loaders return `(creds, sources)`, so splat the first element:
     `creds, _ = ensure_credentials(...)`. Print the account block from
     `account_summary(...)` in whatever plan you ask them to approve. The one
     exception is `submit-to-cea/templates/submit_template.py`, which runs
     inside a container on a compute node where no keyring exists; it reads env
     vars only and says so in a comment.
   - Batch labels: **`from batch_tags import build_tags`**. Every batch a skill
     submits is tagged, with the stage it belongs to — an untagged batch is a
     paid result nobody can find again.
   - A noise model that came from the source: **`import spec_noise`** and
     `spec_noise.resolve(args.noise_source, spec, device_noise,
     overridable_noise_params)`. Print the difference, let the user choose,
     never substitute silently.
   - Device selection: default `FRESNEL_CAN1`, always overridable (`--device` /
     `--device-name` / `spec["device"]`); region via `PASQAL_REGION` (`fr`
     default, `sa` for SA1). Never hardcode a device inside a script body.
   - Cluster specifics (SLURM partition/account, remote hosts) are always
     user-supplied variables with neutral defaults — never bake in a site value.

7. **Pipeline contract**: skills interoperate through
   `experiment_spec.json` (produced by `idea-to-spec`) and sequence files
   exporting `build_sequence(device=None, **params)` +
   `compute_observable(counts) -> float` (produced by `spec-to-sequence`).
   New pipeline skills should consume/produce these, not invent parallel formats.

8. **No personal or site-specific information.** No usernames, personal
   hostnames, allocation codes, tokens, or paths from anyone's machine — this
   repo is Apache-2.0 licensed and intended for distribution. CI runs a secret
   scan; review your diff for the rest.

9. **Figures**: save `.png` only.

## Adding an example

An example is three files named after its directory —
`examples/<name>/{README.md, <name>_spec.json, <name>_sequence.py}` — and CI
checks that the spec's `experiment_name`, `sequence_file` and `builder_fn` agree
with them. The README documents commands that pass those filenames to the skills,
so a half-finished rename breaks both.

The sequence file **must self-test under `if __name__ == "__main__"`, and must
exit non-zero when a check fails.** `scripts/check.sh` runs every example, and
this is the only place in the repo where the physics actually executes — QPU
submission is never part of CI. Compare the observable against states whose value
you can derive by hand (a vacuum, a saturated register, a perfectly ordered
pattern, an analytically solvable ensemble) rather than against a number a
previous run happened to print. A value that is printed but not compared lets a
broken observable pass while still looking plausible.

State the finite-size floor of your observable if it has one. ⟨|m|⟩ in
`triangular_lattice_phases` reads 0.18 on a *disordered* 49-atom array, so a
measurement of 0.18 is no evidence of order; the smoke test prints the floor next
to the measurement so the comparison cannot be skipped.

If the register was sized against Pulser's bundled device rather than live device
specifications, say so in `_notes` — `validate-emu` runs against the real device
and will reject a spec that only fits the stand-in.

## Before opening a PR

```bash
bash scripts/check.sh          # everything CI runs, in the same order
claude --plugin-dir .          # dry-run: skills listed? descriptions present?
                               # trigger phrases invoke the right skill?
```

`scripts/check.sh` is the single entry point, and CI runs nothing else. It covers,
in order: the Claude CLI's manifest validation, JSON syntax for every adapter
manifest, the static conformance checks in `scripts/check_manifests.py`,
`py_compile`, the example smoke tests, `--help` on every support script, the
secret scan, and the `argument-hint` YAML trap.

Two of those need Pulser and are **skipped** without it, which is why CI installs
a pinned version — see below. Run them locally with
`PULSER_VENV=<path> bash scripts/check.sh`; a skipped gate says so on the line
where it would have run.

When you add a gate, break it on purpose once and confirm it fails. A check that
cannot fail is worse than no check, because it reads as coverage: the example
smoke tests originally printed their numbers without comparing them and passed
with the physics broken.

For behavior changes, smoke-test the touched path end-to-end where feasible
(e.g. noise-emulate cloud mode with `--t-list "[100,500]" --shots 100` costs
~1 min of emulator time). QPU submission is never part of CI.

## Repository protection

The rules above — reviewed PR, CI green before merge, never merge your own — are
**not currently enforced by GitHub.** Protected branches and rulesets are
unavailable for a private repository on this organisation's plan; both API
endpoints answer `403 Upgrade to GitHub Pro or make this repository public`. So
`main` today accepts a direct push, a force-push and a deletion from anyone with
write access, and a PR can be self-merged with red CI. Treat the rules as
conventions you are trusted to follow, and know that nothing catches a slip.

`.github/rulesets/main.json` is the configuration to apply the moment that
changes — either when the repository goes public, or on a plan that allows it.
GitHub does not read that file: import it at **Settings → Rules → Rulesets → New
ruleset → Import a ruleset**. It requires one approving review, Code Owner
review, a passing `check` status, approval of the last push (which is what
mechanically stops self-merging), and blocks force-pushes and deletion with no
bypass actors — including admins. `.github/CODEOWNERS` is what the Code Owner
rule reads, and its owner list needs a human decision before it means anything.

What CI can enforce without any of this is already in `scripts/check.sh`. What it
cannot is who approved the merge.

Two settings that *are* live, and worth not regressing: the workflow token is
read-only (`Settings → Actions → Workflow permissions`) and Actions cannot
approve pull requests. `.github/workflows/ci.yml` also declares
`permissions: contents: read` at the top, so the job keeps least privilege even
if the repository default is ever widened again.

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

**Every change that should reach users bumps the version — at least the minor
one.** Harnesses compare the installed version with the published one; a merge
without a bump is not deployed, and users keep the old skills without any error.

Bump all six in the same PR as the change; a new manifest goes into
`VERSION_FIELDS` in `scripts/check_manifests.py` in the same PR, or it ships
stale.

**The Pulser version is pinned once, in `.github/workflows/ci.yml`.** Any file
claiming a tested version must name that one — CI compares them, because they
drifted before and users installed a version nothing had exercised. Two places
deliberately differ and are not compared: `noise-emulate/support/requirements.txt`
keeps a floor rather than a pin, so users are not forced onto one release, and
`submit-to-cea/support/setup_cea_env.sh` installs from offline zips inside an
air-gapped container, where the version is whatever was last validated there.
Bumping the pin is its own PR: the examples assert on device constants Pulser
ships, so a bump can legitimately move the expected numbers. Users receive the update via `/plugin marketplace update pasqal` (Claude
Code), a reinstall + `/new` (Kimi Code), `codex plugin marketplace update`
(Codex), or `gemini extensions update` (Gemini CLI).
