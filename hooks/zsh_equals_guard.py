#!/usr/bin/env python3
"""PreToolUse hook: escape Bash words that zsh would expand as `=word`.

The fixed command goes back through `updatedInput` with no permissionDecision,
so the normal permission flow still judges it. When an unbalanced quote leaves
the words uncertain, the hook exits 2 instead, which blocks the call and shows
stderr to the agent.
"""

from __future__ import annotations

import json
import re
import sys

HEREDOC_START = re.compile(r"(?<!<)<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
QUOTED = re.compile(r"\\.|\$'(?:\\.|[^'\\])*'|'[^']*'|\"(?:\\.|[^\"\\])*\"", re.S)
DOUBLE_BRACKET = re.compile(r"\[\[.*?\]\]", re.S)
ARITHMETIC = re.compile(r"\(\(.*?\)\)", re.S)
WORD_START = r"(?:^|(?<=[\s;&|()<>]))"
COMMENT = re.compile(WORD_START + r"#.*$", re.M)
EQUALS_WORD = re.compile(WORD_START + r"=[^\s=;&|)]*=*[^\s;&|)]*")

# Masked text keeps every offset, so a match in it is a position in the command.
# The filler is a word character, so it never starts or ends a word.
FILLER = "x"


def fill(match: re.Match[str]) -> str:
    return re.sub(r"[^\n]", FILLER, match.group(0))


def heredoc_delimiters(line: str) -> list[str]:
    quoted = [match.span() for match in QUOTED.finditer(line)]
    return [
        match.group(2)
        for match in HEREDOC_START.finditer(line)
        if not any(start <= match.start() < end for start, end in quoted)
    ]


def mask_heredoc_bodies(command: str) -> str:
    kept = []
    pending: list[str] = []
    for line in command.split("\n"):
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            kept.append(FILLER * len(line))
            continue
        kept.append(line)
        pending.extend(heredoc_delimiters(line))
    return "\n".join(kept)


def mask_unexpanded_text(command: str) -> str:
    """Hide the parts of *command* where zsh does no `=` expansion."""
    text = mask_heredoc_bodies(command)
    for pattern in (QUOTED, DOUBLE_BRACKET, ARITHMETIC, COMMENT):
        text = pattern.sub(fill, text)
    return text


def has_unbalanced_quote(masked: str) -> bool:
    return "'" in masked or '"' in masked


def equals_word_starts(masked: str) -> list[int]:
    return [match.start() for match in EQUALS_WORD.finditer(masked) if match.group(0) != "="]


def escape_at(command: str, starts: list[int]) -> str:
    for start in reversed(starts):
        command = command[:start] + "\\" + command[start:]
    return command


def main() -> int:
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input", {})
    command = tool_input.get("command", "")
    masked = mask_unexpanded_text(command)
    starts = equals_word_starts(masked)
    if not starts:
        return 0
    if has_unbalanced_quote(masked):
        words = [EQUALS_WORD.match(masked, start).group(0) for start in starts]
        print(
            "zsh expands an unquoted word starting with '=' to a command path "
            f"(found: {', '.join(repr(w) for w in words)}), and an unbalanced quote "
            "kept this hook from escaping it. Quote it, e.g. echo '=====', "
            "or use [[ a == b ]] instead of [ a == b ].",
            file=sys.stderr,
        )
        return 2
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {**tool_input, "command": escape_at(command, starts)},
            "additionalContext": (
                "A hook escaped the leading '=' of a word in this command, since zsh "
                "expands an unquoted =word to a command path. Quote such words yourself."
            ),
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
