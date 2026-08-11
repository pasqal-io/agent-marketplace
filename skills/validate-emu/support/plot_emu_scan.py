#!/usr/bin/env python3
"""Plot the noiseless + noisy EMU scan curves.

Usage:
    python plot_emu_scan.py \\
        --noiseless emu_noiseless.json \\
        --noisy     emu_noise.json \\
        --out       emu_scan.png \\
        [--title    "Guo sqrt3 onset"]
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load_scan(path: str) -> tuple[list, list, list, str]:
    d = json.loads(Path(path).read_text())
    recs = d["records"]
    xs   = [r["scan_value"]  for r in recs]
    ys   = [r["observable"]  for r in recs]
    es   = [r.get("stderr", 0.0) for r in recs]
    return xs, ys, es, d.get("scan_variable", "param")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--noiseless", required=True)
    ap.add_argument("--noisy",     required=True)
    ap.add_argument("--out",       required=True)
    ap.add_argument("--title",     default="")
    ap.add_argument("--verdict",   default=None,
                    help="path to verdict.json for annotation")
    args = ap.parse_args()

    nl_x, nl_y, nl_e, variable = load_scan(args.noiseless)
    n_x,  n_y,  n_e,  _        = load_scan(args.noisy)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.errorbar(nl_x, nl_y, yerr=nl_e, fmt="-o", color="tab:blue",
                label="Noiseless EMU", lw=1.5, ms=9, capsize=4, capthick=1.5)
    ax.errorbar(n_x, n_y, yerr=n_e, fmt="--s", color="tab:red",
                label="Noisy EMU (FC1 cal.)", lw=1.5, ms=9, capsize=4, capthick=1.5)

    # Annotate retention if verdict available
    if args.verdict and Path(args.verdict).exists():
        v = json.loads(Path(args.verdict).read_text())
        ret = v.get("retention")
        if ret is not None:
            ax.annotate(f"retention = {ret:.0%}", xy=(0.97, 0.05),
                        xycoords="axes fraction", ha="right", fontsize=9,
                        color="green" if v.get("go") else "red")
            go_str = "GO" if v.get("go") else "NO-GO"
            ax.set_title(f"{args.title}  [{go_str}]" if args.title else go_str,
                         fontsize=11)
    elif args.title:
        ax.set_title(args.title, fontsize=11)

    ax.set_xlabel(variable, fontsize=10)
    ax.set_ylabel("Observable", fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
