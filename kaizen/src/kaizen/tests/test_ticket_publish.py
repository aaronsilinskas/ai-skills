"""Tests for ``kaizen ticket publish``: manifest checks and the gh commands it issues.

``gh`` is replaced by a recording runner, so no network or GitHub access is needed.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError
from kaizen.tests.ticket_shell import RELAY, SITE, TILDE, Shell
from kaizen.ticket.publish import (
    DomainDocsError,
    ManifestError,
    load_manifest,
    publish,
    read_back,
    wait_for_domain_docs,
)


def _manifest(tmp_path: Path, tickets: list[dict], parent: int = 100) -> Path:
    for ticket in tickets:
        (tmp_path / ticket.get("body_file", "missing.md")).write_text("body")
    path = tmp_path / "tickets.json"
    path.write_text(
        json.dumps({"parent": parent, "labels": ["ready-for-agent"], "tickets": tickets})
    )
    return path


class _Gh:
    """Records each command; answers ``issue create`` with sequential issue URLs in ``o/r``,
    and each issue lookup with database id ``1000 + N``, or 404 for a number in *missing*;
    fails the edge write whose last argument is *reject*."""

    def __init__(
        self, first: int = 200, missing: tuple[int, ...] = (), reject: str | None = None
    ) -> None:
        self.calls: list[list[str]] = []
        self._next = first
        self._missing = missing
        self._reject = reject

    def __call__(self, cmd: list[str]) -> str:
        self.calls.append(cmd)
        if self._reject and cmd[2:4] == ["-X", "POST"] and cmd[-1] == self._reject:
            raise subprocess.CalledProcessError(1, cmd, stderr="gh: would create a cycle")
        if cmd[1:3] == ["issue", "create"]:
            self._next += 1
            return f"https://github.com/o/r/issues/{self._next - 1}\n"
        if cmd[1] == "api" and (match := re.fullmatch(r"repos/o/r/issues/(\d+)", cmd[2])):
            number = int(match.group(1))
            if number in self._missing:
                raise subprocess.CalledProcessError(1, cmd, stderr="gh: Not Found (HTTP 404)")
            return json.dumps(
                {"id": 1000 + number, "number": number, "title": "T", "state": "open"}
            )
        return ""

    def writes(self) -> list[list[str]]:
        return [c[4:] for c in self.calls if c[2:4] == ["-X", "POST"]]


def test_each_ticket_is_created_under_the_parent_with_its_own_title_in_manifest_order(tmp_path):
    path = _manifest(
        tmp_path,
        [
            {"key": "a", "title": "First", "body_file": "a.md"},
            {"key": "b", "title": "Second", "body_file": "b.md"},
        ],
    )
    gh = _Gh()

    numbers = publish("o/r", *load_manifest(path), gh)

    creates = [c for c in gh.calls if c[1:3] == ["issue", "create"]]
    assert [c[c.index("--title") + 1] for c in creates] == ["First", "Second"]
    assert [c[c.index("--parent") + 1] for c in creates] == ["100", "100"]
    assert numbers == {"a": 200, "b": 201}


def test_the_parent_is_set_by_the_create_itself_not_by_a_later_sub_issue_write(tmp_path):
    path = _manifest(tmp_path, [{"key": "a", "title": "First", "body_file": "a.md"}])
    gh = _Gh()

    publish("o/r", *load_manifest(path), gh)

    assert gh.writes() == []


def test_each_issue_and_edge_prints_one_line_as_it_is_made(tmp_path):
    path = _manifest(
        tmp_path,
        [
            {"key": "a", "title": "First", "body_file": "a.md"},
            {"key": "b", "title": "Second", "body_file": "b.md", "blocked_by": ["a", 42]},
        ],
    )
    said: list[str] = []

    publish("o/r", *load_manifest(path), _Gh(), say=said.append)

    assert said == [
        "created #200 First, a sub-issue of #100",
        "created #201 Second, a sub-issue of #100",
        "#201 is blocked by #200",
        "#201 is blocked by #42",
    ]


def test_the_read_back_table_marks_an_issue_with_no_blockers_with_a_plain_dash():
    def gh(cmd: list[str]) -> str:
        if cmd[1:3] == ["issue", "view"]:
            return f"Title {cmd[3]}\n"
        return "#200\n" if "issues/201/" in cmd[2] else "\n"

    assert read_back({"a": 200, "b": 201}, gh) == [
        "| # | Title | Blocked by |",
        "|---|---|---|",
        "| #200 | Title 200 | - |",
        "| #201 | Title 201 | #200 |",
    ]


def test_blockers_resolve_keys_to_created_numbers_and_pass_existing_numbers_through(tmp_path):
    path = _manifest(
        tmp_path,
        [
            {"key": "a", "title": "First", "body_file": "a.md"},
            {"key": "b", "title": "Second", "body_file": "b.md", "blocked_by": ["a", 42]},
        ],
    )
    gh = _Gh()

    publish("o/r", *load_manifest(path), gh)

    assert gh.writes()[-2:] == [
        ["repos/o/r/issues/201/dependencies/blocked_by", "-F", "issue_id=1200"],
        ["repos/o/r/issues/201/dependencies/blocked_by", "-F", "issue_id=1042"],
    ]


def test_a_rejected_edge_stops_the_publish_and_prints_how_to_finish_it_without_rerunning(
    tmp_path,
):
    path = _manifest(
        tmp_path,
        [
            {"key": "a", "title": "First", "body_file": "a.md"},
            {"key": "b", "title": "Second", "body_file": "b.md", "blocked_by": ["a", 42]},
            {"key": "c", "title": "Third", "body_file": "c.md", "blocked_by": ["b"]},
        ],
    )
    said: list[str] = []

    with pytest.raises(subprocess.CalledProcessError):
        publish("o/r", *load_manifest(path), _Gh(reject="issue_id=1200"), say=said.append)

    recovery = "\n".join(said[said.index("created #201 Second, a sub-issue of #100") + 1 :])
    assert "created so far: #200, #201" in recovery
    assert "do not rerun `kaizen ticket publish`" in recovery
    assert "kaizen issue link 201 --blocked-by 200 --blocked-by 42" in recovery
    assert "not created: c Third (blocked by 201)" in recovery
    assert "`gh issue create --parent 100`" in recovery
    assert "--parent 100 --blocked-by" not in recovery


@pytest.mark.parametrize("missing", [100, 42], ids=["parent", "existing blocker"])
def test_a_missing_parent_or_existing_blocker_refuses_before_anything_is_created(tmp_path, missing):
    path = _manifest(
        tmp_path, [{"key": "a", "title": "First", "body_file": "a.md", "blocked_by": [42]}]
    )
    gh = _Gh(missing=(missing,))

    with pytest.raises(RefusalError, match=f"o/r#{missing} does not exist") as refusal:
        publish("o/r", *load_manifest(path), gh)

    assert "fix: check the reference" in str(refusal.value)
    assert not [c for c in gh.calls if c[1:3] == ["issue", "create"]]


def test_a_blocker_that_is_not_an_earlier_ticket_is_rejected_before_anything_is_created(tmp_path):
    path = _manifest(
        tmp_path,
        [
            {"key": "b", "title": "Second", "body_file": "b.md", "blocked_by": ["a"]},
            {"key": "a", "title": "First", "body_file": "a.md"},
        ],
    )

    with pytest.raises(ManifestError, match="'a'"):
        load_manifest(path)


def test_a_blank_title_is_rejected(tmp_path):
    path = _manifest(tmp_path, [{"key": "a", "title": " ", "body_file": "a.md"}])

    with pytest.raises(ManifestError):
        load_manifest(path)


def test_a_duplicate_key_is_rejected(tmp_path):
    path = _manifest(
        tmp_path,
        [
            {"key": "a", "title": "First", "body_file": "a.md"},
            {"key": "a", "title": "Again", "body_file": "a.md"},
        ],
    )

    with pytest.raises(ManifestError):
        load_manifest(path)


class _PrStates:
    """Answers the domain-docs PR lookup with *states* in turn; a fake clock advances on sleep."""

    def __init__(self, *states: str) -> None:
        self.calls: list[list[str]] = []
        self.slept: list[float] = []
        self._states = list(states)
        self._now = 0.0

    def __call__(self, cmd: list[str]) -> str:
        self.calls.append(cmd)
        return self._states.pop(0) if len(self._states) > 1 else self._states[0]

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self._now += seconds

    def now(self) -> float:
        return self._now


def _wait(gh: _PrStates, timeout: float = 60, interval: float = 10) -> None:
    wait_for_domain_docs(
        300, gh, sleep=gh.sleep, now=gh.now, timeout=timeout, interval=interval, log=lambda _: None
    )


def test_the_wait_looks_up_the_spec_domain_docs_branch():
    gh = _PrStates("MERGED")

    _wait(gh)

    assert gh.calls[0][:3] == ["gh", "pr", "list"]
    assert gh.calls[0][gh.calls[0].index("--head") + 1] == "spec-300-domain-docs"


def test_a_spec_with_no_domain_docs_pr_is_not_waited_for():
    gh = _PrStates("")

    _wait(gh)

    assert gh.slept == []


def test_a_merged_domain_docs_pr_is_not_waited_for():
    gh = _PrStates("MERGED")

    _wait(gh)

    assert gh.slept == []


def test_an_open_domain_docs_pr_is_polled_until_it_merges():
    gh = _PrStates("OPEN", "OPEN", "MERGED")

    _wait(gh, interval=10)

    assert gh.slept == [10, 10]


def test_a_domain_docs_pr_closed_without_merging_stops_the_publish():
    gh = _PrStates("CLOSED")

    with pytest.raises(DomainDocsError, match="spec-300-domain-docs"):
        _wait(gh)


def test_a_domain_docs_pr_still_open_at_the_timeout_stops_the_publish():
    gh = _PrStates("OPEN")

    with pytest.raises(DomainDocsError):
        _wait(gh, timeout=30, interval=10)

    assert sum(gh.slept) <= 30


def _bodies(tmp_path: Path, *bodies: str) -> str:
    """A manifest of one ticket per body, under parent #300."""
    tickets = []
    for n, body in enumerate(bodies):
        (tmp_path / f"t{n}.md").write_text(body)
        tickets.append({"key": f"t{n}", "title": f"Ticket {n}", "body_file": f"t{n}.md"})
    manifest = tmp_path / "tickets.json"
    manifest.write_text(json.dumps({"parent": 300, "tickets": tickets}))
    return str(manifest)


def _publishing_shell(toplevel: Path) -> Shell:
    def lookup(cmd: list[str]) -> str:
        if cmd[2].endswith("/dependencies/blocked_by"):
            return ""
        number = int(cmd[2].rsplit("/", 1)[-1])
        return json.dumps({"id": 1000 + number, "title": "T", "state": "open"})

    return Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{toplevel}\n",
            ("issue", "create"): "https://github.com/owner/site/issues/301\n",
            ("gh", "api"): lookup,
        }
    )


@pytest.mark.parametrize("dry_run", [True, False], ids=["dry run", "real run"])
def test_a_ticket_body_pointing_outside_the_home_is_refused_before_any_gh_call(
    kaizen, tmp_path, capsys, dry_run
):
    manifest = _bodies(tmp_path, "Fine.\n", f"Why.\nsee {TILDE}/dev/elsewhere/notes\n")
    shell = _publishing_shell(RELAY)

    argv = ["ticket", "publish", manifest] + (["--dry-run"] if dry_run else [])
    assert kaizen(argv, run=shell) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused: leak check: text for GitHub points outside this home")
    assert "ticket t1 body line 2: outside path " in err
    assert not shell.ran("gh")


def test_a_public_projects_ticket_body_with_an_own_reference_is_refused(kaizen, tmp_path, capsys):
    shell = _publishing_shell(SITE)

    assert (
        kaizen(["ticket", "publish", _bodies(tmp_path, "part of /fixture/home/docs\n")], run=shell)
        == 1
    )

    assert "ticket t0 body line 1: own reference /fixture/home" in capsys.readouterr().err
    assert not shell.ran("gh")


def test_a_private_projects_ticket_body_with_an_own_reference_is_published(kaizen, tmp_path):
    shell = _publishing_shell(RELAY)

    assert (
        kaizen(["ticket", "publish", _bodies(tmp_path, "part of /fixture/home/docs\n")], run=shell)
        == 0
    )

    assert len(shell.ran("issue", "create")) == 1
