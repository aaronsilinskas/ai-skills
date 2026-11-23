#!/bin/sh
# Bring a Claude Code session to the front in macOS Terminal.
#   focus-session.sh <tty> <job-id>
# <tty> (e.g. ttys001): select the Terminal tab on that tty.
# <job-id>: a background job; when no tab was found, open a window attached to it.
# Either may be empty.
tty="$1"
job="$2"

case "$tty" in *[!A-Za-z0-9]*) tty="" ;; esac
case "$job" in *[!A-Za-z0-9_-]*) job="" ;; esac

if [ -n "$tty" ]; then
  found=$(osascript - "/dev/$tty" <<'APPLESCRIPT'
on run argv
  set target to item 1 of argv
  tell application "Terminal"
    repeat with w in windows
      repeat with t in tabs of w
        if tty of t is target then
          set selected of t to true
          set index of w to 1
          activate
          return "found"
        end if
      end repeat
    end repeat
  end tell
  return "missing"
end run
APPLESCRIPT
)
  [ "$found" = "found" ] && exit 0
fi

if [ -n "$job" ]; then
  osascript -e "tell application \"Terminal\" to do script \"claude attach $job\"" \
            -e 'tell application "Terminal" to activate' >/dev/null
  exit 0
fi

# Nothing to point at: just bring Terminal forward.
osascript -e 'tell application "Terminal" to activate' >/dev/null
