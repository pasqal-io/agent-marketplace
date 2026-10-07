---
name: choose-access-method
description: >-
  Helps a user who does not yet have QPU access decide which route to pursue -
  free CEA/GENCI/EuroHPC access to Ruby (weeks of lead time, specific
  eligibility) versus Pasqal Cloud pay-as-you-go (available today, any
  country, a card). Relevant to requests such as "how do I get QPU access",
  "which account should I use", "Pasqal Cloud vs CEA", "do I qualify for free
  QPU time", "I don't have an account yet and don't know where to start", or
  "what's the fastest way to run on real hardware". Once the route is decided,
  hand off by name to create-pasqal-cloud-account or apply-genci-tgcc-cea -
  this skill is for the decision itself, not either account-creation flow.
---

# Choose a QPU access route

Two independent routes exist to get a Pasqal-Cloud-or-Ruby-capable account,
and neither skill that creates one knows the other exists. This skill is the
one place that compares them and sends the user to the right one.

**Scope: the decision only.** Once the user knows which route they want, stop
here and hand off:

- Pasqal Cloud -> `create-pasqal-cloud-account`
- CEA/GENCI/EuroHPC (Ruby) -> `apply-genci-tgcc-cea`

This skill does not create accounts, fill forms, or touch either portal.

## Ask these, in order

1. **Does the user already know which they want?** If so, skip straight to
   the hand-off above - don't make someone who has already decided sit
   through a comparison.
2. **Organisation country.** Drives eligibility for the free route entirely;
   ask directly, don't infer it from an email domain or name.
3. **Organisation type.** Academia/research, public sector, industry
   (funded vs unfunded), or none of those (personal/hobby project).
4. **How soon does real hardware time matter?** The free route's lead time
   (below) is the deciding factor as often as eligibility is.

## The two routes, compared

| | Free (CEA/GENCI/EuroHPC, via Ruby) | Pasqal Cloud pay-as-you-go |
|---|---|---|
| Cost | Free | QPU hours cost several thousand euros/hour past a small monthly tier |
| Who qualifies | **EU / DEP / Horizon-Europe countries**: academia, public sector, and industry when doing open research; a large enterprise doing *unfunded* commercial R&D does not qualify | Anyone, any country |
| Lead time | **Weeks** - Monthly application windows, plus a technical assessment, then up to ~2 weeks to access | Available today - account creation plus a Google Cloud account, typically same day |
| Hours granted | **French Users**: up to 100 h. **Other**: 10-25 h with subsequent reassessment | Metered, no pre-set allocation - billed as used |
| Device | Ruby (Orion), 100-qubit analogue neutral-atom, at TGCC | FRESNEL / FRESNEL_CAN1 (100-qubit QPUs) plus the advanced cloud emulators |
| Hard requirement besides eligibility | An **organisation-managed public IP** with consistent DNS, for the eventual TGCC SSH connection - needs IT support | A Google Cloud billing account with a payment method |


## Recommendation logic

1. **Already knows the route** -> hand off immediately, no comparison.
2. **Eligible for the free route, and weeks of lead time is acceptable** ->
   recommend starting that application now (`apply-genci-tgcc-cea`), in
   parallel with a free Pasqal Cloud Explorer account for immediate
   development (`create-pasqal-cloud-account`, Explorer only - no need to
   decide on Google Cloud coupling at this point).
3. **Eligible for the free route, but wants hardware access today, or won't
   invest the application effort** -> Pasqal Cloud pay-as-you-go
   (`create-pasqal-cloud-account`).
4. **Not eligible for the free route (country or org type)** -> Pasqal Cloud
   pay-as-you-go (`create-pasqal-cloud-account`); mention the GENCI/EuroHPC
   contacts above only if the user wants to double-check an edge case.
5. **Unsure, or genuinely undecided** -> lay out the comparison table above
   and let the user pick; don't default silently.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Treating "free for academics" as the whole eligibility story | EuroHPC also covers public sector and funded industry/SMEs - a non-academic user may still qualify |
| Recommending the free route to someone who needs hardware this week | The lead time (weeks) is as disqualifying as ineligibility would be - ask about urgency before eligibility |
| Skipping the country/org-type question and guessing from an email domain | Eligibility is organisation-based, not inferable - always ask |
| Forgetting the IP/DNS requirement when recommending the free route | A user without a suitable organisation-managed IP cannot complete the TGCC account even after a successful application - `apply-genci-tgcc-cea`'s early IP check exists for exactly this |

## Reference

- Pasqal Cloud: `create-pasqal-cloud-account` (this toolkit).
- CEA/GENCI/EuroHPC: `apply-genci-tgcc-cea` (this toolkit).
