"""Tests for ``kaizen spec publish``: preconditions and the git/gh commands it issues.

``git`` and ``gh`` are replaced by a recording runner, so no repo state or network is touched.
"""

from pathlib import Path

import pytest

from kaizen.shared.cli import main
from kaizen.shared.common import RefusalError
from kaizen.shared.home import Home
from kaizen.spec.publish import publish, split_spec
from kaizen.tests.ticket_shell import (
    FOOTER,
    HOME_FOOTER,
    RELAY,
    TILDE,
    cli_home,
    home_for,
    quiet,
)

TOPLEVEL = "/fixture/proto"
"""The git checkout ``kaizen spec publish`` runs in: the main checkout of ``proto``, ``_home``'s one
project."""


class _Shell:
    """Records each command and answers the queries ``kaizen spec publish`` makes."""

    def __init__(
        self,
        branch: str = "main",
        staged: str = "",
        status: str = "",
        grep: str = "",
        toplevel: str = TOPLEVEL,
    ) -> None:
        self.toplevel = toplevel
        self.calls: list[list[str]] = []
        self.bodies: list[str] = []
        self._answers: dict[tuple[str, ...], str] = {
            ("git", "rev-parse"): branch + "\n",
            ("git", "diff"): staged,
            ("git", "status"): status,
            ("git", "grep"): grep,
            ("issue", "create"): "https://github.com/o/r/issues/300\n",
            ("pr", "create"): "https://github.com/o/r/pull/301\n",
        }

    def __call__(self, cmd: list[str]) -> str:
        self.calls.append(cmd)
        if cmd[0] == "git" and "grep" in cmd:
            return self._answers[("git", "grep")]
        if "--show-toplevel" in cmd:
            return self.toplevel + "\n"
        if cmd[1:3] == ["issue", "create"]:
            self.bodies.append(Path(cmd[cmd.index("--body-file") + 1]).read_text())
            return self._answers[("issue", "create")]
        return self._answers.get((cmd[0], cmd[1]), self._answers.get(tuple(cmd[1:3]), ""))

    def ran(self, *prefix: str) -> list[list[str]]:
        return [c for c in self.calls if c[: len(prefix)] == list(prefix)]


def _home(tmp_path: Path, public: bool = False, toplevel: str = TOPLEVEL) -> Home:
    """A fixture home registering ``proto``, whose main checkout is *toplevel*."""
    projects = tmp_path / "home" / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    page = f"path: {toplevel}\ngithub: owner/proto\npublic: {str(public).lower()}\n"
    (projects / "proto.md").write_text(f"---\n{page}---\n")
    return home_for(projects)


def _spec(tmp_path: Path, text: str = "# Retire things\n\n## Problem Statement\n\nWhy.\n") -> Path:
    path = tmp_path / "retire-things.md"
    path.write_text(text)
    return path


def test_the_spec_issue_takes_its_title_from_the_heading_and_its_body_from_the_rest(tmp_path):
    shell = _Shell()

    number = publish(_spec(tmp_path), None, None, shell, quiet, home=_home(tmp_path))

    (create,) = shell.ran("gh", "issue", "create")
    assert create[create.index("--title") + 1] == "Retire things"
    assert create[create.index("--label") + 1] == "spec"
    assert shell.bodies == ["## Problem Statement\n\nWhy.\n"]
    assert number == 300


def test_the_local_spec_file_is_deleted_after_publishing(tmp_path):
    spec = _spec(tmp_path)

    publish(spec, None, None, _Shell(), quiet, home=_home(tmp_path))

    assert not spec.exists()


def test_the_source_idea_is_closed_as_superseded_by_the_spec(tmp_path):
    shell = _Shell()

    publish(_spec(tmp_path), 1179, None, shell, quiet, home=_home(tmp_path))

    (close,) = shell.ran("gh", "issue", "close")
    assert close[3] == "1179"
    assert close[close.index("--comment") + 1] == "Superseded by spec #300."


def test_without_domain_doc_changes_no_branch_or_pr_is_made(tmp_path):
    shell = _Shell(status="")

    publish(_spec(tmp_path), None, None, shell, quiet, home=_home(tmp_path))

    assert not shell.ran("git", "checkout")
    assert not shell.ran("gh", "pr")


def test_domain_doc_changes_ship_alone_in_an_auto_merging_pr_that_references_the_spec(tmp_path):
    shell = _Shell(status=" M GLOSSARY.md\n?? docs/adr/0009-thing.md\n")

    publish(_spec(tmp_path), None, "A Bot <bot@example.com>", shell, quiet, home=_home(tmp_path))

    assert shell.ran("git", "checkout", "-b") == [["git", "checkout", "-b", "spec-300-domain-docs"]]
    assert shell.ran("git", "add") == [
        ["git", "add", "--", "GLOSSARY.md", "docs/adr/0009-thing.md"]
    ]
    (commit,) = shell.ran("git", "commit")
    assert commit[-1].endswith("\n\nCo-Authored-By: A Bot <bot@example.com>")
    (pr,) = shell.ran("gh", "pr", "create")
    assert "Refs #300" in pr[pr.index("--body") + 1]
    assert shell.ran("gh", "pr", "merge") == [
        ["gh", "pr", "merge", "--auto", "--merge", "https://github.com/o/r/pull/301"]
    ]


def test_publishing_ends_on_main_without_the_local_docs_branch(tmp_path):
    shell = _Shell(status=" M GLOSSARY.md\n")

    publish(_spec(tmp_path), None, None, shell, quiet, home=_home(tmp_path))

    assert shell.calls[-2:] == [
        ["git", "checkout", "main"],
        ["git", "branch", "-D", "spec-300-domain-docs"],
    ]


def test_off_main_nothing_is_published(tmp_path):
    shell = _Shell(branch="feature")

    with pytest.raises(RefusalError, match="main"):
        publish(_spec(tmp_path), None, None, shell, quiet, home=_home(tmp_path))

    assert not shell.ran("gh")


def test_with_something_already_staged_nothing_is_published(tmp_path):
    shell = _Shell(staged="effects/thing.py\n")

    with pytest.raises(RefusalError, match="unstage"):
        publish(_spec(tmp_path), None, None, shell, quiet, home=_home(tmp_path))

    assert not shell.ran("gh")


@pytest.mark.parametrize("text", ["## Problem Statement\n", "#   \n\nbody\n", "intro\n# Title\n"])
def test_a_spec_without_a_leading_title_is_rejected(text):
    with pytest.raises(RefusalError, match="title"):
        split_spec(text)


def test_a_spec_body_pointing_outside_the_home_is_refused_before_any_gh_call(tmp_path):
    spec = _spec(tmp_path, f"# Retire things\n\nWhy.\nsee {TILDE}/dev/elsewhere/notes\n")
    shell = _Shell()

    with pytest.raises(RefusalError, match=r"text for GitHub(.|\n)*issue body line 2: "):
        publish(spec, None, None, shell, quiet, home=_home(tmp_path))

    assert not shell.ran("gh")
    assert spec.exists()


def test_a_spec_body_with_an_own_reference_is_refused_for_a_public_project(tmp_path):
    spec = _spec(tmp_path, "# Retire things\n\npart of owner/home\n")
    shell = _Shell()

    with pytest.raises(RefusalError, match="issue body line 1: own reference owner/home"):
        publish(spec, None, None, shell, quiet, home=_home(tmp_path, public=True))

    assert not shell.ran("gh")


def test_a_private_projects_spec_body_with_an_own_reference_is_published(tmp_path):
    shell = _Shell()
    spec = _spec(tmp_path, "# Retire things\n\npart of /fixture/home/docs\n")

    publish(spec, None, None, shell, quiet, home=_home(tmp_path))

    assert shell.bodies == ["part of /fixture/home/docs\n"]


def test_a_changed_domain_doc_pointing_outside_the_home_is_refused_before_any_gh_call(tmp_path):
    checkout = tmp_path / "proto"
    (checkout / "docs" / "adr").mkdir(parents=True)
    (checkout / "docs" / "adr" / "0009-thing.md").write_text(f"# Thing\nsee {TILDE}/elsewhere\n")
    shell = _Shell(status="?? docs/adr/0009-thing.md\n", toplevel=str(checkout))
    spec = _spec(tmp_path)

    with pytest.raises(RefusalError, match=r"docs/adr/0009-thing\.md line 2: outside path"):
        publish(spec, None, None, shell, quiet, home=_home(tmp_path, toplevel=str(checkout)))

    assert not shell.ran("gh")
    assert spec.exists()


def test_the_domain_doc_commit_is_leak_checked_before_it_is_pushed(tmp_path):
    shell = _Shell(status=" M GLOSSARY.md\n", grep=f"HEAD:GLOSSARY.md:4:see {TILDE}/elsewhere\n")

    with pytest.raises(RefusalError, match=r"committed text(.|\n)*GLOSSARY\.md:4: outside path"):
        publish(_spec(tmp_path), None, None, shell, quiet, home=_home(tmp_path))

    (grep,) = shell.ran("git", "-C", TOPLEVEL, "grep")
    assert grep[-1] == "HEAD"
    assert not shell.ran("git", "push")


def _docs_checkout(tmp_path: Path, doc: str, text: str) -> Path:
    checkout = tmp_path / "proto"
    (checkout / doc).parent.mkdir(parents=True, exist_ok=True)
    (checkout / doc).write_text(text)
    return checkout


DOCS_PR_BODY = "Domain-doc edits from grilling spec #300.\n\nRefs #300\n"


def _publish_in_home(tmp_path: Path, settings: str) -> str:
    """The domain-docs PR body ``kaizen spec publish`` sends from ``relay``'s main checkout in a
    fixture home whose marker holds *settings*."""
    shell = _Shell(status=" M GLOSSARY.md\n", toplevel=str(RELAY))
    argv = ["spec", "publish", str(_spec(tmp_path))]
    assert main(argv, run=shell, cwd=cli_home(tmp_path, settings), env={}) == 0
    (pr,) = shell.ran("gh", "pr", "create")
    return pr[pr.index("--body") + 1]


def test_a_marker_without_pr_footer_ends_the_domain_docs_pr_body_with_the_default_footer(
    tmp_path,
):
    assert _publish_in_home(tmp_path, "") == f"{DOCS_PR_BODY}\n{FOOTER}\n"


def test_the_homes_footer_ends_the_domain_docs_pr_body(tmp_path):
    body = _publish_in_home(tmp_path, f'pr_footer = "{HOME_FOOTER}"\n')

    assert body == f"{DOCS_PR_BODY}\n{HOME_FOOTER}\n"


def test_an_empty_footer_leaves_the_domain_docs_pr_body_without_a_footer_line(tmp_path):
    assert _publish_in_home(tmp_path, 'pr_footer = ""\n') == DOCS_PR_BODY
