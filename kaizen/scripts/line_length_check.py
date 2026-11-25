"""line_length_check.py: refuses any prose line over 200 characters in the synced files, as a
home renders them, run by kaizen's check from kaizen/.

    uv run python scripts/line_length_check.py

Homes commonly hold their agent docs to 200 characters a line, and a home may not edit a synced
file to fix one, so kaizen's templates must keep to it. It renders every synced file for a
generic home, header line included, and names each line over the limit by its rendered path,
line and length. Lines in fenced code blocks and table rows are exempt, since they can't be
wrapped. Exits 1 when it finds one.
"""

import re
import sys
from collections.abc import Mapping
from pathlib import Path

from kaizen.shared.home import REGISTRY, Home
from kaizen.shared.synced import render
from kaizen.shared.version import Version

LIMIT = 200
_FENCE = re.compile(r"\s*(```|~~~)")
_SHOWN = 60
"""How many of a long line's characters its problem quotes, so the line can be searched for."""


def problems(rendered: Mapping[str, str]) -> list[str]:
    """One problem per prose line over the limit in *rendered*, synced files' text keyed by
    their paths."""
    return [
        f"{path}:{number}: {len(line)} characters, over {LIMIT}: {line[:_SHOWN]}..."
        for path, text in rendered.items()
        for number, line in _prose_lines(text)
        if len(line) > LIMIT
    ]


def _prose_lines(text: str) -> list[tuple[int, str]]:
    """*text*'s numbered lines, leaving out fenced code blocks and table rows."""
    prose = []
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and not line.lstrip().startswith("|"):
            prose.append((number, line))
    return prose


def rendered_synced_files() -> dict[str, str]:
    """Every synced file as a generic home renders it, for a release with a wide version."""
    root = Path("/home")
    return render(Home(root=root, registry=root / REGISTRY, leak_own=()), Version(99, 99, 99))


def main() -> int:
    found = problems(rendered_synced_files())
    for problem in found:
        print(f"refused: {problem}", file=sys.stderr)
    if found:
        return 1
    print(f"no synced file has a prose line over {LIMIT} characters")
    return 0


if __name__ == "__main__":
    sys.exit(main())
