# Neutral Atom Toolkit

**Run an experiment on a neutral-atom quantum computer without first learning
Pulser, the emulator stack, or how hardware access works.** Bring a paper, a
patent or an idea; get a reviewable specification, a working Pulser sequence, an
emulation that tells you whether the signal survives noise, a costed submission
you approve before anything is spent, and an analysis that puts the hardware next
to the prediction.

You keep every scientific decision. The machine-facing work is what this hands
off.

## What it does for you

| You want to | Normally you would | Here you |
|---|---|---|
| Turn a protocol into something runnable | Read the device specification, pick a register, write the pulse code | Point at the paper and answer the questions it left open |
| Know whether it is worth running | Learn an emulator API, guess a noise model | Ask for a local emulation, then a cloud one at full size |
| Get onto a QPU | Find the device, the project, the calibration procedure | Approve a shot count you were shown |
| Read the result | Write the collection and comparison code | Get raw bitstrings, your observable, and an agreement figure |

Each step produces a plain file you can open, correct and re-run. Nothing is
hidden behind a service.

Concretely, this repository is a set of [agent skills](https://agentskills.io):
instructions and tested scripts that a coding agent loads when they are relevant.
You install them into the agent you already use.

## Who it is for

Researchers who can formulate and judge a scientific question and are comfortable
with Python and a coding agent. Internal or external, reproducing published work
or running your own protocol.

**What the agent takes off your hands:** finding the device limits, writing the
register and pulse code, wiring the observable, running emulations, assembling
the submission, collecting and comparing results.

**What stays yours:** the objective, the structuring assumptions, whether the
observable can resolve the physics, the reading of the results, and the decision
to spend anything. The agent proposes, states what it assumed, and asks when the
source does not say. A workflow that runs cleanly is not evidence that the
physics is right.

## Before you install

You need:

- **Python** with `pulser` (plus `numpy`/`scipy`/`matplotlib`). That alone is
  enough to specify an experiment, generate a sequence, and emulate it locally.
- **A Pasqal Cloud account** for the cloud emulator, and one with **QPU access**
  to submit to hardware. Larger local emulation wants a GPU.
- **A cluster account** only for the HPC route (`submit-via-hpc`).

You should know:

- **Account creation, subscription and payment are not part of this toolkit.**
  Nothing here signs you up, buys quota or handles an invoice. Bring access you
  already have; if you do not have it yet, get it through the usual Pasqal
  channels first. Everything up to and including local emulation works without
  any account.
- **QPU shots are metered and a submitted batch cannot be recalled.** The
  submission script prints the full shot count and exits rather than run until
  you have approved it.

## Install

| Agent | How |
|---|---|
| **Claude Code** | `/plugin marketplace add pasqal-io/agent-marketplace` then `/plugin install neutral-atom-toolkit@pasqal` |
| **Kimi Code** | `/plugins install https://github.com/pasqal-io/agent-marketplace`, then `/new` |
| **Codex** | `codex plugin marketplace add pasqal-io/agent-marketplace`, then install from the Plugins view ([details](docs/agents/codex.md)) |
| **Cursor / VS Code / Copilot** | via the root `plugin.json`. Cursor: Customize → Install. VS Code: set `chat.plugins.enabled`, then **Chat: Install Plugin From Source** |
| **DeepSeek Harness** | `git clone`, then link the skills into `~/.agents/skills` ([details](docs/agents/deepseek-harness.md)) |
| **Gemini CLI** | `gemini extensions install https://github.com/pasqal-io/agent-marketplace` |
| **OpenCode** | `git clone`, then `ln -s "$PWD/skills" ~/.agents/skills` |
| **Anything else** | `git clone`; [`AGENTS.md`](AGENTS.md) tells the agent what the skills are |

You do not need to know what a plugin, a skill or a marketplace is to use this.
Run the line for your agent; the skills then appear by name (for example
`/neutral-atom-toolkit:qpu-submit`) and are also triggered by what you ask for
("submit this to the QPU", "run a noise emulation").

Per-agent detail is in [docs/harness-compatibility.md](docs/harness-compatibility.md),
and [docs/porting-to-a-new-harness.md](docs/porting-to-a-new-harness.md) covers
adding one. If an install goes wrong, say which agent and which version: that is
the most useful issue you can open.

Then set up the Python environment and, if you have one, your credentials:
[one-time setup](#one-time-setup).

## Start here

**[docs/tutorial.md](docs/tutorial.md)** walks a first experiment end to end,
with the exact words to type, what each step produces, and the output to expect.
It runs entirely on your machine: no account, no cost.

The short version. Open your agent in an empty directory and say:

> Read arXiv:2302.08963 and turn it into an experiment spec for a neutral-atom
> QPU. Downsize the register so I can emulate it locally first.

The agent will ask you what the paper does not settle, then produce
`<name>_spec.json`, `<name>_sequence.py`, and a local emulation verdict. Read
each file, correct it, and continue when it says what you meant. You can also
enter at any later step: bring your own sequence and ask for an emulation, or
bring batch IDs and ask for the analysis.

## The skills

| Skill | What it does | Needs |
|---|---|---|
| `idea-to-spec` | Turn a paper, a patent, or an experiment idea into `experiment_spec.json`, with its open questions listed | nothing (internet for arXiv) |
| `spec-to-sequence` | Generate a Pulser `*_sequence.py` from a spec, self-testing | Python + `pulser` |
| `validate-emu` | Noiseless and noisy scan, then a go/no-go for QPU. Asks where to run: **locally** (free, ~14 atoms) or **cloud emulator** at the real size | nothing for local; account for cloud |
| `noise-emulate` | Noise emulation with the live device noise model, over time. Runs **locally**, **via SLURM on a GPU cluster**, or **via Pasqal Cloud** | account; GPU only for the first two |
| `qpu-submit` | Calibrated submission of a spec and sequence to a cloud QPU, after you approve the shot count | account with QPU access |
| `submit-via-hpc` | Parametric experiments on a QPU behind an HPC cluster, over SSH. Includes a first-time-access guide | an account on the cluster |
| `harvest-and-analyze` | Collect raw bitstrings, compute the observable, correct for detection error, accept or reject against the emulated baseline | account |

The pipeline order is `idea-to-spec`, `spec-to-sequence`, `validate-emu`,
optionally `noise-emulate`, then `qpu-submit` or `submit-via-hpc`, then
`harvest-and-analyze`. Each step is usable on its own. They interoperate only
through `experiment_spec.json` and a sequence file exporting `build_sequence()`
and `compute_observable()`, so the toolkit carries no experiment of its own and
yours does not have to look like the examples.

Two rules do not bend, and both are enforced in the scripts rather than asked of
the model: **emulation precedes any hardware recommendation**, and **nothing is
submitted without your explicit go-ahead for the shot count you were shown**. A
runner also refuses to resubmit over batch IDs it already recorded, so a dropped
session cannot buy the same shots twice.

## Worked examples

`examples/` holds experiments in exactly the form the pipeline produces: a spec
and a sequence file. They are reading material and CI fixtures, not a path the
product depends on.

| Example | Physics | Observable |
|---|---|---|
| [`literature_z2_reproduction`](examples/literature_z2_reproduction/) | Z₂ ordering and Kibble-Zurek scaling on a 56-atom ring (Keesling *et al.*, Nature **568**, 207 (2019)) | correlation length ξ from the connected correlator G(r) |
| [`triangular_lattice_phases`](examples/triangular_lattice_phases/) | √3×√3 three-sublattice order on a 49-atom triangular patch (Guo *et al.*, [arXiv:2302.08963](https://arxiv.org/abs/2302.08963)) | ⟨\|m\|⟩, the per-shot sublattice order parameter |
| [`square_lattice_eom_quench`](examples/square_lattice_eom_quench/) | transverse-field Ising quench, 25 atoms; unpublished, an end-to-end pipeline test | lattice-averaged occupation ⟨n⟩ |

Each sequence file self-tests when run directly, with no QPU and no credentials,
by asserting its observable against states whose value is known analytically, and
exits non-zero when one fails. `scripts/check.sh` runs all three on every push,
along with manifest validation and a secret scan.

Each README also records the **earlier iteration that was rejected** and why: the
observable that could not resolve the phase, the contract the builder did not
satisfy, the pointers into documents that never existed. The rejected versions
survive under `skills/spec-to-sequence/references/`. Every spec carries its
`objective` and its `open_questions`, so the assumptions still standing are in
the file where a reviewer can find them.

## One-time setup

1. **Python environment**: a venv with `pulser`, `pulser-pasqal`, `pasqal-cloud`,
   numpy/scipy/matplotlib, plus `emu-mps` and `torch` for local or SLURM noise
   emulation (see [skills/noise-emulate/support/requirements.txt](skills/noise-emulate/support/requirements.txt)):

   ```bash
   export PULSER_VENV=~/my-pulser-venv   # skills default to ~/pulser-venv
   ```

   Nothing else is needed for `idea-to-spec`, `spec-to-sequence` and
   `validate-emu`'s local mode.

2. **Pasqal Cloud credentials**, for anything cloud-facing:

   ```bash
   export PASQAL_USERNAME=... PASQAL_PASSWORD=... PASQAL_PROJECT_ID=...
   ```

   Every skill resolves each field from the same three sources, in this order:
   the environment variables above, then the system keyring (password only,
   OS-encrypted, needs `pip install keyring`), then `~/.pasqal_credentials.json`
   (`chmod 600`; a password stored there is plaintext and the skills say so).
   Run any cloud-facing script in a terminal with nothing configured and it
   offers a one-time keyring setup. Because resolution is per field, exporting
   `PASQAL_PASSWORD` alone overrides a stale password in the file.

   Targeting **SA1**? Also set `PASQAL_REGION=sa` (or `"region": "sa"` in the
   credentials file). **Never commit credentials to this or any repo.**

3. **For `submit-via-hpc` only**: an account on the target cluster and an ssh
   alias for it in `~/.ssh/config`. The skill's "Getting access" section covers
   onboarding at the reference site (TGCC).

## Background

The methodology these skills implement, an agentic workflow that carries a
neutral-atom experiment from a paper to hardware with emulation gating every QPU
submission, is described in:

> C. Dalyac, A. Dauphin, L. Henriet, C. Jurczak,
> *Lowering the implementation barrier of neutral-atom quantum computing with
> agentic workflows*, [arXiv:2607.25834](https://arxiv.org/abs/2607.25834) (2026).

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) has the repository layout and the
skill-authoring conventions (frontmatter rules, path and credential conventions,
local-first design, intent-based skill granularity) plus the PR checklist.
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) has the ground rules.

[SECURITY.md](SECURITY.md) covers how credentials are handled, what these skills
can spend on your behalf, and how to report a vulnerability privately.

Dry-run the plugin without installing it:

```bash
claude --plugin-dir .          # sandbox session, nothing installed
bash scripts/check.sh          # manifest validation + examples + secret scan
```
