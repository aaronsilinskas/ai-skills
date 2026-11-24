"""The **leak check**: run on a project's checkout before any push or PR publishes it.

It refuses committed text that points outside the current home (see
``docs/adr/0002-homes-never-reference-each-other.md``), and text a project denies. The first three
rules are allowlists built from the home's own facts: a search finds candidates, and whatever the
home doesn't cover is refused. The last is the project's own denylist.

- *own reference* (public projects only): one of the home's own leak patterns.
- *outside path*: a local absolute path, ``~/`` or the user's home directory followed by more,
  that is neither under nor an ancestor of the home root, a registered project's path or worktree
  root, or a path the home allows. An ancestor such as ``~/<dir>`` names nothing the home doesn't
  already hold.
- *unregistered repo*: ``<owner>/<repo>``, bare or in a github.com link, whose owner is one a
  registered project's ``github`` names but whose repo is neither registered nor allowed.
  Third-party owners are never flagged, and the boundary is per repo, since one owner holds repos
  in more than one home.
- *denied pattern*: a match for one of the project's own ``leak_deny`` patterns (see
  ``kaizen.shared.registry``), public or private. It searches only what is being published, the
  lines a commit or push adds and the text sent to GitHub, never text already in the tree.
"""

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from kaizen.shared.common import RefusalError, Runner
from kaizen.shared.home import MARKER, Home
from kaizen.shared.registry import all_projects

_FIX_BY_ALLOWING = f"add it to leak.allow in the home's {MARKER}"


class Rule(Enum):
    """A leak rule: its name in a refusal, and the fix the refusal gives."""

    OWN_REFERENCE = ("own reference", "remove it (name skills instead of linking the home's files)")
    OUTSIDE_PATH = (
        "outside path",
        f"register the project that holds it, {_FIX_BY_ALLOWING}, or remove the text",
    )
    UNREGISTERED_REPO = (
        "unregistered repo",
        f"register it in the home's registry, {_FIX_BY_ALLOWING}, or remove the text",
    )
    DENIED_PATTERN = ("denied pattern", "remove the text, or change the project's leak_deny")

    def __init__(self, label: str, fix: str) -> None:
        self.label = label
        self.fix = fix


# What may come just before a ``~/`` path: the start of a word in prose, markup, code or a
# setting, or a ``/`` or ``@`` it is glued to, as in a ``file://`` URL or an ``@`` alias. A
# ``~/`` after anything else, such as ``/~(.*?)~/g`` in a regex or minified code, names no path.
# The user's home directory is specific enough to be found after anything. What ends a path:
_TILDE_START = r"""\s'"`(\[{<=:,/@"""
_PATH_END = r"""\s'"`<>()\[\]{},;:*|\\"""


@dataclass(frozen=True)
class _Rules:
    """The rules a project runs, built from one home's facts."""

    own: tuple[str, ...]
    owners: tuple[str, ...]
    user_home: Path
    allowed_paths: tuple[Path, ...]
    allowed_repos: frozenset[str]

    @classmethod
    def for_home(cls, home: Home, public: bool, user_home: Path) -> "_Rules":
        projects = all_projects(home.registry)
        paths = [home.root, *(p.path for p in projects), *(p.worktree_root for p in projects)]
        return cls(
            own=home.leak_own if public else (),
            owners=tuple(sorted({p.github.split("/")[0].lower() for p in projects})),
            user_home=user_home,
            allowed_paths=tuple(
                _absolute(str(path), user_home) for path in [*paths, *home.leak_allow_paths]
            ),
            allowed_repos=frozenset(
                repo.lower() for repo in [*(p.github for p in projects), *home.leak_allow_repos]
            ),
        )

    @property
    def literals(self) -> list[str]:
        """The fixed strings every candidate line holds one of, matched case-insensitively."""
        return [*self.own, "~/", f"{self.user_home}/", *(f"{owner}/" for owner in self.owners)]

    def findings(self, text: str) -> list[tuple[Rule, str]]:
        """``(rule, match)`` for each reference in the line *text* the home doesn't cover."""
        found = [(Rule.OWN_REFERENCE, pattern) for pattern in self.own if pattern in text]
        home = re.escape(str(self.user_home))
        paths = re.compile(rf"(?:(?<![^{_TILDE_START}])~|{home})/[^{_PATH_END}]*")
        for path in map(_trim, paths.findall(text)):
            if not self._path_allowed(_absolute(path, self.user_home)):
                found.append((Rule.OUTSIDE_PATH, path))
        if self.owners:
            # A local path is judged by the path rule alone, never also as a repo.
            outside_paths = paths.sub(" ", text)
            owners = "|".join(map(re.escape, self.owners))
            for repo in re.findall(rf"(?<![\w.-])(?:{owners})/[\w.-]+", outside_paths, re.I):
                repo = _trim(repo).removesuffix(".git")
                if "/" in repo and repo.lower() not in self.allowed_repos:
                    found.append((Rule.UNREGISTERED_REPO, repo))
        return found

    def _path_allowed(self, path: Path) -> bool:
        return any(path.is_relative_to(a) or a.is_relative_to(path) for a in self.allowed_paths)


def leak_check(
    checkout: Path,
    home: Home,
    run: Runner,
    revision: str | None = None,
    *,
    public: bool,
    staged: bool = False,
    denied: tuple[re.Pattern[str], ...] = (),
    base: str | None = None,
    user_home: Path | None = None,
) -> None:
    """Refuses, listing each offending file, line, rule and fix, when *checkout*'s files point
    outside *home*. A *public* project also runs the own-reference rule.

    It searches the tracked files of *checkout*'s working tree; given *revision*, that commit's
    tree, for a push of a commit that is not checked out; or, when *staged*, the index, for a
    commit about to be made. *user_home* is what ``~`` means (default: the current user's home
    directory).

    The project's *denied* patterns are searched only on the lines being published: those the
    index adds to ``HEAD`` when *staged*, otherwise those the searched tree adds since its merge
    base with *base*, which *denied* needs.
    """
    if staged and revision:
        raise ValueError("leak_check: pass a revision or staged, not both")
    if denied and not staged and base is None:
        raise ValueError("leak_check: denied patterns need a base, or staged")
    rules = _Rules.for_home(home, public, user_home or Path.home())
    lines = _candidates(checkout, run, revision, staged, rules.literals)
    findings = _findings(rules, lines)
    if denied:
        source = ["--cached"] if staged else ["--merge-base", str(base), *filter(None, [revision])]
        findings += _findings_denied(denied, added_lines(checkout, run, source))
    _refuse(findings, "committed text", "fix each line as it says, then commit")


def leak_check_text(
    texts: Mapping[str, str],
    home: Home,
    *,
    public: bool,
    denied: tuple[re.Pattern[str], ...] = (),
    user_home: Path | None = None,
) -> None:
    """Refuses, listing each offending text, line, rule and fix, when text ``kaizen`` is about to
    send to GitHub points outside *home*: the same rules as ``leak_check``, run before any ``gh``
    call.

    *texts* maps what each text is (such as ``"PR body"``) to the text. A *public* project also
    runs the own-reference rule, and every line is searched for the project's *denied* patterns.
    """
    rules = _Rules.for_home(home, public, user_home or Path.home())
    lines = numbered_lines(texts, " line ")
    findings = _findings(rules, lines) + _findings_denied(denied, lines)
    _refuse(findings, "text for GitHub", "fix each line as it says, then rerun")


def numbered_lines(texts: Mapping[str, str], separator: str) -> list[tuple[str, str]]:
    """Every line of *texts*, which maps a label to its text, as ``(where, line)`` pairs the leak
    check reads: *where* is the label, *separator*, then the 1-based line number."""
    return [
        (f"{label}{separator}{number}", line)
        for label, text in texts.items()
        for number, line in enumerate(text.splitlines(), 1)
    ]


def leak_check_denied(
    lines: list[tuple[str, str]], denied: tuple[re.Pattern[str], ...], what: str
) -> None:
    """Refuses, listing each ``(where, text)`` line of *lines* that matches one of a project's
    *denied* patterns, for text about to be published that the other entry points can't judge
    alone, such as a working tree's uncommitted additions. *what* names that text."""
    _refuse(_findings_denied(denied, lines), what, "fix each line as it says, then rerun")


class LeakFoundError(RefusalError):
    """The leak check's refusal: text points outside the home. A caller that reports findings
    instead of failing catches it and reads ``findings``."""

    def __init__(self, what: str, findings: list[str], fix: str) -> None:
        super().__init__(
            f"leak check: {what} points outside this home:\n"
            + "\n".join(f"  {finding}" for finding in findings),
            fix,
        )
        self.findings = findings
        """One line per finding: where it is, its rule and match, and the rule's fix."""


def _findings(rules: _Rules, lines: list[tuple[str, str]]) -> list[str]:
    """One finding for each reference *rules* find in the ``(where, text)`` *lines*."""
    return [
        _finding(where, rule, match)
        for where, text in lines
        for rule, match in rules.findings(text)
    ]


def _findings_denied(
    denied: tuple[re.Pattern[str], ...], lines: list[tuple[str, str]]
) -> list[str]:
    """One finding for each match of a *denied* pattern in *lines*."""
    return [
        _finding(where, Rule.DENIED_PATTERN, match.group().strip())
        for where, text in lines
        for pattern in denied
        for match in pattern.finditer(text)
    ]


def _finding(where: str, rule: Rule, match: str) -> str:
    return f"{where}: {rule.label} {match} (fix: {rule.fix})"


def _refuse(findings: list[str], what: str, fix: str) -> None:
    if findings:
        raise LeakFoundError(what, findings, fix)


def _candidates(
    checkout: Path, run: Runner, revision: str | None, staged: bool, literals: list[str]
) -> list[tuple[str, str]]:
    """``(file:line, text)`` for each tracked line holding one of *literals*, matched
    case-insensitively, since GitHub owners are; the rules decide which lines are refused."""
    patterns = [arg for literal in literals for arg in ("-e", literal)]
    source = ["--cached"] if staged else []
    cmd = ["git", "-C", str(checkout), "grep", *source, "-n", "-I", "-F", "-i", *patterns]
    try:
        out = run(cmd + ([revision] if revision else []))
    except subprocess.CalledProcessError as exc:
        if exc.returncode != 1:  # git grep exits 1 when nothing matches
            raise
        return []
    lines = []
    for line in out.splitlines():
        if revision:
            line = line.removeprefix(f"{revision}:")
        file, number, text = line.split(":", 2)
        lines.append((f"{file}:{number}", text))
    return lines


_HUNK = re.compile(r"@@ -\S+ \+(\d+)")


def added_lines(
    checkout: Path, run: Runner, source: list[str], paths: tuple[str, ...] = ()
) -> list[tuple[str, str]]:
    """``(file:line, text)`` for each line ``git diff`` adds with *source* (its revision
    arguments), limited to *paths* when given, numbered as in the new file. Binary files add no
    lines."""
    # Fixed prefixes, rename detection and raw file text, whatever the user's git config; a
    # renamed file adds only the lines it changes.
    options = ["--no-color", "--no-ext-diff", "--no-textconv", "--src-prefix=a/", "--dst-prefix=b/"]
    git = ["git", "-C", str(checkout), "-c", "core.quotePath=false", "diff", *options, "-M", "-U0"]
    out = run([*git, *source, "--", *paths])
    lines: list[tuple[str, str]] = []
    file, number, in_hunk = "", 0, False
    # Split on newlines only: an added line may hold another character ``splitlines`` splits on.
    for line in out.split("\n"):
        if line.startswith("diff "):
            in_hunk = False
        elif not in_hunk and line.startswith("+++ "):
            # git ends the name with a tab when it holds a space.
            file = line[4:].rstrip("\t").strip('"').removeprefix("b/")
        elif hunk := _HUNK.match(line):
            number, in_hunk = int(hunk.group(1)), True
        elif in_hunk and line.startswith("+"):
            lines.append((f"{file}:{number}", line[1:]))
            number += 1
        elif in_hunk and line.startswith(" "):
            number += 1  # a context line, where diff.interHunkContext joins two hunks
    return lines


def _trim(match: str) -> str:
    """*match* without the full stop, slash or ellipsis (``...`` or ``…``) that ends it in prose."""
    return match.rstrip("./…")


def _absolute(path: str, user_home: Path) -> Path:
    if path == "~" or path.startswith("~/"):
        path = str(user_home) + path[1:]
    return Path(path).resolve()
