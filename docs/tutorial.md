# Your first experiment

From a published paper to an emulated result, on your own machine, in about
twenty minutes. **No account, no cloud, nothing spent.** Every command and every
number below was run to produce this page.

By the end you will have four files you can read and correct, and — more usefully
— a clear view of which parts the agent handles and which parts stay yours.

## Before you start

1. A Python environment with Pulser:

   ```bash
   python3 -m venv ~/pulser-venv
   ~/pulser-venv/bin/pip install "pulser==1.9.0" matplotlib
   export PULSER_VENV=~/pulser-venv
   ```

2. The toolkit installed in your agent — one line, see the
   [install table](../README.md#install).

3. An **empty directory**, opened in your agent. Artefacts land next to you, not
   inside the plugin.

## Step 1 — Turn a paper into a specification

Type this (the arXiv ID is a real paper; substitute your own, or a PDF path, or
just describe a protocol):

> Read arXiv:2302.08963 and turn it into an experiment spec for a neutral-atom
> QPU. I want to emulate it locally first, so keep the register small enough for
> that.

The agent reads the paper, extracts the protocol, and — this is the part worth
watching — **asks you about what the paper does not settle**. Expect questions of
this shape:

- the paper reports several observables; which one has to resolve the phase here?
- the register the paper uses does not fit the device you named. Reduce N while
  holding R_b/a, or target a larger machine?
- the ramp times span two decades in the paper; which range matters to you?

Answer them. That exchange is the experiment being designed, and it is the reason
this is not a code generator. What comes back is
`triangular_lattice_phases_spec.json`, and two of its fields are yours to audit
before anything else happens:

```json
  "objective": "Determine whether the sqrt3 x sqrt3 three-sublattice order of
                Guo et al. is reachable on a 49-atom triangular patch, using the
                per-shot sublattice order parameter <|m|> as the discriminator.",

  "open_questions": [
    {
      "field": "observable.expected_max",
      "question": "1.0 is the algebraic maximum of <|m|>, not a prediction.
                   <|m|> already reads 0.18 on a *disordered* 49-atom array —
                   what value should count as having observed order?",
      "provisional": 1.0,
      "impact": "validate-emu compares retention against this number, so a
                 ceiling that cannot be reached makes every verdict look weak"
    }
  ]
```

**Read `objective` first.** If it is not the experiment you meant, stop here —
everything downstream inherits it. Then read `open_questions`: each entry is a
value the agent chose because the source did not give one. They are proposals.
Edit the file, or say what you want changed and let the agent redo it.

If a spec comes back with `open_questions: []` on a real paper, be suspicious
rather than pleased.

## Step 2 — Generate the sequence

> Generate the Pulser sequence for this spec.

Out comes `triangular_lattice_phases_sequence.py` — a normal Python file
exporting `build_sequence()` and `compute_observable()`, which is the whole
contract every later step uses. It self-tests when you run it:

```console
$ $PULSER_VENV/bin/python triangular_lattice_phases_sequence.py
Sequence OK: 2200 ns, 49 atoms
register: N=49, max radial 27.5 µm, R_b/a = 1.21
  ok   perfect order, sublattice 0, ⟨|m|⟩: 1.0196 (expect 1.0000 ± 0.05)
  ok   empty register, ⟨|m|⟩: 0.0000 (expect 0.0000 ± 1e-12)
  ok   uncorrelated 1/3 filling, ⟨|m|⟩ at the finite-size floor: 0.1763 (expect 0.1790 ± 0.03)
  ok   L=3 patch, perfect order, sublattice 0, ⟨|m|⟩: 1.0000 (expect 1.0000 ± 1e-09)
```

Those are not decorative. The observable is compared against states whose value
is known by hand — a perfectly ordered pattern, an empty register, random data at
the same filling — and the file exits non-zero if any of them moves. **The line
worth your attention is the third one:** ⟨|m|⟩ reads 0.18 on *disordered* data at
this size. That is the floor. A measurement of 0.18 is not weak order, it is no
order, and knowing the floor is what stops you from reading noise as a result.

## Step 3 — Emulate locally, before anything costs anything

> Emulate this locally and tell me whether the implementation holds up.

The agent asks where to run and offers your machine first. Exact state-vector
emulation costs 2^N, so 49 atoms is far out of reach locally — it will downsize
the register for the check, and say so:

```console
$ python <validate-emu>/support/run_local_scan.py \
      --spec       triangular_lattice_phases_spec.json \
      --seq-file   triangular_lattice_phases_sequence.py \
      --out-dir    results/triangular_lattice_phases/emu_local/ \
      --shots      200 --seq-kwargs '{"L": 3}' --noiseless-only

=== validate-emu (local): triangular_lattice_phases ===
  device   AnalogDevice (Pulser bundled stand-in)
  tau_ns ∈ [200, 500, 1000, 2000, 3600, 5800]
  shots=200  overrides={'L': 3}

  [noiseless] tau_ns=200   obs=0.5207  (0.1s)
  [noiseless] tau_ns=500   obs=0.5122  (0.1s)
  [noiseless] tau_ns=1000  obs=0.4414  (0.1s)
  [noiseless] tau_ns=2000  obs=0.3984  (0.2s)
  [noiseless] tau_ns=3600  obs=0.3450  (0.3s)
  [noiseless] tau_ns=5800  obs=0.3430  (0.4s)

  Verdict: GO ✓  (local scope — does not authorise hardware)
    emulated 9 atoms, the spec asks for 49 — a downsized check, not the experiment
    noise model is a stand-in, not this device's calibration
```

**Now read it properly, because "GO" is the least informative word on the
screen.** What this run establishes: the sequence builds on a constrained device,
the observable accepts real bitstrings, and it responds to the scan variable.
That is the class of error which otherwise surfaces after you have paid for shots.

What it does not establish: anything about the physics. The disordered floor for
this observable is √(π/2N), which is **0.42 at 9 atoms** — against 0.18 at the 49
the spec asks for — and the whole scan sits between 0.34 and 0.52, straddling it.
There is no three-sublattice order to see on a 3×3 patch, and the scan says so.
That is the correct outcome of this step, not a failure of it.

(Your numbers will differ in the second digit. Two hundred shots is a sample, and
`⟨|m|⟩` at this size is dominated by that sampling.)

Which is why the verdict file carries its own limits:

```json
{
  "go": true,
  "reasons": [
    "emulated 9 atoms, the spec asks for 49 — a downsized check, not the experiment",
    "noise model is a stand-in, not this device's calibration"
  ],
  "scope": "local emulator",
  "gates_hardware": false,
  "nl_max": 0.5414
}
```

`gates_hardware: false` is enforced downstream: `qpu-submit` will not treat this
file as authorisation.

**Timings, measured.** Noiseless at 9 atoms is instant. The noisy path carries a
density matrix and grows steeply with sequence duration: on a 9-atom quench it
ran 4 s per point at 100 ns and 49 s per point at 4000 ns, and a 6000 ns
adiabatic ramp takes minutes per point. Start with `--noiseless-only`, add noise
when the noiseless curve looks right, and never raise `--max-atoms` past 14 to
"make it work" — it will not, it will hang.

## Step 4 — When you want the real thing

Two steps remain, and both need an account you already have. They are worth
knowing about now because of what they refuse to do.

**The cloud emulation** (`run_emu_scan.py`) runs the *real* register size with
the *live* device noise model. That verdict — not the local one — is what
justifies hardware.

**The submission** prices itself and stops. Before any credential is read, before
the cloud is contacted:

```console
=== qpu-submit: square_lattice_eom_quench — submission plan ===
  device            FRESNEL_CAN1
  scan              t_ns ∈ [16, 100, 300, 600, 1000, 1500, 2000, 2600, 3200, 4000]
  batches           10  (one per scan point)
  shots per batch   300
  experiment shots  3000
  calibration       50 jobs × 20 shots = 1000 shots
  TOTAL QPU SHOTS   4000

  Metered, and a submitted batch cannot be recalled.
✘ nothing has approved this submission, and there is no terminal to ask at.
```

It exits non-zero. Nothing was submitted, nothing was contacted. Approving means
your agent passes `--confirm` after **you** agreed to those numbers, or you type
`y` yourself. Change the scan, the shots or the device and the previous agreement
no longer applies.

Then `harvest-and-analyze` collects the results and writes three files in a
deliberate order: `qpu_counts.json` (the raw bitstrings, untransformed),
`qpu_results.json` (your observable applied to them), `verdict.json` (agreement
with the noise model, in σ). The raw file exists so that re-analysing with a
corrected observable never needs the hardware again.

One optional step reads that raw file: `correct_readout.py` inverts the detector's
two error rates and reports the occupation density the atoms actually had, rather
than the one the camera saw. It runs offline, and it deliberately leaves the
verdict alone, because the noisy emulation it is compared against already contains
those same two rates.

## When it goes wrong

| What you see | What it means |
|---|---|
| `obs=nan` at every scan point | The observable rejected the data — nearly always a register-size mismatch, not an absent signal. The local runner says so explicitly. Fix the observable to read N off the bitstring length |
| `N atoms is past the local emulator's reach` | Expected above ~14 atoms. Downsize with `--seq-kwargs`, or run in the cloud at the real size |
| `Pasqal Cloud credentials incomplete` | Only cloud steps need them. Steps 1–3 do not |
| `build_sequence() does not declare omega_offset` | Calibrated submission needs the two calibration hooks in the builder, or `--no-calibration` |
| A verdict that looks too good | Check `scope` and `gates_hardware` in `verdict.json`, and the register size it actually ran |

## What stays yours

The agent will not decide these for you, and if it appears to, that is the bug
worth reporting:

- whether the objective in the spec is the question you care about
- whether the observable can resolve the phase, and what value counts as a signal
  given the finite-size floor
- every entry in `open_questions`
- whether a downsized register still answers anything
- whether to spend shots, on which device, and how many

## Next

- A protocol of your own: same Step 1, hand it a PDF or describe it. Nothing in
  the skills is specific to these examples.
- The [worked examples](../examples/) — including, in each README, the earlier
  version that was **rejected** and why. The failure modes are the useful part.
- [The seven skills](../AGENTS.md), each usable on its own: bring a sequence and
  ask for an emulation, or bring batch IDs and ask for the analysis.
