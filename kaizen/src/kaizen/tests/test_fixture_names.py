"""Tests that the synced-file templates and the tests name no real GitHub owner (ADR 0002), only
the generic fixture ones and the third parties named here."""

import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]

GENERIC_OWNERS = {"acme", "o", "other", "owner", "someone", "stranger"}
"""The made-up owners the tests' fixtures use."""

THIRD_PARTY_OWNERS = {"astral-sh"}
"""Real owners that belong to no home, such as a tool's maker."""

_REPO = r"(?P<owner>[\w.-]+)/[\w.-]+"
_REPO_REFERENCES = [
    re.compile(rf"(?<![\w.])github\.com(?::\d+)?[/:]{_REPO}"),
    re.compile(rf"github: {_REPO}"),
    re.compile(rf"(?:-R|--repo)\W+{_REPO}"),
    re.compile(rf"repos/{_REPO}"),
    re.compile(rf"(?<![\w./-]){_REPO}#\d"),
]
"""The ways a repo is named: a URL, a registry page's field, a gh repo flag, an API path and an
issue reference."""


def _scanned() -> list[Path]:
    templates = sorted((PACKAGE / "shared" / "templates").iterdir())
    return templates + sorted((PACKAGE / "tests").glob("*.py"))


def test_templates_and_tests_name_only_generic_or_third_party_owners():
    allowed = GENERIC_OWNERS | THIRD_PARTY_OWNERS
    found = [
        f"{path.relative_to(PACKAGE)}:{number}: {match.group(0)}"
        for path in _scanned()
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        for pattern in _REPO_REFERENCES
        for match in pattern.finditer(line)
        if match.group("owner").lower() not in allowed
    ]

    assert found == []


def test_the_scan_finds_a_repo_named_in_each_way():
    lines = [
        "https://github.com/stranger/one",
        "git@github.com:stranger/one.git",
        "github: stranger/one",
        "gh -R stranger/one issue view 3",
        'gh api "repos/stranger/one/issues/3"',
        "see stranger/one#3",
    ]

    assert [
        [m.group("owner") for p in _REPO_REFERENCES for m in p.finditer(line)] for line in lines
    ] == [["stranger"]] * len(lines)
