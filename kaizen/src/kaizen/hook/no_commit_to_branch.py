"""``kaizen hook no-commit-to-branch``: refuse a commit on a protected branch, the project's
default branch unless named, so work goes through a branch and a PR."""

import argparse
import subprocess

from kaizen.hook.common import add_files_argument
from kaizen.shared.branch import remote_default_branch
from kaizen.shared.common import RefusalError, Runner
from kaizen.shared.home import Home


def refuse_protected_branch(run: Runner, branches: list[str] | None) -> None:
    """Refuses when the checkout the command runs in is on one of *branches* (default: its
    default branch); a detached HEAD is on no branch."""
    try:
        current = run(["git", "symbolic-ref", "--short", "HEAD"]).strip()
    except subprocess.CalledProcessError:
        return
    if current in (branches or [_default_branch(run)]):
        raise RefusalError(
            f"hook no-commit-to-branch: the commit is on {current}, which takes no direct commits",
            "commit on a branch of its own (`git switch -c <name>`) and land it through a PR",
        )


def _default_branch(run: Runner) -> str:
    """The default branch as last fetched, or asked of origin when the clone never recorded it."""
    try:
        tracking = run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"]).strip()
    except subprocess.CalledProcessError:
        return remote_default_branch(".", run)
    return tracking.removeprefix("origin/")


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "no-commit-to-branch",
        help="refuse a commit on the default branch, or on the branches named",
        description=(
            "Refuse a commit when the checkout it runs in is on a protected branch: each "
            "--branch given, else the project's default branch, read from origin/HEAD as last "
            "fetched, or from origin when the clone has no origin/HEAD. A detached HEAD passes. "
            "Any file names pre-commit passes are ignored."
        ),
    )
    parser.add_argument(
        "--branch",
        action="append",
        help="a branch that takes no direct commits; repeat it for more than one "
        "(default: the project's default branch)",
    )
    add_files_argument(parser)
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    refuse_protected_branch(run, args.branch)
