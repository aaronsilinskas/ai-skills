"""``kaizen issue publish``: create one issue in the current project's repo, after the leak
check."""

import argparse
from pathlib import Path

from kaizen.shared.common import RefusalError, Runner, Say
from kaizen.shared.home import Home
from kaizen.shared.labels import repo_labels
from kaizen.shared.leak import leak_check_text
from kaizen.shared.pr import read_body
from kaizen.shared.registry import resolve_checkout


def publish(
    title: str,
    body_file: Path,
    labels: list[str],
    run: Runner,
    *,
    dry_run: bool = False,
    home: Home,
    say: Say = print,
) -> None:
    """Creates the issue and prints its URL. A blank title, an unreadable body, text that fails
    the leak check for the current project, or a label its repo lacks refuses before any write;
    a dry run makes every check and prints the plan."""
    if not title.strip():
        raise RefusalError("the issue title is blank", "pass the issue's title to --title")
    body = read_body(body_file, "issue body")
    project, _ = resolve_checkout(run, None, home.registry)
    texts = {"issue title": title, "issue body": body}
    leak_check_text(texts, home, public=project.public, denied=project.leak_deny)
    labels = list(dict.fromkeys(labels))
    if labels:
        _check_labels(project.github, labels, run)
    if dry_run:
        say(f"would create in {project.github}: {title} (labels: {', '.join(labels) or 'none'})")
        return
    cmd = ["gh", "issue", "create", "-R", project.github, "--title", title]
    cmd += ["--body-file", str(body_file)]
    for label in labels:
        cmd += ["--label", label]
    say(run(cmd).strip().splitlines()[-1])


def _check_labels(github: str, labels: list[str], run: Runner) -> None:
    """Refuses when repo *github* lacks any of *labels*, so the create can't fail on one."""
    present = repo_labels(github, run, "check that `gh label list` works for that repo, then rerun")
    missing = [label for label in labels if label not in present]
    if missing:
        raise RefusalError(
            f"{github} has no label {', '.join(missing)}",
            "create it in the repo (`kaizen project labels` creates the workflow labels), "
            "or drop that --label",
        )


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "publish",
        help="create one issue in the current project's repo, after the leak check",
        description=(
            "Create an issue in the repo of the project whose main checkout or ticket worktree "
            "it runs from, and print its URL. The title and body must pass the leak check's "
            "rules for that project (its leak_deny patterns included), and each --label must "
            "exist in its repo; any failure refuses before the issue is created, dry runs "
            "included. Use it for every issue filed by hand, such as an idea from to-idea."
        ),
    )
    parser.add_argument("--title", required=True, help="the issue's title")
    parser.add_argument(
        "--body-file", required=True, type=Path, help="a file holding the issue's body"
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="a label the issue gets, which must exist in the repo; repeat for more",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run every check and print the issue it would create, creating nothing",
    )
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    publish(args.title, args.body_file, args.label, run, dry_run=args.dry_run, home=home)
