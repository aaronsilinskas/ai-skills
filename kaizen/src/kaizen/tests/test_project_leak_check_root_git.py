"""Tests for ``kaizen project leak-check --root``, the CI form, against real git: a home committed
in ``tmp_path`` at a path its registry doesn't name, as a fresh CI clone is.

``origin`` is only a URL: no page here sets ``leak_deny``, so nothing fetches or asks origin.
"""

import os
from pathlib import Path

import pytest

from kaizen.shared.cli import main
from kaizen.shared.common import run_subprocess
from kaizen.tests.ticket_shell import RELEASE, TILDE

REGISTERED = f"{TILDE}/registered/home"
"""The home's path on its own page, which a CI clone is never at."""


def _git(*args: str | Path) -> str:
    return run_subprocess(["git", *map(str, args)])


def _commit(root: Path, relative: str, text: str) -> None:
    (root / relative).parent.mkdir(parents=True, exist_ok=True)
    (root / relative).write_text(text)
    _git("-C", root, "add", relative)
    _git("-C", root, "commit", "-q", "-m", f"Add {relative}")


def _clone(tmp_path: Path, origin: str = "https://github.com/acme/home.git") -> Path:
    """A home committed at ``tmp_path/ci/home``, registering itself at ``REGISTERED`` and a
    project ``relay``, with *origin* as its ``origin`` remote."""
    root = tmp_path / "ci" / "home"
    root.mkdir(parents=True)
    _git("init", "-q", "-b", "main", root)
    _git("-C", root, "config", "user.name", "Test")
    _git("-C", root, "config", "user.email", "test@example.com")
    _git("-C", root, "remote", "add", "origin", origin)
    marker = (
        f'registry = "projects"\nsynced_version = "{RELEASE}"\n'
        f'[leak]\nown = ["acme/home", "{REGISTERED}"]\n'
    )
    _commit(root, "kaizen.toml", marker)
    _commit(
        root,
        "projects/home.md",
        f"---\npath: {REGISTERED}\ngithub: acme/home\npublic: false\n---\n",
    )
    _commit(
        root,
        "projects/relay.md",
        "---\npath: /fixture/relay\ngithub: acme/relay\npublic: true\n---\n",
    )
    return root


@pytest.fixture(autouse=True)
def _in_tmp(tmp_path, monkeypatch):
    """Restores the process's directory once a test has run kaizen from inside its clone."""
    monkeypatch.chdir(tmp_path)


def _leak_check(cwd: Path, *args: str) -> int:
    """Runs the leak check from *cwd*, as a CI step does, so ``--root .`` names it."""
    os.chdir(cwd)
    return main(["project", "leak-check", *args], cwd=cwd, env={})


def test_a_clean_clone_at_an_unregistered_path_passes_as_the_homes_own_project(tmp_path, capsys):
    root = _clone(tmp_path)
    _commit(root, "notes.md", f"see {REGISTERED}/wiki and /fixture/relay and acme/relay\n")

    assert _leak_check(root, "--root", ".") == 0

    assert f"leak check found nothing in home at {root.resolve()}\n" in capsys.readouterr().out


def test_text_pointing_outside_the_home_is_refused_as_at_the_registered_path(tmp_path, capsys):
    root = _clone(tmp_path)
    _commit(root, "notes.md", f"see {TILDE}/elsewhere/plans and acme/secret\n")

    assert _leak_check(root, "--root", ".") == 1

    err = capsys.readouterr().err
    assert f"notes.md:1: outside path {TILDE}/elsewhere/plans" in err
    assert "notes.md:1: unregistered repo acme/secret" in err


def test_without_root_a_clone_at_an_unregistered_path_is_still_refused(tmp_path, capsys):
    root = _clone(tmp_path)

    assert _leak_check(root) == 1

    assert "is not a registered project's main checkout" in capsys.readouterr().err


def test_root_naming_a_checkout_other_than_the_homes_root_is_refused(tmp_path, capsys):
    root = _clone(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    _git("init", "-q", "-b", "main", other)

    assert _leak_check(root, "--root", str(other)) == 1

    err = capsys.readouterr().err
    assert f"--root: {other.resolve()} is not the root of the home kaizen serves" in err


@pytest.mark.parametrize(
    "origin",
    ["https://github.com/acme/unlisted.git", "/somewhere/home.git"],
    ids=["unregistered", "not GitHub"],
)
def test_a_clone_whose_origin_no_page_registers_is_refused(tmp_path, capsys, origin):
    root = _clone(tmp_path, origin)

    assert _leak_check(root, "--root", ".") == 1

    assert "refused: project leak-check --root: no registry page's github is origin's" in (
        capsys.readouterr().err
    )


@pytest.mark.parametrize("extra", [["--staged"], [str(Path("."))]], ids=["staged", "checkout"])
def test_root_with_staged_or_a_checkout_is_refused(tmp_path, capsys, extra):
    root = _clone(tmp_path)

    assert _leak_check(root, "--root", ".", *extra) == 1

    assert "refused: project leak-check: --root takes no " in capsys.readouterr().err


def test_help_shows_the_step_a_homes_ci_adds_and_how_a_shallow_clone_is_handled(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["project", "leak-check", "--help"], cwd=tmp_path, env={})

    out = " ".join(capsys.readouterr().out.split())
    expected = ["`kaizen project leak-check --root .`", "shallow one, is refused", "fetch-depth: 0"]
    assert [text for text in expected if text not in out] == []
