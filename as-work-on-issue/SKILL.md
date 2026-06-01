---
name: as-work-on-issue
description: >
  Implement a GitHub issue end-to-end: fetch the issue, read project context,
  explore code, follow TDD to satisfy all acceptance criteria, validate, commit,
  and open a PR. Use this skill whenever the user asks to work on, implement,
  tackle, fix, or close a GitHub issue — even if they just say "work on #N",
  "implement #N", "fix issue #N", "close #N", "tackle #N", or "start on the
  next issue". Also use when the user wants to pick up the next ready-for-agent
  task, grab something from the backlog, or asks "what should I work on next?".
argument-hint: "GitHub issue number (e.g. 12) or leave blank to run dispatch.sh first"
---

# Work on a GitHub Issue

Implement a single GitHub issue from start to merged PR. Stay focused — do not
fix unrelated problems or refactor adjacent code.

> Delegate all implementation to a fresh subagent to avoid context pollution.

## Step 0 — Find the issue (if no number given)

```sh
bash <skill-dir>/scripts/dispatch.sh
```

Use the printed "Next up" number. If unavailable:

```sh
gh issue list --label "ready-for-agent" --state open --json number,title,body
```

Pick the lowest-numbered issue with no open "Blocked by" dependencies.

## Step 0.5 — Set up a git worktree

Before dispatching, create an isolated worktree for the issue branch so parallel
subagents never conflict on checkouts:

```sh
cd <repo-root>
git fetch origin main
git worktree add ../<repo-name>-issue-<N> -b issue-<N>-<short-slug> origin/main
```

Pass the worktree path (e.g. `../<repo-name>-issue-<N>`) to the subagent as its
working directory. After the PR is merged, clean up:

```sh
git worktree remove ../<repo-name>-issue-<N>
git branch -d issue-<N>-<short-slug>
```

## Step 0.6 — Dispatch to a fresh subagent

Call `runSubagent` with description `"Implement issue #<N>"` and this prompt
(substitute `<N>`, `<owner>/<repo>`, `<worktree-path>`, `<branch-name>`):

---

Load the as-work-on-issue skill and follow every step precisely:

```sh
curl -fsSL https://raw.githubusercontent.com/aaronsilinskas/ai-skills/main/as-work-on-issue/SKILL.md
```

Then implement issue #<N> in <owner>/<repo> following that skill exactly.

Context for this run:
- Working directory: <worktree-path> (git worktree already on branch <branch-name>)
- Do NOT run git checkout or git worktree commands — the branch is already set up
- Skip Step 0 (no issue to find) and Step 0.5 (worktree already created)
- Start at Step 0.6 but skip the subagent dispatch — execute the steps directly

Do not summarize, skip, or paraphrase any step. Every step must be fully completed
before moving to the next.

---

Relay the subagent's outcome to the user and stop.

## Maintaining this skill (and all as-* skills)

The canonical source for all as-* skills is https://github.com/aaronsilinskas/ai-skills,
cloned at ~/dev/ai-skills. After patching any as-* skill locally via skill_manage,
sync and push:

```sh
cp ~/.hermes/skills/<skill-name>/SKILL.md ~/dev/ai-skills/<skill-name>/SKILL.md
cd ~/dev/ai-skills
git add <skill-name>/SKILL.md
git commit -m "<describe the change>"
git push
```
