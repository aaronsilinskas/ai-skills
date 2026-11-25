"""Tests for ``scripts/release_check.py``, the release workflow's checks. Each wheel is a zip
built in a temporary directory."""

import zipfile
from pathlib import Path

import pytest

from kaizen.tests.release_script import release_check


def _fake_wheel(tmp_path: Path, version: str) -> str:
    """A wheel whose metadata says *version*."""
    path = tmp_path / f"kaizen_kit-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as wheel:
        wheel.writestr(
            f"kaizen_kit-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: kaizen-kit\nVersion: {version}\n",
        )
    return str(path)


def test_a_tag_matching_the_built_wheels_version_passes(tmp_path):
    assert release_check.version_problems("kaizen-v1.2.3", _fake_wheel(tmp_path, "1.2.3")) == []


def test_a_tag_whose_version_differs_from_the_built_wheel_is_refused_naming_both(tmp_path):
    wheel = _fake_wheel(tmp_path, "1.2.4.dev1+gabc1234")

    assert release_check.version_problems("kaizen-v1.2.3", wheel) == [
        "tag 'kaizen-v1.2.3' is version 1.2.3, but the built wheel is 1.2.4.dev1+gabc1234"
    ]


def test_a_tag_without_the_prefix_is_refused(tmp_path):
    assert release_check.version_problems("v1.2.3", _fake_wheel(tmp_path, "1.2.3")) == [
        "tag 'v1.2.3' does not start with 'kaizen-v'"
    ]


@pytest.mark.parametrize("argv", [["version", "kaizen-v1.2.3"], ["wheel"], ["other", "x"], []])
def test_a_check_with_the_wrong_arguments_is_a_usage_error(argv):
    assert release_check.main(argv) == 2


@pytest.mark.parametrize(
    "name",
    [
        "kaizen/tests/ticket_shell.py",
        "kaizen/tests/__init__.py",
        "kaizen/conftest.py",
        "kaizen/shared/test_home.py",
        "kaizen/shared/home_test.py",
    ],
)
def test_test_files_are_recognised(name):
    assert release_check.is_test_file(name)


@pytest.mark.parametrize(
    "name",
    [
        "kaizen/shared/home.py",
        "kaizen/shared/templates/test_plan.md",
        "kaizen/shared/latest.py",
        "kaizen_kit-0.1.0.dist-info/METADATA",
    ],
)
def test_other_files_are_not_test_files(name):
    assert not release_check.is_test_file(name)


def _templates(tmp_path: Path) -> Path:
    """A templates folder holding one top-level template and one nested a folder down."""
    templates = tmp_path / "templates"
    (templates / "nested").mkdir(parents=True)
    (templates / "workflows.md").write_text("top\n")
    (templates / "nested" / "deep.md").write_text("nested\n")
    return templates


def _wheel(tmp_path: Path, names: list[str]) -> str:
    path = tmp_path / "kaizen_kit-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as wheel:
        for name in names:
            wheel.writestr(name, "")
    return str(path)


PACKAGE = ["kaizen/__init__.py", "kaizen/shared/cli.py"]
SHIPPED = ["kaizen/shared/templates/workflows.md", "kaizen/shared/templates/nested/deep.md"]


@pytest.fixture
def templates(tmp_path, monkeypatch):
    monkeypatch.setattr(release_check, "TEMPLATES", _templates(tmp_path))


def test_a_wheel_with_every_template_and_no_tests_passes(tmp_path, templates):
    assert release_check.check_wheel(_wheel(tmp_path, [*PACKAGE, *SHIPPED])) == []


def test_a_wheel_holding_a_test_file_is_refused_naming_it(tmp_path, templates):
    wheel = _wheel(tmp_path, [*PACKAGE, *SHIPPED, "kaizen/tests/test_cli.py"])

    assert release_check.check_wheel(wheel) == ["test file in the wheel: kaizen/tests/test_cli.py"]


def test_a_wheel_missing_a_nested_template_is_refused_naming_it(tmp_path, templates):
    wheel = _wheel(tmp_path, [*PACKAGE, SHIPPED[0]])

    assert release_check.check_wheel(wheel) == ["template missing from the wheel: nested/deep.md"]


def test_the_wheel_check_refuses_when_no_template_is_found(tmp_path, monkeypatch):
    monkeypatch.setattr(release_check, "TEMPLATES", tmp_path / "empty")

    assert release_check.wheel_problems(PACKAGE) == [f"no templates found in {tmp_path / 'empty'}"]
