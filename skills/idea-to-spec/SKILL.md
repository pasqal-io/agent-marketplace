---
name: idea-to-spec
description: Turn an experiment idea — a physics paper (PDF path, arXiv ID) or a protocol described in conversation — into a structured experiment_spec.json for the Rydberg pipeline. The spec is the input contract for spec-to-sequence, validate-emu, and harvest-and-analyze. Triggered by phrases like "read this paper", "extract the protocol", "I have an idea for an experiment", "turn this idea into a spec", "what's the experiment in this paper", "idea to spec".
argument-hint: "[pdf-path | arxiv-id | description]"
---

# idea-to-spec

Extract a Rydberg quantum experiment protocol from a paper into `<experiment_name>_spec.json`.
This spec is the single shared contract between all pipeline skills — get it right here
and everything downstream works without modification.

---

## Spec schema (all fields required unless marked optional)

```json
{
  "experiment_name": "short_snake_case",
  "version": "1.0",
  "paper": {
    "title": "...",
    "authors": "First Author et al.",
    "arxiv_id": "XXXX.XXXXX",
    "year": 2024
  },
  "device": "FRESNEL_CAN1",
  "register": {
    "geometry": "triangular_rhombus",
    "N_atoms": 36,
    "builder_params": {
      "L": 6,
      "spacing_um": 5.0
    }
  },
  "channel": {
    "type": "rydberg_global",
    "eom_mode": false
  },
  "pulse": {
    "type": "adiabatic_ramp",
    "omega_max_mhz": 2.0,
    "delta_i_mhz": -6.0,
    "ramp_up_ns": 100,
    "ramp_down_ns": 100
  },
  "scan": {
    "variable": "delta_f_mhz",
    "values": [-4.0, 0.0, 2.0, 4.0, 6.0, 8.0],
    "fixed_params": {
      "tau_ns": 4000
    }
  },
  "observable": {
    "type": "structure_factor",
    "description": "S(K) at sqrt(3) ordering wavevector",
    "fn_name": "compute_observable",
    "expected_max": 0.12
  },
  "validation": {
    "noise_retention_min": 0.50
  },
  "shots_per_point": 1000,
  "output_dir": "results/<experiment_name>",
  "sequence_file": "<experiment_name>_sequence.py",
  "builder_fn": "build_sequence",
  "_notes": "any caveats or scaling decisions"
}
```

**`geometry`** — one of: `square`, `chain`, `ring`, `triangular_rhombus`, `custom`
**`pulse.type`** — one of: `adiabatic_ramp`, `eom_quench`
**`observable.type`** — one of: `structure_factor`, `magnetization`, `occupation`, `custom`

---

## Step 1 — Ingest the paper

- **PDF path**: use the Read tool (supports PDFs natively)
- **arXiv ID** (e.g. `2302.08963`): fetch abstract and methods section via WebFetch
- **Description**: use the user's text directly

Read carefully. Focus on: Methods / Experimental Setup / Appendix sections,
figure captions (what observable vs what parameter), and the main result claim.

---

## Step 2 — Extract protocol

Work through these questions and fill the spec:

### Register
- Lattice geometry? (square, triangular, chain, ring)
- Atom number N and side length L?
- Atom spacing a in µm?
- Is N ≤ 100? FC1 hard limit is ~100 atoms, Ruby ~196.

### Drive
- Global Rydberg drive only? (local addressing is not supported in this pipeline)
- EOM mode (fast quench) or standard (adiabatic ramp)?
- Ω_max/2π in MHz?
- Blockade radius: R_b = (C6/Ω)^(1/6) with C6 = 865723 rad/µs·µm^6 (FC1).
  Check R_b/a is in the right regime for the target phase (typically 1.0–2.0).

### Pulse schedule
- **Adiabatic ramp**: linear δ sweep δ_i → δ_f, fixed Ω, duration τ.
  Scan variable is usually δ_f (or τ for Kibble-Zurek).
- **EOM quench**: instantaneous turn-on, constant Ω at mean-field detuning, scan variable is T.

### Scan
- What parameter is swept?
- What values? Cover the phase transition (include both sides).
- What is fixed?

### Observable
- **Structure factor** S(K) = (1/N) |Σ_j e^{iK·r_j} (n_j − ⟨n⟩)|² — for ordered phases.
  K depends on the order: √3 ordering K=(4π/3a,0); Néel K=(π/a)(1,1); Z₃ ring k=2π/3.
- **Staggered magnetization** M_s = (1/N) |Σ_j (−1)^{ix+iy} ⟨n_j⟩| — Néel/antiferromagnetic.
- **Mean occupation** ⟨n⟩ — thermalization or quench dynamics.

---

## Step 3 — Device compatibility check

| Constraint | FRESNEL_CAN1 | Ruby |
|---|---|---|
| Max atoms | ~100 | ~196 |
| Max radial extent | 46 µm | ~50 µm |
| Ω_max/2π | 2 MHz | 4 MHz |
| EOM mode | yes | yes |
| Min spacing | 4–5 µm | 4–5 µm |

If N > FC1 limit: scale down L (reduce by 1 or 2) while preserving R_b/a.
Document this in `_notes`.

If the paper uses Ruby: set `"device": "Ruby"` and ensure the `submit-to-cea`
skill is used for QPU submission instead of `qpu-submit`.

---

## Step 4 — Write the spec

Write `<experiment_name>_spec.json` to the working directory.
Set `output_dir` to `results/<experiment_name>` relative to the working directory.
Set `sequence_file` to `<experiment_name>_sequence.py`.

Add a `"_notes"` field summarising any assumptions or scaling decisions.

---

## Step 5 — Report

Summarise:
1. Paper → protocol translation (what was directly taken vs. adapted)
2. Scaling decisions (if N was reduced)
3. Device choice and compatibility
4. Expected signal: describe qualitatively what the ordered phase looks like
5. **Next step**: `spec-to-sequence` to generate the Pulser builder
