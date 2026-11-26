# Claude Code hooks

Two `PreToolUse` hooks for the Bash tool that catch shell mistakes agents make over and over, before the command runs.
Each is one Python 3.9+ file with no dependencies.

- **`zsh_equals_guard.py`**: zsh expands an unquoted word that starts with `=` to the path of a command, so `echo ====` fails with `=== not found`, and `[ a == b ]` fails the same way.
  The hook puts a backslash before that `=` (`echo \====`), which turns off only that expansion, and hands the fixed command back to Claude Code, so the call runs without a retry.
  It leaves quoted text, heredoc bodies, `[[ ... ]]` tests, `(( ... ))` arithmetic and comments alone.
  It doesn't approve the call: your permission rules judge the fixed command as usual.
  When an unbalanced quote makes the words uncertain, it blocks the call instead and tells the agent to quote the word.
- **`gh_issue_comments_guard.py`**: off a terminal, `gh issue view <n> --comments` prints only the comments, so an issue with none looks empty and the agent misses its body.
  The hook blocks that command unless it has `--json`, and suggests `gh issue view <n> --json title,body,labels,comments`.

## Install

Clone the repo somewhere it will stay, then add the hooks to `~/.claude/settings.json` (or a project's `.claude/settings.json`), pointing at the clone:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/ai-skills/hooks/zsh_equals_guard.py",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "python3 /path/to/ai-skills/hooks/gh_issue_comments_guard.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Merge the entry into any `hooks` block you already have, and take only the hooks you want.
A `git pull` in the clone updates them.

To keep the paths in your settings stable, symlink the files into `~/.claude/hooks/` and point the settings there instead:

```sh
mkdir -p ~/.claude/hooks
ln -sf /path/to/ai-skills/hooks/zsh_equals_guard.py ~/.claude/hooks/
ln -sf /path/to/ai-skills/hooks/gh_issue_comments_guard.py ~/.claude/hooks/
```

Run `/hooks` in Claude Code to see that they are registered.
