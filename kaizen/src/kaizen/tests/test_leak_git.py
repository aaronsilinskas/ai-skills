"""Tests for the **leak check**'s rules, run against a real git checkout.

Each test commits text to a fresh repo under ``tmp_path`` and runs the check with the real
runner, inside a fixture home whose user directory is also under ``tmp_path``, so ``~`` never
means the real home directory.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError, run_subprocess
from kaizen.shared.home import Home
from kaizen.shared.leak import leak_check
from kaizen.tests.leak_home import leak_home, leak_user
from kaizen.tests.real_git import git
from kaizen.tests.ticket_shell import TILDE

VISIBILITY = pytest.mark.parametrize("public", [True, False], ids=["public", "private"])


@pytest.fixture
def user(tmp_path: Path) -> Path:
    return leak_user(tmp_path)


@pytest.fixture
def home(user: Path) -> Home:
    return leak_home(user)


def _checkout(tmp_path: Path, text: str, name: str = "notes.md") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / name).write_text(text)
    git("-C", repo, "init", "-q")
    git("-C", repo, "add", ".")
    return repo


def _check(tmp_path: Path, home: Home, user: Path, text: str, public: bool) -> None:
    leak_check(_checkout(tmp_path, text), home, run_subprocess, public=public, user_home=user)


def _refused(tmp_path, home, user, text, public) -> str:
    with pytest.raises(RefusalError) as refusal:
        _check(tmp_path, home, user, text, public)
    return str(refusal.value)


@VISIBILITY
def test_a_tilde_path_outside_the_home_and_its_projects_is_refused_naming_file_line_rule_fix(
    tmp_path, home, user, public
):
    refusal = _refused(tmp_path, home, user, f"intro\nsee {TILDE}/dev/elsewhere/notes\n", public)

    assert f"notes.md:2: outside path {TILDE}/dev/elsewhere/notes" in refusal
    assert "register the project that holds it, add it to leak.allow in the home's kaizen.toml" in (
        refusal
    )


@VISIBILITY
def test_a_path_under_the_users_home_directory_outside_the_home_is_refused(
    tmp_path, home, user, public
):
    refusal = _refused(tmp_path, home, user, f"see {user}/private/plans.md\n", public)

    assert f"notes.md:1: outside path {user}/private/plans.md" in refusal


@pytest.mark.parametrize(
    ("text", "path"),
    [
        ("open file://{user}/private/plans.md", "{user}/private/plans.md"),
        ("alias @{user}/private/src", "{user}/private/src"),
        ("glued/{user}/private/x", "{user}/private/x"),
        ("glued{user}/private/x", "{user}/private/x"),
        ("glued/{tilde}/private/x", "{tilde}/private/x"),
    ],
    ids=[
        "file URL",
        "after @",
        "user path after /",
        "user path after a letter",
        "tilde after /",
    ],
)
def test_an_outside_path_is_found_whatever_comes_before_it(tmp_path, home, user, text, path):
    text, path = (t.format(user=user, tilde=TILDE) for t in (text, path))

    refusal = _refused(tmp_path, home, user, text + "\n", public=False)

    assert f"notes.md:1: outside path {path} (fix:" in refusal


@VISIBILITY
def test_a_repo_under_a_home_owner_that_is_not_registered_is_refused_with_register_it(
    tmp_path, home, user, public
):
    refusal = _refused(tmp_path, home, user, "see https://github.com/owner/secret/pull/3\n", public)

    assert "notes.md:1: unregistered repo owner/secret" in refusal
    assert "register it in the home's registry, add it to leak.allow" in refusal


@VISIBILITY
def test_a_bare_owner_repo_reference_to_an_unregistered_repo_is_refused(
    tmp_path, home, user, public
):
    refusal = _refused(tmp_path, home, user, "fixed in Owner/Secret#12.\n", public)

    assert "unregistered repo Owner/Secret" in refusal


@VISIBILITY
@pytest.mark.parametrize(
    "text",
    [
        "{tilde}/dev/home/docs/index.md",
        "{tilde}/dev/proto/src/main.py",
        "{tilde}/trees/site/fix-3-thing",
        "{user}/work/site/README.md",
        "{tilde}/dev and ~/ and {tilde}/dev/... hold it",
        "owner/proto#4 and https://github.com/owner/site.git",
        "third/party and https://github.com/astral-sh/uv",
        "ends with owner/proto.",
        "s.replace(/~~/g, '').replace(/~(.*?)~/g, '$1')",
        "see ~/… for the path",
    ],
    ids=[
        "home root",
        "project path",
        "worktree root",
        "absolute project path",
        "ancestors",
        "registered repos",
        "third-party owners",
        "registered repo before a full stop",
        "tilde in a regex",
        "ellipsis",
    ],
)
def test_text_inside_the_home_passes(tmp_path, home, user, public, text):
    _check(tmp_path, home, user, text.format(user=user, tilde=TILDE) + "\n", public)


@VISIBILITY
def test_paths_and_repos_the_home_allows_pass(tmp_path, home, user, public):
    home = replace(
        home,
        leak_allow_paths=(f"{TILDE}/.tool", f"{user}/Library/Tool"),
        leak_allow_repos=("owner/archived",),
    )
    text = f"{TILDE}/.tool/settings.json, {user}/Library/Tool/x and github.com/owner/archived\n"

    _check(tmp_path, home, user, text, public)


def test_an_allowed_path_covers_only_what_is_under_it(tmp_path, home, user):
    home = replace(home, leak_allow_paths=(f"{TILDE}/.tool",))

    refusal = _refused(tmp_path, home, user, f"{TILDE}/.toolbox/x\n", public=False)

    assert f"outside path {TILDE}/.toolbox/x" in refusal


def test_an_own_reference_is_refused_in_a_public_project(tmp_path, home, user):
    refusal = _refused(tmp_path, home, user, "part of owner/home\n", public=True)

    assert "notes.md:1: own reference owner/home" in refusal
    assert "name skills instead of linking the home's files" in refusal


def test_an_own_reference_passes_in_a_private_project(tmp_path, home, user):
    home = Home(home.root, home.registry, leak_own=("home-secret",))

    _check(tmp_path, home, user, "part of home-secret\n", public=False)


def test_every_offending_line_is_listed(tmp_path, home, user):
    text = f"{TILDE}/a/b\nfine\nowner/nope and {TILDE}/c\n"

    refusal = _refused(tmp_path, home, user, text, public=False)

    assert f"notes.md:1: outside path {TILDE}/a/b" in refusal
    assert "notes.md:3: unregistered repo owner/nope" in refusal
    assert f"notes.md:3: outside path {TILDE}/c" in refusal


def test_an_outside_path_naming_a_home_owner_is_reported_once_as_a_path(tmp_path, home, user):
    refusal = _refused(tmp_path, home, user, f"see {TILDE}/src/owner/secret\n", public=False)

    assert f"outside path {TILDE}/src/owner/secret" in refusal
    assert "unregistered repo" not in refusal


def test_a_clean_checkout_passes(tmp_path, home, user):
    _check(tmp_path, home, user, "nothing to see\n", public=True)


def test_given_a_revision_it_searches_that_commits_tree(tmp_path, home, user):
    repo = _checkout(tmp_path, f"see {TILDE}/outside\n")
    author = ("-c", "user.name=t", "-c", "user.email=t@t")
    git("-C", repo, *author, "commit", "-q", "-m", "c")
    (repo / "notes.md").write_text("clean now\n")
    git("-C", repo, *author, "commit", "-q", "-am", "clean")

    leak_check(repo, home, run_subprocess, public=True, user_home=user)
    with pytest.raises(RefusalError, match=rf"notes\.md:1: outside path {TILDE}/outside"):
        leak_check(repo, home, run_subprocess, "HEAD~1", public=True, user_home=user)


def _staged_and_working_tree(tmp_path: Path, staged: str, working: str) -> Path:
    """A checkout whose ``notes.md`` holds *staged* in the index and *working* on disk."""
    repo = _checkout(tmp_path, staged)
    (repo / "notes.md").write_text(working)
    return repo


def test_staged_it_searches_the_index_not_the_working_tree(tmp_path, home, user):
    repo = _staged_and_working_tree(tmp_path, f"see {TILDE}/outside\n", "clean now\n")

    with pytest.raises(RefusalError) as refusal:
        leak_check(repo, home, run_subprocess, public=True, staged=True, user_home=user)
    assert str(refusal.value).startswith(
        "leak check: committed text points outside this home:\n"
        f"  notes.md:1: outside path {TILDE}/outside (fix: register the project"
    )


def test_staged_it_ignores_a_leak_only_in_the_working_tree(tmp_path, home, user):
    repo = _staged_and_working_tree(tmp_path, "clean\n", f"see {TILDE}/outside\n")

    leak_check(repo, home, run_subprocess, public=True, staged=True, user_home=user)


def test_staged_and_a_revision_together_are_a_programming_error(tmp_path, home, user):
    repo = _checkout(tmp_path, "clean\n")

    with pytest.raises(ValueError, match="staged"):
        leak_check(repo, home, run_subprocess, "HEAD", public=True, staged=True, user_home=user)
