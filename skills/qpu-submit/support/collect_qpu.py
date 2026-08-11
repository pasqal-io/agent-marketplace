#!/usr/bin/env python3
"""
collect_qpu.py — Collect QPU batch results into a .npz ready for comparison plots.

Convention matches analysis_utils.compute_magnetization:
  ⟨σᶻ⟩ = 2⟨n_Rydberg⟩ − 1  ∈ [−1, +1]
  Ground state → σᶻ = −1;  Full Rydberg → σᶻ = +1.
SPAM correction applied using FCAN1 default ε/ε' (or CLI override).

Usage
-----
# Non-blocking poll:
python collect_qpu.py --manifest results/qpu/QPU_N5_hx6.0_..._manifest.json

# Wait until all jobs are done (polls every 60 s):
python collect_qpu.py --manifest results/qpu/..._manifest.json --wait

Output .npz layout
------------------
    times_ns     (n_times,)            observation times in ns
    sz_mean      (n_times,)            lattice-averaged ⟨σᶻ⟩ SPAM-corrected
    sz_err       (n_times,)            binomial stderr on ⟨σᶻ⟩
    sz_per_site  (n_times, n_sites)    per-site ⟨σᶻ⟩ SPAM-corrected
    shots        scalar
    N            scalar                atoms per side
    hx           scalar
    eps          scalar                SPAM false-positive ε used
    eprime       scalar                SPAM false-negative ε' used
    manifest_json (1,)
"""

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np


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
        "PASQAL_PASSWORD and PASQAL_PROJECT_ID, or create ~/.pasqal_credentials.json.")


# ── Per-job observable extraction ─────────────────────────────────────────────

def _extract_sz(job, eps: float, eprime: float):
    """
    Return (sz_per_site, sz_mean, sz_err) from a QPU job result dict.

    The job result is {bitstring: count} where '1' = Rydberg, '0' = ground.
    Handles both plain dicts and full_result dicts (with 'counter' key).
    Masks out 'X' detection failures (≤1.5% global rate).

    ⟨σᶻ_i⟩ = 2⟨n_i⟩ − 1, then SPAM-corrected.
    """
    raw = job.result                     # {bitstring: count}
    if not raw:
        Na = 0
        return np.array([]), np.nan, np.nan

    # Support plain dict OR full_result format
    if "counter" in raw:
        items = list(raw["counter"].items()) + list(raw.get("partial_register_counter", {}).items())
    else:
        items = list(raw.items())

    if not items:
        return np.array([]), np.nan, np.nan

    keys, counts = zip(*items)
    counts = np.array(counts, dtype=float)

    # Mask shots with >1.5% 'X' (detection failures)
    Na = len(keys[0])
    mask = np.array([k.count("X") / Na <= 0.015 for k in keys])
    keys   = np.array(keys)[mask]
    counts = counts[mask]
    if len(keys) == 0:
        return np.full(Na, np.nan), np.nan, np.nan

    total = counts.sum()

    # Per-site σᶻ = 2n − 1 (skip 'X' per site)
    sz_per_site = np.full(Na, np.nan)
    for site in range(Na):
        site_mask = np.array([k[site] in "01" for k in keys])
        if not site_mask.any():
            continue
        site_bits   = np.array([int(k[site]) for k in keys[site_mask]])
        site_counts = counts[site_mask]
        n_i = (site_bits * site_counts).sum() / site_counts.sum()
        sz_raw = 2*n_i - 1
        # SPAM correction: ns_corr = (ns − ε)/(1 − ε − ε')  where ns = (sz+1)/2
        ns_raw  = 0.5*(sz_raw + 1)
        denom   = 1 - eps - eprime
        ns_corr = np.clip((ns_raw - eps) / denom, 0, 1) if denom > 0 else ns_raw
        sz_per_site[site] = 2*ns_corr - 1

    sz_mean = np.nanmean(sz_per_site)

    # Binomial stderr on ⟨σᶻ⟩ (before SPAM correction, propagated)
    n_shots_eff = total / Na                   # effective shots per site
    sz_err = np.sqrt(max(0, 1 - sz_mean**2)) / np.sqrt(n_shots_eff * Na)

    return sz_per_site, sz_mean, sz_err


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Collect QPU batch results → ⟨σᶻ⟩ .npz with SPAM correction."
    )
    parser.add_argument("--manifest", required=True,
                        help="Path to manifest JSON from submit_qpu.py.")
    parser.add_argument("--wait",  action="store_true",
                        help="Poll until all jobs are completed (60 s intervals).")
    parser.add_argument("--out",   default=None,
                        help="Output .npz path (default: manifest path with .npz).")
    # SPAM override — if omitted, fetched live from FCAN1 default_noise_model
    parser.add_argument("--eps",    type=float, default=None,
                        help="Override SPAM false-positive ε (default: read from FCAN1 spec).")
    parser.add_argument("--eprime", type=float, default=None,
                        help="Override SPAM false-negative ε' (default: read from FCAN1 spec).")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    with open(manifest_path) as f:
        manifest = json.load(f)

    out_path   = Path(args.out) if args.out else manifest_path.with_suffix(".npz")
    batch_id   = manifest["batch_id"]
    obs_times  = np.array(manifest["obs_times_ns"])
    N          = manifest["N"]
    n_sites    = N * N
    device_name = manifest.get("device", "FRESNEL_CAN1")

    print(f"Connecting to Pasqal Cloud SDK...")
    from pasqal_cloud import SDK
    from pulser.json.abstract_repr.deserializer import deserialize_device
    creds = _load_credentials()
    region = os.environ.get("PASQAL_REGION") or creds.get("region")
    sdk   = SDK(username=creds["username"], project_id=creds["project_id"],
                password=creds["password"], region=region)

    # ── Fetch SPAM parameters from device spec (unless overridden) ────────────
    if args.eps is None or args.eprime is None:
        specs  = sdk.get_device_specs_dict()
        device = deserialize_device(specs[device_name])
        nm     = device.default_noise_model
        eps    = args.eps    if args.eps    is not None else nm.p_false_pos
        eprime = args.eprime if args.eprime is not None else nm.p_false_neg
        print(f"SPAM from {device_name} spec: ε={eps} (p_false_pos), ε'={eprime} (p_false_neg)")
    else:
        eps, eprime = args.eps, args.eprime
        print(f"SPAM override: ε={eps}, ε'={eprime}")

    while True:
        batch  = sdk.get_batch(batch_id)
        jobs   = batch.ordered_jobs
        n_done    = sum(1 for j in jobs if j.status == "DONE")
        n_failed  = sum(1 for j in jobs if j.status in ("ERROR", "CANCELED"))
        n_pending = len(jobs) - n_done - n_failed

        print(f"Batch {batch_id[:8]}  status={batch.status}  "
              f"done={n_done}/{len(jobs)}  pending={n_pending}  failed={n_failed}")

        if n_failed:
            print(f"  WARNING: {n_failed} job(s) failed.")
        if not args.wait or n_pending == 0:
            break
        print(f"  Waiting 60 s for {n_pending} pending jobs...")
        time.sleep(60)

    # ── Extract ⟨σᶻ⟩ per time point ─────────────────────────────────────────
    sz_per_site_arr = np.full((len(obs_times), n_sites), np.nan)
    sz_mean_arr     = np.full(len(obs_times), np.nan)
    sz_err_arr      = np.full(len(obs_times), np.nan)
    n_extracted     = 0

    for t_idx, job in enumerate(jobs):
        if t_idx >= len(obs_times):
            break
        if job.status != "DONE" or job.result is None:
            print(f"  [t={obs_times[t_idx]} ns] MISSING (status={job.status})")
            continue
        try:
            sz_site, sz_mean, sz_err = _extract_sz(job, eps, eprime)
            if len(sz_site) == n_sites:
                sz_per_site_arr[t_idx] = sz_site
            sz_mean_arr[t_idx] = sz_mean
            sz_err_arr[t_idx]  = sz_err
            n_extracted += 1
        except Exception as e:
            print(f"  [t={obs_times[t_idx]} ns] Error: {e}")

    print(f"\nExtracted {n_extracted}/{len(obs_times)} time points.")

    np.savez(
        out_path,
        times_ns     = obs_times,
        sz_mean      = sz_mean_arr,
        sz_err       = sz_err_arr,
        sz_per_site  = sz_per_site_arr,
        shots        = np.array([manifest["shots"]]),
        N            = np.array([N]),
        hx           = np.array([manifest["hx"]]),
        eps          = np.array([eps]),
        eprime       = np.array([eprime]),
        manifest_json = np.array([json.dumps(manifest)]),
    )
    print(f"Saved → {out_path}")
    print(out_path)


if __name__ == "__main__":
    main()
