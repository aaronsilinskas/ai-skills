"""Tests for ``kaizen spec status``: a spec's tickets in one table, then its frontier.

git and gh are replaced by a recording runner and the registry by a temporary ``projects/``
directory, so no repo, network or real project page is touched.
"""

import json
from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError
from kaizen.spec.status import status
from kaizen.tests.ticket_shell import (
    RELAY,
    Reply,
    Shell,
    failed,
    home_for,
    proto_projects,
    register,
    sub_issue_json,
)

HEADS = "def456\trefs/heads/spec-25\n"
MERGES = (
    "Integrate spec-25-fix-28-registry-check into spec-25\n"
    "Merge branch 'main' into spec-25\n"
    "Integrate spec-24-fix-29-other-spec into spec-24\n"
)


def _lines(*items: dict[str, object]) -> str:
    return "".join(json.dumps(item) + "\n" for item in items)


def _blocker(number: int, repo: str = "owner/proto", state: str = "open") -> dict[str, object]:
    return {
        "number": number,
        "title": f"B{number}",
        "state": state,
        "repository_url": f"https://api.github.com/repos/{repo}",
    }


def _worktrees(tmp_path: Path, *branches: str) -> str:
    """A ``git worktree list --porcelain`` reply: the main checkout, then one ticket worktree
    per branch under proto's worktree root."""
    proto = tmp_path / "proto"
    out = f"worktree {proto}\nHEAD abc\nbranch refs/heads/main\n\n"
    for branch in branches:
        out += f"worktree {proto / '.claude' / 'worktrees' / branch}\nHEAD abc\n"
        out += f"branch refs/heads/{branch}\n\n"
    return out


def _shell(
    tmp_path: Path,
    sub_issues: list[str],
    blockers: dict[int, list[dict[str, object]]] | None = None,
    **overrides: Reply,
) -> Shell:
    blocked = blockers or {}

    def gh_api(cmd: list[str]) -> str:
        endpoint = cmd[3]
        if endpoint.endswith("/sub_issues"):
            return "".join(sub_issues)
        number = int(endpoint.split("/")[4])
        return _lines(*blocked.get(number, []))

    return Shell(
        {
            ("rev-parse", "--show-toplevel"): overrides.get("toplevel", f"{tmp_path / 'proto'}\n"),
            ("ls-remote", "--heads"): overrides.get("heads", HEADS),
            ("log",): overrides.get("merges", MERGES),
            ("worktree", "list"): overrides.get("worktrees", _worktrees(tmp_path)),
            ("gh", "api"): overrides.get("gh", gh_api),
        }
    )


def _status(tmp_path: Path, shell: Shell, as_json: bool = False) -> list[str]:
    """Runs status in a home registering ``proto`` and ``owner/other``; ``stranger/repo`` is
    outside it."""
    projects = proto_projects(tmp_path)
    register(tmp_path, "other", "owner/other")
    said: list[str] = []
    status(25, shell, as_json=as_json, home=home_for(projects), say=said.append)
    return said


def _named_anywhere(shell: Shell, said: list[str], text: str) -> bool:
    return any(text in word for call in shell.calls for word in call) or any(
        text in line for line in said
    )


def _row(said: list[str], number: int) -> str:
    (row,) = [line for line in said if line.lstrip().startswith(f"#{number} ")]
    return row


def test_each_sub_issue_gets_one_row_with_its_title_state_labels_and_assignee(tmp_path):
    shell = _shell(
        tmp_path, [sub_issue_json(30, labels=("ready-for-agent",), assignees=("someone",))]
    )

    row = _row(_status(tmp_path, shell), 30).split()

    assert row[:2] == ["#30", "open"]
    assert "ready-for-agent" in row
    assert "someone" in row
    assert row[-1] == "T30"


def test_a_sub_issue_closed_as_not_planned_shows_as_skipped(tmp_path):
    shell = _shell(
        tmp_path, [sub_issue_json(30, "closed", "not_planned"), sub_issue_json(31, "closed")]
    )
    said = _status(tmp_path, shell)

    assert _row(said, 30).split()[1] == "skipped"
    assert _row(said, 31).split()[1] == "closed"


def test_a_row_lists_the_tickets_open_blockers_in_any_repo(tmp_path):
    blockers = {30: [_blocker(12), _blocker(3, "owner/other"), _blocker(13, state="closed")]}
    shell = _shell(tmp_path, [sub_issue_json(30)], blockers)

    row = _row(_status(tmp_path, shell), 30)

    assert "#12, owner/other#3" in row
    assert "#13" not in row


def test_a_row_says_whether_the_ticket_is_integrated_as_ship_reads_it(tmp_path):
    shell = _shell(tmp_path, [sub_issue_json(28), sub_issue_json(29)])
    said = _status(tmp_path, shell)

    assert _row(said, 28).split()[2] == "yes"
    # 29's merge went into another spec, so it is not integrated into this one.
    assert _row(said, 29).split()[2] == "no"


def test_a_row_says_whether_a_ticket_worktree_exists_under_the_worktree_root(tmp_path):
    worktrees = _worktrees(tmp_path, "spec-25-fix-30-build-it", "fix-99-unrelated")
    shell = _shell(tmp_path, [sub_issue_json(30), sub_issue_json(31)], worktrees=worktrees)
    said = _status(tmp_path, shell)

    assert _row(said, 30).split()[3] == "yes"
    assert _row(said, 31).split()[3] == "no"


def test_status_fetches_only_the_integration_branch_first(tmp_path):
    shell = _shell(tmp_path, [sub_issue_json(30)])
    _status(tmp_path, shell)

    (fetch,) = shell.ran("fetch")
    assert fetch[-2:] == ["origin", "+refs/heads/spec-25:refs/remotes/origin/spec-25"]
    assert shell.calls.index(fetch) < shell.calls.index(shell.ran("log")[0])


def test_the_frontier_lists_open_unblocked_unintegrated_unworked_tickets_in_sub_issue_order(
    tmp_path,
):
    sub_issues = [
        sub_issue_json(33),
        sub_issue_json(28),  # integrated
        sub_issue_json(30),  # blocked
        sub_issue_json(31),  # in a ticket worktree
        sub_issue_json(32, "closed"),
        sub_issue_json(29),
    ]
    shell = _shell(
        tmp_path,
        sub_issues,
        {30: [_blocker(12)]},
        worktrees=_worktrees(tmp_path, "spec-25-fix-31-x"),
    )

    assert "frontier: #33, #29" in _status(tmp_path, shell)


def test_an_assigned_or_ready_for_human_ticket_is_held_with_its_reason(tmp_path):
    sub_issues = [
        sub_issue_json(30),
        sub_issue_json(31, assignees=("someone",)),
        sub_issue_json(32, labels=("ready-for-human",)),
    ]
    said = _status(tmp_path, _shell(tmp_path, sub_issues))

    assert "frontier: #30" in said
    assert "held: #31 (assigned to someone), #32 (ready-for-human)" in said


def test_a_blocked_assigned_ticket_is_neither_on_the_frontier_nor_held(tmp_path):
    shell = _shell(tmp_path, [sub_issue_json(30, assignees=("someone",))], {30: [_blocker(12)]})
    said = _status(tmp_path, shell)

    assert "held: none" in said


def test_with_every_open_ticket_integrated_the_frontier_is_none_because_all_are_integrated(
    tmp_path,
):
    shell = _shell(tmp_path, [sub_issue_json(28)])

    assert "frontier: none (all integrated)" in _status(tmp_path, shell)


def test_with_the_rest_blocked_in_progress_or_held_the_frontier_is_none_with_the_counts(
    tmp_path,
):
    sub_issues = [
        sub_issue_json(30),
        sub_issue_json(31),
        sub_issue_json(32, assignees=("someone",)),
    ]
    shell = _shell(
        tmp_path,
        sub_issues,
        {30: [_blocker(12)]},
        worktrees=_worktrees(tmp_path, "spec-25-fix-31-x"),
    )

    assert "frontier: none (1 blocked, 1 in progress, 1 held)" in _status(tmp_path, shell)


def test_a_spec_with_no_integration_branch_still_prints_rows_and_frontier(tmp_path):
    shell = _shell(tmp_path, [sub_issue_json(30)], heads="")
    said = _status(tmp_path, shell)

    assert "integration: not started (origin has no spec-25)" in said
    assert _row(said, 30).split()[2] == "not-started"
    assert "frontier: #30" in said
    assert not shell.ran("fetch")
    assert not shell.ran("log")


def test_blockers_from_every_page_gh_paginate_prints_are_all_read(tmp_path):
    # gh --paginate with --jq prints every page's objects one after another, so 40 lines are the
    # 30-per-page first page and the second page joined.
    pages = [_blocker(n) for n in range(1, 41)]
    shell = _shell(tmp_path, [sub_issue_json(30)], {30: pages})

    row = _row(_status(tmp_path, shell), 30)

    assert "#1, " in row
    assert "#40" in row


def test_json_gives_every_ticket_and_the_frontier_with_stable_field_names(tmp_path):
    sub_issues = [
        sub_issue_json(28),
        sub_issue_json(30, labels=("ready-for-agent",)),
        sub_issue_json(31, assignees=("someone",)),
    ]
    worktrees = _worktrees(tmp_path, "spec-25-fix-28-registry-check")
    shell = _shell(
        tmp_path, sub_issues, {30: [_blocker(3, "owner/other", "open")]}, worktrees=worktrees
    )

    (out,) = _status(tmp_path, shell, as_json=True)
    data = json.loads(out)

    assert data["repo"] == "owner/proto"
    assert data["spec"] == 25
    assert data["integration_branch"] == "spec-25"
    assert data["integration_started"] is True
    assert data["tickets"][0] == {
        "number": 28,
        "title": "T28",
        "state": "open",
        "state_reason": None,
        "skipped": False,
        "labels": [],
        "assignees": [],
        "open_blockers": [],
        "blockers_outside_home": 0,
        "integrated": True,
        "worktree": str(
            tmp_path / "proto" / ".claude" / "worktrees" / "spec-25-fix-28-registry-check"
        ),
    }
    assert data["tickets"][1]["open_blockers"] == [
        {"repo": "owner/other", "number": 3, "title": "B3", "state": "open", "integrated": False}
    ]
    assert data["frontier"] == []
    assert data["held"] == [{"number": 31, "reason": "assigned to someone"}]
    assert data["frontier_none_reason"] == "1 blocked, 1 held"


def test_kaizen_spec_status_on_the_command_line_prints_the_frontier_and_exits_zero(
    kaizen, tmp_path, capsys
):
    shell = _shell(tmp_path, [sub_issue_json(30)], toplevel=f"{RELAY}\n")

    assert kaizen(["spec", "status", "25"], shell) == 0
    assert "frontier: #30" in capsys.readouterr().out


def test_status_refuses_when_gh_cannot_read_the_specs_sub_issues(tmp_path):
    shell = _shell(tmp_path, [], gh=failed("gh api", "HTTP 404: Not Found"))

    with pytest.raises(RefusalError, match=r"sub-issues of #25 in owner/proto: HTTP 404"):
        _status(tmp_path, shell)


def test_a_blocker_integrated_into_the_spec_no_longer_holds_its_ticket_off_the_frontier(tmp_path):
    # A spec's tickets close only when the spec's PR merges, so an integrated blocker stays open.
    shell = _shell(tmp_path, [sub_issue_json(28), sub_issue_json(30)], {30: [_blocker(28)]})
    said = _status(tmp_path, shell)

    assert "frontier: #30" in said
    assert "#28(integrated)" in _row(said, 30)


def test_a_blocker_with_an_integrated_number_in_another_repo_still_blocks(tmp_path):
    shell = _shell(
        tmp_path, [sub_issue_json(28), sub_issue_json(30)], {30: [_blocker(28, "owner/other")]}
    )

    assert "frontier: none (1 blocked)" in _status(tmp_path, shell)


def test_with_the_rest_closed_unintegrated_the_frontier_is_none_as_all_integrated_or_closed(
    tmp_path,
):
    shell = _shell(tmp_path, [sub_issue_json(28), sub_issue_json(30, "closed", "not_planned")])

    assert "frontier: none (all integrated or closed)" in _status(tmp_path, shell)


@pytest.mark.parametrize("state", ["open", "closed"])
def test_a_blocker_outside_the_home_counts_as_open_whatever_its_state(tmp_path, state):
    shell = _shell(tmp_path, [sub_issue_json(30)], {30: [_blocker(3, "stranger/repo", state)]})

    assert "frontier: none (1 blocked)" in _status(tmp_path, shell)


def test_a_blocker_outside_the_home_prints_without_its_repo_and_is_never_fetched(tmp_path):
    shell = _shell(tmp_path, [sub_issue_json(30)], {30: [_blocker(3, "stranger/repo")]})
    said = _status(tmp_path, shell)

    assert "blocked by an issue outside this home" in _row(said, 30)
    assert not _named_anywhere(shell, said, "stranger")


def test_several_blockers_outside_the_home_print_as_one_count(tmp_path):
    blockers = {30: [_blocker(3, "stranger/repo"), _blocker(4, "stranger/repo")]}
    shell = _shell(tmp_path, [sub_issue_json(30)], blockers)

    assert "blocked by 2 issues outside this home" in _row(_status(tmp_path, shell), 30)


def test_json_gives_a_blocker_outside_the_home_as_a_count_without_its_repo(tmp_path):
    blockers = {30: [_blocker(12), _blocker(3, "stranger/repo"), _blocker(4, "stranger/repo")]}
    shell = _shell(tmp_path, [sub_issue_json(30)], blockers)

    (out,) = _status(tmp_path, shell, as_json=True)
    (ticket,) = json.loads(out)["tickets"]

    assert [b["number"] for b in ticket["open_blockers"]] == [12]
    assert ticket["blockers_outside_home"] == 2
    assert "stranger" not in out
