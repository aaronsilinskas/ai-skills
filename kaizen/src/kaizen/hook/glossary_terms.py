"""``kaizen hook glossary-terms``: refuse Markdown that uses a word its glossary says to avoid, so
the docs keep to the project's vocabulary."""

import argparse
import re
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePath

from kaizen.hook.common import Finding, add_files_argument, read_text, refuse
from kaizen.hook.markdown import CODE_SPAN, is_markdown, prose_lines
from kaizen.shared.command_records import HomeCommand
from kaizen.shared.common import Runner, Subparsers
from kaizen.shared.home import Home

GLOSSARY = "GLOSSARY.md"
_AVOID = "_Avoid_:"
_TERM = re.compile(r"\*\*(?P<term>[^*]+)\*\*:")
"""A glossary entry's heading line, ``**Term**:``."""
_TERM_SEPARATOR = re.compile(r",(?![^(]*\))")
"""A comma between avoided terms, not one inside a qualifier."""
_QUOTED = re.compile(r'"[^"\n]*"')

_FIX = (
    "use the glossary's term instead; if the word means something else here, give it a qualifier "
    'in the glossary, such as "_Avoid_: config (for a home setting)", since a qualified term is '
    "never refused"
)


@dataclass(frozen=True)
class _Avoided:
    pattern: re.Pattern[str]
    term: str
    """What the glossary lists as avoided."""
    instead: str
    """The glossary term to use."""


@cache
def _avoided(glossary: str) -> tuple[_Avoided, ...]:
    """The avoided terms of the glossary at *glossary*, none when it can't be read: every term an
    ``_Avoid_:`` line lists, but those with a qualifier in parentheses, which only a reader can
    judge, and those the glossary itself defines."""
    text = read_text(glossary)
    if text is None:
        return ()
    lines = text.splitlines()
    defined = {match.group("term").lower() for line in lines if (match := _TERM.match(line))}
    found = []
    instead = ""
    for line in lines:
        if match := _TERM.match(line):
            instead = match.group("term")
        elif line.startswith(_AVOID):
            for term in (part.strip() for part in _TERM_SEPARATOR.split(line[len(_AVOID) :])):
                if term and "(" not in term and term.lower() not in defined:
                    words = r"\s+".join(map(re.escape, term.split()))
                    pattern = re.compile(rf"(?<![\w-]){words}s?(?![\w-])", re.IGNORECASE)
                    found.append(_Avoided(pattern, term, instead))
    return tuple(found)


def _glossaries(name: str) -> list[str]:
    """The glossaries that apply to the file *name*: one in its folder or any folder above it."""
    return [
        str(folder / GLOSSARY)
        for folder in PurePath(name).parents
        if Path(folder, GLOSSARY).is_file()
    ]


def glossary_term_findings(names: list[str]) -> Iterator[Finding]:
    """Each use, in the prose of the Markdown files among *names*, of a term their glossaries
    avoid: outside fenced code, code spans and double quotes, and never on an ``_Avoid_:`` line."""
    for name in names:
        if not is_markdown(name) or (text := read_text(name)) is None:
            continue
        avoided = [term for glossary in _glossaries(name) for term in _avoided(glossary)]
        if not avoided:
            continue
        for number, line in prose_lines(text):
            if line.startswith(_AVOID):
                continue
            prose = _QUOTED.sub("", CODE_SPAN.sub("", line))
            for term in avoided:
                if match := term.pattern.search(prose):
                    yield Finding(
                        name, number, "avoided term", f'{match.group()}, use "{term.instead}"'
                    )


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "glossary-terms",
        help="refuse Markdown that uses a term its GLOSSARY.md says to avoid",
        description=(
            "Refuse each line of the Markdown files given that uses a term avoided by a "
            f"{GLOSSARY} in the file's folder or a folder above it, naming its file, line, the "
            "term and the glossary term to use. Avoided terms are those an _Avoid_: line lists, "
            "comma-separated, under a **Term**: entry; a term with a qualifier in parentheses, "
            "such as row (in a table), and a term the glossary itself defines are never refused. "
            "A term matches as a whole word, in any case, plural included. Fenced code, code "
            "spans, text in double quotes and the _Avoid_: lines are not read. Files that are not "
            "Markdown are skipped."
        ),
    )
    add_files_argument(parser)
    parser.set_defaults(command=HomeCommand(_command))


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    refuse("glossary-terms", glossary_term_findings(args.files), _FIX)
