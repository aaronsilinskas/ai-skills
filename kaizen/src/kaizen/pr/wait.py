"""``kaizen pr wait``: block until a PR is finished, then exit by the outcome."""

import argparse
import time
from collections.abc import Callable
from pathlib import Path

from kaizen.shared import pr_wait
from kaizen.shared.command_records import HomeCommand
from kaizen.shared.common import Runner, Say, Subparsers
from kaizen.shared.home import Home
from kaizen.shared.pr_wait import DEFAULT_INTERVAL, DEFAULT_TIMEOUT, ChecksTarget
from kaizen.shared.ticket_worktree import resolve_ticket_worktree


def wait(
    pr: str,
    run: Runner,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    interval: float = DEFAULT_INTERVAL,
    home: Home,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    say: Say = print,
) -> int:
    """Waits on *pr* as ``kaizen.shared.pr_wait.wait`` does, and returns its exit code."""
    target = _resolve(pr, run, home.registry)
    waited = pr_wait.wait(
        target, run, timeout=timeout, interval=interval, sleep=sleep, clock=clock, say=say
    )
    return waited.code


def _resolve(pr: str, run: Runner, projects_dir: Path) -> ChecksTarget:
    """A ticket worktree's path (a directory holding ``.git``) names its branch's PR in its
    project's repo.

    Anything else goes to gh as it is, in the repo of the current directory.
    """
    path = Path(pr).expanduser()
    if (path / ".git").exists():
        ticket = resolve_ticket_worktree(path, run, projects_dir)
        return ChecksTarget(ticket.branch, ticket.project.github)
    return ChecksTarget(pr, None)


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "wait",
        help="block until a PR is finished; exit 0 when its checks pass and it merges cleanly",
        description=(
            "Poll the PR (gh pr view and gh pr checks) until no check is pending, then exit 0 "
            "when every check passed or was skipped, or 1 when any failed or was cancelled, "
            "printing each failing check's link and a `gh run view <run> --log-failed` command "
            "for its logs. Exits 1 at once when the PR conflicts with its base (GitHub runs no "
            "pull_request workflow then) or was closed without merging, and 0 when it merged. "
            "While GitHub is still working out whether the PR merges cleanly, or no check is "
            "reported yet, it keeps waiting, unless the repo has no GitHub Actions workflows, "
            "when a PR that merges cleanly exits 0 with a note. Exits 2 when --timeout passes "
            "first, naming what it still waits on. A refusal (such as a PR gh can't find) "
            "exits 1 with refused: on stderr. Prints a line each time what it waits on changes. "
            f"The default timeout of {DEFAULT_TIMEOUT}s fits inside a 10-minute foreground "
            "agent shell call; raise the call's own timeout above --timeout, or run it in the "
            "background."
        ),
    )
    parser.add_argument(
        "pr",
        help="a PR number, URL or branch in the current directory's repo, or the path of a "
        "ticket worktree from `kaizen ticket start` (its branch's PR in its project's repo)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"seconds to wait in all (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"seconds between polls (default: {DEFAULT_INTERVAL})",
    )
    parser.set_defaults(command=HomeCommand(_command))


def _command(args: argparse.Namespace, run: Runner, home: Home) -> int:
    return wait(args.pr, run, timeout=args.timeout, home=home, interval=args.interval)
