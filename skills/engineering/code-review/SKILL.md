---
name: code-review
description: >
  Review the changes since a fixed point (commit, branch, tag, or merge-base)
  along two independent axes — Standards (does the code follow this repo's
  documented conventions, the implementation quality bar, and whole-diff
  structural smell checks?) and Spec (does the code do what the originating
  issue/spec asked for?). Runs both as parallel sub-agents and reports them side
  by side. Use when reviewing a branch, a PR, or work-in-progress changes, or
  when asked to "review since X".
argument-hint: "fixed point to review since (commit/branch/tag), optionally the spec/issue"
---

# Code Review

Two-axis review of the diff between `HEAD` and a fixed point the user supplies:

- **Standards** — does the code conform to this repo's conventions, the
  implementation quality bar, and the whole-diff structural smell checks?
- **Spec** — does the code faithfully implement the originating issue /
  spec?

Both axes run as **parallel sub-agents** (via the Agent tool) so they don't
pollute each other's context; this skill then aggregates their findings.

This is the **whole-diff** review altitude. The cheap, local cleanup done
*under green* during a red→green→refactor loop — extract the duplication you
just created, rename what you just realised is misnamed — is the other altitude
and stays in the `bdd` loop. Structural smells that only become visible across a
whole change (shotgun surgery, divergent change, speculative generality) are
this skill's job; see [smells.md](smells.md).

The issue tracker mapping should have been provided by the project's agent docs
(e.g. `AGENTS.md` and the issue/label docs it points to).

## Process

### 1. Pin the fixed point

Whatever the user named is the fixed point — a commit SHA, branch, tag, `main`,
`HEAD~5`. If they didn't give one, ask.

Confirm it resolves (`git rev-parse <fixed-point>`) and the diff is non-empty
**before** spawning anything — a bad ref or empty diff should fail here, not
inside two sub-agents. Capture the commands once:

- Diff: `git diff <fixed-point>...HEAD` (three-dot — against the merge-base)
- Commits: `git log <fixed-point>..HEAD --oneline`

### 2. Identify the spec source

Find the originating spec, in this order:

1. Issue references in the commit messages (`#123`, `Closes #45`) — fetch with
   `gh issue view <n>`.
2. A path the user passed as an argument.
3. A spec file under `docs/`, `specs/`, or `.scratch/` matching the branch
   name or feature.
4. If nothing is found, ask the user where the spec is. If they say there isn't
   one, the **Spec** sub-agent is skipped and the report notes "no spec
   available".

### 3. Identify the standards sources

The Standards axis draws on three sources, in precedence order:

1. **Repo-documented conventions** — `AGENTS.md`/`CLAUDE.md` and the agent docs
   they point to (coding conventions, constraints, runtime/hardware limits).
   These win on any conflict.
2. **The quality-bar skills** — the `code-quality` skill for source and the
   `bdd` skill for tests. The Standards sub-agent invokes them (Skill tool) and
   applies their bars.
3. **The whole-diff smell baseline** — [smells.md](smells.md), a fixed set of
   Fowler smells that applies even when a repo documents nothing.

Two rules bind the smell baseline: a documented repo standard always overrides
it, and every smell is a labelled judgement call ("possible Feature Envy"),
never a hard violation — and skip anything tooling already enforces.

### 4. Spawn both sub-agents in parallel

Send a single message with two `Agent` tool calls. Use `general-purpose` for
both.

**Standards sub-agent** — include:

- The diff command and commit list.
- The repo-documented standards sources from step 3, and the instruction to
  invoke the `code-quality` and `bdd` skills and apply their bars.
- The full contents of [smells.md](smells.md) pasted in — the sub-agent has no
  other access to it.
- The brief: "Report — per file/hunk where relevant — (a) every place the diff
  breaks a documented standard or a quality-bar skill: cite the source (file +
  rule, or skill + rule); and (b) any baseline smell you spot: name it and
  quote the hunk. Distinguish hard violations (documented standards) from
  judgement calls (baseline smells are always judgement calls, and a documented
  repo standard overrides the baseline). Skip anything tooling enforces. Under
  400 words."

**Spec sub-agent** — include:

- The diff command and commit list.
- The path or fetched contents of the spec.
- The brief: "Report: (a) requirements the spec asked for that are missing or
  partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c)
  requirements that look implemented but where the implementation looks wrong.
  Quote the spec line for each finding. Under 400 words."

If the spec is missing, skip the Spec sub-agent and note this in the final
report.

### 5. Aggregate

Present the two reports under `## Standards` and `## Spec` headings, verbatim or
lightly cleaned. Do **not** merge or rerank findings across axes — the two axes
are deliberately separate (see *Why two axes*).

End with a one-line summary: total findings per axis, and the worst issue
_within each axis_ (if any). Don't pick a single winner across axes — that's the
reranking the separation exists to prevent.

## Why two axes

A change can pass one axis and fail the other:

- Code that follows every standard but implements the wrong thing → **Standards
  pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's
  conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other.
