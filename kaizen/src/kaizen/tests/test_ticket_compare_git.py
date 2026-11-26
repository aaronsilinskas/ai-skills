"""Tests for ``kaizen ticket compare`` against real git, with a local bare repo as ``origin``.

Nothing here touches GitHub or a real remote: ``origin`` is a bare repo in ``tmp_path``, and the
compared commands are instant shell one-liners.
"""

from dataclasses import dataclass
from pathlib import Path

from kaizen.shared.common import run_subprocess
from kaizen.tests.real_git import clone, commit, git
from kaizen.tests.ticket_shell import home_for
from kaizen.ticket.compare import compare

BRANCH = "fix-7-add-greeting"


@dataclass(frozen=True)
class Repos:
    projects: Path
    checkout: Path
    ticket: Path
    base_commit: str

    def worktrees(self) -> list[str]:
        out = git("-C", self.checkout, "worktree", "list", "--porcelain")
        return [
            line.removeprefix("worktree ")
            for line in out.splitlines()
            if line.startswith("worktree ")
        ]


def _repos(tmp_path: Path) -> Repos:
    """A project ``proto`` whose ticket worktree adds ``FAIL`` on top of ``origin/main``, with a
    git-ignored ``tools/helper`` in the main checkout listed in its ``worktree_links``."""
    origin = tmp_path / "origin.git"
    git("init", "-q", "--bare", "-b", "main", origin)
    checkout = clone(origin, tmp_path / "proto")
    commit(checkout, ".gitignore", ".claude/\ntools/\n")
    git("-C", checkout, "push", "-q", "origin", "main")
    (checkout / "tools").mkdir()
    (checkout / "tools" / "helper").write_text("a downloaded tool\n")
    base_commit = git("-C", checkout, "rev-parse", "HEAD").strip()
    ticket = checkout / ".claude" / "worktrees" / BRANCH
    git("-C", checkout, "worktree", "add", "-q", "-b", BRANCH, ticket, "origin/main")
    commit(ticket, "FAIL", "the command fails while this file exists\n")
    (ticket / "tools").mkdir()
    (ticket / "tools" / "helper").symlink_to(checkout / "tools" / "helper")  # as ticket start does

    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "proto.md").write_text(
        f"---\npath: {checkout}\ngithub: owner/proto\npublic: false\n"
        "worktree_links: tools/helper\n---\n"
    )
    return Repos(projects, checkout, ticket, base_commit)


def _compare(repos: Repos, command: str, out: list[str]) -> str | None:
    return compare(
        repos.ticket,
        ["sh", "-c", command],
        run_subprocess,
        runs=2,
        home=home_for(repos.projects),
        say=out.append,
    )


def test_the_base_runs_at_the_base_commit(tmp_path):
    repos = _repos(tmp_path)
    out: list[str] = []

    _compare(repos, "git rev-parse HEAD; exit 1", out)

    assert out[out.index("base run 1: exit 1") + 1] == f"  {repos.base_commit}"


def test_the_scratch_worktree_is_removed_after_a_failing_run(tmp_path):
    repos = _repos(tmp_path)

    assert _compare(repos, "exit 1", []) == "pre-existing"

    assert repos.worktrees() == [str(repos.checkout.resolve()), str(repos.ticket.resolve())]


def test_a_failure_the_ticket_brings_is_caused(tmp_path):
    repos = _repos(tmp_path)

    assert _compare(repos, "test ! -e FAIL", []) == "caused"


def test_rerunning_the_same_compare_gives_the_same_verdict(tmp_path):
    repos = _repos(tmp_path)

    verdicts = [_compare(repos, "test ! -e FAIL", []) for _ in range(2)]

    assert verdicts[0] == verdicts[1]


def test_the_scratch_worktree_has_the_projects_worktree_links(tmp_path):
    repos = _repos(tmp_path)
    out: list[str] = []

    assert _compare(repos, "test -f tools/helper", out) == "passes"
    assert "base run 2: exit 0" in out


def test_no_stash_is_left_after_a_run_with_uncommitted_changes(tmp_path):
    repos = _repos(tmp_path)
    (repos.ticket / "FAIL").unlink()

    assert _compare(repos, "test ! -e FAIL", []) == "passes"

    assert git("-C", repos.checkout, "stash", "list") == ""
    assert not (repos.ticket / "FAIL").exists()
