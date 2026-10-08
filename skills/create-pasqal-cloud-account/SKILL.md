---
name: create-pasqal-cloud-account
description: >-
  Guides a user who has decided on Pasqal Cloud through getting access to it -
  creating the account on portal.pasqal.cloud, and optionally coupling it to
  Google Cloud Marketplace so real QPUs and the advanced emulators become
  available. Relevant to requests such as "create a Pasqal Cloud account",
  "sign up for Pasqal Cloud", "I need a PASQAL_PROJECT_ID", "connect Pasqal to
  Google Cloud", "subscribe to Pasqal on GCP Marketplace", "how do I run on
  FRESNEL", or "my project only shows EMU_FREE". Concerns obtaining access
  only, not building sequences, submitting jobs, or analysing results. Not
  sure whether Pasqal Cloud or CEA/GENCI fits? Use choose-access-method first.
---

# Get access to Pasqal Cloud (account, and optional Google Cloud coupling)

Access to Pasqal Cloud comes in **two stages, and the second is optional**:

1. **A Pasqal Cloud account + project.** Free. Gives `EMU_FREE` (12 qubits) and
   Pulser Studio. Enough to exercise the entire job-creation and submission flow
   end to end without spending anything.
2. **Coupling to Google Cloud Marketplace.** Adds the real QPUs and the advanced
   emulators, billed pay-as-you-go through the user's Google Cloud account.

**The user chooses whether stage 2 happens at all, and they choose before any
project is created** - see **The gate** below. Getting the order wrong costs them
a redundant project.

## Purpose and posture

Help the user obtain **their own** access. The assistant is a guide: it finds the
starting point, hands off, and gets them back on track when they are lost. The user
owns every credential, every consent and every spend.

**Stay high-level, and stay quiet on the happy path.** The value of this skill is
knowing *where the flow starts* and *how to recover from a dead end* - not narrating
a signup form. These pages are self-explanatory and the user is reading them: a
field-by-field walkthrough of a screen they can already see is noise. So while
things are going normally, say which page to be on and what to do there, in a line
or two, and stop. Expand only when they are stuck, when a page diverges from this
map, or when something has gone wrong.

Four things are **not** page commentary and are always worth saying, briefly, at the
step that commits them:

- **Irreversible choices**, because the page does not flag them: the payments-profile
  type (Individual vs Business), a GCP project ID, a billing account's currency.
- **What it costs**, read live: the QPU rate, the tier boundary, and the fact that
  Google trial credits do not apply to Marketplace purchases.
- **Counter-intuitive states**, where the page actively misleads: `Pending` is not a
  Pasqal review queue, and a submitted order is not a subscription.
- **Hard stops**, so the user does not retry forever: a country missing from the
  onboarding list, a trial billing account refused at the final click.

Everything else - what a field is for, where a button is, what happens next on a
screen they have not reached - leave to the screen.

> Field maps are a **dated snapshot**, both stages walked in the live surfaces
> **2 Oct 2026** and re-walked **7 Oct 2026**: stage 1 end to end, stage 2 through
> Google account and billing setup, the trial upgrade, the listing, the Subscribe
> dialog and the order submission. What happens **after the Google and Pasqal
> accounts are linked** is still unverified - the link step itself was blocked by an
> embedded browser pane. Always read
> the live page (accessibility tree or screenshot) and follow it where it diverges;
> say so rather than forcing the user through a step that no longer exists.
>
> The field-level detail below is **reference for the assistant** - for recognising
> where the user is and what went wrong. It is not a script to read out.

## Choose the fill mode (before any form work)

Offer the choice and let the user pick. Keep the voice consistent - **"you" = the
user, "I" = the assistant - in every option**:

- **Guided (default, works everywhere).** You drive your own browser; I tell you
  field-by-field what to enter and confirm each screen. The only option when the
  session has no browser tool.
- **Assisted (needs a real browser, not an embedded pane).** I navigate and read
  the pages back to you; you still do every login, every consent tick, all personal
  data and anything that spends money.

If you do not already have a working browser tool in this session, propose guided.
Every gate below applies identically in both modes.

**Do not run this skill through an embedded browser pane** - Claude Desktop's
built-in browser, or any in-app webview. Verified 7 Oct 2026: Stage 2's **"Sign up
with Pasqal"** handoff opens a popup on `apis.pasqal.cloud` that such a pane
**blocks even when the user clicks it themselves**, and the popup URL cannot be
recovered or reconstructed. That is not a cosmetic limit: it is the step that binds
the Marketplace order to the Pasqal account, so the user ends up with a paid
pending order and no way to register against it. Use the user's own browser - via
a real-browser tool if the harness has one, otherwise guided - from the start,
rather than discovering this after the order is placed. If a pane is all that is
available, say so before Stage 2 and run that stage guided.

## Hard rules (non-negotiable)

- **Never create the account and never type the user's email or password.**
  Navigate to the signup form, then hand off.
- **Never tick the Terms of Service / Privacy Policy consents.** Stage 1 has
  **two separate mandatory ones** (Cloud platform and Community) plus an optional
  marketing opt-in - all three are the user's to decide.
- **Never action the email verification link for them** unless they paste it to you
  and ask. It is single-use.
- **Never enter personal data** - name, country - into the onboarding form.
- **Never touch anything that spends money.** Do not add or verify a payment
  method, do not click **Subscribe** on the Marketplace listing, do not accept the
  Marketplace terms. Stage 2 commits the user to usage-based charges on their own
  Google Cloud billing account; describe the screen and stop.
- **Never state a price from memory.** Every figure the user sees is read at
  runtime: the live `/offers` page for the gate, the live Marketplace listing for
  the subscription, and the user confirms it in the Subscribe dialog before
  confirming. The two surfaces quote **different currencies** - euros in the portal,
  USD on the listing - so they will not look identical even when they agree. The
  dated figures in this file are a staleness check for you, never a quote.

## The gate: Explorer, or pay-as-you-go via Google Cloud?

**Ask this before creating a project**, and ask it as a **two-option choice**. A
Marketplace subscription provisions its own Pasqal project, so a project created
beforehand on the free route is simply a spare.

- **Explorer - free.** Account and project, no card, nothing expires. Gives
  `EMU_FREE` (12 qubits) plus the SDK and the open-source stack. The **whole
  pipeline works on it**: write a sequence, submit a batch, watch it run, pull the
  results back - at no cost. A user who has never submitted a job should do that
  first; it catches the implementation mistakes that are otherwise discovered with
  billed QPU shots. Twelve qubits is the constraint, not the workflow.
- **Pay-as-you-go, billed through Google Cloud.** Adds the **100-qubit QPUs** and
  the **full emulator range** (beyond 12 qubits), with premium support and a
  high-priority SLA. Usage-based: emulation and QPU time are billed by the hour on
  the user's **own Google Cloud billing account**. QPU time is the expensive part.

**Put the rates in the choice, and read them live before you ask.** A free-versus-
paid question cannot be answered without knowing what paid costs, so fetch
`portal.pasqal.cloud/offers` first and quote its **Emulator Price** and **QPU
Price** for the Pay-as-you-go column in the options you present. Read the page in
the same turn you ask - do not carry figures over from a previous session, from
this file, or from memory. The portal rounds; that is fine for the gate, and the
Marketplace listing gives the binding figure to the cent later (see Stage 2). If
`/offers` cannot be reached, say the rates could not be read rather than supplying
remembered ones.

A third answer is allowed: **undecided**. The account itself is free, so Stage 1
can happen and the choice keeps.

**Read `/offers` for the rates, and nothing else.** It is the price source for the
gate, not a page to walk the user through: take the two figures, keep the choice at
two options, and open the page for them only if they ask to see it.

**Do not volunteer the other third-party routes.** `/offers` also lists Microsoft
Azure Quantum, OVH and Scaleway, each billed through that provider's own account,
and only the Google Cloud route is mapped below. Mention them if the user asks
about other providers or already uses one; otherwise keep the gate at two options.

**Do not front-load the rest of the flow.** Explain the step the user is on, not
the whole remaining path - and do not open with Stage 2's requirements either.
Google prompts for the Google account, 2FA, the card and the upgrade out of trial
at the moment each is needed, so handle them as they arrive rather than as an
entry exam.

**Academic and Premium are not self-serve**, and are not part of the gate. Both
route to `portal.pasqal.cloud/request-access`, a human sales loop. Raise Academic
only if the user is at a university and wants QPU time on credits rather than a
card - then point them there instead of walking them into Marketplace billing.

**Ask about an existing institutional grant before routing anyone to a card.** If
the user belongs to an organisation that plausibly already holds QPU entitlement -
Pasqal itself, a partner, a lab with a contract - then being added to an existing
project costs nothing, needs no billing coupling, and is one internal message.
Marketplace puts hardware time at hundreds of euros an hour on **their own**
payment method, which is the wrong instrument for work spend. Raise it once, say
why, and take their answer: if they still choose Marketplace, that is their call
and the flow below proceeds unchanged.

Then branch:

- **Free route** -> Stage 1, then **Stage 1b** (create the project).
- **Google Cloud route** -> Stage 1, **skip Stage 1b**, go to Stage 2.
- **Undecided** -> Stage 1 and stop. The account is free, nothing expires, and the
  decision keeps.

## Stage 1 - Create the Pasqal Cloud account

Walked live 2 Oct 2026. Identity is Auth0 at `authenticate.pasqal.cloud`; the portal
itself is `portal.pasqal.cloud`.

1. **`portal.pasqal.cloud`** -> **"Get started for free"** -> redirects to
   `authenticate.pasqal.cloud/u/signup`.
2. **Sign-up form.** Email, password (there is a show-password toggle), one optional
   marketing checkbox, and **two mandatory consent checkboxes** pointing at
   *different* terms - `portal.pasqal.cloud/terms` and `community.pasqal.com/terms`.
   **The user fills and submits this.** There is no Google or social sign-in here -
   the Google account in stage 2 is for **billing only**, never for login.
3. **`/verify-email`.** The page names the address it mailed and warns **"You will
   need to log in again."** Take that literally: the session does not survive
   verification.
4. **The emailed link** (`/u/email-verification?ticket=...`) -> "Email Verified" ->
   **"Back to User Portal"**. Expect a possible **MFA enrolment** prompt in this
   redirect chain; it is part of the Auth0 flow, and it is the user's to complete.
5. **`/onboard` - "One last step".** Fields: First Name, Last Name, **Country**,
   Email.
   - **Country is a searchable dropdown backed by a read-only input - it must be
     picked from the list, not typed.**
   - **The list is filtered by export-control and sanctions restrictions.** A
     missing country is a **hard stop, not a UI bug** - the account cannot be
     created from there. Say that explicitly; the failure otherwise looks like a
     broken form and the user will retype their country indefinitely.
   - Email arrives prefilled from the signup identity and **is editable**, so the
     profile address can silently diverge from the login address. Leave it alone
     unless the user wants that.
   - The user enters their own name and country and submits.
6. **`/dashboard`.** Greets them by name and shows a 0/3 checklist: create a
   project -> create a job -> check results.

Stage 1 is complete. Plus-addressed emails (`name+tag@domain`) are accepted, which
is useful when a user needs a second account for testing.

## Stage 1b - Create the project (free route only)

**Skip this entirely if the user is going the Google Cloud route** - the
subscription makes its own project.

The create-project dialog is reachable **only from the dashboard checklist**:
**Dashboard -> step 1 -> "Create your first project"**. While the project list is
empty, `/projects` itself offers **no create button** - so a user who dismisses the
checklist with "Skip" loses the obvious path. Flag that before they click Skip.

The modal has three fields: **Company**, **Project name**, **Description**
(optional). Company is per-project, not per-account. **The user submits it.**

Afterwards `/projects` lists the project with a truncated id, name, status
**Active**, its devices and a priority (**P1**). A **"Copy full UUID"** button on
the row yields the full project id. There is no project detail page and **no API-key
UI anywhere** - the SDK authenticates with the account's own username and password
plus this project id.

**A fresh free project shows `EMU_FREE` and nothing else.** The dashboard device
panel lists far more - `FRESNEL` and `FRESNEL_CAN1` (100-qubit QPUs), `EMU_SV` (25),
`EMU_MPS` (80), `EMU_FRESNEL` and `EMU_TN` (100) - but those are the *platform's*
devices, not the project's entitlements. Expect "why can I see FRESNEL but not use
it": the dashboard shows the fleet, the project row shows the grant. That gap is
exactly what stage 2 closes.

**Tell the user what this ceiling actually blocks before they stop here.**
`validate-emu`'s cloud scan (Step 2b) and `noise-emulate`'s cloud mode both
submit to `EMU_MPS`, not `EMU_FREE` - a project at this stage cannot run
either. This free project is genuinely useful: implementation checks, small
register physics, anything `EMU_FREE`'s 12 qubits cover, and the whole
pipeline end to end at that size, for nothing. What it will not do is let the
user progress to real cloud emulation at the register sizes those two skills
exist for. Say that plainly, then ask: stop here on the free project, or
continue to Stage 2 now for `EMU_MPS` access. Don't let the user discover the
ceiling only when a cloud scan fails later.

## Stage 2 - Couple to Google Cloud Marketplace

Walked as far as the order request; **what follows the account link is
unverified.** Read the live pages as you go:

- Guide: `docs.pasqal.com/third-party-cloud-providers/google-cloud-marketplace/`
- Listing: `console.cloud.google.com/marketplace/product/pasqal-public/pasqal-cloud`

**Do not front-load a prerequisites checklist.** Google asks for each of these at
the point it needs them, and walking the user through an audit first just delays
the work - verified 7 Oct 2026 on an account that had none of them. Let the flow
surface them, handle each as it arrives, and know what each one looks like so the
user is not left guessing:

- **A Google Account**, and **2FA on it**. Signing in to the console prompts for
  both. If 2FA is off, `myaccount.google.com/signinoptions/twosv` is where it goes
  on - one click when the account already has passkeys, a prompt or a phone on
  file. **The user turns it on**; the assistant does not touch security settings.
- **A billing account with a payment method.** Google Cloud offers only the **free
  trial signup** when none exists, which collects a card over two steps and
  creates the account. Country and **payments-profile type (Individual vs
  Business) are permanent**, so flag both before the user submits.
- **That billing account upgraded out of free trial.** This is the one that bites,
  because the card is already on file and it still fails: a trial account **can be
  selected in the purchase dialog's billing-account picker** and is only refused at
  the final click, with *"Action Required: Choose Different Billing Account / This
  product cannot be purchased using a billing account currently associated with a
  free trial. Please select a different billing account to proceed or upgrade to a
  paid account."* Fix it with the banner's **Upgrade**, then return to the listing.
  Trial credit is irrelevant throughout - Marketplace purchases never draw on it.
  See step 4 of the flow; it is the user's click.

No Google Cloud experience is needed, and the official guide says no pre-existing
GCP project is either. In practice **the console always has a project in context**
and the purchase URL carries both it and the billing account
(`/purchasev2/<product>;billingAccount=<id>?project=<id>`), so a project does get
involved. Do not send a user to create one they do not need - but if they have
several, ask which.

**The money follows the billing account, not the project.** A brand-new GCP project
linked to an existing billing account charges the same card; the project only
separates the line items under **Billing -> Cost breakdown**. So "use a different
project" and "charge a different account" are two different requests - ask which
one the user means before creating anything.

When a new GCP project *is* created (`console.cloud.google.com/projectcreate`):
**the project ID is permanent and cannot be changed later**, so offer the Edit
button before they submit rather than leaving them with `ninth-victor-510415-u1`
in every future billing report. **Parent resource defaults to "No organization"** -
if the user's employer has a GCP org and the spend belongs to it, that is far
easier to set now than to move afterwards.

**Do not route the user through a Google Cloud budget at all.** Verified in the
Create Budget wizard 7 Oct 2026: **Spend cap enforcement** is limited to **four
services** - Cloud Run, Cloud Run Functions, Gemini API and Vertex AI - one
project and one service per cap, and **no third-party Marketplace service is
eligible**. The other type, **Alerts only**, stops nothing by construction, and
**whether it even registers third-party Marketplace charges is unverified**. So
neither type is a safeguard worth walking a user through: skip the step. If the
user asks for one, set it up and say what it is and is not - never present it as
a limit on Pasqal spend.

**The two stages can happen in either order.** The official guide subscribes first
and creates or links the Pasqal account afterwards (its step 5 offers "Log In" for
an existing account); doing stage 1 first, as above, also works and is easier to
reason about. Pick one with the user and stay in it.

The flow, with the assistant's limits marked:

1. Open the Marketplace listing. Read back the overview, the SKUs and the terms.
2. **The user signs in to Google** and completes any security step.
3. **The user adds or verifies a payment method** under Billing -> Payment methods.
4. **When the listing refuses the billing account, the user upgrades it out of free
   trial.** The console shows a
   persistent banner - *"Free trial status: EUR N credit and M days remaining.
   Upgrade to a full account..."* - and the account's Overview page is labelled
   **Free trial account**; either is enough to tell. The fix is the banner's
   **Upgrade** button, or **Billing -> Account management -> Activate full account**.
   **The user clicks it, never the assistant**: it ends trial protection and makes
   the account liable for usage charges. Per Google's own wording the remaining
   trial credit stays usable for Google services afterwards - but not for this
   purchase, so it does not soften the decision.
   This is the right moment to pause rather than push. Upgrading removes the only
   thing standing between the user and a QPU SKU in the hundreds per hour, so
   restate the two cheaper options once - the free `EMU_FREE` project, which runs
   the whole pipeline at 12 qubits, and an existing institutional project - and take
   their answer.
5. **The user clicks Subscribe** on the listing, which opens the purchase dialog -
   plan, a **billing account selector**, and the terms. *Read it back before they
   confirm; do not click it.* The dialog's terms cover the Marketplace ToS
   **including the GPC terms in Appendix A**, Pasqal's ToS, and bundled open-source
   licences, and it states that **"most Google Cloud promotional credits don't apply
   to Google Cloud Marketplace purchases"** - worth surfacing to anyone expecting
   credits to absorb the cost.
6. **The user ticks the single mandatory consent checkbox**, which gates the
   dialog's own Subscribe button, and confirms. **Never tick it for them.** If the
   billing account is still in trial, this is where it fails - the picker accepted
   it, and only now does a blocking *"Action Required: Choose Different Billing
   Account"* dialog appear. Go back to step 4.
7. **Confirming submits an order request - it does not activate a subscription.**
   The dialog returns "Your order request has been sent to Pasqal": the
   subscription requires registration with Pasqal, and **billing starts when it
   activates, not at the click**. Say that plainly - the official guide's step 5
   implies an immediate redirect, and a user told "you're subscribed" will go
   looking for a QPU that is not there yet.
   **`Pending` is not a queue the user waits in.** Google's wording ("pending
   Pasqal approval") reads like a vendor-side review, and it is not: the order stays
   `Pending` **until the Google account is linked to a Pasqal account on the Pasqal
   platform** - that is, until the user completes the **Sign up with Pasqal**
   handoff below. Nothing moves while they wait, and there is no turnaround time to
   quote. Never tell the user to sit tight for Pasqal; tell them the link is theirs
   to complete, and that the status clears from their side. The dialog offers **Manage orders** (the pending order, i.e. the
   evidence the request exists) and **Sign up with Pasqal** (the registration
   handoff; for an existing stage-1 account this should be a log-in, and the user
   must use the **same email as their Pasqal Cloud account** or the approved
   subscription attaches to an identity they do not work from).
   After the order is placed, the listing's own primary button also becomes **Sign
   up with Pasqal**, and the Pricing section reads *"Your subscription to the
   Pay-as-you-Go plan is pending Pasqal approval"* with a **Manage Orders** link -
   so the handoff is reachable again later, and the pending state is visible on the
   listing itself.
   The order-sent dialog does not come back, but neither destination is lost.
   **Manage orders** is `console.cloud.google.com/marketplace/orders`, which shows
   nothing until a billing account is picked - and the account rides in the URL as a
   **matrix** parameter (`/orders;billingAccount=<id>`), so a `?billingAccount=<id>`
   query is silently stripped and returns the empty picker. The row to look for
   reads **Pending**, plan Pay-as-you-Go, with Start and End both `Pending` and
   payment schedule `Postpay`: that is the not-yet-linked state, and it is the honest
   answer to "am I subscribed yet". It will not change on its own.
   **This step needs a normal browser.** Verified 7 Oct 2026: it opens a **popup**
   on `apis.pasqal.cloud`, and an **embedded browser pane blocked it even on the
   user's own click**, not just on an automated one. The bare host renders blank, so
   navigating there directly is not a substitute, and the popup URL is not
   recoverable from the page. When the session's browser is a pane, stop driving and
   send the user to the listing in their own browser - or switch to a real browser
   if the harness has one. Do not loop on clicking it.
8. **Once the accounts are linked, the subscription provisions a new Pasqal
   project.** Its id is in the portal at `/projects` via "Copy full UUID".
   *Unverified - the linking step was blocked by a browser pane in the session that
   produced this map, so what the portal shows immediately afterwards is unconfirmed.*

### Reading the price off the listing

**Assistant-internal - do not narrate any of this to the user.** How the table
renders is your problem, not theirs: they are not reading the DOM, and a
commentary on blank cells and scroll regions is noise on top of the figures they
asked for. Work around it silently and report only the rates.

The listing and the purchase dialog both render the **Usage fee** SKUs as a table
whose price column belongs to the **selected row only**. An unselected SKU looks
like it has no price at all - the cell is simply blank, and the DOM contains one
price node. **Select the Quantum Hardware Time row explicitly** before quoting
anything, or you will report the emulator rate as the QPU rate. Two further traps
in the same table: the price column sits in a **horizontally scrollable** region
and is off-canvas in a narrow viewport, and the QPU SKU is **tiered**, so one
figure is never the whole answer.

Figures read 2 Oct 2026 - **re-read them live, never quote these**:

| SKU | Rate |
|---|---|
| Pay-as-you-Go Emulation Time | EUR 15.5319/hour, flat |
| Pay-as-you-Go Quantum Hardware Time, tier 1 | EUR 517.88/hour, starting after 0 hour/month |
| Pay-as-you-Go Quantum Hardware Time, tier 2 | EUR 3,106.40/hour, starting after 4 hour/month |

Priced in USD, charged in the billing account's currency at a monthly exchange rate
(1 USD = 0.88 EUR that day), billed monthly. **The tier boundary is a ~6x cliff at
4 QPU-hours per calendar month, and it resets monthly** - that, not the headline
rate, is the number a user needs to plan against. Do not convert it into "how many
shots": wall-clock per shot depends on register loading and sequence duration, and
guessing it invents a budget the user cannot check.

**Pasqal's SKUs are not in Google's first-party price list.** The listing links to
`cloud.google.com/skus`, but filtering it for `pasqal` returns "No SKUs match the
filter" - it is a third-party Marketplace SaaS listing. The listing and the purchase
dialog are the only surfaces that state the rate; do not send the user to the
Google price list for it.

**If the user already created a free project, they now have two.** Both remain
usable - keep the free one for `EMU_FREE` work, and **use the Google-Cloud-
provisioned project for anything touching a QPU or an advanced emulator.** Project
id is the thing that selects between them, so confirm which one is in play before
any submission.

**Billing hygiene, worth saying once:** charges land on the Google Cloud account,
visible under **Billing -> Cost breakdown** - after the fact, and not capped (see
above). Cancellation is in Marketplace under **Subscriptions**, and charges may only take
effect at the end of the billing cycle. Support for the Pasqal side is
`help@pasqal.com` or the portal's contact form.

## What the user has at the end

An account, and at least one **Active** project whose row lists the devices it may
use - **or, on the Google Cloud route, possibly just a pending order request.**
Those are different states, and only the first is access: say which one the user is
actually in rather than treating a submitted order as a finished job.

The project id from "Copy full UUID" is the handle everything else needs - in
this toolkit, `PASQAL_PROJECT_ID`, alongside `PASQAL_USERNAME` and
`PASQAL_PASSWORD`. Credentials live in the environment, never in the project, and
the cloud-facing skills resolve them from there - `qpu-submit` ships the auth
helper that prints which account and projects were found.

**This skill is not done until those three values are actually on the
machine that will run the pipeline - not just known.** Knowing the project id
is not the same as `--whoami` finding anything. Two ways to close that, both
the user's own action - never type a password on their behalf:

- **Export the three variables** - the reliable, scriptable path, and the
  only one that works from inside an automated or piped session:
  ```bash
  export PASQAL_USERNAME=... PASQAL_PASSWORD=... PASQAL_PROJECT_ID=...
  ```
- **Or `python <any skill>/support/pasqal_auth.py --setup`**, which prompts
  for the same three values and stores the password to the OS keyring (the
  username and project id to `~/.pasqal_credentials.json`). This one needs a
  **real interactive terminal the user is typing into themselves** - it
  reads the password with the console's own masked-input mechanism, not from
  redirected input, so it is not something to drive through an automated or
  piped session on the user's behalf.

Either way, finish by running `python <any skill>/support/pasqal_auth.py
--whoami` and showing the user that it reports their account and project back
- that confirmation, not the project UUID alone, is what "done" means here.

**Do not trust a list of entitlements from any document, including this one.** The
authoritative answer to "what can I actually run now" is the project's own device
list in the portal, or `fetch_available_devices()` on an SDK connection - which is
what Pasqal's own Marketplace guide tells the user to run rather than publishing a
fixed list.

From here the work is a different skill: `idea-to-spec` to build an experiment,
`validate-emu` to emulate it before spending anything, `qpu-submit` to run it.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Creating a project before asking about Google Cloud | Redundant project; confusion over which id to use |
| Treating a missing country as a form bug | User retries forever on a hard legal block |
| Promising QPU access on the free tier | Explorer has none; the dashboard fleet list implies otherwise |
| Letting a free-route user assume `EMU_FREE` covers cloud emulation too | It doesn't - `validate-emu`'s cloud scan and `noise-emulate`'s cloud mode need `EMU_MPS`; say so before they stop at Stage 1b, not when a scan fails |
| Expecting the session to survive email verification | The portal says to log in again - it means it |
| Hunting for an API key | There is none; auth is username + password + project id |
| Clicking Subscribe to "see the price" | It opens the purchase dialog, one consent tick away from committing the user's card |
| Recommending Pulser Studio for agent work | No-code GUI; nothing for an agent to drive |
| Quoting the one price the SKU table shows | That is the *emulator* rate; the QPU row renders blank until selected |
| Narrating the SKU table's rendering quirks to the user | They did not ask about the UI; read the figures and report the figures |
| Quoting a QPU rate without its tier | The SKU is tiered - one figure hides a ~6x cliff a few hours in |
| Sending the user to `cloud.google.com/skus` for the rate | Third-party Marketplace SKUs are not in Google's price list |
| Opening Stage 2 with a prerequisites audit | Google prompts for each one in turn; the checklist is a delay, not a safeguard |
| Treating "card on file" as the billing prerequisite | A free-trial account has a card and is still refused at the final click; it must be upgraded to paid first |
| Running Stage 2 in an embedded browser pane | The "Sign up with Pasqal" popup is blocked there even for the user, stranding a paid pending order with no registration path |
| Calling the order request a subscription | Access and billing both wait on the account link; the user hunts for a QPU that is not there |
| Reading `Pending` as a Pasqal review queue | It waits on the user linking Google to their Pasqal account - telling them to wait leaves the order stuck forever |
| Assuming a new GCP project means a new bill | Charges follow the billing account; a new project can share the old card |
| Letting the generated GCP project ID stand | It is permanent and lands in every future billing report |
| Presenting the gate without rates | Free versus paid is unanswerable without knowing what paid costs - read `/offers` first |
| Quoting the gate's rates from this file or a past session | They are a staleness check, not a price source; fetch `/offers` in the same turn you ask |
| Offering Azure Quantum, OVH or Scaleway unprompted | Four routes is a harder choice than two, and only Google Cloud is mapped here - surface them on request |
| Walking the user through a GCP budget | Spend caps exclude Marketplace entirely, and alerts stop nothing and may not even see third-party charges - the step implies protection that is not there |
| Narrating a self-explanatory page field by field | The user is looking at it; say which page and what to do, then stop |
| Explaining every remaining screen up front | Buries the step the user is actually on; give the next step, plus prerequisites that need lead time |
| Routing an institutional user to a personal card | An existing org project may already hold entitlement, for free |
| Calling the skill done once the project UUID is known | Knowing the three values isn't the same as `--whoami` finding them - confirm, don't assume |
| Running `pasqal_auth.py --setup` through an automated or piped session | Its password prompt needs a real interactive terminal the user types into; export the three variables instead in anything scripted |
