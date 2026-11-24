---
name: code-quality
description: "Quality bar for production source: readability, right-sized optimization, public-API discipline, type coverage. Use when writing or reviewing implementation code, or as an implementation review pass."
argument-hint: "file or function to review or implement"
---

# Code Quality

The quality bar for implementation code. Tests have `test-quality`, comments have `comments-backpressure`, and module shape has `codebase-design`.

The project's own standards files (`CODING_STANDARDS.md`, `CONTRIBUTING.md`, `AGENTS.md` or `CLAUDE.md`), `GLOSSARY.md` and the ADRs touching the area extend this bar and override it on any conflict, notably on target runtime versions, listed hot paths and naming. Read any you haven't already.

## Guiding Principle

Readability is the default. Apply performance discipline only where a real constraint demands it, such as hot paths, inner loops, and constrained hardware (see the platform reference files). Everywhere else, never trade clarity for micro-optimizations that don't demonstrably matter.

## Use the Public API

Do not reach into another module's private state (names conventionally marked private, e.g. a leading underscore in Python) to make code or a demo work. Use only the public interface. If the public interface is insufficient, expand it deliberately rather than reaching around it. A missing public affordance is a design signal, not something to bypass.

## Type Coverage

Type hints (or the language's equivalent) are required for all function and method parameters and return values. Use narrowly-scoped exceptions only when a concrete constraint makes precise typing impractical, and even then annotate with the best available fallback and note *why* precise typing isn't possible at that location. Platform-specific typing exceptions (e.g. incomplete hardware stubs) live in the reference files.

## Platform- and Language-Specific Rules

The guidance above is general. Load the matching reference file when the target applies:

- CircuitPython / MicroPython, or any hot path on constrained hardware (animation loops, per-frame updates, per-pixel sampling), even when the user doesn't name the platform: [embedded-python.md](embedded-python.md)

## Checklist

- [ ] The project's standards files, glossary and relevant ADRs read and applied
- [ ] Readability preserved; optimizations confined to where a real constraint demands them
- [ ] No reaching into another module's private state. Only the public interface is used, or a deliberate interface expansion.
- [ ] All function/method parameters and return types annotated (except documented, justified edge cases)
- [ ] Any applicable platform reference file (e.g. `embedded-python.md`) has been applied
