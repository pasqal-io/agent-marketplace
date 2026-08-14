#!/usr/bin/env python3
"""Static conformance checks for the manifests, the skills and the shared modules.

Seven things no harness CLI checks for us:

1. The plugin version is repeated in five manifests. Nothing keeps them in
   sync, so a release bump that touches one file ships a lying manifest to the
   other four harnesses.
2. The Codex marketplace catalog (`.agents/plugins/marketplace.json`) has
   required fields and closed enums. Codex reads that path — not
   `.claude-plugin/marketplace.json`, which is only a legacy fallback — and a
   missing field means the plugin simply does not appear.
3. The root `plugin.json` follows the Agent Plugins standard, whose schema is
   *closed*: an unknown top-level key is a violation, not an extension. That
   one file is the manifest every conformant client must check, so a typo in it
   costs several harnesses at once.
4. Nothing under `skills/` may name a proprietary tool or a harness-specific
   variable. `skills/` is shared verbatim by every harness and never forked; a
   single `${CLAUDE_PLUGIN_ROOT}` or `AskUserQuestion` silently makes one skill
   Claude-only. See docs/porting-to-a-new-harness.md.
5. Modules shared between skills are vendored, one byte-identical copy per
   `support/` directory, because a skill must keep working when installed on
   its own. Nothing stops the copies from drifting, and drifting credential
   handling is how a security policy silently applies to only some scripts.
6. The dependency arrow runs one way: an example cites a skill, never the
   reverse. A skill that imported from `examples/` would break the moment a
   harness installed it alone, which is the normal case.
7. Every example is a spec + sequence pair named after its directory. The
   filenames appear in documented commands and inside the spec itself, so a
   half-finished rename leaves both pointing at nothing.

Schema references: https://agent-plugins.org/specification
                   https://developers.openai.com/codex/plugins/build
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# manifest path -> dotted path to the version string
VERSION_FIELDS = {
    "plugin.json": "version",
    ".claude-plugin/plugin.json": "version",
    ".claude-plugin/marketplace.json": "metadata.version",
    ".codex-plugin/plugin.json": "version",
    ".kimi-plugin/plugin.json": "version",
    "gemini-extension.json": "version",
}

# Agent Plugins 1.0 — the manifest every conformant client must read.
AGENT_PLUGIN_MANIFEST = "plugin.json"
AGENT_PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
AGENT_PLUGIN_FIELDS = {
    "$schema", "name", "version", "description", "author",
    "homepage", "repository", "license", "keywords", "extensions",
}

CODEX_CATALOG = ".agents/plugins/marketplace.json"
CODEX_CATEGORIES = {
    "Business & Operations",
    "Communication",
    "Creativity",
    "Data & Analytics",
    "Developer Tools",
    "Education & Research",
    "Finance",
    "Other",
    "Productivity",
    "Security",
    "Travel",
}
CODEX_INSTALLATION = {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}
CODEX_AUTHENTICATION = {"ON_INSTALL", "ON_USE"}

# Modules vendored byte-identical into every skill's support/ directory.
VENDORED_MODULES = ("pasqal_auth.py",)

# Nothing under skills/ may name one harness's tools or variables. Each entry is
# a pattern and what to write instead; the message is what a contributor reads.
HARNESS_SPECIFIC = (
    (r"\$\{?(CLAUDE|CODEX|KIMI|CURSOR|GEMINI|COPILOT)_[A-Z_]+",
     "harness-specific variable — locate files relative to the skill directory "
     "instead (Path(__file__).parent / $(dirname \"${BASH_SOURCE[0]}\"))"),
    (r"\b(AskUserQuestion|TodoWrite|WebFetch|WebSearch|NotebookEdit|SlashCommand)\b",
     "proprietary tool name — name the action instead (\"ask the user\", "
     "\"fetch the URL\"); the tool mapping belongs in the adapter manifest"),
    (r"~/\.(claude|codex|cursor|gemini)\b|\.claude/skills|\.cursor/rules",
     "path inside one harness's private directory"),
    (r"^\s*/plugin(s)? (install|marketplace)\b",
     "harness-specific install command — installation belongs in "
     "docs/harness-compatibility.md, not in a skill"),
)

# Text files worth scanning under skills/. Anything else is data or a binary.
TEXT_SUFFIXES = {".md", ".py", ".sh", ".txt", ".json", ".yaml", ".yml"}

errors: list[str] = []


def load(rel: str) -> dict:
    path = ROOT / rel
    if not path.is_file():
        errors.append(f"{rel}: missing")
        return {}
    return json.loads(path.read_text())


def dig(data: dict, dotted: str):
    for key in dotted.split("."):
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def check_versions() -> None:
    seen: dict[str, list[str]] = {}
    for rel, field in VERSION_FIELDS.items():
        version = dig(load(rel), field)
        if version is None:
            errors.append(f"{rel}: no `{field}`")
            continue
        seen.setdefault(version, []).append(rel)
    if len(seen) > 1:
        detail = "; ".join(f"{v} in {', '.join(f)}" for v, f in sorted(seen.items()))
        errors.append(f"plugin version diverges across manifests: {detail}")


def check_codex_catalog() -> None:
    catalog = load(CODEX_CATALOG)
    if not catalog:
        return
    for field in ("name", "interface.displayName"):
        if dig(catalog, field) is None:
            errors.append(f"{CODEX_CATALOG}: required `{field}` missing")

    plugins = catalog.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append(f"{CODEX_CATALOG}: `plugins` must be a non-empty list")
        return

    declared_name = load(".codex-plugin/plugin.json").get("name")
    for entry in plugins:
        label = entry.get("name", "<unnamed>")
        for field in (
            "name",
            "source.source",
            "source.path",
            "policy.installation",
            "policy.authentication",
            "category",
        ):
            if dig(entry, field) is None:
                errors.append(f"{CODEX_CATALOG}: {label}: required `{field}` missing")

        for field, allowed in (
            ("category", CODEX_CATEGORIES),
            ("policy.installation", CODEX_INSTALLATION),
            ("policy.authentication", CODEX_AUTHENTICATION),
        ):
            value = dig(entry, field)
            if value is not None and value not in allowed:
                errors.append(
                    f"{CODEX_CATALOG}: {label}: `{field}` = {value!r} "
                    f"not in {sorted(allowed)}"
                )

        path = dig(entry, "source.path")
        if path and not (ROOT / path / ".codex-plugin/plugin.json").is_file():
            errors.append(
                f"{CODEX_CATALOG}: {label}: source.path {path!r} has no "
                ".codex-plugin/plugin.json"
            )
        if declared_name and label != declared_name:
            errors.append(
                f"{CODEX_CATALOG}: catalog entry {label!r} does not match "
                f".codex-plugin/plugin.json name {declared_name!r}"
            )


def check_agent_plugin_manifest() -> None:
    """The root manifest is the one file every Agent Plugins client must read,
    and its schema is closed — an unknown top-level key is a spec violation, so
    a stray field is reported and ignored rather than honoured."""
    manifest = load(AGENT_PLUGIN_MANIFEST)
    if not manifest:
        return

    schema = manifest.get("$schema")
    if schema != AGENT_PLUGIN_SCHEMA:
        errors.append(f"{AGENT_PLUGIN_MANIFEST}: `$schema` is {schema!r}, must be "
                      f"exactly {AGENT_PLUGIN_SCHEMA!r} — clients select their "
                      "validation rules from it and reject anything else")

    unknown = sorted(set(manifest) - AGENT_PLUGIN_FIELDS)
    if unknown:
        errors.append(f"{AGENT_PLUGIN_MANIFEST}: unknown top-level field(s) "
                      f"{unknown} — the Agent Plugins schema is closed; "
                      "client-specific data goes under `extensions`")

    # Skills are discovered from skills/ by fixed convention, not declared.
    name = manifest.get("name")
    declared = load(".claude-plugin/plugin.json").get("name")
    if declared and name != declared:
        errors.append(f"{AGENT_PLUGIN_MANIFEST}: name is {name!r}, but "
                      f".claude-plugin/plugin.json says {declared!r}")


def check_skill_portability() -> None:
    """`skills/` is shared verbatim by every harness and never forked, so a
    proprietary tool name or a harness-specific variable in there quietly makes
    one skill work on one agent only."""
    for path in sorted((ROOT / "skills").rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(errors="replace")
        for pattern, why in HARNESS_SPECIFIC:
            for match in re.finditer(pattern, text, re.M):
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{path.relative_to(ROOT)}:{line}: "
                              f"{match.group(0).strip()!r} — {why}")


def check_agents_index() -> None:
    """AGENTS.md is the toolkit's index for harnesses with no skill mechanism.
    A skill missing from it is invisible to them."""
    index = ROOT / "AGENTS.md"
    if not index.is_file():
        errors.append("AGENTS.md: missing — tier-C harnesses have no other "
                      "way to learn the skills exist")
        return
    text = index.read_text()
    for skill in sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir()):
        if skill not in text:
            errors.append(f"AGENTS.md: does not mention skill {skill!r}")


def check_skill_names() -> None:
    """A skill whose frontmatter `name` differs from its directory is not
    addressable: the harness lists it under one name and resolves paths under
    the other. Renaming a skill directory without the frontmatter is the easy
    way to get there."""
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        directory = skill_md.parent.name
        fields: dict[str, str] = {}
        for line in skill_md.read_text().splitlines()[1:]:
            if line.startswith("---"):
                break
            for key in ("name", "description"):
                if line.startswith(f"{key}:"):
                    fields[key] = line.split(":", 1)[1].strip()

        declared = fields.get("name")
        if declared is None:
            errors.append(f"skills/{directory}/SKILL.md: no `name` in frontmatter")
        elif declared != directory:
            errors.append(f"skills/{directory}/SKILL.md: name is {declared!r}, "
                          f"must match the directory name {directory!r}")

        # The description is the only thing a model sees before invoking, and
        # the Agent Skills standard caps it at 500 characters.
        description = fields.get("description")
        if not description:
            errors.append(f"skills/{directory}/SKILL.md: no `description`")
        elif len(description) > 500:
            errors.append(f"skills/{directory}/SKILL.md: description is "
                          f"{len(description)} characters, limit is 500")


def check_vendored_modules() -> None:
    """Every copy of a vendored module must be byte-identical, and no support
    script may grow its own credential loader beside it."""
    for module in VENDORED_MODULES:
        copies = sorted((ROOT / "skills").glob(f"*/support/{module}"))
        if not copies:
            errors.append(f"vendored module {module} has no copies under skills/*/support/")
            continue
        by_digest: dict[str, list[str]] = {}
        for copy in copies:
            digest = hashlib.sha256(copy.read_bytes()).hexdigest()[:12]
            by_digest.setdefault(digest, []).append(
                str(copy.relative_to(ROOT)))
        if len(by_digest) > 1:
            detail = "; ".join(f"{d}: {', '.join(f)}" for d, f in sorted(by_digest.items()))
            errors.append(
                f"copies of {module} have diverged — {detail}. Copy the "
                "corrected version over the others.")

    # A second loader anywhere would apply a different policy to some scripts.
    loader = re.compile(r"^\s*def _?load_credentials\b", re.M)
    for script in sorted((ROOT / "skills").glob("*/support/*.py")):
        if script.name in VENDORED_MODULES:
            continue
        if loader.search(script.read_text()):
            errors.append(
                f"{script.relative_to(ROOT)} defines its own credential loader "
                "— import it from pasqal_auth instead")


def check_example_isolation() -> None:
    """`examples/` must never become a dependency of `skills/`.

    A skill has to keep working when a harness installs it on its own, with no
    repository around it, so an example may cite a skill but never the reverse.
    The ban is on *executable* references — an import or a script path makes the
    skill fail outright, whereas a Markdown link is documentation and degrades
    only cosmetically. `scripts/` is deliberately exempt: it is repo tooling that
    never ships to a harness, and CI has to reach the examples to run them.
    """
    dependency = re.compile(
        r"\bfrom\s+examples\b|\bimport\s+examples\b|(?:\.\./)*examples/")
    for path in sorted((ROOT / "skills").rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".sh"}:
            continue
        text = path.read_text(errors="replace")
        for match in dependency.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            errors.append(
                f"{path.relative_to(ROOT)}:{line}: reaches into examples/ — a "
                "skill installed on its own has no examples/ directory. Move "
                "what it needs into the skill, or drop the reference.")


def check_examples() -> None:
    """Each example is a spec + sequence pair the pipeline could have produced.

    The three filenames are load-bearing: every README documents commands that
    pass them to the skills by name, and `sequence_file` is how a spec finds its
    builder. A rename that updates the directory but not the spec leaves both
    silently pointing at nothing.
    """
    root = ROOT / "examples"
    if not root.is_dir():
        errors.append("examples/: missing")
        return
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        name = directory.name
        expected = {
            "README.md": "explains what the experiment is and why it is here",
            f"{name}_spec.json": "the spec, as idea-to-spec would emit it",
            f"{name}_sequence.py": "build_sequence + compute_observable",
        }
        for filename, role in expected.items():
            if not (directory / filename).is_file():
                errors.append(f"examples/{name}/: missing {filename} ({role})")

        spec_path = directory / f"{name}_spec.json"
        if not spec_path.is_file():
            continue
        try:
            spec = json.loads(spec_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"examples/{name}/{spec_path.name}: invalid JSON — {exc}")
            continue
        for field, want in (("experiment_name", name),
                            ("sequence_file", f"{name}_sequence.py"),
                            ("builder_fn", "build_sequence")):
            if spec.get(field) != want:
                errors.append(
                    f"examples/{name}/{spec_path.name}: {field} is "
                    f"{spec.get(field)!r}, expected {want!r}")


check_versions()
check_codex_catalog()
check_agent_plugin_manifest()
check_skill_names()
check_skill_portability()
check_agents_index()
check_example_isolation()
check_examples()
check_vendored_modules()

if errors:
    for err in errors:
        print(f"✘ {err}")
    sys.exit(1)
print("  versions aligned, catalogs conform, skill frontmatter valid, "
      "skills harness-neutral, AGENTS.md complete, examples self-contained, "
      "vendored modules identical")
