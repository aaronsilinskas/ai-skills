"""Real git for the ``*_git`` tests, which run it in a temporary repo and never touch GitHub."""

from pathlib import Path

from kaizen.shared.common import run_subprocess


def git(*args: str | Path) -> str:
    """Runs git with *args*, each made a string, and returns its stdout."""
    return run_subprocess(["git", *map(str, args)])


def commit(repo: Path, name: str, text: str) -> str:
    """Returns the new ``HEAD``."""
    (repo / name).write_text(text)
    git("-C", repo, "add", name)
    git("-C", repo, "commit", "-q", "-m", f"Write {name}")
    return git("-C", repo, "rev-parse", "HEAD").strip()


def clone(origin: Path, dest: Path) -> Path:
    """A clone with a committer identity set, so tests can commit in it."""
    git("clone", "-q", origin, dest)
    git("-C", dest, "config", "user.name", "Test")
    git("-C", dest, "config", "user.email", "test@example.com")
    return dest
