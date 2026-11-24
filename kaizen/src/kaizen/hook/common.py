"""What the file hooks share: reading the files pre-commit names, and one refusal listing every
finding's file, line and rule."""

import argparse
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from kaizen.shared.common import RefusalError


@dataclass(frozen=True)
class Finding:
    """One line a hook refuses: where it is, the rule it breaks and what matched."""

    path: str
    line: int
    rule: str
    match: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule} {self.match}"


def add_files_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("files", nargs="*", help="the files to check, as pre-commit passes them")


def read_text(name: str) -> str | None:
    """The file's text, or ``None`` when it is not UTF-8 text, which no text rule applies to, or
    can't be read, such as a dangling symlink or a folder."""
    try:
        return Path(name).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def refuse(hook: str, findings: Iterable[Finding], fix: str) -> None:
    """Refuses, listing each of the *findings* on a line of its own, when there are any."""
    found = list(findings)
    if found:
        raise RefusalError(
            f"hook {hook}: {len(found)} line(s) break its rule:\n"
            + "\n".join(f"  {finding}" for finding in found),
            fix,
        )
