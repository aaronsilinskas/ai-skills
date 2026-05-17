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

## Step 1 — Gather context

Fetch the full issue:

```sh
gh issue view <N> --json number,title,body,comments
```

Then read whatever agent context the project provides — look for these files
and read every one that exists:

- `AGENTS.md` — tool and workflow conventions
- `docs/agents/domain.md` — module layout, key types, domain vocabulary,
  coding constraints
- `docs/agents/backlog.md` — issue conventions, label meanings

If none of these files exist, look for a `CLAUDE.md`, `CONTEXT.md`, or
`CONTRIBUTING.md` at the repo root instead.

## Step 2 — Explore

Read the acceptance criteria carefully. Then explore:

- The source modules the issue mentions or that acceptance-criteria reference
- The existing tests for those modules (look in `tests/` or `**/tests/`)
- Any helpers or fixtures already in test files that are likely to be reused

The goal is to understand existing patterns well enough to write idiomatic code
and tests before writing a single line. Before moving on, note the conventions
you'll follow — naming style, test structure, file organization — so your
implementation stays consistent with the codebase.

## Step 3 — Implement (TDD)

Create a feature branch before writing any code:

```sh
git checkout -b issue-<N>-<short-slug>
```

1. **Write a failing test first.** Run it. Confirm it fails for the right reason.
   This proves you understand the expected behavior before touching production
   code and gives you a tight feedback loop throughout.
2. **Implement the minimal change** that makes the test pass.
3. Repeat per acceptance criterion until all are green.

Keep changes minimal and focused. If you discover a pre-existing bug while
working, note it but do not fix it — stay on the assigned issue.

For tests, use `as-test-dev` skill guidelines for naming and structure.

### Constraints to check in `docs/agents/domain.md`

Always re-read the domain constraints section before writing any code.

## Step 4 — Validate

All checks must pass before committing. Run the project's test suite first:

```sh
# Python projects (adjust paths to match the project)
pytest -x -q
```

Then run the linter. If a pre-commit config exists, use it:

```sh
pre-commit run --all-files
```

Otherwise fall back to running linters directly:

```sh
ruff check .
mypy .
```

Fix every failure. Do not commit with known failing tests or lint errors.

## Step 5 — Commit

Make a single focused commit that covers only this issue.

Message format:

```
<Short imperative summary> (closes #N)

- <Key decision or non-obvious choice>
- <Files changed and why>
```

## Step 6 — Open a PR

```sh
gh pr create \
  --draft \
  --base main \
  --title "<Short imperative summary>" \
  --body "## Summary

<What was implemented and why.>

## Acceptance criteria

All acceptance criteria from #N are satisfied — see the linked issue.

## Key decisions

<Non-obvious implementation choices.>

## Related

Closes #N"
```

### Resolve conflicts with main

Before marking the PR ready, rebase the branch onto the latest main to ensure
there are no conflicts a reviewer would need to deal with:

```sh
git fetch origin main
git rebase origin/main
```

If the rebase produces conflicts:

1. For each conflicted file, keep **all** of your slice's additions on top of
   whatever main already has. Do **not** drop code that arrived from other
   merged PRs.
2. After resolving each file, stage it with `git add` and continue:
   ```sh
   git rebase --continue
   ```
3. Run the full test suite and linter again to confirm nothing broke.
4. Force-push the rebased branch:
   ```sh
   git push --force-with-lease
   ```

Once the rebase is clean and all checks pass, remove the draft status and
request a review:

```sh
gh pr ready
gh pr edit --add-reviewer <reviewer>
```
