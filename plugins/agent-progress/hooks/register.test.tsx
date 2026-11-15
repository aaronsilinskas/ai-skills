import { expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On } from 'claude-code'

const PLUGIN = 'agent-progress'
const PROGRESS = 'mcp__agent-progress__progress'
const STEP = 'mcp__agent-progress__step'

const BAND = { hasSurvey: false, isWorking: false, maxRows: 4, bodyColumns: 100, scroll: { offset: 0, bodyRows: 4 }, view: {} }
const PANE = { title: 'Agents', isFocused: false, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 30 }, view: {} } as const

/** Stands in for core beneath the plugin: spawns hand out ids, prompts are recorded. */
function core(on: On) {
  const prompts: string[] = []
  const opened: string[] = []
  let n = 0
  mock.clock(on, { now: Date.parse('2026-11-15T12:00:00Z') })
  on('agent.spawn', (_$, e) => {
    prompts.push(e.prompt)
    n += 1
    return { model: 'claude-opus-5-5', agentId: `agent-${n}` }
  })
  on('turn.complete', () => ({ text: '' }))
  on('turn.start', (_$, e) => ({ turnId: e.turnId }))
  on('ui.open', (_$, e) => {
    opened.push(e.id)
    return { value: { isPlaced: true } }
  })
  return { prompts, opened }
}

const spawn = ($: Engine, description: string) =>
  $.agent.spawn({ tool_use_id: `tu-${description}`, prompt: `Do: ${description}`, description, subagentType: 'general-purpose' } as never)

const finish = ($: Engine, agentId: string, reason: 'answer' | 'error' = 'answer') =>
  $.turn.complete({ agentId, reason, answer: '', durationMs: 10, isAborted: false, turnId: `t-${agentId}` } as never)

async function bandText($: Engine) {
  const ui = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', component: 'AbovePrompt', props: BAND as never })
  const texts = (await ui.findAll({ type: 'Text' })).map(t => t.text).join(' | ')
  const crew = (await ui.find({ key: 'agent-progress-open' }))?.props.label
  await ui.unmount()
  return { texts, crew }
}

test('no band until a subagent starts', async ($, on) => {
  core(on)
  const ui = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', component: 'AbovePrompt', props: BAND as never })
  expect(await ui.find({ key: 'agent-progress-open' })).toBeUndefined()
  await ui.unmount()
})

test('the band counts subagents as they start and finish', async ($, on) => {
  core(on)
  const a = await spawn($, 'Read the parser')
  const b = await spawn($, 'Read the CLI')

  let band = await bandText($)
  expect(band.texts).toContain('0/2 · 2 running')
  expect(band.crew).toBe('Agents ×2')

  await finish($, a.agentId ?? '')
  band = await bandText($)
  expect(band.texts).toContain('1/2 · 1 running')

  await finish($, b.agentId ?? '', 'error')
  // The main turn ends with nothing running: the automatic run is done.
  await $.turn.complete({ reason: 'answer', answer: '', durationMs: 10, isAborted: false, turnId: 'main' } as never)
  band = await bandText($)
  expect(band.texts).toContain('Done · 1 failed')
})

test('every subagent is asked to report steps, once', async ($, on) => {
  const { prompts } = core(on)
  await spawn($, 'Write tests')
  await $.agent.spawn({ tool_use_id: 'x', prompt: `Already briefed: use ${STEP}`, description: 'x', subagentType: 'Explore' } as never)
  expect(prompts[0]).toContain(STEP)
  expect(prompts[1]?.split(STEP).length).toBe(2)
})

test('a subagent step report shows in the panel', async ($, on) => {
  core(on)
  const { agentId } = await spawn($, 'Refactor module')
  expect(await $.tool.call({ tool: STEP, agentId, done: 1, total: 3, note: 'parsing' } as never)).toMatchObject({ result: 'ok' })

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: PLUGIN, surface, component: 'Pane', requestId: 'agent-progress', props: PANE as never })
    expect(await ui.find({ type: 'Text', text: /1\/3 · parsing/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /Running · 1/ })).toBeDefined()
    await ui.unmount()
  }
})

test('a reported plan drives the band and lists unstarted tasks', async ($, on) => {
  const { opened } = core(on)
  const plan = { tool: PROGRESS, title: 'Ship it', tasks: [{ title: 'Write the parser' }, { title: 'Wire the CLI', after: [1] }] }
  expect(await $.tool.call(plan as never)).toMatchObject({ result: 'ok: 0/2' })
  expect(opened).toEqual(['agent-progress'])

  await spawn($, 'Write the parser')
  const band = await bandText($)
  expect(band.texts).toContain('Ship it')
  expect(band.texts).toContain('0/2 · 1 running')
  // One started, one still planned.
  expect(band.crew).toBe('Agents ×2')

  const ui = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', component: 'Pane', requestId: 'agent-progress', props: PANE as never })
  expect(await ui.find({ type: 'Text', text: /2\. Wire the CLI\s+\(after 1\)/ })).toBeDefined()
  await ui.unmount()

  expect(await $.tool.call({ tool: PROGRESS, done: 1 } as never)).toMatchObject({ result: 'ok: 1/2 · 1 running' })
  expect(await $.tool.call({ tool: PROGRESS, finished: true } as never)).toMatchObject({ result: 'ok: Done' })
})

test('a subagent cannot change the plan', async ($, on) => {
  core(on)
  await $.tool.call({ tool: PROGRESS, title: 'Mine', total: 3 } as never)
  const r = await $.tool.call({ tool: PROGRESS, agentId: 'agent-9', finished: true } as never)
  expect(String((r as { result?: unknown }).result)).toContain('ignored')
  expect((await bandText($)).texts).toContain('0/3')
})

// The schema is advice to the model: input outside it must still draw.
test('input outside the schema is bounded', async ($, on) => {
  core(on)
  const tasks = [{ title: '__proto__' }, { title: 7 }, null, ...Array.from({ length: 500 }, (_, i) => ({ title: `Task ${i}` }))]
  expect(await $.tool.call({ tool: PROGRESS, title: 'Odd', tasks, total: 1e9, done: -4 } as never)).toMatchObject({ result: 'ok: 0/200' })
  const ui = await $.ui.mount({ plugin: PLUGIN, surface: 'desktop', component: 'AbovePrompt', props: BAND as never })
  const svg = (await ui.findAll({ type: 'Svg' })).map(el => String(el.props.source)).join('')
  expect(svg).toContain('0/200')
  expect(svg).not.toContain('[object')
  await ui.unmount()
})
