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


def triple(version: str) -> tuple[int, int, int] | None:
    """*version* as an integer triple, or ``None`` when it is not ``X.Y.Z``."""
    match = _TRIPLE.fullmatch(version)
    return None if match is None else (int(match[1]), int(match[2]), int(match[3]))


def check_synced_version(running: str, synced: str | None, marker: str, warn: Say) -> None:
    """Compares the *running* version with the *synced* version a home's *marker* records:
    *warn*s once on a newer install, on a home that records none and on a running version that
    is not ``X.Y.Z``, and refuses on an older install."""
    ours = triple(running)
    if ours is None:
        warn(
            f"kaizen's version {running} is not X.Y.Z, such as a local build's, so this home's"
            " synced version is not compared with it"
        )
        return
    if synced is None:
        warn(f"this home's {marker} records no synced version: run `kaizen home sync`")
        return
    theirs = triple(synced)
    assert theirs is not None, "the home module refuses a synced version that is not X.Y.Z"
    if ours > theirs:
        warn(
            f"kaizen {running} is newer than this home's synced version {synced}:"
            " run `kaizen home sync`"
        )
    elif ours < theirs:
        raise RefusalError(
            f"kaizen {running} is older than this home's synced version {synced}", UPGRADE
        )


def newer_release(running: str, latest: LatestRelease) -> str | None:
    """The line naming the latest release and the upgrade command when it is newer than
    *running*; ``None`` otherwise, or when the lookup fails."""
    found = latest()
    ours, theirs = triple(running), None if found is None else triple(found)
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
