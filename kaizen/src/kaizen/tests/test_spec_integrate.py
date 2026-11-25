"""Tests for ``kaizen spec integrate``: its refusals, its plan and the steps it reports.

git is replaced by a recording runner and the registry by a temporary ``projects/`` directory,
so no repo or real project page is touched. ``test_spec_integrate_git.py`` runs real git.
"""

from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError
from kaizen.spec.integrate import integrate
from kaizen.tests.ticket_shell import (
    RELAY,
    Reply,
    Shell,
    failed,
    home_for,
    quiet,
)

BRANCH = "spec-25-fix-32-merge-and-check"
REMOTE_HEAD = "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n"


def _setup(tmp_path: Path, check: str | None = "make check", public: bool = False) -> Path:
    """A registry with one project, ``proto``; returns its ``projects/`` directory."""
    projects = tmp_path / "projects"
    projects.mkdir()
    check_line = f"check: {check}\n" if check is not None else ""
    (projects / "proto.md").write_text(
        f"---\npath: {tmp_path / 'proto'}\ngithub: owner/proto\n"
        f"public: {str(public).lower()}\n{check_line}---\n"
    )
    return projects


def _worktree(tmp_path: Path) -> Path:
    return tmp_path / "proto" / ".claude" / "worktrees" / BRANCH


def _shell(**overrides: Reply) -> Shell:
    answers: dict[tuple[str, ...], Reply] = {
        ("rev-parse", "--abbrev-ref", "HEAD"): overrides.get("branch", f"{BRANCH}\n"),
        ("ls-remote",): REMOTE_HEAD,
        ("status", "--porcelain"): overrides.get("status", ""),
        ("rev-list", "--count"): overrides.get("ahead", "2\n"),
        ("grep",): overrides.get("grep", failed("git grep")),
        ("diff",): overrides.get("added", ""),
    }
    for words in (("merge", "--no-ff"), ("push",), ("sh", "-c")):
        if words[0] in overrides:
            answers[words] = overrides[words[0]]
    return Shell(answers)


def _assert_nothing_changed(shell: Shell) -> None:
    assert not shell.ran("fetch")
    assert not shell.ran("worktree", "add")
    assert not shell.ran("push")
    assert not shell.ran("branch", "-D")


@pytest.mark.parametrize(
    ("check", "overrides", "reason"),
    [
        ("make check", {"branch": "fix-32-lone-ticket\n"}, "lone ticket's worktree"),
        ("make check", {"branch": "docs-fix-typos\n"}, "docs ticket's worktree"),
        ("make check", {"status": " M app.py\n"}, "uncommitted changes:\n M app.py"),
        ("make check", {"ahead": "0\n"}, "no commits ahead of origin/spec-25"),
        (None, {}, "declares no check command"),
    ],
    ids=["lone ticket", "docs ticket", "uncommitted changes", "nothing ahead", "no check key"],
)
def test_integrate_refuses_before_changing_anything(tmp_path, check, overrides, reason):
    projects = _setup(tmp_path, check=check)
    shell = _shell(**overrides)

    with pytest.raises(RefusalError, match=reason):
        integrate(_worktree(tmp_path), shell, home=home_for(projects), say=quiet)

    _assert_nothing_changed(shell)


def test_integrate_refuses_a_path_that_is_no_ticket_worktree(tmp_path):
    projects = _setup(tmp_path)
    shell = _shell()

    with pytest.raises(RefusalError, match="not a registered project's ticket worktree"):
        integrate(tmp_path, shell, home=home_for(projects), say=quiet)

    _assert_nothing_changed(shell)


def test_a_leak_on_a_public_project_is_refused_with_nothing_pushed_and_no_scratch_left(tmp_path):
    projects = _setup(tmp_path, public=True)
    shell = _shell(grep="README.md:3:see /fixture/home\n")

    with pytest.raises(RefusalError, match="leak check"):
        integrate(_worktree(tmp_path), shell, home=home_for(projects), say=quiet)

    assert not shell.ran("push")
    assert len(shell.ran("worktree", "remove", "--force")) == 1


def test_a_private_project_pointing_outside_the_home_is_refused_with_nothing_pushed(tmp_path):
    projects = _setup(tmp_path)
    shell = _shell(grep="README.md:3:see owner/secret\n")

    with pytest.raises(RefusalError, match=r"README\.md:3: unregistered repo owner/secret"):
        integrate(_worktree(tmp_path), shell, home=home_for(projects), say=quiet)

    assert not shell.ran("push")
    assert len(shell.ran("worktree", "remove", "--force")) == 1


def test_a_project_that_declares_no_check_skips_it_and_says_so(tmp_path):
    projects = _setup(tmp_path, check="none")
    shell = _shell()
    lines: list[str] = []

    integrate(_worktree(tmp_path), shell, home=home_for(projects), say=lines.append)

    assert not shell.ran("sh", "-c")
    assert "skipped the check: the project declares none" in lines
    assert shell.ran("push")


def test_integrate_pushes_only_the_integration_branch_never_the_ticket_branch(tmp_path):
    projects = _setup(tmp_path)
    shell = _shell()

    integrate(_worktree(tmp_path), shell, home=home_for(projects), say=quiet)

    assert [cmd[3:] for cmd in shell.ran("push")] == [["push", "origin", "HEAD:refs/heads/spec-25"]]


def test_the_merge_subject_names_the_ticket_branch(tmp_path):
    projects = _setup(tmp_path)
    shell = _shell()

    integrate(_worktree(tmp_path), shell, home=home_for(projects), say=quiet)

    (merge,) = shell.ran("merge", "--no-ff")
    assert merge[merge.index("-m") + 1] == f"Integrate {BRANCH} into spec-25"


def test_a_dry_run_issues_only_queries(tmp_path):
    projects = _setup(tmp_path, public=True)
    shell = _shell()
    lines: list[str] = []

    integrate(_worktree(tmp_path), shell, home=home_for(projects), dry_run=True, say=lines.append)

    queries = {("rev-parse",), ("ls-remote",), ("for-each-ref",), ("status",), ("rev-list",)}
    assert all(any(cmd[3:4] == list(q) for q in queries) for cmd in shell.calls)
    assert "would push the merge to spec-25" in lines


def test_a_mid_run_error_follows_the_steps_already_done(kaizen, capsys):
    # The CLI runs from the fixture home, so the worktree sits under relay's worktree root.
    shell = _shell(push=failed("git push", "fatal: unable to access origin"))
    worktree = RELAY / ".claude" / "worktrees" / BRANCH

    assert kaizen(["spec", "integrate", str(worktree)], run=shell) == 1

    captured = capsys.readouterr()
    out = captured.out.splitlines()
    assert out[-4].startswith(f"merged {BRANCH} into origin/spec-25")
    assert out[-3] == "check passed: bash scripts/check.sh"
    assert out[-2] == "leak check found nothing"
    assert out[-1].startswith("removed scratch worktree ")
    assert captured.err.startswith("error: git push failed")
    assert not shell.ran("branch", "-D")
