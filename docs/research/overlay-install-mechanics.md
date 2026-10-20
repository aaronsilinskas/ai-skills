# Overlay install and name-collision mechanics

- **Date:** 2026-10-20
- **Baseline:** mattpocock/skills tag `v1.3.1` (commit `24fe0ef`)
- **Addendum (#59):** for setup output and invocation-graph changes at the official marketplace pin `49dd158`, see [Addendum: v1.3.1 → 49dd158](#addendum-v131--49dd158-official-marketplace-pin).
- **Resolves:** #41 (parent #39)
- **Question (from #41):** How do Matt's v1.3.1 install paths (Claude Code plugin, `npx skills`, others) deliver his skills **per project**, and what happens when a second source provides a same-named skill under each path? Document the effects of a **global** install too (without performing one). What exactly does `setup-matt-pocock-skills` write into a consuming repo, and which upstream skills invoke which others by name?

## Sources

| Key | Source | Version read |
|---|---|---|
| `UP` | mattpocock/skills, read with `git show v1.3.1:<path>` | tag `v1.3.1` |
| `OFF` | `anthropics/claude-plugins-official` `.claude-plugin/marketplace.json` (via `gh api`) | fetched 2026-10-20 |
| `VS` | vercel-labs/skills (`npx skills`) source | `a80e4c9`, v1.7.4 (= `npm view skills version`, published 2026-10-19) |
| `CC-skills` | https://code.claude.com/docs/en/skills | fetched 2026-10-20 |
| `CC-discover` | https://code.claude.com/docs/en/discover-plugins | fetched 2026-10-20 |
| `CC-loading` | https://code.claude.com/docs/en/plugins/loading | fetched 2026-10-20 |
| `CC-components` | https://code.claude.com/docs/en/plugins/components | fetched 2026-10-20 |
| `AURA` | `/Users/AaronH/dev/aura/aura-prototype` `AGENTS.md`, `CLAUDE.md`, `docs/agents/*` | working tree, read-only |

I did not install anything. Every `VS` claim comes from reading the code. The follow-up ticket #42 later tested the collision cases with project-scoped installs; §1.3 and §2 mark those results **[verified, #42]**. Claims about Claude Code behaviour are tagged **[documented]**, meaning a docs page states it, or **[inferred]**, meaning I derived it and no docs page states it.

---

## 1. Install paths at v1.3.1

### 1.1 What upstream tells users

- **Claude Code:** `claude plugins install mattpocock-skills`, or `/plugin install mattpocock-skills` in a session. "It's in Claude Code's official marketplace, so there's nothing to add first, and updates arrive automatically." (`UP/README.md:25-46`, `UP/.agents/install-block.md:7-23`)
- **Codex and other agents:** `npx skills@latest add mattpocock/skills`, and make sure `setup-matt-pocock-skills` is among the skills picked. A "For tinkerers" variant uses the same command on Claude Code. (`UP/README.md:48-72`)
- **The two routes are exclusive.** "Installing both leaves the user with every skill twice: always say 'pick one'." (`UP/.agents/install-block.md:55-57`)
- **Repo-as-marketplace fallback:** `/plugin marketplace add mattpocock/skills`, then `/plugin install mattpocock-skills@mattpocock`. `UP/.claude-plugin/marketplace.json` exists for this, but it is "not documented to users". (`UP/.agents/install-block.md:59-61`)
- **Versus `origin/main`:** v1.3.1 has no Codex-plugin, Copilot or Gemini install routes. Those appear only after the tag (commit `b0618bc`). The earlier lead list described `origin/main`.
- **Per-repo setup:** the setup step, "Run `/setup-matt-pocock-skills` … once per repo", is the same for both routes. (`UP/README.md:74-80`)

### 1.2 Claude Code plugin

**What it delivers**
- The plugin is the `skills` array in `UP/.claude-plugin/plugin.json`: 27 explicit paths.
  - engineering (20): ask-matt, diagnosing-bugs, grill-with-docs, triage, improve-codebase-architecture, setup-matt-pocock-skills, tdd, to-spec, to-tickets, wayfinder, implement, implement-spec, prototype, research, domain-modeling, codebase-design, code-review, pr, retro, wizard
  - productivity (7): grill-me, grilling, handoff, teach, to-questionnaire, wait-what, writing-for-agents
  - `misc/` and `in-progress/` are excluded. (`UP/.agents/adr/0002-…md:9-11`)
- The manifest `version` is `"1.3.1"`.
- Docs say a `skills` manifest key adds to the default `skills/` scan **[documented, CC-components]**. Matt's `skills/` holds only bucket folders (`skills/<bucket>/<skill>/SKILL.md`), so the default scan should add nothing beyond the 27 **[inferred]**.

**Pin mismatch: the official listing does not pin v1.3.1**
- The official listing pins `{"source":"url","url":"https://github.com/mattpocock/skills.git","sha":"49dd158…"}` (`OFF`).
- `49dd158` is 2026-10-09, after the v1.3.1 tag (`24fe0ef`). Its `plugin.json` is byte-identical and still says `1.3.1`, but 18 skill files differ.
- The differences that matter here:
  - `implement` calls `tdd` and `code-review` through the Skill tool. At v1.3.1 it only says "use /tdd" and "/code-review".
  - `setup-matt-pocock-skills` creates the triage labels.
  - `code-review` stops hard-coding `docs/agents/issue-tracker.md`.
  - The GitHub tracker template adds `gh issue create --parent`.
  - `wayfinder` forbids triage labels.
- Users of the official plugin therefore run `49dd158`, not v1.3.1.
- Claude Code detects updates by version and names the cache directory after it (**[documented, CC-loading]** "Versions and updates"). Because `49dd158` and v1.3.1 both report `1.3.1`, a pin move with no version bump may not reach installed users **[inferred]**.

**Install scopes** (**[documented, CC-discover]** "Choose an install scope", "Install from your shell")

| Scope | Command | Records `enabledPlugins` in | Reach |
|---|---|---|---|
| user (CLI default) | `claude plugin install mattpocock-skills@claude-plugins-official` | `~/.claude/settings.json` | "every project on this machine" |
| project | `… --scope project` | `.claude/settings.json` (committed) | "everyone who works in this repository" |
| local | `… --scope local` | `.claude/settings.local.json` | "you, in this repository only" |

- **Upstream never mentions scope.** Its bare `claude plugins install mattpocock-skills` therefore lands at **user scope**.
- **Files land in the user cache whatever the scope.** Scope only says where the plugin is enabled; the files always go to `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` (or `$CLAUDE_CODE_PLUGIN_CACHE_DIR`) **[documented, CC-loading]** "Find plugins on disk".
- **Project scope does not install for collaborators.** A project-scope entry "turns the plugin on for your collaborators but doesn't download it to their machines". Each collaborator runs the install with `--scope project` once. Until then, `/plugin` shows "enabled in project settings but isn't installed here" **[documented, CC-discover, CC-loading]**.
- **Precedence when scopes disagree:** local overrides project, which overrides user. Managed settings override all. To opt out of a project-enabled plugin, set it to `false` in `.claude/settings.local.json` **[documented, CC-loading]** "Find where a plugin is enabled".
- **Cloud sessions:** "Plugins declared in the repository's `.claude/settings.json` and plugins enabled only in your user settings don't load in cloud sessions." Committed `.claude/skills/` does load there **[documented, CC-skills]**.
- **Auto-update** is on by default for `claude-plugins-official` **[documented, CC-discover]**.

**Global (user-scope) effects**
- All 27 namespaced skills (`/mattpocock-skills:<name>`) load in every project **[documented]**.
- Each bare `/<name>` resolves to the plugin skill unless another command already uses that name **[documented, CC-skills]** "How a skill gets its command name".
- A project can turn the plugin off locally with `false` in `.claude/settings.local.json` or `.claude/settings.json` **[documented]**.

### 1.3 `npx skills` (vercel-labs/skills v1.7.4)

**What it offers from Matt's repo**
- The discovery walk descends into known container dirs (`skills/` is one) up to `DEFAULT_SKILL_CONTAINER_DEPTH = 3` (`VS/src/constants.ts`, `VS/src/blob.ts`, `VS/src/skills.ts`).
- That reaches `skills/<bucket>/<skill>/SKILL.md` in every bucket. At v1.3.1 that is **37** SKILL.md files: engineering 20, productivity 7, misc 4, in-progress 6.
- None has `metadata.internal: true`, the only hide flag (`VS/src/skills.ts` ~L117). So the picker should list all 37, not just the 27 the plugin ships **[inferred from code]**.
- **Default ref:** with no ref, the default branch is fetched, i.e. `main`, not v1.3.1.
- **Pinning:** `owner/repo#<ref>` is parsed as a ref (`VS/src/source-parser.ts` ~L285-311). `npx skills add mattpocock/skills#v1.3.1` pins **[inferred from code]**.

**Project scope (the default)**

| Item | Path | Source |
|---|---|---|
| Canonical copy | `<project>/.agents/skills/<name>/` | `getCanonicalSkillsDir` in `VS/src/installer.ts` |
| Claude Code entry | `<project>/.claude/skills/<name>`, a symlink to the canonical copy (`--copy` copies instead). With `-a claude-code` as the **only** target, the skill is copied straight into `.claude/skills/<name>` and no `.agents/` dir is created **[verified, #42]** | `agents['claude-code'].skillsDir = '.claude/skills'`, `createProjectSkillsDirByDefault: true` (`VS/src/agents.ts:155-164`) |
| "Universal" agents (Codex, Cline, Cursor, …) | read `.agents/skills/` directly | `VS/docs/agents.md` |
| Lock | `<project>/skills-lock.json`: `source`, `sourceUrl`, `ref`, `skillPath`, `computedHash` | `VS/src/local-lock.ts` |

- The scope prompt describes Project as "Install in current directory (committed with your project)" (`VS/src/add.ts:836-850`).
- In Claude Code these load as **project** skills (`.claude/skills/`) **[documented location, CC-skills]**.
- **Observed in #42** (`npx skills` 1.5.18, run as `npx -y skills`): a default `-y` install inside Claude Code auto-detected 8 agents and produced `.agents/skills/tdd` with a `.claude/skills/tdd` symlink. So did `-a claude-code codex`. Only `-a claude-code` alone copied the files in directly.

**Global scope (`-g`)**

| Item | Path | Source |
|---|---|---|
| Canonical copy | `~/.agents/skills/<name>/` | `VS/src/installer.ts` |
| Claude Code entry | `~/.claude/skills/<name>` (or `$CLAUDE_CONFIG_DIR/skills`), a symlink | `VS/src/agents.ts:11,159` |
| Lock | `~/.agents/.skill-lock.json` (or `$XDG_STATE_HOME/skills/.skill-lock.json`) | `VS/src/skill-lock.ts:64-72` |

- In Claude Code a global install is a **personal** skill: "All your projects on this machine" **[documented, CC-skills]**.
- Personal beats project on a name clash (see §2.2). A global `npx skills` install therefore overrides a same-named project-local skill in **every** project.
- The skill also shows up in every project's listing and `/` menu.
- Claude Code docs don't mention `~/.agents/skills`. Claude Code sees only the `~/.claude/skills` symlink **[documented by omission]**.

**Context on this machine:** `~/.claude/skills/` already holds fork skills as personal-level symlinks into this repo (for example `bdd -> …/aaronsilinskas-skills/skills/engineering/bdd/`). Those already outrank any project-level copy of the same name.

---

## 2. Same-name collisions

### 2.1 `npx skills`

- **One directory per name, last write wins.**
  - `installSkillForAgent` computes `<base>/.agents/skills/<sanitizeName(name)>`.
  - `cleanAndCreateDirectory` then runs `rm -rf` and the source is copied in (`VS/src/installer.ts:198-205, 327-405`).
  - `createSymlink` removes an existing link or dir at the agent path (`installer.ts:232-293`).
- **Overwrite warning only.** `add` checks `isSkillInstalled` and adds a yellow `overwrites: <agents>` line to the summary. There is one "Proceed with installation?" confirm, which `-y` skips (`VS/src/add.ts:896-943`). There is no per-skill prompt and no merge or layering.
- **The lock is keyed by name.**
  - `addSkillToLocalLock` does `lock.skills = {...lock.skills, [skillName]: entry}` (`local-lock.ts:198-206`).
  - `addSkillToLock` sets `lock.skills[skillName] = …` (`skill-lock.ts:177-193`).
  - So the last `add` of a name also replaces its recorded source.
- **`update` follows the recorded source.**
  - Project `update` reads `skills-lock.json`, clones each entry's `source`/`ref`, and compares the upstream folder hash to the lock's `computedHash` taken at install time.
  - If they differ it runs `add <source> --skill <name> -y` (`VS/src/update.ts:750-975`).
  - Edits made on disk are not part of the comparison. When the source has changed, update overwrites local edits **[inferred from code]**.
  - Global `update` does the same from `~/.agents/.skill-lock.json` with `-g -y` (`update.ts:496-723`).
- **Overlay consequence:**
  - Install the fork after upstream, and each shared name now points at the fork, on disk and in the lock. `update` then pulls those names from the fork.
  - Re-running `npx skills add mattpocock/skills`, which upstream tells users to do to pick up new skills, and selecting a shared name silently restores upstream's copy. The `overwrites:` line is the only signal.
  - **[verified, #42]** I installed `tdd` both ways round with `-a claude-code`. The last install owned `.claude/skills/tdd` and the single `skills-lock.json` entry. Only one `tdd` was listed, and a typed `/tdd` and `Skill("tdd")` both reached it.

### 2.2 Claude Code

| Case | Behaviour | Tag |
|---|---|---|
| Same name in personal (`~/.claude/skills`) and project (`.claude/skills`) | "Enterprise over personal, and personal over project." Only one runs for `/name`. | **[documented]** CC-skills "Resolve skills that share a name" |
| Plugin skill vs local skill of the same name | "Both load, because plugin skills are namespaced as `/plugin-name:skill-name`." | **[documented]** |
| Bare `/name` when a plugin and a local skill share it | Plugin bare name works "unless another command already uses that name". A local skill holds `/name`, and the plugin copy stays reachable as `/mattpocock-skills:name`. | **[documented]** CC-skills "How a skill gets its command name"; **[verified, #42]** for a typed `/tdd` |
| Plain-name Skill-tool call (`Call the Skill tool with "grilling"`) from inside a plugin skill | Resolves to the local skill holding the bare name. Docs describe `/name` resolution only, not Skill-tool name resolution. | **[verified, #42]**: with the plugin enabled at project scope and a local `.claude/skills/tdd`, a top-level `Skill("tdd")` call loaded the local copy (Claude Code 2.1.299). I did not run a call made from inside a plugin skill, but it uses the same plain name. |
| Is the plugin copy still listed and auto-invokable? | Yes, as `mattpocock-skills:<name>` with its own description ("Both load"). For description-triggered invocation, or when the caller's wording is loose, the model may choose either entry. | listed **[documented]**, and **[verified, #42]**: both `tdd` and `mattpocock-skills:tdd` were listed, and `/mattpocock-skills:tdd` loaded the plugin copy; selection behaviour **[inferred]** |
| Two plugins shipping the same skill name | Each is namespaced under its own plugin name. Docs don't say which one wins the bare name. | namespacing **[documented]**; bare-name winner undocumented |
| Two plugins with the same **manifest** name | One loads, by origin order: managed > `--plugin-dir` > marketplace > skills-dir. | **[documented]** CC-loading "Name conflicts" |
| Disable one plugin skill | `skillOverrides` can't: "Plugin skills are not affected by `skillOverrides`. Manage those through `/plugin` instead." `/plugin` enables or disables whole plugins. | **[documented]** CC-skills |
| Block one plugin skill from the model | A permission deny rule `Skill(mattpocock-skills:tdd)`. Docs give `Skill(name)` exact-match syntax and say an unqualified deny also blocks nested qualified variants, but never show a plugin-qualified example. It blocks invocation only; the entry stays listed. | **[inferred]** |
| Calling a skill that has `disable-model-invocation: true` | "Claude can't invoke the skill on its own … If Claude tries anyway, Claude Code blocks the call." The description is not in context. | **[documented]** CC-skills |

**Net for an overlay:**
- **Plugin upstream + local fork** (personal or project): the fork wins bare names. The plugin copies stay listed and can be invoked as `mattpocock-skills:*`, and they can't be hidden one at a time.
- **Fork at personal scope:** beats any project-local `npx skills` copy of upstream.
- **Fork shipped as a second plugin:** gives no reliable shadowing.

---

## 3. `setup-matt-pocock-skills` at v1.3.1

It is user-invoked (`disable-model-invocation: true`, `UP/skills/engineering/setup-matt-pocock-skills/SKILL.md:4`).

**What it reads** (SKILL.md:19-30)
- `git remote -v` and `.git/config`
- whether `AGENTS.md` and `CLAUDE.md` exist, and whether either already has `## Agent skills`
- `GLOSSARY.md` and `GLOSSARY-MAP.md`
- `docs/adr/` and `src/*/docs/adr/`
- `docs/agents/` and `.scratch/`
- whether `triage` is installed
- monorepo signals

**What it asks** (SKILL.md:38-61)
- **A. Tracker:** GitHub (default when the remote is GitHub), GitLab, local `.scratch/`, or "Other" written as prose.
- **B. Triage labels:** only if `triage` is installed. One question: keep the defaults?
- **C. Domain docs:** single-context is written without asking. Multi-context is offered only on monorepo signals.

**What it writes** (SKILL.md:72-112, `UP/docs/engineering/setup-matt-pocock-skills.md` "Prerequisites")

| Path | Content |
|---|---|
| `CLAUDE.md` if it exists, else `AGENTS.md`, else asks | `## Agent skills` block with `### Issue tracker` → "See `docs/agents/issue-tracker.md`."; `### Triage labels` → `docs/agents/triage-labels.md` (only if triage is installed); `### Domain docs` → `docs/agents/domain.md`. "Never create `AGENTS.md` when `CLAUDE.md` already exists." It updates an existing block "in the chosen file" in place. |
| `docs/agents/issue-tracker.md` | From `issue-tracker-{github,gitlab,local}.md`, or written from scratch for "Other" |
| `docs/agents/triage-labels.md` | 5-row table (`Label in mattpocock/skills`, `Label in our tracker`, `Meaning`): `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix` |
| `docs/agents/domain.md` | Read `GLOSSARY.md`/`GLOSSARY-MAP.md` and `docs/adr/`, "proceed silently" if absent, use the glossary's vocabulary, flag ADR conflicts |

- **Labels created:** none at v1.3.1. The docs page says outright that setup does not run `gh label create`, and the same goes for `wayfinder:*` (`UP/docs/engineering/setup-matt-pocock-skills.md`, "It didn't create my triage labels"). Label creation arrived in `5b7cade`, after the tag but inside the official pin `49dd158`.
- **Config scope:** "There is no user-level or global mode: the config lives in the repo." (same page)

**GitHub tracker template sections:** Conventions, Pull requests as a triage surface (default `no`), When a skill says "publish to the issue tracker", When a skill says "fetch the relevant ticket", and Wayfinding operations.

**Blocking convention per tracker** (Wayfinding operations in each template)

| Tracker | Child link | Blocking edge | Frontier |
|---|---|---|---|
| GitHub | sub-issue (`gh api` sub-issues endpoint). Fallback: task list plus `Part of #<map>` | **native issue dependencies**, `POST …/issues/<child>/dependencies/blocked_by -F issue_id=<db-id>`. Fallback: a `Blocked by: #<n>, #<n>` line | drop if `issue_dependencies_summary.blocked_by > 0`, or if the `Blocked by` line names an open issue, or if assigned |
| GitLab | `Part of #<map>` in the description | native `/blocked_by #<n>` quick action (Premium/Ultimate). Fallback: a `Blocked by:` line | `glab api …/links`, or the `Blocked by` line, or assigned |
| Local | `.scratch/<effort>/issues/NN-<slug>.md` | `Blocked by: NN, NN` line | unblocked once every listed file is `resolved` |

**How upstream skills find this config**
- Most say "The issue tracker [and triage label vocabulary] should have been provided to you. If not, tell the user to run `/setup-matt-pocock-skills`." Found in `implement-spec:9`, `to-spec:9`, `to-tickets:11`, `triage:43` and `wayfinder:25`. "Provided" means the always-loaded `## Agent skills` block.
- **Exception:** `code-review` at v1.3.1 hard-codes the path. Line 13: "If `docs/agents/issue-tracker.md` is missing, tell the user to run `/setup-matt-pocock-skills`". Line 29 fetches issues "via the workflow in `docs/agents/issue-tracker.md`". (Relaxed in `49dd158`.)
- `wayfinder` reads the tracker doc's "Wayfinding operations" section and defaults to local markdown when no tracker is provided (`wayfinder:25`).
- **Domain docs are read by literal path, not through config:**
  - `GLOSSARY.md`: `diagnosing-bugs:10`, `tdd:10`, `pr:37`, `improve-codebase-architecture:14,25,54,68-69`, `wait-what:7`
  - `domain-modeling` creates `GLOSSARY.md` and `docs/adr/` lazily (`domain-modeling:40-64`)
- **Publish-time labels:** `to-spec:19` and `to-tickets` §5 both apply `ready-for-agent`.

### Conflicts with aura-prototype's convention

What aura has:
- `CLAUDE.md` says only "Read `AGENTS.md` in full".
- `AGENTS.md` holds the real `## Agent skills` block: Backlog → `docs/agents/backlog.md`, Issue labels → `docs/agents/issue-labels.md`, Domain docs → `docs/domain.md` + `docs/domain-language.md`, plus deploy-watch and the spec/ticket workflow.

| # | Conflict | Upstream (v1.3.1) | aura |
|---|---|---|---|
| 1 | Which file holds the block | Edits `CLAUDE.md` because it exists, and only checks that file for an existing block. Result: a second `## Agent skills` block in `CLAUDE.md` | Block lives in `AGENTS.md`; `CLAUDE.md` is a pointer |
| 2 | Tracker doc name | `docs/agents/issue-tracker.md`, hard-coded by upstream `code-review` | `docs/agents/backlog.md`, so upstream `code-review` would tell the user to run setup |
| 3 | Tracker vocabulary | "publish to the issue tracker" | Heading "When a skill says 'publish to the backlog'". Matching would rely on prose **[inferred]** |
| 4 | Blocking edge | GitHub native dependencies (REST `dependencies/blocked_by`, `issue_dependencies_summary`), fallback `Blocked by: #n`. `to-tickets` says to use native blocking where available | "GitHub has no native issue-to-issue dependency", so a body line `Blocked by #42, #57` with no colon, and a frontier built from GraphQL `subIssues` plus a parsed body line. Mixed use gives edges that one side's frontier can't see |
| 5 | Sub-issue mechanics | `gh api` REST sub-issues endpoint | GraphQL `addSubIssue`. Different calls, same result |
| 6 | Label doc | `docs/agents/triage-labels.md`, 5 triage roles only, labels not created | `docs/agents/issue-labels.md`: same 5 roles in the same table shape, plus `idea`, `spec`, `grilled` and `wayfinder:*` |
| 7 | Publish labels | `to-spec` and `to-tickets` apply `ready-for-agent` on publish | `to-spec` applies `spec` after a local-draft, grill, then publish flow; `grill-with-docs` applies `grilled` |
| 8 | Domain docs | `docs/agents/domain.md` → `GLOSSARY.md` + `docs/adr/`; `domain-modeling` lazily creates `GLOSSARY.md`/ADRs; several skills read `GLOSSARY.md` literally | `docs/domain.md` (map) + `docs/domain-language.md` (glossary), no ADRs, no `docs/agents/domain.md`. Upstream skills would find nothing, "proceed silently", and could start a parallel `GLOSSARY.md` |
| 9 | Fork skills reading setup paths | n/a | Fork `implement/SKILL.md:67-70` names `docs/agents/backlog.md` and `docs/agents/domain.md`; fork `code-quality/SKILL.md:31` names `docs/agents/domain.md`. aura has no `docs/agents/domain.md`, and setup's version of that file means something different (glossary/ADR rules, not constraints) |

---

## 4. Cross-skill invocation graph at v1.3.1

**Invocation mode** (from `disable-model-invocation: true` in frontmatter)
- **User-invoked:** ask-matt, grill-with-docs, implement, implement-spec, improve-codebase-architecture, retro, setup-matt-pocock-skills, to-spec, to-tickets, triage, wayfinder, grill-me, handoff, teach, to-questionnaire, wait-what.
- **Model-invoked:** code-review, codebase-design, diagnosing-bugs, domain-modeling, pr, prototype, research, tdd, wizard, grilling, writing-for-agents.

**Convention:** an operative dependency is written as `Call the Skill tool with "<name>"` (`UP/.agents/invocation.md:16-22`). Only model-invoked targets can be reached this way. A user-invoked prerequisite is phrased as "tell the user to run `/x`".

**Edges**

| Caller (mode) | Calls by bare name | Form | Evidence |
|---|---|---|---|
| grill-with-docs (user) | grilling, domain-modeling | Skill tool | `grill-with-docs/SKILL.md:7` |
| grill-me (user) | grilling | Skill tool | `grill-me/SKILL.md:7` |
| triage (user) | grilling, domain-modeling | Skill tool | `triage/SKILL.md:76` |
| wayfinder (user) | grilling, domain-modeling; research (in a subagent); prototype; any skill named in the map's `## Notes` | Skill tool | `wayfinder/SKILL.md:77-79,111,115,124` |
| improve-codebase-architecture (user) | codebase-design (×2), grilling, domain-modeling | Skill tool | `improve-codebase-architecture/SKILL.md:13,64,66,71` |
| implement-spec (user) | tdd (inside each implementer subagent), code-review | Skill tool | `implement-spec/SKILL.md:29,36` |
| implement (user) | tdd, code-review | prose `/tdd`, `/code-review` at v1.3.1 (Skill tool in `49dd158`) | `implement/SKILL.md:9,13` |
| tdd (model) | codebase-design; code-review | Skill tool; prose "see the `code-review` skill" | `tdd/SKILL.md:26,38` |
| retro (user) | writing-for-agents | Skill tool | `retro/SKILL.md:11` |
| handoff (user) | generic "suggested skills" section |  | `handoff/SKILL.md:10` |
| code-review, to-spec, to-tickets, triage, wayfinder, implement-spec | `/setup-matt-pocock-skills` | tell the user (user action) | see §3 |
| ask-matt (user); setup's `domain.md` template | many `/x` labels | router or template prose only | `ask-matt/SKILL.md`; `domain.md:11` |
| codebase-design, diagnosing-bugs, domain-modeling, pr, prototype, research, wizard, grilling, teach, to-questionnaire, wait-what, writing-for-agents, to-spec, to-tickets, setup | none operative |  | grep of `skills/{engineering,productivity}` at v1.3.1 |

### Upstream callers that would reach a same-named overlay

The fork's skill names come from `skills/*/*/SKILL.md` at `ffa5b37`.

An overlay intercepts a call only if it holds the **bare name** (§2). Under the plugin route the namespaced upstream copy stays listed too, so selection is **[inferred]** rather than guaranteed.

| Fork skill (fork mode) | Upstream callers by bare name | Notes |
|---|---|---|
| grilling (model) | grill-with-docs, grill-me, triage, wayfinder, improve-codebase-architecture | The name with the most upstream callers |
| domain-modeling (model) | grill-with-docs, triage, wayfinder, improve-codebase-architecture | Upstream callers expect `GLOSSARY.md`/ADRs; the fork writes `docs/domain.md`/`domain-language.md` |
| codebase-design (model) | tdd, improve-codebase-architecture | |
| code-review (model) | implement-spec (Skill tool); implement (prose `/code-review`); tdd (prose) | The fork's code-review pulls in fork-only `bdd` and `code-quality`, so the overlay has to ship those too |
| research (model) | wayfinder (subagent) | |
| prototype (model) | wayfinder | |
| implement (model; upstream: user) | none | Only `/implement` and auto-invocation, where both copies compete |
| bdd (model) | **none.** Upstream implement and implement-spec call `tdd` | No overlay effect unless the overlay ships something named `tdd` |
| grill-with-docs, to-spec, to-tickets, triage, wayfinder, improve-codebase-architecture, grill-me, handoff, to-questionnaire, wait-what (user) | none operative | All user-invoked upstream; reached only by the user typing the name |
| diagnosing-bugs, wizard (model) | none | Description-triggered only; both copies listed |
| resolving-merge-conflicts (model) | none | Not shipped at v1.3.1 (removed in v1.3.0; only `docs/engineering/resolving-merge-conflicts.md` remains, marked "Archived") |
| checkout, code-quality, comments, to-idea, air-quality-data | none | Fork-only names; no upstream collision |

**Upstream-only names (no fork counterpart):** ask-matt, implement-spec, pr, retro, setup-matt-pocock-skills, tdd, teach, writing-for-agents. No fork skill names `tdd`, `setup-matt-pocock-skills` or `GLOSSARY.md` (grep of `skills/`).

**Wording:** fork skills say "invoke the `x` skill" and upstream says `Call the Skill tool with "x"`. Both use bare names, so neither targets a namespaced plugin copy on purpose.

---

## Addendum: v1.3.1 → 49dd158 (official marketplace pin)

Answers #59 for this doc: how §3 (setup output) and §4 (invocation graph) differ at `49dd158`, the sha the official listing pins (§1.2). Per-skill content verdicts live in the matching addendum in `docs/research/upstream-delta-v1.3.1.md`. Source key `UP@pin` = `git show 49dd158:<path>`. Commit shas come from `git log --no-merges v1.3.1..49dd158 -- <path>`.

- **Unchanged at the pin:** `.claude-plugin/plugin.json`, `marketplace.json` and `.agents/invocation.md` (`git diff --quiet v1.3.1 49dd158`). Same 27-skill set, version `"1.3.1"`, and the same user-invoked/model-invoked split (identical `disable-model-invocation: true` file sets).

### A.1 `setup-matt-pocock-skills` output (changes to §3)

**Labels created**
- New: "When Section B ran on GitHub or GitLab, create each configured label the tracker lacks (`gh label create` / `glab label create`)." (`UP@pin/skills/engineering/setup-matt-pocock-skills/SKILL.md:104`, `5b7cade`, which closes #616, #635, #733, #801.)
- Section B runs only when `triage` is installed (`SKILL.md:102`). So the labels created are the 5 triage roles, under their "Label in our tracker" strings. `wayfinder:map`/`wayfinder:<type>` are still not created **[inferred]**: nothing at the pin asks for them.
- **The upstream docs lag the skill.** `UP@pin/docs/engineering/setup-matt-pocock-skills.md:67` still answers "It didn't create my triage labels" with "It doesn't … It does not run `gh label create`". The page changed only in `dfe7549` (prose "unslop").

**GitHub tracker template** (`UP@pin/.../issue-tracker-github.md`)
- **Read an issue:** `gh issue view <number> --comments` plus jq filtering → `gh issue view <number> --json number,title,body,labels,comments` (`:8`, `5b7cade`).
- **"fetch the relevant ticket":** `Run gh issue view <number> --comments` → "Read it as in **Read an issue** above" (`:35`, `5b7cade`).
- **New bullet, "Make an issue a sub-issue of a parent":**
  - `gh issue create --parent <parent>`, or `gh issue edit <parent> --add-sub-issue <child>` (`gh` 2.94+).
  - Older `gh`: REST `POST …/issues/<parent>/sub_issues -F sub_issue_id=<child-db-id>`.
  - Fallback: `Part of #<parent>`.
  - Source: `:10`, `cffab50`, `9e2abf8`. The Wayfinding "Child ticket" line now points at this bullet (`:42`).
- **External PRs for triage:** `gh pr list … authorAssociation` → `gh api --paginate 'repos/{owner}/{repo}/pulls?state=open' --jq '… select(.author_association | IN("OWNER","MEMBER","COLLABORATOR") | not) …'` (`:24`, `e0efb6e`, `8e67db2`).
- **Blocking and frontier lines:** unchanged. Native `dependencies/blocked_by` is still canonical, so the §3 "Blocking convention per tracker" table stands.

**GitLab tracker template** (`UP@pin/.../issue-tracker-gitlab.md`)
- **List and frontier:** `glab issue list -F json` → `-O json` (`:9`, `:44`, `5b7cade`).
- **Links path:** `projects/:id/issues/:iid/links` → `…/issues/<child-iid>/links` (`:44`).
- **Read an issue:** still says "Use `-F json`" (`:8`, unchanged). Whether that flag is right for `view` was not checked.

**`triage-labels.md` template**
- Wording only: "Edit the right-hand column" → "Edit the "Label in our tracker" column" (`:15`, `5b7cade`). The 5-row table is unchanged.

**What it reads, asks and writes**
- Otherwise unchanged. Same §3 "What it reads/asks/writes" lists, same `CLAUDE.md`-first file rule, no global mode.

**How skills find the config**
- `code-review` joins the "should have been provided … If not, tell the user to run `/setup-matt-pocock-skills`" group (`UP@pin/skills/engineering/code-review/SKILL.md:13`, `3da8c01`).
- Its spec fetch now reads "via the workflow in the tracker doc" (`:29`). The §3 "Exception" bullet no longer holds at the pin. No promoted skill at the pin hard-codes `docs/agents/issue-tracker.md` (`git grep` of `skills/{engineering,productivity}/*/SKILL.md` at 49dd158 finds only setup itself).
- `implement` now reads the tracker ("fetch it from the issue tracker", `UP@pin/skills/engineering/implement/SKILL.md:9`, `6d6a5b9`) but has no setup pointer.
- `to-tickets` now uses "tracker doc's operation" for sub-issues (`to-tickets/SKILL.md:63`).

**Effect on the aura conflicts table** (rows refer to §3 "Conflicts with aura-prototype's convention")

| # | At `49dd158` |
|---|---|
| 2 | No longer triggered by `code-review`. The pin's code-review accepts any provided tracker doc, so aura's `docs/agents/backlog.md` named in `AGENTS.md` should satisfy it **[inferred]**. |
| 4 | Worse. The pin's `to-tickets` template says to omit `## Blocked by` "when blockers were set as native edges" (`to-tickets/SKILL.md:101`). Upstream-made tickets on GitHub would then carry native edges only, which aura's body-parsing frontier can't see **[inferred]**. |
| 5 | Upstream prefers `gh issue create --parent` / `--add-sub-issue`, with REST as the fallback. aura uses GraphQL `addSubIssue`. Same result. |
| 6 | Setup now creates missing triage labels when `triage` is installed. aura already uses the same 5 role names (row 6), so likely nothing is created **[inferred]**. `idea`/`spec`/`grilled`/`wayfinder:*` are still not created. |
| 1, 3, 7, 8, 9 | Unchanged. |

### A.2 Invocation graph (changes to §4)

**Edges**
- **implement (user) → tdd, code-review:** prose `/tdd`, `/code-review` → `Call the Skill tool with "tdd"` / `call the Skill tool with "code-review"` (`UP@pin/skills/engineering/implement/SKILL.md:11,15`; `e48341a`, wording tightened in `04320ee`).
  - Both targets are model-invoked, so the calls are legal under `.agents/invocation.md:22`.
  - This was the only promoted-skill edge still written as `/x` prose.
- **No other edge added or removed.**
  - `wayfinder:124` reworded step 3, but it calls the same skills.
  - `ask-matt:11` now says to "read that skill's SKILL.md" before asserting what it does. That is a file read, not a Skill-tool call. With an overlay holding the bare name, which copy it reads is undefined **[inferred]**.
  - handoff's "suggested skills" line is unchanged. teach (`ad5400b`) and the in-progress `chief-of-staff`/`claude-handoff` changes add no edges (grep at 49dd158).
- **`tdd` → `code-review`** is still prose (`UP@pin/skills/engineering/tdd/SKILL.md:38`), and `tdd` → `codebase-design` is still a Skill-tool call (`:26`).

**Conventions**
- **Phrasing:** `.agents/invocation.md` is byte-identical. `Call the Skill tool` lines in promoted SKILL.md files: 14 in 9 files → 16 in 10 (`git grep -c`).
- **`subagent-recursion.md` (new):** skills will not add guards that stop sub-agents re-invoking skills. "The harness should be responsible" (`UP@pin/.out-of-scope/subagent-recursion.md`, `4d04daa`).
- **`harness-name-collisions.md` (new):** upstream will not rename skills to dodge same-name collisions.
  - "The way through is namespaced invocation … `/mattpocock-skills:code-review`" (`UP@pin/.out-of-scope/harness-name-collisions.md:11`).
  - For skills.sh: "rename the folder and the `name:` field in your copy" (`:18`).
  - This is upstream's stated policy, and it matches §2.2's "both load; bare name to the local skill" model.

**Upstream callers that would reach a same-named overlay** (changes to the §4 table)

| Fork skill | At `49dd158` |
|---|---|
| code-review | Callers: implement-spec (Skill tool), **implement (Skill tool, was prose)**, tdd (prose). Two operative callers now, not one. |
| bdd | Still **none**. But implement's `tdd` call is now operative too, so an overlay that ships something named `tdd` would intercept it from both implement and implement-spec (per §2.2's verified `Skill("tdd")` row) **[inferred]**. |
| All other rows | Unchanged. |

### A.3 Install routes (non-skill files, bearing on §1)

- **Claude Code command** is now `claude plugin install mattpocock-skills@claude-plugins-official`, with no `--scope`, so it still lands at user scope (§1.2) (`UP@pin/.agents/install-block.md:29`, `b0618bc`).
- **Repo marketplace is now documented for other agents.** The "Not the install story" section is deleted. `.claude-plugin/marketplace.json` is now the documented route for Codex, Copilot and VS Code (`install-block.md:9`; ADR 0002 "Update, 2026-10-08", `UP@pin/.agents/adr/0002-ship-as-a-claude-code-plugin.md:49-51`).
  - The §1.1 "not documented to users" bullet is v1.3.1-scoped and still true there.
  - §1.1's "only after the tag (commit `b0618bc`)" is inside the pin.
- **Version-gated updates are documented for the non-Claude routes.** "Those routes reinstall only when the `version` in `plugin.json` changes" (`install-block.md:9`). This is stated for the `@mattpocock` routes, not for `claude-plugins-official`. It is consistent with §1.2's **[inferred]** note that a pin move with no version bump may not reach installed Claude Code users, but it does not prove it.
- **"Pick one" is unchanged:** installing both routes gives every skill twice (`install-block.md:119-121`).

### A.4 Which existing conclusions change

- **§1.2 "Pin mismatch" bullets:** accurate. Attribution, which §1.2 doesn't give: `gh issue create --parent` came from `cffab50`/`9e2abf8`. `5b7cade` changed the read/fetch commands and added label creation.
- **§3 "Labels created"** and the **code-review "Exception"**: both are superseded at the pin, as each already flags. The new fact is that upstream's own docs page still says labels aren't created (A.1).
- **§3 aura table:** rows 2, 4, 5 and 6 change as in A.1.
- **§4 edges table:** only the implement row changes, and it is already annotated. **Overlay-reach table:** the code-review and bdd rows change as in A.2.
- **§1 and §2 install and collision mechanics:** no conclusion flips. The pin adds upstream's documented collision policy (A.2) and new non-Claude routes (A.3).
