---
name: as-embedded-dev
description: "Write, review, or optimize Python code for CircuitPython and MicroPython constrained runtimes. Use this skill whenever writing or reviewing Python that runs on microcontrollers, LED strips, or embedded hardware — even if the user doesn't say 'CircuitPython' explicitly. Always use for animation loops, per-frame update logic, per-pixel sampling, hot paths, or any code where GC pauses, memory allocations, or CPU limits matter. Also use when the user asks whether a Python pattern is safe, efficient, or compatible with constrained hardware."
argument-hint: "file or function to review or implement"
---

# Embedded Python Development

## When to Use

- Implementing or reviewing code that runs on CircuitPython or MicroPython
- Writing time-sensitive or tight loops where GC pauses would cause visible stutter
- Auditing code for memory allocations, object creation, or patterns that are unsafe on constrained hardware
- Deciding whether a Python pattern is safe to use in a hot path

## Project-Specific Rules

Before applying any guidance from this skill, check the project root for an `AGENTS.md` file. If one exists, look for a section named `## Embedded Runtime Constraints`. Treat all content under that heading as additional project-specific rules that extend or override the general guidance below — in particular, any listed hot paths and project-level conventions.

## Guiding Principle

Preserve readability while prioritizing low-overhead execution patterns. Don't sacrifice clarity for micro-optimizations on cold paths — apply performance discipline only where it demonstrably matters (hot paths and inner loops).

## Hot Path Definition

A hot path is any code that executes many times per second in a tight loop — where even small per-iteration costs compound into GC pressure or visible stutter. Common examples include:

- Animation update loops that run every frame (e.g., 30-60 times per second)
- Per-pixel sampling functions that run for every pixel on every frame

Everything else (construction, one-time initialization) is a cold path and can use normal Python patterns freely.

## Memory Rules (Hot Paths)

**Never allocate inside a hot path** unless genuinely unavoidable:

```python
# Bad — allocates a list every frame
def update(self, state, timer):
    values = [x * 2 for x in self.buffer]  # comprehension allocates

# Good — mutate in place
def update(self, state, timer):
    for i in range(len(self.buffer)):
        self.buffer[i] = self.buffer[i] * 2
```

Specific patterns to avoid in hot paths:

- List/dict/set literals or comprehensions
- `lambda` or closure creation
- Object instantiation (`Foo(...)`)
- String formatting (`f"..."`, `"".join(...)`)
- Exception raising for control flow

## Loop Rules (Hot Paths)

Always use plain `for` loops. List comprehensions and generator expressions allocate:

```python
# Bad
total = sum(x for x in buffer)

# Good
total = 0.0
for i in range(len(buffer)):
    total += buffer[i]
```

Keep branch logic minimal inside loops. Pre-compute bounds and constants outside the loop:

```python
# Pre-compute outside the loop
inv_span = 1.0 / span
lower = padding
upper = 1.0 - padding

# Lean inner loop
for i in range(pixel_count):
    pos = i / pixel_count
    if pos < lower or pos > upper:
        out[i] = 0.0
    else:
        out[i] = shape_func((pos - lower) * inv_span)
```

## Floating Point Rules

Avoid repeated expensive computations. Hoist constants out of loops and cache `math.*` calls:

```python
# Bad — recomputes tau every pixel
def shape(position):
    return math.sin(freq * position * 2.0 * math.pi)

# Good — capture tau once at definition time
tau = 2.0 * math.pi
def shape(position):
    return math.sin(freq * position * tau)
```

Prefer multiply over divide when the denominator is fixed. Avoid `**` (power) in hot paths unless the exponent is a compile-time constant and the platform handles it efficiently.

## CircuitPython Compatibility

Minimize and isolate CircuitPython-specific dependencies so the same code can run on MicroPython and other environments. Avoid scattering platform-specific imports or calls throughout modules; contain them at the boundary.

**Guard all `typing` and `collections.abc` imports:**

`Callable` lives in `collections.abc` in modern Python. `Any` and `TypeAlias` remain in `typing`. Both modules are unavailable on CircuitPython, so guard them together:

```python
try:
    from collections.abc import Callable
    from typing import Any, TypeAlias
except ImportError:
    pass  # Not available on CircuitPython
```

**Module count matters.** Import cost is paid at startup on-device. Keep related logic in the same file rather than splitting into many small modules when startup latency is a concern.

**Unavailable on CircuitPython / MicroPython:**

- `collections.defaultdict`, `functools`, `itertools`
- `dataclasses`
- Type annotations at runtime (use `try/except` guards)
- Large standard library modules

Prefer explicit, simple data structures (`list`, `dict`, plain classes with `__slots__`) over convenience wrappers.

## Type Hint Policy

Type hints are required for all function and method parameters and return values.

Use narrowly-scoped exceptions only when a concrete embedded/runtime constraint makes precise typing impractical, for example:

- Board/runtime-provided objects that have incomplete or incorrect stubs
- CircuitPython-specific APIs where stub types conflict with known runtime behavior
- Dynamic callback/plugin-style call sites where strict callable signatures are not representable without harming portability

When using an exception, still annotate with the best available fallback type and add a brief code comment explaining why a precise type is not possible in that location.

For board-provided attributes and pin objects (for example `board.TX`, `board.RX`) where stubs may be incomplete, prefer leaving diagnostics visible instead of adding inline `# pyright: ignore[...]` comments.
Only suppress these diagnostics when explicitly requested by the user or required by project policy.

## Class-Level Constants

Annotate all class-level constants with `Final` to prevent accidental reassignment. Omit the type parameter — Pylance infers it from the assigned value:

```python
try:
    from typing import Final
except ImportError:
    pass

class MyConfig:
    MAX_PIXELS: "Final" = 117
    DEFAULT_BRIGHTNESS: "Final" = 0x33
```

`Final` is part of the standard `typing` module and is respected by Pylance, mypy, and Pyrefly. The annotation must be in a string so it is never evaluated at runtime on CircuitPython.

## State Object Lifecycle

Initialize state once and mutate in place on every subsequent frame. Use a guard to distinguish first-run from update:

```python
def update(self, state, timer):
    if state is None:
        state = _Data(self.buffer_count)  # allocate once
    # mutate in place — no allocation
    state.phase = (state.phase + 1) % self.period
    return state
```

## `__slots__` for State Objects

Use `__slots__` on objects that are created per-instance and live for the duration of the animation. This lowers per-instance memory and speeds attribute access:

```python
class _Data:
    __slots__ = ("offset", "buffer", "phase")

    def __init__(self, buffer_count: int):
        self.offset = 0.0
        self.buffer = [0.0] * buffer_count
        self.phase = 0
```

## Checklist

- [ ] No list/dict/set allocation inside hot-path loops
- [ ] No comprehensions in hot paths — plain `for` loops only
- [ ] No exceptions used for control flow
- [ ] Constants and math calls hoisted outside inner loops
- [ ] State objects initialized once via a guard, mutated in place on subsequent frames
- [ ] `__slots__` used on long-lived per-instance state objects
- [ ] All function/method parameters and return types are annotated (except documented edge cases)
- [ ] All `typing` imports guarded with `try/except ImportError`
- [ ] Class-level constants annotated with `"Final"` (string form, no type parameter)
- [ ] No imports from unavailable stdlib modules
