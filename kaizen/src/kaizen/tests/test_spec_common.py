"""Tests for the spec plumbing later ``kaizen spec`` commands share: branch names, remote query."""

import pytest

from kaizen.shared.branch import (
    TicketBranch,
    integration_branch,
    integration_merge_message,
    parse_integration_merge,
    parse_ticket_branch,
    spec_ticket_branch,
)
from kaizen.shared.common import RefusalError
from kaizen.spec.common import SubIssue, has_integration_branch, spec_sub_issues
from kaizen.tests.ticket_shell import Shell, failed


def test_a_specs_integration_branch_is_named_from_its_number_alone():
    assert integration_branch(25) == "spec-25"


def test_a_spec_ticket_branch_names_the_spec_issue_and_slug():
    assert (
        spec_ticket_branch(25, 28, "recognise-spec-tickets")
        == "spec-25-fix-28-recognise-spec-tickets"
    )


def test_a_spec_ticket_branch_parses_back_to_its_issue_and_spec():
    assert parse_ticket_branch("spec-25-fix-28-recognise-spec-tickets") == TicketBranch(28, 25)


def test_a_lone_ticket_branch_parses_to_no_spec():
    assert parse_ticket_branch("fix-22-kaizen-one-failure") == TicketBranch(22, None)


def test_has_integration_branch_asks_origin_for_exactly_that_branch():
    shell = Shell({("ls-remote",): "abc123\trefs/heads/spec-25\n"})

    assert has_integration_branch("/repo", 25, shell)
    assert shell.calls == [["git", "-C", "/repo", "ls-remote", "--heads", "origin", "spec-25"]]


def test_has_integration_branch_is_false_when_origin_lacks_it():
    assert not has_integration_branch("/repo", 25, Shell({("ls-remote",): ""}))


SUB_ISSUES = (
    '{"number":28,"state":"closed","state_reason":"completed","title":"Recognise spec tickets",'
    '"labels":[],"assignees":[]}\n'
    '{"number":29,"state":"open","state_reason":null,"title":"Declare a check command",'
    '"labels":[],"assignees":[]}\n'
    '{"number":30,"state":"closed","state_reason":"not_planned","title":"Dropped idea",'
    '"labels":[],"assignees":[]}\n'
)


def test_spec_sub_issues_reads_each_sub_issues_number_title_state_and_reason():
    shell = Shell({("api",): SUB_ISSUES})

    assert spec_sub_issues("owner/proto", 25, shell) == [
        SubIssue(28, "Recognise spec tickets", "closed", "completed", [], []),
        SubIssue(29, "Declare a check command", "open", None, [], []),
        SubIssue(30, "Dropped idea", "closed", "not_planned", [], []),
    ]
    ((gh, api, paginate, endpoint, *_),) = shell.calls
    assert [gh, api, paginate, endpoint] == [
        "gh",
        "api",
        "--paginate",
        "repos/owner/proto/issues/25/sub_issues",
    ]


def test_spec_sub_issues_reads_each_sub_issues_label_names_and_assignee_logins():
    reply = (
        '{"number":29,"state":"open","state_reason":null,"title":"T",'
        '"labels":["ready-for-human","spec"],"assignees":["someone"]}\n'
    )
    shell = Shell({("api",): reply})

    (issue,) = spec_sub_issues("owner/proto", 25, shell)

    assert (issue.labels, issue.assignees) == (["ready-for-human", "spec"], ["someone"])
    assert "labels: [.labels[].name]" in shell.calls[0][-1]
    assert "assignees: [.assignees[].login]" in shell.calls[0][-1]


def test_a_spec_with_no_sub_issues_has_an_empty_list():
    assert spec_sub_issues("owner/proto", 25, Shell({("api",): ""})) == []


def test_spec_sub_issues_refuses_when_gh_cannot_read_the_spec():
    shell = Shell({("api",): failed("gh api", "HTTP 404: Not Found")})

    with pytest.raises(RefusalError, match=r"sub-issues of #25 in owner/proto: HTTP 404"):
        spec_sub_issues("owner/proto", 25, shell)


def test_an_integration_merge_subject_names_the_ticket_branch_and_the_integration_branch():
    assert (
        integration_merge_message("spec-25-fix-32-merge-and-check", 25)
        == "Integrate spec-25-fix-32-merge-and-check into spec-25"
    )


def test_an_integration_merge_subject_parses_back_to_its_ticket():
    subject = integration_merge_message("spec-25-fix-32-merge-and-check", 25)

    assert parse_integration_merge(subject) == TicketBranch(32, 25)


@pytest.mark.parametrize(
    "subject",
    [
        "Merge branch 'spec-25-fix-32-merge-and-check' into spec-25",
        "Integrate fix-32-merge-and-check into spec-25",
        "Integrate spec-24-fix-32-merge-and-check into spec-25",
    ],
    ids=["git's default subject", "lone ticket branch", "another spec's ticket"],
)
def test_other_merge_subjects_name_no_integrated_ticket(subject):
    assert parse_integration_merge(subject) is None
