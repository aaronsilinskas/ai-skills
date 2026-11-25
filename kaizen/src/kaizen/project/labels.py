"""``kaizen project labels``: create the **workflow labels** a project's GitHub repo lacks."""

import argparse
import subprocess

from kaizen.shared.command_records import HomeCommand
from kaizen.shared.common import Runner, Say, Subparsers
from kaizen.shared.home import Home
from kaizen.shared.labels import Label, repo_labels
from kaizen.shared.registry import Project, all_projects, resolve


def create_missing_labels(
    run: Runner,
    name: str | None = None,
    *,
    home: Home,
    dry_run: bool = False,
    say: Say = print,
) -> int:
    """Creates, in the GitHub repo of the project called *name* (default: every registered
    project), each of the home's workflow labels it lacks, and warns about one present with another
    colour or description, which it never edits. Every repo's labels are listed before any is
    created, and a repo two projects share is handled once. Returns 1 when a creation failed, after
    trying every other one; 0 otherwise."""
    projects = [resolve(name, home.registry)] if name else all_projects(home.registry)
    labels_by_repo = {project.github: _present_labels(project, run) for project in projects}
    failed = False
    for repo, present in labels_by_repo.items():
        failed |= not _create_missing_in_repo(
            repo, home.workflow_labels, present, run, dry_run, say
        )
    return 1 if failed else 0


def _present_labels(project: Project, run: Runner) -> dict[str, Label]:
    """The labels of *project*'s repo by name, colours lowercased; refuses when gh can't list
    them."""
    repo = project.github
    fix = f"check that {repo}, the github field of {project.page}, exists and gh can read it"
    return repo_labels(repo, run, fix)


def _create_missing_in_repo(
    repo: str,
    wanted: tuple[Label, ...],
    present: dict[str, Label],
    run: Runner,
    dry_run: bool,
    say: Say,
) -> bool:
    """Creates the labels of *wanted* that *repo* lacks and prints its summary; whether every
    creation succeeded."""
    missing = [label for label in wanted if label.name not in present]
    differ = [label for label in wanted if present.get(label.name) not in (None, label)]
    for label in differ:
        found = present[label.name]
        say(
            f"{repo}: warning: {label.name} is {found.color} {found.description!r}, "
            f"not {label.color} {label.description!r}; left as it is"
        )
    kept = f"{len(wanted) - len(missing)} already present ({len(differ)} differ)"
    if dry_run:
        for label in missing:
            say(f"{repo}: would create {label.name}")
        say(f"{repo}: {len(missing)} to create, {kept}")
        return True
    failures = sum(not _create_label(repo, label, run, say) for label in missing)
    say(f"{repo}: {len(missing) - failures} created, {failures} failed, {kept}")
    return failures == 0


def _create_label(repo: str, label: Label, run: Runner, say: Say) -> bool:
    """Creates *label* in *repo* and prints the outcome; whether it was created."""
    try:
        run(
            [
                *("gh", "label", "create", label.name, "-R", repo),
                *("--color", label.color, "--description", label.description),
            ]
        )
    except subprocess.CalledProcessError as exc:
        say(f"{repo}: failed to create {label.name}: {(exc.stderr or '').strip()}")
        return False
    say(f"{repo}: created {label.name}")
    return True


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "labels",
        help="create the workflow labels a project's GitHub repo lacks",
        description=(
            "Create, in each registered project's GitHub repo (or the named project's), every "
            "workflow label of the home it lacks, with its colour and description: the labels "
            "the home's marker sets, or the default set when it sets none. A label already "
            "there is never edited or deleted: one with another colour or description is "
            "reported as a warning and left. Prints one summary line per repo, and exits 1 when "
            "any creation failed, after trying the rest. Run it when a project is added to the "
            "registry."
        ),
    )
    parser.add_argument(
        "project",
        nargs="?",
        help="a registered project's name, a page in the registry (default: every project)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="list the labels only and print the plan"
    )
    parser.set_defaults(command=HomeCommand(_command))


def _command(args: argparse.Namespace, run: Runner, home: Home) -> int:
    return create_missing_labels(run, args.project, home=home, dry_run=args.dry_run)
