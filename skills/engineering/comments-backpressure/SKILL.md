---
name: comments-backpressure
description: "Push back on code comments: sort each into remove, design change, test, ADR or keep, and try those first before writing a new one. Use when writing code, reviewing or auditing comments and docstrings, or when asked to add docs or document code."
argument-hint: "file or symbol to write or review"
---

# Comments Backpressure

**The code itself** is the documentation: its names, its types, its tests, and the message strings of its asserts, logs and errors. A comment claims the code itself can't say something. Test that claim every time, in both modes below, and keep a comment only for a non-obvious _why_ that passes.

## Review: sort every comment

Put each comment and docstring in scope into the first bucket that fits, then take its action:

1. **remove**: it narrates or restates the code. A phase label (`# Phase 1: add cards`), a section banner, a line retelling the next statement, a docstring retelling the name or the body. Delete it. Where the code reads unclearly without it, rename or extract a helper until the code itself says it.
2. **design change**: it hides something the code itself should express. A precondition that belongs in a type or a check, an ordering rule the API should enforce, a magic value that wants a named constant. Make the change, then delete the comment. When run on its own over code outside the task, file the change as a finding and leave the comment until the change lands.
3. **test**: it states behaviour a test should pin ("returns empty when the buffer wraps"). Write a test named for that behaviour (see the `test-quality` skill), then delete the comment.
4. **ADR**: it records a hard-to-reverse decision with a real trade-off, such as why this protocol or data layout over the obvious one. Call the Skill tool with "domain-modeling" to write the ADR, then replace the comment with a one-line reference to it, or with nothing when the ADR is easy to find from the code.
5. **keep**: the residue, a non-obvious _why_ none of the four can carry. A workaround, a hardware quirk, a deliberate deviation, an external contract. Keep it to one line stating the reason.

Skip whatever the project's hooks or linters already enforce. The review is done when every comment in scope sits in one bucket and its action is taken or filed; report the bucket for each.

## Writing: push back first

Write the code clean as you go, so comments never need pruning later. Before adding any comment, try the four alternatives in order: say it in the code itself (a name, an extracted helper, a message string), change the design so it holds the rule, pin it with a test, or record the decision in an ADR. Write a comment only for what survives all four, as one line.

## The Message String Is the Doc

The assert, log or error message is the doc. Put the reason in the string the program prints, where it reaches the reader at the moment it matters.

```python
assert cache.ready, "cache must be warm before the first frame"
raise ValueError(f"band {key!r} overlaps {other!r}")
log.warning("retrying upload: server dropped the connection mid-chunk")
```

## Specific Cases

- **Docstrings, public APIs included.** A docstring holds a contract the signature can't show: an ordering constraint, a side effect, return semantics, or when it raises. A symbol whose name and signature say it all goes without one. When the project's linter requires docstrings or it publishes generated API docs, follow the project with a one-line summary of what the name leaves out, plus those contracts.
- **Work tracking.** Follow-up work goes in the issue tracker. File it there and delete the TODO, ticket number, "later ticket" or "slice N", which go stale once the work lands.
- **Tests.** The test name states the guarantee and the assertion message explains a failure. Phase labels and Arrange / Act / Assert comments go; the `test-quality` skill owns the layout.
- **Tool directives and headers.** License headers, shebangs, encoding lines and tool directives (`# noqa`, `# type: ignore`, `// eslint-disable-next-line`) stay as they are: tools read them. When a suppression's reason is non-obvious, state it on the same line.

## Language-Specific Formatting

When a docstring survives, format it per the target language's conventions:

- Python docstrings: [python-docstrings.md](python-docstrings.md)
- Kotlin KDoc: [kotlin-kdoc.md](kotlin-kdoc.md)
- TypeScript TSDoc: [typescript-tsdoc.md](typescript-tsdoc.md)

## Checklist

- [ ] Every comment and docstring in scope sits in one bucket, and its action is taken or filed
- [ ] Every kept comment is one line holding a non-obvious _why_
- [ ] Asserts, logs and errors carry their reason in the message
- [ ] Surviving prose is formatted per the target language's reference file
