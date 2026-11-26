"""``kaizen hook test-names``: refuse pytest tests whose names say nothing about what they
guarantee, the bar the test-quality skill sets for a test's name."""

import argparse
import ast
from collections.abc import Iterator
from fnmatch import fnmatch
from pathlib import PurePath

from kaizen.hook.common import Finding, add_files_argument, read_text, refuse
from kaizen.shared.command_records import HomeCommand
from kaizen.shared.common import Runner, Subparsers
from kaizen.shared.home import Home

_TEST_FILES = ("test_*.py", "*_test.py")
"""pytest's default test file names."""

VACUOUS = frozenset(
    {"basic", "case", "example", "happy", "it", "ok", "path", "sanity", "simple", "smoke", "works"}
)
"""Words that say a test passes, not what it guarantees."""

_FIX = (
    "name the guarantee the test checks, as test_<subject>_<condition>, such as "
    "test_parse_rejects_an_empty_header; the test-quality skill's Test naming section sets the bar"
)


def is_vacuous(name: str) -> bool:
    """Whether the test *name* says nothing about a guarantee: at most one word after ``test``,
    or only words from ``VACUOUS``."""
    words = [word for word in name.split("_")[1:] if word]
    return len(words) <= 1 or all(word.lower() in VACUOUS for word in words)


def _tests(source: str) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and (
            node.name == "test" or node.name.startswith("test_")
        ):
            yield node


def vacuous_test_findings(names: list[str]) -> Iterator[Finding]:
    """Each test function with a vacuous name in the pytest test files among *names*."""
    for name in names:
        if not any(fnmatch(PurePath(name).name, pattern) for pattern in _TEST_FILES):
            continue
        if (source := read_text(name)) is None:
            continue
        for test in _tests(source):
            if is_vacuous(test.name):
                yield Finding(name, test.lineno, "vacuous test name", test.name)


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "test-names",
        help="refuse pytest tests named after one word or only vacuous ones",
        description=(
            "Refuse each test function or method, in the pytest test files given (test_*.py or "
            "*_test.py), whose name says nothing about what it guarantees, naming its file, line "
            "and name: test alone, test_ and one word such as test_parse or test_works, or only "
            f"the words {', '.join(sorted(VACUOUS))}, such as test_it_works. A test name should "
            "state the guarantee, as the test-quality skill's Test naming section says. Other "
            "files, and Python that won't parse, are skipped."
        ),
    )
    add_files_argument(parser)
    parser.set_defaults(command=HomeCommand(_command))


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    refuse("test-names", vacuous_test_findings(args.files), _FIX)
