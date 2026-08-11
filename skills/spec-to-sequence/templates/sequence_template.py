"""Template for spec-to-sequence skill.

Copy and adapt for a new experiment. The two public functions — build_sequence()
and compute_observable() — are the only interface that validate-emu and
harvest-and-analyze care about. Everything else is private.

This template implements an adiabatic δ-scan on a triangular rhombus lattice
(Example A / Guo pattern). Adapt register geometry and observable as needed.

Reference: ../references/guo_triangular_sqrt3_sequence.py (bundled with this skill)
"""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path

# ── lazy Pulser import (lets file be inspected without Pulser installed) ────
def _pulser():
    from pulser import Pulse, Register, Sequence
    from pulser.waveforms import RampWaveform, ConstantWaveform
    return Pulse, Register, Sequence, RampWaveform, ConstantWaveform


# ── Module-level constants (set from spec, closed over by compute_observable) ─
# Replace with values from your experiment_spec.json
_SPEC_FILE = Path(__file__).with_suffix("").name.replace("_sequence", "_spec.json")
_SPEC = json.loads((Path(__file__).parent / _SPEC_FILE).read_text()) if (
    Path(__file__).parent / _SPEC_FILE).exists() else {}

_L        = _SPEC.get("register", {}).get("builder_params", {}).get("L", 6)
_SPACING  = _SPEC.get("register", {}).get("builder_params", {}).get("spacing_um", 5.0)

# Triangular rhombus coordinates (L×L, centred)
def _triangular_coords(L: int = _L, spacing_um: float = _SPACING) -> np.ndarray:
    a1 = np.array([spacing_um, 0.0])
    a2 = np.array([spacing_um * 0.5, spacing_um * np.sqrt(3) / 2.0])
    pts = np.array([i * a1 + j * a2 for i in range(L) for j in range(L)])
    return pts - pts.mean(axis=0)

_COORDS = _triangular_coords()
_N      = len(_COORDS)
# √3 ordering wavevector K = (4π/3a)(1,0)
_K      = np.array([4.0 * np.pi / (3.0 * _SPACING), 0.0])


# ── Register builder ─────────────────────────────────────────────────────────
def _build_register(L: int = _L, spacing_um: float = _SPACING, device=None):
    _, Register, _, _, _ = _pulser()
    coords = _triangular_coords(L, spacing_um)
    qubits = {f"q{i}_{j}": (float(coords[i*L+j, 0]), float(coords[i*L+j, 1]))
              for i in range(L) for j in range(L)}
    reg = Register(qubits)
    if device is not None:
        from pulser.devices._device_datacls import Device, VirtualDevice
        if isinstance(device, Device) and not isinstance(device, VirtualDevice):
            reg = reg.with_automatic_layout(device)
    return reg


# ── Public: sequence builder ─────────────────────────────────────────────────
def build_sequence(device=None, **params):
    """Build a non-parametric Pulser sequence with all parameters baked in.

    device : live Device object from the cloud SDK, or None for local testing.
    params : merged scan.fixed_params + {scan.variable: current_value}.
             Expected keys: omega_max_mhz, delta_i_mhz, delta_f_mhz, tau_ns.
    """
    Pulse, _, Sequence, RampWaveform, ConstantWaveform = _pulser()
    if device is None:
        from pulser.devices import AnalogDevice as device  # noqa: N813

    L          = params.get("L", _L)
    spacing_um = params.get("spacing_um", _SPACING)
    omega_max  = 2 * np.pi * float(params["omega_max_mhz"])
    delta_i    = 2 * np.pi * float(params["delta_i_mhz"])
    delta_f    = 2 * np.pi * float(params["delta_f_mhz"])
    tau_ns     = int(params["tau_ns"])
    ramp_up    = _SPEC.get("pulse", {}).get("ramp_up_ns", 100)
    ramp_down  = _SPEC.get("pulse", {}).get("ramp_down_ns", 100)

    reg = _build_register(L=L, spacing_um=spacing_um, device=device)
    seq = Sequence(reg, device)
    seq.declare_channel("ising", "rydberg_global")

    # ramp-up
    seq.add(Pulse(amplitude=RampWaveform(ramp_up, 0.0, omega_max),
                  detuning=ConstantWaveform(ramp_up, delta_i), phase=0.0), "ising")
    # main sweep: delta ramps from delta_i to delta_f over tau_ns
    seq.add(Pulse(amplitude=ConstantWaveform(tau_ns, omega_max),
                  detuning=RampWaveform(tau_ns, delta_i, delta_f), phase=0.0), "ising")
    # ramp-down
    seq.add(Pulse(amplitude=RampWaveform(ramp_down, omega_max, 0.0),
                  detuning=ConstantWaveform(ramp_down, delta_f), phase=0.0), "ising")

    seq.measure("ground-rydberg")
    return seq


# ── Public: observable ───────────────────────────────────────────────────────
def compute_observable(counts: dict[str, int]) -> float:
    """S(K) at the √3 ordering wavevector.

    S(K) = (1/N) ⟨ |Σ_j e^{iK·r_j} (n_j − ⟨n⟩_shot)| ² ⟩_shots
    """
    total = sum(counts.values())
    if total == 0:
        return float("nan")
    sk = 0.0
    phases = np.exp(1j * (_COORDS @ _K))
    for s, c in counts.items():
        bits  = np.array([int(ch) for ch in s[:_N]], dtype=float)
        n_bar = bits.mean()
        sk   += c * abs((phases * (bits - n_bar)).sum()) ** 2
    return float(sk / (total * _N))


# ── Smoke test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    spec_path = Path(__file__).parent / _SPEC_FILE
    if not spec_path.exists():
        print(f"Spec not found at {spec_path} — using defaults")
        test_params = {"omega_max_mhz": 2.0, "delta_i_mhz": -6.0,
                       "delta_f_mhz": 6.0, "tau_ns": 4000}
    else:
        spec = _SPEC
        scan = spec["scan"]
        mid  = scan["values"][len(scan["values"]) // 2]
        test_params = {**scan["fixed_params"], scan["variable"]: mid}

    seq = build_sequence(device=None, **test_params)
    N   = len(seq.register.qubit_ids)
    print(f"Sequence OK: {seq.get_duration()} ns, {N} atoms, device={seq.device}")

    from pulser.devices import AnalogDevice
    C6 = AnalogDevice.interaction_coeff
    omega = 2 * np.pi * test_params.get("omega_max_mhz", 2.0)
    Rb = (C6 / omega) ** (1/6)
    spacing = test_params.get("spacing_um", _SPACING)
    print(f"Rb/a = {Rb/spacing:.2f}  (want 1.2–2.0 for ordered phases)")

    counts = {"0" * N: 100}
    print(f"compute_observable (vacuum state): {compute_observable(counts):.4f}  (expect 0)")
