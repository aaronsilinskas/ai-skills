"""Waiting on a PR until it is finished: its checks passed (or the repo has none) and it merges
cleanly, or it merged. ``kaizen pr wait`` and both ship commands wait through it."""

import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple, TypedDict

from kaizen.shared.common import RefusalError, Runner, Say

DEFAULT_TIMEOUT = 540
"""Seconds to wait in all: inside the 10-minute cap of a foreground agent shell call."""

SHIP_TIMEOUT = 480
"""Seconds a ship waits, leaving a minute of that cap for its push and PR steps."""

DEFAULT_INTERVAL = 15
"""Seconds between polls."""

TIMED_OUT = 2
"""The exit code of a wait whose timeout passed first."""

PENDING_BUCKET = "pending"
"""The ``gh pr checks`` bucket of a check still running or queued."""

FAILED_BUCKETS = ("fail", "cancel")
"""The ``gh pr checks`` buckets that make the wait fail; ``pass`` and ``skipping`` don't."""

VIEW_FIELDS = "state,mergeable,baseRefName"
"""The ``gh pr view --json`` fields each poll reads."""


class _Check(TypedDict):
    """The fields of ``gh pr checks --json name,bucket,workflow,link``."""

    name: str
    bucket: str
    """``pass``, ``fail``, ``pending``, ``skipping`` or ``cancel``."""
    workflow: str
    """The GitHub Actions workflow's name; empty for a check from outside Actions."""
    link: str


class _View(TypedDict):
    """The fields of ``gh pr view --json state,mergeable,baseRefName``."""

    state: str
    """``OPEN``, ``CLOSED`` (without merging) or ``MERGED``."""
    mergeable: str
    """``MERGEABLE``, ``CONFLICTING``, or ``UNKNOWN`` while GitHub works it out."""
    baseRefName: str


@dataclass(frozen=True)
class ChecksTarget:
    ref: str
    """What gh is given: a PR number, URL or branch."""
    github: str | None
    """The ``owner/repo`` it lives in; ``None`` leaves gh to infer it from the current directory."""


class Waited(NamedTuple):
    code: int
    """0 when the PR is finished, 1 when a check failed or the PR can't merge, ``TIMED_OUT``."""
    reason: str
    """The line saying why, without the PR's checks listed."""


def wait(
    target: ChecksTarget,
    run: Runner,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    interval: float = DEFAULT_INTERVAL,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    say: Say = print,
) -> Waited:
    """Polls *target* every *interval* seconds until it is finished, fails, or *timeout* passes.

    Each poll reads the PR first: a merged PR is finished, and a closed or conflicting one fails
    at once, since GitHub runs no ``pull_request`` workflow on a PR that conflicts with its base.
    While GitHub hasn't worked out whether it merges cleanly, the wait goes on.

    A finished set of checks counts once two polls in a row report the same checks, or once the
    timeout passes before the second poll; a workflow can register a check after the earlier
    ones finish. No checks at all counts as passing only when the repo has no GitHub Actions
    workflows. Refuses a PR gh can't read.
    """
    deadline = clock() + timeout
    has_ci: bool | None = None
    said = ""
    # The last poll's checks, when none of them was pending; the next poll confirms them.
    finished: list[_Check] | None = None
    while True:
        view = _view(target, run)
        if view["state"] == "MERGED":
            return _said(Waited(0, f"PR {target.ref} merged"), say)
        if view["state"] == "CLOSED":
            return _said(Waited(1, f"PR {target.ref} was closed without merging"), say)
        if view["mergeable"] == "CONFLICTING":
            base = view["baseRefName"]
            reason = f"PR {target.ref} conflicts with {base} (merge origin/{base} into its branch)"
            return _said(Waited(1, reason), say)
        known = view["mergeable"] == "MERGEABLE"
        checks = _checks(target, run)
        if checks is None:
            if has_ci is None:
                has_ci = _workflow_count(target, run) > 0
            if not has_ci and known:
                reason = f"no checks reported on PR {target.ref}, and the repo has no CI workflows"
                return _said(Waited(0, reason), say)
            finished, waiting = None, "no checks reported yet" if has_ci else ""
        else:
            pending = [check["name"] for check in checks if check["bucket"] == PENDING_BUCKET]
            if pending:
                finished, waiting = None, f"still pending: {', '.join(pending)}"
            elif finished is not None and _names(finished) == _names(checks) and known:
                return _report(checks, target, say)
            else:
                finished, waiting = (
                    checks,
                    "every check finished; polling once more for late checks",
                )
        if not known:
            unknown = "GitHub is still working out whether it merges cleanly"
            waiting = f"{waiting}; {unknown}" if waiting else unknown
        remaining = deadline - clock()
        if remaining <= 0:
            if finished is not None and known:
                return _report(finished, target, say)
            reason = f"timed out after {timeout:g}s on PR {target.ref}; {waiting}"
            return _said(Waited(TIMED_OUT, reason), say)
        if waiting != said:
            say(f"waiting on PR {target.ref}: {waiting}")
            said = waiting
        sleep(min(interval, remaining))


def _on_stderr(line: str) -> None:
    print(line, file=sys.stderr)


def wait_until_finished(
    target: ChecksTarget,
    run: Runner,
    *,
    wait_again: str,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    say: Say = print,
    warn: Say = _on_stderr,
) -> int:
    """A ship's last step: waits on the PR it just pushed, and returns the exit code.

    Short of finished, prints ``not finished:`` with the reason to *warn* (stderr), and how to
    go on: fix and ship again, or run *wait_again* after a timeout.
    """
    waited = wait(target, run, timeout=SHIP_TIMEOUT, sleep=sleep, clock=clock, say=say)
    if waited.code == 0:
        return 0
    if waited.code == TIMED_OUT:
        then = f"run `{wait_again}` until it exits 0"
    else:
        then = "fix it, commit and ship again"
    warn(f"not finished: {waited.reason}; {then}")
    return waited.code


def _said(waited: Waited, say: Say) -> Waited:
    say(waited.reason)
    return waited


def _names(checks: list[_Check]) -> list[str]:
    return sorted(check["name"] for check in checks)


def _report(checks: list[_Check], target: ChecksTarget, say: Say) -> Waited:
    """Prints the outcome of a finished set of checks and returns it."""
    failed = [check for check in checks if check["bucket"] in FAILED_BUCKETS]
    if failed:
        reason = f"{len(failed)} of {len(checks)} check(s) failed on PR {target.ref}"
        say(f"{reason}:")
        for check in failed:
            _say_failure(check, say)
        return Waited(1, reason)
    return _said(Waited(0, f"all {len(checks)} check(s) passed on PR {target.ref}"), say)


def _repo(target: ChecksTarget) -> list[str]:
    return ["-R", target.github] if target.github else []


def _view(target: ChecksTarget, run: Runner) -> _View:
    """The PR's state and whether it merges cleanly; refuses a PR gh can't find."""
    try:
        out = run(["gh", *_repo(target), "pr", "view", target.ref, "--json", VIEW_FIELDS])
    except subprocess.CalledProcessError as exc:
        raise _unreadable(target, exc) from exc
    view: _View = json.loads(out)
    return view


def _checks(target: ChecksTarget, run: Runner) -> list[_Check] | None:
    """The PR's checks; ``None`` while GitHub reports none for it."""
    fields = "name,bucket,workflow,link"
    try:
        out = run(["gh", *_repo(target), "pr", "checks", target.ref, "--json", fields])
    except subprocess.CalledProcessError as exc:
        if "no checks reported" in (exc.stderr or ""):
            return None
        raise _unreadable(target, exc) from exc
    checks: list[_Check] = json.loads(out)
    return checks


def _unreadable(target: ChecksTarget, exc: subprocess.CalledProcessError) -> RefusalError:
    return RefusalError(
        f"could not read PR {target.ref}: {(exc.stderr or '').strip()}",
        "pass an open PR's number or branch, or a ticket worktree whose branch has a PR",
    )


def _workflow_count(target: ChecksTarget, run: Runner) -> int:
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
