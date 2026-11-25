"""``kaizen ticket abandon``: drop an unmerged ticket's PR, branches and worktree."""

import argparse
import subprocess
from pathlib import Path

from kaizen.shared.branch import is_ancestor, origin_has_branch
from kaizen.shared.command_records import HomeCommand
from kaizen.shared.common import RefusalError, Runner, Say, Subparsers
from kaizen.shared.home import Home
from kaizen.shared.pr import PullRequest, branch_prs
from kaizen.shared.ticket_worktree import (
    TicketWorktree,
    commits_ahead,
    refuse_spec_ticket,
    refuse_uncommitted,
    resolve_ticket_worktree,
)
from kaizen.shared.worktree import list_worktrees, refuse_hook_inside


def abandon(
    worktree: Path,
    run: Runner,
    *,
    home: Home,
    cwd: Path | None = None,
    force: bool = False,
    reason: str | None = None,
    dry_run: bool = False,
    say: Say = print,
) -> None:
    """Close an unmerged ticket's open PR, delete its branches and remove its worktree.

    *cwd* is where the command runs (the process's own by default), which must be outside the
    worktree, since removing a shell's working directory strands it.
    """
    ticket = resolve_ticket_worktree(worktree, run, home.registry)
    refuse_spec_ticket(ticket)
    _refuse_running_inside(ticket, cwd or Path.cwd())
    say(f"{ticket.path} is {ticket.project.name}'s {ticket.label}")
    checkout = ticket.project.main_checkout
    _refuse_locked(ticket, checkout, run)
    refuse_hook_inside(checkout, ticket.path, run)
    open_prs = _unmerged_open_prs(ticket, run)
    if force:
        say("--force: any uncommitted changes in the worktree are discarded")
    else:
        refuse_uncommitted(
            ticket,
            run,
            fix="commit and ship them, or pass --force to discard them with the ticket",
        )
        say("worktree is clean")
    base = f"origin/{ticket.default_branch}"
    ahead = commits_ahead(ticket, base, run)
    commits = "commit" if ahead == 1 else "commits"
    say(f"{ticket.branch} has {ahead} {commits} {base} lacks, dropped with the branch")
    on_origin = origin_has_branch(checkout, ticket.branch, run)
    github = ticket.project.github
    comment = ["--comment", reason] if reason else []
    commented = f" with the comment {reason!r}" if reason else ""
    remove = ["git", "-C", checkout, "worktree", "remove", *(["--force"] if force else [])]

    if dry_run:
        for pr in open_prs:
            say(f"would close PR #{pr['number']}{commented}: {pr['url']}")
        if on_origin:
            say(f"would delete {ticket.branch} on origin")
        say(f"would remove worktree {ticket.path}")
        say(f"would force-delete local branch {ticket.branch}")
        _say_issue_stays_open(ticket, say)
        return

    for pr in open_prs:
        run(["gh", "-R", github, "pr", "close", str(pr["number"]), *comment])
        say(f"closed PR #{pr['number']}{commented}: {pr['url']}")
    if on_origin:
        run(["git", "-C", checkout, "push", "-q", "origin", "--delete", ticket.branch])
        say(f"deleted {ticket.branch} on origin")
    run([*remove, str(ticket.path)])
    say(f"removed worktree {ticket.path}")
    run(["git", "-C", checkout, "branch", "-D", ticket.branch])
    say(f"deleted local branch {ticket.branch}")
    _say_issue_stays_open(ticket, say)


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "abandon",
        help="drop an unmerged ticket: close its PR, delete its branches, remove its worktree",
        description=(
            "Check that the command runs outside the worktree, that the worktree is not "
            "locked, that the shared pre-commit hook does not run from an interpreter inside it, "
            "that the branch builds past every merged PR's head, and that the worktree is "
            "clean (unless --force); then close the branch's open PR, delete the branch on "
            "origin if it is there, remove the ticket worktree and force-delete its local "
            "branch, dropping its commits. The issue stays open. Works for a docs change's "
            "docs-<slug> branch too. Refuses a spec's ticket worktree "
            "(spec-<N>-fix-<issue>-<slug>). If it stops after removing the worktree, a rerun "
            "can't find the ticket: delete the local branch with `git branch -D`."
        ),
    )
    parser.add_argument(
        "worktree", type=Path, help="the ticket worktree path `kaizen ticket start` printed"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="remove the worktree even with uncommitted changes, discarding them",
    )
    parser.add_argument("--reason", help="a comment to post on the PR as it is closed")
    parser.add_argument("--dry-run", action="store_true", help="run only queries; print the plan")
    parser.set_defaults(command=HomeCommand(_command))


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    abandon(
        args.worktree, run, force=args.force, reason=args.reason, home=home, dry_run=args.dry_run
    )


def _refuse_running_inside(ticket: TicketWorktree, cwd: Path) -> None:
    if cwd.expanduser().resolve().is_relative_to(ticket.path):
        raise RefusalError(
            f"the command runs inside the worktree it would remove, {ticket.path}",
            f"run it from the project's root, {ticket.project.main_checkout}",
        )


def _refuse_locked(ticket: TicketWorktree, checkout: str, run: Runner) -> None:
    """Refuses a locked worktree, which ``git worktree remove`` fails on once the PR is closed."""
    for worktree in list_worktrees(checkout, run):
        if worktree.locked and Path(worktree.path).resolve() == ticket.path:
            raise RefusalError(
                f"{ticket.path} is locked",
                f"unlock it with `git -C {checkout} worktree unlock {ticket.path}` if it is"
                " safe to drop, then rerun",
            )


def _unmerged_open_prs(ticket: TicketWorktree, run: Runner) -> list[PullRequest]:
    """The branch's open PRs; refuses unless every merged PR's head is behind the branch head.

    Commits made after a merged PR's head are the ticket's to drop; the merged work is not.
    """
    head = run(["git", "-C", str(ticket.path), "rev-parse", "HEAD"]).strip()
    prs = branch_prs(ticket.project.github, ticket.branch, run)
    for pr in prs:
        if pr["state"] != "MERGED":
            continue
        merged_head = pr["headRefOid"]
        if merged_head == head:
            raise RefusalError(
                f"PR #{pr['number']} ({pr['url']}) merged {ticket.branch} at its head {head}",
                f"clean up a merged ticket with `kaizen ticket finish {ticket.path}`",
            )
        if not _is_ancestor(ticket, merged_head, run):
            raise RefusalError(
                f"PR #{pr['number']} ({pr['url']}) merged {ticket.branch} at {merged_head}, which"
                f" the branch head {head} does not build on",
                f"the ticket's work is merged: run `kaizen ticket finish {ticket.path}`, which"
                f" accepts a branch head the merged PR builds on; if it refuses because the"
                f" branch has commits the PR lacks, bring the branch to the merged head with"
                f" `git -C {ticket.path} fetch origin pull/{pr['number']}/head` and"
                f" `git -C {ticket.path} reset --hard {merged_head}`, then run it again",
            )
    return [pr for pr in prs if pr["state"] == "OPEN"]


def _is_ancestor(ticket: TicketWorktree, commit: str, run: Runner) -> bool:
    """Whether *commit* is in the branch's history; ``False`` for a commit git lacks."""
    try:
        return is_ancestor(str(ticket.path), commit, "HEAD", run)
    except subprocess.CalledProcessError:
        return False


def _say_issue_stays_open(ticket: TicketWorktree, say: Say) -> None:
    if ticket.issue is not None:
        say(f"issue #{ticket.issue} stays open")
