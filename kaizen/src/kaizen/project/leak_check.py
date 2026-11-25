"""``kaizen project leak-check``: run the **leak check** on a project's main checkout or ticket
worktree before a push, or on its staged files before a commit."""

import argparse
import textwrap
from dataclasses import replace
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
    _check(run, home, project, checkout, staged=staged, base=base, say=say)


def leak_check_home_clone(run: Runner, root: Path, *, home: Home, say: Say = print) -> None:
    """The CI form: refuses, as ``leak_check_project`` does, when the tracked files of the home's
    own clone at *root*, wherever it is, point outside the home, judged as at the home's
    registered root. Its denied patterns are searched against the default branch, whose history
    the clone must hold."""
    project, checkout = resolve_home_checkout(run, root, home)
    base = _fetched_default(checkout, run) if project.leak_deny else None
    # The rules allow the home's root and its ancestors: take the registered root, not the
    # clone's, so a CI path such as ~/work allows nothing the check at that root would refuse.
    registered = replace(home, root=project.path)
    _check(run, registered, project, checkout, staged=False, base=base, say=say)


def _check(
    run: Runner,
    home: Home,
    project: Project,
    checkout: Path,
    *,
    staged: bool,
    base: str | None,
    say: Say,
) -> None:
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
    branch = remote_default_branch(str(checkout), run)
    base = f"origin/{branch}"
    run_or_refuse(
        ["git", "-C", str(checkout), "merge-base", base, "HEAD"],
        run,
        f"{checkout} lacks {base} or its history with HEAD, which leak_deny's search needs",
        "fetch the default branch with its history before the check, such as actions/checkout's"
        f" fetch-depth: 0, or `git fetch origin {branch}` in a full clone",
    )
    return base


CI_STEP = "kaizen project leak-check --root ."
"""The step a home's CI runs."""


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "leak-check",
        help="run the leak check on the current project or a ticket worktree",
        description="\n\n".join(
            textwrap.fill(paragraph, width=79, break_on_hyphens=False)
            for paragraph in (
                "Run before any push or PR that `kaizen ticket ship` and the `kaizen spec` "
                "commands don't make (they run the check themselves): from the project's root or "
                "a ticket worktree, or pointed at one. Search that checkout's tracked files for "
                "text pointing outside the home (local paths and repos of the home's owners it "
                "doesn't register, and, in a public project, references to the home itself) and "
                "refuse, listing each line with its rule and fix. The project's leak_deny "
                "patterns are searched only on the lines the checkout adds against its base (a "
                "spec ticket's integration branch, else the default branch, as last fetched). It "
                "only queries, so it has no --dry-run.",
                f"In a home's CI, whose clone is at no registered path, run `{CI_STEP}` from the "
                "clone's root instead. --root takes only the root of the home kaizen serves, as "
                "the registry page whose github is origin's repo, which leak.own must also list. "
                "It runs the same rules from the same home facts, with the home at that page's "
                "path, so it allows nothing the check at that path would not. A path is found "
                "written from ~/ or under the running user's home directory, so one spelled out "
                "under another user's directory is caught only on a machine where it is theirs. "
                "With leak_deny, a clone lacking the default branch's history, such as a shallow "
                "one, is refused, so fetch it with fetch-depth: 0.",
            )
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


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    if args.root is not None and (args.staged or args.checkout is not None):
        raise RefusalError(
            "project leak-check: --root takes no --staged and no checkout",
            "drop --staged and the checkout, or drop --root",
        )
    if args.root is not None:
        leak_check_home_clone(run, args.root, home=home)
    else:
        leak_check_project(run, args.checkout, home=home, staged=args.staged)
