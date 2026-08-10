# Agent Skills

A personal collection of [Agent Skills](https://agentskills.io/) — reusable instruction sets that give AI agents domain-specific expertise.

> **Built on Matt Pocock's work.** Most of the engineering skills here are based on [Matt Pocock's excellent skills](https://github.com/mattpocock/skills). This repo adapts them to my workflow and software development preferences — see [What's changed from Matt's skills](#whats-changed-from-matts-skills) below. Huge thanks to Matt for the foundation!

## Skills

**Invoked by** — *You* means the skill only runs when you type it (e.g. `/to-spec`); *You or model* means the model can also reach for it automatically from its description.

### Engineering

| Skill | Invoked by | Description |
| --- | --- | --- |
| [bdd](skills/engineering/bdd/SKILL.md) | You or model | Behavior-driven testing: red-green-refactor by vertical slices, held to a naming/structure/coverage quality bar. |
| [checkout](skills/engineering/checkout/SKILL.md) | You | Check out a branch in the project directory to validate/iterate on it — clears a blocking worktree and rescues local changes first. |
| [code-quality](skills/engineering/code-quality/SKILL.md) | You or model | General implementation-quality review bar (readability, public-API discipline, type coverage); platform specifics in reference files. |
| [code-review](skills/engineering/code-review/SKILL.md) | You or model | Two-axis review of a diff since a fixed point — Standards (conventions, quality bar, whole-diff smells) and Spec (matches the issue/spec) — run as parallel sub-agents. |
| [codebase-design](skills/engineering/codebase-design/SKILL.md) | You or model | Shared vocabulary for designing deep modules — small interfaces, clean seams, testable through the interface. |
| [comments](skills/engineering/comments/SKILL.md) | You or model | Decide whether code needs a comment/docstring at all, and write the ones that survive; language formatting in reference files. |
| [diagnosing-bugs](skills/engineering/diagnosing-bugs/SKILL.md) | You or model | Disciplined diagnosis loop for hard bugs and perf regressions: reproduce → minimise → hypothesise → instrument → fix. |
| [domain-modeling](skills/engineering/domain-modeling/SKILL.md) | You or model | Maintain the domain docs inline — the map (`domain.md`) and the language (`domain-language.md`). |
| [grill-with-docs](skills/engineering/grill-with-docs/SKILL.md) | You | A grilling interview that also keeps the domain docs current as decisions crystallise. |
| [implement](skills/engineering/implement/SKILL.md) | You or model | Implement a GitHub issue end-to-end: fetch → explore → BDD → open a PR → `code-review` pass. |
| [improve-codebase-architecture](skills/engineering/improve-codebase-architecture/SKILL.md) | You | Scan for deepening opportunities, present a visual HTML report, then grill the one you pick. |
| [prototype](skills/engineering/prototype/SKILL.md) | You or model | Build a throwaway prototype to answer a design question — a terminal state model, or several UI variations. |
| [research](skills/engineering/research/SKILL.md) | You or model | Dispatch a background agent to investigate a question against primary sources and write cited findings to a Markdown file. |
| [resolving-merge-conflicts](skills/engineering/resolving-merge-conflicts/SKILL.md) | You or model | Resolve an in-progress git merge/rebase conflict, preserving both intents. |
| [to-idea](skills/engineering/to-idea/SKILL.md) | You | Capture a discovery or new idea as a lightweight `idea`-labeled issue to revisit later — a stub, not a spec. |
| [to-spec](skills/engineering/to-spec/SKILL.md) | You | Synthesize the conversation into a spec (PRD) — local first, grilled, then published to the issue tracker. |
| [to-tickets](skills/engineering/to-tickets/SKILL.md) | You | Break a plan or spec into independently-grabbable tickets via tracer-bullet vertical slices, each declaring its blocking edges. |
| [triage](skills/engineering/triage/SKILL.md) | You | Move issues and external PRs through a state machine of triage roles — categorise, verify, and write agent-ready briefs. |
| [wayfinder](skills/engineering/wayfinder/SKILL.md) | You | Chart work too big for one session as a shared map of investigation tickets on the tracker, resolved one at a time — upstream of `to-spec`. |
| [wizard](skills/engineering/wizard/SKILL.md) | You or model | Generate an interactive bash wizard that walks a human through manual setup an agent can't do — dashboards, credentials, CI secrets; bundles a fixed-UX `template.sh`. |

### Productivity

| Skill | Invoked by | Description |
| --- | --- | --- |
| [grilling](skills/productivity/grilling/SKILL.md) | You or model | Interview relentlessly to stress-test a plan or design, round by round along a recomputed frontier. |
| [grill-me](skills/productivity/grill-me/SKILL.md) | You | Plain user-invoked entry point to a grilling session. |
| [handoff](skills/productivity/handoff/SKILL.md) | You | Compact the current conversation into a handoff document so a fresh agent can continue the work. |
| [to-questionnaire](skills/productivity/to-questionnaire/SKILL.md) | You | Turn a decision you can't answer alone into a Markdown questionnaire for the person who can — grilling the send, not the subject. |
| [wait-what](skills/productivity/wait-what/SKILL.md) | You | One-word corrective when a message didn't land: re-pitch in ASD-STE100 Simplified Technical English grounded in `domain-language.md`. |

### Misc

| Skill | Invoked by | Description |
| --- | --- | --- |
| [air-quality-data](skills/misc/air-quality-data/SKILL.md) | You or model | Fetch and compare air quality data (AQI, PM2.5/PM10) via EPA AirNow, PurpleAir, IQAir, and OpenAQ. |

## What's changed from Matt's skills

These skills started from Matt Pocock's (currently synced to his v1.2.3) and were adapted to fit my workflow. The current divergences and why:

- **`CONTEXT.md` → `domain.md` + `domain-language.md`.** Matt keeps a single `CONTEXT.md` glossary. This fork splits it into a domain **map** (`domain.md`: module layout, key types, constraints) and a domain **glossary** (`domain-language.md`), with a strict boundary so they stop duplicating and drifting. `domain-modeling` maintains both inline during grilling. (This also drives the one-line difference in `wait-what`'s glossary reference.)
- **Removed ADRs.** Matt records Architecture Decision Records (`.agents/adr/`). Here decisions live in the **GitHub issue** for the work (grilling captures them there), and the domain docs are kept current instead — no separate records to drift.
- **`bdd` replaces `tdd`.** Same red-green process, plus a behavior-driven test-quality bar, a *local, under-green* refactor beat, and per-language mocking guidance in reference files (Python/TypeScript/Kotlin). Matt's `tdd` pushes all refactoring out to `code-review`.
- **Fork-only skills.** `code-quality`, `comments`, `to-idea`, and `checkout` have no Matt equivalent. `code-quality`/`comments` hold language-neutral guidance, with specifics (Python docstrings, CircuitPython rules, etc.) in reference files; `to-idea` captures a discovery as a lightweight `idea`-labeled stub, distinct from a full spec.
- **`implement` is end-to-end.** Matt's is a thin wrapper (tdd → code-review → commit). This fork's runs fetch → explore → BDD → validate → open a PR, then applies a whole-diff `code-review` pass (Standards + Spec) back to the branch.
- **`to-spec` grills first.** Matt synthesizes and publishes immediately without interviewing. This fork produces a local draft, hands off to `grill-with-docs`, and publishes only once the design settles.
- **`code-review` refactoring split.** Both are two-axis (Standards + Spec, parallel sub-agents). This fork factors the structural smell list into `code-review/smells.md` and keeps `bdd`'s local refactor beat separate from `code-review`'s whole-diff smell pass, rather than routing all refactoring into `code-review`.
- **`to-tickets` is tracker-only.** Dropped Matt's local-file ticket mode; blocking and hierarchy use the shared `Blocked by #n` + sub-issues convention that `wayfinder` also relies on.
- **`wayfinder` defers to project docs.** Matt's is now tracker-agnostic too; this fork additionally makes the `Blocked by #x` body convention primary (GitHub has no native dependency links), defers label strings and mechanics to the project's own agent docs, and ships a portable `wayfinder/github-operations.md` fallback.
- **Python-canonical examples.** Matt's illustrative code is largely TypeScript; the skills here use Python, with genuinely language-specific bits kept in the per-language reference files.
- **Harness-neutral.** The fork drops the `agents/openai.yaml` files Matt ships with each skill — the only remaining difference in otherwise-unchanged skills like `wizard` and `to-questionnaire`.

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

## Consistency check

After adding, removing, or editing a skill, run the consistency guard:

```bash
bash scripts/check.sh
```

It verifies the repo stays agent-agnostic, that every skill directory is wired into both `.claude-plugin/plugin.json` and a README bucket table (with no orphans either way), and that the bundled `wizard/template.sh` still lints. It exits non-zero if anything is off.
