# Pasqal Agent Marketplace

Home of the **Neutral Atom Toolkit**: agent skills for running Rydberg-atom QPU
experiments end-to-end — from a paper or an idea to submission on neutral-atom
hardware and analysis of the results.

The repository root **is** the `neutral-atom-toolkit` plugin (superpowers-style
layout). One shared `skills/` directory follows the
[Agent Skills](https://agentskills.io) open standard — all paths inside skills
are relative to each skill's directory, no harness-specific variables, never
forked per agent — and thin manifests adapt it to each harness:

```
skills/            the 7 skills (shared verbatim by every agent)
plugin.json        Agent Plugins 1.0 manifest — the one file every conformant
                   client must read (Cursor, VS Code, Copilot, Codex, Kiro)
AGENTS.md          skill index for agents with no plugin mechanism at all
.claude-plugin/    Claude Code plugin manifest + self-hosted marketplace catalog
.codex-plugin/     OpenAI Codex manifest
.agents/plugins/   Codex marketplace catalog
.kimi-plugin/      Kimi Code manifest (+ Kimi tool mapping)
gemini-extension.json + GEMINI.md   Gemini CLI extension (includes AGENTS.md)
docs/agents/       per-agent install guides and adapter notes
```

## Install

| Agent | How |
|---|---|
| **Claude Code** | `/plugin marketplace add pasqal-io/agent-marketplace` then `/plugin install neutral-atom-toolkit@pasqal` |
| **Kimi Code** | `/plugins install https://github.com/pasqal-io/agent-marketplace`, then `/new` |
| **Codex** | `codex plugin marketplace add pasqal-io/agent-marketplace`, then install from the Plugins view — [details](docs/agents/codex.md) |
| **Cursor / VS Code / Copilot** | via the root `plugin.json` — Cursor: Customize → Install; VS Code: set `chat.plugins.enabled`, then **Chat: Install Plugin From Source** |
| **Gemini CLI** | `gemini extensions install https://github.com/pasqal-io/agent-marketplace` |
| **OpenCode** | `git clone`, then `ln -s "$PWD/skills" ~/.agents/skills` |

Skills are namespaced after install (e.g. `/neutral-atom-toolkit:qpu-submit`,
`/neutral-atom-toolkit:noise-emulate`) and are also invoked automatically from
context ("submit this to the QPU", "run a noise emulation", …).

Full matrix, including what has been exercised and what has only been
transcribed from a vendor's docs:
[docs/harness-compatibility.md](docs/harness-compatibility.md). Adding an agent:
[docs/porting-to-a-new-harness.md](docs/porting-to-a-new-harness.md).

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `idea-to-spec` | Turn a paper, a patent, or an experiment idea into `experiment_spec.json` | nothing (internet for arXiv) |
| `spec-to-sequence` | Generate a Pulser `*_sequence.py` from a spec | Python + `pulser` |
| `validate-emu` | Cloud EMU_MPS noiseless + noisy scan → go/no-go for QPU | Pasqal Cloud account |
| `noise-emulate` | Noise emulation with the live device noise model. Asks where to run: **locally**, **via SLURM on a GPU cluster (recommended)**, or **via Pasqal Cloud** (no GPU needed) | Pasqal Cloud account; GPU/cluster only for the first two modes |
| `qpu-submit` | Calibrated submission of a spec + sequence to a Pasqal Cloud QPU (default FRESNEL_CAN1; SA1 via `PASQAL_REGION=sa`) | Pasqal Cloud account with QPU access |
| `submit-via-hpc` | Parametric experiments on a QPU behind an HPC cluster, over SSH — includes a first-time-access guide. Reference site: Ruby at CEA/TGCC | An account on the cluster; the skill walks new users through getting one |
| `harvest-and-analyze` | Collect QPU bitstrings, compute observable, accept/reject vs EMU | Pasqal Cloud account |

## One-time setup

1. **Python environment** — a venv with `pulser`, `pulser-pasqal`, `pasqal-cloud`,
   numpy/scipy/matplotlib (plus `emu-mps` + `torch` for local/SLURM noise
   emulation — see [skills/noise-emulate/support/requirements.txt](skills/noise-emulate/support/requirements.txt)):

   ```bash
   export PULSER_VENV=~/my-pulser-venv   # skills default to ~/pulser-venv
   ```

2. **Pasqal Cloud credentials** — environment variables

   ```bash
   export PASQAL_USERNAME=... PASQAL_PASSWORD=... PASQAL_PROJECT_ID=...
   ```

   Every skill resolves each field from the same three sources, in this order:
   the environment variables above, then the system keyring (password only —
   OS-encrypted, needs `pip install keyring`), then `~/.pasqal_credentials.json`
   (`chmod 600`; a password stored there is plaintext and the skills say so).
   Run any cloud-facing script in a terminal with nothing configured and it
   offers a one-time keyring setup. Because resolution is per field, exporting
   `PASQAL_PASSWORD` alone overrides a stale password in the file.

   Targeting **SA1**? Also set `PASQAL_REGION=sa` (or `"region": "sa"` in the
   credentials file). **Never commit credentials to this or any repo.**

3. **For `submit-via-hpc` only** — an account on the target cluster and an ssh
   alias for it in `~/.ssh/config`; the skill's "Getting access" section covers
   onboarding at the reference site (TGCC).

## Dry-running the plugin

```bash
claude --plugin-dir .          # sandbox session, nothing installed
bash scripts/check.sh          # manifest validation + syntax + secret scan
```

## Background

The methodology these skills implement — an agentic workflow that carries a
neutral-atom experiment from a paper to hardware, with emulation gating every
QPU submission — is described in:

> C. Dalyac, A. Dauphin, L. Henriet, C. Jurczak,
> *Lowering the implementation barrier of neutral-atom quantum computing with
> agentic workflows*, [arXiv:2607.25834](https://arxiv.org/abs/2607.25834) (2026).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the skill-authoring conventions
(frontmatter rules, path and credential conventions, intent-based skill
granularity) and the PR checklist. `SHARING_NOTES.md` records provenance and
per-skill requirements.
