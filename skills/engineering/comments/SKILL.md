---
name: comments
description: "Decide whether code needs a comment or docstring, and write the ones that earn it. Use when writing, reviewing or auditing comments and docstrings, or when asked to add docs or document code."
argument-hint: "file or symbol to document or review"
---

# Comments & Docstrings

## Scope

When run on its own, change only comments and docstrings. The right fix for a bad comment is often a code change (a better name, an extracted helper, a named test): report it as a finding and leave the code as it is. When this skill is part of writing code or a wider review, make those fixes as the order below describes.

## Comments Are a Last Resort

A comment or docstring is the _last_ place to convey intent. Reach for prose only after naming and tests have failed to carry it. Convey intent in this order of preference:

1. **Naming.** A well-named function, variable, or extracted helper says what a comment would have said, and it can't drift out of sync with the code. If you feel the urge to write a comment explaining a block, that block usually wants a name (extract it) or a clearer one.
2. **A test.** Behavior complex or non-obvious enough that you'd want to document it belongs in a _named test that asserts it_. An executable test documents the contract, proves it holds, and fails when it regresses. Prose does none of these. "This handles the empty case by …" → write a test named for that case. (See the `test-quality` skill.)
3. **A comment or docstring, as a last resort only.** Reach for prose _only_ when naming and tests genuinely cannot convey something: a non-obvious _why_ (a workaround, a hardware quirk, a deliberate deviation), an external contract, or an ordering/units constraint the types don't express. Keep it to the minimum. A one-line docstring stating purpose is usually enough.

Never write a comment or docstring that restates what the code already says. If a reviewer can delete it and lose no information, it should not have been written.

```python
# Bad: a comment block narrating mechanics that the code already shows
def _build(self, name, options):
    """Construct an Effect for the named effect.

    Splits the name into pack and effect, dispatches scene-prefixed names to
    the scene-local registry and everything else to the pack registry, then
    translates registry errors into effect-facing messages, builds the
    receipt, and allocates buffers.
    """
    builder, pack, effect = self._resolve(name)
    ...

# Good: a one-line docstring for purpose. The mechanics stay readable from
# the code, and tests pin the dispatch/error behavior rather than narrating it.
def _build(self, name, options):
    """Construct an Effect for the named effect."""
    builder, pack, effect = self._resolve(name)
    ...
```

## What Prose Carries

Prose carries only a _why_, a contract, or a units or ordering constraint the types can't express. When an assert or log message can carry that _why_, put it there: the message is the doc.

Keep one source of truth. Two docstrings describing the same construction, or a comment echoing a test name, drift apart.

## Language-Specific Formatting

The philosophy above is language-agnostic. When you do decide prose is warranted, format it per the target language's conventions:

- Python docstrings: [python-docstrings.md](python-docstrings.md)
- Kotlin KDoc: [kotlin-kdoc.md](kotlin-kdoc.md)
- TypeScript TSDoc: [typescript-tsdoc.md](typescript-tsdoc.md)

## Checklist

- [ ] Naming carries intent and tests pin behavior; any prose that remains explains a non-obvious _why_ (or an external/ordering/units contract) they cannot convey
- [ ] Prose that survives is formatted per the target language's conventions (see the reference files)
- [ ] When run on its own: only comments and docstrings were changed, and code fixes are reported as findings
