"""Tests for ``kaizen project add`` against real git, in a home ``kaizen home init`` made in
``tmp_path``.

``origin`` is only a URL and the flags settle ``public``, so nothing touches GitHub.
"""

from pathlib import Path

from kaizen.shared.cli import main
from kaizen.tests.real_git import git


def _repo(root: Path, origin: str) -> Path:
    root.mkdir(parents=True)
    git("init", "-q", "-b", "main", root)
    git("-C", root, "remote", "add", "origin", origin)
    return root


def test_an_added_project_passes_the_homes_sync_check(tmp_path, monkeypatch, capsys):
    user = tmp_path / "user"
    monkeypatch.setenv("HOME", str(user))
    env = {"HOME": str(user)}
    home = _repo(user / "work" / "newhome", "https://github.com/acme/newhome.git")
    assert main(["home", "init"], cwd=home, env=env) == 0
    tool = _repo(user / "work" / "tool", "git@github.com:acme/tool.git")
    (tool / "src").mkdir()
    (tool / "src" / "a.py").write_text("")
    git("-C", tool, "add", "src/a.py")

    code = main(
        ["project", "add", "tool", str(tool), "--private", "--check", "none"], cwd=home, env=env
    )

    assert code == 0
    capsys.readouterr()
    assert main(["home", "sync", "--check"], cwd=home, env=env) == 0, capsys.readouterr()


def test_a_folder_outside_any_checkout_is_refused(tmp_path, capsys):
    user = tmp_path / "user"
    home = _repo(user / "work" / "newhome", "https://github.com/acme/newhome.git")
    assert main(["home", "init"], cwd=home, env={"HOME": str(user)}) == 0
    loose = tmp_path / "loose"
    loose.mkdir()

    code = main(["project", "add", "loose", str(loose), "--private"], cwd=home, env={})

    assert code == 1
    assert f"{loose.resolve()} is not a git checkout" in capsys.readouterr().err
