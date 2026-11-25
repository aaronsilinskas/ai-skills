"""Tests for ``kaizen home init``, driven through ``main`` against a fixture repo in ``tmp_path``.

git is replaced by a recording runner answering the toplevel and origin queries, so no repo or
network is touched.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

from kaizen.shared.cli import main
from kaizen.shared.common import RefusalError
from kaizen.shared.home import find_home
from kaizen.shared.labels import Label
from kaizen.shared.registry import all_projects, resolve
from kaizen.shared.synced import OVERLAY, SYNCED_FILES, render
from kaizen.tests.hook_config import KAIZEN_REPO_ITEM
from kaizen.tests.ticket_shell import (
    FOOTER,
    LEAK_OWN,
    RELAY,
    SITE,
    TILDE,
    Reply,
    Shell,
    cli_home,
    failed,
)

HTTPS = "https://github.com/acme/newhome.git"
TILDE_ROOT = TILDE + "/work/newhome"
"""The fixture repo's root in ``~`` form."""
DENY = ["Bash(git stash*)", "Bash(git -C * stash*)"]
"""The git stash deny rule's entries, as init writes them."""
SYNCED = [synced.path for synced in SYNCED_FILES]
"""Every synced file in the manifest, in its order."""
DOCS = [*SYNCED, OVERLAY]
"""The docs init writes: every synced file, then the starter overlay."""
EVERY_FILE = sorted(
    [
        ".claude/settings.json",
        ".gitignore",
        ".pre-commit-config.yaml",
        "kaizen.toml",
        "projects/README.md",
        "projects/newhome.md",
        OVERLAY,
        *SYNCED,
    ]
)
"""Every file init writes in a fresh repo, sorted."""


def _repo(tmp_path: Path) -> Path:
    """A repo root under the fixture user directory ``tmp_path / "user"``."""
    root = tmp_path / "user" / "work" / "newhome"
    root.mkdir(parents=True)
    return root


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    return {"HOME": str(tmp_path / "user"), **extra}


def _shell(root: Path, origin: str | BaseException = HTTPS, grep: Reply = "") -> Shell:
    """git answering for a repo at *root* with *origin*, whose tracked files *grep* answers the
    leak check's search for (default: nothing found)."""
    return Shell(
        {
            ("grep",): grep,
            ("rev-parse", "--show-toplevel"): f"{root}\n",
            ("remote", "get-url", "origin"): origin
            if isinstance(origin, BaseException)
            else f"{origin}\n",
        }
    )


def _no_lookup() -> str | None:
    raise AssertionError("home init looked up the latest release")


def _init(tmp_path, root, *extra, shell=None, cwd=None, env=None, version="1.2.3"):
    return main(
        ["home", "init", *extra],
        run=shell or _shell(root),
        cwd=cwd or root,
        env=_env(tmp_path) if env is None else env,
        version=version,
        latest=_no_lookup,
    )


def _written(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def _write(root: Path, relative: str, text: str) -> None:
    (root / relative).parent.mkdir(parents=True, exist_ok=True)
    (root / relative).write_text(text)


def _settings(root: Path) -> dict:
    return json.loads((root / ".claude" / "settings.json").read_text())


def test_a_fresh_repo_becomes_a_home_that_find_home_reads(tmp_path):
    root = _repo(tmp_path)

    assert _init(tmp_path, root) == 0

    home = find_home(root, {})
    assert home.registry == root.resolve() / "projects"
    assert home.leak_own == ("acme/newhome", TILDE_ROOT)
    assert (home.leak_allow_paths, home.leak_allow_repos) == ((), ())


def test_the_registry_loads_the_homes_own_page_with_its_path_in_tilde_form(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "user"))  # the registry expands ~ with it
    root = _repo(tmp_path)

    _init(tmp_path, root)

    page = resolve("newhome", root / "projects")
    assert (page.path, page.github, page.public) == (root, "acme/newhome", False)
    assert (page.check, page.code_paths) == (None, None)
    assert f"path: {TILDE_ROOT}\n" in page.page.read_text()
    assert [p.name for p in all_projects(root / "projects")] == ["newhome"]


def test_the_registry_readme_lists_the_homes_page(tmp_path):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    assert "- [newhome](newhome.md)" in (root / "projects" / "README.md").read_text()


def test_each_step_done_prints_one_line_after_the_home_root(tmp_path, capsys):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    out = capsys.readouterr().out.splitlines()
    assert out[: out.index(f"{root} is now a home") + 1] == [
        f"home root: {root}",
        "wrote .claude/settings.json",
        "wrote .gitignore",
        "wrote projects/README.md",
        "wrote projects/newhome.md",
        *[f"wrote {path}" for path in DOCS],
        "wrote .pre-commit-config.yaml",
        "wrote kaizen.toml",
        f"{root} is now a home",
    ]


def test_init_runs_only_git_and_so_needs_no_network_or_gh(tmp_path):
    root = _repo(tmp_path)
    shell = _shell(root)

    _init(tmp_path, root, shell=shell)

    assert {cmd[0] for cmd in shell.calls} == {"git"}


def test_the_marker_comments_every_key(tmp_path):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    lines = (root / "kaizen.toml").read_text().splitlines()
    keys = [i for i, line in enumerate(lines) if "=" in line and not line.startswith("#")]
    assert [lines[i].split(" =")[0] for i in keys] == ["registry", "synced_version", "own", "allow"]
    assert all(lines[i - 1].startswith("#") for i in keys)


def test_the_marker_comments_name_the_pr_footer_setting_and_its_default(tmp_path):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    lines = (root / "kaizen.toml").read_text().splitlines()
    assert f"# pr_footer = {json.dumps(FOOTER, ensure_ascii=False)}" in lines


def test_the_commented_pr_footer_line_uncommented_sets_the_default_footer(tmp_path):
    root = _repo(tmp_path)
    _init(tmp_path, root)
    marker = root / "kaizen.toml"

    marker.write_text(marker.read_text().replace("# pr_footer = ", "pr_footer = "))

    assert find_home(root, {}).pr_footer == FOOTER


def test_the_marker_names_the_comment_only_switch_and_its_default(tmp_path):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    assert "# auto_merge_comment_only = true\n" in (root / "kaizen.toml").read_text()


def test_the_marker_says_its_own_path_may_be_widened_to_a_parent_folder(tmp_path):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    assert "may be widened to a parent folder" in (root / "kaizen.toml").read_text()


@pytest.mark.parametrize(
    "origin",
    [
        "git@github.com:acme/newhome.git",
        "git@github.com:acme/newhome",
        "ssh://git@github.com/acme/newhome.git",
        "ssh://git@github.com:22/acme/newhome.git",
        "https://github.com/acme/newhome",
        "https://github.com/acme/newhome.git",
        "https://github.com/acme/newhome/",
        "https://github.com/acme/newhome.git/",
        "https://user:s3cret-token@github.com/acme/newhome.git",
    ],
)
def test_ssh_and_https_origins_give_the_pages_github(tmp_path, origin):
    root = _repo(tmp_path)

    assert _init(tmp_path, root, shell=_shell(root, origin)) == 0

    assert resolve("newhome", root / "projects").github == "acme/newhome"


def test_a_token_in_an_https_origin_never_reaches_the_output_or_the_files(tmp_path, capsys):
    root = _repo(tmp_path)
    origin = "https://user:s3cret-token@github.com/acme/newhome.git"

    assert _init(tmp_path, root, "--dry-run", shell=_shell(root, origin)) == 0
    assert _init(tmp_path, root, shell=_shell(root, origin)) == 0

    captured = capsys.readouterr()
    assert "s3cret-token" not in captured.out + captured.err
    assert [f for f in _written(root) if "s3cret-token" in (root / f).read_text()] == []


def test_a_repo_outside_the_user_directory_is_written_with_its_absolute_path(tmp_path):
    root = tmp_path / "elsewhere" / "newhome"
    root.mkdir(parents=True)

    assert _init(tmp_path, root) == 0

    assert f"path: {root}\n" in (root / "projects" / "newhome.md").read_text()
    assert find_home(root, {}).leak_own == ("acme/newhome", str(root))


def test_a_repo_at_the_user_directory_itself_is_written_as_a_bare_tilde(tmp_path):
    root = tmp_path / "user"
    root.mkdir()

    assert _init(tmp_path, root) == 0

    assert _settings(root)["env"]["KAIZEN_HOME"] == TILDE
    assert f"path: {TILDE}\n" in (root / "projects" / "newhome.md").read_text()


def test_a_run_from_a_subdirectory_uses_the_toplevel_and_prints_it_first(tmp_path, capsys):
    root = _repo(tmp_path)
    sub = root / "src" / "deep"
    sub.mkdir(parents=True)
    shell = _shell(root)

    assert _init(tmp_path, root, shell=shell, cwd=sub) == 0

    assert shell.ran("git", "-C", str(sub), "rev-parse", "--show-toplevel")
    assert _written(root) == EVERY_FILE
    assert capsys.readouterr().out.splitlines()[0] == f"home root: {root}"


def test_kaizen_home_naming_this_root_is_accepted(tmp_path):
    root = _repo(tmp_path)

    assert _init(tmp_path, root, env=_env(tmp_path, KAIZEN_HOME=TILDE_ROOT)) == 0


def test_outside_a_git_repo_is_refused(tmp_path, capsys):
    root = _repo(tmp_path)
    shell = Shell({("rev-parse",): failed("git rev-parse", "fatal: not a git repository")})

    assert _init(tmp_path, root, shell=shell) == 1

    assert capsys.readouterr().err.startswith("refused: home init: not inside a git repo")
    assert _written(root) == []


@pytest.mark.parametrize("name", ["kaizen.toml", "mw.toml"])
def test_a_marker_under_either_name_at_the_root_is_refused(tmp_path, capsys, name):
    root = _repo(tmp_path)
    (root / name).write_text("")

    assert _init(tmp_path, root) == 1

    assert capsys.readouterr().err.startswith("refused: home init: a kaizen.toml is already in")
    assert _written(root) == [name]


def test_a_marker_above_the_root_is_refused_without_naming_where(tmp_path, capsys):
    above = tmp_path / "outer-home"
    root = above / "nested" / "newhome"
    root.mkdir(parents=True)
    (above / "kaizen.toml").write_text("")

    assert _init(tmp_path, root) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused: home init: a kaizen.toml is already in")
    assert "outer-home" not in err.replace(str(root), "")
    assert _written(root) == []


@pytest.mark.parametrize("variable", ["KAIZEN_HOME", "MW_HOME"])
def test_either_variable_naming_another_root_is_refused_without_its_value(
    tmp_path, capsys, variable
):
    root = _repo(tmp_path)
    other = tmp_path / "other-home"

    assert _init(tmp_path, root, env=_env(tmp_path, **{variable: str(other)})) == 1

    err = capsys.readouterr().err
    assert f"refused: home init: {variable} is set to a root other than" in err
    assert f"unset {variable}, or start a fresh session" in err
    assert "other-home" not in err
    assert _written(root) == []


@pytest.mark.parametrize(
    ("origin", "reason"),
    [
        (failed("git remote get-url origin", "error: No such remote 'origin'"), "no origin"),
        ("https://gitlab.com/acme/newhome.git", "does not name a GitHub owner/repo"),
        ("https://github.com/acme", "does not name a GitHub owner/repo"),
    ],
    ids=["no origin", "not GitHub", "no repo"],
)
def test_an_origin_that_is_not_a_github_repo_is_refused(tmp_path, capsys, origin, reason):
    root = _repo(tmp_path)

    assert _init(tmp_path, root, shell=_shell(root, origin)) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused: home init:")
    assert reason in err
    assert _written(root) == []


def test_a_differing_registry_file_is_refused_naming_it_before_any_write(tmp_path, capsys):
    root = _repo(tmp_path)
    (root / "projects").mkdir()
    (root / "projects" / "newhome.md").write_text("mine\n")

    assert _init(tmp_path, root) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused: home init: projects/newhome.md already exists and differs")
    assert _written(root) == ["projects/newhome.md"]


def test_dry_run_writes_nothing_and_prints_the_checks(tmp_path, capsys):
    root = _repo(tmp_path)

    assert _init(tmp_path, root, "--dry-run") == 0

    assert _written(root) == []
    out = capsys.readouterr().out
    assert out.startswith(f"home root: {root}\n")
    for check in ["git repo's root", "no kaizen.toml", "KAIZEN_HOME is unset", "acme/newhome"]:
        assert any(line.startswith("checked: ") and check in line for line in out.splitlines())
    assert out.endswith("dry run: nothing written\n")


def test_dry_run_prints_each_file_in_full_as_a_real_run_writes_it(tmp_path, capsys):
    root = _repo(tmp_path)
    _init(tmp_path, root)
    names = EVERY_FILE
    written = {name: (root / name).read_text() for name in names}
    for name in names:
        (root / name).unlink()
    capsys.readouterr()

    assert _init(tmp_path, root, "--dry-run") == 0

    out = capsys.readouterr().out
    for name in names:
        assert f"would write {name}:\n{written[name]}" in out


def test_a_rerun_after_a_failure_partway_finishes(tmp_path, capsys, monkeypatch):
    root = _repo(tmp_path)
    write_text = Path.write_text

    def fail_on_page(path, *args, **kwargs):
        if path.name == "newhome.md":
            raise OSError("disk full")
        return write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_on_page)
    assert _init(tmp_path, root) == 1
    assert _written(root) == [".claude/settings.json", ".gitignore", "projects/README.md"]
    monkeypatch.undo()
    capsys.readouterr()

    assert _init(tmp_path, root) == 0

    assert _written(root) == EVERY_FILE
    steps = [
        "kept .claude/settings.json, its env already sets KAIZEN_HOME to the home and it denies"
        " git stash",
        "kept .gitignore, it already ignores .claude/worktrees/",
        "kept projects/README.md, already as init writes it",
        "wrote projects/newhome.md",
        *[f"wrote {path}" for path in DOCS],
        "wrote .pre-commit-config.yaml",
        "wrote kaizen.toml",
    ]
    assert capsys.readouterr().out.splitlines()[1 : 1 + len(steps)] == steps
    assert resolve("newhome", find_home(root, {}).registry).github == "acme/newhome"


def test_init_help_states_the_preconditions_the_files_and_dry_run(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["home", "init", "--help"], cwd=tmp_path, env={})

    out = " ".join(capsys.readouterr().out.split())
    for text in [
        "outside a git repo",
        "KAIZEN_HOME is set to a different root",
        "no origin remote",
        "projects/README.md",
        "projects/<repo>.md",
        "kaizen.toml",
        "--dry-run",
        ".claude/settings.json",
        "env.KAIZEN_HOME",
        "every other key",
        "is not valid JSON",
        ".gitignore",
        ".claude/worktrees/",
    ]:
        assert text in out


def test_a_root_with_quotes_in_its_path_still_gives_a_readable_marker(tmp_path):
    root = tmp_path / 'say "hi"' / "newhome"
    root.mkdir(parents=True)

    assert _init(tmp_path, root) == 0

    assert find_home(root, {}).leak_own == ("acme/newhome", str(root))


def test_an_existing_file_that_is_not_text_is_refused_naming_it(tmp_path, capsys):
    root = _repo(tmp_path)
    (root / "projects").mkdir()
    (root / "projects" / "README.md").write_bytes(b"\xff\xfe")

    assert _init(tmp_path, root) == 1

    assert "projects/README.md already exists and differs" in capsys.readouterr().err


def test_a_fresh_repo_gets_a_settings_file_whose_env_names_the_home(tmp_path):
    root = _repo(tmp_path)

    assert _init(tmp_path, root) == 0

    assert _settings(root) == {"env": {"KAIZEN_HOME": TILDE_ROOT}, "permissions": {"deny": DENY}}


def test_a_repo_outside_the_user_directory_gets_an_absolute_kaizen_home(tmp_path):
    root = tmp_path / "elsewhere" / "newhome"
    root.mkdir(parents=True)

    assert _init(tmp_path, root) == 0

    assert _settings(root)["env"]["KAIZEN_HOME"] == str(root)


def test_an_existing_settings_file_keeps_every_other_key_in_order(tmp_path):
    root = _repo(tmp_path)
    _write(
        root,
        ".claude/settings.json",
        '{"permissions": {"allow": ["Bash(ls)"]}, "env": {"A": "1"}, "hooks": {}}',
    )

    assert _init(tmp_path, root) == 0

    text = (root / ".claude" / "settings.json").read_text()
    assert text == (
        "{\n"
        '  "permissions": {\n    "allow": [\n      "Bash(ls)"\n    ],\n'
        '    "deny": [\n      "Bash(git stash*)",\n      "Bash(git -C * stash*)"\n    ]\n  },\n'
        f'  "env": {{\n    "A": "1",\n    "KAIZEN_HOME": "{TILDE_ROOT}"\n  }},\n'
        '  "hooks": {}\n'
        "}\n"
    )


def test_settings_without_an_env_gain_one_after_their_other_keys(tmp_path):
    root = _repo(tmp_path)
    _write(root, ".claude/settings.json", '{"hooks": {}}\n')

    assert _init(tmp_path, root) == 0

    assert list(_settings(root).items()) == [
        ("hooks", {}),
        ("env", {"KAIZEN_HOME": TILDE_ROOT}),
        ("permissions", {"deny": DENY}),
    ]


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ('{"env": {', "is not valid JSON"),
        ("[]", "does not hold a JSON object"),
        ('{"env": ["KAIZEN_HOME"]}', "has an env that is not a JSON object"),
    ],
    ids=["not JSON", "not an object", "env not an object"],
)
def test_malformed_settings_are_refused_before_any_write(tmp_path, capsys, text, problem):
    root = _repo(tmp_path)
    _write(root, ".claude/settings.json", text)

    assert _init(tmp_path, root) == 1

    err = capsys.readouterr().err
    assert err.startswith(f"refused: home init: .claude/settings.json {problem}")
    assert _written(root) == [".claude/settings.json"]
    assert (root / ".claude" / "settings.json").read_text() == text


def test_settings_with_another_kaizen_home_are_refused_naming_the_file_but_not_the_value(
    tmp_path, capsys
):
    root = _repo(tmp_path)
    text = '{"env": {"KAIZEN_HOME": "/other-home"}}\n'
    _write(root, ".claude/settings.json", text)

    assert _init(tmp_path, root) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused: home init: .claude/settings.json already sets KAIZEN_HOME to a")
    assert "fix: remove KAIZEN_HOME from .claude/settings.json's env" in err
    assert "other-home" not in err


def test_settings_with_the_same_root_in_another_form_are_refused_before_any_write(tmp_path):
    root = _repo(tmp_path)
    _write(root, ".claude/settings.json", f'{{"env": {{"KAIZEN_HOME": "{root}"}}}}')

    assert _init(tmp_path, root) == 1

    assert _written(root) == [".claude/settings.json"]


def test_settings_with_the_same_root_in_another_form_are_told_to_use_the_tilde_form(
    tmp_path, capsys
):
    root = _repo(tmp_path)
    _write(root, ".claude/settings.json", f'{{"env": {{"KAIZEN_HOME": "{root}"}}}}')

    _init(tmp_path, root)

    err = capsys.readouterr().err
    assert f"fix: set KAIZEN_HOME in .claude/settings.json's env to {TILDE_ROOT} instead" in err
    assert "remove KAIZEN_HOME" not in err


def test_mw_home_naming_this_root_is_accepted_with_a_warning_and_kaizen_home_written(
    tmp_path, capsys
):
    root = _repo(tmp_path)

    assert _init(tmp_path, root, env=_env(tmp_path, MW_HOME=TILDE_ROOT)) == 0

    warnings = [line for line in capsys.readouterr().err.splitlines() if "MW_HOME" in line]
    assert len(warnings) == 1 and warnings[0].startswith("warning: ")
    assert "KAIZEN_HOME" in warnings[0]
    assert _settings(root) == {"env": {"KAIZEN_HOME": TILDE_ROOT}, "permissions": {"deny": DENY}}


def test_both_variables_naming_different_roots_are_refused_naming_which_to_keep(tmp_path, capsys):
    root = _repo(tmp_path)
    env = _env(tmp_path, KAIZEN_HOME=TILDE_ROOT, MW_HOME=str(tmp_path / "other-home"))

    assert _init(tmp_path, root, env=env) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused: home: KAIZEN_HOME and MW_HOME name different roots")
    assert "fix: keep KAIZEN_HOME" in err
    assert _written(root) == []


def test_differing_variables_are_refused_before_a_marker_above_the_root(tmp_path, capsys):
    root = _repo(tmp_path)
    (root.parent / "kaizen.toml").write_text("")
    env = _env(tmp_path, KAIZEN_HOME=TILDE_ROOT, MW_HOME=str(tmp_path / "other-home"))

    assert _init(tmp_path, root, env=env) == 1

    assert "KAIZEN_HOME and MW_HOME name different roots" in capsys.readouterr().err


def test_init_never_writes_the_old_marker_or_variable(tmp_path):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    assert "mw.toml" not in _written(root)
    assert "MW_HOME" not in (root / ".claude" / "settings.json").read_text()


def test_settings_whose_env_sets_mw_home_to_this_home_get_it_renamed_in_place(tmp_path):
    root = _repo(tmp_path)
    _write(root, ".claude/settings.json", f'{{"env": {{"A": "1", "MW_HOME": "{TILDE_ROOT}"}}}}')

    assert _init(tmp_path, root) == 0

    assert list(_settings(root)["env"].items()) == [("A", "1"), ("KAIZEN_HOME", TILDE_ROOT)]


def test_settings_with_mw_home_set_to_another_root_are_refused_naming_the_old_variable(
    tmp_path, capsys
):
    root = _repo(tmp_path)
    _write(root, ".claude/settings.json", '{"env": {"MW_HOME": "/other-home"}}\n')

    assert _init(tmp_path, root) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused: home init: .claude/settings.json already sets MW_HOME to a")
    assert "fix: remove MW_HOME from .claude/settings.json's env" in err
    assert "other-home" not in err
    assert _written(root) == [".claude/settings.json"]


def test_settings_with_mw_home_set_to_this_root_in_another_form_are_told_the_new_setting(
    tmp_path, capsys
):
    root = _repo(tmp_path)
    _write(root, ".claude/settings.json", f'{{"env": {{"MW_HOME": "{root}"}}}}')

    assert _init(tmp_path, root) == 1

    err = capsys.readouterr().err
    assert (
        f"fix: replace MW_HOME in .claude/settings.json's env with KAIZEN_HOME set to {TILDE_ROOT}"
        in err
    )


def test_settings_already_naming_this_home_are_kept_byte_for_byte(tmp_path):
    root = _repo(tmp_path)
    deny = '"Bash(git stash*)","Bash(git -C * stash*)"'
    text = f'{{"env":{{"KAIZEN_HOME":"{TILDE_ROOT}"}},"permissions":{{"deny":[{deny}]}}}}'
    _write(root, ".claude/settings.json", text)

    assert _init(tmp_path, root) == 0

    assert (root / ".claude" / "settings.json").read_text() == text


def test_a_fresh_repo_gets_a_gitignore_that_ignores_ticket_worktrees(tmp_path):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    assert (root / ".gitignore").read_text() == ".claude/worktrees/\n"


def test_an_existing_gitignore_gets_the_line_appended_on_a_line_of_its_own(tmp_path):
    root = _repo(tmp_path)
    _write(root, ".gitignore", ".venv/\n*.pyc")

    assert _init(tmp_path, root) == 0

    assert (root / ".gitignore").read_text() == ".venv/\n*.pyc\n.claude/worktrees/\n"


@pytest.mark.parametrize("line", [".claude/worktrees/", "/.claude/worktrees", ".claude/worktrees"])
def test_a_gitignore_that_already_ignores_worktrees_is_left_alone(tmp_path, line):
    root = _repo(tmp_path)
    text = f".venv/\n{line}\n"
    _write(root, ".gitignore", text)

    assert _init(tmp_path, root) == 0

    assert (root / ".gitignore").read_text() == text


def test_a_gitignore_that_is_not_text_is_refused_before_any_write(tmp_path, capsys):
    root = _repo(tmp_path)
    (root / ".gitignore").write_bytes(b"\xff\xfe")

    assert _init(tmp_path, root) == 1

    assert capsys.readouterr().err.startswith("refused: home init: .gitignore exists but")
    assert _written(root) == [".gitignore"]


def test_dry_run_prints_the_merged_settings_and_the_gitignore_change(tmp_path, capsys):
    root = _repo(tmp_path)
    _write(root, ".claude/settings.json", '{"hooks": {}}')
    _write(root, ".gitignore", ".venv/\n")

    assert _init(tmp_path, root, "--dry-run") == 0

    out = capsys.readouterr().out
    merged = (
        f'{{\n  "hooks": {{}},\n  "env": {{\n    "KAIZEN_HOME": "{TILDE_ROOT}"\n  }},\n'
        '  "permissions": {\n    "deny": [\n      "Bash(git stash*)",\n'
        '      "Bash(git -C * stash*)"\n    ]\n  }\n}\n'
    )
    assert f"would write .claude/settings.json:\n{merged}" in out
    assert "would append to .gitignore:\n.claude/worktrees/\n" in out
    assert (root / ".claude" / "settings.json").read_text() == '{"hooks": {}}'
    assert (root / ".gitignore").read_text() == ".venv/\n"


def test_merging_into_existing_settings_and_gitignore_prints_what_each_step_did(tmp_path, capsys):
    root = _repo(tmp_path)
    _write(root, ".claude/settings.json", "{}")
    _write(root, ".gitignore", ".venv/\n")

    _init(tmp_path, root)

    assert capsys.readouterr().out.splitlines()[1:3] == [
        "merged KAIZEN_HOME and the git stash deny rule into .claude/settings.json",
        "added .claude/worktrees/ to .gitignore",
    ]


FINDING = f"notes.md:3:see {TILDE}/elsewhere/plans\n"
"""A tracked line the leak check finds: a path outside the fixture home."""


def test_leak_findings_never_fail_init(tmp_path):
    root = _repo(tmp_path)

    assert _init(tmp_path, root, shell=_shell(root, grep=FINDING)) == 0


def test_each_leak_finding_is_printed_as_a_to_do_with_its_fixes(tmp_path, capsys):
    root = _repo(tmp_path)

    _init(tmp_path, root, shell=_shell(root, grep=FINDING))

    out = capsys.readouterr().out
    assert "searched committed files only" in out
    finding = next(line for line in out.splitlines() if "notes.md:3" in line)
    assert "outside path" in finding
    assert f"{TILDE}/elsewhere/plans" in finding
    for fix in ["register the project", "leak.allow in the home's kaizen.toml", "remove the text"]:
        assert fix in finding


def test_with_no_findings_the_report_says_the_committed_files_were_clean(tmp_path, capsys):
    root = _repo(tmp_path)

    assert _init(tmp_path, root) == 0

    out = capsys.readouterr().out.splitlines()
    assert "leak check: searched committed files only; it found nothing" in out


def test_the_leak_check_searches_the_new_homes_tracked_files(tmp_path):
    root = _repo(tmp_path)
    shell = _shell(root)

    _init(tmp_path, root, shell=shell)

    assert shell.ran("git", "-C", str(root), "grep")


def test_a_failing_leak_search_still_fails_init(tmp_path, capsys):
    root = _repo(tmp_path)
    grep = subprocess.CalledProcessError(2, ["git", "grep"], stderr="fatal: broken index")

    assert _init(tmp_path, root, shell=_shell(root, grep=grep)) == 1

    assert "error: git grep failed" in capsys.readouterr().err


def test_a_refusal_other_than_a_finding_fails_init_as_an_error_since_its_files_are_written(
    tmp_path, capsys
):
    root = _repo(tmp_path)
    grep = RefusalError("some other check", "its fix")

    assert _init(tmp_path, root, shell=_shell(root, grep=grep)) == 1

    err = capsys.readouterr().err
    assert err.startswith("error: home init: the leak check failed:\nsome other check\n")
    assert "refused:" not in err
    assert err.count("fix:") == 1
    assert "kaizen project leak-check" in err
    assert (
        err.splitlines()[-1]
        == "kaizen: exit 1 (failed: the steps printed above are done; finish the rest by hand)"
    )
    assert (root / "kaizen.toml").is_file()


def test_dry_run_skips_the_leak_check_and_says_it_would_run_it(tmp_path, capsys):
    root = _repo(tmp_path)
    shell = _shell(root)

    assert _init(tmp_path, root, "--dry-run", shell=shell) == 0

    assert shell.ran("grep") == []
    assert "would run the leak check over the home's committed files" in capsys.readouterr().out


def test_the_closing_checklist_lists_what_only_the_user_can_do(tmp_path, capsys):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    out = capsys.readouterr().out
    checklist = out.split("still to do, by you:\n")[1].splitlines()
    for item in [
        "restart the session",
        "KAIZEN_HOME",
        "add a page to projects/ for each project",
        "permissions.additionalDirectories",
        "projects/newhome.md: public, check, code_paths",
        "kaizen project leak-check` again after the first commit",
        "commit the result through a PR",
    ]:
        assert any(item in line for line in checklist), item


def test_the_checklists_install_line_says_only_to_have_kaizen_on_the_path(tmp_path, capsys):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    line = next(line for line in capsys.readouterr().out.splitlines() if "AGENTS.md" in line)
    assert "kaizen must be on the PATH; if it is not, ask the user to install it." in line
    assert not any(word in line for word in ["uv", "pip", "git", "http", "/"])


def test_init_help_describes_the_leak_to_dos_and_the_checklist(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["home", "init", "--help"], cwd=tmp_path, env={})

    out = " ".join(capsys.readouterr().out.split())
    for text in [
        "prints each finding as a to-do",
        "searches committed files only, and findings never fail the command",
        "restart the session in the home's root, so KAIZEN_HOME",
        "add a page to projects/ for each project",
        "permissions.additionalDirectories",
        "settle the to-do fields on projects/<repo>.md",
        "kaizen project leak-check` again after the first commit",
        "commit the result through a PR",
        'AGENTS.md: "kaizen must be on the PATH; if it is not, ask the user to install it."',
        "skips the leak check",
    ]:
        assert text in out


def test_the_fresh_marker_comments_name_the_workflow_labels_setting_and_its_default(tmp_path):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    marker = (root / "kaizen.toml").read_text()
    assert "# [[workflow_labels]]\n" in marker
    for name in ["needs-triage", "ready-for-agent", "wayfinder:task"]:
        assert name in marker
    assert len(find_home(root, {}).workflow_labels) == 11


def test_uncommenting_the_fresh_marker_s_workflow_labels_example_sets_that_one_label(tmp_path):
    root = _repo(tmp_path)
    _init(tmp_path, root)
    marker = root / "kaizen.toml"

    marker.write_text(
        re.sub(
            r"^# ((\[\[workflow_labels|name|color|description).*)$",
            r"\1",
            marker.read_text(),
            flags=re.M,
        )
    )

    assert find_home(root, {}).workflow_labels == (
        Label("needs-triage", "fbca04", "Maintainer needs to evaluate this issue"),
    )


def test_each_synced_file_is_written_as_render_gives_it_for_the_new_home(tmp_path):
    root = _repo(tmp_path)

    assert _init(tmp_path, root) == 0

    home = find_home(root, {})
    assert home.synced_version is not None
    rendered = render(home, home.synced_version)
    assert sorted(rendered) == sorted(SYNCED)
    assert [path for path in SYNCED if (root / path).read_text() != rendered[path]] == []


def test_the_starter_overlay_names_each_synced_file_it_adds_to(tmp_path):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    overlay = (root / OVERLAY).read_text()
    assert [path for path in SYNCED if f"`{path}`" not in overlay] == []


def test_the_starter_overlay_says_it_is_the_homes_to_edit(tmp_path):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    assert "This file is the home's, so edit it here." in (root / OVERLAY).read_text()


def test_the_starter_overlay_has_a_section_for_the_homes_tracker_repo(tmp_path):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    assert "\n## issue-conventions.md: the tracker repo\n" in (root / OVERLAY).read_text()


def test_dry_run_prints_every_synced_file_and_the_overlay_and_writes_nothing(tmp_path, capsys):
    root = _repo(tmp_path)

    assert _init(tmp_path, root, "--dry-run") == 0

    out = capsys.readouterr().out
    assert [path for path in DOCS if f"would write {path}:\n" not in out] == []
    assert _written(root) == []


def test_a_rerun_keeps_identical_synced_files_and_overlay(tmp_path, capsys):
    root = _repo(tmp_path)
    _init(tmp_path, root)
    (root / "kaizen.toml").unlink()
    capsys.readouterr()

    assert _init(tmp_path, root) == 0

    out = capsys.readouterr().out.splitlines()
    for path in DOCS:
        assert f"kept {path}, already as init writes it" in out


@pytest.mark.parametrize("which", ["synced", "overlay"])
def test_a_differing_synced_file_or_overlay_is_refused_naming_it_before_any_write(
    tmp_path, capsys, which
):
    root = _repo(tmp_path)
    path = SYNCED[-1] if which == "synced" else OVERLAY
    _write(root, path, "mine\n")

    assert _init(tmp_path, root) == 1

    err = capsys.readouterr().err
    assert err.startswith(f"refused: home init: {path} already exists and differs")
    assert _written(root) == [path]


@pytest.mark.parametrize("command", ["init", "sync"])
def test_no_written_synced_file_or_overlay_holds_a_second_fixture_homes_facts(tmp_path, command):
    other = cli_home(tmp_path)
    facts = [*LEAK_OWN, str(other), str(RELAY), str(SITE), "acme/relay", "owner/site"]
    root = _repo(tmp_path)

    assert _init(tmp_path, root) == 0
    if command == "sync":
        for path in [*SYNCED, ".claude/settings.json"]:
            (root / path).unlink()
        code = main(
            ["home", "sync"],
            run=Shell({}),
            cwd=root,
            env=_env(tmp_path),
            version="1.2.3",
            latest=lambda: None,
        )
        assert code == 0

    written = {path: (root / path).read_text() for path in [*DOCS, ".claude/settings.json"]}
    assert [(p, f) for p, text in written.items() for f in facts if f in text] == []


def test_init_help_names_the_synced_files_and_the_overlay(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["home", "init", "--help"], cwd=tmp_path, env={})

    out = " ".join(capsys.readouterr().out.split())
    assert [text for text in [*SYNCED, OVERLAY, "synced file"] if text not in out] == []


def test_init_records_the_running_version_as_the_synced_version(tmp_path):
    root = _repo(tmp_path)

    assert _init(tmp_path, root, version="3.4.5") == 0

    assert str(find_home(root, {}).synced_version) == "3.4.5"
    assert "uvx --refresh-package kaizen-kit --from kaizen-kit==3.4.5 kaizen home sync --check" in (
        (root / "docs/agents/workflows.md").read_text()
    )


def test_dry_run_lists_the_synced_version(tmp_path, capsys):
    root = _repo(tmp_path)

    _init(tmp_path, root, "--dry-run", version="3.4.5")

    assert '\nsynced_version = "3.4.5"\n' in capsys.readouterr().out


def test_a_new_homes_first_command_does_not_warn(tmp_path, capsys):
    root = _repo(tmp_path)
    _init(tmp_path, root, version="3.4.5")
    capsys.readouterr()

    code = main(
        ["home", "sync", "--check"],
        run=Shell({}),
        cwd=root,
        env={},
        version="3.4.5",
        latest=_no_lookup,
    )

    err = capsys.readouterr().err
    assert (code, [line for line in err.splitlines() if line.startswith("warning:")]) == (0, [])


def test_init_refuses_a_running_version_that_is_not_x_y_z_before_any_write(tmp_path, capsys):
    root = _repo(tmp_path)

    assert _init(tmp_path, root, version="3.4.5.dev0") == 1

    assert capsys.readouterr().err.startswith(
        "refused: home init: kaizen's version 3.4.5.dev0 is not X.Y.Z"
    )
    assert _written(root) == []


def test_a_fresh_repo_gets_a_hook_config_running_every_kaizen_hook(tmp_path):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    assert (root / ".pre-commit-config.yaml").read_text() == f"repos:\n{KAIZEN_REPO_ITEM}"


def test_dry_run_lists_the_hook_entries(tmp_path, capsys):
    root = _repo(tmp_path)

    _init(tmp_path, root, "--dry-run")

    assert f"would write .pre-commit-config.yaml:\nrepos:\n{KAIZEN_REPO_ITEM}" in (
        capsys.readouterr().out
    )


def test_an_existing_hook_config_is_kept_unchanged(tmp_path, capsys):
    root = _repo(tmp_path)
    _write(root, ".pre-commit-config.yaml", "repos: []\n")

    assert _init(tmp_path, root) == 0

    assert (root / ".pre-commit-config.yaml").read_text() == "repos: []\n"
    assert "kept .pre-commit-config.yaml: the home's own;" in capsys.readouterr().out


def test_an_existing_hook_config_without_the_hook_entries_gets_a_to_do_to_add_them(
    tmp_path, capsys
):
    root = _repo(tmp_path)
    _write(root, ".pre-commit-config.yaml", "repos: []\n")

    _init(tmp_path, root)

    checklist = capsys.readouterr().out.split("still to do, by you:")[1]
    assert (
        "add the kaizen hook entries docs/agents/pre-commit-hooks.md lists to"
        " .pre-commit-config.yaml" in checklist
    )


def test_an_existing_hook_config_with_every_kaizen_hook_is_kept_without_a_to_do(tmp_path, capsys):
    root = _repo(tmp_path)
    _write(root, ".pre-commit-config.yaml", f"repos:\n{KAIZEN_REPO_ITEM}  - repo: other\n")

    assert _init(tmp_path, root) == 0

    out = capsys.readouterr().out
    assert "kept .pre-commit-config.yaml: it already runs every kaizen hook" in out
    assert "pre-commit-hooks.md" not in out.split("still to do, by you:")[1]


def test_a_hook_config_that_is_not_text_is_refused_before_any_write(tmp_path, capsys):
    root = _repo(tmp_path)
    (root / ".pre-commit-config.yaml").write_bytes(b"\xff\xfe")

    assert _init(tmp_path, root) == 1

    assert _written(root) == [".pre-commit-config.yaml"]
    assert "refused: home init: .pre-commit-config.yaml exists but can't be read as text" in (
        capsys.readouterr().err
    )


def test_the_checklist_says_to_install_the_hooks(tmp_path, capsys):
    root = _repo(tmp_path)

    _init(tmp_path, root)

    checklist = capsys.readouterr().out.split("still to do, by you:")[1]
    assert f"run `pre-commit install` in {root}" in checklist


def test_init_help_names_the_hook_config_and_that_an_existing_one_is_kept(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["home", "init", "--help"], cwd=tmp_path, env={})

    out = " ".join(capsys.readouterr().out.split())
    assert ".pre-commit-config.yaml the hook config" in out
    assert "an existing one is the home's own and is kept" in out
