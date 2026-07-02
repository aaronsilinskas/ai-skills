---
name: code-quality
description: >
  Review and guide implementation code against a general quality bar:
  readability, right-sized optimization, public-API discipline, and type
  coverage. Use when writing or reviewing production source (not tests — that's
  the `bdd` skill; not comments — that's the `comments` skill), when asked
  whether an implementation is clean/safe/well-shaped, or as an implementation
  review pass. Language-agnostic; platform- and language-specific rules load
  from the reference files only when relevant.
argument-hint: "file or function to review or implement"
---

# Code Quality

The general quality bar for implementation code. Three neighbouring dimensions
have their own skills — reach for them rather than duplicating their guidance
here:

- **Tests** — writing code test-first and the test quality bar: `bdd`
- **Comments & docstrings** — whether and how to document: `comments`
- **Module shape** — interfaces, seams, deep modules: `codebase-design`

This skill covers what's left: the readability and correctness bar for the
implementation itself.

## Project-Specific Rules

Before applying any guidance from this skill, find the project's authoritative
conventions and constraints. Check `AGENTS.md` and `CLAUDE.md` at the project
root, and any agent-facing docs they point to (commonly `docs/agents/domain.md`
or similar) for sections listing code conventions, coding constraints, or
runtime/hardware limits — the heading wording varies by project. Treat those
sections as authoritative: they extend and, on any conflict, override the
general guidance below, in particular target runtime versions, listed hot
paths, and project-level conventions.

## Guiding Principle

Readability is the default. Apply performance discipline only where a real
constraint demands it (hot paths, inner loops, constrained hardware — see the
platform reference files); everywhere else, never trade clarity for
micro-optimizations that don't demonstrably matter.

## Use the Public API

Do not reach into another module's private state (names conventionally marked
private — e.g. a leading underscore in Python) to make code or a demo work.
Use only the public interface. If the public interface is insufficient, expand
it deliberately rather than reaching around it — a missing public affordance is
a design signal, not something to bypass.

The one exception is a test that is explicitly exercising internal behaviour
(e.g. asserting a private field after calling a public method); even then,
isolate the access to a dedicated helper rather than scattering it.

This is the implementation-side consequence of treating the interface as the
test surface — see `codebase-design` for the design rationale (deep modules,
seams), and `bdd` for the testing side (avoid testing private internals).

## Comments

Comment discipline — the "naming → test → comment" ordering, and never writing
prose that restates what the code already says — is covered by the `comments`
skill. Apply it to all changed source.

## Type Coverage

Type hints (or the language's equivalent) are required for all function and
method parameters and return values. Use narrowly-scoped exceptions only when a
concrete constraint makes precise typing impractical, and even then annotate
with the best available fallback and note *why* precise typing isn't possible
at that location. Platform-specific typing exceptions (e.g. incomplete
hardware stubs) live in the reference files.

## Platform- and Language-Specific Rules

The guidance above is general. Load the matching reference file when the target
applies:

- CircuitPython / MicroPython (constrained hardware) —
  [embedded-python.md](embedded-python.md)

## Checklist

- [ ] Readability preserved; optimizations confined to where a real constraint
      demands them
- [ ] No reaching into another module's private state — public interface only
      (or a deliberate interface expansion), with the narrow test-helper
      exception isolated
- [ ] Comment discipline applied per the `comments` skill
- [ ] All function/method parameters and return types annotated (except
      documented, justified edge cases)
- [ ] Any applicable platform reference file (e.g. `embedded-python.md`) has
      been applied
