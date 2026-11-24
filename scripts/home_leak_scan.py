#!/usr/bin/env python3
"""home_leak_scan.py: refuse a path under a user's home directory in the lines a change adds.

    python3 scripts/home_leak_scan.py <base> <head>

Scans only the lines that <head> adds since its merge base with <base> (git diff base...head),
never removed or unchanged ones. A home path is a tilde path with more after it, or an absolute
path under a macOS, Linux or Windows home directory that names a user. Placeholders such as a
``<name>`` or ``$USER`` segment name no user and pass.

It needs no home's facts and reads nothing outside the repository, so CI can run it on any
runner. Exits 0 when clean, 1 listing each file, line and path found, 2 on a usage or git error.
"""

import re
import subprocess
import sys
from typing import List, NamedTuple

# What may come just before a tilde path: the start of a word, or a ``/`` or ``@`` it is glued to.
# A tilde after anything else, as in a regex such as ``/~(.*?)~/g``, names no path.
_TILDE_START = r"""\s'"`(\[{<=:,/@"""
_PATH_END = r"""\s'"`<>()\[\]{},;:*|\\"""
_HOME_PATH = re.compile(
    rf"(?<![^{_TILDE_START}])~/[^{_PATH_END}]*"
    rf"|(?<![\w.-])/(?:Users|home)/\w[^{_PATH_END}]*"
    r"|\b[A-Za-z]:\\Users\\\w+"
)
_HUNK = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class Finding(NamedTuple):
    file: str
    line: int
    path: str


def _home_paths(text: str) -> List[str]:
    # Prose ends a path with a full stop or an ellipsis; a bare tilde-slash names no file.
    paths = (match.rstrip(".…") for match in _HOME_PATH.findall(text))
    return [path for path in paths if path.rstrip("/") != "~"]


def scan(diff: str) -> List[Finding]:
    """Each home path in the added lines of the unified *diff*, with its file and line."""
    found: List[Finding] = []
    file, number, in_hunk = "", 0, False
    for line in diff.split("\n"):
        if line.startswith("diff --git "):
            in_hunk = False
        elif not in_hunk and line.startswith("+++ "):
            # git ends the name with a tab when it holds a space.
            file = line[4:].rstrip("\t").strip('"')
            file = file[2:] if file.startswith("b/") else file
        elif hunk := _HUNK.match(line):
            number, in_hunk = int(hunk.group(1)), True
        elif in_hunk and line.startswith("+"):
            found.extend(Finding(file, number, path) for path in _home_paths(line[1:]))
            number += 1
        elif in_hunk and line.startswith(" "):
            number += 1
    return found


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("usage: home_leak_scan.py <base> <head>", file=sys.stderr)
        return 2
    base, head = argv
    result = subprocess.run(
        ["git", "diff", "--no-color", "--no-ext-diff", "--unified=0",
         "--src-prefix=a/", "--dst-prefix=b/", f"{base}...{head}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"git diff {base}...{head} failed:\n{result.stderr.strip()}", file=sys.stderr)
        return 2
    found = scan(result.stdout)
    if not found:
        print(f"no path under a home directory in the lines {head} adds since {base}")
        return 0
    print("path under a home directory in added lines; remove it or write a placeholder:")
    for finding in found:
        print(f"  {finding.file}:{finding.line}: {finding.path}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
