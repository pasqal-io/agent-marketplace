---
name: edari-tgcc-apply
description: >-
  Help a researcher apply for computing hours on the Pasqal Ruby (Orion)
  neutral-atom QPU at TGCC CEA through the GENCI eDARI portal (edari.fr). Coaches the
  user through their own application - checks eligibility, elicits the real
  science, drafts/polishes their text, and either guides them click-by-click
  (default) or, when it has direct browser access (browser plugin / integrated
  browser like Claude Desktop), fills the eDARI forms itself. Covers both the
  academic (RENATER federation / RNSR lab) and company (manual /
  SIRET) paths: Dynamic Allocation request, then the TGCC computing-account
  request once a project code exists - including verifying the connection IP.
  Batches questions upfront, shows a review table before touching the browser,
  and stops at every credential/consent/submit gate for explicit approval.
  Triggered by "apply for TGCC hours", "eDARI application", "request QPU computing
  hours", "apply for Ruby/Pasqal QPU allocation", "GENCI allocation", "request a
  TGCC computing account", "eDARI step 5", "attach to a project / rattachement".
---

# Apply for computing hours on the Pasqal Ruby QPU at TGCC (GENCI eDARI)

## Purpose and posture

Help a prospective user **prepare and submit their own genuine application** for
Open Access hours on the Ruby (Pasqal Orion) 100-qubit neutral-atom analog QPU,
via the eDARI portal (https://www.edari.fr). The user is the applicant; the
assistant is a **coach**, not the author of their science. Depending on the
environment the assistant either **guides the user click-by-click** (default) or
**fills the forms itself** (only when it has direct browser access - see the mode
choice below).

- **Elicit the user's real project.** Draft and polish text *from what the user
  tells you*; refine their wording, structure, and length. **Never fabricate the
  scientific content of a real application** - abstracts, justifications and team
  experience are what GENCI evaluates, and invented content is both weak and
  dishonest. If the user has nothing yet, help them articulate it (ask about
  objectives, method, why quantum, expected outcomes) rather than making it up.
- **The user reviews and approves every value** before it is submitted, and the
  user performs every account/credential/signature action themselves.

> This skill guides live web forms that GENCI describes as "in continuous
> evolution." Treat the field maps below as a **dated snapshot (guide: May
> 2026; selector strings re-verified against the English UI Sep 2026)**, not
> ground truth. Always `read_page` / screenshot the actual page and adapt; if the
> live portal diverges from this map, follow the page and, if unsure, explain the
> choice to the user instead of guessing.

> **Interface language: English.** Selectors below are the site's **native English
> UI** (set via the flag ▾ toggle top-right of the eDARI header - this triggers
> Browser's auto-translate). French labels are kept in parentheses where a page was not
> re-verified in English (notably most of Step 5).

## Choose the fill mode (do this before any form work)

Two ways to run this skill. **Offer the choice explicitly and let the user pick.**

- **Guided (default, works everywhere).** The user drives their own browser; the
  assistant instructs them field-by-field, drafts the text to paste, watches
  along if a browser is visible, and confirms each screen. This is the fallback
  whenever automated filling isn't available, and it's a perfectly good primary
  flow.
- **Automated filling (only with direct browser access).** The assistant itself
  navigates and types into the fields. **This is only possible when the assistant
  has a browser-control tool that can act on the page** - e.g. running as a
  **browser plugin/extension**, or in an **agent application with an integrated
  browser (such as Claude Desktop)**. In a plain terminal/CLI with no browser
  tool, automated filling is impossible - use guided.

Rule of thumb: **if you don't already have a working browser-control tool in this
session, propose the guided flow.** Do **not** spend effort trying to install or
wire up dedicated browser tooling just to automate this - the forms are short and
one-time, and the time saved does not justify the setup. A quick check for an
available browser tool is fine; if there isn't one, go guided.

Both modes share everything below - the same eligibility checks, question batch,
review table, field maps, values, and gates. Only *who moves the mouse* differs:
in guided mode, translate each "do X -> Following" instruction into a clear
step for the user and wait for them to report the resulting screen; in automated
mode, perform it yourself and screenshot to confirm. **Every gate and the
no-submit-without-approval rule apply identically in both modes.**

## Hard rules (non-negotiable)

- **Never submit without explicit approval.** Submit buttons: **"Finish"**
  (French "Terminer" - Step 3 allocation) and **"Validate the entry of
  information"** (French "Valider la saisie des informations" - Step 5 account;
  English label to verify live). WARNING: the Step 5 "Validate ..." button is
  **not** a review page - it **validates and immediately emails Visa e-signature
  links** to the applicant, research director and security correspondent. Treat it
  as a real, irreversible, outward-facing submission: click only on an explicit
  "submit"/"validate" from the user, and state afterwards that emails went out.
  ("Finish"/"Terminer" inside the Step 5 form only *saves*; the request shows "not
  validated" / "non validee" until Validate.)
- **Never create an eDARI account, never type the user's email/password**, never
  complete federation login. Navigate to the page and hand off.
- **Never enter passwords or password fragments** (e.g. Step 5's "les 8
  caracteres ... du mot de passe initial") - the user sets these.
- **Never action email confirmation / e-signature links** - the user's job.
- **Pause for explicit approval at every gate**: eligibility confirmation,
  data-processing consent, CGU/terms checkboxes, and before the first browser
  action that writes real data.
- **Never invent real identifiers.** Company SIRET, address, project code,
  connection IP, and any person's name/email are looked up or asked for, then
  shown for confirmation. Only wording of the user's own science may be drafted.

## Phase A - Eligibility & prerequisites (do this FIRST)

Confirm with the user before any form work; if any fails, say so plainly and
stop - do not help build an application that will be rejected.

- **Who:** European researcher in academia **or** an R&D company (permanent staff,
  researcher, post-doc, engineer, PhD or Master's student). No French
  institutional affiliation is required for quantum access.
- **Nationality / security:** access can trigger an HFDS security review; some
  nationalities may face delays or restrictions. Flag this; don't assess it
  yourself - it's decided by the security review.
- **Open research:** results **must** be published open access and deposited on
  HAL (hal.science/GENCI). **Companies** additionally must accept: no proprietary
  development, no confidential deliverables, no commercial valorisation of GENCI
  resources. Make the user explicitly acknowledge this.
- **Fit:** Ruby is analog neutral-atom - good for combinatorial optimization,
  Ising models, graph problems, materials/many-body simulation, graph QML. **Not**
  for error-corrected circuits, Shor, or gate-based quantum chemistry. If the
  project needs the latter, tell the user Ruby is unsuitable before proceeding.
- **IT / network access (hard requirement for Step 5):** the user must be able to
  connect from an **organization-managed public IP** with consistent forward/
  reverse DNS (see 5.2). This normally means access to their institution's IT
  team - e.g. to confirm the managed IP/FQDN, or to configure a dedicated route
  to CEA if the default egress (home/coworking/generic VPN) is unsuitable. Also
  needed: an **IT security officer** to co-sign the account Visa. Without a
  suitable managed IP and IT support, the account (Step 5) cannot be completed and
  the user cannot use CEA resources - flag this early, before Steps 1-3.
- **New vs renewal:** renewals must supply the previous allocation's **activity
  report + HAL publication ID(s)** and reuse the prior dossier (see Renewals).

### Early IP feasibility check (offer BEFORE Step 1, even with no allocation yet)

The connection-IP/DNS requirement (section 5.2) is technically part of **Step 5**,
but it is a **hard prerequisite likely to block a real applicant** - and a
failing IP means the whole application is wasted effort. So **do not defer it to
Step 5.** Right after the three opening questions (applicant path / new vs renewal
/ project-code-yet), and **before starting Step 1**:

1. **Explain the need briefly:** to actually *use* CEA/TGCC resources, the user
   must eventually connect from an **organization-managed public IP** with
   consistent forward/reverse DNS; a home/coworking/generic-VPN IP will be refused
   at Step 5. Better to learn this now than after a granted allocation.
2. **Ask whether they want to verify it now** (go/no-go), even though no project
   code exists yet. It is purely local network diagnostics - it needs no eDARI
   allocation and touches no portal form.
3. **If yes**, run the section 5.2 checks (public IP, reverse+forward DNS,
   ownership, optional CEA-egress traceroute) and give a verdict: *compliant* /
   *needs an IT-configured dedicated route to CEA* / *not usable as-is*.
4. **If no / unsure / no IT access**, proceed with Steps 1-3 anyway but **flag**
   that the IP must be resolved with their IT team before Step 5, so the allocation
   isn't stranded. Re-run this check at the start of Step 5.

This is an offer, not a gate - the user may decline and still build the
allocation request. The point is to surface a likely blocker early, not to force
network work up front.

## Roadmap (5 steps)

1. **Prepare** - gather materials, draft from the user's real inputs (Phase B).
2. **eDARI account** - user logs in / registers (assistant hands off).
3. **Dynamic Allocation request** - fill the form; stop before "Finish"
   ("Terminer") unless told to submit.
4. **Evaluation** - GENCI review (~2 weeks). Nothing to execute. User then
   receives a project number (`20XX-AXXXXX` and/or an `AD##########` id) + hours.
5. **Request access (TGCC computing account)** - only once a project code exists:
   rattachement + account form.

Step 3 grants the *allocation*; Step 5 grants the *account*. Independent: a
validated allocation does **not** create an account, and an account request needs
a project that already obtained resources. No project code yet -> Step 5 is
blocked; do Steps 1-3 and wait.

## Choose the applicant path (affects login + structure fields)

- **Academic / public-sector:** log in via **RENATER Identity Federation**
  (preferred - it dematerialises the manager/security validations); research
  structure is a real **RNSR** lab (search it in the portal). Sector = Publique.
- **Company / private / non-federated:** manual eDARI account; sector = **Prive**;
  structure entered manually with the company **SIRET**.

Ask the user which applies; do not infer sector from an email domain alone

> **Non-French academics (open question - flag, don't guess).** This is unresolved: advise the user to contact
> **acces@genci.fr** for the correct route (declare under a collaborating French
> lab's RNSR, or a GENCI-provided handling), rather than picking an unrelated RNSR.
> Do not fabricate an RNSR entry.

## Phase B - Batch the questions, then show a review table

Ask in as few turns as possible (AskUserQuestion for choices; prose for
free-text). Do **not** open the browser yet. Then present a **single review
table** of every value to be entered - the user's own text and any drafted
wording - flag placeholders (demo mode) and the committee choice, and **wait for
explicit approval** before touching the browser.

**Ordering rule:** elicit the user's **real science first** (objectives, method,
why quantum, outcomes - question #2). Only **after** you have that input should
you ask the **hours + partitions (#5)** and **QAPTIVA emulator** questions -
they depend on the experiment (hours are sized from the shot plan, and whether
QAPTIVA helps depends on the sequences). Do **not** bundle hours/QAPTIVA into the
same opening batch as the science ask. The **early IP feasibility check** is the
exception: keep it where it is (offered right after the three opening questions,
before Step 1), since it is pure network diagnostics independent of the science.

| # | Question | Ask or auto | Note |
|---|----------|-------------|------|
| 1 | Applicant path (academic / company) | ask | drives login + structure fields |
| 2 | Real project: objectives, method, why quantum, outcomes | ask (free text) | source for title/abstract/justifications; do not invent |
| 3 | Thematic committee | ask (confirm) | map from the science - see committee table; the assistant recommends, the user decides |
| 4 | AI used in project? | ask | changes publication-commitment wording |
| 5 | Hours + partitions | ask | max 100h QPU; request what you can justify, not reflexively 100; QAPTIVA (emulator, <=40 qubits) optional. **Ruby runs ~0.25 shots/s** (~900 shots/h) - size hours from total shots: sum over (sequences x sweep points x shots-per-point) / 900, plus overhead |
| 6 | Storage WORKDIR/STOREDIR (TB) | ask | small default (e.g. 1/1); empty TGCC storage is rejected |
| 7 | Structure identity | look up + confirm | company: SIRET/address via registry; academic: RNSR lab |
| 8 | Research-team leader (civility/name/email) | ask | default = applicant, but confirm |
| 9 | Secretariat phone | ask | office number preferred |
| 10 | Processes personal data? | ask | usually No |
| 11 | Supports (ANR/CIR/mesocentre/IA-cluster/industrial/European) | ask | usually all No |
| 12 | Code migratable to other machines? | auto | No + auto justification (QPU-specific) |
| 13 | Supporting PDF / representative publications / HAL IDs | ask | optional (new); mandatory (renewal) |
| 14 | Login handoff acknowledged | ask | user logs in themselves |

### Committee mapping (recommend from the science; user confirms)
The live eDARI committee **labels differ from older guide text** - always read the
live dropdown. English labels as seen in the live dropdown (Sep 2026):
- **CT6** Computer Science, Algorithms, Mathematics and Quantum -> algorithms,
  optimization, general quantum-computing methods.
- **CT5** Theoretical Physics and Plasma Physics -> quantum many-body / Ising
  physics.
- **CT9** Physics, Chemistry and Properties of Materials -> materials simulation.
- **CT8** Quantum Chemistry and Molecular Modelling -> molecular/chemistry.
- **CT10** Artificial intelligence and cross-cutting applications of computing ->
  QML / data.

Pick by the project's actual topic; never default to one blindly.

## Content the assistant DRAFTS (from the user's real inputs, then user approves)
- **Title** and **publishable abstract** (>=100 chars) - from the user's stated
  objectives/method; publishable (non-confidential); shown on the GENCI site.
- **Technical justification** (>=200 chars) - tie requested hours to the user's
  real plan (shots, register geometries, parameter sweeps); derive the hour count
  from Ruby's **~0.25 shots/s (~900 shots/h)** throughput so the ask is defensible;
  note the driver is sequential (1 core) and the cost is on the QPU.
- **Publication objectives** (>=100 chars) - open research, HAL deposit,
  acknowledge project number; for companies, no proprietary deliverables.
- **Dissemination plan** (>=100 chars) - the user's real intent (talks, notes,
  tutorials, hackathon) - ask, don't assume.
- **Migration justification** - hardware-specific Pulser/myQLM stack, not
  compilable on classical CPU/GPU partitions.
- **Code names** - typically Pulser, myQLM (PulserQLMConnection), QuTiP; confirm
  what the user actually uses.

## Step 2 - Account / login (hand off)
Go straight to the login page **https://www.edari.fr/user/login** (skips the
home-page "Log in or create an eDARI account" click). Set the interface to
**English** via the flag ▾ toggle if not already. The login page has two blocks:
- Academic -> **"Connection via the Education-Research Federation"** (RENATER) ->
  pick institution on discovery.renater.fr -> user authenticates (account
  auto-created). If the institution is not listed (common for non-French EU labs),
  fall back to the eDARI-account block below.
- Company / non-federated / non-listed academic -> **"Login via an eDARI
  account"**; if no account yet, **"Not yet registered?"** -> user completes
  registration and **verifies the email** eDARI sends before logging in.
Resume only after the user confirms they are logged in (home shows "Mr./Ms.
<name>, welcome to your space"). Note: a user who tried federation *and* then
registered manually may end up with duplicate accounts (home shows a "merge them"
notice) - harmless, mergeable later.

## Step 3 - Dynamic Allocation request (form map - English UI, verified Sep 2026)

Entry: logged-in home -> **"List of general actions"** (expand) -> **"Create or
renew a request for HPC, AI or quantum computing hours"** -> **"Creation of a new
dossier"** (choose *new*, not renew) -> **data-processing consent** (checkbox +
"Send and continue" - GATE, ask first).

**Nav buttons on every tab:** **"Following"** = Next, **"Previous"** = Back,
**"Save and exit"** = save draft. Submit is only **"Finish"** on the last tab.
**Tab bar grows:** it starts showing 4 stages (Project / Resources / Research
Structure / Complement) and expands to **7** once resources are entered (adds
Laboratory resources (Optional) / Project supporters / Computer details). A draft
id `TMP#####` is assigned after the first "Following"; note it and confirm.

1. **Project** - **"Project Title"**; **"Thematic"** committee dropdown (read live
   English labels - e.g. CT6); **"Use of AI in the project"** Yes/No;
   **"Publishable summary (minimum 100 characters)"**; **"I would like to submit
   an image ..."** = No; **"Will your project process personal data ..."** = No
   (its anonymization sub-question then greys out); tick the **terms/CGU
   checkbox(es)** if present (GATE, ask first) -> Following.
2. **Resources** - a per-machine table. Columns: **"Number of hours requested"**
   (core hours) and, per center on the right, **"Storage space (in TB)"** with
   **WORKDIR** + **STOREDIR** fields. Ruby & QAPTIVA are under **TGCC**; their
   "Indicative valuation" shows **"not specified"** (keeps it Dynamic). Rows:
   **"Ruby Partition, Neutral Atom Quantum Calculator"** (the QPU),
   **"Qaptiva Partition, 40-Qubit Quantum Environment and Emulator"** (emulator),
   **"Lucy Partition, Photonic ..."** (NOT ours - leave 0). Enter Ruby hours (+
   QAPTIVA if used); leave all other centers 0. **Fill TGCC WORKDIR + STOREDIR**
   or it errors ("you did not indicate WORKDIR storage space"). A **"Need
   software?"** control set to Yes (or simply entering resources) makes the next
   "Following" reveal the software step. **Confirm** the banner "Given the
   resources requested, your application will be of the 'Dynamic Access' type."
3. **Software selection** - **"Software for Qaptiva"** offers checkboxes
   **Myqlm / Pulse / Perceval / Jupyter**; tick what the user uses (Pulse =
   Pulser at minimum). **"Software for Ruby"** has **no checkboxes, only an "Add"
   free-text link - leave empty; do NOT "Add"** -> Following.
4. **Research Structure** - RNSR lab search table (search box + "Continue with
   this structure"). Academic: find the **RNSR** lab; **non-French labs are not
   listed - see the non-French-academics note above (contact acces@genci.fr)**.
   After selecting, a detail sub-page: **"Secretariat telephone number"**
   (required), **"Mailing address"**, **"Postal code"**, **"City"** (prefilled
   from RNSR), and **"Head of the research structure"** (Civility / Name / First
   name / Email address). Company path: enter structure manually with the SIRET
   (verify the live English company-entry controls) -> Following.
5. **Laboratory resources (Optional)** - **"Collaborators (name and title)"** +
   **"Team experience"** text (from the user); optional training checkboxes
   (leave unticked unless true) -> Following.
6. **Project supporters** - **"ANR Support"** Yes/No; **"Mesocenter"** dropdown
   ("-- None --"); **"AI Cluster Support"** / **"Industrial support"** /
   **"European support"** Yes/No - per the user's real situation; do not "Add a
   new support" unless real -> Following.
7. **Computer details** - **"number of computing cores"** radio (usually
   **"Sequential code, 1 processing core"**); **"Option to migrate my application
   ..."** Yes/No - **"No" reveals a required justification (Minimum 100
   characters)** -> Following.
8. **Complement (final)** - **"The name of the code(s) you will use most often"**;
   **"Has the simulation code already been run intensively ...?"** Yes/No;
   **"Technical justifications (minimum 200 characters)"**; publication-objectives
   and dissemination fields (each min ~100 chars, if present - read live); optional
   PDF ("Document submission") / representative-publications / HAL deposit. Button
   **"Finish" = SUBMIT**. **Stop before Finish** unless told to submit. Submitting
   also requires the user to return the **Visa** signed by their research manager.

## Step 5 - Request access (TGCC computing account)

Only when the user **has an allocated project code**. Otherwise blocked (portal:
"You do not have a dossier allowing you to create an account-opening request" /
"Vous n'avez pas de dossier vous permettant de creer une demande d'ouverture de
compte") - do Steps 1-3 and wait.

> Step 5 was **not re-verified in the English UI** in the Sep 2026 pass (no
> allocated project code at the time). English labels below are best-effort
> translations of the French; **read the live page and adapt**, and prefer the
> French terms in parentheses if a string doesn't match.

Extra questions to batch: project code (ask, never invent); contract type
(permanent default, else CDD/intern + end date); connection IP + FQDN (verify -
see 5.2); **security correspondent** (the org's IT security officer - ask who;
the applicant should normally *not* list themselves for a real request); confirm
the same structure identity as Step 3.

### 5.1 Portal flow
Reach pages via the home-page links (direct deep-link navigation is often
refused; a blank/`(non-http)` page means the nav failed - reload via home).

**Rattachement first.** Go straight to
**https://www.edari.fr/utilisateur/createRattachementDossier** (skips Home ->
**"List of general actions"** -> **"Attach to a dossier that has obtained
resources"** / "Se rattacher a un dossier ayant obtenu des ressources"). If that
deep link is refused (blank/`(non-http)` page), fall back to those home-page
links. Then enter the **project code** -> **"Request attachment"**
("Demander le rattachement") (GATE - ask first). The **project owner must approve**
it out-of-band before the account form unlocks; confirm the "taken into account" /
"prise en compte" banner, then wait for approval.

**Account form.** Go straight to
**https://www.edari.fr/declarationCompte/gestion/user** to start the
account-opening request (skips the home-page **"Make an account request..."** /
"Faire une demande de compte..." -> **"Create an account-opening request"** /
"Creer une demande d'ouverture de compte" clicks). If that deep link is refused
(blank/`(non-http)` page), fall back to those home-page links. Either way you
land on the data-processing consent (GATE), then four tabs:
1. **Center choice** ("Choix du centre") - select the allocation project, then
   tick **TGCC** -> Following.
2. **User** ("Utilisateur") - contract type (permanent -> just Following).
3. **Research Structure** - academic: find the RNSR lab. Company: **"I can't find
   my structure ... or I am a company"** ("Je ne trouve pas ma structure ... ou je
   suis une entreprise") -> company = Yes + SIRET -> structure block + head +
   attachment organisation -> Following.
4. **Connection information (TGCC)** ("Informations de connexion") - IP + FQDN
   (main fields by the **"Add an IP address"** / "Ajouter une adresse IP" button -
   see 5.2); **never fill the 8-char password field**; leave the outgoing-flow
   (Git/iRODS) table and CCFR checkbox unless needed; **security correspondent**
   ("Correspondant securite") details; "machines under a different structure?" =
   No if the IP is the org's. Button here **"Finish"/"Terminer" = SAVE only**.

**Submit sequence (each GATED):** "Finish"/"Terminer" saves -> request shows "not
validated" / "non validee" with Consult / Modify / **"Validate the entry of
information"** ("Valider la saisie des informations") / Delete -> "Validate ..."
**submits + emails** the Visa e-signature links (expire ~45 days, "Relaunch" /
"Relancer" to resend). The user then actions the email confirmation + Visa
e-signatures (three independent signatures for a real request: applicant +
research manager + IT security officer). Afterwards: TGCC security review +
possible **HFDS inquiry (up to 3 months)**; credentials arrive by email from TGCC.

### 5.2 Connection IP - verify DNS + assess "organization-managed" (CRITICAL)
The declared IP must be the **public egress IP the user's CEA-bound SSH traffic
actually exits from**, and belong to the **organization's managed IT network**.
CEA whitelists this IP; the laptop's private/LAN address is irrelevant.

For most **institutional/campus** users, the normal institutional public IP is
already managed and compliant - just verify it. The dedicated-route workaround
below is an **edge case** for orgs whose default egress (coworking, home, generic
cloud VPN) is not suitable.

Verify (commands differ by OS):
1. **Public IP:** `curl -s https://api.ipify.org` (all OSes).
2. **Reverse DNS (PTR):** Windows `nslookup <IP>`; macOS/Linux
   `dig -x <IP> +short` (or `nslookup <IP>`).
3. **Forward DNS:** `nslookup <hostname>` / `dig +short <hostname>` - must resolve
   **back to the same IP**. Read the answer, not the DNS-server line. NXDOMAIN or
   a different IP = inconsistent -> reject.
4. **Ownership:** inspect the PTR domain and, if available, `whois <IP>`
   (macOS/Linux; on Windows use an online whois or `Resolve-DnsName`).
   - Coworking/serviced-office domains or residential/consumer-ISP ranges -> **not
     org-managed** -> will be refused.
   - A business-ISP domain or the org's own cloud/VPN egress whose hostname ties
     to the organization or its dedicated line -> plausibly org-managed.
5. **CEA-specific egress (if the org split-routes):** compare the path to CEA vs a
   generic host - Windows `tracert -h 8 irene-eu.ccc.cea.fr` vs
   `tracert -h 8 8.8.8.8`; macOS/Linux `traceroute`. If the paths diverge and the
   CEA path leaves via the org's business-ISP block (same /24 as the declared
   IP), that's strong evidence CEA traffic is NATed to the dedicated IP while
   other traffic egresses elsewhere. Definitive proof is IT confirmation or the
   first successful SSH.

**Warn the user:**
- IP not organization-managed (coworking/home/generic VPN) -> the application
  **will be refused**; do not submit that IP.
- No managed address available at all -> the user **cannot use CEA resources** as
  is.
- Remedy: **ask IT to configure a dedicated route to CEA** so CEA-bound traffic
  egresses (via source-NAT) from a dedicated, DNS-consistent, org-owned IP while
  other traffic keeps its normal egress; then re-verify (note the live ipify IP
  may still show the *general* egress - the CEA traceroute confirms the route).

## Renewals
Use **"Create or renew a request for HPC, AI or quantum computing hours"** and
choose **renew** so prior fields pre-copy. Mandatory extras: the previous allocation's **activity report** and
**HAL publication ID(s)** from its results. Update hours/justification for the new
period; otherwise the flow matches Step 3.

## After access - first jobs (point the user to docs; don't automate the cluster)
1. `ssh -m hmac-sha2-512 <login>@irene-eu.ccc.cea.fr` (Windows form), change
   password, accept terms, reconnect.
2. Check QPU status:
   `pcocc-rs run ccc-quantum -- python3 -c "from qlmaas.qpus import PasqalQPU;
   print(PasqalQPU().get_specs().meta_data['operational_status'])"`
3. Validate on the emulator (QAPTIVA / QutipBackend) before Ruby; submit to Ruby
   via `QPUBackend` with a small `runs=`; asynchronous jobs via `ccc_msub`,
   monitor with `squeue --me`.
4. Publish open access + deposit on HAL (hal.science/GENCI), acknowledging the
   project number.

## Reference (guide PDF, May 2026 - re-verify against the live portal)
- Portal https://www.edari.fr | Docs https://docs.pasqal.com,
  https://www-hpc.cea.fr/tgcc-public | HAL https://hal.science/GENCI/ |
  Contacts acces@genci.fr, hotline.tgcc@cea.fr
- Ruby (Pasqal Orion): neutral-atom analog, 100 qubits. Dynamic Allocation only
  (<=100 h); ~2-week evaluation; SDKs Pulser, Qoolqit; QAPTIVA emulator <=40 q.

### Applicant / organization data (look up per run - never hardcode)
- Company: look up the **current head-office SIRET + address** from the French
  registry (annuaire-entreprises.data.gouv.fr, pappers.fr) by name/SIREN and
  **confirm with the user**; head offices move - verify the active establishment.
- Applicant identity, team leader, security correspondent, phone, project code and
  connection IP are the user's own data: ask/read-from-profile and confirm.

## Execution notes (browser automation robustness)
- Field map is a snapshot: `read_page`/screenshot the real page and adapt.
- The Browser pane may open hidden - ask the user to reveal it, or use their real
  Chrome for an existing federated session.
- `read_page` can report a 0x0 viewport before the first screenshot; screenshot
  to force render.
- Set the UI to **English** (flag ▾ toggle) and turn off Chrome auto-translate
  ("Show original") - the selectors above are the native English strings; a
  translation layer on top can shift labels and break input.
- On the Step 5 "Connection information" tab, `ref_N` mapping is **unstable**
  (re-renders shift refs); `form_input` values can land in the wrong field (IP
  ended up in the outgoing-flow table). Fill the main IP + FQDN by **clicking the
  field by coordinate then typing**, re-screenshot to confirm, and use the
  "Delete"/"supprimer" control to clear stray rows. Keep everything away from the
  password field.
- The phone widget mangles input if the field already holds a value; clear first,
  then set a clean full "+NN ..." value (form_input more reliable than typing).
- Confirm success at each step (dossier `TMP#####` assigned; "taken into account"/
  "prise en compte" / "validated"/"validee" banners; rattachement pending owner
  approval) and report state.

## Plugin integration
This file uses only the standard `name` + `description` frontmatter so it loads
cleanly as a plugin skill. Put packaging metadata (version, license, author,
category) in the plugin's `.claude-plugin/plugin.json`, not here. The eDARI/TGCC
access flow is a peer to any Pasqal SDK skills - keep its trigger phrases
(above) distinct from toolkit skills that run sequences or analyze results, so it
isn't invoked for on-hardware work.
