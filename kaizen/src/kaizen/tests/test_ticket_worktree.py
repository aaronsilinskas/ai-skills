"""Tests for ``resolve_ticket_worktree``: the project, issue and spec of a ticket worktree."""

from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError
from kaizen.shared.ticket_worktree import resolve_ticket_worktree
from kaizen.tests.ticket_shell import Shell


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    """A registry with one project, ``proto``, and its worktree root."""
    projects = tmp_path / "projects"
    projects.mkdir()
    repo = tmp_path / "proto"
    (projects / "proto.md").write_text(
        f"---\npath: {repo}\ngithub: owner/proto\npublic: true\n---\n# proto\n"
    )
    return projects, repo / ".claude" / "worktrees"


def _shell(branch: str) -> Shell:
    return Shell(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): f"{branch}\n",
            ("ls-remote",): "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n",
        }
    )


def test_a_spec_ticket_worktree_resolves_to_its_project_issue_and_spec(tmp_path):
    projects, root = _setup(tmp_path)
    branch = "spec-25-fix-28-recognise-spec-tickets"

    ticket = resolve_ticket_worktree(root / branch, _shell(branch), projects)

    assert (ticket.project.name, ticket.issue, ticket.spec) == ("proto", 28, 25)
    assert ticket.branch == branch


def test_a_lone_ticket_worktree_resolves_to_no_spec(tmp_path):
    projects, root = _setup(tmp_path)
    branch = "fix-22-kaizen-one-failure-convention"

    ticket = resolve_ticket_worktree(root / branch, _shell(branch), projects)

    assert (ticket.issue, ticket.spec) == (22, None)


@pytest.mark.parametrize(
    "branch", ["spec-25", "spec-25-domain-docs", "ticket-28", "spec-x-fix-1-a"]
)
def test_a_worktree_on_any_other_branch_is_refused(tmp_path, branch):
    projects, root = _setup(tmp_path)

    with pytest.raises(RefusalError, match="not a fix-<issue>-<slug> ticket branch"):
        resolve_ticket_worktree(root / branch, _shell(branch), projects)


def test_a_docs_change_worktree_resolves_to_no_issue_and_no_spec(tmp_path):
    projects, root = _setup(tmp_path)
    branch = "docs-issueless-mode"

    ticket = resolve_ticket_worktree(root / branch, _shell(branch), projects)

    assert (ticket.project.name, ticket.issue, ticket.spec) == ("proto", None, None)
