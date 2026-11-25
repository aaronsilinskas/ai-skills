# Agent Skills

[Matt Pocock's skills](https://github.com/mattpocock/skills) give a coding agent a solid engineering loop: specs, tickets, TDD, review. They leave some gaps. Nothing in them holds production code or tests to a written quality bar, pushes back on comments that restate the code, knows that a CircuitPython frame loop can't allocate, or parks a half-formed idea somewhere you'll find it again.

This repo is an overlay of [Agent Skills](https://agentskills.io/) that fills those gaps. It sits on top of Matt's skills and depends on them: install his first. Huge thanks to Matt for the foundation.

The repo also hosts two Claude Code plugins and kaizen, a workflow CLI. None of them needs the skills.

## Quick start

From your project's root, install Matt's skills, then the overlay, taking every skill when asked:

```bash
npx skills add mattpocock/skills
npx skills add aaronsilinskas/ai-skills
```

Then, in your agent, run `/setup-matt-pocock-skills` once. It writes the project config the skills read (an `## Agent skills` block and `docs/agents/`).

To try it, ask the agent to review a file you just changed against `code-quality`, and it reports findings against your project's own glossary, ADRs and standards files. Or type `/to-idea` followed by a sentence about something you noticed. It files that as an `idea`-labeled issue in your tracker.

## Skills

*Invoked by:* "You" means the skill runs only when you type it (`/to-idea`). "You or model" means the agent can also pick it up on its own from its description. None of these shares a name with one of Matt's skills.

### Engineering

| Skill | Invoked by | What it does |
| --- | --- | --- |
| [code-quality](skills/engineering/code-quality/SKILL.md) | You or model | A language-neutral review bar for production code: readability, right-sized optimization, public-API discipline, type coverage. It judges against the project's `GLOSSARY.md`, ADRs and standards files, and hands embedded targets to `embedded-python`. |
| [comments-backpressure](skills/engineering/comments-backpressure/SKILL.md) | You or model | Makes the code carry its own intent. Each comment is sorted into remove, design change, test, ADR or keep, and only a non-obvious why survives. |
| [embedded-python](skills/engineering/embedded-python/SKILL.md) | You or model | Rules for CircuitPython, MicroPython and other constrained hardware, where allocations and GC pauses matter: no allocation on hot paths, mutate in place, plain loops, runtime-safe typing. The agent applies them while writing the code, not only at review. |
| [test-quality](skills/engineering/test-quality/SKILL.md) | You or model | A quality bar for the tests themselves (naming, one behavior per test, coverage traced to guarantees) plus per-language mocking guides. Matt's `tdd` owns the red-green loop; this is the review pass. |
| [to-idea](skills/engineering/to-idea/SKILL.md) | You | Captures a discovery as a lightweight `idea`-labeled issue: a stub to come back to, not a spec. It reads the label from the project's triage-labels doc. |

### Misc

| Skill | Invoked by | What it does |
| --- | --- | --- |
| [air-quality-data](skills/misc/air-quality-data/SKILL.md) | You or model | Fetches and compares live AQI and pollutant readings (PM2.5, PM10) from EPA AirNow, PurpleAir, IQAir and OpenAQ through bundled scripts. |

## Install options

- **Keep it current** by running the same two `npx skills add` commands again, in the same order. `npx skills update` also works, because each skill updates from the source it came from.
- **Install per project.** A personal install (`-g`, or a skill in `~/.claude/skills`) overrides the same-named project skill in every project on the machine.
- **Take the whole overlay.** Installing only some of its skills with `-s` hasn't been tested.

On Claude Code you can take Matt's skills from his plugin instead, and add the overlay with npx:

```bash
claude plugin install mattpocock-skills@claude-plugins-official
npx skills add aaronsilinskas/ai-skills
```

Two catches. Only Claude Code gets Matt's skills this way, so any other agent npx installs the overlay for has it without the skills it depends on. And Matt's copies show up as `mattpocock-skills:<name>`, beside any same-named skill npx installed.

## Plugins

Two Claude Code plugins, listed in `.claude-plugin/marketplace.json`. `npx skills` doesn't install them, and they need nothing from Matt's skills.

| Plugin | What it does |
| --- | --- |
| [agent-progress](plugins/agent-progress/README.md) | Shows what your subagents are doing: a progress bar above the prompt and a live agents panel (`/agent-progress`) with each one's steps, model, context, estimated cost and time. |
| [session-board](plugins/session-board/README.md) | Shows every Claude Code session on the machine from any of them: which are working, which need you, which finished. A band above the prompt, a `/sessions` pane, notifications, and `/sessions go` to jump to a session's Terminal tab. |

Install one from the prompt of a Claude Code terminal session. Answer `y` to add the marketplace, then pick a scope:

```
/plugin install agent-progress --marketplace aaronsilinskas/ai-skills
```

From a shell it's `claude plugin install agent-progress --marketplace aaronsilinskas/ai-skills`. In the desktop app, click + next to the prompt box, then Plugins, Add marketplace with `aaronsilinskas/ai-skills`, then Add plugin.

## kaizen

Agents running the same workflow across several repos tend to do the mechanical parts slightly differently each time. [kaizen](kaizen/README.md) is a command-line tool that does those parts the same way every time: starting a ticket worktree, shipping a PR through a leak check, keeping each home's shared agent docs in step with kaizen's templates. Install it with `uv tool install kaizen-kit`. It's a separate product from the skills, and `npx skills` doesn't install it.

## Contributing

To change a skill, a plugin or kaizen, read [CONTRIBUTING.md](CONTRIBUTING.md).
