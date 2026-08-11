#!/usr/bin/env python3
"""
plot_qpu_vs_emu.py — QPU data + noisy EMU envelope, styled like plot_N5_three_regimes.py.

Observable: ⟨σᶻ⟩ = 2⟨n_Rydberg⟩ − 1  (−1 = ground, +1 = full Rydberg).
X-axis: time in µs.

Style (matches plot_N5_three_regimes.py):
  · tab:orange fill     — noisy EMU 70% quantile band
  · tab:orange solid    — noisy EMU mean
  · tab:blue dashed     — noiseless EMU
  · black dots          — QPU data with error bars ("FC1")
  · grey fill           — calibration offset sensitivity band (optional)
  · top-right text box  — calibration results from manifest

Usage
-----
python plot_qpu_vs_emu.py \\
    --qpu  results/qpu/QPU_N5_hx6.0_..._manifest.npz \\
    --emu  results/emu/FCAN1_N5_hx6.0_t4000_ntraj40_...npz \\
    --out  results/comparison_hx6_N5.png \\
    [--coverage 0.7] [--t-max-ns 4000]
"""

import argparse
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Style constants (from plot_N5_three_regimes.py) ───────────────────────────
C_EMU_BAND  = "tab:orange"  # noisy band fill
C_EMU_MEAN  = "tab:orange"  # noisy mean line
C_NL        = "tab:blue"    # noiseless reference
C_QPU       = "black"       # QPU data
C_CAL_BAND  = "tab:grey"    # calibration offset band


# ── Observable helpers ─────────────────────────────────────────────────────────

def _sz_from_n(n_traj: np.ndarray) -> np.ndarray:
    """(n_runs, n_times, n_sites) → (n_runs, n_times): site-averaged ⟨σᶻ⟩ = 2⟨n⟩−1."""
    return (2.0 * n_traj - 1.0).mean(axis=-1)


def _envelope(arr: np.ndarray, coverage: float = 0.7):
    """(n_runs, n_times) → (mean, lo, hi) each (n_times,)."""
    alpha = (1 - coverage) / 2
    return arr.mean(0), np.quantile(arr, alpha, 0), np.quantile(arr, 1 - alpha, 0)


def _calib_text(manifest: dict) -> str | None:
    """Format a calibration annotation from the manifest dict."""
    calib = manifest.get("calibration", {})
    if not calib:
        return None
    omega_nom  = manifest.get("omega", 2*2*3.14159)
    ratio      = calib.get("omega_ratio", 1.0)
    delta_off  = calib.get("delta_offset", 0.0)
    omega_est  = ratio * omega_nom
    omega_MHz  = omega_est / (2 * np.pi)
    delta_kHz  = delta_off * 1e3 / (2 * np.pi)
    return (
        f"Calibration\n"
        f"$\\Omega_{{\\rm est}}$ = {omega_MHz:.3f} MHz\n"
        f"$\\delta_{{\\rm off}}$ = {delta_kHz:+.1f} kHz"
    )


# ── Main plot ──────────────────────────────────────────────────────────────────

def plot(qpu_path: Path, emu_path: Path, out_path: Path,
         coverage: float = 0.7, t_max_ns: float | None = None):

    # ── Load QPU data ─────────────────────────────────────────────────────────
    qpu         = np.load(qpu_path, allow_pickle=False)
    qpu_times   = qpu["times_ns"]                          # (n_t,) ns
    qpu_sz      = qpu["sz_mean"]                           # (n_t,) ⟨σᶻ⟩ SPAM-corrected
    qpu_err     = qpu["sz_err"]                            # (n_t,)
    qpu_N       = int(qpu["N"][0])
    qpu_hx      = float(qpu["hx"][0])
    qpu_shots   = int(qpu["shots"][0])
    qpu_eps     = float(qpu["eps"][0])
    qpu_eprime  = float(qpu["eprime"][0])
    manifest    = json.loads(str(qpu["manifest_json"][0]))

    # ── Load EMU data ─────────────────────────────────────────────────────────
    emu          = np.load(emu_path, allow_pickle=False)
    emu_n_all    = emu["n_traj"]           # (n_traj+1, n_times, n_sites) index 0 = noiseless
    emu_times    = emu["times"]            # normalised ∈ (0, 1]
    emu_dur      = float(emu["total_duration"][0])
    emu_times_us = emu_times * emu_dur / 1e3           # → µs
    n_traj       = emu_n_all.shape[0] - 1              # number of noisy runs
    seq_kw       = json.loads(str(emu["seq_kwargs_json"][0])) if "seq_kwargs_json" in emu else {}
    has_cal         = "cal_n" in emu
    has_qpu_matched = "n_traj_qpu" in emu

    # ── ⟨σᶻ⟩ observables ─────────────────────────────────────────────────────
    sz_nl = _sz_from_n(emu_n_all[0:1])[0]              # noiseless nominal (n_times,)

    if has_qpu_matched:
        # QPU-matched trajectories: sequence at calibrated params + FCAN1 noise
        sz_qpu_all  = _sz_from_n(emu["n_traj_qpu"])    # (n_traj, n_times)
        sz_qpu_single = sz_qpu_all[0]                   # single trajectory — noisy nominal ref
        sz_qpu_mean, sz_qpu_lo, sz_qpu_hi = _envelope(sz_qpu_all, coverage)
        qpu_off = json.loads(str(emu["qpu_offset_json"][0]))
        n_traj_qpu_matched = sz_qpu_all.shape[0]
    else:
        # Fallback: use nominal noisy trajectories (n_traj[1:])
        sz_nom = _sz_from_n(emu_n_all[1:])
        sz_qpu_single = sz_nom[0] if len(sz_nom) > 0 else None
        sz_qpu_mean, sz_qpu_lo, sz_qpu_hi = _envelope(sz_nom, coverage)
        qpu_off = {}
        n_traj_qpu_matched = n_traj

    # Calibration sensitivity band (noiseless at ±offsets)
    if has_cal:
        cal_sz = _sz_from_n(np.concatenate([emu_n_all[0:1], emu["cal_n"]], axis=0))
        cal_lo = cal_sz.min(axis=0)
        cal_hi = cal_sz.max(axis=0)
    else:
        cal_lo = cal_hi = None

    # Time limit for EMU
    t_max_us = (t_max_ns / 1e3) if t_max_ns else emu_times_us[-1]
    emu_mask = emu_times_us <= t_max_us

    # ── Figure ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(7, 4.5))

    # [1] Calibration sensitivity band — widest, behind everything
    if cal_lo is not None:
        ax.fill_between(emu_times_us[emu_mask],
                        cal_lo[emu_mask], cal_hi[emu_mask],
                        color=C_CAL_BAND, alpha=0.25, zorder=1,
                        label="Cal. offset band (noiseless ±)")

    # [2] Noisy QPU-matched envelope — 40 trajectories at calibrated params + noise
    ax.fill_between(emu_times_us[emu_mask],
                    sz_qpu_lo[emu_mask], sz_qpu_hi[emu_mask],
                    color=C_EMU_BAND, alpha=0.25, linewidth=0, zorder=2,
                    label=f"Noisy EMU (QPU-matched, {int(coverage*100)}%, "
                          f"n={n_traj_qpu_matched})")
    ax.plot(emu_times_us[emu_mask], sz_qpu_mean[emu_mask],
            color=C_EMU_MEAN, lw=1.2, zorder=3, label="Noisy EMU mean")

    # [3] Single noisy trajectory — shows individual shot variability
    if sz_qpu_single is not None:
        ax.plot(emu_times_us[emu_mask], sz_qpu_single[emu_mask],
                color=C_EMU_MEAN, lw=0.6, alpha=0.45, zorder=3,
                label="Noisy nominal (1 traj)")

    # [4] Noiseless reference — the user's exact input, no noise, no offsets
    ax.plot(emu_times_us[emu_mask], sz_nl[emu_mask],
            color=C_NL, lw=1.5, ls="--", zorder=4, label="EMU noiseless (nominal)")

    # [5] QPU data
    valid = ~np.isnan(qpu_sz)
    qpu_us = qpu_times / 1e3
    if t_max_ns:
        valid &= qpu_times <= t_max_ns
    ax.errorbar(qpu_us[valid], qpu_sz[valid], yerr=qpu_err[valid],
                fmt="o", ms=3, color=C_QPU, elinewidth=0.8, capsize=2,
                zorder=5, label="FC1")

    # ── Calibration annotation (top-right, matching plot_N5_three_regimes.py) ─
    calib_txt = _calib_text(manifest)
    if calib_txt:
        ax.text(0.97, 0.97, calib_txt,
                transform=ax.transAxes,
                fontsize=7.5, va="top", ha="right",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          alpha=0.8, edgecolor="gray"))

    # ── Axes ──────────────────────────────────────────────────────────────────
    ax.set_xlabel("Time (µs)", fontsize=11)
    ax.set_ylabel(r"$\langle \sigma^z \rangle$", fontsize=12)
    ax.set_xlim(0, t_max_us)
    ax.legend(fontsize=9, framealpha=0.85)
    ax.grid(True, linestyle=":", linewidth=0.4, alpha=0.5)
    ax.tick_params(labelsize=9)

    # SPAM info below legend
    spam_str = f"SPAM: ε={qpu_eps}, ε'={qpu_eprime}"
    ax.text(0.02, 0.03, spam_str, transform=ax.transAxes,
            fontsize=7, va="bottom", color="gray")

    # ── Title ─────────────────────────────────────────────────────────────────
    kw_str = "  ".join(f"{k}={v}" for k, v in seq_kw.items())
    matched_note = (
        f"QPU-matched (ω×{qpu_off.get('omega_offset',1):.4f}, "
        f"δ{qpu_off.get('delta_offset',0):+.3f} MHz)"
        if has_qpu_matched else "nominal params (no QPU manifest)"
    )
    fig.suptitle(
        f"N={qpu_N}×{qpu_N} quench — QPU vs noisy EMU\n"
        f"$h_x/J={qpu_hx:.1f}$   {kw_str}   n_traj={n_traj}   EMU: {matched_note}",
        fontsize=9,
    )

    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight", dpi=150)
    print(f"Figure saved → {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="QPU vs noisy EMU comparison plot, styled like plot_N5_three_regimes.py."
    )
    parser.add_argument("--qpu",       required=True,
                        help="Path to .npz from collect_qpu.py (contains sz_mean, sz_err).")
    parser.add_argument("--emu",       required=True,
                        help="Path to .npz from run_noise_emu.py (contains n_traj).")
    parser.add_argument("--out",       default="qpu_vs_emu.png")
    parser.add_argument("--coverage",  type=float, default=0.7,
                        help="Quantile coverage for EMU band (default 0.7 = 15th–85th pct).")
    parser.add_argument("--t-max-ns",  type=float, default=None,
                        help="Clip x-axis at this time in ns (default: full duration).")
    args = parser.parse_args()

    plot(Path(args.qpu), Path(args.emu), Path(args.out),
         coverage=args.coverage, t_max_ns=args.t_max_ns)


if __name__ == "__main__":
    main()
