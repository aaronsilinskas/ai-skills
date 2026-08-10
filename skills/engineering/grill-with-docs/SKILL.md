---
name: grill-with-docs
description: A relentless interview to sharpen a plan or design, using the domain map + glossary to keep the interview precise while capturing outcomes in the spec.
argument-hint: "the plan or design to grill (or leave blank to use the conversation)"
disable-model-invocation: true
---

Invoke the `grilling` skill to run the interview. Draw on the `domain-modeling` skill's discipline to keep the interview precise — challenge the user's terms against the existing `domain.md` map and `domain-language.md` glossary, sharpen fuzzy language, and cross-reference claims against the code — but capture whatever crystallises in the spec draft, **not** in the domain docs. Those docs describe as-built code, so leave them untouched while grilling; `implement` reconciles them when the code lands. Update the plan or design (e.g. a local spec draft) inline as answers land. Keep looping until no open questions remain.

When the design has settled, do **not** publish silently. If this grilling was sharpening a spec draft toward publication, tell the user it is ready and ask them for the go-ahead. Only after they confirm: publish the finalized spec to the project issue tracker (per the project's backlog docs) and delete the local draft. Do **not** apply the `ready-for-agent` label — that belongs on the implementation tickets the `to-tickets` skill later creates, not on the spec itself.
