---
name: validate-emu
description: Scan an experiment defined by an experiment_spec.json and its sequence file on cloud emulators, noiseless and noisy, then return a go/no-go decision on whether the signal survives device noise well enough to be worth hardware time. This is the gate before any QPU submission, not the submission itself. Triggered by phrases like "validate with EMU", "run EMU scan", "check noise retention", "is this worth submitting to hardware", "validate before QPU", "EMU validation".
argument-hint: "[spec-file] [seq-file]"
---

# validate-emu

Run noiseless + noisy EMU_MPS cloud scans, compute the target observable,
and decide whether the signal survives device noise well enough to justify QPU shots.

**Rule: never submit to QPU without a passing validate-emu verdict first.**

---

## Support scripts

Paths like `support/…` below are relative to **this skill's directory** —
expand them to the skill's absolute location when running commands from your
project directory (keep outputs like `--out-dir` in your project, not the plugin).

```
support/
  run_emu_scan.py      ← cloud scan submission, polling, observable computation
  plot_emu_scan.py     ← scan curve figure
```

Python environment: `source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"`
Credentials: `~/.pasqal_credentials.json` (or `$PASQAL_*` env vars)

---

## What this skill needs

1. `<experiment_name>_spec.json` — from `idea-to-spec`
2. `<experiment_name>_sequence.py` — from `spec-to-sequence`

Check both files exist and that `spec["sequence_file"]` matches the actual filename.

---

## Step 1 — Verify sequence smoke test

Before submitting anything to the cloud:

```bash
source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"
python <experiment_name>_sequence.py
```

Must print: `Sequence OK: <duration> ns, <N> atoms` with no errors.
If it fails, stop and fix the sequence file before proceeding.

---

## Step 2 — Run the EMU scan

```bash
source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"

python support/run_emu_scan.py \
    --spec     <experiment_name>_spec.json \
    --seq-file <experiment_name>_sequence.py \
    --out-dir  <spec.output_dir>/emu/ \
    [--shots   <override>] \
    [--poll    30]
```

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
1. Noiseless peak observable value and at which scan point
2. Noisy peak and retention fraction
3. Go/no-go verdict with reasoning
4. Path to the plot
5. If GO: **Next step** is QPU submission via `qpu-submit` (cloud API) or `submit-via-hpc` (cluster over SSH)
6. If NO-GO: concrete suggestion for how to improve signal retention

---

## Output layout

```
<output_dir>/emu/
  batch_ids.json       submitted batch IDs (noiseless + noisy per scan point)
  emu_noiseless.json   {records: [{scan_value, observable, n_shots, batch_id}...]}
  emu_noise.json       same format, noisy backend
  verdict.json         {go, reasons, nl_max, n_max, retention}
  emu_scan.png         noiseless + noisy scan curves
  run.log              (if run in background)
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `Pasqal credentials not found` | Create `~/.pasqal_credentials.json` (see `noise-emulate` setup) |
| `<device> not in available devices` | Cloud connection failed or device offline; for SA1, is `PASQAL_REGION=sa` set? Retry. |
| `build_sequence` not found in seq file | Check `spec["builder_fn"]` matches the function name |
| `seq.to_abstract_repr()` fails | Sequence violates device constraints — check spacing and duration |
| All observables are NaN | `compute_observable` returns nan for empty counts; check batch status |
| retention low for good physics | Scan range may not hit the ordered phase — check Rb/a |
