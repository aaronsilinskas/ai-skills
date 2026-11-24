"""``kaizen spec integrate``: merge a finished spec ticket into its integration branch behind a
check.

The merge happens in a **scratch worktree** outside the project, so neither the main checkout
nor the ticket worktree is changed by it. The ticket branch is never pushed; only the
integration branch is, and only once the project's check command passes on the merge (ADR 0001).
"""

import argparse
import shlex
import subprocess
from pathlib import Path

from kaizen.shared.branch import integration_branch, integration_merge_message
from kaizen.shared.common import RefusalError, Runner, Say, push_rejected
from kaizen.shared.home import Home
from kaizen.shared.leak import leak_check
from kaizen.shared.registry import (
    NO_CHECK,
    TicketWorktree,
    refuse_nothing_ahead,
    refuse_uncommitted,
    resolve_ticket_worktree,
)
from kaizen.shared.worktree import refuse_hook_inside, scratch_worktree

CHECK_OUTPUT_LINES = 30
"""How much of a failing check's output the refusal shows: enough for pytest's summary."""


def integrate(
    worktree: Path,
    run: Runner,
    *,
    home: Home,
    dry_run: bool = False,
    say: Say = print,
) -> None:
    """Merge, check and push the spec ticket at *worktree*, then remove its worktree and branch."""
    ticket = resolve_ticket_worktree(worktree, run, home.registry)
    if ticket.spec is None:
        kind = "a docs ticket's" if ticket.issue is None else "a lone ticket's"
        raise RefusalError(
            f"{ticket.path} is {kind} worktree (on {ticket.branch}), not a spec's",
            f"ship it with `kaizen ticket ship {ticket.path}`",
        )
    spec, project = ticket.spec, ticket.project
    target = integration_branch(spec)
    say(f"{ticket.path} is {project.name}'s ticket worktree for #{ticket.issue} of spec #{spec}")
    refuse_uncommitted(
        ticket,
        run,
        fix="commit them (or discard them) so the integration holds everything you tested",
    )
    say("worktree is clean")
    ahead = refuse_nothing_ahead(
        ticket, f"origin/{target}", run, fix="commit the ticket's work before integrating it"
    )
    say(f"{ahead} commit(s) ahead of origin/{target}")
    check = project.check
    if check is None:
        raise RefusalError(
            f"project {project.name} declares no check command",
            f"add 'check: <command>' to {project.page}, or 'check: {NO_CHECK}'"
            " if it has nothing to run",
        )
    say(f"check command: {check}")
    checkout = project.main_checkout
    refuse_hook_inside(checkout, ticket.path, run)

    if dry_run:
        say(f"would fetch origin in {checkout}")
        say(f"would merge {ticket.branch} into origin/{target} in a scratch worktree")
        say("would skip the check (none declared)" if check == NO_CHECK else f"would run {check}")
        say("would run the leak check")
        say(f"would push the merge to {target}")
        say(f"would remove worktree {ticket.path} and local branch {ticket.branch}")
        return

    run(["git", "-C", checkout, "fetch", "origin"])
    say(f"fetched origin in {checkout}")
    base = f"origin/{target}"
    with scratch_worktree(checkout, base, run, say, prefix="kaizen-integrate-") as scratch:
        _merge(ticket, spec, scratch, run)
        say(f"merged {ticket.branch} into {base}")
        if check == NO_CHECK:
            say("skipped the check: the project declares none")
        else:
            _run_check(check, scratch, run)
            say(f"check passed: {check}")
        leak_check(scratch, home, run, public=project.public, denied=project.leak_deny, base=base)
        say("leak check found nothing")
        _push(scratch, target, run)
        say(f"pushed the merge to {target}")
    run(["git", "-C", checkout, "worktree", "remove", str(ticket.path)])
    say(f"removed worktree {ticket.path}")
    # Force-delete is safe: the branch is merged into the integration branch just pushed.
    run(["git", "-C", checkout, "branch", "-D", ticket.branch])
    say(f"deleted local branch {ticket.branch}")


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "integrate",
        help="merge a finished spec ticket into its integration branch, check it and push",
        description=(
            "Merge a spec ticket's spec-<N>-fix-<issue>-<slug> branch with --no-ff into "
            "origin/spec-<N> in a scratch worktree (refusing first if the shared pre-commit hook "
            "runs from an interpreter inside the ticket worktree), run the project's check "
            "command there and the leak check, push the merge to spec-<N>, and remove "
            "the ticket worktree and its local branch. The ticket branch is never pushed, and "
            "neither the main checkout nor the ticket worktree is changed by the merge."
        ),
    )
    parser.add_argument(
        "worktree", type=Path, help="the ticket worktree path `kaizen ticket start --spec` printed"
    )
    parser.add_argument("--dry-run", action="store_true", help="run only queries; print the plan")
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    integrate(args.worktree, run, home=home, dry_run=args.dry_run)


def _merge(ticket: TicketWorktree, spec: int, scratch: Path, run: Runner) -> None:
    target = integration_branch(spec)
    message = integration_merge_message(ticket.branch, spec)
    try:
        run(["git", "-C", str(scratch), "merge", "--no-ff", "-m", message, ticket.branch])
    except subprocess.CalledProcessError:
        conflicts = run(["git", "-C", str(scratch), "diff", "--name-only", "--diff-filter=U"])
        if not conflicts.strip():
            raise
        run(["git", "-C", str(scratch), "merge", "--abort"])
        raise RefusalError(
            f"{ticket.branch} conflicts with origin/{target} in:\n{conflicts.rstrip()}",
            f"in {ticket.path}, merge origin/{target} into {ticket.branch} and resolve those"
            f" files, commit, then rerun `kaizen spec integrate {ticket.path}`",
        ) from None


def _run_check(check: str, scratch: Path, run: Runner) -> None:
    # stderr joins stdout in the order written, so installer noise can't bury the failure.
    try:
        run(["sh", "-c", f"(cd {shlex.quote(str(scratch))} && {check}) 2>&1"])
    except subprocess.CalledProcessError as exc:
        output = (exc.output or "").rstrip().splitlines()
        tail = "\n".join(output[-CHECK_OUTPUT_LINES:])
        raise RefusalError(
            f"the check failed on the merged result ({check}):\n{tail}",
            "fix the ticket in its worktree, commit, then rerun `kaizen spec integrate`",
        ) from None


def _push(scratch: Path, target: str, run: Runner) -> None:
    try:
        run(["git", "-C", str(scratch), "push", "origin", f"HEAD:{target}"])
    except subprocess.CalledProcessError as exc:
        if not push_rejected(exc):
            raise
        raise RefusalError(
            f"origin rejected the push: {target} moved since the fetch",
            "rerun `kaizen spec integrate`, which merges and checks against the new tip",
        ) from None
