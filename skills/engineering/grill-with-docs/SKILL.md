---
name: grill-with-docs
description: A relentless interview to sharpen a plan or design, which also keeps the domain docs (map + glossary) up to date as we go.
argument-hint: "the plan or design to grill (or leave blank to use the conversation)"
disable-model-invocation: true
---

Invoke the `grilling` skill via the Skill tool to run the interview, using the `domain-modeling` skill to keep the domain docs (`domain.md` map + `domain-language.md` glossary) current as decisions crystallise. Update the plan or design (e.g. a local PRD draft) inline as answers land. Keep looping until no open questions remain.

When the design has settled, do **not** publish silently. If this grilling was sharpening a PRD draft toward publication, tell the user it is ready and ask them for the go-ahead. Only after they confirm: publish the finalized PRD to the project issue tracker (per the project's backlog docs) and delete the local draft. Do **not** apply the `ready-for-agent` label — that belongs on the implementation issues the `to-issues` skill later creates, not on the PRD itself.
