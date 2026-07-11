---
name: implement
description: >
  Implement a GitHub issue end-to-end: fetch the issue, read project context,
  explore code, follow BDD to satisfy all acceptance criteria, validate, commit,
  and open a PR. Use this skill whenever the user asks to work on, implement,
  tackle, fix, or close a GitHub issue — even if they just say "work on #N",
  "implement #N", "fix issue #N", "close #N", "tackle #N", or "start on the
  next issue". Also use when the user wants to pick up the next ready-for-agent
  task, grab something from the backlog, or asks "what should I work on next?".
argument-hint: "GitHub issue number (e.g. 12) or leave blank to run dispatch.sh first"
---

# Implement a GitHub Issue

Implement a single GitHub issue from start to merged PR. Stay focused — do not
fix unrelated problems or refactor adjacent code.

> Delegate all implementation to a fresh subagent to avoid context pollution.

## Step 1 — Find the issue (if no number given)

```sh
bash <skill-dir>/scripts/dispatch.sh
```

Use the printed "Next up" number. If unavailable:

```sh
gh issue list --label "ready-for-agent" --state open --json number,title,body
```

Pick the lowest-numbered issue with no open "Blocked by" dependencies.

## Step 2 — Set up a git worktree

Before dispatching, create an isolated worktree for the issue branch so parallel
subagents never conflict on checkouts:

```sh
cd <repo-root>
git fetch origin main
git worktree add ../<repo-name>-issue-<N> -b issue-<N>-<short-slug> origin/main
```

Pass the worktree path (e.g. `../<repo-name>-issue-<N>`) to the subagent as its
working directory. Post-merge cleanup of the worktree and branch happens in
Step 5.

## Step 3 — Implement in a fresh subagent

Use the Agent tool with description `"Implement issue #<N>"` and this prompt
(substitute `<N>`, `<owner>/<repo>`, `<repo-root>`, `<worktree-path>`):

---

Implementing GitHub issue #<N> in <owner>/<repo>.
Working directory: <worktree-path> (a git worktree already checked out on branch
issue-<N>-<short-slug>). Stay focused on #<N> only. Do NOT run git checkout or
git worktree commands -- the branch is already set up.

IMPORTANT: Every numbered step below is mandatory. Do not skip, summarize, or
paraphrase any step. Complete each step fully before moving to the next.

**1. Gather context.** `gh issue view <N> --json number,title,body,comments`.
Read `AGENTS.md`, `docs/domain.md`, `docs/domain-language.md`,
`docs/agents/backlog.md` (or `CLAUDE.md`).

**2. Explore.** Find source modules and tests for the acceptance criteria. Note
naming and test conventions. Re-read constraints in `docs/agents/domain.md`.

**3. Implement (BDD).** Branch is already checked out in your working directory.
Invoke the `bdd` skill via the Skill tool and follow it. Do not fix
pre-existing bugs.

**4. Reconcile the domain docs.** If your changes added, moved, renamed, or
removed a module, key type, or project constraint — or coined or sharpened a
term — invoke the `domain-modeling` skill via the Skill tool and update
`docs/domain.md` and/or `docs/domain-language.md` to match what you built. The
map describes as-built code, so it must reflect this change in the same pass. If
nothing structural or terminological changed, skip this step.

**5. Self-check (light).** You've been applying `bdd`'s local under-green
cleanup as you went. Before opening the PR, skim your changed source and tests
once and fix anything obviously off — a misleading name, dead code, a missing
docstring. Keep it light: the thorough whole-diff review (Standards + Spec) runs
via the `code-review` skill after the PR is open (Step 4).

**6. Validate.** Run the project's tests and pre-commit checks using the exact
commands `AGENTS.md` documents for them (fall back to `CLAUDE.md` if that's
where they live). Fix all failures.

**7. Commit.** Commit all changes with a clear message. If this is the initial
implementation: single commit `<imperative summary> (closes #<N>)` with key
decisions in the body. If this is a follow-up review/fix pass: a new commit on
the same branch (do NOT amend or force-push).

**8. Open a PR.** Rebase: `git fetch origin main && git rebase origin/main`.
Resolve conflicts if any, re-run tests, then:

```sh
git push -u origin HEAD
gh pr create --base main --title "<summary>" --body "..."
```

PR body: `## Summary`, `## Acceptance criteria` (all satisfied), `## Key
decisions`, `## Related` (Closes #<N>).

Report: files changed, PR URL, key decisions, open questions.

---

## Step 4 — Review the PR with `code-review`

After the PR is open, invoke the `code-review` skill via the Skill tool to run
the whole-diff review. `code-review` owns the diff mechanics and spec discovery
— don't restate them here. Only two things are `implement`-specific:

- **Run it at this (top) level, in the worktree (`<worktree-path>`)** — not
  inside the implementing subagent, which can't reliably spawn the parallel
  sub-agents `code-review` uses.
- **Fixed point: `origin/main`.** `code-review` finds the spec itself from the
  `closes #<N>` commit.

`code-review` **reports** findings; it does not apply them. So once it returns,
in the worktree:

1. Apply every finding.
2. Re-run the project's tests and pre-commit checks (per `AGENTS.md`, else
   `CLAUDE.md`); fix all failures.
3. Commit on the same branch — a new commit, no amend or force-push — and
   `git push`; it lands on the open PR.

If `code-review` finds nothing, relay that and what each axis checked.

Relay the implementation and review outcomes to the user and stop.

## Step 5 — After merge

Run this only once the PR is merged. Clean up the worktree, branch, and local
`main`:

```sh
git worktree remove ../<repo-name>-issue-<N>
git checkout main && git pull
git branch -d issue-<N>-<short-slug>
```

Then, if the issue has a `## Parent`, check its siblings:

```sh
gh issue list --state all --json number,title,state,body \
  | python3 -c "
import json, sys
for i in json.load(sys.stdin):
    if '#<parent-N>' in (i.get('body') or ''):
        print(f'#{i[\"number\"]} [{i[\"state\"]}] {i[\"title\"]}')
"
```

If all siblings are closed, close the parent:
`gh issue close <parent-N> --reason completed --comment "All child issues merged. [x] <criterion> — <evidence>"`
