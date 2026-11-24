"""Tests for the running version: read from the package metadata, set only in pyproject.toml."""

import tomllib
from pathlib import Path

import kaizen


def test_the_running_version_is_the_one_pyproject_declares():
    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]

    assert kaizen.__version__ == declared
