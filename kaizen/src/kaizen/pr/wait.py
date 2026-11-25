"""``kaizen pr wait``: block until a PR's checks finish, then exit by their outcome."""

import argparse
import json
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from kaizen.shared.command_records import HomeCommand
from kaizen.shared.common import RefusalError, Runner, Say, Subparsers
from kaizen.shared.home import Home
from kaizen.shared.ticket_worktree import resolve_ticket_worktree

DEFAULT_TIMEOUT = 540
"""Seconds to wait in all: inside the 10-minute cap of a foreground agent shell call."""

DEFAULT_INTERVAL = 15
"""Seconds between polls."""

PENDING_BUCKET = "pending"
"""The ``gh pr checks`` bucket of a check still running or queued."""

FAILED_BUCKETS = ("fail", "cancel")
"""The ``gh pr checks`` buckets that make the wait fail; ``pass`` and ``skipping`` don't."""


class _Check(TypedDict):
    """The fields of ``gh pr checks --json name,bucket,workflow,link``."""

    name: str
    bucket: str
    """``pass``, ``fail``, ``pending``, ``skipping`` or ``cancel``."""
    workflow: str
    """The GitHub Actions workflow's name; empty for a check from outside Actions."""
    link: str


@dataclass(frozen=True)
class _ChecksTarget:
    ref: str
    """What ``gh pr checks`` is given: a PR number, URL or branch."""
    github: str | None
    """The ``owner/repo`` it lives in; ``None`` leaves gh to infer it from the current directory."""


def wait(
    pr: str,
    run: Runner,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    interval: float = DEFAULT_INTERVAL,
    home: Home,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    say: Say = print,
) -> int:
    """Polls the checks of *pr* every *interval* seconds until none is pending.

    A finished set counts once two polls in a row report the same checks, or once the timeout
    passes before the second poll; a workflow can register a check after the earlier ones
    finish.

    Returns the exit code: 0 when every check passed or was skipped, or when none is reported
    and the repo has no GitHub Actions workflows; 1 when any failed or was cancelled; 2 when
    *timeout* seconds pass first. Refuses a PR whose checks gh can't read.
    """
    target = _resolve(pr, run, home.registry)
    deadline = clock() + timeout
    has_ci: bool | None = None
    said = ""
    # The last poll's checks, when none of them was pending; the next poll confirms them.
    finished: list[_Check] | None = None
    while True:
        checks = _checks(target, run)
        if checks is None:
            if has_ci is None:
                has_ci = _workflow_count(target, run) > 0
            if not has_ci:
                say(f"no checks reported on PR {target.ref}, and the repo has no CI workflows")
                return 0
            finished, waiting = None, "no checks reported yet"
        else:
            pending = [check["name"] for check in checks if check["bucket"] == PENDING_BUCKET]
            if pending:
                finished, waiting = None, f"still pending: {', '.join(pending)}"
            elif finished is not None and _names(finished) == _names(checks):
                return _report(checks, target, say)
            else:
                finished, waiting = (
                    checks,
                    "every check finished; polling once more for late checks",
                )
        remaining = deadline - clock()
        if remaining <= 0:
            if finished is not None:
                return _report(finished, target, say)
            say(f"timed out after {timeout:g}s on PR {target.ref}; {waiting}")
            return 2
        if waiting != said:
            say(f"waiting on PR {target.ref}: {waiting}")
            said = waiting
        sleep(min(interval, remaining))


def _names(checks: list[_Check]) -> list[str]:
    return sorted(check["name"] for check in checks)


def _report(checks: list[_Check], target: _ChecksTarget, say: Say) -> int:
    """Prints the outcome of a finished set of checks and returns its exit code."""
    failed = [check for check in checks if check["bucket"] in FAILED_BUCKETS]
    if failed:
        say(f"{len(failed)} of {len(checks)} check(s) failed on PR {target.ref}:")
        for check in failed:
            _say_failure(check, say)
        return 1
    say(f"all {len(checks)} check(s) passed on PR {target.ref}")
    return 0


def _resolve(pr: str, run: Runner, projects_dir: Path) -> _ChecksTarget:
    """A ticket worktree's path (a directory holding ``.git``) names its branch's PR in its
    project's repo.

    Anything else goes to gh as it is, in the repo of the current directory.
    """
    path = Path(pr).expanduser()
    if (path / ".git").exists():
        ticket = resolve_ticket_worktree(path, run, projects_dir)
        return _ChecksTarget(ticket.branch, ticket.project.github)
    return _ChecksTarget(pr, None)


def _checks(target: _ChecksTarget, run: Runner) -> list[_Check] | None:
    """The PR's checks; ``None`` while GitHub reports none for it."""
    repo = ["-R", target.github] if target.github else []
    fields = "name,bucket,workflow,link"
    try:
        out = run(["gh", *repo, "pr", "checks", target.ref, "--json", fields])
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        if "no checks reported" in stderr:
            return None
        raise RefusalError(
            f"could not read the checks of PR {target.ref}: {stderr}",
            "pass an open PR's number or branch, or a ticket worktree whose branch has a PR",
        ) from exc
    checks: list[_Check] = json.loads(out)
    return checks


def _workflow_count(target: _ChecksTarget, run: Runner) -> int:
    """How many GitHub Actions workflows the PR's repo defines."""
    repo = target.github or "{owner}/{repo}"
    out = run(["gh", "api", f"repos/{repo}/actions/workflows", "--jq", ".total_count"])
    return int(out.strip())


def _say_failure(check: _Check, say: Say) -> None:
    workflow = f" ({check['workflow']})" if check["workflow"] else ""
    say(f"  {check['name']}{workflow} {check['bucket']}: {check['link']}")
    actions_run = re.search(r"/actions/runs/(\d+)", check["link"])
    if actions_run:
        say(f"    logs: gh run view {actions_run.group(1)} --log-failed")


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "wait",
        help="block until a PR's checks finish; exit 0 when they pass, 1 when any fails",
        description=(
            "Poll the PR's checks (gh pr checks) until none is pending, then exit 0 when every "
            "check passed or was skipped, or 1 when any failed or was cancelled, printing each "
            "failing check's link and a `gh run view <run> --log-failed` command for its logs. "
            "While no check is reported yet it keeps waiting, unless the repo has no GitHub "
            "Actions workflows, when it exits 0 with a note. Exits 2 when --timeout passes "
            "first, naming the checks still pending. A refusal (such as a PR gh can't find) "
            "exits 1 with refused: on stderr. Prints a line each time what it waits on changes. "
            f"The default timeout of {DEFAULT_TIMEOUT}s fits inside a 10-minute foreground "
            "agent shell call; raise the call's own timeout above --timeout, or run it in the "
            "background."
        ),
    )
    parser.add_argument(
        "pr",
        help="a PR number, URL or branch in the current directory's repo, or the path of a "
        "ticket worktree from `kaizen ticket start` (its branch's PR in its project's repo)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"seconds to wait in all (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"seconds between polls (default: {DEFAULT_INTERVAL})",
    )
    parser.set_defaults(command=HomeCommand(_command))


def _command(args: argparse.Namespace, run: Runner, home: Home) -> int:
    return wait(args.pr, run, timeout=args.timeout, home=home, interval=args.interval)
