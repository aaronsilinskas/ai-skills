"""The GitHub PR steps more than one command takes: finding, opening and updating a branch's PR."""

import json
import tempfile
from pathlib import Path
from typing import TypedDict

from kaizen.shared.common import RefusalError, Runner
from kaizen.shared.home import Home
from kaizen.shared.leak import leak_check_text
from kaizen.shared.registry import Project


def check_pr_text(title: str, body: str, project: Project, home: Home) -> None:
    """Refuses when a PR's *title* or *body* for *project* points outside *home*, before any
    ``gh`` call sends them."""
    texts = {"PR title": title, "PR body": body}
    leak_check_text(texts, home, public=project.public, denied=project.leak_deny)


class PullRequest(TypedDict):
    """The fields of ``gh pr list --json number,state,url,headRefOid``."""

    number: int
    state: str
    """``OPEN``, ``CLOSED`` (without merging) or ``MERGED``."""
    url: str
    headRefOid: str


def branch_prs(github: str, branch: str, run: Runner) -> list[PullRequest]:
    """Every PR whose head is *branch* in *github*, in any state, newest first."""
    out = run(
        [
            "gh",
            "-R",
            github,
            "pr",
            "list",
            "--head",
            branch,
            "--state",
            "all",
            "--json",
            "number,state,url,headRefOid",
        ]
    )
    prs: list[PullRequest] = json.loads(out)
    return prs


def open_pr(github: str, branch: str, run: Runner) -> str | None:
    """The URL of *branch*'s open PR, to reuse; refuses when its PR was closed without merging."""
    prs = branch_prs(github, branch, run)
    for pr in prs:
        if pr["state"] == "OPEN":
            return pr["url"]
    closed = [pr for pr in prs if pr["state"] == "CLOSED"]
    if closed:
        pr = closed[0]
        raise RefusalError(
            f"{branch} has PR #{pr['number']} closed without merging: {pr['url']}",
            "ask the maintainer whether to reopen it or take a new approach on a new branch",
        )
    return None


def merged_pr(github: str, branch: str, run: Runner, *, ship_fix: str, rerun: str) -> PullRequest:
    """*branch*'s merged PR; refuses when it has no PR (fix *ship_fix*) or none is merged yet.

    *rerun* is the command to run again once the PR has merged.
    """
    prs = branch_prs(github, branch, run)
    if not prs:
        raise RefusalError(f"no PR from {branch} in {github}", ship_fix)
    merged = [pr for pr in prs if pr["state"] == "MERGED"]
    if not merged:
        pr = prs[0]
        raise RefusalError(
            f"PR #{pr['number']} ({pr['url']}) is {pr['state']}, not MERGED",
            f"wait until the PR is merged on GitHub, then run `{rerun}` again",
        )
    return merged[0]


def enable_auto_merge(url: str, run: Runner) -> None:
    """Sets the PR at *url* to merge (with a merge commit) once its checks pass."""
    run(["gh", "pr", "merge", "--auto", "--merge", url])


def auto_merge_on(url: str, run: Runner) -> bool:
    """Whether the PR at *url* is set to merge once its checks pass."""
    out = run(["gh", "pr", "view", url, "--json", "autoMergeRequest"])
    return json.loads(out)["autoMergeRequest"] is not None


def disable_auto_merge(url: str, run: Runner) -> None:
    """Turns off auto-merge on the PR at *url*, so it waits for someone to merge it."""
    run(["gh", "pr", "merge", "--disable-auto", url])


def read_body(body_file: Path, what: str = "PR body") -> str:
    """The *what* (a PR body unless named) held in *body_file*; refuses when it can't be read."""
    try:
        return body_file.read_text()
    except OSError as exc:
        raise RefusalError(
            f"could not read the body file {body_file}: {exc.strerror}",
            f"write the {what} to a file and pass its path to --body-file",
        ) from exc


def create_pr(
    github: str,
    base: str,
    head: str,
    title: str,
    body_file: Path,
    run: Runner,
    *,
    footer: str,
    prefix: str = "",
) -> str:
    """Opens a ready PR from *head* into *base* and returns its URL.

    The body is built by ``_run_with_body``.
    """
    create = ["gh", "-R", github, "pr", "create", "--base", base, "--head", head]
    cmd = [*create, "--title", title, "--body-file"]
    out = _run_with_body(cmd, body_file, prefix, footer, run)
    return out.strip().splitlines()[-1]


def update_pr(
    github: str,
    url: str,
    title: str,
    body_file: Path,
    run: Runner,
    *,
    footer: str,
    prefix: str = "",
) -> None:
    """Replaces the title and body of the open PR at *url*.

    The body is built by ``_run_with_body``.
    """
    edit = ["gh", "-R", github, "pr", "edit", url, "--title", title, "--body-file"]
    _run_with_body(edit, body_file, prefix, footer, run)


def with_footer(text: str, footer: str) -> str:
    """*text* ending with the home's PR *footer* after a blank line, unless it already ends with
    it or *footer* is empty."""
    if not footer or text.rstrip().endswith(footer):
        return text
    return f"{text.rstrip()}\n\n{footer}\n"


def _run_with_body(cmd: list[str], body_file: Path, prefix: str, footer: str, run: Runner) -> str:
    """Runs *cmd* with the path of the PR body built from *body_file* appended.

    The body is *prefix* (such as ``Closes`` lines), then the body file's text ending with
    *footer* (``with_footer``). An amended body goes to a temporary file outside any worktree,
    since the caller's worktree must stay clean.
    """
    text = read_body(body_file)
    body = prefix + with_footer(text, footer)
    if body == text:
        return run([*cmd, str(body_file)])
    with tempfile.TemporaryDirectory() as tmp:
        amended = Path(tmp) / "body.md"
        amended.write_text(body)
        return run([*cmd, str(amended)])
