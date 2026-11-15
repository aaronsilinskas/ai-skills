import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { AgentRun, Panel, PlannedTask, Run } from '../types'

// Bump a shape tag when that value's fields change: it declines what an
// earlier version stored, which outlives a reload.
const run = atom({ plugin: 'agent-progress', key: 'run' } as const, null, { shape: 'run-1' })
const agents = atom({ plugin: 'agent-progress', key: 'agents' } as const, [], { shape: 'agents-1' })
const panel = atom(
  { plugin: 'agent-progress', key: 'panel' } as const,
  { isCompact: false, isDoneCollapsed: false, autoOpenedFor: '' },
  { shape: 'panel-1' },
)
const now = atom({ plugin: 'agent-progress', key: 'now' } as const, 0)

const PANE = 'agent-progress'
const PANE_TITLE = 'Agents'
const PROGRESS_TOOL = 'mcp__agent-progress__progress'
const STEP_TOOL = 'mcp__agent-progress__step'
const AUTO_TITLE = 'Subagents'

// Appended to a subagent's prompt. A tool merely being listed is not enough:
// subagents follow a request in their brief, not one implied by a tool list.
const STEP_BRIEF = `

Progress reporting: before other work, call \`${STEP_TOOL}\` with \`total\` (your plan in 3-8 steps) and \`done: 0\`; call it again with \`done\` and a few-word \`note\` as each step finishes. It only draws a progress bar for the user.`

// The tools' schemas are advice to the model, not a check: what a call may
// ask the band and the panel to draw is bounded here.
const MAX_TASKS = 200
const MAX_AFTER = 20
const MAX_TITLE = 120
const MAX_NOTE = 80
const MAX_AGENTS = 200

const ACCENT = '#6c8cff'
const DONE = '#3fae74'
const FAILED = '#d0453f'

type ProgressInput = {
  title?: unknown
  total?: unknown
  done?: unknown
  finished?: unknown
  tasks?: unknown
}

type StepInput = { done?: unknown; total?: unknown; note?: unknown }

// ---------------------------------------------------------------------------
// Small helpers

const clip = (s: string, max: number): string => (s.length > max ? s.slice(0, Math.max(1, max - 1)) + '…' : s)

const str = (v: unknown): string => (typeof v === 'string' ? v.trim() : '')

const int = (v: unknown, min: number, max: number): number | undefined =>
  typeof v === 'number' && Number.isFinite(v) ? Math.min(max, Math.max(min, Math.round(v))) : undefined

const norm = (s: string): string => s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim()

const xml = (s: string): string =>
  s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] ?? c)

const fmtTokens = (n: number): string =>
  n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}k` : `${Math.round(n)}`

const fmtCost = (usd: number): string => `$${usd < 10 ? usd.toFixed(2) : usd.toFixed(1)}`

const fmtTime = (ms: number): string => {
  const s = Math.max(0, Math.round(ms / 1000))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

const textBar = (ratio: number, width: number): string => {
  const filled = Math.round(width * Math.min(1, Math.max(0, ratio)))
  return '█'.repeat(filled) + '░'.repeat(Math.max(0, width - filled))
}

// ---------------------------------------------------------------------------
// Models: names, context windows and an estimated price.

/** "claude-opus-5-5" → "Opus 5.5"; anything unrecognised shows as it came. */
const modelName = (id: string): string => {
  const m = /(fable|mythos|opus|sonnet|haiku)-(\d+)(?:-(\d{1,2})(?!\d))?/i.exec(id)
  if (!m) return id.replace(/^claude-/, '').replace(/\[.*\]$/, '') || 'unknown'
  const [, family = '', major = '', minor] = m
  return `${family.charAt(0).toUpperCase()}${family.slice(1).toLowerCase()} ${major}${minor ? '.' + minor : ''}`
}

const windowOf = (model: string): number => (/haiku-4|claude-3/i.test(model) ? 200_000 : 1_000_000)

// USD per million tokens: input, output, cache read, cache write. First match
// wins, so a release sits above its family. List prices as of 2026-11. The
// engine reports one cache-write count with no split by lifetime; writes are
// priced at the 1-hour rate (2x input), which is what Claude Code writes on a
// subscription, so sessions writing 5-minute entries are overestimated there.
type Price = [input: number, output: number, cacheRead: number, cacheWrite: number]

const PRICES: [RegExp, Price][] = [
  [/(fable|mythos)-5-2/, [8, 40, 0.2, 16]],
  [/(fable|mythos)-5-1/, [10, 50, 0.25, 20]],
  [/fable|mythos/, [10, 50, 1, 20]],
  [/opus-5-5/, [4, 20, 0.2, 8]],
  [/opus/, [5, 25, 0.5, 10]],
  [/sonnet-5-5/, [2, 10, 0.1, 4]],
  [/sonnet-5/, [2, 10, 0.2, 4]],
  [/sonnet/, [3, 15, 0.3, 6]],
  [/haiku-5-5/, [0.1, 0.5, 0.01, 0.2]],
  [/haiku/, [1, 5, 0.1, 2]],
]
const FALLBACK_PRICE: Price = [4, 20, 0.2, 8]

// Haiku 5.5 prompts over 100K tokens (input + cache reads + cache writes) pay more.
const HAIKU_LONG_PROMPT = 100_000
const HAIKU_LONG: Price = [0.5, 2.5, 0.05, 1]

type Usage = {
  input_tokens: number
  output_tokens: number
  cache_read_input_tokens: number
  cache_creation_input_tokens: number
}

const promptTokens = (u: Usage): number =>
  (u.input_tokens || 0) + (u.cache_read_input_tokens || 0) + (u.cache_creation_input_tokens || 0)

const allTokens = (u: Usage): number => promptTokens(u) + (u.output_tokens || 0)

/** `isRequest`: the usage is one request, so the prompt-length tier applies. */
const costOf = (model: string, u: Usage, isRequest: boolean): number => {
  const id = model.toLowerCase()
  const price =
    isRequest && promptTokens(u) > HAIKU_LONG_PROMPT && /haiku-5-5/.test(id)
      ? HAIKU_LONG
      : (PRICES.find(([re]) => re.test(id))?.[1] ?? FALLBACK_PRICE)
  const [i, o, r, w] = price
  return (
    ((u.input_tokens || 0) * i +
      (u.output_tokens || 0) * o +
      (u.cache_read_input_tokens || 0) * r +
      (u.cache_creation_input_tokens || 0) * w) /
    1e6
  )
}

// ---------------------------------------------------------------------------
// Runs: what the band tracks.

const newRun = (title: string, isReported: boolean, at: number): Run => ({
  title: clip(title, MAX_TITLE),
  isReported,
  total: 0,
  done: 0,
  tasks: [],
  isFinished: false,
  startedAt: at,
})

const cleanTasks = (v: unknown): PlannedTask[] | undefined => {
  if (!Array.isArray(v)) return undefined
  return v
    .filter((t): t is Record<string, unknown> => !!t && typeof t === 'object' && !!str((t as { title?: unknown }).title))
    .slice(0, MAX_TASKS)
    .map(t => ({
      title: clip(str(t.title), MAX_TITLE),
      after: (Array.isArray(t.after) ? t.after : [])
        .filter((n): n is number => Number.isInteger(n) && n > 0 && n <= MAX_TASKS)
        .slice(0, MAX_AFTER),
    }))
}

/** A new title, or a finished/automatic run, means a fresh reported run. */
const isNewReport = (prev: Run | null, input: ProgressInput): boolean => {
  if (!prev || prev.isFinished || !prev.isReported) return true
  const title = str(input.title)
  return title !== '' && clip(title, MAX_TITLE) !== prev.title
}

const mergeReport = (prev: Run | null, input: ProgressInput, at: number): Run => {
  const base = isNewReport(prev, input) || !prev ? newRun(str(input.title) || 'Plan', true, at) : prev
  const tasks = cleanTasks(input.tasks) ?? base.tasks
  const total = int(input.total, 0, MAX_TASKS) ?? (input.tasks !== undefined ? tasks.length : base.total)
  const done = Math.min(total || MAX_TASKS, int(input.done, 0, MAX_TASKS) ?? base.done)
  const isFinished = input.finished === true
  return { ...base, tasks, total, done: isFinished && total ? total : done, isFinished }
}

const runAgents = (r: Run, list: AgentRun[]): AgentRun[] => list.filter(a => a.startedAt >= r.startedAt)

type Counts = { total: number; done: number; running: number; failed: number }

const countsOf = (r: Run, list: AgentRun[]): Counts => {
  const mine = runAgents(r, list)
  const running = mine.filter(a => a.status === 'running').length
  const failed = mine.filter(a => a.status === 'failed').length
  if (r.isReported && r.total > 0) return { total: r.total, done: r.done, running, failed }
  return { total: mine.length, done: mine.length - running, running, failed }
}

const ratioOf = (r: Run, c: Counts): number => (r.isFinished ? 1 : c.total ? Math.min(1, c.done / c.total) : 0)

const labelOf = (r: Run, c: Counts): string => {
  if (r.isFinished) return c.failed ? `Done · ${c.failed} failed` : 'Done'
  const parts = [c.total ? `${c.done}/${c.total}` : 'starting']
  if (c.running) parts.push(`${c.running} running`)
  if (c.failed) parts.push(`${c.failed} failed`)
  return parts.join(' · ')
}

type Planned = PlannedTask & { n: number }

/** Planned tasks no agent has started yet, matched on the Agent description. */
const plannedOf = (r: Run | null, list: AgentRun[]): Planned[] => {
  if (!r || r.isFinished || !r.isReported) return []
  const started = new Set(runAgents(r, list).map(a => norm(a.description)))
  return r.tasks.map((t, i) => ({ ...t, n: i + 1 })).filter(t => !started.has(norm(t.title)))
}

// ---------------------------------------------------------------------------
// Agent rows

const elapsed = (a: AgentRun, at: number): number => (a.endedAt ?? Math.max(at, a.startedAt)) - a.startedAt

const ctxPct = (a: AgentRun): number =>
  a.contextMax ? Math.min(100, Math.round((a.contextTokens / a.contextMax) * 100)) : 0

/** The task's own progress when it reports steps; null otherwise. */
const stepRatio = (a: AgentRun): number | null => {
  if (a.status === 'done') return 1
  if (a.stepTotal) return Math.min(1, (a.stepDone ?? 0) / a.stepTotal)
  return null
}

const statusColor = (a: AgentRun): string =>
  a.status === 'failed' ? FAILED : a.status === 'done' ? DONE : ACCENT

const GLYPH: Record<string, string> = { running: '●', done: '✓', failed: '✗', planned: '○' }

const totals = (list: AgentRun[], at: number) => {
  if (!list.length) return { cost: 0, tokens: 0, time: 0 }
  const start = Math.min(...list.map(a => a.startedAt))
  const end = Math.max(...list.map(a => a.endedAt ?? Math.max(at, a.startedAt)))
  return {
    cost: list.reduce((s, a) => s + a.costUsd, 0),
    tokens: list.reduce((s, a) => s + a.tokens, 0),
    time: end - start,
  }
}

// ---------------------------------------------------------------------------
// Desktop drawings. The desktop wraps sibling elements of a band onto new
// lines, so the band's title, bar and label are one SVG.

const FONT = "-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',sans-serif"
const BAND_H = 22
const TRACK_H = 10

// Rough advance of UI text in em, for sizing the title's slot.
const textWidth = (s: string, size: number): number =>
  [...s].reduce((w, ch) => w + (/[\s.,:;'|!il1()]/.test(ch) ? 0.3 : /[A-Zmw@%]/.test(ch) ? 0.72 : 0.56) * size, 0)

const fitText = (s: string, size: number, maxW: number): string => {
  if (textWidth(s, size) <= maxW) return s
  let out = ''
  for (const ch of s) {
    if (textWidth(out + ch + '…', size) > maxW) break
    out += ch
  }
  return out + '…'
}

const SVG_CSS = `<style>
.t{fill:#1f1f1f}.m{fill:#77776f}.k{fill:#e6e5e1}
@media (prefers-color-scheme: dark){.t{fill:#ececec}.m{fill:#9a9a96}.k{fill:#30302e}}
.live{animation:p 1.4s ease-in-out infinite}@keyframes p{50%{opacity:.35}}
.flow{animation:f 1s linear infinite}@keyframes f{to{transform:translateX(12px)}}
@media (prefers-reduced-motion: reduce){.live,.flow{animation:none}}
</style>`

const bandSvg = (r: Run, c: Counts, W: number): string => {
  const ratio = ratioOf(r, c)
  const color = r.isFinished ? (c.failed ? FAILED : DONE) : ACCENT
  const label = labelOf(r, c)
  const percent = `${Math.round(ratio * 100)}%`
  const title = fitText(r.title, 13, Math.max(60, W * 0.3))
  const labelW = Math.ceil(textWidth(label, 12)) + 8
  const barX = Math.round(18 + textWidth(title, 13) + 12)
  const barW = Math.max(60, W - barX - labelW - 44)
  const fillW = Math.round(barW * ratio)
  const runW = c.total && !r.isFinished ? Math.round((barW * Math.min(c.total, c.done + c.running)) / c.total) : fillW
  const y = (BAND_H - TRACK_H) / 2
  const ticks: string[] = []
  if (c.total > 1 && c.total <= 60) {
    for (let i = 1; i < c.total; i++) {
      const x = Math.round((barW * i) / c.total)
      ticks.push(`<rect class="k" x="${barX + x - 0.5}" y="${y}" width="1" height="${TRACK_H}"/>`)
    }
  }
  // In-flight work: a striped, moving layer between the done fill and the head.
  const stripes =
    runW > fillW
      ? `<g clip-path="url(#run)"><g class="flow">${Array.from(
          { length: Math.ceil((runW - fillW) / 6) + 4 },
          (_, i) => `<rect x="${barX + fillW - 12 + i * 6}" y="${y}" width="3" height="${TRACK_H}" fill="${color}" opacity=".35" transform="skewX(-20)"/>`,
        ).join('')}</g></g>`
      : ''
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${BAND_H}" viewBox="0 0 ${W} ${BAND_H}">${SVG_CSS}
<defs><clipPath id="run"><rect x="${barX + fillW}" y="${y}" width="${Math.max(0, runW - fillW)}" height="${TRACK_H}"/></clipPath>
<clipPath id="trk"><rect x="${barX}" y="${y}" width="${barW}" height="${TRACK_H}" rx="${TRACK_H / 2}"/></clipPath></defs>
<circle${c.running ? ' class="live"' : ''} cx="6" cy="${BAND_H / 2}" r="4" fill="${color}"/>
<text class="t" x="18" y="${BAND_H / 2 + 4.5}" font-family="${FONT}" font-size="13" font-weight="600">${xml(title)}</text>
<g clip-path="url(#trk)">
<rect class="k" x="${barX}" y="${y}" width="${barW}" height="${TRACK_H}" opacity=".9"/>
<rect x="${barX}" y="${y}" width="${fillW}" height="${TRACK_H}" fill="${color}"/>
${stripes}${ticks.join('')}
</g>
<text class="t" x="${barX + barW + 10}" y="${BAND_H / 2 + 4.5}" font-family="${FONT}" font-size="12" font-weight="500" font-variant-numeric="tabular-nums">${xml(label)}</text>
<text class="m" x="${W - 2}" y="${BAND_H / 2 + 4.5}" text-anchor="end" font-family="${FONT}" font-size="12" font-variant-numeric="tabular-nums">${percent}</text>
</svg>`
}

const rowBarSvg = (W: number, ratio: number, color: string | null): string =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="6" viewBox="0 0 ${W} 6">${SVG_CSS}
<rect class="k" width="${W}" height="6" rx="3"/>
<rect${color ? '' : ' class="m"'} width="${Math.round(W * Math.min(1, Math.max(0, ratio)))}" height="6" rx="3"${color ? ` fill="${color}"` : ''}/>
</svg>`

// ---------------------------------------------------------------------------
// Pane open/close

async function togglePane($: EngineInterface): Promise<boolean> {
  if ((await $.ui.panes()).some(p => p.id === PANE)) {
    await $.ui.close({ id: PANE })
    return false
  }
  await openPane($)
  return true
}

async function openPane($: EngineInterface): Promise<void> {
  const at = await $.clock.now()
  await update($, now, () => at)
  await $.ui.open({ id: PANE, title: PANE_TITLE })
}

/** Opens the pane unasked, at most once per key (a run, or "any"). */
async function autoOpen($: EngineInterface, key: string): Promise<void> {
  const p = await read($, panel)
  if (p.autoOpenedFor === key) return
  await update($, panel, prev => ({ ...prev, autoOpenedFor: key }))
  void $.ui.open({ id: PANE, title: PANE_TITLE })
}

/** Finishes an automatic run once the main turn is over and nothing in it still runs. */
async function settleAutoRun($: EngineInterface, isMainBusy: boolean): Promise<void> {
  const list = await read($, agents)
  await update($, run, prev =>
    prev && !prev.isReported && !prev.isFinished && !isMainBusy && !runAgents(prev, list).some(a => a.status === 'running')
      ? { ...prev, isFinished: true }
      : prev,
  )
}

// ---------------------------------------------------------------------------

export const register: Register = (on, options) => {
  const autoOpenMode = options.autoOpen === 'any' || options.autoOpen === 'never' ? options.autoOpen : 'plan'
  const isBriefing = options.stepBrief !== 'none'
  // Whether the main loop is mid-turn; an automatic run finishes once the main
  // turn has ended and no agent is still running. Resets on reload, harmlessly.
  let isMainBusy = false

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.tool.register({
      name: 'progress',
      description:
        'Report progress of multi-step work you are delegating to subagents; it draws a progress bar above the prompt and fills the agents panel. ' +
        'Call it after settling on a plan (title, tasks), each time a task is accepted (done), when re-planning (tasks), and once at the end with finished: true. ' +
        'Fields left out keep their previous value; a new title starts a new plan. Optional: without it the bar still counts subagents as they run. ' +
        'Main session only: a call from a subagent is ignored (subagents report with `step`).',
      inputSchema: {
        type: 'object',
        properties: {
          title: { type: 'string', description: 'Short name of the overall task, a few words.' },
          total: { type: 'integer', minimum: 0, description: 'Number of planned tasks; defaults to the length of `tasks`.' },
          done: { type: 'integer', minimum: 0, description: 'Number of tasks finished and accepted.' },
          finished: { type: 'boolean', description: 'True once the whole piece of work is closed.' },
          tasks: {
            type: 'array',
            description:
              'The planned tasks in order, numbered from 1. Give each the same title you will pass as the Agent tool `description`, so the panel can match runs to tasks.',
            items: {
              type: 'object',
              properties: {
                title: { type: 'string', description: 'A few words; reused verbatim as the Agent description.' },
                after: { type: 'array', items: { type: 'integer' }, description: 'Numbers of the tasks this one waits for.' },
              },
              required: ['title'],
            },
          },
        },
      },
    })
    await $.tool.register({
      name: 'step',
      description:
        'For subagents: report progress on your own task to the agents panel. ' +
        'Early on, call it with `total` (your plan in 3-8 steps) and `done: 0`; call it again as each step finishes. Cheap and silent: it only draws a bar.',
      inputSchema: {
        type: 'object',
        properties: {
          done: { type: 'integer', minimum: 0, description: 'Steps finished so far.' },
          total: { type: 'integer', minimum: 1, description: 'Steps planned; may change if the plan changes.' },
          note: { type: 'string', description: 'The step in progress, a few words.' },
        },
        required: ['done'],
      },
      // Listed up front in every agent's tools, not behind ToolSearch.
      isDeferred: false,
    })
    await $.command.register({
      name: 'agent-progress',
      description: 'Show or hide the agents panel (running, finished and planned subagents). "open" opens it without toggling; "clear" forgets finished agents',
    })

    // Ticks running agents' clocks once a second; quiet when nothing runs.
    $.clock.every(1000, () => {
      void (async () => {
        const list = await read($, agents)
        if (!list.some(a => a.status === 'running')) return
        const at = await $.clock.now()
        await update($, now, () => at)
      })()
    })
    return started
  })

  on('command.run', { command: 'agent-progress' }, async ($, e) => {
    const arg = (e.args ?? '').trim().toLowerCase()
    if (arg === 'open') {
      await openPane($)
      return { text: 'Agents panel opened.' }
    }
    if (arg === 'clear') {
      await update($, agents, list => list.filter(a => a.status === 'running'))
      return { text: 'Finished agents cleared.' }
    }
    return { text: (await togglePane($)) ? 'Agents panel opened.' : 'Agents panel closed.' }
  })

  on('turn.start', async ($, e, next) => {
    if (!e.agentId) isMainBusy = true
    return next(e)
  })

  // A finished run's band goes away when the user moves on.
  on('prompt.submit', async ($, e, next) => {
    await update($, run, prev => (prev?.isFinished ? null : prev))
    return next(e)
  })

  on('tool.call', { tool: PROGRESS_TOOL }, async ($, e) => {
    // The plan is the main session's: a subagent could otherwise rename,
    // finish or reset it.
    if (e.agentId) return { result: 'ignored: only the main session reports the plan; use step for your own progress' }
    const input = e as unknown as ProgressInput
    const at = await $.clock.now()
    const prev = await read($, run)
    // A fresh plan counts agents from its own start, but keeps those already
    // running so work launched just before the report is not lost.
    const fresh = isNewReport(prev, input)
    const list = await read($, agents)
    const firstRunning = Math.min(at, ...list.filter(a => a.status === 'running').map(a => a.startedAt))
    const next = await update($, run, p => {
      const merged = mergeReport(p, input, at)
      return fresh ? { ...merged, startedAt: firstRunning } : merged
    })
    if (next && !next.isFinished && Array.isArray(input.tasks) && input.tasks.length && autoOpenMode !== 'never') {
      await autoOpen($, `plan:${next.title}:${next.startedAt}`)
    }
    return { result: next ? `ok: ${labelOf(next, countsOf(next, list))}` : 'ok' }
  })

  // A subagent's own progress: its tool call carries its agentId.
  on('tool.call', { tool: STEP_TOOL }, async ($, e) => {
    const agentId = e.agentId
    if (!agentId) return { result: 'ignored: only subagents report steps' }
    const input = e as unknown as StepInput
    let matched = false
    await update($, agents, list =>
      list.map(a => {
        if (a.agentId !== agentId) return a
        matched = true
        const total = int(input.total, 0, 1000) ?? a.stepTotal ?? 0
        const done = int(input.done, 0, 1000) ?? a.stepDone ?? 0
        const note = clip(str(input.note), MAX_NOTE)
        return { ...a, stepTotal: total, stepDone: total ? Math.min(total, done) : done, stepNote: note || undefined }
      }),
    )
    return { result: matched ? 'ok' : 'ignored: no panel row for this agent' }
  })

  on('agent.spawn', async ($, e, next) => {
    const needsBrief = isBriefing && !e.prompt.includes(STEP_TOOL)
    const started = await next(needsBrief ? { ...e, prompt: e.prompt + STEP_BRIEF } : e)
    if (started.deny !== undefined) return started

    const at = await $.clock.now()
    const agent: AgentRun = {
      id: started.agentId ?? `${e.tool_use_id}:${at}`,
      agentId: started.agentId,
      type: e.subagentType,
      description: clip(e.description || e.subagentType, MAX_TITLE),
      model: started.model,
      status: 'running',
      startedAt: at,
      contextTokens: 0,
      contextMax: windowOf(started.model),
      tokens: 0,
      costUsd: 0,
      requests: 0,
    }
    await update($, agents, list => [...list.filter(a => a.id !== agent.id), agent].slice(-MAX_AGENTS))
    // Nothing tracked, or the last run is over: this agent starts a new one.
    const current = await update($, run, prev => (!prev || prev.isFinished ? newRun(AUTO_TITLE, false, at) : prev))
    await update($, now, () => at)
    if (autoOpenMode === 'any' && current) await autoOpen($, `any:${current.startedAt}`)
    return started
  })

  // Each model request of a subagent: live context, tokens and cost.
  on('turn.step', async function* ($, e, next) {
    const result = yield* next(e)
    const agentId = e.agentId
    const usage = result.usage
    if (!agentId || !usage) return result
    const model = usage.model || e.model
    await update($, agents, list =>
      list.map((a): AgentRun =>
        a.agentId !== agentId
          ? a
          : {
              ...a,
              model,
              effort: typeof e.effort === 'string' ? e.effort : a.effort,
              status: 'running',
              endedAt: undefined,
              contextTokens: allTokens(usage),
              contextMax: windowOf(model),
              tokens: a.tokens + allTokens(usage),
              costUsd: a.costUsd + costOf(model, usage, true),
              requests: a.requests + 1,
            },
      ),
    )
    return result
  })

  on('turn.complete', async ($, e, next) => {
    const agentId = e.agentId
    if (!agentId) {
      isMainBusy = false
      await settleAutoRun($, isMainBusy)
      return next(e)
    }
    const at = await $.clock.now()
    await update($, agents, list =>
      list.map((a): AgentRun => {
        if (a.agentId !== agentId) return a
        // A run whose requests went unseen still gets the turn's own sum.
        const fallback = a.requests === 0 && e.usage
        return {
          ...a,
          status: e.reason === 'answer' ? 'done' : 'failed',
          endedAt: at,
          ...(fallback && e.usage
            ? {
                model: e.usage.model || a.model,
                tokens: allTokens(e.usage),
                costUsd: costOf(e.usage.model || a.model, e.usage, false),
              }
            : {}),
        }
      }),
    )
    await update($, now, () => at)
    await settleAutoRun($, isMainBusy)
    return next(e)
  })

  // -------------------------------------------------------------------------
  // The band above the prompt

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const r = await read($, run)
    if (r === null || e.props.hasSurvey) return next(e)
    // Draw with other mods' bands beneath; Claude Code's own placeholder
    // ({ type: 'engine' }) is never nested, as the desktop drops a band that nests it.
    const drawn = await Promise.resolve(next(e)).catch(() => null)
    const below = drawn && typeof drawn === 'object' && (drawn as { type?: string }).type !== 'engine' ? drawn : null

    const ui = $.ui.resolve(e)
    const { Box, Text, Button } = ui
    const list = await read($, agents)
    const c = countsOf(r, list)
    const crew = runAgents(r, list).length + plannedOf(r, list).length
    const ratio = ratioOf(r, c)
    const label = labelOf(r, c)
    const color = r.isFinished ? (c.failed ? FAILED : DONE) : ACCENT
    const crewButton = <Button key="agent-progress-open" label={`Agents ×${crew}`} plain onPress={() => void togglePane($)} />
    const dismiss = <Button key="agent-progress-dismiss" label="✕" plain role="dismiss" onPress={() => update($, run, () => null)} />

    // The terminal's element table carries an `Svg` that draws nothing: test the surface too.
    if (e.surface !== 'terminal' && 'Svg' in ui) {
      const { Svg } = ui
      const width = Math.max(200, Math.min(1600, (e.props.bodyColumns || 100) * 8 - 130))
      return (
        <Box flexDirection="column">
          <Box flexDirection="row" alignItems="center" gap={1}>
            <Svg source={bandSvg(r, c, width)} alt={`${r.title}: ${label}, ${Math.round(ratio * 100)}%`} width={width} height={BAND_H} />
            {crewButton}
            {dismiss}
          </Box>
          {below}
        </Box>
      )
    }

    const cols = e.props.bodyColumns || 80
    const titleW = Math.max(8, Math.min(28, r.title.length + 2, Math.floor(cols / 4)))
    const barW = Math.max(6, Math.min(36, cols - titleW - label.length - 26))
    return (
      <Box flexDirection="column">
        <Box flexDirection="row" gap={1}>
          <Box width={titleW} flexShrink={0}>
            <Text color={color}>● </Text>
            <Text bold wrap="truncate-end">
              {r.title}
            </Text>
          </Box>
          <Text color={color}>{textBar(ratio, barW)}</Text>
          <Text>{label}</Text>
          <Text dimColor>{Math.round(ratio * 100)}%</Text>
          {crewButton}
          {dismiss}
        </Box>
        {below}
      </Box>
    )
  })

  // -------------------------------------------------------------------------
  // The agents pane

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const ui = $.ui.resolve(e)
    const { Box, Text, Button } = ui
    const hasSvg = e.surface !== 'terminal' && 'Svg' in ui
    const list = await read($, agents)
    const r = await read($, run)
    const p: Panel = await read($, panel)
    const at = Math.max(await read($, now), ...list.map(a => a.startedAt), 0)

    const running = list.filter(a => a.status === 'running').reverse()
    const finished = list.filter(a => a.status !== 'running').reverse()
    const planned = plannedOf(r, list)
    const t = totals(list, at)
    const cols = Math.max(24, e.props.bodyColumns || 40)
    const barCols = Math.max(6, Math.min(24, cols - 30))
    const svgW = Math.max(120, Math.min(900, cols * 8 - 16))

    const bar = (ratio: number, color: string | null) =>
      hasSvg && 'Svg' in ui ? (
        <ui.Svg source={rowBarSvg(svgW, ratio, color)} alt={`${Math.round(ratio * 100)}%`} width={svgW} height={6} />
      ) : color ? (
        <Text color={color}>{textBar(ratio, barCols)}</Text>
      ) : (
        <Text dimColor>{textBar(ratio, barCols)}</Text>
      )

    const agentRow = (a: AgentRun) => {
      const steps = stepRatio(a)
      const color = statusColor(a)
      const model = a.effort ? `${modelName(a.model)} · ${a.effort}` : modelName(a.model)
      const stepText = a.stepTotal ? `${a.stepDone ?? 0}/${a.stepTotal}${a.stepNote ? ' · ' + a.stepNote : ''}` : ''
      const stats = `ctx ${ctxPct(a)}% · ${fmtTokens(a.tokens)} tok · ≈${fmtCost(a.costUsd)} · ${fmtTime(elapsed(a, at))}`
      return (
        <Box key={a.id} flexDirection="column" marginBottom={1}>
          <Box flexDirection="row" gap={1}>
            <Text color={color}>{GLYPH[a.status]}</Text>
            <Text bold wrap="truncate-end">
              {a.description}
            </Text>
          </Box>
          <Text dimColor wrap="truncate-end">
            {'  '}
            {a.type} · {model}
            {a.status === 'failed' ? ' · failed' : ''}
          </Text>
          {stepText ? (
            <Text wrap="truncate-end">
              {'  '}
              {stepText}
            </Text>
          ) : null}
          {/* Without reported steps the bar shows context fill, in grey. */}
          {bar(steps ?? ctxPct(a) / 100, steps === null ? null : color)}
          <Text dimColor wrap="truncate-end">
            {'  '}
            {stats}
          </Text>
        </Box>
      )
    }

    const plannedRow = (pl: Planned) => (
      <Box key={`plan-${pl.n}`} flexDirection="column">
        <Text dimColor wrap="truncate-end">
          {GLYPH.planned} {pl.n}. {pl.title}
          {pl.after.length ? `  (after ${pl.after.join(', ')})` : ''}
        </Text>
      </Box>
    )

    const header = (
      <Box flexDirection="column" marginBottom={1}>
        {r && r.isReported && !r.isFinished ? (
          <Text bold wrap="truncate-end">
            {r.title}: {labelOf(r, countsOf(r, list))}
          </Text>
        ) : null}
        <Text dimColor>
          ≈{fmtCost(t.cost)} · {fmtTokens(t.tokens)} tokens · {fmtTime(t.time)}
        </Text>
        <Box flexDirection="row" gap={2}>
          <Button
            key="compact"
            label={p.isCompact ? 'Expand' : 'Compact'}
            plain
            onPress={() => update($, panel, prev => ({ ...prev, isCompact: !prev.isCompact }))}
          />
          {finished.length > 0 ? (
            <Button key="clear" label="Clear finished" plain onPress={() => update($, agents, l => l.filter(a => a.status === 'running'))} />
          ) : null}
        </Box>
      </Box>
    )

    if (list.length === 0 && planned.length === 0) {
      return (
        <Box flexDirection="column">
          {header}
          <Text dimColor>No subagents yet.</Text>
        </Box>
      )
    }

    if (p.isCompact) {
      return (
        <Box flexDirection="column">
          {header}
          {[...running, ...finished].map(a => (
            <Text key={a.id} wrap="truncate-end">
              <Text color={statusColor(a)}>{GLYPH[a.status]}</Text> {a.description}
              <Text dimColor> {a.stepTotal ? `${a.stepDone ?? 0}/${a.stepTotal}` : fmtTime(elapsed(a, at))}</Text>
            </Text>
          ))}
          {planned.map(plannedRow)}
        </Box>
      )
    }

    return (
      <Box flexDirection="column">
        {header}
        {running.length > 0 ? <Text dimColor>Running · {running.length}</Text> : null}
        {running.map(agentRow)}
        {finished.length > 0 ? (
          <Button
            key="done"
            label={`${p.isDoneCollapsed ? '▸' : '▾'} Finished · ${finished.length}`}
            plain
            onPress={() => update($, panel, prev => ({ ...prev, isDoneCollapsed: !prev.isDoneCollapsed }))}
          />
        ) : null}
        {!p.isDoneCollapsed ? finished.map(agentRow) : null}
        {planned.length > 0 ? <Text dimColor>Planned · {planned.length}</Text> : null}
        {planned.map(plannedRow)}
      </Box>
    )
  })
}
