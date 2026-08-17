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
   `qpu-submit` (cloud API) or `submit-via-hpc` (cluster over SSH)
7. If GO **from the local scan**: next step is the cloud scan at the real size,
   which is what a hardware recommendation needs
8. If NO-GO: concrete suggestion for how to improve signal retention

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
