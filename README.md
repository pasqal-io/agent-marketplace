# Neutral Atom Toolkit

**From an experiment you want to run to a measured result on a neutral-atom
quantum computer, without first learning Pulser, the emulator stack, or how
hardware access works.**

An idea is enough to start: describe what you want to measure. A paper, a patent
or a PDF you want to reproduce is one way of having such an idea, not the only
one. If the idea is still a vague interest, or a problem from your own field
rather than an experiment, the first step is a conversation that turns it into
one: which documented method could serve it, and whether one does at all. What
comes back is a specification you can review, a working Pulser
sequence, an emulation that says whether the signal survives the device's noise,
a costed submission you approve before anything is spent, and an analysis that
puts the hardware next to the prediction.

You keep every scientific decision. The machine-facing work is what this hands
off.

## From an idea to a result

| | You provide | You get |
|---|---|---|
| **0. Frame it** *(if you need it)* | an application, a problem or a hunch, in your own words — a selection to make, data to classify, a phenomenon you are curious about | a conversation that ends in `<name>_idea.md`: at most three documented methods with their maturity and their risks, what would be measured, what size is checkable — or a reasoned "no documented fit", with what would change it |
| **1. Specify** | the experiment you want, described in your own words, or a paper, patent or PDF to reproduce | `<name>_spec.json`: register, pulses, observable, and every question your description or source left open |
| **2. Implement** | your review of that spec | `<name>_sequence.py`: Pulser code that self-tests against states whose value is known by hand |
| **3. Emulate** | nothing for the local run; an account to emulate at the real register size | the scan, noiseless and noisy, and a go/no-go on whether the signal is worth hardware time |
| **4. Submit** | your go-ahead on an itemised shot count | batch IDs on a QPU, or jobs on a cluster |
| **5. Analyse** | those batch IDs | raw bitstrings, your observable applied to them, and how far the hardware sits from the prediction |

Every row leaves a plain file on your disk that you can open, correct and re-run,
and you can enter at any row: bring your own sequence and ask for step 3, or
bring batch IDs and ask for step 5. Those files are ordinary ones: a JSON spec, a
Python file exporting two functions, and one JSON of raw bitstrings per scan
point. `compute_observable(counts: dict[str, int]) -> float` takes shot data and
nothing else, so re-analysing a run, replotting it or publishing it never touches
a vendor library again.

Sequence code is [Pulser](https://github.com/pasqal-io/Pulser), Apache-2.0 and a
`pip install` away; specifying, generating and emulating an experiment needs no
account and no service.

Concretely, this repository is a set of [agent skills](https://agentskills.io):
instructions and tested scripts that a coding agent loads when they are relevant.
You install them into the agent you already use.

## Who it is for

Researchers who can formulate and judge a scientific question and are comfortable
with Python and a coding agent. Internal or external, running a protocol of your
own or reproducing published work.

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
- **An account** for QPU and emulator access. Either: 
	- **A Pasqal Cloud account** for the cloud emulator, and one with **QPU access**
	  to submit to hardware. Larger local emulation wants a GPU.
	- **A cluster account** only for the HPC route (`submit-via-hpc`). If you do not
	  have one yet, there is a skill to help you apply. 

You should know:

- **Account creation, subscription and payment for Pasqal cloud are not part of this toolkit.**
  Nothing here signs you up, buys quota or handles an invoice. Bring access you
  already have; if you do not have it yet, get it through the usual Pasqal
  channels first. Everything up to and including local emulation works without
  any account.
- **QPU shots are metered and a submitted batch cannot be recalled.** The
  submission script prints the full shot count — with the project it would be
  billed to and that project's remaining credits — and exits rather than run
  until you have approved it.
- **Being logged in is not permission to spend.** Credentials found on the
  machine are shown to you, and the project is one you pick: the scripts that
  spend refuse to run on the project id that happens to be in your
  environment.

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

Open your agent in an empty directory and say what you want to measure:

> I want to know whether a square array of about 25 atoms orders
> antiferromagnetically when I ramp the detuning through the transition. Set it
> up so I can emulate it locally first.

The agent comes back with the questions your description does not settle, which
observable should decide it, which part of the ramp matters, whether a register
small enough to emulate still answers anything, and then writes
`<name>_spec.json`, `<name>_sequence.py` and a local emulation verdict. Read each
file, correct it, and continue when it says what you meant.

If your idea is not that concrete yet, or is not an experiment at all, say that
instead — the toolkit starts a step earlier and works it out with you:

> I have access to a neutral-atom machine and I would like to do something with
> it that says something about thermalisation. I don't know what to measure.

Or, when the problem is not physics at all:

> I have to choose about 200 projects out of 900 and some pairs conflict with
> each other. Could a neutral-atom machine do anything useful with that, and
> what would it cost me to find out?

You get questions rather than a spec: what would count as an answer, what you
solve it with today, which documented method could serve it and how mature that
method actually is, which observable could resolve it, what this hardware cannot
do at all, and what size is small enough to check for free before anything is
spent. The result is a short note you review, which then goes through the same
steps as above — or a reasoned no, which is a frequent answer and a much cheaper
one than discovering it three steps later.

To reproduce something instead, hand over the source and the rest is identical:

> Read arXiv:2302.08963 and turn it into an experiment spec for a neutral-atom
> QPU. Downsize the register so I can emulate it locally first.

**[docs/tutorial.md](docs/tutorial.md)** walks the paper case end to end, with
the exact words to type, what each step produces and the output to expect. Every
command and number on that page was run to produce it, on one machine, with no
account and nothing spent.

## The skills

| Skill | What it does | Needs |
|---|---|---|
| `application-to-idea` | *(optional, upstream)* A guided conversation from an application, a problem or a hunch to a first technical idea: which documented method could serve it — MIS, QUBO, an Ising or XY simulation, a graph kernel — with its maturity and its baseline, what would be measured, at what size, and what this hardware cannot do at all | nothing |
| `idea-to-spec` | Turn an experiment you describe, or a paper or patent you want to reproduce, into `experiment_spec.json`, with its open questions listed | nothing (internet for arXiv) |
| `spec-to-sequence` | Generate a Pulser `*_sequence.py` from a spec, self-testing | Python + `pulser` |
| `validate-emu` | Noiseless and noisy scan, then a go/no-go for QPU. Asks where to run: **locally** (free, ~14 atoms) or **cloud emulator** at the real size | nothing for local; account for cloud |
| `noise-emulate` | *(optional)* Noise emulation with the live device noise model, over time — where in the pulse the signal is lost. Runs **locally**, **on a GPU cluster**, or **via Pasqal Cloud** | account; GPU only for the first two |
| `qpu-submit` | Calibrated submission of a spec and sequence to a cloud QPU, after you approve the shot count | account with QPU access |
| `submit-to-cea` | Parametric experiments on Ruby, the QPU at CEA/TGCC, over SSH. Includes a first-time-access guide, and says what a sibling cluster needs changed | an account on the cluster |
| `harvest-and-analyze` | Collect raw bitstrings, compute the observable, correct for detection error, accept or reject against the emulated baseline | account |
| `apply-genci-tgcc-cea` | Apply for QPU time at the Genci CEA QPU for open research | nothing (internet)|

The pipeline order is optionally `application-to-idea`, then `idea-to-spec`,
`spec-to-sequence`, `validate-emu`, optionally `noise-emulate`, then
`qpu-submit` or `submit-to-cea`, then `harvest-and-analyze`. The two optional
ones are offered, never assumed: `application-to-idea` only if you do not yet
have an experiment, `noise-emulate` only when you want to know *how* the noise
gets there. Each step is usable on its own. They interoperate only
through `experiment_spec.json` and a sequence file exporting `build_sequence()`
and `compute_observable()`, so the toolkit carries no experiment of its own and
yours does not have to look like the examples.

Three rules do not bend, and all three are enforced in the scripts rather than
asked of the model: **emulation precedes any hardware recommendation**,
**nothing is submitted without your explicit go-ahead for the shot count you
were shown**, and **no run bills a project you did not name**. A runner also
refuses to resubmit over batch IDs it already recorded, so a dropped session
cannot buy the same shots twice.

Everything one experiment produces lands in one tree, as it is produced:
`experiments/<name>/` holds the spec, the sequence, `notes/`, `analysis/`,
`figures/`, `results/<stage>/`, and a `NOTEBOOK.md` that each step appends to —
where it ran, the command, the files written, the numbers. Nothing is left in
your working directory's root, and no number reaches you that is not in a file
you can open.

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
   numpy/scipy/matplotlib, plus `emu-mps` and `torch` for local or cluster noise
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

   `PASQAL_PROJECT_ID` is a convenience, not a decision: every script that
   spends credits requires `--project-id` explicitly, and
   `python <skill>/support/pasqal_auth.py --whoami` prints — free, read-only,
   never a password or a token — which account was found, where each field came
   from, and what each of your projects has left in QPU and EMU credits.

   Every skill resolves each field from the same three sources, in this order:
   the environment variables above, then the system keyring (password only,
   OS-encrypted, needs `pip install keyring`), then `~/.pasqal_credentials.json`
   (`chmod 600`; a password stored there is plaintext and the skills say so).
   Run any cloud-facing script in a terminal with nothing configured and it
   offers a one-time keyring setup. Because resolution is per field, exporting
   `PASQAL_PASSWORD` alone overrides a stale password in the file.

   Targeting **SA1**? Also set `PASQAL_REGION=sa` (or `"region": "sa"` in the
   credentials file). **Never commit credentials to this or any repo.**

3. **For `submit-to-cea` only**: an account on the cluster and an ssh
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
