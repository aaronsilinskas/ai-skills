"""``kaizen spec start``: create a spec's integration branch, on origin or, with ``--local``, only
in the main checkout's clone until its first integration pushes it."""

import argparse
import json

from kaizen.shared.branch import (
    IntegrationBranch,
    find_integration_branch,
    integration_branch,
    remote_default_branch,
)
from kaizen.shared.common import RefusalError, Runner, Say, run_or_refuse
from kaizen.shared.home import Home
from kaizen.shared.leak import leak_check
from kaizen.shared.registry import Project, resolve_current
from kaizen.spec.common import refuse_checked_out

SPEC_LABEL = "spec"


def start(
    spec: int,
    run: Runner,
    *,
    home: Home,
    local: bool = False,
    dry_run: bool = False,
    say: Say = print,
) -> str:
    """Create spec *spec*'s integration branch from ``origin``'s default branch; returns its name.

    It is pushed to ``origin``, or with *local* made only as a local branch, which the spec's
    first ``kaizen spec integrate`` pushes. Without *local*, a local branch an earlier *local*
    run made is pushed and then deleted, so ``origin`` holds the only copy.
    """
    project = resolve_current(run, home.registry)
    checkout = project.main_checkout
    say(f"{project.name} project at {checkout}")
    title = _open_spec_title(project.github, spec, run)
    say(f"spec #{spec} is open: {title}")
    branch = integration_branch(spec)
    next_step = f"`kaizen ticket start {project.name} <issue> --spec {spec}`"
    found = find_integration_branch(checkout, spec, run)
    if found is not None and found.on_origin:
        raise RefusalError(
            f"origin already has {branch}: spec #{spec} is started",
            f"continue it: start each ticket's worktree with {next_step}",
        )
    if found is not None:
        if local:
            raise RefusalError(
                f"{branch} already exists locally: spec #{spec} is started with --local",
                f"continue it: start each ticket's worktree with {next_step}; its first "
                f"`kaizen spec integrate` pushes {branch}, or `kaizen spec start {spec}` "
                "pushes it now",
            )
        _push_local(project, spec, found, home, run, dry_run=dry_run, say=say)
        say(f"start ticket worktrees with {next_step}")
        return branch
    say(f"origin has no {branch} yet")
    default = remote_default_branch(checkout, run)
    base = f"origin/{default}"

    if dry_run:
        say(f"would fetch origin in {checkout}")
        say(f"would run the leak check on {base}")
        if local:
            say(f"would create the local branch {branch} from {base}, pushing nothing")
        else:
            say(f"would push {branch} to origin from {base}")
        return branch

    # Fetching moves only remote-tracking refs, so a leak refusal after it still changes nothing.
    run(["git", "-C", checkout, "fetch", "origin"])
    say(f"fetched origin in {checkout} (default branch {default})")
    # The branch's commit is origin's, not the main checkout's, which may hold other work.
    leak_check(project.path, home, run, base, public=project.public)
    say(f"leak check found nothing in {base}")
    if local:
        # `git branch` writes only the ref, so the main checkout's tree and branch are untouched.
        run(["git", "-C", checkout, "branch", "--no-track", branch, f"refs/remotes/{base}"])
        say(f"created the local branch {branch} from {base}; nothing was pushed")
        say(f"its first `kaizen spec integrate` pushes {branch} to origin")
    else:
        # Pushing the remote-tracking ref makes no local branch, so the main checkout is untouched.
        run(["git", "-C", checkout, "push", "origin", f"refs/remotes/{base}:refs/heads/{branch}"])
        say(f"pushed {branch} to origin from {base}")
    say(f"start ticket worktrees with {next_step}")
    return branch


def _push_local(
    project: Project,
    spec: int,
    found: IntegrationBranch,
    home: Home,
    run: Runner,
    *,
    dry_run: bool,
    say: Say,
) -> None:
    """Pushes the local integration branch an earlier ``--local`` run made, then deletes it."""
    checkout, branch = project.main_checkout, found.name
    say(f"origin has no {branch} yet, but a local {branch} does (started with --local)")
    refuse_checked_out(checkout, branch, run, rerun=f"kaizen spec start {spec}")
    if dry_run:
        say(f"would run the leak check on {branch}")
        say(f"would push the local {branch} to origin, then delete the local branch")
        return
    leak_check(project.path, home, run, branch, public=project.public)
    say(f"leak check found nothing in {branch}")
    run(["git", "-C", checkout, "push", "origin", f"refs/heads/{branch}:refs/heads/{branch}"])
    say(f"pushed the local {branch} to origin")
    # Force-delete is safe: origin now holds the same commit.
    run(["git", "-C", checkout, "branch", "-D", branch])
    say(f"deleted the local {branch}, which origin now holds")


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "start",
        help="create a spec's integration branch, pushed or (--local) local only",
        description=(
            "Run from the project's root. Check that the issue is an open spec and that origin "
            "has no spec-<N> yet, run the leak check, then push spec-<N> to origin from origin's "
            "default branch; no local branch is made. With --local, create spec-<N> as a local "
            "branch from origin's default branch instead and push nothing: `kaizen ticket start "
            "--spec`, `ticket diff` and `ticket compare` use it while origin lacks it, and the "
            "spec's first `kaizen spec integrate` pushes it. Without --local, a local spec-<N> an "
            "earlier --local run made is leak-checked, pushed and then deleted. Neither changes "
            "the main checkout's working tree or current branch. A spec already on origin, or "
            "already local with --local, is refused: continue it with "
            "`kaizen ticket start <project> <issue> --spec <N>`."
        ),
    )
    parser.add_argument("spec", type=int, help="the spec's issue number")
    parser.add_argument(
        "--local",
        action="store_true",
        help="create spec-<N> only as a local branch; its first integration pushes it",
    )
    parser.add_argument("--dry-run", action="store_true", help="run only queries; print the plan")
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    start(args.spec, run, home=home, local=args.local, dry_run=args.dry_run)


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
