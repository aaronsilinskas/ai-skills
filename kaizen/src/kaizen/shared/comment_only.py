"""The comment-only check: whether a change only deletes or shrinks Python comments and docstrings.

A change passes when every changed file is a Python file present on both sides, its syntax tree
with docstrings stripped is unchanged, and the comment-plus-docstring text summed over all the
files is no longer than at the base. The text is summed across the change, not per file, so a
cut-and-cite edit may keep one useful sentence in a file while the change as a whole shrinks.
"""

import ast
import copy
from collections.abc import Iterator
from typing import NamedTuple

from kaizen.shared.python_comments import python_comments


class FileChange(NamedTuple):
    path: str
    old: str | None
    """The file's source at the base; ``None`` when the change adds it."""
    new: str | None
    """The file's source at the head; ``None`` when the change deletes it."""


def comment_only_problems(changes: list[FileChange]) -> list[str]:
    """Why the *changes* are not comment-only, one line each; empty when they are."""
    problems: list[str] = []
    old_prose = new_prose = 0
    for change in changes:
        if not change.path.endswith(".py"):
            problems.append(f"{change.path}: not a Python file")
        elif change.old is None or change.new is None:
            problems.append(f"{change.path}: added or deleted")
        else:
            try:
                old_tree, new_tree = ast.parse(change.old), ast.parse(change.new)
            except SyntaxError:
                problems.append(f"{change.path}: does not parse")
                continue
            old_prose += _prose_length(change.old, old_tree)
            new_prose += _prose_length(change.new, new_tree)
            if _without_docstrings(old_tree) != _without_docstrings(new_tree):
                problems.append(f"{change.path}: code changed")
    if new_prose > old_prose:
        problems.append(f"comment and docstring text grew ({old_prose} -> {new_prose} characters)")
    return problems


def _without_docstrings(tree: ast.Module) -> str:
    """A copy of *tree* with its docstrings removed, dumped for comparison."""
    tree = copy.deepcopy(tree)
    for node, field, block in list(_blocks(tree)):
        setattr(node, field, [n for n in block if _docstring(n) is None] or [ast.Pass()])
    return ast.dump(tree)


def _prose_length(source: str, tree: ast.Module) -> int:
    """The length of *source*'s comments, trimmed, plus its docstrings without whitespace."""
    comments = sum(len(comment.text.lstrip("#").strip()) for comment in python_comments(source))
    docstrings = sum(
        len("".join(text.split()))
        for _, _, block in _blocks(tree)
        for statement in block
        if (text := _docstring(statement)) is not None
    )
    return comments + docstrings


def _blocks(tree: ast.AST) -> Iterator[tuple[ast.AST, str, list[ast.stmt]]]:
    """Each block of statements in *tree*, empty ones included, with the node and field holding
    it; a bare string in one is a docstring or a no-op. A lambda's ``body`` is no block."""
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and all(isinstance(n, ast.stmt) for n in block):
                yield node, field, block


def _docstring(statement: object) -> str | None:
    """The text of *statement* when it is a bare string (a docstring, or a string used as a
    comment); otherwise ``None``."""
    if (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    ):
        return statement.value.value
    return None
