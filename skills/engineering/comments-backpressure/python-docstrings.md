# Python Docstrings

## Summary line

One line, stating what the name and signature leave out. A unit or range the type can't express belongs here.

```python
def value(self, pos: int) -> float:
    """Brightness in [0.0, 1.0], as of the last ``update(t)`` call."""
```

## Class docstrings

A class docstring holds the contracts a caller must follow and the construction parameters whose meaning their names and types don't show. Its summary line is the first contract; give each further contract a short section named after it (for example, **Update model**: when and how state is mutated).

```python
class Ripple:
    """Call ``update(t)`` once per frame, before any ``value(pos)`` call.

    Args:
        speed: Ring growth, in LEDs per second.
    """

    def __init__(self, center: int, speed: float) -> None: ...
```

## `Args:` / `Returns:` / `Raises:`

Use Google-style sections when a parameter's meaning or constraint isn't clear from its name and type, or when the method raises for a caller-facing reason. List only the parameters that need it.

**An `Args:` entry documents only its own parameter.** A side effect or method-level contract goes in the summary or its own paragraph, never in the nearest parameter's entry.

```python
def write_pulses(self, durations: list[int]) -> None:
    """Blocks until the last pulse is sent.

    Args:
        durations: In µs, alternating mark and space, starting with a mark.
    """
```

## `__init__`

Construction parameters go in the class docstring's `Args:`, so `__init__` gets none.

## Symbol references

Use the Sphinx roles `` :class:`Name` `` and `` :meth:`name` `` for another class or method, so the reference resolves to a link in generated docs. Use ``double backticks`` for parameters, fields, literals (``None``, ``True``) and the method's own name.

```python
def drain(self) -> int | None:
    """``None`` until :meth:`start` has run on the :class:`PulseWriter`."""
```
