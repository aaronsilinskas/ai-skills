"""Reading Markdown prose for the doc hooks: the lines outside fenced code, and their code spans."""

import re
from collections.abc import Iterator
from pathlib import PurePath

MARKDOWN = (".md", ".markdown")

CODE_SPAN = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
"""A single-backtick code span; a double-backtick one is left alone."""

_FENCE = re.compile(r"\s{0,3}(```|~~~)")


def is_markdown(name: str) -> bool:
    return PurePath(name).suffix.lower() in MARKDOWN


def prose_lines(text: str) -> Iterator[tuple[int, str]]:
    """Each line of the Markdown *text* outside fenced code, with its line number."""
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if match := _FENCE.match(line):
            if fence is None:
                fence = match.group(1)
            elif match.group(1) == fence:
                fence = None
            continue
        if fence is None:
            yield number, line
