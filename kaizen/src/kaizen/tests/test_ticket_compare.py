"""Tests for ``kaizen ticket compare``: a command run on the ticket and on its base, with a verdict.

The CLI runs from a fixture home, so each ticket worktree sits under ``relay``'s worktree root;
git and the compared command are replaced by a recording runner, so nothing really runs or waits.
"""

import subprocess
from collections.abc import Iterator

import pytest

from kaizen.shared.command import verdict
from kaizen.tests.conftest import Kaizen
from kaizen.tests.ticket_shell import RELAY, Reply, Shell, failed

SPEC_BRANCH = "spec-117-fix-123-kaizen-ticket-compare"
COMMAND = ["uv", "run", "pytest", "-q", "kaizen/tests/test_x.py"]


def _worktree(branch: str = SPEC_BRANCH) -> str:
    return str(RELAY / ".claude" / "worktrees" / branch)


def _exits(*codes: int) -> Iterator[int]:
    return iter(codes)


def _command_runs(ticket: Iterator[int], base: Iterator[int]) -> Reply:
    """Answers each run of the compared command with the next exit code of its side."""

    def answer(cmd: list[str]) -> str:
        script = cmd[-1]
        side, codes = ("ticket", ticket) if f"cd {_worktree()} " in script else ("base", base)
        code = next(codes)
        output = f"{side} output line 1\n{side} output line 2\n"
        if code:
            raise subprocess.CalledProcessError(code, cmd, output=output, stderr="")
        return output

    return answer


def _shell(ticket: Iterator[int], base: Iterator[int], **overrides: Reply) -> Shell:
    return Shell(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): f"{SPEC_BRANCH}\n",
            ("ls-remote", "--symref"): "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n",
            ("fetch",): overrides.get("fetch", ""),
            ("status", "--porcelain"): overrides.get("status", ""),
            ("worktree", "add"): overrides.get("add", ""),
            ("sh", "-c"): overrides.get("runs", _command_runs(ticket, base)),
        }
    )


def _compare(kaizen: Kaizen, shell: Shell, *extra: str) -> int:
    return kaizen(["ticket", "compare", _worktree(), *extra, "--", *COMMAND], shell)


P, F = True, False  # a run that passed, a run that failed


@pytest.mark.parametrize(
    ("ticket", "base", "expected"),
    [
        ((P, P, P), (P, P, P), "passes"),
        ((P, P, P), (F, F, F), "passes"),
        ((P, P, P), (F, P, F), "passes"),
        ((F, F, F), (P, P, P), "caused"),
        ((F, F, F), (F, F, F), "pre-existing"),
        ((F, F, F), (F, P, P), "flaky"),
        ((F, P, F), (P, P, P), "flaky"),
        ((P, F, P), (F, F, F), "flaky"),
        ((F,), (P,), "caused"),
        ((F,), (F,), "pre-existing"),
    ],
)
def test_each_mix_of_run_outcomes_gets_its_verdict(ticket, base, expected):
    assert verdict(ticket, base) == expected


def test_each_run_is_printed_with_its_side_number_and_exit_code(kaizen, capsys):
    shell = _shell(_exits(0, 1, 0), _exits(0, 0, 0))

    assert _compare(kaizen, shell) == 0

    out = capsys.readouterr().out
    for line in [
        "ticket run 1: exit 0",
        "ticket run 2: exit 1",
        "ticket run 3: exit 0",
        "base run 1: exit 0",
        "base run 3: exit 0",
    ]:
        assert f"{line}\n" in out


def test_a_failing_runs_output_tail_is_printed_and_a_passing_runs_is_not(kaizen, capsys):
    _compare(kaizen, _shell(_exits(1, 0, 0), _exits(0, 0, 0)))

    out = capsys.readouterr().out
    assert "ticket run 1: exit 1\n  ticket output line 1\n  ticket output line 2\n" in out
    assert "base output" not in out


def _scratch(shell: Shell) -> str:
    [add] = shell.ran("worktree", "add", "--detach")
    return add[-2]


def _run_roots(shell: Shell) -> list[str]:
    """The directory each run of the compared command started from."""
    return [cmd[-1].removeprefix("(cd ").split(" && ")[0] for cmd in shell.ran("sh", "-c")]


def test_the_ticket_runs_start_from_the_ticket_worktree_root(kaizen, capsys):
    shell = _shell(_exits(0, 0, 0), _exits(0, 0, 0))

    _compare(kaizen, shell)

    assert _run_roots(shell)[:3] == [_worktree()] * 3


def test_the_base_runs_start_from_the_scratch_worktree_root(kaizen, capsys):
    shell = _shell(_exits(0, 0, 0), _exits(0, 0, 0))

    _compare(kaizen, shell)

    assert _run_roots(shell)[3:] == [_scratch(shell)] * 3


def test_the_scratch_worktree_is_detached_at_the_base_outside_the_project(kaizen, capsys):
    shell = _shell(_exits(0, 0, 0), _exits(0, 0, 0))

    _compare(kaizen, shell)

    [add] = shell.ran("worktree", "add", "--detach")
    assert add[-1] == "origin/spec-117"
    assert not add[-2].startswith(str(RELAY))


def test_the_scratch_worktree_is_removed_after_the_runs(kaizen, capsys):
    shell = _shell(_exits(1, 1, 1), _exits(1, 1, 1))

    _compare(kaizen, shell)

    assert shell.calls[-1][3:] == ["worktree", "remove", "--force", _scratch(shell)]


@pytest.mark.parametrize(
    ("ticket", "base", "expected"),
    [
        ((0, 0, 0), (1, 1, 1), "passes"),
        ((2, 1, 1), (0, 0, 0), "caused"),
        ((1, 1, 1), (1, 1, 1), "pre-existing"),
        ((1, 0, 1), (0, 0, 0), "flaky"),
    ],
)
def test_every_verdict_is_printed_last_and_exits_zero(kaizen, capsys, ticket, base, expected):
    assert _compare(kaizen, _shell(_exits(*ticket), _exits(*base))) == 0

    assert capsys.readouterr().out.splitlines()[-1].startswith(f"verdict: {expected}")


def test_runs_sets_how_many_times_each_side_runs(kaizen, capsys):
    shell = _shell(_exits(0), _exits(0))

    assert _compare(kaizen, shell, "--runs", "1") == 0

    assert len(shell.ran("sh", "-c")) == 2


def test_the_scratch_worktree_is_removed_when_the_runs_are_interrupted(kaizen, capsys):
    shell = _shell(_exits(), _exits(), runs=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        _compare(kaizen, shell)

    assert shell.ran("worktree", "remove", "--force")


def test_uncommitted_ticket_changes_are_noted_and_run(kaizen, capsys):
    shell = _shell(_exits(0, 0, 0), _exits(0, 0, 0), status=" M scripts/x.py\n")

    assert _compare(kaizen, shell) == 0

    out = capsys.readouterr().out
    assert "has uncommitted changes, which the ticket runs include:\n M scripts/x.py\n" in out


def test_a_clean_ticket_gets_no_uncommitted_note(kaizen, capsys):
    _compare(kaizen, _shell(_exits(0, 0, 0), _exits(0, 0, 0)))

    assert "uncommitted" not in capsys.readouterr().out


def test_a_dry_run_prints_the_base_and_commands_and_adds_no_worktree(kaizen, capsys):
    shell = _shell(_exits(), _exits())

    assert _compare(kaizen, shell, "--dry-run") == 0

    out = capsys.readouterr().out
    assert out.startswith("base: origin/spec-117\n")
    assert f"would run 3 times in {_worktree()}: uv run pytest -q kaizen/tests/test_x.py" in out
    assert "would run 3 times in a scratch worktree at origin/spec-117" in out
    assert shell.ran("worktree") == []
    assert shell.ran("sh", "-c") == []


def test_a_base_origin_lacks_refuses_and_runs_nothing(kaizen, capsys):
    shell = _shell(_exits(), _exits(), fetch=failed("git fetch", "fatal: couldn't find remote ref"))

    assert _compare(kaizen, shell) == 1

    assert capsys.readouterr().err.startswith("refused: could not fetch spec-117")
    assert shell.ran("worktree") == []


def test_a_failed_worktree_add_is_an_error_not_a_verdict(kaizen, capsys):
    shell = _shell(_exits(), _exits(), add=failed("git worktree add", "fatal: invalid reference"))

    assert _compare(kaizen, shell) == 1

    captured = capsys.readouterr()
    assert captured.err.startswith("error: git worktree add failed")
    assert "verdict" not in captured.out


def test_runs_below_one_is_rejected(kaizen):
    with pytest.raises(SystemExit):
        _compare(kaizen, _shell(_exits(), _exits()), "--runs", "0")
