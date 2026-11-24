# Python Docstrings

## Summary line

One line, on the docstring's first line. A unit or range the type can't express belongs here.

```python
def value(self, pos: int) -> float:
    """Brightness in [0.0, 1.0], as of the last :meth:`update` call."""
```

## Class docstrings

Put the class's first caller contract on the summary line, and each further one under a short section named after it (for example, **Update model**: when and how state is mutated). Construction parameters go under `Args:`.

```python
class Ripple:
    """Call :meth:`update` once per frame, before any :meth:`value` call.

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
def drain(writer: PulseWriter) -> int | None:
    """``None`` until :meth:`PulseWriter.start` has run on ``writer``."""
```
