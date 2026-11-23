import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'

const HOME = '/home/me'
const DIR = `${HOME}/.claude/session-board`
const FRESH = 9_999_999_999

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
  /** Fires the timers `$.clock.after` booked, as if their time came. */
  fireTimers: () => Promise<void>
}

/** Stands in for the engine: a file system in memory, a stepping clock, one session. */
/** A finished process's result. */
const exited = (exitCode: number, stdout: string, stderr = '') =>
  ({ value: { exitCode, stdout, stderr, isStdoutTruncated: false, isStderrTruncated: false } }) as const

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
    files.set(e.path, e.text)
    return { value: undefined }
  })
  on('fs.exists', (_, e) => ({ value: files.has(e.path) }))
  on('fs.read', (_, e) => ({ value: files.get(e.path) ?? '' }))
  on('fs.list', () => ({
    value: [...files.keys()].map(p => ({
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
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })

  const fireTimers = async () => {
    for (const fire of timers.splice(0)) fire()
    // The timer's callback runs once its dispatch resolves.
    for (let i = 0; i < 50; i++) await Promise.resolve()
  }
  return { files, mtimes, notes, runs, fireTimers }
}

/** Another session's status file, live unless `beat` says otherwise. */
function other(files: Files, id: string, fields: Record<string, unknown>) {
  const record = { id, project: id, cwd: '/', title: `task ${id}`, status: 'working', since: 1, note: '', beat: FRESH, tty: '', jobId: '', ...fields }
  files.set(`${DIR}/${id}.json`, JSON.stringify(record))
}

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

const sessionsGo = (args: string) =>
  ({ command: 'sessions', args, origin: { kind: 'composer' }, presentation: 'text' }) as never

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

const sessionsClean = { command: 'sessions', args: 'clean', origin: { kind: 'composer' }, presentation: 'text' } as never

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
