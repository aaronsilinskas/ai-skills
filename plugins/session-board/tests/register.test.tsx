import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

const HOME = '/home/me'
const DIR = `${HOME}/.claude/session-board`

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

type Files = Map<string, string>

/** Stands in for the engine: a file system in memory, a fixed clock and session. */
function engine(on: On, files: Files, notes: string[]) {
  let t = 1_000_000
  on('clock.now', () => ({ value: (t += 1000) }))
  on('clock.every', () => ({ value: undefined }))
  on('clock.after', () => ({ value: undefined }))
  on('env.get', () => ({ value: HOME }))
  on('session.id', () => ({ value: 'me-1' }))
  on('session.root', () => ({ value: '/work/core' }))
  on('command.register', () => ({ value: { command: 'sessions' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.notify', (_, e) => {
    notes.push(`${e.title}|${e.text}`)
    return { value: { isSent: true, channel: 'client' as const } }
  })
  on('fs.write', (_, e) => {
    files.set(e.path, e.text)
    return { value: undefined }
  })
  on('fs.read', (_, e) => ({ value: files.get(e.path) ?? '' }))
  on('fs.list', () => ({
    value: [...files.keys()].map(p => ({ name: p.split('/').at(-1) ?? '', kind: 'file' as const, size: 1, mtimeMs: t, isLink: false })),
  }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('prompt.submit', (_, e) => ({ text: e.text }))
  on('turn.complete', () => ({ text: '' }))
}

/** A prompt typed at the composer. */
const typed = (text: string) => ({ text, wait: false, origin: { kind: 'composer' as const } })

const mine = (files: Files) => JSON.parse(files.get(`${DIR}/me-1.json`) ?? '{}')

test('a turn ending in needs input: marks the session and notifies', async ($, on) => {
  const files: Files = new Map()
  const notes: string[] = []
  engine(on, files, notes)

  await $.session.start({ cwd: '/work/core', surface: 'terminal', isInteractive: true })
  expect(mine(files).status).toBe('idle')

  await $.prompt.submit({ ...typed('a job finished'), origin: { kind: 'task-notification' } } as never)
  expect(mine(files).title).toBe('')

  await $.prompt.submit(typed('Add the sessions board'))
  expect(mine(files).status).toBe('working')
  expect(mine(files).title).toBe('Add the sessions board')

  await $.turn.complete({
    answer: 'Looked around.\nneeds input: which repo should this go in?',
    durationMs: 10,
    isAborted: false,
    turnId: 't1',
    reason: 'answer',
  })
  expect(mine(files).status).toBe('needs-input')
  expect(mine(files).note).toBe('which repo should this go in?')
  expect(notes).toEqual(['core · Add the sessions board|needs input: which repo should this go in?'])
})

test('a result: line finishes the session; a subagent turn changes nothing', async ($, on) => {
  const files: Files = new Map()
  engine(on, files, [])
  await $.session.start({ cwd: '/work/core', surface: 'terminal', isInteractive: true })
  await $.prompt.submit(typed('go'))

  await $.turn.complete({ answer: 'result: nope', durationMs: 1, isAborted: false, turnId: 's', agentId: 'a1', reason: 'answer' })
  expect(mine(files).status).toBe('working')

  await $.turn.complete({ answer: 'All good.\n\nresult: Shipped PR #12', durationMs: 1, isAborted: false, turnId: 't', reason: 'answer' })
  expect(mine(files).status).toBe('finished')
  expect(mine(files).note).toBe('Shipped PR #12')
})

test('the pane lists other sessions, needs-you first', async ($, on) => {
  const files: Files = new Map()
  engine(on, files, [])
  const other = (id: string, status: string, note: string) =>
    files.set(
      `${DIR}/${id}.json`,
      JSON.stringify({ id, project: id, cwd: '/', title: `task ${id}`, status, since: 1, note, beat: 9_999_999_999, tty: id === 'aura' ? 'ttys009' : '', jobId: id === 'web' ? 'job-web' : '' }),
    )
  other('web', 'finished', 'deployed')
  other('aura', 'permission', 'Bash: git push')
  other('gone', 'ended', '')

  await $.session.start({ cwd: '/work/core', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })

  const texts = (await ui.findAll({ type: 'Text' })).map(n => n.text)
  const joined = texts.join('\n')
  expect(joined).toContain('needs permission')
  expect(joined).toContain('Bash: git push')
  expect(joined).not.toContain('gone')
  expect(joined.indexOf('aura')).toBeLessThan(joined.indexOf('web'))
  await ui.unmount()
})

test('Go on a pane row runs the focus script for that session', async ($, on) => {
  const files: Files = new Map()
  engine(on, files, [])
  const runs: string[][] = []
  on('process.run', (_, e) => {
    runs.push([...e.argv])
    return { value: { exitCode: 0, stdout: '??\n', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  files.set(
    `${DIR}/aura.json`,
    JSON.stringify({ id: 'aura', project: 'aura', cwd: '/', title: 't', status: 'permission', since: 1, note: 'n', beat: 9_999_999_999, tty: 'ttys009', jobId: '' }),
  )
  await $.session.start({ cwd: '/work/core', surface: 'terminal', isInteractive: true })
  expect(mine(files).tty).toBe('')

  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await ui.press({ key: 'session-board-go-aura' })
  const focus = runs.find(a => (a[1] ?? '').endsWith('/bin/focus-session.sh'))
  expect(focus?.slice(2)).toEqual(['ttys009', ''])
  await ui.unmount()
})

test('/sessions go switches to the session waiting on you longest', async ($, on) => {
  const files: Files = new Map()
  engine(on, files, [])
  const runs: string[][] = []
  on('process.run', (_, e) => {
    runs.push([...e.argv])
    return { value: { exitCode: 0, stdout: '??\n', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  const other = (id: string, status: string, since: number, tty: string) =>
    files.set(
      `${DIR}/${id}.json`,
      JSON.stringify({ id, project: id, cwd: '/', title: 't', status, since, note: '', beat: 9_999_999_999, tty, jobId: '' }),
    )
  other('web', 'finished', 50, 'ttys002')
  other('aura', 'permission', 20, 'ttys003')
  other('docs', 'question', 10, 'ttys004')
  await $.session.start({ cwd: '/work/core', surface: 'terminal', isInteractive: true })

  const go = (args: string) =>
    $.command.run({ command: 'sessions', args, origin: { kind: 'composer' }, presentation: 'text' } as never)
  const focused = () => runs.filter(a => (a[1] ?? '').endsWith('/bin/focus-session.sh')).map(a => a[2])

  expect((await go('go')).text).toBe('Switched to docs (asking you).')
  expect((await go('go web')).text).toBe('Switched to web (finished).')
  expect((await go('go nope')).text).toBe('No other session matches "nope".')
  expect(focused()).toEqual(['ttys004', 'ttys002'])
})
