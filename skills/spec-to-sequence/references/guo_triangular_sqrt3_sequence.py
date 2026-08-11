"""Parametric Pulser sequence for the Guo et al. (arXiv:2302.08963)
triangular-lattice Rydberg array, √3×√3 (three-sublattice, 1/3-filling)
density-wave ordered phase.

Paper: "Order-by-disorder and emergent Kosterlitz-Thouless phase in
triangular Rydberg array", Sibo Guo et al., arXiv:2302.08963 (2023).
Corpus protocol: global Rabi drive + van der Waals on a triangular
lattice (N <= 196), √3×√3 TAF order via end-of-pulse bitstrings +
correlations, blockade radius R_b ~= 1.2 a.

QPU-friendly equilibrium demonstration:
  - single adiabatic detuning ramp (disordered -> ordered),
  - global rydberg_global drive only,
  - ground-rydberg occupation readout.

Geometry: rhombus patch of L x L sites on the triangular Bravais lattice
    a1 = (a, 0),   a2 = (a/2, a*sqrt(3)/2).
Defaults L=6 -> N=36, a=5 um. Max radial distance 21.7 um < FRESNEL 46 um.

Blockade regime (FRESNEL_CAN1 C6 = 865723 rad/us um^6, Omega = 2pi*2 MHz):
    R_b = (C6/Omega)^(1/6) = 6.40 um  ->  R_b/a = 1.28
    V_NN  / Omega = 4.4   (nearest neighbours strongly blockaded)
    V_NNN / Omega = 0.16  (next-nearest essentially free)
  => a Rydberg atom blockades its 6 nearest neighbours, selecting the
     √3×√3 three-sublattice (1/3-filling) order. Matches Guo R_b ~= 1.2 a.

Ramp (Bernien/Ebadi-style single linear detuning sweep):
    delta_i = -2pi * 6 MHz  (disordered / paramagnetic)
    delta_f = +2pi * 6 MHz  (deep in the √3 ordered lobe)
    Omega held at Omega_max = 2pi * 2 MHz during the sweep.
Sweep duration tau_ns is the single declared Variable.

Order parameter: static structure factor at the √3 ordering wavevector
    S(K) = (1/N) | sum_j e^{i K.r_j} (n_j - <n>) |^2   (shot-averaged),
    K = (4pi / 3a) * (1, 0)  (M/K-point of the triangular lattice that
    is dual to the three-sublattice partition; see analysis module).
"""
from __future__ import annotations
import numpy as np


def _pulser():
    import pulser  # noqa: F401
    from pulser import Pulse, Register, Sequence
    from pulser.waveforms import RampWaveform, ConstantWaveform
    return Pulse, Register, Sequence, RampWaveform, ConstantWaveform


# Defaults: 6x6 triangular rhombus, FRESNEL_CAN1-friendly
DEFAULT_L = 6                          # 6 x 6 = 36 atoms
DEFAULT_SPACING_UM = 5.0
DEFAULT_OMEGA_RADUS = 2 * np.pi * 2.0  # FRESNEL_CAN1 cap
DEFAULT_DELTA_I_RADUS = -2 * np.pi * 6.0
DEFAULT_DELTA_F_RADUS = +2 * np.pi * 6.0


def lattice_vectors(spacing_um: float = DEFAULT_SPACING_UM):
    a1 = np.array([spacing_um, 0.0])
    a2 = np.array([spacing_um * 0.5, spacing_um * np.sqrt(3) / 2.0])
    return a1, a2


def triangular_coords(L: int = DEFAULT_L,
                      spacing_um: float = DEFAULT_SPACING_UM) -> np.ndarray:
    """(N,2) physical xy coords (um), centred. Register order = i*L + j."""
    a1, a2 = lattice_vectors(spacing_um)
    pts = np.array([i * a1 + j * a2 for i in range(L) for j in range(L)])
    pts = pts - pts.mean(axis=0)
    return pts


def sqrt3_wavevector(spacing_um: float = DEFAULT_SPACING_UM) -> np.ndarray:
    """√3 ordering wavevector K = (4pi/3a)(1,0).

    This is the K-point (corner of the Brillouin zone) of the triangular
    lattice; K.r is constant mod 2pi/3 across the three sublattices, so
    a perfect three-sublattice density pattern peaks S(K) here.
    """
    return np.array([4.0 * np.pi / (3.0 * spacing_um), 0.0])


def build_register(L: int = DEFAULT_L,
                   spacing_um: float = DEFAULT_SPACING_UM,
                   device=None):
    """Centred triangular rhombus register (L*L atoms)."""
    _, Register, _, _, _ = _pulser()
    pts = triangular_coords(L, spacing_um)
    qubits = {f"q{i}_{j}": (float(pts[i * L + j, 0]), float(pts[i * L + j, 1]))
              for i in range(L) for j in range(L)}
    reg = Register(qubits)
    if device is not None and getattr(device, "requires_layout", False):
        reg = reg.with_automatic_layout(device)
    return reg


def build_guo_sequence(
    L: int = DEFAULT_L,
    spacing_um: float = DEFAULT_SPACING_UM,
    omega_max_radus: float = DEFAULT_OMEGA_RADUS,
    delta_i_radus: float = DEFAULT_DELTA_I_RADUS,
    delta_f_radus: float = DEFAULT_DELTA_F_RADUS,
    device=None,
    device_str: str = "MockDevice",
):
    """Parametric adiabatic sequence with `tau_ns` as the sole Variable.

    Stack:
      1. ramp-up:   100 ns, Omega 0 -> Omega_max, delta held at delta_i
      2. main:      tau_ns, Omega constant, delta linear delta_i -> delta_f
      3. ramp-down: 100 ns, Omega Omega_max -> 0, delta held at delta_f
    Total duration = tau_ns + 200 ns (<= 6000 ns -> tau_ns <= 5800).
    Pass a live `device` object (e.g. FRESNEL_CAN1) or a `device_str`.
    """
    Pulse, _, Sequence, RampWaveform, ConstantWaveform = _pulser()

    if device is None:
        if device_str == "AnalogDevice":
            from pulser.devices import AnalogDevice as device  # noqa: N813
        elif device_str == "MockDevice":
            from pulser.devices import MockDevice as device  # noqa: N813
        else:
            raise ValueError(f"unknown device_str: {device_str}")

    reg = build_register(L=L, spacing_um=spacing_um, device=device)
    seq = Sequence(reg, device)
    seq.declare_channel("ising", "rydberg_global")

    tau_ns = seq.declare_variable("tau_ns", dtype=int)

    seq.add(Pulse(amplitude=RampWaveform(100, 0.0, omega_max_radus),
                  detuning=ConstantWaveform(100, delta_i_radus),
                  phase=0.0), "ising")
    seq.add(Pulse(amplitude=ConstantWaveform(tau_ns, omega_max_radus),
                  detuning=RampWaveform(tau_ns, delta_i_radus, delta_f_radus),
                  phase=0.0), "ising")
    seq.add(Pulse(amplitude=RampWaveform(100, omega_max_radus, 0.0),
                  detuning=ConstantWaveform(100, delta_f_radus),
                  phase=0.0), "ising")

    seq.measure("ground-rydberg")
    return seq


if __name__ == "__main__":
    pts = triangular_coords()
    print(f"N = {len(pts)}, max radial = {np.linalg.norm(pts, axis=1).max():.2f} um")
    K = sqrt3_wavevector()
    print(f"K = {K}, |K| = {np.linalg.norm(K):.4f} 1/um")
