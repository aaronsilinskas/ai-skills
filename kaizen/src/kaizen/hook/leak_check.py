"""``kaizen hook leak-check``: the leak check on the staged files, so a commit adding a leak is
refused before it exists."""

import argparse

from kaizen.hook.common import add_files_argument
from kaizen.project.leak_check import leak_check_project
from kaizen.shared.common import Runner
from kaizen.shared.home import Home


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "leak-check",
        help="run the leak check on the staged files",
        description=(
            "Run the leak check on the index of the checkout it runs in, as `kaizen project "
            "leak-check --staged` does: refuse, listing each line with its file, rule and fix, "
            "when the next commit would hold text pointing outside the home. It searches the "
            "whole index, so any file names pre-commit passes are ignored."
        ),
    )
    add_files_argument(parser)
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    leak_check_project(run, home=home, staged=True)
