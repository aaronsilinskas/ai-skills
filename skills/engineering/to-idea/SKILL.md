---
name: to-idea
description: Capture a discovery or new idea as a lightweight GitHub issue labeled "idea" to revisit later — a quick stub, not a fleshed-out spec. Use when something surfaces mid-work (often during grilling) that's worth not losing but shouldn't derail the current task.
argument-hint: "the idea to capture (or leave blank to pull it from the conversation)"
disable-model-invocation: true
---

# To Idea

Capture a discovery or new idea as a GitHub issue so it isn't lost — without stopping to flesh it out. This is deliberately a **stub, not a spec**: just enough to remember the idea and why it mattered, so a future session can pick it up.

Do **not** interview or grill the idea into shape. Synthesize what's already known, publish, and return to the original work.

The issue tracker and label vocabulary should have been provided to you by the project's agent docs (e.g. `AGENTS.md` and the docs it points to).

## Process

1. **Draft a short issue.**
   - **Title** — a concise, recognizable summary of the idea.
   - **Body** — 2–4 sentences: what the idea is, what triggered it (the discovery or context it came out of), and a one-line "to explore later" pointer. Link any related issue, PR, or discussion by number or URL — don't restate them. Use the project's domain glossary vocabulary. No file paths or code snippets (they go stale); the point is to remember the idea, not spec it.

2. **Publish it** to the project issue tracker with **only** the `idea` label. Do **not** apply `ready-for-agent`, a category, or any other triage label — an idea is a raw parking-lot entry, not a triaged or specified task.

3. **Report** the issue URL and return to what you were doing.

## Not a spec

The `idea` label keeps these distinct from specs and ready-for-agent work. An idea is a placeholder to look into later; fleshing it out happens *when you revisit it*, not now — that's when it graduates through `to-spec` (or a grilling session) into a real spec and implementation tickets.
