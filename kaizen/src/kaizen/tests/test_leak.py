"""Tests for the **leak check**'s rules, run against a real git checkout.

Each test commits text to a fresh repo under ``tmp_path`` and runs the check with the real
runner, inside a fixture home whose user directory is also under ``tmp_path``, so ``~`` never
means the real home directory.
"""

import re
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError, run_subprocess
from kaizen.shared.home import Home
from kaizen.shared.leak import leak_check, leak_check_text
from kaizen.tests.ticket_shell import TILDE


@pytest.fixture
def user(tmp_path: Path) -> Path:
    """The user's home directory: ``~`` in committed text means this."""
    return tmp_path / "Users" / "someone"


@pytest.fixture
def home(user: Path, tmp_path: Path) -> Home:
    """A home at ``dev/home`` in the user's directory, registering ``proto`` (``dev/proto``,
    ``owner/proto``) and ``site`` (``work/site``, ``owner/site``, worktrees under ``trees/site``),
    both also in the user's directory."""
    root = user / "dev" / "home"
    projects = root / "projects"
    projects.mkdir(parents=True)
    proto = f"path: {user}/dev/proto\ngithub: owner/proto\npublic: true\n"
    (projects / "proto.md").write_text(f"---\n{proto}---\n")
    site = f"path: {user}/work/site\ngithub: owner/site\npublic: false\n"
    (projects / "site.md").write_text(f"---\n{site}worktree_root: {user}/trees/site\n---\n")
    return Home(root=root, registry=projects, leak_own=("owner/home",))


def _checkout(tmp_path: Path, text: str, name: str = "notes.md") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / name).write_text(text)
    for cmd in (["init", "-q"], ["add", "."]):
        subprocess.run(["git", "-C", str(repo), *cmd], check=True)
    return repo


def _check(tmp_path: Path, home: Home, user: Path, text: str, public: bool) -> None:
    leak_check(_checkout(tmp_path, text), home, run_subprocess, public=public, user_home=user)


def _refused(tmp_path, home, user, text, public) -> str:
    with pytest.raises(RefusalError) as refusal:
        _check(tmp_path, home, user, text, public)
    return str(refusal.value)


VISIBILITY = pytest.mark.parametrize("public", [True, False], ids=["public", "private"])


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
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "commit", "-q", "-m", "c"], check=True)
    (repo / "notes.md").write_text("clean now\n")
    subprocess.run([*git, "commit", "-q", "-am", "clean"], check=True)

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


def _text_refused(home: Home, user: Path, texts: dict[str, str], public: bool) -> str:
    with pytest.raises(RefusalError) as refusal:
        leak_check_text(texts, home, public=public, user_home=user)
    return str(refusal.value)


@VISIBILITY
def test_text_pointing_outside_the_home_is_refused_naming_the_text_line_rule_and_fix(
    home, user, public
):
    texts = {"PR title": "Fix it", "PR body": f"Why.\nsee {TILDE}/dev/elsewhere and owner/secret\n"}

    refusal = _text_refused(home, user, texts, public)

    assert "leak check: text for GitHub points outside this home" in refusal
    assert f"PR body line 2: outside path {TILDE}/dev/elsewhere (fix: register the project" in (
        refusal
    )
    assert "PR body line 2: unregistered repo owner/secret (fix: register it" in refusal
    assert "PR title" not in refusal


def test_an_own_reference_in_text_is_refused_for_a_public_project(home, user):
    refusal = _text_refused(home, user, {"issue body": "part of owner/home\n"}, public=True)

    assert "issue body line 1: own reference owner/home" in refusal


def test_an_own_reference_in_text_passes_for_a_private_project(home, user):
    home = replace(home, leak_own=("home-secret",))

    leak_check_text({"issue body": "part of home-secret\n"}, home, public=False, user_home=user)


@VISIBILITY
def test_text_naming_only_registered_paths_registered_repos_and_third_parties_passes(
    home, user, public
):
    text = f"{TILDE}/dev/proto/src, {user}/work/site, owner/proto#4 and astral-sh/uv\n"

    leak_check_text({"PR body": text}, home, public=public, user_home=user)


BARE_ISSUE_REF = re.compile(r"(^|[^\w/.-])#[0-9]+")
"""A ``leak_deny`` entry for an issue ref with no repo before it."""

ZEPHYR = re.compile("zephyr", re.IGNORECASE)
"""A ``leak_deny`` entry, compiled case-insensitive as the registry compiles each."""


def _repo_with_added(tmp_path: Path, tree: str, added: str) -> Path:
    """A checkout whose base commit (tag ``base``) holds *tree* in ``notes.md``, and whose next
    commit appends *added* to it."""
    repo = _checkout(tmp_path, tree)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "commit", "-q", "-m", "base"], check=True)
    subprocess.run([*git, "tag", "base"], check=True)
    (repo / "notes.md").write_text(tree + added)
    subprocess.run([*git, "commit", "-q", "-am", "added"], check=True)
    return repo


def _deny_check(
    repo: Path, home: Home, user: Path, denied: tuple[re.Pattern[str], ...], **source
) -> None:
    leak_check(repo, home, run_subprocess, public=False, denied=denied, user_home=user, **source)


@VISIBILITY
def test_a_denied_pattern_on_an_added_line_is_refused_naming_file_line_rule_and_fix(
    tmp_path, home, user, public
):
    repo = _repo_with_added(tmp_path, "intro\n", "the Zephyr board\n")

    with pytest.raises(RefusalError) as refusal:
        leak_check(
            repo,
            home,
            run_subprocess,
            public=public,
            denied=(ZEPHYR,),
            base="base",
            user_home=user,
        )

    assert (
        "notes.md:2: denied pattern Zephyr"
        " (fix: remove the text, or change the project's leak_deny)" in str(refusal.value)
    )


def test_a_denied_word_already_in_the_tree_passes(tmp_path, home, user):
    repo = _repo_with_added(tmp_path, "the zephyr board\n", "more notes\n")

    _deny_check(repo, home, user, (ZEPHYR,), base="base")


def test_without_denied_patterns_an_added_line_is_not_searched_for_them(tmp_path, home, user):
    repo = _repo_with_added(tmp_path, "intro\n", "the zephyr board\n")

    _deny_check(repo, home, user, (), base="base")


def test_a_bare_issue_ref_is_refused_while_one_naming_its_repo_passes(tmp_path, home, user):
    repo = _repo_with_added(tmp_path, "intro\n", "see owner/proto#12\nand #12\n")

    with pytest.raises(RefusalError) as refusal:
        _deny_check(repo, home, user, (BARE_ISSUE_REF,), base="base")

    assert "notes.md:3: denied pattern #12" in str(refusal.value)
    assert "notes.md:2" not in str(refusal.value)


def test_given_a_revision_and_a_base_it_searches_the_lines_the_revision_adds(tmp_path, home, user):
    repo = _repo_with_added(tmp_path, "intro\n", "the zephyr board\n")
    (repo / "notes.md").write_text("intro\n")  # the working tree drops the added line

    with pytest.raises(RefusalError, match=r"notes\.md:2: denied pattern zephyr"):
        _deny_check(repo, home, user, (ZEPHYR,), revision="HEAD", base="base")


def test_staged_it_searches_the_lines_the_index_adds(tmp_path, home, user):
    repo = _repo_with_added(tmp_path, "the zephyr board\n", "intro\n")
    (repo / "notes.md").write_text("the zephyr board\nintro\nan zephyr note\n")
    subprocess.run(["git", "-C", str(repo), "add", "notes.md"], check=True)

    with pytest.raises(RefusalError) as refusal:
        _deny_check(repo, home, user, (ZEPHYR,), staged=True)

    assert "notes.md:3: denied pattern zephyr" in str(refusal.value)
    assert "notes.md:1" not in str(refusal.value)


def test_a_denied_pattern_in_text_for_github_is_refused_naming_the_text_line_and_fix(home, user):
    with pytest.raises(RefusalError) as refusal:
        leak_check_text(
            {"PR body": "Fixes it.\nsee #12\n"},
            home,
            public=True,
            denied=(BARE_ISSUE_REF,),
            user_home=user,
        )

    assert (
        "PR body line 2: denied pattern #12"
        " (fix: remove the text, or change the project's leak_deny)" in str(refusal.value)
    )


def test_added_lines_keep_their_numbers_when_the_users_config_joins_hunks(tmp_path, home, user):
    tree = "".join(f"line {n}\n" for n in range(1, 6))
    repo = _repo_with_added(tmp_path, tree, "line 6\n")
    edited = tree.replace("line 1", "one").replace("line 5", "zephyr five")
    (repo / "notes.md").write_text(edited + "line 6\n")
    subprocess.run(["git", "-C", str(repo), "config", "diff.interHunkContext", "5"], check=True)

    with pytest.raises(RefusalError, match=r"notes\.md:5: denied pattern zephyr"):
        _deny_check(repo, home, user, (ZEPHYR,), base="HEAD")


def test_a_file_name_holding_a_space_is_named_as_it_is(tmp_path, home, user):
    repo = _repo_with_added(tmp_path, "intro\n", "more\n")
    (repo / "my notes.md").write_text("a zephyr\n")
    subprocess.run(["git", "-C", str(repo), "add", "my notes.md"], check=True)

    with pytest.raises(RefusalError) as refusal:
        _deny_check(repo, home, user, (ZEPHYR,), staged=True)

    assert "  my notes.md:1: denied pattern zephyr (fix:" in str(refusal.value)
