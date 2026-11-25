"""What more than one command shares about a spec: its integration branch, its sub-issues and
which of a ticket's blockers still keep it waiting.

The branch names themselves, and which tickets an integration branch's merges hold, live in
``kaizen/shared/branch.py``, below every command group.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from kaizen.shared.branch import IntegrationBranch, fetch_branch, integrated_issues
from kaizen.shared.common import RefusalError, Runner, run_or_refuse
from kaizen.shared.issue_graph import IssueRef, LinkedIssue, blockers_of
from kaizen.shared.registry import home_repos
from kaizen.shared.worktree import list_worktrees


@dataclass(frozen=True)
class SubIssue:
    """One of a spec's sub-issues, as GitHub reports it."""

    number: int
    title: str
    state: str
    """``open`` or ``closed``."""
    state_reason: str | None
    """Why it is in its state: ``completed``, ``not_planned``, ``reopened``, or ``None``."""
    labels: list[str]
    """The label names."""
    assignees: list[str]
    """The assignees' logins."""


@dataclass(frozen=True)
class TicketBlockers:
    """A spec ticket's open blockers, read against what is integrated into the spec.

    A spec's tickets close only when its PR merges, so a blocker that is a ticket already
    integrated into the spec stays open on GitHub but no longer keeps its ticket waiting.

    A blocker in a repo outside the home is kept only as a count, never as an issue, so its repo
    is neither followed nor echoed (ADR 0002).
    """

    all_open: list[LinkedIssue]
    """Its open blockers in the home's repos."""
    integrated: set[IssueRef]
    """Those of them that are tickets already integrated into the spec."""
    outside: int = 0
    """How many of its blockers, open or closed, are in a repo outside the home; each counts as
    open."""

    @property
    def pending(self) -> list[LinkedIssue]:
        """The open blockers in the home still to be integrated, or outside the spec."""
        return [b for b in self.all_open if b.ref not in self.integrated]

    @property
    def waiting(self) -> bool:
        """Whether a blocker still keeps the ticket waiting: a pending one, or one outside the
        home."""
        return bool(self.pending) or self.outside > 0

    @property
    def outside_words(self) -> str | None:
        """The blockers outside the home in words that never name a repo, such as ``an issue
        outside this home``; ``None`` when there are none."""
        if not self.outside:
            return None
        issues = "an issue" if self.outside == 1 else f"{self.outside} issues"
        return f"{issues} outside this home"


def ticket_blockers(
    ticket: IssueRef, integrated: set[int], projects_dir: Path, run: Runner
) -> TicketBlockers:
    """*ticket*'s open blockers in the home's repos (the registry in *projects_dir*), with those
    among *integrated* (the spec's integrated issues, in *ticket*'s repo) marked, and a count of
    its blockers outside the home, whatever their state."""
    repos = home_repos(projects_dir)
    blockers = blockers_of(ticket, run)
    inside = [b for b in blockers if b.ref.github.lower() in repos]
    open_inside = [b for b in inside if b.state == "open"]
    done = {IssueRef(ticket.github, number) for number in integrated}
    return TicketBlockers(
        open_inside, {b.ref for b in open_inside} & done, len(blockers) - len(inside)
    )


def fetch_integrated_issues(
    checkout: str, spec: int, branch: IntegrationBranch, run: Runner
) -> set[int]:
    """Reads the issues integrated into spec *spec*'s integration *branch*, after fetching it
    alone from ``origin`` when it is there; refuses when the fetch fails."""
    tip = branch.ref
    if branch.on_origin:
        tip = fetch_branch(checkout, branch.name, run, "check that origin is reachable, then rerun")
    return integrated_issues(checkout, spec, tip, run)


def refuse_checked_out(checkout: str, branch: str, run: Runner, *, rerun: str) -> None:
    """Refuses when the main checkout or any of its worktrees is on *branch*, which a command is
    about to delete; the fix ends by running *rerun* again."""
    for worktree in list_worktrees(checkout, run):
        if worktree.branch == branch:
            raise RefusalError(
                f"{branch} is checked out in {worktree.path}, so it can't be deleted",
                f"switch {worktree.path} to another branch, then run `{rerun}` again",
            )


def spec_sub_issues(github: str, spec: int, run: Runner) -> list[SubIssue]:
    """Spec *spec*'s sub-issues in *github*, read from GitHub each time rather than stored."""
    out = run_or_refuse(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/{github}/issues/{spec}/sub_issues",
            "--jq",
            ".[] | {number, title, state, state_reason, labels: [.labels[].name],"
            " assignees: [.assignees[].login]}",
        ],
        run,
        f"could not read the sub-issues of #{spec} in {github}",
        f"check the spec number and that `gh -R {github} issue view {spec}` works",
    )
    issues = (json.loads(line) for line in out.splitlines() if line.strip())
    return [
        SubIssue(
            i["number"], i["title"], i["state"], i["state_reason"], i["labels"], i["assignees"]
        )
        for i in issues
    ]
