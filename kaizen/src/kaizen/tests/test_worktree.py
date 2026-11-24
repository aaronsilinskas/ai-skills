"""Tests for ``list_worktrees``, the one parser of ``git worktree list --porcelain``."""

from kaizen.shared.worktree import Worktree, list_worktrees

PORCELAIN = """\
worktree /p/proto
HEAD 1111111
branch refs/heads/main

worktree /p/proto/.claude/worktrees/fix-7-add-greeting
HEAD 2222222
branch refs/heads/fix-7-add-greeting

"""


def _replying(out: str, ran: list[list[str]] | None = None):
    def run(cmd: list[str]) -> str:
        if ran is not None:
            ran.append(cmd)
        return out

    return run


def test_asks_git_for_the_porcelain_listing_of_the_checkout():
    ran: list[list[str]] = []

    list_worktrees("/p/proto", _replying(PORCELAIN, ran))

    assert ran == [["git", "-C", "/p/proto", "worktree", "list", "--porcelain"]]


def test_lists_each_worktree_path_with_its_branch():
    assert list_worktrees("/p/proto", _replying(PORCELAIN)) == [
        Worktree("/p/proto", "main", locked=False),
        Worktree(
            "/p/proto/.claude/worktrees/fix-7-add-greeting", "fix-7-add-greeting", locked=False
        ),
    ]


def test_a_detached_worktree_has_no_branch():
    out = "worktree /tmp/kaizen-integrate-x/scratch\nHEAD 3333333\ndetached\n\n"

    assert list_worktrees("/p/proto", _replying(out)) == [
        Worktree("/tmp/kaizen-integrate-x/scratch", None, locked=False)
    ]


def test_a_locked_worktree_is_locked_with_or_without_a_reason():
    out = (
        "worktree /p/a\nHEAD 1111111\nbranch refs/heads/a\nlocked\n\n"
        "worktree /p/b\nHEAD 2222222\nbranch refs/heads/b\nlocked on a usb drive\n\n"
    )

    assert list_worktrees("/p/proto", _replying(out)) == [
        Worktree("/p/a", "a", locked=True),
        Worktree("/p/b", "b", locked=True),
    ]
