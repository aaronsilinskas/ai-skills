"""Tests for ``kaizen home sync``, driven through ``main`` against the fixture home ``cli_home``
builds, with git and gh replaced by a recording runner that answers nothing."""

import json
import socket
from pathlib import Path

import pytest

from kaizen.shared.cli import main
from kaizen.shared.home import find_home
from kaizen.shared.synced import SYNCED_FILES, render
from kaizen.tests.ticket_shell import Shell, cli_home

SYNCED = [synced.path for synced in SYNCED_FILES]
"""Every synced file in the manifest, in its order."""
SETTINGS = ".claude/settings.json"
DENY = ["Bash(git stash*)", "Bash(git -C * stash*)"]
"""The git stash deny rule's entries, as Claude Code's settings hold them."""


def _sync(home: Path, *extra: str, shell: Shell | None = None) -> int:
    return main(
        ["home", "sync", *extra],
        run=shell or Shell({}),
        cwd=home,
        env={},
        latest=lambda: None,
    )


def _write(root: Path, relative: str, text: str) -> None:
    (root / relative).parent.mkdir(parents=True, exist_ok=True)
    (root / relative).write_text(text)


def _settings(root: Path) -> dict:
    return json.loads((root / SETTINGS).read_text())


def test_a_fresh_home_gets_every_synced_file_as_rendered_and_the_deny_rule(tmp_path):
    home = cli_home(tmp_path)

    assert _sync(home) == 0

    found = find_home(home, {})
    assert found.synced_version is not None
    rendered = render(found, found.synced_version)
    assert [path for path in SYNCED if (home / path).read_text() != rendered[path]] == []
    assert _settings(home) == {"permissions": {"deny": DENY}}


def test_a_rerun_prints_that_nothing_changed(tmp_path, capsys):
    home = cli_home(tmp_path)
    _sync(home)
    capsys.readouterr()

    assert _sync(home) == 0

    assert capsys.readouterr().out == "nothing changed: every synced file and setting is in step\n"


def _synced(tmp_path: Path) -> Path:
    """The fixture home, synced."""
    home = cli_home(tmp_path)
    assert _sync(home) == 0
    return home


def _files(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_an_edited_synced_file_is_rewritten_and_its_path_printed(tmp_path, capsys):
    home = _synced(tmp_path)
    path = SYNCED[1]
    rendered = (home / path).read_text()
    _write(home, path, rendered + "a home rule\n")
    capsys.readouterr()

    assert _sync(home) == 0

    assert capsys.readouterr().out == f"rewrote {path}\n"
    assert (home / path).read_text() == rendered


def test_a_fresh_home_prints_one_line_per_file_written(tmp_path, capsys):
    home = cli_home(tmp_path)

    _sync(home)

    assert capsys.readouterr().out.splitlines() == [
        *[f"wrote {path}" for path in SYNCED],
        f"merged the git stash deny rule into {SETTINGS}",
    ]


def test_the_overlay_hook_config_and_other_settings_are_untouched_in_order(tmp_path):
    home = cli_home(tmp_path)
    overlay = "docs/agents/home-overlay.md"
    _write(home, overlay, "# mine\n")
    _write(home, ".pre-commit-config.yaml", "repos: []\n")
    _write(
        home,
        SETTINGS,
        '{"env": {"A": "1"}, "permissions": {"deny": ["Bash(rm *)", "Bash(git stash*)"],'
        ' "allow": ["Bash(ls)"]}, "hooks": {}}',
    )

    assert _sync(home) == 0

    assert (home / overlay).read_text() == "# mine\n"
    assert (home / ".pre-commit-config.yaml").read_text() == "repos: []\n"
    assert list(_settings(home).items()) == [
        ("env", {"A": "1"}),
        (
            "permissions",
            {
                "deny": ["Bash(rm *)", "Bash(git stash*)", "Bash(git -C * stash*)"],
                "allow": ["Bash(ls)"],
            },
        ),
        ("hooks", {}),
    ]


def test_sync_leaves_the_settings_env_to_init(tmp_path):
    home = _synced(tmp_path)

    assert "env" not in _settings(home)


def test_dry_run_shows_each_change_and_writes_nothing(tmp_path, capsys):
    home = cli_home(tmp_path)
    before = _files(home)

    assert _sync(home, "--dry-run") == 0

    out = capsys.readouterr().out
    assert [path for path in [*SYNCED, SETTINGS] if f"would write {path}:\n--- " not in out] == []
    assert '+    "deny": [' in out
    assert out.endswith("dry run: nothing written\n")
    assert _files(home) == before


def test_check_passes_on_a_synced_home(tmp_path, capsys):
    home = _synced(tmp_path)
    capsys.readouterr()

    assert _sync(home, "--check") == 0

    assert capsys.readouterr().out == (
        "home sync --check: every synced file and setting is in step\n"
    )


def _edit(home: Path) -> str:
    path = SYNCED[0]
    text = (home / path).read_text()
    (home / path).write_text(text.replace("# Workflows", "# My workflows"))
    return path


def _remove(home: Path) -> str:
    path = SYNCED[-1]
    (home / path).unlink()
    return path


def _drop_deny(home: Path) -> str:
    _write(home, SETTINGS, '{"permissions": {"deny": ["Bash(git stash*)"]}}')
    return SETTINGS


def _change_deny(home: Path) -> str:
    _write(
        home, SETTINGS, '{"permissions": {"deny": ["Bash(git stash)", "Bash(git -C * stash*)"]}}'
    )
    return SETTINGS


@pytest.mark.parametrize(
    ("damage", "shown"),
    [
        (_edit, "+# Workflows"),
        (_remove, "--- /dev/null"),
        (_drop_deny, '+      "Bash(git -C * stash*)"'),
        (_change_deny, '+      "Bash(git stash*)"'),
    ],
    ids=["edited file", "missing file", "missing deny entry", "changed deny entry"],
)
def test_check_fails_naming_the_file_and_showing_the_difference(tmp_path, capsys, damage, shown):
    home = _synced(tmp_path)
    path = damage(home)
    capsys.readouterr()

    assert _sync(home, "--check") == 1

    captured = capsys.readouterr()
    assert f"differs: {path}\n" in captured.out
    assert shown in captured.out
    assert captured.err.startswith(
        f"refused: home sync --check: 1 file(s) differ from what sync writes: {path}\n"
    )


def test_check_names_every_file_that_differs(tmp_path, capsys):
    home = _synced(tmp_path)
    paths = [_edit(home), _remove(home), _drop_deny(home)]
    capsys.readouterr()

    assert _sync(home, "--check") == 1

    assert (
        f"3 file(s) differ from what sync writes: {', '.join(paths)}\n" in capsys.readouterr().err
    )


def test_a_failed_check_says_to_sync_and_move_home_rules_to_the_overlay(tmp_path, capsys):
    home = _synced(tmp_path)
    _edit(home)

    _sync(home, "--check")

    assert (
        "  fix: run `kaizen home sync`, and move home rules to the home overlay\n"
        in capsys.readouterr().err
    )


def test_check_writes_nothing_and_makes_no_call(tmp_path, monkeypatch):
    home = _synced(tmp_path)
    _edit(home)
    _remove(home)
    _drop_deny(home)
    before = _files(home)

    def no_network(*args, **kwargs):
        raise AssertionError("home sync --check opened a connection")

    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    shell = Shell({})

    assert _sync(home, "--check", shell=shell) == 1

    assert _files(home) == before
    assert shell.calls == []


@pytest.mark.parametrize(
    "text",
    ['{"permissions": ', "[]", '{"permissions": []}', '{"permissions": {"deny": "Bash(ls)"}}'],
    ids=["not JSON", "not an object", "permissions not an object", "deny not a list"],
)
def test_settings_that_cant_take_the_deny_rule_are_refused_before_any_write(tmp_path, capsys, text):
    home = cli_home(tmp_path)
    _write(home, SETTINGS, text)
    before = _files(home)

    assert _sync(home) == 1

    assert capsys.readouterr().err.startswith(f"refused: home sync: {SETTINGS} ")
    assert _files(home) == before


def test_a_synced_path_that_is_a_folder_is_refused_before_any_write(tmp_path, capsys):
    home = cli_home(tmp_path)
    (home / SYNCED[-1]).mkdir(parents=True)
    before = _files(home)

    assert _sync(home) == 1

    assert capsys.readouterr().err.startswith(f"refused: home sync: {SYNCED[-1]} is not a file")
    assert _files(home) == before


def test_sync_help_names_the_synced_files_the_deny_rule_and_the_check_fix(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["home", "sync", "--help"], cwd=tmp_path, env={})

    out = " ".join(capsys.readouterr().out.split())
    expected = [
        *SYNCED,
        "git stash deny rule",
        "--dry-run",
        "--check",
        "move home rules to the home overlay",
        "rewrites the whole file as JSON indented by two spaces",
        "delete mw.toml",
    ]
    assert [text for text in expected if text not in out] == []


def _with_old_marker_copy(home: Path) -> Path:
    """*home*, given ``mw.toml`` as a copy of its ``kaizen.toml``."""
    (home / "mw.toml").write_bytes((home / "kaizen.toml").read_bytes())
    return home


@pytest.mark.parametrize("extra", [[], ["--dry-run"]], ids=["sync", "dry run"])
def test_sync_with_both_markers_is_refused_before_any_write(tmp_path, capsys, extra):
    home = _with_old_marker_copy(_synced(tmp_path))
    _edit(home)
    before = _files(home)
    capsys.readouterr()

    assert _sync(home, *extra) == 1

    err = capsys.readouterr().err
    assert "refused: home sync: " in err and "kaizen.toml and mw.toml" in err
    assert "  fix: delete mw.toml\n" in err
    assert _files(home) == before


def test_a_refused_sync_on_a_new_release_leaves_both_markers_alike(tmp_path):
    home = _with_old_marker_copy(cli_home(tmp_path, synced_version="0.0.1"))

    _sync(home)

    said: list[str] = []
    assert find_home(home, {}, said.append).synced_version == (0, 0, 1)
    assert len(said) == 1 and "mw.toml" in said[0]


def test_check_with_both_markers_passes_with_the_warning(tmp_path, capsys):
    home = _with_old_marker_copy(_synced(tmp_path))
    capsys.readouterr()

    assert _sync(home, "--check") == 0

    assert "warning: home: " in capsys.readouterr().err
