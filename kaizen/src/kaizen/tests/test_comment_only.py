"""Tests for the comment-only check: whether a change only deletes or shrinks Python comments
and docstrings."""

from kaizen.shared.comment_only import FileChange, comment_only_problems

BASE = '''"""The module docstring, long enough to cut."""


def double(x):
    """Return twice *x*, explained at some length."""
    # Multiply rather than add, for no reason worth keeping.
    return x * 2
'''


def _change(new: str | None, old: str | None = BASE, path: str = "engine/maths.py") -> FileChange:
    return FileChange(path, old, new)


def test_deleting_a_comment_and_shortening_docstrings_is_comment_only():
    new = '''"""The module docstring."""


def double(x):
    """Return twice *x*."""
    return x * 2
'''

    assert comment_only_problems([_change(new)]) == []


def test_a_change_to_code_alongside_a_docstring_cut_is_not_comment_only():
    new = BASE.replace("x * 2", "x + x").replace("explained at some length", "")

    assert comment_only_problems([_change(new)]) == ["engine/maths.py: code changed"]


def test_rewording_a_comment_longer_is_not_comment_only():
    new = BASE.replace("no reason worth keeping", "a reason we spell out in many more words")

    (problem,) = comment_only_problems([_change(new)])

    assert problem.startswith("comment and docstring text grew")


def test_prose_may_grow_in_one_file_while_the_whole_change_shrinks():
    grown = BASE.replace("for no reason", "for no good reason")
    cut = BASE.replace(", explained at some length", "")

    assert comment_only_problems([_change(grown), _change(cut, path="engine/other.py")]) == []


def test_turning_a_comment_into_code_is_not_comment_only():
    new = BASE.replace(
        "    # Multiply rather than add, for no reason worth keeping.\n", "    x = x\n"
    )

    assert comment_only_problems([_change(new)]) == ["engine/maths.py: code changed"]


def test_a_changed_file_that_is_not_python_is_not_comment_only():
    assert comment_only_problems([_change("# Docs\n", "# Docs, longer\n", path="README.md")]) == [
        "README.md: not a Python file"
    ]


def test_adding_or_deleting_a_python_file_is_not_comment_only():
    problems = comment_only_problems(
        [_change(BASE, old=None, path="engine/new.py"), _change(None, path="engine/gone.py")]
    )

    assert problems == ["engine/new.py: added or deleted", "engine/gone.py: added or deleted"]


def test_a_file_that_does_not_parse_is_not_comment_only():
    assert comment_only_problems([_change("def broken(:\n")]) == ["engine/maths.py: does not parse"]


def test_deleting_a_comment_beside_a_lambda_is_comment_only():
    old = "# Pick the larger of two values.\nlarger = lambda a, b: a if a > b else b\n"
    new = "larger = lambda a, b: a if a > b else b\n"

    assert comment_only_problems([_change(new, old)]) == []


def test_deleting_a_modules_only_docstring_is_comment_only():
    assert comment_only_problems([_change("", '"""The effects package."""\n')]) == []
