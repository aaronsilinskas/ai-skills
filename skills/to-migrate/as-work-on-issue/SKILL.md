---
name: as-work-on-issue
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

# Work on a GitHub Issue

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
working directory. After the PR is merged, clean up:

```sh
git worktree remove ../<repo-name>-issue-<N>
git branch -d issue-<N>-<short-slug>
```

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
Read `AGENTS.md`, `docs/agents/domain.md`, `docs/agents/backlog.md` (or
`CLAUDE.md`/`CONTEXT.md`).

**2. Explore.** Find source modules and tests for the acceptance criteria. Note
naming and test conventions. Re-read constraints in `docs/agents/domain.md`.

**3. Implement (BDD).** Branch is already checked out in your working directory.
Invoke the `bdd` skill via the Skill tool and follow it. Do not fix
pre-existing bugs.

**4. Self-review.** Invoke each skill below via the Skill tool, apply all fixes
to the code, and confirm each finding is resolved before continuing. This is
your own first pass — a separate fresh reviewer subagent runs after you open
the PR, so be thorough but expect a second set of eyes:

- `code-quality` — review changed source against the general quality bar; it
  loads the matching platform reference (embedded, etc.) as needed. Apply any
  fixes found.
- `bdd` — review test files against the naming/structure/coverage quality
  bar. Apply any fixes found.
- `comments` — review changed code and docstrings for comment discipline
  (naming → test → comment) and correct docstring formatting. Apply any
  fixes found.

**5. Validate.** `python -m pytest -x -q` then `pre-commit run --all-files`
(or `ruff check . && ruff format .`). Fix all failures.

**6. Commit.** Commit all changes with a clear message. If this is the initial
implementation: single commit `<imperative summary> (closes #<N>)` with key
decisions in the body. If this is a follow-up review/fix pass: a new commit on
the same branch (do NOT amend or force-push).

**7. Open a PR.** Rebase: `git fetch origin main && git rebase origin/main`.
Resolve conflicts if any, re-run tests, then:

```sh
git push -u origin HEAD
gh pr create --base main --title "<summary>" --body "..."
```

PR body: `## Summary`, `## Acceptance criteria` (all satisfied), `## Key
decisions`, `## Related` (Closes #<N>).

**8. After merge.** `git checkout main && git pull`, delete the branch. If the
issue has a `## Parent`, check siblings:

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

Report: files changed, PR URL, key decisions, open questions.

---

## Step 4 — Review in a fresh subagent

The implementing subagent reviewed its own work in its self-review (Step 3,
item 4) — but an author reviewing their own tests has a blind spot and tends
to rate them "clean."
After the PR is open, dispatch a **second, fresh** subagent that has never seen
the implementation. Its only job is to review the diff and push fix commits.

Use the Agent tool with description `"Review issue #<N> PR"` and this prompt
(substitute `<N>`, `<worktree-path>`, `<PR-URL>`):

---

Reviewing the open PR for GitHub issue #<N>. Working directory: <worktree-path>
(a git worktree on branch issue-<N>-<short-slug>; the PR is already open at
<PR-URL>). You did NOT write this code — review it with fresh eyes. Do NOT run
git checkout or git worktree commands.

IMPORTANT: Every step is mandatory. Do not skip or paraphrase.

**1. Read the diff.** `git fetch origin main && git diff origin/main...HEAD`.
Read `AGENTS.md` and `docs/agents/domain.md` for project constraints. Read the
issue: `gh issue view <N> --json title,body`.

**2. Review.** Invoke each skill below via the Skill tool, read it entirely, and
apply EVERY finding to the code — confirm each is resolved:

- `code-quality` — changed source: the general quality bar, with the skill
  loading the matching platform reference for correctness, memory safety,
  hot-path allocation, and hardware constraints.
- `bdd` — test files: coverage, naming, behaviour-driven structure, and in
  particular that each test's NAME matches the inputs it fires and the
  assertions it makes (a test named "near zero" must not fire exactly zero).
- `comments` — changed code and docstrings: comment discipline and docstring
  formatting.

If you genuinely find nothing to fix after a thorough pass, say so explicitly
and list what you checked — do not invent trivial changes.

**3. Validate.** `python -m pytest -x -q` then `pre-commit run --all-files`
(or `ruff check . && ruff format .`). Fix all failures.

**4. Commit & push.** If you applied fixes, commit them on the same branch (a
new commit — do NOT amend or force-push) and `git push`. The commit lands on
the open PR automatically.

**5. Report.** List findings applied (or "none, here is what I checked"),
files changed, and any open concerns.

---

Relay both subagents' outcomes to the user and stop.
