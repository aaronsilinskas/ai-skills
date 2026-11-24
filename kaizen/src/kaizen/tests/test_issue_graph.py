"""Tests for the issue graph module's reference parsing, which every issue command depends on.

git is replaced by a recording runner and the registry by a temporary ``projects/`` directory.
"""

import pytest

from kaizen.shared.common import RefusalError
from kaizen.shared.issue_graph import IssueRef, parse_ref
from kaizen.tests.ticket_shell import Shell, proto_projects


def _in_proto(tmp_path) -> Shell:
    return Shell({("rev-parse", "--show-toplevel"): f"{tmp_path / 'proto'}\n"})


@pytest.mark.parametrize("text", ["42", "#42"])
def test_a_bare_number_names_an_issue_in_the_current_project(tmp_path, text):
    ref = parse_ref(text, _in_proto(tmp_path), proto_projects(tmp_path))

    assert ref == IssueRef("owner/proto", 42)


@pytest.mark.parametrize("text", ["42", "#42"])
def test_a_bare_number_names_an_issue_in_the_project_owning_the_ticket_worktree(tmp_path, text):
    worktree = tmp_path / "proto" / ".claude" / "worktrees" / "fix-9-thing"
    shell = Shell({("rev-parse", "--show-toplevel"): f"{worktree}\n"})

    ref = parse_ref(text, shell, proto_projects(tmp_path))

    assert ref == IssueRef("owner/proto", 42)


def test_a_bare_number_outside_any_checkout_refuses_naming_main_checkouts_and_worktree_roots(
    tmp_path,
):
    shell = Shell({("rev-parse", "--show-toplevel"): f"{tmp_path / 'elsewhere'}\n"})

    with pytest.raises(RefusalError) as refusal:
        parse_ref("42", shell, proto_projects(tmp_path))

    problem, fix = str(refusal.value).split("\n  fix: ")
    assert problem.endswith(
        "is not a registered project's main checkout or a worktree under its worktree root"
    )
    proto = tmp_path / "proto"
    assert fix == (
        f"run from the root of one of: {proto} (or a worktree under {proto / '.claude/worktrees'})"
    )


def test_a_project_name_reference_takes_the_repo_from_that_projects_page(tmp_path):
    shell = _in_proto(tmp_path)

    ref = parse_ref("proto#7", shell, proto_projects(tmp_path))

    assert ref == IssueRef("owner/proto", 7)
    assert not shell.calls


def test_an_owner_repo_reference_to_a_registered_repo_is_taken_literally(tmp_path):
    shell = _in_proto(tmp_path)

    ref = parse_ref("owner/proto#3", shell, proto_projects(tmp_path))

    assert ref == IssueRef("owner/proto", 3)
    assert not shell.calls


def test_a_registered_repo_matches_in_any_case_as_github_compares_repo_names(tmp_path):
    ref = parse_ref("Owner/Proto#3", _in_proto(tmp_path), proto_projects(tmp_path))

    assert ref == IssueRef("Owner/Proto", 3)


def test_an_owner_repo_reference_outside_the_homes_registry_is_refused_before_any_call(tmp_path):
    shell = _in_proto(tmp_path)

    with pytest.raises(RefusalError, match=r"someone/else\.js is not a repo of this home"):
        parse_ref("someone/else.js#3", shell, proto_projects(tmp_path))
    assert not shell.calls


def test_a_reference_to_an_unregistered_project_is_refused(tmp_path):
    with pytest.raises(RefusalError, match="nope"):
        parse_ref("nope#7", _in_proto(tmp_path), proto_projects(tmp_path))


@pytest.mark.parametrize("text", ["", "#", "seven", "a/b/c#1", "proto#x"])
def test_text_that_is_no_reference_form_is_refused_naming_the_forms(tmp_path, text):
    with pytest.raises(RefusalError, match=r"N, #N, <project>#N or owner/repo#N"):
        parse_ref(text, _in_proto(tmp_path), proto_projects(tmp_path))


def test_a_reference_prints_as_owner_repo_and_number():
    assert str(IssueRef("owner/proto", 7)) == "owner/proto#7"


def test_a_short_reference_drops_the_repo_only_within_the_same_repo():
    ref = IssueRef("owner/proto", 7)

    assert ref.short("owner/proto") == "#7"
    assert ref.short("owner/other") == "owner/proto#7"
