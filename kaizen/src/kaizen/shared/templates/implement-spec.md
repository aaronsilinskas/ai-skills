# implement-spec: repo notes

Repo-specific refinements to the `implement-spec` skill. Where a note here differs from the skill, follow the note.

The spec's git lifecycle is `kaizen spec start`, `kaizen ticket start --spec`, `kaizen spec integrate`, `kaizen spec ship` and `kaizen spec finish`, run from the project's root.
Run each as `docs/agents/implement.md` says to run `kaizen`; the integration branch moves only through them.

Implementers build, test and commit inside their ticket worktree, and nothing more: they never push, open a PR or merge. The orchestrator runs every `kaizen spec` command.

An orchestrator running as a subagent keeps its turn open while any implementer runs, and waits on their handbacks with Monitor.
Its turn ends only after the last ticket is integrated, since ending it forces its own handback.

## The main checkout is not the integration base

The main checkout may hold unrelated uncommitted work, and its default branch may lag `origin` until a `finish` command fast-forwards it after a merge; no other `kaizen` command changes it.
Implementers work from the integration branch on `origin`, so read repo files in the ticket's own worktree, not from the main checkout:
an uncommitted draft in the checkout looks committed when read from disk.
Ticket worktrees share refs, and each `kaizen spec integrate` fetches, so `origin/spec-<N>` moves under every running ticket as others integrate, while the worktree's own commits stay put.

## Start the integration branch (skill step 3)

```sh
kaizen spec start <N>
```

It pushes `spec-<N>` to `origin` at the tip of `origin`'s default branch, adding no commit, so a hook or permission rule that reviews each push can approve this one in advance.
`kaizen ticket start --spec` refuses until `spec-<N>` exists, on `origin` or as the local branch `--local` below creates, so no implementer can start before it does.
Where such a hook or rule would hold that push, run `kaizen spec start <N> --local` instead: it creates `spec-<N>` as a local branch from `origin`'s default branch and pushes nothing.
`kaizen ticket start --spec`, `ticket diff` and `ticket compare` then use that local branch while `origin` lacks it, and the spec's first `kaizen spec integrate` pushes it.

There is no draft PR: `kaizen spec ship` opens the PR, ready for review, once the review is done.

## One ticket worktree per implementer (skill step 4)

Launch implementers without `isolation: "worktree"`, which creates worktrees of the repo the session started in, not the project.
Instead start each ticket's worktree yourself and hand the implementer its path:

```sh
kaizen ticket start <project> <issue> --spec <N>
```

It refuses a ticket with an open blocker not yet integrated into `spec-<N>`; integrate the blocker first, or pass `--ignore-blockers` when starting early is intended.
Tell the implementer to work only inside that path and to report done in its handback once its work is committed there.
The skill's "merges the integration branch tip into its own branch before reporting done" is dropped: a refused `integrate` is the only thing that starts a conflict fix.

Each implementer brief also:

- points to the **Seams** note in `docs/agents/implement.md`, which settles the seams `tdd` asks the user to confirm, since an implementer cannot reach the user;
- points to the **Comparing against the base** and **A failing test outside the change** notes there, which settle a failing test with `kaizen ticket compare`, and to its **Review findings** note;
- says to read repo files in its ticket worktree, as **The main checkout is not the integration base** above explains;
- allows the `--dry-run` form of any `kaizen` command, which runs only queries, and any dry-run recipe the home overlay gives.

A ticket that adds a rule to the check command or a hook must pass it across the whole integration branch (`origin/<default>...spec-<N>`), not just on the ticket's diff.
`integrate` runs the check command across that whole branch.
Integrate that ticket first, or put its rule in the brief of every ticket integrated before it.

## Work the frontier (skill steps 4 and 6)

Work the frontier with `kaizen spec status <N>`, run from the project's root.
It prints every ticket with its blockers, integration and ticket worktree, then the **frontier** to launch implementers on, and the held tickets that wait on a person.

## Integrate a finished ticket (skill step 5)

When an implementer reports done, first check any **flaky** or **pre-existing** verdict in its report: rerun each `kaizen ticket compare` command it quotes and confirm the same verdict.
`integrate` runs the check command, so a flaky test there refuses the merge.
File each confirmed one as its own issue; a verdict that doesn't hold up goes back to the implementer as **caused**.
Settle each finding the report marks **blocking** (one where following the spec drops an existing guarantee) before integrating: fix it in the ticket, or ask the user to change the spec.
Then integrate inline:

```sh
kaizen spec integrate <worktree>
```

A refusal names its fix; route the work by who can do it, then rerun `integrate`:

- **Conflict**: send the named files back to the ticket's own implementer, still reachable with `SendMessage`, since it knows the ticket's intent.
  It follows the fix inside its ticket worktree, commits and reports done in its handback, not with `SendMessage`, so your wait on that handback ends.
  Only when that implementer is gone, hand the files and the worktree path to a fresh merger subagent instead.
- **Failing check**, **uncommitted changes** or **no commits ahead**: send the ticket back to its own implementer (a fresh one when it is gone) to fix and commit in the same worktree.
- **Push race**: another ticket was integrated first; just rerun.

## Review and fixes (skill step 7)

Once every ticket is integrated, run `code-review` over `origin/<default branch>...origin/spec-<N>`.
Fixes take the ticket path: start a worktree with `kaizen ticket start <project> <issue> --spec <N>` for the issue whose code the fix touches (an integrated ticket can be started again),
hand it to a fresh implementer, and integrate it as above.
A fix that touches several tickets' code goes on one of their issues with `--slug review-fixes`, so its branch names it as review fixes rather than that ticket's work.

## Ship and finish (skill steps 8 and 9)

Write the PR body with the `pr` skill to a file outside the project, then:

```sh
kaizen spec ship <N> --title "<PR title>" --body-file <file>
```

It adds the `Closes` lines and the home's PR footer, so the body file leaves both out.
Like `kaizen ticket ship`, it then waits for the PR, and a non-zero exit means the spec is unfinished, as `docs/agents/implement.md` describes for a ticket's PR.
On exit 1, fix the failed check or the conflict through a ticket worktree and `kaizen spec integrate`, then ship again; on exit 2, run `kaizen pr wait spec-<N>` from the project's root.
Hand the PR URL to the user once `ship` exits 0.
To change the PR's body later, edit the body file and rerun `kaizen spec ship` with the same `--title`: it updates the open PR and keeps the `Closes` lines.
`integrate` already removed every ticket worktree, so the skill's cleanup waits for the merge.
After the user says the PR merged:

```sh
kaizen spec finish <N>
```
