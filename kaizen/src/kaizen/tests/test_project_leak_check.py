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
    ADDED_DENIED,
    DENIED,
    Reply,
    Shell,
    failed,
    home_for,
    proto_projects,
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
        leak_check_project(shell, home=home_for(proto_projects(tmp_path)), say=lambda _: None)


def test_a_public_project_is_searched_for_the_patterns_its_home_declares(tmp_path):
    shell = _shell(tmp_path)
    home = replace(home_for(proto_projects(tmp_path)), leak_own=("acme/home",))

    leak_check_project(shell, home=home, say=lambda _: None)

    (grep,) = shell.ran("grep")
    assert grep[grep.index("-e") : grep.index("-e") + 2] == ["-e", "acme/home"]


def test_a_private_project_is_refused_for_text_pointing_outside_the_home(tmp_path):
    shell = _shell(tmp_path, leaks="docs/setup.md:3:see owner/secret\n")

    with pytest.raises(RefusalError, match=r"docs/setup\.md:3: unregistered repo owner/secret"):
        leak_check_project(
            shell, home=home_for(proto_projects(tmp_path, public=False)), say=lambda _: None
        )


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
        leak_check_project(shell, home=home_for(proto_projects(tmp_path)), say=lambda _: None)

    assert not shell.ran("grep")


def test_a_passed_path_outside_any_project_is_refused_with_a_fix_offering_to_pass_one(tmp_path):
    shell = _shell(tmp_path, toplevel="/somewhere/else\n")

    with pytest.raises(RefusalError, match=r"fix: run from, or pass, the root of one of"):
        leak_check_project(
            shell,
            Path("/somewhere/else"),
            home=home_for(proto_projects(tmp_path)),
            say=lambda _: None,
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

    leak_check_project(shell, worktree, home=home_for(proto_projects(tmp_path)), say=lambda _: None)

    (toplevel,) = shell.ran("rev-parse", "--show-toplevel")
    assert toplevel[:3] == ["git", "-C", str(worktree)]
    (grep,) = shell.ran("grep")
    assert grep[:3] == ["git", "-C", str(worktree)]


def test_a_private_projects_ticket_worktree_is_searched(tmp_path):
    worktree = tmp_path / "proto" / ".claude" / "worktrees" / "fix-7-thing"
    shell = _shell(tmp_path, toplevel=f"{worktree}\n", leaks="docs/a.md:3:owner/secret\n")

    projects = proto_projects(tmp_path, public=False)
    with pytest.raises(RefusalError, match=r"docs/a\.md:3: unregistered repo owner/secret"):
        leak_check_project(shell, worktree, home=home_for(projects), say=lambda _: None)

    (grep,) = shell.ran("grep")
    assert grep[:3] == ["git", "-C", str(worktree)]


def test_pointed_at_a_path_outside_any_git_checkout_is_refused_naming_that_path(tmp_path):
    shell = _shell(tmp_path, toplevel=failed("git rev-parse"))

    with pytest.raises(RefusalError, match=r"could not find a git checkout at /no/such/dir"):
        leak_check_project(
            shell, Path("/no/such/dir"), home=home_for(proto_projects(tmp_path)), say=lambda _: None
        )


def test_by_default_it_searches_the_working_trees_tracked_files(tmp_path):
    shell = _shell(tmp_path)

    leak_check_project(shell, home=home_for(proto_projects(tmp_path)), say=lambda _: None)

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
            say=lambda _: None,
        )


def _denying_projects(tmp_path: Path, denied: str = DENIED) -> Path:
    """``proto_projects``, plus ``site`` (``tmp_path / "site"``) whose page denies *denied*."""
    projects = proto_projects(tmp_path)
    site = f"path: {tmp_path / 'site'}\ngithub: owner/site\npublic: false\nleak_deny: {denied}\n"
    (projects / "site.md").write_text(f"---\n{site}---\n")
    return projects


def _denying_shell(tmp_path: Path, worktree: Path | None = None) -> Shell:
    """A shell in ``site``'s main checkout, on ``main``, or in its *worktree* on that worktree's
    branch; the diff adds ``ADDED_DENIED``."""
    return Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{worktree or tmp_path / 'site'}\n",
            ("rev-parse", "--abbrev-ref"): f"{worktree.name if worktree else 'main'}\n",
            ("ls-remote", "--symref"): "ref: refs/heads/main\tHEAD\n",
            ("grep",): failed("git grep"),
            ("diff",): ADDED_DENIED,
        }
    )


def test_a_denied_pattern_on_a_line_the_diff_against_the_default_branch_adds_is_refused(tmp_path):
    shell = _denying_shell(tmp_path)

    with pytest.raises(RefusalError) as refusal:
        leak_check_project(shell, home=home_for(_denying_projects(tmp_path)), say=lambda _: None)

    assert "docs/a.md:4: denied pattern zephyr (fix: remove the text, or change the project's" in (
        str(refusal.value)
    )
    (diff,) = shell.ran("diff")
    assert diff[diff.index("--merge-base") + 1] == "origin/main"


def test_in_a_spec_tickets_worktree_the_diff_is_against_its_integration_branch(tmp_path):
    worktree = tmp_path / "site" / ".claude" / "worktrees" / "spec-206-fix-211-thing"
    shell = _denying_shell(tmp_path, worktree)

    with pytest.raises(RefusalError, match="denied pattern zephyr"):
        leak_check_project(shell, home=home_for(_denying_projects(tmp_path)), say=lambda _: None)

    (diff,) = shell.ran("diff")
    assert diff[:3] == ["git", "-C", str(worktree)]
    assert diff[diff.index("--merge-base") + 1] == "origin/spec-206"


def test_staged_a_denied_pattern_on_a_line_the_index_adds_is_refused(tmp_path):
    shell = _denying_shell(tmp_path)

    with pytest.raises(RefusalError, match=r"docs/a\.md:4: denied pattern zephyr"):
        leak_check_project(
            shell, home=home_for(_denying_projects(tmp_path)), staged=True, say=lambda _: None
        )

    (diff,) = shell.ran("diff")
    assert "--cached" in diff


def test_another_projects_denied_pattern_is_not_searched(tmp_path):
    shell = Shell(
        {("rev-parse", "--show-toplevel"): f"{tmp_path / 'proto'}\n", ("diff",): ADDED_DENIED}
    )

    leak_check_project(shell, home=home_for(_denying_projects(tmp_path)), say=lambda _: None)

    assert not shell.ran("diff")


def test_a_denied_pattern_that_does_not_compile_is_refused_naming_the_page_before_any_search(
    tmp_path,
):
    shell = _denying_shell(tmp_path)

    with pytest.raises(
        RefusalError, match=r"site\.md: leak_deny entry '\(zephyr' is not a regular"
    ):
        leak_check_project(
            shell, home=home_for(_denying_projects(tmp_path, "(zephyr")), say=lambda _: None
        )

    assert not shell.ran("grep")
    assert not shell.ran("diff")


@pytest.mark.parametrize("staged", [False, True], ids=["against the base", "staged"])
def test_a_denied_word_on_no_added_line_passes(tmp_path, staged):
    shell = Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{tmp_path / 'site'}\n",
            ("rev-parse", "--abbrev-ref"): "main\n",
            ("ls-remote", "--symref"): "ref: refs/heads/main\tHEAD\n",
            ("grep",): f"docs/a.md:1:the {DENIED} of owner/site\n",
        }
    )

    leak_check_project(
        shell, home=home_for(_denying_projects(tmp_path)), staged=staged, say=lambda _: None
    )

    assert shell.ran("diff")


def _root_shell(tmp_path: Path, merge_base: Reply = "abc\n") -> Shell:
    """A shell for ``--root`` on the home at ``tmp_path``, on a ticket branch, whose origin is
    ``owner/site``; the diff adds ``ADDED_DENIED``."""
    return Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{tmp_path}\n",
            ("remote", "get-url"): "https://github.com/owner/site\n",
            ("ls-remote", "--symref"): "ref: refs/heads/main\tHEAD\n",
            ("merge-base",): merge_base,
            ("grep",): failed("git grep"),
            ("diff",): ADDED_DENIED,
        }
    )


def test_root_searches_denied_patterns_against_the_default_branch_on_any_branch(tmp_path):
    shell = _root_shell(tmp_path)

    with pytest.raises(RefusalError, match=r"docs/a\.md:4: denied pattern zephyr"):
        leak_check_project(
            shell, home=home_for(_denying_projects(tmp_path)), root=tmp_path, say=lambda _: None
        )

    (diff,) = shell.ran("diff")
    assert diff[diff.index("--merge-base") + 1] == "origin/main"
    assert not shell.ran("rev-parse", "--abbrev-ref")


def test_root_in_a_clone_lacking_the_default_branchs_history_is_refused_before_any_search(
    tmp_path,
):
    shell = _root_shell(tmp_path, merge_base=failed("git merge-base"))

    with pytest.raises(RefusalError, match=r"fetch-depth: 0"):
        leak_check_project(
            shell, home=home_for(_denying_projects(tmp_path)), root=tmp_path, say=lambda _: None
        )

    assert not shell.ran("grep")
