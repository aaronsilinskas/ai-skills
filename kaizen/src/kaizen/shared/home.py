"""Home discovery: which **home** ``kaizen`` serves, read from that home's own facts; and the files
``kaizen home init`` writes to make a new home.

A home declares itself with ``kaizen.toml`` at its root::

    registry = "projects"            # the registry folder, relative to the home root
    synced_version = "0.1.0"         # the release that last synced it; kaizen writes this line
    pr_footer = "…"                  # optional: the last line of each PR kaizen opens; "" for none
    auto_merge_comment_only = false  # optional, default true: the comment-only check's switch
    [leak]
    own = ["owner/home-repo", "/path/to/home"]   # kept out of this home's public projects
    allow = ["/opt/tool", "owner/archived"]      # optional: outside paths and repos it allows
    [[workflow_labels]]          # optional: one table per label, replacing the default set
    name = "needs-triage"
    color = "fbca04"
    description = "Maintainer needs to evaluate this issue"

and sets ``KAIZEN_HOME`` to its root in its ``.claude/settings.json`` ``env``, so ``kaizen`` run
from a registered project's root outside the home's tree still finds it. This module is the only
place that knows the marker's name, its format and ``KAIZEN_HOME``.
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
from kaizen.shared.registry import GITHUB_REPO
from kaizen.shared.version import Version

MARKER = "kaizen.toml"
ENV_VAR = "KAIZEN_HOME"
REGISTRY = "projects"
"""The registry folder a fresh marker names."""
PR_FOOTER = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
"""The PR footer of a home whose marker sets none."""
SETTINGS = ".claude/settings.json"
"""The Claude Code settings file, relative to the home root, whose ``env`` sets ``KAIZEN_HOME``."""

_COLOR = re.compile(r"[0-9a-fA-F]{6}")
_LABEL_FIELDS = tuple(field.name for field in fields(Label))
_COMMENT_WIDTH = 98
"""The width of a comment line's text in a fresh marker: 100 less its ``# ``."""
_MALFORMED_ALLOW = (
    "is malformed: 'leak.allow' must be a list of local paths (~/… or /…) and owner/repo"
)


class SettingsError(ValueError):
    """The settings file can't take ``KAIZEN_HOME``: a problem with the file, said without naming
    the command that asked or the fix, which are the caller's."""

    def __init__(self, problem: str, value: str | None = None) -> None:
        super().__init__(f"{SETTINGS} {problem}")
        self.value = value
        """The other value ``KAIZEN_HOME`` is already set to, when that is the problem. Never in
        the message: it may be another home's root."""


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
    synced_version: Version | None = None
    """The release that last synced the home's synced files; ``None`` when the marker
    records none."""


def find_home(
    start: Path, env: Mapping[str, str], warn: Callable[[str], None] = lambda _: None
) -> Home:
    """The home ``KAIZEN_HOME`` in *env* names, or the nearest one upward from *start*.

    Inside a linked git worktree of the ``KAIZEN_HOME`` home, such as one of its ticket
    worktrees, the worktree is the home, so a command run there reads and writes the worktree's
    files rather than the main checkout's; *warn* gets one line naming both roots.

    Refuses when ``KAIZEN_HOME`` names a root with no marker, when neither finds a home, when
    they find different homes, or when the marker is malformed.
    """
    value = env.get(ENV_VAR)
    named = _expand(value, Path.home()) if value else None
    found = _search_upward(start.resolve())
    if named:
        if not (named / MARKER).is_file():
            raise RefusalError(
                f"home: {ENV_VAR} is {value}, which has no {MARKER}",
                f"set {ENV_VAR} to the root of the home that holds {MARKER}",
            )
        if found and found != named:
            if not _is_worktree_of(found, named):
                # Only the variable's root is named: the other home's path must not reach this
                # one's output.
                raise RefusalError(
                    f"home: {ENV_VAR} names {named}, but kaizen runs inside the tree"
                    f" of a different {MARKER}",
                    f"run kaizen from inside {named} or one of its registered projects",
                )
            warn(f"home: using the worktree {found}; {ENV_VAR} names {named}")
            return _read_marker(found)
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
    """The root ``KAIZEN_HOME`` in *env* names, with ``~`` taken as *user_home*, whether or not a
    home is there; ``None`` when it is unset."""
    value = env.get(ENV_VAR)
    return _expand(value, user_home) if value else None


def same_root(value: str, root: Path, user_home: Path) -> bool:
    """Whether the variable value *value* names *root*, with ``~`` taken as *user_home*."""
    return _expand(value, user_home) == root.resolve()


def home_path(path: Path, user_home: Path) -> str:
    """*path* as a home writes it into its own files: ``~/…`` under *user_home*, so it holds no
    user name, and absolute otherwise. ``find_home`` and the registry expand the ``~``."""
    if path == user_home:
        return "~"
    if path.is_relative_to(user_home):
        return "~/" + path.relative_to(user_home).as_posix()
    return str(path)


def fresh_marker(github: str, path: str, synced_version: Version) -> str:
    """The text of a new home's marker: its registry folder, its *synced_version*, each home
    setting commented out at its default, and a leak table whose own patterns are the home's
    GitHub repo *github* (``owner/repo``) and its root *path*, and that allows nothing yet.
    JSON's string escapes are TOML's, so ``json.dumps`` quotes each value."""
    return f"""\
# This file makes the repo it sits in a home for kaizen: kaizen serves the home whose root
# holds it.

# The project registry: a folder, relative to this file, with one page per project the home's
# sessions work on, the home itself included.
registry = "{REGISTRY}"

# The kaizen release that last synced this home's synced files. kaizen home sync writes it, and
# every kaizen command compares it with the installed release, so don't edit it by hand.
{_synced_version_line(synced_version)}
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
# owner/repo names of archived repos. Default empty; add an entry here when the leak check finds
# one.
allow = []
{_labels_comment()}"""


def fresh_home(root: Path, github: str, path: str, synced_version: Version) -> Home:
    """The ``Home`` that ``find_home`` reads at *root* once
    ``fresh_marker(github, path, synced_version)`` is written there."""
    return Home(
        root=root, registry=root / REGISTRY, leak_own=(github, path), synced_version=synced_version
    )


_TABLE = re.compile(r"\[\[?[\w\s\"'.-]+\]\]?[ \t]*(#.*)?\s*")
"""A table header line, ``[name]`` or ``[[name]]``, at the start of its line, where an indented
row of a multi-line array is not."""
_SYNCED_VERSION = re.compile(r"\s*synced_version\s*=")


def _synced_version_line(version: Version) -> str:
    return f'synced_version = "{version}"\n'


def with_synced_version(marker: str, version: Version) -> str:
    """The *marker* text recording *version* as the synced version: its top-level
    ``synced_version`` line replaced, or, when it has none, one inserted above the first table and
    the comment lines that head it. Every other byte is kept, which a TOML writer, had the
    standard library one, would not promise."""
    lines = marker.splitlines(keepends=True)
    first_table = next((i for i, line in enumerate(lines) if _TABLE.fullmatch(line)), len(lines))
    line = _synced_version_line(version)
    for i in range(first_table):
        if _SYNCED_VERSION.match(lines[i]):
            ending = lines[i][len(lines[i].rstrip("\r\n")) :]
            lines[i] = line.removesuffix("\n") + ending
            return "".join(lines)
    if first_table == len(lines):
        separator = "" if not marker or marker.endswith("\n") else "\n"
        return f"{marker}{separator}{line}"
    at = first_table
    while at > 0 and lines[at - 1].lstrip().startswith("#"):
        at -= 1
    return "".join([*lines[:at], line, "\n", *lines[at:]])


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


def read_settings(root: Path) -> dict[str, object]:
    """*root*'s settings file as a JSON object, empty when the file is absent. Raises
    ``SettingsError`` on a file that is not a JSON object."""
    settings = root / SETTINGS
    if not settings.exists():
        return {}
    try:
        data = json.loads(settings.read_bytes())
    except (ValueError, OSError) as exc:  # UnicodeDecodeError is a ValueError
        raise SettingsError("is not valid JSON") from exc
    if not isinstance(data, dict):
        raise SettingsError("does not hold a JSON object")
    return data


def settings_text(data: dict[str, object]) -> str:
    """The settings file's text for *data*, as every command that writes it writes it."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def add_permission_entries(data: dict[str, object], key: str, entries: list[str]) -> bool:
    """Adds each of *entries* missing from the list ``permissions.<key>`` of the settings *data*,
    after the entries already there, and returns whether any was missing. Every other key and
    entry keeps its order. Raises ``SettingsError`` when ``permissions`` is not an object or
    that list is not a list."""
    listed = _permission_list(data, key)
    missing = [entry for entry in entries if entry not in listed]
    listed.extend(missing)
    return bool(missing)


DIRECTORIES = "additionalDirectories"
"""The settings' ``permissions`` list of the directories outside the home a session may use."""


def add_directory(data: dict[str, object], path: Path, user_home: Path) -> bool:
    """Adds *path* to ``permissions.additionalDirectories`` in the settings *data*, unless an
    entry already names it, and returns whether it did. The entry is written from ``~`` when
    every entry there is, and absolute otherwise. Raises ``SettingsError`` as
    ``add_permission_entries`` does."""
    listed = _permission_list(data, DIRECTORIES)
    spelled = [entry for entry in listed if isinstance(entry, str)]
    if any(same_root(entry, path, user_home) for entry in spelled):
        return False
    from_tilde = bool(listed) and len(spelled) == len(listed)
    from_tilde = from_tilde and all(entry.startswith("~") for entry in spelled)
    entry = home_path(path, user_home) if from_tilde else str(path)
    return add_permission_entries(data, DIRECTORIES, [entry])


def _permission_list(data: dict[str, object], key: str) -> list[object]:
    """The list ``permissions.<key>`` of the settings *data*, made empty when absent."""
    permissions = data.setdefault("permissions", {})
    if not isinstance(permissions, dict):
        raise SettingsError("has permissions that are not a JSON object")
    listed = permissions.setdefault(key, [])
    if not isinstance(listed, list):
        raise SettingsError(f"has a permissions.{key} that is not a JSON list")
    return listed


def name_home(data: dict[str, object], path: str) -> bool:
    """Sets ``env.KAIZEN_HOME`` in the settings *data* to *path*, every other key kept in its
    order, and returns whether that changed *data*: not when it already sets exactly *path*, so a
    rerun leaves the file alone. Raises ``SettingsError`` when ``env`` is not an object, or sets
    ``KAIZEN_HOME`` to anything else."""
    env = data.setdefault("env", {})
    if not isinstance(env, dict):
        raise SettingsError("has an env that is not a JSON object")
    if ENV_VAR in env and env[ENV_VAR] != path:
        raise SettingsError(
            f"already sets {ENV_VAR} to a value other than {path}", str(env[ENV_VAR])
        )
    if ENV_VAR in env:
        return False
    env[ENV_VAR] = path
    return True


def _expand(value: str, user_home: Path) -> Path:
    if value == "~" or value.startswith("~/"):
        value = str(user_home) + value[1:]
    return Path(value).expanduser().resolve()


def _search_upward(start: Path) -> Path | None:
    return next((d for d in (start, *start.parents) if (d / MARKER).is_file()), None)


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
    if not all(GITHUB_REPO.fullmatch(repo) for repo in repos):
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
    synced_version = _synced_version(data, refuse)
    return Home(
        root=root,
        registry=registry,
        leak_own=tuple(own),
        leak_allow_paths=paths,
        leak_allow_repos=repos,
        pr_footer=pr_footer,
        workflow_labels=workflow_labels,
        auto_merge_comment_only=auto_merge_comment_only,
        synced_version=synced_version,
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


def _synced_version(
    data: Mapping[str, object], refuse: Callable[[str], RefusalError]
) -> Version | None:
    value = data.get("synced_version")
    if value is None:
        return None
    version = Version.parse(value) if isinstance(value, str) else None
    if version is None:
        raise refuse("is malformed: 'synced_version' must be a version X.Y.Z, such as \"0.1.0\"")
    return version


def _pr_footer(data: Mapping[str, object], refuse: Callable[[str], RefusalError]) -> str:
    footer = data.get("pr_footer", PR_FOOTER)
    if not isinstance(footer, str):
        raise refuse("is malformed: 'pr_footer' must be a string")
    if footer and not footer.strip():
        raise refuse("is malformed: 'pr_footer' is only whitespace; set it to \"\" for no footer")
    return footer.strip()
