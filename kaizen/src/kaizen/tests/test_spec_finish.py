"""Tests for ``kaizen spec finish``: the checks before a spec's integration branch is cleaned up.

git and gh are replaced by a recording runner and the registry by a temporary ``projects/``
directory, so no repo, network or real project page is touched.
"""

import json
from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError
from kaizen.spec.finish import finish
from kaizen.tests.ticket_shell import (
    MAIN_CHECKOUT_BEHIND,
    RELAY,
    Reply,
    Shell,
    failed,
    home_for,
    sub_issue_json,
)

HEAD = "a1b2c3d4"
PR_URL = "https://github.com/owner/proto/pull/40"


def _prs(state: str = "MERGED", head: str = HEAD) -> str:
    return json.dumps([{"number": 40, "state": state, "url": PR_URL, "headRefOid": head}])


def _sub_issues(*issues: tuple[int, str]) -> str:
    return "".join(sub_issue_json(n, s) for n, s in issues)


def _setup(tmp_path: Path) -> Path:
    """A registry with one project, ``proto``."""
    projects = tmp_path / "projects"
    projects.mkdir()
    page = f"---\npath: {tmp_path / 'proto'}\ngithub: owner/proto\npublic: true\n---\n"
    (projects / "proto.md").write_text(page)
    return projects


def _shell(tmp_path: Path, **overrides: Reply) -> Shell:
    return Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{tmp_path / 'proto'}\n",
            ("pr", "list"): overrides.get("prs", _prs()),
            ("for-each-ref",): overrides.get("local", f"{HEAD}\n"),
            ("ls-remote", "--heads"): overrides.get("heads", ""),
            ("worktree", "list"): overrides.get("worktrees", ""),
            ("gh", "api"): overrides.get("sub_issues", _sub_issues((28, "closed"))),
            **MAIN_CHECKOUT_BEHIND,
            ("symbolic-ref",): overrides.get("checkout_branch", "main\n"),
        }
    )


def _quiet(_: str) -> None:
    pass


def _finish(tmp_path: Path, shell: Shell, **kwargs) -> None:
    finish(25, shell, home=home_for(_setup(tmp_path)), say=_quiet, **kwargs)


def test_finish_deletes_the_local_integration_branch_then_prunes_its_stale_tracking_ref(tmp_path):
    shell = _shell(tmp_path)

    _finish(tmp_path, shell)

    repo = str(tmp_path / "proto")
    assert [cmd for cmd in shell.calls if cmd[3:4] in (["branch"], ["update-ref"])] == [
        ["git", "-C", repo, "branch", "-D", "spec-25"],
        ["git", "-C", repo, "update-ref", "-d", "refs/remotes/origin/spec-25"],
    ]


def _refused(tmp_path: Path, shell: Shell, match: str, dry_run: bool = False) -> None:
    with pytest.raises(RefusalError, match=match):
        _finish(tmp_path, shell, dry_run=dry_run)
    assert not shell.ran("branch", "-D")
    assert not shell.ran("update-ref")


def test_finish_refuses_a_spec_whose_integration_branch_has_no_pr(tmp_path):
    shell = _shell(tmp_path, prs="[]")

    _refused(tmp_path, shell, r"no PR from spec-25 in owner/proto(.|\n)*`kaizen spec ship 25`")


@pytest.mark.parametrize("state", ["OPEN", "CLOSED"])
def test_finish_refuses_while_the_specs_pr_is_not_merged(tmp_path, state):
    shell = _shell(tmp_path, prs=_prs(state))

    _refused(tmp_path, shell, rf"PR #40 \({PR_URL}\) is {state}, not MERGED")


def test_a_merged_pr_counts_even_when_a_newer_pr_from_the_branch_is_open(tmp_path):
    newer = {"number": 41, "state": "OPEN", "url": PR_URL, "headRefOid": "ffff9999"}
    prs = json.dumps([newer, *json.loads(_prs())])
    shell = _shell(tmp_path, prs=prs)

    _finish(tmp_path, shell)

    assert shell.ran("branch", "-D")


def test_finish_keeps_a_local_integration_branch_with_commits_the_merged_pr_lacks(tmp_path):
    shell = _shell(tmp_path, local="ffff9999\n")

    _refused(tmp_path, shell, rf"spec-25 head ffff9999 is not PR #40's head {HEAD}")


def test_without_a_local_integration_branch_finish_still_prunes_the_stale_tracking_ref(tmp_path):
    shell = _shell(tmp_path, local="")

    _finish(tmp_path, shell)

    assert not shell.ran("branch", "-D")
    assert shell.ran("update-ref", "-d", "refs/remotes/origin/spec-25")


def test_finish_refuses_while_a_checkout_has_the_integration_branch_checked_out(tmp_path):
    repo = tmp_path / "proto"
    worktrees = f"worktree {repo}\nHEAD {HEAD}\nbranch refs/heads/spec-25\n\n"
    shell = _shell(tmp_path, worktrees=worktrees)

    _refused(tmp_path, shell, rf"spec-25 is checked out in {repo}(.|\n)*switch")


def test_finish_keeps_the_tracking_ref_while_origin_still_has_the_branch(tmp_path):
    shell = _shell(tmp_path, heads=f"{HEAD}\trefs/heads/spec-25\n")

    _finish(tmp_path, shell)

    assert shell.ran("branch", "-D")
    assert not shell.ran("update-ref")


def _lines(tmp_path: Path, shell: Shell, dry_run: bool = False) -> list[str]:
    lines: list[str] = []
    finish(25, shell, home=home_for(_setup(tmp_path)), dry_run=dry_run, say=lines.append)
    return lines


def test_finish_lists_each_sub_issue_still_open_by_number_and_title(tmp_path):
    sub_issues = _sub_issues((28, "closed"), (29, "open"), (30, "open"))
    shell = _shell(tmp_path, sub_issues=sub_issues)

    lines = _lines(tmp_path, shell)

    assert "sub-issue(s) of #25 still open: #29 T29, #30 T30" in lines


def test_finish_says_so_when_no_sub_issue_is_open(tmp_path):
    lines = _lines(tmp_path, _shell(tmp_path))

    assert "no sub-issue of #25 is open" in lines


def test_a_dry_run_issues_only_queries_and_prints_the_plan(tmp_path):
    shell = _shell(tmp_path)

    lines = _lines(tmp_path, shell, dry_run=True)

    queries = {"rev-parse", "for-each-ref", "list", "ls-remote", "api", "symbolic-ref", "rev-list"}
    queries |= {"diff", "status"}
    assert all(queries & set(cmd[:5]) for cmd in shell.calls)
    assert lines[-3:] == [
        "would force-delete local branch spec-25",
        "would prune the stale remote-tracking ref origin/spec-25",
        "would fast-forward main from 1111111 to 2222222 (as last fetched)",
    ]


def test_finish_fast_forwards_the_main_checkouts_default_branch_after_the_cleanup(tmp_path):
    shell = _shell(tmp_path)

    _finish(tmp_path, shell)

    merge = ["git", "-C", str(tmp_path / "proto"), "merge", "--ff-only", "-q", "origin/main"]
    assert shell.ran("merge") == [merge]
    assert shell.calls.index(merge) > shell.calls.index(shell.ran("update-ref", "-d")[0])


def test_finish_still_succeeds_when_the_fast_forward_is_skipped(tmp_path):
    shell = _shell(tmp_path, checkout_branch="spike\n")

    lines = _lines(tmp_path, shell)

    assert not shell.ran("merge")
    assert "the main checkout is on spike, not main" in lines[-2]


def test_finish_prints_each_step_then_says_to_change_nothing_else_in_the_main_checkout(tmp_path):
    lines = _lines(tmp_path, _shell(tmp_path))

    repo = tmp_path / "proto"
    assert lines[:-1] == [
        f"proto project at {repo}",
        f"PR #40 is merged: {PR_URL}",
        f"spec-25 head matches the merged PR's head {HEAD}",
        "no sub-issue of #25 is open",
        "deleted local branch spec-25",
        "pruned the stale remote-tracking ref origin/spec-25",
        "fast-forwarded main from 1111111 to 2222222",
    ]
    assert (
        "leave the rest of the main checkout as it is, since other sessions work there"
        in (lines[-1])
    )


def test_without_a_local_branch_finish_says_there_was_none_to_delete(tmp_path):
    lines = _lines(tmp_path, _shell(tmp_path, local=""))

    assert "no local spec-25 to delete" in lines


def test_a_failed_branch_delete_leaves_the_completed_steps_printed_above_the_error(
    kaizen, tmp_path, capsys
):
    shell = Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{RELAY}\n",
            ("pr", "list"): _prs(),
            ("for-each-ref",): f"{HEAD}\n",
            ("branch", "-D"): failed("git branch -D spec-25", "error: cannot lock ref"),
        }
    )

    assert kaizen(["spec", "finish", "25"], run=shell) == 1

    captured = capsys.readouterr()
    assert captured.out.splitlines()[-1] == "no sub-issue of #25 is open"
    assert captured.err.startswith("error: git branch -D spec-25 failed")
