#!/usr/bin/env bash
# Repo health checks — run before every PR. CI runs this on every push/PR.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "── Claude Code manifest + skill validation"
if command -v claude >/dev/null 2>&1; then
  claude plugin validate .
else
  echo "  (claude CLI not found — skipping manifest validation; CI runs it)"
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

echo "── Secret scan"
if grep -rnEI "(password|token|api_key)[[:space:]]*[:=][[:space:]]*['\"][^'\"$<{]|glpat-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{20,}|BEGIN (RSA|OPENSSH) PRIVATE" skills .claude-plugin; then
  echo "✘ potential secret found"; exit 1
fi

echo "── Frontmatter sanity (argument-hint must be quoted — YAML flow-seq trap)"
if grep -rn '^argument-hint: \[' skills --include=SKILL.md; then
  echo "✘ unquoted argument-hint found (breaks YAML when two [..] groups are present)"; exit 1
fi

echo "✔ all checks passed"
