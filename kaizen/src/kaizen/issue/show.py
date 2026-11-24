"""``kaizen issue show``: print one issue whole, with its parent, open blockers and comments."""

import argparse
import json
from typing import Any

from kaizen.shared.common import Runner, Say
from kaizen.shared.home import Home
from kaizen.shared.issue_graph import (
    Issue,
    LinkedIssue,
    body_and_comments_lines,
    open_blockers,
    parent_of,
    parse_ref,
    read_issue,
)
from kaizen.shared.registry import home_repos


def show(
    ref_text: str,
    run: Runner,
    *,
    as_json: bool = False,
    home: Home,
    say: Say = print,
) -> None:
    """Prints the issue *ref_text* names; refuses a pull request or an issue gh can't read."""
    ref = parse_ref(ref_text, run, home.registry)
    issue = read_issue(ref, run)
    parent = parent_of(ref, run)
    blockers = open_blockers(ref, run)
    repos = home_repos(home.registry)
    if as_json:
        say(json.dumps(_as_json(issue, parent, blockers, repos), indent=2))
        return
    state = issue.state
    if issue.state == "closed" and issue.state_reason:
        state += f" ({issue.state_reason})"
    say(f"{ref}, {state}: {issue.title}")
    say(f"labels: {', '.join(issue.labels) or 'none'}")
    say(f"parent: {_linked_line(parent, ref.github, repos) if parent else 'none'}")
    if blockers:
        say("open blockers:")
        for blocker in blockers:
            say(f"  {_linked_line(blocker, ref.github, repos)}")
    else:
        say("open blockers: none")
    for line in body_and_comments_lines(issue):
        say(line)


_OUTSIDE = "an issue outside this home"


def _outside(linked: LinkedIssue, repos: frozenset[str]) -> bool:
    """Whether *linked* is in a repo outside the home's registry, so its repo and title stay
    unprinted (ADR 0002)."""
    return linked.ref.github.lower() not in repos


def _linked_line(linked: LinkedIssue, github: str, repos: frozenset[str]) -> str:
    if _outside(linked, repos):
        return _OUTSIDE
    return f"{linked.ref.short(github)} {linked.title}"


def _linked_json(linked: LinkedIssue, repos: frozenset[str]) -> dict[str, Any]:
    if _outside(linked, repos):
        return {"state": linked.state, "outside_home": True}
    return {
        "repo": linked.ref.github,
        "number": linked.ref.number,
        "title": linked.title,
        "state": linked.state,
        "outside_home": False,
    }


def _as_json(
    issue: Issue, parent: LinkedIssue | None, blockers: list[LinkedIssue], repos: frozenset[str]
) -> dict[str, Any]:
    return {
        "repo": issue.ref.github,
        "number": issue.ref.number,
        "title": issue.title,
        "state": issue.state,
        "state_reason": issue.state_reason,
        "labels": issue.labels,
        "assignees": issue.assignees,
        "parent": _linked_json(parent, repos) if parent else None,
        "open_blockers": [_linked_json(blocker, repos) for blocker in blockers],
        "body": issue.body,
        "comments": [{"author": c.author, "date": c.date, "body": c.body} for c in issue.comments],
    }


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "show",
        help="print one issue whole: header, labels, parent, open blockers, body, comments",
        description=(
            "Print an issue as labelled plain-text sections: its reference, state and title; "
            "labels; parent; open blockers, in any repo (one outside the home's repos prints as "
            "'an issue outside this home', with no repo or title); then the body and every "
            "comment with its author and date, or (no comments). A closed issue prints; a "
            "pull request is refused. It only queries, so it has no --dry-run."
        ),
    )
    parser.add_argument(
        "ref",
        help=(
            "the issue: N or #N in the current project (its main checkout or a ticket worktree), "
            "<project>#N for a registry page, or owner/repo#N for a registered project's repo"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "print the same fields as JSON, with stable names; a linked issue outside the "
            "home has only its state and outside_home: true"
        ),
    )
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    show(args.ref, run, home=home, as_json=args.json)
