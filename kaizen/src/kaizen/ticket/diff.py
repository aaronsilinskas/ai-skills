"""``kaizen ticket diff``: a ticket's commits, stat and diff against its resolved base."""

import argparse
import subprocess
from pathlib import Path
from typing import Literal, get_args

from kaizen.shared.branch import is_ancestor
from kaizen.shared.command_records import HomeCommand
from kaizen.shared.common import Runner, Say, Subparsers
from kaizen.shared.home import Home
from kaizen.shared.ticket_worktree import fetch_base, resolve_ticket_worktree, uncommitted

Section = Literal["base", "log", "stat"]
"""A section ``kaizen ticket diff`` can print on its own: the base commit, the commits or the
stat."""


def diff(
    worktree: Path,
    run: Runner,
    *,
    only: Section | None = None,
    home: Home,
    say: Say = print,
) -> None:
    """Print a ticket's changes against its base, only querying: the worktree is never changed.

    Args:
        worktree: The ticket worktree path.
        run: Runs git.
        only: Print just this section, unlabelled; the base section is the merge base's SHA.
            ``None`` prints them all: the base ref and its merge base, whether
            it is an ancestor of ``HEAD``, the commits ahead, the stat, the diff and a note
            listing any uncommitted changes.
        home: The home whose registry names the project.
        say: Prints a line.
    """
    ticket = resolve_ticket_worktree(worktree, run, home.registry)
    base = fetch_base(ticket, run)
    git = ["git", "-C", str(ticket.path)]
    if only == "base":
        say(_merge_base(git, base, run))
        return
    queries: dict[Section, list[str]] = {
        "log": [*git, "log", "--oneline", f"{base}..HEAD"],
        "stat": [*git, "diff", "--stat", f"{base}...HEAD"],
    }
    if only is not None:
        say(_body(run(queries[only])))
        return

    changes = [*git, "diff", f"{base}...HEAD"]
    try:
        merge_base = f"merge base {_merge_base(git, base, run)}"
    except subprocess.CalledProcessError as exc:
        if exc.returncode != 1:  # 1 means no common history; anything else is a real failure
            raise
        merge_base = "no merge base: HEAD shares no history with it"
    say(f"base: {base} ({merge_base})")
    say(_ancestry(str(ticket.path), base, run))
    say(f"commits ahead ({base}..HEAD):\n{_body(run(queries['log']))}")
    say(f"stat ({base}...HEAD):\n{_body(run(queries['stat']))}")
    say(f"diff ({base}...HEAD):\n{_body(run(changes))}")
    if status := uncommitted(ticket, run):
        say(
            f"note: {ticket.path} has uncommitted changes, which the commits and diff above"
            f" leave out:\n{status}"
        )


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "diff",
        help="print a ticket's commits, stat and diff against its base",
        description=(
            "Fetch only the ticket's base from origin: origin/spec-<N> for a spec's ticket"
            " (or the local spec-<N>, fetching nothing, while a spec started with"
            " `kaizen spec start --local` has it only locally), else origin/<default branch>."
            " Then print the base ref with its merge base with HEAD (a SHA that stays put"
            " while the base branch moves on, which --base prints alone), whether it is an"
            " ancestor of HEAD (and the merge that fixes it when not), the commits ahead"
            " (base..HEAD), the stat and the diff (base...HEAD), and a note listing any"
            " uncommitted changes. Works for a spec's ticket, a lone ticket or a docs change."
            " Only queries: never"
            " resets or changes the worktree."
        ),
    )
    parser.add_argument(
        "worktree", type=Path, help="the ticket worktree path `kaizen ticket start` printed"
    )
    sections = parser.add_mutually_exclusive_group()
    for section in get_args(Section):
        sections.add_argument(
            f"--{section}",
            dest="only",
            action="store_const",
            const=section,
            help=f"print only {_SECTION_HELP[section]}",
        )
    parser.set_defaults(command=HomeCommand(_command))


_SECTION_HELP: dict[Section, str] = {
    "base": (
        "the merge base of the base and HEAD, a commit SHA that stays put while the base"
        " branch moves on, to run code-review from"
    ),
    "log": "the commits ahead",
    "stat": "the stat",
}


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    diff(args.worktree, run, home=home, only=args.only)


def _merge_base(git: list[str], base: str, run: Runner) -> str:
    return run([*git, "merge-base", base, "HEAD"]).strip()


def _body(text: str) -> str:
    """A section's text without its trailing newline, or ``none`` when it is empty."""
    return text.rstrip("\n") or "none"


def _ancestry(checkout: str, base: str, run: Runner) -> str:
    """Whether *base* is an ancestor of ``HEAD``, with the merge that makes it one when not."""
    if not is_ancestor(checkout, base, "HEAD", run):
        return (
            f"{base} is not an ancestor of HEAD: the base has commits the ticket branch lacks\n"
            f"  fix: merge the base into the ticket branch: `git -C {checkout} merge {base}`"
        )
    return f"{base} is an ancestor of HEAD"
