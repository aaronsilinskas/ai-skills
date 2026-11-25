"""A **ticket worktree**: the project, branch and issue worked out from a worktree's path and
branch with no stored state, and the git operations a command runs on it."""

from dataclasses import dataclass
from pathlib import Path

from kaizen.shared.branch import (
    fetch_branch,
    find_integration_branch,
    integration_branch,
    parse_ticket_branch,
    remote_default_branch,
)
from kaizen.shared.comment_only import FileChange
from kaizen.shared.common import RefusalError, Runner, run_or_refuse
from kaizen.shared.registry import (
    Project,
    all_projects,
    refuse_undeclared_code_paths,
    worktree_owner,
)


@dataclass(frozen=True)
class TicketWorktree:
    project: Project
    path: Path
    branch: str
    issue: int | None
    """The issue the ticket closes; ``None`` when a ``docs-<slug>`` branch holds a docs change."""
    default_branch: str
    spec: int | None
    """The spec the ticket belongs to (a ``spec-<N>-fix-…`` branch); ``None`` for a lone ticket."""

    @property
    def label(self) -> str:
        """What the worktree is, for a command's first line: a docs change's, or an issue's."""
        if self.issue is None:
            return "ticket worktree for a docs change"
        return f"ticket worktree for issue #{self.issue}"

    @property
    def base_branch(self) -> str:
        """The branch the ticket is built on: its spec's integration branch, else the default."""
        return integration_branch(self.spec) if self.spec is not None else self.default_branch

    @property
    def base_ref(self) -> str:
        """The base branch's remote-tracking ref, ``origin/<base>``, as ``fetch_base`` sets it."""
        return f"origin/{self.base_branch}"


def fetch_base(ticket: TicketWorktree, run: Runner) -> str:
    """Fetches only the ticket's base branch from ``origin`` and returns its ref, ``origin/<base>``.

    A spec's ticket whose integration branch is only local (see ``local_base``) gets that branch,
    and nothing is fetched. Refuses when neither ``origin`` nor the clone has the branch, such as
    a spec whose integration branch was never started.
    """
    local = local_base(ticket, run)
    if local is not None:
        return local
    return fetch_branch(str(ticket.path), ticket.base_branch, run, _missing_base_fix(ticket))


def base_ref(ticket: TicketWorktree, run: Runner) -> str:
    """The ticket's base ref as last fetched, fetching nothing: ``local_base`` when it has one,
    else ``origin/<base>``. Only queries."""
    return local_base(ticket, run) or ticket.base_ref


def local_base(ticket: TicketWorktree, run: Runner) -> str | None:
    """The local integration branch a spec's ticket is based on while ``origin`` lacks it, as
    ``kaizen spec start --local`` leaves it until the first integration; ``None`` for any other
    ticket. Only queries."""
    if ticket.spec is None:
        return None
    found = find_integration_branch(str(ticket.path), ticket.spec, run)
    return found.ref if found is not None and not found.on_origin else None


def _missing_base_fix(ticket: TicketWorktree) -> str:
    if ticket.spec is not None:
        return (
            f"check that origin has {ticket.base_branch}; if spec #{ticket.spec}'s integration"
            f" branch was never started, run `kaizen spec start {ticket.spec}`"
        )
    return f"check that origin has {ticket.base_branch} and that the remote is reachable"


def resolve_ticket_worktree(path: Path, run: Runner, projects_dir: Path) -> TicketWorktree:
    """The project and issue of the ticket worktree at *path*, worked out with no stored state.

    The project is the one whose worktree root holds *path*; the issue, and the spec if any,
    come from the ``fix-<issue>-<slug>`` or ``spec-<N>-fix-<issue>-<slug>`` branch checked
    out there, and a ``docs-<slug>`` branch has neither. Refuses, in this order, a path under
    no project's worktree root, a worktree on the default branch, and any other branch.
    """
    path = path.expanduser().resolve()
    projects = all_projects(projects_dir)
    project = worktree_owner(path, projects)
    if project is None:
        roots = ", ".join(str(p.worktree_root) for p in projects)
        raise RefusalError(
            f"{path} is not a registered project's ticket worktree",
            f"pass a worktree made by `kaizen ticket start`, directly under one of: {roots}",
        )
    branch = run_or_refuse(
        ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
        run,
        f"could not read the branch of {path}",
        "check that the path is a git worktree",
    ).strip()
    default = remote_default_branch(project.main_checkout, run)
    if branch == default:
        raise RefusalError(
            f"{path} is on the default branch {default}",
            "work lands through a PR: commit on a fix-<issue>-<slug> branch "
            "from `kaizen ticket start`",
        )
    parsed = parse_ticket_branch(branch)
    if parsed is None:
        raise RefusalError(
            f"{path} is on {branch!r}, not a fix-<issue>-<slug> ticket branch"
            " (or spec-<N>-fix-<issue>-<slug> for a spec's ticket,"
            " docs-<slug> for a docs change)",
            "use the ticket worktree `kaizen ticket start` made, on its own branch",
        )
    return TicketWorktree(project, path, branch, parsed.issue, default, parsed.spec)


def refuse_spec_ticket(ticket: TicketWorktree) -> None:
    """Refuses a spec's ticket worktree, which integrates into its spec instead of its own PR."""
    if ticket.spec is not None:
        raise RefusalError(
            f"{ticket.path} is a ticket worktree of spec #{ticket.spec} (on {ticket.branch}),"
            f" which integrates into {integration_branch(ticket.spec)}, not its own PR",
            f"run `kaizen spec integrate {ticket.path}`",
        )


def refuse_uncommitted(ticket: TicketWorktree, run: Runner, *, fix: str) -> None:
    """Refuses a ticket worktree with uncommitted changes, listing them."""
    if status := uncommitted(ticket, run):
        raise RefusalError(f"{ticket.path} has uncommitted changes:\n{status}", fix)


def uncommitted(ticket: TicketWorktree, run: Runner) -> str:
    """The ticket worktree's uncommitted changes as ``git status --porcelain`` lists them;
    empty when it is clean."""
    return run(["git", "-C", str(ticket.path), "status", "--porcelain"]).rstrip()


def changed_paths(ticket: TicketWorktree, run: Runner) -> list[str]:
    """The paths the ticket's diff against the default branch changes.

    Renames count as a deletion and an addition, so moving a file out of a code path is caught.
    """
    base = f"origin/{ticket.default_branch}"
    changed = run(
        ["git", "-C", str(ticket.path), "diff", "--name-only", "--no-renames", f"{base}...HEAD"]
    )
    return changed.splitlines()


def file_changes(ticket: TicketWorktree, run: Runner) -> list[FileChange]:
    """Each file the ticket's diff against the default branch changes, with its source at the
    merge base and at ``HEAD``. Renames count as a deletion and an addition, as in
    ``changed_paths``; refuses a file git cannot show."""
    worktree = str(ticket.path)
    upstream = f"origin/{ticket.default_branch}"
    statuses = run(
        ["git", "-C", worktree, "diff", "--name-status", "--no-renames", f"{upstream}...HEAD"]
    )
    base = run(["git", "-C", worktree, "merge-base", upstream, "HEAD"]).strip()

    def source(ref: str, path: str) -> str:
        return run_or_refuse(
            ["git", "-C", worktree, "show", f"{ref}:{path}"],
            run,
            f"could not read {path} at {ref}",
            "check the worktree's git objects, then ship again",
        )

    changes = []
    for line in statuses.splitlines():
        status, _, path = line.partition("\t")
        old = None if status == "A" else source(base, path)
        new = None if status == "D" else source("HEAD", path)
        changes.append(FileChange(path, old, new))
    return changes


def refuse_code_changes(ticket: TicketWorktree, changed: list[str]) -> None:
    """Refuses a docs change whose *changed* paths touch code, naming the files."""
    refuse_undeclared_code_paths(ticket.project)
    base = f"origin/{ticket.default_branch}"
    code = [path for path in changed if ticket.project.is_code(path)]
    if code:
        listed = "\n".join(f"  {path}" for path in code)
        raise RefusalError(
            f"{ticket.branch} holds a docs change, but its diff against {base} touches"
            f" code:\n{listed}",
            f"open an issue for the change and start it with"
            f" `kaizen ticket start {ticket.project.name} <issue>`, or drop the code changes",
        )


def refuse_nothing_ahead(ticket: TicketWorktree, base: str, run: Runner, *, fix: str) -> int:
    """How many commits the ticket's branch is ahead of *base*; refuses none."""
    ahead = commits_ahead(ticket, base, run)
    if not ahead:
        raise RefusalError(f"{ticket.branch} has no commits ahead of {base}", fix)
    return ahead


def commits_ahead(ticket: TicketWorktree, base: str, run: Runner) -> int:
    """How many commits the ticket's branch has that *base* lacks."""
    return int(run(["git", "-C", str(ticket.path), "rev-list", "--count", f"{base}..HEAD"]))
