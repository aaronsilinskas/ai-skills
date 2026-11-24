"""``kaizen home sync``: bring a home's synced files and managed settings back in step with
kaizen's templates, or, with ``--check``, fail on any difference."""

import argparse
import difflib
from dataclasses import dataclass
from pathlib import Path

from kaizen.shared.common import RefusalError, Runner, Say
from kaizen.shared.home import SETTINGS, Home, SettingsError
from kaizen.shared.synced import OVERLAY, SYNCED_FILES, render, synced_settings

CHECK_FIX = "run `kaizen home sync`, and move home rules to the home overlay"
"""The fix a failed ``--check`` gives: a difference is either a template change the home hasn't
synced yet, or a hand edit that belongs in the home overlay."""


@dataclass(frozen=True)
class Change:
    """One file ``sync`` writes because its text differs from what ``sync`` writes."""

    relative: str
    """Its path relative to the home root."""
    current: str | None
    """Its text now, ``None`` when it is absent."""
    synced: str
    """Its text once synced."""
    merged: str | None = None
    """What ``sync`` merges into it, for a file ``sync`` owns only part of."""

    def diff(self) -> str:
        """The difference from its text now to its synced text, as a unified diff."""
        before = [] if self.current is None else self.current.splitlines()
        lines = difflib.unified_diff(
            before,
            self.synced.splitlines(),
            "/dev/null" if self.current is None else f"a/{self.relative}",
            f"b/{self.relative}",
            lineterm="",
        )
        return "\n".join(lines) or "(they differ only in line endings or the final newline)"

    def apply(self, root: Path) -> str:
        """Writes the synced text; returns the line of output."""
        path = root / self.relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.synced, encoding="utf-8")
        if self.merged is not None:
            return f"merged {self.merged} into {self.relative}"
        return f"wrote {self.relative}" if self.current is None else f"rewrote {self.relative}"


def changes(home: Home) -> list[Change]:
    """Every file of *home* whose text differs from what ``sync`` writes: each synced file, in the
    manifest's order, then the settings file. Reads only; refuses, before anything is written, on
    a path that is not a file and on settings that can't take the managed settings."""
    found = []
    for relative, synced in render(home).items():
        current = _current(home.root, relative)
        if current != synced.encode():
            found.append(Change(relative, _text(current), synced))
    try:
        settings = synced_settings(home.root)
    except SettingsError as exc:
        raise RefusalError(
            f"home sync: {exc}",
            f"fix {SETTINGS} so it holds a JSON object whose permissions.deny is a list,"
            " then run sync again",
        ) from exc
    if settings is not None:
        current = _current(home.root, SETTINGS)
        found.append(Change(SETTINGS, _text(current), settings, "the git stash deny rule"))
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


def sync_home(home: Home, *, dry_run: bool = False, check: bool = False, say: Say = print) -> None:
    """Writes each of *home*'s ``changes``, one line each, or says nothing changed. With
    *dry_run*, prints each change's diff instead; with *check*, prints them and refuses when there
    is any. Neither writes anything."""
    found = changes(home)
    if check:
        for change in found:
            say(f"differs: {change.relative}\n{change.diff()}")
        if found:
            raise RefusalError(
                f"home sync --check: {len(found)} file(s) differ from what sync writes: "
                + ", ".join(change.relative for change in found),
                CHECK_FIX,
            )
        say("home sync --check: every synced file and setting is in step")
        return
    if not found:
        say("nothing changed: every synced file and setting is in step")
    for change in found:
        say(
            f"would write {change.relative}:\n{change.diff()}"
            if dry_run
            else change.apply(home.root)
        )
    if dry_run:
        say("dry run: nothing written")


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "sync",
        help="re-render the home's synced files and managed settings, or check them",
        description=(
            "Bring the home's synced files back in step with kaizen's templates, after kaizen is "
            "upgraded or a template changes. It renders every synced file:\n"
            + "".join(f"  {synced.path}\n" for synced in SYNCED_FILES)
            + "and writes each one that is missing or differs, printing one line per file, or "
            "that nothing changed.\n\n"
            f"It also merges the managed settings into {SETTINGS}: the git stash deny rule, whose "
            "entries it adds to permissions.deny when missing, keeping every other key and entry "
            f"in order. It leaves the env's KAIZEN_HOME to `kaizen home init`, and never touches "
            f"the home overlay ({OVERLAY}), .pre-commit-config.yaml or any other file the home "
            "owns.\n\n"
            f"It refuses, before writing anything, when {SETTINGS} is not a JSON object, its "
            "permissions not an object or its permissions.deny not a list, and when a synced "
            "file's path is not a file.\n\n"
            "With --dry-run it prints each change as a diff and writes nothing.\n\n"
            "With --check it compares instead: it passes when nothing would change, and "
            "otherwise prints each difference and fails, naming every file, with the fix "
            f'"{CHECK_FIX}". It writes nothing and makes no network call, so a home\'s CI can '
            "run it."
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
        help="fail, listing every difference, unless the home is in step; write nothing",
    )
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    sync_home(home, dry_run=args.dry_run, check=args.check)
