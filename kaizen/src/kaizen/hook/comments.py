"""Finding the comments in a source file, so the comment hooks never read strings or code.

Python's comments come from the standard tokenizer. Other languages' come from their line-comment
prefix: a line whose first text is the prefix is a comment; a comment after code on the same line
is not read, since telling it from a string needs the language's own tokenizer. A file of a
language not listed here has no comments to read.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import PurePath

from kaizen.hook.common import Finding, read_text
from kaizen.shared.python_comments import python_comments

PYTHON = (".py", ".pyi")

LINE_PREFIX = {
    **dict.fromkeys((".sh", ".bash", ".zsh", ".yaml", ".yml", ".toml"), "#"),
    **dict.fromkeys(
        (
            *(".c", ".h", ".cc", ".cpp", ".cxx", ".hh", ".hpp", ".cs", ".java", ".go", ".swift"),
            *(".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"),
            *(".kt", ".kts", ".rs"),
        ),
        "//",
    ),
    **dict.fromkeys((".sql", ".lua"), "--"),
}

LANGUAGES = (
    "Python's through its tokenizer, and whole-line comments by their prefix in shell, YAML and "
    "TOML (#), C-family languages, JavaScript, TypeScript, Kotlin and Rust (//), and SQL and Lua "
    "(--). Files of other languages are skipped."
)
"""Which comments the comment hooks read, for their help."""


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
        for comment in python_comments(text):
            yield Comment(comment.line, comment.text.strip(), "#")
        return
    prefix = LINE_PREFIX[suffix]
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith(prefix):
            yield Comment(number, line.strip(), prefix)


def comment_findings(
    names: list[str], rule: str, matches: Callable[[Comment], Iterator[str]]
) -> Iterator[Finding]:
    """One finding for each text *matches* returns from a comment of the files *names*."""
    for name in names:
        for comment in comments(name):
            for match in matches(comment):
                yield Finding(name, comment.line, rule, match)
