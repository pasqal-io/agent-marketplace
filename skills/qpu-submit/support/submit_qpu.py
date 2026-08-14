#!/usr/bin/env python3
"""Submit a spec-driven scan to a QPU, with an optional pre-calibration batch.

The QPU analogue of validate-emu's run_emu_scan.py: it consumes the same
`experiment_spec.json` and `*_sequence.py` contract, so any experiment that
reached validate-emu can be submitted without touching this file.

One batch per scan point (one job each), which is the `per_point` format
harvest-and-analyze reads back.

Calibration measures the device's Rabi frequency and Rydberg resonance on a
small reference register, then feeds the measured offsets to the sequence
builder as `omega_offset` (multiplicative on Ω) and `delta_offset` (additive,
MHz) — the same convention noise-emulate uses, so an emulation run against
`batch_ids.json` reproduces exactly what the hardware ran.

Usage:
    python submit_qpu.py \\
        --spec       experiment_spec.json \\
        --seq-file   my_experiment_sequence.py \\
        --out-dir    results/my_experiment/qpu/ \\
        [--shots 300] [--device FRESNEL_CAN1] \\
        [--no-calibration] [--calib-poll 60] [--wait]

Outputs (in --out-dir):
    batch_ids.json       per_point batch IDs + calibration block (written
                         immediately after submission, crash recovery)
    calibration/calibration_fits.png, calib_results.json
"""
from __future__ import annotations
import argparse
import importlib.util
import inspect
import json
import time
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

from pasqal_auth import load_credentials


def _load_seq_module(path: str):
    spec = importlib.util.spec_from_file_location("seq_mod", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Calibration ────────────────────────────────────────────────────────────────

CALIB_OFFSET_PARAMS = ("omega_offset", "delta_offset")


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

    N_det, N_rabi_early, N_rabi_late, shots = 30, 8, 12, 20
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
                    poll: int, out_dir: Path) -> dict:
    """Submit the calibration batch, wait for it, fit. Returns offsets dict."""
    calib_dir = out_dir / "calibration"
    calib_dir.mkdir(parents=True, exist_ok=True)

    seq, job_params, det_scan, tpulse_scan = make_calibration_parametric(omega, device)
    n_jobs, n_det = len(job_params), len(det_scan)
    print(f"  {n_jobs} calibration jobs ({n_det} Rydberg + {len(tpulse_scan)} Rabi)")

    batch = sdk.create_batch(seq.to_abstract_repr(), [], open=True, wait=True,
                             device_type=device_name)
    print(f"  Calibration batch: {batch.id}")
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


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Submit a spec-driven scan to a QPU, with optional calibration.")
    ap.add_argument("--spec",            required=True)
    ap.add_argument("--seq-file",        required=True)
    ap.add_argument("--out-dir",         required=True)
    ap.add_argument("--shots",           type=int, default=None,
                    help="shots per scan point (default: spec.shots_per_point)")
    ap.add_argument("--device",          default=None,
                    help="device name (default: spec.device)")
    ap.add_argument("--no-calibration",  action="store_true",
                    help="submit at nominal Ω and δ, without a calibration batch")
    ap.add_argument("--calib-poll",      type=int, default=60,
                    help="calibration poll interval in seconds (default 60)")
    ap.add_argument("--wait",            action="store_true",
                    help="wait for every experiment job to complete before returning")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    out  = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Nothing here is idempotent: a re-run submits a fresh calibration batch and
    # every scan point again, on hardware, then overwrites this file — so the
    # first submission's shots are both paid for and unrecoverable, because its
    # batch IDs only ever existed here. Refuse.
    batch_ids_path = out / "batch_ids.json"
    if batch_ids_path.exists():
        try:
            previous = json.loads(batch_ids_path.read_text())
            count = len(previous.get("batches", []))
            when = previous.get("ts", "an earlier run")
        except (json.JSONDecodeError, AttributeError):
            count, when = "?", "an earlier run"
        raise SystemExit(
            f"✘ {batch_ids_path} already records {count} submitted batch(es) "
            f"from {when}.\n"
            "  Re-running would buy the same shots twice and overwrite the only "
            "record of the first submission.\n"
            "  Collect what was already submitted:  harvest-and-analyze with "
            f"--batch-ids {batch_ids_path}\n"
            "  Submit a genuinely different run into another --out-dir.")

    shots       = args.shots or spec["shots_per_point"]
    device_name = args.device or spec["device"]
    scan        = spec["scan"]
    variable    = scan["variable"]
    values      = scan["values"]
    fixed       = scan.get("fixed_params", {})

    mod            = _load_seq_module(args.seq_file)
    build_sequence = getattr(mod, spec.get("builder_fn", "build_sequence"))
    if not args.no_calibration:
        _check_builder_accepts_offsets(build_sequence)

    from pasqal_cloud import SDK, CreateJob
    from pulser.json.abstract_repr.deserializer import deserialize_device

    sdk    = SDK(**load_credentials())
    specs  = sdk.get_device_specs_dict()
    if device_name not in specs:
        raise SystemExit(f"✘ device {device_name!r} not available in this project. "
                         f"Available: {sorted(specs)}")
    device = deserialize_device(specs[device_name])

    print(f"=== qpu-submit: {spec['experiment_name']} ===")
    print(f"  device={device_name}  C6={device.interaction_coeff:.0f} rad·µm⁶/µs")
    print(f"  {variable} ∈ {values}")
    print(f"  {len(values)} batches × {shots} shots = {len(values)*shots} QPU shots\n")

    # ── Calibration ───────────────────────────────────────────────────────────
    offsets = {"omega_offset": 1.0, "delta_offset": 0.0}
    calib   = {}
    if not args.no_calibration:
        print("── Calibration batch")
        omega = 2 * np.pi * spec["pulse"]["omega_max_mhz"]
        calib = run_calibration(sdk, device, device_name, omega,
                                args.calib_poll, out)
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

    # ── Experiment batches, one per scan point ────────────────────────────────
    print("── Experiment batches")
    batches = []
    for val in values:
        params = {**fixed, variable: val, **offsets}
        seq    = build_sequence(device=device, **params)
        if seq.get_duration() > device.max_sequence_duration:
            raise SystemExit(
                f"✘ {variable}={val}: sequence is {seq.get_duration()} ns, over "
                f"{device_name}'s {device.max_sequence_duration} ns limit. "
                "Shorten the scan range or the pulse schedule.")
        b = sdk.create_batch(
            serialized_sequence=seq.to_abstract_repr(),
            jobs=[CreateJob(runs=shots)],
            device_type=device_name, wait=False,
        )
        sdk.set_batch_tags(b.id, [spec["experiment_name"]])
        batches.append({"scan_value": val, "batch_id": str(b.id), "n_shots": shots})
        print(f"  {variable}={val}  →  {b.id}", flush=True)

    batch_ids_path.write_text(json.dumps({
        "ts":             time.strftime("%Y-%m-%dT%H:%M:%S"),
        "experiment":     spec["experiment_name"],
        "format":         "per_point",
        "scan_variable":  variable,
        "device":         device_name,
        "builder_kwargs": offsets,
        "calibration":    calib,
        "batches":        batches,
    }, indent=2))
    print(f"\n  batch_ids saved → {batch_ids_path}")

    if args.wait:
        print("  Waiting for all jobs to complete...")
        pending = {b["batch_id"] for b in batches}
        while pending:
            for bid in sorted(pending):
                st = sdk.get_batch(bid).ordered_jobs[0].status
                if st in ("DONE", "ERROR", "CANCELED", "TIMED_OUT"):
                    print(f"    {bid[:8]} {st}")
                    pending.discard(bid)
            if pending:
                time.sleep(args.calib_poll)

    print(f"\n  Next: harvest-and-analyze with --batch-ids {batch_ids_path}")
    print(batch_ids_path)  # machine-readable last line


if __name__ == "__main__":
    main()
