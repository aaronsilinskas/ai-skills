---
name: as-work-on-issue
description: >
  Implement a GitHub issue end-to-end: fetch the issue, read project context,
  explore code, follow TDD to satisfy all acceptance criteria, validate, commit,
  and open a PR. Use this skill whenever the user asks to work on a GitHub issue,
  pick up the next ready-for-agent task, implement an issue from the backlog, or
  says anything like "work on #N", "implement issue #N", or "start on the next
  issue".
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

Read the acceptance criteria carefully.  Then explore:

- The source modules the issue mentions or that acceptance-criteria reference
- The existing tests for those modules (look in `tests/` or `**/tests/`)
- Any helpers or fixtures already in test files that are likely to be reused

The goal is to understand existing patterns well enough to write idiomatic code
and tests before writing a single line.

## Step 3 — Implement (TDD)

1. **Write a failing test first.** Run it. Confirm it fails for the right reason.
2. **Implement the minimal change** that makes the test pass.
3. Repeat per acceptance criterion until all are green.

Keep changes minimal and focused. If you discover a pre-existing bug while
working, note it but do not fix it — stay on the assigned issue.

### Constraints to check in `docs/agents/domain.md`

Always re-read the domain constraints section before writing any code. For
Python/CircuitPython projects, common constraints include:

- No `dataclasses`, no generics, no walrus operator
- Wrap typing imports in `try/except ImportError`
- `__slots__` on performance-sensitive classes
- No per-frame heap allocation in hot paths
- Line length and formatter rules (check `pyproject.toml` or the domain doc)

## Step 4 — Validate

All checks must pass before committing. Run the project's test and lint suite:

```sh
# Python projects (adjust paths to match the project)
pytest -x -q
```

If a pre-commit config exists, run it dry to catch formatter/lint issues:

```sh
pre-commit run --all-files
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
