"""``kaizen hook prose-marks``: refuse em dashes and curly quotes in Markdown, the marks that give
prose away as machine-written; en dashes stay allowed for ranges."""

import argparse
from collections.abc import Iterator
from pathlib import PurePath

from kaizen.hook.common import Finding, add_files_argument, read_text, refuse
from kaizen.shared.common import Runner
from kaizen.shared.home import Home

_MARKDOWN = (".md", ".markdown")

_MARKS = {
    "\u2014": "em dash",
    "\u2018": "left single quote",
    "\u2019": "right single quote",
    "\u201c": "left double quote",
    "\u201d": "right double quote",
}

_FIX = (
    "replace each mark with a plain one: a comma, colon, parentheses or a hyphen for an em dash,"
    " straight quotes for curly ones"
)


def prose_mark_findings(names: list[str]) -> Iterator[Finding]:
    """Each line of the Markdown files among *names* holding a refused mark, once per mark."""
    for name in names:
        if PurePath(name).suffix.lower() not in _MARKDOWN or (text := read_text(name)) is None:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for mark, label in _MARKS.items():
                if mark in line:
                    yield Finding(name, number, "prose mark", f"{label} (U+{ord(mark):04X})")


def add_parser(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    parser = subparsers.add_parser(
        "prose-marks",
        help="refuse em dashes and curly quotes in Markdown",
        description=(
            "Refuse each line of the Markdown files given (.md or .markdown) that holds an em "
            "dash or a curly quote, naming its file, line and mark. En dashes are allowed, for "
            "ranges. Files that are not Markdown are skipped."
        ),
    )
    add_files_argument(parser)
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    refuse("prose-marks", prose_mark_findings(args.files), _FIX)
