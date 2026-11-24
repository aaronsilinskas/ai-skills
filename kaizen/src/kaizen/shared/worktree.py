"""Worktrees: listing a checkout's, adding a **scratch worktree**, linking ignored paths, and
guarding the shared pre-commit hook before one is removed."""

import shlex
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from kaizen.shared.common import RefusalError, Runner, Say
from kaizen.shared.registry import Project


@dataclass(frozen=True)
class Worktree:
    """One entry of ``git worktree list --porcelain``. *branch* is the short name of the
    checked-out branch, or ``None`` for a detached HEAD."""

    path: str
    branch: str | None
    locked: bool


def list_worktrees(checkout: str, run: Runner) -> list[Worktree]:
    """The main checkout and every worktree of *checkout*, in ``git worktree list`` order."""
    out = run(["git", "-C", checkout, "worktree", "list", "--porcelain"])
    found: list[Worktree] = []
    for entry in out.split("\n\n"):
        lines = entry.splitlines()
        if not lines:
            continue
        branch = None
        for line in lines[1:]:
            if line.startswith("branch refs/heads/"):
                branch = line.removeprefix("branch refs/heads/")
        locked = any(line == "locked" or line.startswith("locked ") for line in lines[1:])
        found.append(Worktree(lines[0].removeprefix("worktree "), branch, locked))
    return found


@contextmanager
def scratch_worktree(
    checkout: str, ref: str, run: Runner, say: Say, *, prefix: str
) -> Iterator[Path]:
    """A worktree detached at *ref* in a temporary directory outside the project, removed however
    the block ends. *prefix* names the temporary directory after the command, such as
    ``kaizen-integrate-``."""
    with tempfile.TemporaryDirectory(prefix=prefix) as parent:
        scratch = Path(parent) / "scratch"
        run(["git", "-C", checkout, "worktree", "add", "--detach", str(scratch), ref])
        say(f"added scratch worktree {scratch} at {ref}")
        try:
            yield scratch
        finally:
            run(["git", "-C", checkout, "worktree", "remove", "--force", str(scratch)])
            say(f"removed scratch worktree {scratch}")


def add_ticket_worktree(
    project: Project, checkout: str, worktree: Path, branch: str, start: str, run: Runner, say: Say
) -> None:
    """Adds *worktree* of *checkout* on a new *branch* from *start*, then links the project's
    ``worktree_links`` into it: how ``kaizen ticket start`` makes a ticket worktree."""
    run(["git", "-C", checkout, "worktree", "add", str(worktree), "-b", branch, start])
    say(f"added worktree on {branch} from {start}")
    link_ignored_paths(project, worktree, say)


def link_ignored_paths(
    project: Project, worktree: Path, say: Say, *, dry_run: bool = False
) -> None:
    """Symlinks each of the project's ``worktree_links`` from the main checkout into *worktree*,
    warning about one the main checkout lacks."""
    for entry in project.worktree_links:
        target = project.path / entry
        if not target.exists():
            say(f"warning: {entry} is not in the main checkout {project.path}, so not linked")
            continue
        if dry_run:
            say(f"would link {entry} from the main checkout")
            continue
        link = worktree / entry
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        say(f"linked {entry} from the main checkout")


def refuse_hook_inside(checkout: str, worktree: Path, run: Runner) -> None:
    """Refuses while the shared pre-commit hook runs from an interpreter inside ``worktree``, which
    the caller is about to remove.

    Every worktree of a repo shares one hook, which ``pre-commit install`` points at the
    interpreter it ran from (``INSTALL_PYTHON``); once that worktree is gone, every commit fails.
    """
    common = Path(checkout) / run(["git", "-C", checkout, "rev-parse", "--git-common-dir"]).strip()
    hook = common / "hooks" / "pre-commit"
    if not hook.is_file():
        return
    for line in hook.read_text(errors="replace").splitlines():
        if not line.startswith("INSTALL_PYTHON="):
            continue
        words = shlex.split(line.removeprefix("INSTALL_PYTHON="))
        if not words:
            return
        python = Path(words[0])
        if python.is_relative_to(worktree) or python.parent.resolve().is_relative_to(
            worktree.resolve()
        ):
            raise RefusalError(
                f"the shared pre-commit hook {hook} runs from {python}, inside the worktree"
                " it would remove, so every commit would fail once it is gone",
                f"reinstall the hook from the main checkout's environment"
                f" (`cd {checkout} && uv run pre-commit install`), then rerun",
            )
        return
