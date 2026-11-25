"""Tests for ``kaizen project add``: run through the CLI from a fixture home, with git and gh
replaced by a recording runner, and its prompts driven through the ``ask`` seam."""

import json
from pathlib import Path

import pytest

from kaizen.project.add import add_project
from kaizen.shared.cli import main
from kaizen.shared.common import RefusalError
from kaizen.shared.registry import KEYS, resolve
from kaizen.tests.ticket_shell import RELAY, Reply, Shell, cli_home, failed, home_for

KEYS_BY_NAME = {key.name: key for key in KEYS}

FLAGS = [
    *("--github", "acme/tool", "--public", "--check", "bash scripts/check.sh"),
    *("--code-paths", "src/, tests/"),
]
"""Flags giving every required field, so no field is detected or asked for."""


def _checkout(tmp_path: Path) -> Path:
    checkout = tmp_path / "tool"
    checkout.mkdir()
    return checkout


def _shell(checkout: Path, **answers: Reply) -> Shell:
    """git and gh for a checkout at *checkout*: its toplevel, an origin on GitHub, a public repo
    and three tracked files; keyword *answers* (``toplevel``, ``remote``, ``repo``, ``files``)
    replace those."""
    return Shell(
        {
            ("rev-parse", "--show-toplevel"): answers.get("toplevel", f"{checkout}\n"),
            ("remote", "get-url"): answers.get("remote", "git@github.com:acme/tool.git\n"),
            ("repo", "view"): answers.get("repo", '{"visibility": "PUBLIC"}'),
            ("ls-files",): answers.get("files", "src/a.py\ntests/test_a.py\nREADME.md\n"),
        }
    )


def _add(home: Path, args: list[str], shell: Shell) -> int:
    return main(["project", "add", *args], run=shell, cwd=home, env={}, latest=lambda: None)


def test_flags_alone_write_a_page_that_reads_back_as_given(tmp_path):
    home = cli_home(tmp_path)
    checkout = _checkout(tmp_path)

    assert _add(home, ["tool", str(checkout), *FLAGS], _shell(checkout)) == 0

    project = resolve("tool", home / "projects")
    assert project.path == checkout
    assert project.github == "acme/tool"
    assert project.public is True
    assert project.check == "bash scripts/check.sh"
    assert project.code_paths == ("src/", "tests/")
    assert project.worktree_root == checkout / ".claude/worktrees"
    assert project.auto_merge_paths is None
    assert project.auto_merge_comment_only is False
    assert project.worktree_links == ()


def test_every_optional_flag_reads_back_as_given(tmp_path):
    home = cli_home(tmp_path)
    checkout = _checkout(tmp_path)
    optional = [
        *("--worktree-root", str(tmp_path / "trees"), "--auto-merge-paths", "docs/"),
        *("--auto-merge-comment-only", "--worktree-links", "tools/mpy-cross"),
    ]

    assert _add(home, ["tool", str(checkout), *FLAGS, *optional], _shell(checkout)) == 0

    project = resolve("tool", home / "projects")
    assert project.worktree_root == tmp_path / "trees"
    assert project.auto_merge_paths == ("docs/",)
    assert project.auto_merge_comment_only is True
    assert project.worktree_links == ("tools/mpy-cross",)


def test_the_path_defaults_to_the_current_directory(tmp_path):
    cli_home(tmp_path)
    checkout = _checkout(tmp_path)
    shell = _shell(checkout)
    env = {"KAIZEN_HOME": str(tmp_path / "cli-home")}

    code = main(["project", "add", "tool", *FLAGS], run=shell, cwd=checkout, env=env)

    assert code == 0
    assert resolve("tool", tmp_path / "cli-home" / "projects").path == checkout


def test_a_path_under_the_user_directory_is_written_from_tilde(tmp_path, monkeypatch):
    home = cli_home(tmp_path)
    checkout = _checkout(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert _add(home, ["tool", str(checkout), *FLAGS], _shell(checkout)) == 0

    assert "path: ~/tool\n" in (home / "projects" / "tool.md").read_text()


def test_the_page_is_listed_in_the_readmes_pages_list_in_name_order(tmp_path):
    home = cli_home(tmp_path)
    readme = home / "projects" / "README.md"
    readme.write_text("# Projects\n\n## Pages\n\n- [relay](relay.md)\n- [web](web.md)\n")
    checkout = _checkout(tmp_path)

    assert _add(home, ["tool", str(checkout), *FLAGS], _shell(checkout)) == 0

    assert readme.read_text() == (
        "# Projects\n\n## Pages\n\n- [relay](relay.md)\n- [tool](tool.md)\n- [web](web.md)\n"
    )


def test_a_readme_with_no_pages_list_gets_one(tmp_path):
    home = cli_home(tmp_path)
    readme = home / "projects" / "README.md"
    readme.write_text("# Projects\n\nNotes.\n")
    checkout = _checkout(tmp_path)

    assert _add(home, ["tool", str(checkout), *FLAGS], _shell(checkout)) == 0

    assert readme.read_text() == "# Projects\n\nNotes.\n\n## Pages\n\n- [tool](tool.md)\n"


def test_a_pages_heading_with_no_links_gets_the_first(tmp_path):
    home = cli_home(tmp_path)
    readme = home / "projects" / "README.md"
    readme.write_text("# Projects\n\n## Pages\n")
    checkout = _checkout(tmp_path)

    assert _add(home, ["tool", str(checkout), *FLAGS], _shell(checkout)) == 0

    assert readme.read_text() == "# Projects\n\n## Pages\n\n- [tool](tool.md)\n"


def test_a_link_with_a_note_after_it_counts_as_listed(tmp_path):
    home = cli_home(tmp_path)
    readme = home / "projects" / "README.md"
    readme.write_text("# Projects\n\n- [relay](relay.md): the API\n- [web](web.md)\n")
    checkout = _checkout(tmp_path)

    assert _add(home, ["tool", str(checkout), *FLAGS], _shell(checkout)) == 0

    assert readme.read_text() == (
        "# Projects\n\n- [relay](relay.md): the API\n- [tool](tool.md)\n- [web](web.md)\n"
    )


def test_the_defaults_left_off_the_page_are_shown(tmp_path, capsys):
    home = cli_home(tmp_path)
    checkout = _checkout(tmp_path)

    assert _add(home, ["tool", str(checkout), *FLAGS], _shell(checkout)) == 0

    out = capsys.readouterr().out
    assert f"worktree_root: {checkout}/.claude/worktrees (the default, left off the page)" in out
    assert "worktree_links: none (the default, left off the page)" in out


def _settings(home: Path) -> Path:
    return home / ".claude" / "settings.json"


def test_the_directory_is_added_to_the_settings_keeping_every_other_key(tmp_path):
    home = cli_home(tmp_path)
    _settings(home).parent.mkdir()
    before = {
        "env": {"KAIZEN_HOME": "~/home"},
        "permissions": {"additionalDirectories": ["/fixture/relay"], "deny": ["Bash(x)"]},
    }
    _settings(home).write_text(json.dumps(before))
    checkout = _checkout(tmp_path)

    assert _add(home, ["tool", str(checkout), *FLAGS], _shell(checkout)) == 0

    after = json.loads(_settings(home).read_text())
    assert after == {
        "env": {"KAIZEN_HOME": "~/home"},
        "permissions": {
            "additionalDirectories": ["/fixture/relay", str(checkout)],
            "deny": ["Bash(x)"],
        },
    }


def test_a_settings_file_spelling_directories_from_tilde_gets_one_too(tmp_path, monkeypatch):
    home = cli_home(tmp_path)
    _settings(home).parent.mkdir()
    listed = {"permissions": {"additionalDirectories": ["~/elsewhere"]}}
    _settings(home).write_text(json.dumps(listed))
    checkout = _checkout(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert _add(home, ["tool", str(checkout), *FLAGS], _shell(checkout)) == 0

    entries = json.loads(_settings(home).read_text())["permissions"]["additionalDirectories"]
    assert entries == ["~/elsewhere", "~/tool"]


def test_a_directory_the_settings_already_list_is_left_alone(tmp_path, monkeypatch, capsys):
    home = cli_home(tmp_path)
    _settings(home).parent.mkdir()
    text = '{"permissions": {"additionalDirectories": ["~/tool"]}}'
    _settings(home).write_text(text)
    checkout = _checkout(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert _add(home, ["tool", str(checkout), *FLAGS], _shell(checkout)) == 0

    assert _settings(home).read_text() == text
    assert ".claude/settings.json already lists" in capsys.readouterr().out


def test_the_next_step_is_creating_the_labels(tmp_path, capsys):
    home = cli_home(tmp_path)
    checkout = _checkout(tmp_path)

    assert _add(home, ["tool", str(checkout), *FLAGS], _shell(checkout)) == 0

    assert "next: run `kaizen project labels tool`" in capsys.readouterr().out


def _with_check_script(checkout: Path) -> Path:
    (checkout / "scripts").mkdir()
    (checkout / "scripts" / "check.sh").write_text("true\n")
    return checkout


def test_detected_values_fill_the_fields_no_flag_gives(tmp_path):
    home = cli_home(tmp_path)
    checkout = _with_check_script(_checkout(tmp_path))

    assert _add(home, ["tool", str(checkout)], _shell(checkout)) == 0

    project = resolve("tool", home / "projects")
    assert (project.github, project.public) == ("acme/tool", True)
    assert project.check == "bash scripts/check.sh"
    assert project.code_paths == ("src/", "tests/")


def test_each_detected_value_is_shown_with_its_source(tmp_path, capsys):
    home = cli_home(tmp_path)
    checkout = _with_check_script(_checkout(tmp_path))

    assert _add(home, ["tool", str(checkout)], _shell(checkout)) == 0

    out = capsys.readouterr().out
    assert "github: acme/tool (detected from origin, git@github.com:acme/tool.git)" in out
    assert "public: true (detected from GitHub, acme/tool is PUBLIC)" in out
    assert "check: bash scripts/check.sh (detected, scripts/check.sh exists)" in out
    assert "code_paths: src/, tests/ (detected, the top-level tracked directories)" in out


def test_a_private_repo_is_detected_as_not_public(tmp_path):
    home = cli_home(tmp_path)
    checkout = _checkout(tmp_path)
    shell = _shell(checkout, repo='{"visibility": "PRIVATE"}')

    assert _add(home, ["tool", str(checkout), "--check", "none"], shell) == 0

    assert resolve("tool", home / "projects").public is False


def test_without_a_terminal_each_missing_required_field_is_refused_with_its_explanation(
    tmp_path, capsys
):
    home = cli_home(tmp_path)
    checkout = _checkout(tmp_path)
    shell = _shell(checkout, remote=failed("git remote", "error: No such remote 'origin'"))

    assert _add(home, ["tool", str(checkout), "--code-paths", "src/"], shell) == 1

    err = capsys.readouterr().err
    assert "refused: project add: 3 required key(s) have no value" in err
    assert "  github: the project's GitHub repo, `owner/repo`." in err
    assert "  public: " in err
    assert "  check: " in err
    assert "fix: pass --github, --public or --private, --check" in err
    assert not (home / "projects" / "tool.md").exists()


@pytest.mark.parametrize(
    ("args", "problem"),
    [
        (["relay", "{checkout}", *FLAGS], "project relay already has a page"),
        (["again", str(RELAY), *FLAGS], f"{RELAY} is already registered, as relay"),
        (["tool", "{checkout}", *FLAGS, "--github", "acme"], "github 'acme' is not owner/repo"),
        (["tool", "{checkout}/sub", *FLAGS], "is inside the git checkout at"),
        (["README", "{checkout}", *FLAGS], "'README' can't name a project page"),
    ],
)
def test_a_refusal_writes_nothing(tmp_path, capsys, args, problem):
    home = cli_home(tmp_path)
    checkout = _checkout(tmp_path)
    before = {page.name: page.read_text() for page in (home / "projects").iterdir()}
    toplevel = lambda cmd: f"{RELAY}\n" if cmd[2] == str(RELAY) else f"{checkout}\n"  # noqa: E731
    shell = _shell(checkout, toplevel=toplevel)

    assert _add(home, [arg.format(checkout=checkout) for arg in args], shell) == 1

    assert problem in capsys.readouterr().err
    after = {page.name: page.read_text() for page in (home / "projects").iterdir()}
    assert after == before
    assert not _settings(home).exists()


def test_a_path_that_is_not_a_git_checkout_is_refused(tmp_path, capsys):
    home = cli_home(tmp_path)
    checkout = _checkout(tmp_path)
    shell = Shell({("rev-parse", "--show-toplevel"): failed("git", "fatal: not a git repository")})

    assert _add(home, ["tool", str(checkout), *FLAGS], shell) == 1

    assert f"{checkout} is not a git checkout" in capsys.readouterr().err
    assert not (home / "projects" / "tool.md").exists()


def test_a_dry_run_prints_the_page_and_each_change_and_writes_nothing(tmp_path, capsys):
    home = cli_home(tmp_path)
    (home / "projects" / "README.md").write_text("# Projects\n\n- [relay](relay.md)\n")
    checkout = _checkout(tmp_path)

    assert _add(home, ["tool", str(checkout), "--dry-run", *FLAGS], _shell(checkout)) == 0

    out = capsys.readouterr().out
    assert "would write projects/tool.md:\n---\npath: " in out
    assert "\ngithub: acme/tool\npublic: true\n" in out
    assert "+- [tool](tool.md)" in out
    assert f'+      "{checkout}"' in out
    assert "dry run: nothing written" in out
    assert not (home / "projects" / "tool.md").exists()
    assert not _settings(home).exists()


class _Terminal:
    """The ``ask`` seam as a terminal: answers each prompt with the next of *answers* and records
    the prompts."""

    def __init__(self, *answers: str) -> None:
        self.prompts: list[str] = []
        self._answers = list(answers)

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._answers.pop(0)


def _add_asking(tmp_path: Path, terminal: _Terminal, given: dict[str, str], lines: list[str]):
    home = cli_home(tmp_path)
    checkout = _checkout(tmp_path)
    add_project(
        _shell(checkout),
        home_for(home / "projects"),
        "tool",
        checkout,
        given,
        ask=terminal,
        say=lines.append,
    )
    return resolve("tool", home / "projects")


_ACCEPT_ALL = ("", "", "none", "", "", "", "", "")
"""Answers accepting every offer, and ``none`` for ``check``, which detects nothing here."""


def test_a_terminal_is_asked_each_field_no_flag_gives_in_page_order(tmp_path):
    terminal = _Terminal(*_ACCEPT_ALL)

    _add_asking(tmp_path, terminal, {}, [])

    assert [prompt.split(" ")[0] for prompt in terminal.prompts] == [
        "github",
        "public",
        "check",
        "code_paths",
        "worktree_root",
        "auto_merge_paths",
        "auto_merge_comment_only",
        "worktree_links",
    ]


def test_a_prompt_shows_the_keys_explanation_options_and_detected_value(tmp_path):
    terminal = _Terminal(*_ACCEPT_ALL)
    lines: list[str] = []

    _add_asking(tmp_path, terminal, {}, lines)

    assert "github: the project's GitHub repo, `owner/repo`." in lines
    assert terminal.prompts[0] == (
        "github (owner/repo) [acme/tool] (detected from origin; Enter accepts): "
    )
    assert terminal.prompts[2] == "check (a shell command, or none): "
    assert lines[lines.index(f"check: {KEYS_BY_NAME['check'].summary}") + 1] == (
        "  nothing detected"
    )


def test_enter_accepts_the_detected_value_or_the_default(tmp_path):
    project = _add_asking(tmp_path, _Terminal(*_ACCEPT_ALL), {}, [])

    assert (project.github, project.public, project.check) == ("acme/tool", True, "none")
    assert project.code_paths == ("src/", "tests/")
    assert project.worktree_root == tmp_path / "tool" / ".claude/worktrees"


def test_a_terminal_is_not_asked_a_field_a_flag_gives(tmp_path):
    terminal = _Terminal("", "", "", "")
    given = {"github": "acme/tool", "public": "false", "check": "make check", "code_paths": "lib/"}

    project = _add_asking(tmp_path, terminal, given, [])

    assert [prompt.split(" ")[0] for prompt in terminal.prompts] == [
        "worktree_root",
        "auto_merge_paths",
        "auto_merge_comment_only",
        "worktree_links",
    ]
    assert (project.public, project.check, project.code_paths) == (False, "make check", ("lib/",))


def test_an_answer_that_is_not_valid_is_asked_again(tmp_path):
    terminal = _Terminal("acme", "acme/other", "maybe", "false", "", "", "", "", "", "")
    lines: list[str] = []

    project = _add_asking(tmp_path, terminal, {"check": "none"}, lines)

    assert (project.github, project.public) == ("acme/other", False)
    assert "  'acme' is not owner/repo; try again" in lines
    assert "  'maybe' is not true or false; try again" in lines


def test_a_closed_terminal_refuses_and_writes_nothing(tmp_path):
    def closed(prompt: str) -> str:
        raise EOFError

    home = cli_home(tmp_path)
    checkout = _checkout(tmp_path)

    with pytest.raises(RefusalError, match="no answer for github"):
        add_project(_shell(checkout), home_for(home / "projects"), "tool", checkout, {}, ask=closed)
    assert not (home / "projects" / "tool.md").exists()
