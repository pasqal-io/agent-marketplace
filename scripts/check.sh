#!/usr/bin/env bash
# Repo health checks — run before every PR. CI runs this on every push/PR.
set -euo pipefail
cd "$(dirname "$0")/.."
skipped=""   # what did not run: a local green is not CI green

echo "── Claude Code manifest + skill validation"
if command -v claude >/dev/null 2>&1; then
  claude plugin validate .
else
  echo "  (claude CLI not found — skipping manifest validation; CI runs it)"
  skipped+=" claude-plugin-validate"
fi

echo "── Manifest JSON syntax (all agent adapters)"
for f in plugin.json gemini-extension.json .claude-plugin/*.json \
         .codex-plugin/plugin.json .kimi-plugin/plugin.json \
         .agents/plugins/marketplace.json; do
  python3 -m json.tool "$f" >/dev/null || { echo "✘ invalid JSON: $f"; exit 1; }
done

echo "── Manifest, skill and portability conformance"
python3 scripts/check_manifests.py

echo "── Python syntax (templates excluded — they contain <<PLACEHOLDER>> markers)"
find skills examples -name '*.py' -not -path '*/templates/*' -print0 | xargs -0 -n1 python3 -m py_compile
find skills examples -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

echo "── Example smoke tests (the only place the physics actually runs)"
# Each example's sequence file self-tests when executed: it builds the sequence
# from its own spec and checks compute_observable against states whose value is
# known analytically. Needs Pulser, so it is skipped rather than faked when the
# environment has none — set PULSER_VENV to point at one. CI pins Pulser (see
# .github/workflows/ci.yml) because the assertions read device constants from it.
example_python="$(command -v python3)"
for candidate in "${PULSER_VENV:-}/bin/python" "$HOME/pulser-venv/bin/python"; do
  [ -x "$candidate" ] && { example_python="$candidate"; break; }
done
if "$example_python" -c "import pulser" >/dev/null 2>&1; then
  for seq in examples/*/*_sequence.py; do
    echo "   $seq"
    ( cd "$(dirname "$seq")" && "$example_python" "$(basename "$seq")" >/dev/null ) \
      || { echo "✘ example smoke test failed: $seq"; exit 1; }
  done
else
  echo "  (pulser not importable — skipping; CI installs it)"
  skipped+=" example-smoke-tests"
fi

echo "── Analytic self-tests inside the skills"
# A support script that computes something checkable against a known answer says
# so with --self-test. The readout inversion is the case that matters: it rescales
# every density it touches, and a swapped or mis-signed rate would be invisible in
# the output. Needs numpy only, so it runs wherever the examples do.
if "$example_python" -c "import numpy" >/dev/null 2>&1; then
  ( cd skills/harvest-and-analyze/support \
    && "$example_python" correct_readout.py --self-test >/dev/null ) \
    || { echo "✘ readout inversion self-test failed"; exit 1; }
  echo "   correct_readout.py: inversion recovers known densities"
else
  echo "  (numpy not importable — skipping)"
  skipped+=" readout-self-test"
fi

# The rest need neither Pulser nor numpy: labels, the job-to-scan-point mapping,
# the refusal to spend on a project nobody chose, and the noise-source
# resolution. Those are the paths a wrong edit would break silently — a batch
# submitted under the wrong project, or a scan point paired with the wrong job.
for selftest in \
  skills/qpu-submit/support/pasqal_auth.py \
  skills/qpu-submit/support/batch_tags.py \
  skills/validate-emu/support/spec_noise.py \
  skills/qpu-submit/support/submit_qpu.py ; do
  ( cd "$(dirname "$selftest")" \
    && "$example_python" "$(basename "$selftest")" --self-test >/dev/null ) \
    || { echo "✘ self-test failed: $selftest"; exit 1; }
  echo "   $(basename "$selftest"): --self-test passed"
done

echo "── Support script wiring (--help must work with no credentials, no GPU)"
# py_compile only parses. This imports each script for real and runs its argparse
# setup, which is where a missing top-level import, a duplicate flag or a bad
# default actually surfaces. --help never reaches the network, so no credentials
# are involved — and none of these scripts may require any to print usage.
if "$example_python" -c "import pulser" >/dev/null 2>&1; then
  for script in skills/*/support/*.py; do
    ( cd "$(dirname "$script")" && "$example_python" "$(basename "$script")" --help ) \
      >/dev/null 2>/tmp/support_help.err \
      || { echo "✘ $script --help failed:"; sed 's/^/    /' /tmp/support_help.err; exit 1; }
  done
  echo "  $(ls skills/*/support/*.py | wc -l | tr -d ' ') scripts importable and argparse-clean"
else
  echo "  (pulser not importable — skipping; CI installs it)"
  skipped+=" support-script-wiring"
fi

echo "── Secret scan"
# Every tracked path, not a hand-listed subset. It previously covered `skills
# examples .claude-plugin` and so never looked at .github/ (where a workflow
# secret would live), scripts/, docs/, the root manifests, or the three adapter
# manifest directories that are exact analogues of the .claude-plugin one it did
# scan. Patterns widened to the token prefixes GitHub actually issues (ghp_ is
# only one of five), AWS keys, and more key types.
#
# This scans the working tree only. History is not covered — nothing here would
# catch a credential that was committed and then removed, and this repo is
# intended to go public, where history goes with it. `git log -p` grep, or a
# dedicated scanner, is the tool for that; secret scanning with push protection
# is the real answer and is a repository setting, not a script.
secret_paths=$(git ls-files 2>/dev/null || echo ".")
if printf '%s\n' "$secret_paths" | xargs grep -nEI \
    "(password|passwd|token|api_key|apikey|secret|client_secret)[[:space:]]*[:=][[:space:]]*['\"][^'\"\$<{]{4,}|glpat-[A-Za-z0-9_-]{10,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC|DSA|PGP) PRIVATE"; then
  echo "✘ potential secret found"; exit 1
fi

echo "── Frontmatter sanity (argument-hint must be quoted — YAML flow-seq trap)"
if grep -rn '^argument-hint: \[' skills --include=SKILL.md; then
  echo "✘ unquoted argument-hint found (breaks YAML when two [..] groups are present)"; exit 1
fi

if [ -n "$skipped" ]; then
  echo "⚠ SKIPPED:$skipped — what ran passed, but this is not a full check (CI runs them)"
else
  echo "✔ all checks passed"
fi
