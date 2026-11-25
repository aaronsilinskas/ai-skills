"""Plumbing every ``kaizen`` command shares: the runner seam and refusals."""

import argparse
import difflib
import subprocess
from collections.abc import Callable

Runner = Callable[[list[str]], str]
"""Runs one argv and returns its stdout; raises ``CalledProcessError`` on a non-zero exit."""

Say = Callable[[str], None]

type Subparsers = argparse._SubParsersAction[argparse.ArgumentParser]
"""What ``kaizen``'s CLI passes each command module's ``add_parser`` to add its subparser to."""


class RefusalError(Exception):
    """A check failed before anything mutating ran. Names the check and how to fix it."""

    def __init__(self, check: str, fix: str) -> None:
        super().__init__(f"{check}\n  fix: {fix}")


class StepFailedError(Exception):
    """A step that is not a git or gh command failed after earlier steps changed things, so
    ``main`` reports it as it does a failed command: ``error:``, with the steps printed above
    done."""

    def __init__(self, step: str, detail: str) -> None:
        super().__init__(f"{step} failed:\n{detail}")


def unified_diff(relative: str, before: str | None, after: str) -> str:
    """The unified diff from *before* (``None`` for a file that is absent) to *after*, for the
    file at *relative*; empty when they differ only in line endings or the final newline."""
    lines = difflib.unified_diff(
        [] if before is None else before.splitlines(),
        after.splitlines(),
        "/dev/null" if before is None else f"a/{relative}",
        f"b/{relative}",
        lineterm="",
    )
    return "\n".join(lines)


def run_subprocess(cmd: list[str]) -> str:
    """Runs *cmd* with its stderr captured, so a failure carries git's or gh's own message."""
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def push_rejected(exc: subprocess.CalledProcessError) -> bool:
    """Whether a failed ``git push`` was rejected because origin has commits the pushed ref lacks.

    Git prints these reasons untranslated, so the match holds in any locale.
    """
    stderr = exc.stderr or ""
    return "(non-fast-forward)" in stderr or "(fetch first)" in stderr


def run_or_refuse(cmd: list[str], run: Runner, check: str, fix: str) -> str:
    """Runs a query whose failure is a refusal, appending the command's stderr to *check*."""
    try:
        return run(cmd)
    except subprocess.CalledProcessError as exc:
        raise RefusalError(f"{check}: {(exc.stderr or '').strip()}", fix) from exc
