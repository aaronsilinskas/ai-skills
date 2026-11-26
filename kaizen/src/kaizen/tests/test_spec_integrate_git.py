"""Tests for ``kaizen spec integrate`` against real git, with a local bare repo as ``origin``.

Nothing here touches GitHub or a real remote: ``origin`` is a bare repo in ``tmp_path``.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError, run_subprocess
from kaizen.spec.integrate import integrate
from kaizen.tests.real_git import clone, commit, git
from kaizen.tests.ticket_shell import home_for, install_hook, quiet

SPEC = 25
BRANCH = f"spec-{SPEC}-fix-7-add-greeting"


@dataclass(frozen=True)
class Repos:
    projects: Path
    origin: Path
    checkout: Path
    ticket: Path

    def remote_tip(self) -> str:
        return git("-C", self.origin, "rev-parse", f"refs/heads/spec-{SPEC}").strip()

    def push_to_integration_branch(self, name: str, text: str) -> None:
        """Moves ``origin``'s integration branch from another clone, as a parallel run would."""
        other = self.origin.parent / f"other-{name}"
        if not other.exists():
            clone(self.origin, other)
        git("-C", other, "fetch", "-q", "origin")
        git("-C", other, "checkout", "-q", "-B", f"spec-{SPEC}", f"origin/spec-{SPEC}")
        commit(other, name, text)
        git("-C", other, "push", "-q", "origin", f"spec-{SPEC}")


def _repos(tmp_path: Path, check: str = "test ! -e FAIL", public: bool = False) -> Repos:
    """A project ``proto`` with ``spec-25`` on origin and a ticket worktree with one commit."""
    origin = tmp_path / "origin.git"
    git("init", "-q", "--bare", "-b", "main", origin)
    checkout = clone(origin, tmp_path / "proto")
    commit(checkout, ".gitignore", ".claude/\n.venv\n")
    git("-C", checkout, "push", "-q", "origin", "main")
    git("-C", checkout, "push", "-q", "origin", f"main:spec-{SPEC}")
    git("-C", checkout, "fetch", "-q", "origin")
    ticket = checkout / ".claude" / "worktrees" / BRANCH
    git("-C", checkout, "worktree", "add", "-q", "-b", BRANCH, ticket, f"origin/spec-{SPEC}")
    commit(ticket, "greeting.txt", "hello\n")

    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "proto.md").write_text(
        f"---\npath: {checkout}\ngithub: owner/proto\npublic: {str(public).lower()}\n"
        f"check: {check}\n---\n"
    )
    return Repos(projects, origin, checkout, ticket)


def _worktrees(repos: Repos) -> list[str]:
    out = git("-C", repos.checkout, "worktree", "list", "--porcelain")
    return [
        line.removeprefix("worktree ") for line in out.splitlines() if line.startswith("worktree ")
    ]


def test_integrating_pushes_a_merge_of_the_ticket_and_leaves_no_worktree_or_branch(tmp_path):
    repos = _repos(tmp_path)

    integrate(repos.ticket, run_subprocess, home=home_for(repos.projects), say=quiet)

    tip = f"refs/heads/spec-{SPEC}"
    assert git("-C", repos.origin, "show", f"{tip}:greeting.txt") == "hello\n"
    parents = git("-C", repos.origin, "rev-list", "--parents", "-n", "1", tip).split()
    assert len(parents) == 3, "a --no-ff merge commit has two parents"
    assert BRANCH in git("-C", repos.origin, "log", "-1", "--format=%s", tip)
    assert _worktrees(repos) == [str(repos.checkout.resolve())]
    assert not git("-C", repos.checkout, "branch", "--list", BRANCH).strip()


def _integrate(repos: Repos, run=run_subprocess) -> None:
    integrate(repos.ticket, run, home=home_for(repos.projects), say=quiet)


def test_a_conflict_is_refused_naming_its_files_and_leaves_no_scratch_worktree(tmp_path):
    repos = _repos(tmp_path)
    repos.push_to_integration_branch("greeting.txt", "hi there\n")
    before = repos.remote_tip()

    with pytest.raises(RefusalError, match=r"conflicts with origin/spec-25 in:\ngreeting\.txt"):
        _integrate(repos)

    assert _worktrees(repos) == [str(repos.checkout.resolve()), str(repos.ticket.resolve())]
    assert repos.remote_tip() == before


def test_a_failing_check_is_refused_and_leaves_the_integration_branch_unmoved(tmp_path):
    repos = _repos(tmp_path)
    commit(repos.ticket, "FAIL", "the check fails while this file exists\n")
    before = repos.remote_tip()

    with pytest.raises(RefusalError, match=r"the check failed on the merged result"):
        _integrate(repos)

    assert repos.remote_tip() == before
    assert _worktrees(repos) == [str(repos.checkout.resolve()), str(repos.ticket.resolve())]


def test_a_failing_checks_refusal_ends_with_its_last_lines_in_the_order_they_were_written(tmp_path):
    # Installer noise on stderr comes first; the real failure is the last thing on stdout.
    noise = "i=0; while [ $i -lt 40 ]; do echo installing >&2; i=$((i+1)); done"
    repos = _repos(tmp_path, check=f"{noise}; echo 'FAILED test_greeting'; exit 1")

    with pytest.raises(RefusalError) as refused:
        _integrate(repos)

    assert "installing\nFAILED test_greeting\n  fix:" in str(refused.value)


def test_a_push_rejected_because_the_tip_moved_is_refused_with_rerun(tmp_path):
    repos = _repos(tmp_path)

    def racing(cmd: list[str]) -> str:
        if "push" in cmd:
            repos.push_to_integration_branch("other.txt", "from a parallel integrate\n")
        return run_subprocess(cmd)

    with pytest.raises(RefusalError, match=r"spec-25 moved(.|\n)*rerun"):
        _integrate(repos, racing)

    assert git("-C", repos.origin, "log", "-1", "--format=%s", "spec-25") == "Write other.txt\n"
    assert _worktrees(repos) == [str(repos.checkout.resolve()), str(repos.ticket.resolve())]


def test_the_check_runs_from_the_scratch_worktrees_root_on_the_merged_result(tmp_path):
    repos = _repos(tmp_path, check="test -f greeting.txt && test -f .gitignore")

    _integrate(repos)

    assert "Integrate" in git("-C", repos.origin, "log", "-1", "--format=%s", "spec-25")


def test_a_hook_installed_from_the_ticket_worktree_is_refused_with_the_reinstall_command(
    tmp_path,
):
    repos = _repos(tmp_path)
    hook = install_hook(repos.checkout, repos.ticket / ".venv" / "bin" / "python")
    written = hook.read_text()
    before = repos.remote_tip()

    with pytest.raises(RefusalError, match=r"pre-commit hook(.|\n)*uv run pre-commit install"):
        _integrate(repos)

    assert repos.remote_tip() == before
    assert _worktrees(repos) == [str(repos.checkout.resolve()), str(repos.ticket.resolve())]
    assert hook.read_text() == written


def test_a_hook_installed_from_the_main_checkout_lets_integrate_remove_the_worktree(tmp_path):
    repos = _repos(tmp_path)
    hook = install_hook(repos.checkout, repos.checkout / ".venv" / "bin" / "python")
    written = hook.read_text()

    _integrate(repos)

    assert _worktrees(repos) == [str(repos.checkout.resolve())]
    assert hook.read_text() == written


def _venv_python_linked_to(venv: Path, interpreter: Path) -> Path:
    """Makes *venv* a venv whose ``bin/python`` is a symlink to *interpreter*, as uv makes one."""
    (venv / "bin").mkdir(parents=True)
    python = venv / "bin" / "python"
    python.symlink_to(interpreter)
    return python


def test_a_hook_whose_worktree_interpreter_links_out_of_the_worktree_is_refused(tmp_path):
    repos = _repos(tmp_path)
    outside = tmp_path / "pyenv-python"
    outside.write_text("")
    install_hook(repos.checkout, _venv_python_linked_to(repos.ticket / ".venv", outside))

    with pytest.raises(RefusalError, match=r"pre-commit hook"):
        _integrate(repos)

    assert _worktrees(repos) == [str(repos.checkout.resolve()), str(repos.ticket.resolve())]


def test_a_hook_in_a_worktree_venv_linked_from_elsewhere_is_refused(tmp_path):
    repos = _repos(tmp_path)
    shared = tmp_path / "shared-venv"
    _venv_python_linked_to(shared, tmp_path / "pyenv-python")
    (repos.ticket / ".venv").symlink_to(shared)
    install_hook(repos.checkout, repos.ticket / ".venv" / "bin" / "python")

    with pytest.raises(RefusalError, match=r"pre-commit hook"):
        _integrate(repos)

    assert _worktrees(repos) == [str(repos.checkout.resolve()), str(repos.ticket.resolve())]
