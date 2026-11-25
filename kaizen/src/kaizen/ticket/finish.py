"""``kaizen ticket finish``: remove a merged ticket's worktree and local branch."""

import argparse
import subprocess
from pathlib import Path

from kaizen.shared.branch import (
    FAST_FORWARD_HELP,
    MAIN_CHECKOUT_NOTE,
    fast_forward_main_checkout,
    is_ancestor,
    origin_has_branch,
    prune_tracking_ref,
)
from kaizen.shared.command_records import HomeCommand
from kaizen.shared.common import RefusalError, Runner, Say, Subparsers, run_or_refuse
from kaizen.shared.home import Home
from kaizen.shared.pr import PullRequest, merged_pr
from kaizen.shared.ticket_worktree import (
    TicketWorktree,
    refuse_spec_ticket,
    refuse_uncommitted,
    resolve_ticket_worktree,
)
from kaizen.shared.worktree import refuse_hook_inside


def finish(
    worktree: Path,
    run: Runner,
    *,
    home: Home,
    dry_run: bool = False,
    say: Say = print,
) -> None:
    """Remove a merged ticket's worktree and branch (force-delete is safe: nothing is unmerged)."""
    ticket = resolve_ticket_worktree(worktree, run, home.registry)
    refuse_spec_ticket(ticket)
    say(f"{ticket.path} is {ticket.project.name}'s {ticket.label}")
    pr = merged_pr(
        ticket.project.github,
        ticket.branch,
        run,
        ship_fix="ship the ticket with `kaizen ticket ship` and get the PR merged first",
        rerun="kaizen ticket finish",
    )
    say(f"PR #{pr['number']} is merged: {pr['url']}")
    _refuse_unmerged_commits(ticket, pr, run, say)
    refuse_uncommitted(
        ticket,
        run,
        fix="commit and ship them in a new PR, or discard them if they are not wanted",
    )
    say("worktree is clean")
    checkout = ticket.project.main_checkout
    refuse_hook_inside(checkout, ticket.path, run)
    stale = not origin_has_branch(checkout, ticket.branch, run)

    if dry_run:
        say(f"would remove worktree {ticket.path}")
        say(f"would force-delete local branch {ticket.branch}")
        prune_tracking_ref(checkout, ticket.branch, stale, run, dry_run=True, say=say)
        fast_forward_main_checkout(checkout, run, dry_run=True, say=say)
        return

    run(["git", "-C", checkout, "worktree", "remove", str(ticket.path)])
    say(f"removed worktree {ticket.path}")
    run(["git", "-C", checkout, "branch", "-D", ticket.branch])
    say(f"deleted local branch {ticket.branch}")
    prune_tracking_ref(checkout, ticket.branch, stale, run, dry_run=False, say=say)
    fast_forward_main_checkout(checkout, run, dry_run=False, say=say)
    say(MAIN_CHECKOUT_NOTE)


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "finish",
        help="remove a merged ticket's worktree and local branch",
        description=(
            "Check that the branch's PR is merged, that the branch head is the PR's head or an "
            'ancestor of it (the PR gained commits on GitHub, such as from "Update branch"; '
            "the PR's head is fetched from origin to check, even on --dry-run; the fetch moves "
            "no branch), that the worktree is clean, and that the shared pre-commit hook does "
            "not run from an interpreter inside it; "
            "then remove the ticket worktree, force-delete its local branch and prune its "
            "remote-tracking ref once origin no longer has the branch; then "
            f"{FAST_FORWARD_HELP}. Never deletes the remote branch. Works for a "
            "docs change's docs-<slug> branch too. Refuses a spec's ticket worktree "
            "(spec-<N>-fix-<issue>-<slug>), which `kaizen spec integrate` cleans up."
        ),
    )
    parser.add_argument(
        "worktree", type=Path, help="the ticket worktree path `kaizen ticket start` printed"
    )
    parser.add_argument("--dry-run", action="store_true", help="run only queries; print the plan")
    parser.set_defaults(command=HomeCommand(_command))


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    finish(args.worktree, run, home=home, dry_run=args.dry_run)


def _refuse_unmerged_commits(
    ticket: TicketWorktree, pr: PullRequest, run: Runner, say: Say
) -> None:
    """Refuses unless the merged PR's head is the branch head or builds on it, so deleting the
    branch loses no commit."""
    path = str(ticket.path)
    head = run(["git", "-C", path, "rev-parse", "HEAD"]).strip()
    merged_head = pr["headRefOid"]
    if head == merged_head:
        say(f"{ticket.branch} head matches the merged PR's head {merged_head}")
        return
    number = pr["number"]
    run_or_refuse(
        ["git", "-C", path, "fetch", "-q", "origin", f"pull/{number}/head"],
        run,
        f"could not fetch PR #{number}'s head from origin to compare it with {ticket.branch}",
        "check the network and origin, then run `kaizen ticket finish` again",
    )
    try:
        built_on = is_ancestor(path, head, merged_head, run)
    except subprocess.CalledProcessError as exc:
        raise RefusalError(
            f"could not compare {ticket.branch} head {head} with PR #{number}'s head"
            f" {merged_head}: {(exc.stderr or '').strip()}",
            "check that the worktree's repository is intact, then run `kaizen ticket finish` again",
        ) from exc
    if not built_on:
        raise RefusalError(
            f"{ticket.branch} head {head} is not PR #{number}'s head {merged_head} nor an"
            " ancestor of it: the branch has commits the merged PR does not",
            "open a new PR for the extra commits, or drop them if they are not wanted",
        )
    say(
        f"{ticket.branch} head {head} is an ancestor of the merged PR's head {merged_head}:"
        f' PR #{number} gained commits on GitHub (such as from "Update branch")'
        " that the local branch lacks"
    )
