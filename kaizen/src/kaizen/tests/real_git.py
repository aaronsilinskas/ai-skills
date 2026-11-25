"""Real git for the ``*_git`` tests, which run it in a temporary repo and never touch GitHub."""

from pathlib import Path

from kaizen.shared.common import run_subprocess


def git(*args: str | Path) -> str:
    """Runs git with *args*, each made a string, and returns its stdout."""
    return run_subprocess(["git", *map(str, args)])
