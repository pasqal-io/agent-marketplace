#!/usr/bin/env python3
"""Plot the cloud noise-emulation envelope.

Usage:
    python plot_noise_emu_cloud.py \\
        --results noise_emu_cloud.json \\
        --out     noise_emu_cloud.png \\
        [--title  "N=5 hx=6.0 quench"] \\
        [--qpu    qpu_results.json]      # optional QPU overlay (harvest-and-analyze format)
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out",     required=True)
    ap.add_argument("--title",   default="")
    ap.add_argument("--qpu",     default=None,
                    help="optional qpu_results.json to overlay")
    args = ap.parse_args()

    d    = json.loads(Path(args.results).read_text())
    recs = [r for r in d["records"] if not np.isnan(r["noisy_obs"])]
    ts   = [r["t"] for r in recs]

    fig, ax = plt.subplots(figsize=(6, 4))

    ax.plot(ts, [r["noiseless_obs"] for r in recs], "--o", color="tab:blue",
            label="Noiseless EMU_MPS (cloud)", lw=1.5, ms=6)
    ax.plot(ts, [r["noisy_obs"] for r in recs], "-s", color="tab:red",
            label="Noisy EMU_MPS (device model)", lw=1.5, ms=6)

    # Quantile envelope, if the run used --n-envelope
    if all("q10" in r for r in recs) and recs:
        ax.fill_between(ts, [r["q10"] for r in recs], [r["q90"] for r in recs],
                        color="tab:red", alpha=0.15, lw=0,
                        label="10–90% envelope")
        ax.fill_between(ts, [r["q25"] for r in recs], [r["q75"] for r in recs],
                        color="tab:red", alpha=0.25, lw=0)

    if args.qpu and Path(args.qpu).exists():
        q = json.loads(Path(args.qpu).read_text())
        qx = [r["scan_value"] for r in q["records"]]
        qy = [r["observable"] for r in q["records"]]
        qe = [r.get("obs_err", 0.0) for r in q["records"]]
        ax.errorbar(qx, qy, yerr=qe, fmt="D", color="black", ms=5,
                    capsize=3, label="QPU", zorder=5)

    nm = d.get("noise_params", d.get("noise_overrides", {}))
    det = nm.get("detuning_sigma_radus")
    det_str = f"{det:.3f}" if isinstance(det, (int, float)) else "?"
    sub = (f"T2={nm.get('T2_us','?')}µs  T={nm.get('temperature_uk','?')}µK  "
           f"σδ={det_str} rad/µs  shots={d.get('shots','?')}")
    ax.set_xlabel(f"{d.get('t_var', 't')} (ns)")
    ax.set_ylabel("observable")
    ax.set_title(f"{args.title}\n{sub}" if args.title else sub, fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    print(f"figure saved → {args.out}")


if __name__ == "__main__":
    main()
