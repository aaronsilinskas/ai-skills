"""``kaizen hook doc-paths``: refuse a repo path in the agent docs that names nothing tracked, such
as a folder deleted while the docs still send readers to it. It reads the whole index, since a
commit that deletes the folder stages none of the docs that name it."""

import argparse
import posixpath
import re
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from kaizen.hook.common import Finding, add_files_argument, read_text, refuse
from kaizen.hook.markdown import CODE_SPAN, is_markdown, prose_lines
from kaizen.shared.command_records import HomeCommand
from kaizen.shared.common import Runner, Subparsers
from kaizen.shared.home import Home
from kaizen.shared.synced import SYNCED_LINE

_SEGMENT = r"(?:[\w-][\w.-]*|\.[\w-][\w.-]*)"
"""A folder or file name: no glob, placeholder or other punctuation, and never only dots."""
_FILE_NAME = r"[\w-][\w.-]*\.[A-Za-z]\w*"
"""A file name with an extension, such as ``cli.py``."""
_PATH = re.compile(rf"(?P<up>(?:\.\.?/)*)(?P<rest>(?:{_SEGMENT}/)*(?:{_SEGMENT}/|{_FILE_NAME}))")
"""A repo path: a folder ending in ``/`` or a file with an extension, optionally behind ``./`` or
``../``. A path holds a ``/``, so a bare file name, a branch such as ``origin/main`` and a repo
such as ``owner/repo`` are not paths."""

_DOC_NAMES = ("AGENTS.md", "GLOSSARY.md")
_RECORD_FOLDERS = {"adr", "history", "research", "wiki"}
"""Folders of dated records, which name paths as they were when written."""

_FIX = (
    "point the doc at the path that exists now, or drop the reference; when it names a path "
    "outside this repo or one not made yet, pass it with --allow in the hook's args"
)


def is_agent_doc(path: str) -> bool:
    """Whether the tracked *path* is one the hook reads: an ``AGENTS.md`` or ``GLOSSARY.md``, or
    Markdown under a ``docs/`` folder, at any depth, outside a folder of dated records."""
    folders = PurePosixPath(path).parent.parts
    if _RECORD_FOLDERS.intersection(folders):
        return False
    return PurePosixPath(path).name in _DOC_NAMES or ("docs" in folders and is_markdown(path))


class _Tracked:
    """The tracked files and folders, by full path and by every trailing part of it, so a path
    written relative to its doc or to a folder the doc names still matches."""

    def __init__(self, files: list[str]) -> None:
        self.paths: set[str] = set()
        self.endings: set[str] = set()
        for name in files:
            parts = name.split("/")
            for end in range(1, len(parts) + 1):
                path = "/".join(parts[:end])
                self.paths.add(path)
                self.endings.update("/".join(parts[start:end]) for start in range(end))

    def holds(self, doc: str, path: re.Match[str]) -> bool:
        """Whether the repo *path* the *doc* names is tracked; one that resolves outside the
        repo is not this hook's to judge, so it is taken as tracked."""
        if not path.group("up"):
            return path.group("rest").rstrip("/") in self.endings
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(doc), path.group()))
        return resolved == ".." or resolved.startswith("../") or resolved in self.paths


def _allowed(span: str, allow: list[str]) -> bool:
    return any(span == path or (path.endswith("/") and span.startswith(path)) for path in allow)


def doc_path_findings(root: Path, files: list[str], allow: list[str]) -> Iterator[Finding]:
    """Each repo path in the agent docs among the tracked *files* under *root* that names no
    tracked file or folder, nor one in *allow*."""
    tracked = _Tracked(files)
    for doc in filter(is_agent_doc, files):
        text = read_text(str(root / doc))
        if text is None or text.startswith(SYNCED_LINE):
            continue
        for number, line in prose_lines(text):
            for span in CODE_SPAN.findall(line):
                path = _PATH.fullmatch(span) if "/" in span else None
                if path and not _allowed(span, allow) and not tracked.holds(doc, path):
                    yield Finding(doc, number, "missing doc path", span)


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "doc-paths",
        help="refuse a backticked repo path in the agent docs that names nothing tracked",
        description=(
            "Refuse each backticked repo path in the agent docs that names no tracked file or "
            "folder of tracked files, naming its doc, line and path. The agent docs are every "
            "tracked AGENTS.md and GLOSSARY.md, and Markdown under a docs/ folder, at any depth; "
            "folders named adr, history, research or wiki hold dated records and are skipped, "
            "as are synced files. A repo path is a single-backtick code span outside fenced "
            "code that holds a / and is only folder names ending in /, or folder names and a "
            "file name with an extension, such as `docs/adr/` or `src/app/cli.py`: globs, "
            "<placeholders>, spaces, URLs, absolute and ~ paths, branches such as origin/main "
            "and repos such as owner/repo are not. It names a tracked path when some tracked "
            "path ends with it, or, behind ./ or ../, when it resolves from the doc's folder. It "
            "reads the whole index, so any file names pre-commit passes are ignored."
        ),
    )
    add_files_argument(parser)
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "a path the docs may name though it is not tracked, such as one in another repo or "
            "a folder made later; one ending in / allows the paths under it too (repeatable)"
        ),
    )
    parser.set_defaults(command=HomeCommand(_command))


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    root = Path(run(["git", "rev-parse", "--show-toplevel"]).strip())
    files = [name for name in run(["git", "-C", str(root), "ls-files", "-z"]).split("\0") if name]
    refuse("doc-paths", doc_path_findings(root, files, args.allow), _FIX)
