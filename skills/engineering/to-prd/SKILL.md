---
name: to-prd
description: Turn the current conversation into a PRD — no interview, just synthesis of what you've already discussed. Produces a local document first for grilling, then publishes to the issue tracker once the design settles.
argument-hint: "topic to scope the PRD (or leave blank to use the whole conversation)"
disable-model-invocation: true
---

This skill takes the current conversation context and codebase understanding and produces a PRD. Do NOT interview the user — just synthesize what you already know. If the user passed a topic as an argument, use it to scope which part of the conversation to synthesize; otherwise cover the whole discussion.

The issue tracker vocabulary (for publishing later) should have been provided to you by the project's agent docs (e.g. `AGENTS.md` and the docs it points to).

## Process

1. Explore the repo to understand the current state of the codebase, if you haven't already. Use the project's domain glossary vocabulary throughout the PRD.

2. Sketch out the seams at which you're going to test the feature. Existing seams should be preferred to new ones. Use the highest seam possible. If new seams are needed, propose them at the highest point you can. The fewer seams across the codebase, the better - the ideal number is one.

Check with the user that these seams match their expectations.

3. Write the PRD using the template below as a **local document** (e.g. a markdown file in the repo or a scratch location) — do **not** publish it to the issue tracker yet. The design still needs sharpening.

<prd-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype. Trim to the decision-rich parts — not a working demo, just the important bits.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not implementation details)
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

A description of the things that are out of scope for this PRD.

## Further Notes

Any further notes about the feature.

</prd-template>

4. Stop here and hand back to the user. Tell them the draft is ready and say where it lives, then ask which they'd like to do next:

   - **Publish now, grill later** — publish the draft to the issue tracker as-is; the design can be sharpened later.
   - **Grill now** — run `grill-with-docs` to sharpen the design before publishing.

   Do **not** pick for them, and do **not** invoke `grill-with-docs` (or the `grilling` skill) yourself — it is **user-triggered**. If they choose to grill now, tell them to run `grill-with-docs` as the next step; the grilling loop, any inline updates to the draft and the domain docs, and the eventual publish all happen under that user-run skill.

5. Only if the user chose **publish now**: publish the draft to the project issue tracker (per the project's backlog docs), applying the `prd` label to the created issue, and delete the local file. Do **not** apply the `ready-for-agent` label — that belongs on the implementation issues the `to-issues` skill later creates from this PRD, not on the PRD itself. (If they chose to grill now, publishing instead happens at the tail of the user-run `grill-with-docs`, once the design has settled and only after the agent asks for the go-ahead.)
