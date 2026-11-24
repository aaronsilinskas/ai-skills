"""The **synced version** check: how the running ``kaizen`` compares with the release that last
synced a home, and the latest release on PyPI that ``kaizen home sync`` names.

The running version and the lookup are passed into ``kaizen``'s ``main``; no command reads either
for itself.
"""

import json
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

from kaizen.shared.common import RefusalError, Say

LatestRelease = Callable[[], str | None]
"""Looks up the latest release of ``kaizen-kit``: its version, or ``None`` when the lookup
failed."""


@dataclass(frozen=True)
class Install:
    """The running ``kaizen``: its version, and how to look up the latest release, which only
    ``kaizen home sync`` does."""

    version: str
    latest: LatestRelease


UPGRADE = "uv tool upgrade kaizen-kit"
_PYPI = "https://pypi.org/pypi/kaizen-kit/json"
_TIMEOUT = 3
"""Seconds before the lookup gives up, so ``home sync`` never hangs offline."""
_TRIPLE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


class Version(NamedTuple):
    """A release version ``X.Y.Z``, which compares as an integer triple."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: str) -> "Version | None":
        """*text* as a ``Version``, or ``None`` when it is not ``X.Y.Z``."""
        match = _TRIPLE.fullmatch(text)
        return None if match is None else cls(int(match[1]), int(match[2]), int(match[3]))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def recordable_version(running: str, command: str) -> Version:
    """The *running* version, which *command* (``home init`` or ``home sync``) records as a home's
    synced version; refuses one that is not ``X.Y.Z``, such as a local build's, which no home's CI
    could install."""
    version = Version.parse(running)
    if version is None:
        raise RefusalError(
            f"{command}: kaizen's version {running} is not X.Y.Z, so it can't be recorded"
            " as the home's synced version",
            "install a release of kaizen (`uv tool install --force kaizen-kit`), then run"
            f" `kaizen {command}` again",
        )
    return version


def check_synced_version(
    running: str, synced: Version | None, marker: str, warn: Say, *, syncing: bool = False
) -> None:
    """Compares the *running* version with the *synced* version a home's *marker* records:
    refuses on an older install, and *warn*s once on a running version that is not ``X.Y.Z``, on
    a newer install and on a home that records none. With *syncing*, for the command that
    records the version, it only refuses, since that command is the fix the warnings name."""
    ours = Version.parse(running)
    if ours is None:
        warn(
            f"kaizen's version {running} is not X.Y.Z, such as a local build's, so this home's"
            " synced version is not compared with it"
        )
        return
    if synced is None:
        if not syncing:
            warn(f"this home's {marker} records no synced version: run `kaizen home sync`")
        return
    if ours < synced:
        raise RefusalError(
            f"kaizen {running} is older than this home's synced version {synced}", UPGRADE
        )
    if ours > synced and not syncing:
        warn(
            f"kaizen {running} is newer than this home's synced version {synced}:"
            " run `kaizen home sync`"
        )


def newer_release(running: str, latest: LatestRelease) -> str | None:
    """The line naming the latest release and the upgrade command when it is newer than
    *running*; ``None`` otherwise, or when the lookup fails."""
    found = latest()
    ours, theirs = Version.parse(running), None if found is None else Version.parse(found)
    if ours is None or theirs is None or theirs <= ours:
        return None
    return f"kaizen {found} is out (this is {running}): run `{UPGRADE}`"


def latest_on_pypi() -> str | None:
    """The latest ``kaizen-kit`` version on PyPI's JSON API, or ``None`` on any failure."""
    try:
        with urllib.request.urlopen(_PYPI, timeout=_TIMEOUT) as response:
            version = json.load(response)["info"]["version"]
    except Exception:  # offline, a proxy, an error status or an odd reply: skip silently
        return None
    return version if isinstance(version, str) else None
