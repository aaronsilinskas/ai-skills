"""``kaizen ticket ship``: publish a ticket worktree through its checks, then push and open its
PR."""

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from kaizen.shared.command_records import HomeCommand
from kaizen.shared.comment_only import comment_only_problems
from kaizen.shared.common import RefusalError, Runner, Say, Subparsers, push_rejected
from kaizen.shared.home import Home
from kaizen.shared.leak import leak_check
from kaizen.shared.pr import (
    auto_merge_on,
    closes_issue,
    create_pr,
    disable_auto_merge,
    enable_auto_merge,
    open_pr,
    pr_body,
    read_body,
    update_pr,
)
from kaizen.shared.pr_wait import SHIP_TIMEOUT, ChecksTarget, wait_until_finished
from kaizen.shared.registry import Project
from kaizen.shared.ticket_worktree import (
    TicketWorktree,
    changed_paths,
    file_changes,
    refuse_code_changes,
    refuse_nothing_ahead,
    refuse_spec_ticket,
    refuse_uncommitted,
    resolve_ticket_worktree,
)
from kaizen.ticket.common import open_issue_title


@dataclass(frozen=True)
class Shipped:
    url: str | None
    """The PR's URL; ``None`` after a dry run that would open a new one."""
    github: str
    """The ``owner/repo`` the PR is in."""


class _AutoMerge(NamedTuple):
    enabled: bool
    reason: str
    """The line ``ship`` prints saying whether the PR auto-merges, and why."""


def ship(
    worktree: Path,
    title: str,
    body_file: Path,
    run: Runner,
    *,
    home: Home,
    dry_run: bool = False,
    say: Say = print,
) -> Shipped:
    """Push the ticket branch, then open its PR or update the open one; every check runs first.

    A docs change (no issue) gets no ``Closes`` line, and is refused if it touches code. Its PR
    gets auto-merge when every path it changes is under the project's ``auto_merge_paths``.
    A ticket closing an issue gets it when the home's and the project's ``auto_merge_comment_only``
    are both on and the change is comment-only (``kaizen.shared.comment_only``). Where a ship could
    have enabled auto-merge but does not, it turns auto-merge off on the open PR.
    """
    text = read_body(body_file)
    ticket = resolve_ticket_worktree(worktree, run, home.registry)
    refuse_spec_ticket(ticket)
    project, branch, issue = ticket.project, ticket.branch, ticket.issue
    closes = [] if issue is None or closes_issue(text, project.github, issue) else [issue]
    body = pr_body(title, text, project, home, closes=closes)
    say(f"{project.name} ticket worktree on {branch}")
    refuse_uncommitted(
        ticket, run, fix="commit them (or discard them) so the PR holds everything you tested"
    )
    say("working tree is clean")
    ahead = refuse_nothing_ahead(
        ticket,
        f"origin/{ticket.default_branch}",
        run,
        fix="commit the ticket's work before shipping",
    )
    say(f"{ahead} commit(s) ahead of origin/{ticket.default_branch}")
    if issue is None:
        changed = changed_paths(ticket, run)
        refuse_code_changes(ticket, changed)
        say("docs change: it touches no code path")
        auto_merge = _auto_merge(project, changed)
    else:
        open_issue_title(project.github, issue, run)
        say(f"issue #{issue} is open")
        auto_merge = _comment_only_auto_merge(ticket, home, run)
    reusable = open_pr(project.github, branch, run)
    stale = (
        (issue is None or project.auto_merge_comment_only)
        and reusable is not None
        and not auto_merge.enabled
        and auto_merge_on(reusable, run)
    )
    leak_check(ticket.path, home, run, public=project.public)
    say("leak check found nothing")
    say(auto_merge.reason)

    if dry_run:
        say(f"would push {branch} to origin with -u")
        if reusable:
            say(f"would update the open PR's title and body: {reusable}")
        else:
            say(f"would open a PR into {ticket.default_branch}: {title}")
        if auto_merge.enabled:
            say("would enable auto-merge on the PR")
        elif stale:
            say(f"would turn off auto-merge on the open PR: {reusable}")
        say("would wait until the PR's checks pass and it merges cleanly")
        return Shipped(reusable, project.github)

    _push(ticket, run)
    say(f"pushed {branch} to origin")
    if reusable:
        update_pr(project.github, reusable, title, body, run)
        say(f"updated the open PR's title and body: {reusable}")
        url = reusable
    else:
        url = create_pr(project.github, ticket.default_branch, branch, title, body, run)
        say(f"opened PR: {url}")
    if auto_merge.enabled:
        enable_auto_merge(url, run)
        say(f"enabled auto-merge: {url}")
    elif stale:
        disable_auto_merge(url, run)
        say(f"turned off auto-merge on the open PR: {url}")
    return Shipped(url, project.github)


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "ship",
        help="check a ticket worktree, push its branch and open (or update) its PR",
        description=(
            "Work out the project and issue from the ticket worktree's path and its "
            "fix-<issue>-<slug> branch (or docs-<slug> for a docs change, which has no issue), "
            "check it is safe to publish (the PR title and the exact body it sends, Closes line "
            "and footer included, before any gh call, and the committed files pass the leak "
            "check), push the branch with -u "
            "(never forced; a push rejected because the branch diverged from origin's is "
            "refused, naming the merges that fix it), and open a PR into the default branch, "
            "or reuse the open one and "
            "update its title and body from --title and --body-file. "
            "Prepends 'Closes #<issue>' unless the body already closes the issue with a "
            "GitHub closing keyword (such as 'Fixes #<issue>'), and ends it with the home's PR "
            "footer unless it already does or the footer is empty. A docs change gets no "
            "'Closes' line, and "
            "is refused when its diff against the default branch touches the project's "
            "code_paths. When every path in a docs change is under the project's "
            "auto_merge_paths, enables auto-merge on its PR (gh pr merge --auto --merge). "
            "A ticket closing an issue gets auto-merge when the project sets "
            "auto_merge_comment_only, the home's marker does not set it to false, and every "
            "changed file is an existing Python file whose "
            "code (its syntax tree without docstrings) is unchanged, with the comment and "
            "docstring text across the change no longer than before. When such a ticket no "
            "longer qualifies, ship turns auto-merge off on its open PR. Prints whether "
            "auto-merge is on and why, and the PR URL. Then waits on the PR as `kaizen pr wait` "
            "does, auto-merge or not: the ticket is finished only once its checks pass (or the "
            "repo has no CI workflows) and it merges cleanly, or it merged. Short of that it "
            "prints `not finished: <reason>` on stderr and exits 1 when a check failed or the "
            "PR conflicts with its base (fix it, commit and ship again), or 2 when the wait "
            f"times out after {SHIP_TIMEOUT}s (run `kaizen pr wait <worktree>`); give the shell "
            "call a 10-minute timeout. Refuses a spec's "
            "ticket worktree (spec-<N>-fix-<issue>-<slug>), which `kaizen spec integrate` takes."
        ),
    )
    parser.add_argument("worktree", type=Path, help="the ticket worktree's path")
    parser.add_argument("--title", required=True, help="the PR title (names the change)")
    parser.add_argument("--body-file", type=Path, required=True, help="a file holding the PR body")
    parser.add_argument("--dry-run", action="store_true", help="run only queries; print the plan")
    parser.set_defaults(command=HomeCommand(_command))


def _command(args: argparse.Namespace, run: Runner, home: Home) -> int:
    shipped = ship(args.worktree, args.title, args.body_file, run, home=home, dry_run=args.dry_run)
    if args.dry_run or shipped.url is None:
        return 0
    target = ChecksTarget(shipped.url, shipped.github)
    return wait_until_finished(target, run, wait_again=f"kaizen pr wait {args.worktree}")


def _auto_merge(project: Project, changed: list[str]) -> _AutoMerge:
    """Whether a docs change to the paths *changed* gets auto-merge, and why."""
    if project.auto_merge_paths is None:
        return _AutoMerge(
            False, f"no auto-merge: project {project.name} declares no auto_merge_paths"
        )
    if not changed:
        return _AutoMerge(False, "no auto-merge: the diff changes no path")
    entries = ", ".join(project.auto_merge_paths)
    outside = [path for path in changed if not project.is_auto_merge(path)]
    if outside:
        listed = ", ".join(outside)
        return _AutoMerge(False, f"no auto-merge: outside auto_merge_paths ({entries}): {listed}")
    return _AutoMerge(True, f"auto-merge: every changed path is under auto_merge_paths ({entries})")


def _comment_only_auto_merge(ticket: TicketWorktree, home: Home, run: Runner) -> _AutoMerge:
    """Whether a ticket closing an issue gets auto-merge, and the line saying why."""
    if not home.auto_merge_comment_only:
        return _AutoMerge(False, "no auto-merge: the home turns the comment-only check off")
    if not ticket.project.auto_merge_comment_only:
        return _AutoMerge(False, "no auto-merge: a ticket closing an issue waits for review")
    changes = file_changes(ticket, run)
    if not changes:
        return _AutoMerge(False, "no auto-merge: the diff changes no path")
    problems = comment_only_problems(changes)
    if problems:
        return _AutoMerge(False, "no auto-merge: not comment-only: " + "; ".join(problems))
    return _AutoMerge(
        True, "auto-merge: the change only deletes or shrinks comments and docstrings"
    )


def _push(ticket: TicketWorktree, run: Runner) -> None:
    """Push the ticket branch; a push rejected because the branch diverged is a refusal.

    The push is ship's first change, so a rejected one leaves everything as it was.
    """
    branch, default = ticket.branch, ticket.default_branch
    try:
        run(["git", "-C", str(ticket.path), "push", "-u", "origin", branch])
    except subprocess.CalledProcessError as exc:
        if not push_rejected(exc):
            raise
        raise RefusalError(
            f"git push rejected {branch}: {branch} has diverged from origin/{branch}, "
            "which has commits it lacks (typically after a rebase, or another push)",
            "in the worktree, rejoin the pushed history and catch up by merging, never by "
            f"rebasing or force-pushing: git fetch origin && git merge origin/{branch} && "
            f"git merge origin/{default}, then ship again",
        ) from exc
