# Harness compatibility

`skills/` is the whole toolkit and it is never forked. Every harness below runs
the same seven skill directories, byte for byte; what differs is only how they
reach the model. Nothing in `skills/` names a proprietary tool or a
harness-specific variable — `scripts/check.sh` fails if that changes.

## Tiers

| Tier | What it means |
|---|---|
| **A** | The harness installs this repo as a plugin and discovers the skills itself, by name and description. Full behaviour, including automatic invocation from a phrase like "submit this to the QPU". |
| **B** | The skills are discovered, but not through a plugin install — a symlink into a scanned directory, or a context file the harness always loads. Same skills, one manual setup step. |
| **C** | The harness has no skill mechanism. Clone the repo; [`AGENTS.md`](../AGENTS.md) tells the agent what the skills are and to read the matching `SKILL.md` before acting. |

## Matrix

| Harness | Tier | Mechanism | Install |
|---|---|---|---|
| **Claude Code** | A | `.claude-plugin/plugin.json` + self-hosted marketplace catalog | `/plugin marketplace add pasqal-io/agent-marketplace` then `/plugin install neutral-atom-toolkit@pasqal` — [details](agents/claude-code.md) |
| **OpenAI Codex** | A | `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json` | `codex plugin marketplace add pasqal-io/agent-marketplace`, then install from the Plugins view — [details](agents/codex.md) |
| **Kimi Code** | A | `.kimi-plugin/plugin.json` (+ `skillInstructions` tool mapping) | `/plugins install https://github.com/pasqal-io/agent-marketplace`, then `/new` — [details](agents/kimi.md) |
| **Cursor** | A | root `plugin.json` (Agent Plugins 1.0) | Customize → find the plugin → Install, project or user scope. Cursor loads an Agent Plugins package unchanged, so no `.cursor-plugin/` is needed |
| **VS Code / GitHub Copilot** | A | root `plugin.json` (Agent Plugins 1.0) | set `chat.plugins.enabled`, then the **Chat: Install Plugin From Source** command (Copilot CLI: `/plugin marketplace add pasqal-io/agent-marketplace`, `/plugin install neutral-atom-toolkit@agent-marketplace`) |
| **DeepSeek Harness** | B | native Agent Skills discovery from a scanned directory; no manifest | `git clone`, then link the skills into `~/.agents/skills`, or name the checkout in `customSkillDirs` — [details](agents/deepseek-harness.md) |
| **Gemini CLI** | B | `gemini-extension.json` declares `GEMINI.md`, which `@`-includes `AGENTS.md` | `gemini extensions install https://github.com/pasqal-io/agent-marketplace` |
| **OpenCode** | B | native Agent Skills discovery from a scanned directory | `git clone`, then `ln -s "$PWD/skills" ~/.agents/skills` (or `.agents/skills` inside a project) |
| **Anything else** | C | `AGENTS.md` at the repo root | `git clone` and open the repo |

Every manifest above is validated in CI against the specification its vendor
publishes, and the install command in each row is that vendor's documented one.
Skill discovery for the two tier-B directory scanners is checked too: CI rejects
a skill that is not `skills/<kebab-case-name>/SKILL.md`, because neither of them
recurses and both skip a name they cannot match. If an install goes wrong on
your agent, say which one and which version — that is the most useful issue you
can open.

## What degrades, and where

- **Interactive multiple-choice questions.** `validate-emu` asks where to run
  (this machine / cloud), `noise-emulate` the same with SLURM in between, and
  `submit-to-cea` asks for site values. The
  skills say to use the harness's question mechanism *if it has one* and plain
  text otherwise, so the worst case is a text question. A harness whose adapter
  can name its own tool should do so there — Kimi's `skillInstructions` is the
  worked example.
- **Long-running polls.** Cloud emulator batches and QPU jobs take minutes to
  hours. Every runner writes its batch IDs to `<out-dir>/batch_ids.json` *before*
  waiting, and refuses to submit again while that file is there, so a dropped
  session never costs shots. `validate-emu` picks the recorded batches back up
  with `--resume`; QPU results are collected by `harvest-and-analyze` from the
  same file, which is a re-runnable step by construction. A harness that cannot
  run a command in the background costs the user a re-invocation, never a batch.
- **No native skill tool.** The model reads `skills/<name>/SKILL.md` itself.
  This is the sanctioned fallback, not a hack — the skills are written to be
  read that way.
- **Frontmatter extensions.** `argument-hint` is a Claude Code extension; other
  harnesses ignore it. Nothing depends on it.
- **What never degrades.** The gate order (emulation before hardware), the cost
  confirmation before a submission, and credential handling. Two of those hold
  even if a harness ignores its skill instructions entirely, because they are
  enforced in the scripts: `submit_qpu.py` refuses to submit without `--confirm`
  or a terminal `y`, and every runner refuses to resubmit over recorded batch
  IDs. A port that weakens one of those is not a port — see
  [porting-to-a-new-harness.md](porting-to-a-new-harness.md).
