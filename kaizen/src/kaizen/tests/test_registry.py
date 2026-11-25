"""Tests for the project registry's ``check`` key, read through ``resolve`` and ``all_projects``.

Pages are written to a temporary ``projects/`` directory.
"""

from pathlib import Path

import pytest

from kaizen.shared import registry
from kaizen.shared.common import RefusalError
from kaizen.shared.registry import resolve, starter_readme

BASE = "path: /p\ngithub: owner/proto\npublic: true\n"


def _projects(tmp_path: Path, frontmatter: str) -> Path:
    directory = tmp_path / "projects"
    directory.mkdir()
    (directory / "proto.md").write_text(f"---\n{frontmatter}---\n# proto\n")
    return directory


def test_a_page_exposes_its_check_command(tmp_path):
    projects = _projects(tmp_path, BASE + "check: npm ci && npm run check\n")

    assert resolve("proto", projects).check == "npm ci && npm run check"


def test_a_page_without_a_check_still_resolves_with_none(tmp_path):
    assert resolve("proto", _projects(tmp_path, BASE)).check is None


@pytest.mark.parametrize(("value", "shown"), [("", "''"), ("true", "True"), ("''", "''")])
def test_a_non_string_or_empty_check_is_refused(tmp_path, value, shown):
    projects = _projects(tmp_path, BASE + f"check: {value}\n")

    with pytest.raises(RefusalError, match=rf"proto\.md: field 'check' is {shown}"):
        resolve("proto", projects)


def test_a_page_exposes_its_code_paths_as_a_comma_separated_list(tmp_path):
    projects = _projects(tmp_path, BASE + "code_paths: src/, tests/,package.json\n")

    assert resolve("proto", projects).code_paths == ("src/", "tests/", "package.json")


def test_a_page_without_code_paths_resolves_with_none(tmp_path):
    assert resolve("proto", _projects(tmp_path, BASE)).code_paths is None


def test_a_page_exposes_its_auto_merge_paths_as_a_comma_separated_list(tmp_path):
    projects = _projects(tmp_path, BASE + "auto_merge_paths: docs/, guides/,CHANGELOG.md\n")

    assert resolve("proto", projects).auto_merge_paths == ("docs/", "guides/", "CHANGELOG.md")


def test_a_page_without_auto_merge_paths_resolves_with_none(tmp_path):
    assert resolve("proto", _projects(tmp_path, BASE)).auto_merge_paths is None


def test_a_page_opts_in_to_auto_merging_comment_only_changes(tmp_path):
    projects = _projects(tmp_path, BASE + "auto_merge_comment_only: true\n")

    assert resolve("proto", projects).auto_merge_comment_only is True


def test_a_page_without_auto_merge_comment_only_does_not_auto_merge_comment_only_changes(tmp_path):
    assert resolve("proto", _projects(tmp_path, BASE)).auto_merge_comment_only is False


def test_a_page_refuses_an_auto_merge_comment_only_that_is_not_true_or_false(tmp_path):
    projects = _projects(tmp_path, BASE + "auto_merge_comment_only: yes\n")

    with pytest.raises(RefusalError, match="auto_merge_comment_only"):
        resolve("proto", projects)


def test_a_page_without_worktree_links_resolves_with_no_links(tmp_path):
    assert resolve("proto", _projects(tmp_path, BASE)).worktree_links == ()


@pytest.mark.parametrize("entry", ["/opt/mpy-cross", "../other/tools", "tools/../../x"])
def test_a_worktree_link_outside_the_project_root_is_refused(tmp_path, entry):
    projects = _projects(tmp_path, BASE + f"worktree_links: tools/mpy-cross, {entry}\n")

    with pytest.raises(RefusalError, match=rf"proto\.md: worktree_links entry '{entry}'"):
        resolve("proto", projects)


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("engine/clock.py", True),
        ("pyproject.toml", True),
        (".github/x.yml", True),
        ("docs/adr/0001-x.md", False),
        ("README.md", False),
        ("pyproject.toml.bak", False),
        ("engine-notes.md", False),
    ],
)
def test_a_code_path_ending_in_a_slash_covers_a_directory_and_any_other_names_one_file(
    tmp_path, path, code
):
    projects = _projects(tmp_path, BASE + "code_paths: engine/, pyproject.toml, .github/\n")

    assert resolve("proto", projects).is_code(path) is code


@pytest.mark.parametrize(
    ("path", "code"),
    [("code.py", True), (".hidden.py", True), ("lib/x.py", False), ("code.pyc", False)],
)
def test_a_glob_code_path_matches_root_files_and_its_star_never_crosses_a_slash(
    tmp_path, path, code
):
    projects = _projects(tmp_path, BASE + "code_paths: *.py\n")

    assert resolve("proto", projects).is_code(path) is code


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("x.py", True),
        ("a/b/x.py", True),
        ("docs/guide.md", True),
        ("docs/adr/0001-x.md", True),
        ("docs", False),
        ("README.md", False),
    ],
)
def test_a_double_star_glob_segment_matches_any_number_of_directories(tmp_path, path, code):
    projects = _projects(tmp_path, BASE + "code_paths: **/*.py, docs/**\n")

    assert resolve("proto", projects).is_code(path) is code


@pytest.mark.parametrize(
    ("path", "code"),
    [("pkg/x.py", True), ("pkg_extra/a/b.json", True), ("pkg.toml", False), ("lib/pkg/x", False)],
)
def test_a_glob_ending_in_a_slash_covers_everything_under_each_directory_it_matches(
    tmp_path, path, code
):
    projects = _projects(tmp_path, BASE + "code_paths: pkg*/\n")

    assert resolve("proto", projects).is_code(path) is code


@pytest.mark.parametrize(
    ("path", "code"), [("v1.txt", True), ("v10.txt", False), ("v/.txt", False)]
)
def test_a_glob_question_mark_matches_one_character_within_a_segment(tmp_path, path, code):
    projects = _projects(tmp_path, BASE + "code_paths: v?.txt\n")

    assert resolve("proto", projects).is_code(path) is code


@pytest.mark.parametrize(
    ("path", "code"),
    [("src/[id].astro", True), ("src/i.astro", False), ("src/[slug]/x.astro", True)],
)
def test_brackets_in_a_code_path_are_literal_in_a_plain_entry_and_in_a_glob(tmp_path, path, code):
    projects = _projects(tmp_path, BASE + "code_paths: src/[id].astro, src/[slug]/*.astro\n")

    assert resolve("proto", projects).is_code(path) is code


def test_a_glob_worktree_link_is_refused(tmp_path):
    projects = _projects(tmp_path, BASE + "worktree_links: tools/*\n")

    with pytest.raises(RefusalError, match=r"proto\.md: worktree_links entry 'tools/\*' is a glob"):
        resolve("proto", projects)


class _KeysRead(dict):
    """A page's frontmatter that records every key the parser asks about, present or not."""

    def __init__(self, fields, read):
        super().__init__(fields)
        self.read = read

    def __contains__(self, key):
        self.read.add(key)
        return super().__contains__(key)

    def __getitem__(self, key):
        self.read.add(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self.read.add(key)
        return super().get(key, default)


def keys_the_parser_reads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> set[str]:
    """Every key the registry parser asks a page about, present or not."""
    read: set[str] = set()
    frontmatter = registry._frontmatter
    monkeypatch.setattr(registry, "_frontmatter", lambda page: _KeysRead(frontmatter(page), read))
    resolve("proto", _projects(tmp_path, BASE))
    assert {"path", "github", "public", "check"} <= read
    return read


def test_the_starter_readme_describes_every_key_the_parser_reads(tmp_path, monkeypatch):
    read = keys_the_parser_reads(tmp_path, monkeypatch)

    readme = starter_readme([])
    assert sorted(key for key in read if f"- `{key}` (" not in readme) == []


def test_a_page_lists_its_denied_patterns_compiled(tmp_path):
    projects = _projects(tmp_path, BASE + r"leak_deny: zephyr, internal/, (^|[^\w/])#[0-9]+" + "\n")

    denied = resolve("proto", projects).leak_deny

    assert [pattern.pattern for pattern in denied] == ["zephyr", "internal/", r"(^|[^\w/])#[0-9]+"]


def test_a_denied_pattern_matches_case_insensitively(tmp_path):
    projects = _projects(tmp_path, BASE + "leak_deny: zephyr\n")

    (denied,) = resolve("proto", projects).leak_deny

    assert denied.match("ZEPHYR")


def test_a_page_without_leak_deny_denies_nothing(tmp_path):
    assert resolve("proto", _projects(tmp_path, BASE)).leak_deny == ()


@pytest.mark.parametrize("pattern", ["(unclosed", "[[:alpha:]]"])
def test_a_denied_pattern_that_does_not_compile_is_refused_naming_the_page(tmp_path, pattern):
    projects = _projects(tmp_path, BASE + f"leak_deny: zephyr, {pattern}\n")

    with pytest.raises(RefusalError) as refusal:
        resolve("proto", projects)

    assert f"proto.md: leak_deny entry '{pattern}' is not a regular expression" in str(
        refusal.value
    )


@pytest.mark.parametrize("key", ["path", "worktree_root"])
def test_a_relative_path_is_refused_naming_the_page_and_key(tmp_path, key):
    frontmatter = BASE.replace("path: /p", "path: p") if key == "path" else BASE + f"{key}: p\n"

    with pytest.raises(RefusalError, match=rf"proto\.md: field '{key}' is 'p', not an absolute"):
        resolve("proto", _projects(tmp_path, frontmatter))


def test_invalid_pages_lists_each_bad_page_and_skips_good_ones_and_the_readme(tmp_path):
    projects = _projects(tmp_path, BASE)
    (projects / "README.md").write_text("# Projects\n")
    (projects / "a.md").write_text("# none\n")
    (projects / "b.md").write_text("---\npath: /b\n---\n")

    found = registry.invalid_pages(projects)

    assert [(page.name, refusal.check) for page, refusal in found] == [
        ("a.md", f"{projects / 'a.md'}: no registry frontmatter"),
        ("b.md", f"{projects / 'b.md'}: missing field 'github'"),
    ]
