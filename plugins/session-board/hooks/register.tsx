import { atom, read, update } from 'claude-code'
import type { ButtonProps, EngineInterface, Register } from 'claude-code'

import type { SessionRecord, Status } from '../types'

const PANE = 'session-board'
const PANE_TITLE = 'Sessions'

const board = atom({ plugin: 'session-board', key: 'board' } as const, [], { shape: 'board-1' })
const selfId = atom({ plugin: 'session-board', key: 'selfId' } as const, '')
const hiddenSig = atom({ plugin: 'session-board', key: 'hiddenSig' } as const, '')
const lastPoll = atom({ plugin: 'session-board', key: 'lastPoll' } as const, 0)

const POLL_MS = 3_000
const BEAT_MS = 20_000
/** A session with no heartbeat for this long is treated as gone (crashed, killed). */
const STALE_MS = 90_000
/** Files untouched for this long are not even read. */
const FORGET_MS = 24 * 60 * 60 * 1000
/** A permission ask a person still holds after this long earns a notification. */
const PERMISSION_GRACE_MS = 4_000
/** How much of the transcript's end is searched for its name: the most one read returns. */
const NAME_TAIL_BYTES = 4 * 1024 * 1024

const ATTENTION = '#d97706'
const DONE = '#16a34a'
const FAILED = '#dc2626'
const WORKING = '#2563eb'

type StatusLook = {
  glyph: string
  label: string
  color?: string
  /** Order on the board: what needs you first, then working, then done. */
  rank: number
  needsYou: boolean
}

const STATUS: Record<Status, StatusLook> = {
  permission: { glyph: '⚠', label: 'needs permission', color: ATTENTION, rank: 0, needsYou: true },
  question: { glyph: '?', label: 'asking you', color: ATTENTION, rank: 0, needsYou: true },
  'needs-input': { glyph: '⚠', label: 'needs input', color: ATTENTION, rank: 0, needsYou: true },
  failed: { glyph: '✗', label: 'failed', color: FAILED, rank: 0, needsYou: true },
  working: { glyph: '⏳', label: 'working', color: WORKING, rank: 1, needsYou: false },
  finished: { glyph: '✓', label: 'finished', color: DONE, rank: 2, needsYou: false },
  idle: { glyph: '·', label: 'idle', rank: 3, needsYou: false },
  ended: { glyph: '·', label: 'ended', rank: 3, needsYou: false },
}

/** A session's status and what goes with it: what it waits on, or the turn's headline. */
type Outcome = Pick<SessionRecord, 'status' | 'note'>

function basename(path: string): string {
  const parts = path.split('/').filter(Boolean)
  return parts.at(-1) ?? path
}

function oneLine(text: string, max: number): string {
  const flat = text.replace(/\s+/g, ' ').trim()
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat
}

function age(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s}s`
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m`
  const h = Math.round(m / 60)
  return h < 48 ? `${h}h` : `${Math.round(h / 24)}d`
}

/** What a tool call is about, in a few words, for a permission note. */
function callSummary(tool: string, input: unknown): string {
  const args = (input ?? {}) as Record<string, unknown>
  const detail = args.command ?? args.file_path ?? args.url ?? args.pattern ?? ''
  const name = tool.startsWith('mcp__') ? tool.split('__').slice(1).join(':') : tool
  return detail ? `${name}: ${oneLine(String(detail), 60)}` : name
}

/**
 * The turn's outcome. Honours the `result:` / `needs input:` / `failed:`
 * convention, taking the last such line; otherwise the turn simply finished,
 * and its last line is the note.
 */
function outcomeOf(answer: string): Outcome {
  const lines = answer.split('\n')
  for (let i = lines.length - 1; i >= 0; i--) {
    const m = /^\s*(result|needs input|failed):\s*(.*)$/i.exec(lines[i] ?? '')
    if (m) {
      const word = (m[1] ?? '').toLowerCase()
      const status: Status = word === 'result' ? 'finished' : word === 'failed' ? 'failed' : 'needs-input'
      return { status, note: oneLine(m[2] ?? '', 120) }
    }
  }
  const last = lines.map(l => l.trim()).filter(Boolean).at(-1) ?? ''
  return { status: 'finished', note: oneLine(last, 120) }
}

/** What a session is called: its `/rename` name, else its first prompt. */
function titleOf(r: SessionRecord): string {
  return r.name || r.title
}

/**
 * The latest name `/rename` gave this session, or '' for none. The engine
 * records each one in the transcript as a `custom-title` row and repeats it
 * as the transcript grows, so the end of the file holds the current name.
 */
async function transcriptName($: EngineInterface): Promise<string> {
  const { transcriptPath } = await $.session.info()
  if (!transcriptPath) return ''
  const { size } = await $.fs.stat(transcriptPath)
  const offset = Math.max(0, size - NAME_TAIL_BYTES)
  const tail = await $.fs.read(transcriptPath, { offset, length: size - offset })
  const lines = tail.split('\n')
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i] ?? ''
    if (!line.includes('"custom-title"')) continue
    try {
      const row = JSON.parse(line) as { type?: string; customTitle?: unknown }
      if (row.type === 'custom-title' && typeof row.customTitle === 'string') return row.customTitle
    } catch {
      // The tail's first line may start mid-row.
    }
  }
  return ''
}

/** What the band shows; dismissing it hides it until this changes. */
function signatureOf(others: SessionRecord[]): string {
  return others
    .filter(r => r.status !== 'working')
    .map(r => `${r.id}:${r.status}:${r.since}`)
    .sort()
    .join('|')
}

/** For status writes inside hooks that gate a prompt or a tool call: never fail them. */
function ignore(): void {}

function isLive(r: SessionRecord, at: number): boolean {
  return r.status !== 'ended' && at - r.beat < STALE_MS
}

// ---------------------------------------------------------------------------
// This session's own record. Module variables start over on a reload, and
// session.start fills them again.

let notifyMode: 'all' | 'attention' | 'none' = 'all'
let dir = ''
let me: SessionRecord | null = null
/** tool_use_ids put to a person and not yet run or refused. */
const asking = new Map<string, string>()

async function save($: EngineInterface): Promise<void> {
  if (!me || !dir) return
  me = { ...me, beat: await $.clock.now() }
  await $.fs.write(`${dir}/${me.id}.json`, JSON.stringify(me))
}

/** The tty of the Claude Code process this module runs in: `ttys001`, or '' when it has none. */
async function ttyOf($: EngineInterface): Promise<string> {
  const { stdout } = await $.process.run(['/bin/sh', '-c', 'ps -o tty= -p $PPID'])
  const tty = stdout.trim()
  return /^[A-Za-z0-9]+$/.test(tty) ? tty : ''
}

/** Brings a session to the front: its Terminal tab, or a window attached to its background job. */
async function focusSession($: EngineInterface, r: SessionRecord): Promise<void> {
  const argv = ['/bin/sh', `${$.plugin.root}/bin/focus-session.sh`, r.tty, r.jobId]
  await $.process.run(argv, { timeoutMs: 10_000 }).catch(ignore)
}

/** The props of a session's Go button, the same in the band and the pane. */
function goButtonProps($: EngineInterface, r: SessionRecord): ButtonProps & { key: string } {
  return { key: `session-board-go-${r.id}`, label: 'Go', plain: true, onPress: () => void focusSession($, r) }
}

async function notifyFor($: EngineInterface, { status, note }: Outcome): Promise<void> {
  if (notifyMode === 'none' || !me) return
  const wants = STATUS[status].needsYou || (status === 'finished' && notifyMode === 'all')
  if (!wants) return
  const label = STATUS[status].label
  const text = note ? `${label}: ${note}` : label
  const title = titleOf(me) ? `${me.project} · ${oneLine(titleOf(me), 40)}` : me.project
  await $.ui.notify(text, { title, key: me.id }).catch(ignore)
}

async function setStatus($: EngineInterface, outcome: Outcome, opts?: { quiet?: boolean }): Promise<void> {
  if (!me) return
  if (me.status === outcome.status && me.note === outcome.note) return
  me = { ...me, ...outcome, since: await $.clock.now() }
  await save($)
  if (!opts?.quiet) await notifyFor($, outcome)
  await poll($)
}

/** Settles a permission ask (allowed, refused, or decided by the classifier) and resumes work. */
async function settleAsk($: EngineInterface, id: string | undefined): Promise<void> {
  if (id && asking.delete(id)) await resume($)
}

/** Back to work once nothing waits on a person. */
async function resume($: EngineInterface): Promise<void> {
  if (!me) return
  const pending = [...asking.values()].at(-1)
  if (pending !== undefined) {
    await setStatus($, { status: 'permission', note: pending }, { quiet: true })
    return
  }
  if (me.status === 'permission' || me.status === 'question') await setStatus($, { status: 'working', note: '' })
}

async function poll($: EngineInterface): Promise<void> {
  if (!dir) return
  const at = await $.clock.now()
  const entries = await $.fs.list(dir).catch(() => [])
  const found: SessionRecord[] = []
  for (const f of entries) {
    if (f.kind !== 'file' || !f.name.endsWith('.json') || at - f.mtimeMs > FORGET_MS) continue
    try {
      const r = JSON.parse(await $.fs.read(`${dir}/${f.name}`)) as SessionRecord
      if (r && typeof r.id === 'string' && isLive(r, at)) found.push(r)
    } catch {
      // A file mid-write or hand-edited: skip it this round.
    }
  }
  found.sort((a, b) => STATUS[a.status].rank - STATUS[b.status].rank || b.since - a.since)
  await update($, lastPoll, () => at)
  await update($, board, () => found)
}

/** Every live session but this one. */
async function othersOf($: EngineInterface): Promise<SessionRecord[]> {
  const self = await read($, selfId)
  return (await read($, board)).filter(r => r.id !== self)
}

/**
 * Switches to another session: the one named (a project name or its start),
 * else the one that has waited on you longest, else the one that finished last.
 */
async function goTo($: EngineInterface, name: string): Promise<string> {
  await poll($)
  const others = await othersOf($)
  const wanted = name.toLowerCase()
  const named = wanted ? others.filter(r => r.project.toLowerCase().startsWith(wanted)) : others
  const waiting = named.filter(r => STATUS[r.status].needsYou).sort((a, b) => a.since - b.since)
  const done = named.filter(r => r.status === 'finished').sort((a, b) => b.since - a.since)
  const target = waiting[0] ?? done[0] ?? (wanted ? named[0] : undefined)
  if (!target) return wanted ? `No other session matches "${name}".` : 'No other session is waiting on you.'
  await focusSession($, target)
  return `Switched to ${target.project} (${STATUS[target.status].label}).`
}

async function openPane($: EngineInterface): Promise<void> {
  await poll($)
  await $.ui.open({ id: PANE, title: PANE_TITLE })
}

export const register: Register = (on, options) => {
  notifyMode = options.notify === 'attention' || options.notify === 'none' ? options.notify : 'all'

  // ---------------------------------------------------------------------------
  // Lifecycle

  on('session.start', async ($, e, next) => {
    const result = await next(e)
    const home = await $.env.get('HOME')
    dir = `${home}/.claude/session-board`
    const id = await $.session.id()
    const root = await $.session.root().catch(() => e.cwd)
    const at = await $.clock.now()
    // A background job's folder is named by its id, the one `claude attach` takes.
    const jobDir = (await $.env.get('CLAUDE_JOB_DIR')) ?? ''
    const tty = await ttyOf($).catch(() => '')
    // A resumed session, or this module reloaded, keeps the name it was given.
    const name = await transcriptName($).catch(() => '')
    me = {
      id,
      project: basename(root),
      cwd: e.cwd,
      name,
      title: '',
      status: 'idle',
      since: at,
      note: '',
      beat: at,
      tty,
      jobId: jobDir ? basename(jobDir) : '',
    }
    await update($, selfId, () => id)
    await save($)

    await $.command.register({
      name: 'sessions',
      description: 'Show every Claude Code session; "go" switches to the one waiting on you longest',
      argumentHint: '[go [project]]',
    })
    $.clock.every(POLL_MS, () => void poll($))
    $.clock.every(BEAT_MS, () => void save($))
    await poll($)
    return result
  })

  on('session.end', async ($, e, next) => {
    if (me) {
      me = { ...me, status: 'ended', since: await $.clock.now() }
      await save($).catch(ignore)
    }
    return next(e)
  })

  on('command.run', { command: 'sessions' }, async ($, e) => {
    const [verb, ...rest] = e.args.trim().split(/\s+/)
    if (verb === 'go') return { text: await goTo($, rest.join(' ')) }
    if ((await $.ui.panes()).some(p => p.id === PANE)) {
      await $.ui.close({ id: PANE })
      return { text: 'Sessions pane closed.' }
    }
    await openPane($)
    return { text: 'Sessions pane opened.' }
  })

  on('command.run', { command: 'rename' }, async ($, e, next) => {
    const result = await next(e)
    // A bare `/rename` generates the name, which only the transcript then holds.
    const name = e.args.trim() || (await transcriptName($).catch(() => ''))
    if (me && name && name !== me.name) {
      me = { ...me, name }
      await save($).catch(ignore)
      await poll($).catch(ignore)
    }
    return result
  })

  // ---------------------------------------------------------------------------
  // Status transitions

  on('prompt.submit', async ($, e, next) => {
    // A task notification, trigger or peer message is not what the session is for.
    const isNotice =
      e.origin.kind === 'task-notification' ||
      e.origin.kind === 'scheduled-trigger' ||
      e.origin.kind === 'peer' ||
      /^\s*<[a-z][\w-]*>/i.test(e.text)
    if (me && !me.title && !isNotice) {
      me = { ...me, title: oneLine(e.text, 80) }
      await save($).catch(ignore)
    }
    asking.clear()
    await setStatus($, { status: 'working', note: '' }, { quiet: true }).catch(ignore)
    return next(e)
  })

  // tool.call → tool.check → (tool.judge in auto mode, or a person) → tool.run.
  on('tool.check', async ($, e, next) => {
    const verdict = await next(e)
    if (verdict.decision === 'ask' && e.approver === 'person' && e.tool_use_id) {
      const id = e.tool_use_id
      const note = callSummary(e.tool, e.input)
      asking.set(id, note)
      await setStatus($, { status: 'permission', note }, { quiet: true }).catch(ignore)
      // Auto mode puts most asks to its classifier (tool.judge), which settles
      // them fast: only an ask still held after the grace period notifies.
      $.clock.after(PERMISSION_GRACE_MS, () => {
        if (asking.has(id) && me?.status === 'permission') void notifyFor($, { status: 'permission', note })
      })
    }
    return verdict
  })

  on('tool.judge', async ($, e, next) => {
    const verdict = await next(e)
    // The classifier decided: nobody is asked. An `ask` still goes to a person.
    if (verdict.decision !== 'ask') await settleAsk($, e.tool_use_id).catch(ignore)
    return verdict
  })

  on('tool.run', async ($, e, next) => {
    await settleAsk($, e.tool_use_id).catch(ignore)
    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    const isQuestion = e.tool === 'AskUserQuestion' || e.tool === 'ExitPlanMode'
    if (isQuestion) {
      const args = e as unknown as { questions?: { question?: string }[] }
      const q = args.questions?.[0]?.question ?? (e.tool === 'ExitPlanMode' ? 'plan ready for review' : '')
      await setStatus($, { status: 'question', note: oneLine(q, 100) }).catch(ignore)
    }
    try {
      return await next(e)
    } finally {
      // A refused call never reaches tool.run: settle its ask here.
      const wasAsking = e.tool_use_id ? asking.delete(e.tool_use_id) : false
      if (wasAsking || isQuestion) await resume($).catch(ignore)
    }
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId !== undefined || !me) return result
    asking.clear()
    if (e.reason === 'aborted') {
      await setStatus($, { status: 'idle', note: 'interrupted' }, { quiet: true })
    } else if (e.reason === 'refusal' || e.reason === 'error') {
      const note = e.reason === 'error' ? 'the turn ended on an API error' : 'the model refused'
      await setStatus($, { status: 'failed', note })
    } else {
      await setStatus($, outcomeOf(e.answer))
    }
    return result
  })

  // ---------------------------------------------------------------------------
  // The band above the prompt: other sessions only

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const others = (await othersOf($)).filter(r => r.status !== 'idle')
    const sig = signatureOf(others)
    if (others.length === 0 || (sig !== '' && sig === (await read($, hiddenSig)))) return next(e)

    const drawn = await Promise.resolve(next(e)).catch(() => null)
    const below = drawn && typeof drawn === 'object' && (drawn as { type?: string }).type !== 'engine' ? drawn : null
    const { Box, Text, Button } = $.ui.resolve(e)

    const needs = others.filter(r => STATUS[r.status].needsYou)
    const working = others.filter(r => r.status === 'working').length
    const done = others.filter(r => r.status === 'finished').length
    // Named in full only while they fit one row; the rest are counted.
    const cols = e.props.bodyColumns || 80
    const shown = needs.slice(0, cols >= 120 ? 2 : 1)

    return (
      <Box flexDirection="column">
        <Box flexDirection="row" gap={1}>
          {shown.map(r => (
            <Box key={r.id} flexDirection="row" flexShrink={1}>
              <Text color={STATUS[r.status].color} bold>
                {STATUS[r.status].glyph} {r.project}
              </Text>
              <Text wrap="truncate-end">
                {' '}
                {STATUS[r.status].label}
                {r.note ? ` · ${oneLine(r.note, 40)}` : ''}
              </Text>
              <Button {...goButtonProps($, r)} />
            </Box>
          ))}
          {needs.length > shown.length && <Text color={ATTENTION}>+{needs.length - shown.length} need you</Text>}
          {working > 0 && <Text color={WORKING}>⏳ {working} working</Text>}
          {done > 0 && <Text color={DONE}>✓ {done} done</Text>}
          <Button key="session-board-open" label="Sessions" plain onPress={() => void openPane($)} />
          {sig !== '' && (
            <Button key="session-board-dismiss" label="✕" plain role="dismiss" onPress={() => update($, hiddenSig, () => sig)} />
          )}
        </Box>
        {below}
      </Box>
    )
  })

  // ---------------------------------------------------------------------------
  // The /sessions pane: every live session, this one included

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const list = await read($, board)
    const self = await read($, selfId)
    const at = await read($, lastPoll)
    const cols = Math.max(24, e.props.bodyColumns || 40)

    if (list.length === 0) return <Text dimColor>No live sessions.</Text>

    return (
      <Box flexDirection="column">
        {list.map(r => (
          <Box key={r.id} flexDirection="column" marginBottom={1}>
            <Box flexDirection="row" gap={1}>
              <Text color={STATUS[r.status].color}>{STATUS[r.status].glyph}</Text>
              <Text bold wrap="truncate-end">
                {r.project}
                {r.id === self ? ' (this one)' : ''}
              </Text>
              <Text color={STATUS[r.status].color}>{STATUS[r.status].label}</Text>
              <Text dimColor>{age(at - r.since)}</Text>
              {r.id !== self && <Button {...goButtonProps($, r)} />}
            </Box>
            {titleOf(r) !== '' && (
              <Text dimColor wrap="truncate-end">
                {'  '}
                {oneLine(titleOf(r), cols - 2)}
              </Text>
            )}
            {r.note !== '' && (
              <Text wrap="truncate-end">
                {'  '}→ {oneLine(r.note, cols - 4)}
              </Text>
            )}
          </Box>
        ))}
      </Box>
    )
  })
}
