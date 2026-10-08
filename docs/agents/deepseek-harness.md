# DeepSeek Harness (`dsh`)

DeepSeek Harness reads the Agent Skills format natively, so this repository
needs no manifest for it. Point `dsh` at `skills/` and the eleven skills appear
in its catalog under their own names.

Checked against [`deepseek-ai/deepseek-harness`](https://github.com/deepseek-ai/deepseek-harness)
at `master` and npm `@deepseek-ai/dsh` 0.1.0-rc.6.

## Install

`dsh` scans a fixed set of roots. The simplest is the shared per-user one,
`~/.agents/skills`, which is the same root OpenCode reads:

```bash
git clone https://github.com/pasqal-io/agent-marketplace ~/agent-marketplace
mkdir -p ~/.agents/skills
for skill in ~/agent-marketplace/skills/*/; do ln -s "$skill" ~/.agents/skills/; done
```

Symlinks are followed: `dsh` stats each entry and treats a link to a directory
as a directory. Linking the eleven skills individually rather than the whole
`skills/` tree keeps the root usable by anything else you have put there.

Restart `dsh` and the skills are in the catalog. To scope them to one project
instead, use `<project>/.agents/skills` — same layout, and it wins over the
per-user root.

### Without a symlink

`dsh-skill-filesystem` takes extra roots through `customSkillDirs`, set on that
plugin's row in your profile's `cordis.yml`:

```yaml
- id: skill-filesystem
  config:
    customSkillDirs:
      - /home/you/agent-marketplace/skills
```

This is the route to prefer if you already maintain a profile patch. It scans
the checkout in place, so `git pull` is the whole update procedure.

## Discovery roots and precedence

The local provider scans these in rank order, and a lower rank wins a duplicate
skill name:

| Rank | Source | Root |
|---|---|---|
| 100 | `project-dsh` | `<projectRoot>/.dsh/skills` |
| 200 | `project-agents` | `<projectRoot>/.agents/skills` |
| 300 | `custom` | `customSkillDirs` |
| 400 | `user-dsh` | `$DSH_HOME` or `~/.dsh`, `/skills` |
| 500 | `user-agents` | `$DSH_AGENTS_HOME` or `~/.agents`, `/skills` |
| 600 | `bundled` | whatever the deployment packages |

The project root is the nearest ancestor holding `.git`; with none, the current
working directory is used. Because a project root outranks both user roots, a
checkout of this repo that contains its own `.agents/skills` would shadow the
installed copy — worth knowing if you work inside the toolkit itself.

## What `dsh` requires of a skill

Three constraints, all of which `scripts/check.sh` enforces so they cannot
regress:

- **`<name>/SKILL.md`, exactly one level deep.** A flat `<name>.md` is also
  accepted. Recursive `**/SKILL.md` discovery is not supported, so a skill
  nested two directories down is invisible rather than an error.
- **Kebab-case names**, matching `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
- **A `description` under 500 characters.** `dsh` renders name and description
  only into the model's catalog, bounded by `catalogDescriptionMaxLength`
  (default 500). Our limit is the same number.

Frontmatter beyond `name`, `description` and the optional `whenToUse` is parsed
into a metadata object and otherwise ignored, which is why `argument-hint` is
harmless here. `disable-model-invocation` and `user-invocable` both default to
true, so the skills are reachable from the model and from the `/` palette
without declaring anything.

## Why there is no `.dsh-plugin` manifest here

There was one, briefly. DeepSeek removed the whole repository-plugin path on
2026-08-09 — the `.dsh-plugin` authoring format, the generated wrapper, the
`dsh-plugin-prepare` executable and the repository-specific skill adapter — and
kept no compatibility parser or migration. A tutorial that tells you to write
`.dsh-plugin/plugin.json` predates that removal.

What replaced it is a single path for packaged extensions: an installable
*profile bundle*, an npm or git package that declares `dsh.bundle.patch` and is
added with `dsh plugin --profile <name> add <package-or-git-spec>`. A bundle
contributing skills mounts `@deepseek-ai/dsh-skill-filesystem` — the same
plugin the filesystem routes above configure directly. Since a bundle also
requires `pnpm` on `PATH` and an npm publication to be worth anything, it buys
this repository nothing that a scanned directory does not already give.

`dsh` is in developer preview and its README promises compatibility-breaking
changes. Filesystem discovery is the part least likely to move, which is a
second reason to sit on it.

## Sources

- [Skills subsystem](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md)
  — discovery ranks, skill identity, catalog bound
- [Config catalog](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/config-catalog.md)
  — `dsh-skill-filesystem` options and their defaults
- [Removing the repository plugin path](https://github.com/deepseek-ai/deepseek-harness/blob/master/.agents/notes/implemented/simplification/2026-08-09-remove-repository-plugin.md)
  — why `.dsh-plugin` is gone and what took its place
