---
name: application-to-idea
description: Scope a rough problem or application into a first technical idea for a neutral-atom (Rydberg) QPU: which documented Pulser method could serve it — MIS, QUBO, an Ising or XY simulation, a graph kernel — what would be measured, at what size, or an honest no-fit. Writes a note for idea-to-spec; use idea-to-spec when a protocol or paper exists. Triggered by phrases like "can neutral atoms do anything with my problem", "is this a fit for a Rydberg QPU", "I don't know what to measure on the QPU".
argument-hint: "[the problem or the wish, in your own words]"
---

# application-to-idea

Start one step before the pipeline. The user has an application, a problem from
their own field, or a hunch — a selection to make, a schedule to build, molecules
to classify, a material whose behaviour they want, a phenomenon they are curious
about — and no view of what a neutral-atom machine could do with it. End with an
idea stated technically enough for `idea-to-spec`: a named method, something
measurable, a size that can be checked before it is bought. Or end with a
documented "no method here fits", which is a result and not a failure.

Entirely a conversation. No scripts but the one that checks the note at the end.

Write and reason in English if that is your working language, but **answer the
user in the language they wrote in.**

**This skill decides nothing scientific.** It surfaces the choices, says what
each one costs and what it would change, and records what the user picked and
what is still open. If you find yourself filling four fields in a row without
asking, stop — you are writing their experiment for them.

It also designs nothing: no Pulser code, no register coordinates, no pulse
values, no `experiment_spec.json`, no emulation, no cloud connection, no
submission. Those are downstream, and doing them here produces numbers nobody
chose. It never forces a problem into a QUBO for want of anything else to say,
never claims a quantum advantage, never invents a device capability, and never
presents a research possibility as a feature that is ready to use.

Skip this skill when the user already has a protocol, a paper, a patent, a PDF or
a Hamiltonian: that is `idea-to-spec`, and a scoping dialogue they do not need
wastes their turn.

## What this skill ships

Load a reference when the step says to, not up front:

```
references/
  method-catalog.md       the candidate methods, each with its maturity level
  selection-rubric.md     how to score and rank candidates, and worked mappings
  pasqal-stack.md         what exists in the stack, and what each part is for
  pulser-primitives.md    the controls, the two physical modes, what is measurable
  emulation-ladder.md     what each register size costs to check, and why start small
  handoff-template.md     the note's required sections
  sources.md              the public documentation to check current claims against
support/
  validate_idea_note.py   checks the finished note has every section, filled
```

Device limits, backend availability and API names **change**. Anything a user
would act on — a size limit, a device capability, an import path — is checked
against the current public documentation in `references/sources.md` before it is
asserted, or it is stated as unverified.

---

## How to run the conversation

Ask in **small batches — two or three questions at a time**, never a
questionnaire. After each batch, say what you now believe and what it rules out.
Offer a recommendation with each question so the user can answer "the second one"
and move on. It is normal for this to take three or four rounds.

Two failure modes to avoid:

- **Interrogating.** Twelve questions up front makes the user do the synthesis
  that is your job. Two questions, then a proposal they can correct.
- **Guessing.** Silently choosing the method or the observable, then presenting a
  finished idea, hands them something they cannot judge and did not choose. Every
  choice you make instead of asking goes in the note as an open question.

---

## Step 1 — What is the actual question, in the user's own words

Do not say QUBO, MIS, Ising, XY or kernel yet. Introducing the vocabulary before
the problem is understood makes the user answer questions about *your* framing.

Three things have to hold by the end of this step:

1. **What they want to know or obtain.** A phenomenon ("does this order"), a
   quantity ("how fast does it thermalise"), a comparison, or a decision ("which
   200 of these 900 projects").
2. **Why it matters to them.** A paper they doubt, a phase diagram they want a
   point on, an internal demo, a proposal, plain curiosity, a process that costs
   money today. This decides how much rigour and how many shots are worth buying.
3. **What outcome would satisfy them.** A curve with a visible feature, a number
   with an error bar, a subset that beats what they use today, a yes/no. **If
   nothing would count as an answer, the experiment cannot be designed yet** —
   say so and go back to 1.

Depending on which way it leans, the useful questions are:

- What concrete result do you want to obtain? What must be selected, predicted,
  simulated or prepared?
- What does one candidate solution look like? How do you decide it is good?
- Are the decisions yes/no choices? Are some pairs incompatible? Do pairs carry a
  cost or a reward?
- What data exists; what are the variables and the constraints?
- What is the approximate size — items, variables, nodes, atoms?
- What classical method is used today, or would be the obvious baseline?
- Do you want the best configuration, several good ones, a distribution, a
  physical observable, a dynamics, or a prepared state?

That last one decides more than the rest: an optimum, a set of good candidates
and a curve are three different pipelines. Do not move on until you can state the
question in one sentence and the user agrees with it. That sentence becomes the
spec's `objective`.

---

## Step 2 — Classify the request

One family, named out loud:

`discrete optimization` · `graph selection` · `analog quantum simulation` ·
`state preparation and control` · `transport or exchange dynamics` ·
`graph machine learning` · `quantum sampling` ·
`reproduction of a published protocol` · `unsupported or insufficiently specified`

**Never classify by industry.** "Finance", "chemistry", "energy" and "logistics"
are not methods — two logistics problems land in different families, and the same
QUBO serves a bank and a warehouse. If the only thing connecting the problem to
this hardware is a sector name, the family is the last one.

---

## Step 3 — Is there a documented method, and is this the right instrument?

Say this plainly, early and without hedging: **this hardware is not a
general-purpose computer.** A wish it cannot serve is better refused in the first
five minutes than after a spec.

What the pipeline's target — a global Rydberg drive on a 2D register — actually
gives you is one Hamiltonian, whose parameters you shape in time:

```
H(t) = Σ_i  (Ω(t)/2) σ_i^x  −  Σ_i δ(t) n_i  +  Σ_{i<j} (C₆ / r_ij⁶) n_i n_j
```

You control the atom positions, Ω(t), δ(t), the total duration, and you read out
which atoms ended up excited.

| Fits well | Why |
|---|---|
| Ordered phases of the Rydberg model (Z₂, Z₃, √3×√3, checkerboard) | this is the native Hamiltonian; the register geometry and R_b/a pick the phase |
| Quenches and non-equilibrium dynamics | Ω, δ are time-dependent by construction |
| Adiabatic sweeps, Kibble-Zurek scaling | a δ ramp through the transition, with duration as the scan variable |
| Unit-disk MIS / QUBO whose graph is a blockade graph | blockade forbids neighbouring excitations, which *is* the independence constraint |
| Selection with pairwise incompatibilities, weighted or not | the same thing, arriving from an application rather than from physics |

| Does not fit this pipeline | What to do instead |
|---|---|
| Gate circuits, QFT, Shor, textbook VQE | a digital backend; nothing here builds circuits |
| Generic electronic-structure chemistry, generic tabular or image ML | no documented fit on this route — say so |
| A graph that is not embeddable in 2D at the required distances | reformulate, or accept an approximate embedding and say so |
| Dynamics far longer than the device's coherence, or than its max sequence duration | shorten the protocol, or accept that you measure a decohered state |
| Fermions, gauge fields, spin > 1/2, beyond a mapping onto the Hamiltonian above | only via an explicit mapping the user must supply and defend |

Then read `references/method-catalog.md` and `references/pasqal-stack.md`, plus
`references/pulser-primitives.md` for anything that has to map onto controls, and
put candidates against these checks:

| Check | The question that kills a candidate |
|---|---|
| Naturalness of mapping | does the problem *become* the model, or is it crowbarred in via penalties? |
| Maturity | is there a library, a public tutorial, a primitive, or only a paper? |
| Physical mode and controls | Rydberg-Ising or XY; global drive, or local addressing / DMM / EOM a device may not offer? |
| Geometry, size, density | embeddable in 2D at allowed distances, N within reach, blockade regime intact? |
| Observable | is the answer computable **from sampled bitstrings**? |
| Classical baseline | what would beat it on a laptop, and is that acceptable? |
| Scientific risk | if it runs perfectly, does the result mean anything? |
| Implementation risk | how much of the work has no documented precedent? |

Score and rank with `references/selection-rubric.md`, and put **at most three**
candidates on the table — three is a ceiling, not a target. For each: method ID,
maturity, why it matches, the domain-to-physics mapping, the Pulser mechanism,
required inputs, expected outputs, the success metric, the classical baseline,
constraints, risks, what is unresolved, the sources, your confidence.

**Recommend one, with the reason, then stop and let the user weigh it.** A silent
choice presented as a conclusion is a decision they cannot audit.

Two distinctions worth stating out loud, because they decide most cases:
**mathematically encodable is not hardware-feasible**, and **technically feasible
is not scientifically useful**.

If nothing fits, `no-documented-pulser-fit` is the answer — and **name the
nearest in-scope question** rather than stopping at "no". "Your QUBO is not
unit-disk, but the sub-problem on this subgraph is, and it would tell you whether
the encoding is the bottleneck" is a useful sentence. Say why no fit was found,
what reformulation could change that, which adjacent tool would be worth
investigating, and which classical approach should stay the default. Never dress
an out-of-scope wish as feasible.

---

## Step 4 — What would be measured, and against what axis?

An experiment is not a state, it is **a curve**. One measurement at one parameter
value is almost never an answer: a structure factor of 0.09 means nothing on its
own, and everything if it rises from 0.01 as the detuning crosses the transition.
So settle two things together:

- **The observable** — computed from bitstrings and nothing else. Structure factor
  S(K) for an ordered phase, staggered magnetisation for Néel order, mean
  occupation ⟨n⟩ for thermalisation, the objective value and the feasibility rate
  for an optimisation. Ask which one the user believes resolves *their* question,
  and say what each would look like if the answer were yes and if it were no.
- **The scan variable** — final detuning δ_f, ramp duration τ, quench time T,
  spacing, instance size. It must cross the interesting region, with points on
  both sides.

The test to apply out loud: *if the physics is there, what does this curve look
like, and does it look different from the curve where the physics is absent?* If
those two sketches are the same picture, the observable is wrong, and finding
that out here costs nothing. Finding it out after a QPU run costs the run.

Say plainly which quantities would exist **only in emulation**: entanglement
entropy, a fidelity to a target state, a full amplitude. A plan resting on one of
those has no QPU step.

---

## Step 5 — What size is affordable, and why start small

Register size is not a detail to settle later: it decides whether the experiment
can be checked before it is bought. Read `references/emulation-ladder.md`, walk
the user down the ladder, and let them choose where they land.

The two sentences that have to reach the user, in their own words:

- **The small run is the only free error message you get.** Almost every failure
  caught at 9 atoms is an implementation failure, not a physics one — and those
  look identical to "nature said no" once they arrive as QPU data.
- **Do not plan on finding the right bond dimension.** Either the register fits
  the emulator's calibrated envelope, or the validation moves to a **sub-system**
  that keeps the geometry motif, the R_b/a and the protocol, and reproduces
  something approaching the expected signal. The full-size number comes from the
  QPU — that is what hardware is for.

---

## Step 6 — Validate, write the note, hand off

Before writing anything, have the user confirm four things:

1. the reformulation is their problem, not a neighbouring one;
2. the output object — the curve, the subset, the number — is what they wanted;
3. the structuring assumptions are acceptable, each one named;
4. the recommended method is the one to hand downstream.

If they cannot confirm 1 or 2, go back to Step 1. That is cheaper than a note
that answers the wrong question convincingly.

Then fill `references/handoff-template.md` and write it as `<short_name>_idea.md`
in the working directory. Prose and lists, not JSON — the spec's schema belongs to
`idea-to-spec`, and locking numbers in here just moves the guessing earlier.

Check it before handing it over:

```bash
python support/validate_idea_note.py <short_name>_idea.md
```

It only checks that every required section exists, is non-empty, and that the
maturity level is one of the six — an empty **Classical baseline** or a missing
**Open questions** is exactly what gets lost between two skills. Paths like
`support/…` resolve against **this skill's directory**; keep the note in the
user's project.

Report to the user in the note's own order, then hand off:

> **Next step**: `idea-to-spec` with this note, to turn it into
> `<name>_spec.json`. It will re-ask anything under **Open questions** that has to
> be a number before a sequence can be built.

Say what `idea-to-spec` must **re-check rather than inherit**: device
compatibility against the live device, whether each observable is measurable
there, register feasibility, the controls the method assumes, and every
unresolved scientific assumption. And that `validate-emu` is the gate before any
hardware — so a plan whose only validation is "emulate the full-size instance"
has no validation.

If the conversation ends without a question the user endorses, say so and write
nothing. A note that invents an objective is worse than no note: it will be read
downstream as a decision the user made.
