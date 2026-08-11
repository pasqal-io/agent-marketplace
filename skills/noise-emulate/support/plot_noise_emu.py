#!/usr/bin/env python3
"""
plot_noise_emu.py — Plot noise emulation results from run_noise_emu.py output.

Produces a 2-panel figure:
  Panel 1  — Site-averaged magnetisation ⟨σᶻ⟩ = 2⟨n⟩ − 1 vs time
  Panel 2  — Staggered structure factor S(π,π) vs time
             (only for square lattices; otherwise NN connected correlation)

Each panel shows:
  · Noiseless (dashed black)
  · Noisy mean (solid colour)
  · 75% quantile band — 12.5th to 87.5th percentile (filled, same colour)
  · Extended calibration envelope (union of ±offset noiseless curves, light grey)
  · Noise model summary in a text box

Usage
-----
python plot_noise_emu.py --result results/FCAN1_N6_hx4.0_...npz [--out fig.png] [--coverage 0.75]
"""

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pulser


# ── Colour palette  (matches plot_N5_three_regimes.py convention) ──────────────
C_NOISELESS = "tab:blue"     # noiseless reference (blue dashed)
C_NOISY     = "tab:orange"   # noisy mean (orange solid)
C_BAND      = "tab:orange"   # noisy band fill (orange, lower alpha)
C_CAL       = "tab:grey"     # calibration offset band (grey fill)
C_CAL_EDGE  = "tab:grey"


# ── Observable helpers ─────────────────────────────────────────────────────────

def magnetisation(n_traj: np.ndarray, central_mask=None) -> np.ndarray:
    """
    n_traj : (n_runs, n_times, n_sites)
    Returns (n_runs, n_times) — spatially averaged ⟨σᶻ⟩ = 2⟨n⟩ − 1.
    Convention: σᶻ = +1 for Rydberg, −1 for ground (same as analysis_utils).
    """
    sz = 2.0 * n_traj - 1.0          # (n_runs, n_times, n_sites)
    if central_mask is not None:
        sz = sz[:, :, central_mask]
    return sz.mean(axis=-1)           # (n_runs, n_times)


def structure_factor(n_traj: np.ndarray, c_traj: np.ndarray,
                     coords: np.ndarray) -> np.ndarray:
    """
    Compute S(π,π) = (1/N²) Σᵢⱼ φᵢ φⱼ C_conn(i,j) for each trajectory/time.

    n_traj : (n_runs, n_times, n_sites)
    c_traj : (n_runs, n_times, n_sites, n_sites)   ← ⟨n_i n_j⟩
    coords : (n_sites, 2)

    Returns (n_runs, n_times).
    """
    N = n_traj.shape[-1]
    # Staggered phase: φᵢ = (-1)^(ix+iy) from integer grid positions
    # Infer integer grid by dividing by smallest nonzero spacing
    c = coords - coords.min(axis=0)  # shift to origin
    spacings = []
    for d in range(2):
        vals = np.unique(np.round(c[:, d], 6))
        diffs = np.diff(vals)
        if len(diffs):
            spacings.append(diffs.min())
    if not spacings:
        return np.full((n_traj.shape[0], n_traj.shape[1]), np.nan)
    spacing = min(spacings)
    ix = np.round(c[:, 0] / spacing).astype(int)
    iy = np.round(c[:, 1] / spacing).astype(int)
    phase = (-1.0) ** (ix + iy)      # (n_sites,)

    # Connected correlator: C_conn(i,j) = ⟨n_i n_j⟩ - ⟨n_i⟩⟨n_j⟩
    # c_traj stores ⟨n_i n_j⟩; n_traj stores ⟨n_i⟩
    # Shapes: (..., n_sites, n_sites) and (..., n_sites)
    conn = c_traj - (n_traj[..., :, np.newaxis] * n_traj[..., np.newaxis, :])

    # S(q) = (1/N²) φᵢ C_conn(i,j) φⱼ   summed over i,j
    sf = np.einsum("...ij,i,j->...", conn, phase, phase) / N**2
    return sf.real                    # (n_runs, n_times)


def nn_connected_corr(n_traj: np.ndarray, c_traj: np.ndarray,
                      coords: np.ndarray) -> np.ndarray:
    """
    Nearest-neighbour connected correlation averaged over all NN bonds.
    Returns (n_runs, n_times).
    """
    N = n_traj.shape[-1]
    # Find NN bonds: pairs with distance ≈ minimum inter-atom distance
    dists = np.linalg.norm(
        coords[:, np.newaxis, :] - coords[np.newaxis, :, :], axis=-1
    )
    np.fill_diagonal(dists, np.inf)
    d_nn = dists.min()
    pairs = [(i, j) for i in range(N) for j in range(i+1, N)
             if abs(dists[i, j] - d_nn) < 0.1 * d_nn]
    if not pairs:
        return np.full((n_traj.shape[0], n_traj.shape[1]), np.nan)

    conn = c_traj - (n_traj[..., :, np.newaxis] * n_traj[..., np.newaxis, :])
    vals = np.stack([conn[..., i, j] for i, j in pairs], axis=-1)
    return vals.mean(axis=-1)        # (n_runs, n_times)


def _is_square_lattice(coords: np.ndarray, tol=0.05) -> bool:
    """True if coords form an approximately square grid."""
    N = len(coords)
    L = int(round(N**0.5))
    if L * L != N:
        return False
    c = coords - coords.min(axis=0)
    spacings = []
    for d in range(2):
        vals = np.unique(np.round(c[:, d], 6))
        diffs = np.diff(vals)
        if len(diffs):
            spacings.append(diffs.min())
    if len(spacings) < 2:
        return False
    return abs(spacings[0] - spacings[1]) / max(spacings) < tol


def _central_mask(N: int) -> np.ndarray | None:
    """Row-major boolean mask for the inner (L-2)×(L-2) sites of an L×L lattice."""
    L = int(round(N**0.5))
    if L < 3 or L * L != N:
        return None
    mask = np.zeros(N, dtype=bool)
    for r in range(1, L-1):
        for c in range(1, L-1):
            mask[r * L + c] = True
    return mask


# ── Quantile envelope ──────────────────────────────────────────────────────────

def envelope(arr: np.ndarray, coverage: float = 0.75):
    """
    arr      : (n_runs, n_times)
    coverage : fraction of the distribution to show, e.g. 0.75 → 12.5th–87.5th pct
    Returns (mean, lower, upper) each of shape (n_times,).
    """
    alpha = (1.0 - coverage) / 2.0
    mean  = arr.mean(axis=0)
    lo    = np.quantile(arr, alpha,        axis=0)
    hi    = np.quantile(arr, 1.0 - alpha,  axis=0)
    return mean, lo, hi


# ── Noise model text box ───────────────────────────────────────────────────────

def _noise_box_text(nm_json: str) -> str:
    """Format a compact noise model summary from the JSON string."""
    try:
        nm_dict = json.loads(nm_json)
    except Exception:
        return "noise model: (parse error)"

    T2 = (f"1/{nm_dict['dephasing_rate']:.3f}" if nm_dict.get("dephasing_rate")
          else "∞")
    T1 = (f"1/{nm_dict['relaxation_rate']:.4f}" if nm_dict.get("relaxation_rate")
          else "∞")
    n_psd = len(nm_dict.get("detuning_hf", []))

    return (
        f"FRESNEL_CAN1 noise model\n"
        f"  σ_Ω = {nm_dict.get('amp_sigma', 0):.4f}   "
        f"σ_δ = {nm_dict.get('detuning_sigma', 0):.3f} rad/µs\n"
        f"  γ_z = {nm_dict.get('dephasing_rate', 0):.4f}   "
        f"T₂ = {T2} µs\n"
        f"  γ_r = {nm_dict.get('relaxation_rate', 0):.4f}   "
        f"T₁ = {T1} µs\n"
        f"  T = {nm_dict.get('temperature', 0):.0f} µK   "
        f"η = {nm_dict.get('state_prep_error', 0):.3f}   "
        f"ε = {nm_dict.get('p_false_pos', 0):.3f}   "
        f"ε' = {nm_dict.get('p_false_neg', 0):.3f}\n"
        f"  Fresnel PSD: {n_psd} freq. points"
    )


# ── Plot ──────────────────────────────────────────────────────────────────────

def plot(result_path: Path, out_path: Path, coverage: float = 0.75):
    data = np.load(result_path, allow_pickle=False)

    n_traj_all = data["n_traj"]          # (n_traj+1, n_times, n_sites)
    c_traj_all = data["c_traj"]
    times      = data["times"]            # normalised (0, 1]
    total_dur  = float(data["total_duration"][0])
    coords     = data["coords"]           # (n_sites, 2)
    times_ns   = times * total_dur

    n_nl    = n_traj_all[0:1]            # noiseless nominal: shape (1, T, N)
    c_nl    = c_traj_all[0:1]
    n_noisy = n_traj_all[1:]             # noisy: shape (n_traj, T, N)
    c_noisy = c_traj_all[1:]

    n_traj  = n_noisy.shape[0]
    n_sites = n_noisy.shape[2]
    sq      = _is_square_lattice(coords)
    L       = int(round(n_sites**0.5)) if sq else None
    c_mask  = _central_mask(n_sites) if sq else None

    nm_json = str(data["noise_model_json"][0]) if "noise_model_json" in data else ""
    seq_kw  = json.loads(str(data["seq_kwargs_json"][0])) if "seq_kwargs_json" in data else {}

    # ── Calibration curves (noiseless at ±offsets) ────────────────────────
    has_cal     = "cal_n" in data
    has_qpu_traj = "n_traj_qpu" in data   # QPU-matched noisy trajectories

    if has_cal:
        cal_n_all = np.concatenate([n_nl, data["cal_n"]], axis=0)
        cal_c_all = np.concatenate([c_nl, data["cal_c"]], axis=0)
    else:
        cal_n_all = n_nl
        cal_c_all = c_nl

    # QPU-matched trajectories (sequence at calibrated params + noise)
    # n_traj_qpu[0]  → single "noisy nominal" reference line (individual shot)
    # n_traj_qpu[:]  → full ensemble band (40 trajectories)
    if has_qpu_traj:
        n_qpu  = data["n_traj_qpu"]                         # (n_traj, n_times, n_sites)
        c_qpu  = data["c_traj_qpu"]
        qpu_off = json.loads(str(data["qpu_offset_json"][0]))
        # Use QPU-matched trajectories for the noisy curves
        noisy_src_n = n_qpu
        noisy_src_c = c_qpu
        band_label  = f"Noisy QPU-matched ({int(coverage*100)}%, n={n_qpu.shape[0]})"
        mean_label  = "Noisy mean (QPU-matched)"
        single_label = "Noisy nominal (1 traj, QPU-matched params)"
    else:
        # No manifest — use the standard noisy-at-nominal trajectories
        noisy_src_n = n_noisy
        noisy_src_c = c_noisy
        band_label  = f"Noisy EMU ({int(coverage*100)}% quantile, n={n_traj})"
        mean_label  = "Noisy mean (nominal)"
        single_label = None

    # ── Compute observables ────────────────────────────────────────────────
    mag_nl    = magnetisation(n_nl, central_mask=c_mask)[0]
    mag_cal   = magnetisation(cal_n_all, central_mask=c_mask) if has_cal else None

    if sq:
        obs2_nl    = structure_factor(n_nl, c_nl, coords)[0]
        obs2_cal   = structure_factor(cal_n_all, cal_c_all, coords) if has_cal else None
        obs2_label = r"$S(\pi,\pi)$"
    else:
        obs2_nl    = nn_connected_corr(n_nl, c_nl, coords)[0]
        obs2_cal   = nn_connected_corr(cal_n_all, cal_c_all, coords) if has_cal else None
        obs2_label = r"NN connected corr."

    # Ensemble observables from whichever source (QPU-matched or nominal)
    mag_ens  = magnetisation(noisy_src_n, central_mask=c_mask)
    obs2_ens = (structure_factor(noisy_src_n, noisy_src_c, coords) if sq
                else nn_connected_corr(noisy_src_n, noisy_src_c, coords))

    # Single noisy trajectory (index 0 of QPU-matched, or None)
    mag_single  = mag_ens[0]  if has_qpu_traj else None
    obs2_single = obs2_ens[0] if has_qpu_traj else None

    # ── Envelopes ─────────────────────────────────────────────────────────
    mag_mean,  mag_lo,  mag_hi  = envelope(mag_ens,  coverage)
    obs2_mean, obs2_lo, obs2_hi = envelope(obs2_ens, coverage)
    times_us = times_ns / 1e3      # µs for x-axis (matches QPU plots)

    # ── Figure layout ──────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(7, 6), sharex=True,
                             gridspec_kw={"hspace": 0.08})
    ax_mag, ax_obs2 = axes

    for ax, (ens_mean, ens_lo, ens_hi, nl_curve, single_curve,
             cal_curves, ylabel) in zip(
        axes,
        [
            (mag_mean,  mag_lo,  mag_hi,  mag_nl,  mag_single,
             mag_cal,  r"$\langle \sigma^z \rangle$"),
            (obs2_mean, obs2_lo, obs2_hi, obs2_nl, obs2_single,
             obs2_cal, obs2_label),
        ],
    ):
        # Extended calibration envelope (grey, widest band first)
        if cal_curves is not None and has_cal:
            cal_lo = cal_curves.min(axis=0)
            cal_hi = cal_curves.max(axis=0)
            ax.fill_between(times_us, cal_lo, cal_hi,
                            color=C_CAL, edgecolor=C_CAL_EDGE, linewidth=0.5,
                            alpha=0.3, zorder=1,
                            label="Calibration offset envelope")

        # Ensemble band (QPU-matched or nominal depending on whether manifest was given)
        ax.fill_between(times_us, ens_lo, ens_hi,
                        color=C_BAND, alpha=0.25, linewidth=0, zorder=2,
                        label=band_label)

        # Ensemble mean
        ax.plot(times_us, ens_mean,
                color=C_NOISY, linewidth=1.6, zorder=3, label=mean_label)

        # Single noisy trajectory (index 0) — shows individual shot variability
        if single_curve is not None:
            ax.plot(times_us, single_curve,
                    color=C_NOISY, linewidth=0.6, alpha=0.5, zorder=3,
                    label=single_label)

        # Noiseless reference — the user's exact input, no noise, no offsets
        ax.plot(times_us, nl_curve,
                color=C_NOISELESS, linewidth=1.2, linestyle="--", zorder=4,
                label="Noiseless nominal (exact input)")

        ax.set_ylabel(ylabel, fontsize=11)
        ax.grid(True, linestyle=":", linewidth=0.4, alpha=0.5)
        ax.tick_params(labelsize=9)

    ax_obs2.set_xlabel("Time (µs)", fontsize=11)

    # ── Legend on top panel ────────────────────────────────────────────────
    ax_mag.legend(fontsize=8, loc="best", framealpha=0.85,
                  handlelength=1.8, borderpad=0.5)

    # ── Noise model annotation (bottom panel) ─────────────────────────────
    if nm_json:
        txt = _noise_box_text(nm_json)
        ax_obs2.text(
            0.01, 0.03, txt,
            transform=ax_obs2.transAxes,
            fontsize=6.5,
            verticalalignment="bottom",
            fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor="#BDBDBD", alpha=0.9),
        )

    # ── Title ──────────────────────────────────────────────────────────────
    title_parts = ["FRESNEL_CAN1 noise emulation"]
    if seq_kw:
        title_parts.append("  |  " + "  ".join(f"{k}={v}" for k, v in seq_kw.items()))
    if sq and L:
        title_parts.append(f"  |  {L}×{L} lattice ({n_sites} qubits)")
    chi_str = (result_path.stem.split("chi")[-1].split("_")[0]
               if "chi" in result_path.stem else "?")
    title_parts.append(f"\nmax_χ = {chi_str}"
                       f"   n_traj = {n_traj}"
                       f"   coverage = {int(coverage*100)}%")
    fig.suptitle("".join(title_parts), fontsize=8.5, y=1.01)

    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight", dpi=150)
    print(f"Figure saved → {out_path}")
    return out_path


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Plot noise emulation results from run_noise_emu.py output.",
    )
    parser.add_argument("--result",   required=True,
                        help="Path to .npz file produced by run_noise_emu.py.")
    parser.add_argument("--out",      default=None,
                        help="Output figure path (default: same name as .npz, .png).")
    parser.add_argument("--coverage", type=float, default=0.75,
                        help="Quantile coverage fraction (default: 0.75 → 12.5th–87.5th pct).")
    args = parser.parse_args()

    result_path = Path(args.result)
    out_path    = Path(args.out) if args.out else result_path.with_suffix(".png")
    plot(result_path, out_path, coverage=args.coverage)


if __name__ == "__main__":
    main()
