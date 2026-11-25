"""Tests for ``kaizen spec start``: creating and pushing a spec's integration branch.

git and gh are replaced by a recording runner and the registry by a temporary ``projects/``
directory, so no repo, network or real project page is touched.
"""

from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError
from kaizen.spec.start import start
from kaizen.tests.ticket_shell import Shell, failed, home_for, proto_projects, quiet

SPEC_OPEN = '{"state": "OPEN", "title": "One CLI for relay", "labels": [{"name": "spec"}]}'
REMOTE_HEAD = "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n"


def _shell(tmp_path: Path, **overrides: str | BaseException) -> Shell:
    return Shell(
        {
            ("rev-parse", "--show-toplevel"): overrides.get("toplevel", f"{tmp_path / 'proto'}\n"),
            ("issue", "view"): overrides.get("issue", SPEC_OPEN),
            ("ls-remote", "--heads"): overrides.get("heads", ""),
            ("ls-remote", "--symref"): REMOTE_HEAD,
            ("for-each-ref",): overrides.get("local", ""),
            ("worktree", "list"): overrides.get("worktrees", ""),
            ("grep",): overrides.get("leaks", failed("git grep")),
            ("push",): overrides.get("push", ""),
        }
    )


def _start(tmp_path: Path, shell: Shell, public: bool = True, **kwargs) -> None:
    start(25, shell, home=home_for(proto_projects(tmp_path, public)), say=quiet, **kwargs)


def test_start_pushes_the_integration_branch_from_the_remote_default_branch(tmp_path):
    shell = _shell(tmp_path)

    _start(tmp_path, shell)

    repo = str(tmp_path / "proto")
    assert shell.ran("fetch") == [["git", "-C", repo, "fetch", "origin"]]
    assert shell.ran("push") == [
        ["git", "-C", repo, "push", "origin", "refs/remotes/origin/main:refs/heads/spec-25"]
    ]


def _refused(tmp_path: Path, shell: Shell, match: str, public: bool = True) -> None:
    with pytest.raises(RefusalError, match=match):
        _start(tmp_path, shell, public)
    assert not shell.ran("fetch")
    assert not shell.ran("push")


@pytest.mark.parametrize(
    ("issue", "match"),
    [
        (
            '{"state": "CLOSED", "title": "Old", "labels": [{"name": "spec"}]}',
            "#25 is closed",
        ),
        (
            '{"state": "OPEN", "title": "A ticket", "labels": [{"name": "ready-for-agent"}]}',
            "#25 is not labelled spec",
        ),
    ],
    ids=["closed", "not a spec"],
)
def test_start_refuses_an_issue_that_is_not_an_open_spec(tmp_path, issue, match):
    _refused(tmp_path, _shell(tmp_path, issue=issue), match)


def test_start_refuses_an_issue_gh_cannot_read(tmp_path):
    shell = _shell(tmp_path, issue=failed("gh issue view", "Could not resolve to an issue"))

    _refused(tmp_path, shell, "could not read issue #25 in owner/proto")


def test_start_refuses_a_spec_already_started_and_says_how_to_continue(tmp_path):
    shell = _shell(tmp_path, heads="def456\trefs/heads/spec-25\n")

    _refused(
        tmp_path,
        shell,
        r"origin already has spec-25(.|\n)*fix: .*`kaizen ticket start proto <issue> --spec 25`",
    )


def test_start_refuses_a_public_project_whose_default_branch_leaks_and_pushes_nothing(tmp_path):
    shell = _shell(tmp_path, leaks="origin/main:docs/setup.md:3:see /fixture/home/relay\n")

    with pytest.raises(RefusalError, match=r"leak check(.|\n)*docs/setup\.md:3"):
        _start(tmp_path, shell)

    assert not shell.ran("push")


def test_the_leak_check_searches_the_commit_being_pushed(tmp_path):
    shell = _shell(tmp_path)

    _start(tmp_path, shell)

    (grep,) = shell.ran("grep")
    assert grep[:3] == ["git", "-C", str(tmp_path / "proto")]
    assert grep[-1] == "origin/main"


def test_start_refuses_a_private_project_whose_default_branch_points_outside_the_home(tmp_path):
    shell = _shell(tmp_path, leaks="origin/main:docs/setup.md:3:see owner/secret\n")

    with pytest.raises(RefusalError, match=r"docs/setup\.md:3: unregistered repo owner/secret"):
        _start(tmp_path, shell, public=False)

    assert not shell.ran("push")


def test_start_prints_one_line_per_completed_step(tmp_path):
    lines: list[str] = []

    start(25, _shell(tmp_path), home=home_for(proto_projects(tmp_path)), say=lines.append)

    repo = tmp_path / "proto"
    assert lines == [
        f"proto project at {repo}",
        "spec #25 is open: One CLI for relay",
        "origin has no spec-25 yet",
        f"fetched origin in {repo} (default branch main)",
        "leak check found nothing in origin/main",
        "pushed spec-25 to origin from origin/main",
        "start ticket worktrees with `kaizen ticket start proto <issue> --spec 25`",
    ]


def test_a_dry_run_issues_only_queries_and_prints_the_plan(tmp_path):
    shell = _shell(tmp_path)
    lines: list[str] = []

    start(25, shell, home=home_for(proto_projects(tmp_path)), dry_run=True, say=lines.append)

    assert not shell.ran("fetch")
    assert not shell.ran("push")
    assert lines[-3:] == [
        f"would fetch origin in {tmp_path / 'proto'}",
        "would run the leak check on origin/main",
        "would push spec-25 to origin from origin/main",
    ]


def test_start_refuses_to_run_outside_a_registered_projects_main_checkout(tmp_path):
    shell = _shell(tmp_path, toplevel="/somewhere/else\n")

    with pytest.raises(RefusalError, match=r"/somewhere/else is not a registered project"):
        _start(tmp_path, shell)

    assert not shell.ran("issue", "view")


def test_start_refuses_to_run_outside_any_git_checkout(tmp_path):
    shell = _shell(tmp_path, toplevel=failed("git rev-parse", "fatal: not a git repository"))

    with pytest.raises(RefusalError, match="not a git repository"):
        _start(tmp_path, shell)


def test_a_local_start_creates_the_branch_from_the_remote_default_and_pushes_nothing(tmp_path):
    shell = _shell(tmp_path)
    lines: list[str] = []

    start(25, shell, home=home_for(proto_projects(tmp_path)), local=True, say=lines.append)

    repo = str(tmp_path / "proto")
    assert shell.ran("branch") == [
        ["git", "-C", repo, "branch", "--no-track", "spec-25", "refs/remotes/origin/main"]
    ]
    assert not shell.ran("push")
    assert "created the local branch spec-25 from origin/main; nothing was pushed" in lines


def test_a_local_dry_run_issues_only_queries_and_prints_the_plan(tmp_path):
    shell = _shell(tmp_path)
    lines: list[str] = []

    start(
        25,
        shell,
        home=home_for(proto_projects(tmp_path)),
        local=True,
        dry_run=True,
        say=lines.append,
    )

    assert not shell.ran("fetch")
    assert not shell.ran("branch")
    assert not shell.ran("push")
    assert lines[-1] == "would create the local branch spec-25 from origin/main, pushing nothing"


def test_a_local_start_refuses_a_spec_already_started_locally(tmp_path):
    shell = _shell(tmp_path, local="abc123\n")

    with pytest.raises(RefusalError, match=r"spec-25 already exists locally"):
        _start(tmp_path, shell, local=True)
    assert not shell.ran("branch")
    assert not shell.ran("push")


def test_start_pushes_a_local_branch_an_earlier_local_start_made_then_deletes_it(tmp_path):
    shell = _shell(tmp_path, local="abc123\n")

    _start(tmp_path, shell)

    repo = str(tmp_path / "proto")
    assert shell.ran("push") == [
        ["git", "-C", repo, "push", "origin", "refs/heads/spec-25:refs/heads/spec-25"]
    ]
    assert shell.ran("branch", "-D") == [["git", "-C", repo, "branch", "-D", "spec-25"]]
    (grep,) = shell.ran("grep")
    assert grep[-1] == "spec-25"


def test_start_refuses_to_push_a_local_branch_a_checkout_has_checked_out(tmp_path):
    worktrees = f"worktree {tmp_path / 'proto'}\nHEAD abc123\nbranch refs/heads/spec-25\n\n"
    shell = _shell(tmp_path, local="abc123\n", worktrees=worktrees)

    with pytest.raises(RefusalError, match=r"spec-25 is checked out in"):
        _start(tmp_path, shell)
    assert not shell.ran("push")
