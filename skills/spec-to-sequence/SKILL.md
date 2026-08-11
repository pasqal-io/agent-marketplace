---
name: spec-to-sequence
description: Generate a Pulser sequence builder file from an experiment_spec.json. Output is a *_sequence.py with two standardised functions — build_sequence() and compute_observable() — consumed by validate-emu and harvest-and-analyze. Triggered by phrases like "generate the sequence", "write the sequence file", "spec to sequence", "build the Pulser sequence from spec", "convert spec to code".
argument-hint: "[spec-file]"
---

# spec-to-sequence

Generate `<experiment_name>_sequence.py` from `<experiment_name>_spec.json`.

The file must export exactly **two public functions** with standardised signatures.
Everything else (register helpers, intermediate constants) can be private.

---

## Two required functions

### `build_sequence(device=None, **params) -> pulser.Sequence`

Returns a **non-parametric** (fully built) Pulser sequence — no `declare_variable`,
no `.build()` call required downstream.

```python
def build_sequence(device=None, **params) -> pulser.Sequence:
    """
    Build a non-parametric sequence with all parameter values baked in.

    device : live Pulser Device object from the cloud SDK, or None for local
             validation (falls back to AnalogDevice / MockDevice).
    params : merged dict of spec["scan"]["fixed_params"] and
             {spec["scan"]["variable"]: current_value}.
             Example: {"tau_ns": 4000, "delta_f_mhz": 6.0}
    """
```

### `compute_observable(counts: dict[str, int]) -> float`

Compute the target observable. Must close over experiment-specific
constants (lattice coordinates, wavevector, N) defined at module level.

```python
def compute_observable(counts: dict[str, int]) -> float:
    """
    Compute the target observable from bitstring counts.
    counts maps bitstring -> integer count.
    Returns a scalar.
    """
```

---

## Reference implementations

Study these before writing. They are the ground truth for FC1-compatible code.

| What you need | File |
|---|---|
| Triangular rhombus register | `references/guo_triangular_sqrt3_sequence.py` |
| Ring register | `references/chiral_potts_n21_sequence.py` |
| Adiabatic ramp pulse stack | `guo_triangular_sqrt3_sequence.py::build_guo_sequence` |
| S(K) structure factor | `references/guo_triangular_analysis.py` |
| Ring S(k) structure factor | `chiral_potts_n21_sequence.py::structure_factor_k` |
| `with_automatic_layout` guard | `chiral_potts_n21_sequence.py::build_ring_register` |

The `references/` directory is bundled inside this skill's own directory.

---

## Step 1 — Read the spec

Load `<experiment_name>_spec.json`. Note:
- `register.geometry`, `register.builder_params`
- `channel.eom_mode` (true = EOM, false = adiabatic ramp)
- `pulse.type` and all pulse parameters
- `scan.variable`, `scan.fixed_params`
- `observable.type` and `observable.description`

---

## Step 2 — Register builder

Write a private `_build_register(device=None, **params)` function.

**Geometry patterns:**

```python
# square L×L (use SquareLatticeLayout)
from pulser.register.special_layouts import SquareLatticeLayout
coords = SquareLatticeLayout(L, L, spacing_um).coords
reg = pulser.Register.from_coordinates(coords, prefix="q")

# chain: N atoms on x-axis, centred
xs = (np.arange(N) - (N-1)/2.0) * spacing_um
qubits = {f"q{i}": (float(xs[i]), 0.0) for i in range(N)}
reg = Register(qubits)

# ring: N atoms on circle, chord = spacing_um
R_ring = spacing_um / (2.0 * np.sin(np.pi / N))
theta = 2*np.pi*np.arange(N)/N
qubits = {f"q{i}": (R_ring*np.cos(theta[i]), R_ring*np.sin(theta[i])) for i in range(N)}
reg = Register(qubits)

# triangular rhombus: L×L on Bravais lattice, centred
a1 = np.array([spacing_um, 0.0])
a2 = np.array([spacing_um*0.5, spacing_um*np.sqrt(3)/2.0])
pts = np.array([i*a1 + j*a2 for i in range(L) for j in range(L)])
pts -= pts.mean(axis=0)
qubits = {f"q{i}_{j}": (float(pts[i*L+j,0]), float(pts[i*L+j,1]))
          for i in range(L) for j in range(L)}
reg = Register(qubits)
```

Always add the layout guard (required by real FC1/Ruby device, skipped for VirtualDevice):
```python
if device is not None:
    from pulser.devices._device_datacls import Device, VirtualDevice
    if isinstance(device, Device) and not isinstance(device, VirtualDevice):
        reg = reg.with_automatic_layout(device)
```

---

## Step 3 — Pulse schedule

**Units convention: Ω and δ in rad/µs; time in ns.**
`2 * np.pi * 2.0` = 2 MHz in rad/µs.

### Adiabatic ramp (`pulse.type == "adiabatic_ramp"`)

```python
from pulser import Pulse, Sequence
from pulser.waveforms import RampWaveform, ConstantWaveform

omega_max = 2 * np.pi * params["omega_max_mhz"]
delta_i   = 2 * np.pi * params["delta_i_mhz"]
delta_f   = 2 * np.pi * params["delta_f_mhz"]
tau_ns    = int(params["tau_ns"])
ramp_up   = spec["pulse"]["ramp_up_ns"]     # typically 100
ramp_down = spec["pulse"]["ramp_down_ns"]   # typically 100

seq = Sequence(reg, device or AnalogDevice)
seq.declare_channel("ising", "rydberg_global")

seq.add(Pulse(amplitude=RampWaveform(ramp_up, 0.0, omega_max),
              detuning=ConstantWaveform(ramp_up, delta_i), phase=0.0), "ising")
seq.add(Pulse(amplitude=ConstantWaveform(tau_ns, omega_max),
              detuning=RampWaveform(tau_ns, delta_i, delta_f), phase=0.0), "ising")
seq.add(Pulse(amplitude=RampWaveform(ramp_down, omega_max, 0.0),
              detuning=ConstantWaveform(ramp_down, delta_f), phase=0.0), "ising")
seq.measure("ground-rydberg")
```

### EOM quench (`pulse.type == "eom_quench"`)

```python
C6     = device.interaction_coeff if device else AnalogDevice.interaction_coeff
ci     = (L//2)*L + (L//2)          # central atom index (square lattice)
diff   = coords - coords[ci]
dist   = np.linalg.norm(diff, axis=-1); dist[ci] = np.inf
delta  = C6 * np.sum(1.0 / dist**6)  # mean-field detuning at centre

omega  = 2 * np.pi * params["omega_max_mhz"]
t_ns   = int(params["t_ns"])

seq = Sequence(reg, device or AnalogDevice)
seq.declare_channel("ising", "rydberg_global")
seq.enable_eom_mode("ising", amp_on=omega, detuning_on=delta)
seq.add_eom_pulse("ising", duration=t_ns, phase=0.0)
seq.disable_eom_mode("ising")
seq.measure("ground-rydberg")
```

---

## Step 4 — Observable function

Define module-level constants first (these are closed over by `compute_observable`):

### Structure factor S(K)

```python
# Module-level constants (set once from spec)
_L        = spec["register"]["builder_params"]["L"]
_SPACING  = spec["register"]["builder_params"]["spacing_um"]
_COORDS   = <lattice coords as (N,2) array>
_N        = len(_COORDS)

# Wavevector from observable.description:
# "sqrt3" → K = (4π/3a)(1,0)
# "pi"    → K = (π/a)(1,1)  [2D Néel]
# "2pi/3" → handled as ring index below
_K = np.array([4.0*np.pi/(3.0*_SPACING), 0.0])  # example: sqrt3

def compute_observable(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    if total == 0:
        return float("nan")
    sk = 0.0
    for s, c in counts.items():
        bits  = np.array([int(ch) for ch in s[:_N]], dtype=float)
        n_bar = bits.mean()
        phases = np.exp(1j * (_COORDS @ _K))
        sk    += c * abs((phases * (bits - n_bar)).sum()) ** 2
    return float(sk / (total * _N))
```

### Ring structure factor S(k) at k = 2π/3

```python
_N = <n_atoms>
_K_RING = 2.0 * np.pi / 3.0   # Z₃ ordering wavevector in index space

def compute_observable(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    if total == 0:
        return float("nan")
    nn = np.zeros((_N, _N))
    for s, c in counts.items():
        bits = np.array([int(ch) for ch in s[:_N]], dtype=float)
        nn  += c * np.outer(bits, bits)
    nn /= total
    ij   = np.arange(_N)
    diff = ij[:, None] - ij[None, :]
    return float((nn * np.cos(_K_RING * diff)).sum() / _N**2)
```

---

## Step 5 — Smoke test

Add at the bottom of the file:

```python
if __name__ == "__main__":
    import json
    from pathlib import Path
    spec = json.loads(Path("<experiment_name>_spec.json").read_text())
    scan = spec["scan"]
    mid  = scan["values"][len(scan["values"])//2]
    params = {**scan["fixed_params"], scan["variable"]: mid}
    seq = build_sequence(device=None, **params)
    N   = len(seq.register.qubit_ids)
    print(f"Sequence OK: {seq.get_duration()} ns, {N} atoms")
    counts = {"0" * N: 100}
    print(f"compute_observable (vacuum): {compute_observable(counts):.4f}  (expect 0)")
```

Run `python <experiment_name>_sequence.py` — must complete with no errors.

---

## Step 6 — Report

1. Confirm the file is written at `spec["sequence_file"]`
2. Show smoke test output
3. Print Rb/a = (C6/Ω)^(1/6) / spacing to verify blockade regime
4. **Next step**: run `validate-emu` with this spec and sequence file
