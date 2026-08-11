# Sharing notes — provenance and per-user requirements

These skills were extracted from an individual developer setup (June–August 2026)
and generalized for company-wide use. This file records what was changed and what
each new user must still provide.

## What each skill needs

| Skill | Requirements |
|---|---|
| `idea-to-spec` | None (internet for arXiv) |
| `spec-to-sequence` | Python + `pulser`; reference implementations bundled in `references/` |
| `validate-emu` | Pasqal Cloud account + project. Caveat: cloud EMU_MPS quality degrades / can OOM for large registers (N ≳ 60–100) |
| `noise-emulate` | Pasqal Cloud account (noise model is fetched live in all modes). Local mode: a machine with a CUDA GPU (CPU works for small N). SLURM mode (recommended): any SLURM+GPU cluster — set `PARTITION`/`GRES`/`ACCOUNT` to your site's values. Cloud mode: nothing else |
| `qpu-submit` | Pasqal Cloud project with FRESNEL_CAN1 access |
| `submit-to-cea` | A personal TGCC account under a GENCI project with Ruby hours, SSH access from a registered IP range, and an `irene` alias in `~/.ssh/config`. The skill's "Getting access" section walks new users through the full onboarding |
| `harvest-and-analyze` | Pasqal Cloud account |

## Changes made during extraction

1. **Paths**: all skill-internal references are relative to the skill's own
   directory (portable across agent harnesses); scripts locate their siblings
   relative to themselves.
2. **Python venv**: parameterized as `${PULSER_VENV:-~/pulser-venv}`.
3. **Credentials**: uniform loading everywhere — `PASQAL_USERNAME` /
   `PASQAL_PASSWORD` / `PASQAL_PROJECT_ID` env vars, then
   `~/.pasqal_credentials.json` (the local/SLURM noise-emulate runner also
   supports the OS keyring and an interactive first-run setup). No repo-specific
   credential loaders.
4. **Noise model**: emulations use the **as-shipped device noise model** fetched
   live from the SDK. No baked-in calibration overrides; individual fields can
   be overridden per run via CLI flags for sensitivity studies. Effective values
   are recorded in each run's output (`noise_params`).
5. **`submit-to-cea`**: assumes a plain `ssh irene` connection (user's own TGCC
   account, ControlMaster for password reuse) and includes a first-time-access
   guide. Remote working directory is `~/cea_deploy/`.
6. **Reference implementations** (`spec-to-sequence`): bundled in the skill's
   `references/` directory.

## What each user must provide (never shipped in this repo)

- Pasqal Cloud username, password, project ID (env vars or `~/.pasqal_credentials.json`, chmod 600).
- A Python venv with the Pulser stack (`PULSER_VENV`).
- For SLURM noise emulation: their cluster's `PARTITION`/`GRES`/`ACCOUNT` values.
- For `submit-to-cea`: their own TGCC account, GENCI allocation code (`genXXXXX`,
  from their PI), and SSH config — see the skill's "Getting access" section.

## Known caveats

- Device limits and noise parameters on the cloud change over time — the skills
  always re-query live specs via the SDK rather than assuming quoted values.
- Cloud EMU_MPS batches queue behind other users; the runners save batch IDs
  immediately and support `--resume` so nothing is lost to a dropped session.
