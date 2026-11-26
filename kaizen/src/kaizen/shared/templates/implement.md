# implement: repo notes

Repo-specific refinements to the `implement` skill. Where a note here differs from the skill, follow the note.

The ticket's git lifecycle is `kaizen ticket start`, `kaizen ticket ship` and `kaizen ticket finish`; `kaizen ticket abandon` drops an unmerged ticket.
`kaizen ticket <command> --help` is the reference for each; `--dry-run` prints the plan, and a refusal names its fix.

Run each check or test command (the project's check command, `pytest`, `pre-commit`, `mypy`) on its own or chained with `&&`, never piped or after `;`.
Otherwise the shell reports the last command's exit code, and a failed step looks like success.
To shorten its long output, read the exit code first (`cmd; echo "exit=$?"` on its own line), or write the output to a file and read its tail.

`kaizen` ends its stderr with its own exit code, `kaizen: exit <code>`, so `kaizen ... 2>&1 | tail -n <N>` may shorten its output.
A `grep` may filter it too, as long as the pattern keeps `kaizen: exit`.
Never pipe it through `head`, which cuts that line.
A non-zero exit means stop.
`kaizen: exit 1 (refused: nothing changed)` follows a `refused:` message.
`kaizen: exit 1 (failed: ...)` follows `error: <command> failed`: the steps printed above it are done and the rest are not.

## Start: one ticket worktree per ticket

The main checkout may hold other sessions' uncommitted work, and its default branch moves under you as they pull.
So the ticket is built in its own ticket worktree, on a branch from the remote tip, where you stage only your own changes.
Before the first edit:

```sh
kaizen ticket start <project> <issue>
```

`<project>` is a `{{registry}}/` page name.
Its output is the ticket (title, body and comments), so don't fetch the issue again. State the title, as the skill asks.
Do all edits, tests and commits inside the worktree path it prints.
Never run `pre-commit install` in a ticket worktree: the main checkout's install covers every worktree.
Every worktree shares one hook, so an install there points it at that worktree's environment, and every commit fails once the worktree is gone.
`kaizen ticket finish`, `kaizen ticket abandon` and `kaizen spec integrate` refuse to remove a worktree the hook runs from, naming the reinstall command.

After a `warning:` from `start` about a missing `worktree_links` path, or when a check needs a git-ignored tool the worktree lacks, report the check as not run; never pass over it.

### Docs changes: no issue

A change only to docs needs no issue (**Sizing** in `docs/agents/workflows.md`). Start it without one:

```sh
kaizen ticket start <project> --slug <slug>
```

Then edit, commit, and `ship` and `finish` it as below.
It has no code to test and no issue to review against, so `tdd`, the **Seams** note and `code-review` don't apply.
If `ship` refuses it for touching the project's code paths, the change needs an issue: open one and start the ticket with it.
Adding or editing a `{{registry}}/` page is such a change.

## Seams

The issue's acceptance criteria (an agent brief's, when it has one) are the pre-agreed seams `tdd` asks for. Ask about seams only when the issue has no acceptance criteria.

## Domain map

In `docs/domain.md`, give a new module one line on what it is for, plus any constraint an agent must not break; its functions, flags and file mechanics stay in the code and `--help`.

## Comparing against the base

To run a test against the base, never check the base out by hand or `git stash`:

```sh
kaizen ticket compare <worktree> -- <test command>
```

It runs the command 3 times on the ticket (uncommitted changes included) and 3 times on its base, in a scratch worktree it removes, and prints each run and one verdict.
`--dry-run` prints the base and the commands; `--help` gives the verdict rules.

## A failing test outside the change

When a test the change didn't touch fails, settle its verdict before reporting with two `compare` calls: the test alone, and its file.
Report one verdict, quoting each `compare` command and its run lines as evidence.
When the two calls disagree, or one says **passes**, the verdict is **flaky**.

- **caused**: fix it in this ticket.
- **flaky** or **pre-existing**: name the test in the report, so it can be filed as its own issue.

## Review findings

Commit before you review. The skill runs `code-review` before its commit step, but `code-review` reviews commits, so it can't see uncommitted work.
Build and commit, run `code-review` on the commits, then fix its findings in new commits.
Run `code-review` from the commit `kaizen ticket diff <worktree> --base` prints, never a base picked by hand.
It is the merge base of the ticket's base and `HEAD`, a SHA that stays put while other tickets integrate, where a ref such as `origin/spec-<N>` moves on and would take in their work.
`kaizen ticket diff <worktree>` shows the commits, stat and diff it will review, and says when the base is not an ancestor of `HEAD`.

Fix every `code-review` finding in this ticket, including judgement calls and doc or GLOSSARY wording a reviewer marks optional.
Leave a finding only for a stated reason: it is outside the issue's scope, it contradicts the spec or an ADR, or the fix is a refactor larger than the ticket.
List each finding you left in the report, with its reason.
On a spec's ticket, a finding left because the spec says so may still drop a guarantee the code gives, such as atomicity or a safety check.
Watch for these in particular: `refused:` means nothing changed; every check runs before any write; the ticket's branch is never pushed.
Mark such a finding **blocking** in the report, so the orchestrator settles it before the spec merges.

## Ship: commit means commit, push, open a PR

Work lands through a PR, never straight on the default branch; the PR is the hand-off.
The skill's "commit your work to the current branch" lands on the ticket branch.
Before each commit, run the project's checks from the ticket worktree's root.
When the worktree has a `.pre-commit-config.yaml`, run `uv run pre-commit run --files <changed files>`.
Otherwise run the project's check command, the `check:` field of its `{{registry}}/` page, which checks the whole project.
When that field is `none` or missing, skip this step and report the check as not run.
That surfaces lint and type errors while the change is fresh, not one commit attempt at a time.
Then write the PR body with the `pr` skill, using the Write tool, to a file outside the ticket worktree (`ship` refuses a worktree with untracked files), and run:

```sh
kaizen ticket ship <worktree> --title "<PR title>" --body-file <file>
```

The title names the change, not the problem the issue names.
`ship` adds the `Closes` line and the home's PR footer, so the body file leaves both out.
After opening the PR, `ship` waits for it as `kaizen pr wait` does, so give its shell call a 10-minute timeout.
The ticket is finished only when `ship` exits 0: the PR's checks passed (or the repo has no CI) and it merges cleanly with the default branch.
A non-zero exit means the work is unfinished, whatever was pushed: its `not finished:` line says why.
On exit 1 (a failed check, with its log command, or a conflict), fix it, commit, and run `ship` again; never hand back a ticket in that state.
On exit 2 the wait timed out: run `kaizen pr wait <worktree>` until it exits 0 or 1.
Then hand the PR URL it printed to the user.
If `ship` reports auto-merge on, the PR merges itself once its checks pass, and a merge during the wait counts as finished; otherwise the user merges it.
To wait on a PR again, run `kaizen pr wait <worktree>`, never a `gh pr checks` or `gh run watch` loop: `gh pr checks` exits 8 while checks are pending.
It exits 0 when the checks pass (or the repo has no CI) and the PR merges cleanly, and 2 on `--timeout`.
It exits 1 naming each failed check and its log command, or a conflict, or with `refused:`, such as for a PR it can't find.
Give the shell call a timeout above `--timeout` (540 seconds by default), or run it in the background.
After review fixes, update the body file if the change grew, commit, and run `ship` again; it pushes, refreshes the open PR and waits again.

## Finish: after the PR merged

```sh
kaizen ticket finish <worktree>
```
