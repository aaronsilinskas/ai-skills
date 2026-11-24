"""Tests for home discovery: ``find_home`` over fixture homes built in ``tmp_path``."""

import pwd
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from kaizen.shared.common import RefusalError
from kaizen.shared.home import find_home, fresh_home, fresh_marker
from kaizen.shared.labels import Label
from kaizen.shared.version import Version

MARKER = 'registry = "projects"\n[leak]\nown = ["acme/home", "/fixture/acme"]\n'


def _home(root: Path, marker: str = MARKER, name: str = "kaizen.toml") -> Path:
    (root / "projects").mkdir(parents=True, exist_ok=True)
    (root / name).write_text(marker)
    return root


def test_a_marker_at_the_start_directory_is_the_home(tmp_path):
    root = _home(tmp_path / "home")

    home = find_home(root, {})

    assert home.root == root.resolve()
    assert home.registry == root.resolve() / "projects"
    assert home.leak_own == ("acme/home", "/fixture/acme")
    assert (home.leak_allow_paths, home.leak_allow_repos) == ((), ())


def test_the_leak_allowlist_holds_the_paths_and_repos_the_marker_allows(tmp_path):
    tilde_path = "~" + "/tool-settings"
    marker = MARKER + f'allow = ["{tilde_path}", "/opt/tool", "acme/archived"]\n'

    home = find_home(_home(tmp_path / "home", marker), {})

    assert home.leak_allow_paths == (tilde_path, "/opt/tool")
    assert home.leak_allow_repos == ("acme/archived",)


def test_an_unset_comment_only_switch_leaves_the_comment_only_check_on(tmp_path):
    assert find_home(_home(tmp_path), {}).auto_merge_comment_only is True


def test_the_marker_turns_the_comment_only_check_off(tmp_path):
    root = _home(tmp_path, "auto_merge_comment_only = false\n" + MARKER)

    assert find_home(root, {}).auto_merge_comment_only is False


def test_the_marker_is_found_from_a_subdirectory(tmp_path):
    root = _home(tmp_path / "home")
    (root / "src" / "deep").mkdir(parents=True)

    assert find_home(root / "src" / "deep", {}).root == root.resolve()


def test_kaizen_home_alone_finds_the_home_from_outside_its_tree(tmp_path):
    root = _home(tmp_path / "home")
    project = tmp_path / "project"
    project.mkdir()

    assert find_home(project, {"KAIZEN_HOME": str(root)}).root == root.resolve()


def test_kaizen_home_written_from_another_users_home_directory_finds_the_home(
    tmp_path, monkeypatch
):
    root = _home(tmp_path / "other" / "home")
    users = {"other": SimpleNamespace(pw_dir=str(tmp_path / "other"))}
    monkeypatch.setattr(pwd, "getpwnam", users.__getitem__)

    other_users_home = "~" + "other/home"

    assert find_home(tmp_path, {"KAIZEN_HOME": other_users_home}).root == root.resolve()


def test_kaizen_home_and_the_marker_agreeing_is_the_home(tmp_path):
    root = _home(tmp_path / "home")

    assert find_home(root, {"KAIZEN_HOME": str(root)}).root == root.resolve()


def test_kaizen_home_and_the_marker_disagreeing_is_refused_naming_only_kaizen_homes_root(tmp_path):
    first = _home(tmp_path / "first")
    second = _home(tmp_path / "second" / "deep")

    with pytest.raises(RefusalError) as refusal:
        find_home(second, {"KAIZEN_HOME": str(first)})

    message = str(refusal.value)
    assert f"KAIZEN_HOME names {first.resolve()}" in message
    assert f"fix: run kaizen from inside {first.resolve()}" in message
    assert "second" not in message


def test_a_linked_git_worktree_of_kaizen_home_counts_as_that_home(tmp_path):
    # A ticket worktree of the home sits in its tree and carries its own copy of the marker.
    root = _home(tmp_path / "home")
    worktree = _home(root / ".claude" / "worktrees" / "fix-7-x")
    (worktree / ".git").write_text(f"gitdir: {root}/.git/worktrees/fix-7-x\n")

    assert find_home(worktree, {"KAIZEN_HOME": str(root)}).root == root.resolve()


def test_a_git_worktree_of_another_repo_inside_kaizen_homes_tree_is_still_refused(tmp_path):
    root = _home(tmp_path / "home")
    other = _home(root / "nested")
    (other / ".git").write_text(f"gitdir: {tmp_path}/elsewhere/.git/worktrees/nested\n")

    with pytest.raises(RefusalError, match="KAIZEN_HOME"):
        find_home(other, {"KAIZEN_HOME": str(root)})


def test_neither_finding_a_home_is_refused_with_a_fix_naming_both(tmp_path):
    with pytest.raises(RefusalError, match=r"no home(.|\n)*fix:.*KAIZEN_HOME.*kaizen\.toml"):
        find_home(tmp_path, {})


def test_kaizen_home_naming_a_directory_without_a_marker_is_refused(tmp_path):
    with pytest.raises(RefusalError, match=r"KAIZEN_HOME(.|\n)*kaizen\.toml"):
        find_home(tmp_path, {"KAIZEN_HOME": str(tmp_path / "nowhere")})


@pytest.mark.parametrize(
    ("marker", "reason"),
    [
        ("registry = \n", "is not valid TOML"),
        ("[leak]\nown = []\n", "missing 'registry'"),
        ('registry = "projects"\n', "missing 'leak.own'"),
        ("registry = 3\n[leak]\nown = []\n", "'registry' must be a string"),
        ('registry = "projects"\nleak = 1\n', "'leak' must be a table"),
        ('registry = "projects"\n[leak]\nown = "x"\n', "'leak.own' must be a list"),
        ('registry = "projects"\n[leak]\nown = [""]\n', "'leak.own' must be a list"),
        ('registry = "nope"\n[leak]\nown = []\n', "registry folder"),
        ('registry = "projects"\n[leak]\nown = []\nallow = "x"\n', "'leak.allow'"),
        ('registry = "projects"\n[leak]\nown = []\nallow = ["x"]\n', "'leak.allow'"),
        ('registry = "projects"\n[leak]\nown = []\nallow = ["/"]\n', "holds the home"),
        (
            'auto_merge_comment_only = "no"\nregistry = "projects"\n[leak]\nown = []\n',
            "'auto_merge_comment_only' must be true or false",
        ),
    ],
    ids=[
        "bad toml",
        "no registry",
        "no leak patterns",
        "registry not a string",
        "leak not a table",
        "leak.own not a list",
        "empty leak pattern",
        "registry folder missing",
        "leak.allow not a list",
        "allowed entry neither a path nor a repo",
        "allowed path holds the home",
        "comment-only switch not a boolean",
    ],
)
def test_a_malformed_marker_is_refused_naming_the_marker(tmp_path, marker, reason):
    root = _home(tmp_path / "home", marker)

    with pytest.raises(RefusalError, match=rf"kaizen\.toml(.|\n)*{reason}"):
        find_home(root, {})


def test_an_unset_workflow_labels_setting_gives_the_eleven_default_labels(tmp_path):
    home = find_home(_home(tmp_path / "home"), {})

    assert len(home.workflow_labels) == 11
    assert home.workflow_labels[0] == Label(
        "needs-triage", "fbca04", "Maintainer needs to evaluate this issue"
    )


_LABEL = '\n[[workflow_labels]]\nname = "triage"\ncolor = "fbca04"\ndescription = "Look"\n'


@pytest.mark.parametrize(
    ("marker", "reason"),
    [
        ("workflow_labels = 1\n" + MARKER, "'workflow_labels' must be one or more"),
        ("workflow_labels = []\n" + MARKER, "'workflow_labels' must be one or more"),
        (MARKER + _LABEL.replace('color = "fbca04"\n', ""), "entry 1 needs a string 'color'"),
        (MARKER + _LABEL.replace('"Look"', "3"), "entry 1 needs a string 'description'"),
        (MARKER + _LABEL.replace('"triage"', '""'), "entry 1 has an empty 'name'"),
        (MARKER + _LABEL.replace("fbca04", "#fbca04"), "entry 1's 'color' '#fbca04' must be"),
        (MARKER + _LABEL.replace("fbca04", "fbca0"), "entry 1's 'color' 'fbca0' must be"),
        (MARKER + _LABEL + 'colour = "x"\n', "entry 1 has an unknown key 'colour'"),
        (MARKER + _LABEL + _LABEL.replace("fbca04", "000000"), "names 'triage' twice"),
    ],
    ids=[
        "not tables",
        "empty set",
        "missing field",
        "field not a string",
        "empty name",
        "colour with #",
        "colour too short",
        "unknown key",
        "duplicate name",
    ],
)
def test_a_malformed_workflow_label_is_refused_naming_the_marker_and_the_fix(
    tmp_path, marker, reason
):
    root = _home(tmp_path / "home", marker)
    refusal = (
        rf"kaizen\.toml is malformed: [^\n]*{re.escape(reason)}[^\n]*\n  fix: fix .*kaizen\.toml"
    )

    with pytest.raises(RefusalError, match=refusal):
        find_home(root, {})


def test_a_configured_colour_is_read_lowercased(tmp_path):
    root = _home(tmp_path / "home", MARKER + _LABEL.replace("fbca04", "FBCA04"))

    assert find_home(root, {}).workflow_labels == (Label("triage", "fbca04", "Look"),)


def test_fresh_home_is_the_home_find_home_reads_from_the_fresh_marker(tmp_path):
    version = Version(1, 2, 3)
    marker = fresh_marker("acme/home", "/fixture/acme", version)
    root = _home(tmp_path / "home", marker).resolve()

    assert fresh_home(root, "acme/home", "/fixture/acme", version) == find_home(root, {})


@pytest.mark.parametrize(
    ("marker", "variable", "warnings"),
    [
        ("kaizen.toml", "KAIZEN_HOME", []),
        ("kaizen.toml", "MW_HOME", ["MW_HOME"]),
        ("mw.toml", "KAIZEN_HOME", ["mw.toml"]),
        ("mw.toml", "MW_HOME", ["MW_HOME", "mw.toml"]),
    ],
)
def test_each_marker_and_variable_name_finds_the_home_warning_about_each_old_name(
    tmp_path, marker, variable, warnings
):
    root = _home(tmp_path / "home", name=marker)
    project = tmp_path / "project"
    project.mkdir()
    said: list[str] = []

    home = find_home(project, {variable: str(root)}, warn=said.append)

    assert home.root == root.resolve()
    assert home.leak_own == ("acme/home", "/fixture/acme")
    assert len(said) == len(warnings)
    for line, old in zip(said, warnings, strict=True):
        new = {"MW_HOME": "KAIZEN_HOME", "mw.toml": "kaizen.toml"}[old]
        assert old in line and new in line and "\n" not in line


def test_the_old_marker_found_by_the_upward_search_warns_naming_the_new_one(tmp_path):
    root = _home(tmp_path / "home", name="mw.toml")
    said: list[str] = []

    assert find_home(root, {}, warn=said.append).root == root.resolve()
    assert len(said) == 1 and "mw.toml" in said[0] and "kaizen.toml" in said[0]


def test_both_markers_with_the_same_bytes_pass_with_the_warning(tmp_path):
    root = _home(_home(tmp_path / "home"), name="mw.toml")
    said: list[str] = []

    assert find_home(root, {}, warn=said.append).root == root.resolve()
    assert len(said) == 1 and "mw.toml" in said[0] and "kaizen.toml" in said[0]


def test_both_markers_with_different_bytes_are_refused_before_any_other_check(tmp_path):
    malformed_new_marker = "registry = \n"
    root = _home(_home(tmp_path / "home", malformed_new_marker), MARKER, name="mw.toml")

    with pytest.raises(RefusalError) as refusal:
        find_home(root, {})

    message = str(refusal.value)
    assert "kaizen.toml" in message and "mw.toml" in message
    assert re.search(r"fix: keep kaizen\.toml.*delete mw\.toml", message)


def test_both_variables_naming_the_same_root_pass_with_the_warning(tmp_path):
    root = _home(tmp_path / "home")
    said: list[str] = []
    env = {"KAIZEN_HOME": str(root), "MW_HOME": str(root) + "/"}

    assert find_home(tmp_path, env, warn=said.append).root == root.resolve()
    assert len(said) == 1 and "MW_HOME" in said[0] and "KAIZEN_HOME" in said[0]


def test_both_variables_naming_different_roots_are_refused_before_any_other_check(tmp_path):
    roots_without_markers = tmp_path / "first", tmp_path / "second"
    env = dict(zip(("KAIZEN_HOME", "MW_HOME"), map(str, roots_without_markers), strict=True))

    with pytest.raises(RefusalError) as refusal:
        find_home(tmp_path, env)

    message = str(refusal.value)
    assert "KAIZEN_HOME and MW_HOME name different roots" in message
    assert re.search(r"fix: keep KAIZEN_HOME.*unset MW_HOME", message)
    assert str(tmp_path) not in message


def test_differing_markers_in_another_home_than_the_variable_names_are_refused_unnamed(tmp_path):
    root = _home(tmp_path / "home")
    other = _home(_home(tmp_path / "other-home", "registry = \n"), name="mw.toml")

    with pytest.raises(RefusalError) as refusal:
        find_home(other, {"KAIZEN_HOME": str(root)})

    message = str(refusal.value)
    assert f"a directory at or above {other} holds both kaizen.toml and mw.toml" in message
    assert str(other) not in message.replace(f"a directory at or above {other}", "")
