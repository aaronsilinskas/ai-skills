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
    ("symbolic-ref",),
    ("branch", "--list"),
    ("remote", "get-url"),
    ("worktree", "list"),
    # A fetch moves only remote-tracking refs, never a branch, the index or the working tree.
    ("fetch",),
}
_GH_QUERIES = {("issue", "view"), ("label", "list"), ("pr", "list")}
_GH_API_WRITES = {"--method", "-X", "--field", "-F", "--raw-field", "-f", "--input"}


def _is_query(cmd: list[str]) -> bool:
    """Whether *cmd* is a git or gh call that changes nothing, locally or on GitHub."""
    program, *words = cmd
    if program == "git":
        while words[:1] in (["-C"], ["-c"]):
            words = words[2:]
        return tuple(words[:1]) in _GIT_QUERIES or tuple(words[:2]) in _GIT_QUERIES
    if program == "gh":
        while words[:1] == ["-R"]:
            words = words[2:]
        if words[:1] == ["api"]:
            return not _GH_API_WRITES & set(words)
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
    """A command's arguments, given the fixture folder, and the replies to its queries that take
    it past every check, on top of ``_DEFAULT_ANSWERS``."""

    args: Callable[[Path], list[str]]
    answers: dict[tuple[str, ...], Reply] = field(default_factory=dict)


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


def _new_home(tmp_path: Path) -> Path:
    return tmp_path / "newhome"


DRY_RUNS = {
    "home init": DryRun(
        lambda t: [],
        {
            ("--show-toplevel",): lambda cmd: f"{cmd[2]}\n",
            ("remote", "get-url"): "https://github.com/acme/newhome.git\n",
        },
    ),
    "home sync": DryRun(lambda t: []),
    "issue link": DryRun(
        lambda t: ["relay#5", "--parent", "relay#4", "--blocked-by", "relay#3"],
        {("gh", "api"): _issue_api},
    ),
    "issue publish": DryRun(lambda t: ["--title", "T", "--body-file", _body(t)]),
    "project labels": DryRun(lambda t: ["relay"], {("label", "list"): "[]"}),
    "spec publish": DryRun(lambda t: [_spec(t)], {("--abbrev-ref", "HEAD"): "main\n"}),
    "spec start": DryRun(lambda t: ["25"], dict(SPEC_START)),
    "spec integrate": DryRun(
        lambda t: [SPEC_WORKTREE], {("--abbrev-ref", "HEAD"): "spec-25-fix-5-x\n"}
    ),
    "spec ship": DryRun(
        lambda t: ["25", "--title", "T", "--body-file", _body(t)],
        {("ls-remote", "--heads"): "abc123\trefs/heads/spec-25\n"},
    ),
    "spec finish": DryRun(lambda t: ["25"], {("pr", "list"): _MERGED}),
    "ticket publish": DryRun(lambda t: [_manifest(t)]),
    "ticket start": DryRun(lambda t: ["relay", "5", "--slug", "x"]),
    "ticket ship": DryRun(
        lambda t: [WORKTREE, "--title", "T", "--body-file", _body(t)], _ON_TICKET
    ),
    "ticket finish": DryRun(
        lambda t: [WORKTREE],
        {
            **_ON_TICKET,
            ("pr", "list"): _MERGED,
            ("rev-parse", "HEAD"): "a1\n",
            **MAIN_CHECKOUT_BEHIND,
        },
    ),
    "ticket abandon": DryRun(lambda t: [WORKTREE], _ON_TICKET),
    "ticket compare": DryRun(lambda t: [WORKTREE, "--", "true"], _ON_TICKET),
}
"""One dry run of each command that has ``--dry-run``, run from the fixture home (``home init``
from an empty folder) with ``--dry-run`` right after the command's name."""


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


def test_every_command_with_a_dry_run_has_a_case_here():
    with_dry_run = {name for name, command in command_parsers().items() if has_dry_run(command)}

    assert set(DRY_RUNS) == with_dry_run


@pytest.mark.parametrize("name", DRY_RUNS)
def test_a_dry_run_gets_past_its_checks_running_only_queries(tmp_path, capsys, name):
    case = DRY_RUNS[name]
    home = cli_home(tmp_path)
    cwd = home
    if name == "home init":
        cwd = _new_home(tmp_path)
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

    assert code == 0, capsys.readouterr().err
    assert [cmd for cmd in shell.calls if not _is_query(cmd)] == []
