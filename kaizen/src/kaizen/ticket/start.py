"""``kaizen ticket start``: create a project's ticket worktree for one issue, or for a docs
change."""

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from kaizen.shared.branch import (
    IntegrationBranch,
    docs_branch,
    find_integration_branch,
    integration_branch,
    remote_default_branch,
    spec_ticket_branch,
)
from kaizen.shared.command_records import HomeCommand
from kaizen.shared.common import RefusalError, Runner, Say, Subparsers, run_or_refuse
from kaizen.shared.home import Home
from kaizen.shared.issue_graph import Issue, IssueRef, body_and_comments_lines
from kaizen.shared.registry import Project, refuse_undeclared_code_paths, resolve
from kaizen.shared.worktree import add_ticket_worktree, link_ignored_paths, list_worktrees
from kaizen.spec.common import (
    fetch_integrated_issues,
    spec_sub_issues,
    ticket_blockers,
)
from kaizen.ticket.common import open_issue

SLUG_WORDS = 5
# Dropped from the end of a derived slug, where they dangle once the title is cut short.
SLUG_TRAILING_STOPWORDS = frozenset({"the", "for", "a", "an", "of", "to", "and"})
_SLUG = re.compile(r"[\w.-]+")


@dataclass(frozen=True)
class Started:
    worktree: Path
    branch: str
    title: str | None
    """The issue's title; ``None`` for a docs change."""


def start(
    project_name: str,
    issue: int | None,
    slug: str | None,
    run: Runner,
    *,
    home: Home,
    spec: int | None = None,
    ignore_blockers: bool = False,
    dry_run: bool = False,
    say: Say = print,
) -> Started:
    """Add *issue*'s ticket worktree from ``origin``, so the main checkout's branch and changes
    never matter; only its git-ignored ``worktree_links`` are linked in.

    With *spec*, the worktree is spec *spec*'s ticket worktree, based on its integration branch;
    a ticket with an open blocker not yet integrated is refused unless *ignore_blockers*.
    With no *issue*, it is the ticket worktree for a docs change on ``docs-<slug>``, so *slug* is
    required.
    """
    project = resolve(project_name, home.registry)
    checkout = project.main_checkout
    ticket_issue: Issue | None = None
    base: str | None = None
    if ignore_blockers and spec is None:
        raise RefusalError(
            "--ignore-blockers applies only to a spec's ticket",
            "drop --ignore-blockers, or pass --spec <N> to start a spec's ticket",
        )
    if issue is None:
        branch = docs_branch(_refuse_bad_docs_start(project, slug, spec))
        say(f"no issue: a docs change on {branch}, which may not touch code")
    else:
        ticket_issue = open_issue(project.github, issue, run)
        say(f"issue #{issue} is open: {ticket_issue.title}")
        if spec is not None:
            found = _refuse_outside_spec(project.github, checkout, spec, issue, run)
            where = "on origin" if found.on_origin else "local only (started with --local)"
            say(
                f"issue #{issue} is a sub-issue of spec #{spec}, whose integration branch is"
                f" {where}"
            )
            base = found.ref
            _refuse_pending_blockers(
                checkout,
                IssueRef(project.github, issue),
                spec,
                found,
                ignore_blockers,
                home.registry,
                run,
                say,
            )
        slug = _refuse_bad_slug(slug) if slug is not None else _slug(ticket_issue.title)
        branch = f"fix-{issue}-{slug}" if spec is None else spec_ticket_branch(spec, issue, slug)

    title = ticket_issue.title if ticket_issue is not None else None
    worktree = project.worktree_root / branch
    _refuse_existing(checkout, branch, worktree, run)
    if base is None:
        base = f"origin/{remote_default_branch(checkout, run)}"

    if dry_run:
        say(f"would fetch origin in {checkout}")
        if project.worktree_links:
            say(f"would refuse any worktree link that {base} tracks")
        say(f"would add worktree {worktree} on {branch} from {base}")
        link_ignored_paths(project, worktree, say, dry_run=True)
        return Started(worktree, branch, title)

    run(["git", "-C", checkout, "fetch", "origin"])
    say(f"fetched origin in {checkout}")
    _refuse_tracked_links(project, base, run)
    add_ticket_worktree(project, checkout, worktree, branch, base, run, say)
    say(f"worktree: {worktree}")
    if ticket_issue is not None:
        say(f"issue: #{issue} {ticket_issue.title}")
        for line in body_and_comments_lines(ticket_issue):
            say(line)
    return Started(worktree, branch, title)


def _refuse_tracked_links(project: Project, base: str, run: Runner) -> None:
    """Refuses a worktree link that *base* tracks, since the worktree gets that path from git.

    Runs after the fetch, so *base* exists locally and is the commit the worktree is added from.
    """
    for entry in project.worktree_links:
        cmd = [
            "git",
            "-C",
            project.main_checkout,
            "ls-tree",
            "-r",
            "--name-only",
            base,
            "--",
            entry,
        ]
        tracked = run_or_refuse(
            cmd,
            run,
            f"could not list {base} in {project.main_checkout}",
            f"check that {base} exists",
        )
        if tracked.strip():
            raise RefusalError(
                f"worktree link {entry} is tracked in {base}, so a ticket worktree already has it",
                f"list only git-ignored paths in worktree_links on {project.page}",
            )


def _refuse_bad_docs_start(project: Project, slug: str | None, spec: int | None) -> str:
    """The docs change's slug; refuses a spec, a missing or malformed slug, and a project
    with no code paths to guard."""
    if spec is not None:
        raise RefusalError(
            f"--spec {spec} needs an issue: a spec's tickets are sub-issues",
            "pass the ticket's issue number: "
            f"kaizen ticket start {project.name} <issue> --spec {spec}",
        )
    if slug is None:
        raise RefusalError(
            "no issue and no --slug: a docs change's branch is named from its slug",
            f"pass --slug <slug>, or an issue number for a code change: "
            f"kaizen ticket start {project.name} <issue>",
        )
    refuse_undeclared_code_paths(project)
    return _refuse_bad_slug(slug)


def _refuse_bad_slug(slug: str) -> str:
    if not _SLUG.fullmatch(slug):
        raise RefusalError(
            f"--slug {slug!r} is not a branch slug",
            "use letters, digits, '.', '_' and '-' only, such as --slug fix-typos",
        )
    return slug


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "start",
        help="create the ticket worktree for an issue or a docs change",
        description=(
            "Read the issue, fetch the project, and add the ticket worktree on a "
            "fix-<issue>-<slug> branch from origin's default branch (with --spec, on a "
            "spec ticket branch from the spec's integration branch, origin's or, while origin "
            "lacks it, the local one `kaizen spec start --local` made, refusing a ticket with an "
            "open blocker not yet integrated into it unless --ignore-blockers; that check "
            "fetches the integration branch alone, also on --dry-run). Prints the worktree "
            "path and the issue's title, body and comments. With no issue, add the "
            "ticket worktree for a docs change, which touches no code, on a docs-<slug> branch "
            "(--slug required, --spec refused); `kaizen ticket ship` refuses it if it touches "
            "the project's code_paths. "
            "Each path in the project's worktree_links (git-ignored, such as a downloaded "
            "tool) is then symlinked from the main checkout into the worktree; one missing "
            "there is warned about, and one the base commit tracks is refused. "
            "The project's main checkout is never changed."
        ),
    )
    parser.add_argument("project", help="a registry page name, the home included")
    parser.add_argument(
        "issue",
        type=int,
        nargs="?",
        help="the issue number in the project's repo; omit it for a docs change",
    )
    parser.add_argument(
        "--slug",
        help=(
            "branch slug (default: the first words of the title, without apostrophes or "
            "trailing stopwords; required without an issue)"
        ),
    )
    parser.add_argument(
        "--spec",
        type=int,
        help=(
            "the spec the issue is a sub-issue of: base the worktree on its integration "
            "branch, on a spec-<spec>-fix-<issue>-<slug> branch that is never pushed"
        ),
    )
    parser.add_argument(
        "--ignore-blockers",
        action="store_true",
        help=(
            "with --spec, start even though an open blocker is not yet integrated into "
            "spec-<spec>, and print the blockers started before"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "run only queries (with --spec, after fetching the integration branch alone, "
            "as `kaizen spec status` does); print the plan"
        ),
    )
    parser.set_defaults(command=HomeCommand(_command))


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    start(
        args.project,
        args.issue,
        args.slug,
        run,
        spec=args.spec,
        ignore_blockers=args.ignore_blockers,
        dry_run=args.dry_run,
        home=home,
    )


def _refuse_outside_spec(
    github: str, checkout: str, spec: int, issue: int, run: Runner
) -> IntegrationBranch:
    """Spec *spec*'s integration branch; refuses an issue outside the spec or a spec not started."""
    if issue not in {sub.number for sub in spec_sub_issues(github, spec, run)}:
        raise RefusalError(
            f"issue #{issue} is not a sub-issue of spec #{spec} in {github}",
            "check the issue and spec numbers, or add the issue to the spec's sub-issues",
        )
    found = find_integration_branch(checkout, spec, run)
    if found is None:
        raise RefusalError(
            f"origin has no {integration_branch(spec)}, spec #{spec}'s integration branch,"
            " and neither does the main checkout's clone",
            f"run `kaizen spec start {spec}` (or `--local`) first, or check the spec number",
        )
    return found


def _refuse_pending_blockers(
    checkout: str,
    ticket: IssueRef,
    spec: int,
    found: IntegrationBranch,
    ignore_blockers: bool,
    projects_dir: Path,
    run: Runner,
    say: Say,
) -> None:
    """Refuses a ticket whose open blocker is not yet integrated into the spec, the rule that
    keeps a ticket off `kaizen spec status`'s frontier; with *ignore_blockers*, says so instead."""
    integrated = fetch_integrated_issues(checkout, spec, found, run)
    blockers = ticket_blockers(ticket, integrated, projects_dir, run)
    branch = integration_branch(spec)
    if not blockers.waiting:
        say(f"issue #{ticket.number} has no open blocker still to be integrated into {branch}")
        return
    names = ", ".join(
        [b.ref.short(ticket.github) for b in blockers.pending]
        + ([blockers.outside_words] if blockers.outside_words else [])
    )
    if ignore_blockers:
        say(f"--ignore-blockers: starting before open blocker(s) {names} are in {branch}")
        return
    raise RefusalError(
        f"issue #{ticket.number} has open blocker(s) not integrated into {branch}: {names}",
        "integrate each first with `kaizen spec integrate <its worktree>` (or wait for one outside "
        "the spec to close), then rerun; or pass --ignore-blockers to start before them",
    )


def _refuse_existing(checkout: str, branch: str, worktree: Path, run: Runner) -> None:
    if worktree.exists():
        raise RefusalError(
            f"the worktree path {worktree} already exists",
            "resume the earlier attempt there, or remove it after checking it holds nothing needed",
        )
    if run(["git", "-C", checkout, "branch", "--list", branch]).strip():
        where = [path for path, b in _worktree_branches(checkout, run).items() if b == branch]
        location = f"checked out at {where[0]}" if where else "not checked out in any worktree"
        raise RefusalError(
            f"branch {branch} already exists, {location}",
            "resume the earlier attempt there, or pass --slug for a new branch name",
        )


def _worktree_branches(checkout: str, run: Runner) -> dict[str, str]:
    """Each worktree path of *checkout* mapped to its checked-out branch (detached ones omitted)."""
    return {
        worktree.path: worktree.branch
        for worktree in list_worktrees(checkout, run)
        if worktree.branch is not None
    }


def _slug(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", re.sub(r"['\u2019]", "", title.lower()))[:SLUG_WORDS]
    while words and words[-1] in SLUG_TRAILING_STOPWORDS:
        words.pop()
    if not words:
        raise RefusalError(f"the issue title {title!r} makes no slug", "pass --slug <slug>")
    return "-".join(words)
