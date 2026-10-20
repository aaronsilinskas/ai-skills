# Upstream delta and fork divergence at v1.3.1

- **Date:** 2026-10-20
- **Baseline:** `mattpocock/skills` tag `v1.3.1` (commit `24fe0ef`, 2026-10-04). Delta measured from `v1.2.3` (`6acc160`, 2026-08-06).
- **Addendum (#59):** for what changed from v1.3.1 to the official marketplace pin `49dd158`, per shared skill, see [Addendum: v1.3.1 → 49dd158](#addendum-v131--49dd158-official-marketplace-pin).
- **Fork:** `aaronsilinskas/ai-skills` `main` @ `ffa5b37`.
- **Question (#40):** Between Matt's `v1.2.3` and `v1.3.1`, what changed in each upstream skill, and what does each fork skill currently differ by from `v1.3.1`? Tag every divergence by its source (a README-listed divergence, or untracked), and list upstream-only skills, removed skills, and repo-wide upstream conventions. This is the shared fact base for every divergence ticket.

**Method.** `git diff [--word-diff] v1.2.3 v1.3.1 -- <path>` on the upstream clone. `diff -ru` of a `git archive v1.3.1` extract against the fork. `git show v1.2.3:<path> | cmp` for identity checks. Ruby Psych `YAML.safe_load` on every fork frontmatter. No upstream scripts were run. Upstream paths below are `v1.3.1:` unless marked. Fork paths are relative to the repo root.

**Divergence tags.** These are the bullets in README.md "What's changed from Matt's skills":
**CTX** = CONTEXT.md split into domain.md + domain-language.md · **ADR** = removed ADRs · **BDD** = bdd replaces tdd · **FORK** = fork-only skills · **IMPL** = implement is end-to-end · **SPEC** = to-spec grills first · **CR** = code-review refactoring split · **TKT** = to-tickets is tracker-only · **WAY** = wayfinder defers to project docs · **PY** = Python-canonical examples · **OAI** = harness-neutral (no `agents/openai.yaml`) · **untracked** = matches none of these. "#17" marks the agent-agnostic sweep from issue #17. The README does not list that sweep, so #17 items are untracked.

**Cross-cutting fork divergences.** These are not repeated per skill unless a skill differs:
- No `agents/openai.yaml` in any fork skill (`find skills -name openai.yaml` returns 0). Every v1.3.1 skill has one. **cosmetic**, OAI.
- Em-dashes are kept. Fork `skills/` + `README.md` contain 620 `—`. v1.3.1 `skills/engineering` + `skills/productivity` contain 0. **cosmetic**, untracked.
- Cross-skill calls use bare names ("Invoke/Run the `x` skill"). v1.3.1 uses `Call the Skill tool with "x"`. **cosmetic** (harness wording), untracked (#17).
- `argument-hint:` frontmatter on most fork skills. It does not exist in v1.3.1. **cosmetic**, untracked.
- Setup pointers. v1.3.1 says "If not, tell the user to run `/setup-matt-pocock-skills`". The fork says "provided ... by the project's agent docs (e.g. `AGENTS.md` ...)". **behavioural** (different config source), untracked (WAY's idea applied repo-wide).

## 1. Roster

| Status | Skills (fork path ↔ `v1.3.1:` path) |
|---|---|
| Both | `engineering/`: code-review, codebase-design, diagnosing-bugs, domain-modeling, grill-with-docs, implement, improve-codebase-architecture, prototype, research, to-spec, to-tickets, triage, wayfinder, wizard. `productivity/`: grill-me, grilling, handoff, to-questionnaire, wait-what. Mapped pair: fork `engineering/bdd` ~ upstream `engineering/tdd`. |
| Upstream-only (existed at v1.2.3) | `engineering/ask-matt`, `engineering/setup-matt-pocock-skills`, `productivity/teach`, `productivity/writing-for-agents`. `misc/`: git-guardrails-claude-code, migrate-to-shoehorn, scaffold-exercises, setup-pre-commit. |
| Upstream-only (new v1.2.3→v1.3.1) | `engineering/implement-spec` (`24f41cc`), `engineering/pr`, `engineering/retro` (`a7d038f`). All three graduated from in-progress. |
| Fork-only | `engineering/checkout`, `engineering/code-quality`, `engineering/comments`, `engineering/to-idea`, `misc/air-quality-data` [FORK; README lists all except air-quality-data]. |
| Removed upstream | `engineering/resolving-merge-conflicts`, removed in `daa01d8` (v1.3.0): "No longer needed", nothing replaces it. `v1.3.1:docs/engineering/resolving-merge-conflicts.md` stays as an archived page. The fork copy `skills/engineering/resolving-merge-conflicts/SKILL.md` is byte-identical to `v1.2.3:`. |

**In-progress at v1.3.1** (`v1.3.1:skills/in-progress/`). None of these are in the fork: claude-handoff, loop-me, setup-ts-deep-modules, writing-beats, writing-fragments, writing-shape. `skills/deprecated/` holds only a README.

**Invocation parity** (`disable-model-invocation`). Fork and v1.3.1 match for every shared skill except **implement**: it is user-invoked upstream (`v1.3.1:skills/engineering/implement/SKILL.md`) and model-invoked in the fork.

## 2. Shared skills

### bdd ~ tdd
(a) Upstream v1.2.3→v1.3.1 (`v1.3.1:skills/engineering/tdd/SKILL.md`, the only tdd file changed):
- `CONTEXT.md` → `GLOSSARY.md`.
- "use the `/codebase-design` skill" → `call the Skill tool with "codebase-design"`.
- Em-dashes removed.

(b) Fork (`skills/engineering/bdd/`):
- Different name and description (TDD/BDD plus test-review triggers). **behavioural**, BDD.
- Has a Refactor step 4 plus `refactoring.md` (local, under green). Upstream says "Refactoring is not part of the loop" and gives it to `code-review`. **behavioural**, BDD/CR.
- ~200-line Quality Bar: naming, structure, coverage checklist, review examples. **behavioural**, BDD.
- Per-language `mocking-{python,typescript,kotlin}.md` instead of `mocking.md`. **behavioural**, BDD.
- `tests.md` is folded into SKILL.md with Python examples. **behavioural**, PY.
- Reads `domain-language.md`. **behavioural**, CTX.
- No "respect ADRs". **behavioural**, ADR.
- Points to the `code-quality` skill (fork-only) for mockability. **behavioural**, FORK.

(c) Not a copy. It is a rewrite.

### code-review
(a) Upstream:
- Description quoted (`5c89081`, YAML colon fix).
- Setup pointer → "tell the user to run `/setup-matt-pocock-skills`" (`1dab982`).
- Em-dashes removed.

(b) Fork (`skills/engineering/code-review/`):
- Smell list moved into `smells.md`. **behavioural** (the content is the same, the location differs), CR.
- Adds a "whole-diff altitude vs bdd local refactor" framing paragraph. **behavioural**, CR.
- Standards has three ranked sources: AGENTS.md/agent docs → `code-quality` + `bdd` skills → smells. The sub-agent is told to invoke `code-quality`/`bdd`. **behavioural**, untracked (FORK wiring).
- Fetches the spec with a hard-coded `gh issue view <n>`, where upstream uses the `docs/agents/issue-tracker.md` workflow. GitLab `!67` is dropped. **behavioural**, untracked.
- Tracker comes from the project's agent docs. **behavioural**, untracked.
- Folded `>` description, reworded. **cosmetic** (quoting).
- Adds an `# Code Review` H1 and re-wraps lines. **cosmetic**, untracked.

(c) Not a copy.

### codebase-design
(a) Upstream: em-dashes removed in SKILL.md, DEEPENING.md, DESIGN-IT-TWICE.md. DESIGN-IT-TWICE says `GLOSSARY.md`. No behavioural change.

(b) Fork (`skills/engineering/codebase-design/`):
- Python code samples. "TypeScript `interface`" → "`interface`/`Protocol`". **behavioural** (examples), PY.
- DEEPENING.md: PGLite → in-memory SQLite. **behavioural**, PY.
- DEEPENING.md adds a pointer to the `bdd` quality bar. **behavioural**, BDD.
- DESIGN-IT-TWICE: `domain-language.md`. **behavioural**, CTX.
- Intro adds "navigable, for humans and AI alike". **cosmetic**, untracked.
- "subagent" vs upstream "sub-agent". **cosmetic**, untracked.

(c) Effectively a copy, plus PY/CTX substitutions.

### diagnosing-bugs
(a) Upstream:
- `GLOSSARY.md`.
- Phase 6 post-mortem hand-off to `/improve-codebase-architecture` removed. The heading is now "Cleanup" (`1dab982`, #880: a user-invoked skill cannot be called).
- `hitl-loop.template.sh` comment reworded.
- Em-dashes removed.

(b) Fork (`skills/engineering/diagnosing-bugs/`):
- Reads `domain-language.md`. **behavioural**, CTX.
- No ADR check. **behavioural**, ADR.
- `time.perf_counter()`/`cProfile` instead of `performance.now()`. **behavioural**, PY.
- `## Redact` expanded to 4 bullets. The "cannot build a loop" and Phase 1 completion steps repeat "redacted per `## Redact`". **behavioural**, untracked.
- `hitl-loop.template.sh` NOTE expanded ("never for credentials"). **cosmetic** (comment), untracked.
- **Keeps the Phase 6 post-mortem hand-off to `improve-codebase-architecture`**, which is user-invoked in the fork. **behavioural**, untracked (bug, §4).

(c) Not a copy, because of the Redact and Phase 6 differences.

### domain-modeling
(a) Upstream:
- `CONTEXT-FORMAT.md` → `GLOSSARY-FORMAT.md`. CONTEXT/CONTEXT-MAP → GLOSSARY/GLOSSARY-MAP (`d80fa0f`).
- Description → "Use when discussing codebase terminology, writing or editing a GLOSSARY.md, or recording or editing an ADR". The "another skill needs to maintain" caveat was dropped (`54bc6b6`).
- Em-dashes removed. ADR-FORMAT.md is unchanged apart from em-dashes.

(b) Fork (`skills/engineering/domain-modeling/`):
- Rewritten around `domain.md` (map) and `domain-language.md` (language), with routing rules, a no-overlap rule, a subdomain-folder option and a "Reviewing the whole domain" mode. **behavioural**, CTX.
- `ADR-FORMAT.md` and "Offer ADRs sparingly" removed. Decisions go in the GitHub issue. **behavioural**, ADR.
- `domain-language-format.md` replaces `GLOSSARY-FORMAT.md`. **behavioural**, CTX.
- Description keeps "when another skill needs to keep the domain docs current". **behavioural** (trigger), untracked.
- **Description is invalid YAML** (unquoted `: ` inside the plain scalar). **behavioural**, untracked (bug, §4).

(c) Not a copy.

### grill-with-docs
(a) Upstream: the body is now `Call the Skill tool twice, for "grilling" and "domain-modeling".` (`d28dfdc`/`447ca70`). Nothing else changed.

(b) Fork (`skills/engineering/grill-with-docs/SKILL.md`):
- Grilling uses domain-modeling's discipline but writes outcomes to the spec draft. Domain docs are left untouched and reconciled later by `implement`. **behavioural**, CTX/SPEC.
- Publishes the spec only after an explicit user go-ahead, applies the project's "grilled" label and deletes the draft. **behavioural**, SPEC.
- Never applies `ready-for-agent`. **behavioural**, SPEC.
- New description (domain map + glossary, outcomes in the spec). **behavioural**, untracked.

(c) Not a copy.

### implement
(a) Upstream: SKILL.md is unchanged v1.2.3→v1.3.1 (empty diff). It is still a thin user-invoked wrapper that says "Use /tdd ... use /code-review". The parallel case moved to the new `implement-spec`.

(b) Fork (`skills/engineering/implement/`):
- End-to-end flow: `scripts/dispatch.sh` → git worktree → sub-agent (bdd, reconcile domain docs, validate, commit, PR) → top-level `code-review` with findings applied → post-merge cleanup and parent close. **behavioural**, IMPL.
- Model-invoked, with a GitHub-issue trigger description. **behavioural**, IMPL.
- Adds `scripts/` and `evals/`. **behavioural**, IMPL.
- Hard-coded `gh` commands and a `python3` sibling-check snippet. **behavioural**, untracked.
- Reads `docs/domain.md` (step 1) but "Re-read constraints in `docs/agents/domain.md`" (step 2). **behavioural**, untracked (inconsistency, §4).

(c) Not a copy. The fork's flow is closer to v1.3.1 `implement-spec` (worktrees, sub-agents) than to v1.3.1 `implement`.

### improve-codebase-architecture
(a) Upstream:
- `GLOSSARY.md`.
- `/codebase-design`, `/grilling` and `/domain-modeling` → "Call the Skill tool with ..." (4 hits).
- Em-dashes removed in SKILL.md and HTML-REPORT.md (`<title>` became "Architecture review for ...").

(b) Fork (`skills/engineering/improve-codebase-architecture/`):
- `domain-language.md` throughout. **behavioural**, CTX.
- ADRs → "decisions recorded in the project's issues/backlog". "ADR callout" → "Prior-decision callout". A rejection is noted in the backlog, not in an ADR. **behavioural**, ADR.
- YAGNI scoping says "roughly the last ~20 commits" and takes the focus as an argument. Upstream says "a good stretch of the commit history". **behavioural** (minor), untracked.
- "This command" → "This skill". "decision tree" → "design tree". **cosmetic**, untracked.

(c) Effectively a copy, plus CTX/ADR substitutions.

### prototype
(a) Upstream: em-dashes removed in SKILL.md, LOGIC.md and UI.md. No behavioural change.

(b) Fork (`skills/engineering/prototype/`):
- LOGIC.md is an older shape than `v1.2.3:` (it differs from v1.2.3, see `6bcbcb0` "shareable HTML demo"). It is reducer-only `(state, action) => state` with a JS example and fixed steps. Upstream offers reducer, state-machine, pure-function or class shapes, is written for a non-developer, and uses domain-language labels. **behavioural**, untracked.
- LOGIC.md adds a "Python-canonical exception" (translate the reducer). **behavioural**, PY.
- SKILL.md rule 6 and UI.md step 6 pin the branch name `prototype/<name>`, defer issue-pointer mechanics to the agent docs, and leave an AFK verdict placeholder on the issue. Upstream frames this as "primary source" capture. **behavioural**, untracked.
- SKILL.md branch line drops "that a non-developer can drive". **behavioural**, untracked.

(c) Not a copy, because of LOGIC.md.

### research
(a) Upstream: one em-dash removed. Nothing else changed.

(b) Fork (`skills/engineering/research/SKILL.md`):
- Description says "cited Markdown file". **cosmetic**, untracked.
- "Dispatch a **background agent** (a sub-agent run in the background)". **cosmetic** (harness wording), untracked (#17).
- Hard line wrapping. **cosmetic**.

(c) A direct copy.

### to-spec
(a) Upstream:
- Description quoted.
- Setup pointer → "tell the user to run" (`1dab982`).
- Em-dashes removed. It still publishes immediately with `ready-for-agent`.

(b) Fork (`skills/engineering/to-spec/SKILL.md`):
- Writes a local draft. A new step 4 asks "publish now / grill now", and the user must run `grill-with-docs`. **behavioural**, SPEC.
- Publishes with a `spec` label, never `ready-for-agent`. **behavioural**, SPEC.
- No ADRs. **behavioural**, ADR.
- Tracker from agent docs. **behavioural**, untracked.
- Optional topic argument and a "PRD" alias. **behavioural** (minor), untracked.
- New description. **cosmetic**, untracked.

(c) Not a copy.

### to-tickets
(a) Upstream:
- Setup pointer → "tell the user to run".
- Em-dashes removed. Local-file mode is kept. On a real tracker it uses native blocking/sub-issue links where available.

(b) Fork (`skills/engineering/to-tickets/SKILL.md`):
- Local-file mode and `<local-ticket-template>` removed. **behavioural**, TKT.
- Every ticket is a sub-issue, with `Blocked by #<n>` in the body because "GitHub has no native issue-to-issue blocking". **behavioural**, TKT.
- Quiz field "What it delivers" → "User stories covered". **behavioural**, untracked.
- The issue template restores v1.2.x wording: the file-path caveat sits inside "What to build", plus a third criterion stub. **cosmetic**, untracked.
- Ends with "work the frontier ... one ticket at a time with the `implement` skill". **behavioural**, IMPL.
- No ADRs. Tracker from agent docs. **behavioural**, ADR / untracked.

(c) Not a copy.

### triage
(a) Upstream:
- `/grilling` + `/domain-modeling` → `Call the Skill tool twice ...`.
- `GLOSSARY.md`/ADRs.
- Setup pointer → "tell the user to run".
- Em-dashes removed in SKILL.md, AGENT-BRIEF.md and OUT-OF-SCOPE.md.

(b) Fork (`skills/engineering/triage/`):
- Updates `domain-language.md`/`domain.md`, not GLOSSARY/ADRs. No "respecting ADRs". **behavioural**, CTX/ADR.
- Label mapping from agent docs. **behavioural**, untracked.
- `AGENT-BRIEF.md` and `OUT-OF-SCOPE.md` are byte-identical to `v1.2.3:`, so they differ from v1.3.1 only by em-dashes. **cosmetic**.

(c) Effectively a copy, plus CTX/ADR substitutions.

### wayfinder
(a) Upstream:
- 6× "Call the Skill tool ..." wording. Research is "a subagent that calls the Skill tool with "research"".
- Setup pointer → "tell the user to run".
- Em-dashes removed. Research findings still go on a throwaway `research/<name>` branch.

(b) Fork (`skills/engineering/wayfinder/`):
- Blocking is a `Blocked by #x` body convention ("GitHub has no native dependency link"). Upstream uses the tracker's native relationship. **behavioural**, WAY.
- Label strings come from the project's label doc. Falls back to `github-operations.md` (fork-only file). **behavioural**, WAY.
- Charting resolves research tickets inline through `research` into an in-repo Markdown asset (never a `research/<name>` branch), then closes them and records them in the map. **behavioural**, WAY (from #17).
- Adds an "upstream front end to `to-spec`" paragraph, a "Reaching the destination → hand off to the `to-spec` skill" step, and "usually straight to `to-spec`". **behavioural**, untracked (bug, §4).
- Adds the sentence "Plain **ticket** is the everyday word for one hereafter." **cosmetic**, untracked.
- Description em-dash. **cosmetic**.

(c) Not a copy.

### wizard
(a) Upstream: SKILL.md and `template.sh` changed only by em-dash removal. In `template.sh` this touches comments plus the `warn` strings "couldn't open a browser; ..." and "skipped GitHub secret $name: ...". The functional template fixes (`868c4cf`, `49dd158`) are **after** v1.3.1.

(b) Fork (`skills/engineering/wizard/`): SKILL.md and `template.sh` are byte-identical to `v1.2.3:`. The only differences from v1.3.1 are em-dashes and openai.yaml. **cosmetic**, OAI.

(c) A direct copy.

### grill-me
(a) Upstream: "Run a `/grilling` session." → `Call the Skill tool with "grilling".`

(b) Fork (`skills/productivity/grill-me/SKILL.md`):
- "Invoke the `grilling` skill." **cosmetic** (harness wording), untracked (#17).
- `argument-hint`. **cosmetic**.

(c) A direct copy.

### grilling
(a) Upstream:
- Format block now shows two questions separated by `---` (`85f83d3`, #917).
- Em-dashes removed.

(b) Fork (`skills/productivity/grilling/SKILL.md`):
- The body is a separate first-person rewrite ("Interview me ...", "## Each round" steps, "## Facts vs. decisions"). It is neither v1.2.3 nor v1.3.1 text. **behavioural**, untracked.
- Description is software-framed ("plan or design ... before building"). Upstream says "plan, decision, or idea ... stress-test their thinking". **behavioural** (trigger), untracked.
- No `---` separator between questions, and `➡️` sits on the line directly after `❓`. **behavioural** (output format), untracked.
- Facts go to "a background sub-agent". **cosmetic**.

(c) Not a copy.

### handoff
(a) Upstream: the "suggested skills" line → "naming which skills the next agent should call the Skill tool for". The temp-dir resolution change is **after** v1.3.1.

(b) Fork (`skills/productivity/handoff/SKILL.md`):
- "ADRs" → "the domain docs". **behavioural**, ADR/CTX.
- Keeps the v1.2.3 "suggests skills that the agent should invoke" wording. **cosmetic** (harness wording), untracked (#17).

(c) Effectively a copy.

### to-questionnaire
(a) Upstream: em-dashes removed, and one blank line added before step 1.

(b) Fork (`skills/productivity/to-questionnaire/SKILL.md`): byte-identical to `v1.2.3:`, so the differences are em-dashes, the blank line and openai.yaml. **cosmetic**, OAI.

(c) A direct copy.

### wait-what
(a) Upstream:
- Description quoted.
- `GLOSSARY.md` "(follow `GLOSSARY-MAP.md` to the right one if the repo has more than one)" (`d6cd26f`).
- Em-dash removed.

(b) Fork (`skills/productivity/wait-what/SKILL.md`):
- `domain-language.md`. **behavioural**, CTX.
- No multi-file pointer, although fork domain-modeling allows a `domain-language/` folder. **behavioural**, untracked (gap).
- Unquoted description with an em-dash (valid YAML). **cosmetic**.

(c) Effectively a copy, plus the CTX substitution.

## 3. Repo-wide upstream conventions at v1.3.1

| Convention | Source (`v1.3.1:`) | Fork state | Conflicts with fork `scripts/check.sh`? |
|---|---|---|---|
| No em-dashes anywhere. Rewrite each sentence by hand, never blind substitution. | `CLAUDE.md` last paragraph; `3216582` | 620 em-dashes. | No. check.sh does not test em-dashes. |
| Operative cross-skill calls say `Call the Skill tool with "x"`, and `Call the Skill tool twice, for "x" and "y"`. Router prose (ask-matt, bucket READMEs) keeps `/x` labels. 18 hits in 9 promoted SKILL.md files (v1.3.1 `implement` still says `/tdd`, `/code-review`). | `.agents/invocation.md` "Dependencies between them" | Bare backtick names (#17). | **Yes.** Check 1 `VOCAB='Skill tool\|Agent tool\|subagent_type\|runSubagent\|general-purpose'` fails on any ported line. |
| User-invoked carve-out: "a user-invoked skill may invoke model-invoked skills, but it can never reach another user-invoked skill". A precondition becomes "tell the user to run `/x`". | `.agents/invocation.md`; `README.md` §Skills intro | Violated in wayfinder → to-spec and diagnosing-bugs → improve-codebase-architecture (§4). Followed by to-spec → grill-with-docs. | No. |
| User-invoked = `disable-model-invocation: true` + openai.yaml `policy.allow_implicit_invocation: false`. User-invoked descriptions are human-facing, with no trigger lists. Every skill carries `agents/openai.yaml`. | `.agents/invocation.md` | Uses `disable-model-invocation` only. No openai.yaml (OAI). | No (check.sh does not check either). |
| Quote any `description:` containing `: `. | `5c89081` (#911) | domain-modeling is invalid (§4). The rest parse. | No. check.sh does not parse YAML. |
| `CONTEXT.md` → `GLOSSARY.md`, `CONTEXT-MAP.md` → `GLOSSARY-MAP.md`. | `d80fa0f`, `006a52b` | N/A: fork uses domain.md + domain-language.md (CTX). README CTX bullet still names "`CONTEXT.md`". | No. |
| Consumer ADRs live in `docs/adr/` (per-context `src/<ctx>/docs/adr/`). Repo-internal ADRs live in `.agents/adr/0001` (setup pointer only for hard-dependency skills) and `0002` (Claude Code plugin + `marketplace.json`, `claude plugin validate . --strict`). | `skills/engineering/domain-modeling/SKILL.md`; `.agents/adr/` | No ADRs (ADR). README says Matt's ADRs live in "`.agents/adr/`", but that is upstream's own repo ADRs, not what the skills write. | No. |
| `.out-of-scope/` knowledge base: `mainstream-issue-trackers-only.md`, `question-limits.md`, `setup-skill-verify-mode.md`. **No `SCOPE.md` at v1.3.1.** | `.out-of-scope/` | Absent. | No. |
| plugin.json ships exactly the promoted set (engineering + productivity). `misc/`, `in-progress/`, `deprecated/` must not appear in plugin.json or the top-level README. README groups by **User-invoked / Model-invoked**. | `CLAUDE.md`; `.claude-plugin/plugin.json` (27 entries, no misc) | plugin.json and README include `misc/air-quality-data`. README groups by bucket with an "Invoked by" column. | **Yes.** Check 2 requires *every* `skills/*/*/`, misc included, in both plugin.json and README. Upstream policy forbids misc there. Grouping style itself passes. |
| Docs page per promoted skill at `docs/<bucket>/<skill>.md` (What it does / When to reach for it / Common questions / It's working if). Removed skills keep archived pages. | `CLAUDE.md`; `.agents/writing-docs.md` | No `docs/` pages. | No. |
| `AGENTS.md` → symlink to `CLAUDE.md`. Changesets (`.changeset/`) for versioning. "sub-agent" spelling. | repo root | Fork has neither root file nor changesets. It mixes "subagent"/"sub-agent". | No. |

## 4. Known fork bugs and inconsistencies

1. **Invalid YAML.** `skills/engineering/domain-modeling/SKILL.md` description fails Psych: "mapping values are not allowed in this context at line 3 column 78" (the unquoted `` (`domain.md`: modules ``). This is the same bug class upstream fixed in `5c89081`. Every other fork SKILL.md parses.
2. **A model-invoked skill hands off to a user-invoked skill.** `skills/engineering/diagnosing-bugs/SKILL.md` Phase 6: "hand off to the `improve-codebase-architecture` skill", and that skill has `disable-model-invocation: true`. Upstream removed this hand-off in `1dab982` (#880).
3. **A user-invoked skill hands off to a user-invoked skill.** `skills/engineering/wayfinder/SKILL.md` "Reaching the destination → hand off to the `to-spec` skill" (to-spec is `disable-model-invocation: true`). The same text says to-spec "grills and publishes", but fork to-spec drafts locally and does not grill.
4. **Contradiction about domain docs.** `skills/engineering/to-spec/SKILL.md` step 4 says that under `grill-with-docs` "the grilling loop, any inline updates to the draft and the domain docs" happen. `skills/engineering/grill-with-docs/SKILL.md` says to leave the domain docs untouched while grilling.
5. **Wrong invocation label.** `to-spec` step 4 says "do not invoke `grill-with-docs` (or the `grilling` skill) yourself, it is user-triggered". `grilling` is model-invoked in the fork.
6. **Two domain-doc paths.** `skills/engineering/implement/SKILL.md` reads `docs/domain.md` in step 1 and then "Re-read constraints in `docs/agents/domain.md`" in step 2. `skills/engineering/code-quality/SKILL.md:31` also cites `docs/agents/domain.md`.
7. **Stale README claims** (`README.md` "What's changed"):
   - "currently synced to his v1.2.3". Upstream is at v1.3.1.
   - CTX bullet names `CONTEXT.md`. Upstream now uses `GLOSSARY.md`.
   - ADR bullet's `.agents/adr/` location is wrong for consumer ADRs (`docs/adr/`).
   - "Fork-only skills" omits `air-quality-data`, and `resolving-merge-conflicts` is not flagged as removed upstream.
   - The OAI bullet says openai.yaml is "the only remaining difference in ... `wizard` and `to-questionnaire`". That is true against v1.3.1 apart from em-dashes, but both files are v1.2.3 copies.
8. **Unverified premise.** "GitHub has no native blocking/dependency links" (`to-tickets`, `wayfinder`, README WAY bullet) is asserted without a source. Upstream v1.3.1 says to use native blocking where the tracker has it. Not verified here: needs a GitHub-docs research ticket.

## Lead-list items dropped (post-v1.3.1 only, per `git log v1.3.1..origin/main`)

These items from `scratchpad/inventory.md` do not exist at v1.3.1 and are out of this baseline:
- tdd seam catches/misses note (`3f59913`).
- code-review standards-file search and foreground sub-agents (`3da8c01`).
- diagnosing-bugs pristine-copy mutation check (`f3fc563`).
- implement "fetch passed ticket" and Skill-tool wording (`6d6a5b9`, `e48341a`).
- grilling "yes accepts" wording (`95249b0`).
- to-tickets attach-as-sub-issue and drop `## Blocked by` (`cffab50`, `9e2abf8`).
- wayfinder no-triage-labels and real-id rules (`8295b8e`).
- handoff temp-dir resolution (`4f4e943`).
- wizard template.sh fixes (`868c4cf`, `49dd158`).
- `SCOPE.md`, the extra `.out-of-scope/` records, and triage workflows (`f0588cd`, `4d04daa`, `423ed08`).
- in-progress `chief-of-staff`.

## Addendum: v1.3.1 → 49dd158 (official marketplace pin)

Answers #59: what changed between `v1.3.1` (`24fe0ef`) and `49dd158`, the sha the official `claude-plugins-official` listing pins (see `docs/research/overlay-install-mechanics.md` §1.2), for the skills that have keep/drop tickets. No keep/drop calls here.

**Method.** `git log --no-merges v1.3.1..49dd158 -- <path>`, `git diff v1.3.1 49dd158 -- <path>` and `git show 49dd158:<path>` on the upstream clone. The fork side is the working tree at `59100e7`. Upstream line numbers below are `49dd158:`.

**Shape of the delta**
- 46 commits, 34 of them non-merge. 80 files changed, 18 under `skills/` (+127/−47) (`git diff --stat v1.3.1 49dd158`).
- `.claude-plugin/` and `.agents/invocation.md` are byte-identical (`git diff --quiet`). `plugin.json` still says `"1.3.1"`.
- The user-invoked set (`disable-model-invocation: true`) is identical at both refs, so §1 "Invocation parity" stands.
- Every item in "Lead-list items dropped" above is inside the pin (all of its shas are in `v1.3.1..49dd158`).

**Shared skills touched:** code-review, diagnosing-bugs, implement, tdd, to-tickets, wayfinder, wizard (`template.sh` only), grilling, handoff.
**Shared skills not touched** (no file in `git diff --stat`): codebase-design, domain-modeling, grill-with-docs, improve-codebase-architecture, prototype, research, to-spec, triage, grill-me, to-questionnaire, wait-what. One indirect change: triage reads the GitHub tracker template's PR-listing line, which changed (`e0efb6e`, `8e67db2`; see the install doc's addendum).
**Upstream-only skills touched (out of scope):** ask-matt (`954ee7f`), setup-matt-pocock-skills (install doc's addendum), teach (`ad5400b`), in-progress claude-handoff and the new chief-of-staff.

**Verdict key.** **closer** = the change shrinks an existing divergence. **further** = it widens one, on lines the fork already diverges on. **neutral** = it touches lines the fork shares with upstream, so the fork simply lacks the new text (a new, untracked gap).

### A.1 Per shared skill

**bdd ~ tdd**: **neutral**.
- Δ: `3f59913` appends to the seam question: "Give each proposed seam a one-line note on what it catches and what it misses." (`skills/engineering/tdd/SKILL.md:24`).
- Fork: `skills/engineering/bdd/SKILL.md:106` has the same question with no note. That line is not one of the §2 bdd divergences.

**code-review**: **mixed**. The tracker lines move **closer**, the standards and sub-agent lines move **further**.
- Δ `3da8c01`, setup pointer: "If `docs/agents/issue-tracker.md` is missing" → "If not, tell the user to run `/setup-matt-pocock-skills`" (`code-review/SKILL.md:13`). **closer**: like the fork (`skills/engineering/code-review/SKILL.md:33-34`), upstream no longer names a file. It still points at setup, not the agent docs.
- Δ `3da8c01`, spec fetch: "via the workflow in `docs/agents/issue-tracker.md`" → "via the workflow in the tracker doc" (`:29`). **closer** in that the path is gone. The fork's own hard-coded `gh issue view <n>` (`skills/engineering/code-review/SKILL.md:54-55`) and its dropped GitLab `!67` are still divergences.
- Δ `3da8c01`, standards: "Search the repo for every file that documents how code should be written. When `CODING_STANDARDS.md` or `CONTRIBUTING.md` exists, it must be on the list." (`:36`). **further**: the fork names three ranked sources (agent docs → `code-quality`/`bdd` → `smells.md`, `skills/engineering/code-review/SKILL.md:63-78`) and has no repo-wide search.
- Δ `3da8c01`, sub-agents: "Issue both sub-agent calls together, in the foreground, and aggregate the reports they return." (`:60`). **further**: the fork says only "Dispatch the two sub-agents together so they run in parallel" (`skills/engineering/code-review/SKILL.md:82`). Nothing in the fork says foreground.

**diagnosing-bugs**: **neutral**.
- Δ `f3fc563`: step 2 "Watch it fail." gains "If you forced the red by mutating code or a fixture, `diff` against a pristine copy to prove the mutation landed before you trust it." (`diagnosing-bugs/SKILL.md:125`).
- Fork: `skills/engineering/diagnosing-bugs/SKILL.md:129` is the bare "Watch it fail." The §2 divergences (Redact, Phase 6, PY, CTX/ADR) are untouched.

**grilling**: **further**.
- Δ `95249b0` (#706): a new line after the format block: "Word each question so "yes" accepts your recommended answer." (`grilling/SKILL.md:24`).
- Fork: the body is a first-person rewrite with its own round format (`skills/productivity/grilling/SKILL.md:13-21`), and it has no such rule. This adds to the output-format divergence already listed in §2.

**handoff**: **neutral**.
- Δ `4f4e943`, trimmed by `0f5e033`: "temporary directory of the user's OS" gains "(`$TMPDIR`, else `/tmp`; `%TEMP%` on Windows)" (`handoff/SKILL.md:8`).
- Fork: `skills/productivity/handoff/SKILL.md:8` keeps the v1.2.3 wording. The ADR/CTX and suggested-skills differences are unchanged. Still effectively a copy, minus this clause.

**implement**: **closer**, though it is still not a copy.
- Δ `6d6a5b9`: "If the user passes a ticket reference, fetch it from the issue tracker and state its title before starting. If the reference is ambiguous, ask." (`implement/SKILL.md:9`). The fork already fetches the issue (`skills/engineering/implement/SKILL.md:65`, `gh issue view <N> --json number,title,body,comments`).
- Δ `e48341a`, tightened by `04320ee`: "Use /tdd" → `Call the Skill tool with "tdd"`, and "use /code-review" → `call the Skill tool with "code-review"` (`:11`, `:15`). Upstream now invokes test-first and review skills as operative calls, as the fork does ("Invoke the `bdd` skill", `:73`; "invoke the `code-review` skill", `:115`). The wording still differs (Skill tool vs bare name, #17).
- Still user-invoked upstream (`:4`), so the §1 parity exception stands. The end-to-end flow (IMPL) is untouched.

**to-tickets**: **mixed**. Hierarchy moves **closer**, the Blocked-by section moves **further**.
- Δ `cffab50`, then `9e2abf8`, publish bullet: "native blocking / sub-issue relationship" → "native blocking relationship". It adds "If the source was an existing issue, make each ticket its sub-issue (tracker doc's operation)." (`to-tickets/SKILL.md:63`). **closer**: the fork attaches every ticket under the parent as a sub-issue and keeps hierarchy separate from blocking (`skills/engineering/to-tickets/SKILL.md:63`).
- Δ `cffab50`/`9e2abf8`, template: "Omit this section when blockers were set as native edges." (`:101`). **further**: the fork always writes `Blocked by #<n>` in the body because "GitHub has no native issue-to-issue blocking" (`skills/engineering/to-tickets/SKILL.md:63,82-84`).
- Local-file mode is kept upstream (`:62`), so the TKT divergence is unchanged.

**wayfinder**: **mostly neutral**, with one **further**.
- Δ `8295b8e`, labels: "`wayfinder:` labels are the only labels a map and its tickets carry, never a triage label like `ready-for-agent`" (`wayfinder/SKILL.md:65`). **neutral**: the fork's line (`skills/engineering/wayfinder/SKILL.md:68`) matches the v1.3.1 sentence apart from an em-dash. Not in conflict with WAY's label-doc indirection (`:28`).
- Δ `8295b8e`, second pass: "Write cross-references in that pass too, with real ids: a placeholder `#<n>` auto-links to an unrelated issue." (`:114`). **neutral**: fork `:117` is the v1.3.1 text.
- Δ `8295b8e`, research: "Push the branch but open no PR: it is never merged." (`:115`). **further**: upstream doubles down on the throwaway `research/<name>` branch. The fork never uses one and writes an in-repo Markdown asset instead (`skills/engineering/wayfinder/SKILL.md:118`; WAY, #17).
- Δ `8295b8e`, working a ticket: "Resolve it as the type its `wayfinder:<type>` label names ... Read the label, not just the body: the body never states the type." (`:124`). **neutral**: fork `:127` differs from v1.3.1 only in harness wording.

**wizard**: **neutral** by the key, but the net effect matters.
- Δ `868c4cf` and `49dd158`, all in `template.sh` (SKILL.md unchanged):
  - `ask` reads with Readline (`read -e`, `:115`), and `ask`/`ask_secret` fail at EOF.
  - `.env` values are written single-quoted and decoded on re-read.
  - The env file is created at mode 0600 (`umask 077`, `:142`) and written through symlinks.
  - `tput clear` has a fallback.
  - Every stage is wrapped in `run_wizard() { … }; run_wizard "$@"; exit` (`:197-223`), so a mid-run edit cannot break parsing.
- Fork: `skills/engineering/wizard/template.sh` and `SKILL.md` are still byte-identical to `v1.2.3:` (`cmp`). Measured against the pin, the fork's diff goes from cosmetic (em-dashes, OAI) to **behavioural**, untracked.

### A.2 Repo-wide conventions at 49dd158 (changes to §3)

| Change | Source (`49dd158:`) | Bears on |
|---|---|---|
| The Skill-tool convention text is unchanged. `implement` now follows it, so the "(v1.3.1 `implement` still says `/tdd`, `/code-review`)" exception is gone. `Call the Skill tool` lines in promoted SKILL.md files: 14 in 9 files → 16 in 10 (line count with `git grep -c`) | `.agents/invocation.md` (identical); `skills/engineering/implement/SKILL.md:11,15` | §3 row 2. The check.sh `VOCAB` conflict now covers implement too **[inferred]** |
| The em-dash rule is unchanged. New upstream lines carry none | `CLAUDE.md:25` | §3 row 1 unchanged |
| `SCOPE.md` added: the "observed failure" + "fits the philosophy" bar, `misc/` frozen, new skills closed | `SCOPE.md` (`f0588cd`, `4d04daa`) | §3 row 7 ("No `SCOPE.md` at v1.3.1") is v1.3.1-scoped and still true there |
| `.out-of-scope/` gains `frozen-misc-skills`, `harness-name-collisions`, `lazy-load-writing-for-agents`, `native-question-tool`, `new-skills`, `subagent-recursion`. `mainstream-issue-trackers-only` is rewritten to "GitHub, GitLab and local markdown only", with everything else going through **Other** | `.out-of-scope/*` (`f0588cd`, `4d04daa`, `8267225`) | `subagent-recursion.md`: upstream will not add guards that stop sub-agents re-invoking skills, which the fork's Standards sub-agent does with `code-quality`/`bdd`. `harness-name-collisions.md`: see the install doc's addendum |
| Upstream's own `CLAUDE.md` gains an `## Agent skills` → `### Triage labels` block and `docs/agents/triage-labels.md` (canonical names, judged against `SCOPE.md`) | `CLAUDE.md:27-31`; `docs/agents/triage-labels.md` (`f0588cd`) | Repo-internal only: upstream now runs its own setup output |
| `CLAUDE.md`'s install sentence: `marketplace.json` is now the route for "every agent except Claude Code" | `CLAUDE.md:11` (`b0618bc`) | §3 row 6 wording (`marketplace.json`) |
| 15 new `.changeset/*.md`, one per shipped fix. `docs/` pages "unslopped" (`dfe7549`). Issue forms and triage workflows under `.github/` (`f0588cd`, `423ed08`) | repo root | §3 row 10 (changesets) unchanged in kind |

### A.3 Which existing conclusions change

- **Cross-cutting bullets:**
  - "Cross-skill calls use bare names … v1.3.1 uses `Call the Skill tool`": the gap is one skill wider at the pin (implement).
  - "Setup pointers": upstream code-review now uses the same "If not, tell the user to run" form as the other skills, so the fork's agent-docs pointer differs from one uniform upstream pattern.
- **§2 (c) verdicts:**
  - **wizard:** "A direct copy" holds against v1.3.1 but not against the pin. It is now behavioural, because of `template.sh`.
  - **handoff:** still "effectively a copy", minus the temp-dir clause.
  - code-review, implement, to-tickets, wayfinder, grilling, bdd and diagnosing-bugs stay "not a copy".
- **§1 roster and parity:** unchanged. No skill was added to or removed from the promoted set, and the modes are identical.
- **§3:** row 2 loses its implement exception. Rows 7 and 10 gain the items in A.2. No row's "Conflicts with check.sh" answer flips.
- **§4 item 8 (unverified premise):**
  - Upstream still uses GitHub native dependencies for blocking.
  - The pin's GitHub template adds `gh issue create --parent` / `gh issue edit --add-sub-issue` (`gh` 2.94+) (`skills/engineering/setup-matt-pocock-skills/issue-tracker-github.md:10`). That contradicts the fork's "`gh` has no first-class sub-issue command yet" (`skills/engineering/wayfinder/github-operations.md:16-17`).
  - **[verified]** `gh` 2.102.0 (local, 2026-09-30) lists `issue create --parent` and `issue edit --parent / --add-sub-issue / --remove-sub-issue` in `--help`. The fork's "`gh` has no first-class sub-issue command" line is stale.
- **§4 items 1-7 and the README claims:** unchanged. None of them touches the files in the delta. The OAI bullet's "only remaining difference" for `wizard` is now false against the pin, but it was v1.2.3-based anyway.
