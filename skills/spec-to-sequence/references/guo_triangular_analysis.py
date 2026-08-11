"""Observables for the Guo √3×√3 triangular-lattice ordered phase.

Static structure factor at the √3 ordering wavevector K:

    S(K) = (1/N) < | sum_j e^{i K.r_j} (n_j - n_bar) |^2 >_shots

where n_bar = (1/N) sum_j n_j is the *per-shot* mean occupation, n_j in
{0,1} is the measured occupation of atom j (bit '1' = Rydberg), r_j its
physical coordinate, and < . >_shots averages over measurement shots.
Subtracting n_bar removes the trivial k=0 component so S(K) measures
density-wave order specifically at K, not overall filling.

For the triangular lattice with K = (4pi/3a)(1,0):
  K.r over the three sublattices A/B/C takes values {0, 2pi/3, 4pi/3}
  (mod 2pi), so a perfect three-sublattice pattern (one sublattice fully
  Rydberg, the other two empty, i.e. 1/3 filling) maximises S(K).

Perfect-order reference: with N/3 atoms on one sublattice set to n=1 and
2N/3 set to n=0, n_bar = 1/3 and
    |sum_j e^{iK.r_j}(n_j - 1/3)|^2 = (2N/3)^2 * (1/3) ... see compute.
We provide perfect_order_SK() to compute it numerically for the register.
"""
from __future__ import annotations
import numpy as np

from sequences.guo_triangular_sqrt3_sequence import (
    triangular_coords, sqrt3_wavevector, DEFAULT_L, DEFAULT_SPACING_UM,
)


def _bits_array(s: str, N: int) -> np.ndarray:
    return np.fromiter((int(ch) for ch in s[:N]), dtype=float)


def structure_factor_SK(counts: dict[str, int], coords: np.ndarray,
                        K: np.ndarray) -> float:
    """S(K) = (1/N) < |sum_j e^{iK.r_j}(n_j - n_bar)|^2 >_shots.

    n_bar is the per-shot mean occupation. coords is (N,2) in same atom
    order as the bitstrings.
    """
    N = coords.shape[0]
    total = sum(counts.values())
    if total == 0:
        return float("nan")
    phase = np.exp(1j * (coords @ K))  # (N,)
    acc = 0.0
    for s, c in counts.items():
        n = _bits_array(s, N)
        nbar = n.mean()
        amp = np.sum(phase * (n - nbar))
        acc += c * (abs(amp) ** 2)
    return float(acc / total / N)


def mean_density(counts: dict[str, int], N: int) -> float:
    total = sum(counts.values())
    ones = sum(s[:N].count("1") * c for s, c in counts.items())
    return ones / (total * N)


def sublattice_index(coords: np.ndarray,
                     spacing_um: float = DEFAULT_SPACING_UM) -> np.ndarray:
    """Assign each atom to sublattice 0/1/2 via (i - j) mod 3 on the
    triangular Bravais indices.  Recover integer (i,j) from coordinates."""
    a1 = np.array([spacing_um, 0.0])
    a2 = np.array([spacing_um * 0.5, spacing_um * np.sqrt(3) / 2.0])
    # invert [a1 a2] (columns) to get fractional indices
    M = np.column_stack([a1, a2])
    Minv = np.linalg.inv(M)
    # coords were centred; recover by shifting back to integer lattice
    frac = (coords - coords.min(axis=0)) @ Minv.T
    ij = np.rint(frac).astype(int)
    return (ij[:, 0] - ij[:, 1]) % 3


def perfect_order_SK(coords: np.ndarray, K: np.ndarray,
                     spacing_um: float = DEFAULT_SPACING_UM,
                     sublattice: int = 0) -> tuple[float, str]:
    """S(K) for a perfect three-sublattice pattern (one sublattice =1).
    Returns (S(K), bitstring)."""
    sl = sublattice_index(coords, spacing_um)
    n = (sl == sublattice).astype(int)
    bits = "".join(str(b) for b in n)
    return structure_factor_SK({bits: 1000}, coords, K), bits


def sublattice_occupations(counts: dict[str, int], coords: np.ndarray,
                           spacing_um: float = DEFAULT_SPACING_UM):
    """Shot-averaged mean occupation per sublattice (0,1,2)."""
    N = coords.shape[0]
    sl = sublattice_index(coords, spacing_um)
    total = sum(counts.values())
    occ = np.zeros(3)
    cnt = np.array([(sl == k).sum() for k in range(3)], dtype=float)
    for s, c in counts.items():
        n = _bits_array(s, N)
        for k in range(3):
            occ[k] += c * n[sl == k].sum()
    return occ / total / cnt


def top_bitstrings(counts: dict[str, int], k: int = 5):
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:k]


if __name__ == "__main__":
    coords = triangular_coords(DEFAULT_L, DEFAULT_SPACING_UM)
    K = sqrt3_wavevector(DEFAULT_SPACING_UM)
    N = coords.shape[0]
    print(f"N={N}, K={K}")
    for sub in (0, 1, 2):
        sk, bits = perfect_order_SK(coords, K, DEFAULT_SPACING_UM, sub)
        print(f"perfect 3-sublattice (sub={sub}): S(K)={sk:.3f}  "
              f"<n>={bits.count('1')/N:.3f}")
    # disordered reference: all atoms n=0 -> S(K)=0
    print("empty:", structure_factor_SK({"0" * N: 1000}, coords, K))
    # random product of independent 1/3-filling (no spatial order):
    rng = np.random.default_rng(0)
    rc = {}
    for _ in range(2000):
        b = "".join("1" if rng.random() < 1 / 3 else "0" for _ in range(N))
        rc[b] = rc.get(b, 0) + 1
    print("random 1/3-fill (uncorrelated):",
          round(structure_factor_SK(rc, coords, K), 3))
