import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'

const HOME = '/home/me'
const DIR = `${HOME}/.claude/session-board`
const FRESH = 9_999_999_999
const TRANSCRIPT = `${HOME}/.claude/projects/work-core/me-1.jsonl`

const PANE = {
  plugin: 'session-board',
  component: 'Pane',
  requestId: 'session-board',
  props: {
    title: 'Sessions',
    isFocused: false,
    bodyColumns: 60,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 20 },
    view: {},
  },
} as const

const BAND = {
  plugin: 'session-board',
  component: 'AbovePrompt',
  props: { hasSurvey: false, isCollapsed: false, isWorking: false, maxRows: 4, bodyColumns: 100 },
} as const

type Files = Map<string, string>

type World = {
  files: Files
  /** A file's last-modified time, when it is not now. */
  mtimes: Map<string, number>
  notes: string[]
  runs: string[][]
  /** Whether `/rename` refuses, as it does a bare one with no conversation to name. */
  renameRefused: boolean
  /** Set, every file write fails with this message. */
  writeError?: string
  /** Fires the timers `$.clock.after` booked, as if their time came. */
  fireTimers: () => Promise<void>
}

/** A finished process's result. */
const exited = (exitCode: number, stdout: string, stderr = '') =>
  ({ value: { exitCode, stdout, stderr, isStdoutTruncated: false, isStderrTruncated: false } }) as const

/** Stands in for the engine: a file system in memory, a stepping clock, one session. */
function engine(on: On, opts: { rmError?: string; home?: string } = {}): World {
  const files: Files = new Map()
  const mtimes = new Map<string, number>()
  const notes: string[] = []
  const runs: string[][] = []
  const timers: (() => void)[] = []
  let t = 1_000_000
  on('clock.now', () => ({ value: (t += 1000) }))
  on('clock.every', () => ({ value: undefined }))
  on('clock.after', () => new Promise(done => timers.push(() => done({ value: undefined }))))
  on('env.get', () => ({ value: 'home' in opts ? opts.home : HOME }))
  on('session.id', () => ({ value: 'me-1' }))
  on('session.root', () => ({ value: '/work/core' }))
  on('session.info', () => ({ value: { transcriptPath: TRANSCRIPT } }))
  on('command.register', () => ({ value: { command: 'sessions' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.notify', (_, e) => {
    notes.push(`${e.title}|${e.text}`)
    return { value: { isSent: true, channel: 'client' as const } }
  })
  on('process.run', (_, e) => {
    runs.push([...e.argv])
    if (e.argv[0] === '/bin/rm' && opts.rmError !== undefined) return exited(1, '', opts.rmError)
    if (e.argv[0] === '/bin/rm') for (const p of e.argv.slice(e.argv.indexOf('--') + 1)) files.delete(p)
    return exited(0, '??\n')
  })
  on('fs.write', (_, e) => {
    if (world.writeError !== undefined) return { deny: world.writeError } as never
    files.set(e.path, e.text)
    return { value: undefined }
  })
  on('fs.exists', (_, e) => ({ value: files.has(e.path) }))
  on('fs.read', (_, e) => {
    const text = files.get(e.path) ?? ''
    const from = e.offset ?? 0
    return { value: text.slice(from, e.length === undefined ? undefined : from + e.length) }
  })
  on('fs.stat', (_, e) => ({
    value: { kind: 'file' as const, size: (files.get(e.path) ?? '').length, mtimeMs: t, isLink: false },
  }))
  on('fs.list', (_, e) => ({
    value: [...files.keys()].filter(p => p.startsWith(`${e.path}/`)).map(p => ({
      name: p.split('/').at(-1) ?? '',
      kind: 'file' as const,
      size: 1,
      mtimeMs: mtimes.get(p) ?? t,
      isLink: false,
    })),
  }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('prompt.submit', (_, e) => ({ text: e.text }))
  on('turn.complete', () => ({ text: '' }))
  on('tool.call', () => ({ result: {} }))
  on('tool.run', () => ({ result: {} }))
  on('command.run', (_, e) => {
    if (e.command !== 'rename' || world.renameRefused || !e.args.trim()) return { text: '' }
    nameInTranscript(files, e.args.trim())
    return { text: `Session renamed to: ${e.args.trim()}` }
  })
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })

  const fireTimers = async () => {
    for (const fire of timers.splice(0)) fire()
    // The timer's callback runs once its dispatch resolves.
    for (let i = 0; i < 50; i++) await Promise.resolve()
  }
  const world: World = { files, mtimes, notes, runs, renameRefused: false, fireTimers }
  return world
}

/** Another session's status file, live unless `beat` says otherwise. */
function other(files: Files, id: string, fields: Record<string, unknown>) {
  const record = { id, project: id, cwd: '/', title: `task ${id}`, status: 'working', since: 1, note: '', beat: FRESH, tty: '', jobId: '', ...fields }
  files.set(`${DIR}/${id}.json`, JSON.stringify(record))
}

/** Appends the rows `/rename` leaves in the transcript: a conversation row, then the name it set. */
function nameInTranscript(files: Files, name: string) {
  const rows = [
    JSON.stringify({ type: 'user', message: { role: 'user', content: 'hello' } }),
    JSON.stringify({ type: 'custom-title', customTitle: name, sessionId: 'me-1' }),
  ]
  files.set(TRANSCRIPT, `${files.get(TRANSCRIPT) ?? ''}${rows.join('\n')}\n`)
}

/** A slash command typed at the composer. */
const slashCommand = (command: string, args: string) =>
  ({ command, args, origin: { kind: 'composer' }, presentation: 'text' }) as never

/** A prompt typed at the composer. */
const typed = (text: string) => ({ text, wait: false, origin: { kind: 'composer' as const } })

const answered = (answer: string, agentId?: string) =>
  ({ answer, durationMs: 1, isAborted: false, turnId: 't', reason: 'answer', ...(agentId ? { agentId } : {}) }) as const

const start = ($: Engine) =>
  $.session.start({ cwd: '/work/core', surface: 'terminal', isInteractive: true })

const mine = (files: Files) => JSON.parse(files.get(`${DIR}/me-1.json`) ?? '{}')

const focused = (runs: string[][]) =>
  runs.filter(a => (a[1] ?? '').endsWith('/bin/focus-session.sh')).map(a => a.slice(2))

const permissionAsk = { tool: 'Bash', input: { command: 'git push' }, tool_use_id: 'call-1', approver: 'person' } as never

// --- status transitions ------------------------------------------------------

test('a typed prompt sets the title and marks the session working', async ($, on) => {
  const w = engine(on)
  await start($)
  await $.prompt.submit(typed('Add the sessions board'))
  expect(mine(w.files).title).toBe('Add the sessions board')
  expect(mine(w.files).status).toBe('working')
})

test('a task notification prompt does not become the title', async ($, on) => {
  const w = engine(on)
  await start($)
  await $.prompt.submit({ ...typed('a job finished'), origin: { kind: 'task-notification' } } as never)
  expect(mine(w.files).title).toBe('')
})

test('a needs input: line marks the session needs-input with the rest of that line as the note', async ($, on) => {
  const w = engine(on)
  await start($)
  await $.prompt.submit(typed('go'))
  await $.turn.complete(answered('Looked around.\nneeds input: which repo?\nmore text after'))
  expect(mine(w.files).status).toBe('needs-input')
  expect(mine(w.files).note).toBe('which repo?')
})

test('a turn that needs you notifies with the project and title', async ($, on) => {
  const w = engine(on)
  await start($)
  await $.prompt.submit(typed('Add the sessions board'))
  await $.turn.complete(answered('needs input: which repo?'))
  expect(w.notes).toEqual(['core · Add the sessions board|needs input: which repo?'])
})

test('a result: line marks the session finished', async ($, on) => {
  const w = engine(on)
  await start($)
  await $.prompt.submit(typed('go'))
  await $.turn.complete(answered('All good.\n\nresult: Shipped PR #12'))
  expect(mine(w.files).status).toBe('finished')
  expect(mine(w.files).note).toBe('Shipped PR #12')
})

test("a subagent's turn leaves the session's status alone", async ($, on) => {
  const w = engine(on)
  await start($)
  await $.prompt.submit(typed('go'))
  await $.turn.complete(answered('result: nope', 'agent-1'))
  expect(mine(w.files).status).toBe('working')
})

// --- the session's name -------------------------------------------------------

const rename = (args: string) => slashCommand('rename', args)

test('/rename <name> names the session on the board', async ($, on) => {
  const w = engine(on)
  await start($)
  await $.command.run(rename('board work'))
  expect(mine(w.files).name).toBe('board work')
})

test('renaming a session keeps its first prompt', async ($, on) => {
  const w = engine(on)
  await start($)
  await $.prompt.submit(typed('Add the sessions board'))
  await $.command.run(rename('board work'))
  expect(mine(w.files).title).toBe('Add the sessions board')
})

test('a bare /rename takes the name it generated from the transcript', async ($, on) => {
  const w = engine(on)
  await start($)
  nameInTranscript(w.files, 'first name')
  nameInTranscript(w.files, 'generated name')
  await $.command.run(rename(''))
  expect(mine(w.files).name).toBe('generated name')
})

test('a /rename the engine refused keeps the name the session had', async ($, on) => {
  const w = engine(on)
  await start($)
  await $.command.run(rename('board work'))
  w.renameRefused = true
  await $.command.run(rename('not kept'))
  expect(mine(w.files).name).toBe('board work')
})

test('a resumed session starts with the name its transcript holds', async ($, on) => {
  const w = engine(on)
  nameInTranscript(w.files, 'board work')
  await start($)
  expect(mine(w.files).name).toBe('board work')
})

test('a session never renamed has no name', async ($, on) => {
  const w = engine(on)
  await start($)
  expect(mine(w.files).name).toBe('')
})

test('the pane shows a named session by its name in place of its first prompt', async ($, on) => {
  const w = engine(on)
  other(w.files, 'named', { name: 'board work', title: 'Add the sessions board' })
  await start($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  const text = (await ui.findAll({ type: 'Text' })).map(n => n.text).join('\n')
  expect(text).toContain('board work')
  expect(text).not.toContain('Add the sessions board')
  await ui.unmount()
})

test('the pane shows a record with no name field, as an older version wrote it, by its first prompt', async ($, on) => {
  const w = engine(on)
  other(w.files, 'older', { title: 'Fix the login bug' })
  expect(JSON.parse(w.files.get(`${DIR}/older.json`) ?? '{}')).not.toHaveProperty('name')
  await start($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  const text = (await ui.findAll({ type: 'Text' })).map(n => n.text).join('\n')
  expect(text).toContain('Fix the login bug')
  await ui.unmount()
})

test("a named session's notification carries its name", async ($, on) => {
  const w = engine(on)
  await start($)
  await $.prompt.submit(typed('Add the sessions board'))
  await $.command.run(rename('board work'))
  await $.turn.complete(answered('needs input: which repo?'))
  expect(w.notes).toEqual(['core · board work|needs input: which repo?'])
})

// --- permission asks ---------------------------------------------------------

test('a permission ask marks the session needs-permission with the command', async ($, on) => {
  const w = engine(on)
  on('tool.check', () => ({ decision: 'ask' as const }))
  await start($)
  await $.tool.check(permissionAsk)
  expect(mine(w.files).status).toBe('permission')
  expect(mine(w.files).note).toBe('Bash: git push')
})

test('a permission ask still held after the grace period notifies', async ($, on) => {
  const w = engine(on)
  on('tool.check', () => ({ decision: 'ask' as const }))
  await start($)
  await $.tool.check(permissionAsk)
  expect(w.notes).toEqual([])
  await w.fireTimers()
  expect(w.notes).toEqual(['core|needs permission: Bash: git push'])
})

test('an ask the classifier settles before the grace period never notifies', async ($, on) => {
  const w = engine(on)
  on('tool.check', () => ({ decision: 'ask' as const }))
  on('tool.judge', () => ({ decision: 'allow' as const }))
  await start($)
  await $.tool.check(permissionAsk)
  await $.tool.judge(permissionAsk)
  await w.fireTimers()
  expect(w.notes).toEqual([])
  expect(mine(w.files).status).toBe('working')
})

test('an allowed call goes back to working as it starts to run', async ($, on) => {
  const w = engine(on)
  on('tool.check', () => ({ decision: 'ask' as const }))
  await start($)
  await $.tool.check(permissionAsk)
  await $.tool.run({ tool: 'Bash', command: 'git push', tool_use_id: 'call-1' } as never)
  expect(mine(w.files).status).toBe('working')
})

// --- the board ---------------------------------------------------------------

test('the pane lists sessions that need you before the others', async ($, on) => {
  const w = engine(on)
  other(w.files, 'web', { status: 'finished', note: 'deployed' })
  other(w.files, 'aura', { status: 'permission', note: 'Bash: git push' })
  await start($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  const text = (await ui.findAll({ type: 'Text' })).map(n => n.text).join('\n')
  expect(text.indexOf('aura')).toBeLessThan(text.indexOf('web'))
  await ui.unmount()
})

test('the pane leaves out ended sessions', async ($, on) => {
  const w = engine(on)
  other(w.files, 'gone', { status: 'ended' })
  await start($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  const text = (await ui.findAll({ type: 'Text' })).map(n => n.text).join('\n')
  expect(text).not.toContain('gone')
  await ui.unmount()
})

test('the pane leaves out sessions whose heartbeat went stale', async ($, on) => {
  const w = engine(on)
  other(w.files, 'crashed', { status: 'working', beat: 1 })
  await start($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  const text = (await ui.findAll({ type: 'Text' })).map(n => n.text).join('\n')
  expect(text).not.toContain('crashed')
  await ui.unmount()
})

test('the band names another session that needs you, and what it waits on', async ($, on) => {
  const w = engine(on)
  other(w.files, 'aura', { status: 'permission', note: 'Bash: git push' })
  await start($)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' } as never)
  const text = (await ui.findAll({ type: 'Text' })).map(n => n.text).join('\n')
  expect(text).toContain('aura')
  expect(text).toContain('needs permission · Bash: git push')
  await ui.unmount()
})

test('dismissing the band hides it until a session changes', async ($, on) => {
  const w = engine(on)
  other(w.files, 'aura', { status: 'permission', since: 5 })
  await start($)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' } as never)
  await ui.press({ key: 'session-board-dismiss' })
  await ui.unmount()

  const hidden = await $.ui.mount({ ...BAND, surface: 'terminal' } as never)
  expect((await hidden.find({ type: 'Text' }))?.text).toBe('engine')
  await hidden.unmount()

  other(w.files, 'aura', { status: 'permission', since: 6 })
  await $.command.run({ command: 'sessions', args: 'go nobody', origin: { kind: 'composer' }, presentation: 'text' } as never)
  const back = await $.ui.mount({ ...BAND, surface: 'terminal' } as never)
  const text = (await back.findAll({ type: 'Text' })).map(n => n.text).join('\n')
  expect(text).toContain('aura')
  await back.unmount()
})

// --- switching ---------------------------------------------------------------

test("Go on a pane row runs the focus script with that session's tty and job", async ($, on) => {
  const w = engine(on)
  other(w.files, 'aura', { status: 'permission', tty: 'ttys009' })
  other(w.files, 'job', { status: 'finished', jobId: 'job-7' })
  await start($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'session-board-go-aura' })
  await ui.press({ key: 'session-board-go-job' })
  expect(focused(w.runs)).toEqual([
    ['ttys009', ''],
    ['', 'job-7'],
  ])
  await ui.unmount()
})

test('Go on the band runs the focus script for that session', async ($, on) => {
  const w = engine(on)
  other(w.files, 'aura', { status: 'permission', tty: 'ttys009' })
  await start($)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' } as never)
  await ui.press({ key: 'session-board-go-aura' })
  expect(focused(w.runs)).toEqual([['ttys009', '']])
  await ui.unmount()
})

const sessionsGo = (args: string) => slashCommand('sessions', args)

test('/sessions go switches to the session that has waited on you longest', async ($, on) => {
  const w = engine(on)
  other(w.files, 'web', { status: 'finished', since: 50, tty: 'ttys002' })
  other(w.files, 'aura', { status: 'permission', since: 20, tty: 'ttys003' })
  other(w.files, 'docs', { status: 'question', since: 10, tty: 'ttys004' })
  await start($)
  expect((await $.command.run(sessionsGo('go'))).text).toBe('Switched to docs (asking you).')
  expect(focused(w.runs)).toEqual([['ttys004', '']])
})

test('/sessions go <project> switches to the session of that project', async ($, on) => {
  const w = engine(on)
  other(w.files, 'web', { status: 'finished', tty: 'ttys002' })
  other(w.files, 'aura', { status: 'permission', tty: 'ttys003' })
  await start($)
  expect((await $.command.run(sessionsGo('go we'))).text).toBe('Switched to web (finished).')
  expect(focused(w.runs)).toEqual([['ttys002', '']])
})

test('/sessions go <project> with no match switches nowhere', async ($, on) => {
  const w = engine(on)
  other(w.files, 'web', { status: 'finished' })
  await start($)
  expect((await $.command.run(sessionsGo('go nope'))).text).toBe('No other session matches "nope".')
  expect(focused(w.runs)).toEqual([])
})

// --- cleaning ----------------------------------------------------------------

const sessionsClean = slashCommand('sessions', 'clean')

const removals = (runs: string[][]) => runs.filter(a => a[0] === '/bin/rm')

test('/sessions clean removes ended and stale files and keeps live ones', async ($, on) => {
  const w = engine(on)
  other(w.files, 'live', { status: 'working' })
  other(w.files, 'gone', { status: 'ended' })
  other(w.files, 'crashed', { status: 'working', beat: 1 })
  await start($)
  expect((await $.command.run(sessionsClean)).text).toBe('Removed 2 status files.')
  expect([...w.files.keys()].sort()).toEqual([`${DIR}/live.json`, `${DIR}/me-1.json`])
})

test('/sessions clean removes files untouched for over a day', async ($, on) => {
  const w = engine(on)
  w.files.set(`${DIR}/old.json`, 'not json')
  w.mtimes.set(`${DIR}/old.json`, -100_000_000)
  await start($)
  expect((await $.command.run(sessionsClean)).text).toBe('Removed 1 status file.')
  expect(w.files.has(`${DIR}/old.json`)).toBe(false)
})

test("/sessions clean never removes this session's own file, even one that reads as ended", async ($, on) => {
  const w = engine(on)
  await start($)
  w.files.set(`${DIR}/me-1.json`, JSON.stringify({ ...mine(w.files), status: 'ended', beat: 1 }))
  w.mtimes.set(`${DIR}/me-1.json`, -100_000_000)
  expect((await $.command.run(sessionsClean)).text).toBe('No ended or stale status files to remove.')
  expect(w.files.has(`${DIR}/me-1.json`)).toBe(true)
  expect(removals(w.runs)).toEqual([])
})

test('/sessions clean keeps a recent file it cannot read, and files that are not status files', async ($, on) => {
  const w = engine(on)
  w.files.set(`${DIR}/half-written.json`, '{"id":')
  w.files.set(`${DIR}/notes.txt`, 'ended')
  w.mtimes.set(`${DIR}/notes.txt`, -100_000_000)
  await start($)
  expect((await $.command.run(sessionsClean)).text).toBe('No ended or stale status files to remove.')
  expect(w.files.has(`${DIR}/half-written.json`)).toBe(true)
  expect(w.files.has(`${DIR}/notes.txt`)).toBe(true)
})

test('/sessions clean runs rm once, on exact paths inside the session-board folder', async ($, on) => {
  const w = engine(on)
  other(w.files, 'gone', { status: 'ended' })
  other(w.files, 'crashed', { status: 'idle', beat: 1 })
  await start($)
  await $.command.run(sessionsClean)
  const rm = removals(w.runs)
  expect(rm.length).toBe(1)
  expect(rm[0]?.slice(0, 3)).toEqual(['/bin/rm', '-f', '--'])
  expect(rm[0]?.slice(3).sort()).toEqual([`${DIR}/crashed.json`, `${DIR}/gone.json`])
})

test('/sessions clean says how many it removed when rm fails', async ($, on) => {
  const w = engine(on, { rmError: 'rm: gone.json: Permission denied\n' })
  other(w.files, 'gone', { status: 'ended' })
  await start($)
  expect((await $.command.run(sessionsClean)).text).toBe('Removed 0 status files of 1: rm: gone.json: Permission denied')
  expect(w.files.has(`${DIR}/gone.json`)).toBe(true)
})

test('/sessions clean removes nothing when HOME is not an absolute path', async ($, on) => {
  const w = engine(on, { home: '' })
  w.files.set('/.claude/session-board/gone.json', JSON.stringify({ id: 'gone', status: 'ended', beat: 1 }))
  await start($)
  expect((await $.command.run(sessionsClean)).text).toBe('The session board has not started yet.')
  expect(removals(w.runs)).toEqual([])
})

// --- gating hooks: the board's own faults never change what they gate --------

test('a prompt outside the schema goes through untouched', async ($, on) => {
  engine(on)
  await start($)
  expect(await $.prompt.submit({ text: 'hi', wait: false } as never)).toEqual({ text: 'hi' })
})

test('a permission verdict stands when the call it asks about is outside the schema', async ($, on) => {
  engine(on)
  on('tool.check', () => ({ decision: 'ask' as const }))
  await start($)
  const verdict = await $.tool.check({ input: {}, tool_use_id: 'call-1', approver: 'person' } as never)
  expect(verdict).toEqual({ decision: 'ask' })
})

test("the classifier's verdict stands when the board cannot write its file", async ($, on) => {
  const w = engine(on)
  on('tool.check', () => ({ decision: 'ask' as const }))
  on('tool.judge', () => ({ decision: 'allow' as const }))
  await start($)
  w.writeError = 'disk full'
  await $.tool.check(permissionAsk)
  expect(await $.tool.judge(permissionAsk)).toEqual({ decision: 'allow' })
})

test("a run's result stands when the board cannot write its file", async ($, on) => {
  const w = engine(on)
  on('tool.check', () => ({ decision: 'ask' as const }))
  await start($)
  w.writeError = 'disk full'
  await $.tool.check(permissionAsk)
  expect(await $.tool.run({ tool: 'Bash', command: 'git push', tool_use_id: 'call-1' } as never)).toEqual({ result: {} })
})

test("a question's result stands when its question is outside the schema", async ($, on) => {
  engine(on)
  await start($)
  const call = { tool: 'AskUserQuestion', questions: [{ question: 7 }], tool_use_id: 'call-2' } as never
  expect(await $.tool.call(call)).toEqual({ result: {} })
})

test("/rename's answer stands when the board cannot write its file", async ($, on) => {
  const w = engine(on)
  await start($)
  w.writeError = 'disk full'
  expect(await $.command.run(rename('board work'))).toEqual({ text: 'Session renamed to: board work' })
})

test('an error beneath a gating hook still reaches the caller', async ($, on) => {
  engine(on)
  await start($)
  // Nothing beneath answers tool.check here, so the engine's dispatch fails.
  await expect($.tool.check(permissionAsk)).rejects.toThrow('no implementation for tool.check')
})
