# agent-progress

A Claude Code mod that shows what your subagents are doing. It needs no workflow skill: it tracks any subagent the session launches (`general-purpose`, `Explore`, plugin agents, forks).

- **Progress bar above the prompt.** It appears when a subagent starts and shows how many have finished, how many are running, and how many failed. The `Agents ×N` button opens the panel and `✕` hides the bar. Once the work is done the bar turns green and goes away with your next prompt.
- **Agents panel** (`/agent-progress` toggles it, `/agent-progress open` opens it without toggling, `/agent-progress clear` forgets finished agents): running, finished and planned subagents, each with its type, model and effort, its own step progress, context fill, tokens, estimated cost and elapsed time. A Compact button shrinks it to one line per agent.

## Tools it adds

- `mcp__agent-progress__step`: a subagent reports its own steps (`done`, `total`, `note`). By default every subagent's prompt gets one extra line at the end asking it to do this. A subagent that never reports shows its context fill as a grey bar instead.
- `mcp__agent-progress__progress` (optional): the main session reports a plan (`title`, `tasks`, `done`, `finished`). The bar then counts accepted tasks out of the planned ones rather than agents, and the panel lists tasks that haven't started yet. A task is matched to its subagent when the task title equals the Agent tool's `description`. Only the main session can call it; a call from a subagent is ignored.

You don't need any particular prompt for this. Asking Claude to "report progress with the progress tool" when you hand it a big delegated job is enough to get the plan view.

Cost is a rough estimate from token counts and a built-in price table (`PRICES` in `hooks/register.tsx`, list prices as of 2026-11), not a bill. Cache writes are priced at the 1-hour rate.

## Settings

Set these in `/config`, or under `pluginConfigs` in `~/.claude/settings.json`:

```json
{ "pluginConfigs": { "agent-progress": { "options": { "autoOpen": "any", "stepBrief": "all" } } } }
```

- `autoOpen`: `plan` (the default) opens the panel by itself when the main session reports a plan. `any` also opens it when any subagent starts. `session` opens it once when each session starts, and not again after you close it. `never` opens it only when you ask. The panel opens itself at most once per run.
- `stepBrief`: `all` (the default) appends the step-reporting line to every subagent's prompt. `none` leaves prompts alone.

Inspired by [savvy-progress](https://github.com/JohnnyVizz/claude-kit/tree/main/plugins/savvy-progress) (MIT), without the savvy-flow coupling.
