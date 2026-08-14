<!-- Delete any section that does not apply. -->

## What this changes, and why

## Checks

- [ ] `bash scripts/check.sh` passes (with `PULSER_VENV=<path>` so the example
      smoke tests and the support-script wiring check actually run — without it
      they are skipped, and the run still says "all checks passed")
- [ ] If this adds a gate: I broke it on purpose once and confirmed it fails

## If this touches a skill

- [ ] `name` in the frontmatter still matches the directory
- [ ] Every file the skill ships is named in its `SKILL.md`, and every path the
      `SKILL.md` cites exists
- [ ] No harness-specific variable, proprietary tool name, or absolute path
- [ ] Vendored `pasqal_auth.py` copies still byte-identical, if touched

## If this touches an example or the physics

- [ ] The sequence file self-tests and exits non-zero when a check fails
- [ ] The observable is compared against a state whose value is derivable by
      hand, not against a number a previous run printed
- [ ] The disordered floor is stated, if the observable has one
- [ ] Where the register was sized against a stand-in device rather than live
      specs, `_notes` says so

## If this changes a version

- [ ] All six manifests bumped together
- [ ] Pulser pin: still one number across CI and anything claiming a tested
      version (a bump is its own PR — the examples assert on device constants)
