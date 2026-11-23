import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { SessionRecord, Status } from '../types'

const PANE = 'session-board'
const PANE_TITLE = 'Sessions'

const board = atom({ plugin: 'session-board', key: 'board' } as const, [], { shape: 'board-1' })
const selfId = atom({ plugin: 'session-board', key: 'selfId' } as const, '')
const hiddenSig = atom({ plugin: 'session-board', key: 'hiddenSig' } as const, '')
const now = atom({ plugin: 'session-board', key: 'now' } as const, 0)

const POLL_MS = 3_000
const BEAT_MS = 20_000
/** A session with no heartbeat for this long is treated as gone (crashed, killed). */
const STALE_MS = 90_000
/** Files untouched for this long are not even read. */
const FORGET_MS = 24 * 60 * 60 * 1000
/** A permission ask the auto-mode classifier settles clears well inside this. */
const PERMISSION_GRACE_MS = 4_000

const NEEDS_YOU: ReadonlySet<Status> = new Set(['permission', 'question', 'needs-input', 'failed'])

const GLYPH: Record<Status, string> = {
  idle: '·',
  working: '⏳',
  permission: '⚠',
  question: '?',
  'needs-input': '⚠',
  failed: '✗',
  finished: '✓',
  ended: '·',
}
const LABEL: Record<Status, string> = {
  idle: 'idle',
  working: 'working',
  permission: 'needs permission',
  question: 'asking you',
  'needs-input': 'needs input',
  failed: 'failed',
  finished: 'finished',
  ended: 'ended',
}
const ATTENTION = '#d97706'
const DONE = '#16a34a'
const FAILED = '#dc2626'
const WORKING = '#2563eb'

function colorOf(s: Status): string | undefined {
  if (s === 'failed') return FAILED
  if (NEEDS_YOU.has(s)) return ATTENTION
  if (s === 'finished') return DONE
  if (s === 'working') return WORKING
  return undefined
}

/** Order on the board: what needs you first, then working, then done. */
function rank(s: Status): number {
  if (NEEDS_YOU.has(s)) return 0
  if (s === 'working') return 1
  if (s === 'finished') return 2
  return 3
}

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
 * convention, taking the last such line; otherwise the turn simply finished.
 */
function outcomeOf(answer: string): { status: Status; note: string } {
  const lines = answer.split('\n')
  for (let i = lines.length - 1; i >= 0; i--) {
    const m = /^\s*(result|needs input|failed):\s*(.*)$/i.exec(lines[i] ?? '')
    if (m) {
      const word = (m[1] ?? '').toLowerCase()
      const status: Status = word === 'result' ? 'finished' : word === 'failed' ? 'failed' : 'needs-input'
      const rest = [m[2] ?? '', ...lines.slice(i + 1)].join(' ')
      return { status, note: oneLine(rest, 120) }
    }
  }
  const last = lines.map(l => l.trim()).filter(Boolean).at(-1) ?? ''
  return { status: 'finished', note: oneLine(last, 120) }
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

function focusArgv($: EngineInterface, r: Pick<SessionRecord, 'tty' | 'jobId'>): string[] {
  return ['/bin/sh', `${$.plugin.root}/bin/focus-session.sh`, r.tty, r.jobId]
}

/** The tty of the Claude Code process this module runs in: `ttys001`, or '' when it has none. */
async function ttyOf($: EngineInterface): Promise<string> {
  const { stdout } = await $.process.run(['/bin/sh', '-c', 'ps -o tty= -p $PPID'])
  const tty = stdout.trim()
  return /^[A-Za-z0-9]+$/.test(tty) ? tty : ''
}

/** Brings a session to the front: its Terminal tab, or a window attached to its background job. */
async function focusSession($: EngineInterface, r: SessionRecord): Promise<void> {
  await $.process.run(focusArgv($, r), { timeoutMs: 10_000 }).catch(ignore)
}

async function notifyFor($: EngineInterface, status: Status, note: string): Promise<void> {
  if (notifyMode === 'none' || !me) return
  const wants = NEEDS_YOU.has(status) || (status === 'finished' && notifyMode === 'all')
  if (!wants) return
  const text = note ? `${LABEL[status]}: ${note}` : LABEL[status]
  const title = me.title ? `${me.project} · ${oneLine(me.title, 40)}` : me.project
  await $.ui.notify(text, { title, key: me.id }).catch(() => undefined)
}

async function setStatus($: EngineInterface, status: Status, note: string, opts?: { quiet?: boolean }): Promise<void> {
  if (!me) return
  if (me.status === status && me.note === note) return
  me = { ...me, status, note, since: await $.clock.now() }
  await save($)
  if (!opts?.quiet) await notifyFor($, status, note)
  await poll($)
}

/** Back to work once nothing waits on a person. */
async function resume($: EngineInterface): Promise<void> {
  if (!me) return
  if (asking.size > 0) {
    const [, note] = [...asking.entries()].at(-1) ?? ['', '']
    await setStatus($, 'permission', note, { quiet: true })
    return
  }
  if (me.status === 'permission' || me.status === 'question') await setStatus($, 'working', '')
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
  found.sort((a, b) => rank(a.status) - rank(b.status) || b.since - a.since)
  await update($, now, () => at)
  await update($, board, () => found)
}

/**
 * Switches to another session: the one named (a project name or its start),
 * else the one that has waited on you longest, else the one that finished last.
 */
async function goTo($: EngineInterface, name: string): Promise<string> {
  await poll($)
  const self = await read($, selfId)
  const others = (await read($, board)).filter(r => r.id !== self)
  const wanted = name.toLowerCase()
  const named = wanted ? others.filter(r => r.project.toLowerCase().startsWith(wanted)) : others
  const waiting = named.filter(r => NEEDS_YOU.has(r.status)).sort((a, b) => a.since - b.since)
  const done = named.filter(r => r.status === 'finished').sort((a, b) => b.since - a.since)
  const target = waiting[0] ?? done[0] ?? (wanted ? named[0] : undefined)
  if (!target) return wanted ? `No other session matches "${name}".` : 'No other session is waiting on you.'
  await focusSession($, target)
  return `Switched to ${target.project} (${LABEL[target.status]}).`
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
    const jobDir = (await $.env.get('CLAUDE_JOB_DIR')) ?? ''
    const tty = await ttyOf($).catch(() => '')
    me = {
      id,
      project: basename(root),
      cwd: e.cwd,
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
      await save($).catch(() => undefined)
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
    await setStatus($, 'working', '', { quiet: true }).catch(ignore)
    return next(e)
  })

  on('tool.check', async ($, e, next) => {
    const verdict = await next(e)
    if (verdict.decision === 'ask' && e.approver === 'person' && e.tool_use_id) {
      const id = e.tool_use_id
      const note = callSummary(e.tool, e.input)
      asking.set(id, note)
      await setStatus($, "permission", note, { quiet: true }).catch(ignore)
      // Auto mode puts most asks to its classifier, which settles them fast:
      // only a call still waiting after the grace period earns a notification.
      $.clock.after(PERMISSION_GRACE_MS, () => {
        if (asking.has(id) && me?.status === 'permission') void notifyFor($, 'permission', note)
      })
    }
    return verdict
  })

  on('tool.call', async ($, e, next) => {
    const id = e.tool_use_id
    if (id && asking.delete(id)) await resume($).catch(ignore)
    const isQuestion = e.tool === 'AskUserQuestion' || e.tool === 'ExitPlanMode'
    if (isQuestion) {
      const args = e as unknown as { questions?: { question?: string }[] }
      const q = args.questions?.[0]?.question ?? (e.tool === 'ExitPlanMode' ? 'plan ready for review' : '')
      await setStatus($, "question", oneLine(q, 100)).catch(ignore)
    }
    try {
      return await next(e)
    } finally {
      if (id && asking.delete(id)) await resume($).catch(ignore)
      if (isQuestion) await resume($).catch(ignore)
    }
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId !== undefined || !me) return result
    asking.clear()
    if (e.reason === 'aborted') {
      await setStatus($, 'idle', 'interrupted', { quiet: true })
    } else if (e.reason === 'refusal' || e.reason === 'error') {
      await setStatus($, 'failed', e.reason === 'error' ? 'the turn ended on an API error' : 'the model refused')
    } else {
      const { status, note } = outcomeOf(e.answer)
      await setStatus($, status, note)
    }
    return result
  })

  // ---------------------------------------------------------------------------
  // The band above the prompt: other sessions only

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const self = await read($, selfId)
    const others = (await read($, board)).filter(r => r.id !== self && r.status !== 'idle')
    const sig = signatureOf(others)
    if (others.length === 0 || (sig !== '' && sig === (await read($, hiddenSig))) ) return next(e)

    const drawn = await Promise.resolve(next(e)).catch(() => null)
    const below = drawn && typeof drawn === 'object' && (drawn as { type?: string }).type !== 'engine' ? drawn : null
    const { Box, Text, Button } = $.ui.resolve(e)

    const needs = others.filter(r => NEEDS_YOU.has(r.status))
    const working = others.filter(r => r.status === 'working').length
    const done = others.filter(r => r.status === 'finished').length
    const cols = e.props.bodyColumns || 80
    const shown = needs.slice(0, cols >= 120 ? 2 : 1)

    return (
      <Box flexDirection="column">
        <Box flexDirection="row" gap={1}>
          {shown.map(r => (
            <Box key={r.id} flexDirection="row" flexShrink={1}>
              <Text color={colorOf(r.status)} bold>
                {GLYPH[r.status]} {r.project}
              </Text>
              <Text wrap="truncate-end"> {LABEL[r.status]}{r.note ? ` · ${oneLine(r.note, 40)}` : ''}</Text>
              <Button key={`session-board-go-${r.id}`} label="Go" plain onPress={() => void focusSession($, r)} />
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
    const at = await read($, now)
    const cols = Math.max(24, e.props.bodyColumns || 40)

    if (list.length === 0) return <Text dimColor>No live sessions.</Text>

    return (
      <Box flexDirection="column">
        {list.map(r => (
          <Box key={r.id} flexDirection="column" marginBottom={1}>
            <Box flexDirection="row" gap={1}>
              <Text color={colorOf(r.status)}>{GLYPH[r.status]}</Text>
              <Text bold wrap="truncate-end">
                {r.project}
                {r.id === self ? ' (this one)' : ''}
              </Text>
              <Text color={colorOf(r.status)}>{LABEL[r.status]}</Text>
              <Text dimColor>{age(at - r.since)}</Text>
              {r.id !== self && (
                <Button key={`session-board-go-${r.id}`} label="Go" plain onPress={() => void focusSession($, r)} />
              )}
            </Box>
            {r.title !== '' && (
              <Text dimColor wrap="truncate-end">
                {'  '}
                {oneLine(r.title, cols - 2)}
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
