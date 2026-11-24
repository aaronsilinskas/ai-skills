"""Tests for ``kaizen project labels``: the workflow labels created in each project's GitHub repo.

gh is replaced by a recording runner and the registry by a temporary ``projects/`` directory, so
no repo or label on GitHub is touched.
"""

import json
from pathlib import Path

import pytest

from kaizen.project.labels import sync_labels
from kaizen.shared.cli import main
from kaizen.shared.common import RefusalError
from kaizen.tests.ticket_shell import (
    Shell,
    failed,
    home_for,
    proto_projects,
    register,
    write_marker,
)


def _labels(*labels: tuple[str, str, str]) -> str:
    """A ``gh label list --json`` reply holding each (name, colour, description)."""
    return json.dumps([{"name": n, "color": c, "description": d} for n, c, d in labels])


def test_the_missing_workflow_labels_are_created_with_the_default_colour_and_description(
    tmp_path,
):
    shell = Shell({("label", "list"): _labels()})

    sync_labels(shell, home=home_for(proto_projects(tmp_path)), say=lambda _: None)

    creates = shell.ran("label", "create")
    assert len(creates) == 11
    assert [
        "gh",
        "label",
        "create",
        "needs-triage",
        "-R",
        "owner/proto",
        "--color",
        "fbca04",
        "--description",
        "Maintainer needs to evaluate this issue",
    ] in creates


def test_a_workflow_label_already_present_with_the_default_colour_and_description_is_untouched(
    tmp_path,
):
    shell = Shell(
        {
            ("label", "list"): _labels(
                ("spec", "5319e7", "Published, grilled spec ready for to-tickets")
            )
        }
    )

    sync_labels(shell, home=home_for(proto_projects(tmp_path)), say=lambda _: None)

    assert not shell.ran("label", "create", "spec")
    assert not shell.ran("label", "edit")


def test_a_workflow_label_with_another_colour_or_description_is_warned_about_and_left(tmp_path):
    shell = Shell({("label", "list"): _labels(("spec", "ffffff", "A spec"))})
    lines: list[str] = []

    sync_labels(shell, home=home_for(proto_projects(tmp_path)), say=lines.append)

    assert not shell.ran("label", "create", "spec")
    assert not shell.ran("label", "edit")
    assert (
        "owner/proto: warning: spec is ffffff 'A spec', not 5319e7 "
        "'Published, grilled spec ready for to-tickets'; left as it is"
    ) in lines


def test_a_dry_run_creates_no_label_and_names_each_it_would_create(tmp_path):
    shell = Shell({("label", "list"): _labels()})
    lines: list[str] = []

    sync_labels(shell, home=home_for(proto_projects(tmp_path)), dry_run=True, say=lines.append)

    assert not shell.ran("label", "create")
    assert "owner/proto: would create needs-triage" in lines


def _two_projects(tmp_path: Path) -> Path:
    """A registry holding ``proto`` (``owner/proto``) and ``tool`` (``owner/tool``)."""
    projects = proto_projects(tmp_path)
    register(tmp_path, "tool", "owner/tool")
    return projects


def _repos_created_in(shell: Shell) -> set[str]:
    return {cmd[cmd.index("-R") + 1] for cmd in shell.ran("label", "create")}


def test_with_no_project_named_every_registered_projects_repo_gets_the_labels(tmp_path):
    shell = Shell({("label", "list"): _labels()})

    sync_labels(shell, home=home_for(_two_projects(tmp_path)), say=lambda _: None)

    assert _repos_created_in(shell) == {"owner/proto", "owner/tool"}


def test_a_named_project_is_the_only_repo_that_gets_the_labels(tmp_path):
    shell = Shell({("label", "list"): _labels()})

    sync_labels(shell, "tool", home=home_for(_two_projects(tmp_path)), say=lambda _: None)

    assert _repos_created_in(shell) == {"owner/tool"}
    assert all("owner/proto" not in cmd for cmd in shell.calls)


def test_an_unknown_project_is_refused_before_any_label_is_listed(tmp_path):
    shell = Shell({("label", "list"): _labels()})

    with pytest.raises(RefusalError, match="no project page"):
        sync_labels(shell, "nope", home=home_for(proto_projects(tmp_path)), say=lambda _: None)

    assert not shell.calls


def _failing_idea_in_proto(cmd: list[str]) -> str:
    """A ``gh label create`` reply that fails for ``idea`` in ``owner/proto`` only."""
    if cmd[3] == "idea" and "owner/proto" in cmd:
        raise failed("gh label create", "HTTP 500")
    return ""


def test_a_failed_creation_exits_1_after_every_other_label_and_repo_is_tried(tmp_path):
    shell = Shell({("label", "list"): _labels(), ("label", "create"): _failing_idea_in_proto})

    code = sync_labels(shell, home=home_for(_two_projects(tmp_path)), say=lambda _: None)

    assert code == 1
    assert len(shell.ran("label", "create")) == 2 * 11


def test_a_failed_creation_is_reported_with_gh_s_error(tmp_path):
    shell = Shell({("label", "list"): _labels(), ("label", "create"): _failing_idea_in_proto})
    lines: list[str] = []

    sync_labels(shell, home=home_for(_two_projects(tmp_path)), say=lines.append)

    assert "owner/proto: failed to create idea: HTTP 500" in lines


def test_each_repo_s_summary_counts_the_labels_created_failed_present_and_differing(tmp_path):
    present = _labels(
        ("spec", "5319e7", "Published, grilled spec ready for to-tickets"),
        ("idea", "ffffff", "Idea captured to revisit later"),
    )
    shell = Shell({("label", "list"): present, ("label", "create"): _failing_idea_in_proto})
    lines: list[str] = []

    sync_labels(shell, home=home_for(proto_projects(tmp_path)), say=lines.append)

    assert lines[-1] == "owner/proto: 9 created, 0 failed, 2 already present (1 differ)"


def test_a_repo_whose_labels_cannot_be_listed_is_refused_before_any_label_is_created(tmp_path):
    def listing(cmd: list[str]) -> str:
        if "owner/tool" in cmd:
            raise failed("gh label list", "HTTP 404")
        return _labels()

    shell = Shell({("label", "list"): listing})

    with pytest.raises(RefusalError, match="could not list the labels of owner/tool: HTTP 404"):
        sync_labels(shell, home=home_for(_two_projects(tmp_path)), say=lambda _: None)

    assert not shell.ran("label", "create")


_CONFIGURED = """
[[workflow_labels]]
name = "triage"
color = "ABCDEF"
description = "Needs a look"

[[workflow_labels]]
name = "spec"
color = "123456"
description = "A spec"
"""
"""A workflow labels setting naming two labels, ``spec`` among them with a colour unlike the
default's."""


def _home_with_labels(tmp_path: Path, setting: str) -> Path:
    """The root of a fixture home registering ``proto`` (``owner/proto``) whose marker holds the
    workflow labels *setting*."""
    root = tmp_path / "home"
    root.mkdir()
    proto_projects(root)
    write_marker(root, setting)
    return root


def test_a_home_s_configured_labels_are_the_only_ones_created(tmp_path):
    shell = Shell({("label", "list"): _labels()})
    root = _home_with_labels(tmp_path, _CONFIGURED)

    assert main(["project", "labels"], run=shell, cwd=root, env={}) == 0

    create = ("gh", "label", "create")
    assert shell.ran("label", "create") == [
        [
            *create,
            "triage",
            "-R",
            "owner/proto",
            "--color",
            "abcdef",
            "--description",
            "Needs a look",
        ],
        [*create, "spec", "-R", "owner/proto", "--color", "123456", "--description", "A spec"],
    ]


def test_a_label_differing_from_the_home_s_configured_one_is_warned_about(tmp_path, capsys):
    default_spec = ("spec", "5319e7", "Published, grilled spec ready for to-tickets")
    shell = Shell({("label", "list"): _labels(default_spec)})
    root = _home_with_labels(tmp_path, _CONFIGURED)

    main(["project", "labels"], run=shell, cwd=root, env={})

    out = capsys.readouterr().out
    assert (
        "owner/proto: warning: spec is 5319e7 'Published, grilled spec ready for to-tickets', "
        "not 123456 'A spec'; left as it is"
    ) in out
    assert out.splitlines()[-1] == "owner/proto: 1 created, 0 failed, 1 already present (1 differ)"
