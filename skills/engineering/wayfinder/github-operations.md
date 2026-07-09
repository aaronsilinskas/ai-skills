# Default Wayfinding Operations

The portable fallback for expressing a wayfinder map on a GitHub tracker. **A
project's own tracker doc — its "Wayfinding operations" section — overrides
this.** Use it only when the project hasn't defined one.

Generic issue operations (create, comment, close, label, list) are **not**
redefined here — use whatever the project's tracker/backlog doc prescribes. This
file covers only what's unique to wayfinding: hierarchy, blocking, and the
frontier.

## Hierarchy — map and tickets

- The **map** is one issue carrying the `wayfinder:map` role label.
- Each **ticket** is a child issue attached under the map as a **GitHub
  sub-issue** (hierarchy the tracker renders). `gh` has no first-class sub-issue
  command yet — attach via the GraphQL API (`addSubIssue`) or the map issue's UI
  ("Create sub-issue" / "Add existing issue").
- The map body never re-lists open tickets; they are found by querying the map's
  children.

## Blocking — a body convention

GitHub has no native dependency link, so a ticket declares its blockers in its
body:

```
Blocked by #42, #57
```

A ticket is **unblocked** when every issue it names as a blocker is **closed**.
Wire these edges in a second pass — issues need numbers before they can
reference each other.

## The frontier query

The **frontier** = the map's open children that are unblocked and unassigned:

1. List the map's open sub-issues.
2. Drop any that are **assigned** — an assignee is a claim.
3. Drop any whose `Blocked by #…` line still names an **open** issue.
4. What remains, in issue-number order, is takeable.

## Claim and resolve

- **Claim** a ticket by assigning it to yourself before any work.
- **Resolve** by recording the answer as a comment and closing the issue (per
  the project's tracker doc), then appending a one-line pointer — gist + link,
  never the full answer — to the map's **Decisions so far**.
