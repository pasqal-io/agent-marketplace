# Per-agent installation

The skills in this repository follow the [Agent Skills](https://agentskills.io)
open standard: each skill is a directory with a `SKILL.md` (YAML frontmatter +
instructions) plus supporting files. The root `plugin.json` follows
[Agent Plugins 1.0](https://agent-plugins.org/specification), the manifest every
conformant client must read — one file covering Cursor, VS Code, GitHub Copilot,
Codex and Kiro without a per-vendor adapter.

**Which agents work, how the skills reach them, and the install command for
each: [../harness-compatibility.md](../harness-compatibility.md).** That matrix
is the single list. The pages below add detail only where an agent has a quirk
worth explaining.

| Agent | Page | Why it has a page |
|---|---|---|
| Claude Code | [claude-code.md](claude-code.md) | marketplace install, enterprise distribution, `--plugin-dir` dry run |
| OpenAI Codex | [codex.md](codex.md) | the catalog path Codex actually reads, and the empty-`hooks` trap |
| Kimi Code | [kimi.md](kimi.md) | the `skillInstructions` tool mapping |
| DeepSeek Harness | [deepseek-harness.md](deepseek-harness.md) | six discovery roots and their precedence, and why `.dsh-plugin` is not one of them |

Adding an agent: [../porting-to-a-new-harness.md](../porting-to-a-new-harness.md).
It covers the capability floor, the three delivery shapes, where a tool mapping
goes (the adapter manifest, never a skill), and the definition of done —
including the behavioural tests no CI can run for you.
[obra/superpowers](https://github.com/obra/superpowers) remains the reference for
multi-harness adapter layouts.
