"""Fixtures shared by the ``kaizen`` CLI tests."""

from collections.abc import Callable
from pathlib import Path

import pytest

from kaizen.shared.cli import main
from kaizen.shared.common import Runner
from kaizen.tests.ticket_shell import cli_home

Kaizen = Callable[[list[str], Runner], int]


@pytest.fixture
def kaizen(tmp_path: Path) -> Kaizen:
    """Runs ``main`` from the fixture home ``cli_home`` builds, with no ``KAIZEN_HOME`` set."""
    home = cli_home(tmp_path)

    def run_kaizen(argv: list[str], run: Runner) -> int:
        return main(argv, run=run, cwd=home, env={})

    return run_kaizen
