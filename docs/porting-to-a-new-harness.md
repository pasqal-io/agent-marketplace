# Porting the toolkit to a new harness

A harness is any agent that could run these skills — an IDE, a CLI, an agent
runner. This guide says what a port consists of, how to tell whether a given
harness can host the toolkit at all, and when a port is finished.

The integration mechanisms below will keep changing; the vendors ship faster than
this file does. What does not change are the invariants in Part 1 and Part 5.
When this guide and the code disagree, the code wins — fix the guide.

## Part 1 — What a port is, and is not

`skills/` is the toolkit. All seven skill directories are shared verbatim by
every harness, and a port **never edits them**. The skills are written to name
*actions* — "ask the user", "read a file", "run this script", "run this poll in
the background" — never a tool. That is what lets one skill body run on Claude
Code, Codex, Cursor, Gemini and the rest unchanged, and `scripts/check.sh`
enforces it by rejecting proprietary tool names and harness-specific variables
anywhere under `skills/`.

A port therefore consists of at most three small things:

1. **An entry point** — the manifest or extension file the harness installs.
   Ten to twenty lines, no logic.
2. **A tool mapping**, only if the harness's tool names differ enough to confuse
   the model. It lives *in the adapter*, never in a skill. `.kimi-plugin/plugin.json`
   carries one in its `skillInstructions` field; that is the worked example.
3. **A row in [harness-compatibility.md](harness-compatibility.md)** and an
   install note, honest about what you actually ran.

Two things a port must never do, in any circumstance:

- **Never edit skill bodies to fit the harness.** If the model misbehaves
  because a tool is named differently, the fix goes in the tool mapping.
- **Never write to the user's own configuration.** The bootstrap, the skills and
  the mapping all ride the harness's install mechanism. Reaching into
  `~/.config/<harness>/settings.json` or a shell profile to inject the toolkit
  is not a port. (A context file *shipped inside the installed extension* and
  declared by its manifest — Gemini's `contextFileName` — is fine: the harness
  loads the extension's file, not a file you edited in the user's home.)

**You may not need to add anything.** Some harnesses read an existing manifest
already: Cursor and VS Code both load the root `plugin.json`, and OpenCode
discovers skills from a directory it already scans. A port whose entire diff is
one table row and one install line is the best possible outcome.

## Part 2 — Can this harness host the toolkit?

Unlike a skills framework that must teach the model that skills exist, this
toolkit needs **no session-start injection**. It ships no hooks at all. A
harness qualifies if the model can find the skills and act on them:

| Capability | Why it is needed | If absent |
|---|---|---|
| **Skill discovery** — list skills by description, load one on demand | The seven skills are chosen from their descriptions | Degradable: the model reads `skills/<name>/SKILL.md` itself. Ship `AGENTS.md` so it knows they exist (tier C). A harness that can neither discover skills nor read files cannot work. |
| **File read / write** | Every skill produces or consumes a spec, a sequence, results | Essential. No workaround. |
| **Run shell commands** | Each skill's real work is in `support/*.py` | Essential. Without it the model would have to reimplement the physics inline, which is exactly what these skills exist to prevent. |
| **Ask the user a question mid-task** | Execution mode, cluster values, cost confirmation before a submission | Degradable to a plain-text question, and the skills already word it that way. **Not** degradable to skipping the question — see Part 5. |
| **Long-running or background commands** | Cloud batches and QPU jobs run for minutes to hours | Degradable: every runner saves its batch IDs before waiting and accepts `--resume`. Document the re-invocation. |
| **Fetch a URL** | `idea-to-spec` with an arXiv ID or a link | Degradable: the user supplies a local PDF instead. |

Python 3 and a Pulser virtual environment are the user's responsibility on every
harness (`PULSER_VENV`), not the port's.

## Part 3 — Choose a delivery shape

| If the harness… | Shape | Copy from |
|---|---|---|
| installs a plugin and discovers `skills/` itself | **A** — manifest | root `plugin.json` (Agent Plugins 1.0, covers Cursor / VS Code / Copilot / Codex / Kiro), `.claude-plugin/`, `.codex-plugin/`, `.kimi-plugin/` |
| installs an extension that declares a context file it always loads | **B** — declared context file | `gemini-extension.json` + `GEMINI.md`, which `@`-includes `AGENTS.md` |
| scans a directory for `SKILL.md` but has no installer | **B** — symlink | the OpenCode row: `ln -s "$PWD/skills" ~/.agents/skills` |
| has none of the above | **C** — clone + `AGENTS.md` | nothing to add but documentation |

Prefer shape A through the **Agent Plugins standard** rather than a
vendor-specific manifest: a root `plugin.json` with the canonical `$schema` is
the one manifest every conformant client must check, and it already covers
several harnesses at once. Add a vendor-specific directory only when the harness
needs something the standard does not carry.

## Part 4 — The tool mapping, if you need one

Write it as a translation from the actions the skills use to the harness's real
tools, and put it in the adapter. Actions the skills actually name:

| Action in a skill | What the mapping must say |
|---|---|
| "ask the user, offering the options" | the harness's interactive-question tool, or "ask in plain text" |
| "read the file" / "search for" | the read and search tools |
| "run `support/foo.py`" | the shell tool, plus how to expand a skill-relative path to an absolute one |
| "poll until the batch completes" | how to run a long command in the background, and that `--resume` exists |

Also state the rule that paths like `support/…` and `templates/…` are relative
to the skill's own directory. That single sentence is the most common reason a
port half-works.

## Part 5 — Definition of done

1. The skills are installable through the harness's own mechanism — no
   hand-copying of files, no edit to the user's config.
2. `bash scripts/check.sh` passes, including the manifest checks for whatever
   file you added.
3. **The invocation test.** In a clean session, "turn this paper into an
   experiment spec" reaches `idea-to-spec` and the model follows the skill
   rather than improvising an extraction. Capture the transcript in the PR.
4. **The gate test.** Ask for a QPU submission directly, with no prior
   validation: the model must route through `validate-emu` and must ask for
   confirmation of device, shots and point count before submitting. A harness
   where the model skips the gate is not ready, and the fix is the adapter or
   the mapping — not a weaker skill.
5. **The credential test.** With `PASQAL_*` unset and a non-interactive run, the
   scripts must fail with the "credentials incomplete" message naming the
   missing variables, and nothing must echo a password.
6. A row in [harness-compatibility.md](harness-compatibility.md) stating the
   tier, the mechanism, the install command, and what you actually exercised.
7. If you added a manifest carrying a version, register it in
   `scripts/check_manifests.py` so a release bump cannot leave it behind.

Steps 3–5 are behavioural and no CI can run them; they are what the PR
transcript is for.

## Reference index

| Harness | Entry point | Tool mapping | Notes |
|---|---|---|---|
| Claude Code | `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` | none needed | validated in CI |
| Codex | `.codex-plugin/plugin.json` (`"hooks": {}` suppresses hook discovery) + `.agents/plugins/marketplace.json` | none needed | catalog schema checked in CI |
| Kimi Code | `.kimi-plugin/plugin.json` | inline `skillInstructions` | |
| Cursor, VS Code, Copilot, Kiro | root `plugin.json` | none needed | Agent Plugins 1.0; closed schema — unknown top-level keys are a violation |
| Gemini CLI | `gemini-extension.json` + `GEMINI.md` | none yet | `GEMINI.md` includes `AGENTS.md`; keep it a one-line include so the index stays single-sourced |
| OpenCode | none | none | symlink into a scanned skills directory |
| Everything else | `AGENTS.md` | — | tier C |
