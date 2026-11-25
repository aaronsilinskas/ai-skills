"""``kaizen spec ship``: open a spec's one PR, ready for review, closing every integrated ticket."""

import argparse
from dataclasses import dataclass
from pathlib import Path

from kaizen.shared.branch import (
    find_integration_branch,
    integrated_issues,
    integration_branch,
    remote_default_branch,
)
from kaizen.shared.common import RefusalError, Runner, Say, Subparsers
from kaizen.shared.home import Home
from kaizen.shared.leak import leak_check
from kaizen.shared.pr import create_pr, open_pr, pr_body, read_body, update_pr
from kaizen.shared.registry import resolve_current
from kaizen.spec.common import SubIssue, spec_sub_issues


@dataclass(frozen=True)
class Shipped:
    url: str | None
    """The PR's URL; ``None`` after a dry run that would open a new one."""


def ship(
    spec: int,
    title: str,
    body_file: Path,
    run: Runner,
    *,
    home: Home,
    dry_run: bool = False,
    say: Say = print,
) -> Shipped:
    """Open the PR from spec *spec*'s integration branch, or update the open one.

    Every open sub-issue must be integrated; every check runs before the PR is opened.
    """
    text = read_body(body_file)
    project = resolve_current(run, home.registry)
    # Checks all but the tickets' Closes lines before any gh call; the sub-issues name those.
    pr_body(title, text, project, home, closes=[spec])
    checkout = project.main_checkout
    say(f"{project.name} project at {checkout}")
    branch = integration_branch(spec)
    found = find_integration_branch(checkout, spec, run)
    if found is None:
        raise RefusalError(
            f"origin has no {branch}: spec #{spec} was never started",
            f"start it with `kaizen spec start {spec}` and integrate its tickets first",
        )
    if not found.on_origin:
        raise RefusalError(
            f"origin has no {branch}: spec #{spec} was started with --local and nothing is"
            " integrated yet",
            f"integrate its tickets first with `kaizen spec integrate <ticket-worktree>`, whose"
            f" first run pushes {branch}",
        )
    say(f"origin has {branch}")
    default = remote_default_branch(checkout, run)
    tip = f"origin/{branch}"
    if dry_run:
        say(f"would fetch origin in {checkout}; checking {tip} as last fetched")
    else:
        # Fetching moves only remote-tracking refs, so a refusal after it still changes nothing.
        run(["git", "-C", checkout, "fetch", "origin"])
        say(f"fetched origin in {checkout}")
    closes = _integrated_tickets(project.github, spec, checkout, tip, run, say)
    leak_check(project.path, home, run, tip, public=project.public)
    say(f"leak check found nothing in {tip}")
    body = pr_body(title, text, project, home, closes=[spec, *closes])
    reusable = open_pr(project.github, branch, run)

    if dry_run:
        if reusable:
            say(f"would update the open PR's title and body: {reusable}")
        else:
            say(f"would open a ready PR from {branch} into {default}: {title}")
        return Shipped(reusable)

    if reusable:
        update_pr(project.github, reusable, title, body, run)
        say(f"updated the open PR's title and body: {reusable}")
        return Shipped(reusable)
    url = create_pr(project.github, default, branch, title, body, run)
    say(f"opened PR: {url}")
    return Shipped(url)


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "ship",
        help="open (or update) a spec's PR, closing the spec and its integrated tickets",
        description=(
            "Run from the project's root, after code-review of the integration branch. Check "
            "that origin has spec-<N> and that every open sub-issue of the spec has an "
            "integration merge in origin/spec-<N>'s history (sub-issues closed as not planned "
            "are skipped), run the leak check on the PR title and the exact body it sends, "
            "Closes lines and footer included (all but the tickets' Closes lines before any gh "
            "call, and the whole body again once the sub-issues name them), and on "
            "the integration branch's tip, then open a PR, ready for "
            "review, from spec-<N> into the default branch, or reuse the open one and update its "
            "title and body from --title and --body-file. The body "
            "starts with 'Closes #<spec>' and a 'Closes #<ticket>' line per integrated ticket "
            "and ends with the home's PR footer unless it already does or the footer is empty."
        ),
    )
    parser.add_argument("spec", type=int, help="the spec's issue number")
    parser.add_argument("--title", required=True, help="the PR title (names the change)")
    parser.add_argument("--body-file", type=Path, required=True, help="a file holding the PR body")
    parser.add_argument("--dry-run", action="store_true", help="run only queries; print the plan")
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    ship(args.spec, args.title, args.body_file, run, home=home, dry_run=args.dry_run)


def _integrated_tickets(
    github: str, spec: int, checkout: str, tip: str, run: Runner, say: Say
) -> list[int]:
    """The spec's sub-issues to close; refuses when an open one has no integration merge."""
    merged = integrated_issues(checkout, spec, tip, run)
    sub_issues = spec_sub_issues(github, spec, run)
    missing = [i for i in sub_issues if i.state == "open" and i.number not in merged]
    if missing:
        raise RefusalError(
            f"{tip} has no integration merge for open sub-issue(s): {_names(missing)}",
            "integrate each with `kaizen spec integrate <ticket-worktree>`, or close it as not "
            "planned if it is dropped",
        )
    skipped = [i for i in sub_issues if i.state_reason == "not_planned"]
    if skipped:
        say(f"skipping sub-issue(s) closed as not planned: {_names(skipped)}")
    closes = [i.number for i in sub_issues if i.number in merged and i not in skipped]
    say(f"{len(closes)} integrated ticket(s): " + ", ".join(f"#{n}" for n in closes))
    return closes


def _names(issues: list[SubIssue]) -> str:
    return ", ".join(f"#{i.number} {i.title}" for i in issues)
