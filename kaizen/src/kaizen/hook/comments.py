"""Finding the comments in a source file, so the comment hooks never read strings or code.

Python's comments come from the standard tokenizer. Other languages' come from their line-comment
prefix: a line whose first text is the prefix is a comment; a comment after code on the same line
is not read, since telling it from a string needs the language's own tokenizer. A file of a
language not listed here has no comments to read.
"""

import io
import tokenize
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import PurePath

from kaizen.hook.common import Finding, read_text

PYTHON = (".py", ".pyi")

LINE_PREFIX = {
    **dict.fromkeys((".sh", ".bash", ".zsh", ".yaml", ".yml", ".toml"), "#"),
    **dict.fromkeys(
        (
            # C-family, JavaScript and TypeScript
            *(".c", ".h", ".cc", ".cpp", ".cxx", ".hh", ".hpp", ".cs", ".java", ".go", ".swift"),
            *(".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"),
            *(".kt", ".kts", ".rs"),
        ),
        "//",
    ),
    **dict.fromkeys((".sql", ".lua"), "--"),
}
"""Each known language's line-comment prefix, by file suffix."""


@dataclass(frozen=True)
class Comment:
    line: int
    text: str
    """The comment as written, its prefix included, stripped of surrounding whitespace."""
    prefix: str

    @property
    def body(self) -> str:
        """The comment's words: its text without the prefix."""
        return self.text.removeprefix(self.prefix).strip()


def comments(name: str) -> Iterator[Comment]:
    """Every comment in the file *name*, nothing for a language not known or a file that is not
    text, and nothing for Python the tokenizer can't read."""
    suffix = PurePath(name).suffix.lower()
    if suffix not in PYTHON and suffix not in LINE_PREFIX:
        return
    text = read_text(name)
    if text is None:
        return
    if suffix in PYTHON:
        yield from _python_comments(text)
        return
    prefix = LINE_PREFIX[suffix]
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith(prefix):
            yield Comment(number, line.strip(), prefix)


def _python_comments(text: str) -> Iterator[Comment]:
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return
    for token in tokens:
        if token.type == tokenize.COMMENT:
            yield Comment(token.start[0], token.string.strip(), "#")


def comment_findings(
    names: list[str], rule: str, matches: Callable[[Comment], Iterator[str]]
) -> Iterator[Finding]:
    """One finding for each text *matches* returns from a comment of the files *names*."""
    for name in names:
        for comment in comments(name):
            for match in matches(comment):
                yield Finding(name, comment.line, rule, match)
