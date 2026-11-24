# Spec tickets integrate locally behind a check, with no per-ticket PRs

A spec's tickets are merged into its integration branch on the user's machine, one at a time in a scratch worktree, and the integration branch is pushed only after the project's check command passes on the merged result.
Ticket branches are never pushed, and no ticket gets its own PR or CI run.
Review runs once over the whole integration branch, and a single PR merges the spec into the default branch, where CI runs.

We chose this for two reasons.
A push to an integration branch triggers no CI, so the local check is the gate that keeps every push green.
And per-ticket PRs cost a push, a PR and remote-branch cleanup for each ticket, for review that already happens over the whole spec.

## Considered Options

- **Per-ticket PRs into the integration branch.**
  Rejected: CI and review per ticket, but every ticket adds remote state to create and clean up, and the review happens again over the whole spec anyway.
- **Pushing ticket branches as a backup, merging locally.**
  Rejected: the remote branches need cleaning up and add nothing the integration branch doesn't already hold once a ticket is integrated.

## Consequences

- Lone tickets and spec tickets take different paths, so `kaizen ticket ship` and `kaizen ticket finish` refuse a spec's ticket and point to `kaizen spec integrate`.
- Every project needs a check command that runs in a fresh worktree, or must declare explicitly that it has none.
