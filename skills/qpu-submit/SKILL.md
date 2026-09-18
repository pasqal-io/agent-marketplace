---
name: qpu-submit
description: Submit a neutral-atom experiment_spec.json plus its Pulser sequence file to a Rydberg QPU on Pasqal Cloud, with an optional pre-calibration batch that measures the device's Rabi frequency and Rydberg resonance and compensates the submitted jobs. Writes batch IDs for harvest-and-analyze. For a QPU reached over SSH through a cluster scheduler, use submit-to-cea. Triggered by phrases like "submit this spec to the QPU", "run this sequence on Fresnel", "send it to the neutral-atom hardware".
argument-hint: "[spec-file] [sequence-file]"
---

# qpu-submit

Submit a spec-driven scan to a QPU and record the batch IDs. One batch per scan
point, one job each — the format `harvest-and-analyze` reads back.

This skill submits **whatever sequence file you give it**. It contains no
physics of its own: the register, pulse schedule and observable all come from
the `build_sequence()` / `compute_observable()` pair that `spec-to-sequence`
generated. A worked example lives in
[`examples/square_lattice_eom_quench/`](../../examples/square_lattice_eom_quench/).

Device selection: `--device` (default: `spec["device"]`); for **SA1** also set
`PASQAL_REGION=sa` and use a project with SA1 access. **Ruby (CEA)** is not on
the Pasqal Cloud — use the `submit-to-cea` skill.

## Support scripts

Paths like `support/…` below are relative to **this skill's directory** —
expand them to the skill's absolute location when running commands from your
project directory (keep outputs like `--out-dir` in your project, not the plugin).

```
support/
  submit_qpu.py        ← calibration + submission
  pasqal_auth.py       ← Pasqal Cloud credential loading (shared, do not edit here)
```

Python environment: `source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"`

---

## Step 0 — Confirm the cost before submitting

QPU shots are a metered resource and a submitted batch cannot be un-submitted.
Before running anything, state the cost to the user and get an explicit go-ahead:

- **number of batches** = number of scan points (`len(spec["scan"]["values"])`)
- **shots per batch** = `--shots`, default `spec["shots_per_point"]`
- **total QPU shots** = batches × shots
- **plus the calibration batch**: 50 jobs × 20 shots, unless `--no-calibration`

Say those four numbers back to the user, name the device, and wait for
confirmation. If they change the scan, the shots or the device afterwards,
confirm again — the previous go-ahead was for a different submission.

**The script enforces this, it does not trust you to.** `submit_qpu.py` prints
that plan itself and then stops: it submits only with `--confirm`, or with a
`y` typed at a terminal. Run without a terminal and without the flag — the
normal case for an agent — and it exits non-zero having contacted nothing, not
even the credential store. So pass `--confirm` **only** to carry a go-ahead the
user actually gave you, in this conversation, for these numbers. Getting the
plan wrong is cheap; getting the flag wrong spends someone's shots.

The same rule covers a re-run after a plan change: new numbers, new go-ahead.

Do not submit to hardware before `validate-emu` has returned a GO for this spec.
If no emulation has been run, say so and offer to run it first. Check the verdict
you are relying on: `validate-emu`'s local mode writes the same `verdict.json`
with `"gates_hardware": false`, because it ran a stand-in noise model and often a
smaller register. That file is not a green light for shots — the cloud verdict at
the real size is.

---

## Step 1 — Check the sequence file accepts calibration offsets

Calibration is only meaningful if the builder can receive its results. The
builder must declare both parameters explicitly:

```python
def build_sequence(device=None, omega_offset=1.0, delta_offset=0.0, **params):
    omega = 2*np.pi*params["omega_max_mhz"] * omega_offset   # multiplicative
    delta = delta_nominal + 2*np.pi*delta_offset             # additive, MHz
```

`**params` would swallow them silently, so `submit_qpu.py` refuses to run rather
than submit jobs that claim to be calibrated and are not. Either add the two
parameters to the sequence file, or pass `--no-calibration`.

This is the same convention `noise-emulate` uses, so an emulation replayed
against `batch_ids.json` reproduces what the hardware actually ran.

---

## Step 2 — Submit

```bash
source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"

python support/submit_qpu.py \
    --spec      <experiment_name>_spec.json \
    --seq-file  <experiment_name>_sequence.py \
    --out-dir   <spec.output_dir>/qpu/ \
    --confirm                       # only with the user's go-ahead (Step 0)
```

Options: `--shots`, `--device`, `--no-calibration`, `--calib-poll` (seconds,
default 60), `--wait`. Drop `--confirm` to see the plan and the total shot count
without submitting anything — that is the cheapest way to check the numbers you
are about to quote to the user.

What the script does:

1. **Calibration batch** — 30 Rydberg spectroscopy jobs + 20 Rabi oscillation
   jobs on a 7-atom reference register, at the spec's `pulse.omega_max_mhz`.
   Polls until complete, fits Ω and δ offsets over two rounds, saves the fits
   and their plot. The Ω compensation is capped at the channel maximum.
2. **Experiment batches** — one per scan point, built by calling
   `build_sequence(device=<live device>, **fixed_params, <variable>=value,
   omega_offset=…, delta_offset=…)`. Sequences longer than the device's
   maximum duration are rejected before anything is submitted.
3. Writes `batch_ids.json` immediately after submission, then returns. The last
   printed line is its path.

**Never re-run this on an `--out-dir` that already has a `batch_ids.json`.** The
script refuses, before touching credentials, and says why: a second run buys the
same shots again on hardware *and* overwrites the only record of the first
submission's batch IDs, so those shots become unrecoverable as well as paid for.
If a session dropped after submission, the batches are already queued — go to
Step 3 and collect them. A genuinely different run belongs in a different
`--out-dir`.

**Typical duration**: calibration ~10–30 min of execution, but queue wait is
site-dependent and can be far longer. The experiment batches queue behind it.

**Monitoring** — run in the background and watch only significant events:

```bash
tail -f <out-dir>/submit.log | grep --line-buffered \
    -E "Calibration|omega_offset|batch_ids saved|ERROR|Traceback"
```

---

## Step 3 — Collect and analyze

**Next step**: `harvest-and-analyze`. Collection, observable computation, EMU
comparison and the accept/reject verdict all belong to it:

```bash
python <harvest-and-analyze>/support/harvest_qpu.py \
    --spec      <experiment_name>_spec.json \
    --seq-file  <experiment_name>_sequence.py \
    --batch-ids <spec.output_dir>/qpu/batch_ids.json \
    --emu-dir   <spec.output_dir>/emu/ \
    --out-dir   <spec.output_dir>/qpu/
```

It tolerates partial completion: jobs that are not `DONE` are reported and
skipped, so re-running later fills the gaps.

---

## Output files

```
<spec.output_dir>/qpu/
  batch_ids.json                    per_point batch IDs, builder kwargs, calibration
  calibration/
    calibration_fits.png            Rydberg spectroscopy + Rabi fits
    calib_results.json              omega_ratio, delta_offset
```

`batch_ids.json` layout:

```json
{
  "format": "per_point",
  "scan_variable": "t_ns",
  "device": "FRESNEL_CAN1",
  "builder_kwargs": {"omega_offset": 1.032, "delta_offset": 0.187},
  "calibration": {"omega_ratio": 0.969, "delta_offset": 1.175, "batch_id": "..."},
  "batches": [{"scan_value": 16, "batch_id": "...", "n_shots": 300}]
}
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `device not available in this project` | QPU may be offline, or the region is wrong (SA1 needs `PASQAL_REGION=sa`). The error lists the devices the project can see. |
| `build_sequence() does not declare omega_offset` | Add the two calibration parameters to the sequence file (Step 1), or pass `--no-calibration`. |
| Calibration fit fails | Re-run calibration alone, or pass `--no-calibration` to submit at nominal Ω and δ. The fit degrades when the reference register loads poorly. |
| `sequence is N ns, over the device limit` | The scan reaches durations the device cannot run. Shorten the scan range — EOM enable/disable adds ~240 ns on top of the pulse. |
| Ω compensation capped | The setpoint is already at the channel maximum, so the hardware shortfall cannot be compensated. Lower `pulse.omega_max_mhz` in the spec if the compensation matters. |
| Jobs stuck in `PENDING` | Normal — the QPU has a queue. `harvest_qpu.py` handles partial results; re-run it later. |
| Large δ offset from calibration | If \|delta_offset\|/(2π) > 0.5 MHz, flag it to the user: that is above typical drift and may indicate a hardware issue. |
