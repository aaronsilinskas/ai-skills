"""Tests for ``kaizen ticket abandon``: the checks before an unmerged ticket is dropped, and the
drop.

git and gh are replaced by a recording runner and the registry by a temporary ``projects/``
directory, so no repo, network or real project page is touched.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError
from kaizen.tests.ticket_shell import Reply, Shell, failed, home_for, install_hook, quiet
from kaizen.ticket.abandon import abandon

BRANCH = "fix-53-retry-the-flaky-upload"
PR_OPEN = (
    '[{"state": "OPEN", "headRefOid": "a1b2c3d4", "number": 77,'
    ' "url": "https://github.com/owner/proto/pull/77"}]'
)
ON_ORIGIN = f"a1b2c3d4\trefs/heads/{BRANCH}\n"


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    """A registry with one project, ``proto``, and the path of its ticket worktree."""
    projects = tmp_path / "projects"
    projects.mkdir()
    repo = tmp_path / "proto"
    (projects / "proto.md").write_text(
        f"---\npath: {repo}\ngithub: owner/proto\npublic: true\n---\n# proto\n"
    )
    return projects, repo / ".claude" / "worktrees" / BRANCH


def _shell(**overrides: Reply) -> Shell:
    answers: dict[tuple[str, ...], Reply] = {
        ("rev-parse", "--abbrev-ref", "HEAD"): overrides.get("branch", f"{BRANCH}\n"),
        ("ls-remote", "--heads"): overrides.get("remote_branch", ON_ORIGIN),
        ("ls-remote",): "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n",
        ("pr", "list"): overrides.get("pr", PR_OPEN),
        ("status", "--porcelain"): overrides.get("status", ""),
        ("rev-list", "--count"): overrides.get("ahead", "2\n"),
        ("rev-parse", "HEAD"): overrides.get("head", "a1b2c3d4\n"),
        ("worktree", "list"): overrides.get("worktrees", ""),
        ("merge-base", "--is-ancestor"): overrides.get("is_ancestor", ""),
        ("--git-common-dir",): ".git\n",
    }
    return Shell(answers)


def _abandon(
    tmp_path: Path,
    shell: Shell,
    *,
    force: bool = False,
    reason: str | None = None,
    dry_run: bool = False,
    say: Callable[[str], None] = quiet,
) -> Path:
    """Runs ``abandon`` on the ticket worktree from *tmp_path*, outside it; returns the path."""
    projects, worktree = _setup(tmp_path)
    abandon(
        worktree,
        shell,
        home=home_for(projects),
        cwd=tmp_path,
        force=force,
        reason=reason,
        dry_run=dry_run,
        say=say,
    )
    return worktree


def _mutations(shell: Shell) -> list[list[str]]:
    """Every mutating git and gh command, in the order it ran."""
    mutating = (("pr", "close"), ("push",), ("worktree", "remove"), ("branch", "-D"))
    found = [cmd for words in mutating for cmd in shell.ran(*words)]
    return [cmd for cmd in shell.calls if cmd in found]


def test_abandon_closes_the_pr_deletes_both_branches_and_removes_the_worktree_in_order(tmp_path):
    shell = _shell()

    worktree = _abandon(tmp_path, shell)

    repo = str(tmp_path / "proto")
    assert _mutations(shell) == [
        ["gh", "-R", "owner/proto", "pr", "close", "77"],
        ["git", "-C", repo, "push", "-q", "origin", "--delete", BRANCH],
        ["git", "-C", repo, "worktree", "remove", str(worktree)],
        ["git", "-C", repo, "branch", "-D", BRANCH],
    ]


def test_abandon_posts_the_reason_as_the_pr_close_comment(tmp_path):
    shell = _shell()

    _abandon(tmp_path, shell, reason="Superseded by #80")

    assert shell.ran("pr", "close") == [
        ["gh", "-R", "owner/proto", "pr", "close", "77", "--comment", "Superseded by #80"]
    ]


def test_abandon_of_a_ticket_never_shipped_only_removes_the_worktree_and_local_branch(tmp_path):
    shell = _shell(pr="[]", remote_branch="")

    _abandon(tmp_path, shell)

    assert [cmd[3:5] for cmd in _mutations(shell)] == [["worktree", "remove"], ["branch", "-D"]]


def test_abandon_refuses_a_merged_ticket_and_points_at_finish(tmp_path):
    shell = _shell(pr=PR_OPEN.replace("OPEN", "MERGED"))

    with pytest.raises(RefusalError, match=r"PR #77 .* merged (.|\n)*kaizen ticket finish"):
        _abandon(tmp_path, shell)

    assert not _mutations(shell)


def test_abandon_refuses_a_worktree_with_uncommitted_changes(tmp_path):
    shell = _shell(status=" M src/app.py\n?? notes.txt\n")

    with pytest.raises(RefusalError, match=r"uncommitted changes(.|\n)*notes\.txt(.|\n)*--force"):
        _abandon(tmp_path, shell)

    assert not _mutations(shell)


def test_abandon_with_force_removes_a_worktree_with_uncommitted_changes(tmp_path):
    shell = _shell(status="?? notes.txt\n")

    worktree = _abandon(tmp_path, shell, force=True)

    repo = str(tmp_path / "proto")
    assert shell.ran("worktree", "remove") == [
        ["git", "-C", repo, "worktree", "remove", "--force", str(worktree)]
    ]
    assert shell.ran("branch", "-D")


def test_abandon_refuses_a_spec_ticket_worktree(tmp_path):
    shell = _shell(branch="spec-25-fix-53-retry-the-flaky-upload\n")

    with pytest.raises(RefusalError, match="ticket worktree of spec #25"):
        _abandon(tmp_path, shell)

    assert not _mutations(shell)


def test_abandon_refuses_to_run_from_inside_the_worktree_it_removes(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell()

    with pytest.raises(RefusalError, match="runs inside the worktree"):
        abandon(worktree, shell, home=home_for(projects), cwd=worktree / "src", say=quiet)

    assert not _mutations(shell)


def test_a_dry_run_runs_every_check_but_changes_nothing(tmp_path):
    shell = _shell()
    lines: list[str] = []

    worktree = _abandon(tmp_path, shell, dry_run=True, say=lines.append)

    assert shell.ran("status", "--porcelain")
    assert not _mutations(shell)
    assert "would close PR #77: https://github.com/owner/proto/pull/77" in lines
    assert f"would remove worktree {worktree}" in lines


def test_abandon_drops_commits_made_after_an_earlier_pr_from_the_branch_merged(tmp_path):
    shell = _shell(pr=PR_OPEN.replace("OPEN", "MERGED"), head="ffff9999\n")

    _abandon(tmp_path, shell)

    assert shell.ran("merge-base", "--is-ancestor", "a1b2c3d4", "HEAD")
    assert shell.ran("branch", "-D")
    assert not shell.ran("pr", "close")


def test_abandon_refuses_a_locked_worktree(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell(worktrees=f"worktree {worktree}\nHEAD a1b2c3d4\nbranch x\nlocked\n\n")

    with pytest.raises(RefusalError, match=r"is locked(.|\n)*worktree unlock"):
        abandon(worktree, shell, home=home_for(projects), cwd=tmp_path, say=quiet)

    assert not _mutations(shell)


def test_a_dry_run_names_the_close_comment_it_would_post(tmp_path):
    shell = _shell()
    lines: list[str] = []

    _abandon(tmp_path, shell, reason="Superseded", dry_run=True, say=lines.append)

    assert any("Superseded" in line for line in lines)


def test_abandon_refuses_a_merged_pr_whose_head_the_branch_does_not_build_on(tmp_path):
    shell = _shell(
        pr=PR_OPEN.replace("OPEN", "MERGED"),
        head="0ld0ld00\n",
        is_ancestor=failed("git merge-base", "fatal: bad object"),
    )

    with pytest.raises(RefusalError, match="does not build on"):
        _abandon(tmp_path, shell)

    assert not _mutations(shell)


@pytest.mark.parametrize("dry_run", [False, True])
def test_abandon_refuses_while_the_shared_hook_runs_from_the_worktree(tmp_path, dry_run):
    checkout = tmp_path / "proto"
    install_hook(checkout, checkout / ".claude" / "worktrees" / BRANCH / ".venv" / "bin" / "python")
    shell = _shell()

    with pytest.raises(RefusalError, match=r"pre-commit hook(.|\n)*uv run pre-commit install"):
        _abandon(tmp_path, shell, dry_run=dry_run)

    assert _mutations(shell) == []


def test_abandon_removes_the_worktree_and_keeps_a_hook_installed_from_the_main_checkout(tmp_path):
    checkout = tmp_path / "proto"
    hook = install_hook(checkout, checkout / ".venv" / "bin" / "python")
    written = hook.read_text()
    shell = _shell()

    _abandon(tmp_path, shell)

    assert shell.ran("worktree", "remove")
    assert hook.read_text() == written
