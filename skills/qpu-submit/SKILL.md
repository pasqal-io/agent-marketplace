---
name: qpu-submit
description: Submit a neutral-atom experiment_spec.json plus its Pulser sequence file to a Rydberg QPU on Pasqal Cloud, with an optional pre-calibration batch that measures the device's Rabi frequency and Rydberg resonance and compensates the submitted jobs. Writes batch IDs for harvest-and-analyze. For a QPU reached over SSH through a cluster scheduler, use submit-to-cea. Triggered by phrases like "submit this spec to the QPU", "run this sequence on Fresnel", "send it to the neutral-atom hardware".
argument-hint: "[spec-file] [sequence-file]"
---

# qpu-submit

Submit a spec-driven scan to a QPU and record what was submitted. **One batch,
one job per scan point** — one queue slot, one atom loading, one labelled object
`harvest-and-analyze` reads back.

RUNS ON: a QPU, through the cloud API. Billed shots, and a submitted batch
cannot be recalled. Everything before the confirmation gate happens on this
machine and costs nothing.

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
  batch_tags.py        ← the labels every batch carries (shared, do not edit here)
  pasqal_auth.py       ← credentials, projects and credits (shared, do not edit here)
```

Python environment: `source "${PULSER_VENV:-$HOME/pulser-venv}/bin/activate"`

## Decisions that are not yours

Not even under "do whatever you think is best". Ask, recommend, and wait:

- **which account and which project** pays for this (Step 0a)
- **the shot count and the number of scan points** (Step 0b)
- **the device**, and the region it lives in
- **calibration or not** — it costs 1000 shots and changes what the jobs run
- **an open batch** (Step 2b), which holds the device until you close it

And if something will not work — a builder that will not serialize, a device
that stays unavailable — stop after about **three** attempts. Report what was
tried, what failed and what is now known, then offer changing the objective,
narrowing the scope, or digging further. Do not keep retrying against billed
hardware or a silent queue.

---

## Step 0a — Confirm the account, and let the user pick the project

Finding credentials on the machine is not permission to spend them, and
`PASQAL_PROJECT_ID` is the last thing somebody exported, not a decision. Before
anything else:

```bash
python support/pasqal_auth.py --whoami
```

Free, read-only, submits nothing. It prints the username, the region, **which
source each credential came from** (environment, system keyring, credentials
file), and the projects this account belongs to with the QPU and EMU credits
each has left. No password and no token is ever printed.

Show that to the user and ask **which project should pay for this run**. Then
pass it explicitly:

```bash
python support/submit_qpu.py … --project-id <the id they chose>
```

`submit_qpu.py` refuses to run without `--project-id`, and the plan it asks you
to approve names the account, the project and its remaining credits. If the
`--whoami` account is not theirs, stop — do not work around it, and never type a
password on their behalf.

---

## Step 0b — Confirm the cost before submitting

QPU shots are a metered resource and a submitted batch cannot be un-submitted.
Before running anything, state the cost to the user and get an explicit go-ahead:

- **one batch**, with **one job per scan point** (`len(spec["scan"]["values"])`)
- **shots per job** = `--shots`, default `spec["shots_per_point"]`
- **total QPU shots** = jobs × shots
- **plus the calibration batch**: 50 jobs × 20 shots, unless `--no-calibration`
- **against** the remaining credits from Step 0a

Say those numbers back to the user, name the device and the project, and wait for
confirmation. If they change the scan, the shots or the device afterwards,
confirm again — the previous go-ahead was for a different submission.

**The script enforces this, it does not trust you to.** `submit_qpu.py` prints
the spec-derived plan before it contacts anything, then the account block, then
stops: it submits only with `--confirm`, or with a `y` typed at a terminal. Run
without a terminal and without the flag — the normal case for an agent — and it
exits non-zero having submitted nothing. So pass `--confirm` **only** to carry a
go-ahead the user actually gave you, in this conversation, for these numbers.
Getting the plan wrong is cheap; getting the flag wrong spends someone's shots.

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
    --spec       experiments/<name>/<name>_spec.json \
    --seq-file   experiments/<name>/<name>_sequence.py \
    --out-dir    experiments/<name>/results/qpu/ \
    --project-id <the project from Step 0a> \
    --tag        "<the user's own words for this run>" \
    --confirm                       # only with the user's go-ahead (Step 0b)
```

Options: `--shots`, `--device`, `--no-calibration`, `--calib-poll` (seconds,
default 60), `--wait`, `--tag` (repeatable), `--open-batch` (Step 2b). Drop
`--confirm` to see the plan and the total shot count without submitting
anything — that is the cheapest way to check the numbers you are about to quote
to the user.

What the script does:

1. **Calibration batch** — 30 Rydberg spectroscopy jobs + 20 Rabi oscillation
   jobs on a 7-atom reference register, at the spec's `pulse.omega_max_mhz`.
   Polls until complete, fits Ω and δ offsets over two rounds, saves the fits
   and their plot. The Ω compensation is capped at the channel maximum. Tagged
   `stage:calibration`, so it is findable next to the experiment batch.
2. **One experiment batch**, with one job per scan point. Two shapes, chosen
   automatically:
   - the sequence file exposes `build_parametric_sequence(device=None, **fixed)
     -> (Sequence, (var_name,))` → one batch-level parametrized sequence and one
     `variables` binding per job. The canonical cloud shape, and the cheapest
     payload.
   - it does not → the N concrete sequences from `build_sequence(device=<live
     device>, **fixed_params, <variable>=value, omega_offset=…,
     delta_offset=…)` go in as N jobs of the same batch, each carrying its own
     serialized sequence. Nothing has to be regenerated for this to work.

   Either way, sequences longer than the device's maximum duration are rejected
   before anything is submitted, and **never N batches of one job**: that is N
   queue slots, N atom loadings and N calibration drifts across what is supposed
   to be one scan.
3. **Labels, always.** Every batch carries `exp:<name>`, `stage:…`,
   `device:…`, `scan:<variable>`, `n_atoms:…`, `shots:…`, `spec:<version>`,
   `date:…`, `obj:<objective slug>`, plus each `--tag` you pass. That is how a
   run is found again months later:

   ```python
   from pasqal_cloud.utils.filters import BatchFilters
   sdk.get_batches(filters=BatchFilters(tag="exp:<name>"))   # emu + calib + qpu
   sdk.set_batch_tags(batch_id, tags)                        # amend afterwards
   ```
4. Writes `batch_ids.json` immediately after submission, then returns. The last
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

## Step 2b — Closed loop, only when the next wave depends on this one

An **open batch** keeps the device reserved for you: jobs added later run
immediately instead of queueing again behind everyone else. That is what makes
an adaptive scan or a variational loop possible — and it is also a way to hold a
shared QPU hostage, so it is not the default and it needs a reason you can say
out loud.

Use it when the next wave genuinely depends on the measured result: refining the
scan around a transition the first wave located, or a variational step. Do not
use it to "keep the option open".

```bash
python support/submit_qpu.py … --open-batch          # first wave, batch stays open
# read the results with harvest-and-analyze, decide the next points, then:
python support/submit_qpu.py --out-dir experiments/<name>/results/qpu/ \
    --spec … --seq-file … --project-id … --add-jobs 24,28,32 --confirm
python support/submit_qpu.py --out-dir experiments/<name>/results/qpu/ \
    --project-id … --close-batch                     # releases the device
```

The added wave reuses the recorded calibration offsets, so both halves of the
scan are comparable. Two things to tell the user before starting:

- **an open batch with nothing left to run is killed `TIMED_OUT` after a few
  minutes** — so compute the next wave promptly, or close the batch and submit
  the rest as its own run;
- while it is open, the device is unavailable to everyone else. Close it as soon
  as the last wave is in.

The agent never decides the next wave alone: show the points, say why, and wait.

---

## Step 3 — Collect and analyze

**Next step**: `harvest-and-analyze`. Collection, observable computation, EMU
comparison and the accept/reject verdict all belong to it:

```bash
python <harvest-and-analyze>/support/harvest_qpu.py \
    --spec      experiments/<name>/<name>_spec.json \
    --seq-file  experiments/<name>/<name>_sequence.py \
    --batch-ids experiments/<name>/results/qpu/batch_ids.json \
    --emu-dir   experiments/<name>/results/emu/ \
    --out-dir   experiments/<name>/results/qpu/
```

It tolerates partial completion: jobs that are not `DONE` are reported and
skipped, so re-running later fills the gaps.

---

## Output files

```
experiments/<name>/results/qpu/
  batch_ids.json                    the batch, its jobs, its labels, the account
  calibration/
    calibration_fits.png            Rydberg spectroscopy + Rabi fits
    calib_results.json              omega_ratio, delta_offset
```

`batch_ids.json` layout:

```json
{
  "format": "single_batch",
  "shape": "per_job_sequence",
  "scan_variable": "t_ns",
  "device": "FRESNEL_CAN1",
  "account": {"username": "…", "project_id": "…"},
  "tags": ["exp:square_lattice_eom_quench", "stage:experiment", "…"],
  "open": false,
  "batch_id": "…",
  "builder_kwargs": {"omega_offset": 1.032, "delta_offset": 0.187},
  "calibration": {"omega_ratio": 0.969, "delta_offset": 1.175, "batch_id": "…"},
  "jobs": [{"scan_value": 16, "job_id": "…", "variables": {}, "n_shots": 300}]
}
```

The `jobs` list is not decoration: a job that carries its own sequence cannot
also carry `variables`, so this file is the only place the job ↔ scan-point
pairing exists. `harvest-and-analyze` reads it from here.

Then append the step to `experiments/<name>/NOTEBOOK.md` — locus (QPU, which
device, which project), the command, the batch id and its tags, the shots spent,
and where `batch_ids.json` landed. A batch id in a chat log is lost; in the
notebook it is still there next month.

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
| `no project was chosen` | Expected, and not a bug to route around: run `pasqal_auth.py --whoami`, ask the user which project, pass `--project-id`. |
| `build_parametric_sequence() declares (…)` | The parametric builder must declare exactly the spec's scan variable. Fix it, or delete it and let the per-job-sequence shape run. |
| `the jobs do not all use the same register` | A warning, not a refusal: one batch is one atom loading pattern. Check the scan is not silently changing the geometry. |
| batch `TIMED_OUT` while open | An open batch with nothing left to run is killed after a few minutes. Re-submit the remaining points as their own run. |
| Large δ offset from calibration | If \|delta_offset\|/(2π) > 0.5 MHz, flag it to the user: that is above typical drift and may indicate a hardware issue. |
