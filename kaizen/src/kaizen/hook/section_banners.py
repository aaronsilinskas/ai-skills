"""``kaizen hook section-banners``: refuse banner comments, which section a file by hand where a
smaller module or a function would."""

import argparse
import re
from collections.abc import Iterator

from kaizen.hook.comments import LANGUAGES, Comment, comment_findings
from kaizen.hook.common import add_files_argument, refuse
from kaizen.shared.common import Runner, Subparsers
from kaizen.shared.home import Home

_RULE = re.compile(r"[-=]{10,}")
"""A comment that is only a rule of ten or more ``-`` or ``=``."""
_TITLED = re.compile(r"[-=]{3,}\s*[^-=\s].*?\s*[-=]{3,}")
"""A one-line titled banner, such as ``--- name ---``."""

_FIX = "delete the banner; if the file needs sections, split it into modules or functions"


def _banner(comment: Comment) -> Iterator[str]:
    # The whole text is tried as well as the body, since a ``--`` prefix is itself part of a rule.
    if any(
        pattern.fullmatch(text)
        for pattern in (_RULE, _TITLED)
        for text in (comment.body, comment.text)
    ):
        yield comment.text


def add_parser(subparsers: Subparsers) -> None:
    parser = subparsers.add_parser(
        "section-banners",
        help="refuse banner comments",
        description=(
            "Refuse each comment in the files given that is only a rule of ten or more - or =, "
            "or a titled one-line banner such as `--- name ---`, naming its file and line. Only "
            f"comments are read, never strings or code: {LANGUAGES}"
        ),
    )
    add_files_argument(parser)
    parser.set_defaults(handler=_command)


def _command(args: argparse.Namespace, run: Runner, home: Home) -> None:
    refuse("section-banners", comment_findings(args.files, "section banner", _banner), _FIX)
