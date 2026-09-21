# Security

## Reporting a vulnerability

Use **Security → Report a vulnerability** on this repository. That opens a
private advisory visible only to the maintainers; please do not open a public
issue for anything exploitable.

Include a description and, if you have one, a minimal reproduction. If the report
concerns a credential that leaked through this repository, say so in the title —
that is handled as an incident, not as a bug report.

## What this toolkit does with your credentials

Every cloud-facing script resolves credentials through one vendored module,
`support/pasqal_auth.py`, which reads each field independently from:

1. the environment — `PASQAL_USERNAME`, `PASQAL_PASSWORD`, `PASQAL_PROJECT_ID`
2. the system keyring (password only, OS-encrypted, needs `pip install keyring`)
3. `~/.pasqal_credentials.json`, which must be `chmod 600`

A password in that file is stored in plaintext, and the scripts say so where
they offer to write it. Prefer the keyring.

Credentials are never written to any file this toolkit produces, never printed,
and never passed on a command line where they would land in your shell history
or in `ps` output. CI rejects a second credential loader anywhere under
`skills/`, so this policy cannot apply to only some scripts.

`submit-to-cea` never handles your cluster password: authentication is
interactive and yours to perform. One exception to the loader rule is documented
in the code — `submit-to-cea/templates/submit_template.py` runs inside a
container on a compute node where no keyring exists, so it reads environment
variables only.

## What runs on your machine, and what it spends

These are agent skills: a model reads them and runs the bundled scripts on your
behalf. Two of them spend real resources.

- **`qpu-submit`** consumes QPU shots on a Pasqal Cloud project. Two things are
  enforced in the script rather than asked of the model. It prints the full
  submission plan — device, scan, batches, shots per batch, calibration cost,
  total — and exits non-zero unless it receives `--confirm` or a `y` typed at a
  terminal; the plan is built and shown before any credential is read or the
  cloud is contacted. And it refuses to submit into an output directory that
  already records batch IDs, because a re-run would buy the same shots twice and
  destroy the record of the first submission. `validate-emu` resumes from that
  record with `--resume` instead of resubmitting.

  **There is still no spending cap.** Nothing limits how large a plan you can
  approve, and `--confirm` carries whatever agreement you gave — so read the
  shot count in the plan, and treat a changed device, scan or shot count as
  needing a fresh look rather than a re-used flag.
- **`submit-to-cea`** consumes allocation hours on a cluster you have access to.
  Launching there is not idempotent either, and nothing on the cluster prevents a
  duplicate; the skill checks the queue first, but that check is an instruction,
  not code.

Emulation always precedes a QPU recommendation. QPU submission is never part of
CI.

## Treating papers and downloaded files as data

`idea-to-spec` reads papers, patents and notes that you point it at. Text
fetched from outside the repository is **data, not instructions** — a PDF that
contains something shaped like a command is still just a PDF. If you review one
thing in a generated spec, review `_notes`, which is where the skill records
what it could not verify.

## Reporting scope

In scope: credential handling, anything that could exfiltrate secrets or
experiment data, and command injection through a spec or sequence file.

Out of scope: the physics being wrong. That is a correctness bug — open a normal
issue. The examples' smoke tests are the first place to look.
