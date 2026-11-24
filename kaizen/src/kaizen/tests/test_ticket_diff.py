"""Tests for ``kaizen ticket diff``: a ticket's commits, stat and diff against its resolved base.

The CLI runs from a fixture home, so each ticket worktree sits under ``relay``'s worktree root;
git is replaced by a recording runner, so no repo or network is touched.
"""

import subprocess

import pytest

from kaizen.tests.ticket_shell import RELAY, Reply, Shell, failed

SPEC_BRANCH = "spec-117-fix-122-kaizen-ticket-diff"
DOCS_BRANCH = "docs-tidy-guides"
LOG = "abc1234 Add kaizen ticket diff\n"
STAT = " kaizen/ticket/diff.py | 40 ++++++++\n 1 file changed, 40 insertions(+)\n"
DIFF = "diff --git a/kaizen/ticket/diff.py b/kaizen/ticket/diff.py\n+new line\n"


def _worktree(branch: str) -> str:
    return str(RELAY / ".claude" / "worktrees" / branch)


def _not_ancestor(cmd: list[str]) -> str:
    raise subprocess.CalledProcessError(1, cmd, output="", stderr="")


def _shell(branch: str = SPEC_BRANCH, **overrides: Reply) -> Shell:
    return Shell(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): f"{branch}\n",
            ("ls-remote", "--symref"): "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n",
            ("fetch",): overrides.get("fetch", ""),
            ("merge-base", "--is-ancestor"): overrides.get("ancestor", ""),
            ("log",): LOG,
            ("diff", "--stat"): STAT,
            ("diff",): DIFF,
            ("status", "--porcelain"): overrides.get("status", ""),
        }
    )


def _mutating(shell: Shell) -> list[list[str]]:
    """Every recorded git call that could change the worktree, its branch or its index."""
    queries = {"rev-parse", "ls-remote", "fetch", "merge-base", "log", "diff", "status"}
    return [cmd for cmd in shell.calls if cmd[3] not in queries]


def test_a_spec_tickets_diff_is_against_its_integration_branch(kaizen, capsys):
    shell = _shell()

    assert kaizen(["ticket", "diff", _worktree(SPEC_BRANCH)], run=shell) == 0

    out = capsys.readouterr().out
    assert out.startswith("base: origin/spec-117\n")
    assert "origin/spec-117 is an ancestor of HEAD\n" in out
    assert f"commits ahead (origin/spec-117..HEAD):\n{LOG}" in out
    assert f"stat (origin/spec-117...HEAD):\n{STAT}" in out
    assert f"diff (origin/spec-117...HEAD):\n{DIFF}" in out
    assert shell.ran("log", "--oneline", "origin/spec-117..HEAD")
    assert shell.ran("diff", "origin/spec-117...HEAD")
    assert _mutating(shell) == []


def test_only_the_base_ref_is_fetched(kaizen, capsys):
    shell = _shell()

    kaizen(["ticket", "diff", _worktree(SPEC_BRANCH)], run=shell)

    refspec = "+refs/heads/spec-117:refs/remotes/origin/spec-117"
    assert shell.ran("fetch") == [
        ["git", "-C", _worktree(SPEC_BRANCH), "fetch", "-q", "origin", refspec]
    ]


def test_a_docs_tickets_diff_is_against_the_default_branch(kaizen, capsys):
    shell = _shell(DOCS_BRANCH)

    assert kaizen(["ticket", "diff", _worktree(DOCS_BRANCH)], run=shell) == 0

    out = capsys.readouterr().out
    assert out.startswith("base: origin/main\n")
    assert shell.ran("diff", "origin/main...HEAD")


def test_a_base_that_is_not_an_ancestor_is_named_with_the_merge_that_fixes_it(kaizen, capsys):
    shell = _shell(ancestor=_not_ancestor)

    assert kaizen(["ticket", "diff", _worktree(SPEC_BRANCH)], run=shell) == 0

    out = capsys.readouterr().out
    assert "origin/spec-117 is not an ancestor of HEAD" in out
    assert f"fix: merge the base into the ticket branch: `git -C {_worktree(SPEC_BRANCH)}" in out
    assert "merge origin/spec-117`" in out
    assert _mutating(shell) == []


def test_uncommitted_changes_are_noted_and_left_in_place(kaizen, capsys):
    shell = _shell(status=" M kaizen/ticket/diff.py\n?? notes.txt\n")

    assert kaizen(["ticket", "diff", _worktree(SPEC_BRANCH)], run=shell) == 0

    out = capsys.readouterr().out
    assert out.endswith(
        "has uncommitted changes, which the commits and diff above leave out:\n"
        " M kaizen/ticket/diff.py\n?? notes.txt\n"
    )
    assert _mutating(shell) == []


def test_a_clean_worktree_gets_no_uncommitted_note(kaizen, capsys):
    kaizen(["ticket", "diff", _worktree(SPEC_BRANCH)], run=_shell())

    assert "uncommitted" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("flag", "expected"),
    [("--base", "origin/spec-117\n"), ("--stat", STAT), ("--log", LOG)],
    ids=["base", "stat", "log"],
)
def test_a_section_flag_prints_only_that_section(kaizen, capsys, flag, expected):
    assert kaizen(["ticket", "diff", _worktree(SPEC_BRANCH), flag], run=_shell()) == 0

    assert capsys.readouterr().out == expected


def test_section_flags_cannot_be_combined(kaizen):
    with pytest.raises(SystemExit):
        kaizen(["ticket", "diff", _worktree(SPEC_BRANCH), "--base", "--stat"], run=_shell())


def test_a_base_origin_lacks_refuses_naming_the_branch(kaizen, capsys):
    shell = _shell(fetch=failed("git fetch", "fatal: couldn't find remote ref spec-117"))

    assert kaizen(["ticket", "diff", _worktree(SPEC_BRANCH)], run=shell) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused: could not fetch spec-117 from origin")
    assert "run `kaizen spec start 117`" in err


def test_a_failed_ancestry_check_is_an_error_not_a_verdict(kaizen, capsys):
    def broken(cmd: list[str]) -> str:
        raise subprocess.CalledProcessError(128, cmd, output="", stderr="fatal: bad object")

    assert kaizen(["ticket", "diff", _worktree(SPEC_BRANCH)], run=_shell(ancestor=broken)) == 1

    captured = capsys.readouterr()
    assert captured.err.startswith("error: git -C")
    assert "is not an ancestor" not in captured.out
