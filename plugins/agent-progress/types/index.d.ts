export type PlannedTask = {
  title: string
  /** 1-based numbers of the tasks this one waits for. */
  after: number[]
}

/**
 * One stretch of subagent work the band tracks. Either reported by the main
 * session through the `progress` tool, or started automatically when a
 * subagent spawns and nothing is being tracked.
 */
export type Run = {
  title: string
  /** True when the main session reported it; false for an automatic run. */
  isReported: boolean
  /** Reported runs only: planned and accepted task counts. */
  total: number
  done: number
  tasks: PlannedTask[]
  isFinished: boolean
  startedAt: number
}

export type AgentStatus = 'running' | 'done' | 'failed'

export type AgentRun = {
  id: string
  agentId?: string
  type: string
  description: string
  model: string
  effort?: string
  status: AgentStatus
  startedAt: number
  endedAt?: number
  /** Last request's prompt + output tokens: how full the context is. */
  contextTokens: number
  contextMax: number
  /** All tokens billed across the agent's requests. */
  tokens: number
  costUsd: number
  requests: number
  /** Self-reported through the `step` tool. */
  stepDone?: number
  stepTotal?: number
  stepNote?: string
}

export type Panel = {
  isCompact: boolean
  isDoneCollapsed: boolean
  autoOpenedFor: string
}

declare module 'claude-code' {
  interface PluginState {
    'agent-progress': {
      run: Shaped<Run | null>
      agents: Shaped<AgentRun[]>
      panel: Shaped<Panel>
      now: number
    }
  }
}
