import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'

const HOME = '/home/me'
const DIR = `${HOME}/.claude/session-board`
const FRESH = 9_999_999_999
const TRANSCRIPT = '/home/me/.claude/projects/work-core/me-1.jsonl'

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
  notes: string[]
  runs: string[][]
  /** Fires the timers `$.clock.after` booked, as if their time came. */
  fireTimers: () => Promise<void>
}

/** Stands in for the engine: a file system in memory, a stepping clock, one session. */
function engine(on: On): World {
  const files: Files = new Map()
  const notes: string[] = []
  const runs: string[][] = []
  const timers: (() => void)[] = []
  let t = 1_000_000
  on('clock.now', () => ({ value: (t += 1000) }))
  on('clock.every', () => ({ value: undefined }))
  on('clock.after', () => new Promise(done => timers.push(() => done({ value: undefined }))))
  on('env.get', () => ({ value: HOME }))
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
    return { value: { exitCode: 0, stdout: '??\n', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('fs.write', (_, e) => {
    files.set(e.path, e.text)
    return { value: undefined }
  })
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
      mtimeMs: t,
      isLink: false,
    })),
  }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('prompt.submit', (_, e) => ({ text: e.text }))
  on('turn.complete', () => ({ text: '' }))
  on('tool.call', () => ({ result: {} }))
  on('tool.run', () => ({ result: {} }))
  on('command.run', () => ({ text: '' }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })

  const fireTimers = async () => {
    for (const fire of timers.splice(0)) fire()
    // The timer's callback runs once its dispatch resolves.
    for (let i = 0; i < 50; i++) await Promise.resolve()
  }
  return { files, notes, runs, fireTimers }
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

// --- the session's name -------------------------------------------------------

/** The transcript lines `/rename` leaves: the name it set, among the conversation's own rows. */
function renamed(files: Files, ...names: string[]) {
  const rows = names.flatMap(name => [
    JSON.stringify({ type: 'user', message: { role: 'user', content: 'hello' } }),
    JSON.stringify({ type: 'custom-title', customTitle: name, sessionId: 'me-1' }),
  ])
  files.set(TRANSCRIPT, `${rows.join('\n')}\n`)
}

const rename = (args: string) =>
  ({ command: 'rename', args, origin: { kind: 'composer' }, presentation: 'text' }) as never

test('/rename <name> names the session on the board', async ($, on) => {
  const w = engine(on)
  await start($)
  await $.prompt.submit(typed('Add the sessions board'))
  await $.command.run(rename('board work'))
  expect(mine(w.files).name).toBe('board work')
  expect(mine(w.files).title).toBe('Add the sessions board')
})

test('a bare /rename takes the name it generated from the transcript', async ($, on) => {
  const w = engine(on)
  await start($)
  renamed(w.files, 'first name', 'generated name')
  await $.command.run(rename(''))
  expect(mine(w.files).name).toBe('generated name')
})

test('a resumed session starts with the name its transcript holds', async ($, on) => {
  const w = engine(on)
  renamed(w.files, 'board work')
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
  other(w.files, 'plain', { title: 'Fix the login bug' })
  await start($)
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  const text = (await ui.findAll({ type: 'Text' })).map(n => n.text).join('\n')
  expect(text).toContain('board work')
  expect(text).not.toContain('Add the sessions board')
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
