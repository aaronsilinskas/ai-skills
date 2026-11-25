#!/usr/bin/env python3
"""home_leak_scan.py: refuse a path under a user's home directory in the lines a change adds.

    python3 scripts/home_leak_scan.py <base> <head>
    python3 scripts/home_leak_scan.py --branch

Scans only the lines that <head> adds since its merge base with <base> (git diff base...head),
never removed or unchanged ones. With --branch, <base> is origin's default branch (what
origin/HEAD names, else origin/main) and <head> is HEAD; it skips, exiting 3 with a SKIP line,
when HEAD adds nothing since that branch, or when there is no such branch or merge base. A home path is a tilde path with more after it, a user name after the
tilde included, or an absolute path under a macOS, Linux or Windows home directory that names a
user.
Placeholders such as a ``<name>`` or ``$USER`` segment name no user and pass, and so does the
macOS ``Shared`` folder, which is no user's home.

It needs no home's facts and reads nothing outside the repository, so CI can run it on any
runner. Exits 0 when clean, 1 listing each file, line and path found, 2 on a usage or git error,
3 when --branch skips.
"""

import re
import subprocess
import sys
from typing import NamedTuple

# What may come just before a tilde path: the start of a word, or a ``/`` or ``@`` it is glued to.
# A tilde after anything else, as in a regex such as ``/~(.*?)~/g``, names no path.
_TILDE_START = r"""\s'"`(\[{<=:,/@"""
_PATH_END = r"""\s'"`<>()\[\]{},;:*|\\"""
_HOME_PATH = re.compile(
    rf"(?<![^{_TILDE_START}])~[\w.-]*/[^{_PATH_END}]*"
    rf"|(?<![\w.-])/(?:Users/(?!Shared\b)|home/)\w[^{_PATH_END}]*"
    r"|(?i:\b[a-z]:(?:\\{1,2}|/)users(?:\\{1,2}|/)\w+)"
)
SKIPPED = 3
_FALLBACK_DEFAULT = "origin/main"
_HUNK = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class Finding(NamedTuple):
    file: str
    line: int
    path: str


def _home_paths(text: str) -> list[str]:
    paths = (match.rstrip(".…") for match in _HOME_PATH.findall(text))
    return [path for path in paths if path.rstrip("/") != "~"]


def scan(diff: str) -> list[Finding]:
    """Each home path in the added lines of the unified *diff*, with its file and line."""
    found: list[Finding] = []
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


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def _branch_base() -> tuple[str | None, str]:
    """The base for --branch, or None and why the scan skips."""
    origin_head = _git("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    base = origin_head.stdout.strip() if origin_head.returncode == 0 else _FALLBACK_DEFAULT
    if _git("rev-parse", "--verify", "--quiet", f"refs/remotes/{base}").returncode != 0:
        return None, f"no {base} to compare against (no remote, or not fetched)"
    if _git("merge-base", base, "HEAD").returncode != 0:
        return None, f"no merge base between {base} and HEAD (a shallow clone?)"
    if _git("merge-base", "--is-ancestor", "HEAD", base).returncode == 0:
        return None, f"HEAD adds nothing since {base}"
    return base, ""


def main(argv: list[str]) -> int:
    if argv == ["--branch"]:
        branch_base, why = _branch_base()
        if branch_base is None:
            print(f"SKIP: {why}")
            return SKIPPED
        argv = [branch_base, "HEAD"]
    if len(argv) != 2:
        print("usage: home_leak_scan.py <base> <head> | --branch", file=sys.stderr)
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
