"""Tests for the **synced version**: ``home sync`` and ``home init`` record it in the marker, every
command that needs a home compares it with the running version, and ``home sync`` alone looks
up the latest release. Driven through ``main`` with the running version and the lookup passed
in, so no install or network is needed."""

from pathlib import Path

import pytest

from kaizen.shared.cli import main
from kaizen.shared.home import MARKER
from kaizen.tests.ticket_shell import Shell, cli_home


class Lookup:
    """A latest-release lookup answering *answer*, counting its calls."""

    def __init__(self, answer: str | None = None) -> None:
        self.answer = answer
        self.calls = 0

    def __call__(self) -> str | None:
        self.calls += 1
        return self.answer


def _kaizen(home: Path, *argv: str, version: str = "1.2.3", latest=None) -> int:
    return main(
        list(argv), run=Shell({}), cwd=home, env={}, version=version, latest=latest or Lookup()
    )


def _home(tmp_path: Path, synced_version: str | None = "1.2.3") -> Path:
    """The fixture home, its marker recording *synced_version* (none when ``None``)."""
    return cli_home(tmp_path, synced_version=synced_version)


def _synced(tmp_path: Path, version: str = "1.2.3") -> Path:
    """The fixture home, synced by *version*."""
    home = _home(tmp_path, None)
    assert _kaizen(home, "home", "sync", version=version, latest=lambda: None) == 0
    return home


def _marker(home: Path) -> str:
    return (home / MARKER).read_text()


def _warnings(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("warning:")]


# Recording the version


def test_sync_records_the_running_version_above_the_first_table(tmp_path):
    home = _home(tmp_path, None)
    before = _marker(home)

    assert _kaizen(home, "home", "sync", version="2.0.1", latest=lambda: None) == 0

    table = before.index("[leak]")
    assert _marker(home) == before[:table] + 'synced_version = "2.0.1"\n\n' + before[table:]


def test_sync_replaces_a_recorded_version_and_keeps_every_other_byte(tmp_path):
    home = _synced(tmp_path, "1.2.3")
    before = _marker(home)

    _kaizen(home, "home", "sync", version="1.10.0", latest=lambda: None)

    assert _marker(home) == before.replace('"1.2.3"', '"1.10.0"')


def test_the_version_goes_above_the_comments_that_head_the_first_table(tmp_path):
    home = _home(tmp_path, None)
    marker = 'registry = "projects"\n# the leak table\n[leak]\nown = ["owner/home"]\n'
    (home / MARKER).write_text(marker)

    _kaizen(home, "home", "sync", version="1.2.3", latest=lambda: None)

    assert _marker(home) == (
        'registry = "projects"\nsynced_version = "1.2.3"\n\n# the leak table\n[leak]\n'
        'own = ["owner/home"]\n'
    )


def test_a_synced_version_key_inside_a_table_is_not_the_recorded_one(tmp_path):
    home = _home(tmp_path, None)
    marker = 'registry = "projects"\n[leak]\nown = ["owner/home"]\n[x]\nsynced_version = "0.0.1"\n'
    (home / MARKER).write_text(marker)

    _kaizen(home, "home", "sync", version="1.2.3", latest=lambda: None)

    assert _marker(home) == marker.replace("[leak]", 'synced_version = "1.2.3"\n\n[leak]', 1)


def test_a_multi_line_array_row_is_not_taken_for_a_table(tmp_path):
    home = _home(tmp_path, None)
    marker = 'registry = "projects"\nx = [\n  ["a"]\n]\n[leak]\nown = ["owner/home"]\n'
    (home / MARKER).write_text(marker)

    _kaizen(home, "home", "sync", version="1.2.3")

    assert _marker(home) == marker.replace("[leak]", 'synced_version = "1.2.3"\n\n[leak]', 1)


def test_sync_prints_the_version_it_records(tmp_path, capsys):
    home = _synced(tmp_path, "1.2.3")
    capsys.readouterr()

    _kaizen(home, "home", "sync", version="1.3.0", latest=lambda: None)

    out = capsys.readouterr().out
    assert f"recorded synced version 1.3.0 in {MARKER}\n" in out


def test_the_synced_doc_shows_the_homes_ci_step_with_the_recorded_version(tmp_path):
    home = _synced(tmp_path, "4.5.6")

    workflows = (home / "docs/agents/workflows.md").read_text()

    step = "`uvx --refresh-package kaizen-kit --from kaizen-kit==4.5.6 kaizen home sync --check`"
    assert step in workflows


def test_the_synced_doc_names_the_upgrade_that_moves_a_pinned_install(tmp_path):
    home = _synced(tmp_path, "4.5.6")

    workflows = (home / "docs/agents/workflows.md").read_text()

    assert "an older one refuses until `uv tool install kaizen-kit@latest` runs" in workflows


def test_sync_refuses_to_record_a_running_version_that_is_not_x_y_z(tmp_path, capsys):
    home = _synced(tmp_path, "1.2.3")
    before = _marker(home)
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", version="1.3.0.dev0") == 1

    err = capsys.readouterr().err
    assert "refused: home sync: kaizen's version 1.3.0.dev0 is not X.Y.Z" in err
    assert "(`uv tool install kaizen-kit@latest`)" in err
    assert _marker(home) == before


# The check on every command


def test_a_command_in_a_home_synced_by_the_running_version_does_not_warn(tmp_path, capsys):
    home = _synced(tmp_path, "1.2.3")
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", "--check", version="1.2.3") == 0

    assert _warnings(capsys.readouterr().err) == []


def test_a_newer_install_warns_once_naming_both_versions_and_runs_the_command(tmp_path, capsys):
    home = _synced(tmp_path, "1.2.3")
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", "--check", version="1.10.0") == 0

    captured = capsys.readouterr()
    assert _warnings(captured.err) == [
        "warning: kaizen 1.10.0 is newer than this home's synced version 1.2.3:"
        " run `kaizen home sync`"
    ]
    assert "in step" in captured.out


def test_an_older_install_is_refused_with_the_upgrade_fix_before_the_command_runs(tmp_path, capsys):
    home = _synced(tmp_path, "1.10.0")
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", "--check", version="1.9.9") == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(
        "refused: kaizen 1.9.9 is older than this home's synced version 1.10.0\n"
        "  fix: uv tool install kaizen-kit@latest\n"
    )


def test_sync_refuses_on_an_older_install_and_writes_nothing(tmp_path, capsys):
    home = _synced(tmp_path, "2.0.0")
    (home / "docs/agents/workflows.md").write_text("edited\n")
    before = {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}

    assert _kaizen(home, "home", "sync", version="1.9.9", latest=lambda: None) == 1

    assert {p: p.read_bytes() for p in home.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("recorded", [None, "1.0.0"])
def test_sync_itself_does_not_warn_to_run_sync(tmp_path, capsys, recorded):
    home = _home(tmp_path, recorded)

    assert _kaizen(home, "home", "sync", version="1.2.3") == 0

    assert _warnings(capsys.readouterr().err) == []


def test_a_home_with_no_recorded_version_warns_to_sync(tmp_path, capsys):
    home = _home(tmp_path, None)

    _kaizen(home, "spec", "status", "7")

    assert _warnings(capsys.readouterr().err) == [
        f"warning: this home's {MARKER} records no synced version: run `kaizen home sync`"
    ]


@pytest.mark.parametrize("running", ["1.2.3.dev0", "1.2", "local"])
def test_a_running_version_that_is_not_x_y_z_warns_once_and_skips_the_comparison(
    tmp_path, capsys, running
):
    home = _synced(tmp_path, "9.9.9")
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", "--check", version=running) == 0

    assert _warnings(capsys.readouterr().err) == [
        f"warning: kaizen's version {running} is not X.Y.Z, such as a local build's, so this"
        " home's synced version is not compared with it"
    ]


def test_a_recorded_version_that_is_not_x_y_z_is_refused_as_a_malformed_marker(tmp_path, capsys):
    home = _home(tmp_path, "soon")

    assert _kaizen(home, "spec", "status", "7") == 1

    assert "'synced_version' must be a version X.Y.Z" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["--help"], ["home", "--help"], ["spec", "status", "--help"]])
def test_help_skips_the_check(tmp_path, capsys, argv):
    home = _home(tmp_path, "9.9.9")

    with pytest.raises(SystemExit):
        _kaizen(home, *argv, version="1.0.0")

    assert capsys.readouterr().err == ""


# --check


def test_check_fails_when_no_synced_version_is_recorded(tmp_path, capsys):
    home = _synced(tmp_path)
    (home / MARKER).write_text(_marker(home).replace('synced_version = "1.2.3"\n\n', ""))
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", "--check") == 1

    assert (
        f"refused: home sync --check: {MARKER} records no synced version\n"
        "  fix: run `kaizen home sync`"
    ) in capsys.readouterr().err


def test_check_passes_on_a_home_synced_by_the_release_ci_runs(tmp_path, capsys):
    home = _synced(tmp_path, "1.2.3")
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", "--check", version="1.2.3") == 0


# The latest-release lookup


def test_sync_names_a_newer_release_and_the_upgrade_command(tmp_path, capsys):
    home = _synced(tmp_path, "1.2.3")
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", version="1.2.3", latest=lambda: "1.3.0") == 0

    assert capsys.readouterr().out.splitlines()[-1] == (
        "kaizen 1.3.0 is out (this is 1.2.3): run `uv tool install kaizen-kit@latest`"
    )


@pytest.mark.parametrize("latest", ["1.2.3", "1.2.2", "not a version"])
def test_sync_says_nothing_of_a_release_that_is_not_newer(tmp_path, capsys, latest):
    home = _synced(tmp_path, "1.2.3")
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", version="1.2.3", latest=lambda: latest) == 0

    assert capsys.readouterr().out == (
        "nothing changed: every synced file and setting is in step\n"
    )


def test_a_failed_lookup_prints_nothing_and_sync_still_exits_0(tmp_path, capsys):
    home = _synced(tmp_path, "1.2.3")
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", version="1.2.3", latest=lambda: None) == 0

    captured = capsys.readouterr()
    assert captured.out == "nothing changed: every synced file and setting is in step\n"
    assert _warnings(captured.err) == []


@pytest.mark.parametrize(
    "argv",
    [
        ["home", "sync", "--check"],
        ["spec", "status", "7"],
        ["project", "leak-check"],
        ["issue", "show", "7"],
    ],
)
def test_no_command_but_sync_calls_the_lookup(tmp_path, argv):
    home = _synced(tmp_path)
    lookup = Lookup("9.9.9")

    _kaizen(home, *argv, latest=lookup)

    assert lookup.calls == 0


# Previewing a local build: --dry-run --allow-dev

DEV = "1.3.0.dev0"
"""A local build's version, which is not X.Y.Z."""


def _tree(home: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}


def test_a_local_build_dry_run_prints_each_diff_and_writes_nothing(tmp_path, capsys):
    home = _synced(tmp_path, "1.2.3")
    workflows = "docs/agents/workflows.md"
    (home / workflows).write_text("edited\n")
    (home / ".claude/settings.json").write_text("{}")
    before = _tree(home)
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", "--dry-run", "--allow-dev", version=DEV) == 0

    out = capsys.readouterr().out
    assert f"would write {workflows}:\n--- a/{workflows}\n+++ b/{workflows}\n" in out
    assert "would write .claude/settings.json:\n--- " in out
    assert out.endswith("dry run: nothing written\n")
    assert _tree(home) == before


def test_a_local_build_dry_run_renders_for_the_recorded_version_so_only_templates_differ(
    tmp_path, capsys
):
    home = _synced(tmp_path, "1.2.3")
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", "--dry-run", "--allow-dev", version=DEV) == 0

    assert capsys.readouterr().out == (
        "nothing changed: every synced file and setting is in step\ndry run: nothing written\n"
    )


def test_a_local_build_dry_run_makes_no_lookup(tmp_path):
    home = _synced(tmp_path, "1.2.3")
    lookup = Lookup("9.9.9")

    _kaizen(home, "home", "sync", "--dry-run", "--allow-dev", version=DEV, latest=lookup)

    assert lookup.calls == 0


@pytest.mark.parametrize("mode", [[], ["--check"]])
def test_allow_dev_without_dry_run_is_refused_as_preview_only(tmp_path, capsys, mode):
    home = _synced(tmp_path, "1.2.3")
    (home / "docs/agents/workflows.md").write_text("edited\n")
    before = _tree(home)
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", "--allow-dev", *mode, version=DEV) == 1

    assert (
        f"refused: home sync: --allow-dev is preview-only, so it needs --dry-run to run"
        f" kaizen {DEV}, which is not X.Y.Z\n"
        "  fix: add --dry-run to preview the synced files, or install a release to write them"
    ) in capsys.readouterr().err
    assert _tree(home) == before


def test_a_local_build_dry_run_is_refused_when_the_home_records_no_synced_version(tmp_path, capsys):
    home = _home(tmp_path, None)

    assert _kaizen(home, "home", "sync", "--dry-run", "--allow-dev", version=DEV) == 1

    assert (
        f"refused: home sync --dry-run --allow-dev: {MARKER} records no synced version\n"
        "  fix: run a release's `kaizen home sync` first"
    ) in capsys.readouterr().err


def test_a_release_build_ignores_allow_dev_and_syncs_as_usual(tmp_path, capsys):
    home = _synced(tmp_path, "1.2.3")
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", "--allow-dev", version="1.3.0", latest=lambda: None) == 0

    assert capsys.readouterr().out.splitlines()[-1] == f"recorded synced version 1.3.0 in {MARKER}"
    assert 'synced_version = "1.3.0"' in _marker(home)


def test_a_release_build_dry_run_ignores_allow_dev_and_previews_its_own_version(tmp_path, capsys):
    home = _synced(tmp_path, "1.2.3")
    before = _tree(home)
    capsys.readouterr()

    assert (
        _kaizen(home, "home", "sync", "--dry-run", "--allow-dev", version="1.3.0", latest=None) == 0
    )

    out = capsys.readouterr().out
    assert f"would write {MARKER}:\n" in out
    assert '+synced_version = "1.3.0"' in out
    assert _tree(home) == before


def test_a_local_build_sync_without_allow_dev_names_the_preview_in_its_fix(tmp_path, capsys):
    home = _synced(tmp_path, "1.2.3")
    capsys.readouterr()

    assert _kaizen(home, "home", "sync", version=DEV) == 1

    assert (
        "; or, to preview a local build's synced files, run"
        " `kaizen home sync --dry-run --allow-dev`"
    ) in capsys.readouterr().err
