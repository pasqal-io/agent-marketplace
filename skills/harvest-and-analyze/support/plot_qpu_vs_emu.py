#!/usr/bin/env python3
"""QPU vs EMU comparison figure.

Usage:
    python plot_qpu_vs_emu.py \\
        --qpu        results/my_exp/qpu/qpu_results.json \\
        --noiseless  results/my_exp/emu/emu_noiseless.json \\
        --noisy      results/my_exp/emu/emu_noise.json \\
        --out        results/my_exp/comparison.png \\
        [--title "Guo sqrt3 — QPU vs EMU"] \\
        [--verdict results/my_exp/qpu/verdict.json]
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load_records(path: str) -> tuple[list, str]:
    d = json.loads(Path(path).read_text())
    return d["records"], d.get("scan_variable", "param")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qpu",        required=True)
    ap.add_argument("--noiseless",  required=True)
    ap.add_argument("--noisy",      required=True)
    ap.add_argument("--out",        required=True)
    ap.add_argument("--title",      default="")
    ap.add_argument("--verdict",    default=None)
    args = ap.parse_args()

    qpu_recs, variable = load_records(args.qpu)
    nl_recs,  _        = load_records(args.noiseless)
    n_recs,   _        = load_records(args.noisy)

    fig, ax = plt.subplots(figsize=(7, 4.5))

    # EMU curves
    nl_x = [r["scan_value"] for r in nl_recs]
    nl_y = [r["observable"] for r in nl_recs]
    n_x  = [r["scan_value"] for r in n_recs]
    n_y  = [r["observable"] for r in n_recs]
    ax.plot(nl_x, nl_y, "b--",  lw=1.5, label="Noiseless EMU", zorder=2)
    ax.plot(n_x,  n_y,  "r-",   lw=1.5, label="Noisy EMU (FC1 cal.)", zorder=2)

    # QPU points with error bars
    qpu_x   = [r["scan_value"] for r in qpu_recs]
    qpu_y   = [r["observable"] for r in qpu_recs]
    qpu_err = [r.get("obs_err", 0) for r in qpu_recs]
    ax.errorbar(qpu_x, qpu_y, yerr=qpu_err,
                fmt="ko", ms=5, lw=1.2, capsize=3, label="QPU", zorder=3)

    # Verdict annotation
    if args.verdict and Path(args.verdict).exists():
        v   = json.loads(Path(args.verdict).read_text())
        dev = v.get("max_deviation_sigma")
        if dev is not None:
            label_str = "ACCEPT" if v.get("accept") else "REJECT"
            colour    = "green"  if v.get("accept") else "red"
            ax.annotate(f"{label_str}  ({dev:.1f}σ)",
                        xy=(0.97, 0.05), xycoords="axes fraction",
                        ha="right", fontsize=9, color=colour)

    title = args.title or ""
    if args.verdict and Path(args.verdict).exists():
        v      = json.loads(Path(args.verdict).read_text())
        suffix = "  [ACCEPT]" if v.get("accept") else "  [REJECT]"
        title  = title + suffix if title else suffix.strip()

    if title:
        ax.set_title(title, fontsize=11)

    ax.set_xlabel(variable, fontsize=10)
    ax.set_ylabel("Observable", fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
