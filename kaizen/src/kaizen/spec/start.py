"""``kaizen spec start``: create and push a spec's integration branch."""

import argparse
import json

from kaizen.shared.branch import integration_branch, remote_default_branch
from kaizen.shared.common import RefusalError, Runner, Say, run_or_refuse
from kaizen.shared.home import Home
from kaizen.shared.leak import leak_check
from kaizen.shared.registry import resolve_current
from kaizen.spec.common import has_integration_branch

SPEC_LABEL = "spec"


def start(
    spec: int,
    run: Runner,
    *,
    home: Home,
    dry_run: bool = False,
    say: Say = print,
) -> str:
    """Push spec *spec*'s integration branch from ``origin``'s default branch; returns its name."""
    project = resolve_current(run, home.registry)
    checkout = project.main_checkout
    say(f"{project.name} project at {checkout}")
    title = _open_spec_title(project.github, spec, run)
    say(f"spec #{spec} is open: {title}")
    branch = integration_branch(spec)
    next_step = f"`kaizen ticket start {project.name} <issue> --spec {spec}`"
    if has_integration_branch(checkout, spec, run):
        raise RefusalError(
            f"origin already has {branch}: spec #{spec} is started",
            f"continue it: start each ticket's worktree with {next_step}",
        )
    say(f"origin has no {branch} yet")
    default = remote_default_branch(checkout, run)
    base = f"origin/{default}"

    if dry_run:
        say(f"would fetch origin in {checkout}")
        say(f"would run the leak check on {base}")
        say(f"would push {branch} to origin from {base}")
        return branch

    # Fetching moves only remote-tracking refs, so a leak refusal after it still changes nothing.
    run(["git", "-C", checkout, "fetch", "origin"])
    say(f"fetched origin in {checkout} (default branch {default})")
    # The pushed commit is origin's, not the main checkout's, which may hold other work.
    leak_check(project.path, home, run, base, public=project.public)
    say(f"leak check found nothing in {base}")
    # Pushing the remote-tracking ref creates no local branch, so the main checkout is untouched.
    run(["git", "-C", checkout, "push", "origin", f"refs/remotes/{base}:refs/heads/{branch}"])
    say(f"pushed {branch} to origin from {base}")
    say(f"start ticket worktrees with {next_step}")
    return branch


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "start",
        help="create and push a spec's integration branch",
        description=(
            "Run from the project's root. Check that the issue is an open spec and that origin "
            "has no spec-<N> yet, run the leak check, then push spec-<N> "
            "to origin from origin's default branch. No local branch is made, so the main "
            "checkout is never changed. A spec already started is refused: continue it with "
            "`kaizen ticket start <project> <issue> --spec <N>`."
        ),
    )
    parser.add_argument("spec", type=int, help="the spec's issue number")
    parser.add_argument("--dry-run", action="store_true", help="run only queries; print the plan")
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    start(args.spec, run, home=home, dry_run=args.dry_run)


def _open_spec_title(github: str, spec: int, run: Runner) -> str:
    """The title of issue *spec*; refuses unless it is open and labelled ``spec``."""
    out = run_or_refuse(
        ["gh", "-R", github, "issue", "view", str(spec), "--json", "state,title,labels"],
        run,
        f"could not read issue #{spec} in {github}",
        f"check the spec number and that `gh -R {github} issue view {spec}` works",
    )
    data = json.loads(out)
    title = str(data["title"])
    if data["state"] != "OPEN":
        raise RefusalError(
            f"issue #{spec} is closed: {title}",
            "pass the number of an open spec, or reopen this one if its work is still wanted",
        )
    if SPEC_LABEL not in {label["name"] for label in data["labels"]}:
        raise RefusalError(
            f"issue #{spec} is not labelled {SPEC_LABEL}: {title}",
            "pass the spec's issue number, not a ticket's or an idea's",
        )
    return title
