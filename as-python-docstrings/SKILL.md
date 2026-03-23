---
name: as-python-docstrings
description: "Write or review Python docstrings for classes, methods, functions, and modules. Use this skill whenever touching Python documentation — adding docstrings to new or undocumented code, rewriting vague or unhelpful ones, auditing a module for missing or stale docs, or deciding whether a symbol even needs a docstring. Use even when the user just says 'add docs' or 'document this' without specifying a format. Scope is strictly docstrings only — no code changes."
argument-hint: "file or symbol to document"
---

# Python Docstrings

## When to Use

- Adding docstrings to new or undocumented Python code
- Reviewing or rewriting existing docstrings for quality
- Auditing a module for missing or stale documentation

## Scope Constraint

Only add or update docstrings. Do **not** modify, refactor, or restructure any code — even if issues are noticed. Report code-level findings separately but leave the code unchanged.

## Class Docstrings

Open with what the class is **for** and why it matters to the caller — not a description of its internal mechanics.

Follow with technical contracts using concise bullet lists under named sections. Name sections after the actual contract being expressed — these will vary by domain. Examples from an animation library:

- **Update model** — when and how state is mutated
- **Sampling model** — how values are read or queried
- **State ownership** — who owns, creates, and disposes of state

```python
class Ripple:
    """Produces an expanding ring animation centered on a point.

    Useful for highlighting events or drawing attention to a position
    in a pixel strip or grid.

    Update model:
      - Call ``update(t)`` once per frame with the current timestamp.
    Sampling model:
      - Call ``value(pos)`` per pixel after each ``update`` call.
    State ownership:
      - Owns internal phase state; safe to copy by value.
    """
```

## Method Docstrings

One line is correct when the signature already conveys the _what_. Expand only to describe:

- Non-obvious **ordering** constraints (e.g., must call X before Y)
- **Return semantics** that aren't clear from the type annotation
- **Side effects** that affect external state

```python
def update(self, t: float) -> None:
    """Advance animation state to timestamp ``t``."""

def value(self, pos: int) -> float:
    """Return brightness at ``pos`` for the current frame, in [0.0, 1.0]."""
```

## `__init__` Docstrings

Do **not** add a docstring to `__init__` when the class docstring already describes construction parameters. Duplicate documentation drifts out of sync.

## Symbol References

Use `double backticks` for all symbol names, including:

- Class and method names: `Effect`, `update()`
- Parameters and fields: `t`, `pos`
- Literals that would otherwise read as bare words: `None`, `True`, `False`

```python
# Correct
"""Returns ``None`` if the buffer is empty."""

# Incorrect
"""Returns None if the buffer is empty."""
```

## What to Avoid

- **Restating the code**: if what a method does is obvious from its name and signature, the docstring adds no value.
- **Internal implementation details**: describe intent and contracts, not how it achieves them.
- **Caller responsibilities already expressed by types**: don't rephrase type annotations as prose unless there is a non-obvious constraint.

## Checklist

- [ ] Class docstring leads with user-facing purpose, not mechanics
- [ ] Technical contracts are in named bullet sections
- [ ] Method docstrings are one line unless non-obvious behavior needs explanation
- [ ] All symbol references use `double backticks`
- [ ] No `__init__` docstring if class docstring covers parameters
- [ ] Only docstrings were changed — no code was modified, refactored, or restructured
