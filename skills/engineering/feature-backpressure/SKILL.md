---
name: feature-backpressure
description: "Push back on features: weigh the cost of each command, flag, option or config key against evidence of its use, and propose the smallest version that serves that use. Use when about to add a feature, flag, option or config key, or when a spec or request proposes one."
argument-hint: "feature proposal to weigh"
---

# Feature Backpressure

A **feature** is anything a user or caller can use or configure: a command, a flag, a config key, a behaviour, an application feature. An agent writes one cheaply, and the project pays for it on every later change: code to keep working, tests, docs, help text, one more thing for a user to learn. Feature creep is that cost piling up, one small addition at a time. Backpressure weighs each feature before it lands, so the project grows by the features its users reach for.

Three inputs settle a feature, and each has one owner:

- **Cost**, measured by you: what each part adds. Name it concretely, in your own judgement: code and tests, docs and help text, new config surface, new failure modes, interactions with other features, upkeep on every later change.
- **Use**, measured by you, from evidence (below). "Might be useful" is a guess, and a guess counts as unknown use.
- **Value** to the people using it, rated by the user: **high**, **low** or **unsure**. Ask only for a feature that cost and use leave undecided (its use is unknown, or real use meets a real cost and neither clearly wins), and record the answer in the ledger. You never rate value yourself.

## Evidence of Use

Name the source for every use claim:

- **The user's knowledge**: asked once per undecided feature, then read from the ledger.
- **The issue tracker**: requests and reports that name the feature or the need behind it.
- **Agent transcripts**, for a tool agents run: the calls of a command or flag.
- **Reachability**: whether a user can get to the feature at all (a menu, a route, a documented command).
- **Telemetry**, where the project has it.

When none of them settles the use, the use is unknown: say so, and name the evidence that would settle it.

## Proposal Mode

Run it before building a feature: one a spec proposes, one a request asks for, or an extra you are about to add on your own.

1. Read the ledger. A feature, or a near match, with a **decline** or **deferred** row stays at that verdict unless the row's revisit condition has come up: cite the row and stop.
2. Split the proposal into its parts (each command, flag, option, mode, config key, output format) and name each part's cost.
3. Give each part's evidence of use, with its source.
4. Find the smallest version that serves the evidenced use.
5. Ask the user to rate value on the parts that cost and use leave undecided.
6. End on exactly one verdict:
   - **build**: the evidenced use covers the whole proposal.
   - **build smaller**: build the smallest version, and list each deferred extra with what would bring it back, for the user to add back.
   - **measure first**: the use is unknown; name the evidence that would settle it and how to gather it.
   - **decline**: the cost outweighs the evidenced use and the user's value rating.
7. Write the ledger rows the verdict makes (see **Feature Ledger**).

Report it as a **Cost and use** section:

```markdown
## Cost and use

| Part | Cost | Use (source) |
| --- | --- | --- |
| `export` command, JSON output | one command, one test file, a README section | 4 issues ask to move data out (#12, #31, #40, #52) |
| `--format csv` | a second writer and its tests | none: every request names JSON |

Smallest version: `export` with JSON output only.
Verdict: **build smaller**. Deferred: `--format csv`, revisit when an issue asks for CSV.
```

A feature you add while implementing something else, one the issue didn't ask for, you may build: name it in your handback with its cost and use, so the user can weigh it there.

## Feature Ledger

Each project keeps its decisions in `docs/feature-backpressure.md`, one Markdown table at that fixed path, so the user answers each unknown once. Create it with its first row:

```markdown
# Feature backpressure ledger

| Feature | Verdict | Value | Reason | Date | Revisit when |
| --- | --- | --- | --- | --- | --- |
| `export --format csv` | deferred | unsure | every request names JSON | 2026-11-26 | an issue asks for CSV |
| `sync --watch` | decline | low | one request, and cron covers it | 2026-11-26 | a second user asks |
| usage counter on `report` | measure | - | no evidence of use yet | 2026-11-26 | 30 days of the counter |
| `plugin` config key | build | - | groundwork for plugins | 2026-11-26 | the plugins spec starts |
```

One row per decided feature. **Value** holds the user's rating, or `-` when they weren't asked. The rows it holds:

- **decline** verdicts, and the **deferred** extras of a build-smaller verdict, with why, so they aren't proposed again until their revisit condition comes up.
- **measure** rows (a **measure first** verdict), whose revisit condition names the signal they wait for.
- **groundwork** features, kept for work not yet started: "groundwork for X", revisit when X starts.
- any other verdict the user gave a value rating, so they aren't asked again.

A plain **build** with no value rating needs no row, and a **build smaller** needs rows only for its deferred extras.

The ledger stays current by these rules:

- The change that acts on a verdict (a cut, a shrink, a merge, a deferred extra built) updates its row in the same commit.
- Proposal mode rewrites a deferred row as **build** when it adds that extra back.
- Only a hard-to-reverse decision with a real trade-off also gets an ADR: call the Skill tool with "domain-modeling" to write it, and point the row's reason at it.

## Checklist

- [ ] The ledger was read first, and no declined or deferred item came back without its revisit condition
- [ ] Every part of the proposal has its cost and its use, with the use's source
- [ ] Value came from the user, asked only where cost and use left a part undecided
- [ ] The report ends on exactly one verdict, with deferred extras or the settling evidence named
- [ ] The ledger holds a row for every verdict that needs one
