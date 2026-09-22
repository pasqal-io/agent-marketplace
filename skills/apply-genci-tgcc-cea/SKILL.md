---
name: apply-genci-tgcc-cea
description: >-
  Help a researcher apply for QPU hours on the Pasqal Ruby (Orion) analogue
  neutral-atom simulator hosted at GENCI/CEA TGCC. Two application routes to the
  same machine, chosen by one question - which country is the organisation in?
  French organisations apply through the national GENCI eDARI portal (edari.fr,
  Dynamic Allocation up to 100 h); non-French EU / Digital-Europe / Horizon-Europe
  organisations apply through the EuroHPC Quantum Access Pilot call
  (access.eurohpc-ju.europa.eu, 10-25 h). Everything else - eligibility posture,
  eliciting the science, drafting the text, the early connection-IP check, and the
  shared TGCC computing-account + onboarding tail - is common to both. Coaches the
  user through their own application: guides click-by-click (default) or, with
  direct browser access (browser plugin / integrated browser like Claude Desktop),
  fills the forms itself. Batches questions upfront, shows a review table before
  touching the browser, stops at every credential/consent/submit gate for explicit
  approval. Triggered by "apply for TGCC hours", "eDARI application", "request QPU
  computing hours", "apply for Ruby/Pasqal QPU allocation", "GENCI allocation",
  "request a TGCC computing account", "EuroHPC quantum hours", "Quantum Access
  Pilot", "apply on access.eurohpc-ju.europa.eu", "attach to a project /
  rattachement".
---

# Apply for QPU hours on Ruby at GENCI/CEA TGCC (eDARI or EuroHPC route)

**Ruby** (Pasqal Orion, 100-qubit analogue neutral-atom simulator) is hosted at
**GENCI/CEA TGCC (France)**. There are two ways to *apply* for time on it - the
national **GENCI eDARI** route and the **EuroHPC Quantum Access Pilot** - selected
by a single question **after** the shared setup below (see **Pick the route**).

## Purpose and posture (both routes)

Help a prospective user **prepare and submit their own genuine application**. The
user is the applicant; the assistant is a **coach**, not the author of their
science. Depending on the environment the assistant either **guides the user
click-by-click** (default) or **fills the forms itself** (only with direct browser
access - see the mode choice below).

- **Elicit the user's real project.** Draft and polish text *from what the user
  tells you*; refine wording, structure and length. **Never fabricate the
  scientific or technical content of a real application** - abstracts,
  justifications, feasibility and team experience are exactly what the assessors
  evaluate, and invented content is both weak and dishonest. If the user has
  nothing yet, help them articulate it (objectives, method/protocol, why hardware
  rather than emulation, expected outcomes) rather than making it up.
- **The user reviews and approves every value** before it is submitted, makes
  every declaration themselves, and performs every account/credential/signature
  action themselves.

> Field maps are **dated snapshots** (eDARI selectors re-verified against the
> English UI Sep 2026; EuroHPC portal walked end to end Sep 2026, footer v1.7.0).
> Both portals are "in continuous evolution." Always `read_page` / screenshot the
> real page and adapt; if the live portal diverges, follow the page and, if
> unsure, explain the choice to the user instead of guessing.

## Choose the fill mode (both routes; do this before any form work)

**Offer the choice explicitly and let the user pick.**

- **Guided (default, works everywhere).** The user drives their own browser; the
  assistant instructs them field-by-field, drafts the text to paste, watches along
  if a browser is visible, and confirms each screen. Perfectly good as a primary
  flow, and the only option without browser access.
- **Automated filling (only with direct browser access).** The assistant itself
  navigates and types. **Only possible with a browser-control tool that can act on
  the page** - a browser plugin/extension, or an agent app with an integrated
  browser (e.g. Claude Desktop). In a plain terminal/CLI with no browser tool it
  is impossible - use guided.

When you present this as an AskUserQuestion, **keep the voice consistent: "you" =
the user, "I" = the assistant, in every option** (the confusing version flips -
"*I* drive my browser" then "*I* fill the forms" mean different actors). Phrase it
like: *"Guided - you drive your browser, I instruct you field-by-field"* vs
*"Automated - I navigate and type in the browser; you still do login, personal
data, all declarations and the submit."*

Rule of thumb: **if you don't already have a working browser-control tool in this
session, propose guided.** Don't spend effort wiring up browser tooling for a
one-time form - the time saved doesn't justify the setup. A **hybrid split works
well**: the assistant fills project/technical/organisation fields; the user fills
their own personal data and makes all declarations.

Both modes share the same eligibility checks, question batch, review table, field
maps and gates. Only *who moves the mouse* differs; **every gate and the
no-submit-without-approval rule apply identically in both modes.**

## Hard rules (non-negotiable, both routes)

- **Never click the final submit without explicit approval.**
  - Route FR (eDARI): **"Finish"** ("Terminer") submits the allocation; and in the
    TGCC-account tail, **"Validate the entry of information"** ("Valider la saisie
    des informations") is **not** a review page - it validates and **immediately
    emails Visa e-signature links** to the applicant, research director and
    security correspondent. Irreversible and outward-facing.
  - Route EU (EuroHPC): on the last section the primary button changes from
    **Next** to **Submit**; submitting queues the application for the next cut-off.
- **Never register a portal account and never type the user's email/password**,
  and never complete federation login. Navigate to the page and hand off.
- **Never tick a declaration/consent/eligibility box on the user's behalf** unless
  they tell you to in this session (civilian purpose, employment continuity,
  eligibility confirmations, publication consent, CGU/terms, Terms of Reference).
- **Never enter the user's personal data** (gender, title, DOB, nationality,
  phone, private address, password fragments) - hand those fields to them.
- **Never action email confirmation / e-signature links** - the user's job.
- **Never invent identifiers.** SIRET/VAT/PIC, addresses, percentages, ORCID,
  project code, connection IP, RNSR, any person's name/email: look them up from an
  authoritative source and **show them for confirmation**, or ask. Only the
  wording of the user's own science may be drafted.
- **No custom free-text software entries** where the form offers a predefined list
  (eDARI Ruby software "Add"): tick predefined checkboxes only.

## Pick the route (after the shared setup above, before Phase A)

The application route is selected by **which country the applicant's organisation
is in**. **Ask this once** - it picks the route *and* is the EuroHPC country
eligibility check, so **do not ask country again later** (Phase A / the Route EU
batch just reuse this answer):

- **France -> GENCI eDARI national route.** Portal **https://www.edari.fr**;
  Dynamic Allocation up to **100 h**; ~2-week evaluation. The **"Route FR"**
  sections below.
- **Another EU / Digital Europe Programme / Horizon Europe country -> EuroHPC
  Quantum Access Pilot.** Portal **https://access.eurohpc-ju.europa.eu**; **10-25
  QPU h**, 3 or 6 months. The **"Route EU"** sections below. This country
  requirement applies to the **PI and every team member** - confirm the team, not
  just the PI.
- **Outside that list -> neither route as-is.** Point the user to `acces@genci.fr`
  / `access@eurohpc-ju.europa.eu`; don't force a fit.

Ask the country directly; do not infer it from an email domain.

Only the **middle** branches - *which portal you apply on, the account there, the
eligibility rules and the allocation form*. Everything else is shared: the
posture/fill-mode/hard-rules above, Phase A/B below, and - after an allocation
exists - the **TGCC computing-account + onboarding tail** (both routes land on the
same machine, so both need the same TGCC account, connection IP and first-jobs
steps).

> Edge cases (don't guess): a French org needing the EuroHPC pilot's terms, or a
> non-French org wanting >25 h, are unusual. Mention the other route exists and
> point to the relevant contact (`acces@genci.fr` / `access@eurohpc-ju.europa.eu`)
> rather than forcing a fit.

## Phase A - Eligibility & prerequisites (do this FIRST, both routes)

Confirm before any form work; if one fails, say so plainly and stop rather than
help build a rejected application.

### Shared (both routes)
- **Fit.** Ruby is **analogue neutral-atom** in a 2D array - good for Ising /
  many-body physics, quench dynamics, combinatorial optimization, graph problems,
  materials/many-body simulation, analogue/graph QML. **Not** for gate-based
  circuits, error correction, Shor, or gate-based quantum chemistry. If the project
  needs those, tell the user Ruby is unsuitable before proceeding.
- **Open research.** Results must be published open access (eDARI: deposit on HAL,
  hal.science/GENCI; EuroHPC: acknowledge the JU resources). Make the user
  acknowledge this. (EuroHPC exempts only SMEs doing private innovation.)
- **Security review.** Access to CEA/TGCC can trigger an **HFDS security review**;
  some nationalities may face delays or restrictions. Flag it; don't assess it -
  it's decided by the review.
- **TGCC connection IP (hard prerequisite for the shared account tail).** Both
  routes end with a **TGCC computing account** that requires connecting from an
  **organization-managed public IP** with consistent forward/reverse DNS (see the
  IP section in the shared tail). Needs the org's IT team and an **IT security
  officer** to co-sign. Without a suitable managed IP + IT support the account
  can't be completed and the user can't use the resources - flag early. Offer the
  **early IP feasibility check** below regardless of route.

### Route FR only (eDARI)
- **Who:** European researcher in academia or an R&D company (permanent staff,
  researcher, post-doc, engineer, PhD or Master's student).
- **Companies** must additionally accept: no proprietary development, no
  confidential deliverables, no commercial valorisation of GENCI resources.
- **New vs renewal:** renewals must supply the previous allocation's **activity
  report + HAL publication ID(s)** and reuse the prior dossier (see Renewals).

### Route EU only (EuroHPC)
- **Organisation country (hard).** Already established by the route question above
  for the PI - **don't re-ask it.** Here just confirm the same requirement holds
  for **all team members** (each affiliated with an org in an EU Member State or a
  DEP / Horizon Europe associated country; the *Organization country* dropdown is
  the authoritative list). Edge case -> **access@eurohpc-ju.europa.eu**, don't guess.
- **Who may apply / free-of-charge basis.** Academia, research, public sector,
  industry - handled the same way, no peer-review panel. Free access covers
  public-sector users, **industrial users funded by Horizon Europe / Digital
  Europe**, and **SMEs doing private innovation**. A **large enterprise doing
  unfunded commercial R&D falls outside** free access (toward pay-per-use) - raise
  this explicitly with an industrial applicant; the *Organization type* answer has
  real consequences.
- **Civilian purpose only** (cybersecurity dual-use allowed) - mandatory tick.
- **Outcome report mandatory**; acknowledge resources in publications.
- **3 or 6 months, no extensions.** Only in-flight top-up: once consumed, request
  additional resources up to the initial allocation while the duration still runs.
  If the plan needs a year or >25 h, scope down or use Route FR.
- **Employment continuity** - mandatory tick that the PI's contract is valid for
  **more than 3 months after the end of the allocation**; a real blocker on a
  short contract.

### Early IP feasibility check (offer BEFORE the application, both routes)

The connection-IP/DNS requirement blocks the shared TGCC account, not the
application form - but a failing IP means the whole application is wasted effort,
so **don't defer it.** Right after the route question and eligibility, and before
starting the application:

1. **Explain the need briefly:** to actually *use* TGCC resources, the user must
   eventually connect from an **organization-managed public IP** with consistent
   forward/reverse DNS; a home/coworking/generic-VPN IP will be refused. Better to
   learn this now than after a granted allocation.
2. **Ask whether to verify it now** (go/no-go). It is purely local network
   diagnostics - needs no allocation and touches no portal form.
3. **If yes**, run the checks in the shared tail's IP section and give a verdict:
   *compliant* / *needs an IT-configured dedicated route to CEA* / *not usable
   as-is*.
4. **If no / unsure / no IT access**, proceed with the application anyway but
   **flag** that the IP must be resolved with IT before the account step. Re-run
   the check then.

This is an offer, not a gate.

## Phase B - Batch the questions, then show a review table (both routes)

Ask in as few turns as possible (AskUserQuestion for choices; prose for
free-text). Do **not** open the browser yet. Then present a **single review
table** of every value to be entered - the user's own text and any drafted
wording - flag placeholders, and **wait for explicit approval** before touching
the browser.

**Ordering rule:** elicit the user's **real science first**, then size the
**hours** (derived from the shot plan, not guessed up front). The early IP check is
the exception - it's pure network diagnostics, independent of the science.

Route FR question set: see the table under **Route FR**. Route EU question set: see
the table under **Route EU**. The shared questions in both are: the science
(objectives/method/why-hardware/outcomes), the hours (sized from shots), the codes
used, and the organisation identity.

---

# Route FR - GENCI eDARI national route (French organisations)

## FR roadmap
1. **Prepare** - Phase A/B above.
2. **eDARI account** - user logs in / registers (assistant hands off).
3. **Dynamic Allocation request** - fill the form; stop before "Finish".
4. **Evaluation** - GENCI review (~2 weeks). User then receives a project number
   (`20XX-AXXXXX` and/or `AD##########`) + hours.
5. **TGCC computing account** - the shared tail below (needs a project code first).

Step 3 grants the *allocation*; the account tail grants the *account*. Independent:
a validated allocation does not create an account; no project code -> the account
step is blocked; do 1-4 and wait.

## FR applicant sub-path (affects login + structure fields)
- **Academic / public-sector:** log in via **RENATER Identity Federation**
  (dematerialises the manager/security validations); research structure is a real
  **RNSR** lab. Sector = Publique.
- **Company / private / non-federated:** manual eDARI account; sector = **Prive**;
  structure entered manually with the company **SIRET**.

Ask which applies; don't infer sector from an email domain. If a French applicant
genuinely cannot find their RNSR lab, contact **acces@genci.fr** rather than
picking an unrelated one; never fabricate an RNSR entry.

## FR question batch

| # | Question | Ask or auto | Note |
|---|----------|-------------|------|
| 1 | Applicant sub-path (academic / company) | ask | drives login + structure fields |
| 2 | Real project: objectives, method, why quantum, outcomes | ask (free text) | source for title/abstract/justifications; do not invent |
| 3 | Thematic committee | ask (confirm) | map from the science - see committee table; recommend, user decides |
| 4 | AI used in project? | ask | changes publication-commitment wording |
| 5 | Hours + partitions | ask | max 100h QPU; request what you can justify. QAPTIVA (emulator, <=40 q) optional. **Ruby ~0.25 shots/s (~900 shots/h)** - size from total shots: Σ(sequences x sweep points x shots-per-point) / 900 + overhead |
| 6 | Storage WORKDIR/STOREDIR (TB) | ask | small default (e.g. 1/1); empty TGCC storage is rejected |
| 7 | Structure identity | look up + confirm | company: SIRET/address via registry; academic: RNSR lab |
| 8 | Research-team leader (civility/name/email) | ask | default = applicant, confirm |
| 9 | Secretariat phone | ask | office number preferred |
| 10 | Processes personal data? | ask | usually No |
| 11 | Supports (ANR/CIR/mesocentre/IA-cluster/industrial/European) | ask | usually all No |
| 12 | Code migratable to other machines? | auto | No + auto justification (QPU-specific) |
| 13 | Supporting PDF / representative publications / HAL IDs | ask | optional (new); mandatory (renewal) |
| 14 | Login handoff acknowledged | ask | user logs in themselves |

### FR committee mapping (recommend from the science; user confirms)
Read the live dropdown. English labels (Sep 2026):
- **CT6** Computer Science, Algorithms, Mathematics and Quantum -> algorithms,
  optimization, general quantum-computing methods.
- **CT5** Theoretical Physics and Plasma Physics -> quantum many-body / Ising.
- **CT9** Physics, Chemistry and Properties of Materials -> materials simulation.
- **CT8** Quantum Chemistry and Molecular Modelling -> molecular/chemistry.
- **CT10** Artificial intelligence and cross-cutting applications -> QML / data.

Pick by the project's actual topic; never default blindly.

## FR content the assistant DRAFTS (from real inputs, then user approves)
- **Title** and **publishable abstract** (>=100 chars) - from stated
  objectives/method; publishable; shown on the GENCI site.
- **Technical justification** (>=200 chars) - tie requested hours to the real plan
  (shots, geometries, sweeps); derive the count from **~0.25 shots/s (~900
  shots/h)**; note the driver is sequential (1 core), cost is on the QPU.
- **Publication objectives** (>=100 chars) - open research, HAL deposit,
  acknowledge project number; companies: no proprietary deliverables.
- **Dissemination plan** (>=100 chars) - the user's real intent (talks, notes,
  tutorials) - ask, don't assume.
- **Migration justification** - hardware-specific Pulser/myQLM stack, not
  compilable on classical CPU/GPU partitions.
- **Code names** - typically Pulser, myQLM (PulserQLMConnection), QuTiP; confirm.

## FR Step 2 - eDARI account / login (hand off)
Go to **https://www.edari.fr/user/login**. Set the interface to **English** via the
flag toggle top-right. Two blocks:
- Academic -> **"Connection via the Education-Research Federation"** (RENATER) ->
  pick institution on discovery.renater.fr -> user authenticates (account
  auto-created). (French orgs are in the federation; if not listed, use the eDARI
  block.)
- Company / non-federated -> **"Login via an eDARI account"**; if no account,
  **"Not yet registered?"** -> user completes registration and **verifies the
  email** before logging in.
Resume only after the user confirms they are logged in (home shows "Mr./Ms.
<name>, welcome to your space"). A user who tried federation *and* registered
manually may see a "merge them" duplicate-account notice - harmless.

## FR Step 3 - Dynamic Allocation request (English UI, verified Sep 2026)

Entry: logged-in home -> **"List of general actions"** (expand) -> **"Create or
renew a request for HPC, AI or quantum computing hours"** -> **"Creation of a new
dossier"** (new, not renew) -> **data-processing consent** (checkbox + "Send and
continue" - GATE, ask first).

**Nav buttons:** **"Following"** = Next, **"Previous"** = Back, **"Save and exit"**
= save draft. Submit is only **"Finish"** on the last tab. **Tab bar grows:** starts
at 4 stages (Project / Resources / Research Structure / Complement), expands to
**7** once resources are entered (adds Laboratory resources (Optional) / Project
supporters / Computer details). A draft id `TMP#####` is assigned after the first
"Following"; note it.

1. **Project** - **"Project Title"**; **"Thematic"** committee dropdown (live
   English labels); **"Use of AI in the project"** Yes/No; **"Publishable summary
   (minimum 100 characters)"**; **"I would like to submit an image ..."** = No;
   **"Will your project process personal data ..."** = No (its anonymization
   sub-question greys out); tick the **terms/CGU checkbox(es)** if present (GATE) ->
   Following.
2. **Resources** - per-machine table. Columns: **"Number of hours requested"**
   (core hours) and, per center, **"Storage space (in TB)"** with **WORKDIR** +
   **STOREDIR**. Ruby & QAPTIVA are under **TGCC**; their "Indicative valuation"
   shows **"not specified"** (keeps it Dynamic). Rows: **"Ruby Partition, Neutral
   Atom Quantum Calculator"** (the QPU), **"Qaptiva Partition, 40-Qubit ...
   Emulator"**, **"Lucy Partition, Photonic ..."** (NOT ours - leave 0). Enter Ruby
   hours (+ QAPTIVA if used); leave others 0. **Fill TGCC WORKDIR + STOREDIR** or it
   errors. A **"Need software?"** = Yes (or simply entering resources) makes the
   next "Following" reveal the software step. **Confirm** the banner "... 'Dynamic
   Access' type."
3. **Software selection** - **"Software for Qaptiva"** checkboxes **Myqlm / Pulse /
   Perceval / Jupyter**; tick what the user uses (Pulse = Pulser minimum).
   **"Software for Ruby"** has no checkboxes, only an "Add" free-text link - **leave
   empty; do NOT "Add"** -> Following.
4. **Research Structure** - RNSR lab search table (search box + "Continue with this
   structure"). Find the **RNSR** lab. Detail sub-page: **"Secretariat telephone
   number"** (required), **"Mailing address"**, **"Postal code"**, **"City"**
   (prefilled from RNSR), **"Head of the research structure"** (Civility / Name /
   First name / Email). Company: enter structure manually with the SIRET -> Following.
5. **Laboratory resources (Optional)** - **"Collaborators (name and title)"** +
   **"Team experience"** text; optional training checkboxes -> Following.
6. **Project supporters** - **"ANR Support"** / **"Mesocenter"** ("-- None --") /
   **"AI Cluster Support"** / **"Industrial support"** / **"European support"** per
   the real situation; don't "Add a new support" unless real -> Following.
7. **Computer details** - core-count radio (usually **"Sequential code, 1 processing
   core"**); **"Option to migrate ..."** Yes/No - **"No" reveals a required
   justification (Minimum 100 characters)** -> Following.
8. **Complement (final)** - **"The name of the code(s) you will use most often"**;
   **"Has the simulation code already been run intensively ...?"** Yes/No;
   **"Technical justifications (minimum 200 characters)"**; publication-objectives
   and dissemination fields (each ~100 chars, if present - read live); optional PDF
   / representative-publications / HAL deposit. Button **"Finish" = SUBMIT**. **Stop
   before Finish** unless told to submit. Submitting also requires the user to
   return the **Visa** signed by their research manager.

## FR Renewals
Use **"Create or renew a request ..."** and choose **renew** so prior fields
pre-copy. Mandatory extras: the previous allocation's **activity report** and **HAL
publication ID(s)**. Update hours/justification; otherwise the flow matches Step 3.

---

# Route EU - EuroHPC Quantum Access Pilot (non-French organisations)

Portal **https://access.eurohpc-ju.europa.eu** (footer © PRACE v1.7.0).
**English only, no toggle**; turn off browser auto-translate ("Show original").
Other systems in the same call (Euro-Q-Exa, Lucy, Piast-Q, VLQ) are out of scope -
select **RUBY** only.

## EU roadmap
1. **Prepare** - Phase A/B above.
2. **Portal account** - user registers/logs in (assistant hands off).
3. **Application** - Calls -> *EuroHPC Quantum Access Pilot Call* -> **Apply to
   Call** -> six sections -> save as draft. **Stop before Submit.**
4. **Cut-off + evaluation** - eligibility check + **technical assessment** by the
   hosting entity. **No scientific peer review.** Passing proposals are
   **automatically allocated**; access within **max 2 weeks after the cut-off**
   (indicative 10 working days). First-come-first-serve against a finite contingent
   (50% of the Union's access time), so an earlier cut-off is strictly better. A
   mandated **emulator-benchmark round may come first** (see section 4).
5. **TGCC computing account** - the shared tail below.

**Cut-offs: 1st of each month, 10:00 CET/CEST** (2026: 1 Aug/Sep/Oct/Nov/Dec). The
call card shows no "Cut-off ends in" counter, but an **open draft shows a Deadline
panel** - use that. Read the live call page for later dates.

## EU resources & sizing
Ruby in this call: **Analogue simulator, neutral atoms, 2D array, max 25 (min 10)
QPU hours**, allocation window **3 or 6 months**. Resources are stated in **QPU
hours**; no storage component in the Access Policy, though the form still has a
required **Total storage required (GB)** field - put a small honest number.

The window is narrow, so the job is justifying a number between 10 and 25:
> total shots = Σ (sequences x sweep points x shots per point)

divide by Ruby's effective shot rate (**~0.25 shots/s ~900 shots/h**, treat as an
**assumption to confirm** and **state it in the form text**), add calibration/queue
overhead. Under 10 -> ask for the 10 h minimum and say what spare capacity is for;
over 25 -> cut the sweep or use Route FR.

> The in-form dropdown's spec strings don't exactly match public material (qubit
> counts differ); prefer the in-form value and don't over-state qubit counts.

## EU question batch

| # | Question | Ask or auto | Note |
|---|---|---|---|
| 1 | User category (academia/research/public/industry) | ask | application type + free-of-charge basis. **Country already known from the route question - don't re-ask** |
| 2 | Real project: objectives, protocol, why hardware not emulation, outcomes | ask (free text) | title, abstract, scientific case, relevance-of-hardware; do not invent |
| 3 | QPU hours (10-25) and duration (3 or 6 months) | ask | size from shots; state the shot-rate assumption |
| 4 | Feasibility proof? | ask | **drives direct hardware vs mandated emulator benchmarks first** - see below |
| 5 | ERC research field + sub-field + share % | ask (recommend) | see the panel note |
| 6 | Codes used | ask | chip input; Pulser / Qoolqit etc. |
| 7 | Register/sequence details: atoms, 2D layout, duration, sweep points, shots | ask | circuit characteristics + runs/jobs + hardware characteristics |
| 8 | Hybrid classical-quantum workflow foreseen? | ask | Yes/No |
| 9 | HLST support wanted? | ask | consents to share the proposal with support staff |
| 10 | PI personal data | **user fills** | gender, title, DOB, nationality, phone, institutional email, job title |
| 11 | Organisation identity: name, type, VAT, PIC, address, % R&D in Europe, department | look up + confirm | never invent - see below |
| 12 | Contact person + team members | ask | members must also be in DEP/HE countries |
| 13 | Confidentiality: any part confidential? | ask | usually No |
| 14 | Declarations + publication consent | **user decides** | gates |

### The feasibility-proof question matters more than it looks
Section 4 opens with the call's two-track statement: (1) proposals that **should
perform emulator benchmarks** get emulator-benchmark time first and are
**re-assessed before physical hardware**; (2) a **feasibility proof demonstrating
capability to run on the quantum system** may be allocated **directly to
hardware**. Acceptable proof: emulator benchmark, theoretical analysis, or
prototype implementation. A user who already validated on an emulator should say so
with specifics - it's the difference between Ruby time now vs an emulator round
first. Highest-leverage field in the form.

### ERC research field
*Research field title* is the **ERC panel list** (PE1..PE11, then LS.. and SH..).
Choosing a panel reveals a dependent **sub-title** (e.g. PE6_1..PE6_8). Add more
with **"+ Research fields"**; shares must sum to <=100%. **No dedicated
quantum-computing panel** - analogue neutral-atom work fits **PE2** or **PE3**; PE6
fits algorithm/software-centred projects (PE6_5 cryptography, PE6_6 algorithms).
Recommend from the actual topic; don't default.

### Organisation identifiers - look up, never invent
- **Company VAT number** is required and the field **only appears once
  *Organization type* is an enterprise category**. For a company, derive from the
  national registration and **verify against VIES**
  (`https://ec.europa.eu/taxation_customs/vies/rest-api/ms/<CC>/vat/<digits>`).
  **Trap:** rate-limited VIES returns `"isValid": false` **with**
  `"userError": "MS_MAX_CONCURRENT_REQ"` - not a negative answer; wait and retry
  until `userError` is `VALID`. A genuine hit returns the registered name/address
  (a free cross-check).
- **Registered address** = current legal head office; registries are
  authoritative and head offices move - confirm with the user.
- **PIC number** optional ("if applicable") - leave blank rather than guess.
- **Percentage of R&D in Europe vs total R&D** - ask, don't estimate.

## EU content the assistant DRAFTS (from real inputs, then user approves)
- **Project title** - concise, technology-specific.
- **Project summary (abstract)** - what runs on Ruby and why.
- **Scientific case / technical problem** - main goals *and* current status
  (invite preliminary work: theory, simulations, prototypes, prior experiments).
- **Relevance of quantum hardware** - answer *why beyond emulator only* directly
  (register sizes past classical reach, hardware noise, calibration effects).
- **Circuit characteristics** - restate in analogue terms (atom count, 2D geometry,
  sequence duration, sweep points); say plainly there are no gate circuits.
- **Estimated number of runs/jobs** - sequences x sweep points x shots.
- **Specific hardware characteristics** - register geometry, interatomic spacing,
  Rabi frequency and detuning ranges, readout fidelity.
- **Code details** - per code: name+version, repository, licensing model, the
  user's connection to it, optional developer contact.
- **Development / algorithms / performance** - implementation, reusability,
  bottlenecks, solutions considered, optimisation needed, the computational
  limitation the project aims to overcome.

## EU Step 2 - Portal account (hand off)
Go to **https://access.eurohpc-ju.europa.eu**. Header: **Calls / Login / Sign Up**
when logged out; **Calls / Applications / user menu** once in. Sign Up asks First
Name*, Last Name*, **E-mail*** (organisation's official address - personal
gmail/yahoo only as secondary), Password*, Confirm Password*, **"I accept the terms
of use and privacy policy."** The user registers, accepts terms, verifies email.
Resume once they confirm login (header shows their name). Some PI fields arrive
**prefilled from the profile** - verify, don't assume blank.

## EU Step 3 - Application, section by section (verified Sep 2026)
Entry: **Calls** -> **EuroHPC Quantum Access Pilot Call** (status **Open**) ->
**Apply to Call**. Creates a real draft `DRAFT-#####` with a **Draft** badge, a
**Deadline** panel, a **Documents** link, and **Delete Application**.

Nav: **Back**, **Save Changes**, **Next** (**Submit** on the last). **Save Changes
greys out when nothing is unsaved** - that's the save confirmation. **Next
validates the current section** and marks missing required fields red with **"This
is mandatory."**

### 1. The Project
Project title*, Project summary (abstract)*, **Explain the scientific case or
technical problem*** (goals + current status incl. preliminary work), Keywords*,
**Proposal for civilian purposes*** (checkbox - **user ticks**), **Is any part
confidential?*** (Yes/No), **Research fields** (title* ERC panel -> sub-title* ->
share %*, "+ Research fields", sum <=100%), **Submission details**: Project
duration* (3/6 months), Application type* (Academic & research (scientific) /
Industrial / Public sector).

### 2. Principal Investigator
*Personal info* - **user fills**: Gender*, Title*, First name*, Last name*,
Initials, Date of birth* (picker), E-mail* (institutional), Secondary e-mail,
Nationality*, Phone (defaults +32), Job title*, **Employment contract valid >3
months after end allocation*** (checkbox - declaration), Website.
*Organization details*: Organization name*; **Organization type*** (Large
enterprise / University / Research institution / International association / NGO /
Public administration / SME / Startup / Other); **Company VAT number*** *(enterprise
types only)*; PIC (if applicable); Organization with research activity* (Yes/No);
Head office located in Europe* (Yes/No); % R&D in Europe vs total*; Department*;
Group; Address*; Postal code*; City*; **Country*** (restricted list, no type-ahead -
scroll it).

### 3. Contact Person and Team Members
Contact Person: First name*, Last name*, E-mail* (institutional). **Does the project
have Team Members?*** (Yes/No) - Yes opens rows. Every member must sit in a DEP/HE
country (declared in section 6).

### 4. Quantum Simulator/Computer Selection
Two-track intro (above). **Technical feasibility**: **Does the application have a
feasibility proof?*** (Yes/No) + **Additional comment on feasibility**. **Partition**:
**Quantum system selection*** -> pick **RUBY - 100Qubit Neutral Atom**; **Relevance
of quantum hardware***; **Code(s) used*** (chip input - see gotchas). **Computing
resources**: **Requested QPU resources (hours)*** (**10-25**); **Circuit
characteristics***; **Hybrid workflows foreseen*** (Yes/No); **Estimated number of
runs or jobs***; **Specific hardware characteristics***; **Total storage required
(GB)***. "+ Quantum Simulator/Computer partition" not needed for Ruby-only.

### 5. Code Details and Development
**Development of the code(s) description***; *Code details* (repeatable via "+ Code
details"): Name and version*, Code repositories/references*, Licensing model*,
Developer contact, **Your connection to the code***; *Scalability and performance
(if applicable)* - two optional fields; *Algorithms and use cases*: **main
algorithms and how implemented***, **is the code widely used / reusable***;
*Performance*: **bottlenecks***, **solutions considered***, **enabling/optimization
work needed***, **which computational limitation to solve***; *HLST*: **require
assistance from a HLST?*** (Yes/No) - selection consents to sharing the proposal
with HLST staff; an award doesn't guarantee this support.

### 6. Eligibility Confirmation and Data Consent - then Submit
All mandatory, all **the user's own declarations**:
- I confirm PI and Team Members are affiliated with organizations on the DEP /
  Horizon Europe countries list.*
- I confirm the information is correct/complete and complies with eligibility for
  the whole action.*
- **Data consent** (Reg. (EU) 2018/1725): if awarded, EuroHPC JU wishes to publish
  PI/team names + organisations. **I consent / I do not consent.***
- I accept the Terms of Reference.*

> **Known portal defect (Sep 2026):** the Terms of Reference link points to the
> **Extreme Scale Access** call, not the Quantum Access Pilot. Tell the user; point
> them at the Quantum Access Pilot call page and the **EuroHPC JU Access Policy
> (Version 2025.12)**. Worth reporting to access@eurohpc-ju.europa.eu.

**Submit** is the gate. Stop unless the user explicitly says to submit; then confirm
which cut-off the application is queued for.

## EU renewals / follow-ons
No extensions/renewal flow. Options: request **additional resources up to the
initial allocation** while the project runs; submit a **new application at a later
cut-off** using the first project's results + outcome report as feasibility proof;
or, for >25 h on Ruby, switch to **Route FR**.

---

# Shared tail - TGCC computing account, IP, and first jobs (both routes)

Once an allocation exists (an eDARI project code, or an EuroHPC award), the user
still needs the **actual TGCC computing account** to SSH in - this is the same
machine and the same account mechanism regardless of how the allocation was
granted.

> Distinguish two "accounts": the **portal account** to *apply* (eDARI account for
> Route FR, EuroHPC portal account for Route EU - different, covered above) vs the
> **TGCC computing account** to *log in and run* (this tail - shared).

> **Route EU note:** GENCI/CEA onboards EuroHPC awardees and may send their own
> onboarding instructions - **those take precedence if they differ.** Absent
> other instructions, the eDARI Step 5 flow below (rattachement with the granted
> project code, then the account form) is the path. Verify live rather than
> asserting; this shared tail was verified for the eDARI route.

## TGCC account - request flow (eDARI Step 5)

Only when the user **has an allocated project code**. Otherwise blocked (portal:
"You do not have a dossier allowing you to create an account-opening request").

> **Route EU users need an eDARI account first.** This TGCC-account flow lives on
> **edari.fr** and requires an eDARI login. A Route EU applicant has only a
> *EuroHPC portal* account so far, not an eDARI one - so before the rattachement
> below they must **register a manual eDARI account** (see *FR Step 2*: the
> "Login via an eDARI account" -> "Not yet registered?" path, and verify the
> confirmation email). Non-French orgs aren't in the RENATER federation, so this is
> always the manual email/password registration, not federation login. (Route FR
> users already made this account when they applied.)

> Not re-verified in the English UI in the Sep 2026 pass (no allocated code at the
> time). English labels are best-effort; **read the live page and adapt**, prefer
> the French terms in parentheses if a string doesn't match.

Extra questions to batch: project code (ask, never invent); contract type
(permanent default, else CDD/intern + end date); connection IP + FQDN (verify -
see below); **security correspondent** (the org's IT security officer - ask who;
the applicant should normally *not* list themselves); confirm the same structure
identity as the application.

### Portal flow
Reach pages via home-page links (deep links are often refused; a blank/`(non-http)`
page means the nav failed - reload via home).

**Rattachement first.** Try
**https://www.edari.fr/utilisateur/createRattachementDossier** (else Home ->
**"List of general actions"** -> **"Attach to a dossier that has obtained
resources"**). Enter the **project code** -> **"Request attachment"** ("Demander le
rattachement") (GATE). The **project owner must approve** it out-of-band before the
account form unlocks; confirm the "taken into account" banner, then wait.

**Account form.** Try **https://www.edari.fr/declarationCompte/gestion/user** (else
Home -> **"Make an account request..."** -> **"Create an account-opening
request"**). Data-processing consent (GATE), then four tabs:
1. **Center choice** - select the allocation project, tick **TGCC** -> Following.
2. **User** - contract type (permanent -> Following).
3. **Research Structure** - academic: find the RNSR lab. Company: **"I can't find
   my structure ... or I am a company"** -> company = Yes + SIRET -> structure block
   + head + attachment organisation -> Following.
4. **Connection information (TGCC)** - IP + FQDN (main fields by **"Add an IP
   address"**; see IP section); **never fill the 8-char password field**; leave the
   outgoing-flow (Git/iRODS) table and CCFR checkbox unless needed; **security
   correspondent** details; "machines under a different structure?" = No if the IP
   is the org's. Button **"Finish" = SAVE only**.

**Submit sequence (each GATED):** "Finish" saves -> request shows "not validated"
with Consult / Modify / **"Validate the entry of information"** / Delete ->
"Validate ..." **submits + emails** the Visa e-signature links (expire ~45 days,
"Relaunch" to resend). The user then actions the email confirmation + Visa
e-signatures (applicant + research manager + IT security officer). Afterwards: TGCC
security review + possible **HFDS inquiry (up to 3 months)**; credentials arrive by
email from TGCC.

### Connection IP - verify DNS + assess "organization-managed" (CRITICAL)
The declared IP must be the **public egress IP the user's CEA-bound SSH traffic
actually exits from**, and belong to the **organization's managed IT network**. CEA
whitelists this IP; the laptop's private/LAN address is irrelevant. For most
institutional/campus users the normal public IP is already compliant - just verify.
The dedicated-route workaround is an edge case for orgs whose default egress
(coworking, home, generic VPN) is unsuitable.

Verify (commands differ by OS):
1. **Public IP:** `curl -s https://api.ipify.org`.
2. **Reverse DNS (PTR):** Windows `nslookup <IP>`; macOS/Linux `dig -x <IP> +short`.
3. **Forward DNS:** `nslookup <hostname>` / `dig +short <hostname>` - must resolve
   **back to the same IP**. Read the answer, not the DNS-server line. NXDOMAIN or a
   different IP = inconsistent -> reject.
4. **Ownership:** inspect the PTR domain and `whois <IP>` if available. Coworking /
   serviced-office / residential-ISP ranges -> **not org-managed** -> refused. A
   business-ISP domain or the org's own cloud/VPN egress tied to the organisation ->
   plausibly org-managed.
5. **CEA-specific egress (if the org split-routes):** compare the path to CEA vs a
   generic host - `tracert -h 8 irene-eu.ccc.cea.fr` vs `tracert -h 8 8.8.8.8`
   (Windows) / `traceroute` (macOS/Linux). Diverging paths where the CEA path leaves
   via the org's business-ISP block (same /24 as the declared IP) is strong evidence
   CEA traffic is NATed to the dedicated IP. Definitive proof: IT confirmation or
   first successful SSH.

**Warn the user:** IP not org-managed -> the application **will be refused**, don't
submit it. No managed address at all -> the user **cannot use CEA resources** as is.
Remedy: **ask IT to configure a dedicated route to CEA** (source-NAT CEA-bound
traffic from a dedicated, DNS-consistent, org-owned IP); then re-verify (live ipify
may still show the general egress - the CEA traceroute confirms the route).

## After access - first jobs (point the user to docs; don't automate the cluster)
1. `ssh -m hmac-sha2-512 <login>@irene-eu.ccc.cea.fr` (Windows form), change
   password, accept terms, reconnect.
2. Check QPU status:
   `pcocc-rs run ccc-quantum -- python3 -c "from qlmaas.qpus import PasqalQPU;
   print(PasqalQPU().get_specs().meta_data['operational_status'])"`
3. Validate on the emulator (QAPTIVA / QutipBackend) before Ruby; submit to Ruby via
   `QPUBackend` with a small `runs=`; async jobs via `ccc_msub`, monitor `squeue
   --me`.
4. Publish open access (deposit on HAL, hal.science/GENCI, for the eDARI route) and
   **acknowledge the resources** (GENCI project number, or EuroHPC JU) in
   publications; file the outcome report (mandatory on the EuroHPC route).
5. **Use the allocation only for what the application described** - misuse is held
   against the PI in future calls.

---

## Reference
- **Route FR:** Portal https://www.edari.fr | HAL https://hal.science/GENCI/ |
  contacts acces@genci.fr, hotline.tgcc@cea.fr. Ruby via eDARI: Dynamic Allocation
  <=100 h, ~2-week evaluation.
- **Route EU:** Portal https://access.eurohpc-ju.europa.eu (© PRACE v1.7.0) | call
  page
  https://www.eurohpc-ju.europa.eu/eurohpc-ju-call-proposals-quantum-access-pilot-mode_en
  (QUANTUM ACCESS PILOT MODE, published 25 Jun 2026, Open, multiple cut-off; systems
  table is a PNG) | **EuroHPC JU Access Policy Version 2025.12** (§1.3 principles,
  §1.5-1.6 submission, §4 quantum access modes) | contact
  access@eurohpc-ju.europa.eu (eligibility edge cases). Pilot at a glance: 3/6
  months; monthly cut-offs; no extension; no storage; not peer-reviewed; technical
  assessment; indicative response 10 working days after cut-off.
- **Shared:** Ruby (Pasqal Orion): analogue neutral-atom, 100 qubits, at TGCC/CEA
  with GENCI as hosting entity. SDKs Pulser, Qoolqit; QAPTIVA emulator <=40 q. Docs
  https://docs.pasqal.com, https://www-hpc.cea.fr/tgcc-public.
- **Look up per run, never hardcode:** company head-office SIRET/VAT + address from
  the registry (annuaire-entreprises.data.gouv.fr, pappers.fr; VIES for VAT) and
  confirm; applicant identity, team leader, security correspondent, phone, project
  code and connection IP are the user's own data - ask/read-from-profile and confirm.

## Execution notes (browser automation robustness, both routes)
- Field maps are snapshots: `read_page`/screenshot the real page and adapt. The
  Browser pane may open hidden - ask the user to reveal it. `read_page` can report a
  0x0 viewport before the first screenshot; screenshot to force a render; the pane
  may reflow to a narrow layout - re-read coordinates after that.
- **Route FR:** set the UI to **English** (flag toggle) and turn off Chrome
  auto-translate ("Show original") - selectors are native English strings; a
  translation layer shifts labels and breaks input. On the TGCC-account "Connection
  information" tab, `ref_N` mapping is **unstable** and `form_input` can land in the
  wrong field (IP ended up in the outgoing-flow table) - fill main IP + FQDN by
  **clicking the field by coordinate then typing**, re-screenshot, use
  "Delete"/"supprimer" for stray rows, keep away from the password field. The phone
  widget mangles input if the field holds a value - clear first, then set a clean
  full "+NN ..." value.
- **Route EU:** single-page app - deep links (`/login`, `/calls/<id>`) may 404 or
  bounce; navigate to root and **click** through. The Calls list mixes Open and
  Closed calls with near-identical names - **match on the status badge**. Refs shift
  after every re-render - click radios **one at a time** and screenshot between;
  re-`read_page` after a dependent field appears (VAT after Organization type,
  sub-title after research panel). Batched `form_input` may be refused - fill one at
  a time (one retry on transient failure). **Don't scroll with the pointer over the
  form** - the DOB picker captures the wheel and changes the year; scroll over the
  sidebar or use `scroll_to`; Cancel an open picker rather than Escape. **"Code(s)
  used" is a chip input** - type each name and commit it (a comma made one chip
  "Pulser Qoolqit"); verify with
  `[...document.querySelectorAll('.MuiChip-label')].map(e=>e.textContent)`. Long
  dropdowns (Organization country, ERC panels) have **no type-ahead** - scroll the
  open list. The systems table on the public call page is an **image** - screenshot
  it or read the in-form dropdown.
- Confirm state at each step (eDARI `TMP#####` / EuroHPC `DRAFT-#####`; greyed *Save
  Changes*; section advanced; validation messages; "taken into account" / "validated"
  banners; rattachement pending owner approval) and report it.

## Plugin integration
Standard `name` + `description` frontmatter only, so this loads cleanly as a plugin
skill; packaging metadata belongs in `.claude-plugin/plugin.json`. This single skill
now owns **both** application routes to Ruby (eDARI national + EuroHPC pilot) plus
the shared TGCC access tail - keep its triggers distinct from toolkit skills that
build sequences or analyse results; this skill is about obtaining access, not doing
the physics.
