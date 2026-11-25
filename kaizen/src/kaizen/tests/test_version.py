"""Tests for the running version: read from the package metadata, which the build works out from
the ``kaizen-v*`` git tags (``test_version_scheme_git.py`` covers that)."""

from importlib.metadata import version

import kaizen


def test_the_running_version_is_the_installed_packages():
    assert kaizen.__version__ == version("kaizen-kit")
