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

Implement a single GitHub issue from start to merged PR. Stay focused on the
assigned issue — do not fix unrelated problems or refactor adjacent code.

> **Context isolation:** After identifying the issue number, delegate all
> implementation to a fresh subagent (Step 0.5) so accumulated conversation
> history cannot interfere.

## Step 0 — Find the issue (if no number was given)

If no issue number was provided, run the dispatch script bundled with this
skill to find the next unblocked issue. The script lives at
`scripts/dispatch.sh` inside the skill directory — run it from the repo root:

```sh
bash <skill-dir>/scripts/dispatch.sh
```

Use the issue number it prints as "Next up". If the script is unavailable, list
open issues tagged `ready-for-agent`:

```sh
gh issue list --label "ready-for-agent" --state open --json number,title,body
```

Pick the lowest-numbered unblocked one (check each "Blocked by" section for
still-open issues).

## Step 0.5 — Dispatch to a fresh subagent

Pass all implementation work to a clean subagent so accumulated conversation
context cannot cause skipped steps or incorrect assumptions. Fill in the
placeholders and call `runSubagent`:

- **description**: `"Implement issue #<N>"`
- **prompt** (substitute `<N>`, `<owner>/<repo>`, `<repo-root>`):

---

You are implementing GitHub issue #<N> in <owner>/<repo> (local path:
<repo-root>). Stay focused on #<N> only — do not fix unrelated problems.

**1. Gather context.** `gh issue view <N> --json number,title,body,comments`.
Read: `AGENTS.md`, `docs/agents/domain.md`, `docs/agents/backlog.md` (or
`CLAUDE.md`/`CONTEXT.md` if those don't exist).

**2. Explore.** Find source modules and tests referenced by the acceptance
criteria. Note naming and test-structure conventions before writing any code.
Re-read the constraints section of `docs/agents/domain.md` before implementing.

**3. Implement (TDD).** `git checkout -b issue-<N>-<short-slug>`. Write a
failing test, confirm it fails for the right reason, implement the minimal
change, repeat per acceptance criterion. Use `as-test-dev` skill guidelines.
Do not fix pre-existing bugs.

**4. Review.** Use the `as-embedded-dev` skill to review the implementation for
correctness, memory safety, and hardware constraints. Use the `as-test-dev`
skill to review the tests for coverage, naming, and behaviour-driven structure.
Address any issues before proceeding.

**5. Validate.** `python -m pytest -x -q` then `pre-commit run --all-files`
(or `ruff check . && ruff format .`). Fix every failure before committing.

**6. Commit.** Single focused commit: `<imperative summary> (closes #<N>)`.
Include bullet notes for key decisions in the commit body.

**7. Open a PR.**
Rebase first: `git fetch origin main && git rebase origin/main`.
If conflicts, resolve, stage, `git rebase --continue`, then run tests again.

Push and create the PR as ready (not draft):
`git push -u origin HEAD`
`gh pr create --base main --title "<summary>" --body "..."`

PR body sections: `## Summary`, `## Acceptance criteria` (all satisfied — see
linked issue), `## Key decisions` (non-obvious choices), `## Related` (Closes #<N>).

**8. After PR merges.** `git checkout main && git pull`. Delete the feature
branch. If the issue has a `## Parent` section, list sibling issues:

```sh
gh issue list --state all --json number,title,state,body \
  | python3 -c "
import json, sys
for i in json.load(sys.stdin):
    if '#<parent-N>' in (i.get('body') or ''):
        print(f'#{i[\"number\"]} [{i[\"state\"]}] {i[\"title\"]}')
"
```

If all siblings are closed, verify each parent PRD acceptance criterion against
the codebase, then close:
`gh issue close <parent-N> --reason completed --comment "All child issues merged. [x] <criterion> — <evidence>"`

Report: files changed, PR URL, key decisions, any open questions.

---

After the subagent finishes, relay its outcome to the user and stop.
