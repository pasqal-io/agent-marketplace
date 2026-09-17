#!/usr/bin/env python3
"""Static conformance checks for the manifests, the skills and the shared modules.

Eleven things no harness CLI checks for us:

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
8. A SKILL.md and the files it ships describe each other exactly, in both
   directions. Nothing else indexes `support/` or `templates/`, so a cited file
   that is absent sends the model to run something that is not there, and a
   shipped file nobody names is invisible and unmaintained.
9. Relative Markdown links resolve. The docs cross-reference each other
   heavily and a broken link renders fine on GitHub — it only fails on click.
10. The tested Pulser version is one number. CI installs exactly one, the
   examples assert on device constants that version ships, and any file
   claiming to state a tested version has to name the same one.
11. Skill directories stay kebab-case and one level deep. Harnesses that
   discover Agent Skills from a scanned directory — OpenCode, DeepSeek
   Harness — match `<name>/SKILL.md` exactly and do not recurse. A nested or
   oddly-named skill is not rejected there, it is silently absent.

Schema references: https://agent-plugins.org/specification
                   https://developers.openai.com/codex/plugins/build
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
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
VENDORED_MODULES = ("pasqal_auth.py", "spec_noise.py", "batch_tags.py")

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

# The Pulser version the toolkit is tested against is stated in prose in several
# places that no tool keeps in sync. Each entry is a file and a pattern whose
# first group is the version; they must all agree.
PULSER_PIN_SOURCES = (
    (".github/workflows/ci.yml", r'pip install "pulser==([0-9.]+)"'),
    ("skills/noise-emulate/SKILL.md", r"CI pins pulser ([0-9.]+)"),
)

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


def check_skill_layout() -> None:
    """`skills/<kebab-case-name>/SKILL.md`, and nothing deeper.

    Harnesses that install this repo as a plugin are told where the skills are.
    The ones that discover them from a scanned directory are not: OpenCode and
    DeepSeek Harness list the entries of a root and accept `<name>/SKILL.md` or
    a flat `<name>.md`, with no recursion and a kebab-case name pattern. Both
    failure modes there are silent — a skill one directory too deep, or named
    with an underscore, is simply not in the catalog, with nothing logged.
    """
    kebab = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    root = ROOT / "skills"
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        if not kebab.match(directory.name):
            errors.append(
                f"skills/{directory.name}/: not kebab-case — a scanned-directory "
                "harness matches ^[a-z0-9]+(?:-[a-z0-9]+)*$ and skips the rest")
        if not (directory / "SKILL.md").is_file():
            errors.append(f"skills/{directory.name}/: no SKILL.md at its root")

    for skill_md in sorted(root.rglob("SKILL.md")):
        depth = len(skill_md.relative_to(root).parts)
        if depth != 2:
            errors.append(
                f"{skill_md.relative_to(ROOT)}: nested {depth} levels under "
                "skills/, must be exactly skills/<name>/SKILL.md — discovery is "
                "not recursive, so this file is invisible rather than an error")


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
    loader = re.compile(r"^\s*def _?(?:load|ensure)_credentials\b", re.M)
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


def check_skill_references() -> None:
    """A SKILL.md and the files it ships must describe each other exactly.

    Both directions fail silently in their own way. A cited path that does not
    exist sends the model to run a script that is not there — the failure the
    audit found, and the reason it is checked mechanically now. A bundled file
    that the SKILL.md never names is worse than dead weight: `support/` and
    `templates/` are not indexed anywhere else, so an undocumented file is
    invisible to the model that would use it and unmaintained by everyone else.

    Paths written `<other-skill>/support/x.py` are deliberately skipped: the
    angle brackets mark a placeholder for another skill's install location,
    which is not resolvable from here and not this skill's to ship.
    """
    bundled = re.compile(
        r"(?<![>/\w])(?:support|templates|references)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+")
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        directory = skill_md.parent
        text = skill_md.read_text()

        for match in bundled.finditer(text):
            cited = match.group(0).rstrip(".,;:")
            if not (directory / cited).exists():
                line = text.count("\n", 0, match.start()) + 1
                errors.append(
                    f"skills/{directory.name}/SKILL.md:{line}: cites {cited!r}, "
                    "which the skill does not ship")

        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.name == "SKILL.md":
                continue
            if "__pycache__" in path.parts:
                continue
            if path.name not in text:
                errors.append(
                    f"skills/{directory.name}/{path.relative_to(directory)}: "
                    "shipped but never named in SKILL.md — document it there or "
                    "delete it; nothing else indexes a skill's own files")


def check_markdown_links() -> None:
    """Every relative Markdown link must resolve, and to a file git actually ships.

    The docs cross-reference each other constantly — README to examples,
    examples to the reference implementations inside a skill, CONTRIBUTING to
    both — and a rename that misses one leaves a link that renders fine on
    GitHub and 404s on click. External URLs are not checked: CI must not depend
    on the network.

    Existence on disk is not enough. A link to an untracked or ignored file
    resolves perfectly for whoever wrote it and 404s for everyone else, which is
    the one broken link a local check would never see. Directories are exempt —
    git tracks files, not folders.
    """
    tracked: set[str] | None = None
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout
        tracked = {p for p in out.split("\0") if p}
    except (OSError, subprocess.CalledProcessError):
        pass  # not a git checkout: the on-disk check below still applies

    link = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)\s]*)?\)")
    for md in sorted(ROOT.rglob("*.md")):
        if ".git" in md.parts:
            continue
        text = md.read_text(errors="replace")
        for match in link.finditer(text):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            line = text.count("\n", 0, match.start()) + 1
            resolved = md.parent / target
            if not resolved.exists():
                errors.append(f"{md.relative_to(ROOT)}:{line}: link target "
                              f"{target!r} does not exist")
                continue
            if tracked is None or resolved.is_dir():
                continue
            rel = resolved.resolve().relative_to(ROOT).as_posix()
            if rel not in tracked:
                errors.append(
                    f"{md.relative_to(ROOT)}:{line}: link target {target!r} "
                    "exists here but is not tracked by git — it would 404 for "
                    "anyone else. Commit it, or drop the link.")


def check_pulser_pins() -> None:
    """One tested Pulser version, stated the same way everywhere.

    These drifted before: CI ran one version while a skill documented another,
    so a user following the docs installed something no test had exercised. The
    examples assert on device constants Pulser ships, which is what makes the
    number load-bearing rather than cosmetic. `requirements.txt` deliberately
    keeps a floor rather than a pin — users are not forced onto one release —
    and `submit-via-hpc` installs from offline zips on an air-gapped cluster,
    where the version is whatever was last validated in that container.
    """
    found: dict[str, list[str]] = {}
    for rel, pattern in PULSER_PIN_SOURCES:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"{rel}: missing — it states the tested Pulser version")
            continue
        match = re.search(pattern, path.read_text())
        if match is None:
            errors.append(f"{rel}: no Pulser version matching /{pattern}/ — the "
                          "pin was reworded; update PULSER_PIN_SOURCES with it")
            continue
        found.setdefault(match.group(1), []).append(rel)
    if len(found) > 1:
        detail = "; ".join(f"{v} in {', '.join(f)}" for v, f in sorted(found.items()))
        errors.append(f"tested Pulser version diverges: {detail}. CI installs one "
                      "version; anything the docs claim was tested must be it.")


check_versions()
check_codex_catalog()
check_agent_plugin_manifest()
check_skill_names()
check_skill_layout()
check_skill_portability()
check_skill_references()
check_agents_index()
check_markdown_links()
check_example_isolation()
check_examples()
check_vendored_modules()
check_pulser_pins()

if errors:
    for err in errors:
        print(f"✘ {err}")
    sys.exit(1)
print("  versions aligned, catalogs conform, skill frontmatter valid, "
      "skill layout discoverable, skills harness-neutral, bundled files "
      "documented, links resolve, AGENTS.md complete, examples self-contained, "
      "vendored modules identical")
