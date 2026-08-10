---
name: grilling
description: Interview the user relentlessly about a plan or design. Use when the user wants to stress-test a plan before building, or uses any 'grill' trigger phrases.
argument-hint: "the plan or design to grill (or leave blank to use the conversation)"
---

Interview me relentlessly about every aspect of this until we reach a shared understanding. If nothing was handed to you, grill what we've been discussing in the conversation.

Map the decision as a tree: some questions can't be settled until earlier ones are. The **frontier** is every question whose prerequisites are already answered. Work the frontier in rounds rather than one question at a time — asking one-by-one when several are independent is needlessly slow.

## Each round

1. **Compute the frontier** — every open question whose prerequisites are now settled.
2. **Ask the whole frontier at once**, as one numbered round. Each question uses this fixed shape:

   ```
   ❓ **Q1** - **<short title>**: <the question, with any choices>
   ➡️ <your recommended answer>
   ```

   Number the questions `Q1`, `Q2`, … within the round. Always give a recommended answer on its own `➡️` line — never ask without recommending.
3. **Wait for my answers** to the round before moving on.
4. **Recompute the frontier** from what I answered — new questions may open up, others may fall away.

Repeat until the frontier is empty. That's when we're done.

## Facts vs. decisions

A *fact* is something the environment can answer — how something already works, what a file or resource contains, what a tool already does. Don't ask me these. Dispatch them to a background sub-agent and keep going; only a question that depends on a running exploration waits for it. Fold the answer in when it lands.

A *decision* is mine. Put each one to me and wait — never decide it for me, even when you have a recommendation.

Do not act on it until I confirm we've reached a shared understanding.
