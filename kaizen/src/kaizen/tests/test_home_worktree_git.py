"""Tests for a home's linked git worktree as the home, against real git: a home repo in
``tmp_path`` with a ticket worktree under its tree, each holding its own tracked marker."""

from pathlib import Path

from kaizen.shared.cli import main
from kaizen.shared.home import find_home
from kaizen.tests.real_git import git
from kaizen.tests.ticket_shell import Shell, cli_home, register

VERSION = "1.2.3"
SYNCED_FILE = Path("docs/agents/workflows.md")


def _home_and_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A committed fixture home, registered as its own project ``home``, and a linked worktree of
    it at ``.claude/worktrees/fix-7-x``."""
    root = cli_home(tmp_path, synced_version=VERSION)
    register(root, "home", "owner/home", root.resolve())
    git("init", "-q", "-b", "main", root)
    git("-C", root, "config", "user.name", "Test")
    git("-C", root, "config", "user.email", "test@example.com")
    git("-C", root, "add", ".")
    git("-C", root, "commit", "-q", "-m", "Make a home")
    worktree = root / ".claude" / "worktrees" / "fix-7-x"
    git("-C", root, "worktree", "add", "-q", "-b", "fix-7-x", worktree)
    return root.resolve(), worktree.resolve()


def _kaizen(cwd: Path, root: Path, *argv: str) -> int:
    return main(
        list(argv),
        run=Shell({}),
        cwd=cwd,
        env={"KAIZEN_HOME": str(root)},
        version=VERSION,
        latest=lambda: None,
    )


def _warnings(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("warning:")]


def test_a_linked_worktree_of_kaizen_home_is_the_home_inside_it(tmp_path):
    root, worktree = _home_and_worktree(tmp_path)

    assert find_home(worktree / "projects", {"KAIZEN_HOME": str(root)}).root == worktree


def test_home_sync_in_a_worktree_writes_the_worktree_not_the_main_checkout(tmp_path):
    root, worktree = _home_and_worktree(tmp_path)

    assert _kaizen(worktree, root, "home", "sync") == 0

    assert (worktree / SYNCED_FILE).is_file()
    assert not (root / SYNCED_FILE).exists()


def test_running_in_a_worktree_of_kaizen_home_warns_once_naming_both_roots(tmp_path, capsys):
    root, worktree = _home_and_worktree(tmp_path)

    assert _kaizen(worktree, root, "home", "sync") == 0

    assert _warnings(capsys.readouterr().err) == [
        f"warning: home: using the worktree {worktree}; KAIZEN_HOME names {root}"
    ]


def test_running_in_kaizen_homes_main_checkout_does_not_warn(tmp_path, capsys):
    root, _ = _home_and_worktree(tmp_path)

    assert _kaizen(root, root, "home", "sync") == 0

    assert _warnings(capsys.readouterr().err) == []


def test_the_leak_check_in_a_worktree_allows_the_main_checkouts_paths(tmp_path, monkeypatch):
    # The home's own text names files in its main checkout, which the worktree no longer is.
    monkeypatch.setenv("HOME", str(tmp_path.resolve()))
    root, worktree = _home_and_worktree(tmp_path)
    (worktree / "notes.md").write_text(f"see ~/{root.name}/wiki/index.md and {root}/AGENTS.md\n")
    git("-C", worktree, "add", "notes.md")
    git("-C", worktree, "commit", "-q", "-m", "Add notes")

    code = main(
        ["project", "leak-check", str(worktree)],
        cwd=worktree,
        env={"KAIZEN_HOME": str(root)},
        version=VERSION,
        latest=lambda: None,
    )

    assert code == 0
