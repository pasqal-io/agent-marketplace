# Pasqal Agent Marketplace

Home of the **Neutral Atom Toolkit**: agent skills for running Rydberg-atom QPU
experiments end-to-end — from a paper or an idea to submission on neutral-atom
hardware and analysis of the results.

The repository root **is** the `neutral-atom-toolkit` plugin (superpowers-style layout):
`skills/` holds the skills, `.claude-plugin/` holds both the plugin manifest and
the marketplace catalog.

## Install (Claude Code)

```
/plugin marketplace add pasqal-io/agent-marketplace
/plugin install neutral-atom-toolkit@pasqal
```

Skills are namespaced after install: `/neutral-atom-toolkit:qpu-submit`,
`/neutral-atom-toolkit:noise-emulate`, etc. Claude also invokes them automatically from
context ("submit this to the QPU", "run a noise emulation", …).

While the repository is private, your git must be authenticated to GitHub
(SSH key or `gh auth login`) for the marketplace add to work.

**Kimi Code**: `/plugins install https://github.com/pasqal-io/agent-marketplace`
(then `/new`). **Codex**: manifest ready, discoverable once the repo is public —
see [docs/agents/](docs/agents/) for details and other agents.

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `idea-to-spec` | Turn a paper or an experiment idea into `experiment_spec.json` | nothing (internet for arXiv) |
| `spec-to-sequence` | Generate a Pulser `*_sequence.py` from a spec | Python + `pulser` |
| `validate-emu` | Cloud EMU_MPS noiseless + noisy scan → go/no-go for QPU | Pasqal Cloud account |
| `noise-emulate` | Noise emulation with the live device noise model. Asks where to run: **locally**, **via SLURM on a GPU cluster (recommended)**, or **via Pasqal Cloud** (no GPU needed) | Pasqal Cloud account; GPU/cluster only for the first two modes |
| `qpu-submit` | Calibrated submission to a Pasqal Cloud QPU (default FRESNEL_CAN1; SA1 via `PASQAL_REGION=sa`), collection, comparison plots | Pasqal Cloud account with QPU access |
| `submit-to-cea` | Parametric experiments on Ruby (CEA/TGCC) over SSH — includes a first-time-access guide (GENCI project, TGCC account, SSH setup) | A TGCC account; the skill walks new users through getting one |
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

   or `~/.pasqal_credentials.json` (`chmod 600`). Targeting **SA1**? Also set
   `PASQAL_REGION=sa` (or `"region": "sa"` in the credentials file).
   **Never commit credentials to this or any repo.**

3. **For `submit-to-cea` only** — a TGCC account and an `irene` alias in
   `~/.ssh/config`; the skill's "Getting access" section covers onboarding.

## Dry-running the plugin

```bash
claude --plugin-dir .          # sandbox session, nothing installed
bash scripts/check.sh          # manifest validation + syntax + secret scan
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the skill-authoring conventions
(frontmatter rules, path and credential conventions, intent-based skill
granularity) and the PR checklist. `SHARING_NOTES.md` records provenance and
per-skill requirements.
