---
name: feature-backpressure
description: "Push back on features: weigh each one's cost against evidence of its use, propose the smallest version that serves it, and audit existing ones into cut, merge, shrink, measure or keep. Use when about to add a feature, flag, option or config key, when a spec or request proposes one, or when asked to audit a project's features."
argument-hint: "feature proposal to weigh, or a project, module or path to audit"
---

# Feature Backpressure

A **feature** is anything a user or caller can use or configure: a command, a flag, a config key, a behaviour, an application feature. An agent writes one cheaply, and the project pays for it on every later change: code to keep working, tests, docs, help text, one more thing for a user to learn. Feature creep is that cost piling up, one small addition at a time. Backpressure weighs each feature before it lands, so the project grows by the features its users reach for.

Three inputs settle a feature, and each has one owner:

- **Cost**, measured by you: what each part adds. Name it concretely, in your own judgement: code and tests, docs and help text, new config surface, new failure modes, interactions with other features, upkeep on every later change.
- **Use**, measured by you, from evidence (below). "Might be useful" is a guess, and a guess counts as unknown use.
- **Value** to the people using it, rated by the user: **high**, **low** or **unsure**. Ask only for a feature that cost and use leave undecided (its use is unknown, or real use meets a real cost and neither clearly wins), and record the answer in the ledger. The rating is the user's alone: leave it as `-` until they give it.

## Evidence of Use

Name the source for every use claim:

- **The user's knowledge**: asked once per undecided feature, then read from the ledger.
- **The issue tracker**: requests and reports that name the feature or the need behind it.
- **Agent transcripts**, for a tool agents run: the calls of a command or flag.
- **Reachability**: whether a user can get to the feature at all (a menu, a route, a documented command).
- **Telemetry**, where the project has it.

When none of them settles the use, the use is unknown: say so, and name the evidence that would settle it.

## Proposal Mode

Run it before building a feature that a spec proposes or a request asks for.

1. Read the ledger. A feature, or a near match, with a **decline** or **deferred** row stays at that verdict unless the row's revisit condition has come up: cite the row and stop.
2. Split the proposal into its parts (each command, flag, option, mode, config key, output format) and name each part's cost.
3. Give each part's evidence of use, with its source.
4. Find the smallest version that serves the evidenced use.
5. Ask the user to rate the value of each undecided part (see **Value** above).
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

## Audit Mode

Run it when the user asks to audit a project's features, or one module or path of them. An audit only reports: it gives each feature a bucket and its evidence, the user approves each cut, and each cut ships as its own change.

1. **Read the ledger**, and apply its audit rules (see **Feature Ledger**) before scanning.
2. **Scan the scope.** List every feature in it: each command, flag, config key, hook, behaviour or application feature a user or caller reaches. Each command and each flag is its own feature, so an unused flag of a used command is a cut. Date each by the commit that added it (for a flag, the commit that added its argument definition), following its history across moves and imports back to where it first appeared.
3. **Measure cost and use** for each, by the evidence sources above and the counting rules below.
4. **Sort** each feature into the first bucket that fits, trying them in this order:
   1. **trivial**: its cost is too small to weigh, such as a one-line alias. Count it and move on.
   2. **cut**: it has a real cost and no evidenced use across the chances it had to be used.
   3. **merge**: another feature does the same job, in the project or in a tool its users already run (such as a hook in the standard collection of the hook runner the project uses); fold it into that one.
   4. **shrink**: it is used, but only some of its parts are, such as an option whose values nobody passes; the unused parts go.
   5. **measure**: its use is unknown; name the signal it waits for and where that would come from. Telemetry may be that signal, named as a proposal of its own for proposal mode.
   6. **keep**: its evidenced use justifies its cost.

   Judge a young feature like any other, by its use across the chances it had.
5. **Write the report** to the temp directory, as [HTML-REPORT.md](HTML-REPORT.md) specifies, open it, and ask the user which candidates to explore.
6. **Grill** through the candidates the user picks: call the Skill tool with "grilling". Ask the user to rate the value of each undecided one, and write each decision to the ledger as it is made.

The audit is done when every feature in scope sits in one bucket with its cost and use, the report is written, and each decision from the grilling is in the ledger.

### Counting use

Count what shows a feature serving someone, not what touches it:

- **Use comes from outside the build.** Drop the calls from the session that built or changed the feature: its building and testing.
- **Setup commands count outcomes**, such as homes made or repos registered, not calls, so dev runs don't inflate them.
- **Hooks count outcomes**: each pass and each fail, not each call. A guard that has never failed may be idle or may be working: sort it as **measure**, with the user's value rating as the signal it waits for.
- **Once-per-trigger features** (once per spec, once per repo) are judged against how often their trigger happened, so a low count by design doesn't read as disuse.
- **A cross-cutting rule is one feature.** Judge a rule that spans many commands, such as `--dry-run` on every mutating command, as a whole, so it isn't cut piece by piece.

## Feature Ledger

Each project keeps its decisions in `docs/feature-backpressure.md`, one Markdown table at that fixed path, so the user answers each unknown once. Create it with its first row:

```markdown
# Feature backpressure ledger

| Feature | Verdict | Value | Reason | Date | Revisit when |
| --- | --- | --- | --- | --- | --- |
| `export --format csv` | deferred | unsure | every request names JSON | 2026-11-26 | an issue asks for CSV |
| `sync --watch` | decline | low | one request, and cron covers it | 2026-11-26 | a second user asks |
| usage counter on `report` | measure first | - | no evidence of use yet | 2026-11-26 | 30 days of the counter |
| `plugin` config key | build | - | groundwork for plugins | 2026-11-26 | the plugins spec starts |
```

One row per decided feature. **Verdict** holds a proposal verdict, **deferred** for an extra a build-smaller verdict left out, or an audit bucket. **Value** holds the user's rating, or `-` when they weren't asked. The rows it holds:

- **decline** verdicts, and the **deferred** extras of a build-smaller verdict, with why, so they aren't proposed again until their revisit condition comes up.
- **measure first** and **measure** rows, whose revisit condition names the signal they wait for.
- **build** and **build smaller** rows, including groundwork built for work not yet started: reason "groundwork for X", revisit when X starts.
- **audit buckets** the grilling settled (cut, merge, shrink, keep), so the next audit skips them.

The ledger stays current by these rules:

- The change that acts on a verdict (a cut, a shrink, a merge, a deferred extra built) updates its row in the same commit.
- Proposal mode rewrites a deferred row as **build** when it adds that extra back.
- An audit skips settled rows until their revisit condition comes up, re-checks any row dated before its feature's last commit, and drops the rows for features that no longer exist.
- Only a hard-to-reverse decision with a real trade-off also gets an ADR: call the Skill tool with "domain-modeling" to write it, and point the row's reason at it.

## Checklist

- [ ] The ledger was read first, and no declined or deferred item came back without its revisit condition
- [ ] Every part of the proposal has its cost and its use, with the use's source
- [ ] Value came from the user, asked only where cost and use left a part undecided
- [ ] The report ends on exactly one verdict, with deferred extras or the settling evidence named
- [ ] The ledger holds a row for every verdict
- [ ] An audit applied the ledger's audit rules, put every feature in scope in one bucket with its cost and use, and capped its report's cards at 10 with a count of the rest
- [ ] No cut is made without the user's approval, and each approved cut ships as its own change
