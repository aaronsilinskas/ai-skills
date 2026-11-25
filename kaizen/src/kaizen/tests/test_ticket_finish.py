"""Tests for ``kaizen ticket finish``: the checks before a ticket worktree is removed, and the
cleanup.

git and gh are replaced by a recording runner and the registry by a temporary ``projects/``
directory, so no repo, network or real project page is touched.
"""

import subprocess
from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError
from kaizen.tests.ticket_shell import (
    MAIN_CHECKOUT_BEHIND,
    Reply,
    Shell,
    failed,
    home_for,
    install_hook,
    quiet,
)
from kaizen.ticket.finish import finish

BRANCH = "fix-1358-each-reboot-writes-app-state"
HEAD = "a1b2c3d4"
PR_MERGED = (
    '[{"state": "MERGED", "headRefOid": "a1b2c3d4", "number": 1385,'
    ' "url": "https://github.com/owner/proto/pull/1385"}]'
)


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
        ("ls-remote", "--heads"): overrides.get("remote_branch", ""),
        ("ls-remote",): "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n",
        ("pr", "list"): overrides.get("pr", PR_MERGED),
        ("rev-parse", "HEAD"): overrides.get("head", f"{HEAD}\n"),
        ("fetch", "-q", "origin", "pull/1385/head"): overrides.get("fetch_pr", ""),
        ("merge-base", "--is-ancestor"): overrides.get("ancestor", ""),
        ("status", "--porcelain"): overrides.get("status", ""),
        ("--git-common-dir",): ".git\n",
        **MAIN_CHECKOUT_BEHIND,
        ("symbolic-ref",): overrides.get("checkout_branch", "main\n"),
    }
    return Shell(answers)


def _assert_nothing_removed(shell: Shell) -> None:
    assert not shell.ran("worktree", "remove")
    assert not shell.ran("branch", "-D")
    assert not shell.ran("update-ref", "-d")


def test_finish_removes_the_worktree_force_deletes_the_branch_and_prunes_in_that_order(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell()

    finish(worktree, shell, home=home_for(projects), say=quiet)

    repo = str(tmp_path / "proto")
    cleanup = (["worktree", "remove"], ["branch", "-D"], ["update-ref", "-d"])
    assert [cmd for cmd in shell.calls if cmd[3:5] in cleanup] == [
        ["git", "-C", repo, "worktree", "remove", str(worktree)],
        ["git", "-C", repo, "branch", "-D", BRANCH],
        ["git", "-C", repo, "update-ref", "-d", f"refs/remotes/origin/{BRANCH}"],
    ]


def test_finish_prunes_only_this_branchs_remote_tracking_ref(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell()

    finish(worktree, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("prune")
    assert not shell.ran("--prune")


def test_finish_keeps_the_remote_tracking_ref_while_origin_still_has_the_branch(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell(remote_branch=f"a1b2c3d4\trefs/heads/{BRANCH}\n")

    finish(worktree, shell, home=home_for(projects), say=quiet)

    assert shell.ran("branch", "-D")
    assert not shell.ran("update-ref", "-d")


def test_finish_refuses_while_the_pr_is_still_open_and_removes_nothing(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell(pr=PR_MERGED.replace("MERGED", "OPEN"))

    with pytest.raises(RefusalError, match=r"PR #1385 .* is OPEN, not MERGED"):
        finish(worktree, shell, home=home_for(projects), say=quiet)

    _assert_nothing_removed(shell)


def test_finish_refuses_a_branch_with_no_pr(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell(pr="[]")

    with pytest.raises(RefusalError, match=f"no PR from {BRANCH} in owner/proto"):
        finish(worktree, shell, home=home_for(projects), say=quiet)

    _assert_nothing_removed(shell)


def test_finish_removes_a_branch_whose_head_the_merged_pr_built_on_after_fetching_its_head(
    tmp_path,
):
    projects, worktree = _setup(tmp_path)
    shell = _shell(head="0ld0ld00\n")

    finish(worktree, shell, home=home_for(projects), say=quiet)

    path = str(worktree)
    fetch = ["git", "-C", path, "fetch", "-q", "origin", "pull/1385/head"]
    ancestry = ["git", "-C", path, "merge-base", "--is-ancestor", "0ld0ld00", HEAD]
    assert shell.calls.index(fetch) < shell.calls.index(ancestry)
    assert shell.ran("branch", "-D")


def test_finish_says_the_pr_gained_commits_on_github_when_it_built_on_the_branch_head(tmp_path):
    projects, worktree = _setup(tmp_path)
    lines: list[str] = []

    finish(worktree, _shell(head="0ld0ld00\n"), home=home_for(projects), say=lines.append)

    assert any("PR #1385 gained commits on GitHub" in line for line in lines)


def test_finish_refuses_when_git_cannot_tell_whether_the_merged_pr_built_on_the_head(tmp_path):
    projects, worktree = _setup(tmp_path)
    broken = subprocess.CalledProcessError(128, ["git"], output="", stderr="fatal: bad object")
    shell = _shell(head="0ld0ld00\n", ancestor=broken)

    with pytest.raises(RefusalError, match=r"could not compare(.|\n)*bad object"):
        finish(worktree, shell, home=home_for(projects), say=quiet)

    _assert_nothing_removed(shell)


def test_a_dry_run_fetches_the_merged_prs_head_to_check_a_head_it_built_on(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell(head="0ld0ld00\n")

    finish(worktree, shell, home=home_for(projects), dry_run=True, say=quiet)

    assert shell.ran("fetch", "-q", "origin", "pull/1385/head")
    _assert_nothing_removed(shell)


def test_finish_keeps_the_branch_when_its_head_has_commits_the_merged_pr_lacks(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell(head="ffff9999\n", ancestor=failed("git merge-base --is-ancestor"))

    with pytest.raises(RefusalError, match=r"head ffff9999 is not PR #1385's head a1b2c3d4"):
        finish(worktree, shell, home=home_for(projects), say=quiet)

    _assert_nothing_removed(shell)


def test_finish_refuses_when_it_cannot_fetch_the_merged_prs_head(tmp_path):
    projects, worktree = _setup(tmp_path)
    fetch_failed = failed("git fetch", stderr="fatal: could not read from remote repository")
    shell = _shell(head="0ld0ld00\n", fetch_pr=fetch_failed)

    with pytest.raises(RefusalError, match=r"could not fetch PR #1385's head(.|\n)*remote"):
        finish(worktree, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("merge-base")
    _assert_nothing_removed(shell)


def test_finish_refuses_a_head_the_merged_pr_built_on_while_the_worktree_is_dirty(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell(head="0ld0ld00\n", status=" M src/app.py\n")

    with pytest.raises(RefusalError, match="uncommitted changes"):
        finish(worktree, shell, home=home_for(projects), say=quiet)

    _assert_nothing_removed(shell)


def test_finish_refuses_a_worktree_with_uncommitted_changes(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell(status=" M src/app.py\n?? notes.txt\n")

    with pytest.raises(RefusalError, match=r"uncommitted changes(.|\n)*notes\.txt"):
        finish(worktree, shell, home=home_for(projects), say=quiet)

    _assert_nothing_removed(shell)


def test_finish_refuses_a_path_outside_every_project_worktree_root(tmp_path):
    projects, _ = _setup(tmp_path)
    shell = _shell()

    with pytest.raises(RefusalError, match="not a registered project's ticket worktree"):
        finish(tmp_path / "proto", shell, home=home_for(projects), say=quiet)

    assert not shell.calls


def test_finish_refuses_a_worktree_whose_branch_is_not_a_ticket_branch(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell(branch="spike\n")

    with pytest.raises(RefusalError, match="on 'spike', not a fix-<issue>-<slug> ticket branch"):
        finish(worktree, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("pr", "list")
    _assert_nothing_removed(shell)


def test_finish_finds_the_project_from_a_worktree_under_its_worktree_root(tmp_path):
    projects, _ = _setup(tmp_path)
    page = projects / "proto.md"
    page.write_text(
        page.read_text().replace(
            "public: true\n", f"public: true\nworktree_root: {tmp_path}/outside\n"
        )
    )
    shell = _shell()

    finish(tmp_path / "outside" / BRANCH, shell, home=home_for(projects), say=quiet)

    assert shell.ran("branch", "-D") == [
        ["git", "-C", str(tmp_path / "proto"), "branch", "-D", BRANCH]
    ]


def test_a_dry_run_runs_every_check_but_removes_nothing(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell()
    lines: list[str] = []

    finish(worktree, shell, home=home_for(projects), dry_run=True, say=lines.append)

    assert shell.ran("status", "--porcelain")
    _assert_nothing_removed(shell)
    assert not shell.ran("fetch")
    assert f"would remove worktree {worktree}" in lines


def test_finish_fast_forwards_the_main_checkouts_default_branch_after_the_cleanup(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell()

    finish(worktree, shell, home=home_for(projects), say=quiet)

    repo = str(tmp_path / "proto")
    merge = ["git", "-C", repo, "merge", "--ff-only", "-q", "origin/main"]
    assert shell.ran("merge") == [merge]
    assert shell.calls.index(merge) > shell.calls.index(shell.ran("update-ref", "-d")[0])


def test_finish_still_succeeds_when_the_fast_forward_is_skipped(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell(checkout_branch="spike\n")
    lines: list[str] = []

    finish(worktree, shell, home=home_for(projects), say=lines.append)

    assert not shell.ran("merge")
    assert "the main checkout is on spike, not main" in lines[-2]


def test_a_dry_run_says_whether_it_would_fast_forward_the_main_checkout_without_merging(tmp_path):
    projects, worktree = _setup(tmp_path)
    shell = _shell()
    lines: list[str] = []

    finish(worktree, shell, home=home_for(projects), dry_run=True, say=lines.append)

    assert not shell.ran("merge")
    assert lines[-1] == "would fast-forward main from 1111111 to 2222222 (as last fetched)"


def test_finish_prints_each_step_then_says_to_change_nothing_else_in_the_main_checkout(tmp_path):
    projects, worktree = _setup(tmp_path)
    lines: list[str] = []

    finish(worktree, _shell(), home=home_for(projects), say=lines.append)

    assert lines[-5:-1] == [
        f"removed worktree {worktree}",
        f"deleted local branch {BRANCH}",
        f"pruned the stale remote-tracking ref origin/{BRANCH}",
        "fast-forwarded main from 1111111 to 2222222",
    ]
    assert (
        "leave the rest of the main checkout as it is, since other sessions work there"
        in (lines[-1])
    )


def test_finish_explains_why_git_may_call_the_branch_unmerged_in_the_main_checkout(tmp_path):
    projects, worktree = _setup(tmp_path)
    lines: list[str] = []

    finish(worktree, _shell(), home=home_for(projects), say=lines.append)

    assert "not yet merged to HEAD" in lines[-1]


@pytest.mark.parametrize("dry_run", [False, True])
def test_finish_refuses_a_spec_ticket_worktree_and_points_to_spec_integrate(tmp_path, dry_run):
    projects, worktree = _setup(tmp_path)
    shell = _shell(branch="spec-25-fix-1358-each-reboot\n")

    with pytest.raises(RefusalError, match=r"spec #25(.|\n)*kaizen spec integrate"):
        finish(worktree, shell, home=home_for(projects), dry_run=dry_run, say=quiet)

    _assert_nothing_removed(shell)
    assert not shell.ran("pr", "list")


def test_the_cli_runs_finish_and_exits_nonzero_on_a_refusal(kaizen, tmp_path, capsys):

    code = kaizen(["ticket", "finish", str(tmp_path / "nowhere")], run=_shell())

    assert code == 1
    assert "ticket worktree" in capsys.readouterr().err


def test_finish_removes_the_worktree_and_branch_of_a_merged_docs_change(tmp_path):
    projects, _ = _setup(tmp_path)
    worktree = tmp_path / "proto" / ".claude" / "worktrees" / "docs-fix-typos"
    shell = _shell(branch="docs-fix-typos\n")
    lines: list[str] = []

    finish(worktree, shell, home=home_for(projects), say=lines.append)

    assert shell.ran("pr", "list", "--head", "docs-fix-typos")
    assert shell.ran("worktree", "remove", str(worktree))
    assert shell.ran("branch", "-D", "docs-fix-typos")
    assert lines[0] == f"{worktree} is proto's ticket worktree for a docs change"


@pytest.mark.parametrize("dry_run", [False, True])
def test_finish_refuses_while_the_shared_hook_runs_from_the_worktree(tmp_path, dry_run):
    projects, worktree = _setup(tmp_path)
    install_hook(tmp_path / "proto", worktree / ".venv" / "bin" / "python")
    shell = _shell()

    with pytest.raises(RefusalError, match=r"pre-commit hook(.|\n)*uv run pre-commit install"):
        finish(worktree, shell, home=home_for(projects), dry_run=dry_run, say=quiet)

    _assert_nothing_removed(shell)


def test_finish_removes_the_worktree_and_keeps_a_hook_installed_from_the_main_checkout(tmp_path):
    projects, worktree = _setup(tmp_path)
    checkout = tmp_path / "proto"
    hook = install_hook(checkout, checkout / ".venv" / "bin" / "python")
    written = hook.read_text()
    shell = _shell()

    finish(worktree, shell, home=home_for(projects), say=quiet)

    assert shell.ran("worktree", "remove")
    assert hook.read_text() == written
