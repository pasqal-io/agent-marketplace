---
name: noise-emulate
description: Run a noise emulation of a Pulser sequence using the target device's noise model fetched live from the Pasqal Cloud SDK (FRESNEL_CAN1 by default; SA1 supported). Three execution modes — local machine, SLURM GPU cluster (recommended), or Pasqal Cloud EMU_MPS emulators. Produces noiseless + noisy curves with a quantile envelope. Triggered by phrases like "run noise emulation", "emulate with noise", "noisy simulation", "noise model", "noise envelope", "run on GPU with noise".
argument-hint: "[sequence-description-or-file]"
---

# noise-emulate

Emulate a Pulser sequence's time evolution with the target device's noise
model (fetched live from the Pasqal Cloud — includes SPAM, amplitude, dephasing,
detuning, Doppler, relaxation).

**Choosing the device** — all modes accept `--device-name` (default `FRESNEL_CAN1`):
- **FRESNEL_CAN1** (default): no extra setup.
- **SA1**: pass `--device-name SA1` and set `PASQAL_REGION=sa` (SA1 lives in the
  `sa` cloud region and is invisible without it); your project must have SA1
  access. Verify the exact device key with `sdk.get_device_specs_dict().keys()`.
- **Ruby (CEA/TGCC)**: not on the Pasqal Cloud SDK — no live noise model is
  available. QPU runs go through `submit-to-cea`; for emulation of Ruby-style
  sequences, build against `AnalogDevice` constraints instead. The user never needs to touch the Python
scripts: this skill reads their sequence, writes the builder, runs everything,
and shows the result.

## Support scripts

```
${CLAUDE_PLUGIN_ROOT}/skills/noise-emulate/support/
  run_noise_emu.py          ← MPS trajectory runner (local + SLURM modes)
  plot_noise_emu.py         ← trajectory envelope figure
  submit_slurm.sh           ← turnkey SLURM launcher (one GPU job per trajectory)
  run_noise_emu_cloud.py    ← Pasqal Cloud EMU_MPS runner (cloud mode)
  plot_noise_emu_cloud.py   ← cloud results figure
  requirements.txt          ← Python dependencies (local/SLURM modes)
```

---

## Step 0 — Ask the user how to run

**Always ask this first** (use AskUserQuestion if interactive):

> Where should the emulation run?
> 1. **Locally** — on this machine. Fine for small systems / quick tests; a CUDA GPU
>    helps a lot. Trajectories run sequentially in one process.
> 2. **Via SLURM on a cluster (recommended)** — one GPU job per trajectory, all
>    trajectories in parallel. By far the fastest for full 40-trajectory envelopes.
>    Requires `sbatch` on the current machine.
> 3. **Via Pasqal Cloud** — runs on the Pasqal Cloud EMU_MPS emulator fleet.
>    No GPU or cluster needed, only Pasqal Cloud credentials. Best when you have
>    no local compute; queue times apply and quality degrades for large registers
>    (N ≳ 60–100).

Quick heuristics if the user has no preference: `which sbatch` succeeds → SLURM;
otherwise a CUDA GPU present (`nvidia-smi`) → local; otherwise → cloud.

Then read the user's sequence carefully:
- Register layout? (N×N square, chain, custom)
- Channel? (EOM or standard rydberg_global)
- Parametric variable? (hx, T, R, …)

---

## First-time setup (all modes)

**Pasqal Cloud credentials** (needed in every mode — the noise model is fetched live):
either set `PASQAL_USERNAME` / `PASQAL_PASSWORD` / `PASQAL_PROJECT_ID`, or create
`~/.pasqal_credentials.json`:
```json
{"username": "your.email@example.com", "password": "...", "project_id": "your-project-uuid"}
```
then `chmod 600 ~/.pasqal_credentials.json`.

**Python environment** (local and SLURM modes):
```bash
python3 -m venv ~/pulser-venv
source ~/pulser-venv/bin/activate
pip install -r ${CLAUDE_PLUGIN_ROOT}/skills/noise-emulate/support/requirements.txt
```
Tested versions (2026-06): pulser 1.8.0, pasqal-cloud 0.22.0, emu-mps 2.7.5,
torch 2.9.0. For GPU, install PyTorch for your CUDA version from pytorch.org first.
If a suitable venv already exists, point the skill at it with `export PULSER_VENV=<path>`.
Cloud mode only needs `pulser`, `pulser-pasqal` and `pasqal-cloud` (no emu-mps/torch).

---

## Step 1 — Write the sequence builder

### Local / SLURM modes

Write `seq_builder.py` with this signature (fully built, not parametric):

```python
def build_sequence(
    N:            int   = 6,
    hx:           float = 4.0,
    t:            int   = 4000,     # pulse duration in ns
    omega_offset: float = 1.0,      # multiplicative Ω scale
    delta_offset: float = 0.0,      # additive δ in rad/µs
    R_offset:     float = 1.0,      # multiplicative lattice spacing scale
    **kwargs,
) -> pulser.Sequence: ...
```

Use `AnalogDevice` for emulation; call `with_automatic_layout(AnalogDevice)` if
spacing < 10 µm. For EOM/quench sequences use the mean-field detuning at the
central site:

```python
import numpy as np, pulser
from pulser import Sequence
from pulser.devices import AnalogDevice
from pulser.register.special_layouts import SquareLatticeLayout

def build_sequence(N=6, hx=4.0, t=4000,
                   omega_offset=1.0, delta_offset=0.0, R_offset=1.0, **kwargs):
    omega = 2 * np.pi * 2.0
    C6    = AnalogDevice.interaction_coeff
    R     = (hx * 2 * C6 / (4 * omega)) ** (1/6)
    coords = SquareLatticeLayout(N, N, R * R_offset).coords
    register = pulser.Register.from_coordinates(coords, prefix="q")
    if R * R_offset < 10:
        register = register.with_automatic_layout(AnalogDevice)
    ci   = (N//2)*N + N//2
    dist = np.linalg.norm(coords - coords[ci], axis=-1); dist[ci] = np.inf
    delta = C6 * np.sum(1.0 / dist**6) + 2 * np.pi * delta_offset
    seq = Sequence(register, AnalogDevice)
    seq.declare_channel("ising", "rydberg_global")
    seq.enable_eom_mode("ising", amp_on=omega*omega_offset, detuning_on=delta)
    seq.add_eom_pulse("ising", duration=t, phase=0.0)
    seq.disable_eom_mode("ising")
    return seq
```

### Cloud mode

The cloud runner follows the `spec-to-sequence` contract instead: the file must
export `build_sequence(device=None, **params)` (observation time in ns as a
kwarg, default name `t`) **and** `compute_observable(counts) -> float`. If the
user brings a raw sequence, wrap it into this contract; default to mean Rydberg
density if no observable is specified, and say so.

---

## Step 2 — Run

### Mode 1 — Local

```bash
source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"

python ${CLAUDE_PLUGIN_ROOT}/skills/noise-emulate/support/run_noise_emu.py \
    --seq-file    seq_builder.py \
    --fn-name     build_sequence \
    --seq-kwargs  '{"N": 6, "hx": 4.0, "t": 4000}' \
    --n-traj      40 \
    --max-chi     128 \
    --n-times     75 \
    --out-dir     results/ \
    --cal-offsets '{"omega_offset": 0.03, "delta_offset": 0.2, "R_offset": 0.01}'
```

`--cal-offsets` adds a sensitivity band: ±3% on ω, ±0.2 rad/µs on δ, ±1% on R
(6 extra noiseless runs). If a QPU manifest from `qpu-submit` exists, ask the
user whether to add `--qpu-manifest <path>` — this runs the noisy trajectories
at the measured calibrated parameters for a fair comparison with QPU data.

Typical runtime on one A100: 3–8 min per noisy trajectory, so a full 40+1 run is
hours — run it with `nohup`/background for large systems, or use `--n-traj 5
--max-chi 64` for quick tests. The last printed line is the output `.npz` path.

### Mode 2 — SLURM (recommended)

```bash
SEQFILE=seq_builder.py \
SEQKWARGS='{"N":6,"hx":4.0,"t":4000}' \
OUTDIR=results/run1 \
NTRAJ=40 CHI=128 \
PARTITION=<your_partition> GRES=gpu:a100:1 ACCOUNT=<your_account> \
bash ${CLAUDE_PLUGIN_ROOT}/skills/noise-emulate/support/submit_slurm.sh
```

The launcher (1) fetches the noise model once on the login node (compute nodes
are usually offline) → `OUTDIR/noise_model.json`, (2) submits a SLURM array
`0..NTRAJ` — one GPU per trajectory, id 0 = noiseless — and (3) submits a
dependent merge+plot job. Set `PARTITION`/`GRES`/`ACCOUNT`/`TIME` to your
site's values; on a shared cluster cap concurrency with `ARRAY_MAX=10`.
Watch with `squeue -u $USER | grep nemu`; figure appears at `OUTDIR/noise_plot.png`.

Wall time per trajectory (N=6, χ=128, dt=10): ~8–14 min on A100; the whole array
finishes in roughly one trajectory's wall time when GPUs are free. For larger N
or entanglement/full-distribution observables, raise `CHI` (200+) and re-validate
convergence at the longest evolution time.

### Mode 3 — Pasqal Cloud

```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/noise-emulate/support/run_noise_emu_cloud.py \
    --seq-file   my_experiment_sequence.py \
    --seq-kwargs '{"N": 5, "hx": 6.0}' \
    --t-max      4000 \
    --n-times    15 \
    --shots      500 \
    --out-dir    results/noise_emu_cloud/
```

The cloud can't sample mid-evolution states, so this builds **one sequence per
observation time** (what the real QPU does) and submits noiseless + noisy
EMU_MPS batches per point. Batch budget = n_times × (2 + n_envelope); warn the
user beyond ~100 batches. `--n-envelope K` adds K independent noisy batches per
point for a client-side quantile band. Batch IDs are saved immediately; if the
session dies mid-poll, re-run with `--resume` and the same `--out-dir`.

---

## Step 3 — Plot

```bash
# local / SLURM (.npz):
python ${CLAUDE_PLUGIN_ROOT}/skills/noise-emulate/support/plot_noise_emu.py \
    --result results/FCAN1_*.npz --out results/noise_plot.png --coverage 0.75

# cloud (.json):
python ${CLAUDE_PLUGIN_ROOT}/skills/noise-emulate/support/plot_noise_emu_cloud.py \
    --results results/noise_emu_cloud/noise_emu_cloud.json \
    --out     results/noise_emu_cloud/noise_emu_cloud.png
```

Save figures as `.png` only.

---

## Step 4 — Report to the user

1. The noise model values printed during the run (copy the table) — these come
   as-shipped from the live device spec.
2. Key observations: how wide is the noise band, does the noiseless curve lie
   within it, signal retention at the peak.
3. If `--cal-offsets` was used and the calibration band is much wider than the
   stochastic band, flag that calibration precision matters more than noise.
4. Paths to the saved data file and figure.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Pasqal credentials not found` | See **First-time setup** above |
| `<device> not in available devices` | Cloud SDK connection failed or device hidden from the project (for SA1: is `PASQAL_REGION=sa` set?); retry / check project |
| `build_sequence not found` | Pass `--fn-name <name>` |
| Builder returned a parametric sequence | Call `.build(...)` inside the builder |
| GPU OOM (local/SLURM) | Reduce `--max-chi`; start at 64–128 |
| `emu_mps` not found | Wrong virtualenv; install from `requirements.txt` |
| `partial_*.npz` missing after SLURM job | Check the `.err` log: time limit, OOM, or missing venv |
| Cloud batches stuck PENDING | Queue congestion — normal; re-poll later with `--resume` |
| Cloud batch ERROR on large N | Cloud EMU_MPS degrades for N ≳ 60–100; reduce N or use SLURM/local mode |

---

## Output files

```
# local / SLURM
results/FCAN1_<kwargs>_ntraj40_chi128_<timestamp>.npz   ← raw data (self-documenting:
results/noise_plot.png                                     embeds noise model + kwargs)

# cloud
<out-dir>/batch_ids.json          ← submitted batches (for --resume)
<out-dir>/noise_emu_cloud.json    ← per-time records
<out-dir>/noise_emu_cloud.png
```
