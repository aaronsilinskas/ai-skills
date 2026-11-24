"""Tests for home discovery: ``find_home`` over fixture homes built in ``tmp_path``."""

import pwd
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from kaizen.shared.common import RefusalError
from kaizen.shared.home import find_home, fresh_home, fresh_marker
from kaizen.shared.labels import Label

MARKER = 'registry = "projects"\n[leak]\nown = ["acme/home", "/fixture/acme"]\n'


def _home(root: Path, marker: str = MARKER) -> Path:
    (root / "projects").mkdir(parents=True)
    (root / "mw.toml").write_text(marker)
    return root


def test_a_marker_at_the_start_directory_is_the_home(tmp_path):
    root = _home(tmp_path / "home")

    home = find_home(root, {})

    assert home.root == root.resolve()
    assert home.registry == root.resolve() / "projects"
    assert home.leak_own == ("acme/home", "/fixture/acme")
    assert (home.leak_allow_paths, home.leak_allow_repos) == ((), ())


def test_the_leak_allowlist_holds_the_paths_and_repos_the_marker_allows(tmp_path):
    marker = MARKER + 'allow = ["~/.claude", "/opt/tool", "acme/archived"]\n'

    home = find_home(_home(tmp_path / "home", marker), {})

    assert home.leak_allow_paths == ("~/.claude", "/opt/tool")
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


def test_mw_home_alone_finds_the_home_from_outside_its_tree(tmp_path):
    root = _home(tmp_path / "home")
    project = tmp_path / "project"
    project.mkdir()

    assert find_home(project, {"MW_HOME": str(root)}).root == root.resolve()


def test_mw_home_written_from_another_users_home_directory_finds_the_home(tmp_path, monkeypatch):
    root = _home(tmp_path / "other" / "home")
    users = {"other": SimpleNamespace(pw_dir=str(tmp_path / "other"))}
    monkeypatch.setattr(pwd, "getpwnam", users.__getitem__)

    assert find_home(tmp_path, {"MW_HOME": "~other/home"}).root == root.resolve()


def test_mw_home_and_the_marker_agreeing_is_the_home(tmp_path):
    root = _home(tmp_path / "home")

    assert find_home(root, {"MW_HOME": str(root)}).root == root.resolve()


def test_mw_home_and_the_marker_disagreeing_is_refused_naming_only_mw_homes_root(tmp_path):
    first = _home(tmp_path / "first")
    second = _home(tmp_path / "second" / "deep")

    with pytest.raises(RefusalError) as refusal:
        find_home(second, {"MW_HOME": str(first)})

    message = str(refusal.value)
    assert f"MW_HOME names {first.resolve()}" in message
    assert f"fix: run kaizen from inside {first.resolve()}" in message
    assert "second" not in message


def test_a_linked_git_worktree_of_mw_home_counts_as_that_home(tmp_path):
    # A ticket worktree of the home sits in its tree and carries its own copy of the marker.
    root = _home(tmp_path / "home")
    worktree = _home(root / ".claude" / "worktrees" / "fix-7-x")
    (worktree / ".git").write_text(f"gitdir: {root}/.git/worktrees/fix-7-x\n")

    assert find_home(worktree, {"MW_HOME": str(root)}).root == root.resolve()


def test_a_git_worktree_of_another_repo_inside_mw_homes_tree_is_still_refused(tmp_path):
    root = _home(tmp_path / "home")
    other = _home(root / "nested")
    (other / ".git").write_text(f"gitdir: {tmp_path}/elsewhere/.git/worktrees/nested\n")

    with pytest.raises(RefusalError, match="MW_HOME"):
        find_home(other, {"MW_HOME": str(root)})


def test_neither_finding_a_home_is_refused_with_a_fix_naming_both(tmp_path):
    with pytest.raises(RefusalError, match=r"no home(.|\n)*fix:.*MW_HOME.*mw\.toml"):
        find_home(tmp_path, {})


def test_mw_home_naming_a_directory_without_a_marker_is_refused(tmp_path):
    with pytest.raises(RefusalError, match=r"MW_HOME(.|\n)*mw\.toml"):
        find_home(tmp_path, {"MW_HOME": str(tmp_path / "nowhere")})


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

    with pytest.raises(RefusalError, match=rf"mw\.toml(.|\n)*{reason}"):
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
    refusal = rf"mw\.toml is malformed: [^\n]*{re.escape(reason)}[^\n]*\n  fix: fix .*mw\.toml"

    with pytest.raises(RefusalError, match=refusal):
        find_home(root, {})


def test_a_configured_colour_is_read_lowercased(tmp_path):
    root = _home(tmp_path / "home", MARKER + _LABEL.replace("fbca04", "FBCA04"))

    assert find_home(root, {}).workflow_labels == (Label("triage", "fbca04", "Look"),)


def test_fresh_home_is_the_home_find_home_reads_from_the_fresh_marker(tmp_path):
    root = _home(tmp_path / "home", fresh_marker("acme/home", "/fixture/acme")).resolve()

    assert fresh_home(root, "acme/home", "/fixture/acme") == find_home(root, {})
