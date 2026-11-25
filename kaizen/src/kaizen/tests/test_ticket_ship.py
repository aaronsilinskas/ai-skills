"""Tests for ``kaizen ticket ship``: the checks before publishing a ticket worktree, then push and
PR.

git and gh are replaced by a recording runner and the registry by a temporary ``projects/``
directory, so no repo, network or real project page is touched.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from kaizen.shared.cli import main
from kaizen.shared.common import RefusalError
from kaizen.tests.conftest import Kaizen
from kaizen.tests.ticket_shell import (
    FOOTER,
    HOME_FOOTER,
    RELAY,
    TILDE,
    Reply,
    Shell,
    ShipShell,
    cli_home,
    failed,
    home_for,
    quiet,
    write_marker,
)
from kaizen.ticket.ship import ship

BRANCH = "fix-1358-double-write"
REMOTE_HEAD = "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n"
ISSUE_OPEN = '{"state": "OPEN", "title": "Each Reboot writes app-state.json twice"}'
NEW_PR = "https://github.com/owner/proto/pull/1400"
OPEN_PR = "https://github.com/owner/proto/pull/1385"
OPEN_PRS = f'[{{"number": 1385, "state": "OPEN", "url": "{OPEN_PR}"}}]'
TITLE = "Persist each Reboot in one app-state.json write"
AUTO_MERGE_OFF = '{"autoMergeRequest": null}'
AUTO_MERGE_ON = '{"autoMergeRequest": {"mergeMethod": "MERGE"}}'


def _setup(tmp_path: Path, public: bool = True) -> tuple[Path, Path, Path]:
    """A registry with one project, its ticket worktree, and a PR body file."""
    projects = tmp_path / "projects"
    projects.mkdir()
    repo = tmp_path / "proto"
    (projects / "proto.md").write_text(
        f"---\npath: {repo}\ngithub: owner/proto\npublic: {str(public).lower()}\n---\n# proto\n"
    )
    worktree = repo / ".claude" / "worktrees" / BRANCH
    worktree.mkdir(parents=True)
    body = tmp_path / "body.md"
    body.write_text("Writes the state once per Reboot.\n")
    return projects, worktree, body


def _shell(show: Reply = "", **overrides: str | BaseException) -> ShipShell:
    answers: dict[tuple[str, ...], Reply] = {
        ("rev-parse", "--abbrev-ref", "HEAD"): overrides.get("branch", f"{BRANCH}\n"),
        ("ls-remote",): REMOTE_HEAD,
        ("status", "--porcelain"): overrides.get("status", ""),
        ("rev-list", "--count"): overrides.get("ahead", "2\n"),
        ("issue", "view"): overrides.get("issue", ISSUE_OPEN),
        ("pr", "list"): overrides.get("prs", "[]"),
        ("grep",): overrides.get("leaks", failed("git grep")),
        ("diff", "--no-color"): overrides.get("added", ""),
        ("diff", "--name-only"): overrides.get("changed", "docs/setup.md\nREADME.md\n"),
        ("diff", "--name-status"): overrides.get("statuses", "M\tengine/maths.py\n"),
        ("pr", "view"): overrides.get("auto_merge", AUTO_MERGE_OFF),
        ("merge-base",): overrides.get("merge_base", "abc123\n"),
        ("show",): show,
        ("push",): overrides.get("push", ""),
    }
    return ShipShell(NEW_PR, answers)


def test_ship_pushes_the_branch_with_upstream_tracking(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.ran("push") == [["git", "-C", str(worktree), "push", "-u", "origin", BRANCH]]


def test_ship_opens_a_pr_from_the_branch_into_the_default_branch(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell()

    shipped = ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    (create,) = shell.ran("pr", "create")
    assert create[: create.index("--body-file")] == [
        "gh",
        "-R",
        "owner/proto",
        "pr",
        "create",
        "--base",
        "main",
        "--head",
        BRANCH,
        "--title",
        TITLE,
    ]
    assert shipped.url == NEW_PR


def test_ship_prepends_closes_to_a_body_that_does_not_close_the_issue(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies == [f"Closes #1358\n\nWrites the state once per Reboot.\n\n{FOOTER}\n"]


def test_ship_ends_the_body_with_the_claude_code_attribution_line(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    body.write_text("Writes the state once.\n\nCloses #1358\n")
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies == [f"Writes the state once.\n\nCloses #1358\n\n{FOOTER}\n"]


def test_ship_writes_the_amended_body_outside_the_ticket_worktree(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    (body_file,) = shell.body_files
    assert not body_file.resolve().is_relative_to(worktree.resolve())
    assert not body_file.exists()


def test_ship_adds_no_second_attribution_line_to_a_body_already_ending_with_it(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    body.write_text(f"Writes the state once.\n\n{FOOTER}\n")
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies == [f"Closes #1358\n\nWrites the state once.\n\n{FOOTER}\n"]


def test_ship_passes_a_body_that_already_closes_the_issue_and_ends_with_attribution_as_is(
    tmp_path,
):
    projects, worktree, body = _setup(tmp_path)
    body.write_text(f"Writes the state once.\n\nCloses #1358\n\n{FOOTER}\n")
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies == [f"Writes the state once.\n\nCloses #1358\n\n{FOOTER}\n"]
    assert body.read_text() == f"Writes the state once.\n\nCloses #1358\n\n{FOOTER}\n"


def _refused(tmp_path, shell, match, worktree=None):
    projects, ticket_worktree, body = _setup(tmp_path)
    with pytest.raises(RefusalError, match=match):
        ship(worktree or ticket_worktree, TITLE, body, shell, home=home_for(projects), say=quiet)
    assert not shell.ran("push")
    assert not shell.ran("pr", "create")


def test_ship_refuses_a_path_outside_every_registered_worktree_root(tmp_path):
    shell = _shell()
    stray = tmp_path / "elsewhere" / BRANCH
    stray.mkdir(parents=True)

    _refused(tmp_path, shell, "is not a registered project's ticket worktree", stray)

    assert not shell.calls


def test_ship_refuses_to_push_the_default_branch(tmp_path):
    shell = _shell(branch="main\n")

    _refused(tmp_path, shell, "is on the default branch main")

    assert not shell.ran("status")


def test_ship_refuses_a_branch_that_is_not_a_ticket_branch(tmp_path):
    shell = _shell(branch="experiment\n")

    _refused(tmp_path, shell, "not a fix-<issue>-<slug> ticket branch")


def test_ship_refuses_a_dirty_working_tree(tmp_path):
    shell = _shell(status=" M src/state.py\n")

    _refused(tmp_path, shell, "has uncommitted changes")

    assert not shell.ran("rev-list")


def test_ship_refuses_a_branch_with_no_commits_ahead_of_the_default_branch(tmp_path):
    shell = _shell(ahead="0\n")

    _refused(tmp_path, shell, "no commits ahead of origin/main")

    assert not shell.ran("issue", "view")


def test_ship_refuses_when_the_issue_was_closed_during_the_work(tmp_path):
    shell = _shell(issue='{"state": "CLOSED", "title": "Old work"}')

    _refused(tmp_path, shell, "#1358 is closed")

    assert not shell.ran("pr", "list")


def test_ship_refuses_a_branch_whose_pr_was_closed_without_merging_and_names_it(tmp_path):
    shell = _shell(
        prs='[{"number": 1390, "state": "CLOSED", "url": "https://github.com/owner/proto/pull/1390"}]'
    )

    _refused(tmp_path, shell, "PR #1390 closed without merging")

    assert not shell.ran("grep")


def test_ship_refuses_a_public_project_whose_leak_check_matches(tmp_path):
    shell = _shell(leaks="docs/setup.md:3:see /fixture/home/relay\n")

    _refused(tmp_path, shell, r"leak check(.|\n)*docs/setup\.md:3")


def test_ship_refuses_a_private_project_pointing_outside_the_home(tmp_path):
    projects, worktree, body = _setup(tmp_path, public=False)
    shell = _shell(leaks="docs/setup.md:3:see owner/secret\n")

    with pytest.raises(RefusalError, match=r"docs/setup\.md:3: unregistered repo owner/secret"):
        ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("push")


def test_the_leak_check_searches_the_worktree_for_each_of_the_homes_own_patterns(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    (grep,) = shell.ran("grep")
    assert grep[:4] == ["git", "-C", str(worktree), "grep"]
    assert {"owner/home", "/fixture/home"} <= set(grep)


def test_a_body_closing_a_different_issue_still_gets_closes_for_this_one(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    body.write_text("Closes #13580\n")
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies == [f"Closes #1358\n\nCloses #13580\n\n{FOOTER}\n"]


def test_reshipping_pushes_the_new_commits_and_reuses_the_open_pr(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell(prs=OPEN_PRS)

    shipped = ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.ran("push")
    assert not shell.ran("pr", "create")
    assert shipped.url == OPEN_PR


def test_reshipping_updates_the_open_prs_title_and_body_from_the_arguments(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell(prs=OPEN_PRS)

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    (edit,) = shell.ran("pr", "edit")
    assert edit[: edit.index("--body-file")] == [
        "gh",
        "-R",
        "owner/proto",
        "pr",
        "edit",
        OPEN_PR,
        "--title",
        TITLE,
    ]
    assert shell.bodies == [f"Closes #1358\n\nWrites the state once per Reboot.\n\n{FOOTER}\n"]


def test_reshipping_adds_no_second_attribution_line_to_the_updated_body(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    body.write_text(f"Writes the state once.\n\n{FOOTER}\n")
    shell = _shell(prs=OPEN_PRS)

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies == [f"Closes #1358\n\nWrites the state once.\n\n{FOOTER}\n"]


def test_reshipping_writes_the_updated_body_outside_the_ticket_worktree(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell(prs=OPEN_PRS)

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    (body_file,) = shell.body_files
    assert not body_file.resolve().is_relative_to(worktree.resolve())
    assert not body_file.exists()


def test_reshipping_prints_that_the_open_pr_was_updated(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell(prs=OPEN_PRS)
    lines: list[str] = []

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=lines.append)

    assert lines[-1] == f"updated the open PR's title and body: {OPEN_PR}"


def test_a_dry_run_reship_says_it_would_update_the_open_pr_and_edits_nothing(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell(prs=OPEN_PRS)
    lines: list[str] = []

    ship(worktree, TITLE, body, shell, home=home_for(projects), dry_run=True, say=lines.append)

    assert not shell.ran("pr", "edit")
    assert lines[-1] == f"would update the open PR's title and body: {OPEN_PR}"


def test_ship_never_force_pushes(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    (push,) = shell.ran("push")
    assert not {"-f", "--force", "--force-with-lease"} & set(push)


def test_ship_prints_the_pr_url_last(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    lines: list[str] = []

    ship(worktree, TITLE, body, _shell(), home=home_for(projects), say=lines.append)

    assert lines[-1] == f"opened PR: {NEW_PR}"


def test_a_dry_run_issues_only_queries(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), dry_run=True, say=quiet)

    assert shell.ran("grep")
    assert not shell.ran("push")
    assert not shell.ran("pr", "create")


def test_ship_refuses_a_missing_body_file_before_running_anything(tmp_path):
    projects, worktree, _ = _setup(tmp_path)
    shell = _shell()

    with pytest.raises(RefusalError, match="could not read the body file"):
        ship(worktree, TITLE, tmp_path / "nope.md", shell, home=home_for(projects), say=quiet)

    assert not shell.calls


def test_the_cli_requires_a_title(kaizen, tmp_path, capsys):
    with pytest.raises(SystemExit):
        kaizen(
            ["ticket", "ship", str(tmp_path), "--body-file", str(tmp_path / "b.md")], run=_shell()
        )

    assert "--title" in capsys.readouterr().err


@pytest.mark.parametrize(
    "line", ["fixes #1358", "Resolved: #1358", "CLOSE #1358", "fix #1358", "resolves #1358"]
)
def test_a_body_using_any_github_closing_keyword_gets_no_extra_closes_line(tmp_path, line):
    projects, worktree, body = _setup(tmp_path)
    body.write_text(f"Writes the state once.\n\n{line}\n")
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies == [f"Writes the state once.\n\n{line}\n\n{FOOTER}\n"]


@pytest.mark.parametrize("dry_run", [False, True])
def test_ship_refuses_a_spec_ticket_worktree_and_points_to_spec_integrate(tmp_path, dry_run):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell(branch="spec-25-fix-1358-double-write\n")

    with pytest.raises(RefusalError, match=r"spec #25(.|\n)*kaizen spec integrate"):
        ship(worktree, TITLE, body, shell, home=home_for(projects), dry_run=dry_run, say=quiet)

    assert not shell.ran("push")
    assert not shell.ran("pr", "create")


DOCS_BRANCH = "docs-fix-typos"


def _docs_setup(
    tmp_path: Path,
    code_paths: str | None = "src/, package.json",
    auto_merge_paths: str | None = None,
) -> tuple[Path, Path, Path]:
    """A registry whose project declares *code_paths* and *auto_merge_paths*, its docs worktree,
    and a PR body file."""
    projects, _, body = _setup(tmp_path)
    for key, value in (("code_paths", code_paths), ("auto_merge_paths", auto_merge_paths)):
        if value is not None:
            _declare(projects, key, value)
    worktree = tmp_path / "proto" / ".claude" / "worktrees" / DOCS_BRANCH
    worktree.mkdir(parents=True)
    return projects, worktree, body


def _declare(projects: Path, key: str, value: str) -> None:
    """Adds *key*: *value* to the frontmatter of the registry's ``proto`` page."""
    page = projects / "proto.md"
    page.write_text(page.read_text().replace("---\n# proto", f"{key}: {value}\n---\n# proto"))


def _docs_shell(**overrides: str) -> ShipShell:
    return _shell(branch=f"{DOCS_BRANCH}\n", **overrides)


def test_shipping_a_docs_ticket_pushes_its_branch(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path)
    shell = _docs_shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.ran("push") == [["git", "-C", str(worktree), "push", "-u", "origin", DOCS_BRANCH]]


def test_a_docs_tickets_pr_body_has_no_closes_line_and_ends_with_the_attribution(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path)
    shell = _docs_shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies == [f"Writes the state once per Reboot.\n\n{FOOTER}\n"]


def test_shipping_a_docs_ticket_reads_no_issue(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path)
    shell = _docs_shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("issue", "view")


def test_shipping_a_docs_ticket_still_runs_the_leak_check(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path)
    shell = _docs_shell(leaks="docs/setup.md:3:see /fixture/home/relay\n")

    with pytest.raises(RefusalError, match="leak check"):
        ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("push")


def test_reshipping_a_docs_ticket_reuses_its_open_pr(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path)
    shell = _docs_shell(prs=OPEN_PRS)

    shipped = ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("pr", "create")
    assert shipped.url == OPEN_PR


def test_reshipping_a_docs_ticket_updates_its_pr_body_with_no_closes_line(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path)
    shell = _docs_shell(prs=OPEN_PRS)

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies == [body.read_text().rstrip() + f"\n\n{FOOTER}\n"]


def test_ship_compares_a_docs_ticket_with_the_default_branch_counting_renames_as_both_paths(
    tmp_path,
):
    projects, worktree, body = _docs_setup(tmp_path)
    shell = _docs_shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.ran("diff", "--name-only") == [
        ["git", "-C", str(worktree), "diff", "--name-only", "--no-renames", "origin/main...HEAD"]
    ]


def test_ship_refuses_a_docs_ticket_that_touches_code_naming_only_the_code_files(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path)
    shell = _docs_shell(changed="docs/setup.md\nsrc/state.py\npackage.json\nsrcs/notes.md\n")

    with pytest.raises(RefusalError) as refused:
        ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    message = str(refused.value)
    assert "src/state.py" in message and "package.json" in message
    assert "docs/setup.md" not in message and "srcs/notes.md" not in message
    assert "open an issue" in message
    assert not shell.ran("push")


def test_ship_refuses_a_docs_ticket_that_touches_a_file_a_glob_code_path_matches(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path, code_paths="*.py, lib/")
    shell = _docs_shell(changed="README.md\nnew_module.py\ndocs/example.py\n")

    with pytest.raises(RefusalError) as refused:
        ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    message = str(refused.value)
    assert "new_module.py" in message and "docs/example.py" not in message
    assert not shell.ran("push")


def test_ship_refuses_a_docs_ticket_of_a_project_that_declares_no_code_paths(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path, code_paths=None)
    shell = _docs_shell()

    with pytest.raises(RefusalError, match="declares no code_paths"):
        ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("push")


DOCS_ONLY = "docs/index.md\ndocs/auto-merge-docs.md\n"
DOCS_AND_README = "docs/index.md\nREADME.md\n"


def test_a_docs_ticket_changing_only_auto_merge_paths_gets_auto_merge_on_its_pr(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path, auto_merge_paths="docs/")
    shell = _docs_shell(changed=DOCS_ONLY)

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.ran("pr", "merge") == [["gh", "pr", "merge", "--auto", "--merge", NEW_PR]]


def test_a_docs_ticket_changing_only_paths_an_auto_merge_glob_matches_gets_auto_merge(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path, auto_merge_paths="**/*.md")
    shell = _docs_shell(changed=DOCS_AND_README)

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.ran("pr", "merge") == [["gh", "pr", "merge", "--auto", "--merge", NEW_PR]]


def test_a_docs_ticket_changing_a_path_outside_auto_merge_paths_gets_no_auto_merge(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path, auto_merge_paths="docs/")
    shell = _docs_shell(changed=DOCS_AND_README)

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("pr", "merge")


def test_ship_names_the_changed_paths_that_kept_a_docs_ticket_from_auto_merging(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path, auto_merge_paths="docs/")
    shell = _docs_shell(changed=DOCS_AND_README)
    lines: list[str] = []

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=lines.append)

    assert "no auto-merge: outside auto_merge_paths (docs/): README.md" in lines


def test_a_docs_ticket_of_a_project_without_auto_merge_paths_gets_no_auto_merge(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path)
    shell = _docs_shell(changed=DOCS_ONLY)

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("pr", "merge")


def test_ship_says_a_project_without_auto_merge_paths_kept_a_docs_ticket_from_auto_merging(
    tmp_path,
):
    projects, worktree, body = _docs_setup(tmp_path)
    lines: list[str] = []

    ship(
        worktree,
        TITLE,
        body,
        _docs_shell(changed=DOCS_ONLY),
        home=home_for(projects),
        say=lines.append,
    )

    assert "no auto-merge: project proto declares no auto_merge_paths" in lines


def _fix_ticket_with_auto_merge_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A ticket closing an issue, whose project auto-merges the one path it changes."""
    projects, worktree, body = _setup(tmp_path)
    _declare(projects, "auto_merge_paths", "docs/")
    return projects, worktree, body


def test_a_ticket_closing_an_issue_never_gets_auto_merge(tmp_path):
    projects, worktree, body = _fix_ticket_with_auto_merge_paths(tmp_path)
    shell = _shell(changed="docs/setup.md\n")

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("pr", "merge")


def test_ship_says_a_ticket_closing_an_issue_waits_for_review(tmp_path):
    projects, worktree, body = _fix_ticket_with_auto_merge_paths(tmp_path)
    lines: list[str] = []

    ship(
        worktree,
        TITLE,
        body,
        _shell(changed="docs/setup.md\n"),
        home=home_for(projects),
        say=lines.append,
    )

    assert "no auto-merge: a ticket closing an issue waits for review" in lines


def test_reshipping_a_docs_ticket_changing_only_auto_merge_paths_auto_merges_its_open_pr(
    tmp_path,
):
    projects, worktree, body = _docs_setup(tmp_path, auto_merge_paths="docs/")
    shell = _docs_shell(changed=DOCS_ONLY, prs=OPEN_PRS)

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.ran("pr", "merge") == [["gh", "pr", "merge", "--auto", "--merge", OPEN_PR]]


def _docs_only_lines(tmp_path: Path) -> list[str]:
    """What ``ship`` prints for a docs ticket changing only its project's auto-merge paths."""
    projects, worktree, body = _docs_setup(tmp_path, auto_merge_paths="docs/")
    lines: list[str] = []
    ship(
        worktree,
        TITLE,
        body,
        _docs_shell(changed=DOCS_ONLY),
        home=home_for(projects),
        say=lines.append,
    )
    return lines


def test_ship_says_why_a_docs_ticket_auto_merges(tmp_path):
    lines = _docs_only_lines(tmp_path)

    assert "auto-merge: every changed path is under auto_merge_paths (docs/)" in lines


def test_ship_prints_that_auto_merge_was_enabled_last(tmp_path):
    lines = _docs_only_lines(tmp_path)

    assert lines[-1] == f"enabled auto-merge: {NEW_PR}"


def test_a_dry_run_says_it_would_enable_auto_merge_and_enables_nothing(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path, auto_merge_paths="docs/")
    shell = _docs_shell(changed=DOCS_ONLY)
    lines: list[str] = []

    ship(worktree, TITLE, body, shell, home=home_for(projects), dry_run=True, say=lines.append)

    assert not shell.ran("pr", "merge")
    assert lines[-1] == "would enable auto-merge on the PR"


def test_a_docs_ticket_with_no_net_change_gets_no_auto_merge(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path, auto_merge_paths="docs/")
    shell = _docs_shell(changed="")

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("pr", "merge")


def test_reshipping_a_docs_ticket_that_no_longer_qualifies_turns_its_pr_auto_merge_off(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path, auto_merge_paths="docs/")
    shell = _docs_shell(changed=DOCS_AND_README, prs=OPEN_PRS, auto_merge=AUTO_MERGE_ON)

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.ran("pr", "merge") == [["gh", "pr", "merge", "--disable-auto", OPEN_PR]]


def test_reshipping_a_docs_ticket_leaves_a_pr_without_auto_merge_alone(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path, auto_merge_paths="docs/")
    shell = _docs_shell(changed=DOCS_AND_README, prs=OPEN_PRS)

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("pr", "merge")


def test_a_dry_run_reship_says_it_would_turn_auto_merge_off_and_changes_nothing(tmp_path):
    projects, worktree, body = _docs_setup(tmp_path, auto_merge_paths="docs/")
    shell = _docs_shell(changed=DOCS_AND_README, prs=OPEN_PRS, auto_merge=AUTO_MERGE_ON)
    lines: list[str] = []

    ship(worktree, TITLE, body, shell, home=home_for(projects), dry_run=True, say=lines.append)

    assert not shell.ran("pr", "merge")
    assert lines[-1] == f"would turn off auto-merge on the open PR: {OPEN_PR}"


SOURCE = '''def double(x):
    """Return twice *x*, explained at some length."""
    return x * 2  # Multiply rather than add.
'''
CUT = SOURCE.replace(", explained at some length", "").replace("  # Multiply rather than add.", "")
FIXED = CUT.replace("x * 2", "x + x")


def _sources(head: str, base: str = SOURCE) -> Reply:
    """A ``git show <ref>:engine/maths.py`` reply: *base* at the merge base, *head* at HEAD."""
    sources = {"abc123:engine/maths.py": base, "HEAD:engine/maths.py": head}

    def show(cmd: list[str]) -> str:
        if cmd[-1] not in sources:
            raise failed("git show")
        return sources[cmd[-1]]

    return show


def _comment_only_ship(tmp_path: Path, head: str, **overrides: str) -> tuple[ShipShell, list[str]]:
    """Ships a ticket closing an issue, changing ``engine/maths.py`` from ``SOURCE`` to *head*, for
    a project that auto-merges comment-only changes; returns the shell and the printed lines."""
    projects, worktree, body = _setup(tmp_path)
    _declare(projects, "auto_merge_comment_only", "true")
    shell = _shell(show=_sources(head), **overrides)
    lines: list[str] = []
    ship(worktree, TITLE, body, shell, home=home_for(projects), say=lines.append)
    return shell, lines


def test_a_ticket_closing_an_issue_with_a_comment_only_change_gets_auto_merge(tmp_path):
    shell, _ = _comment_only_ship(tmp_path, CUT)

    assert shell.ran("pr", "merge") == [["gh", "pr", "merge", "--auto", "--merge", NEW_PR]]


def test_ship_says_a_comment_only_change_auto_merges(tmp_path):
    _, lines = _comment_only_ship(tmp_path, CUT)

    assert "auto-merge: the change only deletes or shrinks comments and docstrings" in lines


def test_a_ticket_closing_an_issue_that_changes_code_gets_no_auto_merge(tmp_path):
    shell, _ = _comment_only_ship(tmp_path, FIXED)

    assert not shell.ran("pr", "merge")


def test_ship_names_what_kept_a_change_from_being_comment_only(tmp_path):
    _, lines = _comment_only_ship(tmp_path, FIXED)

    assert "no auto-merge: not comment-only: engine/maths.py: code changed" in lines


def test_ship_refuses_a_comment_only_check_that_cannot_read_a_changed_file(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    _declare(projects, "auto_merge_comment_only", "true")
    shell = _shell(show=failed("git show", "fatal: bad object"))

    with pytest.raises(RefusalError, match=r"engine/maths\.py"):
        ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("push")


def test_reshipping_a_ticket_closing_an_issue_leaves_auto_merge_alone_without_the_opt_in(
    tmp_path,
):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell(prs=OPEN_PRS, auto_merge=AUTO_MERGE_ON)

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("pr", "merge")


def test_reshipping_a_ticket_that_is_no_longer_comment_only_turns_its_pr_auto_merge_off(tmp_path):
    shell, _ = _comment_only_ship(tmp_path, FIXED, prs=OPEN_PRS, auto_merge=AUTO_MERGE_ON)

    assert shell.ran("pr", "merge") == [["gh", "pr", "merge", "--disable-auto", OPEN_PR]]


def _ship_from_a_home_whose_marker_sets(
    tmp_path: Path, setting: str, *, page_opts_in: bool, **overrides: str
) -> ShipShell:
    """Runs ``kaizen ticket ship`` from a fixture home whose marker adds *setting*, on a ticket
    closing an issue whose change only cuts comments, for a project whose page sets
    ``auto_merge_comment_only: true`` when *page_opts_in*; returns the shell."""
    projects, worktree, body = _setup(tmp_path)
    if page_opts_in:
        _declare(projects, "auto_merge_comment_only", "true")
    write_marker(tmp_path, setting + "\n")
    shell = _shell(show=_sources(CUT), **overrides)
    argv = ["ticket", "ship", str(worktree), "--title", TITLE, "--body-file", str(body)]
    assert main(argv, run=shell, cwd=tmp_path, env={}) == 0
    return shell


def test_a_home_with_the_comment_only_check_off_never_auto_merges_an_opted_in_change(tmp_path):
    shell = _ship_from_a_home_whose_marker_sets(
        tmp_path, "auto_merge_comment_only = false", page_opts_in=True
    )

    assert not shell.ran("pr", "merge")


def test_ship_says_the_home_turns_the_comment_only_check_off(tmp_path, capsys):
    _ship_from_a_home_whose_marker_sets(
        tmp_path, "auto_merge_comment_only = false", page_opts_in=True
    )

    assert "no auto-merge: the home turns the comment-only check off" in capsys.readouterr().out


def test_reshipping_in_a_home_with_the_comment_only_check_off_turns_its_pr_auto_merge_off(
    tmp_path,
):
    shell = _ship_from_a_home_whose_marker_sets(
        tmp_path,
        "auto_merge_comment_only = false",
        page_opts_in=True,
        prs=OPEN_PRS,
        auto_merge=AUTO_MERGE_ON,
    )

    assert shell.ran("pr", "merge") == [["gh", "pr", "merge", "--disable-auto", OPEN_PR]]


def test_a_home_with_the_comment_only_check_on_still_needs_the_project_page_to_opt_in(tmp_path):
    shell = _ship_from_a_home_whose_marker_sets(
        tmp_path, "auto_merge_comment_only = true", page_opts_in=False
    )

    assert not shell.ran("pr", "merge")


def test_a_home_with_the_comment_only_check_on_auto_merges_an_opted_in_comment_only_change(
    tmp_path,
):
    shell = _ship_from_a_home_whose_marker_sets(
        tmp_path, "auto_merge_comment_only = true", page_opts_in=True
    )

    assert shell.ran("pr", "merge") == [["gh", "pr", "merge", "--auto", "--merge", NEW_PR]]


def _rejected(reason: str) -> str:
    """``git push`` stderr for a push of the ticket branch that the remote rejected."""
    return (
        "To github.com:owner/proto.git\n"
        f" ! [rejected]        {BRANCH} -> {BRANCH} ({reason})\n"
        "error: failed to push some refs to 'github.com:owner/proto.git'\n"
    )


def _ship_hub_ticket(kaizen: Kaizen, tmp_path: Path, shell: ShipShell) -> int:
    """Run ``kaizen ticket ship`` on a ticket worktree of ``relay`` in the fixture home."""
    body = tmp_path / "body.md"
    body.write_text("Writes the state once per Reboot.\n")
    worktree = RELAY / ".claude" / "worktrees" / BRANCH
    return kaizen(
        ["ticket", "ship", str(worktree), "--title", TITLE, "--body-file", str(body)], shell
    )


@pytest.mark.parametrize("reason", ["non-fast-forward", "fetch first"])
def test_ship_names_a_diverged_branch_and_says_to_merge_the_default_branch(
    kaizen, tmp_path, capsys, reason
):
    shell = _shell(push=failed("git push", _rejected(reason)))

    assert _ship_hub_ticket(kaizen, tmp_path, shell) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused: ")
    assert f"{BRANCH} has diverged from origin/{BRANCH}" in err
    assert "git merge origin/main" in err


def test_ship_opens_no_pr_after_a_push_rejected_because_the_branch_diverged(kaizen, tmp_path):
    shell = _shell(push=failed("git push", _rejected("non-fast-forward")))

    _ship_hub_ticket(kaizen, tmp_path, shell)

    assert not shell.ran("pr", "create")


def test_ship_keeps_the_generic_message_for_any_other_push_failure(kaizen, tmp_path, capsys):
    stderr = "remote: Permission to owner/proto.git denied.\n"
    shell = _shell(push=failed("git push", stderr))

    assert _ship_hub_ticket(kaizen, tmp_path, shell) == 1

    err = capsys.readouterr().err
    assert err.startswith("error: git push failed")
    assert (
        "kaizen: exit 1 (failed: the steps printed above are done; finish the rest by hand)" in err
    )
    assert "diverged" not in err


def test_ship_refuses_a_pr_body_pointing_outside_the_home_before_any_gh_call(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    body.write_text(f"Why.\nsee {TILDE}/dev/elsewhere/notes\n")
    shell = _shell()

    with pytest.raises(RefusalError, match=r"text for GitHub(.|\n)*PR body as sent line 4: "):
        ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("gh")


def test_ship_refuses_a_pr_body_with_an_own_reference_for_a_public_project(tmp_path):
    projects, worktree, body = _setup(tmp_path, public=True)
    body.write_text("part of /fixture/home/docs\n")
    shell = _shell()

    with pytest.raises(RefusalError, match="PR body as sent line 3: own reference /fixture/home"):
        ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("gh")


def test_ship_sends_a_private_projects_pr_body_with_an_own_reference(tmp_path):
    projects, worktree, body = _setup(tmp_path, public=False)
    body.write_text("part of /fixture/home/docs\n")
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies[0].startswith("Closes #1358\n\npart of /fixture/home/docs\n")


def test_ship_refuses_a_pr_title_pointing_outside_the_home_before_any_gh_call(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    shell = _shell()

    with pytest.raises(RefusalError, match="PR title line 1: unregistered repo owner/secret"):
        ship(worktree, "Port owner/secret's fix", body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("gh")


def _ship_in_home(tmp_path: Path, settings: str, body_text: str, prs: str = "[]") -> ShipShell:
    """Run ``kaizen ticket ship`` on a ``relay`` ticket in a fixture home whose marker holds
    *settings*, with a body file holding *body_text*, while the branch has the PRs *prs*."""
    shell = _shell(prs=prs)
    body = tmp_path / "body.md"
    body.write_text(body_text)
    worktree = RELAY / ".claude" / "worktrees" / BRANCH
    argv = ["ticket", "ship", str(worktree), "--title", TITLE, "--body-file", str(body)]
    assert main(argv, run=shell, cwd=cli_home(tmp_path, settings), env={}) == 0
    return shell


def test_a_marker_without_pr_footer_ends_the_pr_body_with_the_default_footer(tmp_path):
    shell = _ship_in_home(tmp_path, "", "Writes the state once.\n")

    assert shell.bodies == [f"Closes #1358\n\nWrites the state once.\n\n{FOOTER}\n"]


def test_the_homes_footer_ends_the_pr_body(tmp_path):
    shell = _ship_in_home(tmp_path, f'pr_footer = "{HOME_FOOTER}"\n', "Writes the state once.\n")

    assert shell.bodies == [f"Closes #1358\n\nWrites the state once.\n\n{HOME_FOOTER}\n"]


def test_a_body_already_ending_with_the_homes_footer_gets_no_second_copy(tmp_path):
    body_text = f"Writes the state once.\n\n{HOME_FOOTER}\n"

    shell = _ship_in_home(tmp_path, f'pr_footer = "{HOME_FOOTER}"\n', body_text)

    assert shell.bodies == [f"Closes #1358\n\n{body_text}"]


def test_an_empty_footer_leaves_the_pr_body_without_a_footer_line(tmp_path):
    shell = _ship_in_home(tmp_path, 'pr_footer = ""\n', "Writes the state once.\n")

    assert shell.bodies == ["Closes #1358\n\nWrites the state once.\n"]


def test_reshipping_ends_the_updated_pr_body_with_the_homes_footer(tmp_path):
    settings = f'pr_footer = "{HOME_FOOTER}"\n'

    shell = _ship_in_home(tmp_path, settings, "Writes the state once.\n", prs=OPEN_PRS)

    assert shell.ran("pr", "edit")
    assert shell.bodies == [f"Closes #1358\n\nWrites the state once.\n\n{HOME_FOOTER}\n"]


def test_reshipping_with_an_empty_footer_updates_the_pr_body_without_a_footer_line(tmp_path):
    shell = _ship_in_home(tmp_path, 'pr_footer = ""\n', "Writes the state once.\n", prs=OPEN_PRS)

    assert shell.ran("pr", "edit")
    assert shell.bodies == ["Closes #1358\n\nWrites the state once.\n"]


def test_a_footer_written_with_a_trailing_newline_is_not_added_twice(tmp_path):
    body_text = f"Writes the state once.\n\n{HOME_FOOTER}\n"

    shell = _ship_in_home(tmp_path, f'pr_footer = "{HOME_FOOTER}\\n"\n', body_text)

    assert shell.bodies == [f"Closes #1358\n\n{body_text}"]


@pytest.mark.parametrize(
    ("setting", "problem"),
    [
        ("pr_footer = 3\n", "'pr_footer' must be a string"),
        ('pr_footer = "  "\n', "'pr_footer' is only whitespace"),
    ],
    ids=["not a string", "only whitespace"],
)
def test_a_malformed_footer_is_refused_naming_the_marker_before_any_command(
    tmp_path, capsys, setting, problem
):
    shell = _shell()
    home = cli_home(tmp_path, setting)
    worktree = RELAY / ".claude" / "worktrees" / BRANCH
    argv = ["ticket", "ship", str(worktree), "--title", TITLE, "--body-file", "b.md"]

    assert main(argv, run=shell, cwd=home, env={}) == 1

    err = capsys.readouterr().err
    assert f"{home / 'kaizen.toml'} is malformed: {problem}" in err
    assert f"fix {home / 'kaizen.toml'}" in err
    assert shell.calls == []


def _gh_calls(shell: Shell) -> list[list[str]]:
    return [cmd for cmd in shell.calls if cmd[0] == "gh"]


@pytest.mark.parametrize("dry_run", [False, True], ids=["ship", "dry-run"])
@pytest.mark.parametrize("prs", ["[]", OPEN_PRS], ids=["new PR", "open PR"])
def test_a_footer_pointing_outside_the_home_refuses_before_any_gh_call(tmp_path, dry_run, prs):
    projects, worktree, body = _setup(tmp_path)
    home = replace(home_for(projects), pr_footer=f"see {TILDE}/dev/elsewhere/notes")
    shell = _shell(prs=prs)

    with pytest.raises(RefusalError, match="PR body as sent line 5: outside path"):
        ship(worktree, TITLE, body, shell, home=home, say=quiet, dry_run=dry_run)

    assert _gh_calls(shell) == []


def test_a_body_closing_the_issue_by_its_full_reference_gets_no_closes_line(tmp_path):
    projects, worktree, body = _setup(tmp_path)
    body.write_text("Writes the state once.\n\nFixes owner/proto#1358\n")
    shell = _shell()

    ship(worktree, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies == [f"Writes the state once.\n\nFixes owner/proto#1358\n\n{FOOTER}\n"]
