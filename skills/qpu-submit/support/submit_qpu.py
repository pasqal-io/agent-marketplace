#!/usr/bin/env python3
"""Submit a spec-driven scan to a QPU, with an optional pre-calibration batch.

RUNS ON: a QPU, through Pasqal Cloud. Shots are billed and a submitted batch
cannot be recalled. Everything before the confirmation gate is local.

The QPU analogue of validate-emu's run_emu_scan.py: it consumes the same
`experiment_spec.json` and `*_sequence.py` contract, so any experiment that
reached validate-emu can be submitted without touching this file.

**One batch, one job per scan point.** A scan is one queue slot, one atom
loading pattern and one object to find again later — not N batches racing each
other through the queue with N different calibration drifts. Two shapes,
picked automatically:

  - the sequence file exposes `build_parametric_sequence(device=None, **fixed)
    -> (Sequence, (var_name,))` → one batch-level sequence, one `variables`
    binding per job. The canonical Pasqal Cloud shape.
  - it does not → the N concrete sequences from `build_sequence()` are submitted
    as N jobs of one batch, each carrying its own serialized sequence. The
    existing sequence-file contract is enough; nothing has to be regenerated.

Every batch is tagged, always: the experiment name, the device, the scan
variable, the register size, the shot count and the objective, so a batch can be
found months later from what it was for rather than from a UUID somebody wrote
down. `--tag` adds the user's own words.

Calibration measures the device's Rabi frequency and Rydberg resonance on a
small reference register, then feeds the measured offsets to the sequence
builder as `omega_offset` (multiplicative on Ω) and `delta_offset` (additive,
MHz) — the same convention noise-emulate uses, so an emulation run against
`batch_ids.json` reproduces exactly what the hardware ran.

Usage:
    python submit_qpu.py \\
        --spec       experiment_spec.json \\
        --seq-file   my_experiment_sequence.py \\
        --out-dir    experiments/my_experiment/results/qpu/ \\
        --project-id <the project the user picked> \\
        --confirm \\
        [--shots 300] [--device FRESNEL_CAN1] [--tag "kibble-zurek run 2"] \\
        [--no-calibration] [--calib-poll 60] [--wait] [--open-batch]

    python submit_qpu.py --out-dir ... --project-id ... --add-jobs 24,28,32 \\
        --spec ... --seq-file ... --confirm      # second wave, open batch
    python submit_qpu.py --out-dir ... --project-id ... --close-batch

Nothing is submitted until the shot count has been approved *and* the project
that pays for it has been named: the script prints the plan with the account
block, then either reads a yes at the terminal or requires --confirm, which
stands for a go-ahead the user gave in the conversation. `--project-id` is
required, because the project id that happens to be in the environment is the
last one somebody exported, not a decision.

Outputs (in --out-dir):
    batch_ids.json       single_batch id, per-job scan values, tags, account
                         (written immediately after submission, crash recovery)
    calibration/calibration_fits.png, calib_results.json
"""
from __future__ import annotations
import argparse
import importlib.util
import inspect
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

from batch_tags import build_tags
from pasqal_auth import account_summary, load_credentials


def _load_seq_module(path: str):
    spec = importlib.util.spec_from_file_location("seq_mod", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _n_atoms(seq) -> int | None:
    """Register size, when the sequence has a concrete register."""
    try:
        return len(seq.register.qubit_ids)
    except Exception:                       # mappable register, or Pulser drift
        return None


def _register_signature(seq) -> str | None:
    """A cheap fingerprint of the register, to spot jobs that disagree."""
    try:
        coords = getattr(seq.register, "_coords", None) or [
            seq.register.qubits[q] for q in seq.register.qubit_ids]
        return ";".join(f"{float(c[0]):.3f},{float(c[1]):.3f}" for c in coords)
    except Exception:
        return None


# ── Calibration ────────────────────────────────────────────────────────────────

CALIB_OFFSET_PARAMS = ("omega_offset", "delta_offset")

# Calibration batch size. Named here because two places need it: the builder
# below, and the cost the user approves before anything is submitted.
CALIB_N_DET, CALIB_N_RABI_EARLY, CALIB_N_RABI_LATE = 30, 8, 12
CALIB_SHOTS  = 20
CALIB_N_JOBS = CALIB_N_DET + CALIB_N_RABI_EARLY + CALIB_N_RABI_LATE


def _confirm_submission(plan: str, confirmed: bool) -> None:
    """Refuse to spend hardware shots that nobody approved.

    The plan is printed either way, so the numbers are on the record whether the
    user says yes at a prompt or the agent passes --confirm after being told to
    go ahead in the conversation. With no terminal there is nobody to ask, and
    the wrong default there is an agent buying shots on its own behalf — so the
    absence of an answer is a refusal, not a yes.
    """
    print(plan, flush=True)
    if confirmed:
        print("  approved by --confirm\n", flush=True)
        return
    if not sys.stdin.isatty():
        raise SystemExit(
            "✘ nothing has approved this submission, and there is no terminal "
            "to ask at.\n"
            "  Show the plan above to the user, get an explicit go-ahead, then "
            "re-run with --confirm.\n"
            "  If any of those numbers or the device changed since they agreed, "
            "ask again: the\n"
            "  earlier go-ahead was for a different submission.")
    if input("  Submit this to hardware? [y/N] ").strip().lower() not in ("y", "yes"):
        raise SystemExit("✘ aborted — nothing was submitted.")
    print(flush=True)


def _check_builder_accepts_offsets(build_sequence) -> None:
    """Fail loudly if the builder cannot receive the calibration offsets.

    `build_sequence(device=None, **params)` swallows unknown keywords, so a
    builder that ignores omega_offset/delta_offset would submit *uncalibrated*
    jobs while the manifest claims they were compensated. Wrong physics, no
    error message. Require the parameters to be named explicitly.
    """
    params  = inspect.signature(build_sequence).parameters
    missing = [p for p in CALIB_OFFSET_PARAMS if p not in params]
    if missing:
        raise SystemExit(
            f"✘ build_sequence() does not declare {', '.join(missing)}.\n"
            "  Calibration offsets would be silently discarded and the jobs\n"
            "  submitted uncalibrated. Either add them to the builder:\n"
            "      def build_sequence(device=None, omega_offset=1.0, "
            "delta_offset=0.0, **params):\n"
            "          omega = 2*np.pi*params['omega_max_mhz'] * omega_offset\n"
            "          delta = delta_nominal + 2*np.pi*delta_offset\n"
            "  or submit without calibration: --no-calibration")


def make_calibration_parametric(omega: float, device) -> tuple:
    """Parametric calibration sequence on a small reference register.

    Rydberg spectroscopy (detuning scan at fixed π-pulse) + Rabi oscillations
    (duration scan on resonance). Variables: duration_0, amp_0, detuning.
    Returns (seq, job_params, det_scan, tpulse_scan).
    """
    from pulser import Sequence
    from pulser.register.special_layouts import TriangularLatticeLayout

    layout = TriangularLatticeLayout(61, 8)
    reg    = layout.define_register(4, 15, 18, 30, 42, 45, 56)
    reg    = reg.with_automatic_layout(device)

    seq = Sequence(reg, device)
    seq.declare_channel("ising", "rydberg_global")
    dt  = seq.declare_variable("duration_0", dtype=int)
    amp = seq.declare_variable("amp_0",      dtype=float)
    det = seq.declare_variable("detuning",   dtype=float)
    seq.enable_eom_mode("ising", amp_on=amp, detuning_on=det)
    seq.add_eom_pulse("ising", duration=dt, phase=0.0)
    seq.disable_eom_mode("ising")

    N_det, N_rabi_early, N_rabi_late, shots = (
        CALIB_N_DET, CALIB_N_RABI_EARLY, CALIB_N_RABI_LATE, CALIB_SHOTS)
    tpi_int  = int(round(np.pi / omega * 1e3))          # ns
    det_scan = np.linspace(-1.5*omega, 2.5*omega, N_det).astype(float)

    T = 2*np.pi / omega * 1e3                           # Rabi period, ns
    max_per = max(min(5, int(5000/T)) - 1, 1)
    t_early = np.linspace(20, T, N_rabi_early)
    t_late  = np.linspace(max_per*T, (max_per+1.5)*T, N_rabi_late)
    tpulse  = np.clip(np.concatenate([t_early, t_late]), 16, None)

    job_params = [
        {"runs": shots, "variables":
         {"duration_0": tpi_int, "amp_0": float(omega), "detuning": float(d)}}
        for d in det_scan
    ] + [
        {"runs": shots, "variables":
         {"duration_0": int(round(tp)), "amp_0": float(omega), "detuning": 0.0}}
        for tp in tpulse
    ]
    return seq, job_params, det_scan, tpulse.astype(float)


def _bitstring_stats(job):
    """Laplace-smoothed mean occupation and its stderr from a QPU job result."""
    result  = job.result                       # {bitstring: count}
    Na      = len(next(iter(result)))
    n_shots = sum(result.values())
    occ = np.zeros(Na)
    for bs, cnt in result.items():
        for i, b in enumerate(bs):
            occ[i] += int(b) * cnt
    tot = int(occ.sum())
    mean_smooth = (tot + 1) / (Na * n_shots + 2)
    err_smooth  = np.sqrt((tot+1)*(Na*n_shots-tot+1) /
                          ((Na*n_shots+2)**2*(Na*n_shots+3)))
    return mean_smooth, err_smooth, occ / n_shots


def analyze_calibration(rydberg_jobs, rabi_jobs, det_scan, tpulse_scan,
                        omega: float, t_pi_ns: float, out_dir: Path) -> dict:
    """Two-round Rydberg-spectroscopy + Rabi fit. Returns offset corrections."""
    # Imported here, not at module level: the plan, the confirmation gate and
    # --self-test must run on a machine that has no plotting or fitting stack.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.optimize import curve_fit

    means_det = np.array([_bitstring_stats(j)[0] for j in rydberg_jobs])
    errs_det  = np.array([_bitstring_stats(j)[1] for j in rydberg_jobs])

    # QPU bitstrings count |r⟩=1 (Rydberg occupation), but the rydberg_spec
    # model returns ground-state survival probability (starts at 1, dips at
    # resonance). Invert the data once so argmin correctly finds the dip.
    means_det = 1.0 - means_det

    def rydberg_spec(delta_p, delta_c, Om):
        eps, eps_p, eta = 0.01, 0.07, 0.01
        d = delta_p - delta_c
        R = 1 - Om**2/(Om**2+d**2) * np.sin(np.sqrt(Om**2+d**2)*t_pi_ns*1e-3/2)**2
        return (1-eps)*(eta + eps_p - eta*eps_p + (1-eta)*(1-eps_p)*R)

    p0     = [det_scan[np.argmin(means_det)], omega]
    bounds = ((det_scan[0], omega*0.95), (det_scan[-1], omega*1.05))
    popt, _ = curve_fit(rydberg_spec, det_scan, means_det, sigma=errs_det+1e-6,
                        p0=p0, bounds=bounds, maxfev=10000)
    delta_offset_1 = popt[0]

    means_rabi = np.array([_bitstring_stats(j)[0] for j in rabi_jobs])
    errs_rabi  = np.array([_bitstring_stats(j)[1] for j in rabi_jobs])

    def rabi(t, omega_, A_, offset_, sigma_, phi_):
        return offset_ + A_ * np.sin(omega_*t*1e-3+phi_) * np.exp(-2*(t*1e-3)**2*sigma_)

    p0_r     = [omega, 1, 0.5, 0.1, np.pi/2]
    bounds_r = ((omega*0.5, 0, 0, 0, 0), (omega*3, 1, 1, np.inf, 2*np.pi))
    popt_r, _ = curve_fit(rabi, tpulse_scan, means_rabi, sigma=errs_rabi+1e-6,
                          p0=p0_r, bounds=bounds_r, maxfev=10000)
    omega_ratio_1 = np.sqrt(max(popt_r[0]**2 - delta_offset_1**2, 0)) / omega

    # Round 2, with the updated Ω. Guard: if omega_ratio_1 collapsed to 0,
    # fall back to a wide ±20% window.
    omega_eff_1 = max(omega * omega_ratio_1, omega * 0.3)
    p0_2     = [det_scan[np.argmin(means_det)], omega_eff_1]
    bounds_2 = ((det_scan[0], omega_eff_1 * 0.8), (det_scan[-1], omega_eff_1 * 1.2))
    popt_2, _ = curve_fit(rydberg_spec, det_scan, means_det, sigma=errs_det+1e-6,
                          p0=p0_2, bounds=bounds_2, maxfev=10000)
    delta_offset_2 = popt_2[0]

    popt_r2, _ = curve_fit(rabi, tpulse_scan, means_rabi, sigma=errs_rabi+1e-6,
                           p0=p0_r, bounds=bounds_r, maxfev=10000)
    omega_ratio_2 = np.sqrt(max(popt_r2[0]**2 - delta_offset_2**2, 0)) / omega

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].errorbar(det_scan/(2*np.pi), means_det, errs_det, fmt="s", ms=4, label="data")
    axes[0].plot(det_scan/(2*np.pi), rydberg_spec(det_scan, *popt_2),
                 label=f"fit: δ₀={delta_offset_2/(2*np.pi):.3f} MHz, "
                       f"Ω={popt_2[1]/(2*np.pi):.3f} MHz")
    axes[0].set_xlabel("Detuning / 2π (MHz)"); axes[0].set_ylabel("⟨n⟩")
    axes[0].legend(fontsize=8); axes[0].set_title("Rydberg spectroscopy")

    axes[1].errorbar(tpulse_scan, means_rabi, errs_rabi, fmt="s", ms=4, label="data")
    axes[1].plot(tpulse_scan, rabi(tpulse_scan, *popt_r2),
                 label=f"fit: Ω_eff={popt_r2[0]/(2*np.pi):.3f} MHz, "
                       f"ratio={omega_ratio_2:.4f}")
    axes[1].set_xlabel("Pulse duration (ns)"); axes[1].set_ylabel("⟨n⟩")
    axes[1].legend(fontsize=8); axes[1].set_title("Rabi oscillations")

    plt.tight_layout()
    fig.savefig(out_dir / "calibration_fits.png", bbox_inches="tight")
    plt.close()
    print(f"  Calibration plots → {out_dir/'calibration_fits.png'}")

    return {
        "omega_ratio":     omega_ratio_2,
        "delta_offset":    delta_offset_2,      # rad/µs
        "omega_ratio_r1":  omega_ratio_1,
        "delta_offset_r1": delta_offset_1,
    }


def run_calibration(sdk, device, device_name: str, omega: float,
                    poll: int, out_dir: Path, tags: list[str]) -> dict:
    """Submit the calibration batch, wait for it, fit. Returns offsets dict."""
    calib_dir = out_dir / "calibration"
    calib_dir.mkdir(parents=True, exist_ok=True)

    seq, job_params, det_scan, tpulse_scan = make_calibration_parametric(omega, device)
    n_jobs, n_det = len(job_params), len(det_scan)
    print(f"  {n_jobs} calibration jobs ({n_det} Rydberg + {len(tpulse_scan)} Rabi)")

    batch = sdk.create_batch(seq.to_abstract_repr(), [], open=True, wait=True,
                             device_type=device_name, tags=tags)
    print(f"  Calibration batch: {batch.id}  tags: {', '.join(tags)}")
    batch.add_jobs(job_params, wait=False)
    batch.close()

    print(f"  Waiting for calibration (polling every {poll} s)...")
    while True:
        batch  = sdk.get_batch(batch.id)
        states = [j.status for j in batch.ordered_jobs]
        n_done = sum(s == "DONE" for s in states)
        n_err  = sum(s == "ERROR" for s in states)
        print(f"    {n_done}/{n_jobs} DONE, {n_err} ERROR", flush=True)
        if n_done + n_err == n_jobs:
            break
        time.sleep(poll)

    results = analyze_calibration(
        batch.ordered_jobs[:n_det], batch.ordered_jobs[n_det:],
        det_scan, tpulse_scan, omega, np.pi / omega * 1e3, calib_dir,
    )
    results["batch_id"] = batch.id
    (calib_dir / "calib_results.json").write_text(json.dumps(results, indent=2))
    return results


# ── Building the one batch ─────────────────────────────────────────────────────

def _check_duration(seq, device, device_name: str, label: str) -> None:
    if seq.get_duration() > device.max_sequence_duration:
        raise SystemExit(
            f"✘ {label}: sequence is {seq.get_duration()} ns, over "
            f"{device_name}'s {device.max_sequence_duration} ns limit. "
            "Shorten the scan range or the pulse schedule.")


def build_jobs(mod, spec: dict, device, device_name: str, values: list,
               shots: int, offsets: dict, CreateJob) -> tuple:
    """One job per scan point, for the one batch. Returns (shape, batch_repr, jobs, n_atoms).

    Preferred shape is a parametrized batch sequence with one variable binding
    per job — what the cloud is built for. The fallback submits the N concrete
    sequences as N jobs of the same batch, which keeps working with every
    sequence file the pipeline has already generated. Either way the scan is one
    batch: one queue slot, one atom loading, one thing to find later.
    """
    variable = spec["scan"]["variable"]
    fixed    = spec["scan"].get("fixed_params", {})
    build_sequence = getattr(mod, spec.get("builder_fn", "build_sequence"))
    parametric     = getattr(mod, "build_parametric_sequence", None)

    if parametric is not None:
        seq, var_names = parametric(device=device, **fixed, **offsets)
        if tuple(var_names) != (variable,):
            raise SystemExit(
                f"✘ build_parametric_sequence() declares {tuple(var_names)}, but "
                f"the spec scans {variable!r}.\n"
                "  The parametric builder must declare exactly the scan "
                "variable as its Pulser variable; everything else is fixed and "
                "baked in. Fix the builder, or delete it to fall back on one "
                "serialized sequence per job.")
        for val in values:                       # free, local, before anything ships
            _check_duration(seq.build(**{variable: val}), device, device_name,
                            f"{variable}={val}")
        jobs = [CreateJob(runs=shots, variables={variable: val}) for val in values]
        print(f"  shape: one parametrized batch sequence, {len(jobs)} variable "
              f"bindings ({variable})")
        return "parametric", seq.to_abstract_repr(), jobs, _n_atoms(seq)

    jobs, signatures, n_atoms = [], set(), None
    for val in values:
        seq = build_sequence(device=device, **{**fixed, variable: val, **offsets})
        _check_duration(seq, device, device_name, f"{variable}={val}")
        jobs.append(CreateJob(runs=shots,
                              serialized_sequence=seq.to_abstract_repr()))
        signatures.add(_register_signature(seq))
        n_atoms = _n_atoms(seq) or n_atoms
    print(f"  shape: {len(jobs)} jobs, each carrying its own sequence "
          "(no parametric builder in the sequence file)")
    if len(signatures) > 1:
        print(f"  ⚠  the {len(signatures)} jobs do not all use the same register. "
              "One batch is one atom loading pattern — check this is intended.")
    return "per_job_sequence", None, jobs, n_atoms


def _job_list(sdk, batch) -> list:
    """The batch's jobs in submission order, re-fetched once if they are absent.

    The create response normally carries them, but the job ↔ scan-point pairing
    is the one thing this file exists to record: an empty list here would lose
    it for good, and one extra read is cheaper than unattributable shots.
    """
    jobs = list(getattr(batch, "ordered_jobs", None) or [])
    if not jobs:
        jobs = list(getattr(sdk.get_batch(str(batch.id)), "ordered_jobs", None) or [])
    if not jobs:
        print("  ⚠  the cloud returned no job ids for this batch. The scan "
              "values are recorded without them;\n     harvest-and-analyze will "
              "need the batch's own job order to pair them up.")
    return jobs


def record_jobs(ordered: list, values: list, variable: str, shots: int,
                shape: str) -> list:
    """Pair each submitted job id with the scan point it stands for.

    `ordered_jobs` comes back in submission order, which is the order of
    `values`. Recording the pairing is not optional: in the per-job-sequence
    shape the cloud holds no `variables` to recover it from, so this file is the
    only place the mapping exists.

    Callers adding a wave to an open batch pass only the tail of `ordered_jobs`,
    because `add_jobs` returns the whole batch, earlier waves included.
    """
    if ordered and len(ordered) != len(values):
        print(f"  ⚠  {len(ordered)} jobs came back for {len(values)} scan points "
              "— the pairing below is by order and should be checked.")
    records = []
    for i, val in enumerate(values):
        records.append({
            "scan_value": val,
            "job_id":     str(ordered[i].id) if i < len(ordered) else None,
            "variables":  {variable: val} if shape == "parametric" else {},
            "n_shots":    shots,
        })
    return records


def _self_test() -> None:
    """Offline asserts on the label and mapping logic. No network, no Pulser."""
    spec = {"experiment_name": "Square Lattice Quench", "version": "1.0",
            "objective": "Does the Z2 order survive a fast quench?",
            "scan": {"variable": "t_ns", "values": [16, 24]}}

    class _J:
        def __init__(self, i): self.id = f"job-{i}"

    ordered = [_J(0), _J(1)]
    recs = record_jobs(ordered, [16, 24], "t_ns", 300, "per_job_sequence")
    assert [r["job_id"] for r in recs] == ["job-0", "job-1"], recs
    assert recs[0]["variables"] == {}, recs
    recs_p = record_jobs(ordered, [16, 24], "t_ns", 300, "parametric")
    assert recs_p[1]["variables"] == {"t_ns": 24}, recs_p

    plan = _plan_text({**spec, "shots_per_point": 300}, "FRESNEL_CAN1", 300,
                      [16, 24], calib_shots=1000)
    assert "batches           1" in plan and "TOTAL QPU SHOTS   1600" in plan, plan
    wave = _plan_text(spec, "FRESNEL_CAN1", 300, [32], calib_shots=0,
                      calib_note="reusing the offsets recorded for this batch",
                      adding_to="b-1")
    assert "adding 1 job(s) to open batch b-1" in wave, wave
    assert "no-calibration" not in wave and "reusing the offsets" in wave, wave
    print("submit_qpu self-test OK")


# ── Main ───────────────────────────────────────────────────────────────────────

def _plan_text(spec: dict, device_name: str, shots: int, values: list,
               calib_shots: int, calib_note: str | None = None,
               adding_to: str | None = None) -> str:
    """The spec-derived half of the plan: no credentials, no network."""
    variable = spec["scan"]["variable"]
    return "\n".join([
        f"=== qpu-submit: {spec['experiment_name']} — submission plan ===",
        f"  device            {device_name}"
        + ("   (region: SA1)" if os.environ.get("PASQAL_REGION") == "sa" else ""),
        f"  scan              {variable} ∈ {values}",
        (f"  batches           adding {len(values)} job(s) to open batch "
         f"{adding_to}" if adding_to else
         f"  batches           1  ({len(values)} jobs, one per scan point)"),
        f"  shots per job     {shots}",
        f"  experiment shots  {len(values) * shots}",
        "  calibration       " + (
            f"{CALIB_N_JOBS} jobs × {CALIB_SHOTS} shots = {calib_shots} shots  "
            "(its own batch)" if calib_shots else
            calib_note or
            "skipped (--no-calibration): jobs run at nominal Ω and δ"),
        f"  TOTAL QPU SHOTS   {len(values) * shots + calib_shots}",
    ])


def main():
    ap = argparse.ArgumentParser(
        description="Submit a spec-driven scan to a QPU as one tagged batch, "
                    "with optional calibration.")
    ap.add_argument("--spec")
    ap.add_argument("--seq-file")
    ap.add_argument("--out-dir")
    ap.add_argument("--project-id",      default=None,
                    help="the project the user chose to pay for this run. "
                         "Required: run `python pasqal_auth.py --whoami` first, "
                         "show them the projects and credits, and ask.")
    ap.add_argument("--shots",           type=int, default=None,
                    help="shots per scan point (default: spec.shots_per_point)")
    ap.add_argument("--device",          default=None,
                    help="device name (default: spec.device)")
    ap.add_argument("--tag",             action="append", default=[],
                    help="extra batch label, in the user's own words; repeatable")
    ap.add_argument("--no-calibration",  action="store_true",
                    help="submit at nominal Ω and δ, without a calibration batch")
    ap.add_argument("--calib-poll",      type=int, default=60,
                    help="calibration poll interval in seconds (default 60)")
    ap.add_argument("--wait",            action="store_true",
                    help="wait for every experiment job to complete before returning")
    ap.add_argument("--open-batch",      action="store_true",
                    help="leave the batch open so a later wave of jobs runs on "
                         "the same reservation (closed-loop). The QPU stays held "
                         "for this batch, and an open batch with nothing to run "
                         "is killed TIMED_OUT after a few minutes — only use it "
                         "when the next wave is already being computed.")
    ap.add_argument("--add-jobs",        default=None,
                    help="comma-separated scan values to add to the open batch "
                         "recorded in --out-dir/batch_ids.json")
    ap.add_argument("--close-batch",     action="store_true",
                    help="close the open batch recorded in --out-dir, releasing "
                         "the device")
    ap.add_argument("--self-test",      action="store_true",
                    help="offline asserts on the label and mapping logic")
    ap.add_argument("--confirm",         action="store_true",
                    help="the user has seen the shot count, the project it is "
                         "billed to and its remaining credits, and approved this "
                         "submission. Without it the script prints the plan and "
                         "asks at the terminal, or refuses if there is none.")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    print("RUNS ON: a QPU, through Pasqal Cloud — billed shots, no recall.\n"
          "  Everything up to the confirmation gate is local and free.\n",
          flush=True)

    missing = [f"--{n.replace('_', '-')}" for n in ("out_dir", "project_id")
               if not getattr(args, n)]
    if missing:
        raise SystemExit(f"✘ missing required argument(s): {', '.join(missing)}")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    batch_ids_path = out / "batch_ids.json"
    previous = (json.loads(batch_ids_path.read_text())
                if batch_ids_path.exists() else None)

    if args.close_batch:
        _close_batch(args, previous, batch_ids_path)
        return

    if not args.add_jobs:
        # Nothing here is idempotent: a re-run submits a fresh calibration batch
        # and every scan point again, on hardware, then overwrites this file — so
        # the first submission's shots are both paid for and unrecoverable,
        # because its batch IDs only ever existed here. Refuse.
        if previous is not None:
            n = len(previous.get("jobs", previous.get("batches", [])))
            raise SystemExit(
                f"✘ {batch_ids_path} already records a submission of {n} job(s) "
                f"from {previous.get('ts', 'an earlier run')}.\n"
                "  Re-running would buy the same shots twice and overwrite the "
                "only record of the first submission.\n"
                "  Collect what was already submitted:  harvest-and-analyze with "
                f"--batch-ids {batch_ids_path}\n"
                "  Add a wave to an open batch:  --add-jobs <values>\n"
                "  Submit a genuinely different run into another --out-dir.")

    missing = [f"--{n.replace('_', '-')}" for n in ("spec", "seq_file")
               if not getattr(args, n)]
    if missing:
        raise SystemExit(f"✘ missing required argument(s): {', '.join(missing)}")

    spec        = json.loads(Path(args.spec).read_text())
    shots       = args.shots or spec["shots_per_point"]
    device_name = args.device or spec["device"]
    scan        = spec["scan"]
    variable    = scan["variable"]
    values      = scan["values"]

    if args.add_jobs:
        if not previous:
            raise SystemExit(f"✘ no batch recorded in {batch_ids_path} to add to.")
        if not previous.get("open"):
            raise SystemExit(
                f"✘ the batch in {batch_ids_path} is not open, so no job can be "
                "added to it. A closed batch is final: submit the extra points "
                "as their own run, in their own --out-dir.")
        values      = [json.loads(v) for v in args.add_jobs.split(",")]
        already     = [j["scan_value"] for j in previous.get("jobs", [])]
        overlap     = [v for v in values if v in already]
        if overlap:
            print(f"  ⚠  {overlap} were already submitted in this batch — "
                  "adding them again buys those shots twice.")
        print(f"── Adding {len(values)} job(s) to open batch "
              f"{previous['batch_id']}")

    # The spec-derived half of the plan needs neither credentials nor network.
    calib_shots = 0 if (args.no_calibration or args.add_jobs) else \
        CALIB_N_JOBS * CALIB_SHOTS
    # Printed before the cloud is contacted, so someone with no credentials at
    # all still sees the numbers they are being asked about.
    print(_plan_text(
        spec, device_name, shots, values, calib_shots,
        calib_note=("reusing the offsets recorded for this batch — no new "
                    "calibration shots" if args.add_jobs else None),
        adding_to=previous["batch_id"] if args.add_jobs else None), flush=True)

    mod            = _load_seq_module(args.seq_file)
    build_sequence = getattr(mod, spec.get("builder_fn", "build_sequence"))
    if not (args.no_calibration or args.add_jobs):
        _check_builder_accepts_offsets(build_sequence)

    from pasqal_cloud import SDK, CreateJob
    from pulser.json.abstract_repr.deserializer import deserialize_device

    # Opening a session and reading the account is free and submits nothing, and
    # it is what puts "whose credits, and how many are left" into the plan the
    # user approves. A cost without a payer is the approval the tester gave by
    # accident.
    creds = load_credentials(project_id=args.project_id,
                             require_explicit_project=True)
    sdk   = SDK(**creds)
    specs = sdk.get_device_specs_dict()
    if device_name not in specs:
        raise SystemExit(f"✘ device {device_name!r} not available in this project. "
                         f"Available: {sorted(specs)}")
    device = deserialize_device(specs[device_name])

    print(account_summary(sdk, creds["project_id"], creds.get("region"),
                          creds.get("username")), flush=True)
    _confirm_submission("\n  Metered, and a submitted batch cannot be recalled.",
                        args.confirm)

    # The plan the user approved was priced from the spec; this is the live
    # device it will actually run on.
    print(f"  live device {device_name}: C6={device.interaction_coeff:.0f} "
          f"rad·µm⁶/µs, max {device.max_atom_num} atoms\n")

    # ── Calibration ───────────────────────────────────────────────────────────
    offsets = {"omega_offset": 1.0, "delta_offset": 0.0}
    calib   = {}
    if args.add_jobs:
        # The added wave must run under the offsets the first wave was
        # compensated with, or the two halves of one scan are not comparable.
        offsets = previous.get("builder_kwargs", offsets)
        calib   = previous.get("calibration", {})
        print(f"── Reusing the recorded calibration: {offsets}\n")
    elif not args.no_calibration:
        print("── Calibration batch")
        omega = 2 * np.pi * spec["pulse"]["omega_max_mhz"]
        calib = run_calibration(
            sdk, device, device_name, omega, args.calib_poll, out,
            build_tags(spec, device_name, CALIB_SHOTS, "calibration",
                       extra=args.tag))
        # Convention shared with noise-emulate: the builder scales Ω by
        # omega_offset and adds 2π·delta_offset (MHz) to the detuning.
        omega_offset = 1.0 / calib["omega_ratio"] if calib["omega_ratio"] else 1.0
        # Compensation always pushes Ω up (hardware delivers less than the
        # setpoint). Cap it at the channel maximum, or the builder would raise
        # after the calibration batch has already been paid for.
        max_amp = device.channels["rydberg_global"].max_amp
        if max_amp and omega * omega_offset > max_amp:
            capped = max_amp / omega
            print(f"  Ω compensation {omega_offset:.5f} would exceed the channel "
                  f"maximum ({max_amp/(2*np.pi):.3f} MHz) — capping at {capped:.5f}")
            omega_offset = capped
        offsets = {
            "omega_offset": omega_offset,
            "delta_offset": calib["delta_offset"] / (2 * np.pi),
        }
        print(f"  Ω ratio  = {calib['omega_ratio']:.5f}  "
              f"→ omega_offset = {offsets['omega_offset']:.5f}")
        print(f"  δ offset = {offsets['delta_offset']:+.4f} MHz\n")
    else:
        print("── Calibration skipped (--no-calibration): submitting at nominal "
              "Ω and δ\n")

    # ── One batch, one job per scan point ─────────────────────────────────────
    print("── Experiment batch")
    shape, batch_repr, jobs, n_atoms = build_jobs(
        mod, spec, device, device_name, values, shots, offsets, CreateJob)
    tags = build_tags(spec, device_name, shots, "experiment", n_atoms=n_atoms,
                      extra=args.tag)

    if args.add_jobs:
        batch = sdk.add_jobs(previous["batch_id"], jobs, wait=False)
        new_jobs = _job_list(sdk, batch)[-len(values):]
        record = previous
        record["jobs"] = previous.get("jobs", []) + record_jobs(
            new_jobs, values, variable, shots, shape)
        record["waves"] = record.get("waves", 1) + 1
    else:
        batch = sdk.create_batch(
            serialized_sequence=batch_repr, jobs=jobs,
            device_type=device_name, tags=tags, open=args.open_batch, wait=False,
        )
        record = {
            "ts":             time.strftime("%Y-%m-%dT%H:%M:%S"),
            "experiment":     spec["experiment_name"],
            "format":         "single_batch",
            "shape":          shape,
            "scan_variable":  variable,
            "device":         device_name,
            "account":        {"username":   creds["username"],
                               "project_id": creds["project_id"]},
            "tags":           tags,
            "open":           bool(args.open_batch),
            "batch_id":       str(batch.id),
            "builder_kwargs": offsets,
            "calibration":    calib,
            "jobs":           record_jobs(
                _job_list(sdk, batch), values, variable, shots, shape),
        }
        print(f"  batch {batch.id}  ({len(jobs)} jobs)")
        print(f"  tags  {', '.join(tags)}")

    batch_ids_path.write_text(json.dumps(record, indent=2))
    print(f"\n  batch_ids saved → {batch_ids_path}")
    for j in record["jobs"][-len(values):]:
        print(f"    {variable}={j['scan_value']}  →  job {j['job_id']}")

    if record["open"]:
        print("\n  ⚠  the batch is OPEN: the device stays reserved for it, and an "
              "open batch\n     with nothing left to run is killed TIMED_OUT "
              "after a few minutes.\n"
              f"     Add the next wave:  --add-jobs <values> --out-dir {out}\n"
              f"     Release the device: --close-batch --out-dir {out}")

    if args.wait:
        print("  Waiting for all jobs to complete...")
        while True:
            states = [j.status for j in sdk.get_batch(record["batch_id"]).ordered_jobs]
            done = sum(s in ("DONE", "ERROR", "CANCELED", "TIMED_OUT")
                       for s in states)
            print(f"    {done}/{len(states)} terminal", flush=True)
            if done == len(states):
                break
            time.sleep(args.calib_poll)

    print(f"\n  Next: harvest-and-analyze with --batch-ids {batch_ids_path}")
    print(batch_ids_path)  # machine-readable last line


def _close_batch(args, previous, batch_ids_path) -> None:
    """Release the device held by an open batch, and record that it is closed."""
    if not previous or not previous.get("batch_id"):
        raise SystemExit(f"✘ no batch recorded in {batch_ids_path} to close.")
    from pasqal_cloud import SDK
    creds = load_credentials(project_id=args.project_id,
                             require_explicit_project=True)
    SDK(**creds).close_batch(previous["batch_id"])
    previous["open"] = False
    batch_ids_path.write_text(json.dumps(previous, indent=2))
    print(f"  batch {previous['batch_id']} closed — the device is released.")
    print(f"\n  Next: harvest-and-analyze with --batch-ids {batch_ids_path}")
    print(batch_ids_path)


if __name__ == "__main__":
    main()
