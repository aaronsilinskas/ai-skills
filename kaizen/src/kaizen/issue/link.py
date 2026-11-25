"""``kaizen issue link``: add sub-issue and blocked-by edges, in one repo or across the home's
repos."""

import argparse

from kaizen.shared.common import RefusalError, Runner, Say, Subparsers
from kaizen.shared.home import Home
from kaizen.shared.issue_graph import (
    EdgeWrite,
    add_edge,
    blocked_by_write,
    blockers_of,
    parent_of,
    parse_ref,
    resolve_issue,
    sub_issue_write,
)
from kaizen.shared.registry import home_repos


def link(
    child_text: str,
    parent_text: str | None,
    blocker_texts: list[str],
    run: Runner,
    *,
    dry_run: bool = False,
    home: Home,
    say: Say = print,
) -> None:
    """Adds the edges that are not already present, after resolving every reference and reading
    the child's current parent and blockers; refuses before any write when a check fails."""
    if parent_text is None and not blocker_texts:
        raise RefusalError(
            "nothing to link", "name the parent with --parent, blockers with --blocked-by, or both"
        )
    child_ref = parse_ref(child_text, run, home.registry)
    parent_ref = parse_ref(parent_text, run, home.registry) if parent_text else None
    blocker_refs = list(dict.fromkeys(parse_ref(t, run, home.registry) for t in blocker_texts))
    for ref in [parent_ref, *blocker_refs]:
        if ref == child_ref:
            raise RefusalError(
                f"{child_ref} cannot be linked to itself",
                "name a different issue as its parent or blocker",
            )

    child = resolve_issue(child_ref, run)
    parent = resolve_issue(parent_ref, run) if parent_ref else None
    blockers = [resolve_issue(ref, run) for ref in blocker_refs]
    current_parent = parent_of(child_ref, run) if parent else None
    present_blockers = {b.ref for b in blockers_of(child_ref, run)} if blockers else set()

    planned: list[tuple[EdgeWrite, str]] = []
    if parent:
        write = sub_issue_write(parent.issue.ref, child)
        if current_parent is None:
            planned.append((write, ""))
        elif current_parent.ref == parent.issue.ref:
            say(f"already present: {write.describe(child_ref.github)}")
        elif current_parent.ref.github.lower() not in home_repos(home.registry):
            raise RefusalError(
                f"{child_ref} already has parent an issue outside this home",
                "to move it, remove its parent in GitHub first, then rerun",
            )
        else:
            raise RefusalError(
                f"{child_ref} already has parent {current_parent.ref} ({current_parent.title})",
                f"to move it, remove it from {current_parent.ref} in GitHub first, then rerun",
            )
    for blocker in blockers:
        write = blocked_by_write(child_ref, blocker)
        note = " (closed)" if blocker.issue.state == "closed" else ""
        if blocker.issue.ref in present_blockers:
            say(f"already present: {write.describe(child_ref.github)}{note}")
        else:
            planned.append((write, note))

    for write, note in planned:
        edge = write.describe(child_ref.github) + note
        if dry_run:
            say(f"would add: {edge} ({write})")
        else:
            add_edge(write, run)
            say(f"added: {edge}")


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "link",
        help="add an issue's parent and blocked-by edges, in one repo or across the home's repos",
        description=(
            "Make CHILD a sub-issue of --parent and blocked by each --blocked-by, looking up "
            "the database ids GitHub wants. Every reference is resolved and the child's current "
            "parent and blockers read before any write, so a missing issue, a self-link or a "
            "child that already has a different parent refuses with nothing written. An edge "
            "already present is skipped and each edge added prints one line, so a rerun is "
            "safe. A closed blocker is allowed and noted."
        ),
    )
    ref_help = (
        "N or #N in the current project (its main checkout or a ticket worktree), <project>#N, "
        "or owner/repo#N in the home"
    )
    parser.add_argument("child", help=f"the issue to link: {ref_help}")
    parser.add_argument("--parent", help=f"the issue CHILD becomes a sub-issue of: {ref_help}")
    parser.add_argument(
        "--blocked-by",
        action="append",
        default=[],
        metavar="REF",
        help=f"an issue that blocks CHILD; repeat for more: {ref_help}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the edges and the ids it would send, and write nothing",
    )
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    link(args.child, args.parent, args.blocked_by, run, home=home, dry_run=args.dry_run)
