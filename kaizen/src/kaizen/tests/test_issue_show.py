"""Tests for ``kaizen issue show``: one issue printed whole, through ``main`` with a recording
runner.

gh is replaced by a recording runner and the registry by a temporary ``projects/`` directory,
so no repo, network or real project page is touched.
"""

import json

import pytest

from kaizen.tests.conftest import Kaizen
from kaizen.tests.ticket_shell import RELAY, Reply, Shell, failed, issue_json, register

COMMENTS = [
    {"author": {"login": "alice"}, "body": "Seen on rev B.", "createdAt": "2026-11-19T08:30:00Z"},
    {"author": {"login": "bob"}, "body": "Fixed?\nNo.", "createdAt": "2026-11-20T17:05:00Z"},
]
ISSUE = issue_json(
    title="Each Reboot writes twice",
    labels=[{"name": "ready-for-agent"}, {"name": "bug"}],
    assignees=[{"login": "alice"}],
    body="Two writes per Reboot.",
    comments=COMMENTS,
)
PARENT = '{"number": 5, "title": "Reboot spec", "state": "open",' + (
    ' "repository_url": "https://api.github.com/repos/owner/proto"}'
)
BLOCKERS = (
    '{"number": 3, "title": "Open here", "state": "open",'
    ' "repository_url": "https://api.github.com/repos/owner/proto"}\n'
    '{"number": 4, "title": "Done here", "state": "closed",'
    ' "repository_url": "https://api.github.com/repos/owner/proto"}\n'
    '{"number": 9, "title": "Open elsewhere", "state": "open",'
    ' "repository_url": "https://api.github.com/repos/other/lib"}\n'
)
NO_PARENT = failed("gh api", "gh: No parent issue found (HTTP 404)")


@pytest.fixture(autouse=True)
def _registered(kaizen, tmp_path):
    """Registers owner/proto in the fixture home ``kaizen`` runs from."""
    register(tmp_path / "cli-home", "proto", "owner/proto")


def _shell(**overrides: Reply) -> Shell:
    return Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{RELAY}\n",
            ("issue", "view"): overrides.get("issue", ISSUE),
            ("repos/owner/proto/issues/7/parent",): overrides.get("parent", PARENT),
            ("repos/owner/proto/issues/7/dependencies/blocked_by",): overrides.get(
                "blockers", BLOCKERS
            ),
        }
    )


def _show(kaizen: Kaizen, capsys, shell: Shell, *argv: str) -> tuple[int, str, str]:
    code = kaizen(["issue", "show", *argv], shell)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_show_prints_header_labels_parent_open_blockers_body_and_comments_in_order(kaizen, capsys):
    code, out, _ = _show(kaizen, capsys, _shell(), "owner/proto#7")

    assert code == 0
    assert out == (
        "owner/proto#7, open: Each Reboot writes twice\n"
        "labels: ready-for-agent, bug\n"
        "parent: #5 Reboot spec\n"
        "open blockers:\n"
        "  #3 Open here\n"
        "  an issue outside this home\n"
        "\nbody:\nTwo writes per Reboot.\n"
        "\ncomment by alice on 2026-11-19:\nSeen on rev B.\n"
        "\ncomment by bob on 2026-11-20:\nFixed?\nNo.\n"
    )


def test_show_reads_with_issue_view_json_never_the_comments_flag(kaizen, capsys):
    shell = _shell()

    _show(kaizen, capsys, shell, "owner/proto#7")

    (view,) = shell.ran("issue", "view")
    assert view[:5] == ["gh", "-R", "owner/proto", "issue", "view"]
    assert "--json" in view
    assert "--comments" not in view


def test_show_reads_every_page_of_blockers(kaizen, capsys):
    shell = _shell()

    _show(kaizen, capsys, shell, "owner/proto#7")

    (blockers,) = shell.ran("repos/owner/proto/issues/7/dependencies/blocked_by")
    assert "--paginate" in blockers


def test_an_issue_with_no_labels_parent_blockers_or_comments_says_none_for_each(kaizen, capsys):
    shell = _shell(
        issue=issue_json(title="Bare", body="Just a body."), parent=NO_PARENT, blockers=""
    )

    code, out, _ = _show(kaizen, capsys, shell, "owner/proto#7")

    assert code == 0
    assert out == (
        "owner/proto#7, open: Bare\n"
        "labels: none\n"
        "parent: none\n"
        "open blockers: none\n"
        "\nbody:\nJust a body.\n"
        "\n(no comments)\n"
    )


def test_a_closed_issue_prints_with_its_state_reason(kaizen, capsys):
    issue = issue_json(title="Old", state="CLOSED", stateReason="NOT_PLANNED")

    code, out, _ = _show(kaizen, capsys, _shell(issue=issue), "owner/proto#7")

    assert code == 0
    assert out.splitlines()[0] == "owner/proto#7, closed (not_planned): Old"


def test_a_closed_issue_with_no_state_reason_prints_just_closed(kaizen, capsys):
    issue = issue_json(title="Old", state="CLOSED", stateReason="")

    _, out, _ = _show(kaizen, capsys, _shell(issue=issue), "owner/proto#7")

    assert out.splitlines()[0] == "owner/proto#7, closed: Old"


def test_a_bare_number_names_an_issue_in_the_current_project(kaizen, capsys):
    shell = Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{RELAY}\n",
            ("issue", "view"): issue_json(url="https://github.com/acme/relay/issues/7"),
            ("repos/acme/relay/issues/7/parent",): NO_PARENT,
        }
    )

    code, out, _ = _show(kaizen, capsys, shell, "#7")

    assert code == 0
    assert out.startswith("acme/relay#7, open: T\n")


def test_a_pull_request_is_refused_with_a_pointer_to_gh_pr_view(kaizen, capsys):
    shell = _shell(issue=issue_json(url="https://github.com/owner/proto/pull/7"))

    code, _, err = _show(kaizen, capsys, shell, "owner/proto#7")

    assert code == 1
    assert "refused: owner/proto#7 is a pull request" in err
    assert "gh -R owner/proto pr view 7" in err
    assert not shell.ran("gh", "api")


def test_a_missing_issue_is_refused_naming_the_reference_and_gh_stderr(kaizen, capsys):
    gone = failed("gh issue view", "GraphQL: Could not resolve to an issue or pull request")
    shell = _shell(issue=gone)

    code, _, err = _show(kaizen, capsys, shell, "owner/proto#7")

    assert code == 1
    assert "refused: could not read issue #7 in owner/proto: GraphQL: Could not resolve" in err


def test_a_parent_gh_cannot_read_for_another_reason_is_refused(kaizen, capsys):
    shell = _shell(parent=failed("gh api", "HTTP 403: rate limited"))

    code, _, err = _show(kaizen, capsys, shell, "owner/proto#7")

    assert code == 1
    assert "could not read the parent of owner/proto#7: HTTP 403" in err


def test_json_prints_every_field_with_stable_names(kaizen, capsys):
    code, out, _ = _show(kaizen, capsys, _shell(), "owner/proto#7", "--json")

    assert code == 0
    assert json.loads(out) == {
        "repo": "owner/proto",
        "number": 7,
        "title": "Each Reboot writes twice",
        "state": "open",
        "state_reason": None,
        "labels": ["ready-for-agent", "bug"],
        "assignees": ["alice"],
        "parent": {
            "repo": "owner/proto",
            "number": 5,
            "title": "Reboot spec",
            "state": "open",
            "outside_home": False,
        },
        "open_blockers": [
            {
                "repo": "owner/proto",
                "number": 3,
                "title": "Open here",
                "state": "open",
                "outside_home": False,
            },
            {"state": "open", "outside_home": True},
        ],
        "body": "Two writes per Reboot.",
        "comments": [
            {"author": "alice", "date": "2026-11-19", "body": "Seen on rev B."},
            {"author": "bob", "date": "2026-11-20", "body": "Fixed?\nNo."},
        ],
    }


def test_json_gives_a_missing_parent_as_null(kaizen, capsys):
    _, out, _ = _show(
        kaizen, capsys, _shell(parent=NO_PARENT, blockers=""), "owner/proto#7", "--json"
    )

    data = json.loads(out)
    assert data["parent"] is None
    assert data["open_blockers"] == []


def test_text_that_is_no_reference_is_refused_before_any_gh_call(kaizen, capsys):
    shell = _shell()

    code, _, err = _show(kaizen, capsys, shell, "seven")

    assert code == 1
    assert "N, #N, <project>#N or owner/repo#N" in err
    assert not shell.ran("gh")


def test_an_issue_in_a_repo_outside_the_homes_registry_is_refused_before_any_gh_call(
    kaizen, capsys
):
    shell = _shell()

    code, _, err = _show(kaizen, capsys, shell, "stranger/repo#7")

    assert code == 1
    assert "refused: stranger/repo is not a repo of this home" in err
    assert not shell.ran("gh")


OUTSIDE_PARENT = '{"number": 2, "title": "Stranger spec", "state": "open",' + (
    ' "repository_url": "https://api.github.com/repos/stranger/repo"}'
)


def test_a_parent_outside_the_home_prints_without_its_repo_or_title(kaizen, capsys):
    _, out, _ = _show(kaizen, capsys, _shell(parent=OUTSIDE_PARENT), "owner/proto#7")

    assert "parent: an issue outside this home\n" in out
    assert "stranger" not in out.lower()


def test_json_gives_a_parent_outside_the_home_without_its_repo_number_or_title(kaizen, capsys):
    _, out, _ = _show(kaizen, capsys, _shell(parent=OUTSIDE_PARENT), "owner/proto#7", "--json")

    assert json.loads(out)["parent"] == {"state": "open", "outside_home": True}
    assert "stranger" not in out.lower()
