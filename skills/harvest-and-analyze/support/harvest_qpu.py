#!/usr/bin/env python3
"""Collect QPU results and compare to EMU baseline.

Reads QPU batch IDs (written by qpu-submit or submit-via-hpc), pulls bitstrings
from Pasqal Cloud, computes the observable, and compares to the EMU scan from
validate-emu. Writes a final accept/reject verdict.

Supports two batch formats (written by the QPU submission scripts):
  per_point   : one batch per scan point (Guo/launch_fc1 pattern)
  parametric  : one batch with multiple parametric jobs (Z2 pattern)

Usage:
    python harvest_qpu.py \\
        --spec       experiment_spec.json \\
        --seq-file   my_experiment_sequence.py \\
        --batch-ids  results/my_experiment/qpu/batch_ids.json \\
        --emu-dir    results/my_experiment/emu/ \\
        --out-dir    results/my_experiment/qpu/ \\
        [--bootstrap 300]

Outputs (in --out-dir):
    qpu_counts.json     raw bitstring counts per scan point, exactly as the
                        device returned them — written before anything is
                        derived from them
    qpu_results.json    observable scan curve with bootstrap errors
    verdict.json        {accept, reasons, max_deviation_sigma, ...}
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np

from pasqal_auth import load_credentials


def _load_seq_module(path: str):
    spec = importlib.util.spec_from_file_location("seq_mod", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _counts_from_job(job) -> dict[str, int]:
    fr = getattr(job, "full_result", None)
    if isinstance(fr, dict):
        return dict(fr.get("counter") or {})
    return {}


def _bootstrap_std(counts: dict[str, int], obs_fn, n_boot: int = 300) -> float:
    """Bootstrap standard deviation of obs_fn over the shot distribution."""
    shots = []
    for s, c in counts.items():
        shots.extend([s] * c)
    if not shots:
        return float("nan")
    rng  = np.random.default_rng(42)
    boot = []
    for _ in range(n_boot):
        sample = rng.choice(shots, size=len(shots), replace=True)
        c_boot = {}
        for s in sample:
            c_boot[s] = c_boot.get(s, 0) + 1
        boot.append(obs_fn(c_boot))
    return float(np.std(boot))


def _collect_per_point(sdk, batch_ids_data: dict, obs_fn, n_boot: int) -> list:
    """Collect per_point format: one batch per scan point."""
    records = []
    for entry in batch_ids_data["batches"]:
        val = entry["scan_value"]
        bid = entry["batch_id"]
        B   = sdk.get_batch(bid)
        job = B.ordered_jobs[0]
        if job.status != "DONE":
            print(f"  WARNING: {entry['scan_value']} batch {bid[:8]} status={job.status}")
        counts = _counts_from_job(job)
        obs    = obs_fn(counts) if counts else float("nan")
        err    = _bootstrap_std(counts, obs_fn, n_boot) if counts else float("nan")
        records.append({
            "scan_value":  val,
            "observable":  obs,
            "obs_err":     err,
            "n_shots":     sum(counts.values()),
            "n_unique":    len(counts),
            "batch_id":    bid,
            "status":      job.status,
            "counts":      counts,
        })
        print(f"  collected {entry['scan_value']:>8}  obs={obs:.4f} ± {err:.4f}"
              f"  ({sum(counts.values())} shots)", flush=True)
    return records


def _collect_parametric(sdk, batch_ids_data: dict, obs_fn, scan_var: str,
                         n_boot: int) -> list:
    """Collect parametric format: one batch, multiple jobs keyed by variable."""
    bid = batch_ids_data["batch_id"]
    B   = sdk.get_batch(bid)
    records = []
    for job in B.ordered_jobs:
        val = (job.variables or {}).get(scan_var)
        if val is None:
            continue
        counts = _counts_from_job(job)
        obs    = obs_fn(counts) if counts else float("nan")
        err    = _bootstrap_std(counts, obs_fn, n_boot) if counts else float("nan")
        records.append({
            "scan_value":  val,
            "observable":  obs,
            "obs_err":     err,
            "n_shots":     sum(counts.values()),
            "n_unique":    len(counts),
            "batch_id":    bid,
            "status":      job.status,
            "counts":      counts,
        })
        print(f"  collected {val:>8}  obs={obs:.4f} ± {err:.4f}"
              f"  ({sum(counts.values())} shots)", flush=True)
    records.sort(key=lambda r: float(r["scan_value"]))
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec",       required=True)
    ap.add_argument("--seq-file",   required=True)
    ap.add_argument("--batch-ids",  required=True)
    ap.add_argument("--emu-dir",    required=True)
    ap.add_argument("--out-dir",    required=True)
    ap.add_argument("--bootstrap",  type=int, default=300)
    args = ap.parse_args()

    spec        = json.loads(Path(args.spec).read_text())
    batch_data  = json.loads(Path(args.batch_ids).read_text())
    emu_dir     = Path(args.emu_dir)
    out         = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    scan_var = spec["scan"]["variable"]

    mod      = _load_seq_module(args.seq_file)
    obs_fn   = mod.compute_observable

    from pasqal_cloud.pasqal_cloud_client import PasqalCloudClient
    sdk = PasqalCloudClient(**load_credentials())

    print(f"=== harvest-and-analyze: {spec['experiment_name']} ===")
    fmt = batch_data.get("format", "per_point")

    if fmt == "per_point":
        qpu_records = _collect_per_point(sdk, batch_data, obs_fn, args.bootstrap)
    else:
        qpu_records = _collect_parametric(sdk, batch_data, obs_fn, scan_var,
                                          args.bootstrap)

    # Raw bitstrings first, and in their own file. The observable is a *choice*:
    # re-analysing this run with a different one, or with a corrected
    # compute_observable, must not require the cloud a second time — a batch is
    # not guaranteed to still be readable, and those shots were paid for once.
    # Everything below this line is a transformation of this file.
    raw_keys = ("scan_value", "batch_id", "status", "counts")
    (out / "qpu_counts.json").write_text(json.dumps({
        "ts":           time.strftime("%Y-%m-%dT%H:%M:%S"),
        "experiment":   spec["experiment_name"],
        "device":       spec["device"],
        "scan_variable": scan_var,
        "content":      "raw bitstring counts as returned by the device, untransformed",
        "records":      [{k: r[k] for k in raw_keys} for r in qpu_records],
    }, indent=2))
    print(f"  raw bitstrings → {out / 'qpu_counts.json'}")

    for record in qpu_records:
        del record["counts"]

    (out / "qpu_results.json").write_text(json.dumps({
        "ts":           time.strftime("%Y-%m-%dT%H:%M:%S"),
        "experiment":   spec["experiment_name"],
        "device":       spec["device"],
        "scan_variable": scan_var,
        "n_bootstrap":  args.bootstrap,
        "derived_from": "qpu_counts.json",
        "observable_fn": f"{Path(args.seq_file).name}:compute_observable",
        "records":      qpu_records,
    }, indent=2))

    # ── load EMU baseline ────────────────────────────────────────────────────
    nl_file = emu_dir / "emu_noiseless.json"
    n_file  = emu_dir / "emu_noise.json"
    nl_recs = json.loads(nl_file.read_text())["records"] if nl_file.exists() else []
    n_recs  = json.loads(n_file.read_text())["records"]  if n_file.exists()  else []

    nl_map = {str(r["scan_value"]): r["observable"] for r in nl_recs}
    n_map  = {str(r["scan_value"]): r["observable"] for r in n_recs}

    # ── verdict ──────────────────────────────────────────────────────────────
    # QPU is "accepted" if it lies within noise model prediction
    # (within N sigma of the noisy EMU value at each scan point).
    SIGMA_TOL = 2.0   # accept if |QPU - noisy_emu| < SIGMA_TOL * qpu_err

    deviations = []
    for r in qpu_records:
        key   = str(r["scan_value"])
        n_val = n_map.get(key)
        err   = r["obs_err"]
        if n_val is not None and not np.isnan(r["observable"]) and err > 0:
            dev = abs(r["observable"] - n_val) / err
            deviations.append(dev)

    max_dev = float(max(deviations)) if deviations else float("nan")
    accept  = (max_dev < SIGMA_TOL) if not np.isnan(max_dev) else False

    verdict = {
        "accept":             accept,
        "max_deviation_sigma": max_dev,
        "sigma_tolerance":    SIGMA_TOL,
        "reasons":            [],
    }

    if np.isnan(max_dev):
        verdict["reasons"].append(
            "could not compute deviation — missing EMU noise baseline or QPU errors")
    elif accept:
        verdict["reasons"].append(
            f"QPU max deviation {max_dev:.1f}σ < {SIGMA_TOL}σ — "
            "consistent with noise model")
    else:
        verdict["reasons"].append(
            f"QPU max deviation {max_dev:.1f}σ ≥ {SIGMA_TOL}σ — "
            "QPU data not fully explained by noise model")

    (out / "verdict.json").write_text(json.dumps(verdict, indent=2))

    # ── summary ──────────────────────────────────────────────────────────────
    print(f"\n=== QPU harvest summary ({scan_var}) ===")
    print(f"  {'value':>10}  {'QPU':>10}  {'±err':>8}  {'noisy EMU':>12}")
    for r in qpu_records:
        key = str(r["scan_value"])
        n_v = n_map.get(key, float("nan"))
        print(f"  {r['scan_value']:>10}  {r['observable']:>10.4f}  "
              f"{r['obs_err']:>8.4f}  {n_v:>12.4f}")

    label = "ACCEPT ✓" if verdict["accept"] else "REJECT ✗"
    print(f"\n  Verdict: {label}  (max deviation {max_dev:.1f}σ)")
    for r in verdict["reasons"]:
        print(f"    {r}")
    print(f"\n  Results: {out}")


if __name__ == "__main__":
    main()