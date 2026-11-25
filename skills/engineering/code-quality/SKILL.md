---
name: code-quality
description: "Quality bar for production source: readability, right-sized optimization, public-API discipline, type coverage. Use to review a file or function against this bar; code-review owns reviewing a branch's diff against standards and spec."
argument-hint: "file or function to review"
---

# Code Quality

The quality bar for implementation code. Tests have `test-quality`, comments have `comments-backpressure`, and module shape has `codebase-design`.

The project's own standards files (`CODING_STANDARDS.md`, `CONTRIBUTING.md`, `AGENTS.md` or `CLAUDE.md`), `GLOSSARY.md` and the ADRs touching the area extend this bar and override it on any conflict, notably on target runtime versions, listed hot paths and naming. Read any you haven't already.

## Guiding Principle

Readability is the default. Apply performance discipline only where a real constraint demands it, such as hot paths, inner loops, and constrained hardware. Everywhere else, never trade clarity for micro-optimizations that don't demonstrably matter.

## Use the Public API

Do not reach into another module's private state (names conventionally marked private, e.g. a leading underscore in Python) to make code or a demo work. Use only the public interface. If the public interface is insufficient, expand it deliberately rather than reaching around it. A missing public affordance is a design signal, not something to bypass.

## Type Coverage

Type hints (or the language's equivalent) are required for all function and method parameters and return values. Use narrowly-scoped exceptions only when a concrete constraint makes precise typing impractical, and even then annotate with the best available fallback and note *why* precise typing isn't possible at that location.

## Embedded Targets

The guidance above is general. Call the Skill tool with "embedded-python" when the target is embedded: CircuitPython, MicroPython, or a hot path on constrained hardware, even when the user doesn't name the platform.

## Checklist

- [ ] The project's standards files, glossary and relevant ADRs read and applied
- [ ] Readability preserved; optimizations confined to where a real constraint demands them
- [ ] No reaching into another module's private state. Only the public interface is used, or a deliberate interface expansion.
- [ ] All function/method parameters and return types annotated (except documented, justified edge cases)
- [ ] `embedded-python` applied when the target is embedded
