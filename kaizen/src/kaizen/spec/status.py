"""``kaizen spec status``: a spec's tickets in one table, then its frontier.

The frontier follows the glossary's **Frontier**. A ticket that meets every other condition but
is assigned or labelled ``ready-for-human`` is "held", an output label only. Which blockers
still count is ``TicketBlockers``'s reading, shared with ``kaizen ticket start --spec``.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kaizen.shared.branch import find_integration_branch, integration_branch, parse_ticket_branch
from kaizen.shared.common import Runner, Say, Subparsers
from kaizen.shared.home import Home
from kaizen.shared.issue_graph import IssueRef, LinkedIssue
from kaizen.shared.registry import Project, resolve_current
from kaizen.shared.worktree import list_worktrees
from kaizen.spec.common import (
    SubIssue,
    TicketBlockers,
    fetch_integrated_issues,
    spec_sub_issues,
    ticket_blockers,
)

HUMAN_LABEL = "ready-for-human"


@dataclass(frozen=True)
class Ticket:
    """One sub-issue of the spec, with what the frontier needs to know about it."""

    issue: SubIssue
    blockers: TicketBlockers
    """Its open blockers; none for a closed ticket, whose blockers aren't read."""
    integrated: bool
    worktree: str | None
    """The path of its ticket worktree under the project's worktree root, if it has one."""

    @property
    def blocked(self) -> bool:
        """Whether an open blocker is still to be integrated, or is outside the spec or the
        home."""
        return self.blockers.waiting

    @property
    def skipped(self) -> bool:
        return self.issue.state_reason == "not_planned"

    @property
    def held_reason(self) -> str | None:
        """Why a person holds it: its assignees, the ``ready-for-human`` label, or ``None``."""
        reasons = []
        if self.issue.assignees:
            reasons.append(f"assigned to {', '.join(self.issue.assignees)}")
        if HUMAN_LABEL in self.issue.labels:
            reasons.append(HUMAN_LABEL)
        return "; ".join(reasons) or None


@dataclass(frozen=True)
class Frontier:
    ready: list[Ticket]
    held: list[Ticket]
    none_reason: str | None
    """Why nothing is ready, when nothing is: ``None`` when the frontier has a ticket."""


def status(
    spec: int,
    run: Runner,
    *,
    as_json: bool = False,
    home: Home,
    say: Say = print,
) -> None:
    """Prints spec *spec*'s tickets and its frontier, for the project the command runs in."""
    project = resolve_current(run, home.registry)
    checkout = project.main_checkout
    branch = integration_branch(spec)
    found = find_integration_branch(checkout, spec, run)
    started = found is not None
    integrated = fetch_integrated_issues(checkout, spec, found, run) if found else set()
    tickets = _tickets(project, spec, integrated, home.registry, run)
    frontier = _frontier(tickets)
    if as_json:
        say(json.dumps(_as_json(project.github, spec, started, tickets, frontier), indent=2))
        return
    say(f"{project.name} project at {checkout}")
    if found is not None and not found.on_origin:
        say(f"integration: {branch}, local only until its first integration pushes it")
    elif started:
        say(f"integration: origin/{branch}, {len(integrated)} ticket(s) integrated")
    else:
        say(f"integration: not started (neither origin nor the clone has {branch})")
    say(f"tickets of #{spec}:")
    for line in _table(tickets, project.github, started):
        say(f"  {line}")
    if frontier.none_reason:
        say(f"frontier: none ({frontier.none_reason})")
    else:
        say(f"frontier: {_numbers(frontier.ready)}")
    held = ", ".join(f"#{t.issue.number} ({t.held_reason})" for t in frontier.held)
    say(f"held: {held or 'none'}")


def _tickets(
    project: Project, spec: int, integrated: set[int], projects_dir: Path, run: Runner
) -> list[Ticket]:
    """Each sub-issue of the spec with its open blockers, integration and ticket worktree."""
    worktrees = _ticket_worktrees(project, run)
    tickets = []
    for issue in spec_sub_issues(project.github, spec, run):
        blockers = (
            ticket_blockers(IssueRef(project.github, issue.number), integrated, projects_dir, run)
            if issue.state == "open"
            else TicketBlockers([], set())
        )
        tickets.append(
            Ticket(issue, blockers, issue.number in integrated, worktrees.get(issue.number))
        )
    return tickets


def _frontier(tickets: list[Ticket]) -> Frontier:
    """Sorts the open, unintegrated tickets into ready, held, blocked and in progress."""
    ready: list[Ticket] = []
    held: list[Ticket] = []
    blocked = in_progress = 0
    for ticket in tickets:
        if ticket.issue.state != "open" or ticket.integrated:
            continue
        if ticket.worktree:
            in_progress += 1
        elif ticket.blocked:
            blocked += 1
        elif ticket.held_reason:
            held.append(ticket)
        else:
            ready.append(ticket)
    if ready:
        return Frontier(ready, held, None)
    if not tickets:
        return Frontier(ready, held, "the spec has no sub-issues")
    counts = [(blocked, "blocked"), (in_progress, "in progress"), (len(held), "held")]
    if any(n for n, _ in counts):
        return Frontier(ready, held, ", ".join(f"{n} {what}" for n, what in counts if n))
    if all(ticket.integrated for ticket in tickets):
        return Frontier(ready, held, "all integrated")
    return Frontier(ready, held, "all integrated or closed")


def _ticket_worktrees(project: Project, run: Runner) -> dict[int, str]:
    """Each issue with a ticket worktree directly under the project's worktree root, mapped to
    that worktree's path."""
    root = project.worktree_root.resolve()
    found: dict[int, str] = {}
    for worktree in list_worktrees(project.main_checkout, run):
        if worktree.branch is None or Path(worktree.path).resolve().parent != root:
            continue
        ticket = parse_ticket_branch(worktree.branch)
        if ticket is not None and ticket.issue is not None:
            found[ticket.issue] = worktree.path
    return found


def _table(tickets: list[Ticket], github: str, started: bool) -> list[str]:
    header = ["ticket", "state", "integrated", "worktree", "assignee", "labels", "blockers"]
    rows = [header]
    for t in tickets:
        state = "skipped" if t.skipped else t.issue.state
        integrated = ("yes" if t.integrated else "no") if started else "not-started"
        rows.append(
            [
                f"#{t.issue.number}",
                state,
                integrated,
                "yes" if t.worktree else "no",
                ",".join(t.issue.assignees) or "-",
                ",".join(t.issue.labels) or "-",
                _blockers_cell(t, github),
            ]
        )
    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    titles = ["title", *(t.issue.title for t in tickets)]
    return [
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)) + "  " + title
        for row, title in zip(rows, titles, strict=True)
    ]


def _blockers_cell(ticket: Ticket, github: str) -> str:
    cells = [_blocker_cell(b, ticket, github) for b in ticket.blockers.all_open]
    if outside := ticket.blockers.outside_words:
        cells.append(f"blocked by {outside}")
    return ", ".join(cells) or "-"


def _blocker_cell(blocker: LinkedIssue, ticket: Ticket, github: str) -> str:
    done = "(integrated)" if blocker.ref in ticket.blockers.integrated else ""
    return blocker.ref.short(github) + done


def _numbers(tickets: list[Ticket]) -> str:
    return ", ".join(f"#{t.issue.number}" for t in tickets)


def _as_json(
    github: str, spec: int, started: bool, tickets: list[Ticket], frontier: Frontier
) -> dict[str, Any]:
    return {
        "repo": github,
        "spec": spec,
        "integration_branch": integration_branch(spec),
        "integration_started": started,
        "tickets": [
            {
                "number": t.issue.number,
                "title": t.issue.title,
                "state": t.issue.state,
                "state_reason": t.issue.state_reason,
                "skipped": t.skipped,
                "labels": t.issue.labels,
                "assignees": t.issue.assignees,
                "open_blockers": [
                    {
                        "repo": b.ref.github,
                        "number": b.ref.number,
                        "title": b.title,
                        "state": b.state,
                        "integrated": b.ref in t.blockers.integrated,
                    }
                    for b in t.blockers.all_open
                ],
                "blockers_outside_home": t.blockers.outside,
                "integrated": t.integrated,
                "worktree": t.worktree,
            }
            for t in tickets
        ],
        "frontier": [t.issue.number for t in frontier.ready],
        "held": [{"number": t.issue.number, "reason": t.held_reason} for t in frontier.held],
        "frontier_none_reason": frontier.none_reason,
    }


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "status",
        help="print a spec's tickets and its frontier",
        description=(
            "Run from the project's root. Fetch origin/spec-<N> alone (when origin has it; a "
            "local spec-<N> that `kaizen spec start --local` made, which origin lacks, is read "
            "as it is and counts as started), then "
            "print one row per sub-issue of the spec: reference, state (closed as not planned "
            "shows as skipped), whether it is integrated (an integration merge in "
            "spec-<N>'s history, read as `kaizen spec ship` reads it, or not-started when "
            "neither origin nor the clone has spec-<N>), whether it has a ticket worktree under "
            "the project's "
            "worktree root, assignees, labels, open blockers in the home's repos (one outside "
            "them prints as 'blocked by an issue outside this home', with no repo name, and "
            "counts as open), and title. Then the "
            "frontier on one line in sub-issue order: open tickets not blocked by an open "
            "issue (a blocker already integrated into the spec counts as done), not "
            "integrated, with no ticket worktree, unassigned and not labelled "
            "ready-for-human. A ticket that is only assigned or labelled ready-for-human goes "
            "on the held line with its reason. With no frontier it prints 'frontier: none' "
            "and why. It only queries, so it has no --dry-run."
        ),
    )
    parser.add_argument("spec", type=int, help="the spec's issue number")
    parser.add_argument(
        "--json", action="store_true", help="print the same fields as JSON, with stable names"
    )
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    status(args.spec, run, home=home, as_json=args.json)
