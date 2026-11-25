"""``kaizen project leak-check``: run the **leak check** on a project's main checkout or ticket
worktree before a push, or on its staged files before a commit."""

import argparse
from pathlib import Path

from kaizen.shared.branch import parse_ticket_branch, remote_default_branch
from kaizen.shared.common import Runner, Say
from kaizen.shared.home import Home
from kaizen.shared.leak import leak_check
from kaizen.shared.registry import (
    Project,
    base_ref,
    resolve_checkout,
    resolve_ticket_worktree,
)


def leak_check_project(
    run: Runner,
    path: Path | None = None,
    *,
    home: Home,
    staged: bool = False,
    say: Say = print,
) -> None:
    """Refuses, listing each offending line, when the tracked files of the checkout at *path*
    (default: the one the command runs in), a project's main checkout or ticket worktree, point
    outside the home; when *staged*, its index instead, the files the next commit records.

    The project's denied patterns are searched on the lines the index adds when *staged*, else
    on those the checkout adds against its base: a spec ticket's integration branch, otherwise
    the default branch, as last fetched."""
    project, checkout = resolve_checkout(run, path, home.registry)
    base = None if staged or not project.leak_deny else _base(project, checkout, run, home.registry)
    leak_check(
        checkout,
        home,
        run,
        public=project.public,
        staged=staged,
        denied=project.leak_deny,
        base=base,
    )
    where = "staged in " if staged else "in "
    say(f"leak check found nothing {where}{project.name} at {checkout}")


def _base(project: Project, checkout: Path, run: Runner, projects_dir: Path) -> str:
    branch = run(["git", "-C", str(checkout), "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if checkout.resolve() == project.path.resolve() or parse_ticket_branch(branch) is None:
        return f"origin/{remote_default_branch(str(checkout), run)}"
    return base_ref(resolve_ticket_worktree(checkout, run, projects_dir), run)


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "leak-check",
        help="run the leak check on the current project or a ticket worktree",
        description=(
            "Run before any push or PR that `kaizen ticket ship` and the `kaizen spec` commands "
            "don't make (they run the check themselves): from the project's root or a ticket "
            "worktree, or pointed at one. Search that checkout's tracked files for text pointing "
            "outside the home (local paths and repos of the home's owners it doesn't register, "
            "and, in a public project, references to the home itself) and refuse, listing each "
            "line with its rule and fix. The project's leak_deny patterns are searched only on "
            "the lines the checkout adds against its base (a spec ticket's integration branch, "
            "else the default branch, as last fetched). It only queries, so it has no --dry-run."
        ),
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="search the index, what the next commit records, instead of the working tree's "
        "tracked files, and the lines it adds for leak_deny patterns: the pre-commit hook's "
        "mode, so a leak is refused before it is committed",
    )
    parser.add_argument(
        "checkout",
        nargs="?",
        type=Path,
        help="a project's main checkout, or a ticket worktree path `kaizen ticket start` printed "
        "(default: the checkout the command runs in)",
    )
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    leak_check_project(run, args.checkout, home=home, staged=args.staged)
