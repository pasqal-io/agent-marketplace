---
name: harvest-and-analyze
description: Collect QPU bitstrings from Pasqal Cloud by batch ID, compute the target observable, compare to the EMU baseline from validate-emu, and return an accept/reject verdict. Triggered by phrases like "collect QPU results", "harvest results", "analyze QPU data", "compare QPU to EMU", "is the QPU data consistent with the noise model", "accept or reject".
argument-hint: "[spec-file] [batch-ids-file]"
---

# harvest-and-analyze

Collect QPU results from the cloud, compute the observable, and compare to the
EMU baseline. The accept/reject decision is: does QPU agree with the noise model?

---

## Support scripts

Paths like `support/…` below are relative to **this skill's directory** —
expand them to the skill's absolute location when running commands from your
project directory (keep outputs like `--out-dir` in your project, not the plugin).

```
support/
  harvest_qpu.py       ← collect, compute observable, compare, verdict
  plot_qpu_vs_emu.py   ← QPU vs noiseless/noisy EMU figure
```

Python environment: `source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"`

---

## What this skill needs

1. `<experiment_name>_spec.json` — from `idea-to-spec`
2. `<experiment_name>_sequence.py` — from `spec-to-sequence` (for `compute_observable`)
3. QPU `batch_ids.json` — from `qpu-submit` or `submit-to-cea`
4. EMU results directory — from `validate-emu` (contains `emu_noiseless.json` + `emu_noise.json`)

---

## Step 1 — Check QPU job status

Before collecting, confirm jobs are done:

```python
from pasqal_cloud import SDK
import json, os
sdk = SDK(username=os.environ["PASQAL_USERNAME"],
          password=os.environ["PASQAL_PASSWORD"],
          project_id=os.environ["PASQAL_PROJECT_ID"])

batch_ids = json.loads(open("batch_ids.json").read())
# for per_point format:
for entry in batch_ids["batches"]:
    b = sdk.get_batch(entry["batch_id"])
    done = sum(1 for j in b.ordered_jobs if j.status == "DONE")
    print(f"{entry['scan_value']}: {done}/{len(b.ordered_jobs)} done")
```

Partial collection is fine — `harvest_qpu.py` skips jobs that aren't DONE and
reports their status. Re-run later to fill gaps.

---

## Step 2 — Collect and analyze

```bash
source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"

python support/harvest_qpu.py \
    --spec      <experiment_name>_spec.json \
    --seq-file  <experiment_name>_sequence.py \
    --batch-ids <spec.output_dir>/qpu/batch_ids.json \
    --emu-dir   <spec.output_dir>/emu/ \
    --out-dir   <spec.output_dir>/qpu/ \
    [--bootstrap 300]
```

The script:
1. Connects to Pasqal Cloud
2. Pulls bitstrings for each batch (handles both `per_point` and `parametric` formats)
3. Calls `compute_observable(counts)` from the sequence file
4. Computes bootstrap error bars (300 resamples by default)
5. Loads `emu_noise.json` from `--emu-dir` as the comparison baseline
6. Accepts if max QPU deviation < 2σ from noisy EMU prediction
7. Writes `qpu_results.json` + `verdict.json`

**Batch ID formats supported:**

*per_point* (one batch per scan point — FC1 pattern from `qpu-submit`):
```json
{
  "format": "per_point",
  "scan_variable": "delta_f_mhz",
  "batches": [
    {"scan_value": -4.0, "batch_id": "uuid-...", "n_shots": 1000},
    ...
  ]
}
```

*parametric* (one batch, multiple jobs — Z₂/Ruby pattern):
```json
{
  "format": "parametric",
  "scan_variable": "tau_ns",
  "batch_id": "uuid-..."
}
```

`qpu-submit` writes `per_point`. A different launcher script producing neither
format must be reformatted before running.

---

## Step 3 — Generate the comparison figure

```bash
python support/plot_qpu_vs_emu.py \
    --qpu       <spec.output_dir>/qpu/qpu_results.json \
    --noiseless <spec.output_dir>/emu/emu_noiseless.json \
    --noisy     <spec.output_dir>/emu/emu_noise.json \
    --out       <spec.output_dir>/comparison.png \
    --verdict   <spec.output_dir>/qpu/verdict.json \
    --title     "<experiment_name>"
```

Figure shows: QPU data points (±bootstrap errors), noiseless EMU (dashed),
noisy EMU (solid), ACCEPT/REJECT annotation.

---

## Step 4 — Interpret the verdict

Read `qpu/verdict.json`:
```json
{
  "accept": true,
  "max_deviation_sigma": 1.4,
  "sigma_tolerance": 2.0,
  "reasons": ["QPU max deviation 1.4σ < 2σ — consistent with noise model"]
}
```

**ACCEPT**: QPU agrees with the noise model. The experiment is publishable.

**REJECT** (and what to do):
- **Systematic offset** (QPU curve shifted up/down): possible calibration drift —
  check if Rabi/spectroscopy calibration was run. Flag to hardware team.
- **Missing signal** (QPU much lower than noisy EMU): check SPAM parameters,
  check atom loading. May need recalibration.
- **Signal at wrong scan value** (onset shifted): normal — noise shifts the
  effective transition. Update the interpretation, don't automatically reject.
- **Noisy but trend matches**: likely fine — increase shots and re-run.

---

## Step 5 — Report

Summarise:
1. QPU observable at each scan point vs noise model prediction
2. Max deviation in σ units
3. Accept/reject verdict with reasoning
4. Path to the comparison figure
5. If REJECT: specific diagnosis and recommended follow-up

---

## Output layout

```
<output_dir>/qpu/
  batch_ids.json        (written by qpu-submit / submit-to-cea)
  qpu_results.json      {records: [{scan_value, observable, obs_err, n_shots, ...}]}
  verdict.json          {accept, max_deviation_sigma, sigma_tolerance, reasons}

<output_dir>/
  comparison.png        QPU vs EMU figure
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Job status not DONE | Wait longer; re-run `harvest_qpu.py` — it handles partial completion |
| `full_result` is None | Job may still be processing; check status again in a few minutes |
| All observables are 0 | Bitstrings all-zero means readout failed; check SPAM parameters |
| Bootstrap error ≫ signal | Increase shots per point (update `spec["shots_per_point"]`) |
| batch_ids format not recognised | Manually edit to match per_point or parametric format above |
| Max deviation huge but trend right | Normal for small N; consider weaker σ_tolerance (e.g., 3σ) |
