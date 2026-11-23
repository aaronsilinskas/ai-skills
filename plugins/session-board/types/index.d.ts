export type Status =
  | 'idle'
  | 'working'
  | 'permission'
  | 'question'
  | 'needs-input'
  | 'failed'
  | 'finished'
  | 'ended'

/** One session's line on the board, as it writes it to its own file. */
export type SessionRecord = {
  id: string
  project: string
  cwd: string
  /**
   * The name `/rename` gave the session, '' for none. Shown in place of
   * `title`; absent from a record an older version of the plugin wrote.
   */
  name?: string
  /** The session's first prompt, cut short. */
  title: string
  status: Status
  /** When `status` last changed, epoch ms. */
  since: number
  /** What it waits on, or the turn's headline. */
  note: string
  /** Last heartbeat, epoch ms. */
  beat: number
  /** The Terminal tab's tty (`ttys001`), empty for a background job. */
  tty: string
  /** A background job's id for `claude attach`, else empty. */
  jobId: string
}

declare module 'claude-code' {
  interface PluginState {
    'session-board': {
      board: Shaped<SessionRecord[]>
      selfId: string
      /** Band signature the person dismissed; the band returns when it changes. */
      hiddenSig: string
      /** When the board was last read, epoch ms: what the pane's ages count from. */
      lastPoll: number
    }
  }
}
