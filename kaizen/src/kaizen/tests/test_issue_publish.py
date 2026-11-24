"""Tests for ``kaizen issue publish``: the leak check and label check before the one ``gh`` create.

git and gh are replaced by a recording runner, so no network or GitHub access is needed.
"""

import json
from pathlib import Path

import pytest

from kaizen.tests.ticket_shell import DENIED, RELAY, SITE, TILDE, Shell, deny, failed

URL = "https://github.com/acme/relay/issues/42"


def _shell(toplevel: Path = RELAY, labels: tuple[str, ...] = ("idea", "bug")) -> Shell:
    return Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{toplevel}\n",
            ("label", "list"): json.dumps(
                [{"name": label, "color": "ABCDEF", "description": ""} for label in labels]
            ),
            ("issue", "create"): f"{URL}\n",
        }
    )


def _body(tmp_path: Path, text: str) -> str:
    path = tmp_path / "body.md"
    path.write_text(text)
    return str(path)


def _argv(
    tmp_path: Path, *extra: str, body: str = "An idea.\n", title: str = "Park an idea"
) -> list[str]:
    return ["issue", "publish", "--title", title, "--body-file", _body(tmp_path, body), *extra]


def test_clean_text_creates_the_issue_in_the_projects_repo_with_its_labels(
    kaizen, tmp_path, capsys
):
    shell = _shell()
    argv = _argv(tmp_path, "--label", "idea", "--label", "bug")

    assert kaizen(argv, run=shell) == 0

    (create,) = shell.ran("issue", "create")
    assert create == [
        "gh",
        "issue",
        "create",
        "-R",
        "acme/relay",
        "--title",
        "Park an idea",
        "--body-file",
        str(tmp_path / "body.md"),
        "--label",
        "idea",
        "--label",
        "bug",
    ]
    assert capsys.readouterr().out == f"{URL}\n"


def test_an_issue_is_published_from_a_ticket_worktree_into_its_projects_repo(kaizen, tmp_path):
    shell = _shell(toplevel=RELAY / ".claude/worktrees/fix-9-x")

    assert kaizen(_argv(tmp_path, "--label", "idea"), run=shell) == 0

    assert shell.ran("issue", "create", "-R", "acme/relay")


def test_a_dry_run_prints_the_plan_and_creates_nothing(kaizen, tmp_path, capsys):
    shell = _shell()

    assert kaizen(_argv(tmp_path, "--label", "idea", "--dry-run"), run=shell) == 0

    out = capsys.readouterr().out
    assert "would create in acme/relay: Park an idea (labels: idea)" in out
    assert not shell.ran("issue", "create")


@pytest.mark.parametrize("dry_run", [True, False], ids=["dry run", "real run"])
def test_a_body_pointing_outside_the_home_is_refused_naming_each_line_before_any_gh_call(
    kaizen, tmp_path, capsys, dry_run
):
    shell = _shell()
    body = f"Fine.\nsee {TILDE}/dev/elsewhere/notes\n"
    argv = _argv(tmp_path, *(["--dry-run"] if dry_run else []), body=body)

    assert kaizen(argv, run=shell) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused: leak check: text for GitHub points outside this home")
    assert "issue body line 2: outside path " in err
    assert not shell.ran("gh")


def test_a_public_projects_title_with_an_own_reference_is_refused(kaizen, tmp_path, capsys):
    shell = _shell(toplevel=SITE)

    assert kaizen(_argv(tmp_path, title="Move /fixture/home/docs"), run=shell) == 1

    assert "issue title line 1: own reference /fixture/home" in capsys.readouterr().err
    assert not shell.ran("gh")


def test_a_body_holding_the_projects_denied_pattern_is_refused(kaizen, tmp_path, capsys):
    deny(tmp_path / "cli-home" / "projects", "relay")
    shell = _shell()

    assert kaizen(_argv(tmp_path, body=f"Why the {DENIED} goes.\n"), run=shell) == 1

    assert f"issue body line 1: denied pattern {DENIED}" in capsys.readouterr().err
    assert not shell.ran("gh")


def test_a_label_the_repo_lacks_is_refused_before_the_create(kaizen, tmp_path, capsys):
    shell = _shell(labels=("bug",))

    assert kaizen(_argv(tmp_path, "--label", "idea", "--dry-run"), run=shell) == 1

    err = capsys.readouterr().err
    assert "refused: acme/relay has no label idea" in err
    assert "kaizen project labels" in err
    assert not shell.ran("issue", "create")


def test_labels_that_cannot_be_listed_are_refused(kaizen, tmp_path, capsys):
    shell = Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{RELAY}\n",
            ("label", "list"): failed("gh label list", "HTTP 404"),
        }
    )

    assert kaizen(_argv(tmp_path, "--label", "idea"), run=shell) == 1

    assert "refused: could not list the labels of acme/relay" in capsys.readouterr().err
    assert not shell.ran("issue", "create")


def test_no_labels_skips_the_label_lookup(kaizen, tmp_path):
    shell = _shell()

    assert kaizen(_argv(tmp_path), run=shell) == 0

    assert not shell.ran("label", "list")
    assert shell.ran("issue", "create")


def test_a_blank_title_is_refused(kaizen, tmp_path, capsys):
    shell = _shell()

    assert kaizen(_argv(tmp_path, title="  "), run=shell) == 1

    assert "refused: the issue title is blank" in capsys.readouterr().err
    assert not shell.ran("gh")


def test_an_unreadable_body_file_is_refused(kaizen, tmp_path, capsys):
    shell = _shell()
    argv = ["issue", "publish", "--title", "T", "--body-file", str(tmp_path / "missing.md")]

    assert kaizen(argv, run=shell) == 1

    assert "refused: could not read the body file" in capsys.readouterr().err
    assert not shell.ran("gh")


def test_outside_a_registered_project_it_is_refused(kaizen, tmp_path, capsys):
    shell = _shell(toplevel=Path("/fixture/unregistered"))

    assert kaizen(_argv(tmp_path), run=shell) == 1

    err = capsys.readouterr().err
    assert (
        "refused: /fixture/unregistered is not a registered project's main checkout"
        " or a worktree under its worktree root" in err
    )
    assert not shell.ran("gh")


def test_a_label_given_twice_is_sent_once(kaizen, tmp_path):
    shell = _shell()

    assert kaizen(_argv(tmp_path, "--label", "idea", "--label", "idea"), run=shell) == 0

    (create,) = shell.ran("issue", "create")
    assert create.count("idea") == 1
