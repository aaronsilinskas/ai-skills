"""``kaizen spec finish``: clean up a spec's integration branch once its PR has merged."""

import argparse

from kaizen.shared.branch import (
    FAST_FORWARD_HELP,
    MAIN_CHECKOUT_NOTE,
    fast_forward_main_checkout,
    integration_branch,
    local_branch_head,
    origin_has_branch,
    prune_tracking_ref,
)
from kaizen.shared.command_records import HomeCommand
from kaizen.shared.common import RefusalError, Runner, Say, Subparsers
from kaizen.shared.home import Home
from kaizen.shared.pr import PullRequest, merged_pr
from kaizen.shared.registry import resolve_current
from kaizen.spec.common import refuse_checked_out, spec_sub_issues


def finish(
    spec: int,
    run: Runner,
    *,
    home: Home,
    dry_run: bool = False,
    say: Say = print,
) -> None:
    """Delete spec *spec*'s local integration branch and stale tracking ref after its PR merged."""
    project = resolve_current(run, home.registry)
    checkout = project.main_checkout
    say(f"{project.name} project at {checkout}")
    branch = integration_branch(spec)
    pr = merged_pr(
        project.github,
        branch,
        run,
        ship_fix=f"open it with `kaizen spec ship {spec}` and get it merged first",
        rerun=f"kaizen spec finish {spec}",
    )
    say(f"PR #{pr['number']} is merged: {pr['url']}")
    local = local_branch_head(checkout, branch, run)
    if local:
        _refuse_unmerged_commits(branch, local, pr)
        say(f"{branch} head matches the merged PR's head {pr['headRefOid']}")
        refuse_checked_out(checkout, branch, run, rerun=f"kaizen spec finish {spec}")
    stale = not origin_has_branch(checkout, branch, run)
    _report_open_sub_issues(project.github, spec, run, say)

    if dry_run:
        if local:
            say(f"would force-delete local branch {branch}")
        prune_tracking_ref(checkout, branch, stale, run, dry_run=True, say=say)
        fast_forward_main_checkout(checkout, run, dry_run=True, say=say)
        return

    if local:
        run(["git", "-C", checkout, "branch", "-D", branch])
        say(f"deleted local branch {branch}")
    else:
        say(f"no local {branch} to delete")
    prune_tracking_ref(checkout, branch, stale, run, dry_run=False, say=say)
    fast_forward_main_checkout(checkout, run, dry_run=False, say=say)
    say(MAIN_CHECKOUT_NOTE)


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "finish",
        help="delete a spec's local integration branch once its PR has merged",
        description=(
            "Run from the project's root after the spec's PR merges. Check that the PR from "
            "spec-<N> is merged and, when a local spec-<N> exists, that its head is the PR's "
            "head and no checkout has it checked out; report the spec's sub-issues still open; "
            "then force-delete the local spec-<N> and prune origin/spec-<N> once origin no "
            f"longer has the branch; last, {FAST_FORWARD_HELP}. Never deletes the remote branch."
        ),
    )
    parser.add_argument("spec", type=int, help="the spec's issue number")
    parser.add_argument("--dry-run", action="store_true", help="run only queries; print the plan")
    parser.set_defaults(command=HomeCommand(_command))


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    finish(args.spec, run, home=home, dry_run=args.dry_run)


def _refuse_unmerged_commits(branch: str, local: str, pr: PullRequest) -> None:
    if local != pr["headRefOid"]:
        raise RefusalError(
            f"{branch} head {local} is not PR #{pr['number']}'s head {pr['headRefOid']}:"
            " the local integration branch has commits the merged PR does not",
            "open a new PR for the extra commits, or drop them if they are not wanted",
        )


def _report_open_sub_issues(github: str, spec: int, run: Runner, say: Say) -> None:
    still_open = [i for i in spec_sub_issues(github, spec, run) if i.state == "open"]
    if still_open:
        names = ", ".join(f"#{i.number} {i.title}" for i in still_open)
        say(f"sub-issue(s) of #{spec} still open: {names}")
    else:
        say(f"no sub-issue of #{spec} is open")
