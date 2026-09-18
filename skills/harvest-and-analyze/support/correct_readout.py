#!/usr/bin/env python3
"""Invert the detection channel on harvested bitstrings.

A neutral-atom readout mislabels sites in two ways: an atom in the ground state
is sometimes read as excited (p_false_pos, "epsilon"), and an atom in the Rydberg
state is sometimes read as absent (p_false_neg, "epsilon'"). Both are single-site
and independent, so the measured density of one site is

    n_raw = eps + n_true * (1 - eps - eps')

and one division recovers n_true. This script does that for every site at every
scan point, reading `qpu_counts.json` and writing `qpu_readout.json`.

It runs offline. The raw counts file is all it needs, so a corrected density can
be produced long after the batch expired, and without an account when the two
rates are passed explicitly.

**It does not touch the verdict, deliberately.** `harvest-and-analyze` accepts or
rejects by comparing the QPU curve to the *noisy* emulation, whose noise model
already contains p_false_pos and p_false_neg. Both sides of that comparison
include the detection error, which is what makes it a fair test. Correcting one
side only would bias it. Use this script to report a density, to compare against
a paper that quotes corrected values, or to see how much of your signal the
detector is eating — not to improve an accept.

Usage:
    python correct_readout.py \\
        --counts  results/my_experiment/qpu/qpu_counts.json \\
        --out     results/my_experiment/qpu/qpu_readout.json \\
        [--device FRESNEL_CAN1 | --eps 0.015 --eps-prime 0.09]

    python correct_readout.py --self-test    # analytic round trip, no data needed
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

from pasqal_auth import load_credentials


def _rates_from_device(device_name: str) -> tuple[float, float]:
    """Read the two detection rates off the live device noise model."""
    from pasqal_cloud import PasqalCloudConnection

    cloud = PasqalCloudConnection(**load_credentials())
    devices = {d.name: d for d in cloud.fetch_available_devices().values()}
    if device_name not in devices:
        raise SystemExit(
            f"✘ device {device_name!r} not available to this project. "
            f"Available: {', '.join(sorted(devices)) or '(none)'}")
    noise = getattr(devices[device_name], "noise_model", None)
    if noise is None:
        raise SystemExit(
            f"✘ {device_name} publishes no noise model, so its detection rates "
            "are not readable. Pass --eps and --eps-prime from the calibration "
            "you are working against.")
    return float(noise.p_false_pos), float(noise.p_false_neg)


def _register_size(counts: dict) -> int:
    """Bitstring length, taken from the shots rather than assumed.

    Reading N off the data is what lets this run on a downsized register, or on
    a batch whose spec has since been edited.
    """
    lengths = Counter(len(s) for s in counts)
    return lengths.most_common(1)[0][0] if lengths else 0


def _site_densities(counts: dict, n_atoms: int) -> tuple[np.ndarray, int]:
    """Per-site measured density, over the shots of the expected length."""
    total = 0
    occupied = np.zeros(n_atoms)
    for bits, weight in counts.items():
        if len(bits) != n_atoms or any(c not in "01" for c in bits):
            continue
        occupied += weight * np.frombuffer(bits.encode(), dtype=np.uint8).astype(float) - weight * 48.0
        total += weight
    return (occupied / total if total else occupied), total


def correct(counts: dict, eps: float, eps_prime: float) -> dict:
    """Per-site and array-mean density, measured and corrected."""
    denom = 1.0 - eps - eps_prime
    n_atoms = _register_size(counts)
    raw, shots = _site_densities(counts, n_atoms)
    if not shots:
        return {"n_atoms": n_atoms, "n_shots": 0}

    corrected_unclipped = (raw - eps) / denom
    corrected = np.clip(corrected_unclipped, 0.0, 1.0)
    # Binomial per site, divided by the same factor the mean was.
    err_raw  = np.sqrt(np.clip(raw * (1.0 - raw), 0.0, None) / shots)
    err_site = err_raw / denom

    # Clipping alone means little: a site whose true density sits at 0 or 1 lands
    # outside the interval half the time from sampling noise. What is diagnostic
    # is clipping the error cannot absorb — that density is not something these
    # two rates can produce, so the rates are wrong for this data (stale
    # calibration, wrong device) before the physics is.
    excess = np.maximum(-corrected_unclipped, corrected_unclipped - 1.0)
    beyond = (excess > 0) & ((err_site <= 0) | (excess > 2.0 * err_site))

    return {
        "n_atoms":            n_atoms,
        "n_shots":            shots,
        "density_raw":        float(raw.mean()),
        "density_corrected":  float(corrected.mean()),
        "density_err":        float(np.sqrt((err_raw**2).sum()) / (n_atoms * denom)),
        "site_density_raw":       [round(float(v), 6) for v in raw],
        "site_density_corrected": [round(float(v), 6) for v in corrected],
        "sites_clipped":             int(np.sum(excess > 0)),
        "sites_clipped_beyond_err":  int(np.sum(beyond)),
    }


def _self_test() -> int:
    """Forward channel, then inversion, on distributions with known densities."""
    rng = np.random.default_rng(7)
    eps, eps_prime = 0.015, 0.09
    failures = 0

    for n_atoms, p_true, shots in ((9, 0.0, 4000), (9, 1.0, 4000),
                                  (16, 0.35, 40000), (25, 0.6, 40000)):
        # Sample truth, then push it through the detection channel.
        truth = rng.random((shots, n_atoms)) < p_true
        flip  = np.where(truth, rng.random((shots, n_atoms)) < eps_prime,
                                rng.random((shots, n_atoms)) < eps)
        read  = np.where(flip, ~truth, truth)
        counts: dict[str, int] = {}
        for row in read:
            key = "".join("1" if b else "0" for b in row)
            counts[key] = counts.get(key, 0) + 1

        got = correct(counts, eps, eps_prime)
        raw_expected = eps + p_true * (1.0 - eps - eps_prime)
        # Consistent rates never clip beyond the error, including at the
        # boundaries where ordinary clipping is expected.
        ok = (abs(got["density_corrected"] - p_true) < 0.01
              and abs(got["density_raw"] - raw_expected) < 0.01
              and got["n_atoms"] == n_atoms
              and got["sites_clipped_beyond_err"] == 0)
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} N={n_atoms:>2} n_true={p_true:.2f}"
              f"  measured {got['density_raw']:.4f} (expect {raw_expected:.4f})"
              f"  corrected {got['density_corrected']:.4f}"
              f"  clipped {got['sites_clipped']}/{n_atoms}, "
              f"beyond error {got['sites_clipped_beyond_err']}")

    # Rates that cannot explain the data must announce themselves.
    saturated = correct({"1" * 9: 1000}, eps, eps_prime)
    ok = saturated["sites_clipped_beyond_err"] == 9
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} every shot fully excited: "
          f"{saturated['sites_clipped_beyond_err']}/9 sites clipped beyond error "
          "(expect 9 — a measured density of exactly 1.0 is above anything eps' "
          "allows, and has no sampling spread to hide in)")

    print("\n  readout inversion OK" if not failures
          else f"\n  {failures} case(s) failed")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Invert the detection channel on harvested bitstrings.")
    ap.add_argument("--counts", help="qpu_counts.json from harvest_qpu.py")
    ap.add_argument("--out",    help="output path (default: <counts dir>/qpu_readout.json)")
    ap.add_argument("--device", default=None,
                    help="read the two rates off this device's live noise model")
    ap.add_argument("--eps",       type=float, default=None,
                    help="p_false_pos: ground state read as excited")
    ap.add_argument("--eps-prime", type=float, default=None,
                    help="p_false_neg: Rydberg state read as absent")
    ap.add_argument("--self-test", action="store_true",
                    help="run the analytic round trip and exit")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()
    if not args.counts:
        ap.error("--counts is required (or use --self-test)")

    if args.eps is not None and args.eps_prime is not None:
        eps, eps_prime, source = args.eps, args.eps_prime, "given on the command line"
    elif args.device:
        eps, eps_prime = _rates_from_device(args.device)
        source = f"{args.device} live noise model"
    else:
        raise SystemExit(
            "✘ no detection rates. Pass --device to read them off the live "
            "noise model, or both --eps and --eps-prime to state them yourself. "
            "There is no default: a wrong rate silently rescales every density.")

    if eps + eps_prime >= 1.0:
        raise SystemExit(
            f"✘ eps + eps' = {eps + eps_prime:.3f} ≥ 1, so the channel carries no "
            "information and cannot be inverted. Check which rate is which.")

    counts_path = Path(args.counts)
    payload = json.loads(counts_path.read_text())
    out = Path(args.out) if args.out else counts_path.parent / "qpu_readout.json"

    print(f"=== correct-readout: {payload.get('experiment', counts_path.name)} ===")
    print(f"  eps={eps:.4f}  eps'={eps_prime:.4f}   ({source})")
    print(f"  {'value':>10}  {'measured':>10}  {'corrected':>10}  {'±err':>8}"
          f"  clipped (beyond err)")

    records = []
    for record in payload.get("records", []):
        result = correct(record.get("counts") or {}, eps, eps_prime)
        result["scan_value"] = record.get("scan_value")
        records.append(result)
        if not result.get("n_shots"):
            print(f"  {result['scan_value']:>10}   no shots")
            continue
        print(f"  {result['scan_value']:>10}  {result['density_raw']:>10.4f}  "
              f"{result['density_corrected']:>10.4f}  {result['density_err']:>8.4f}"
              f"  {result['sites_clipped']}/{result['n_atoms']}"
              f"  ({result['sites_clipped_beyond_err']})")

    out.write_text(json.dumps({
        "ts":            time.strftime("%Y-%m-%dT%H:%M:%S"),
        "experiment":    payload.get("experiment"),
        "device":        payload.get("device"),
        "scan_variable": payload.get("scan_variable"),
        "derived_from":  counts_path.name,
        "p_false_pos":   eps,
        "p_false_neg":   eps_prime,
        "rates_source":  source,
        "content": "per-site occupation density, measured and detection-corrected. "
                   "Not comparable to emu_noise.json, whose noise model already "
                   "includes these two rates.",
        "records":       records,
    }, indent=2))

    beyond = sum(r.get("sites_clipped_beyond_err", 0) for r in records)
    if beyond:
        print(f"\n  {beyond} site-points clipped beyond their own error bar. Those "
              "densities are outside anything these two rates can produce, so "
              "treat the rates as suspect — stale calibration, or the wrong "
              "device — before treating the physics as suspect.")
    print(f"\n  Corrected densities → {out}")
    print("  The accept/reject verdict is unchanged: it compares uncorrected "
          "shots to a noise model that already includes this detection error.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
