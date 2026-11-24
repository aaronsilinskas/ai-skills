"""The issue queries of the ``kaizen ticket`` commands: an open issue's title, or all of it."""

from kaizen.shared.common import RefusalError, Runner
from kaizen.shared.issue_graph import Issue, IssueRef, read_issue, view_issue


def open_issue_title(github: str, issue: int, run: Runner) -> str:
    """The title of issue *issue* in *github*; refuses when it is closed or can't be read."""
    data = view_issue(IssueRef(github, issue), "state,title", run)
    _refuse_closed(issue, data["title"], data["state"].lower())
    return str(data["title"])


def open_issue(github: str, issue: int, run: Runner) -> Issue:
    """Issue *issue* in *github* with its body and comments; refuses like `open_issue_title`."""
    found = read_issue(IssueRef(github, issue), run)
    _refuse_closed(issue, found.title, found.state)
    return found


def _refuse_closed(issue: int, title: str, state: str) -> None:
    if state != "open":
        raise RefusalError(
            f"issue #{issue} is closed: {title}",
            "pick an open issue, or reopen this one if the work is still wanted",
        )
