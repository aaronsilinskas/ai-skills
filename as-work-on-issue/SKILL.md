---
name: as-work-on-issue
description: >
  Implement a GitHub issue end-to-end: fetch the issue, read project context,
  explore code, follow TDD to satisfy all acceptance criteria, validate, commit,
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

## Step 0 — Find the issue (if no number given)

```sh
bash <skill-dir>/scripts/dispatch.sh
```

Use the printed "Next up" number. If unavailable:

```sh
gh issue list --label "ready-for-agent" --state open --json number,title,body
```

Pick the lowest-numbered issue with no open "Blocked by" dependencies.

## Step 0.5 — Set up a git worktree

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

## Step 0.6 — Dispatch to a fresh subagent

Call `runSubagent` with description `"Implement issue #<N>"` and this prompt
(substitute `<N>`, `<owner>/<repo>`, `<repo-root>`, `<worktree-path>`):

---

Implementing GitHub issue #<N> in <owner>/<repo>.
Working directory: <worktree-path> (a git worktree already checked out on branch
issue-<N>-<short-slug>). Stay focused on #<N> only. Do NOT run git checkout or
git worktree commands -- the branch is already set up.

**1. Gather context.** `gh issue view <N> --json number,title,body,comments`.
Read `AGENTS.md`, `docs/agents/domain.md`, `docs/agents/backlog.md` (or
`CLAUDE.md`/`CONTEXT.md`).

**2. Explore.** Find source modules and tests for the acceptance criteria. Note
naming and test conventions. Re-read constraints in `docs/agents/domain.md`.

**3. Implement (TDD).** Branch is already checked out in your working directory. Load the
`tdd` skill (`read_file` its SKILL.md from your skills list) and follow it. If
not available locally, fetch it from
`https://github.com/mattpocock/skills/tree/main/skills/engineering/tdd`.
Do not fix pre-existing bugs.

**4. Review.** Load each skill via `read_file` (paths in your skills list),
apply all fixes to the code, and confirm each finding is resolved before
continuing:

- `as-embedded-dev` — review changed source for correctness, memory safety,
  and hardware constraints. Apply any fixes found.
- `as-test-dev` — review test files for coverage, naming, and behaviour-driven
  structure. Apply any fixes found.

**5. Validate.** `python -m pytest -x -q` then `pre-commit run --all-files`
(or `ruff check . && ruff format .`). Fix all failures.

**6. Commit.** Single commit: `<imperative summary> (closes #<N>)` with key
decisions in the body.

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

Relay the subagent's outcome to the user and stop.
