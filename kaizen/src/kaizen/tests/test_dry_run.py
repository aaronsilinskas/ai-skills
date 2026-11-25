"""Tests for the ``--dry-run`` rule: only the query-only commands lack one, and every dry run gets
past its checks running only queries.

git and gh are replaced by a recording runner that answers each command's queries, so no repo,
network or GitHub is touched.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from kaizen.shared.cli import main
from kaizen.tests.commands import command_parsers, has_dry_run
from kaizen.tests.ticket_shell import (
    MAIN_CHECKOUT_BEHIND,
    RELAY,
    SPEC_START,
    Reply,
    Shell,
    cli_home,
    failed,
    issue_json,
)

_GIT_QUERIES = {
    ("diff",),
    ("for-each-ref",),
    ("grep",),
    ("log",),
    ("ls-remote",),
    ("rev-list",),
    ("rev-parse",),
    ("status",),
    ("branch", "--list"),
    ("remote", "get-url"),
    ("worktree", "list"),
}
_GH_QUERIES = {("issue", "view"), ("label", "list"), ("pr", "list")}
_GH_API_WRITE_FLAGS = ("--method", "-X", "--field", "-F", "--raw-field", "-f", "--input")


def _is_query(cmd: list[str]) -> bool:
    """Whether *cmd* is a git or gh call that changes nothing, locally or on GitHub.

    A fetch counts as a change, since most dry runs skip theirs. No case here reaches one of the
    few a dry run makes by design: ``ticket finish`` fetching a PR's head it lacks, and ``ticket
    start --spec`` fetching the integration branch."""
    program, *words = cmd
    if program == "git":
        while words[:1] in (["-C"], ["-c"]):
            words = words[2:]
        if words[:1] == ["symbolic-ref"]:
            return len([word for word in words[1:] if not word.startswith("-")]) == 1
        return tuple(words[:1]) in _GIT_QUERIES or tuple(words[:2]) in _GIT_QUERIES
    if program == "gh":
        while words[:1] == ["-R"]:
            words = words[2:]
        if words[:1] == ["api"]:
            return not any(word.startswith(_GH_API_WRITE_FLAGS) for word in words)
        return tuple(words[:2]) in _GH_QUERIES
    return False


WORKTREE = f"{RELAY}/.claude/worktrees/fix-5-x"
SPEC_WORKTREE = f"{RELAY}/.claude/worktrees/spec-25-fix-5-x"
_ON_TICKET: dict[tuple[str, ...], Reply] = {("--abbrev-ref", "HEAD"): "fix-5-x\n"}
_MERGED = '[{"number": 9, "state": "MERGED", "url": "u", "headRefOid": "a1"}]'


def _issue_api(cmd: list[str]) -> str:
    """``gh api`` for an issue with no parent and no blockers."""
    path = next(word for word in cmd if word.startswith("repos/"))
    if path.endswith("/parent"):
        raise failed("gh api", stderr="HTTP 404: Not Found")
    if path.endswith("/dependencies/blocked_by"):
        return ""
    number = int(path.rsplit("/", 1)[1])
    issue = {"id": 100 + number, "number": number, "title": "T", "state": "open"}
    return json.dumps(issue | {"pull_request": None})


@dataclass(frozen=True)
class DryRun:
    """A command's arguments, given the fixture folder, a line of its plan, and the replies to its
    queries that take it past every check, on top of ``_DEFAULT_ANSWERS``. It runs from the fixture home, or from an
    empty folder when *outside_a_home*."""

    args: Callable[[Path], list[str]]
    plan: str
    """A line near the end of the plan the dry run prints, so it is known to have run every check."""
    answers: dict[tuple[str, ...], Reply] = field(default_factory=dict)
    outside_a_home: bool = False


def _body(tmp_path: Path) -> str:
    body = tmp_path / "body.md"
    body.write_text("Body.\n")
    return str(body)


def _spec(tmp_path: Path) -> str:
    spec = tmp_path / "spec.md"
    spec.write_text("# One CLI for relay\n\nBody.\n")
    return str(spec)


def _manifest(tmp_path: Path) -> str:
    (tmp_path / "a.md").write_text("Body.\n")
    manifest = tmp_path / "tickets.json"
    tickets = [{"key": "a", "title": "Add kaizen", "body_file": "a.md"}]
    manifest.write_text(json.dumps({"parent": 300, "tickets": tickets}))
    return str(manifest)


DRY_RUNS = {
    "home init": DryRun(
        lambda t: [],
        "dry run: nothing written",
        {
            ("--show-toplevel",): lambda cmd: f"{cmd[2]}\n",
            ("remote", "get-url"): "https://github.com/acme/newhome.git\n",
        },
        outside_a_home=True,
    ),
    "home sync": DryRun(lambda t: [], "dry run: nothing written"),
    "issue link": DryRun(
        lambda t: ["relay#5", "--parent", "relay#4", "--blocked-by", "relay#3"],
        "would add: #5 is blocked by #3",
        {("gh", "api"): _issue_api},
    ),
    "issue publish": DryRun(
        lambda t: ["--title", "T", "--body-file", _body(t)], "would create in acme/relay: T"
    ),
    "project labels": DryRun(
        lambda t: ["relay"], "11 to create, 0 already present", {("label", "list"): "[]"}
    ),
    "spec publish": DryRun(
        lambda t: [_spec(t)],
        "domain docs for the PR: GLOSSARY.md",
        {("--abbrev-ref", "HEAD"): "main\n", ("status", "--porcelain"): " M GLOSSARY.md\n"},
    ),
    "spec start": DryRun(
        lambda t: ["25"], "would push spec-25 to origin from origin/main", dict(SPEC_START)
    ),
    "spec integrate": DryRun(
        lambda t: [SPEC_WORKTREE],
        "would remove worktree",
        {("--abbrev-ref", "HEAD"): "spec-25-fix-5-x\n"},
    ),
    "spec ship": DryRun(
        lambda t: ["25", "--title", "T", "--body-file", _body(t)],
        "would open a ready PR from spec-25 into main: T",
        {("ls-remote", "--heads"): "abc123\trefs/heads/spec-25\n"},
    ),
    "spec finish": DryRun(
        lambda t: ["25"],
        "would fast-forward main from 1111111 to 2222222",
        {("pr", "list"): _MERGED, **MAIN_CHECKOUT_BEHIND},
    ),
    "ticket publish": DryRun(lambda t: [_manifest(t)], "- a: Add kaizen (blocked by none)"),
    "ticket start": DryRun(lambda t: ["relay", "5", "--slug", "x"], "would add worktree"),
    "ticket ship": DryRun(
        lambda t: [WORKTREE, "--title", "T", "--body-file", _body(t)],
        "would open a PR into main: T",
        _ON_TICKET,
    ),
    "ticket finish": DryRun(
        lambda t: [WORKTREE],
        "would fast-forward main from 1111111 to 2222222",
        {
            **_ON_TICKET,
            ("pr", "list"): _MERGED,
            ("rev-parse", "HEAD"): "a1\n",
            **MAIN_CHECKOUT_BEHIND,
        },
    ),
    "ticket abandon": DryRun(
        lambda t: [WORKTREE], "would force-delete local branch fix-5-x", _ON_TICKET
    ),
    "ticket compare": DryRun(
        lambda t: [WORKTREE, "--", "true"],
        "would run 3 times in a scratch worktree at origin/main: true",
        _ON_TICKET,
    ),
}
"""One dry run of each command that has ``--dry-run``, with ``--dry-run`` right after the
command's name."""


_DEFAULT_ANSWERS: dict[tuple[str, ...], Reply] = {
    ("rev-parse", "--show-toplevel"): f"{RELAY}\n",
    ("rev-parse", "--git-common-dir"): ".git\n",
    ("issue", "view"): issue_json(),
    ("ls-remote", "--symref"): "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n",
    ("rev-list", "--count"): "1\n",
    ("pr", "list"): "[]",
}
"""The queries every command makes in ``relay``: its toplevel, a ``.git`` common dir, an open
issue, origin's default branch, one commit ahead and no PR."""


def _shell(answers: dict[tuple[str, ...], Reply]) -> Shell:
    """A recording runner trying *answers* before the ``_DEFAULT_ANSWERS`` they don't replace."""
    defaults = {words: reply for words, reply in _DEFAULT_ANSWERS.items() if words not in answers}
    return Shell({**answers, **defaults})


def test_only_the_query_only_commands_lack_a_dry_run():
    commands = command_parsers()
    without_dry_run = {name for name, command in commands.items() if not has_dry_run(command)}

    hooks = {name for name in commands if name.startswith("hook ")}
    query_only = {"project leak-check", "pr wait", "issue show", "spec status", "ticket diff"}
    assert without_dry_run == hooks | query_only


def test_every_command_with_a_dry_run_has_a_case_in_dry_runs():
    with_dry_run = {name for name, command in command_parsers().items() if has_dry_run(command)}

    assert set(DRY_RUNS) == with_dry_run


@pytest.mark.parametrize("name", DRY_RUNS)
def test_a_dry_run_gets_past_its_checks_running_only_queries(tmp_path, capsys, name):
    case = DRY_RUNS[name]
    cwd = cli_home(tmp_path)
    if case.outside_a_home:
        cwd = tmp_path / "newhome"
        cwd.mkdir()
    shell = _shell(case.answers)
    group, command = name.split()

    code = main(
        [group, command, "--dry-run", *case.args(tmp_path)],
        run=shell,
        cwd=cwd,
        env={},
        latest=lambda: None,
    )

    out, err = capsys.readouterr()
    assert code == 0, err
    assert case.plan in out
    assert [cmd for cmd in shell.calls if not _is_query(cmd)] == []
