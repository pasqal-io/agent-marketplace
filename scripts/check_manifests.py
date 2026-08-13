#!/usr/bin/env python3
"""Static conformance checks for the per-harness manifests.

Two things no harness CLI checks for us:

1. The plugin version is repeated in four manifests. Nothing keeps them in
   sync, so a release bump that touches one file ships a lying manifest to the
   other three harnesses.
2. The Codex marketplace catalog (`.agents/plugins/marketplace.json`) has
   required fields and closed enums. Codex reads that path — not
   `.claude-plugin/marketplace.json`, which is only a legacy fallback — and a
   missing field means the plugin simply does not appear.

Schema reference: https://developers.openai.com/codex/plugins/build
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# manifest path -> dotted path to the version string
VERSION_FIELDS = {
    ".claude-plugin/plugin.json": "version",
    ".claude-plugin/marketplace.json": "metadata.version",
    ".codex-plugin/plugin.json": "version",
    ".kimi-plugin/plugin.json": "version",
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


check_versions()
check_codex_catalog()
check_skill_names()

if errors:
    for err in errors:
        print(f"✘ {err}")
    sys.exit(1)
print("  versions aligned, Codex catalog conforms, skill frontmatter valid")
