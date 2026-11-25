"""Tests for ``kaizen ticket diff --base`` against real git, with a local bare repo as ``origin``:
the base it prints is a commit that stays put while the ticket's base branch moves on.

Nothing here touches GitHub or a real remote: ``origin`` is a bare repo in ``tmp_path``.
"""

from pathlib import Path

import pytest

from kaizen.shared.common import run_subprocess
from kaizen.tests.ticket_shell import home_for
from kaizen.ticket.diff import diff


def _git(*args: str | Path) -> str:
    return run_subprocess(["git", *map(str, args)])


def _commit(repo: Path, name: str, text: str) -> str:
    (repo / name).write_text(text)
    _git("-C", repo, "add", name)
    _git("-C", repo, "commit", "-q", "-m", f"Write {name}")
    return _git("-C", repo, "rev-parse", "HEAD").strip()


def _clone(origin: Path, dest: Path) -> Path:
    _git("clone", "-q", origin, dest)
    _git("-C", dest, "config", "user.name", "Test")
    _git("-C", dest, "config", "user.email", "test@example.com")
    return dest


@pytest.mark.parametrize(
    ("branch", "base"),
    [("spec-25-fix-7-add-greeting", "spec-25"), ("fix-7-add-greeting", "main")],
    ids=["spec ticket", "lone ticket"],
)
def test_base_prints_the_merge_base_which_stays_put_as_the_base_branch_moves(
    tmp_path, capsys, branch, base
):
    tmp_path = tmp_path.resolve()
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "main", origin)
    checkout = _clone(origin, tmp_path / "proto")
    started_from = _commit(checkout, ".gitignore", ".claude/\n")
    _git("-C", checkout, "push", "-q", "origin", "main", "main:spec-25")
    _git("-C", checkout, "fetch", "-q", "origin")
    ticket = checkout / ".claude" / "worktrees" / branch
    _git("-C", checkout, "worktree", "add", "-q", "-b", branch, ticket, f"origin/{base}")
    _commit(ticket, "greeting.txt", "hello\n")
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "proto.md").write_text(
        f"---\npath: {checkout}\ngithub: owner/proto\npublic: false\n---\n"
    )
    other = _clone(origin, tmp_path / "other")
    _git("-C", other, "checkout", "-q", base)
    _commit(other, "later.txt", "another ticket's work\n")
    _git("-C", other, "push", "-q", "origin", base)

    diff(ticket, run_subprocess, only="base", home=home_for(projects))

    assert capsys.readouterr().out == f"{started_from}\n"
