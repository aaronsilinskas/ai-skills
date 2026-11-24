"""Publish a grilled local spec to GitHub and ship the domain-doc edits from grilling.

The publish step at the tail of ``grill-with-docs`` (see the Spec workflow in the
home's docs), in order:

1. Create the spec issue (label ``spec``): title from the spec's ``# `` heading,
   body is everything after it.
2. Delete the local spec file.
3. Close the source ``idea`` issue (``--idea``) as superseded by the spec.
4. If ``GLOSSARY.md`` or ``docs/adr/`` has changes, commit only those on a new
   ``spec-<N>-domain-docs`` branch, push, open a PR referencing the spec, turn on
   auto-merge, switch back to ``main``, and delete the local branch.

Every precondition is checked before anything leaves the machine: on ``main``,
nothing staged, the spec has a title, the checkout is a registered project's main
checkout, and the spec's title and body and the changed domain docs pass the
leak check's rules for that project. The domain-doc commit is leak-checked again
before it is pushed. Each step prints as it completes, so a failure partway through shows
exactly what is already done.

Usage
-----
Run from the project's root::

    kaizen spec publish docs/spec/<slug>.md \\
        --idea 1179 --co-author "Claude Opus 5.5 <noreply@anthropic.com>"
    kaizen spec publish docs/spec/<slug>.md --dry-run
"""

import argparse
import tempfile
from pathlib import Path

from kaizen.shared.common import RefusalError, Runner, Say, run_or_refuse
from kaizen.shared.home import Home
from kaizen.shared.leak import (
    added_lines,
    leak_check,
    leak_check_denied,
    leak_check_text,
    numbered_lines,
)
from kaizen.shared.pr import enable_auto_merge, with_footer
from kaizen.shared.registry import Project, resolve_current

DOMAIN_DOC_PATHS = ("GLOSSARY.md", "docs/adr")
OUTSIDE_CHECKOUT_FIX = "run from the project's root, inside its git checkout"


def split_spec(text: str) -> tuple[str, str]:
    """Return the spec's ``# `` heading text and the body after it."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title, "\n".join(lines[i + 1 :]).strip() + "\n"
            break
        if line.strip():
            break
    raise RefusalError("the spec has no title", "start the spec with a non-blank '# ' title line")


def changed_domain_docs(run: Runner) -> tuple[list[str], set[str]]:
    """Modified or untracked paths under the domain docs (glossary, ADRs), and the untracked
    ones among them."""
    out = run_or_refuse(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", *DOMAIN_DOC_PATHS],
        run,
        "could not read the domain docs' git status",
        OUTSIDE_CHECKOUT_FIX,
    )
    statuses = [(line[:2], line[3:]) for line in out.splitlines() if line.strip()]
    return [path for _, path in statuses], {path for status, path in statuses if status == "??"}


def check_preconditions(run: Runner) -> None:
    branch = run_or_refuse(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        run,
        "could not read the branch",
        OUTSIDE_CHECKOUT_FIX,
    ).strip()
    if branch != "main":
        raise RefusalError(f"on {branch!r}, not main", "switch to main and rerun")
    staged = run_or_refuse(
        ["git", "diff", "--cached", "--name-only"],
        run,
        "could not read the staged files",
        OUTSIDE_CHECKOUT_FIX,
    ).strip()
    if staged:
        raise RefusalError(
            f"files are staged and would ride along in the commit: {staged}",
            "unstage them (git restore --staged <path>) and rerun",
        )


def check_text(title: str, body: str, project: Project, home: Home) -> None:
    """Refuses when the spec issue's *title* or *body* points outside *home*, judged for
    *project*."""
    texts = {"issue title": title, "issue body": body}
    leak_check_text(texts, home, public=project.public, denied=project.leak_deny)


def check_domain_docs(
    docs: list[str], untracked: set[str], project: Project, home: Home, run: Runner
) -> None:
    """Refuses when a changed domain doc that still exists points outside *home*, judged for
    *project*, or adds a line *project* denies, so a leak in one refuses before the spec issue
    is created. Only an *untracked* doc is searched whole for denied patterns."""
    root = Path(project.path)
    texts = {doc: (root / doc).read_text() for doc in docs if (root / doc).is_file()}
    leak_check_text(texts, home, public=project.public)
    if not project.leak_deny or not texts:
        return
    tracked = tuple(doc for doc in texts if doc not in untracked)
    lines = added_lines(root, run, ["HEAD"], tracked) if tracked else []
    lines += numbered_lines({doc: text for doc, text in texts.items() if doc in untracked}, ":")
    leak_check_denied(lines, project.leak_deny, "domain-doc text")


def prepare(spec: Path, run: Runner, home: Home) -> tuple[str, str, list[str], Project]:
    """Every check before anything leaves the machine, run from the main checkout of a
    registered project; returns the spec's title and body, the changed domain docs and the
    project."""
    title, body = split_spec(_read_spec(spec))
    check_preconditions(run)
    project = resolve_current(run, home.registry)
    check_text(title, body, project, home)
    docs, untracked = changed_domain_docs(run)
    check_domain_docs(docs, untracked, project, home, run)
    return title, body, docs, project


def publish(
    spec: Path,
    idea: int | None,
    co_author: str | None,
    run: Runner,
    say: Say = print,
    *,
    home: Home,
) -> int:
    """Run every step; returns the spec issue number."""
    title, body, docs, project = prepare(spec, run, home)

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
        handle.write(body)
    try:
        url = run(
            [
                "gh",
                "issue",
                "create",
                "--label",
                "spec",
                "--title",
                title,
                "--body-file",
                handle.name,
            ]
        )
    finally:
        Path(handle.name).unlink()
    number = int(url.strip().splitlines()[-1].rsplit("/", 1)[-1])
    say(f"spec published: #{number} {title}")

    spec.unlink()
    say(f"deleted {spec}")

    if idea is not None:
        run(
            [
                "gh",
                "issue",
                "close",
                str(idea),
                "--reason",
                "not planned",
                "--comment",
                f"Superseded by spec #{number}.",
            ]
        )
        say(f"closed idea #{idea} as superseded")

    if not docs:
        say("no GLOSSARY.md or docs/adr/ changes: no PR opened")
        return number

    branch = f"spec-{number}-domain-docs"
    message = f"Domain docs for spec #{number}: {title}"
    trailer = f"\n\nCo-Authored-By: {co_author}" if co_author else ""
    run(["git", "checkout", "-b", branch])
    run(["git", "add", "--", *docs])
    run(["git", "commit", "-m", message + trailer])
    say(f"committed the domain docs on {branch}")
    leak_check(
        Path(project.path),
        home,
        run,
        "HEAD",
        public=project.public,
        denied=project.leak_deny,
        base="origin/main",
    )
    run(["git", "push", "-u", "origin", branch])
    pr_body = with_footer(
        f"Domain-doc edits from grilling spec #{number}.\n\nRefs #{number}\n", home.pr_footer
    )
    pr = run(["gh", "pr", "create", "--title", message, "--body", pr_body]).strip().splitlines()[-1]
    enable_auto_merge(pr, run)
    run(["git", "checkout", "main"])
    # The PR merges from the pushed branch, so the local copy has no further use.
    run(["git", "branch", "-D", branch])
    say(f"domain-doc PR with auto-merge: {pr} ({', '.join(docs)})")
    return number


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "publish",
        help="publish a grilled local spec and ship its domain-doc edits",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("spec", type=Path, help="the local spec file, docs/spec/<slug>.md")
    parser.add_argument("--idea", type=int, help="source idea issue to close as superseded")
    parser.add_argument("--co-author", help="'Name <email>' for the commit's Co-Authored-By")
    parser.add_argument(
        "--dry-run", action="store_true", help="check preconditions and print the plan"
    )
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    if not args.dry_run:
        publish(args.spec, args.idea, args.co_author, run, home=home)
        return
    title, _, docs, _ = prepare(args.spec, run, home)
    print(f"spec: {title}")
    print(f"idea to close: {f'#{args.idea}' if args.idea else 'none'}")
    print(f"domain docs for the PR: {', '.join(docs) or 'none (no PR)'}")


def _read_spec(spec: Path) -> str:
    try:
        return spec.read_text()
    except OSError as exc:
        raise RefusalError(f"could not read the spec: {exc}", "pass the local spec's path") from exc
