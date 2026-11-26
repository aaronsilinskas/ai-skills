#!/usr/bin/env python3
"""PreToolUse hook: escape Bash words that zsh would expand as `=word`.

zsh expands an unquoted `=word` to the path of command `word` (EQUALS option),
so `echo =====` fails with "==== not found" and `[ a == b ]` fails the same way.
The hook puts a backslash before each such word's leading `=`, which turns off
only that expansion, and hands the command back through `updatedInput`.
It sets no permissionDecision, so the rewritten command still goes through the
normal permission flow. Quoted text, heredoc bodies, `[[ ... ]]` tests and
comments are ignored. When an unbalanced quote leaves the words uncertain, it
exits 2 instead, which blocks the call and shows stderr to the agent.
"""

import json
import re
import sys

HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
QUOTED = re.compile(r"\\.|\$'(?:\\.|[^'\\])*'|'[^']*'|\"(?:\\.|[^\"\\])*\"", re.S)
DOUBLE_BRACKET = re.compile(r"\[\[.*?\]\]", re.S)
COMMENT = re.compile(r"(?:^|(?<=\s))#.*$", re.M)
EQUALS_WORD = re.compile(r"(?:^|(?<=[\s;&|(]))=[^\s=;&|)]*=*[^\s;&|)]*")

# Masked text keeps every offset, so a match in it is a position in the command.
# The filler is a word character, so it never starts or ends a word.
FILLER = "x"


def mask(match):
    return re.sub(r"[^\n]", FILLER, match.group(0))


def mask_heredoc_bodies(command):
    lines = command.split("\n")
    kept = []
    pending = []
    for line in lines:
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            kept.append(FILLER * len(line))
            continue
        kept.append(line)
        pending.extend(match.group(2) for match in HEREDOC_START.finditer(line))
    return "\n".join(kept)


def masked(command):
    text = mask_heredoc_bodies(command)
    text = QUOTED.sub(mask, text)
    text = DOUBLE_BRACKET.sub(mask, text)
    return COMMENT.sub(mask, text)


def equals_word_starts(text):
    return [match.start() for match in EQUALS_WORD.finditer(text) if match.group(0) != "="]


def escape_at(command, starts):
    for start in reversed(starts):
        command = command[:start] + "\\" + command[start:]
    return command


def main():
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input", {})
    command = tool_input.get("command", "")
    text = masked(command)
    starts = equals_word_starts(text)
    if not starts:
        return 0
    if "'" in text or '"' in text:
        words = [EQUALS_WORD.match(text, start).group(0) for start in starts]
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
