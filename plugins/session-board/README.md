# session-board

See every Claude Code session on this machine at once, from any of them.

```
/plugin install session-board --marketplace aaronsilinskas/ai-skills
```

Each session writes a small status file, `<session-id>.json`, to a `session-board` folder in your Claude Code configuration folder (`.claude` in your home), and reads everyone else's every few seconds.

- **Band above the prompt** in every session: other sessions that need you (permission prompt, a question, `needs input:`, failed): the first by name (two in a window 120 columns wide), the rest counted, plus counts of working and finished ones. `Sessions` opens the pane; `✕` hides the band until something changes.
- **`/sessions` pane**: every live session, sorted needs-you first, with its first prompt, its status, how long ago it changed, and what it waits on or the turn's headline.
- **Desktop notifications** through your normal notification channel when a session needs you or finishes (`notify`: `all`, `attention` or `none`). A permission prompt notifies only if it is still waiting after 4 seconds, so asks that auto mode's classifier settles stay quiet.

## Switching to a session (macOS Terminal)

Each session records its Terminal tty, or its background job id. `bin/focus-session.sh` selects the Terminal tab on that tty, or opens a new window running `claude attach <job-id>` for a background job.

- **`/sessions go`** switches to the other session that has waited on you longest (or, with none waiting, the one that finished last). `/sessions go <project>` picks one by project name.
- **Go** on a `/sessions` row, or beside a session the band names, does the same.

Notifications go through Claude Code's own channel (`preferredNotifChannel`). Clicking one does whatever your terminal does with it: iTerm2, Ghostty and kitty show a banner that focuses the sending tab; Terminal.app only rings the bell.

A turn ending in a `result:`, `needs input:` or `failed:` line uses that line as the session's status, and the rest of the line as its note; a turn with no such line is finished, with its last line as the note. A refused turn or an API error is failed; an interrupted turn goes quiet. A session with no heartbeat for 90 seconds drops off the board.

## Cleaning up

Status files stay in the folder after their sessions end; the board stops reading one once it has gone a day untouched. **`/sessions clean`** removes the files of ended sessions, of sessions with no heartbeat for 90 seconds, and files untouched for over a day, then says how many it removed. It never removes a live session's file, its own included. It deletes with `rm` on each file's exact path in the `session-board` folder, since the plugin API has no file delete. A stale session that comes back writes its file again at its next heartbeat.
