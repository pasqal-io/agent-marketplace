---
name: qpu-submit
description: Submit a Pulser EOM quench sequence to a QPU on the Pasqal Cloud (FRESNEL_CAN1 by default; SA1 via --device and PASQAL_REGION=sa), including an automatic pre-calibration batch (Rydberg spectroscopy + Rabi oscillations on a 7-atom triangular lattice). Handles the full workflow end-to-end — calibration, experiment submission, result collection, and optionally a comparison plot with noise-model emulation. Triggered by phrases like "submit to QPU", "run on QPU", "send to cloud QPU", "QPU experiment", "compare QPU with noise model".
argument-hint: "[physics-params or description]"
---

# qpu-submit

This skill submits an EOM quench experiment to a Pasqal Cloud QPU with a
pre-calibration batch. Device selection: `--device` (default `FRESNEL_CAN1`);
for **SA1** also set `PASQAL_REGION=sa` and use a project with SA1 access. The
workflow assumes an EOM-capable rydberg_global channel — check the live specs of
any other target first. **Ruby (CEA)** is not on the Pasqal Cloud: use the
`submit-to-cea` skill instead. The calibration measures Rabi and Rydberg spectroscopy
on a fixed 7-atom triangular lattice, extracts omega and detuning offsets, and
injects compensated values into the main experiment jobs.

## Support scripts

Paths like `support/…` below are relative to **this skill's directory** —
expand them to the skill's absolute location when running commands from your
project directory (keep outputs like `--out-dir` in your project, not the plugin).

All scripts live in:
```
support/
  submit_qpu.py        ← calibration + submission
  collect_qpu.py       ← result collection (async)
  plot_qpu_vs_emu.py   ← QPU + emulation comparison figure
```

Python environment: `source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"`

---

## Step 0 — Determine experiment parameters

Ask the user (or read from context):
- `N` — atoms per side of the square lattice (e.g. 5 for 5×5=25 atoms)
- `hx` — transverse field ratio hx/J (e.g. 6.0 for the paramagnetic regime)
- `omega` — Rabi setpoint in rad/µs (default: 4π ≈ 12.566, i.e. 2 MHz)
- `t_max` — max pulse duration in ns (default 4000)
- `shots` — shots per observation time (default 300)
- `n_times` — number of observation times (default 75)

The lattice spacing R is computed automatically from `hx`, `omega`, and the
FCAN1 device's C6 coefficient:
```
R = (hx × 2 × C6 / (4 × omega))^(1/6)
```

---

## Step 1 — Submit (calibration + experiment)

```bash
source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"

python support/submit_qpu.py \
    --N 5 \
    --hx 6.0 \
    --omega 12.566370614359172 \
    --t-max 4000 \
    --shots 300 \
    --n-times 75 \
    --out-dir results/qpu/hx6_N5/ \
    --device FRESNEL_CAN1
```

What the script does:
1. **Calibration batch**: 30 Rydberg spectroscopy jobs + 20 Rabi oscillation jobs
   on a fixed 7-atom triangular lattice. Submits jobs, then immediately opens the
   experiment batch (empty) so both land in the QPU queue back-to-back with no gap.
   Polls for calibration completion every **3600 s** (1 hour), fits offsets with
   two-round Lorentzian/sinusoidal fitting. Saves calibration plots.
2. **Experiment batch**: Opened immediately after calibration is submitted (empty,
   holding its queue slot). Jobs are filled with compensated ω and δ once
   calibration finishes, then the batch is closed. Does NOT wait (async).
3. Saves a manifest JSON to `--out-dir` containing all batch IDs, calibration
   results, and experiment parameters. The last printed line is the manifest path.

**Typical duration:**
- Calibration: ~10–30 min execution (queue wait is site-dependent — can be 40+ h)
- Experiment: ~2–4 hours for 75 time points × 300 shots (queue-dependent)

**Monitoring**: run the submission in the background and use a Monitor that fires
only on significant events (not every poll tick):
```bash
tail -f <out-dir>/submit_run.log | grep --line-buffered \
    -E "Calibration complete|omega_compensated|Manifest|ERROR|Traceback|Batch closed"
```

The script returns immediately after submitting the experiment batch. Use
`collect_qpu.py` to retrieve results.

---

## Step 2 — Monitor and collect results

**Check status:**
```python
from pasqal_cloud import SDK
# (load credentials)
sdk = SDK(...)
batch = sdk.get_batch("<batch_id_from_manifest>")
done = sum(1 for j in batch.ordered_jobs if j.status == "DONE")
print(f"{done}/{len(batch.ordered_jobs)} jobs done")
```

**Collect when ready:**
```bash
python support/collect_qpu.py \
    --manifest results/qpu/hx6_N5/QPU_N5_hx6.0_t4000_<timestamp>_manifest.json

# Or wait until all jobs finish (polls every 60 s):
python support/collect_qpu.py \
    --manifest results/qpu/hx6_N5/..._manifest.json \
    --wait
```

Saves a `.npz` alongside the manifest with:
- `times_ns` — observation times
- `mag_mean` — lattice-averaged ⟨n⟩ (Laplace-smoothed)
- `mag_err`  — binomial stderr
- `occ_mean` — per-site ⟨n_i⟩ (shape: n_times × n_sites)

---

## Step 3 — Comparison plot (QPU + noise-model emulation)

If a noise-model emulation `.npz` is available from the `noise-emulate` skill:

```bash
python support/plot_qpu_vs_emu.py \
    --qpu results/qpu/hx6_N5/QPU_N5_hx6.0_t4000_<timestamp>_manifest.npz \
    --emu results/emu/FCAN1_N5_hx6.0_t4000_ntraj40_chi512_<timestamp>.npz \
    --out results/comparison_hx6_N5.png \
    --coverage 0.75
```

The figure shows:
- **Orange markers**: QPU mean ⟨n⟩ with error bars (300 shots)
- **Dark dashed**: noiseless emulation
- **Blue solid**: noisy emulation mean (40 trajectories)
- **Blue fill**: 75% quantile band
- **Grey fill**: calibration offset sensitivity band
- **Text box**: full FCAN1 noise model parameters

---

## End-to-end: hx/J = 6.0 on a 5×5 lattice

This is the recommended test case: the noise model agrees well with QPU in
the large-hx paramagnetic regime.

### Seq builder for `noise-emulate`

Write `seq_builder.py` in your working directory:

```python
import numpy as np
import pulser
from pulser import Sequence
from pulser.devices import AnalogDevice
from pulser.register.special_layouts import SquareLatticeLayout
from pulser.register.register_layout import RegisterLayout

def _make_square_register(N, R):
    from pasqal_cloud import SDK
    import importlib.util
    from pathlib import Path
    from pulser.json.abstract_repr.deserializer import deserialize_device
    # Use AnalogDevice as a fallback — the noise-emulate skill doesn't need the
    # exact FCAN1 register layout since MPSBackend handles it internally.
    coords = SquareLatticeLayout(N, N, R).coords
    reg = pulser.Register.from_coordinates(coords, prefix="q")
    if R < 10:
        reg = reg.with_automatic_layout(AnalogDevice)
    return reg

def build_sequence(
    N: int = 5,
    hx: float = 6.0,
    t: int = 4000,
    omega_offset: float = 1.0,
    delta_offset: float = 0.0,
    R_offset: float = 1.0,
    **kwargs,
) -> pulser.Sequence:
    omega = 2 * 2 * np.pi                  # 4π rad/µs (2 MHz)
    C6    = AnalogDevice.interaction_coeff
    R     = (hx * 2 * C6 / (4 * omega)) ** (1/6)

    coords = SquareLatticeLayout(N, N, R * R_offset).coords
    register = pulser.Register.from_coordinates(coords, prefix="q")
    if R * R_offset < 10:
        register = register.with_automatic_layout(AnalogDevice)

    # Mean-field detuning at central site
    ci = (N//2)*N + (N//2)
    diff = coords - coords[ci]
    dist = np.linalg.norm(diff, axis=-1)
    dist[ci] = np.inf
    delta = C6 * np.sum(1.0/dist**6) + 2*np.pi*delta_offset

    seq = Sequence(register, AnalogDevice)
    seq.declare_channel("ising", "rydberg_global")
    seq.enable_eom_mode("ising",
                        amp_on=omega*omega_offset,
                        detuning_on=delta)
    seq.add_eom_pulse("ising", duration=t, phase=0.0)
    seq.disable_eom_mode("ising")
    return seq
```

### Run noise emulation

> **Note:** this optional step uses the `noise-emulate` skill (same plugin).
> The `.npz`-based command below is the local/SLURM mode and needs a GPU; with
> cloud-only access, use noise-emulate's Pasqal Cloud mode instead (its JSON
> output feeds `plot_noise_emu_cloud.py` rather than the comparison below), or
> skip this step — the QPU submission does not depend on it.

```bash
source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"

python ../noise-emulate/support/run_noise_emu.py \
    --seq-file    seq_builder.py \
    --fn-name     build_sequence \
    --seq-kwargs  '{"N": 5, "hx": 6.0, "t": 4000}' \
    --n-traj      40 \
    --max-chi     512 \
    --n-times     75 \
    --out-dir     results/emu/ \
    --cal-offsets '{"omega_offset": 0.03, "delta_offset": 0.2, "R_offset": 0.01}'
```

### Run QPU submission

```bash
python support/submit_qpu.py \
    --N 5 --hx 6.0 --t-max 4000 --shots 300 --n-times 75 \
    --out-dir results/qpu/hx6_N5/
```

### Wait for QPU results, collect, and plot

```bash
python support/collect_qpu.py \
    --manifest results/qpu/hx6_N5/QPU_N5_hx6.0_..._manifest.json --wait

python support/plot_qpu_vs_emu.py \
    --qpu results/qpu/hx6_N5/QPU_N5_hx6.0_..._manifest.npz \
    --emu results/emu/FCAN1_N5_hx6.0_t4000_ntraj40_chi512_<timestamp>.npz \
    --out results/comparison_hx6_N5.png
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `<device> not available` | QPU may be offline, or wrong region (SA1 needs `PASQAL_REGION=sa`). Check `sdk.get_device_specs_dict().keys()`. |
| Calibration fit fails | Try `--no-calibration` to skip and use nominal values. The fit can fail if queue noise is high; re-run calibration alone. |
| Jobs stuck in PENDING | Normal — QPU has a queue. Use `--wait` on `collect_qpu.py` to poll automatically. |
| Large delta_offset from calibration | If `|delta_offset|/(2π) > 0.5 MHz`, flag to the user — this is above typical drift and may indicate a hardware issue. |
| Missing correlation matrix for S(q) | QPU only returns bitstrings, so S(π,π) cannot be reconstructed from QPU data alone. The plot shows the staggered magnetisation M_s instead, or leaves panel 2 as EMU-only. |

---

## Output files

```
results/qpu/hx6_N5/
  QPU_N5_hx6.0_t4000_<timestamp>_manifest.json   ← submission record
  QPU_N5_hx6.0_t4000_<timestamp>_manifest.npz    ← collected observables
  calibration/
    calibration_fits.png                           ← Rabi + Rydberg spec plots
    calib_results.json                             ← omega_ratio, delta_offset

results/emu/
  FCAN1_N5_hx6.0_t4000_ntraj40_chi512_<ts>.npz   ← EMU trajectories

results/
  comparison_hx6_N5.png                           ← QPU vs EMU figure
```
