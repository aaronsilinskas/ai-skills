"""Home discovery: which **home** ``kaizen`` serves, read from that home's own facts; and the files
``kaizen home init`` writes to make a new home.

A home declares itself with ``mw.toml`` at its root::

    registry = "projects"            # the registry folder, relative to the home root
    pr_footer = "…"                  # optional: the last line of each PR kaizen opens; "" for none
    auto_merge_comment_only = false  # optional, default true: the comment-only check's switch
    [leak]
    own = ["owner/home-repo", "/path/to/home"]   # kept out of this home's public projects
    allow = ["~/.claude", "owner/archived"]      # optional: outside paths and repos it allows
    [[workflow_labels]]          # optional: one table per label, replacing the default set
    name = "needs-triage"
    color = "fbca04"
    description = "Maintainer needs to evaluate this issue"

and sets ``MW_HOME`` to its root in its ``.claude/settings.json`` ``env``, so ``kaizen`` run from a
registered project's root outside the home's tree still finds it. This module is the only place
that knows the marker's name, its format and ``MW_HOME``.
"""

import json
import re
import textwrap
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from pathlib import Path

from kaizen.shared.common import RefusalError
from kaizen.shared.labels import DEFAULT_WORKFLOW_LABELS, Label

MARKER = "mw.toml"
ENV_VAR = "MW_HOME"
REGISTRY = "projects"
"""The registry folder a fresh marker names."""
PR_FOOTER = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
"""The PR footer of a home whose marker sets none."""
SETTINGS = ".claude/settings.json"
"""The Claude Code settings file, relative to the home root, whose ``env`` sets ``MW_HOME``."""

_REPO = re.compile(r"[\w.-]+/[\w.-]+")
_COLOR = re.compile(r"[0-9a-fA-F]{6}")
_LABEL_FIELDS = tuple(field.name for field in fields(Label))
_COMMENT_WIDTH = 98
"""The width of a comment line's text in a fresh marker: 100 less its ``# ``."""
_MALFORMED_ALLOW = (
    "is malformed: 'leak.allow' must be a list of local paths (~/… or /…) and owner/repo"
)


class SettingsError(ValueError):
    """The settings file can't take ``MW_HOME``: a problem with the file, said without naming the
    command that asked or the fix, which are the caller's."""

    def __init__(self, problem: str, mw_home: str | None = None) -> None:
        super().__init__(f"{SETTINGS} {problem}")
        self.mw_home = mw_home
        """The ``MW_HOME`` value already there, when that is the problem. Never in the message: it
        may be another home's root."""


@dataclass(frozen=True)
class Home:
    root: Path
    registry: Path
    """The registry folder: one page per project."""
    leak_own: tuple[str, ...]
    """Literal strings the leak check keeps out of this home's public projects."""
    leak_allow_paths: tuple[str, ...] = ()
    """Local paths (``~/…`` or absolute) outside the home's registry that the leak check lets its
    projects mention, such as a tool's settings folder."""
    leak_allow_repos: tuple[str, ...] = ()
    """``owner/repo`` names outside the home's registry that the leak check lets its projects
    mention."""
    pr_footer: str = PR_FOOTER
    """The line every PR ``kaizen`` opens in this home ends with; empty for no footer line."""
    workflow_labels: tuple[Label, ...] = DEFAULT_WORKFLOW_LABELS
    """The labels ``kaizen project labels`` creates in each project's repo: the marker's whole set
    when it sets one, the default set otherwise."""
    auto_merge_comment_only: bool = True
    """Whether ``kaizen ticket ship`` may auto-merge a PR on the comment-only check at all; a
    project still opts in on its registry page."""


def find_home(start: Path, env: Mapping[str, str]) -> Home:
    """The home ``MW_HOME`` in *env* names, or the nearest one upward from *start*.

    Refuses when neither finds a home, when they find different homes, or when the marker is
    malformed. A linked git worktree of the ``MW_HOME`` home, such as a ticket worktree inside its
    tree, counts as that home.
    """
    found = _search_upward(start.resolve())
    named = _named_by_env(env)
    if named and found and found != named and not _is_worktree_of(found, named):
        # Only MW_HOME's root is named: the other home's path must not reach this one's output.
        raise RefusalError(
            f"home: {ENV_VAR} names {named}, but kaizen runs inside the tree of a "
            f"different {MARKER}",
            f"run kaizen from inside {named} or one of its registered projects",
        )
    root = named or found
    if root is None:
        raise RefusalError(
            f"home: no home found: {ENV_VAR} is unset and no {MARKER} is in {start} or above it",
            f"run kaizen inside a home, or set {ENV_VAR} to the root of the home that "
            f"holds {MARKER}",
        )
    return _read_marker(root)


def marker_at_or_above(start: Path) -> bool:
    """Whether a marker is at *start* or in a directory above it. Only a yes or no, so a caller
    can refuse without naming another home's root."""
    return _search_upward(start.resolve()) is not None


def root_named_by_env(env: Mapping[str, str], user_home: Path) -> Path | None:
    """The root ``MW_HOME`` in *env* names, with ``~`` taken as *user_home*, whether or not a home
    is there; ``None`` when it is unset."""
    value = env.get(ENV_VAR)
    if not value:
        return None
    if value == "~" or value.startswith("~/"):
        value = str(user_home) + value[1:]
    return Path(value).expanduser().resolve()


def home_path(path: Path, user_home: Path) -> str:
    """*path* as a home writes it into its own files: ``~/…`` under *user_home*, so it holds no
    user name, and absolute otherwise. ``find_home`` and the registry expand the ``~``."""
    if path == user_home:
        return "~"
    if path.is_relative_to(user_home):
        return "~/" + path.relative_to(user_home).as_posix()
    return str(path)


def fresh_marker(github: str, path: str) -> str:
    """The text of a new home's marker: its registry folder, each home setting commented out at
    its default, and a leak table whose own patterns are the home's GitHub repo *github*
    (``owner/repo``) and its root *path*, and that allows nothing yet. JSON's string escapes are
    TOML's, so ``json.dumps`` quotes each value."""
    return f"""\
# This file makes the repo it sits in a home for kaizen: kaizen serves the home whose root
# holds it.

# The project registry: a folder, relative to this file, with one page per project the home's
# sessions work on, the home itself included.
registry = "{REGISTRY}"

# The line every PR kaizen opens in this home ends with, after a blank line. Set it to "" to open
# PRs with no footer line.
# pr_footer = {json.dumps(PR_FOOTER, ensure_ascii=False)}

# Whether kaizen ticket ship may auto-merge a comment-only change in this home's projects; a
# project also opts in on its registry page. Default true; set false to turn the check off
# home-wide.
# auto_merge_comment_only = true

[leak]
# Text the leak check keeps out of this home's public projects: the home's own GitHub repo and
# its local path. The path may be widened to a parent folder that holds only this home's work.
own = [{json.dumps(github)}, {json.dumps(path)}]
# Text the leak check lets this home's projects mention although no registry page covers it:
# local paths outside the home, written from ~ or /, such as a tool's settings folder, and
# owner/repo names of archived repos. Add an entry here when the leak check finds one.
allow = []
{_labels_comment()}"""


def fresh_home(root: Path, github: str, path: str) -> Home:
    """The ``Home`` that ``find_home`` reads at *root* once ``fresh_marker(github, path)`` is
    written there."""
    return Home(root=root, registry=root / REGISTRY, leak_own=(github, path))


def _labels_comment() -> str:
    """The fresh marker's commented-out workflow labels setting: what it is, the default set's
    names, and one default label as the example of a table."""
    names = textwrap.wrap(
        ", ".join(label.name for label in DEFAULT_WORKFLOW_LABELS) + ".",
        width=_COMMENT_WIDTH,
        initial_indent="# ",
        subsequent_indent="# ",
    )
    example = DEFAULT_WORKFLOW_LABELS[0]
    return "\n".join(
        [
            "",
            "# The workflow labels kaizen project labels creates in each project's GitHub",
            "# repo, one table per label. A set given here replaces the whole default set",
            "# rather than adding to it. Unset, the home gets the default set:",
            *names,
            "# Its first label, written as a table:",
            "# [[workflow_labels]]",
            f"# name = {json.dumps(example.name)}",
            f"# color = {json.dumps(example.color)}",
            f"# description = {json.dumps(example.description)}",
            "",
        ]
    )


def settings_naming_home(root: Path, path: str) -> str | None:
    """The text of *root*'s settings file with ``env.MW_HOME`` set to *path*, every other key kept
    in its order; ``None`` when it already sets exactly *path*, so a rerun leaves it alone. An
    absent file gives a new one. Raises ``SettingsError`` on a file that is not a JSON object,
    whose ``env`` is not an object, or that sets a different ``MW_HOME``."""
    settings = root / SETTINGS
    data: dict[str, object] = {}
    if settings.exists():
        try:
            data = json.loads(settings.read_bytes())
        except (ValueError, OSError) as exc:  # UnicodeDecodeError is a ValueError
            raise SettingsError("is not valid JSON") from exc
        if not isinstance(data, dict):
            raise SettingsError("does not hold a JSON object")
    env = data.setdefault("env", {})
    if not isinstance(env, dict):
        raise SettingsError("has an env that is not a JSON object")
    if ENV_VAR in env:
        if env[ENV_VAR] == path:
            return None
        raise SettingsError(
            f"already sets {ENV_VAR} to a value other than {path}", mw_home=str(env[ENV_VAR])
        )
    env[ENV_VAR] = path
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _search_upward(start: Path) -> Path | None:
    return next((d for d in (start, *start.parents) if (d / MARKER).is_file()), None)


def _named_by_env(env: Mapping[str, str]) -> Path | None:
    root = root_named_by_env(env, Path.home())
    if root is not None and not (root / MARKER).is_file():
        raise RefusalError(
            f"home: {ENV_VAR} is {env[ENV_VAR]}, which has no {MARKER}",
            f"set {ENV_VAR} to the root of the home that holds {MARKER}",
        )
    return root


def _is_worktree_of(path: Path, main: Path) -> bool:
    """Whether *path* is a linked git worktree of the repo whose main checkout is *main*."""
    dot_git = path / ".git"
    if not dot_git.is_file():
        return False
    prefix = "gitdir:"
    text = dot_git.read_text().strip()
    if not text.startswith(prefix):
        return False
    git_dir = Path(text.removeprefix(prefix).strip())
    return git_dir.resolve().is_relative_to((main / ".git" / "worktrees").resolve())


def _read_marker(root: Path) -> Home:
    marker = root / MARKER

    def refuse(problem: str) -> RefusalError:
        return RefusalError(f"home: {marker} {problem}", f"fix {marker}")

    try:
        data = tomllib.loads(marker.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise refuse(f"is not valid TOML: {exc}") from exc
    if "registry" not in data:
        raise refuse("is missing 'registry'")
    if not isinstance(data["registry"], str) or not data["registry"]:
        raise refuse("is malformed: 'registry' must be a string")
    leak = data.get("leak")
    if leak is None or (isinstance(leak, dict) and "own" not in leak):
        raise refuse("is missing 'leak.own'")
    if not isinstance(leak, dict):
        raise refuse("is malformed: 'leak' must be a table")
    own = leak["own"]
    if not isinstance(own, list) or not all(isinstance(p, str) and p for p in own):
        raise refuse("is malformed: 'leak.own' must be a list of non-empty strings")
    allow = leak.get("allow", [])
    if not isinstance(allow, list) or not all(isinstance(a, str) for a in allow):
        raise refuse(_MALFORMED_ALLOW)
    paths = tuple(a for a in allow if a.startswith(("~/", "/")))
    repos = tuple(a for a in allow if a not in paths)
    if not all(_REPO.fullmatch(repo) for repo in repos):
        raise refuse(_MALFORMED_ALLOW)
    if broad := [p for p in paths if root.is_relative_to(Path(p).expanduser().resolve())]:
        raise refuse(
            f"is malformed: 'leak.allow' entry {broad[0]} holds the home itself, so it would "
            "allow every path"
        )
    registry = root / data["registry"]
    if not registry.is_dir():
        raise refuse(f"names a registry folder that does not exist: {registry}")
    pr_footer = _pr_footer(data, refuse)
    workflow_labels = _workflow_labels(data, refuse)
    auto_merge_comment_only = _auto_merge_comment_only(data, refuse)
    return Home(
        root=root,
        registry=registry,
        leak_own=tuple(own),
        leak_allow_paths=paths,
        leak_allow_repos=repos,
        pr_footer=pr_footer,
        workflow_labels=workflow_labels,
        auto_merge_comment_only=auto_merge_comment_only,
    )


def _workflow_labels(
    data: Mapping[str, object], refuse: Callable[[str], RefusalError]
) -> tuple[Label, ...]:
    """The marker's ``[[workflow_labels]]`` set, colours lowercased, or the default set when it
    has none."""
    tables = data.get("workflow_labels")
    if tables is None:
        return DEFAULT_WORKFLOW_LABELS
    if not isinstance(tables, list) or not tables or not all(isinstance(t, dict) for t in tables):
        raise refuse(
            "is malformed: 'workflow_labels' must be one or more [[workflow_labels]] tables"
        )
    labels: list[Label] = []
    for number, table in enumerate(tables, start=1):
        entry = f"'workflow_labels' entry {number}"
        for field in _LABEL_FIELDS:
            if not isinstance(table.get(field), str):
                raise refuse(f"is malformed: {entry} needs a string '{field}'")
        if extra := sorted(set(table) - set(_LABEL_FIELDS)):
            raise refuse(f"is malformed: {entry} has an unknown key '{extra[0]}'")
        name, color, description = (table[field] for field in _LABEL_FIELDS)
        if not name:
            raise refuse(f"is malformed: {entry} has an empty 'name'")
        if not _COLOR.fullmatch(color):
            raise refuse(
                f"is malformed: {entry}'s 'color' {color!r} must be six hex digits, without '#'"
            )
        if any(label.name == name for label in labels):
            raise refuse(f"is malformed: 'workflow_labels' names {name!r} twice")
        labels.append(Label(name, color.lower(), description))
    return tuple(labels)


def _auto_merge_comment_only(
    data: Mapping[str, object], refuse: Callable[[str], RefusalError]
) -> bool:
    value = data.get("auto_merge_comment_only", True)
    if not isinstance(value, bool):
        raise refuse("is malformed: 'auto_merge_comment_only' must be true or false")
    return value


def _pr_footer(data: Mapping[str, object], refuse: Callable[[str], RefusalError]) -> str:
    footer = data.get("pr_footer", PR_FOOTER)
    if not isinstance(footer, str):
        raise refuse("is malformed: 'pr_footer' must be a string")
    if footer and not footer.strip():
        raise refuse("is malformed: 'pr_footer' is only whitespace; set it to \"\" for no footer")
    return footer.strip()
