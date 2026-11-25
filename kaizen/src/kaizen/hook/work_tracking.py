"""``kaizen hook work-tracking``: refuse comments that point at tracked work, which reads as stale
once that work lands; a full ``owner/repo#N`` reference or an issue URL stays allowed."""

import argparse
import re
from collections.abc import Iterator

from kaizen.hook.comments import LANGUAGES, Comment, comment_findings
from kaizen.hook.common import add_files_argument, refuse
from kaizen.shared.common import Runner, Subparsers
from kaizen.shared.home import Home

_REFERENCE = re.compile(
    r"\blater tickets?\b|\bslice\s+\d+\b|\bissue\s+#?\d+\b|(?<![\w/.-])#\d+\b", re.IGNORECASE
)
""""later ticket", "slice N", "issue N" and a bare issue number; ``owner/repo#N`` and an issue
URL's ``/issues/N`` don't match."""

_FIX = (
    "say what the code does now, and keep the history in the commit or PR; where a link is "
    "needed, use owner/repo#N or the issue's URL"
)


def _references(comment: Comment) -> Iterator[str]:
    # The text, not the body, so a Python comment that opens with a number keeps its hash.
    for match in _REFERENCE.finditer(comment.text):
        yield match.group()


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "work-tracking",
        help="refuse comments that name a ticket, slice or bare issue number",
        description=(
            'Refuse each comment in the files given that says "later ticket", "slice N", '
            '"issue N" or a bare issue number such as #12, naming its file, line and match. '
            "owner/repo#N and issue URLs pass. Only "
            f"comments are read, never strings or code: {LANGUAGES}"
        ),
    )
    add_files_argument(parser)
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    refuse(
        "work-tracking", comment_findings(args.files, "work-tracking reference", _references), _FIX
    )
