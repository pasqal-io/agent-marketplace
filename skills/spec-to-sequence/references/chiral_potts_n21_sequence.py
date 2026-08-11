"""Parametric Pulser sequence for Example 3: chiral-Potts Kibble-Zurek.

Implements the protocol designed in
notes/example3_chiral_potts_design_2026-05-24.md, derived by the
agent from Nyckees, Colbois & Mila, arXiv:2008.08408.

Sweep a 1D Rydberg chain across the Z3 -> disordered transition with
a linear detuning ramp. Vary the sweep duration tau geometrically
({0.5, 1.0, 2.0, 4.0, 8.0} us by default). The end-of-pulse
bitstrings yield the period-3 structure factor S(k=2pi/3), and its
scaling with tau tests the chiral-Potts universality class.

Usage:
    from sequences.chiral_potts_n21_sequence import (
        build_para_chiral_potts_sequence, TAUS_NS,
    )
    seq = build_para_chiral_potts_sequence(
        n_atoms=21, spacing_um=5.74, omega_max_radus=2*np.pi*4e6,
        delta_i_radus=-2*np.pi*8e6, delta_f_radus=+2*np.pi*8e6,
        device="Ruby",   # or "FRESNEL_CAN1" or "DigitalAnalogDevice"
    )
    # tau gets bound at submission time, as the single swept Variable.

The sequence has ONE declared Variable: `tau_ns`. All other
parameters are fixed at construction. This matches the V2 bundle
template's expectation of "one Variable per swept axis".
"""
from __future__ import annotations
import numpy as np

# -- Pulser imports (kept lazy so the file is importable without Pulser) ---
def _pulser():
    """Lazy import so this module can be inspected without Pulser installed."""
    import pulser
    from pulser import Pulse, Register, Sequence
    from pulser.waveforms import RampWaveform, ConstantWaveform
    from pulser.parametrized import Variable
    return pulser, Pulse, Register, Sequence, RampWaveform, ConstantWaveform


# Default sweep grid (Kibble-Zurek log-spaced)
TAUS_NS: tuple[int, ...] = (500, 1_000, 2_000, 4_000, 8_000)

# Default physical parameters. Pulser unit for amplitude / detuning is
# rad/µs (= 2π × MHz), NOT rad/s — these constants must be passed in
# that unit. Hold times are in ns.
DEFAULT_N = 15   # multiple of 3 → fits Z3 exactly; AnalogDevice radius cap 38µm
                 # allows max (N-1)/2 · a ≤ 38, so at a=5µm, N ≤ 16. N=15 picks
                 # the largest Ruby-compatible multiple of 3.
# Bernien-2017 / Ebadi-2021 parameters that experimentally produce a
# clear Z3 phase on real Rydberg arrays:
#   a = 5.74 µm, Ω/2π = 2 MHz, δ sweep from -16 MHz to +8 MHz.
# At Ω = 2π × 2 MHz with C6 = 5.42e6 rad/µs·µm^6 (70S), the blockade
# radius is Rb ≈ 8.85 µm so Rb/a ≈ 1.54 — the system enters the Z3
# regime as δ_f rises above the V_NNN/V_NN crossover (the Z2 → Z3
# transition in the chiral-Potts universality class is at δ ≈ few × Ω
# for this spacing).
# Ruby-compatible Z3-targeting parameters:
#   a = 5.0 µm (Ruby + AnalogDevice min-spacing constraint)
#   Ω/2π = 1 MHz → R_b ≈ 9.78 µm → R_b/a ≈ 1.96 (in Z3 regime, R_b/a > 1.78)
#   δ_f/2π = 4 MHz (within AnalogDevice's ±20 MHz cap)
DEFAULT_SPACING_UM = 5.0
DEFAULT_OMEGA_RADUS = 2 * np.pi * 1.0
DEFAULT_DELTA_I_RADUS = -2 * np.pi * 10
DEFAULT_DELTA_F_RADUS = +2 * np.pi * 4
DEFAULT_HOLD_NS = 0   # AnalogDevice max sequence duration is 6000 ns; reserve all of it for τ


def build_register(n_atoms: int = DEFAULT_N,
                   spacing_um: float = DEFAULT_SPACING_UM,
                   device=None):
    """1D chain on the x-axis, centred on the origin."""
    _, _, Register, _, _, _ = _pulser()
    # Centre the chain at x=0 so a custom register doesn't waste atoms
    # to the side of the layout.
    xs = (np.arange(n_atoms) - (n_atoms - 1) / 2.0) * spacing_um
    qubits = {f"q{i}": (float(xs[i]), 0.0) for i in range(n_atoms)}
    reg = Register(qubits)
    # Pad to satisfy Ruby/FRESNEL filling-fraction constraint (KNOWN_ISSUES #2).
    # Skip for VirtualDevice (e.g. MockDevice) used in local sims.
    if device is not None:
        from pulser.devices._device_datacls import Device, VirtualDevice
        if isinstance(device, Device):
            reg = reg.with_automatic_layout(device)
    return reg


def build_ring_register(n_atoms: int = DEFAULT_N,
                        spacing_um: float = DEFAULT_SPACING_UM,
                        device=None):
    """1D ring with periodic boundary: N atoms on a circle, NN chord = spacing_um.

    The qubit index i runs around the ring in order; for N=21 the geometric
    nearest neighbours of qubit i are qubits (i-1) % N and (i+1) % N. This
    preserves the structure-factor S(2pi/3) calculation (it indexes qubits
    by i, not by spatial coordinate, so chain and ring share the observable).

    Ring radius R = spacing / (2 sin(pi/N)). For N=21, spacing=5 um:
    R = 5 / (2 sin(pi/21)) ~= 16.8 um (well inside FRESNEL's 46 um radial cap).
    """
    _, _, Register, _, _, _ = _pulser()
    R = spacing_um / (2.0 * np.sin(np.pi / n_atoms))
    theta = 2 * np.pi * np.arange(n_atoms) / n_atoms
    qubits = {f"q{i}": (float(R * np.cos(theta[i])),
                        float(R * np.sin(theta[i])))
              for i in range(n_atoms)}
    reg = Register(qubits)
    if device is not None:
        from pulser.devices._device_datacls import Device, VirtualDevice
        if isinstance(device, Device):
            reg = reg.with_automatic_layout(device)
    return reg


def build_para_chiral_potts_sequence(
    n_atoms: int = DEFAULT_N,
    spacing_um: float = DEFAULT_SPACING_UM,
    omega_max_radus: float = DEFAULT_OMEGA_RADUS,
    delta_i_radus: float = DEFAULT_DELTA_I_RADUS,
    delta_f_radus: float = DEFAULT_DELTA_F_RADUS,
    hold_ns: int = DEFAULT_HOLD_NS,
    device_str: str = "Ruby",
):
    """Build the parametric Pulser sequence with `tau_ns` as the single swept Variable.

    The pulse is a Stack of:
      1. ramp-up: Omega 0 -> Omega_max, delta held at delta_i; duration 100 ns
      2. main sweep: Omega constant at Omega_max, delta linear from delta_i -> delta_f,
                     duration `tau_ns` (the swept Variable)
      3. hold: Omega = Omega_max, delta = delta_f, duration `hold_ns`
      4. ramp-down: Omega Omega_max -> 0, delta held at delta_f, duration 100 ns

    The ramp-up/down are needed so Pulser doesn't reject sudden-jump pulses
    on the Ruby hardware.
    """
    pulser, Pulse, _, Sequence, RampWaveform, ConstantWaveform = _pulser()

    # Pick the device by name
    if device_str == "Ruby":
        from pulser.devices import Ruby as device  # noqa: N813
    elif device_str == "FRESNEL_CAN1":
        from pulser.devices import FRESNEL_CAN1 as device  # noqa: N813
    elif device_str == "DigitalAnalog":
        from pulser.devices import DigitalAnalogDevice as device  # noqa: N813
    elif device_str == "AnalogDevice":
        from pulser.devices import AnalogDevice as device  # noqa: N813
    elif device_str == "MockDevice":
        from pulser.devices import MockDevice as device  # noqa: N813
    else:
        raise ValueError(f"unknown device_str: {device_str}")

    reg = build_register(n_atoms=n_atoms, spacing_um=spacing_um, device=device)
    seq = Sequence(reg, device)
    seq.declare_channel("ising", "rydberg_global")

    tau_ns = seq.declare_variable("tau_ns", dtype=int)

    # ramp-up: 100 ns
    seq.add(Pulse(amplitude=RampWaveform(100, 0.0, omega_max_radus),
                  detuning=ConstantWaveform(100, delta_i_radus),
                  phase=0.0), "ising")

    # main sweep: tau_ns
    seq.add(Pulse(amplitude=ConstantWaveform(tau_ns, omega_max_radus),
                  detuning=RampWaveform(tau_ns, delta_i_radus, delta_f_radus),
                  phase=0.0), "ising")

    # hold: hold_ns (skip when 0 — Pulser rejects zero-duration waveforms)
    if hold_ns > 0:
        seq.add(Pulse(amplitude=ConstantWaveform(hold_ns, omega_max_radus),
                      detuning=ConstantWaveform(hold_ns, delta_f_radus),
                      phase=0.0), "ising")

    # ramp-down: 100 ns
    seq.add(Pulse(amplitude=RampWaveform(100, omega_max_radus, 0.0),
                  detuning=ConstantWaveform(100, delta_f_radus),
                  phase=0.0), "ising")

    seq.measure("ground-rydberg")
    return seq


def build_para_chiral_potts_ring_sequence(
    n_atoms: int = DEFAULT_N,
    spacing_um: float = DEFAULT_SPACING_UM,
    omega_max_radus: float = DEFAULT_OMEGA_RADUS,
    delta_i_radus: float = DEFAULT_DELTA_I_RADUS,
    delta_f_radus: float = DEFAULT_DELTA_F_RADUS,
    hold_ns: int = DEFAULT_HOLD_NS,
    device_str: str = "FRESNEL_CAN1",
    device=None,
):
    """Ring variant of build_para_chiral_potts_sequence.

    Identical pulse schedule (ramp-up, main sweep with tau_ns Variable, optional
    hold, ramp-down); only the register topology changes from chain to ring.

    Two ways to specify the target device:
    * `device_str` — one of the Pulser-shipped device names ("Ruby",
      "FRESNEL_CAN1", "DigitalAnalog", "AnalogDevice"). Note: in Pulser 1.6.x
      Ruby/FRESNEL_CAN1 are NOT shipped — they must come from the live SDK
      (`conn.fetch_available_devices()["FRESNEL_CAN1"]`); pass that via `device`.
    * `device` — a Pulser `Device` object obtained from the live SDK; takes
      precedence over `device_str` when both are given.

    Per KNOWN_ISSUES #18, prefer the SDK-fetched real device for any sequence
    bound for QPU OR EMU (so the same builder is used both ways).
    """
    pulser, Pulse, _, Sequence, RampWaveform, ConstantWaveform = _pulser()

    if device is None:
        if device_str == "Ruby":
            from pulser.devices import Ruby as device  # noqa: N813
        elif device_str == "FRESNEL_CAN1":
            from pulser.devices import FRESNEL_CAN1 as device  # noqa: N813
        elif device_str == "DigitalAnalog":
            from pulser.devices import DigitalAnalogDevice as device  # noqa: N813
        elif device_str == "AnalogDevice":
            from pulser.devices import AnalogDevice as device  # noqa: N813
        elif device_str == "MockDevice":
            from pulser.devices import MockDevice as device  # noqa: N813
        else:
            raise ValueError(f"unknown device_str: {device_str}")

    reg = build_ring_register(n_atoms=n_atoms, spacing_um=spacing_um, device=device)
    seq = Sequence(reg, device)
    seq.declare_channel("ising", "rydberg_global")

    tau_ns = seq.declare_variable("tau_ns", dtype=int)

    seq.add(Pulse(amplitude=RampWaveform(100, 0.0, omega_max_radus),
                  detuning=ConstantWaveform(100, delta_i_radus),
                  phase=0.0), "ising")

    seq.add(Pulse(amplitude=ConstantWaveform(tau_ns, omega_max_radus),
                  detuning=RampWaveform(tau_ns, delta_i_radus, delta_f_radus),
                  phase=0.0), "ising")

    if hold_ns > 0:
        seq.add(Pulse(amplitude=ConstantWaveform(hold_ns, omega_max_radus),
                      detuning=ConstantWaveform(hold_ns, delta_f_radus),
                      phase=0.0), "ising")

    seq.add(Pulse(amplitude=RampWaveform(100, omega_max_radus, 0.0),
                  detuning=ConstantWaveform(100, delta_f_radus),
                  phase=0.0), "ising")

    seq.measure("ground-rydberg")
    return seq


# ---------------------------------------------------------------------
# Observable: structure factor at k = 2*pi/3 from bitstring counts
# ---------------------------------------------------------------------

def structure_factor_k(counts: dict[str, int], k: float, n_atoms: int) -> float:
    """Compute S(k) = (1/N^2) sum_{i,j} <n_i n_j> cos(k * (i - j)) from shot counts.

    `counts[bitstring]` is the integer number of shots producing that bitstring.
    Bitstring convention: counts[s] where s[i] == '1' iff atom i was excited.
    """
    total = sum(counts.values())
    if total == 0:
        return float("nan")
    # Mean two-point correlator <n_i n_j>
    nn = np.zeros((n_atoms, n_atoms), dtype=float)
    for s, c in counts.items():
        bits = np.fromiter((int(ch) for ch in s[:n_atoms]), dtype=int)
        nn += c * np.outer(bits, bits)
    nn /= total
    # Sum cos(k(i-j)) weighted by <n_i n_j>
    ij = np.arange(n_atoms)
    diff = ij[:, None] - ij[None, :]
    return float((nn * np.cos(k * diff)).sum() / (n_atoms ** 2))


def structure_factor_period3(counts: dict[str, int], n_atoms: int) -> float:
    """Convenience: S(k = 2*pi/3) — the Z3 order parameter."""
    return structure_factor_k(counts, k=2 * np.pi / 3, n_atoms=n_atoms)


# ---------------------------------------------------------------------
# A tiny smoke test you can run locally (no QPU needed)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # Idealised Z3 product state, alternating 1-0-0-1-0-0-...
    bits = "".join(("1" if i % 3 == 0 else "0") for i in range(DEFAULT_N))
    counts_ideal = {bits: 1000}
    print(f"S(2pi/3) on ideal Z3 state, N={DEFAULT_N}: "
          f"{structure_factor_period3(counts_ideal, DEFAULT_N):.4f}")
    # Disordered state (uniform 1/2 occupation, no correlations) gives ~ 0
    rng = np.random.default_rng(0)
    counts_random = {"".join(rng.integers(0, 2, DEFAULT_N).astype(str)): 1
                     for _ in range(5000)}
    print(f"S(2pi/3) on random uncorrelated bitstrings, N={DEFAULT_N}: "
          f"{structure_factor_period3(counts_random, DEFAULT_N):.4f}")
