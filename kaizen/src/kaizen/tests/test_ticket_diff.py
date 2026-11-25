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
MERGE_BASE = "4f1c2d9e8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e"
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
            ("ls-remote", "--heads"): overrides.get("heads", "def456\trefs/heads/spec-117\n"),
            ("for-each-ref",): overrides.get("local", ""),
            ("fetch",): overrides.get("fetch", ""),
            ("merge-base", "--is-ancestor"): overrides.get("ancestor", ""),
            ("merge-base",): overrides.get("merge_base", f"{MERGE_BASE}\n"),
            ("log",): LOG,
            ("diff", "--stat"): STAT,
            ("diff",): DIFF,
            ("status", "--porcelain"): overrides.get("status", ""),
        }
    )


def _mutating(shell: Shell) -> list[list[str]]:
    """Every recorded git call that could change the worktree, its branch or its index."""
    queries = {
        "rev-parse",
        "ls-remote",
        "for-each-ref",
        "fetch",
        "merge-base",
        "log",
        "diff",
        "status",
    }
    return [cmd for cmd in shell.calls if cmd[3] not in queries]


def test_a_spec_tickets_diff_is_against_its_integration_branch(kaizen, capsys):
    shell = _shell()

    assert kaizen(["ticket", "diff", _worktree(SPEC_BRANCH)], run=shell) == 0

    out = capsys.readouterr().out
    assert out.startswith(f"base: origin/spec-117 (merge base {MERGE_BASE})\n")
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


def test_the_diff_of_a_docs_change_is_against_the_default_branch(kaizen, capsys):
    shell = _shell(DOCS_BRANCH)

    assert kaizen(["ticket", "diff", _worktree(DOCS_BRANCH)], run=shell) == 0

    out = capsys.readouterr().out
    assert out.startswith(f"base: origin/main (merge base {MERGE_BASE})\n")
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
    [("--base", f"{MERGE_BASE}\n"), ("--stat", STAT), ("--log", LOG)],
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


def test_a_spec_ticket_whose_integration_branch_is_only_local_diffs_against_it(kaizen, capsys):
    shell = _shell(heads="", local="abc123\n")

    assert kaizen(["ticket", "diff", _worktree(SPEC_BRANCH), "--base"], run=shell) == 0

    assert capsys.readouterr().out == f"{MERGE_BASE}\n"
    assert shell.ran("merge-base", "spec-117", "HEAD")
    assert not shell.ran("fetch")


def test_base_is_the_merge_base_of_the_fetched_base_and_head(kaizen, capsys):
    shell = _shell()

    kaizen(["ticket", "diff", _worktree(SPEC_BRANCH), "--base"], run=shell)

    assert shell.ran("merge-base") == [
        ["git", "-C", _worktree(SPEC_BRANCH), "merge-base", "origin/spec-117", "HEAD"]
    ]


def test_a_base_with_no_common_history_still_prints_the_rest(kaizen, capsys):
    shell = _shell(merge_base=_not_ancestor, ancestor=_not_ancestor)

    assert kaizen(["ticket", "diff", _worktree(SPEC_BRANCH)], run=shell) == 0

    out = capsys.readouterr().out
    assert out.startswith("base: origin/spec-117 (no merge base: HEAD shares no history with it)\n")
    assert f"diff (origin/spec-117...HEAD):\n{DIFF}" in out
