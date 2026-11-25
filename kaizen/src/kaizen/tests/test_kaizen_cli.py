"""Tests for ``kaizen``: each noun-verb pair reaches its own command.

git and gh are replaced by a recording runner, so no repo, network or GitHub is touched.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import kaizen
from kaizen.shared.cli import main
from kaizen.shared.version import Version
from kaizen.tests.commands import command_parsers
from kaizen.tests.ticket_shell import (
    RELAY,
    SITE,
    SPEC_START,
    Shell,
    cli_home,
    failed,
    issue_json,
)


def _gh_api(cmd: list[str]) -> str:
    """Issue #5 as the only sub-issue, with no blockers."""
    if any(word.endswith("/dependencies/blocked_by") for word in cmd):
        return ""
    return (
        '{"number": 5, "state": "open", "state_reason": null, "title": "T",'
        ' "labels": [], "assignees": []}\n'
    )


def _shell() -> Shell:
    return Shell(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): "main\n",
            ("rev-parse", "--show-toplevel"): f"{RELAY}\n",
            ("issue", "view"): issue_json(title="Fold ticket into kaizen"),
            ("gh", "api"): _gh_api,
            ("ls-remote", "--heads"): "abc123\trefs/heads/spec-25\n",
            ("ls-remote",): "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n",
        }
    )


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


@pytest.mark.parametrize(
    ("argv", "code", "output"),
    [
        (lambda t: ["spec", "publish", _spec(t), "--dry-run"], 0, "spec: One CLI for relay"),
        (
            lambda t: ["spec", "integrate", str(t), "--dry-run"],
            1,
            "is not a registered project's ticket worktree",
        ),
        (
            lambda t: ["spec", "ship", "25", "--title", "T", "--body-file", str(t / "none")],
            1,
            "could not read the body file",
        ),
        (lambda t: ["ticket", "publish", _manifest(t), "--dry-run"], 0, "parent #300"),
        (
            lambda t: ["ticket", "start", "relay", "5", "--slug", "kaizen-dispatch", "--dry-run"],
            0,
            "on fix-5-kaizen-dispatch from origin/main",
        ),
        (
            lambda t: ["ticket", "start", "relay", "5", "--slug", "x", "--spec", "25", "--dry-run"],
            0,
            "on spec-25-fix-5-x from origin/spec-25",
        ),
        (
            lambda t: ["ticket", "ship", str(t), "--title", "T", "--body-file", str(t / "none")],
            1,
            "could not read the body file",
        ),
        (
            lambda t: ["ticket", "finish", str(t)],
            1,
            "is not a registered project's ticket worktree",
        ),
        (
            lambda t: ["ticket", "abandon", str(t), "--dry-run"],
            1,
            "is not a registered project's ticket worktree",
        ),
    ],
    ids=[
        "spec publish",
        "spec integrate",
        "spec ship",
        "ticket publish",
        "ticket start",
        "ticket start --spec",
        "ticket ship",
        "ticket finish",
        "ticket abandon",
    ],
)
def test_kaizen_routes_each_noun_verb_pair_to_its_command(
    kaizen, tmp_path, capsys, argv, code, output
):
    assert kaizen(argv(tmp_path), run=_shell()) == code

    captured = capsys.readouterr()
    assert output in captured.out + captured.err


def _untitled_spec(tmp_path: Path) -> str:
    spec = tmp_path / "spec.md"
    spec.write_text("Body without a title.\n")
    return str(spec)


def _missing(tmp_path: Path) -> str:
    return str(tmp_path / "missing")


@pytest.mark.parametrize(
    ("spec", "answers", "reason"),
    [
        (
            _spec,
            {("rev-parse",): failed("git rev-parse", "fatal: not a git repository")},
            "not a git repository",
        ),
        (_spec, {("rev-parse",): "feature\n"}, "not main"),
        (_spec, {("rev-parse",): "main\n", ("diff", "--cached"): "a.py\n"}, "unstage"),
        (_untitled_spec, {}, "the spec has no title"),
        (_missing, {}, "could not read the spec"),
    ],
    ids=["outside a git repo", "off main", "something staged", "no title", "missing spec"],
)
@pytest.mark.parametrize("dry_run", [True, False], ids=["dry run", "real run"])
def test_spec_publish_precondition_failures_are_refused_before_anything_is_published(
    kaizen, tmp_path, capsys, spec, answers, reason, dry_run
):
    shell = Shell(answers)
    argv = ["spec", "publish", spec(tmp_path)] + (["--dry-run"] if dry_run else [])

    assert kaizen(argv, run=shell) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused:")
    assert reason in err
    assert not shell.ran("gh")


def _bad_manifest(tmp_path: Path) -> str:
    manifest = tmp_path / "tickets.json"
    manifest.write_text(json.dumps({"tickets": []}))
    return str(manifest)


@pytest.mark.parametrize(
    ("manifest", "pr_list", "reason"),
    [
        (_bad_manifest, "", "needs an integer 'parent'"),
        (_missing, "", "could not read the manifest"),
        (_manifest, "CLOSED", "is closed, not merged"),
        (_manifest, failed("gh pr list", "HTTP 502"), "HTTP 502"),
    ],
    ids=["malformed manifest", "missing manifest", "closed domain-docs PR", "failed PR lookup"],
)
def test_ticket_publish_precondition_failures_are_refused_before_any_issue_exists(
    kaizen, tmp_path, capsys, manifest, pr_list, reason
):
    shell = Shell({("rev-parse", "--show-toplevel"): f"{RELAY}\n", ("pr", "list"): pr_list})

    assert kaizen(["ticket", "publish", manifest(tmp_path)], run=shell) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused:")
    assert reason in err
    assert not shell.ran("issue", "create")


def test_a_ticket_publish_failing_mid_batch_shows_what_was_made_and_what_is_left(
    kaizen, tmp_path, capsys
):
    for name in ("a", "b", "c"):
        (tmp_path / f"{name}.md").write_text("Body.\n")
    tickets = [
        {"key": "a", "title": "First", "body_file": "a.md"},
        {"key": "b", "title": "Second", "body_file": "b.md", "blocked_by": ["a"]},
        {"key": "c", "title": "Third", "body_file": "c.md"},
    ]
    manifest = tmp_path / "tickets.json"
    manifest.write_text(json.dumps({"parent": 300, "tickets": tickets}))
    created = iter(
        [
            "https://github.com/acme/relay/issues/301\n",
            "https://github.com/acme/relay/issues/302\n",
        ]
    )

    def create(cmd: list[str]) -> str:
        reply = next(created, None)
        if reply is None:
            raise failed("gh issue create", "HTTP 502")
        return reply

    def lookup(cmd: list[str]) -> str:
        number = int(cmd[2].rsplit("/", 1)[-1])
        return json.dumps({"id": 1000 + number, "title": "T", "state": "open"})

    shell = Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{RELAY}\n",
            ("issue", "create"): create,
            ("-X", "POST"): "",
            ("gh", "api"): lookup,
        }
    )
    assert kaizen(["ticket", "publish", str(manifest)], run=shell) == 1

    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert lines[:4] == [
        "created #301 First, a sub-issue of #300",
        "created #302 Second, a sub-issue of #300",
        "#302 is blocked by #301",
        "created so far: #301, #302",
    ]
    assert "  not created: c Third" in lines
    assert captured.err.startswith("error: gh issue create failed")


def _spec_start_shell(answers: dict | None = None) -> Shell:
    return Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{RELAY}\n",
            ("issue", "view"): '{"state": "OPEN", "title": "S", "labels": [{"name": "spec"}]}',
            ("ls-remote", "--heads"): "",
            ("ls-remote", "--symref"): "ref: refs/heads/main\tHEAD\nabc123\tHEAD\n",
            **(answers or {}),
        }
    )


def test_kaizen_routes_spec_start_to_its_command(kaizen, capsys):
    shell = _spec_start_shell()

    assert kaizen(["spec", "start", "25", "--dry-run"], run=shell) == 0

    assert "would push spec-25 to origin from origin/main" in capsys.readouterr().out
    assert not shell.ran("push")


def test_a_spec_start_failing_mid_run_shows_the_steps_already_done(kaizen, capsys):
    shell = _spec_start_shell({("push",): failed("git push", "remote: rejected")})

    assert kaizen(["spec", "start", "25"], run=shell) == 1

    captured = capsys.readouterr()
    assert captured.out.splitlines()[-1] == "leak check found nothing in origin/main"
    assert captured.err.startswith("error: git push failed")


def test_the_spec_groups_help_names_more_than_publishing(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["spec", "--help"], cwd=tmp_path, env={})

    out = capsys.readouterr().out
    assert "start" in out
    assert "publish a grilled spec and run" in out


def test_the_project_groups_help_says_it_creates_the_workflow_labels(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["project", "--help"], cwd=tmp_path, env={})

    out = " ".join(capsys.readouterr().out.split())
    assert "create the workflow labels the projects' repos lack" in out
    assert "sync" not in out


def test_kaizen_routes_spec_finish_to_its_command(kaizen, capsys):
    pr = '[{"number": 40, "state": "MERGED", "url": "u", "headRefOid": "abc123"}]'
    shell = Shell(
        {
            ("rev-parse", "--show-toplevel"): f"{RELAY}\n",
            ("pr", "list"): pr,
            ("for-each-ref",): "abc123\n",
        }
    )

    assert kaizen(["spec", "finish", "25", "--dry-run"], run=shell) == 0

    assert "would force-delete local branch spec-25" in capsys.readouterr().out
    assert not shell.ran("branch", "-D")


def test_kaizen_routes_project_leak_check_to_its_command(kaizen, capsys):
    shell = Shell({("rev-parse", "--show-toplevel"): f"{RELAY}\n"})

    assert kaizen(["project", "leak-check"], run=shell) == 0

    assert f"leak check found nothing in relay at {RELAY}" in capsys.readouterr().out


def test_kaizen_project_leak_check_exits_1_with_refused_and_the_matching_lines(kaizen, capsys):
    leaks = "docs/setup.md:3:see /fixture/home/relay\n"
    shell = Shell({("rev-parse", "--show-toplevel"): f"{SITE}\n", ("grep",): leaks})

    assert kaizen(["project", "leak-check"], run=shell) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused: leak check")
    assert "docs/setup.md:3: own reference /fixture/home" in err


def test_kaizen_project_labels_exits_1_when_a_label_creation_fails(kaizen):
    shell = Shell({("label", "list"): "[]", ("label", "create"): failed("gh label create")})

    assert kaizen(["project", "labels", "site"], run=shell) == 1


def test_kaizen_project_leak_check_staged_searches_the_index(kaizen):
    shell = Shell({("rev-parse", "--show-toplevel"): f"{RELAY}\n", ("grep",): failed("grep")})

    assert kaizen(["project", "leak-check", "--staged"], run=shell) == 0

    (grep,) = shell.ran("grep")
    assert "--cached" in grep


def test_kaizen_project_leak_check_searches_the_ticket_worktree_it_is_pointed_at(kaizen, capsys):
    worktree = SITE / ".claude" / "worktrees" / "fix-7-thing"
    shell = Shell({("rev-parse", "--show-toplevel"): f"{worktree}\n", ("grep",): failed("grep")})

    assert kaizen(["project", "leak-check", str(worktree)], run=shell) == 0

    (grep,) = shell.ran("grep")
    assert grep[:3] == ["git", "-C", str(worktree)]
    assert f"leak check found nothing in site at {worktree}" in capsys.readouterr().out


def _pr_checks(bucket: str) -> Shell:
    link = "https://github.com/o/r/actions/runs/7/job/70"
    check = {"name": "check", "bucket": bucket, "workflow": "CI", "link": link}
    return Shell({("pr", "checks"): json.dumps([check])})


@pytest.mark.parametrize(
    ("bucket", "code", "output"),
    [
        ("pass", 0, "all 1 check(s) passed on PR 42"),
        ("fail", 1, "gh run view 7 --log-failed"),
        ("pending", 2, "timed out after 0s on PR 42; still pending: check"),
    ],
    ids=["passed", "failed", "timed out"],
)
def test_kaizen_pr_wait_exits_with_the_code_of_the_checks_outcome(
    kaizen, capsys, bucket, code, output
):
    assert kaizen(["pr", "wait", "42", "--timeout", "0"], run=_pr_checks(bucket)) == code

    assert output in capsys.readouterr().out


_PIPED_FAILURE = """
import sys
from kaizen.shared.cli import main
from kaizen.tests.ticket_shell import SPEC_START, Shell, failed
shell = Shell({**SPEC_START, ("push",): failed("git push", "remote: rejected")})
sys.exit(main(["spec", "start", "25"], run=shell))
"""


def _subprocess_home(tmp_path: Path) -> Path:
    """The fixture home for a test that runs kaizen in a subprocess, which the tests' fixture
    can't reach, so it runs as the checkout's own version: the home records that version when
    it is a release, and none otherwise, so no comparison refuses it."""
    running = kaizen.__version__ if Version.parse(kaizen.__version__) else None
    return cli_home(tmp_path, synced_version=running)


def test_piped_kaizen_output_ends_with_the_error_after_every_progress_line(tmp_path):
    # Run from a fixture home, with the repo on the import path and no KAIZEN_HOME, so the
    # CLI's defaults (the cwd and the process environment) find that home.
    env = {k: v for k, v in os.environ.items() if k != "KAIZEN_HOME"}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    result = subprocess.run(
        [sys.executable, "-c", _PIPED_FAILURE],
        cwd=_subprocess_home(tmp_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert result.returncode == 1
    assert result.stdout.splitlines()[-4:] == [
        "leak check found nothing in origin/main",
        "error: git push failed:",
        "remote: rejected",
        "kaizen: exit 1 (failed: the steps printed above are done; finish the rest by hand)",
    ]


@pytest.mark.parametrize("name", ["kaizen", "kz"])
def test_either_installed_name_ends_its_stderr_with_the_kaizen_exit_trailer(tmp_path, name):
    # The console scripts sit beside the interpreter that runs the tests.
    script = Path(sys.executable).parent / name
    env = {k: v for k, v in os.environ.items() if k != "KAIZEN_HOME"}
    result = subprocess.run(
        [str(script), "issue", "show", "1"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert result.stderr.splitlines()[-1] == "kaizen: exit 1 (refused: nothing changed)"


@pytest.mark.parametrize("argv", [["--help"], ["ticket", "--help"]], ids=["kaizen", "group"])
def test_help_works_outside_any_home(tmp_path, capsys, argv):
    with pytest.raises(SystemExit) as exit_info:
        main(argv, run=Shell({}), cwd=tmp_path, env={})

    assert exit_info.value.code == 0
    assert "usage: kaizen" in capsys.readouterr().out


def test_a_command_outside_any_home_is_refused_before_it_runs(tmp_path, capsys):
    shell = Shell({})

    assert main(["spec", "status", "25"], run=shell, cwd=tmp_path, env={}) == 1

    err = capsys.readouterr().err
    assert err.startswith("refused: home: no home found")
    assert "KAIZEN_HOME" in err
    assert "kaizen.toml" in err
    assert shell.calls == []


def test_kaizen_home_finds_the_home_from_a_project_root_outside_its_tree(tmp_path, capsys):
    home = cli_home(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    shell = Shell({("rev-parse", "--show-toplevel"): f"{RELAY}\n"})

    code = main(["project", "leak-check"], run=shell, cwd=project, env={"KAIZEN_HOME": str(home)})

    assert code == 0
    assert f"leak check found nothing in relay at {RELAY}" in capsys.readouterr().out


def test_kaizen_home_and_the_nearest_marker_disagreeing_is_refused(tmp_path, capsys):
    home = cli_home(tmp_path)
    other = cli_home(tmp_path / "other")
    shell = Shell({})

    code = main(["project", "leak-check"], run=shell, cwd=other, env={"KAIZEN_HOME": str(home)})

    assert code == 1
    assert capsys.readouterr().err.startswith("refused: home: KAIZEN_HOME names")
    assert shell.calls == []


def test_a_malformed_marker_is_refused_before_any_command_runs(tmp_path, capsys):
    home = cli_home(tmp_path)
    (home / "kaizen.toml").write_text("registry = [\n")
    shell = Shell({})

    assert main(["project", "leak-check"], run=shell, cwd=home, env={}) == 1

    err = capsys.readouterr().err
    assert err.startswith(f"refused: home: {home.resolve() / 'kaizen.toml'} is not valid TOML")
    assert shell.calls == []


def test_home_init_is_the_only_command_that_runs_without_a_home():
    exempt = [
        name
        for name, command in command_parsers().items()
        if command.get_default("needs_home") is False
    ]

    assert exempt == ["home init"]


def test_kaizen_help_lists_the_home_group(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["--help"], run=Shell({}), cwd=tmp_path, env={})

    assert "set up a new home" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("bucket", "line"),
    [("pass", "kaizen: exit 0"), ("fail", "kaizen: exit 1"), ("pending", "kaizen: exit 2")],
    ids=["passed", "failed checks", "timed out"],
)
def test_the_last_stderr_line_is_the_exit_code_the_handler_returned(kaizen, capsys, bucket, line):
    kaizen(["pr", "wait", "42", "--timeout", "0"], run=_pr_checks(bucket))

    assert capsys.readouterr().err.splitlines()[-1] == line


def test_the_last_stderr_line_of_a_refusal_says_nothing_changed(tmp_path, capsys):
    assert main(["spec", "status", "25"], run=Shell({}), cwd=tmp_path, env={}) == 1

    assert capsys.readouterr().err.splitlines()[-1] == "kaizen: exit 1 (refused: nothing changed)"


def test_the_last_stderr_line_of_a_failed_step_says_the_steps_above_are_done(kaizen, capsys):
    shell = Shell({**SPEC_START, ("push",): failed("git push", "remote: rejected")})

    assert kaizen(["spec", "start", "25"], run=shell) == 1

    assert capsys.readouterr().err.splitlines()[-2:] == [
        "remote: rejected",
        "kaizen: exit 1 (failed: the steps printed above are done; finish the rest by hand)",
    ]


_SPEC_START = """
import sys
from kaizen.shared.cli import main
from kaizen.tests.ticket_shell import SPEC_START, Shell
shell = Shell(SPEC_START)
code = main(["spec", "start", "25"], run=shell)
print("ran:", *(" ".join(cmd) for cmd in shell.calls), sep="\\n", file=sys.stderr)
sys.exit(code)
"""


def _run_with_closed_pipe(tmp_path, *, stderr_too: bool) -> subprocess.CompletedProcess:
    """Runs ``kaizen spec start`` with stdout (and stderr, if *stderr_too*) writing into a pipe
    whose reader has already gone, as `kaizen ... | head` leaves it once head exits."""
    env = {k: v for k, v in os.environ.items() if k != "KAIZEN_HOME"}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    reader, writer = os.pipe()
    os.close(reader)
    try:
        return subprocess.run(
            [sys.executable, "-c", _SPEC_START],
            cwd=_subprocess_home(tmp_path),
            env=env,
            stdout=writer,
            stderr=writer if stderr_too else subprocess.PIPE,
            text=True,
        )
    finally:
        os.close(writer)


def test_kaizen_runs_to_the_end_when_the_reader_of_its_stdout_has_gone(tmp_path):
    result = _run_with_closed_pipe(tmp_path, stderr_too=False)

    outcome, ran = result.stderr.split("ran:\n")
    assert outcome.splitlines()[-1] == "kaizen: exit 0"
    assert " push origin " in ran


def test_a_closed_pipe_prints_no_traceback(tmp_path):
    assert "Traceback" not in _run_with_closed_pipe(tmp_path, stderr_too=False).stderr


def test_kaizen_exits_with_its_own_code_when_the_reader_of_all_its_output_has_gone(tmp_path):
    assert _run_with_closed_pipe(tmp_path, stderr_too=True).returncode == 0


def test_the_last_stderr_line_of_a_crash_follows_its_traceback(kaizen, capsys):
    shell = Shell({("pr", "checks"): FileNotFoundError(2, "No such file", "gh")})

    assert kaizen(["pr", "wait", "42", "--timeout", "0"], run=shell) == 1

    err = capsys.readouterr().err
    assert "Traceback" in err
    assert err.splitlines()[-1] == (
        "kaizen: exit 1 (crashed: see the traceback above; the steps printed above are done)"
    )
