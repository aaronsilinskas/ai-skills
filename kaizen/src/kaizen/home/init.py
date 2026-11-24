"""``kaizen home init``: make the git repo the command runs in a **home**, the one command that runs
where no home exists yet."""

import argparse
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from kaizen.shared.common import RefusalError, Runner, Say, StepFailedError, run_or_refuse
from kaizen.shared.home import (
    ENV_VAR,
    MARKER,
    REGISTRY,
    SETTINGS,
    SettingsError,
    find_home,
    fresh_home,
    fresh_marker,
    home_path,
    marker_at_or_above,
    name_home,
    read_settings,
    root_named_by_env,
    same_root,
    settings_text,
)
from kaizen.shared.leak import LeakFoundError, leak_check
from kaizen.shared.pre_commit import CONFIG, FRESH_CONFIG, runs_every_hook
from kaizen.shared.registry import WORKTREES, resolve, starter_page, starter_readme
from kaizen.shared.synced import (
    HOOKS_DOC,
    OVERLAY,
    SETTINGS_SHAPE,
    SYNCED_FILES,
    merge_stash_deny,
    render,
    starter_overlay,
)
from kaizen.shared.version import Install, Version, recordable_version

GITIGNORE = ".gitignore"

# A GitHub remote URL in SSH (``git@github.com:o/r``, ``ssh://git@github.com/o/r``) or HTTPS
# form, with or without ``.git``.
_GITHUB_REMOTE = re.compile(
    r"(?:git@github\.com:|ssh://git@github\.com(?::\d+)?/|https://(?:[^@/]+@)?github\.com/)"
    r"(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?"
)


@dataclass(frozen=True)
class NewHome:
    """The facts of the home being made, all read before anything is written."""

    root: Path
    owner: str
    """The owner of the home's GitHub repo, from its ``origin`` remote."""
    repo: str
    """The home's GitHub repo name, from its ``origin`` remote; also its project name in its own
    registry."""
    user_home: Path

    @property
    def github(self) -> str:
        """The home's GitHub repo, ``owner/repo``."""
        return f"{self.owner}/{self.repo}"

    @property
    def name(self) -> str:
        """The home's project name in its own registry."""
        return self.repo

    @property
    def path(self) -> str:
        """The root as the home's files write it."""
        return home_path(self.root, self.user_home)


class Step(Protocol):
    """One thing ``init`` writes. Every step's ``check`` runs before any step's ``apply``."""

    def check(self) -> str:
        """Refuses when the step can't be done; returns the check, as dry-run prints it."""
        ...

    def preview(self) -> str:
        """What the step would write, in full."""
        ...

    def apply(self) -> str:
        """Does the step; returns its line of output."""
        ...


@dataclass(frozen=True)
class NewFile:
    """A file ``init`` writes whole. An existing one identical to it is kept, so a rerun after a
    failure partway finishes; a differing one is refused."""

    root: Path
    relative: str
    content: str

    @property
    def path(self) -> Path:
        return self.root / self.relative

    def check(self) -> str:
        if self.path.exists() and (
            not self.path.is_file() or self.path.read_bytes() != self.content.encode()
        ):
            raise RefusalError(
                f"home init: {self.relative} already exists and differs from what init writes",
                f"move {self.relative} aside, or make it match `kaizen home init --dry-run`'s"
                " output, then run init again",
            )
        return f"{self.relative} is absent, or identical to what init writes"

    def preview(self) -> str:
        return f"would write {self.relative}:\n{self.content}"

    def apply(self) -> str:
        if self.path.is_file():
            return f"kept {self.relative}, already as init writes it"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.content)
        return f"wrote {self.relative}"


@dataclass(frozen=True)
class SettingsMerge:
    """``KAIZEN_HOME`` merged into the settings file's ``env``, so sessions started in the home
    find it, and the managed settings merged as ``kaizen home sync`` merges them; the file is
    created when absent, and one that holds both already is kept."""

    root: Path
    value: str
    """``KAIZEN_HOME``'s value: the root as the home's files write it."""
    user_home: Path

    @property
    def path(self) -> Path:
        return self.root / SETTINGS

    def _merged(self) -> str | None:
        try:
            settings = read_settings(self.root)
            named = name_home(settings, self.value)
            denied = merge_stash_deny(settings)
        except SettingsError as exc:
            raise RefusalError(f"home init: {exc}", self._fix(exc)) from exc
        return settings_text(settings) if named or denied else None

    def _fix(self, exc: SettingsError) -> str:
        if exc.variable is None or exc.value is None:
            fix = f"fix {SETTINGS} so it holds {SETTINGS_SHAPE}"
        elif not same_root(exc.value, self.root, self.user_home):
            # The value is not printed: it may be another home's root.
            fix = (
                f"remove {exc.variable} from {SETTINGS}'s env if this repo is meant to be a new"
                " home"
            )
        elif exc.names_old_variable:
            fix = f"replace {exc.variable} in {SETTINGS}'s env with {ENV_VAR} set to {self.value}"
        else:
            # The same root in another form, such as absolute, which can hold a user name.
            fix = f"set {ENV_VAR} in {SETTINGS}'s env to {self.value} instead"
        return f"{fix}, then run init again"

    def check(self) -> str:
        self._merged()
        return (
            f"{SETTINGS} is absent, or a JSON object whose env sets no other {ENV_VAR} and that"
            " can take the git stash deny rule"
        )

    def preview(self) -> str:
        merged = self._merged()
        if merged is None:
            return (
                f"would keep {SETTINGS}: its env already sets {ENV_VAR} to the home, and it"
                " denies git stash"
            )
        return f"would write {SETTINGS}:\n{merged}"

    def apply(self) -> str:
        merged = self._merged()
        if merged is None:
            return (
                f"kept {SETTINGS}, its env already sets {ENV_VAR} to the home and it denies"
                " git stash"
            )
        existed = self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(merged)
        if existed:
            return f"merged {ENV_VAR} and the git stash deny rule into {SETTINGS}"
        return f"wrote {SETTINGS}"


@dataclass(frozen=True)
class IgnoreLine:
    """A line appended to ``.gitignore`` when no line there ignores the same path yet; the file is
    created when absent."""

    root: Path
    line: str

    @property
    def path(self) -> Path:
        return self.root / GITIGNORE

    def _text(self) -> str | None:
        return _optional_text(self.root, GITIGNORE)

    def _present(self, text: str) -> bool:
        # A leading or trailing slash doesn't change what a root .gitignore line ignores here.
        return any(line.strip().strip("/") == self.line.strip("/") for line in text.splitlines())

    def check(self) -> str:
        self._text()
        return f"{GITIGNORE} is absent or readable, so init can make it ignore {self.line}"

    def preview(self) -> str:
        text = self._text()
        if text is None:
            return f"would write {GITIGNORE}:\n{self.line}\n"
        if self._present(text):
            return f"would keep {GITIGNORE}: it already ignores {self.line}"
        return f"would append to {GITIGNORE}:\n{self.line}\n"

    def apply(self) -> str:
        text = self._text()
        if text is None:
            self.path.write_text(f"{self.line}\n")
            return f"wrote {GITIGNORE}"
        if self._present(text):
            return f"kept {GITIGNORE}, it already ignores {self.line}"
        separator = "" if not text or text.endswith("\n") else "\n"
        self.path.write_text(f"{text}{separator}{self.line}\n")
        return f"added {self.line} to {GITIGNORE}"


@dataclass(frozen=True)
class HookConfig:
    """The hook config, written with every hook entry when absent. An existing one is the home's
    own and is kept, with a to-do when it lacks a hook entry."""

    root: Path

    def to_do(self) -> str | None:
        """What is left to add by hand, or ``None`` when the config runs every hook."""
        text = _optional_text(self.root, CONFIG)
        if text is None or runs_every_hook(text):
            return None
        return f"add the kaizen hook entries {HOOKS_DOC} lists to {CONFIG}"

    def check(self) -> str:
        _optional_text(self.root, CONFIG)
        return f"{CONFIG} is absent or readable"

    def preview(self) -> str:
        if _optional_text(self.root, CONFIG) is None:
            return f"would write {CONFIG}:\n{FRESH_CONFIG}"
        return f"would keep {CONFIG}: {self._kept()}"

    def apply(self) -> str:
        if _optional_text(self.root, CONFIG) is None:
            (self.root / CONFIG).write_text(FRESH_CONFIG)
            return f"wrote {CONFIG}"
        return f"kept {CONFIG}: {self._kept()}"

    def _kept(self) -> str:
        to_do = self.to_do()
        return "it already runs every kaizen hook" if to_do is None else f"the home's own; {to_do}"


def _optional_text(root: Path, relative: str) -> str | None:
    """The text of the file *relative* to *root*, ``None`` when absent; refuses when it can't be
    read as text."""
    path = root / relative
    if not path.exists():
        return None
    try:
        return path.read_text()
    except (OSError, UnicodeDecodeError) as exc:
        raise RefusalError(
            f"home init: {relative} exists but can't be read as text",
            f"fix or move {relative} aside, then run init again",
        ) from exc


def init_home(
    run: Runner,
    cwd: Path,
    env: Mapping[str, str],
    install: Install,
    *,
    dry_run: bool = False,
    say: Say = print,
) -> None:
    """Makes the git repo holding *cwd* a home: checks every precondition, writes each step of
    ``_steps`` in order, reports the leak check's findings as to-dos and prints what is left for
    the user. With *dry_run*, prints the checks and every file in full instead. The marker
    records the running version as the synced version, which the synced files are rendered
    for, so the new home's first command does not warn."""
    user_home = Path(env.get("HOME") or Path.home()).resolve()
    root = Path(
        run_or_refuse(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            run,
            "home init: not inside a git repo",
            "run kaizen home init inside the repo that becomes the home (`git init` it first)",
        ).strip()
    )
    say(f"home root: {root}")
    checks = [f"{root} is a git repo's root"]
    checks += _check_not_inside_home(root, env, user_home)
    new = NewHome(root, *_origin_repo(root, run), user_home)
    checks.append(f"origin is the GitHub repo {new.github}")
    version = recordable_version(install.version, "home init")
    checks.append(f"kaizen's version {version} is X.Y.Z, so the marker can record it")
    steps = _steps(new, version)
    checks += [step.check() for step in steps]
    if dry_run:
        for check in checks:
            say(f"checked: {check}")
        for step in steps:
            say(step.preview())
        say("would run the leak check over the home's committed files and print its findings")
        say("dry run: nothing written")
        return
    for step in steps:
        say(step.apply())
    say(f"{root} is now a home")
    _report_leaks(new, run, say)
    say("still to do, by you:")
    if hook_to_do := HookConfig(new.root).to_do():
        say(f"  - [ ] {hook_to_do}")
    for item in _checklist(str(new.root), new.name):
        say(f"  - [ ] {item}")


def _check_not_inside_home(root: Path, env: Mapping[str, str], user_home: Path) -> list[str]:
    """The checks that *root* is not, or not inside, a home, and that ``KAIZEN_HOME`` doesn't
    point away from it; refuses otherwise. The refusals name no other root, so another home's path
    never reaches this one's output."""
    named = root_named_by_env(env, user_home)
    if named is not None and named.root != root.resolve():
        variable = named.variable
        raise RefusalError(
            f"home init: {variable} is set to a root other than {root}",
            f"unset {variable}, or start a fresh session in {root}, then run init again",
        )
    if marker_at_or_above(root):
        raise RefusalError(
            f"home init: a {MARKER} is already in {root} or a directory above it, so this repo"
            " is a home already or sits inside one",
            "run kaizen home init in a repo outside every home; "
            "init never changes an existing home",
        )
    return [f"no {MARKER} in {root} or above it", f"{ENV_VAR} is unset or names {root}"]


def _origin_repo(root: Path, run: Runner) -> tuple[str, str]:
    """The GitHub owner and repo of the repo's ``origin`` remote; refuses when there is none."""
    url = run_or_refuse(
        ["git", "-C", str(root), "remote", "get-url", "origin"],
        run,
        "home init: the repo has no origin remote",
        "add the home's GitHub repo as origin (`git remote add origin <url>`), then run init again",
    ).strip()
    # The URL itself is not printed: an HTTPS remote can carry a token.
    if match := _GITHUB_REMOTE.fullmatch(url):
        return match["owner"], match["repo"]
    raise RefusalError(
        "home init: origin's URL does not name a GitHub owner/repo",
        "point origin at the home's GitHub repo, in SSH or HTTPS form, then run init again",
    )


def _report_leaks(new: NewHome, run: Runner, say: Say) -> None:
    """Runs the shared leak check once over the new home and prints each finding as a to-do; a
    finding never fails ``init``, but any other refusal fails it as an error, since the files are
    written."""
    heading = "leak check: searched committed files only"
    try:
        # No env: the marker just written at the root is the home, whatever KAIZEN_HOME says.
        home = find_home(new.root, {})
        public = resolve(new.name, home.registry).public
        leak_check(new.root, home, run, public=public, user_home=new.user_home)
    except LeakFoundError as exc:
        say(f"{heading}; to do, one line per finding with its fix:")
        for finding in exc.findings:
            say(f"  - [ ] {finding}")
        return
    except RefusalError as exc:
        # Not a refusal: init's files are written by now, which an error says and a refusal
        # would deny.
        raise StepFailedError(
            "home init: the leak check",
            f"{exc}\nonce that is fixed, run `kaizen project leak-check` from the home's root",
        ) from exc
    say(f"{heading}; it found nothing")


def _checklist(root: str, name: str) -> list[str]:
    """What only the user can do once ``init`` is done, for the home at *root* whose page is
    *name*."""
    return [
        f"restart the session in {root}, so {ENV_VAR} in {SETTINGS} loads",
        f"add a page to {REGISTRY}/ for each project the home's sessions work on, and list it"
        f" in {REGISTRY}/README.md",
        f"add each project's directory to permissions.additionalDirectories in {SETTINGS}",
        f"settle the to-do fields on {REGISTRY}/{name}.md: public, check, code_paths",
        "run `kaizen project leak-check` again after the first commit, since it searches committed"
        " files only",
        f"run `pre-commit install` in {root}, so the hooks in {CONFIG} run on every commit",
        "commit the result through a PR",
        "put this line in the home's AGENTS.md: \"kaizen must be on the PATH; if it is not, ask the"
        ' user to install it."',
    ]


def _steps(new: NewHome, version: Version) -> list[Step]:
    """What ``init`` writes, in write order. The marker comes last, so a failure partway leaves
    no marker, and a rerun is not refused as a home already."""
    return [
        SettingsMerge(new.root, new.path, new.user_home),
        IgnoreLine(new.root, f"{WORKTREES}/"),
        NewFile(new.root, f"{REGISTRY}/README.md", starter_readme([new.name])),
        NewFile(
            new.root, f"{REGISTRY}/{new.name}.md", starter_page(new.name, new.path, new.github)
        ),
        *[
            NewFile(new.root, relative, text)
            for relative, text in render(
                fresh_home(new.root, new.github, new.path, version), version
            ).items()
        ],
        NewFile(new.root, OVERLAY, starter_overlay()),
        HookConfig(new.root),
        NewFile(new.root, MARKER, fresh_marker(new.github, new.path, version)),
    ]


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "init",
        help="make the current git repo a new home",
        description=(
            "Make the git repo the command runs in a home for kaizen, from any directory in it: "
            "init uses the repo's root (its git toplevel) and prints it first. It is the one "
            "kaizen command that runs where no home exists.\n\n"
            f"It refuses, before writing anything: outside a git repo; when a {MARKER} is at "
            f"the root or in any directory above it; when {ENV_VAR} is set to a different root; "
            "when the repo has no origin remote, or one that is not a GitHub repo in SSH or "
            f"HTTPS form; when {SETTINGS} is not valid JSON, is not a JSON object, has an env "
            "or permissions that is not an object or a permissions.deny that is not a list, or "
            f"already sets {ENV_VAR} to a different value; and when "
            f"{GITIGNORE} can't be read as text. It also refuses when a file it writes whole "
            "already exists and differs from what it would write; an identical one is kept, so "
            "a rerun after a failure partway finishes.\n\n"
            "It writes, in this order:\n"
            f"  {SETTINGS}  env.{ENV_VAR} set to the home's root (written from ~ when under "
            "your user directory), so sessions started in the home find it, and the git stash "
            "deny rule's entries added to permissions.deny, as `kaizen home sync` adds them; the "
            "file is created when absent, and an existing one keeps every other key and entry "
            "and their order\n"
            f"  {GITIGNORE}  a {WORKTREES}/ line, so ticket worktrees stay out of git status; "
            "the file is created when absent, and the line is added only when missing\n"
            f"  {REGISTRY}/README.md  the project registry's README: what each page key means, "
            "which commands read it, and a list of the pages\n"
            f"  {REGISTRY}/<repo>.md  the home's own page, named after origin's repo: its "
            "path (written from ~ when under your user directory), github from origin, "
            "public: false, and what is left to settle (public, check, code_paths)\n"
            + "".join(f"  {synced.path}\n" for synced in SYNCED_FILES)
            + "    each a synced file: a generic workflow doc rendered for the home from kaizen's "
            "templates, opening with a line that says not to edit it there\n"
            f"  {OVERLAY}  the home overlay: a starter page for the home's own rules beside "
            "the synced files; init writes it whole, like the registry files, and it is the home's "
            "to edit, never rendered from a template\n"
            f"  {CONFIG}  the hook config: a repo: local entry for each kaizen hook, as "
            f"{HOOKS_DOC} lists them; an existing one is the home's own and is kept, with a "
            "to-do when it lacks any of them\n"
            f"  {MARKER}  the home marker, written last so a failure partway leaves none: "
            f'registry = "{REGISTRY}", synced_version set to the running kaizen\'s version, '
            "which the synced files are rendered for, and a [leak] table whose own holds the "
            "home's owner/repo and path, and whose allow starts empty\n\n"
            "It prints one line per step done. It makes no network call and needs no gh.\n\n"
            "Then it runs the leak check once over the new home and prints each finding as a "
            "to-do: its file, line, rule and match, and its fixes (register the project in the "
            f"registry, allow it in leak.allow in {MARKER}, or remove the text). The check "
            "searches committed files only, and findings never fail the command.\n\n"
            "Last it prints a checklist of what only you can do:\n"
            + "".join(f"  - {item}\n" for item in _checklist("the home's root", "<repo>"))
            + "\n"
            "With --dry-run it runs the same checks, prints them, every file it would write in "
            f"full, the merged {SETTINGS} and the {GITIGNORE} change, skips the leak check, and "
            "writes nothing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run the checks, print them and every file in full, and write nothing",
    )
    parser.set_defaults(handler=_command, needs_home=False)


def _command(
    args: argparse.Namespace, run: Runner, cwd: Path, env: Mapping[str, str], install: Install
) -> None:
    init_home(run, cwd, env, install, dry_run=args.dry_run)
