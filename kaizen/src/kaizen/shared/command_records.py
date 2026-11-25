"""The command records: each command module sets one as its parser's ``command`` default, and
its type says what ``shared/cli.py`` calls the handler with.

A handler that returns ``None`` has succeeded, and one that returns an int exits with it; it fails
by raising, which the CLI reports.
"""

from argparse import Namespace
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from kaizen.shared.common import Runner
from kaizen.shared.home import Home
from kaizen.shared.version import Install


@dataclass(frozen=True)
class HomeCommand:
    """An ordinary command: run in the home found for it, after the synced version check."""

    handler: Callable[[Namespace, Runner, Home], int | None]


@dataclass(frozen=True)
class InstallCommand:
    """A command also passed the running ``Install``.
    ``records_version`` says whether a run records the running version as the home's synced
    version, which the synced version check needs to know."""

    handler: Callable[[Namespace, Runner, Home, Install], int | None]
    records_version: Callable[[Namespace], bool]


@dataclass(frozen=True)
class HomelessCommand:
    """A command that needs no home: no home is looked for and no synced version checked, and it
    gets the start directory and the environment instead."""

    handler: Callable[[Namespace, Runner, Path, Mapping[str, str], Install], int | None]


CommandRecord = HomeCommand | InstallCommand | HomelessCommand
