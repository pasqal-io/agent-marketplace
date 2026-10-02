---
name: spec-to-sequence
description: Generate a Pulser sequence builder for a neutral-atom (Rydberg) experiment from an experiment_spec.json. Output is a *_sequence.py with two standardised functions — build_sequence() and compute_observable() — consumed by validate-emu, qpu-submit and harvest-and-analyze. Triggered by phrases like "generate the Pulser sequence", "write the sequence file for this spec", "spec to sequence", "turn the spec into Pulser code".
argument-hint: "[spec-file]"
---

# spec-to-sequence

Generate `experiments/<name>/<name>_sequence.py` from
`experiments/<name>/<name>_spec.json` — beside the spec, in the experiment's own
tree, not in the working directory's root.

RUNS ON: this machine. Writing and smoke-testing a sequence file costs nothing
and contacts nothing.

The file must export **two required public functions** with standardised
signatures, and may export a third (`build_parametric_sequence`, below).
Everything else (register helpers, intermediate constants) can be private.

## Decisions that are not yours

A geometry or an observable has more than one defensible encoding, and picking
one silently makes the result unreviewable. Ask, with the alternatives named:

- **how the spec's geometry maps onto a Pulser register** when the spec is
  ambiguous (which sites, which layout, what happens at the boundary)
- **the observable's exact definition** — the wavevector, the sign convention,
  whether the mean occupation is subtracted
- **any deviation from the spec** you had to make for the device to accept the
  sequence, which belongs in the spec's `_notes` too

If the sequence will not build or the smoke test will not pass after about
**three** attempts, stop and report: the error, what you changed, and what you
now believe is wrong (the spec, the device limit, or the observable). Then offer
changing the spec, reducing the register, or a different observable. Do not keep
editing the same file hoping the constraint moves.

---

## The functions this file exports

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

### `build_parametric_sequence(device=None, **fixed) -> (Sequence, (var_name,))`

**Optional, and worth writing.** Returns a Pulser sequence with the spec's scan
variable left as a declared variable, plus the tuple of variable names — exactly
one, the scan variable:

```python
def build_parametric_sequence(device=None, **fixed):
    # Same physics as build_sequence, with the scan variable left free.
    # Lets qpu-submit send one batch-level sequence and bind one value per job,
    # which is what the cloud is built for. Without it, the same scan still goes
    # out as one batch, with each job carrying its own serialized sequence.
    seq = pulser.Sequence(_register(device, **fixed), device)
    seq.declare_channel("ising", "rydberg_global")
    t = seq.declare_variable("t_ns", dtype=int)      # the spec's scan variable
    ...                                              # same schedule, t in place
    return seq, ("t_ns",)
```

Everything else — `fixed_params`, the calibration offsets — is baked in as it is
in `build_sequence`. Write it when the scan variable maps cleanly onto a Pulser
variable (a duration, an amplitude, a detuning); skip it when it would change
the register or the number of pulses, and say why in the file.

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

### Provenance stamp — required

Pulser records, inside every serialized sequence, which packages produced it.
Stamping the toolkit there is what later identifies the sequence as
agent-generated: it travels with the abstract representation into the cloud, the
QPU batch and any saved JSON, so a submission stays attributable long after the
`experiments/` directory is gone.

Put this at module level, with the imports:

```python
# Provenance: marks every serialized sequence as produced by this toolkit.
try:
    from pulser.sequence.metadata import store_package_version_metadata
except ImportError:      # older pulser has no sequence metadata
    pass
else:
    store_package_version_metadata("neutral-atom-toolkit", "<toolkit version>")
```

Two things to get right:

- **Read `<toolkit version>` from the toolkit manifest, do not recall it.** The
  `version` field of `plugin.json`, two directories above this skill's own
  directory. Write the value you read as a literal — the generated file is
  copied into HPC bundles and run where no manifest exists, so a lookup at run
  time would either crash or report the wrong version.
- **Keep the `try`/`except`.** Sequence metadata is a recent Pulser addition and
  there is no repo-wide floor that guarantees it, so a bare import would take the
  whole sequence file down over a provenance tag. The stamp is optional; the
  sequence is not.

One call, `package_versions` only. Nothing else belongs in the metadata.

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

Load `experiments/<name>/<name>_spec.json`. Note:
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
    from pulser.devices import Device, VirtualDevice
    if isinstance(device, Device) and not isinstance(device, VirtualDevice):
        reg = reg.with_automatic_layout(device)
```

The guard is the whole layout requirement. `with_automatic_layout` builds a
layout for whatever geometry the spec asks for, and `Sequence(reg, device)` is
the validity check: if it does not raise, the register is allowed. Do not
restrict the geometry to `device.pre_calibrated_layouts` or swap it for a
triangular one — on a device whose `accepts_new_layouts` is True (the Fresnel
devices) those are a convenience, not a constraint.

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

**Compare the observable against states whose value you can derive by hand, and
exit non-zero when one moves.** A printed value nobody compares is not a test:
it catches a crash and nothing else, so a sign error or a dropped term passes
while still looking plausible.

Add at the bottom of the file:

```python
if __name__ == "__main__":
    import json
    from pathlib import Path
    spec = json.loads(
        Path(__file__).with_name("<experiment_name>_spec.json").read_text())
    scan = spec["scan"]
    mid  = scan["values"][len(scan["values"])//2]
    params = {**scan["fixed_params"], scan["variable"]: mid}

    seq = build_sequence(device=None, **params)
    N   = len(seq.register.qubit_ids)
    print(f"Sequence OK: {seq.get_duration()} ns, {N} atoms")

    # The provenance stamp only reaches the serialized form, so check it there.
    stamped = json.loads(seq.to_abstract_repr()).get("metadata", {})
    if "neutral-atom-toolkit" not in stamped.get("package_versions", {}):
        raise SystemExit("✘ provenance stamp missing — see the module header")

    failures = []
    for label, counts, want, tol in [
        ("vacuum",          {"0" * N: 100}, 0.0, 1e-12),
        # add one perfectly ordered pattern, whose value you derived by hand
    ]:
        got = compute_observable(counts)
        ok  = abs(got - want) <= tol
        print(f"  {'ok  ' if ok else 'FAIL'} {label}: {got:+.4f} "
              f"(expect {want:+.4f} ± {tol:g})")
        if not ok:
            failures.append(label)
    if failures:
        raise SystemExit(f"✘ compute_observable wrong for: {', '.join(failures)}")
```

Run `python experiments/<name>/<name>_sequence.py` — every line must read `ok`.
The spec is resolved beside the file, so the smoke test works from anywhere.

Two things to get right in the comparisons:

- **State the disordered floor** if the observable has one. An order parameter
  built from a modulus does not go to zero on random data: ⟨|m|⟩ on an
  uncorrelated array reads √(π/2N), which is 0.18 on 49 atoms. Print that floor
  next to the measurement, or a null result reads as weak order.
- **Assert what the observable silently assumes.** If it reconstructs atom
  coordinates by bitstring index, check that the register's `qubit_ids` order
  and coordinates survived `with_automatic_layout` — a reordering returns a
  plausible wrong number rather than failing.
- **Derive the register size from the shots, never from a module constant.**
  `compute_observable(counts)` receives no geometry, so it is tempting to close
  over the spec's N. Do not: the same file is emulated at reduced size on the way
  to hardware — locally, where 49 atoms are out of reach, or on a device that
  caps lower — and every shot then fails the length check and is skipped. The
  function returns `nan`, which reads as *no signal* rather than *wrong size*, so
  a downsized run looks like failed physics and the real defect is invisible.
  Read the size off the counts instead, take the modal bitstring length so a few
  truncated detections cannot redefine the register, and return `nan` only when
  the length is genuinely inconsistent with any register you could have built:

  ```python
  def register_size_from_counts(counts: dict[str, int]) -> int:
      weight: dict[int, int] = {}
      for bitstring, count in counts.items():
          weight[len(bitstring)] = weight.get(len(bitstring), 0) + count
      return max(weight, key=weight.get) if weight else 0
  ```

  Then add a smoke-test case at a *second* size — a 3×3 patch beside the 7×7 —
  so the inference is exercised rather than assumed. Quantities that scale
  together often cancel and need no adjustment: for a wavevector K ∝ 1/a and
  positions r ∝ a, K·r is spacing-independent. Say which ones you checked.

---

## Step 6 — Report

1. Confirm the file is written beside the spec, at
   `experiments/<name>/` + `spec["sequence_file"]`
2. Show smoke test output — the actual lines, not a summary of them
3. Print Rb/a = (C6/Ω)^(1/6) / spacing to verify blockade regime
4. Say whether `build_parametric_sequence` was written, and if not, why — it
   decides which shape `qpu-submit` uses for the batch
5. Append the block to `experiments/<name>/NOTEBOOK.md`: what was generated,
   which reference it followed, the smoke-test result, Rb/a
6. **Next step**: run `validate-emu` with this spec and sequence file
