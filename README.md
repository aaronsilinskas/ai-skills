# Agent Skills

A personal collection of [Agent Skills](https://agentskills.io/) — reusable instruction sets that give AI agents domain-specific expertise.

> **Built on Matt Pocock's work.** Most of the engineering skills here are based on [Matt Pocock's excellent skills](https://github.com/mattpocock/skills). This repo adapts them to my workflow and software development preferences — see [What's changed from Matt's skills](#whats-changed-from-matts-skills) below. Huge thanks to Matt for the foundation!

## Skills

**Invoked by** — *You* means the skill only runs when you type it (e.g. `/to-prd`); *You or model* means the model can also reach for it automatically from its description.

### Engineering

| Skill | Invoked by | Description |
| --- | --- | --- |
| [bdd](skills/engineering/bdd/SKILL.md) | You or model | Behavior-driven testing: red-green-refactor by vertical slices, held to a naming/structure/coverage quality bar. |
| [code-quality](skills/engineering/code-quality/SKILL.md) | You or model | General implementation-quality review bar (readability, public-API discipline, type coverage); platform specifics in reference files. |
| [codebase-design](skills/engineering/codebase-design/SKILL.md) | You or model | Shared vocabulary for designing deep modules — small interfaces, clean seams, testable through the interface. |
| [comments](skills/engineering/comments/SKILL.md) | You or model | Decide whether code needs a comment/docstring at all, and write the ones that survive; language formatting in reference files. |
| [diagnosing-bugs](skills/engineering/diagnosing-bugs/SKILL.md) | You or model | Disciplined diagnosis loop for hard bugs and perf regressions: reproduce → minimise → hypothesise → instrument → fix. |
| [domain-modeling](skills/engineering/domain-modeling/SKILL.md) | You or model | Maintain the domain docs inline — the map (`domain.md`) and the language (`domain-language.md`). |
| [grill-with-docs](skills/engineering/grill-with-docs/SKILL.md) | You | A grilling interview that also keeps the domain docs current as decisions crystallise. |
| [improve-codebase-architecture](skills/engineering/improve-codebase-architecture/SKILL.md) | You | Scan for deepening opportunities, present a visual HTML report, then grill the one you pick. |
| [prototype](skills/engineering/prototype/SKILL.md) | You or model | Build a throwaway prototype to answer a design question — a terminal state model, or several UI variations. |
| [resolving-merge-conflicts](skills/engineering/resolving-merge-conflicts/SKILL.md) | You or model | Resolve an in-progress git merge/rebase conflict, preserving both intents. |
| [to-idea](skills/engineering/to-idea/SKILL.md) | You | Capture a discovery or new idea as a lightweight `idea`-labeled issue to revisit later — a stub, not a PRD. |
| [to-issues](skills/engineering/to-issues/SKILL.md) | You | Break a plan or PRD into independently-grabbable issues via tracer-bullet vertical slices. |
| [to-prd](skills/engineering/to-prd/SKILL.md) | You | Synthesize the conversation into a PRD — local first, grilled, then published to the issue tracker. |
| [triage](skills/engineering/triage/SKILL.md) | You | Move issues and external PRs through a state machine of triage roles — categorise, verify, and write agent-ready briefs. |
| [work-on-issue](skills/engineering/work-on-issue/SKILL.md) | You or model | Implement a GitHub issue end-to-end: fetch → explore → BDD → validate → open a PR. |

### Productivity

| Skill | Invoked by | Description |
| --- | --- | --- |
| [grilling](skills/productivity/grilling/SKILL.md) | You or model | Interview relentlessly to stress-test a plan or design, one question at a time. |
| [grill-me](skills/productivity/grill-me/SKILL.md) | You | Plain user-invoked entry point to a grilling session. |
| [handoff](skills/productivity/handoff/SKILL.md) | You | Compact the current conversation into a handoff document so a fresh agent can continue the work. |

### Misc

| Skill | Invoked by | Description |
| --- | --- | --- |
| [air-quality-data](skills/misc/air-quality-data/SKILL.md) | You or model | Fetch and compare air quality data (AQI, PM2.5/PM10) via EPA AirNow, PurpleAir, IQAir, and OpenAQ. |

## What's changed from Matt's skills

These skills started from Matt Pocock's and were adapted to fit my workflow. The notable divergences and why:

- **`CONTEXT.md` → `domain-language.md`.** "Context" collides with the AI sense of session/window context, and the file is really the project's *domain glossary*. It's now paired with a `domain.md` **map** (module layout, key types, constraints): one file for *meaning*, one for *structure*, with a strict boundary so they stop duplicating and drifting.
- **Removed ADRs.** Architecture Decision Records were getting created for decisions that easily change, then drifting out of date. Decisions now live in the **GitHub issue** for the work (grilling captures them there); the domain docs are kept current instead.
- **Merged the test skills into `bdd`.** Matt's `tdd` (the red-green-refactor process) merged with a behavior-driven test-quality bar into one skill, with per-language mocking guidance in reference files.
- **Dropped the `implement` skill.** It was a thin wrapper that shadowed the preferred `work-on-issue` flow, so it's gone.
- **Language-agnostic skills + reference files.** `comments` and `code-quality` hold general, language-neutral guidance; language/platform specifics (Python docstrings, CircuitPython rules, etc.) load from reference files only when relevant.
- **Python-canonical examples.** Matt's code examples are largely TypeScript; the skills here use Python for illustrative examples, with genuinely language-specific bits kept in the per-language reference files.
- **Claude Code idiom.** Skills invoke each other via the **Skill tool** and dispatch fresh subagents via the **Agent tool**, rather than fetching files or calling `runSubagent`.
- **`domain-modeling` maintains both domain docs inline** during grilling, rather than allowing domain.md to become stale until manually updated.
- **`to-prd` is grill-first.** Instead of publishing a PRD to the issue tracker immediately, it produces a local draft, hands off to `grill-with-docs`, and publishes only once the design settles.
- **Added `to-idea`.** A new skill (not one of Matt's) for capturing a discovery as a lightweight `idea`-labeled issue to revisit later — a stub, distinct from a full PRD.

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
for skill in aaronsilinskas-skills/skills/{engineering,productivity,misc}/*/; do
  ln -s "$(pwd)/$skill" ~/.claude/skills/"$(basename "$skill")"
done
```

Skills are then available at `~/.claude/skills/<name>/SKILL.md` and can be edited directly in the repo.

## Conventions

Skills follow the [agentskills.io specification](https://agentskills.io/specification) and [best practices](https://agentskills.io/skill-creation/best-practices). Use the Anthropic [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) skill when creating or updating any skill here.
