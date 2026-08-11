#!/usr/bin/env python3
"""
submit_qpu.py — Submit an EOM quench experiment to the FRESNEL_CAN1 QPU
                with a pre-calibration batch.

Workflow
--------
1. Connect to Pasqal Cloud SDK.
2. Fetch FRESNEL_CAN1 device specs and build the experiment's register/sequence.
3. Submit a calibration batch (7-atom triangular lattice, EOM Rabi + Rydberg
   spectroscopy). Wait for it to complete, fit the offsets.
4. Build a parametric experiment sequence using calibrated omega and detuning.
5. Submit the main batch (one job per observation time).
6. Save a manifest JSON and print the batch IDs.

The experiment sequence is an EOM quench on an N×N square lattice at hx/J = hx,
observed at n_times points from 4 ns to t_max_ns. It is always parametric:
variables {echo_time, omega_quench, detuning_quench} are filled per-job.

Usage
-----
python submit_qpu.py \\
    --N 5 --hx 6.0 --omega 12.5664 --t-max 4000 \\
    --shots 300 --n-times 75 \\
    --out-dir results/hx6_N5/ \\
    [--R-offset 1.0] [--no-calibration] [--wait]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

import pulser
from pulser import Sequence, Register
from pulser.register.special_layouts import SquareLatticeLayout, TriangularLatticeLayout
from pulser.register.register_layout import RegisterLayout
from pulser.json.abstract_repr.deserializer import deserialize_device
from pasqal_cloud import SDK

# ── Credentials ───────────────────────────────────────────────────────────────

def _load_credentials():
    """Priority: PASQAL_* env vars → ~/.pasqal_credentials.json."""
    env = {k: os.environ.get(f"PASQAL_{k.upper()}")
           for k in ("username", "password", "project_id")}
    if all(env.values()):
        return env
    cred_file = Path.home() / ".pasqal_credentials.json"
    if cred_file.exists():
        d = json.loads(cred_file.read_text())
        if all(k in d for k in ("username", "password", "project_id")):
            return d
    raise FileNotFoundError(
        "Pasqal Cloud credentials not found. Either set PASQAL_USERNAME, "
        "PASQAL_PASSWORD and PASQAL_PROJECT_ID, or create ~/.pasqal_credentials.json "
        'with {"username": ..., "password": ..., "project_id": ...} (chmod 600).')


# ── Register helpers ───────────────────────────────────────────────────────────

def make_square_register(N: int, R: float) -> Register:
    """N×N square lattice with checkerboard reservoir (FRESNEL-compatible layout)."""
    reg_coords  = SquareLatticeLayout(N, N, R).coords
    res_coords  = SquareLatticeLayout(N+1, N+1, R).coords
    shift = R*0.5 - R
    res_coords  = [[x-shift, y-shift] for x, y in res_coords]
    layout_coords = np.concatenate((reg_coords, res_coords))
    layout = RegisterLayout(layout_coords, slug=f"SqChecker{N}_{R:.3f}um")
    reg_ids = [i for i, (x, y) in enumerate(layout.coords)
               if (x, y) in set(map(tuple, reg_coords))]
    return layout.define_register(*reg_ids)


def central_site_detuning(N: int, R: float, C6: float) -> float:
    """Sum C6/r^6 from the central site of an N×N square lattice."""
    coords = SquareLatticeLayout(N, N, R).coords
    ci = (N//2)*N + (N//2)
    diff = coords - coords[ci]
    dist = np.linalg.norm(diff, axis=-1)
    dist[ci] = np.inf
    return C6 * np.sum(1.0 / dist**6)


# ── Experiment parametric sequence ─────────────────────────────────────────────

def make_experiment_parametric(N: int, R: float, device) -> Sequence:
    """
    Parametric EOM quench sequence on an N×N square lattice.
    Variables: echo_time (int, ns), omega_quench (float, rad/µs),
               detuning_quench (float, rad/µs).
    """
    register = make_square_register(N, R)
    if R < 10:
        register = register.with_automatic_layout(device)

    seq = Sequence(register, device)
    seq.declare_channel("ising", "rydberg_global")

    echo_time     = seq.declare_variable("echo_time", dtype=int)
    omega_quench  = seq.declare_variable("omega_quench", dtype=float)
    det_quench    = seq.declare_variable("detuning_quench", dtype=float)

    seq.enable_eom_mode("ising", amp_on=omega_quench, detuning_on=det_quench)
    seq.add_eom_pulse("ising", duration=echo_time, phase=0.0)
    seq.disable_eom_mode("ising")
    return seq


# ── Calibration ────────────────────────────────────────────────────────────────

def make_calibration_parametric(omega: float, device) -> tuple:
    """
    Parametric calibration sequence on a fixed 7-atom triangular lattice.
    Variables: duration_0 (int), amp_0 (float), detuning (float).
    Returns (seq, job_params_calib, det_scan, tpulse_scan).
    """
    layout = TriangularLatticeLayout(61, 8)
    reg    = layout.define_register(4, 15, 18, 30, 42, 45, 56)
    reg    = reg.with_automatic_layout(device)

    seq = Sequence(reg, device)
    seq.declare_channel("ising", "rydberg_global")
    dt     = seq.declare_variable("duration_0", dtype=int)
    amp    = seq.declare_variable("amp_0",      dtype=float)
    det    = seq.declare_variable("detuning",   dtype=float)
    seq.enable_eom_mode("ising", amp_on=amp, detuning_on=det)
    seq.add_eom_pulse("ising", duration=dt, phase=0.0)
    seq.disable_eom_mode("ising")

    # ── Job parameters ───────────────────────────────────────────────────────
    N_det, N_rabi_early, N_rabi_late, shots = 30, 8, 12, 20
    tpi     = np.pi / omega * 1e3          # ns
    tpi_int = int(round(tpi))
    det_scan = np.linspace(-1.5*omega, 2.5*omega, N_det).astype(float)

    T = 2*np.pi / omega * 1e3             # Rabi period ns
    max_per = max(min(5, int(5000/T)) - 1, 1)
    t_early = np.linspace(20, T, N_rabi_early)
    t_late  = np.linspace(max_per*T, (max_per+1.5)*T, N_rabi_late)
    tpulse  = np.clip(np.concatenate([t_early, t_late]), 16, None)

    job_params = []
    for d in det_scan:
        job_params.append({"runs": shots, "variables":
                           {"duration_0": tpi_int, "amp_0": float(omega), "detuning": float(d)}})
    for tp in tpulse:
        job_params.append({"runs": shots, "variables":
                           {"duration_0": int(round(tp)), "amp_0": float(omega), "detuning": 0.0}})

    return seq, job_params, det_scan, tpulse.astype(float)


def _bitstring_stats(job):
    """Mean occupation and binomial stderr from a QPU job result."""
    result = job.result                       # {bitstring: count}
    Na     = len(next(iter(result)))
    n_shots = sum(result.values())
    # Rydberg counts per atom
    occ = np.zeros(Na)
    for bs, cnt in result.items():
        for i, b in enumerate(bs):
            occ[i] += int(b) * cnt
    occ_mean = occ / n_shots                  # per-site ⟨n_i⟩
    mean_n   = occ_mean.mean()                # lattice-averaged ⟨n⟩

    # Global Laplace-smoothed mean
    tot = int(occ.sum())
    mean_smooth = (tot + 1) / (Na * n_shots + 2)  # ≈ mean_n for large n_shots
    err_smooth  = np.sqrt((tot+1)*(Na*n_shots-tot+1) /
                          ((Na*n_shots+2)**2*(Na*n_shots+3)))
    return mean_smooth, err_smooth, occ_mean


def analyze_calibration(
    rydberg_jobs, rabi_jobs,
    det_scan, tpulse_scan,
    omega: float, t_pi_ns: float, out_dir: Path
):
    """
    Two-round Rydberg spec + Rabi fit. Returns dict with offset corrections.
    Saves calibration plots to out_dir.
    """
    # Round-1 Rydberg spec
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

    p0 = [det_scan[np.argmin(means_det)], omega]
    bounds = ((det_scan[0], omega*0.95), (det_scan[-1], omega*1.05))
    popt, _ = curve_fit(rydberg_spec, det_scan, means_det, sigma=errs_det+1e-6,
                        p0=p0, bounds=bounds, maxfev=10000)
    delta_offset_1 = popt[0]

    # Round-1 Rabi
    means_rabi = np.array([_bitstring_stats(j)[0] for j in rabi_jobs])
    errs_rabi  = np.array([_bitstring_stats(j)[1] for j in rabi_jobs])

    def rabi(t, omega_, A_, offset_, sigma_, phi_):
        return offset_ + A_ * np.sin(omega_*t*1e-3+phi_) * np.exp(-2*(t*1e-3)**2*sigma_)

    p0_r = [omega, 1, 0.5, 0.1, np.pi/2]
    bounds_r = ((omega*0.5,0,0,0,0),(omega*3,1,1,np.inf,2*np.pi))
    popt_r, _ = curve_fit(rabi, tpulse_scan, means_rabi, sigma=errs_rabi+1e-6,
                          p0=p0_r, bounds=bounds_r, maxfev=10000)
    omega_ratio_1 = np.sqrt(max(popt_r[0]**2 - delta_offset_1**2, 0)) / omega

    # Round-2 Rydberg spec (with updated omega).
    # Guard: if omega_ratio_1 collapsed to 0 fall back to wide ±20% window.
    omega_eff_1 = max(omega * omega_ratio_1, omega * 0.3)
    p0_2 = [det_scan[np.argmin(means_det)], omega_eff_1]
    bounds_2 = ((det_scan[0], omega_eff_1 * 0.8),
                (det_scan[-1], omega_eff_1 * 1.2))
    popt_2, _ = curve_fit(rydberg_spec, det_scan, means_det, sigma=errs_det+1e-6,
                          p0=p0_2, bounds=bounds_2, maxfev=10000)
    delta_offset_2  = popt_2[0]

    # Round-2 Rabi
    popt_r2, _ = curve_fit(rabi, tpulse_scan, means_rabi, sigma=errs_rabi+1e-6,
                           p0=p0_r, bounds=bounds_r, maxfev=10000)
    omega_ratio_2 = np.sqrt(max(popt_r2[0]**2 - delta_offset_2**2, 0)) / omega

    # ── Calibration plots ─────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].errorbar(det_scan/(2*np.pi), means_det, errs_det, fmt="s", ms=4, label="data")
    axes[0].plot(det_scan/(2*np.pi), rydberg_spec(det_scan, *popt_2),
                 label=f"fit: δ₀={delta_offset_2/(2*np.pi):.3f} MHz, Ω={popt_2[1]/(2*np.pi):.3f} MHz")
    axes[0].set_xlabel("Detuning / 2π (MHz)"); axes[0].set_ylabel("⟨n⟩"); axes[0].legend(fontsize=8)
    axes[0].set_title("Rydberg spectroscopy")

    axes[1].errorbar(tpulse_scan, means_rabi, errs_rabi, fmt="s", ms=4, label="data")
    axes[1].plot(tpulse_scan, rabi(tpulse_scan, *popt_r2),
                 label=f"fit: Ω_eff={popt_r2[0]/(2*np.pi):.3f} MHz, ratio={omega_ratio_2:.4f}")
    axes[1].set_xlabel("Pulse duration (ns)"); axes[1].set_ylabel("⟨n⟩"); axes[1].legend(fontsize=8)
    axes[1].set_title("Rabi oscillations")

    plt.tight_layout()
    fig.savefig(out_dir / "calibration_fits.png", bbox_inches="tight")
    plt.close()
    print(f"  Calibration plots → {out_dir/'calibration_fits.png'}")

    return {
        "omega_ratio":    omega_ratio_2,
        "delta_offset":   delta_offset_2,
        "omega_ratio_r1": omega_ratio_1,
        "delta_offset_r1": delta_offset_1,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Submit EOM quench to FRESNEL_CAN1 QPU with calibration."
    )
    parser.add_argument("--N",              type=int,   default=5)
    parser.add_argument("--hx",             type=float, default=6.0)
    parser.add_argument("--omega",          type=float, default=2*2*np.pi,
                        help="Rabi setpoint in rad/µs (default 4π ≈ 12.566)")
    parser.add_argument("--t-max",          type=int,   default=4000,
                        help="Max pulse duration in ns (default 4000)")
    parser.add_argument("--shots",          type=int,   default=300)
    parser.add_argument("--n-times",        type=int,   default=75)
    parser.add_argument("--out-dir",        default="results/qpu/",
                        help="Output directory for manifest and plots")
    parser.add_argument("--device",         default="FRESNEL_CAN1")
    parser.add_argument("--R-offset",       type=float, default=1.0,
                        help="Multiplicative offset on lattice spacing (default 1.0)")
    parser.add_argument("--no-calibration", action="store_true",
                        help="Skip calibration (use nominal omega and detuning)")
    parser.add_argument("--wait",           action="store_true",
                        help="Wait for simulation batch to complete before returning")
    args = parser.parse_args()

    out_dir   = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    label     = f"QPU_N{args.N}_hx{args.hx}_t{args.t_max}_{timestamp}"

    # ── Connect ───────────────────────────────────────────────────────────────
    print("Connecting to Pasqal Cloud SDK...")
    creds  = _load_credentials()
    region = os.environ.get("PASQAL_REGION") or creds.get("region")
    sdk    = SDK(username=creds["username"], project_id=creds["project_id"],
                 password=creds["password"], region=region)
    specs  = sdk.get_device_specs_dict()
    device = deserialize_device(specs[args.device])
    C6     = device.interaction_coeff
    print(f"  Device: {args.device}  |  C6 = {C6:.0f} rad·µm⁶/µs\n")

    # ── Experiment geometry ───────────────────────────────────────────────────
    R = (args.hx * 2 * C6 / (4 * args.omega)) ** (1/6)
    R_phys = R * args.R_offset
    delta_nom = central_site_detuning(args.N, R, C6)
    # Clamp t_max to leave room for EOM enable/disable overhead (~300 ns).
    eom = device.channels["rydberg_global"].eom_config
    eom_overhead = 4 * (eom.rise_time + eom.custom_buffer_time)
    t_max_safe = device.max_sequence_duration - eom_overhead
    if args.t_max > t_max_safe:
        print(f"  Warning: --t-max {args.t_max} exceeds device limit "
              f"({device.max_sequence_duration} ns total - {eom_overhead} ns EOM overhead). "
              f"Capping at {t_max_safe} ns.")
        args.t_max = t_max_safe
    obs_times = (np.round(np.linspace(16, args.t_max, args.n_times) / 4) * 4).astype(int)
    obs_times = np.clip(obs_times, 16, args.t_max)

    print(f"Experiment parameters:")
    print(f"  N = {args.N}×{args.N} = {args.N**2} atoms")
    print(f"  hx/J = {args.hx:.2f}")
    print(f"  R_nominal = {R:.4f} µm   R_phys = {R_phys:.4f} µm")
    print(f"  ω setpoint = {args.omega/(2*np.pi):.4f} MHz")
    print(f"  δ nominal  = {delta_nom/(2*np.pi):.4f} MHz")
    print(f"  Obs times : {obs_times[0]}…{obs_times[-1]} ns ({len(obs_times)} points)")
    print(f"  Shots     : {args.shots} per time point\n")

    # ── Build parametric experiment sequence ──────────────────────────────────
    seq_experiment = make_experiment_parametric(args.N, R_phys, device)

    # ── Calibration ───────────────────────────────────────────────────────────
    omega_compensated = args.omega
    delta_compensated = delta_nom
    calib_results     = {}
    calib_batch_id    = None

    if not args.no_calibration:
        print("="*60)
        print("Phase 1 — Calibration batch")
        print("="*60)
        calib_dir = out_dir / "calibration"
        calib_dir.mkdir(exist_ok=True)

        t_pi_ns = np.pi / args.omega * 1e3
        seq_calib, job_params_calib, det_scan, tpulse_scan = make_calibration_parametric(
            args.omega, device
        )
        n_calib_jobs = len(job_params_calib)
        n_det, n_rabi = len(det_scan), len(tpulse_scan)
        print(f"  {n_calib_jobs} calibration jobs ({n_det} Rydberg + {n_rabi} Rabi)")

        batch_calib = sdk.create_batch(
            seq_calib.to_abstract_repr(), [], open=True, wait=True,
            device_type=args.device
        )
        calib_batch_id = batch_calib.id
        print(f"  Calibration batch: {calib_batch_id[:8]}...")

        # Submit calibration jobs without blocking, then immediately open the
        # experiment batch so both land in the queue back-to-back.
        batch_calib.add_jobs(job_params_calib, wait=False)
        batch_calib.close()
        print(f"  Calibration jobs submitted (not yet complete).\n")

        # ── Experiment batch opened immediately (empty, open) ─────────────────
        # Enters the QPU queue right behind calibration so there is no gap.
        # Jobs are added once calibration offsets are known (below).
        print("="*60)
        print("Phase 2 — Experiment batch (queued, awaiting calibration offsets)")
        print("="*60)
        batch_sim = sdk.create_batch(
            seq_experiment.to_abstract_repr(), [], open=True, wait=True,
            device_type=args.device
        )
        sdk.set_batch_tags(batch_sim.id, [label])
        print(f"  Experiment batch: {batch_sim.id[:8]}... (open, 0 jobs so far)\n")

        # ── Poll until calibration is complete ────────────────────────────────
        print("Waiting for calibration to complete (polling every 3600 s)...")
        poll_interval = 3600
        while True:
            batch_calib = sdk.get_batch(calib_batch_id)
            statuses = [j.status for j in batch_calib.ordered_jobs]
            n_done = sum(s == "DONE" for s in statuses)
            n_err  = sum(s == "ERROR" for s in statuses)
            print(f"  Calibration: {n_done}/{n_calib_jobs} DONE, {n_err} ERROR", flush=True)
            if n_done + n_err == n_calib_jobs:
                break
            time.sleep(poll_interval)
        print(f"  Calibration complete.\n")

        rydberg_jobs = batch_calib.ordered_jobs[:n_det]
        rabi_jobs    = batch_calib.ordered_jobs[n_det:]

        calib_results = analyze_calibration(
            rydberg_jobs, rabi_jobs,
            det_scan, tpulse_scan,
            args.omega, t_pi_ns, calib_dir
        )

        max_amp = device.channels["rydberg_global"].max_amp
        omega_compensated = min(args.omega / calib_results["omega_ratio"], max_amp)
        delta_compensated = delta_nom  + calib_results["delta_offset"]

        print(f"Calibration results:")
        print(f"  ω ratio      = {calib_results['omega_ratio']:.5f}")
        print(f"  δ offset     = {calib_results['delta_offset']/(2*np.pi):+.4f} MHz")
        print(f"  ω compensated = {omega_compensated/(2*np.pi):.4f} MHz")
        print(f"  δ compensated = {delta_compensated/(2*np.pi):.4f} MHz\n")
        with open(calib_dir / "calib_results.json", "w") as f:
            json.dump(calib_results, f, indent=2)

    # ── Fill in experiment jobs (compensated params) ──────────────────────────
    # If calibration was skipped, batch_sim was not yet created — create it now.
    if args.no_calibration:
        print("="*60)
        print("Phase 2 — Experiment batch")
        print("="*60)
        batch_sim = sdk.create_batch(
            seq_experiment.to_abstract_repr(), [], open=True, wait=True,
            device_type=args.device
        )
        sdk.set_batch_tags(batch_sim.id, [label])
        print(f"  Experiment batch: {batch_sim.id[:8]}...")

    job_params_sim = [
        {"runs": args.shots, "variables": {
            "echo_time":     int(t),
            "omega_quench":  float(omega_compensated),
            "detuning_quench": float(delta_compensated),
        }}
        for t in obs_times
    ]

    batch_sim.add_jobs(job_params_sim, wait=args.wait)
    batch_sim.close()
    print(f"  {len(obs_times)} jobs submitted. Batch closed.")
    if args.wait:
        print("  All jobs completed.")

    # ── Save manifest ─────────────────────────────────────────────────────────
    manifest = {
        "label":            label,
        "batch_id":         batch_sim.id,
        "calib_batch_id":   calib_batch_id,
        "device":           args.device,
        "N":                args.N,
        "hx":               args.hx,
        "omega":            args.omega,
        "omega_compensated": omega_compensated,
        "detuning_nom":     delta_nom,
        "detuning_compensated": delta_compensated,
        "spacing_um":       R_phys,
        "R_offset":         args.R_offset,
        "t_max_ns":         args.t_max,
        "shots":            args.shots,
        "obs_times_ns":     obs_times.tolist(),
        "calibration":      calib_results,
    }
    manifest_path = out_dir / f"{label}_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  Manifest  → {manifest_path}")
    print(f"  Batch ID  : {batch_sim.id}")
    if calib_batch_id:
        print(f"  Calib ID  : {calib_batch_id}")
    print(f"\nTo collect results:")
    print(f"  python collect_qpu.py --manifest {manifest_path}")
    print(f"{'='*60}")
    print(manifest_path)  # machine-readable last line


if __name__ == "__main__":
    main()
