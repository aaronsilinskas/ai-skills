"""``kaizen project leak-check``: run the **leak check** on a project's main checkout or ticket
worktree before a push, or on its staged files before a commit."""

import argparse
from pathlib import Path

from kaizen.shared.branch import parse_ticket_branch, remote_default_branch
from kaizen.shared.common import RefusalError, Runner, Say, run_or_refuse
from kaizen.shared.home import Home
from kaizen.shared.leak import leak_check
from kaizen.shared.registry import (
    Project,
    base_ref,
    resolve_checkout,
    resolve_home_checkout,
    resolve_ticket_worktree,
)


def leak_check_project(
    run: Runner,
    path: Path | None = None,
    *,
    home: Home,
    staged: bool = False,
    root: Path | None = None,
    say: Say = print,
) -> None:
    """Refuses, listing each offending line, when the tracked files of the checkout at *path*
    (default: the one the command runs in), a project's main checkout or ticket worktree, point
    outside the home; when *staged*, its index instead, the files the next commit records.

    The project's denied patterns are searched on the lines the index adds when *staged*, else
    on those the checkout adds against its base: a spec ticket's integration branch, otherwise
    the default branch, as last fetched.

    Given *root*, the CI form, the checkout is the home's own, at *root* wherever it is, and its
    base is always the default branch, whose history the clone must hold."""
    if root is not None:
        project, checkout = resolve_home_checkout(run, root, home.root, home.registry)
        base = _fetched_default(checkout, run) if project.leak_deny else None
    else:
        project, checkout = resolve_checkout(run, path, home.registry)
        base = (
            None
            if staged or not project.leak_deny
            else _base(project, checkout, run, home.registry)
        )
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


def _fetched_default(checkout: Path, run: Runner) -> str:
    """``origin/<default branch>``, refusing a clone that lacks it or its merge base with
    ``HEAD``, such as a shallow CI clone, so no denied pattern goes unsearched."""
    base = f"origin/{remote_default_branch(str(checkout), run)}"
    run_or_refuse(
        ["git", "-C", str(checkout), "merge-base", base, "HEAD"],
        run,
        f"project leak-check --root: {checkout} lacks {base} or its history with HEAD, which"
        " leak_deny's search needs",
        f"fetch the default branch with its history before the check, such as actions/checkout's"
        f" fetch-depth: 0, or `git fetch origin {base.removeprefix('origin/')}` in a full clone",
    )
    return base


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
            "\n\n"
            "In a home's CI, where the clone is at no registered path, run it as "
            f"`{CI_STEP}` from the clone's root. --root takes the home kaizen serves (KAIZEN_HOME "
            "unset or set to that root, so the marker found there) and refuses any other "
            "checkout; the project is the registry page whose github is origin's repo, so it "
            "needs no main checkout. It runs the same rules on the tracked files, built from the "
            "same home facts, with the clone's root as the home's root; as on any machine, ~ is "
            "the running user's home directory. leak_deny patterns are searched on the lines "
            "the clone adds against the default branch, as last fetched, and a clone lacking "
            "that branch or its history with HEAD, such as a shallow one, is refused, so fetch "
            "it with fetch-depth: 0. --root takes no --staged and no checkout."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    parser.add_argument(
        "--root",
        type=Path,
        metavar="ROOT",
        help="the CI form: check the home's own clone at ROOT, wherever it is, as the project "
        "whose github is origin's repo; for a home's CI",
    )
    parser.set_defaults(handler=_command)


CI_STEP = "kaizen project leak-check --root ."
"""The step a home's CI runs."""


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    if args.root is not None and (args.staged or args.checkout is not None):
        raise RefusalError(
            "project leak-check: --root takes no --staged and no checkout",
            "drop --staged and the checkout, or drop --root",
        )
    leak_check_project(run, args.checkout, home=home, staged=args.staged, root=args.root)
