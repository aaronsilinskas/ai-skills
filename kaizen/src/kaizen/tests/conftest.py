"""Fixtures shared by the ``kaizen`` CLI tests."""

from collections.abc import Callable
from pathlib import Path

import pytest

from kaizen.shared.cli import main
from kaizen.shared.common import Runner
from kaizen.tests.ticket_shell import RELEASE, cli_home

Kaizen = Callable[[list[str], Runner], int]


@pytest.fixture(autouse=True)
def runs_as_a_release(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs ``main`` as the release ``RELEASE`` when a test passes no version, so no test depends
    on the checkout's own version."""
    monkeypatch.setattr("kaizen.shared.cli.__version__", RELEASE)


@pytest.fixture
def kaizen(tmp_path: Path) -> Kaizen:
    """Runs ``main`` from the fixture home ``cli_home`` builds, with no ``KAIZEN_HOME`` set."""
    home = cli_home(tmp_path)

    def run_kaizen(argv: list[str], run: Runner) -> int:
        return main(argv, run=run, cwd=home, env={})

    return run_kaizen
