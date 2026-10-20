# Agent Skills

An optional overlay of [Agent Skills](https://agentskills.io/) on top of [Matt Pocock's skills](https://github.com/mattpocock/skills). It adds a few skills that Matt's set doesn't have, and nothing else.

> **Requires Matt Pocock's skills.** This overlay is not a standalone collection. It assumes Matt's skills are installed in the same project and that his `setup-matt-pocock-skills` has written the project's config (the `## Agent skills` block and `docs/agents/`). Matt's skills do most of the work; huge thanks to Matt for the foundation.

## Skills

**Invoked by:** *You* means the skill only runs when you type it (e.g. `/to-idea`); *You or model* means the model can also reach for it automatically from its description.

### Engineering

| Skill | Invoked by | Description |
| --- | --- | --- |
| [checkout](skills/engineering/checkout/SKILL.md) | You | Check out a branch in the project directory to validate/iterate on it, clearing a blocking worktree and rescuing local changes first. |
| [code-quality](skills/engineering/code-quality/SKILL.md) | You or model | General implementation-quality review bar (readability, public-API discipline, type coverage); platform specifics in reference files. |
| [comments](skills/engineering/comments/SKILL.md) | You or model | Decide whether code needs a comment/docstring at all, and write the ones that survive; language formatting in reference files. |
| [test-quality](skills/engineering/test-quality/SKILL.md) | You or model | Review and audit tests against a quality bar: test naming, one behavior per test, coverage planning, per-language mocking guides. Pairs with Matt's `tdd`, which owns the loop. |
| [to-idea](skills/engineering/to-idea/SKILL.md) | You | Capture a discovery or new idea as a lightweight `idea`-labeled issue to revisit later: a stub, not a spec. |

### Misc

| Skill | Invoked by | Description |
| --- | --- | --- |
| [air-quality-data](skills/misc/air-quality-data/SKILL.md) | You or model | Fetch and compare air quality data (AQI, PM2.5/PM10) via EPA AirNow, PurpleAir, IQAir, and OpenAQ. Installs as `as-air-quality-data`. |

## What this overlay adds

Each skill here fills a gap in Matt's skills. None of them shares a name with one of his.

- **`code-quality`:** a language-neutral review bar for production code (readability, right-sized optimization, public-API discipline, type coverage). It judges against the project's `GLOSSARY.md`, ADRs and standards files, with platform rules in reference files.
- **`comments`:** decides whether a symbol needs a comment or docstring at all, then writes the ones that earn their place.
- **`test-quality`:** a quality bar for the tests themselves (naming, one behavior per test, coverage traced to guarantees) plus per-language mocking guides, run as its own review pass. Matt's `tdd` owns the red-green loop.
- **`to-idea`:** captures a discovery as a lightweight `idea`-labeled issue, a stub to revisit rather than a spec. It reads the label from the project's triage-labels doc.
- **`checkout`:** checks out a branch in the project directory so you can validate and iterate on it, clearing a worktree that holds it and rescuing local changes first.
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

## Conventions

Skills follow [Matt's authoring conventions](https://github.com/mattpocock/skills/blob/main/CLAUDE.md) and the [agentskills.io specification](https://agentskills.io/specification) and [best practices](https://agentskills.io/skill-creation/best-practices):

- No em-dashes. Rewrite each sentence by hand rather than substituting a character.
- An operative cross-skill call says `Call the Skill tool with "x"` (or `Call the Skill tool twice, for "x" and "y"`).
- A user-invoked skill may call model-invoked skills, never another user-invoked one. In that case it tells the user to run `/x`.
- Quote any `description:` that contains `: `.
- Every skill ships `agents/openai.yaml` in Matt's shape. User-invoked skills set `policy.allow_implicit_invocation: false`.
- Spell it "sub-agent".

**One exception:** skill frontmatter keeps `argument-hint` wherever a skill has one, so the slash-command prompt still hints at what to pass. Matt drops it.

Use the Anthropic [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) skill when creating or updating any skill here.

## Consistency check

After adding, removing, or editing a skill, run the consistency guard:

```bash
bash scripts/check.sh
```

It runs every check even after a failure, prints a PASS, FAIL or SKIP line for each, and exits non-zero if anything failed. It works from any directory.

1. **Conventions:** no em-dash in any git-tracked file; every `description:` parses as YAML; every skill has an `agents/openai.yaml` whose `allow_implicit_invocation` matches its `disable-model-invocation`; and no user-invoked skill calls another user-invoked skill through the Skill tool (Matt's skills installed under `.claude/skills/` count too).
2. **Wiring parity:** every `skills/<bucket>/<skill>` directory appears exactly once in a README bucket table, and the README lists no skill that isn't on disk.
3. **Script lint:** `skills/engineering/wizard/template.sh` passes `bash -n` (and `shellcheck`, when installed). With no `wizard` skill in this repo, it reports SKIP.

## Upstream

[`UPSTREAM.md`](UPSTREAM.md) records the `mattpocock/skills` commit this overlay was last tested against, and how to sync to a newer one.
