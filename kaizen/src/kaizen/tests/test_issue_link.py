"""Tests for ``kaizen issue link``: sub-issue and blocked-by edges, through ``main`` with a
recording runner, so no network or live issue is touched."""

import json

import pytest

from kaizen.tests.conftest import Kaizen
from kaizen.tests.ticket_shell import RELAY, Reply, Shell, failed, register

NO_PARENT = failed("gh api", "gh: No parent issue found (HTTP 404)")
NOT_FOUND = failed("gh api", "gh: Not Found (HTTP 404)")


def _issue(number: int, repo: str = "owner/proto", state: str = "open", **extra: object) -> str:
    """A REST ``issues/N`` reply as the module's ``--jq`` projection prints it."""
    return json.dumps(
        {"id": 1000 + number, "number": number, "title": f"Issue {number}", "state": state}
        | {"repository_url": f"https://api.github.com/repos/{repo}"}
        | extra
    )


@pytest.fixture(autouse=True)
def _registered(kaizen, tmp_path):
    """Registers owner/proto and other/lib in the fixture home ``kaizen`` runs from."""
    register(tmp_path / "cli-home", "proto", "owner/proto")
    register(tmp_path / "cli-home", "lib", "other/lib")


def _shell(**overrides: Reply) -> Shell:
    """The child owner/proto#7 with no parent and no blockers; owner/proto#5, #3, #4 and
    other/lib#9 exist; *overrides* replaces a reply by its key name."""
    answers: dict[tuple[str, ...], Reply] = {
        ("repos/owner/proto/issues/7/parent",): overrides.get("parent", NO_PARENT),
        ("repos/owner/proto/issues/7/dependencies/blocked_by", "--jq"): overrides.get(
            "blockers", ""
        ),
        ("-X", "POST"): overrides.get("write", ""),
        ("repos/owner/proto/issues/7",): _issue(7),
        ("repos/owner/proto/issues/5",): overrides.get("issue5", _issue(5)),
        ("repos/owner/proto/issues/3",): _issue(3),
        ("repos/owner/proto/issues/4",): overrides.get("issue4", _issue(4)),
        ("repos/other/lib/issues/9",): _issue(9, repo="other/lib"),
    }
    return Shell(answers)


def _link(kaizen: Kaizen, capsys, shell: Shell, *argv: str) -> tuple[int, str, str]:
    code = kaizen(["issue", "link", "owner/proto#7", *argv], shell)
    out = capsys.readouterr()
    return code, out.out, out.err


def _writes(shell: Shell) -> list[list[str]]:
    return shell.ran("-X", "POST")


def test_parent_adds_the_child_as_a_sub_issue_by_its_database_id(kaizen, capsys):
    shell = _shell()

    code, out, _ = _link(kaizen, capsys, shell, "--parent", "owner/proto#5")

    assert code == 0
    assert _writes(shell) == [
        [
            "gh",
            "api",
            "-X",
            "POST",
            "repos/owner/proto/issues/5/sub_issues",
            "-F",
            "sub_issue_id=1007",
        ]
    ]
    assert out == "added: #7 is a sub-issue of #5\n"


def test_each_blocked_by_is_added_by_its_database_id_across_repos_one_line_per_edge(kaizen, capsys):
    shell = _shell()

    code, out, _ = _link(
        kaizen, capsys, shell, "--blocked-by", "owner/proto#3", "--blocked-by", "other/lib#9"
    )

    assert code == 0
    assert [w[4:] for w in _writes(shell)] == [
        ["repos/owner/proto/issues/7/dependencies/blocked_by", "-F", "issue_id=1003"],
        ["repos/owner/proto/issues/7/dependencies/blocked_by", "-F", "issue_id=1009"],
    ]
    assert out == "added: #7 is blocked by #3\nadded: #7 is blocked by other/lib#9\n"


def test_parent_and_blockers_combine_in_one_call(kaizen, capsys):
    shell = _shell()

    code, out, _ = _link(
        kaizen, capsys, shell, "--parent", "owner/proto#5", "--blocked-by", "other/lib#9"
    )

    assert code == 0
    assert out == "added: #7 is a sub-issue of #5\nadded: #7 is blocked by other/lib#9\n"


def test_a_bare_number_names_an_issue_in_the_current_project(kaizen, capsys):
    shell = Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{RELAY}\n",
            ("repos/acme/relay/issues/7/dependencies/blocked_by", "--jq"): "",
            ("repos/acme/relay/issues/7",): _issue(7, repo="acme/relay"),
            ("repos/acme/relay/issues/3",): _issue(3, repo="acme/relay"),
        }
    )

    code = kaizen(["issue", "link", "7", "--blocked-by", "#3"], shell)

    assert code == 0
    assert _writes(shell)[0][4:] == [
        "repos/acme/relay/issues/7/dependencies/blocked_by",
        "-F",
        "issue_id=1003",
    ]


def test_link_with_neither_parent_nor_blocker_refuses_naming_both_flags(kaizen, capsys):
    shell = _shell()

    code, _, err = _link(kaizen, capsys, shell)

    assert code == 1
    assert err.startswith("refused: nothing to link")
    assert "--parent" in err
    assert "--blocked-by" in err
    assert shell.calls == []


def test_a_missing_issue_refuses_by_name_with_nothing_written(kaizen, capsys):
    shell = _shell(issue4=NOT_FOUND)

    code, _, err = _link(
        kaizen,
        capsys,
        shell,
        "--parent",
        "owner/proto#5",
        "--blocked-by",
        "owner/proto#3",
        "--blocked-by",
        "owner/proto#4",
    )

    assert code == 1
    assert "refused: owner/proto#4 does not exist" in err
    assert "fix: check the reference" in err
    assert _writes(shell) == []


def test_a_pull_request_refuses_with_nothing_written(kaizen, capsys):
    shell = _shell(issue5=_issue(5, pull_request={"url": "https://api.github.com/x"}))

    code, _, err = _link(kaizen, capsys, shell, "--parent", "owner/proto#5")

    assert code == 1
    assert "refused: owner/proto#5 is a pull request, not an issue" in err
    assert "fix: link issues only" in err
    assert _writes(shell) == []


def test_a_self_link_refuses_with_nothing_written(kaizen, capsys):
    shell = _shell()

    code, _, err = _link(kaizen, capsys, shell, "--blocked-by", "owner/proto#7")

    assert code == 1
    assert "refused: owner/proto#7 cannot be linked to itself" in err
    assert "fix: name a different issue" in err
    assert _writes(shell) == []


def test_a_child_with_a_different_parent_refuses_naming_it_with_nothing_written(kaizen, capsys):
    other_parent = _issue(6, repo="owner/proto")
    shell = _shell(parent=other_parent)

    code, _, err = _link(
        kaizen, capsys, shell, "--parent", "owner/proto#5", "--blocked-by", "other/lib#9"
    )

    assert code == 1
    assert "refused: owner/proto#7 already has parent owner/proto#6 (Issue 6)" in err
    assert "fix: to move it, remove it from owner/proto#6" in err
    assert _writes(shell) == []


def test_a_different_parent_outside_the_home_refuses_without_its_repo_or_title(kaizen, capsys):
    shell = _shell(parent=_issue(2, repo="stranger/repo", title="Stranger spec"))

    code, _, err = _link(kaizen, capsys, shell, "--parent", "owner/proto#5")

    assert code == 1
    assert "refused: owner/proto#7 already has parent an issue outside this home" in err
    assert "fix: to move it, remove its parent in GitHub first, then rerun" in err
    assert "stranger" not in err.lower()
    assert _writes(shell) == []


def test_a_closed_blocker_is_added_and_noted(kaizen, capsys):
    shell = _shell(issue4=_issue(4, state="closed"))

    code, out, _ = _link(kaizen, capsys, shell, "--blocked-by", "owner/proto#4")

    assert code == 0
    assert len(_writes(shell)) == 1
    assert out == "added: #7 is blocked by #4 (closed)\n"


def test_edges_already_present_print_as_such_and_are_not_written_again(kaizen, capsys):
    blockers = _issue(3) + "\n"
    shell = _shell(parent=_issue(5), blockers=blockers)

    code, out, _ = _link(
        kaizen,
        capsys,
        shell,
        "--parent",
        "owner/proto#5",
        "--blocked-by",
        "owner/proto#3",
        "--blocked-by",
        "other/lib#9",
    )

    assert code == 0
    assert [w[4] for w in _writes(shell)] == ["repos/owner/proto/issues/7/dependencies/blocked_by"]
    assert out == (
        "already present: #7 is a sub-issue of #5\n"
        "already present: #7 is blocked by #3\n"
        "added: #7 is blocked by other/lib#9\n"
    )


def test_the_blockers_read_paginates(kaizen, capsys):
    shell = _shell()

    _link(kaizen, capsys, shell, "--blocked-by", "owner/proto#3")

    (read,) = shell.ran("repos/owner/proto/issues/7/dependencies/blocked_by", "--jq")
    assert "--paginate" in read


def test_a_write_github_rejects_refuses_with_github_message_not_a_raw_error(kaizen, capsys):
    cycle = failed("gh api", "gh: Validation Failed: would create a dependency cycle (HTTP 422)")
    shell = _shell(write=cycle)

    code, out, err = _link(kaizen, capsys, shell, "--blocked-by", "owner/proto#3")

    assert code == 1
    assert out == ""
    assert err.startswith(
        "refused: GitHub refused the edge owner/proto#7 is blocked by owner/proto#3:"
        " Validation Failed: would create a dependency cycle (HTTP 422)\n"
    )
    assert "fix: the edges printed above are added" in err
    assert "error:" not in err


def test_dry_run_prints_each_edge_with_the_id_it_would_send_and_writes_nothing(kaizen, capsys):
    shell = _shell()

    code, out, _ = _link(
        kaizen,
        capsys,
        shell,
        "--parent",
        "owner/proto#5",
        "--blocked-by",
        "other/lib#9",
        "--dry-run",
    )

    assert code == 0
    assert out == (
        "would add: #7 is a sub-issue of #5"
        " (POST repos/owner/proto/issues/5/sub_issues sub_issue_id=1007)\n"
        "would add: #7 is blocked by other/lib#9"
        " (POST repos/owner/proto/issues/7/dependencies/blocked_by issue_id=1009)\n"
    )
    assert _writes(shell) == []


def test_a_rejected_write_names_the_reasons_in_github_response_body(kaizen, capsys):
    body = json.dumps(
        {
            "message": "Validation Failed",
            "errors": [{"message": "Adding this dependency would create a cycle"}],
        }
    )
    rejected = failed("gh api", "gh: Validation Failed (HTTP 422)")
    rejected.output = body
    shell = _shell(write=rejected)

    code, _, err = _link(kaizen, capsys, shell, "--blocked-by", "owner/proto#3")

    assert code == 1
    assert ": Validation Failed; Adding this dependency would create a cycle\n" in err


@pytest.mark.parametrize(
    "argv",
    [
        ["stranger/repo#7", "--parent", "owner/proto#5"],
        ["owner/proto#7", "--parent", "stranger/repo#5"],
        ["owner/proto#7", "--blocked-by", "owner/proto#3", "--blocked-by", "stranger/repo#9"],
    ],
    ids=["child", "parent", "blocker"],
)
def test_a_repo_outside_the_homes_registry_is_refused_before_any_gh_call(kaizen, capsys, argv):
    shell = _shell()

    code = kaizen(["issue", "link", *argv], shell)

    assert code == 1
    assert "refused: stranger/repo is not a repo of this home" in capsys.readouterr().err
    assert not shell.ran("gh")
