# Agent Skills

An optional overlay of [Agent Skills](https://agentskills.io/) on top of [Matt Pocock's skills](https://github.com/mattpocock/skills). It adds a few skills that Matt's set doesn't have. The repo also hosts one optional Claude Code plugin, listed under [Plugins](#plugins), which the skills don't need.

> **Requires Matt Pocock's skills.** This overlay is not a standalone collection. It assumes Matt's skills are installed in the same project and that his `setup-matt-pocock-skills` has written the project's config (the `## Agent skills` block and `docs/agents/`). Matt's skills do most of the work; huge thanks to Matt for the foundation.

## Skills

**Invoked by:** *You* means the skill only runs when you type it (e.g. `/to-idea`); *You or model* means the model can also reach for it automatically from its description.

### Engineering

| Skill | Invoked by | Description |
| --- | --- | --- |
| [code-quality](skills/engineering/code-quality/SKILL.md) | You or model | General implementation-quality review bar (readability, public-API discipline, type coverage); `embedded-python` covers constrained hardware. |
| [comments-backpressure](skills/engineering/comments-backpressure/SKILL.md) | You or model | Push back on comments: sort each into remove, design change, test, ADR or keep, and try those before writing one. Language formatting in reference files. |
| [embedded-python](skills/engineering/embedded-python/SKILL.md) | You or model | Embedded Python rules for CircuitPython, MicroPython and other constrained hardware: no allocation on hot paths, mutate in place, plain loops, runtime-safe typing. |
| [test-quality](skills/engineering/test-quality/SKILL.md) | You or model | Review and audit tests against a quality bar: test naming, one behavior per test, coverage planning, per-language mocking guides. Pairs with Matt's `tdd`, which owns the loop. |
| [to-idea](skills/engineering/to-idea/SKILL.md) | You | Capture a discovery or new idea as a lightweight `idea`-labeled issue to revisit later: a stub, not a spec. |

### Misc

| Skill | Invoked by | Description |
| --- | --- | --- |
| [air-quality-data](skills/misc/air-quality-data/SKILL.md) | You or model | Fetch and compare air quality data (AQI, PM2.5/PM10) via EPA AirNow, PurpleAir, IQAir, and OpenAQ. |

## What this overlay adds

Each skill here fills a gap in Matt's skills. None of them shares a name with one of his.

- **`code-quality`:** a language-neutral review bar for production code (readability, right-sized optimization, public-API discipline, type coverage). It judges against the project's `GLOSSARY.md`, ADRs and standards files, and hands embedded targets to `embedded-python`.
- **`comments-backpressure`:** pushes back on comments so the code itself carries intent. It sorts each comment into remove, design change, test, ADR or keep, and keeps only a non-obvious why.
- **`embedded-python`:** Python rules for CircuitPython, MicroPython and other constrained hardware, where allocations and GC pauses matter: no allocation on hot paths, mutate in place, plain loops, runtime-safe typing. The model reaches it while writing the code, not only at review.
- **`test-quality`:** a quality bar for the tests themselves (naming, one behavior per test, coverage traced to guarantees) plus per-language mocking guides, run as its own review pass. Matt's `tdd` owns the red-green loop.
- **`to-idea`:** captures a discovery as a lightweight `idea`-labeled issue, a stub to revisit rather than a spec. It reads the label from the project's triage-labels doc.
- **`air-quality-data`:** fetches live AQI and pollutant readings from EPA AirNow, PurpleAir, IQAir and OpenAQ through bundled scripts.

## Installation

Install into the project, with the [`skills`](https://github.com/vercel-labs/skills) CLI's default agents. Run Matt's skills first and the overlay second:

```bash
npx skills add mattpocock/skills
npx skills add aaronsilinskas/ai-skills
```

Take every skill when the installer asks (or pass `-y`), and then run `/setup-matt-pocock-skills` once to write the project's config.

- **Resync** with the same two commands, in the same order. `npx skills update` is also safe, because each skill updates from the source it was installed from.
- **Stay project-scoped.** A personal install (`-g`, or a skill in `~/.claude/skills`) overrides the same-named project skill in every project on the machine.
- **Picking skills is untested.** Installing only some overlay skills with `-s` has not been tested. Install the whole overlay unless you accept that risk.

### Alternative: Matt's Claude Code plugin

On Claude Code you can take Matt's skills from his plugin instead, and add the overlay with npx:

```bash
claude plugin install mattpocock-skills@claude-plugins-official
npx skills add aaronsilinskas/ai-skills
```

This route has two caveats:

- Only Claude Code gets Matt's skills. The other agents npx installs the overlay for will have the overlay without the skills it depends on.
- Matt's copies stay listed as `mattpocock-skills:<name>`, beside any same-named skill installed by npx.

## Plugins

Claude Code plugins live under `plugins/`, listed in the marketplace file `.claude-plugin/marketplace.json`. They are separate from the skills: `npx skills` does not install them, and they need nothing from Matt's skills.

| Plugin | Description |
| --- | --- |
| [agent-progress](plugins/agent-progress/README.md) | Progress bar above the prompt and a live agents panel (`/agent-progress`) for any subagents: steps, model, context, estimated cost and time. |
| [session-board](plugins/session-board/README.md) | Every Claude Code session at a glance from any of them: which are working, need you or finished. A band above the prompt, a `/sessions` pane, notifications, `/sessions go` to switch to a session's Terminal tab, and `/sessions clean` to remove ended sessions' files. |

Install one at the prompt of a Claude Code terminal session, answering `y` to add the marketplace and then picking a scope:

```
/plugin install agent-progress --marketplace aaronsilinskas/ai-skills
```

From a shell, the same is `claude plugin install agent-progress --marketplace aaronsilinskas/ai-skills`. In the desktop app, click + next to the prompt box, then Plugins, Add marketplace with `aaronsilinskas/ai-skills`, then Add plugin.

## kaizen

[kaizen](kaizen/README.md) is a command-line tool, published to PyPI as `kaizen-kit`, that runs the deterministic parts of agent workflows for every project a home repo registers: tickets, specs, the leak check and issue links. It is usually changed through the retro process. It lives in `kaizen/` as its own Python package. It adds no skill to the `npx skills` install and changes nothing about it: the skills and the CLI are separate products. Its glossary, decisions and domain map start from [`GLOSSARY-MAP.md`](GLOSSARY-MAP.md).

## Conventions

Skills follow [Matt's authoring conventions](https://github.com/mattpocock/skills/blob/main/CLAUDE.md) and the [agentskills.io specification](https://agentskills.io/specification) and [best practices](https://agentskills.io/skill-creation/best-practices):

- No em-dashes. Rewrite each sentence by hand rather than substituting a character.
- An operative cross-skill call says `Call the Skill tool with "x"` (or `Call the Skill tool twice, for "x" and "y"`).
- A user-invoked skill may call model-invoked skills, never another user-invoked one. In that case it tells the user to run `/x`.
- Quote any `description:` that contains `: `.
- A skill's directory takes its frontmatter `name:`.
- Every skill ships `agents/openai.yaml` in Matt's shape. User-invoked skills set `policy.allow_implicit_invocation: false`.
- Spell it "sub-agent".

**One exception:** skill frontmatter keeps `argument-hint` wherever a skill has one, so the slash-command prompt still hints at what to pass. Matt drops it.

Use Matt's `writing-for-agents` skill (installed under `.claude/skills/`) when creating or updating any skill here.

## Consistency check

Before a PR, and after adding, removing, or editing a skill, run the check command:

```bash
bash scripts/check.sh
```

It runs every check even after a failure, prints a PASS, FAIL or SKIP line for each, and exits non-zero if anything failed. It works from any directory.

1. **Conventions:** no em-dash in any git-tracked file outside `.claude/skills/` (Matt's copies, which this repo doesn't own); every `description:` parses as YAML; every skill has an `agents/openai.yaml` whose `allow_implicit_invocation` matches its `disable-model-invocation`; no user-invoked skill calls another user-invoked skill through the Skill tool (Matt's skills installed under `.claude/skills/` count too); and every skill's `name:` is its directory's name.
2. **Wiring parity:** every `skills/<bucket>/<skill>` directory appears exactly once in a README bucket table; every `plugins/<plugin>` has one entry in `.claude-plugin/marketplace.json`, at its `plugin.json` version, and one row in the README's plugin table; `skills-lock.json` names exactly the skills in `.claude/skills/`. None of them lists anything that isn't on disk.
3. **Links:** every relative link in a git-tracked Markdown file names a tracked file or directory. Matt's copies and kaizen's templates, whose links resolve where they are rendered, are skipped.
4. **Plugins:** `claude plugin validate .` passes, and `claude plugin test` passes for each plugin. Without the `claude` CLI on the PATH, it reports SKIP; CI installs it.
5. **kaizen:** `kaizen/scripts/check.sh` passes: the kaizen package's own check, whose script lists its steps.

CI (`.github/workflows/check.yml`) runs the same command on every pull request and on pushes to `main`.

## Upstream

[`UPSTREAM.md`](UPSTREAM.md) records the `mattpocock/skills` commit this overlay was last tested against, and how to sync to a newer one.
