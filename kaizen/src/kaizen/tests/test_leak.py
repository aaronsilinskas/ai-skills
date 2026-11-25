"""Tests for the **leak check**'s rules on text bound for GitHub, such as a PR or issue body.

The text is judged inside a fixture home whose user directory is under ``tmp_path``, so ``~``
never means the real home directory. The same rules run against a real git checkout in
``test_leak_git.py``.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from kaizen.shared.common import RefusalError
from kaizen.shared.home import Home
from kaizen.shared.leak import leak_check_text
from kaizen.tests.leak_home import leak_home, leak_user
from kaizen.tests.ticket_shell import TILDE

VISIBILITY = pytest.mark.parametrize("public", [True, False], ids=["public", "private"])


@pytest.fixture
def user(tmp_path: Path) -> Path:
    return leak_user(tmp_path)


@pytest.fixture
def home(user: Path) -> Home:
    return leak_home(user)


def _text_refused(home: Home, user: Path, texts: dict[str, str], public: bool) -> str:
    with pytest.raises(RefusalError) as refusal:
        leak_check_text(texts, home, public=public, user_home=user)
    return str(refusal.value)


@VISIBILITY
def test_text_pointing_outside_the_home_is_refused_naming_the_text_line_rule_and_fix(
    home, user, public
):
    texts = {"PR title": "Fix it", "PR body": f"Why.\nsee {TILDE}/dev/elsewhere and owner/secret\n"}

    refusal = _text_refused(home, user, texts, public)

    assert "leak check: text for GitHub points outside this home" in refusal
    assert f"PR body line 2: outside path {TILDE}/dev/elsewhere (fix: register the project" in (
        refusal
    )
    assert "PR body line 2: unregistered repo owner/secret (fix: register it" in refusal
    assert "PR title" not in refusal


def test_an_own_reference_in_text_is_refused_for_a_public_project(home, user):
    refusal = _text_refused(home, user, {"issue body": "part of owner/home\n"}, public=True)

    assert "issue body line 1: own reference owner/home" in refusal


def test_an_own_reference_in_text_passes_for_a_private_project(home, user):
    home = replace(home, leak_own=("home-secret",))

    leak_check_text({"issue body": "part of home-secret\n"}, home, public=False, user_home=user)


@VISIBILITY
def test_text_naming_only_registered_paths_registered_repos_and_third_parties_passes(
    home, user, public
):
    text = f"{TILDE}/dev/proto/src, {user}/work/site, owner/proto#4 and astral-sh/uv\n"

    leak_check_text({"PR body": text}, home, public=public, user_home=user)
