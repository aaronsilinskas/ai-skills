#!/usr/bin/env python3
"""PreToolUse hook: block `gh issue view ... --comments` without `--json`.

Off a TTY, `gh issue view <n> --comments` prints only the comments, so an issue
with none reads as empty and the agent misses its body. Each command segment
(split on `;`, `&&`, `||`, `|` and newlines) is checked on its own.
Exit 2 blocks the call and shows stderr to the agent.
"""

import json
import re
import sys

SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n]")
ISSUE_VIEW = re.compile(r"\bgh\b.*\bissue\s+view\b")


def offending_segments(command: str) -> list:
    return [
        segment.strip()
        for segment in SEGMENT_SPLIT.split(command)
        if ISSUE_VIEW.search(segment)
        and re.search(r"(?<!\S)--comments\b", segment)
        and not re.search(r"(?<!\S)--json\b", segment)
    ]


def main() -> int:
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")
    segments = offending_segments(command)
    if not segments:
        return 0
    print(
        "Off a TTY, `gh issue view --comments` prints only the comments, so an issue "
        f"with none looks empty (found: {segments[0]!r}). "
        "Use `gh issue view <n> --json title,body,labels,comments` instead.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
