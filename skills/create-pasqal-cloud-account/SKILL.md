---
name: create-pasqal-cloud-account
description: >-
  Guides a user through getting access to Pasqal Cloud - creating the account on
  portal.pasqal.cloud, and optionally coupling it to Google Cloud Marketplace so
  real QPUs and the advanced emulators become available. Relevant to requests such
  as "create a Pasqal Cloud account", "sign up for Pasqal Cloud", "get access to
  Pasqal QPU", "I need a PASQAL_PROJECT_ID", "connect Pasqal to Google Cloud",
  "subscribe to Pasqal on GCP Marketplace", "pay-as-you-go QPU access", "how do I
  run on FRESNEL", or "my project only shows EMU_FREE". Concerns obtaining access
  only, not building sequences, submitting jobs, or analysing results.
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

Help the user obtain **their own** access. The assistant is a guide: it navigates,
reads the live page back, names the next field and explains what each screen
commits them to. The user owns every credential, every consent and every spend.

> Field maps are a **dated snapshot**: stage 1 walked end to end in the live portal
> **2 Oct 2026**; stage 2 from the Pasqal documentation and the Marketplace listing
> as read the same day, **not** walked through a real subscription. Always read the
> live page (accessibility tree or screenshot) and follow it where it diverges; say
> so rather than forcing the user through a step that no longer exists.

## Choose the fill mode (before any form work)

Offer the choice and let the user pick. Keep the voice consistent - **"you" = the
user, "I" = the assistant - in every option**:

- **Guided (default, works everywhere).** You drive your own browser; I tell you
  field-by-field what to enter and confirm each screen. The only option when the
  session has no browser tool.
- **Assisted (only with direct browser access).** I navigate and read the pages
  back to you; you still do every login, every consent tick, all personal data and
  anything that spends money.

If you do not already have a working browser tool in this session, propose guided.
Every gate below applies identically in both modes.

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
- **Never state a price from memory.** Quote the live `/offers` page and the live
  Marketplace listing, and have the user confirm the figures in the Subscribe
  dialog before confirming. The two surfaces quote **different currencies** -
  euros in the portal, USD on the listing - so they will not look identical even
  when they agree.

## The gate: free, or coupled to Google Cloud?

**Ask this before creating a project.** A Marketplace subscription provisions its
own Pasqal project, so a project created beforehand on the free route is simply a
spare.

Present the trade-off from the live `/offers` page. The part that decides it:

| | Explorer (free) | Pay-as-you-go (via Google Cloud) |
|---|---|---|
| QPU access | **No** | Yes, 100-qubit |
| Emulators | Restricted - `EMU_FREE`, 12 qubits | Full range |
| Support / SLA | Community, none | Premium, high |
| Cost | Free | Usage-based; emulation and QPU time billed per hour |

Both routes include the Pasqal Cloud SDK, Pulser Studio and the open-source stack.

**Say plainly what the free route is good for:** the whole pipeline - writing a
sequence, submitting a batch, watching it run, pulling results back - works on
`EMU_FREE` at no cost. A user who has never submitted a job should do that first;
it catches the implementation mistakes that are otherwise discovered with billed
QPU shots. Twelve qubits is the constraint, not the workflow.

**Also mention, once:** Pulser Studio (`pulserstudio.pasqal.cloud`) is a no-code
drag-and-drop interface. It is fine for a human exploring by hand, but it is **not
usable in an agent-driven flow** - there is nothing to script. For anything this
toolkit does, the SDK is the path.

**Academic and Premium are not self-serve.** Both route to
`portal.pasqal.cloud/request-access`, a human sales loop. If the user is at a
university and wants QPU time on credits rather than a card, point them there
instead of walking them into Marketplace billing.

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

## Stage 2 - Couple to Google Cloud Marketplace

From the Pasqal documentation and the Marketplace listing, read 2 Oct 2026; **not
verified by a real subscription.** Read the live pages as you go:

- Guide: `docs.pasqal.com/third-party-cloud-providers/google-cloud-marketplace/`
- Listing: `console.cloud.google.com/marketplace/product/pasqal-public/pasqal-cloud`

**Prerequisites - check all three before starting**, because the subscription stalls
at whichever is missing:

- A Google Account.
- **2FA enabled on it.** Google Cloud requires it for third-party integrations; the
  user will be forced through enrolment mid-flow otherwise.
- **A valid payment method on a Google Cloud Billing account.** This is the
  pay-as-you-go requirement and the real commitment.

No pre-existing GCP project or Google Cloud experience is needed. (The official
guide also says to ensure billing is "linked to the project where you'll deploy",
which contradicts that - Pasqal Cloud is a SaaS listing with nothing to deploy. If
the user has no GCP project, do not send them to create one.)

**The two stages can happen in either order.** The official guide subscribes first
and creates or links the Pasqal account afterwards (its step 5 offers "Log In" for
an existing account); doing stage 1 first, as above, also works and is easier to
reason about. Pick one with the user and stay in it.

The flow, with the assistant's limits marked:

1. Open the Marketplace listing. Read back the overview, the SKUs and the terms.
2. **The user signs in to Google** and completes any security step.
3. **The user adds or verifies a payment method** under Billing -> Payment methods.
4. **The user clicks Subscribe**, reviews the dialog, accepts the Google Cloud
   Marketplace terms and Pasqal's terms, and confirms. *Read the dialog back to
   them before they confirm; do not click it.*
5. **The user is redirected to create or link the Pasqal account.** If stage 1 is
   already done, this is a log-in, not a sign-up.
6. **The subscription provisions a new Pasqal project.** Its id is in the portal
   at `/projects` via "Copy full UUID".

**If the user already created a free project, they now have two.** Both remain
usable - keep the free one for `EMU_FREE` work, and **use the Google-Cloud-
provisioned project for anything touching a QPU or an advanced emulator.** Project
id is the thing that selects between them, so confirm which one is in play before
any submission.

**Billing hygiene, worth saying once:** charges land on the Google Cloud account,
visible under **Billing -> Cost breakdown**, where budgets and alerts can be set.
Cancellation is in Marketplace under **Subscriptions**, and charges may only take
effect at the end of the billing cycle. Support for the Pasqal side is
`help@pasqal.com` or the portal's contact form.

## What the user has at the end

An account, and at least one **Active** project whose row lists the devices it may
use. The project id from "Copy full UUID" is the handle everything else needs - in
this toolkit, `PASQAL_PROJECT_ID`, alongside `PASQAL_USERNAME` and
`PASQAL_PASSWORD`. Credentials live in the environment, never in the project, and
the cloud-facing skills resolve them from there - `qpu-submit` ships the auth
helper that prints which account and projects were found.

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
| Expecting the session to survive email verification | The portal says to log in again - it means it |
| Hunting for an API key | There is none; auth is username + password + project id |
| Clicking Subscribe to "see the price" | That is the commitment step, on the user's card |
| Recommending Pulser Studio for agent work | No-code GUI; nothing for an agent to drive |
