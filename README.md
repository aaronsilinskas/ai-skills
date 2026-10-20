# Agent Skills

A personal collection of [Agent Skills](https://agentskills.io/) — reusable instruction sets that give AI agents domain-specific expertise.

> **Built on Matt Pocock's work.** Most of the engineering skills here are based on [Matt Pocock's excellent skills](https://github.com/mattpocock/skills). This repo adapts them to my workflow and software development preferences — see [What's changed from Matt's skills](#whats-changed-from-matts-skills) below. Huge thanks to Matt for the foundation!

## Skills

**Invoked by** — *You* means the skill only runs when you type it (e.g. `/to-idea`); *You or model* means the model can also reach for it automatically from its description.

### Engineering

| Skill | Invoked by | Description |
| --- | --- | --- |
| [checkout](skills/engineering/checkout/SKILL.md) | You | Check out a branch in the project directory to validate/iterate on it — clears a blocking worktree and rescues local changes first. |
| [code-quality](skills/engineering/code-quality/SKILL.md) | You or model | General implementation-quality review bar (readability, public-API discipline, type coverage); platform specifics in reference files. |
| [comments](skills/engineering/comments/SKILL.md) | You or model | Decide whether code needs a comment/docstring at all, and write the ones that survive; language formatting in reference files. |
| [test-quality](skills/engineering/test-quality/SKILL.md) | You or model | Review and audit tests against a quality bar: test naming, one behavior per test, coverage planning, per-language mocking guides. Pairs with Matt's `tdd`, which owns the loop. |
| [to-idea](skills/engineering/to-idea/SKILL.md) | You | Capture a discovery or new idea as a lightweight `idea`-labeled issue to revisit later — a stub, not a spec. |

### Misc

| Skill | Invoked by | Description |
| --- | --- | --- |
| [air-quality-data](skills/misc/air-quality-data/SKILL.md) | You or model | Fetch and compare air quality data (AQI, PM2.5/PM10) via EPA AirNow, PurpleAir, IQAir, and OpenAQ. |

## What's changed from Matt's skills

These skills started from Matt Pocock's (currently synced to his v1.2.3) and were adapted to fit my workflow. The current divergences and why:

- **Fork-only skills.** `code-quality`, `comments`, `test-quality`, `to-idea`, and `checkout` have no Matt equivalent. `code-quality`/`comments` hold language-neutral guidance, with specifics (Python docstrings, CircuitPython rules, etc.) in reference files; `to-idea` captures a discovery as a lightweight `idea`-labeled stub, distinct from a full spec; `test-quality` is a test quality bar with per-language mocking guides, run as a review pass alongside Matt's `tdd` loop.
- **Harness-neutral.** The fork drops the `agents/openai.yaml` files Matt ships with each skill.

## Installation

The easiest way is the [`skills`](https://github.com/vercel-labs/skills) CLI, which lets you pick which skills to install and which agents (Claude Code, Cursor, etc.) to install them to:

```bash
npx skills@latest add aaronsilinskas/ai-skills
```

### Manual install

Alternatively, clone the repo and symlink each skill into the Claude Code skills directory:

```bash
git clone https://github.com/aaronsilinskas/ai-skills.git aaronsilinskas-skills
mkdir -p ~/.claude/skills
for skill in aaronsilinskas-skills/skills/{engineering,misc}/*/; do
  ln -s "$(pwd)/$skill" ~/.claude/skills/"$(basename "$skill")"
done
```

Skills are then available at `~/.claude/skills/<name>/SKILL.md` and can be edited directly in the repo.

## Conventions

Skills follow the [agentskills.io specification](https://agentskills.io/specification) and [best practices](https://agentskills.io/skill-creation/best-practices). Use the Anthropic [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) skill when creating or updating any skill here.

## Consistency check

After adding, removing, or editing a skill, run the consistency guard:

```bash
bash scripts/check.sh
```

It verifies the repo stays agent-agnostic, that every skill directory is listed in a README bucket table (with no orphans either way), and that `wizard/template.sh` lints when it is present (it reports SKIP when it isn't). It exits non-zero if anything is off.
