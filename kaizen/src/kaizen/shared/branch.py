"""Branch names and steps more than one command shares.

A spec's **integration branch** is ``spec-<N>``. A ticket of that spec is built on
``spec-<N>-fix-<issue>-<slug>``, and a ticket with no spec on ``fix-<issue>-<slug>``.
The domain-doc edits from grilling spec ``<N>`` ship on ``spec-<N>-domain-docs``.
A **docs change**, a change to docs only that needs no issue, is built on ``docs-<slug>``.
Integrating a ticket records its branch in the merge commit's subject, so the integration
branch's history alone says which tickets are in it.
"""

import re
import subprocess
from dataclasses import dataclass

from kaizen.shared.common import RefusalError, Runner, Say

_TICKET_BRANCH = re.compile(r"(?:spec-(\d+)-)?fix-(\d+)-[\w.-]+|docs-[\w.-]+")
_MERGE_SUBJECT = re.compile(r"Integrate (\S+) into spec-(\d+)")

MAIN_CHECKOUT_NOTE = (
    "note: leave the rest of the main checkout as it is, since other sessions work there. git may"
    " call the merged branch 'not yet merged to HEAD' there, which is expected: a squash merge"
    " never merges the branch itself"
)


@dataclass(frozen=True)
class TicketBranch:
    issue: int | None
    """The issue the ticket closes; ``None`` when the branch holds a docs change."""
    spec: int | None
    """The spec whose integration branch the ticket integrates into; ``None`` for a lone ticket."""


def integration_branch(spec: int) -> str:
    """The name of spec *spec*'s integration branch."""
    return f"spec-{spec}"


def domain_docs_branch(spec: int) -> str:
    """The branch ``kaizen spec publish`` ships spec *spec*'s domain-doc edits on, and
    ``kaizen ticket publish`` waits for."""
    return f"{integration_branch(spec)}-domain-docs"


def spec_ticket_branch(spec: int, issue: int, slug: str) -> str:
    """The branch name of ticket *issue* of spec *spec*."""
    return f"{integration_branch(spec)}-fix-{issue}-{slug}"


def docs_branch(slug: str) -> str:
    return f"docs-{slug}"


def parse_ticket_branch(branch: str) -> TicketBranch | None:
    """The issue and spec a ``[spec-<N>-]fix-<issue>-<slug>`` or ``docs-<slug>`` branch names.

    ``None`` for any other branch.
    """
    match = _TICKET_BRANCH.fullmatch(branch)
    if not match:
        return None
    spec, issue = match.groups()
    return TicketBranch(int(issue) if issue else None, int(spec) if spec else None)


def integration_merge_message(ticket_branch: str, spec: int) -> str:
    """The subject of the ``--no-ff`` merge that integrates *ticket_branch* into spec *spec*."""
    return f"Integrate {ticket_branch} into {integration_branch(spec)}"


def integrated_issues(checkout: str, spec: int, tip: str, run: Runner) -> set[int]:
    """The issues of spec *spec* with an integration merge in *tip*'s history, as last fetched."""
    subjects = run(["git", "-C", checkout, "log", "--merges", "--format=%s", tip])
    return {
        ticket.issue
        for ticket in map(parse_integration_merge, subjects.splitlines())
        if ticket is not None and ticket.spec == spec and ticket.issue is not None
    }


def parse_integration_merge(subject: str) -> TicketBranch | None:
    """The spec ticket an integration merge's *subject* names; ``None`` for any other subject."""
    match = _MERGE_SUBJECT.fullmatch(subject)
    if not match:
        return None
    ticket = parse_ticket_branch(match.group(1))
    if ticket is None or ticket.spec != int(match.group(2)):
        return None
    return ticket


def is_ancestor(checkout: str, ancestor: str, descendant: str, run: Runner) -> bool:
    """Whether *ancestor* is in *descendant*'s history in *checkout*.

    Raises ``CalledProcessError`` when git can't tell, such as for a commit it lacks.
    """
    try:
        run(["git", "-C", checkout, "merge-base", "--is-ancestor", ancestor, descendant])
    except subprocess.CalledProcessError as exc:
        if exc.returncode != 1:  # 1 means "not an ancestor"; anything else is a real failure
            raise
        return False
    return True


def remote_default_branch(checkout: str, run: Runner) -> str:
    """The branch ``origin``'s HEAD points at, read from the remote rather than assumed."""
    out = run(["git", "-C", checkout, "ls-remote", "--symref", "origin", "HEAD"])
    for line in out.splitlines():
        if line.startswith("ref: refs/heads/"):
            return line.removeprefix("ref: refs/heads/").split("\t", 1)[0]
    raise RefusalError(
        f"could not read origin's default branch in {checkout}",
        f"check that `git -C {checkout} ls-remote --symref origin HEAD` names a branch",
    )


def default_branch(run: Runner) -> str:
    """The default branch of the checkout the command runs in: ``origin/HEAD`` as last fetched,
    or asked of origin when the clone never recorded it; refuses when neither answers."""
    try:
        tracking = run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"]).strip()
    except subprocess.CalledProcessError:
        pass
    else:
        return tracking.removeprefix("origin/")
    try:
        return remote_default_branch(".", run)
    except subprocess.CalledProcessError as exc:
        raise RefusalError(
            f"could not read the default branch: origin/HEAD is unset and origin did not answer:"
            f" {(exc.stderr or '').strip()}",
            "run `git remote set-head origin --auto`, or name the branches with --branch",
        ) from exc


def origin_has_branch(checkout: str, branch: str, run: Runner) -> bool:
    """Whether ``origin`` has *branch*, asked of the remote itself rather than a tracking ref."""
    out = run(["git", "-C", checkout, "ls-remote", "--heads", "origin", branch])
    return any(line.endswith(f"\trefs/heads/{branch}") for line in out.splitlines())


def local_branch_head(checkout: str, branch: str, run: Runner) -> str | None:
    """The commit the local *branch* points at, or ``None`` when there is no such branch."""
    out = run(
        ["git", "-C", checkout, "for-each-ref", "--format=%(objectname)", f"refs/heads/{branch}"]
    )
    return out.strip() or None


@dataclass(frozen=True)
class IntegrationBranch:
    """Where a started spec's integration branch is: on ``origin``, or only in the local clone,
    where ``kaizen spec start --local`` made it and no push has published it yet."""

    name: str
    on_origin: bool

    @property
    def ref(self) -> str:
        """The ref a command reads it at: ``origin/<name>``, or the local branch itself."""
        return f"origin/{self.name}" if self.on_origin else self.name


def find_integration_branch(checkout: str, spec: int, run: Runner) -> IntegrationBranch | None:
    """Spec *spec*'s integration branch, on ``origin`` when the remote has it, else the local
    branch; ``None`` when the spec is not started. Only queries."""
    branch = integration_branch(spec)
    if origin_has_branch(checkout, branch, run):
        return IntegrationBranch(branch, on_origin=True)
    if local_branch_head(checkout, branch, run) is not None:
        return IntegrationBranch(branch, on_origin=False)
    return None


def prune_tracking_ref(
    checkout: str, branch: str, stale: bool, run: Runner, *, dry_run: bool, say: Say
) -> None:
    """Delete ``origin/<branch>`` when *stale* (origin no longer has the branch), else keep it.

    Only this one ref is deleted, never the remote branch and never other stale refs.
    """
    tracking = f"origin/{branch}"
    if dry_run:
        if stale:
            say(f"would prune the stale remote-tracking ref {tracking}")
        return
    if stale:
        run(["git", "-C", checkout, "update-ref", "-d", f"refs/remotes/{tracking}"])
        say(f"pruned the stale remote-tracking ref {tracking}")
    else:
        say(f"origin still has {branch}, so {tracking} was kept")


def fast_forward_main_checkout(checkout: str, run: Runner, *, dry_run: bool, say: Say) -> None:
    """Fast-forward the main checkout's default branch to ``origin``'s, once a PR has merged.

    No local work is lost: a checkout on another branch or with local commits is left alone, and
    git refuses a merge that would overwrite a local change. Whatever stops it is said as a skip
    naming the manual command, never raised, since the cleanup before it has already succeeded.
    A dry run compares against ``origin`` as last fetched.
    """
    default = None
    try:
        default = remote_default_branch(checkout, run)
        say(_fast_forward(checkout, default, run, dry_run))
    except _SkipError as skip:
        say(_skipped(checkout, default, str(skip), dry_run))
    except (RefusalError, subprocess.CalledProcessError, ValueError) as exc:
        say(_skipped(checkout, default, _detail(exc), dry_run))


FAST_FORWARD_HELP = (
    "fast-forward the main checkout's default branch to origin's when it is on that branch with "
    "no local commits and git can merge without overwriting local changes, else say why not and "
    "how to do it by hand"
)
"""The ``--help`` clause for :func:`fast_forward_main_checkout`, which both finish commands run."""


class _SkipError(Exception):
    """A reason not to fast-forward the main checkout."""


def _fast_forward(checkout: str, default: str, run: Runner, dry_run: bool) -> str:
    """Fast-forwards ``default`` unless a check raises :class:`_SkipError`; says what happened."""
    tracking = f"origin/{default}"
    git = ["git", "-C", checkout]
    if not dry_run:
        run([*git, "fetch", "-q", "origin"])
    try:
        branch = run([*git, "symbolic-ref", "--quiet", "--short", "HEAD"]).strip()
    except subprocess.CalledProcessError:
        raise _SkipError("the main checkout is not on a branch") from None
    if branch != default:
        raise _SkipError(f"the main checkout is on {branch}, not {default}")
    ahead = int(run([*git, "rev-list", "--count", f"{tracking}..{default}"]))
    if ahead:
        commits = "commit" if ahead == 1 else "commits"
        raise _SkipError(f"{default} has {ahead} local {commits} {tracking} lacks")
    old = run([*git, "rev-parse", "--short", default]).strip()
    new = run([*git, "rev-parse", "--short", tracking]).strip()
    fetched = " (as last fetched)" if dry_run else ""
    if old == new:
        return f"{default} is already up to date with {tracking}{fetched}"
    if dry_run:
        _skip_if_overwriting(git, default, tracking, run)
        return f"would fast-forward {default} from {old} to {new}{fetched}"
    try:
        run([*git, "merge", "--ff-only", "-q", tracking])
    except subprocess.CalledProcessError as exc:
        raise _SkipError(f"git refused the merge: {_detail(exc)}") from exc
    return f"fast-forwarded {default} from {old} to {new}"


def _skip_if_overwriting(git: list[str], default: str, tracking: str, run: Runner) -> None:
    """Raises the skip git's merge would cause by overwriting a local change, for a dry run."""
    incoming = run([*git, "diff", "--name-only", "-z", default, tracking]).split("\0")
    status = run([*git, "status", "--porcelain", "-z", "--untracked-files=all"])
    clash = sorted(set(incoming) & _changed_paths(status) - {""})
    if clash:
        raise _SkipError(f"git would refuse the merge over local changes to {', '.join(clash)}")


def _changed_paths(status: str) -> set[str]:
    """Every path ``git status --porcelain -z`` lists, a rename's source included."""
    paths: set[str] = set()
    fields = iter(status.split("\0"))
    for entry in fields:
        if not entry:
            continue
        paths.add(entry[3:])
        if entry[0] in "RC":
            paths.add(next(fields, ""))
    return paths


def _detail(exc: Exception) -> str:
    """A failed step's message on one line: git's stderr when it has one."""
    text = getattr(exc, "stderr", None) or str(exc)
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _skipped(checkout: str, default: str | None, reason: str, dry_run: bool) -> str:
    verb = "would skip" if dry_run else "skipped"
    branch = default or "default branch"
    return (
        f"{verb} fast-forwarding the main checkout's {branch}: {reason}."
        f" To update it by hand, run `git -C {checkout} pull --ff-only`"
    )
