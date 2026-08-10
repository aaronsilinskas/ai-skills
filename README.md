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

These skills started from Matt Pocock's and were adapted to fit my workflow. For the ported subset, the baseline has advanced from Matt's v1.1.0 to a 1.2.3-equivalent. The notable divergences and why:

- **`CONTEXT.md` → `domain-language.md`.** "Context" collides with the AI sense of session/window context, and the file is really the project's *domain glossary*. It's now paired with a `domain.md` **map** (module layout, key types, constraints): one file for *meaning*, one for *structure*, with a strict boundary so they stop duplicating and drifting.
- **Removed ADRs.** Architecture Decision Records were getting created for decisions that easily change, then drifting out of date. Decisions now live in the **GitHub issue** for the work (grilling captures them there); the domain docs are kept current instead.
- **Merged the test skills into `bdd`.** Matt's `tdd` (the red-green-refactor process) merged with a behavior-driven test-quality bar into one skill, with per-language mocking guidance in reference files.
- **`implement` is a deeper flow than Matt's was.** Matt's `implement` was a thin wrapper; this fork replaced it with an end-to-end flow — fetch → explore → BDD → open a PR, then a whole-diff `code-review` pass (Standards + Spec) whose findings are applied back — that was called `work-on-issue` before reclaiming the `implement` name.
- **Language-agnostic skills + reference files.** `comments` and `code-quality` hold general, language-neutral guidance; language/platform specifics (Python docstrings, CircuitPython rules, etc.) load from reference files only when relevant.
- **Python-canonical examples.** Matt's code examples are largely TypeScript; the skills here use Python for illustrative examples, with genuinely language-specific bits kept in the per-language reference files.
- **`domain-modeling` maintains both domain docs inline** during grilling, rather than allowing domain.md to become stale until manually updated.
- **`to-prd` → `to-spec`, grill-first.** Adopted Matt's v1.1.0 `to-prd` → `to-spec` rename and the PRD→spec vocabulary (the `prd` label became `spec` too); "spec" is now the document term across the skills. But where Matt publishes immediately, this skill still produces a local draft, hands off to `grill-with-docs`, and publishes only once the design settles.
- **Added `to-idea`.** A new skill (not one of Matt's) for capturing a discovery as a lightweight `idea`-labeled issue to revisit later — a stub, distinct from a full spec.
- **`code-review` with refactoring kept at two altitudes.** Adopted Matt's v1.1.0 two-axis `code-review` (Standards + Spec, run as parallel sub-agents), but where he moved refactoring entirely out of the red→green loop into it, `bdd` keeps its *local, under-green* refactor beat and `code-review` owns the *whole-diff* structural smell pass (`code-review/smells.md`). This keeps `bdd` self-contained for standalone use and separates the two genuine refactoring altitudes. The Standards axis also leans on the existing `code-quality`/`bdd` bars rather than restating them.
- **`wayfinder` as the upstream of `to-spec`.** Adopted Matt's v1.1.0 `wayfinder` (his promoted `decision-mapping`) for charting work too big and foggy for a single session. Slotted explicitly ahead of `to-spec`: when a map's destination is a spec, it hands its settled decisions to `to-spec` to synthesize and publish. Its ticket types reuse existing skills (`research`, `prototype`, `grilling`, `domain-modeling`), and since GitHub lacks native dependency links, blocking/frontier use a GitHub sub-issues + `Blocked by #x` body convention rather than Matt's native-blocking assumption. Following the fork's tracker-agnostic pattern, the skill defers its mechanics and label strings to the project's own agent docs (a shared "Issue relationships" section plus a wayfinder-specific "Wayfinding operations" section in its tracker doc, and its label doc), falling back to a portable default (`wayfinder/github-operations.md`) only when the project defines none.
- **Added `wait-what`.** Newly adopted from Matt's skills — a one-word corrective the user fires when a message didn't land, re-pitching in ASD-STE100 Simplified Technical English. Its glossary reference swaps Matt's `CONTEXT.md` for this fork's `domain-language.md`.
- **Added `to-questionnaire`.** Newly adopted from Matt's skills — turns a decision the user can't answer alone into a Markdown questionnaire for the person who can, grilling the user about the send rather than the subject. Ported as-is.
- **`to-issues` → `to-tickets`, with Matt's `to-tickets` substance.** Adopted Matt's v1.1.0 rename (a **ticket** is the unit of work — a vertical slice — realized as a GitHub **issue**; the vocabulary now matches `wayfinder`, whose child issues are also tickets). Ported the wide-refactor **expand–contract** sequence (for a mechanical change too broad for any vertical slice), single-context-window slice sizing, and **frontier** framing (work one ticket at a time via `implement`, clearing context between). Blocking and hierarchy defer to the shared **Issue relationships** convention `wayfinder` uses (`Blocked by #n` + sub-issues) instead of a freeform field. Skipped Matt's local-file `tickets.md` mode (this fork is tracker-centric).
- **Added `wizard`, the fork's first bundled executable.** Newly adopted from Matt's skills — generates an interactive bash wizard that walks a human through manual setup an agent can't do itself (provisioning, credentials, CI secrets, unfamiliar dashboards). Ported unchanged, and it's the first skill here to carry a bundled asset: a fixed-UX `template.sh` library (progress stages, confirmation gates, hidden secret entry, idempotent `.env` upserts, `gh secret`/`gh variable` writes) that the generated wizard builds on and never hand-edits. Matt's `agents/`/`openai.yaml` were dropped, following the fork's harness-neutral pattern.

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
