"""Tests for the ``kaizen hook`` group: the pre-commit hooks, run through the CLI from a fixture
home on files written to a temporary directory, with git replaced by a recording runner."""

from pathlib import Path

import pytest

from kaizen.shared.cli import main
from kaizen.tests.ticket_shell import RELAY, Reply, Shell, failed

EM_DASH = "\u2014"
EN_DASH = "\u2013"
CURLY_QUOTES = "\u2018\u2019\u201c\u201d"

HOOKS = ["leak-check", "no-commit-to-branch", "prose-marks", "section-banners", "work-tracking"]


def _file(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / "files" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_hook_help_lists_the_five_hooks(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["hook", "--help"], cwd=tmp_path, env={})

    out = capsys.readouterr().out
    for hook in HOOKS:
        assert hook in out


def test_an_em_dash_in_markdown_is_refused_naming_file_line_and_rule(tmp_path, kaizen, capsys):
    path = _file(tmp_path, "a.md", f"fine\nnot {EM_DASH} fine\n")

    assert kaizen(["hook", "prose-marks", path], Shell({})) == 1

    err = capsys.readouterr().err
    assert f"{path}:2: prose mark em dash" in err
    assert f"{path}:1" not in err


@pytest.mark.parametrize("mark", list(CURLY_QUOTES))
def test_each_curly_quote_in_markdown_is_refused(tmp_path, kaizen, capsys, mark):
    path = _file(tmp_path, "a.md", f"a {mark}quote\n")

    assert kaizen(["hook", "prose-marks", path], Shell({})) == 1

    assert f"{path}:1: prose mark" in capsys.readouterr().err


def test_en_dashes_and_plain_marks_pass(tmp_path, kaizen):
    path = _file(tmp_path, "a.md", f"pages 1{EN_DASH}5, \"plain\" and 'plain' - fine\n")

    assert kaizen(["hook", "prose-marks", path], Shell({})) == 0


def test_prose_marks_skips_a_file_that_is_not_markdown(tmp_path, kaizen):
    path = _file(tmp_path, "a.py", f'TEXT = "{EM_DASH}"\n')

    assert kaizen(["hook", "prose-marks", path], Shell({})) == 0


def test_every_offending_file_is_listed_in_one_refusal(tmp_path, kaizen, capsys):
    first = _file(tmp_path, "a.md", f"{EM_DASH}\n")
    second = _file(tmp_path, "b.md", f"ok\n{EM_DASH}\n")

    assert kaizen(["hook", "prose-marks", first, second], Shell({})) == 1

    err = capsys.readouterr().err
    assert f"{first}:1:" in err
    assert f"{second}:2:" in err


@pytest.mark.parametrize("hook", HOOKS)
def test_a_hook_run_outside_any_home_is_refused_with_the_kaizen_home_fix(tmp_path, capsys, hook):
    path = _file(tmp_path, "a.md", "fine\n")

    assert main(["hook", hook, path], run=Shell({}), cwd=tmp_path, env={}) == 1

    err = capsys.readouterr().err
    assert "refused: home: no home found" in err
    assert "set KAIZEN_HOME to the root of the home" in err


COMMENTED = {
    "a.py": "# {}\n",
    "a.sh": "# {}\n",
    "a.yaml": "# {}\n",
    "a.toml": "# {}\n",
    "a.c": "// {}\n",
    "a.ts": "// {}\n",
    "a.kt": "// {}\n",
    "a.rs": "// {}\n",
    "a.sql": "-- {}\n",
    "a.lua": "-- {}\n",
}
"""A one-line file per supported language, a comment holding the ``{}`` text."""


def _commented(tmp_path: Path, name: str, comment: str) -> str:
    return _file(tmp_path, name, "x = 1\n" + COMMENTED[name].format(comment))


@pytest.mark.parametrize("name", list(COMMENTED))
@pytest.mark.parametrize("banner", ["-" * 10, "=" * 24, "--- name ---", "=== Setup ==="])
def test_a_banner_comment_is_refused_in_each_language(tmp_path, kaizen, capsys, name, banner):
    path = _commented(tmp_path, name, banner)

    assert kaizen(["hook", "section-banners", path], Shell({})) == 1

    assert f"{path}:2: section banner" in capsys.readouterr().err


@pytest.mark.parametrize("name", list(COMMENTED))
@pytest.mark.parametrize("comment", ["-" * 9, "a plain comment", "x --- y", "see --help"])
def test_a_comment_that_is_no_banner_passes(tmp_path, kaizen, name, comment):
    path = _commented(tmp_path, name, comment)

    assert kaizen(["hook", "section-banners", path], Shell({})) == 0


@pytest.mark.parametrize("line", ["-" * 12, "--- name ---"])
def test_a_sql_banner_written_with_the_prefix_as_its_rule_is_refused(tmp_path, kaizen, line):
    path = _file(tmp_path, "a.sql", f"select 1;\n{line}\n")

    assert kaizen(["hook", "section-banners", path], Shell({})) == 1


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("a.py", 'RULE = "# ' + "-" * 20 + '"\nTITLE = """\n# --- name ---\n"""\n'),
        ("a.py", "x = 1  - 2\n"),
        ("a.ts", 'const rule = "' + "=" * 20 + '";\n'),
    ],
)
def test_banner_text_in_strings_and_code_passes(tmp_path, kaizen, name, text):
    path = _file(tmp_path, name, text)

    assert kaizen(["hook", "section-banners", path], Shell({})) == 0


@pytest.mark.parametrize("hook", ["section-banners", "work-tracking"])
def test_a_file_of_an_unknown_language_is_skipped(tmp_path, kaizen, hook):
    path = _file(tmp_path, "notes.txt", "# " + "-" * 20 + "\n# fixed in a later ticket\n")

    assert kaizen(["hook", hook, path], Shell({})) == 0


def test_python_the_tokenizer_cant_read_is_skipped(tmp_path, kaizen):
    path = _file(tmp_path, "a.py", 'x = """never closed\n# ' + "-" * 20 + "\n")

    assert kaizen(["hook", "section-banners", path], Shell({})) == 0


@pytest.mark.parametrize("name", list(COMMENTED))
@pytest.mark.parametrize(
    ("comment", "match"),
    [
        ("done in a later ticket", "later ticket"),
        ("see Slice 3 for the rest", "Slice 3"),
        ("tracked as issue 42", "issue 42"),
        ("tracked as issue #42", "issue #42"),
        ("works around #42", "#42"),
    ],
)
def test_a_work_tracking_reference_in_a_comment_is_refused_in_each_language(
    tmp_path, kaizen, capsys, name, comment, match
):
    path = _commented(tmp_path, name, comment)

    assert kaizen(["hook", "work-tracking", path], Shell({})) == 1

    assert f"{path}:2: work-tracking reference {match}" in capsys.readouterr().err


@pytest.mark.parametrize("name", list(COMMENTED))
@pytest.mark.parametrize(
    "comment",
    [
        "works around owner/repo#42",
        "see https://github.com/owner/repo/issues/42",
        "a ticket worktree, sliced 3 ways",
        "colour #ff0000",
    ],
)
def test_full_references_urls_and_other_text_pass(tmp_path, kaizen, name, comment):
    path = _commented(tmp_path, name, comment)

    assert kaizen(["hook", "work-tracking", path], Shell({})) == 0


def test_a_python_comment_that_starts_with_an_issue_number_is_refused(tmp_path, kaizen):
    path = _file(tmp_path, "a.py", "x = 1  #42\n")

    assert kaizen(["hook", "work-tracking", path], Shell({})) == 1


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("a.py", 'assert out == "closed #42 in a later ticket"\n'),
        ("a.py", 'URL = "issue 42"  # the issue URL\n'),
        ("a.sh", 'echo "see issue 42"\n'),
        ("a.ts", 'const ref = "#42";\n'),
    ],
)
def test_issue_text_in_strings_and_code_passes(tmp_path, kaizen, name, text):
    path = _file(tmp_path, name, text)

    assert kaizen(["hook", "work-tracking", path], Shell({})) == 0


BRANCHES: dict[tuple[str, ...], Reply] = {
    ("symbolic-ref", "--short", "HEAD"): "main\n",
    ("symbolic-ref", "--short", "refs/remotes/origin/HEAD"): "origin/main\n",
}


def test_a_commit_on_the_default_branch_is_refused(kaizen, capsys):
    assert kaizen(["hook", "no-commit-to-branch"], Shell(BRANCHES)) == 1

    err = capsys.readouterr().err
    assert "refused: hook no-commit-to-branch: the commit is on main" in err
    assert "git switch -c" in err


def test_a_commit_on_another_branch_passes(kaizen):
    shell = Shell({**BRANCHES, ("symbolic-ref", "--short", "HEAD"): "fix-7-thing\n"})

    assert kaizen(["hook", "no-commit-to-branch", "a.py"], shell) == 0


def test_a_detached_head_passes(kaizen):
    shell = Shell({("symbolic-ref", "--short", "HEAD"): failed("git symbolic-ref")})

    assert kaizen(["hook", "no-commit-to-branch"], shell) == 0


def test_the_default_branch_is_asked_of_origin_when_the_clone_never_recorded_it(kaizen):
    shell = Shell(
        {
            ("symbolic-ref", "--short", "HEAD"): "trunk\n",
            ("refs/remotes/origin/HEAD",): failed("git symbolic-ref"),
            ("ls-remote", "--symref"): "ref: refs/heads/trunk\tHEAD\nabc123\tHEAD\n",
        }
    )

    assert kaizen(["hook", "no-commit-to-branch"], shell) == 1

    assert shell.ran("ls-remote", "--symref", "origin", "HEAD")


def test_a_clone_whose_default_branch_cant_be_read_is_refused_with_the_fix(kaizen, capsys):
    shell = Shell(
        {
            ("symbolic-ref", "--short", "HEAD"): "main\n",
            ("refs/remotes/origin/HEAD",): failed("git symbolic-ref"),
            ("ls-remote",): failed("git ls-remote", "fatal: 'origin' does not appear to be"),
        }
    )

    assert kaizen(["hook", "no-commit-to-branch"], shell) == 1

    err = capsys.readouterr().err
    assert "refused: could not read the default branch" in err
    assert "git remote set-head origin --auto" in err


def test_the_branches_named_replace_the_default_branch(kaizen):
    on_release = Shell({**BRANCHES, ("symbolic-ref", "--short", "HEAD"): "release\n"})
    argv = ["hook", "no-commit-to-branch", "--branch", "release", "--branch", "prod"]

    assert kaizen(argv, on_release) == 1
    assert kaizen(argv, Shell(BRANCHES)) == 0


def test_the_leak_check_hook_runs_the_staged_leak_check(kaizen):
    shell = Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{RELAY}\n",
            ("grep", "--cached"): "docs/a.md:3:see owner/secret\n",
        }
    )

    assert kaizen(["hook", "leak-check", "docs/a.md"], shell) == 1

    (grep,) = shell.ran("grep")
    assert "--cached" in grep


def test_the_leak_check_hook_passes_a_clean_index(kaizen):
    shell = Shell({("rev-parse", "--show-toplevel"): f"{RELAY}\n", ("grep",): failed("git grep")})

    assert kaizen(["hook", "leak-check"], shell) == 0


KAIZEN = Path(__file__).resolve().parents[3]
"""kaizen's own folder, holding its ``pyproject.toml``."""


@pytest.mark.parametrize("hook", ["section-banners", "work-tracking"])
def test_kaizen_s_own_sources_pass_the_comment_hooks(kaizen, capsys, hook):
    sources = [
        str(path)
        for path in [*(KAIZEN / "src").rglob("*"), *(KAIZEN / "scripts").rglob("*")]
        if path.is_file() and "__pycache__" not in path.parts
    ]
    sources.append(str(KAIZEN / "pyproject.toml"))

    assert kaizen(["hook", hook, *sources], Shell({})) == 0, capsys.readouterr().err


def _dangling_symlink(path: Path) -> None:
    path.symlink_to(path.parent / "missing")


def _folder(path: Path) -> None:
    path.mkdir()


@pytest.mark.parametrize("make", [_dangling_symlink, _folder], ids=["dangling symlink", "folder"])
@pytest.mark.parametrize(
    ("hook", "name"),
    [("prose-marks", "a.md"), ("section-banners", "a.py"), ("work-tracking", "a.py")],
)
def test_a_path_that_cant_be_read_is_skipped(tmp_path, kaizen, capsys, make, hook, name):
    path = tmp_path / "files" / name
    path.parent.mkdir(parents=True)
    make(path)

    assert kaizen(["hook", hook, str(path)], Shell({})) == 0

    assert "Traceback" not in capsys.readouterr().err
