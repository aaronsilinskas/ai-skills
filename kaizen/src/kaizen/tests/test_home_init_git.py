"""Tests for ``kaizen home init``'s leak report against real git, in a fresh repo in ``tmp_path``.

``origin`` is only a URL: init reads it and never fetches, so nothing touches GitHub.
"""

from pathlib import Path

from kaizen.shared.cli import main
from kaizen.tests.real_git import git
from kaizen.tests.ticket_shell import TILDE


def _fresh_repo(tmp_path: Path) -> Path:
    root = tmp_path / "user" / "work" / "newhome"
    root.mkdir(parents=True)
    git("init", "-q", "-b", "main", root)
    git("-C", root, "config", "user.name", "Test")
    git("-C", root, "config", "user.email", "test@example.com")
    git("-C", root, "remote", "add", "origin", "https://github.com/acme/newhome.git")
    return root


def _init(tmp_path: Path, root: Path) -> int:
    return main(["home", "init"], cwd=root, env={"HOME": str(tmp_path / "user")})


def test_a_committed_outside_path_is_reported_as_a_to_do(tmp_path, capsys):
    root = _fresh_repo(tmp_path)
    (root / "notes.md").write_text(f"# Notes\n\nsee {TILDE}/elsewhere/plans\n")
    git("-C", root, "add", "notes.md")
    git("-C", root, "commit", "-q", "-m", "Add notes")

    assert _init(tmp_path, root) == 0

    out = capsys.readouterr().out.splitlines()
    header = "leak check: searched committed files only; to do, one line per finding with its fix:"
    assert header in out
    assert any(
        line.startswith(f"  - [ ] notes.md:3: outside path {TILDE}/elsewhere/plans") for line in out
    )


def test_untracked_files_are_not_searched(tmp_path, capsys):
    root = _fresh_repo(tmp_path)
    (root / "notes.md").write_text(f"see {TILDE}/elsewhere/plans\n")

    assert _init(tmp_path, root) == 0

    out = capsys.readouterr().out.splitlines()
    assert "leak check: searched committed files only; it found nothing" in out
