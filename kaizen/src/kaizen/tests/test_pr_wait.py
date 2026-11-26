"""Tests for ``kaizen pr wait``: waiting on a PR's checks and the exit code each outcome gives.

gh is replaced by a recording runner and time by a fake clock whose ``sleep`` only advances it,
so no network, GitHub or real waiting is involved.
"""

import json
from pathlib import Path

import pytest

from kaizen.pr.wait import wait
from kaizen.shared.common import RefusalError
from kaizen.tests.ticket_shell import Shell, failed, home_for, proto_pr_argv


class Clock:
    """A monotonic clock that ``sleep`` advances, recording each sleep."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _check(name: str, bucket: str, run: int = 101, job: int = 201) -> dict[str, str]:
    return {
        "name": name,
        "bucket": bucket,
        "workflow": "CI",
        "link": f"https://github.com/o/r/actions/runs/{run}/job/{job}",
    }


def _checks(*checks: dict[str, str]) -> str:
    return json.dumps(list(checks))


def _wait(shell: Shell, clock: Clock, lines: list[str], target: str = "42", **kw) -> int:
    kw.setdefault("home", home_for(Path("/unused/projects")))
    return wait(target, shell, sleep=clock.sleep, clock=clock, say=lines.append, **kw)


def test_wait_exits_0_when_every_check_passes():
    shell = Shell({("pr", "checks"): _checks(_check("check", "pass"), _check("lint", "skipping"))})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines, interval=15) == 0
    assert clock.sleeps == [15]
    assert lines[-1] == "all 2 check(s) passed on PR 42"


def _replies(*replies):
    """A reply that answers each call with the next of *replies*, repeating the last."""
    queue = list(replies)

    def reply(cmd: list[str]) -> str:
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, BaseException):
            raise item
        return item

    return reply


def test_wait_polls_every_interval_until_no_check_is_pending():
    pending = _checks(_check("check", "pending"), _check("lint", "pass"))
    done = _checks(_check("check", "pass"), _check("lint", "pass"))
    shell = Shell({("pr", "checks"): _replies(pending, pending, done)})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines, interval=15) == 0
    assert clock.sleeps == [15, 15, 15]
    assert lines[-1] == "all 2 check(s) passed on PR 42"


def test_a_check_registered_after_the_others_finished_is_waited_for():
    first = _checks(_check("check", "pass"))
    late = _checks(_check("check", "pass"), _check("deploy", "pending"))
    done = _checks(_check("check", "pass"), _check("deploy", "fail"))
    shell = Shell({("pr", "checks"): _replies(first, late, done)})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines, interval=15) == 1
    assert lines[-3] == "1 of 2 check(s) failed on PR 42:"


def test_wait_prints_a_line_each_time_what_it_waits_on_changes():
    a = _checks(_check("check", "pending"), _check("lint", "pending"))
    b = _checks(_check("check", "pass"), _check("lint", "pending"))
    done = _checks(_check("check", "pass"), _check("lint", "pass"))
    shell = Shell({("pr", "checks"): _replies(a, a, b, done)})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines) == 0
    assert lines == [
        "waiting on PR 42: still pending: check, lint",
        "waiting on PR 42: still pending: lint",
        "waiting on PR 42: every check finished; polling once more for late checks",
        "all 2 check(s) passed on PR 42",
    ]


def test_a_poll_with_no_checks_drops_the_finished_set_it_was_confirming():
    finished = _checks(_check("check", "pass"))
    shell = Shell({("pr", "checks"): _replies(finished, NO_CHECKS), ("gh", "api"): "1\n"})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines, interval=15, timeout=15) == 2
    assert lines[-1] == "timed out after 15s on PR 42; no checks reported yet"


def test_a_timeout_while_confirming_a_finished_set_reports_that_set():
    shell = Shell({("pr", "checks"): _checks(_check("check", "pass"))})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines, timeout=0) == 0
    assert lines[-1] == "all 1 check(s) passed on PR 42"


def test_wait_exits_1_naming_each_failed_or_cancelled_check_and_its_logs():
    checks = _checks(
        _check("check", "fail", run=7, job=70),
        _check("lint", "pass"),
        _check("docs", "cancel", run=8, job=80),
    )
    shell = Shell({("pr", "checks"): checks})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines) == 1
    assert lines[-5:] == [
        "2 of 3 check(s) failed on PR 42:",
        "  check (CI) fail: https://github.com/o/r/actions/runs/7/job/70",
        "    logs: gh run view 7 --log-failed",
        "  docs (CI) cancel: https://github.com/o/r/actions/runs/8/job/80",
        "    logs: gh run view 8 --log-failed",
    ]


def test_wait_reports_failures_only_once_every_check_has_finished():
    early = _checks(_check("check", "fail"), _check("lint", "pending"))
    done = _checks(_check("check", "fail"), _check("lint", "pass"))
    shell = Shell({("pr", "checks"): _replies(early, done)})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines, interval=10) == 1
    assert clock.sleeps == [10, 10]


def test_a_failed_check_outside_github_actions_points_at_its_link_alone():
    check = {"name": "ext", "bucket": "fail", "workflow": "", "link": "https://ci.example/1"}
    shell = Shell({("pr", "checks"): _checks(check)})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines) == 1
    assert lines[-1] == "  ext fail: https://ci.example/1"


def test_wait_exits_2_naming_the_pending_checks_once_the_timeout_passes():
    pending = _checks(_check("check", "pending"), _check("lint", "pass"))
    shell = Shell({("pr", "checks"): pending})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines, interval=15, timeout=40) == 2
    assert clock.now <= 40
    assert lines[-1] == "timed out after 40s on PR 42; still pending: check"


NO_CHECKS = failed("gh pr checks", "no checks reported on the 'fix-1-x' branch\n")


def test_wait_exits_0_with_a_note_when_the_repo_has_no_ci_workflows():
    shell = Shell({("pr", "checks"): NO_CHECKS, ("gh", "api"): "0\n"})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines) == 0
    assert clock.sleeps == []
    assert lines[-1] == "no checks reported on PR 42, and the repo has no CI workflows"


def test_wait_keeps_waiting_while_a_repo_with_ci_has_reported_no_checks_yet():
    done = _checks(_check("check", "pass"))
    shell = Shell({("pr", "checks"): _replies(NO_CHECKS, done), ("gh", "api"): "1\n"})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines, interval=5) == 0
    assert clock.sleeps == [5, 5]
    assert lines[-1] == "all 1 check(s) passed on PR 42"


def test_a_timeout_before_any_check_is_reported_says_none_was():
    shell = Shell({("pr", "checks"): NO_CHECKS, ("gh", "api"): "2\n"})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines, interval=5, timeout=10) == 2
    assert lines[-1] == "timed out after 10s on PR 42; no checks reported yet"


def test_a_pr_gh_cannot_find_is_refused():
    missing = failed("gh pr checks", 'no pull requests found for branch "nope"\n')
    shell = Shell({("pr", "checks"): missing})
    clock, lines = Clock(), list[str]()

    with pytest.raises(RefusalError, match="no pull requests found"):
        _wait(shell, clock, lines, target="nope")


BRANCH = "fix-9-wait-for-ci"


def _registry(tmp_path):
    """A registry with one project, ``proto``, and the path of its ticket worktree."""
    projects = tmp_path / "projects"
    projects.mkdir()
    repo = tmp_path / "proto"
    page = f"---\npath: {repo}\ngithub: owner/proto\npublic: false\n---\n# proto\n"
    (projects / "proto.md").write_text(page)
    worktree = repo / ".claude" / "worktrees" / BRANCH
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: elsewhere\n")
    return projects, worktree


def _worktree_shell(checks) -> Shell:
    return Shell(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): f"{BRANCH}\n",
            ("ls-remote",): "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n",
            ("pr", "checks"): checks,
            ("gh", "api"): "0\n",
        }
    )


def test_a_ticket_worktree_waits_on_its_branchs_pr_in_its_projects_repo(tmp_path):
    projects, worktree = _registry(tmp_path)
    shell = _worktree_shell(_checks(_check("check", "pass")))
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines, target=str(worktree), home=home_for(projects)) == 0
    assert shell.ran(*proto_pr_argv("checks", BRANCH))
    assert lines[-1] == f"all 1 check(s) passed on PR {BRANCH}"


def test_a_ticket_worktree_asks_its_projects_repo_whether_it_has_ci(tmp_path):
    projects, worktree = _registry(tmp_path)
    shell = _worktree_shell(NO_CHECKS)
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines, target=str(worktree), home=home_for(projects)) == 0
    assert shell.ran("repos/owner/proto/actions/workflows")


def test_a_directory_that_is_not_a_worktree_is_passed_to_gh_as_a_branch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    shell = Shell({("pr", "checks"): _checks(_check("check", "pass"))})
    clock, lines = Clock(), list[str]()

    assert _wait(shell, clock, lines, target="docs") == 0
    assert shell.ran("gh", "pr", "checks", "docs")
