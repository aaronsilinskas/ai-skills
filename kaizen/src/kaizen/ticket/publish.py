"""Publish a batch of tickets to GitHub as sub-issues of one parent, with blocking edges.

Reads a JSON manifest and creates one issue per ticket, in manifest order, so a ticket's
blockers must appear before it. Each issue is created as a sub-issue of the parent
(``gh issue create --parent``), so no created ticket is ever left without one, and then gets
GitHub's native "blocked by" edges. The parent and every existing-number blocker are
checked first, so a missing one stops the publish before any issue exists, and every
ticket's title and body must pass the leak check's rules for the project whose main
checkout it runs from (a dry run checks them too). Each issue and edge prints as it is
made, so a failure partway through shows which issues and edges already exist; it then
lists the issues created so far and the ``kaizen issue link`` calls that add the missing
blocked-by edges. Don't rerun after such a failure: a rerun creates every ticket again.
Afterwards every created issue is read back and printed as a table, so a wrong title or
edge shows up immediately.

Tickets cite the spec's glossary and ADR entries, so before creating anything the command
waits for the spec's domain-docs PR (branch ``spec-<parent>-domain-docs``, opened by
``kaizen spec publish``) to merge. A spec with no such PR is not waited for; one closed
unmerged, or still open at ``--wait-timeout``, stops the publish.

Manifest shape (``body_file`` paths are relative to the manifest)::

    {
      "parent": 1160,
      "labels": ["ready-for-agent"],
      "tickets": [
        {"key": "rename", "title": "...", "body_file": "rename.md"},
        {"key": "declare", "title": "...", "body_file": "declare.md",
         "blocked_by": ["rename"]}
      ]
    }

A ``blocked_by`` entry is a key of an earlier ticket in the manifest, or an
existing issue number.

Usage
-----
Run from the project's root::

    kaizen ticket publish path/to/tickets.json
    kaizen ticket publish path/to/tickets.json --dry-run
"""

import argparse
import json
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from kaizen.shared.common import RefusalError, Runner, Say, Subparsers, run_or_refuse
from kaizen.shared.home import Home
from kaizen.shared.issue_graph import (
    IssueRef,
    ResolvedIssue,
    blocked_by_write,
    resolve_issue,
    send_edge,
)
from kaizen.shared.leak import leak_check_text
from kaizen.shared.registry import Project, resolve_current


class ManifestError(RefusalError):
    """The manifest is unreadable or malformed: a missing field, duplicate key, or bad blocker."""

    def __init__(self, check: str) -> None:
        super().__init__(check, "correct the manifest and rerun")


class DomainDocsError(RefusalError):
    """The spec's domain-docs PR was closed unmerged, or did not merge before the timeout."""

    def __init__(self, check: str) -> None:
        super().__init__(
            check, "get the domain-docs PR merged (reopen it if it was closed), then rerun"
        )


class Ticket:
    __slots__ = ("blocked_by", "body_file", "key", "title")

    def __init__(self, key: str, title: str, body_file: Path, blocked_by: list[str | int]) -> None:
        self.key = key
        self.title = title
        self.body_file = body_file
        self.blocked_by = blocked_by


def load_manifest(path: Path) -> tuple[int, list[str], list[Ticket]]:
    """Parse and check *path*; every blocker key must name an earlier ticket."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ManifestError(f"could not read the manifest: {exc}") from exc
    try:
        parent = int(data["parent"])
        labels = list(data.get("labels", []))
        raw_tickets = data["tickets"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ManifestError(f"{path}: needs an integer 'parent' and a 'tickets' list") from exc

    seen: set[str] = set()
    tickets: list[Ticket] = []
    for raw in raw_tickets:
        try:
            key, title, body = raw["key"], raw["title"], raw["body_file"]
        except KeyError as exc:
            raise ManifestError(f"ticket {raw!r} is missing {exc}") from exc
        if not title.strip():
            raise ManifestError(f"ticket {key!r} has a blank title")
        if key in seen:
            raise ManifestError(f"duplicate ticket key {key!r}")
        body_file = path.parent / body
        if not body_file.is_file():
            raise ManifestError(f"ticket {key!r}: body file {body_file} does not exist")
        blocked_by = list(raw.get("blocked_by", []))
        for blocker in blocked_by:
            if isinstance(blocker, str) and blocker not in seen:
                raise ManifestError(
                    f"ticket {key!r} is blocked by {blocker!r}, which is not an earlier ticket"
                )
        seen.add(key)
        tickets.append(Ticket(key, title, body_file, blocked_by))
    return parent, labels, tickets


def wait_for_domain_docs(
    spec: int,
    run: Runner,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
    timeout: float = 900,
    interval: float = 15,
    log: Say = print,
) -> None:
    """Return once spec *spec*'s domain-docs PR has merged, or when it has none."""
    branch = f"spec-{spec}-domain-docs"
    deadline = now() + timeout
    while True:
        state = run_or_refuse(
            [
                "gh",
                "pr",
                "list",
                "--head",
                branch,
                "--state",
                "all",
                "--json",
                "state",
                "--jq",
                '.[0].state // ""',
            ],
            run,
            f"could not look up the domain-docs PR for {branch}",
            "check that `gh pr list` works here, then rerun",
        ).strip()
        if state in ("", "MERGED"):
            return
        if state != "OPEN":
            raise DomainDocsError(f"domain-docs PR for {branch} is {state.lower()}, not merged")
        if now() + interval > deadline:
            raise DomainDocsError(f"domain-docs PR for {branch} did not merge within {timeout:g}s")
        log(f"waiting for the domain-docs PR ({branch}) to merge...")
        sleep(interval)


def publish(
    github: str,
    parent: int,
    labels: list[str],
    tickets: list[Ticket],
    run: Runner,
    say: Say = print,
) -> dict[str, int]:
    """Create every ticket in repo *github* and its edges, saying each as it lands; returns each
    key's number. A missing parent or existing-number blocker refuses before any issue exists.
    A gh failure partway says what was created and how to finish by hand, then re-raises, since
    rerunning would create those tickets again."""
    parent_ref = IssueRef(github, parent)
    resolve_issue(parent_ref, run)
    existing = {
        blocker: resolve_issue(IssueRef(github, blocker), run)
        for ticket in tickets
        for blocker in ticket.blocked_by
        if isinstance(blocker, int)
    }

    created: dict[str, ResolvedIssue] = {}
    for index, ticket in enumerate(tickets):
        try:
            _create(github, parent, labels, ticket, created, existing, run, say)
        except subprocess.CalledProcessError:
            for line in _recovery(parent, tickets[index:], created):
                say(line)
            raise
    return {key: issue.issue.ref.number for key, issue in created.items()}


def _create(
    github: str,
    parent: int,
    labels: list[str],
    ticket: Ticket,
    created: dict[str, ResolvedIssue],
    existing: dict[int, ResolvedIssue],
    run: Runner,
    say: Say,
) -> None:
    """Create *ticket* as a sub-issue of *parent* in one call, then add its blocked-by edges,
    recording it in *created* as soon as it exists."""
    cmd = ["gh", "issue", "create", "--title", ticket.title, "--body-file", str(ticket.body_file)]
    cmd += ["--parent", str(parent)]
    for label in labels:
        cmd += ["--label", label]
    url = run(cmd).strip().splitlines()[-1]
    number = int(url.rsplit("/", 1)[-1])
    say(f"created #{number} {ticket.title}, a sub-issue of #{parent}")
    issue = created[ticket.key] = resolve_issue(IssueRef(github, number), run)
    for b in ticket.blocked_by:
        write = blocked_by_write(issue.issue.ref, created[b] if isinstance(b, str) else existing[b])
        send_edge(write, run)
        say(write.describe(github))


def _recovery(parent: int, remaining: list[Ticket], created: dict[str, ResolvedIssue]) -> list[str]:
    """How to finish a publish that stopped at *remaining*[0], whose blocked-by edges may be
    partly added; every created ticket already has its parent."""
    numbers = {key: issue.issue.ref.number for key, issue in created.items()}

    def blockers(ticket: Ticket) -> list[str]:
        return [str(numbers.get(b, b)) if isinstance(b, str) else str(b) for b in ticket.blocked_by]

    lines = [
        "created so far: " + ", ".join(f"#{n}" for n in numbers.values()),
        "do not rerun `kaizen ticket publish`; it would create these tickets again. "
        "Fix the failure named below, then finish by hand:",
    ]
    stopped, *rest = remaining
    if stopped.key in numbers:
        link = f"kaizen issue link {numbers[stopped.key]}"
        lines.append("  " + link + "".join(f" --blocked-by {b}" for b in blockers(stopped)))
        not_created = rest
    else:
        not_created = remaining
    for ticket in not_created:
        blocked = f" (blocked by {', '.join(blockers(ticket))})" if ticket.blocked_by else ""
        lines.append(f"  not created: {ticket.key} {ticket.title}{blocked}")
    if not_created:
        lines.append(
            f"  create each with `gh issue create --parent {parent}`, then "
            "`kaizen issue link <N> --blocked-by <blocker>`"
        )
    return lines


def read_back(numbers: dict[str, int], run: Runner) -> list[str]:
    """One table row per created issue, read from GitHub: number, title, blocked-by numbers."""
    rows = ["| # | Title | Blocked by |", "|---|---|---|"]
    for number in numbers.values():
        title = run(
            ["gh", "issue", "view", str(number), "--json", "title", "--jq", ".title"]
        ).strip()
        blockers = run(
            [
                "gh",
                "api",
                f"repos/{{owner}}/{{repo}}/issues/{number}/dependencies/blocked_by",
                "--jq",
                '[.[].number] | map("#\\(.)") | join(", ")',
            ]
        ).strip()
        rows.append(f"| #{number} | {title} | {blockers or '-'} |")
    return rows


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "publish",
        help="publish a batch of tickets as sub-issues of their spec",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--dry-run", action="store_true", help="check the manifest and print the plan"
    )
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=900,
        help="seconds to wait for the spec's domain-docs PR to merge (default 900)",
    )
    parser.set_defaults(handler=_command)


def check_text(tickets: list[Ticket], project: Project, home: Home) -> None:
    """Refuses when any ticket's title or body points outside *home*, judged for *project*."""
    texts: dict[str, str] = {}
    for ticket in tickets:
        texts[f"ticket {ticket.key} title"] = ticket.title
        texts[f"ticket {ticket.key} body"] = _read_body(ticket)
    leak_check_text(texts, home, public=project.public)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    parent, labels, tickets = load_manifest(args.manifest)
    project = resolve_current(run, home.registry)
    check_text(tickets, project, home)
    if args.dry_run:
        print(f"parent #{parent}, labels {labels}")
        for ticket in tickets:
            print(f"- {ticket.key}: {ticket.title} (blocked by {ticket.blocked_by or 'none'})")
        return
    wait_for_domain_docs(parent, run, timeout=args.wait_timeout)
    numbers = publish(project.github, parent, labels, tickets, run)
    print("\n".join(read_back(numbers, run)))


def _read_body(ticket: Ticket) -> str:
    try:
        return ticket.body_file.read_text()
    except OSError as exc:
        raise ManifestError(
            f"ticket {ticket.key!r}: could not read {ticket.body_file}: {exc}"
        ) from exc
