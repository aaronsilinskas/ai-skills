"""Tests for ``kaizen hook test-names``, run through the CLI from a fixture home on test files
written to a temporary directory."""

from pathlib import Path

import pytest

from kaizen.tests.ticket_shell import Shell


def _file(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / "files" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


@pytest.mark.parametrize(
    "name",
    [
        "test",
        "test_",
        "test_parse",
        "test_works",
        "test_it",
        "test_basic",
        "test_it_works",
        "test_happy_path",
        "test_basic_ok",
        "test__parse",
    ],
)
def test_a_test_named_after_one_word_or_only_vacuous_words_is_refused(
    tmp_path, kaizen, capsys, name
):
    path = _file(tmp_path, "test_a.py", f"import os\n\n\ndef {name}():\n    assert os\n")

    assert kaizen(["hook", "test-names", path], Shell({})) == 1

    assert f"{path}:4: vacuous test name {name}" in capsys.readouterr().err


@pytest.mark.parametrize(
    "source",
    [
        "def test_parse_rejects_an_empty_header():\n    pass\n",
        "def test_cli_works_offline():\n    pass\n",
        "def helper():\n    pass\n",
        "def testing():\n    pass\n",
        "def _test():\n    pass\n",
        'DOC = """\ndef test_parse():\n"""\n',
        "# def test_parse():\n",
    ],
)
def test_names_that_state_a_guarantee_and_other_text_pass(tmp_path, kaizen, capsys, source):
    path = _file(tmp_path, "test_a.py", source)

    assert kaizen(["hook", "test-names", path], Shell({})) == 0, capsys.readouterr().err


def test_methods_and_async_tests_are_checked(tmp_path, kaizen, capsys):
    source = (
        "class TestParser:\n    def test_basic(self):\n        pass\n\n\n"
        "async def test_it():\n    pass\n"
    )
    path = _file(tmp_path, "test_a.py", source)

    assert kaizen(["hook", "test-names", path], Shell({})) == 1

    err = capsys.readouterr().err
    assert f"{path}:2: vacuous test name test_basic" in err
    assert f"{path}:6: vacuous test name test_it" in err


@pytest.mark.parametrize("name", ["a_test.py", "pkg/test_a.py"])
def test_both_pytest_test_file_patterns_are_checked(tmp_path, kaizen, name):
    path = _file(tmp_path, name, "def test_works():\n    pass\n")

    assert kaizen(["hook", "test-names", path], Shell({})) == 1


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("helpers.py", "def test_works():\n    pass\n"),
        ("conftest.py", "def test_works():\n    pass\n"),
        ("test_a.txt", "def test_works():\n"),
        ("test_a.py", "def test_works(:\n"),
    ],
)
def test_files_that_are_no_pytest_test_files_or_won_t_parse_are_skipped(
    tmp_path, kaizen, capsys, name, text
):
    path = _file(tmp_path, name, text)

    assert kaizen(["hook", "test-names", path], Shell({})) == 0

    assert "Traceback" not in capsys.readouterr().err


def test_the_test_names_refusal_names_the_test_quality_skill(tmp_path, kaizen, capsys):
    path = _file(tmp_path, "test_a.py", "def test_works():\n    pass\n")

    kaizen(["hook", "test-names", path], Shell({}))

    assert "test-quality" in capsys.readouterr().err


KAIZEN = Path(__file__).resolve().parents[3]
"""kaizen's own folder."""


def test_kaizen_s_own_tests_pass_the_test_names_hook(kaizen, capsys):
    tests = [str(path) for path in (KAIZEN / "src").rglob("test_*.py")]

    assert kaizen(["hook", "test-names", *tests], Shell({})) == 0, capsys.readouterr().err
