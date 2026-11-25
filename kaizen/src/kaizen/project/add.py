"""``kaizen project add``: register a project with the home: its registry page, its link in the
registry README, and its directory in the home's Claude Code settings."""

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from kaizen.shared.command_records import HomeCommand
from kaizen.shared.common import (
    RefusalError,
    Runner,
    Say,
    Subparsers,
    run_or_refuse,
    unified_diff,
)
from kaizen.shared.home import (
    DIRECTORIES,
    SETTINGS,
    Home,
    SettingsError,
    add_directory,
    home_path,
    read_settings,
    settings_text,
)
from kaizen.shared.registry import (
    GITHUB_REPO,
    KEYS,
    NO_CHECK,
    WORKTREES,
    all_projects,
    github_remote,
    page_text,
    parse_page_text,
    starter_readme,
    with_page_listed,
    wrap,
)

Ask = Callable[[str], str]
"""Shows a prompt on a terminal and returns the line typed; raises ``EOFError`` when the input
ends. ``input`` is the real one."""

_NAME = re.compile(r"[\w.-]+")
_SUMMARY = {key.name: key.summary for key in KEYS}


@dataclass(frozen=True)
class Value:
    """A field's value as the page writes it, and where it came from, for the output."""

    text: str
    source: str
    """Where it came from, in a few words, such as ``detected from origin``."""
    detail: str = ""
    """What the source showed, such as the remote's URL; empty when there is nothing more."""

    def shown(self) -> str:
        return f"{self.source}, {self.detail}" if self.detail else self.source


Detect = Callable[[Runner, Path, dict[str, Value]], Value | None]
"""Works out a field's value from the checkout and the fields settled before it; ``None`` when
there is nothing to suggest. Only queries."""


@dataclass(frozen=True)
class Field:
    """One page key the command settles, from its flag, a detection, a prompt or its default."""

    key: str
    flag: str
    options: str
    """The answers it takes, as its prompt shows them."""
    problem: Callable[[str], str | None]
    """What is wrong with an answer, or ``None`` when it is valid."""
    detect: Detect | None = None
    default: Callable[[Path], str] | None = None
    """For an optional key, what the registry assumes when the page leaves it out, as its
    prompt offers it; empty for none. A key with no default is required."""

    @property
    def required(self) -> bool:
        return self.default is None

    @property
    def boolean(self) -> bool:
        return self.problem is _bool_problem


def _detect_github(run: Runner, path: Path, settled: dict[str, Value]) -> Value | None:
    try:
        url = run(["git", "-C", str(path), "remote", "get-url", "origin"]).strip()
    except subprocess.CalledProcessError:
        return None
    remote = github_remote(url)
    if remote is None:
        return None
    return Value("/".join(remote), "detected from origin", url)


def _detect_public(run: Runner, path: Path, settled: dict[str, Value]) -> Value | None:
    if "github" not in settled:
        return None
    repo = settled["github"].text
    try:
        reply = run(["gh", "repo", "view", repo, "--json", "visibility"])
        visibility = str(json.loads(reply)["visibility"])
    except (subprocess.CalledProcessError, ValueError, KeyError, TypeError):
        return None
    public = "true" if visibility.upper() == "PUBLIC" else "false"
    return Value(public, "detected from GitHub", f"{repo} is {visibility}")


def _detect_check(run: Runner, path: Path, settled: dict[str, Value]) -> Value | None:
    if (path / "scripts" / "check.sh").is_file():
        return Value("bash scripts/check.sh", "detected", "scripts/check.sh exists")
    return None


def _detect_code_paths(run: Runner, path: Path, settled: dict[str, Value]) -> Value | None:
    tracked = run(["git", "-C", str(path), "ls-files"]).splitlines()
    directories = sorted({f"{line.split('/')[0]}/" for line in tracked if "/" in line})
    if not directories:
        return None
    return Value(", ".join(directories), "detected", "the top-level tracked directories")


def _repo_problem(answer: str) -> str | None:
    return None if GITHUB_REPO.fullmatch(answer) else f"{answer!r} is not owner/repo"


def _bool_problem(answer: str) -> str | None:
    return None if answer in ("true", "false") else f"{answer!r} is not true or false"


def _command_problem(answer: str) -> str | None:
    if answer in ("true", "false"):
        return f"{answer!r} would read as a boolean, not a command"
    return None if answer else "it is empty"


def _list_problem(answer: str) -> str | None:
    return None if any(entry.strip() for entry in answer.split(",")) else "it lists nothing"


def _path_problem(answer: str) -> str | None:
    if Path(answer).is_absolute() or answer.startswith("~/"):
        return None
    return f"{answer!r} is not absolute or from ~/"


def _links_problem(answer: str) -> str | None:
    if any(char in answer for char in "*?"):
        return "a worktree link is linked by name, so it can't be a glob"
    entries = [Path(entry.strip()) for entry in answer.split(",") if entry.strip()]
    if any(entry.is_absolute() or ".." in entry.parts for entry in entries):
        return "list paths relative to the project root, with no '..' parts"
    return _list_problem(answer)


FIELDS = (
    Field("github", "--github", "owner/repo", _repo_problem, detect=_detect_github),
    Field("public", "--public or --private", "true/false", _bool_problem, detect=_detect_public),
    Field("check", "--check", f"a shell command, or {NO_CHECK}", _command_problem, _detect_check),
    Field(
        "code_paths",
        "--code-paths",
        "comma-separated paths",
        _list_problem,
        detect=_detect_code_paths,
    ),
    Field(
        "worktree_root",
        "--worktree-root",
        "absolute or ~/ path",
        _path_problem,
        default=lambda path: str(path / WORKTREES),
    ),
    Field(
        "auto_merge_paths",
        "--auto-merge-paths",
        "comma-separated paths",
        _list_problem,
        default=lambda path: "",
    ),
    Field(
        "auto_merge_comment_only",
        "--auto-merge-comment-only or --no-auto-merge-comment-only",
        "true/false",
        _bool_problem,
        default=lambda path: "false",
    ),
    Field(
        "worktree_links",
        "--worktree-links",
        "comma-separated paths",
        _links_problem,
        default=lambda path: "",
    ),
)
"""Every page key but ``path``, in the order they are settled and asked for."""


def add_project(
    run: Runner,
    home: Home,
    name: str,
    path: Path | None,
    given: Mapping[str, str],
    *,
    ask: Ask | None,
    dry_run: bool = False,
    say: Say = print,
) -> None:
    """Registers the project *name* whose main checkout is *path* (default: the git checkout
    the command runs in): writes its page, lists it in the registry README and adds *path* to
    the settings' additional directories when missing.

    Each field comes from *given* (its flag's value), else, on a terminal (*ask*), from the
    answer to its prompt, which offers what was detected; else from what was detected, else
    from its default. Every check, and every refusal, comes before the first write."""
    _refuse_taken_name(name, home)
    root = _checkout_root(run, path, home)
    say(f"path: {root}")
    for field in FIELDS:
        if field.key in given and (problem := field.problem(given[field.key])):
            raise RefusalError(f"project add: {field.key} {problem}", f"fix {field.flag}")
    settled = _settle(run, root, given, ask, say)
    values = {"path": home_path(root, Path.home())} | {k: v.text for k, v in settled.items()}
    page = home.registry / f"{name}.md"
    text = page_text(name, values)
    parse_page_text(name, page, text)
    readme = home.registry / "README.md"
    readme_now = readme.read_text(encoding="utf-8") if readme.is_file() else None
    readme_new = (
        with_page_listed(readme_now, name)
        if readme_now is not None
        else starter_readme(sorted([*(p.name for p in all_projects(home.registry)), name]))
    )
    settings_now, settings_new = _settings_change(home, root)

    relative = page.relative_to(home.root).as_posix()
    readme_relative = readme.relative_to(home.root).as_posix()
    kept = f"{SETTINGS} already lists {root}, or it is the home's own root"
    if dry_run:
        say(f"would write {relative}:\n{text}")
        readme_diff = unified_diff(readme_relative, readme_now, readme_new)
        say(f"would change {readme_relative}:\n{readme_diff}")
        if settings_new is not None:
            say(f"would change {SETTINGS}:\n{unified_diff(SETTINGS, settings_now, settings_new)}")
        else:
            say(kept)
        say("dry run: nothing written")
        return
    page.write_text(text, encoding="utf-8")
    say(f"wrote {relative}")
    readme.write_text(readme_new, encoding="utf-8")
    say(f"listed {name} in {readme_relative}")
    if settings_new is not None:
        settings = home.root / SETTINGS
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(settings_new, encoding="utf-8")
        say(f"added {root} to permissions.{DIRECTORIES} in {SETTINGS}")
    else:
        say(kept)
    say(f"next: run `kaizen project labels {name}` to create the workflow labels its repo lacks")


def _refuse_taken_name(name: str, home: Home) -> None:
    """Refuses a *name* that can't name a page, or whose page exists."""
    if not _NAME.fullmatch(name) or name == "README":
        raise RefusalError(
            f"project add: {name!r} can't name a project page",
            "use letters, digits, '.', '_' and '-', and not README",
        )
    if (home.registry / f"{name}.md").exists():
        raise RefusalError(
            f"project add: project {name} already has a page, {home.registry / name}.md",
            "pick another name, or edit that page",
        )


def _checkout_root(run: Runner, path: Path | None, home: Home) -> Path:
    """*path*, resolved (default: the root of the git checkout the command runs in), once it is
    a git checkout's root that no project registers; refuses otherwise."""
    if path is None:
        path = Path(
            run_or_refuse(
                ["git", "rev-parse", "--show-toplevel"],
                run,
                "project add: this command runs in no git checkout",
                "run it from the project's main checkout, or pass its path",
            ).strip()
        )
    path = path.expanduser().resolve()
    toplevel = run_or_refuse(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        run,
        f"project add: {path} is not a git checkout",
        "pass the root of the project's main checkout",
    ).strip()
    if Path(toplevel).resolve() != path:
        raise RefusalError(
            f"project add: {path} is inside the git checkout at {toplevel}",
            f"pass the checkout's root, {toplevel}",
        )
    for project in all_projects(home.registry):
        if project.path.resolve() == path:
            raise RefusalError(
                f"project add: {path} is already registered, as {project.name}",
                f"use project {project.name}, or edit {project.page}",
            )
    return path


def _settle(
    run: Runner, root: Path, given: Mapping[str, str], ask: Ask | None, say: Say
) -> dict[str, Value]:
    """Each field's value, in ``FIELDS`` order, saying where each came from; optional fields
    left at their default are left out. Refuses, without a terminal, naming every required field
    with no value."""
    settled: dict[str, Value] = {}
    missing: list[Field] = []
    for field in FIELDS:
        if field.key in given:
            value: Value | None = Value(given[field.key], "given")
        else:
            detected = field.detect(run, root, settled) if field.detect else None
            value = _ask(field, root, detected, ask, say) if ask else detected
        if value is None and field.required:
            missing.append(field)
        elif value is None and field.default is not None:
            say(f"{field.key}: {field.default(root) or 'none'} (the default, left off the page)")
        elif value is not None:
            say(f"{field.key}: {value.text} ({value.shown()})")
            settled[field.key] = value
    if missing:
        listed = "".join(f"\n  {field.key}: {_SUMMARY[field.key]}" for field in missing)
        raise RefusalError(
            f"project add: {len(missing)} required key(s) have no value, and stdin is not a"
            f" terminal to ask:{listed}",
            "pass " + ", ".join(field.flag for field in missing),
        )
    return settled


def _ask(field: Field, root: Path, detected: Value | None, ask: Ask, say: Say) -> Value | None:
    """*field*'s value from a terminal: its explanation, then a prompt offering what was
    detected or its default, asked again until the answer is valid. ``None`` when an optional
    field keeps its default."""
    say(f"{field.key}: {_SUMMARY[field.key]}")
    if field.detect is not None and detected is None:
        say("  nothing detected")
    if detected is not None:
        offer = f" [{detected.text}] ({detected.source}; Enter accepts)"
    elif field.default is not None:
        default = field.default(root)
        offer = f" [{default}] (the default; Enter accepts)" if default else " (Enter for none)"
    else:
        offer = ""
    while True:
        try:
            answer = ask(f"{field.key} ({field.options}){offer}: ").strip()
        except EOFError:
            raise RefusalError(
                f"project add: no answer for {field.key}: the input ended",
                f"answer each prompt, or pass {field.flag}",
            ) from None
        if not answer:
            if detected is not None:
                return detected
            if field.default is not None:
                return None
            say("  it needs an answer; try again")
            continue
        if problem := field.problem(answer):
            say(f"  {problem}; try again")
            continue
        return Value(answer, "entered")


def _settings_change(home: Home, root: Path) -> tuple[str | None, str | None]:
    """The settings file's text now, and with *root* added to its additional directories; the
    second is ``None`` when it lists *root* already or *root* is the home's own. Refuses settings
    that can't take the entry."""
    settings = home.root / SETTINGS
    now = settings.read_text(encoding="utf-8") if settings.is_file() else None
    if root == home.root.resolve():
        return now, None
    try:
        data = read_settings(home.root)
        if not add_directory(data, root, Path.home()):
            return now, None
    except SettingsError as exc:
        raise RefusalError(
            f"project add: {exc}",
            f"fix {SETTINGS} so it holds a JSON object whose permissions.{DIRECTORIES} is a list",
        ) from exc
    return now, settings_text(data)


def terminal() -> Ask | None:
    """``input`` when stdin is a terminal to prompt on; ``None`` otherwise."""
    try:
        return input if sys.stdin.isatty() else None
    except (AttributeError, ValueError, OSError):
        return None


_HELP_WIDTH = 79
_HERE = "the current directory"
_FIELDS_BY_KEY = {field.key: field for field in FIELDS}


def _keys_help() -> str:
    """The help's list of the keys: each one's status, how the command takes it, and its full
    explanation."""
    entries = []
    for key in KEYS:
        given = (
            f"PATH (default: {_HERE})"
            if key.name == "path"
            else _flag_help(_FIELDS_BY_KEY[key.name])
        )
        explanation = wrap(f"{key.summary} {key.detail}", _HELP_WIDTH, "    ", "    ")
        entries.append(f"  {key.name} ({key.status})\n    {given}\n{explanation}")
    return "The keys a page sets, in page order:\n\n" + "\n\n".join(entries)


def _flag_help(field: Field) -> str:
    """How *field* is given on the command line, and what the page means when it is left out."""
    given = field.flag if field.boolean else f"{field.flag} {field.options}"
    if field.default is not None:
        given += f"; left out: {field.default(Path('<path>')) or 'none'}"
    return given


def add_parser(subparsers: Subparsers) -> None:
    required = ", ".join(field.key for field in FIELDS if field.required)
    parser = subparsers.add_parser(
        "add",
        help="register a project with the home: its page, README link and settings entry",
        description=(
            "Register the git checkout at PATH (default: the current directory) as the project "
            "NAME. It writes the registry page NAME.md, links it in the registry README's list "
            f"of pages, and adds PATH to permissions.{DIRECTORIES} in the home's {SETTINGS} "
            "when missing, keeping every other key and entry (the file is rewritten as JSON "
            "indented by two spaces). The entry is spelled from ~ when every entry there is, "
            "and absolute otherwise; the page's path is from ~ under your user directory.\n\n"
            "Each key has a flag. A key no flag gives is detected where it can be, and the "
            "detected value is printed with where it came from: github from the origin remote, "
            "public from `gh repo view`, check from scripts/check.sh, code_paths from the "
            "top-level tracked directories. When stdin is a terminal, it prompts for every key "
            "no flag gives, offering the detected value or default; Enter accepts it. Without "
            "a terminal it never prompts, and refuses, listing each required key "
            f"({required}) with neither a flag nor a detected value. "
            "The keys are explained after the options.\n\n"
            "It refuses, before writing anything: a name that already has a page, a path that "
            "is not a git checkout's root or that a page already registers, a github that is "
            "not owner/repo, any value the registry would refuse, and settings it can't merge "
            "into. It creates no labels: run `kaizen project labels NAME` next."
        ),
        epilog=_keys_help(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("name", help="the project's name: its page is NAME.md in the registry")
    parser.add_argument(
        "path", nargs="?", type=Path, help=f"the project's main checkout (default: {_HERE})"
    )
    for field in FIELDS:
        if not field.boolean:
            parser.add_argument(field.flag, help=_SUMMARY[field.key])
    visibility = parser.add_mutually_exclusive_group()
    visibility.add_argument(
        "--public", dest="public", action="store_const", const="true", help="the repo is public"
    )
    visibility.add_argument(
        "--private", dest="public", action="store_const", const="false", help="it is private"
    )
    parser.add_argument(
        "--auto-merge-comment-only",
        action=argparse.BooleanOptionalAction,
        help=_SUMMARY["auto_merge_comment_only"],
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the page, the README change and the settings change; write nothing",
    )
    parser.set_defaults(command=HomeCommand(_command))


def _given(args: argparse.Namespace) -> dict[str, str]:
    given = {field.key: getattr(args, field.key) for field in FIELDS}
    if args.auto_merge_comment_only is not None:
        given["auto_merge_comment_only"] = str(args.auto_merge_comment_only).lower()
    return {key: value for key, value in given.items() if value is not None}


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    add_project(run, home, args.name, args.path, _given(args), ask=terminal(), dry_run=args.dry_run)
