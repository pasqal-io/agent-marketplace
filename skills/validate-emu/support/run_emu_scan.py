#!/usr/bin/env python3
"""Cloud EMU_MPS scan — noiseless + noisy in parallel.

Submits one EMU_MPS batch per scan point for both noiseless and noisy backends,
polls all concurrently, computes the observable, and writes a go/no-go verdict.

Usage:
    python run_emu_scan.py \\
        --spec       experiment_spec.json \\
        --seq-file   my_experiment_sequence.py \\
        --out-dir    results/my_experiment/emu/ \\
        [--shots     1000] \\
        [--poll      30] \\
        [--noiseless-only | --noisy-only]

Outputs (in --out-dir):
    batch_ids.json       submitted batch IDs (written immediately, crash recovery)
    emu_noiseless.json   observable scan curve, noiseless
    emu_noise.json       observable scan curve, noisy (FC1 calibrated)
    verdict.json         {go: bool, reasons: [...], retention: float}
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


def _emu_noise_model(device):
    """Device noise model repackaged for cloud EMU_MPS.

    Built from scratch rather than dataclasses.replace(device noise model):
    the device model carries state_prep_error and register/trap-noise fields
    that crash cloud EMU_MPS execution ("'numpy.bool' object cannot be
    interpreted as an integer"). Only the supported fields are kept, all
    taken from the live device spec. Returns (noise_model, params_dict).
    """
    from pulser.noise_model import NoiseModel
    nm = getattr(device, "noise_model", None)
    dephasing_rate = getattr(nm, "dephasing_rate", 0.05)
    temperature    = getattr(nm, "temperature", 20.0)
    det_sigma      = getattr(nm, "detuning_sigma", 0.0)
    noise = NoiseModel(
        temperature=temperature,
        dephasing_rate=dephasing_rate,
        detuning_sigma=det_sigma,
        relaxation_rate=getattr(nm, "relaxation_rate", 0.01),
        amp_sigma=getattr(nm, "amp_sigma", 0.01),
        p_false_pos=getattr(nm, "p_false_pos", 0.015),
        p_false_neg=getattr(nm, "p_false_neg", 0.09),
        laser_waist=getattr(nm, "laser_waist", None),
    )
    params = {
        "T2_us":                round(1.0 / dephasing_rate, 3) if dephasing_rate else None,
        "temperature_uk":       temperature,
        "detuning_sigma_radus": det_sigma,
    }
    return noise, params


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec",            required=True)
    ap.add_argument("--seq-file",        required=True)
    ap.add_argument("--out-dir",         required=True)
    ap.add_argument("--shots",           type=int, default=None)
    ap.add_argument("--poll",            type=int, default=30,
                    help="poll interval in seconds")
    ap.add_argument("--noiseless-only",  action="store_true")
    ap.add_argument("--noisy-only",      action="store_true")
    ap.add_argument("--resume",          action="store_true",
                    help="Poll the batches already recorded in "
                         "<out-dir>/batch_ids.json instead of submitting new "
                         "ones. Use this after a dropped session — a plain "
                         "re-run would pay for the whole scan a second time.")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    out  = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    shots    = args.shots or spec["shots_per_point"]
    scan     = spec["scan"]
    variable = scan["variable"]
    values   = scan["values"]
    fixed    = scan.get("fixed_params", {})

    # Submission is not idempotent: every scan point creates a fresh pair of
    # cloud batches and this file is overwritten, so a plain re-run after a
    # dropped session pays for the scan twice and loses the first set of IDs.
    # Refuse instead, and offer the recorded batches. Checked here, before the
    # cloud imports and the credential load, so it costs nothing to hit.
    manifest_path = out / "batch_ids.json"
    recorded = None
    if manifest_path.exists():
        if not args.resume:
            raise SystemExit(
                f"✘ {manifest_path} already exists — this scan was already "
                "submitted.\n"
                "  Poll the batches it recorded:  --resume\n"
                "  Or submit a genuinely new scan into a different --out-dir.")
        recorded = json.loads(manifest_path.read_text())
        # A spec edited between submission and resume would poll batches that
        # ran something else, and the verdict would be attributed to the current
        # spec. Refuse rather than mislabel the result.
        if (recorded.get("scan_variable") != variable
                or recorded.get("scan_values") != values):
            raise SystemExit(
                "✘ the spec no longer matches what was submitted: "
                f"{recorded.get('scan_variable')} ∈ {recorded.get('scan_values')} "
                f"was recorded, the spec now says {variable} ∈ {values}.\n"
                "  Submit the new scan into a different --out-dir.")
        print(f"  resuming from {manifest_path} "
              f"(submitted {recorded.get('ts', 'unknown time')})")
    elif args.resume:
        raise SystemExit(f"✘ --resume needs {manifest_path}, which does not "
                         "exist. Drop the flag to submit the scan.")

    run_nl = not args.noisy_only
    run_n  = not args.noiseless_only

    mod              = _load_seq_module(args.seq_file)
    build_sequence   = getattr(mod, spec.get("builder_fn", "build_sequence"))
    compute_obs      = mod.compute_observable

    creds = load_credentials()
    from pasqal_cloud import PasqalCloudConnection
    from pasqal_cloud.device import DeviceTypeName
    from pasqal_cloud.job import CreateJob
    from pasqal_cloud.pasqal_cloud_client import PasqalCloudClient
    from pulser.backend import EmulationConfig
    from pulser.backend.default_observables import BitStrings

    conn   = PasqalCloudConnection(**creds)
    device = conn.fetch_available_devices()[spec["device"]]
    sdk    = PasqalCloudClient(**creds)

    noisy_cfg = None
    noise_params = None
    if run_n and recorded is None:
        noise, noise_params = _emu_noise_model(device)
        noisy_cfg = EmulationConfig(
            noise_model=noise,
            # One trajectory per batch: the scan's error bars come from the
            # `shots` samples, not from averaging trajectories. This used to be
            # NoiseModel(runs=1), deprecated since pulser 1.7. It is the
            # resolved default too, but a default that becomes 40 under
            # prefer_device_noise_model is not one to leave implicit on a
            # metered backend.
            n_trajectories=1,
            observables=[BitStrings(evaluation_times=[1.0], num_shots=shots)],
        ).to_abstract_repr()

    print(f"=== validate-emu: {spec['experiment_name']} ===")
    print(f"  {variable} ∈ {values}")
    print(f"  shots={shots}  device={spec['device']}")
    print(f"  run noiseless={run_nl}  noisy={run_n}\n")

    nl_batches: dict = {}
    n_batches:  dict = {}

    if recorded is not None:
        nl_batches = {v: recorded["noiseless"][str(v)] for v in values
                      if str(v) in (recorded.get("noiseless") or {})}
        n_batches  = {v: recorded["noisy"][str(v)] for v in values
                      if str(v) in (recorded.get("noisy") or {})}
        noise_params = recorded.get("noise_params")
        run_nl, run_n = bool(nl_batches), bool(n_batches)
        print(f"  {len(nl_batches)} noiseless + {len(n_batches)} noisy batches "
              "to poll — nothing resubmitted\n")

    for val in values if recorded is None else []:
        params = {**fixed, variable: val}
        seq    = build_sequence(device=device, **params)

        if run_nl:
            b = sdk.create_batch(
                serialized_sequence=seq.to_abstract_repr(),
                jobs=[CreateJob(runs=shots)],
                device_type=DeviceTypeName.EMU_MPS, wait=False,
            )
            nl_batches[val] = str(b.id)
            print(f"  [noiseless] {variable}={val}  →  {b.id}", flush=True)

        if run_n:
            b = sdk.create_batch(
                serialized_sequence=seq.to_abstract_repr(),
                jobs=[CreateJob(runs=shots)],
                device_type=DeviceTypeName.EMU_MPS, wait=False,
                backend_configuration=noisy_cfg,
            )
            n_batches[val] = str(b.id)
            print(f"  [noisy]     {variable}={val}  →  {b.id}", flush=True)

    if recorded is None:
        manifest_path.write_text(json.dumps({
            "ts":           time.strftime("%Y-%m-%dT%H:%M:%S"),
            "experiment":   spec["experiment_name"],
            "scan_variable": variable,
            "scan_values":  values,
            "shots":        shots,
            "noiseless":    {str(k): v for k, v in nl_batches.items()},
            "noisy":        {str(k): v for k, v in n_batches.items()},
            "noise_params": noise_params if run_n else None,
        }, indent=2))
        print(f"\n  batch_ids saved → {manifest_path}")

    # ── poll ─────────────────────────────────────────────────────────────────
    def poll_all(batch_map: dict, label: str) -> dict:
        pending = set(batch_map)
        done    = {}
        t0      = time.time()
        while pending:
            for val in sorted(pending):
                B  = sdk.get_batch(batch_map[val])
                st = B.ordered_jobs[0].status
                if st == "DONE":
                    done[val] = _counts_from_job(B.ordered_jobs[0])
                    pending.discard(val)
                    print(f"  [{label} DONE] {variable}={val}  "
                          f"{sum(done[val].values())} shots  "
                          f"({time.time()-t0:.0f}s)", flush=True)
                elif st in ("ERROR", "CANCELED", "TIMED_OUT"):
                    print(f"  [{label} {st}] {variable}={val}  skip")
                    pending.discard(val)
            if pending:
                time.sleep(args.poll)
        return done

    nl_counts = poll_all(nl_batches, "noiseless") if run_nl else {}
    n_counts  = poll_all(n_batches,  "noisy")     if run_n  else {}

    # ── compute observables ──────────────────────────────────────────────────
    def to_records(counts_map: dict, batch_map: dict) -> list:
        recs = []
        for val in sorted(counts_map, key=float):
            c   = counts_map[val]
            obs = compute_obs(c) if c else float("nan")
            recs.append({
                "scan_value":   val,
                "observable":   obs,
                "n_shots":      sum(c.values()),
                "n_unique":     len(c),
                "batch_id":     batch_map.get(val, ""),
            })
        return recs

    nl_records = to_records(nl_counts, nl_batches)
    n_records  = to_records(n_counts,  n_batches)

    if run_nl:
        (out / "emu_noiseless.json").write_text(json.dumps({
            "ts":           time.strftime("%Y-%m-%dT%H:%M:%S"),
            "experiment":   spec["experiment_name"],
            "backend":      "EMU_MPS_noiseless",
            "device":       spec["device"],
            "scan_variable": variable,
            "shots":        shots,
            "records":      nl_records,
        }, indent=2))

    if run_n:
        (out / "emu_noise.json").write_text(json.dumps({
            "ts":           time.strftime("%Y-%m-%dT%H:%M:%S"),
            "experiment":   spec["experiment_name"],
            "backend":      "EMU_MPS_noisy",
            "device":       spec["device"],
            "scan_variable": variable,
            "shots":        shots,
            "noise_params": noise_params,
            "records": n_records,
        }, indent=2))

    # ── verdict ──────────────────────────────────────────────────────────────
    verdict = {"go": True, "reasons": []}
    min_ret = spec.get("validation", {}).get("noise_retention_min", 0.50)

    if run_nl and nl_records:
        nl_obs = [r["observable"] for r in nl_records
                  if not np.isnan(r["observable"])]
        if not nl_obs or max(nl_obs) <= 0:
            verdict["go"] = False
            verdict["reasons"].append(
                "noiseless signal is zero or negative — check protocol or scan range")
        else:
            verdict["nl_max"] = float(max(nl_obs))

    if run_nl and run_n and nl_records and n_records:
        nl_obs = [r["observable"] for r in nl_records
                  if not np.isnan(r["observable"])]
        n_obs  = [r["observable"] for r in n_records
                  if not np.isnan(r["observable"])]
        if nl_obs and n_obs:
            nl_max    = max(nl_obs)
            n_max     = max(n_obs)
            retention = n_max / nl_max if nl_max > 0 else 0.0
            verdict["nl_max"]    = float(nl_max)
            verdict["n_max"]     = float(n_max)
            verdict["retention"] = float(retention)
            if retention < min_ret:
                verdict["go"] = False
                verdict["reasons"].append(
                    f"noise retention {retention:.0%} < threshold {min_ret:.0%} — "
                    "signal may not be observable on QPU")
            else:
                verdict["reasons"].append(
                    f"noise retention {retention:.0%} ≥ {min_ret:.0%} — signal "
                    "expected to survive QPU noise")

    (out / "verdict.json").write_text(json.dumps(verdict, indent=2))

    # ── summary ──────────────────────────────────────────────────────────────
    print(f"\n=== EMU scan summary ({variable}) ===")
    nl_map = {r["scan_value"]: r["observable"] for r in nl_records}
    n_map  = {r["scan_value"]: r["observable"] for r in n_records}
    header = f"  {'value':>10}  {'noiseless':>12}  {'noisy':>12}"
    print(header)
    for val in values:
        nl_v = nl_map.get(val, float("nan"))
        n_v  = n_map.get(val,  float("nan"))
        print(f"  {val:>10}  {nl_v:>12.4f}  {n_v:>12.4f}")

    go_str = "GO ✓" if verdict["go"] else "NO-GO ✗"
    print(f"\n  Verdict: {go_str}")
    for r in verdict["reasons"]:
        print(f"    {r}")
    print(f"\n  Results: {out}")


if __name__ == "__main__":
    main()
