"""``kaizen home sync``: bring a home's synced files and managed settings back in step with
kaizen's templates, or, with ``--check``, fail on any difference."""

import argparse
from dataclasses import dataclass
from pathlib import Path

from kaizen.shared.command_records import InstallCommand
from kaizen.shared.common import RefusalError, Runner, Say, Subparsers, unified_diff
from kaizen.shared.home import (
    MARKER,
    SETTINGS,
    Home,
    SettingsError,
    with_synced_version,
)
from kaizen.shared.registry import invalid_pages
from kaizen.shared.synced import (
    OVERLAY,
    SETTINGS_SHAPE,
    SYNCED_FILES,
    managed_settings_text,
    render,
)
from kaizen.shared.version import UPGRADE, Install, Version, newer_release, recordable_version

CHECK_FIX = "run `kaizen home sync`, and move home rules to the home overlay"
"""The fix a failed ``--check`` gives: a difference is either a template change the home hasn't
synced yet, or a hand edit that belongs in the home overlay."""


@dataclass(frozen=True)
class Change:
    """One file of a home that is out of step: a synced file whose text is not its render, the
    settings file lacking part of the managed settings, or the marker not recording the synced
    version."""

    relative: str
    """Its path relative to the home root."""
    current: str | None
    """Its text now, ``None`` when it is absent."""
    synced: str
    """Its text once synced."""
    done_line: str | None = None
    """For a file the home owns but for one part that ``sync`` writes, the output line saying
    what it wrote; ``None`` for a file ``sync`` renders whole."""

    def diff(self) -> str:
        """The difference from its text now to its synced text, as a unified diff."""
        diff = unified_diff(self.relative, self.current, self.synced)
        return diff or "(they differ only in line endings or the final newline)"

    def apply(self, root: Path) -> str:
        """Writes the synced text; returns the line of output."""
        path = root / self.relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.synced, encoding="utf-8")
        if self.done_line is not None:
            return self.done_line
        return f"wrote {self.relative}" if self.current is None else f"rewrote {self.relative}"


def changes(home: Home, version: Version) -> list[Change]:
    """Every file of *home* whose text differs from what ``sync`` writes as the release *version*:
    each synced file, in the manifest's order, then the settings file, then the marker recording
    *version*. Reads only; refuses, before anything is written, on a path that is not a file and
    on settings that can't take the managed settings."""
    found = []
    for relative, synced in render(home, version).items():
        current = _current(home.root, relative)
        if current != synced.encode():
            found.append(Change(relative, _text(current), synced))
    try:
        settings = managed_settings_text(home.root)
    except SettingsError as exc:
        raise RefusalError(
            f"home sync: {exc}", f"fix {SETTINGS} so it holds {SETTINGS_SHAPE}, then run sync again"
        ) from exc
    if settings is not None:
        current = _current(home.root, SETTINGS)
        found.append(
            Change(
                SETTINGS,
                _text(current),
                settings,
                f"merged the git stash deny rule into {SETTINGS}",
            )
        )
    marker = (home.root / MARKER).read_text(encoding="utf-8")
    recorded = with_synced_version(marker, version)
    if recorded != marker:
        found.append(
            Change(
                MARKER,
                marker,
                recorded,
                f"recorded synced version {version} in {MARKER}",
            )
        )
    return found


def _current(root: Path, relative: str) -> bytes | None:
    path = root / relative
    if not path.exists():
        return None
    if not path.is_file():
        raise RefusalError(
            f"home sync: {relative} is not a file", f"move {relative} aside, then run sync again"
        )
    return path.read_bytes()


def _text(current: bytes | None) -> str | None:
    return None if current is None else current.decode("utf-8", errors="replace")


IN_STEP = "every synced file and setting is in step"
PAGE_FIX = "fix each page as its line says"
"""The fix a failed ``--check`` gives for invalid registry pages: each page's own refusal, printed
on its ``invalid:`` line, names the key and its fix."""


def sync_home(
    home: Home,
    install: Install,
    *,
    dry_run: bool = False,
    preview: bool = False,
    say: Say = print,
) -> None:
    """Writes each of *home*'s ``changes`` for the running version, which it records as the
    synced version, one line each, or says nothing changed; then names a newer release when
    there is one. With *dry_run*, prints each change's diff instead and writes nothing.

    With *preview*, for a local build, it is a dry run rendered for *home*'s recorded synced
    version, so the diffs show only template changes.

    Refuses: a running version that is not ``X.Y.Z``, which no home's CI could install, unless
    *preview*; and a *preview* of a home that records no synced version."""
    if preview:
        dry_run = True
        version = _recorded_version(
            home, "home sync --dry-run --allow-dev", "run a release's `kaizen home sync` first"
        )
    else:
        version = recordable_version(install.version, "home sync", alternative=PREVIEW_FIX)
    found = changes(home, version)
    if not found:
        say(f"nothing changed: {IN_STEP}")
    for change in found:
        say(
            f"would write {change.relative}:\n{change.diff()}"
            if dry_run
            else change.apply(home.root)
        )
    if dry_run:
        say("dry run: nothing written")
    if line := newer_release(install.version, install.latest):
        say(line)


PREVIEW_FIX = (
    "to preview a local build's synced files, run `kaizen home sync --dry-run --allow-dev`"
)


def is_preview(running: str, *, allow_dev: bool, dry_run: bool) -> bool:
    """Whether a sync of the *running* version is a local build's preview: *allow_dev* on a
    version that is not ``X.Y.Z``. A release build ignores *allow_dev*. Refuses a local build's
    *allow_dev* without *dry_run*, since its version can't be recorded."""
    if not allow_dev or Version.parse(running) is not None:
        return False
    if not dry_run:
        raise RefusalError(
            f"home sync: --allow-dev is preview-only, so it needs --dry-run to run kaizen"
            f" {running}, which is not X.Y.Z",
            "add --dry-run to preview the synced files, or install a release to write them",
        )
    return True


def _recorded_version(home: Home, command: str, fix: str) -> Version:
    if home.synced_version is None:
        raise RefusalError(f"{command}: {MARKER} records no synced version", fix)
    return home.synced_version


def check_home(home: Home, *, say: Say = print) -> None:
    """Prints each invalid registry page of *home* with its problem, then each of its
    ``changes`` as a diff, and refuses, naming them all, when there is any. Writes nothing, and
    renders for the synced version *home* records, the release its CI installs; refuses when it
    records none. The marker itself was validated when *home* was found."""
    invalid = invalid_pages(home.registry)
    for problem in invalid:
        say(f"invalid: {problem.refusal}")
    version = _recorded_version(home, "home sync --check", "run `kaizen home sync`")
    found = changes(home, version)
    for change in found:
        say(f"differs: {change.relative}\n{change.diff()}")
    problems, fixes = [], []
    if invalid:
        pages = ", ".join(problem.page.relative_to(home.root).as_posix() for problem in invalid)
        problems.append(f"{len(invalid)} registry page(s) are invalid: {pages}")
        fixes.append(PAGE_FIX)
    if found:
        files = ", ".join(change.relative for change in found)
        problems.append(f"{len(found)} file(s) differ from what sync writes: {files}")
        fixes.append(CHECK_FIX)
    if problems:
        raise RefusalError("home sync --check: " + "; ".join(problems), "; ".join(fixes))
    say(f"home sync --check: {IN_STEP}")


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "sync",
        help="re-render the home's synced files and merge its managed settings, or check both",
        description=(
            "Bring the home's synced files back in step with kaizen's templates, after kaizen is "
            "upgraded or a template changes. It renders every synced file:\n"
            + "".join(f"  {synced.path}\n" for synced in SYNCED_FILES)
            + "and writes each one that is missing or differs, printing one line per file, or "
            "that nothing changed. It overwrites any local edit to a synced file, which the "
            "home's git diff shows and its history keeps.\n\n"
            f"It also merges the managed settings into {SETTINGS}: the git stash deny rule, whose "
            "entries it adds to permissions.deny when missing, keeping every other key and entry "
            "in order. When it adds an entry, it rewrites the whole file as JSON indented by "
            "two spaces, so the file's own formatting is not kept. It leaves the env's "
            "KAIZEN_HOME to `kaizen home init`, and never touches "
            f"the home overlay ({OVERLAY}), .pre-commit-config.yaml or any other file the home "
            "owns.\n\n"
            "Last it records the running kaizen's version as synced_version in the home's "
            f"{MARKER}, the release every kaizen command compares itself with; the synced files "
            "show it in the home's CI step. That line is the only part of the marker it writes, "
            "replacing it, or else inserting it above the first table.\n\n"
            "It refuses, before writing anything: when the installed kaizen is older than the "
            f"home's synced version, so a sync never rolls a home back (the fix is `{UPGRADE}`); "
            "when kaizen's version is not X.Y.Z, such as a local build's, except in the "
            "--dry-run --allow-dev preview; when "
            f"{SETTINGS} is not a JSON object, its permissions not an object or its "
            "permissions.deny not a list; and when a synced file's path is not a file.\n\n"
            "Then it asks PyPI, once and briefly, for kaizen's latest release, and prints the "
            "upgrade command when that is newer; a failed lookup prints nothing. No other kaizen "
            "command looks up releases.\n\n"
            "With --dry-run it prints each change as a diff and writes nothing.\n\n"
            "With --dry-run --allow-dev, a local build, whose version is not X.Y.Z, previews "
            "what it would sync: this is the way to check a template change against a real home "
            "before release. It renders for the home's recorded synced version, so the diffs "
            "show only template changes, prints each change as a diff, and writes nothing: no "
            "synced file, no settings merge and no synced version. It makes no network call, and "
            "refuses when the marker records no synced version. --allow-dev without --dry-run "
            "is refused as preview-only, and a release build ignores it.\n\n"
            "With --check it compares instead, rendering for the home's recorded synced version, "
            "which is the release a home's CI runs it with: it passes when nothing would change, "
            "and otherwise prints each difference and fails, naming every file, with the fix "
            f'"{CHECK_FIX}". It also fails when the marker records no synced version. It writes '
            "nothing and makes no network call, so a home's CI can run it.\n\n"
            "--check also validates the home marker and every registry page, as the commands "
            f"that read them do: {MARKER} must parse as TOML, hold its required keys and name a "
            "registry folder that exists, or the run is refused before anything else; each page "
            "(every .md in the registry folder but README.md) must parse as every command that "
            "reads it parses it: a frontmatter block of key: value lines, its required keys "
            "present and every key well formed, as the registry folder's README lists them. "
            "It lists each invalid page "
            "with its problem beside the differing files, so one run shows everything, and "
            f'fails with the fix "{PAGE_FIX}".'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true", help="print each change as a diff and write nothing"
    )
    mode.add_argument(
        "--check",
        action="store_true",
        dest="check",
        help="fail, listing every difference and every invalid registry page, unless the home is "
        "in step and its marker and pages are valid; write nothing",
    )
    parser.add_argument(
        "--allow-dev",
        action="store_true",
        help="with --dry-run, preview a local build's synced files and diffs against the home, "
        "to check a template change before release; a release build ignores it",
    )
    parser.set_defaults(
        command=InstallCommand(_command, records_version=lambda args: not args.check)
    )


def _command(args: argparse.Namespace, run: Runner, home: Home, install: Install) -> None:
    preview = is_preview(install.version, allow_dev=args.allow_dev, dry_run=args.dry_run)
    if args.check:
        check_home(home)
    else:
        sync_home(home, install, dry_run=args.dry_run, preview=preview)
