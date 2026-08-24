---
name: validate-emu
description: Scan an experiment_spec.json and its sequence file, noiseless and noisy, and return a go/no-go decision on whether the signal survives device noise well enough to be worth hardware time. Asks where to run: locally (free, small registers, offered first) or on cloud emulators at the real size. This is the gate before a QPU submission, not the submission. Triggered by phrases like "validate with EMU", "run an emulation scan", "check noise retention", "is this worth submitting to hardware".
argument-hint: "[spec-file] [seq-file]"
---

# validate-emu

Run noiseless + noisy scans of a spec, compute the target observable, and decide
whether the signal survives device noise well enough to justify QPU shots.

**Rule: never submit to QPU without a passing cloud verdict first** — see the
scope note at the end of Step 2a for why a local GO is not that verdict.

---

## Support scripts

Paths like `support/…` below are relative to **this skill's directory** —
expand them to the skill's absolute location when running commands from your
project directory (keep outputs like `--out-dir` in your project, not the plugin).

```
support/
  run_local_scan.py    ← local emulator scan, no account, no cost (start here)
  run_emu_scan.py      ← cloud scan submission, polling, observable computation
  plot_emu_scan.py     ← scan curve figure (reads either scan's output)
  pasqal_auth.py       ← Pasqal Cloud credential loading (shared, do not edit here)
```

Python environment: `source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"`
Credentials (cloud mode only): `$PASQAL_USERNAME` / `$PASQAL_PASSWORD` /
`$PASQAL_PROJECT_ID`, or `~/.pasqal_credentials.json`

---

## What this skill needs

1. `<experiment_name>_spec.json` — from `idea-to-spec`
2. `<experiment_name>_sequence.py` — from `spec-to-sequence`

Check both files exist and that `spec["sequence_file"]` matches the actual filename.

---

## Step 1 — Verify sequence smoke test

Before emulating anything:

```bash
source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"
python <experiment_name>_sequence.py
```

Must print: `Sequence OK: <duration> ns, <N> atoms` with no errors.
If it fails, stop and fix the sequence file before proceeding.

---

## Step 2 — Ask where to run, and offer local first

Both modes produce the same three files, so nothing downstream cares which ran.
Ask the user, and say what each one buys:

| | **2a — this machine** | **2b — cloud emulator** |
|---|---|---|
| Needs | nothing but the Python environment | an account with emulator access |
| Register | up to ~14 atoms (exact state vector) | the real size, up to N ≳ 60–100 |
| Noise | a documented stand-in, or the live model with `--live-device` | the live device's own model |
| Cost | seconds to minutes, free | queue time, metered |
| Answers | is the implementation right, does the observable move | does the signal survive real noise at real size |

**Default to 2a when the register is small enough or can be shrunk for a check,
and run 2b before recommending hardware.** A user without an account can still
get everything 2a gives — say so rather than stopping at the credential error.

### Why the small run first — explain this, do not just do it

A user who is told "I will run a downsized emulation first" hears a delay. Tell
them what it buys, in one or two sentences of their experiment's terms:

Nearly everything that goes wrong at this stage is an **implementation** error,
not physics: a structure-factor wavevector with the wrong sign, an observable
that returns the same number at every scan point, a ramp too fast to be
adiabatic, a register that violates the device's spacing limit. On a downsized
run those cost seconds and are obvious. Arriving as QPU data they are
indistinguishable from "the physics is not there" — the shots are spent, and the
null result cannot be interpreted. The small run is what makes a null result at
full size mean something.

Say equally plainly what it does not settle: a transition sharpens with N, so a
9-atom stand-in can show a feature that is a finite-size artefact or miss one
that only develops at scale. Small **then** full size — and "full size" often
exists only on hardware, which is fine; what is not fine is quoting the small
run as if it were the full-size result.

### Emulation budget — the ladder, and where each rung stops

When the user proposes a size, place it on this ladder rather than answering yes
or no:

| Rung | Reach | Cost | Note |
|---|---|---|---|
| 2a, exact state vector (this skill) | ~14 atoms noiseless, ~12 noisy | seconds, free | cost is 2^N; a wall, not a tuning parameter |
| MPS locally or on a GPU cluster (`noise-emulate`) | tens of atoms | free, minutes to hours | accuracy depends on the bond dimension χ — see below |
| 2b, cloud MPS emulator | the real size, degrading past N ≳ 60–100 | queue time, metered | the only verdict that gates hardware |

**If the user wants a big register on their own machine** — 60 atoms locally by
lowering χ, say — the answer is not a χ to find. **Do not go looking for the
right bond dimension.** χ caps the entanglement the MPS can hold, so a truncated
run still prints a smooth, plausible, quietly wrong curve; but hunting for the χ
where that stops is days of runs for a number nobody can defend, and at a size
that matters no χ is ever large enough. Treat it as a two-way decision, not an
optimisation:

- **Small enough that the emulator's default χ is already calibrated** → run it,
  once, and move on. No convergence study. (`noise-emulate` records what its
  default covers.)
- **Bigger than that** → stop emulating the full register. Build a **sub-system**
  instead: a smaller register that keeps the physics — same geometry motif, same
  R_b/a, same protocol shape — and reproduces something approaching the target
  signal. Validate the *approach* there, then let the real size be measured on
  the QPU. That is what hardware is for.

Say the division of labour out loud, because it is the point: the emulator's job
is to establish that the protocol and the observable work, and the QPU's job is
to give the full-size number. An emulation of the full register is a bonus when
it is affordable, never the thing the plan depends on.

---

## Step 2a — Local scan (no account, no cost)

```bash
source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"

python support/run_local_scan.py \
    --spec       <experiment_name>_spec.json \
    --seq-file   <experiment_name>_sequence.py \
    --out-dir    <spec.output_dir>/emu_local/ \
    [--shots 200] [--noiseless-only] \
    [--seq-kwargs '{"N": 3}']      # shrink the register for the check
```

Exact state-vector emulation, so cost is 2^N: the script refuses past
`--max-atoms` (default 14) rather than hanging, and names the two paths that
handle larger registers. If the spec's register is too big, do not raise the
limit — pass `--seq-kwargs` with whatever parameter your builder uses to reduce
it, and report that the check ran downsized.

`--live-device` fetches the real device's specs and noise model and still
emulates locally. That costs no emulator time, only credentials, and is the
sharpest local check available.

**Scope.** `verdict.json` from this mode carries `"gates_hardware": false`. A
local GO means the implementation is sound and the observable responds to the
scan — a genuine result, and the cheapest way to find the errors that would
otherwise be found with paid shots. It does not mean the signal survives on
hardware at the real size, which is Step 2b's question. Never present a local GO
to the user as authorisation to submit.

---

## Step 2b — Cloud scan (real size, live noise model)

```bash
source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"

python support/run_emu_scan.py \
    --spec     <experiment_name>_spec.json \
    --seq-file <experiment_name>_sequence.py \
    --out-dir  <spec.output_dir>/emu/ \
    [--shots   <override>] \
    [--poll    30]
```

**If the session drops while polling, add `--resume`** — never re-run the plain
command. A submission is not idempotent: it creates a fresh pair of batches per
scan point, so a plain re-run buys the whole scan twice. The script refuses to
run at all while `<out-dir>/batch_ids.json` exists; `--resume` polls the batches
that file records and resubmits nothing. It also refuses to resume if the spec's
scan no longer matches what was submitted, because the verdict would then be
attributed to a spec the hardware never ran.

The script:
1. Fetches the live device from the cloud
2. Builds a non-parametric sequence for each scan point (calls `build_sequence(**params)`)
3. Submits noiseless + noisy EMU_MPS batches for each point in parallel (non-blocking)
4. Saves `batch_ids.json` immediately (crash recovery)
5. Polls all batches until DONE
6. Calls `compute_observable(counts)` for each point
7. Writes `emu_noiseless.json`, `emu_noise.json`, `verdict.json`

**Noise model applied**: the live device's shipped noise model (T₂, temperature,
detuning_sigma, SPAM p_fp/p_fn, relaxation_rate, amp_sigma), repackaged into the
subset of fields cloud EMU_MPS supports. The effective values are recorded in
`emu_noise.json` under `noise_params`.

**Register size limit**: cloud EMU_MPS accuracy degrades, and the job can run out
of memory, somewhere around **N ≳ 60–100 atoms** — the exact point depends on how
entangled the state gets, not on N alone. A no-go verdict on a register that
large is not automatically physics: check the batch actually completed before
reporting it, and tell the user which of the two you are looking at. For a
register in that range, confirm the observable behaves as expected at a smaller N
first — that is exactly what Step 2a is for, and it costs nothing.

**Typical wall time**: a few minutes to a few hours depending on cloud queue depth.
Run in the background for large scans:
```bash
python support/run_emu_scan.py ... \
    > <spec.output_dir>/emu/run.log 2>&1 &
tail -f <spec.output_dir>/emu/run.log
```

---

## Step 3 — Plot the scan

```bash
python support/plot_emu_scan.py \
    --noiseless <spec.output_dir>/emu/emu_noiseless.json \
    --noisy     <spec.output_dir>/emu/emu_noise.json \
    --out       <spec.output_dir>/emu/emu_scan.png \
    --verdict   <spec.output_dir>/emu/verdict.json \
    --title     "<experiment_name>"
```

---

## Step 4 — Interpret the verdict

Read `verdict.json`:
```json
{
  "go": true,
  "reasons": ["noise retention 77% ≥ 50% — signal expected to survive QPU noise"],
  "nl_max": 0.092,
  "n_max":  0.071,
  "retention": 0.77
}
```

A local verdict carries two extra fields — `"scope": "local emulator"` and
`"gates_hardware": false` — plus a `reasons` line for every way it falls short of
the cloud verdict (downsized register, stand-in noise model). **Read them before
quoting the verdict.** "GO, locally, on 9 of the 25 atoms, with a stand-in noise
model" is a useful sentence; "GO" on its own, from that file, is a false one.

**GO** — signal survives noise, QPU submission is justified.
**NO-GO** — signal too degraded. Options:
- Reduce system size (smaller N → less decoherence)
- Shorten pulse duration (less exposure to dephasing)
- Adjust scan range to better centre on the transition
- Ask the user before proceeding

---

## Step 4b — Offer a noise study, do not impose one

This scan gives one number per scan point, noiseless and noisy. It does not show
*how* the noise got there. `noise-emulate` does: it emulates the time evolution
under the live noise model and returns the trajectory envelope, which answers a
different question — where in the pulse the signal is lost, and whether the
spread comes from stochastic noise or from calibration uncertainty.

It is **optional**, it is not a gate, and it costs GPU or emulator time. So
offer it, with the reason it might be worth their time, and accept "no":

- **After a NO-GO** — the most useful case. "The signal drops to 31% of the
  noiseless peak. A noise emulation over time would show whether that happens
  early in the ramp, which would point at dephasing and a shorter protocol, or
  only at the end, which would point at readout. Worth a run before we change
  the protocol blind?"
- **After a GO, before spending real shots** — only if the margin is thin, or if
  the user intends to buy a large scan: an envelope says how much of the
  variation to expect shot to shot, so a QPU point inside it is not a surprise.
- **Not at all** when the retention is comfortable and the user wants to submit.
  Proposing every optional step every time trains them to ignore the proposals.

Ask once, in one sentence, and move on with their answer.

**In addition to retention, visually check the plot:**
- Does the noiseless curve show a clear onset / peak?
- Does the noisy curve follow the same qualitative shape?
- Is the onset shifted? (common: noisy onset moves to larger parameter value)

---

## Step 5 — Report

Summarise:
1. Which mode ran, at what register size, with which noise model
2. Noiseless peak observable value and at which scan point
3. Noisy peak and retention fraction
4. Go/no-go verdict with reasoning, and its scope
5. Path to the plot
6. If GO **from the cloud scan**: **Next step** is QPU submission via
   `qpu-submit` (cloud API) or `submit-to-cea` (cluster over SSH)
7. If GO **from the local scan**: next step is the cloud scan at the real size,
   which is what a hardware recommendation needs
8. If NO-GO: concrete suggestion for how to improve signal retention, and the
   `noise-emulate` offer from Step 4b if it would inform the next change

---

## Output layout

```
<output_dir>/emu_local/          Step 2a
  emu_noiseless.json   {records: [{scan_value, observable, n_shots, batch_id}...]}
  emu_noise.json       same format, noisy — with noise_params.source
  verdict.json         {go, reasons, scope, gates_hardware, retention, ...}
  emu_scan.png         noiseless + noisy scan curves

<output_dir>/emu/                Step 2b
  batch_ids.json       submitted batch IDs (noiseless + noisy per scan point)
  emu_noiseless.json   same schema as above
  emu_noise.json       same format, noisy backend
  verdict.json         {go, reasons, nl_max, n_max, retention}
  emu_scan.png         noiseless + noisy scan curves
  run.log              (if run in background)
```

Keep the two directories apart. Same filenames, different authority: overwriting
the cloud verdict with a local one destroys the only file that can justify a
submission.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `Pasqal Cloud credentials incomplete` | Export `PASQAL_USERNAME` / `PASQAL_PASSWORD` / `PASQAL_PROJECT_ID`, or see `noise-emulate` first-time setup. No account? Step 2a needs none |
| `N atoms is past the local emulator's reach` | Expected above ~14 atoms. Shrink the register with `--seq-kwargs` for the local check, or run Step 2b at the real size — do not raise `--max-atoms` |
| `<device> not in available devices` | Cloud connection failed or device offline; for SA1, is `PASQAL_REGION=sa` set? Retry. |
| `build_sequence` not found in seq file | Check `spec["builder_fn"]` matches the function name |
| `seq.to_abstract_repr()` fails | Sequence violates device constraints — check spacing and duration |
| All observables are NaN | `compute_observable` returns nan for empty counts; check batch status |
| retention low for good physics | Scan range may not hit the ordered phase — check Rb/a |
