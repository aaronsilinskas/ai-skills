"""Tests for ``kaizen spec ship``: opening a spec's one PR, closing every integrated ticket.

git and gh are replaced by a recording runner and the registry by a temporary ``projects/``
directory, so no repo, network or real project page is touched.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from kaizen.shared.cli import main
from kaizen.shared.common import RefusalError
from kaizen.spec.ship import ship
from kaizen.tests.ticket_shell import (
    FINISHED_PR,
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
    sub_issue_json,
)

TITLE = "One CLI for spec integration"
NEW_PR = "https://github.com/owner/proto/pull/40"
OPEN_PR = "https://github.com/owner/proto/pull/39"
OPEN_PRS = f'[{{"number": 39, "state": "OPEN", "url": "{OPEN_PR}"}}]'
REMOTE_HEAD = "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n"
HEADS = "def456\trefs/heads/spec-25\n"
MERGES = (
    "Integrate spec-25-fix-28-registry-check into spec-25\n"
    "Merge branch 'main' into spec-25\n"
    "Integrate spec-25-fix-29-check-script into spec-25\n"
)


def _sub_issues(*issues: tuple[int, str, str | None]) -> str:
    return "".join(sub_issue_json(n, s, r) for n, s, r in issues)


SUB_ISSUES = _sub_issues((28, "open", None), (29, "open", None))
CLOSES = "Closes #25\nCloses #28\nCloses #29\n\n"


def _setup(tmp_path: Path, public: bool = True) -> tuple[Path, Path]:
    """A registry with one project, and a PR body file."""
    projects = tmp_path / "projects"
    projects.mkdir()
    visibility = str(public).lower()
    page = f"---\npath: {tmp_path / 'proto'}\ngithub: owner/proto\npublic: {visibility}\n---\n"
    (projects / "proto.md").write_text(page)
    body = tmp_path / "body.md"
    body.write_text("Adds the spec lifecycle.\n")
    return projects, body


def _shell(tmp_path: Path, **overrides: Reply) -> ShipShell:
    return ShipShell(
        NEW_PR,
        {
            **FINISHED_PR,
            **({VIEW: overrides["view"]} if "view" in overrides else {}),
            ("rev-parse", "--show-toplevel"): overrides.get("toplevel", f"{tmp_path / 'proto'}\n"),
            ("ls-remote", "--heads"): overrides.get("heads", HEADS),
            ("ls-remote", "--symref"): REMOTE_HEAD,
            ("for-each-ref",): overrides.get("local", ""),
            ("gh", "api"): overrides.get("sub_issues", SUB_ISSUES),
            ("log",): overrides.get("merges", MERGES),
            ("grep",): overrides.get("leaks", failed("git grep")),
            ("diff",): overrides.get("added", ""),
            ("pr", "list"): overrides.get("prs", "[]"),
            **({("pr", "create"): overrides["create"]} if "create" in overrides else {}),
        },
    )


def _ship(tmp_path: Path, shell: Shell, public: bool = True, **kwargs):
    projects, body = _setup(tmp_path, public)
    return ship(25, TITLE, body, shell, home=home_for(projects), say=quiet, **kwargs)


def test_ship_opens_one_ready_pr_from_the_integration_branch_into_the_default_branch(tmp_path):
    shell = _shell(tmp_path)

    shipped = _ship(tmp_path, shell)

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
        "spec-25",
        "--title",
        TITLE,
    ]
    assert "--draft" not in create
    assert shipped.url == NEW_PR


def test_the_body_closes_the_spec_and_each_integrated_ticket_before_the_given_body(tmp_path):
    shell = _shell(tmp_path)

    _ship(tmp_path, shell)

    assert shell.bodies == [CLOSES + f"Adds the spec lifecycle.\n\n{FOOTER}\n"]


def test_the_body_ends_with_the_claude_code_attribution_line_exactly_once(tmp_path):
    shell = _shell(tmp_path)
    projects, body = _setup(tmp_path)
    body.write_text(f"Adds the spec lifecycle.\n\n{FOOTER}\n")

    ship(25, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies == [CLOSES + f"Adds the spec lifecycle.\n\n{FOOTER}\n"]


def test_integrated_tickets_are_read_from_the_integration_branchs_merge_subjects(tmp_path):
    shell = _shell(tmp_path)

    _ship(tmp_path, shell)

    (log,) = shell.ran("log")
    assert log[:3] == ["git", "-C", str(tmp_path / "proto")]
    assert "origin/spec-25" in log


def _refused(tmp_path: Path, shell: Shell, match: str, body: Path | None = None) -> None:
    projects, written = _setup(tmp_path)
    with pytest.raises(RefusalError, match=match):
        ship(25, TITLE, body or written, shell, home=home_for(projects), say=quiet)
    assert not shell.ran("pr", "create")
    assert not shell.ran("push")


def test_ship_refuses_and_names_each_open_sub_issue_with_no_integration_merge(tmp_path):
    sub_issues = _sub_issues((28, "open", None), (29, "open", None), (30, "open", None))
    shell = _shell(tmp_path, sub_issues=sub_issues, merges="Merge pull request #28\n")

    _refused(tmp_path, shell, r"open sub-issue\(s\): #28 T28, #29 T29, #30 T30")


def test_a_merge_integrating_a_ticket_into_another_spec_does_not_count(tmp_path):
    merges = (
        "Integrate spec-24-fix-28-registry-check into spec-24\n"
        "Integrate spec-25-fix-29-check-script into spec-25\n"
    )
    shell = _shell(tmp_path, merges=merges)

    _refused(tmp_path, shell, r"open sub-issue\(s\): #28 T28\n")


def test_ship_refuses_a_spec_whose_integration_branch_origin_lacks(tmp_path):
    shell = _shell(tmp_path, heads="")

    _refused(tmp_path, shell, r"origin has no spec-25(.|\n)*`kaizen spec start 25`")
    assert not shell.ran("fetch")


def test_ship_refuses_a_spec_started_with_local_whose_branch_is_not_pushed_yet(tmp_path):
    shell = _shell(tmp_path, heads="", local="abc123\n")

    _refused(tmp_path, shell, r"started with --local(.|\n)*`kaizen spec integrate")
    assert not shell.ran("fetch")


def test_ship_refuses_a_public_project_whose_integration_branch_leaks(tmp_path):
    shell = _shell(tmp_path, leaks="origin/spec-25:docs/a.md:3:see /fixture/home/relay\n")

    _refused(tmp_path, shell, r"leak check(.|\n)*docs/a\.md:3")


def test_the_leak_check_searches_the_integration_branchs_tip(tmp_path):
    shell = _shell(tmp_path)

    _ship(tmp_path, shell)

    (grep,) = shell.ran("grep")
    assert grep[-1] == "origin/spec-25"


def test_ship_refuses_a_private_project_whose_integration_branch_points_outside_the_home(
    tmp_path,
):
    shell = _shell(tmp_path, leaks="origin/spec-25:docs/a.md:3:see owner/secret\n")

    with pytest.raises(RefusalError, match=r"docs/a\.md:3: unregistered repo owner/secret"):
        _ship(tmp_path, shell, public=False)

    assert not shell.ran("pr", "create")


def test_ship_refuses_an_unreadable_body_file_before_running_anything(tmp_path):
    shell = _shell(tmp_path)

    _refused(tmp_path, shell, "could not read the body file", body=tmp_path / "nope.md")
    assert not shell.calls


def test_sub_issues_closed_as_not_planned_get_no_closes_line_and_are_reported(tmp_path):
    sub_issues = _sub_issues((28, "open", None), (29, "open", None), (31, "closed", "not_planned"))
    shell = _shell(tmp_path, sub_issues=sub_issues)
    projects, body = _setup(tmp_path)
    lines: list[str] = []

    ship(25, TITLE, body, shell, home=home_for(projects), say=lines.append)

    assert shell.bodies == [CLOSES + f"Adds the spec lifecycle.\n\n{FOOTER}\n"]
    assert "skipping sub-issue(s) closed as not planned: #31 T31" in lines


def test_an_open_pr_for_the_integration_branch_is_reused(tmp_path):
    pr = '[{"number": 39, "state": "OPEN", "url": "https://github.com/owner/proto/pull/39"}]'
    shell = _shell(tmp_path, prs=pr)

    shipped = _ship(tmp_path, shell)

    assert not shell.ran("pr", "create")
    assert shipped.url == "https://github.com/owner/proto/pull/39"
    (lookup,) = shell.ran("pr", "list")
    assert lookup[lookup.index("--head") + 1] == "spec-25"


def test_reusing_the_open_pr_updates_its_title_and_body_from_the_arguments(tmp_path):
    shell = _shell(tmp_path, prs=OPEN_PRS)

    _ship(tmp_path, shell)

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
    assert shell.bodies == [CLOSES + f"Adds the spec lifecycle.\n\n{FOOTER}\n"]


def test_reusing_the_open_pr_prints_that_it_was_updated(tmp_path):
    projects, body = _setup(tmp_path)
    lines: list[str] = []

    ship(25, TITLE, body, _shell(tmp_path, prs=OPEN_PRS), home=home_for(projects), say=lines.append)

    assert lines[-1] == f"updated the open PR's title and body: {OPEN_PR}"


def test_a_dry_run_with_an_open_pr_says_it_would_update_it_and_edits_nothing(tmp_path):
    shell = _shell(tmp_path, prs=OPEN_PRS)
    projects, body = _setup(tmp_path)
    lines: list[str] = []

    ship(25, TITLE, body, shell, home=home_for(projects), dry_run=True, say=lines.append)

    assert not shell.ran("pr", "edit")
    assert lines[-2] == f"would update the open PR's title and body: {OPEN_PR}"


def test_a_dry_run_issues_only_queries_and_prints_the_plan(tmp_path):
    shell = _shell(tmp_path)
    projects, body = _setup(tmp_path)
    lines: list[str] = []

    ship(25, TITLE, body, shell, home=home_for(projects), dry_run=True, say=lines.append)

    assert shell.ran("grep")
    assert not shell.ran("fetch")
    assert not shell.ran("pr", "create")
    assert lines[-2] == f"would open a ready PR from spec-25 into main: {TITLE}"


def test_ship_prints_one_line_per_completed_step(tmp_path):
    projects, body = _setup(tmp_path)
    lines: list[str] = []

    ship(25, TITLE, body, _shell(tmp_path), home=home_for(projects), say=lines.append)

    repo = tmp_path / "proto"
    assert lines == [
        f"proto project at {repo}",
        "origin has spec-25",
        f"fetched origin in {repo}",
        "2 integrated ticket(s): #28, #29",
        "leak check found nothing in origin/spec-25",
        f"opened PR: {NEW_PR}",
    ]


def test_a_failed_pr_create_leaves_the_completed_steps_printed_above_the_error(
    kaizen, tmp_path, capsys
):
    _, body = _setup(tmp_path)
    shell = _shell(tmp_path, toplevel=f"{RELAY}\n", create=failed("gh pr create", "HTTP 502"))

    code = kaizen(["spec", "ship", "25", "--title", TITLE, "--body-file", str(body)], run=shell)

    assert code == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines()[-1] == "leak check found nothing in origin/spec-25"
    assert captured.err.startswith("error: gh pr create failed")


def test_ship_refuses_a_pr_body_pointing_outside_the_home_before_any_gh_call(tmp_path):
    projects, body = _setup(tmp_path)
    body.write_text(f"Why.\nsee {TILDE}/dev/elsewhere/notes\n")
    shell = _shell(tmp_path)

    with pytest.raises(RefusalError, match=r"text for GitHub(.|\n)*PR body as sent line 4: "):
        ship(25, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("gh")


def test_ship_refuses_a_pr_body_with_an_own_reference_for_a_public_project(tmp_path):
    projects, body = _setup(tmp_path, public=True)
    body.write_text("part of owner/home\n")
    shell = _shell(tmp_path)

    with pytest.raises(RefusalError, match="PR body as sent line 3: own reference owner/home"):
        ship(25, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("gh")


def test_ship_sends_a_private_projects_pr_body_with_an_own_reference(tmp_path):
    projects, body = _setup(tmp_path, public=False)
    body.write_text("part of /fixture/home/docs\n")
    shell = _shell(tmp_path)

    ship(25, TITLE, body, shell, home=home_for(projects), say=quiet)

    assert shell.bodies[0].startswith(f"{CLOSES}part of /fixture/home/docs\n")


def _ship_in_home(tmp_path: Path, settings: str, body_text: str, prs: str = "[]") -> ShipShell:
    """Run ``kaizen spec ship 25`` in ``relay`` in a fixture home whose marker holds *settings*,
    with a body file holding *body_text*, while ``spec-25`` has the PRs *prs*."""
    shell = _shell(tmp_path, toplevel=f"{RELAY}\n", prs=prs)
    body = tmp_path / "body.md"
    body.write_text(body_text)
    argv = ["spec", "ship", "25", "--title", TITLE, "--body-file", str(body)]
    assert main(argv, run=shell, cwd=cli_home(tmp_path, settings), env={}) == 0
    return shell


def test_a_marker_without_pr_footer_ends_the_spec_pr_body_with_the_default_footer(tmp_path):
    shell = _ship_in_home(tmp_path, "", "Adds the spec lifecycle.\n")

    assert shell.bodies == [CLOSES + f"Adds the spec lifecycle.\n\n{FOOTER}\n"]


def test_the_homes_footer_ends_the_spec_pr_body(tmp_path):
    shell = _ship_in_home(tmp_path, f'pr_footer = "{HOME_FOOTER}"\n', "Adds the spec lifecycle.\n")

    assert shell.bodies == [CLOSES + f"Adds the spec lifecycle.\n\n{HOME_FOOTER}\n"]


def test_a_spec_pr_body_already_ending_with_the_homes_footer_gets_no_second_copy(tmp_path):
    body_text = f"Adds the spec lifecycle.\n\n{HOME_FOOTER}\n"

    shell = _ship_in_home(tmp_path, f'pr_footer = "{HOME_FOOTER}"\n', body_text)

    assert shell.bodies == [CLOSES + body_text]


def test_an_empty_footer_leaves_the_spec_pr_body_without_a_footer_line(tmp_path):
    shell = _ship_in_home(tmp_path, 'pr_footer = ""\n', "Adds the spec lifecycle.\n")

    assert shell.bodies == [CLOSES + "Adds the spec lifecycle.\n"]


def test_reshipping_a_spec_ends_the_updated_pr_body_with_the_homes_footer(tmp_path):
    settings = f'pr_footer = "{HOME_FOOTER}"\n'

    shell = _ship_in_home(tmp_path, settings, "Adds the spec lifecycle.\n", prs=OPEN_PRS)

    assert shell.ran("pr", "edit")
    assert shell.bodies == [CLOSES + f"Adds the spec lifecycle.\n\n{HOME_FOOTER}\n"]


def test_reshipping_a_spec_with_an_empty_footer_updates_the_body_without_a_footer_line(tmp_path):
    shell = _ship_in_home(tmp_path, 'pr_footer = ""\n', "Adds the spec lifecycle.\n", prs=OPEN_PRS)

    assert shell.ran("pr", "edit")
    assert shell.bodies == [CLOSES + "Adds the spec lifecycle.\n"]


def _gh_calls(shell: Shell) -> list[list[str]]:
    return [cmd for cmd in shell.calls if cmd[0] == "gh"]


def _gh_pr_calls(shell: Shell) -> list[list[str]]:
    return shell.ran("pr", "list") + shell.ran("pr", "create") + shell.ran("pr", "edit")


@pytest.mark.parametrize("dry_run", [False, True], ids=["ship", "dry-run"])
@pytest.mark.parametrize("prs", ["[]", OPEN_PRS], ids=["new PR", "open PR"])
def test_a_footer_pointing_outside_the_home_refuses_before_any_gh_call(tmp_path, dry_run, prs):
    projects, body = _setup(tmp_path)
    home = replace(home_for(projects), pr_footer=f"see {TILDE}/dev/elsewhere/notes")
    shell = _shell(tmp_path, prs=prs)

    with pytest.raises(RefusalError, match="PR body as sent line 5: outside path"):
        ship(25, TITLE, body, shell, home=home, say=quiet, dry_run=dry_run)

    assert _gh_calls(shell) == []


VIEW = ("state,mergeable,baseRefName",)
"""The words of the ``gh pr view`` each poll of ship's wait on its PR runs."""


def _ship_relay_spec(tmp_path: Path, shell: ShipShell) -> int:
    """Runs ``kaizen spec ship 25`` in ``relay`` in the fixture home and returns its exit code."""
    body = tmp_path / "body.md"
    body.write_text("Adds the spec lifecycle.\n")
    argv = ["spec", "ship", "25", "--title", TITLE, "--body-file", str(body)]
    return main(argv, run=shell, cwd=cli_home(tmp_path), env={})


def test_spec_ship_waits_on_its_pr_in_the_projects_repo_after_opening_it(tmp_path):
    shell = _shell(tmp_path, toplevel=f"{RELAY}\n")

    assert _ship_relay_spec(tmp_path, shell) == 0

    opened = shell.calls.index(shell.ran("pr", "create")[0])
    (view, *_) = shell.ran("gh", "-R", "acme/relay", "pr", "view", NEW_PR)
    assert shell.calls.index(view) > opened


def test_spec_ship_says_a_pr_that_conflicts_with_its_base_is_not_finished(tmp_path, capsys):
    conflicting = '{"state": "OPEN", "mergeable": "CONFLICTING", "baseRefName": "main"}'
    shell = _shell(tmp_path, toplevel=f"{RELAY}\n", view=conflicting)

    assert _ship_relay_spec(tmp_path, shell) == 1

    assert capsys.readouterr().err.splitlines()[-2] == (
        f"not finished: PR {NEW_PR} conflicts with main (merge origin/main into its branch); "
        "fix it, commit and ship again"
    )


def test_a_spec_dry_run_ends_saying_it_would_wait_and_waits_on_nothing(tmp_path):
    shell = _shell(tmp_path)
    projects, body = _setup(tmp_path)
    lines: list[str] = []

    ship(25, TITLE, body, shell, home=home_for(projects), dry_run=True, say=lines.append)

    assert lines[-1] == "would wait until the PR's checks pass and it merges cleanly"
    assert not shell.ran(*VIEW)
