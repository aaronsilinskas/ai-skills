"""Reading a Python source's comments through the standard tokenizer, so a ``#`` inside a string
is never taken for one."""

import io
import tokenize
from typing import NamedTuple


class PythonComment(NamedTuple):
    line: int
    text: str
    """The comment as the tokenizer gives it, its ``#`` included."""


def python_comments(source: str) -> list[PythonComment]:
    """Every comment in *source*, in order; none when the tokenizer can't read *source*."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, SyntaxError):
        return []
    return [
        PythonComment(token.start[0], token.string)
        for token in tokens
        if token.type == tokenize.COMMENT
    ]
