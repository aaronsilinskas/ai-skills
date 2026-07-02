---
name: comments
description: >
  Decide whether code needs a comment or docstring at all, and write the ones
  that survive that test well. Use whenever writing or reviewing comments and
  docstrings, adding documentation to new or undocumented code, rewriting vague
  or stale prose, auditing a module for missing or unnecessary docs, or deciding
  whether a symbol even needs a comment — even when the user just says "add
  docs", "document this", or "comment this code". Language-agnostic philosophy;
  language-specific formatting lives in the reference files.
argument-hint: "file or symbol to document or review"
---

# Comments & Docstrings

## Scope Constraint

Only add or update comments and docstrings. Do **not** modify, refactor, or
restructure code — even if issues are noticed. Report code-level findings
separately (often the _right_ fix for a bad comment is a code change you should
recommend, not make here) and leave the code unchanged.

## Comments Are a Last Resort

A comment or docstring is the _last_ place to convey intent — reach for prose
only after naming and tests have failed to carry it. Convey intent in this
order of preference:

1. **Naming.** A well-named function, variable, or extracted helper says what a
   comment would have said — and can't drift out of sync with the code. If you
   feel the urge to write a comment explaining a block, that block usually
   wants a name (extract it) or a clearer one.
2. **A test.** Behavior complex or non-obvious enough that you'd want to
   document it belongs in a _named test that asserts it_. An executable test
   documents the contract, proves it holds, and fails when it regresses — prose
   does none of these. "This handles the empty case by …" → write a test named
   for that case. (See the `bdd` skill.)
3. **A comment or docstring — last resort only.** Reach for prose _only_ when
   naming and tests genuinely cannot convey something: a non-obvious _why_ (a
   workaround, a hardware quirk, a deliberate deviation), an external contract,
   or an ordering/units constraint the types don't express. Keep it to the
   minimum — a one-line docstring stating purpose is usually enough.

Never write a comment or docstring that restates what the code already says. If
a reviewer can delete it and lose no information, it should not have been
written.

```python
# Bad — a comment block narrating mechanics that the code already shows
def _build(self, name, options):
    """Construct an Effect for the named effect.

    Splits the name into pack and effect, dispatches scene. names to the
    scene-local registry and everything else to the pack registry, then
    translates registry errors into effect-facing messages, builds the
    receipt, and allocates buffers.
    """
    builder, pack, effect = self._resolve(name)
    ...

# Good — purpose in one line; the mechanics are readable from the named
# resolver call, and the dispatch/error behavior is pinned by resolver tests
def _build(self, name, options):
    """Construct an Effect for the named effect."""
    builder, pack, effect = self._resolve(name)
    ...
```

## What to Avoid

- **Restating the code.** If what a symbol does is obvious from its name and
  signature, prose adds no value.
- **Narrating _what_ over _why_.** Describe intent and contracts, not the
  mechanics the reader can already see in the code.
- **Rephrasing the types.** Don't turn a type signature into prose unless there
  is a non-obvious constraint the type can't express.
- **Documentation that duplicates another source.** Two docstrings describing
  the same construction, or a comment echoing a test name, drift apart. Keep
  one source of truth.

## Language-Specific Formatting

The philosophy above is language-agnostic. When you do decide prose is
warranted, format it per the target language's conventions:

- Python docstrings — [python-docstrings.md](python-docstrings.md)
- Kotlin KDoc — [kotlin-kdoc.md](kotlin-kdoc.md)
- TypeScript TSDoc — [typescript-tsdoc.md](typescript-tsdoc.md)

## Checklist

- [ ] No comment or docstring narrates _what_ the code does — intent is carried
      by naming, with behavior pinned by tests
- [ ] Any prose that remains explains a non-obvious _why_ (or an
      external/ordering/units contract) that naming and tests cannot convey
- [ ] No comment or docstring merely restates the code or rephrases the types
- [ ] Prose that survives is formatted per the target language's conventions
      (see the reference files)
- [ ] Only comments/docstrings were changed — no code was modified, refactored,
      or restructured
