"""The issue graph: issue references, reading one issue with its comments, parent and blockers,
and adding sub-issue and blocked-by edges.

Shared by the ``issue``, ``spec`` and ``ticket`` groups. Every list call paginates.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kaizen.shared.common import RefusalError, Runner, run_or_refuse
from kaizen.shared.registry import home_repos, resolve, resolve_checkout

_ISSUE_FIELDS = "number,title,state,stateReason,labels,assignees,body,comments,url"

_LINK_FIELDS = "{id, number, title, state, pull_request}"

_NUMBER = re.compile(r"#?(\d+)")
_PROJECT_REF = re.compile(r"([\w.-]+)#(\d+)")
_REPO_REF = re.compile(r"([\w.-]+/[\w.-]+)#(\d+)")
_API_REPO = re.compile(r"https://api\.github\.com/repos/([^/]+/[^/]+)")


@dataclass(frozen=True)
class IssueRef:
    github: str
    """The repo, as ``owner/repo``."""
    number: int

    def __str__(self) -> str:
        return f"{self.github}#{self.number}"

    def short(self, github: str) -> str:
        """``#N`` when the issue is in *github*, else the full ``owner/repo#N``."""
        return f"#{self.number}" if github == self.github else str(self)


@dataclass(frozen=True)
class Comment:
    author: str
    date: str
    """The day it was posted, as ``YYYY-MM-DD``."""
    body: str


@dataclass(frozen=True)
class Issue:
    ref: IssueRef
    title: str
    state: str
    """``open`` or ``closed``."""
    state_reason: str | None
    """Such as ``completed`` or ``not_planned``, as the REST API spells it; ``None`` when unset."""
    labels: list[str]
    assignees: list[str]
    body: str
    comments: list[Comment]


@dataclass(frozen=True)
class LinkedIssue:
    """An issue another one links to, as its parent or a blocker."""

    ref: IssueRef
    title: str
    state: str
    """``open`` or ``closed``."""


@dataclass(frozen=True)
class ResolvedIssue:
    """An issue that exists, with the database id the edge writes send."""

    issue: LinkedIssue
    id: int


@dataclass(frozen=True)
class EdgeWrite:
    """One edge write: a POST of a database id to an issue's sub-issues or blocked-by list."""

    child: IssueRef
    relation: str
    """``is a sub-issue of`` or ``is blocked by``."""
    other: IssueRef
    """The parent or the blocker."""
    endpoint: str
    id_field: str
    """``sub_issue_id`` or ``issue_id``."""
    id: int

    def __str__(self) -> str:
        return f"POST {self.endpoint} {self.id_field}={self.id}"

    def describe(self, github: str | None = None) -> str:
        """The edge in words, each issue as ``#N`` when it is in *github*."""
        return f"{self._name(self.child, github)} {self.relation} {self._name(self.other, github)}"

    @staticmethod
    def _name(ref: IssueRef, github: str | None) -> str:
        return ref.short(github) if github else str(ref)


def parse_ref(text: str, run: Runner, projects_dir: Path) -> IssueRef:
    """The issue *text* names: ``N`` or ``#N`` in the project of the checkout the command runs in
    (as ``resolve_checkout`` finds it), ``<project>#N`` in that project's repo, or
    ``owner/repo#N`` as given; refuses a repo no registered project has, so no command reads or
    edits an issue outside the home."""
    if match := _NUMBER.fullmatch(text):
        project, _ = resolve_checkout(run, None, projects_dir)
        return IssueRef(project.github, int(match.group(1)))
    if match := _REPO_REF.fullmatch(text):
        github = match.group(1)
        if github.lower() not in home_repos(projects_dir):
            raise RefusalError(
                f"{github} is not a repo of this home",
                "name an issue in a registered project's repo, or register the project",
            )
        return IssueRef(github, int(match.group(2)))
    if match := _PROJECT_REF.fullmatch(text):
        return IssueRef(resolve(match.group(1), projects_dir).github, int(match.group(2)))
    raise RefusalError(
        f"{text!r} is not an issue reference",
        "name the issue as N, #N, <project>#N or owner/repo#N",
    )


def view_issue(ref: IssueRef, fields: str, run: Runner) -> dict[str, Any]:
    """The ``gh issue view --json`` *fields* of *ref*; refuses an issue gh can't read."""
    out = run_or_refuse(
        ["gh", "-R", ref.github, "issue", "view", str(ref.number), "--json", fields],
        run,
        f"could not read issue #{ref.number} in {ref.github}",
        f"check the issue number and that `gh -R {ref.github} issue view {ref.number}` works",
    )
    data: dict[str, Any] = json.loads(out)
    return data


def read_issue(ref: IssueRef, run: Runner) -> Issue:
    """Issue *ref* with its body and every comment, open or closed; refuses a pull request and
    an issue gh can't read."""
    data = view_issue(ref, _ISSUE_FIELDS, run)
    if "/pull/" in data["url"]:
        raise RefusalError(
            f"{ref} is a pull request, not an issue",
            f"read it with `gh -R {ref.github} pr view {ref.number}`",
        )
    comments = [
        Comment(author=_login(c["author"]), date=c["createdAt"][:10], body=c["body"])
        for c in data["comments"]
    ]
    return Issue(
        ref=ref,
        title=data["title"],
        state=data["state"].lower(),
        state_reason=data["stateReason"].lower() or None,
        labels=[label["name"] for label in data["labels"]],
        assignees=[a["login"] for a in data["assignees"]],
        body=data["body"],
        comments=comments,
    )


def parent_of(ref: IssueRef, run: Runner) -> LinkedIssue | None:
    """The issue *ref* is a sub-issue of, in any repo; ``None`` when it has none."""
    endpoint = f"repos/{ref.github}/issues/{ref.number}/parent"
    out = _get_unless_404(
        ["gh", "api", endpoint, "--jq", "{number, title, state, repository_url}"],
        run,
        f"could not read the parent of {ref}",
        f"check that `gh api {endpoint}` works",
    )
    return None if out is None else _linked(json.loads(out))


def blockers_of(ref: IssueRef, run: Runner) -> list[LinkedIssue]:
    """Every issue, open or closed and in any repo, that blocks *ref*."""
    out = run_or_refuse(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/{ref.github}/issues/{ref.number}/dependencies/blocked_by",
            "--jq",
            ".[] | {number, title, state, repository_url}",
        ],
        run,
        f"could not read the blockers of {ref}",
        f"check that `gh api repos/{ref.github}/issues/{ref.number}/dependencies/blocked_by` works",
    )
    return [_linked(json.loads(line)) for line in out.splitlines() if line.strip()]


def open_blockers(ref: IssueRef, run: Runner) -> list[LinkedIssue]:
    """The open issues, in any repo, that block *ref*."""
    return [blocker for blocker in blockers_of(ref, run) if blocker.state == "open"]


def resolve_issue(ref: IssueRef, run: Runner) -> ResolvedIssue:
    """Issue *ref* with its database id; refuses a missing issue and a pull request."""
    endpoint = f"repos/{ref.github}/issues/{ref.number}"
    out = _get_unless_404(
        ["gh", "api", endpoint, "--jq", _LINK_FIELDS],
        run,
        f"could not read {ref}",
        f"check that `gh api {endpoint}` works",
    )
    if out is None:
        raise RefusalError(
            f"{ref} does not exist",
            f"check the reference; `gh -R {ref.github} issue list` lists its issues",
        )
    data = json.loads(out)
    if data.get("pull_request"):
        raise RefusalError(
            f"{ref} is a pull request, not an issue", "link issues only; name an issue instead"
        )
    return ResolvedIssue(LinkedIssue(ref, data["title"], data["state"]), data["id"])


def sub_issue_write(parent: IssueRef, child: ResolvedIssue) -> EdgeWrite:
    """The write that makes *child* a sub-issue of *parent*."""
    endpoint = f"repos/{parent.github}/issues/{parent.number}/sub_issues"
    return EdgeWrite(
        child.issue.ref, "is a sub-issue of", parent, endpoint, "sub_issue_id", child.id
    )


def blocked_by_write(child: IssueRef, blocker: ResolvedIssue) -> EdgeWrite:
    """The write that marks *child* blocked by *blocker*."""
    endpoint = f"repos/{child.github}/issues/{child.number}/dependencies/blocked_by"
    return EdgeWrite(child, "is blocked by", blocker.issue.ref, endpoint, "issue_id", blocker.id)


def send_edge(write: EdgeWrite, run: Runner) -> None:
    """Sends *write*; raises ``CalledProcessError`` when GitHub rejects it."""
    run(["gh", "api", "-X", "POST", write.endpoint, "-F", f"{write.id_field}={write.id}"])


def add_edge(write: EdgeWrite, run: Runner) -> None:
    """Sends *write*; refuses with GitHub's own message when GitHub rejects it, such as a cycle."""
    try:
        send_edge(write, run)
    except subprocess.CalledProcessError as exc:
        raise RefusalError(
            f"GitHub refused the edge {write.describe()}: {_github_message(exc)}",
            "the edges printed above are added; fix what GitHub names, then add the rest "
            "with `kaizen issue link`, which skips edges already present",
        ) from exc


def body_and_comments_lines(issue: Issue) -> list[str]:
    """The body, then each comment with its author and date, as `kaizen ticket start` and
    `kaizen issue show` both print them; says so when there is no body or no comment."""
    lines = [f"\nbody:\n{issue.body}" if issue.body else "\nbody: none"]
    lines += [f"\ncomment by {c.author} on {c.date}:\n{c.body}" for c in issue.comments]
    if not issue.comments:
        lines.append("\n(no comments)")
    return lines


def _get_unless_404(cmd: list[str], run: Runner, check: str, fix: str) -> str | None:
    """*cmd*'s output, or ``None`` when GitHub answers 404; any other failure refuses."""
    try:
        return run(cmd)
    except subprocess.CalledProcessError as exc:
        if "HTTP 404" in (exc.stderr or ""):
            return None
        raise RefusalError(f"{check}: {(exc.stderr or '').strip()}", fix) from exc


def _github_message(exc: subprocess.CalledProcessError) -> str:
    """GitHub's reason for a rejected write: the response body's message and each error's
    message, which ``gh api`` prints to stdout, else gh's own stderr line."""
    try:
        body = json.loads(exc.output or "")
    except ValueError:
        body = None
    if isinstance(body, dict) and body.get("message"):
        details = [
            e["message"]
            for e in body.get("errors") or []
            if isinstance(e, dict) and e.get("message")
        ]
        return "; ".join([body["message"], *details])
    return (exc.stderr or "").strip().removeprefix("gh: ")


def _linked(data: dict[str, Any]) -> LinkedIssue:
    match = _API_REPO.match(data["repository_url"])
    if match is None:
        raise ValueError(f"unexpected repository_url {data['repository_url']!r}")
    return LinkedIssue(IssueRef(match.group(1), data["number"]), data["title"], data["state"])


def _login(author: dict[str, str] | None) -> str:
    """The author's login; gh gives a deleted account no login, which GitHub shows as ghost."""
    return (author or {}).get("login") or "ghost"
