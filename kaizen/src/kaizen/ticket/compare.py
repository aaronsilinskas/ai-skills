"""``kaizen ticket compare``: run a command on a ticket and on its base, and print one verdict.

The base runs in a **scratch worktree** outside the project, so the ticket worktree is never
stashed, reset or switched, and its uncommitted changes take part in the ticket's runs.
"""

import argparse
import shlex
from pathlib import Path
from typing import Literal

from kaizen.shared.command import VERDICT_MEANING, Verdict, run_from, verdict
from kaizen.shared.common import Runner, Say, Subparsers
from kaizen.shared.home import Home
from kaizen.shared.ticket_worktree import base_ref, fetch_base, resolve_ticket_worktree, uncommitted
from kaizen.shared.worktree import link_ignored_paths, scratch_worktree

Side = Literal["ticket", "base"]

DEFAULT_RUNS = 3
"""Runs per side: enough for a flaky failure to show itself."""


def compare(
    worktree: Path,
    command: list[str],
    run: Runner,
    *,
    runs: int = DEFAULT_RUNS,
    home: Home,
    dry_run: bool = False,
    say: Say = print,
) -> Verdict | None:
    """Run *command* *runs* times in the ticket worktree and *runs* times at its base, printing
    each run and the verdict, which it returns (``None`` on a dry run).

    Args:
        worktree: The ticket worktree path.
        command: The argv to run from each worktree's root, through ``sh``.
        run: Runs git and each run of *command*.
        runs: Runs per side.
        home: The home whose registry names the project.
        dry_run: Whether to only print the base and the commands.
        say: Prints each step, run and the verdict.

    A dry run fetches nothing and adds no worktree.
    """
    ticket = resolve_ticket_worktree(worktree, run, home.registry)
    project = ticket.project
    line = shlex.join(command)
    if dry_run:
        base = base_ref(ticket, run)
        say(f"base: {base}")
        say(f"would fetch {base}")
        say(f"would add a scratch worktree at {base}")
        link_ignored_paths(project, Path(), say, dry_run=True)
        say(f"would run {runs} times in {ticket.path}: {line}")
        say(f"would run {runs} times in a scratch worktree at {base}: {line}")
        return None

    base = fetch_base(ticket, run)
    say(f"base: {base}")
    say(f"command: {line}")
    if status := uncommitted(ticket, run):
        say(
            f"note: {ticket.path} has uncommitted changes, which the ticket runs include:\n{status}"
        )
    with scratch_worktree(
        project.main_checkout, base, run, say, prefix="kaizen-ticket-compare-"
    ) as scratch:
        link_ignored_paths(project, scratch, say)
        ticket_passed = _runs("ticket", ticket.path, line, runs, run, say)
        base_passed = _runs("base", scratch, line, runs, run, say)
    outcome = verdict(ticket_passed, base_passed)
    say(f"verdict: {outcome} ({VERDICT_MEANING[outcome]})")
    return outcome


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "compare",
        help="run a command on a ticket and on its base, and print a verdict",
        description=(
            "Fetch only the ticket's base from origin (as `kaizen ticket diff` resolves it), run"
            " the command K times in the ticket worktree, committed and uncommitted changes alike,"
            " then K times in a scratch worktree detached at the base in a temporary directory"
            " outside the project, with the project's worktree_links linked in. The scratch"
            " worktree is removed however the run ends. Prints each run's side, number and exit"
            " code, the tail of each failing run's output, and one verdict: "
            + "; ".join(f"{name} ({meaning})" for name, meaning in VERDICT_MEANING.items())
            + ". Every verdict exits 0."
        ),
    )
    parser.add_argument(
        "worktree", type=Path, help="the ticket worktree path `kaizen ticket start` printed"
    )
    parser.add_argument(
        "--runs",
        type=_positive,
        default=DEFAULT_RUNS,
        metavar="K",
        help=f"runs per side (default {DEFAULT_RUNS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the base and the commands; fetch nothing and add no worktree",
    )
    parser.add_argument(
        "command", nargs="+", help="the command to run from each worktree's root, after `--`"
    )
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    compare(args.worktree, args.command, run, runs=args.runs, home=home, dry_run=args.dry_run)


def _positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"{text} is not a positive number of runs")
    return value


def _runs(side: Side, root: Path, line: str, runs: int, run: Runner, say: Say) -> list[bool]:
    """Run *line* from *root* *runs* times, printing each run; whether each one passed."""
    passed = []
    for number in range(1, runs + 1):
        outcome = run_from(root, line, run)
        say(f"{side} run {number}: exit {outcome.exit_code}")
        if not outcome.passed:
            say("\n".join(f"  {text}" for text in outcome.tail()) or "  (no output)")
        passed.append(outcome.passed)
    return passed
