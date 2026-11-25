"""Tests for ``kaizen ticket start``: the project registry and the commands that make a ticket
worktree.

git and gh are replaced by a recording runner and the registry by a temporary ``projects/``
directory, so no repo, network or real project page is touched.
"""

import json
from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError
from kaizen.tests.ticket_shell import Reply, Shell, failed, home_for, issue_json, quiet, register
from kaizen.ticket.start import start

ISSUE_OPEN = issue_json(
    title="Each Reboot writes app-state.json twice", body="Two writes per Reboot."
)
REMOTE_HEAD = "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n"
INTEGRATION_BRANCH = "def456\trefs/heads/spec-25\n"
SUB_ISSUES = (
    '{"number":1357,"state":"closed","state_reason":"completed","title":"Earlier",'
    '"labels":[],"assignees":[]}\n'
    '{"number":1358,"state":"open","state_reason":null,"title":"Each Reboot writes twice",'
    '"labels":[],"assignees":[]}\n'
)


MERGES = "Integrate spec-25-fix-1357-earlier into spec-25\n"
"""The integration branch's merge subjects: #1357 is integrated into spec-25."""


def _blockers(*blockers: tuple[int, str] | tuple[int, str, str]) -> str:
    """A blocked-by reply: one blocker per ``(number, state)`` or ``(number, state, repo)``."""
    lines = []
    for number, state, *repo in blockers:
        url = f"https://api.github.com/repos/{repo[0] if repo else 'owner/proto'}"
        item = {"number": number, "title": f"B{number}", "state": state, "repository_url": url}
        lines.append(json.dumps(item) + "\n")
    return "".join(lines)


def _open_issue(title: str) -> str:
    return issue_json(title=title)


def _projects(tmp_path: Path, **pages: str) -> Path:
    directory = tmp_path / "projects"
    directory.mkdir()
    for name, frontmatter in pages.items():
        (directory / f"{name}.md").write_text(f"---\n{frontmatter}---\n# {name}\n\nProse.\n")
    return directory


def _proto(tmp_path: Path, extra: str = "") -> Path:
    repo = tmp_path / "proto"
    return _projects(
        tmp_path,
        proto=f"path: {repo}\ngithub: owner/proto\npublic: true\n{extra}",
    )


def _shell(**overrides: str | BaseException) -> Shell:
    sub_issues = overrides.get("sub_issues", SUB_ISSUES)
    blockers = overrides.get("blockers", "")

    def gh_api(cmd: list[str]) -> str:
        blocked_by = any(word.endswith("/dependencies/blocked_by") for word in cmd)
        reply = blockers if blocked_by else sub_issues
        if isinstance(reply, BaseException):
            raise reply
        return reply

    answers: dict[tuple[str, ...], Reply] = {
        ("issue", "view"): overrides.get("issue", ISSUE_OPEN),
        ("log", "--merges"): overrides.get("merges", MERGES),
        ("gh", "api"): gh_api,
        ("ls-remote", "--heads"): overrides.get("integration", INTEGRATION_BRANCH),
        ("for-each-ref",): overrides.get("local", ""),
        ("ls-remote",): overrides.get("remote_head", REMOTE_HEAD),
        ("branch", "--list"): overrides.get("branches", ""),
        ("worktree", "list"): overrides.get("worktrees", ""),
    }
    return Shell(answers)


def test_start_creates_the_ticket_worktree_from_the_remote_default_branch(tmp_path):
    shell = _shell()

    start("proto", 1358, None, shell, home=home_for(_proto(tmp_path)), say=quiet)

    repo = str(tmp_path / "proto")
    worktree = f"{repo}/.claude/worktrees/fix-1358-each-reboot-writes-app-state"
    assert shell.ran("git", "-C", repo, "fetch") == [["git", "-C", repo, "fetch", "origin"]]
    assert shell.ran("worktree", "add") == [
        [
            "git",
            "-C",
            repo,
            "worktree",
            "add",
            worktree,
            "-b",
            "fix-1358-each-reboot-writes-app-state",
            "origin/main",
        ]
    ]


def test_with_spec_the_worktree_is_on_a_spec_ticket_branch_from_the_integration_branch(tmp_path):
    shell = _shell()

    started = start(
        "proto", 1358, "double-write", shell, home=home_for(_proto(tmp_path)), spec=25, say=quiet
    )

    repo = str(tmp_path / "proto")
    branch = "spec-25-fix-1358-double-write"
    assert started.branch == branch
    assert shell.ran("worktree", "add") == [
        [
            "git",
            "-C",
            repo,
            "worktree",
            "add",
            f"{repo}/.claude/worktrees/{branch}",
            "-b",
            branch,
            "origin/spec-25",
        ]
    ]
    assert not shell.ran("push")


def test_with_spec_start_refuses_a_ticket_with_an_open_blocker_not_yet_integrated(tmp_path):
    shell = _shell(blockers=_blockers((1356, "open"), (9, "open", "owner/other")))
    projects = _proto(tmp_path)
    register(tmp_path, "other", "owner/other")

    with pytest.raises(RefusalError) as refused:
        start("proto", 1358, "x", shell, home=home_for(projects), spec=25, say=quiet)

    message = str(refused.value)
    assert "#1358 has open blocker(s) not integrated into spec-25: #1356, owner/other#9" in message
    assert "kaizen spec integrate" in message
    assert "--ignore-blockers" in message
    assert not shell.ran("worktree", "add")


@pytest.mark.parametrize("state", ["open", "closed"])
def test_with_spec_a_blocker_outside_the_home_refuses_without_naming_its_repo(tmp_path, state):
    shell = _shell(blockers=_blockers((9, state, "stranger/repo")))

    with pytest.raises(RefusalError) as refused:
        start("proto", 1358, "x", shell, home=home_for(_proto(tmp_path)), spec=25, say=quiet)

    message = str(refused.value)
    assert "not integrated into spec-25: an issue outside this home" in message
    assert "stranger" not in message
    assert not any("stranger" in word for call in shell.calls for word in call)


def test_with_spec_a_closed_blocker_does_not_refuse(tmp_path):
    shell = _shell(blockers=_blockers((1356, "closed")))

    start("proto", 1358, "x", shell, home=home_for(_proto(tmp_path)), spec=25, say=quiet)

    assert shell.ran("worktree", "add")


def test_with_spec_a_blocker_already_integrated_into_the_spec_does_not_refuse(tmp_path):
    shell = _shell(blockers=_blockers((1357, "open")))

    start("proto", 1358, "x", shell, home=home_for(_proto(tmp_path)), spec=25, say=quiet)

    assert shell.ran("worktree", "add")


def test_with_spec_the_integration_is_read_from_the_integration_branch_just_fetched(tmp_path):
    shell = _shell(blockers=_blockers((1357, "open")))

    start("proto", 1358, "x", shell, home=home_for(_proto(tmp_path)), spec=25, say=quiet)

    fetch = shell.ran("fetch", "-q", "origin")
    log = shell.ran("log", "--merges")
    assert fetch[0][-1] == "+refs/heads/spec-25:refs/remotes/origin/spec-25"
    assert log[0][-1] == "origin/spec-25"
    assert shell.calls.index(fetch[0]) < shell.calls.index(log[0])


def test_with_ignore_blockers_start_starts_anyway_and_prints_the_blockers(tmp_path):
    shell = _shell(blockers=_blockers((1356, "open")))
    lines: list[str] = []

    start(
        "proto",
        1358,
        "x",
        shell,
        home=home_for(_proto(tmp_path)),
        spec=25,
        ignore_blockers=True,
        say=lines.append,
    )

    assert shell.ran("worktree", "add")
    assert "--ignore-blockers: starting before open blocker(s) #1356 are in spec-25" in lines


def test_start_refuses_ignore_blockers_without_a_spec(tmp_path):
    shell = _shell()

    with pytest.raises(RefusalError, match="--ignore-blockers applies only to a spec's ticket"):
        start("proto", 1358, "x", shell, home=home_for(_proto(tmp_path)), ignore_blockers=True)

    assert not shell.calls


def test_with_spec_start_refuses_when_origin_has_no_integration_branch(tmp_path):
    shell = _shell(integration="")

    with pytest.raises(RefusalError, match=r"origin has no spec-25(.|\n)*kaizen spec start 25"):
        start("proto", 1358, "x", shell, home=home_for(_proto(tmp_path)), spec=25, say=quiet)

    assert not shell.ran("fetch")
    assert not shell.ran("worktree", "add")


def test_with_spec_start_refuses_an_issue_that_is_not_a_sub_issue_of_the_spec(tmp_path):
    shell = _shell(
        sub_issues='{"number":1357,"state":"open","state_reason":null,"title":"E",'
        '"labels":[],"assignees":[]}\n'
    )

    with pytest.raises(RefusalError, match="#1358 is not a sub-issue of spec #25"):
        start("proto", 1358, "x", shell, home=home_for(_proto(tmp_path)), spec=25, say=quiet)

    assert not shell.ran("fetch")
    assert not shell.ran("worktree", "add")


def test_with_spec_start_refuses_a_closed_issue(tmp_path):
    shell = _shell(issue=issue_json(state="CLOSED", title="Old work"))

    with pytest.raises(RefusalError, match="#1358 is closed"):
        start("proto", 1358, "x", shell, home=home_for(_proto(tmp_path)), spec=25, say=quiet)

    assert not shell.ran("fetch")
    assert not shell.ran("worktree", "add")


def test_with_spec_a_dry_run_fetches_only_the_integration_branch_and_adds_nothing(tmp_path):
    shell = _shell()
    lines: list[str] = []

    start(
        "proto",
        1358,
        "x",
        shell,
        home=home_for(_proto(tmp_path)),
        spec=25,
        dry_run=True,
        say=lines.append,
    )

    repo = str(tmp_path / "proto")
    refspec = "+refs/heads/spec-25:refs/remotes/origin/spec-25"
    assert shell.ran("gh", "api")
    assert shell.ran("fetch") == [["git", "-C", repo, "fetch", "-q", "origin", refspec]]
    assert not shell.ran("worktree", "add")
    assert lines[-1].endswith("on spec-25-fix-1358-x from origin/spec-25")


def test_start_refuses_a_closed_issue_and_issues_nothing_after(tmp_path):
    shell = _shell(issue=issue_json(state="CLOSED", title="Old work"))

    with pytest.raises(RefusalError, match="#1358 is closed"):
        start("proto", 1358, None, shell, home=home_for(_proto(tmp_path)), say=quiet)

    assert shell.calls == [shell.ran("issue", "view")[0]]


def test_start_refuses_an_issue_gh_cannot_read(tmp_path):
    shell = _shell(issue=failed("gh issue view", "GraphQL: Could not resolve to an issue"))

    with pytest.raises(RefusalError, match="could not read issue #1358 in owner/proto"):
        start("proto", 1358, None, shell, home=home_for(_proto(tmp_path)), say=quiet)

    assert not shell.ran("fetch")


def test_start_refuses_an_existing_branch_and_names_the_worktree_it_is_checked_out_in(tmp_path):
    shell = _shell(
        branches="+ fix-1358-each-reboot-writes-app-state\n",
        worktrees=(
            "worktree /repos/proto\nHEAD abc\nbranch refs/heads/main\n\n"
            "worktree /elsewhere/attempt\nHEAD def\n"
            "branch refs/heads/fix-1358-each-reboot-writes-app-state\n"
        ),
    )

    with pytest.raises(RefusalError, match=r"already exists.*/elsewhere/attempt"):
        start("proto", 1358, None, shell, home=home_for(_proto(tmp_path)), say=quiet)

    assert not shell.ran("fetch")
    assert not shell.ran("worktree", "add")


def test_start_refuses_when_the_worktree_path_already_exists(tmp_path):
    projects = _proto(tmp_path)
    existing = tmp_path / "proto/.claude/worktrees/fix-1358-each-reboot-writes-app-state"
    existing.mkdir(parents=True)
    shell = _shell()

    with pytest.raises(RefusalError, match=f"{existing} already exists"):
        start("proto", 1358, None, shell, home=home_for(projects), say=quiet)

    assert not shell.ran("fetch")


def test_a_given_slug_replaces_the_one_derived_from_the_title(tmp_path):
    started = start(
        "proto", 7, "double-write", _shell(), home=home_for(_proto(tmp_path)), say=quiet
    )

    assert started.branch == "fix-7-double-write"


def test_the_worktree_goes_under_worktree_root_when_the_page_sets_it(tmp_path):
    shell = _shell()
    projects = _proto(tmp_path, extra=f"worktree_root: {tmp_path}/outside\n")

    start("proto", 7, "x", shell, home=home_for(projects), say=quiet)

    (add,) = shell.ran("worktree", "add")
    assert add[5] == f"{tmp_path}/outside/fix-7-x"


def test_start_prints_the_worktree_path_and_the_issue_title(tmp_path):
    lines: list[str] = []

    start("proto", 7, "x", _shell(), home=home_for(_proto(tmp_path)), say=lines.append)

    assert lines[-4:-2] == [
        f"worktree: {tmp_path}/proto/.claude/worktrees/fix-7-x",
        "issue: #7 Each Reboot writes app-state.json twice",
    ]


def test_start_prints_the_issue_body_and_every_comment_after_the_title(tmp_path):
    issue = issue_json(
        title="Each Reboot writes app-state.json twice",
        body="## Problem\n\nTwo writes per Reboot.",
        comments=[
            {
                "author": {"login": "alice"},
                "body": "Seen on rev B too.",
                "createdAt": "2026-11-19T08:30:00Z",
            },
            {
                "author": {"login": "bob"},
                "body": "Fixed upstream?\nNo.",
                "createdAt": "2026-11-20T17:05:00Z",
            },
        ],
    )
    lines: list[str] = []

    start("proto", 7, "x", _shell(issue=issue), home=home_for(_proto(tmp_path)), say=lines.append)

    assert lines[-4:] == [
        "issue: #7 Each Reboot writes app-state.json twice",
        "\nbody:\n## Problem\n\nTwo writes per Reboot.",
        "\ncomment by alice on 2026-11-19:\nSeen on rev B too.",
        "\ncomment by bob on 2026-11-20:\nFixed upstream?\nNo.",
    ]


def test_start_says_when_the_issue_has_no_body_and_no_comments(tmp_path):
    lines: list[str] = []

    start(
        "proto",
        7,
        "x",
        _shell(issue=_open_issue("Bare")),
        home=home_for(_proto(tmp_path)),
        say=lines.append,
    )

    assert lines[-3:] == ["issue: #7 Bare", "\nbody: none", "\n(no comments)"]


@pytest.mark.parametrize("author", [None, {"login": ""}])
def test_start_names_a_deleted_comment_author_ghost(tmp_path, author):
    comment = {"author": author, "body": "Old note.", "createdAt": "2026-01-02T03:04:05Z"}
    issue = issue_json(body="B", comments=[comment])
    lines: list[str] = []

    start("proto", 7, "x", _shell(issue=issue), home=home_for(_proto(tmp_path)), say=lines.append)

    assert lines[-1] == "\ncomment by ghost on 2026-01-02:\nOld note."


def test_start_asks_gh_for_the_body_and_comments_as_json_never_with_the_comments_flag(tmp_path):
    shell = _shell()

    start("proto", 7, "x", shell, home=home_for(_proto(tmp_path)), say=quiet)

    (view,) = shell.ran("issue", "view")
    assert view[-2] == "--json"
    assert {"body", "comments"} <= set(view[-1].split(","))
    assert "--comments" not in view


def test_a_dry_run_does_not_print_the_issue_body(tmp_path):
    lines: list[str] = []

    start(
        "proto", 7, "x", _shell(), home=home_for(_proto(tmp_path)), dry_run=True, say=lines.append
    )

    assert not any("Two writes" in line or "comment" in line for line in lines)


def test_a_dry_run_issues_only_queries(tmp_path):
    shell = _shell()

    start("proto", 7, "x", shell, home=home_for(_proto(tmp_path)), dry_run=True, say=quiet)

    assert shell.calls
    assert not shell.ran("fetch")
    assert not shell.ran("worktree", "add")


def test_start_refuses_an_unknown_project_and_lists_the_registered_ones(tmp_path):
    shell = _shell()

    with pytest.raises(RefusalError, match=r"nope\.md(.|\n)*registered project: proto$"):
        start("nope", 7, None, shell, home=home_for(_proto(tmp_path)), say=quiet)

    assert not shell.calls


@pytest.mark.parametrize(
    ("frontmatter", "field"),
    [
        ("github: owner/proto\npublic: true\n", "missing field 'path'"),
        ("path: /p\npublic: true\n", "missing field 'github'"),
        ("path: /p\ngithub: owner/proto\n", "missing field 'public'"),
        ("path: /p\ngithub: owner/proto\npublic: yes\n", "field 'public' is 'yes'"),
        ("path: /p\ngithub: proto\npublic: true\n", "field 'github' is 'proto'"),
        ("path: true\ngithub: owner/proto\npublic: true\n", "field 'path' is True"),
        (
            "path: /p\ngithub: owner/proto\npublic: false\nworktree_root: false\n",
            "field 'worktree_root' is False",
        ),
    ],
)
def test_start_refuses_a_malformed_page_naming_the_page_and_the_field(tmp_path, frontmatter, field):
    shell = _shell()
    projects = _projects(tmp_path, proto=frontmatter)

    with pytest.raises(RefusalError, match=rf"proto\.md: {field}"):
        start("proto", 7, None, shell, home=home_for(projects), say=quiet)

    assert not shell.calls


def test_start_refuses_a_page_without_frontmatter(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "proto.md").write_text("# proto\n\n- **Path:** `/fixture/proto`\n")

    with pytest.raises(RefusalError, match=r"proto\.md: no registry frontmatter"):
        start("proto", 7, None, _shell(), home=home_for(projects), say=quiet)


@pytest.mark.parametrize(
    ("title", "branch"),
    [
        ("Run implement-spec's git steps", "fix-7-run-implement-specs-git-steps"),
        ("Run implement-spec\u2019s git steps", "fix-7-run-implement-specs-git-steps"),
    ],
)
def test_the_derived_slug_drops_apostrophes_instead_of_splitting_on_them(tmp_path, title, branch):
    shell = _shell(issue=_open_issue(title))

    started = start("proto", 7, None, shell, home=home_for(_proto(tmp_path)), say=quiet)

    assert started.branch == branch


@pytest.mark.parametrize(
    ("title", "branch"),
    [
        ("kaizen spec ship: open the PR ready", "fix-7-kaizen-spec-ship-open"),
        ("Pick a convention for and of the branch", "fix-7-pick-a-convention"),
    ],
)
def test_the_derived_slug_drops_trailing_stopwords(tmp_path, title, branch):
    shell = _shell(issue=_open_issue(title))

    started = start("proto", 7, None, shell, home=home_for(_proto(tmp_path)), say=quiet)

    assert started.branch == branch


def _docs_proto(tmp_path: Path) -> Path:
    return _proto(tmp_path, extra="code_paths: src/\n")


def test_without_an_issue_start_adds_a_docs_change_worktree_from_the_remote_default_branch(
    tmp_path,
):
    shell = _shell()
    lines: list[str] = []

    started = start(
        "proto", None, "fix-typos", shell, home=home_for(_docs_proto(tmp_path)), say=lines.append
    )

    repo = str(tmp_path / "proto")
    worktree = f"{repo}/.claude/worktrees/docs-fix-typos"
    assert started.branch == "docs-fix-typos"
    assert shell.ran("worktree", "add") == [
        ["git", "-C", repo, "worktree", "add", worktree, "-b", "docs-fix-typos", "origin/main"]
    ]
    assert not shell.ran("issue", "view")
    assert lines[-1] == f"worktree: {worktree}"


def test_without_an_issue_start_refuses_a_missing_slug(tmp_path):
    shell = _shell()

    with pytest.raises(RefusalError, match="no issue and no --slug"):
        start("proto", None, None, shell, home=home_for(_docs_proto(tmp_path)), say=quiet)

    assert not shell.calls


def test_without_an_issue_start_refuses_a_spec(tmp_path):
    shell = _shell()

    with pytest.raises(RefusalError, match="--spec 25 needs an issue"):
        start("proto", None, "x", shell, home=home_for(_docs_proto(tmp_path)), spec=25, say=quiet)

    assert not shell.calls


def test_without_an_issue_start_refuses_a_project_that_declares_no_code_paths(tmp_path):
    shell = _shell()

    with pytest.raises(RefusalError, match=r"declares no code_paths(.|\n)*projects/proto\.md"):
        start("proto", None, "x", shell, home=home_for(_proto(tmp_path)), say=quiet)

    assert not shell.calls


@pytest.mark.parametrize("issue", [None, 7])
@pytest.mark.parametrize("slug", ["", "a/b", "fix typos"])
def test_start_refuses_a_slug_that_is_no_branch_slug(tmp_path, issue, slug):
    shell = _shell()

    with pytest.raises(RefusalError, match="is not a branch slug"):
        start("proto", issue, slug, shell, home=home_for(_docs_proto(tmp_path)), say=quiet)

    assert not shell.ran("worktree", "add")


def test_start_links_each_worktree_link_from_the_main_checkout_into_the_worktree(tmp_path):
    projects = _proto(tmp_path, extra="worktree_links: tools/mpy-cross, .env\n")
    repo = tmp_path / "proto"
    (repo / "tools").mkdir(parents=True)
    (repo / "tools/mpy-cross").write_text("binary")
    (repo / ".env").write_text("KEY=1")

    started = start("proto", 7, "x", _shell(), home=home_for(projects), say=quiet)

    linked = started.worktree / "tools/mpy-cross"
    assert linked.is_symlink()
    assert linked.readlink() == repo / "tools/mpy-cross"
    assert (started.worktree / ".env").readlink() == repo / ".env"


def test_a_worktree_link_missing_from_the_main_checkout_is_warned_about_and_start_still_finishes(
    tmp_path,
):
    projects = _proto(tmp_path, extra="worktree_links: tools/mpy-cross\n")
    lines: list[str] = []

    started = start("proto", 7, "x", _shell(), home=home_for(projects), say=lines.append)

    assert not (started.worktree / "tools/mpy-cross").is_symlink()
    assert any(
        line.startswith("warning:") and "tools/mpy-cross" in line and "main checkout" in line
        for line in lines
    )
    assert "issue: #7 Each Reboot writes app-state.json twice" in lines


def test_start_refuses_a_worktree_link_the_base_commit_tracks_before_adding_the_worktree(tmp_path):
    projects = _proto(tmp_path, extra="worktree_links: tools/mpy-cross, scripts/check.sh\n")
    shell = Shell(
        {
            ("ls-tree",): lambda cmd: "scripts/check.sh\n" if "scripts/check.sh" in cmd else "",
            ("issue", "view"): ISSUE_OPEN,
            ("ls-remote",): REMOTE_HEAD,
        }
    )

    with pytest.raises(
        RefusalError, match=r"scripts/check\.sh is tracked in origin/main(.|\n)*projects/proto\.md"
    ):
        start("proto", 7, "x", shell, home=home_for(projects), say=quiet)

    assert not shell.ran("worktree", "add")


def test_a_dry_run_reports_the_worktree_links_it_would_make_and_makes_none(tmp_path):
    projects = _proto(tmp_path, extra="worktree_links: tools/mpy-cross\n")
    (tmp_path / "proto/tools").mkdir(parents=True)
    (tmp_path / "proto/tools/mpy-cross").write_text("binary")
    lines: list[str] = []

    started = start(
        "proto", 7, "x", _shell(), home=home_for(projects), dry_run=True, say=lines.append
    )

    assert not started.worktree.exists()
    assert "would link tools/mpy-cross from the main checkout" in lines


def test_with_spec_the_tracked_check_reads_the_integration_branch_after_fetching_it(tmp_path):
    projects = _proto(tmp_path, extra="worktree_links: tools/mpy-cross\n")
    (tmp_path / "proto/tools").mkdir(parents=True)
    (tmp_path / "proto/tools/mpy-cross").write_text("binary")
    shell = _shell()

    started = start("proto", 1358, "x", shell, home=home_for(projects), spec=25, say=quiet)

    (ls_tree,) = shell.ran("ls-tree")
    assert "origin/spec-25" in ls_tree
    assert shell.calls.index(shell.ran("fetch")[0]) < shell.calls.index(ls_tree)
    assert (started.worktree / "tools/mpy-cross").is_symlink()


def test_start_refuses_when_git_cannot_list_the_base_for_the_tracked_check(tmp_path):
    projects = _proto(tmp_path, extra="worktree_links: tools/mpy-cross\n")
    shell = Shell(
        {
            ("ls-tree",): failed("git ls-tree", "fatal: Not a valid object name origin/main"),
            ("issue", "view"): ISSUE_OPEN,
            ("ls-remote",): REMOTE_HEAD,
        }
    )

    with pytest.raises(RefusalError, match="could not list origin/main"):
        start("proto", 7, "x", shell, home=home_for(projects), say=quiet)

    assert not shell.ran("worktree", "add")


def test_with_spec_started_locally_the_worktree_is_based_on_the_local_integration_branch(
    tmp_path,
):
    shell = _shell(integration="", local="abc123\n")
    lines: list[str] = []

    start("proto", 1358, "x", shell, home=home_for(_proto(tmp_path)), spec=25, say=lines.append)

    (add,) = shell.ran("worktree", "add")
    assert add[-1] == "spec-25"
    assert shell.ran("log", "--merges")[0][-1] == "spec-25"
    assert not shell.ran("fetch", "-q")
    assert "whose integration branch is local only (started with --local)" in " ".join(lines)
