"""``kaizen``: every command a home offers, grouped noun then verb (``kaizen ticket start``).

``project leak-check`` runs the leak check before a push no other command makes, and
``project labels`` creates the workflow labels the projects' GitHub repos lack;
``spec publish`` and ``ticket publish`` are the publish steps of the Spec workflow;
``spec start``, ``spec integrate``, ``spec ship`` and ``spec finish`` run a spec's integration
branch, ``ticket start``, ``ship`` and ``finish`` a ticket's git lifecycle, and
``ticket abandon`` drops an unmerged ticket, with fixed, checked git and gh steps.
``ticket diff`` prints a ticket's changes against its base, and ``ticket compare`` runs a
command on a ticket and its base with a verdict.
``spec status`` prints a spec's tickets and its frontier.
``issue show`` prints one issue whole, ``issue link`` adds its parent and blocked-by edges,
and ``issue publish`` creates one issue after the leak check.
``pr wait`` blocks until a PR's checks finish and exits by their outcome.
``home init`` makes the git repo it runs in a new home, and is the one command that needs none.
Each command that changes anything checks its preconditions first and has a ``--dry-run``.
Run it inside a **home** (the tree under a directory holding ``mw.toml``), or from one of its
projects' roots with ``MW_HOME`` set to the home's root; the home's docs say how to install it.
"""

import argparse
import io
import os
import subprocess
import sys
import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO, cast

from kaizen.home import init as home_init
from kaizen.issue import link as issue_link
from kaizen.issue import publish as issue_publish
from kaizen.issue import show as issue_show
from kaizen.pr import wait
from kaizen.project import labels as project_labels
from kaizen.project import leak_check as project_leak_check
from kaizen.shared.common import RefusalError, Runner, StepFailedError, run_subprocess
from kaizen.shared.home import find_home
from kaizen.spec import finish as spec_finish
from kaizen.spec import integrate
from kaizen.spec import publish as spec_publish
from kaizen.spec import ship as spec_ship
from kaizen.spec import start as spec_start
from kaizen.spec import status as spec_status
from kaizen.ticket import abandon, compare, diff, finish, ship, start
from kaizen.ticket import publish as ticket_publish

# Each command module adds its own subparser and sets ``handler`` (see ``start.add_parser``),
# which is called with the parsed arguments, the runner and the ``Home``. A command that sets
# ``needs_home=False`` as well (only ``home init``, which makes the home) is called with the
# start directory and the environment instead, and no home is looked for.
# A handler that returns ``None`` has succeeded, and one that returns an int exits with it;
# it fails by raising, which ``main`` reports.
GROUPS = {
    "home": ("set up a new home", (home_init,)),
    "issue": ("read, link and publish issues", (issue_show, issue_link, issue_publish)),
    "project": (
        "check the current project, or sync the workflow labels to the projects' repos",
        (project_leak_check, project_labels),
    ),
    "pr": ("wait on a pull request's checks", (wait,)),
    "spec": (
        "publish a grilled spec and run its integration branch; report its status",
        (spec_publish, spec_start, integrate, spec_ship, spec_finish, spec_status),
    ),
    "ticket": (
        "publish tickets, run or drop a ticket's git lifecycle, and diff or compare a ticket",
        (ticket_publish, start, ship, finish, abandon, diff, compare),
    ),
}


def main(
    argv: list[str] | None = None,
    run: Runner = run_subprocess,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    """Runs one command in the home found from *cwd* and *env* (default: the current directory
    and the process environment); ``--help`` exits before the home is looked for, and a command
    that needs no home skips the search."""
    parser = argparse.ArgumentParser(
        prog="kaizen", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    groups = parser.add_subparsers(required=True, metavar="<group>")
    for name, (help_text, commands) in GROUPS.items():
        group = groups.add_parser(name, help=help_text, description=help_text)
        subparsers = group.add_subparsers(required=True, metavar="<command>")
        for module in commands:
            module.add_parser(subparsers)
    args = parser.parse_args(argv)
    # Progress goes to stdout and the outcome to stderr. A piped stdout is block-buffered, so
    # without line buffering the outcome could print before the progress, and not be the last
    # line. The guards skip a stream with no file behind it, such as an io.StringIO.
    real_stdout, real_stderr = sys.stdout, sys.stderr
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)
        sys.stdout = cast(TextIO, _SurvivesClosedPipe(sys.stdout))
    if isinstance(sys.stderr, io.TextIOWrapper):
        # The wrapper is no TextIO to mypy: it overrides write and flush and hands every other
        # attribute to the stream it wraps through __getattr__.
        sys.stderr = cast(TextIO, _SurvivesClosedPipe(sys.stderr))
    try:
        return _run(args, run, cwd, env)
    finally:
        sys.stdout, sys.stderr = real_stdout, real_stderr


def _run(
    args: argparse.Namespace, run: Runner, cwd: Path | None, env: Mapping[str, str] | None
) -> int:
    """Runs the parsed command and returns its exit code."""
    start = cwd or Path.cwd()
    environ = os.environ if env is None else env
    try:
        if getattr(args, "needs_home", True):
            code = args.handler(args, run, find_home(start, environ)) or 0
        else:
            code = args.handler(args, run, start, environ) or 0
        outcome = ""
    except RefusalError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        code, outcome = 1, " (refused: nothing changed)"
    except subprocess.CalledProcessError as exc:
        code, outcome = _failed(f"{' '.join(exc.cmd)} failed:\n{exc.stderr}")
    except StepFailedError as exc:
        code, outcome = _failed(str(exc))
    except Exception:  # a bug or a missing tool: still end with the exit line
        traceback.print_exc()
        code, outcome = 1, " (crashed: see the traceback above; the steps printed above are done)"
    # The exit code as the last line, so `kaizen ... 2>&1 | tail -n 1` shows the outcome even
    # though the shell reports tail's exit status.
    print(f"kaizen: exit {code}{outcome}", file=sys.stderr)
    return code


def _failed(message: str) -> tuple[int, str]:
    print(f"error: {message}", file=sys.stderr)
    return 1, " (failed: the steps printed above are done; finish the rest by hand)"


class _SurvivesClosedPipe:
    """A text stream that outlives its pipe's reader, as `kaizen ... | head` leaves it once head
    exits: rather than stop the command halfway with ``BrokenPipeError``, it points the file
    descriptor at /dev/null and drops the rest."""

    def __init__(self, stream: io.TextIOWrapper) -> None:
        self._stream = stream

    def write(self, text: str) -> int:
        try:
            return self._stream.write(text)
        except BrokenPipeError:
            self._drop_the_rest()
            return len(text)

    def flush(self) -> None:
        try:
            self._stream.flush()
        except BrokenPipeError:
            self._drop_the_rest()

    def _drop_the_rest(self) -> None:
        # Text still buffered then flushes into /dev/null, also when the interpreter exits.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, self._stream.fileno())
        os.close(devnull)

    def __getattr__(self, name: str) -> object:
        return getattr(self._stream, name)


if __name__ == "__main__":
    sys.exit(main())
