"""Tests for ``kaizen project leak-check``: the leak check run on its own, before a push.

git is replaced by a recording runner and the registry by a temporary ``projects/`` directory,
so no repo or real project page is touched.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from kaizen.project.leak_check import leak_check_project
from kaizen.shared.common import RefusalError
from kaizen.tests.ticket_shell import (
    Reply,
    Shell,
    failed,
    home_for,
    proto_projects,
    quiet,
)


def _shell(tmp_path: Path, **overrides: Reply) -> Shell:
    return Shell(
        {
            ("rev-parse", "--show-toplevel"): overrides.get("toplevel", f"{tmp_path / 'proto'}\n"),
            ("grep",): overrides.get("leaks", failed("git grep")),
        }
    )


def test_a_public_project_with_no_reference_to_its_home_passes_and_says_so(tmp_path):
    shell = _shell(tmp_path)
    lines: list[str] = []

    leak_check_project(shell, home=home_for(proto_projects(tmp_path)), say=lines.append)

    (grep,) = shell.ran("grep")
    assert grep[:3] == ["git", "-C", str(tmp_path / "proto")]
    assert lines == [f"leak check found nothing in proto at {tmp_path / 'proto'}"]


def test_a_public_project_that_references_its_home_is_refused_with_every_matching_line(tmp_path):
    leaks = "docs/setup.md:3:see /fixture/home/relay\nREADME.md:9:owner/home#5\n"
    shell = _shell(tmp_path, leaks=leaks)

    with pytest.raises(RefusalError, match=r"leak check(.|\n)*docs/setup\.md:3(.|\n)*README\.md:9"):
        leak_check_project(shell, home=home_for(proto_projects(tmp_path)), say=quiet)


def test_a_public_project_is_searched_for_the_patterns_its_home_declares(tmp_path):
    shell = _shell(tmp_path)
    home = replace(home_for(proto_projects(tmp_path)), leak_own=("acme/home",))

    leak_check_project(shell, home=home, say=quiet)

    (grep,) = shell.ran("grep")
    assert grep[grep.index("-e") : grep.index("-e") + 2] == ["-e", "acme/home"]


def test_a_private_project_is_refused_for_text_pointing_outside_the_home(tmp_path):
    shell = _shell(tmp_path, leaks="docs/setup.md:3:see owner/secret\n")

    with pytest.raises(RefusalError, match=r"docs/setup\.md:3: unregistered repo owner/secret"):
        leak_check_project(shell, home=home_for(proto_projects(tmp_path, public=False)), say=quiet)


def test_a_private_project_is_not_searched_for_its_homes_own_patterns(tmp_path):
    shell = _shell(tmp_path, leaks="docs/setup.md:3:see /fixture/home/relay\n")
    lines: list[str] = []

    leak_check_project(
        shell, home=home_for(proto_projects(tmp_path, public=False)), say=lines.append
    )

    (grep,) = shell.ran("grep")
    assert "/fixture/home" not in grep
    assert lines == [f"leak check found nothing in proto at {tmp_path / 'proto'}"]


def test_running_outside_a_registered_projects_main_checkout_is_refused(tmp_path):
    shell = _shell(tmp_path, toplevel="/somewhere/else\n")

    with pytest.raises(RefusalError, match=r"/somewhere/else is not a registered project"):
        leak_check_project(shell, home=home_for(proto_projects(tmp_path)), say=quiet)

    assert not shell.ran("grep")


def test_a_passed_path_outside_any_project_is_refused_with_a_fix_offering_to_pass_one(tmp_path):
    shell = _shell(tmp_path, toplevel="/somewhere/else\n")

    with pytest.raises(RefusalError, match=r"fix: run from, or pass, the root of one of"):
        leak_check_project(
            shell,
            Path("/somewhere/else"),
            home=home_for(proto_projects(tmp_path)),
            say=quiet,
        )


def test_run_in_a_public_projects_ticket_worktree_it_searches_that_worktree(tmp_path):
    worktree = tmp_path / "proto" / ".claude" / "worktrees" / "fix-7-thing"
    shell = _shell(tmp_path, toplevel=f"{worktree}\n")
    lines: list[str] = []

    leak_check_project(shell, home=home_for(proto_projects(tmp_path)), say=lines.append)

    (grep,) = shell.ran("grep")
    assert grep[:3] == ["git", "-C", str(worktree)]
    assert lines == [f"leak check found nothing in proto at {worktree}"]


def test_pointed_at_a_ticket_worktree_it_searches_that_worktree_wherever_it_runs(tmp_path):
    worktree = tmp_path / "proto" / ".claude" / "worktrees" / "fix-7-thing"
    shell = _shell(tmp_path, toplevel=f"{worktree}\n")

    leak_check_project(shell, worktree, home=home_for(proto_projects(tmp_path)), say=quiet)

    (toplevel,) = shell.ran("rev-parse", "--show-toplevel")
    assert toplevel[:3] == ["git", "-C", str(worktree)]
    (grep,) = shell.ran("grep")
    assert grep[:3] == ["git", "-C", str(worktree)]


def test_a_private_projects_ticket_worktree_is_searched(tmp_path):
    worktree = tmp_path / "proto" / ".claude" / "worktrees" / "fix-7-thing"
    shell = _shell(tmp_path, toplevel=f"{worktree}\n", leaks="docs/a.md:3:owner/secret\n")

    projects = proto_projects(tmp_path, public=False)
    with pytest.raises(RefusalError, match=r"docs/a\.md:3: unregistered repo owner/secret"):
        leak_check_project(shell, worktree, home=home_for(projects), say=quiet)

    (grep,) = shell.ran("grep")
    assert grep[:3] == ["git", "-C", str(worktree)]


def test_pointed_at_a_path_outside_any_git_checkout_is_refused_naming_that_path(tmp_path):
    shell = _shell(tmp_path, toplevel=failed("git rev-parse"))

    with pytest.raises(RefusalError, match=r"could not find a git checkout at /no/such/dir"):
        leak_check_project(
            shell, Path("/no/such/dir"), home=home_for(proto_projects(tmp_path)), say=quiet
        )


def test_by_default_it_searches_the_working_trees_tracked_files(tmp_path):
    shell = _shell(tmp_path)

    leak_check_project(shell, home=home_for(proto_projects(tmp_path)), say=quiet)

    (grep,) = shell.ran("grep")
    assert "--cached" not in grep


def test_staged_it_searches_the_index_and_says_so(tmp_path):
    shell = _shell(tmp_path)
    lines: list[str] = []

    leak_check_project(
        shell, home=home_for(proto_projects(tmp_path)), staged=True, say=lines.append
    )

    (grep,) = shell.ran("grep")
    assert "--cached" in grep
    assert lines == [f"leak check found nothing staged in proto at {tmp_path / 'proto'}"]


def test_staged_a_leak_in_the_index_is_refused_with_the_usual_findings(tmp_path):
    shell = _shell(tmp_path, leaks="docs/setup.md:3:see owner/secret\n")

    with pytest.raises(RefusalError, match=r"docs/setup\.md:3: unregistered repo owner/secret"):
        leak_check_project(
            shell,
            home=home_for(proto_projects(tmp_path, public=False)),
            staged=True,
            say=quiet,
        )
