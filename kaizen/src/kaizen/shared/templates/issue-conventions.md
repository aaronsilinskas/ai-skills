# Issue conventions: GitHub

The commands every home uses on its GitHub issue tracker.
Issues and specs live as GitHub issues in the home's tracker repo, which the home overlay names.
Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: write the body to a file, then run `kaizen issue publish --title "..." --body-file <file> [--label <label>...]`
  from the project's root or a ticket worktree (`--dry-run` first), never a bare `gh issue create`.
  It runs the leak check on the title and body for that project, checks each label exists in its repo, creates the issue there and prints its URL.
- **Read an issue**: `kaizen issue show <ref>` prints its state, labels, parent, open blockers, body and comments (`--json` for fields).
  `<ref>` is `N` or `#N` from the project's root or a ticket worktree, `<project>#N`, or `owner/repo#N` for a registered project's repo; any other repo is refused.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`
  with appropriate `--label` and `--state` filters.
- **Make an issue a sub-issue of a parent**: `kaizen issue link <child> --parent <parent>` (`--dry-run` prints the plan).
  References take the forms `kaizen issue show` accepts, in any of the home's repos; a child that already has a different parent is refused.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation.
  Add edges with `kaizen issue link <child> --blocked-by <ref> [--blocked-by <ref>...]`, which takes `--parent` in the same call and works across the home's repos.
  An edge already present is skipped, so a rerun is safe.
  An issue is unblocked when every blocker is closed.
  A spec's ticket is also unblocked by a blocker already integrated into the spec's branch, so `kaizen spec status <N>` lists its **frontier**.
- **Count open blockers**: `kaizen issue show <ref>` lists the open blockers, in any repo; none means startable.
- **Publish a batch of tickets** (`to-tickets`): write each body to a file and list the tickets in a manifest,
  then run `kaizen ticket publish <manifest.json>` from the project's root (`--dry-run` checks it first).
  It creates them in order under the parent, adds the blocking edges, and prints a read-back table to compare against the approved breakdown.
  If it fails partway, don't rerun it, which would create the tickets again: it prints the issues created so far and the `kaizen issue link` calls that finish them.
  The manifest shape is in `kaizen ticket publish --help`.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: post the explanation with `gh issue comment <number> --body "..."`, then `gh issue close <number>`.
  On an already-closed issue, `gh issue close --comment` drops the comment and still exits 0.

Infer the repo from `git remote -v`; `gh` does this automatically when run inside a clone.

File issues only into the user's own repo.
Never file into `mattpocock/skills` (the repo these skills come from) unless the user owns it.
`kaizen issue publish` always files into the project's registered repo.
For any other `gh` write, note that in a fork `gh` can default to the upstream parent, so before the first one of a session,
check the target with `gh repo view --json nameWithOwner` and confirm it with the user if it is not their repo.

## Issue and pull request numbers

GitHub shares one number space across issues and PRs, so a bare issue number may name an issue or a PR: `kaizen issue show 42` reads an issue and, for a PR, points at `gh pr view 42`.

## When a skill says "publish to the issue tracker" (or "the backlog")

Create a GitHub issue, as in **Create an issue** above.

## When a skill says "fetch the relevant ticket"

Read it as in **Read an issue** above.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets. Labels live in [triage-labels.md](triage-labels.md).

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `kaizen issue publish ... --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (see **Make an issue a sub-issue of a parent**).
  Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`).
  Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: see **Blocking** under Conventions.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues),
  drop any with an open blocker (see **Count open blockers**) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
