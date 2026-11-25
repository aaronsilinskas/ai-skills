"""Tests for a spec started with ``kaizen spec start --local``, against real git, with a local
bare repo as ``origin``: its tickets start, diff, compare and integrate off the local integration
branch, and the first integration pushes it.

Nothing here touches GitHub or a real remote: ``origin`` is a bare repo in ``tmp_path``, and gh
is answered from canned replies while git runs for real.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError, run_subprocess
from kaizen.spec.integrate import integrate
from kaizen.spec.start import start as spec_start
from kaizen.tests.ticket_shell import home_for, issue_json, sub_issue_json
from kaizen.ticket.compare import compare
from kaizen.ticket.diff import diff
from kaizen.ticket.start import start as ticket_start

SPEC = 25
ISSUE = 7
SPEC_JSON = '{"state": "OPEN", "title": "S", "labels": [{"name": "spec"}]}'


def _git(*args: str | Path) -> str:
    return run_subprocess(["git", *map(str, args)])


def _commit(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text)
    _git("-C", repo, "add", name)
    _git("-C", repo, "commit", "-q", "-m", f"Write {name}")


@dataclass
class Runs:
    """Runs git for real and answers gh from canned replies, recording every argv."""

    calls: list[list[str]]

    def __call__(self, cmd: list[str]) -> str:
        self.calls.append(cmd)
        if cmd[0] != "gh":
            return run_subprocess(cmd)
        if "sub_issues" in " ".join(cmd):
            return sub_issue_json(ISSUE)
        if "blocked_by" in " ".join(cmd):
            return ""
        if str(SPEC) in cmd:
            return SPEC_JSON
        return issue_json(number=ISSUE, title="Add greeting")

    def ran(self, *words: str) -> list[list[str]]:
        n = len(words)
        return [c for c in self.calls if any(tuple(c[i : i + n]) == words for i in range(len(c)))]


@dataclass(frozen=True)
class Repos:
    origin: Path
    checkout: Path
    projects: Path

    def on_origin(self, ref: str) -> str | None:
        out = _git("-C", self.origin, "for-each-ref", "--format=%(objectname)", ref)
        return out.strip() or None

    def local(self, branch: str) -> str | None:
        out = _git("-C", self.checkout, "for-each-ref", "--format=%(objectname)", branch)
        return out.strip() or None


def _quiet(_: str) -> None:
    pass


@pytest.fixture
def repos(tmp_path, monkeypatch) -> Repos:
    """A project ``proto`` whose main checkout is on ``main``, the command's working directory."""
    tmp_path = tmp_path.resolve()
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "main", origin)
    checkout = tmp_path / "proto"
    _git("clone", "-q", origin, checkout)
    _git("-C", checkout, "config", "user.name", "Test")
    _git("-C", checkout, "config", "user.email", "test@example.com")
    _commit(checkout, ".gitignore", ".claude/\n")
    _git("-C", checkout, "push", "-q", "origin", "main")
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "proto.md").write_text(
        f"---\npath: {checkout}\ngithub: owner/proto\npublic: false\ncheck: exit 0\n---\n"
    )
    monkeypatch.chdir(checkout)
    return Repos(origin, checkout, projects)


def _start_ticket(repos: Repos, run: Runs) -> Path:
    started = ticket_start(
        "proto", ISSUE, "add-greeting", run, home=home_for(repos.projects), spec=SPEC, say=_quiet
    )
    _commit(started.worktree, "greeting.txt", "hello\n")
    return started.worktree


def test_a_local_start_makes_the_branch_from_origins_default_and_pushes_nothing(repos):
    run = Runs([])
    head_before = _git("-C", repos.checkout, "symbolic-ref", "HEAD")

    spec_start(SPEC, run, home=home_for(repos.projects), local=True, say=_quiet)

    assert repos.local(f"refs/heads/spec-{SPEC}") == repos.local("refs/remotes/origin/main")
    assert repos.on_origin(f"refs/heads/spec-{SPEC}") is None
    assert not run.ran("push")
    assert _git("-C", repos.checkout, "symbolic-ref", "HEAD") == head_before
    assert _git("-C", repos.checkout, "status", "--porcelain") == ""


def test_a_ticket_of_a_local_spec_diffs_and_compares_against_the_local_branch(repos, capsys):
    run = Runs([])
    home = home_for(repos.projects)
    spec_start(SPEC, run, home=home, local=True, say=_quiet)
    worktree = _start_ticket(repos, run)

    diff(worktree, run, home=home, only="base")
    verdict = compare(
        worktree, ["test", "!", "-e", "greeting.txt"], run, runs=1, home=home, say=_quiet
    )

    assert capsys.readouterr().out == repos.local(f"refs/heads/spec-{SPEC}") + "\n"
    assert verdict == "caused"
    assert not run.ran("fetch", "-q", "origin")


def test_the_first_integration_pushes_the_branch_and_deletes_the_local_one(repos):
    run = Runs([])
    home = home_for(repos.projects)
    spec_start(SPEC, run, home=home, local=True, say=_quiet)
    local_tip = repos.local(f"refs/heads/spec-{SPEC}")
    worktree = _start_ticket(repos, run)

    integrate(worktree, run, home=home, say=_quiet)

    tip = f"refs/heads/spec-{SPEC}"
    assert _git("-C", repos.origin, "show", f"{tip}:greeting.txt") == "hello\n"
    parents = _git("-C", repos.origin, "rev-list", "--parents", "-n", "1", tip).split()
    assert parents[1] == local_tip
    assert repos.local(tip) is None


def test_a_later_ticket_starts_and_integrates_from_origin_after_the_first_push(repos):
    run = Runs([])
    home = home_for(repos.projects)
    spec_start(SPEC, run, home=home, local=True, say=_quiet)
    integrate(_start_ticket(repos, run), run, home=home, say=_quiet)
    first = repos.on_origin(f"refs/heads/spec-{SPEC}")

    worktree = ticket_start(
        "proto", ISSUE, "second", run, home=home, spec=SPEC, say=_quiet
    ).worktree
    _commit(worktree, "second.txt", "again\n")
    integrate(worktree, run, home=home, say=_quiet)

    tip = f"refs/heads/spec-{SPEC}"
    parents = _git("-C", repos.origin, "rev-list", "--parents", "-n", "1", tip).split()
    assert parents[1] == first


def test_start_without_local_pushes_a_local_branch_and_deletes_it(repos):
    run = Runs([])
    home = home_for(repos.projects)
    spec_start(SPEC, run, home=home, local=True, say=_quiet)
    local_tip = repos.local(f"refs/heads/spec-{SPEC}")

    spec_start(SPEC, run, home=home, say=_quiet)

    assert repos.on_origin(f"refs/heads/spec-{SPEC}") == local_tip
    assert repos.local(f"refs/heads/spec-{SPEC}") is None


def test_a_second_local_start_is_refused(repos):
    run = Runs([])
    home = home_for(repos.projects)
    spec_start(SPEC, run, home=home, local=True, say=_quiet)

    with pytest.raises(RefusalError, match=f"spec-{SPEC} already exists locally"):
        spec_start(SPEC, run, home=home, local=True, say=_quiet)
