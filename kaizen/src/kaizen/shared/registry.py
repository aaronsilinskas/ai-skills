"""The project registry: each project's facts, read from the frontmatter of ``<name>.md`` in
the home's registry folder (see ``kaizen.shared.home``).

A page starts with::

    ---
    path: ~/<dir>/example
    github: owner/example
    public: true
    worktree_root: ~/<dir>/elsewhere    # optional
    check: bash scripts/check.sh       # optional here; `kaizen spec integrate` refuses without it
    code_paths: src/, *.py, package.json     # optional; a docs change is refused without it
    auto_merge_paths: docs/                  # optional
    auto_merge_comment_only: true            # optional; default false
    worktree_links: tools/mpy-cross          # optional
    ---

``check`` is a shell command run from the root of a fresh worktree, so it installs what it needs
itself, or the literal ``none`` for a project with nothing to run.

``code_paths`` lists, comma-separated, the paths a **docs change** may not touch: an entry ending
in ``/`` covers everything under that directory, any other entry names one file. An entry holding
``*`` or ``?`` is a glob, matched against the whole repo-relative path from the project
root: ``*`` and ``?`` never cross ``/`` but do match a leading ``.``, ``**`` as a whole segment
matches any number of directories, and a glob ending in ``/`` covers everything under each
directory it matches. So ``*.py`` names the root's Python files and ``**/*.py`` every one.
Brackets are always literal, so ``src/[id].astro`` names one file.

``auto_merge_paths`` lists, the same way, the paths a docs change's PR may auto-merge for: when
every path it changes is under one of them, ``kaizen ticket ship`` enables auto-merge.

``auto_merge_comment_only: true`` lets a ticket closing an issue auto-merge when its change only
deletes or shrinks Python comments and docstrings (see ``kaizen.shared.comment_only``), unless the
home's marker turns the comment-only check off.

``worktree_links`` lists, comma-separated, git-ignored paths relative to the project root, such as
a downloaded tool: ``kaizen ticket start`` symlinks each one from the main checkout into the new
ticket worktree, which would otherwise lack it. Each is linked by name, so a glob is refused.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from kaizen.shared.branch import (
    find_integration_branch,
    integration_branch,
    parse_ticket_branch,
    remote_default_branch,
)
from kaizen.shared.comment_only import FileChange
from kaizen.shared.common import RefusalError, Runner, run_or_refuse

NO_CHECK = "none"
WORKTREES = ".claude/worktrees"
"""A project's worktree root when its page sets no ``worktree_root``, relative to its path."""

_GITHUB_REPO = re.compile(r"[\w.-]+/[\w.-]+")
# A GitHub remote URL in SSH (``git@github.com:o/r``, ``ssh://git@github.com/o/r``) or HTTPS
# form, with or without ``.git``.
_GITHUB_REMOTE = re.compile(
    r"(?:git@github\.com:|ssh://git@github\.com(?::\d+)?/|https://(?:[^@/]+@)?github\.com/)"
    r"(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?"
)

_WILDCARDS = {"*": "[^/]*", "?": "[^/]"}
"""The regex each glob wildcard stands for within one path segment."""


@dataclass(frozen=True)
class Project:
    name: str
    path: Path
    github: str
    public: bool
    worktree_root: Path
    check: str | None
    """The **check command**, ``NO_CHECK`` when the project declares it has nothing to run, or
    ``None`` when its page has no ``check`` key."""
    code_paths: tuple[str, ...] | None
    """The paths a docs change may not touch; ``None`` when the page has no ``code_paths`` key."""
    auto_merge_paths: tuple[str, ...] | None
    """The paths a docs change's PR auto-merges for when it changes nothing else; ``None`` when
    the page has no ``auto_merge_paths`` key."""
    auto_merge_comment_only: bool
    """Whether a ticket's PR auto-merges when it only deletes or shrinks comments and docstrings."""
    worktree_links: tuple[str, ...]
    """The git-ignored paths ``kaizen ticket start`` links from the main checkout into a
    worktree."""
    page: Path
    """The registry page these facts were read from."""

    def is_code(self, path: str) -> bool:
        """Whether the repo-relative *path* is under one of the project's code paths."""
        return _covers(self.code_paths, path)

    def is_auto_merge(self, path: str) -> bool:
        """Whether the repo-relative *path* is under one of the project's auto-merge paths."""
        return _covers(self.auto_merge_paths, path)

    @property
    def main_checkout(self) -> str:
        """The main checkout's path, as ``git -C`` takes it."""
        return str(self.path)


def resolve(name: str, projects_dir: Path) -> Project:
    """The registered project called *name*; refuses an unknown name or a malformed page."""
    page = projects_dir / f"{name}.md"
    if not page.is_file():
        known = ", ".join(p.name for p in all_projects(projects_dir))
        raise RefusalError(f"no project page {page}", f"use a registered project: {known}")
    return _parse(name, page)


def home_repos(projects_dir: Path) -> frozenset[str]:
    """Every registered project's GitHub repo, lowercased, as GitHub compares repo names."""
    return frozenset(p.github.lower() for p in all_projects(projects_dir))


def refuse_undeclared_code_paths(project: Project) -> None:
    """Refuses a project whose page declares no code paths, so a docs change can't pass its code
    guard by default."""
    if project.code_paths is None:
        raise RefusalError(
            f"project {project.name} declares no code_paths, so a docs change can't be checked"
            " for code changes",
            f"add 'code_paths: <dir>/, <file>' to {project.page}, or open an issue"
            " and start the ticket with it",
        )


def resolve_current(run: Runner, projects_dir: Path) -> Project:
    """The registered project whose main checkout is the git checkout the command runs in."""
    root = _toplevel(run)
    projects = all_projects(projects_dir)
    if project := _main_checkout_owner(root, projects):
        return project
    raise RefusalError(
        f"{root} is not a registered project's main checkout",
        "run from the root of one of: " + ", ".join(str(p.path) for p in projects),
    )


def resolve_checkout(run: Runner, path: Path | None, projects_dir: Path) -> tuple[Project, Path]:
    """The registered project, and the checkout's root, for the git checkout at *path* (default:
    the one the command runs in): the project's main checkout, or a worktree directly under its
    worktree root, such as a ticket worktree. The worktree's branch is not checked."""
    root = _toplevel(run, path.expanduser() if path is not None else None)
    projects = all_projects(projects_dir)
    # Main checkouts first, so a project's checkout is never taken for a sibling's worktree.
    if project := _main_checkout_owner(root, projects) or _worktree_owner(root, projects):
        return project, root
    places = ", ".join(f"{p.path} (or a worktree under {p.worktree_root})" for p in projects)
    action = "run from" if path is None else "run from, or pass,"
    raise RefusalError(
        f"{root} is not a registered project's main checkout or a worktree under its worktree root",
        f"{action} the root of one of: {places}",
    )


def github_remote(url: str) -> tuple[str, str] | None:
    """The GitHub owner and repo a remote *url* names, in SSH or HTTPS form; ``None`` for any
    other URL."""
    if match := _GITHUB_REMOTE.fullmatch(url):
        return match["owner"], match["repo"]
    return None


def _main_checkout_owner(root: Path, projects: list[Project]) -> Project | None:
    """The project whose main checkout is *root*, if any."""
    return next((p for p in projects if p.path.resolve() == root.resolve()), None)


def _worktree_owner(root: Path, projects: list[Project]) -> Project | None:
    """The project whose worktree root directly holds *root*, if any."""
    parent = root.resolve().parent
    return next((p for p in projects if p.worktree_root.resolve() == parent), None)


def _toplevel(run: Runner, path: Path | None = None) -> Path:
    """The root of the git checkout at *path*, or of the one the command runs in."""
    if path is None:
        cmd = ["git", "rev-parse", "--show-toplevel"]
        problem = "could not find the git checkout this command runs in"
        fix = "run inside a registered project's git checkout"
    else:
        cmd = ["git", "-C", str(path), "rev-parse", "--show-toplevel"]
        problem = f"could not find a git checkout at {path}"
        fix = (
            "pass a project's main checkout or a ticket worktree path `kaizen ticket start` printed"
        )
    return Path(run_or_refuse(cmd, run, problem, fix).strip())


def all_projects(projects_dir: Path) -> list[Project]:
    """Every project with a page, in name order."""
    return [_parse(page.stem, page) for page in _pages(projects_dir)]


class InvalidPage(NamedTuple):
    """A registry page ``all_projects`` refuses, and its refusal."""

    page: Path
    refusal: RefusalError


def invalid_pages(projects_dir: Path) -> list[InvalidPage]:
    """Each page that ``all_projects`` would refuse, in name order, with its refusal."""
    found = []
    for page in _pages(projects_dir):
        try:
            _parse(page.stem, page)
        except RefusalError as refusal:
            found.append(InvalidPage(page, refusal))
    return found


def _pages(projects_dir: Path) -> list[Path]:
    return [page for page in sorted(projects_dir.glob("*.md")) if page.name != "README.md"]


def _parse(name: str, page: Path) -> Project:
    fields = _frontmatter(page)
    path = _path_field(page, fields, "path")
    github = _field(page, fields, "github", str)
    if not _GITHUB_REPO.fullmatch(github):
        raise RefusalError(
            f"{page}: field 'github' is {github!r}, not owner/repo",
            "set it to the GitHub repo, such as owner/example",
        )
    public = _field(page, fields, "public", bool)
    worktree_root = (
        _path_field(page, fields, "worktree_root")
        if "worktree_root" in fields
        else path / WORKTREES
    )
    check = _field(page, fields, "check", str) if "check" in fields else None
    code_paths = _comma_list(page, fields, "code_paths")
    auto_merge_paths = _comma_list(page, fields, "auto_merge_paths")
    auto_merge_comment_only = "auto_merge_comment_only" in fields and _field(
        page, fields, "auto_merge_comment_only", bool
    )
    worktree_links = _worktree_links(page, fields)
    return Project(
        name,
        path,
        github,
        public,
        worktree_root,
        check,
        code_paths,
        auto_merge_paths,
        auto_merge_comment_only,
        worktree_links,
        page,
    )


def _comma_list(page: Path, fields: dict[str, str | bool], key: str) -> tuple[str, ...] | None:
    """The comma-separated entries under *key*; ``None`` when the page has no such key."""
    if key not in fields:
        return None
    listed = _field(page, fields, key, str)
    return tuple(entry.strip() for entry in listed.split(",") if entry.strip())


def _worktree_links(page: Path, fields: dict[str, str | bool]) -> tuple[str, ...]:
    """The page's ``worktree_links`` entries; refuses one that reaches outside the project root."""
    entries = _comma_list(page, fields, "worktree_links") or ()
    for entry in entries:
        if Path(entry).is_absolute() or ".." in Path(entry).parts:
            raise RefusalError(
                f"{page}: worktree_links entry {entry!r} is outside the project root",
                "list paths relative to the project root, with no '..' parts",
            )
        if _is_glob(entry):
            raise RefusalError(
                f"{page}: worktree_links entry {entry!r} is a glob, but entries are linked by name",
                "list each path to link by name, with no '*' or '?'",
            )
    return entries


def _covers(entries: tuple[str, ...] | None, path: str) -> bool:
    """Whether *path* is under one of *entries*: a directory ending in ``/``, a file, or a glob."""
    return any(_entry_covers(entry, path) for entry in entries or ())


def _entry_covers(entry: str, path: str) -> bool:
    if _is_glob(entry):
        pattern = entry + "**" if entry.endswith("/") else entry
        return re.fullmatch(_glob_regex(pattern), path) is not None
    return path.startswith(entry) if entry.endswith("/") else path == entry


def _glob_regex(pattern: str) -> str:
    """The regex for a path glob. ``glob.translate`` would do, but it needs Python 3.13 and
    treats ``[`` as a character class, which would break a route file such as ``[id].astro``."""
    segments = pattern.split("/")
    regex = ""
    for index, segment in enumerate(segments):
        last = index == len(segments) - 1
        if segment == "**":
            regex += ".*" if last else "(?:[^/]+/)*"
        else:
            regex += "".join(_WILDCARDS.get(char) or re.escape(char) for char in segment)
            regex += "" if last else "/"
    return regex


def _is_glob(entry: str) -> bool:
    return "*" in entry or "?" in entry


def _frontmatter(page: Path) -> dict[str, str | bool]:
    lines = page.read_text().splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise RefusalError(
            f"{page}: no registry frontmatter",
            "start the page with a '---' block holding path, github and public",
        )
    fields: dict[str, str | bool] = {}
    for line in lines[1 : lines.index("---", 1)]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise RefusalError(
                f"{page}: frontmatter line {line!r} is not 'key: value'", "fix the line"
            )
        fields[key.strip()] = _scalar(value.strip())
    return fields


def _scalar(value: str) -> str | bool:
    if value in ("true", "false"):
        return value == "true"
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _field[T](page: Path, fields: dict[str, str | bool], key: str, kind: type[T]) -> T:
    if key not in fields:
        raise RefusalError(
            f"{page}: missing field '{key}'", f"add '{key}:' to the page's frontmatter"
        )
    value = fields[key]
    if not isinstance(value, kind) or (kind is str and not value):
        expected = "true or false" if kind is bool else "a non-empty string"
        raise RefusalError(
            f"{page}: field '{key}' is {value!r}, not {expected}",
            f"set '{key}' to {expected}",
        )
    return value


def _path_field(page: Path, fields: dict[str, str | bool], key: str) -> Path:
    """The page's *key* as a path, ``~`` expanded; refuses a relative one, which would resolve
    against wherever a command runs."""
    value = _field(page, fields, key, str)
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise RefusalError(
            f"{page}: field '{key}' is {value!r}, not an absolute path or ~/…",
            f"set '{key}' to a full path, written from / or ~/",
        )
    return path


_STARTER_README = """\
# Projects

This folder is the home's project registry, the folder its `kaizen.toml` names as `registry`.
Each project the home's sessions work on, the home itself included, has one page here,
`<name>.md`, and `<name>` is the name `kaizen` commands take for it.
A page starts with a frontmatter block of `key: value` lines between two `---` lines, which `kaizen`
reads; the rest of the page is free notes. The project's own repo holds its facts and docs, and
its page only points at them.

## Keys

- `path` (required): the project's main checkout, absolute or from `~`. Every command that
  takes a project name or runs from a project's root finds the project by it, and the leak check
  lets the home's projects mention it.
- `github` (required): the project's GitHub repo, `owner/repo`. The `kaizen ticket`, `kaizen spec`,
  `kaizen issue` and `kaizen pr` commands run `gh` against it, and the leak check lets the home's
  projects mention it and treats its owner as one of the home's owners.
- `public` (required): `true` or `false`, whether the repo is public. The leak check, which
  `kaizen ticket ship`, the `kaizen spec` commands, the publish commands and
  `kaizen project leak-check` run, keeps the home's own repo and path (`leak.own` in
  `kaizen.toml`) out of a public project.
- `worktree_root` (optional): where `kaizen ticket start` puts the project's ticket worktrees,
  absolute or from `~`; default `<path>/.claude/worktrees`. The commands that take a ticket
  worktree find its project by it, and the leak check lets the home's projects mention it.
- `check` (optional, but `kaizen spec integrate` refuses a project without it): the project's check
  command, a shell command run from the root of a fresh worktree, so it installs what it needs
  itself, or the literal `none` for a project with nothing to run. `kaizen spec integrate` runs it
  before pushing a spec's integration branch.
- `code_paths` (optional, but a docs change is refused without it): comma-separated paths a
  docs change may not touch. An entry ending in `/` covers everything under that directory, and
  any other names one file. An entry holding `*` or `?` is a glob, matched against the whole
  path from the project root: `*` and `?` never cross `/` but do match a leading `.`, `**` as a
  whole segment matches any number of directories, and a glob ending in `/` covers everything
  under each directory it matches. Brackets are literal. `kaizen ticket start` and
  `kaizen ticket ship` check a docs change against it.
- `auto_merge_paths` (optional): comma-separated paths, as in `code_paths`. `kaizen ticket ship`
  enables auto-merge on a docs change's PR when every path it changes is under one of them.
- `auto_merge_comment_only` (optional, default `false`): when `true`, `kaizen ticket ship` enables
  auto-merge on a ticket's PR, even one closing an issue, when its change only deletes or
  shrinks Python comments and docstrings, unless the home's marker sets
  `auto_merge_comment_only = false`.
- `worktree_links` (optional): comma-separated git-ignored paths relative to the project root,
  such as a downloaded tool, with no globs. `kaizen ticket start` and `kaizen ticket compare`
  symlink each one from the main checkout into the worktrees they make.
## Pages

{pages}
"""


def starter_readme(pages: list[str]) -> str:
    """The text of a new registry's README: what each frontmatter key means and which commands
    read it, then a link to each page in *pages* (page names, in order)."""
    return _STARTER_README.format(pages="\n".join(f"- [{name}]({name}.md)" for name in pages))


def starter_page(name: str, path: str, github: str) -> str:
    """The text of a new home's own page, *name*: its *path* and *github*, ``public: false`` until
    the user settles it, and no ``check`` or ``code_paths`` yet."""
    return f"""\
---
path: {path}
github: {github}
public: false
---
# {name}

This home's own page. Still to settle:

- `public`: written `false`; set it to `true` if the repo is public.
- `check`: add the home's check command, or `none` if it has nothing to run.
- `code_paths`: add the paths a docs change may not touch.
"""


@dataclass(frozen=True)
class TicketWorktree:
    project: Project
    path: Path
    branch: str
    issue: int | None
    """The issue the ticket closes; ``None`` for a docs change (a ``docs-<slug>`` branch)."""
    default_branch: str
    spec: int | None
    """The spec the ticket belongs to (a ``spec-<N>-fix-…`` branch); ``None`` for a lone ticket."""

    @property
    def label(self) -> str:
        """What the worktree is, for a command's first line: a docs change's, or an issue's."""
        if self.issue is None:
            return "ticket worktree for a docs change"
        return f"ticket worktree for issue #{self.issue}"

    @property
    def base_branch(self) -> str:
        """The branch the ticket is built on: its spec's integration branch, else the default."""
        return integration_branch(self.spec) if self.spec is not None else self.default_branch

    @property
    def base_ref(self) -> str:
        """The base branch's remote-tracking ref, ``origin/<base>``, as ``fetch_base`` sets it."""
        return f"origin/{self.base_branch}"


def fetch_base(ticket: TicketWorktree, run: Runner) -> str:
    """Fetches only the ticket's base branch from ``origin`` and returns its ref, ``origin/<base>``.

    A spec's ticket whose integration branch is only local (see ``local_base``) gets that branch,
    and nothing is fetched. Refuses when neither ``origin`` nor the clone has the branch, such as
    a spec whose integration branch was never started.
    """
    local = local_base(ticket, run)
    if local is not None:
        return local
    return fetch_branch(str(ticket.path), ticket.base_branch, run, _missing_base_fix(ticket))


def base_ref(ticket: TicketWorktree, run: Runner) -> str:
    """The ticket's base ref as last fetched, fetching nothing: ``local_base`` when it has one,
    else ``origin/<base>``. Only queries."""
    return local_base(ticket, run) or ticket.base_ref


def local_base(ticket: TicketWorktree, run: Runner) -> str | None:
    """The local integration branch a spec's ticket is based on while ``origin`` lacks it, as
    ``kaizen spec start --local`` leaves it until the first integration; ``None`` for any other
    ticket. Only queries."""
    if ticket.spec is None:
        return None
    found = find_integration_branch(str(ticket.path), ticket.spec, run)
    return found.ref if found is not None and not found.on_origin else None


def fetch_branch(checkout: str, branch: str, run: Runner, fix: str) -> str:
    """Fetches only *branch* from ``origin`` into *checkout* and returns its remote-tracking ref,
    ``origin/<branch>``; refuses with *fix* when the fetch fails."""
    refspec = f"+refs/heads/{branch}:refs/remotes/origin/{branch}"
    run_or_refuse(
        ["git", "-C", checkout, "fetch", "-q", "origin", refspec],
        run,
        f"could not fetch {branch} from origin",
        fix,
    )
    return f"origin/{branch}"


def _missing_base_fix(ticket: TicketWorktree) -> str:
    if ticket.spec is not None:
        return (
            f"check that origin has {ticket.base_branch}; if spec #{ticket.spec}'s integration"
            f" branch was never started, run `kaizen spec start {ticket.spec}`"
        )
    return f"check that origin has {ticket.base_branch} and that the remote is reachable"


def resolve_ticket_worktree(path: Path, run: Runner, projects_dir: Path) -> TicketWorktree:
    """The project and issue of the ticket worktree at *path*, worked out with no stored state.

    The project is the one whose worktree root holds *path*; the issue, and the spec if any,
    come from the ``fix-<issue>-<slug>`` or ``spec-<N>-fix-<issue>-<slug>`` branch checked
    out there, and a ``docs-<slug>`` branch has neither. Refuses, in this order, a path under
    no project's worktree root, a worktree on the default branch, and any other branch.
    """
    path = path.expanduser().resolve()
    projects = all_projects(projects_dir)
    project = _worktree_owner(path, projects)
    if project is None:
        roots = ", ".join(str(p.worktree_root) for p in projects)
        raise RefusalError(
            f"{path} is not a registered project's ticket worktree",
            f"pass a worktree made by `kaizen ticket start`, directly under one of: {roots}",
        )
    branch = run_or_refuse(
        ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
        run,
        f"could not read the branch of {path}",
        "check that the path is a git worktree",
    ).strip()
    default = remote_default_branch(project.main_checkout, run)
    if branch == default:
        raise RefusalError(
            f"{path} is on the default branch {default}",
            "work lands through a PR: commit on a fix-<issue>-<slug> branch "
            "from `kaizen ticket start`",
        )
    parsed = parse_ticket_branch(branch)
    if parsed is None:
        raise RefusalError(
            f"{path} is on {branch!r}, not a fix-<issue>-<slug> ticket branch"
            " (or spec-<N>-fix-<issue>-<slug> for a spec's ticket,"
            " docs-<slug> for a docs change)",
            "use the ticket worktree `kaizen ticket start` made, on its own branch",
        )
    return TicketWorktree(project, path, branch, parsed.issue, default, parsed.spec)


def refuse_spec_ticket(ticket: TicketWorktree) -> None:
    """Refuses a spec's ticket worktree, which integrates into its spec instead of its own PR."""
    if ticket.spec is not None:
        raise RefusalError(
            f"{ticket.path} is a ticket worktree of spec #{ticket.spec} (on {ticket.branch}),"
            f" which integrates into {integration_branch(ticket.spec)}, not its own PR",
            f"run `kaizen spec integrate {ticket.path}`",
        )


def refuse_uncommitted(ticket: TicketWorktree, run: Runner, *, fix: str) -> None:
    """Refuses a ticket worktree with uncommitted changes, listing them."""
    if status := uncommitted(ticket, run):
        raise RefusalError(f"{ticket.path} has uncommitted changes:\n{status}", fix)


def uncommitted(ticket: TicketWorktree, run: Runner) -> str:
    """The ticket worktree's uncommitted changes as ``git status --porcelain`` lists them;
    empty when it is clean."""
    return run(["git", "-C", str(ticket.path), "status", "--porcelain"]).rstrip()


def changed_paths(ticket: TicketWorktree, run: Runner) -> list[str]:
    """The paths the ticket's diff against the default branch changes.

    Renames count as a deletion and an addition, so moving a file out of a code path is caught.
    """
    base = f"origin/{ticket.default_branch}"
    changed = run(
        ["git", "-C", str(ticket.path), "diff", "--name-only", "--no-renames", f"{base}...HEAD"]
    )
    return changed.splitlines()


def file_changes(ticket: TicketWorktree, run: Runner) -> list[FileChange]:
    """Each file the ticket's diff against the default branch changes, with its source at the
    merge base and at ``HEAD``. Renames count as a deletion and an addition, as in
    ``changed_paths``; refuses a file git cannot show."""
    worktree = str(ticket.path)
    upstream = f"origin/{ticket.default_branch}"
    statuses = run(
        ["git", "-C", worktree, "diff", "--name-status", "--no-renames", f"{upstream}...HEAD"]
    )
    base = run(["git", "-C", worktree, "merge-base", upstream, "HEAD"]).strip()

    def source(ref: str, path: str) -> str:
        return run_or_refuse(
            ["git", "-C", worktree, "show", f"{ref}:{path}"],
            run,
            f"could not read {path} at {ref}",
            "check the worktree's git objects, then ship again",
        )

    changes = []
    for line in statuses.splitlines():
        status, _, path = line.partition("\t")
        old = None if status == "A" else source(base, path)
        new = None if status == "D" else source("HEAD", path)
        changes.append(FileChange(path, old, new))
    return changes


def refuse_code_changes(ticket: TicketWorktree, changed: list[str]) -> None:
    """Refuses a docs change whose *changed* paths touch code, naming the files."""
    refuse_undeclared_code_paths(ticket.project)
    base = f"origin/{ticket.default_branch}"
    code = [path for path in changed if ticket.project.is_code(path)]
    if code:
        listed = "\n".join(f"  {path}" for path in code)
        raise RefusalError(
            f"{ticket.branch} is a docs change, but its diff against {base} touches"
            f" code:\n{listed}",
            f"open an issue for the change and start it with"
            f" `kaizen ticket start {ticket.project.name} <issue>`, or drop the code changes",
        )


def refuse_nothing_ahead(ticket: TicketWorktree, base: str, run: Runner, *, fix: str) -> int:
    """How many commits the ticket's branch is ahead of *base*; refuses none."""
    ahead = commits_ahead(ticket, base, run)
    if not ahead:
        raise RefusalError(f"{ticket.branch} has no commits ahead of {base}", fix)
    return ahead


def commits_ahead(ticket: TicketWorktree, base: str, run: Runner) -> int:
    """How many commits the ticket's branch has that *base* lacks."""
    return int(run(["git", "-C", str(ticket.path), "rev-list", "--count", f"{base}..HEAD"]))
