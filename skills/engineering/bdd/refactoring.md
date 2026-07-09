# Refactor Candidates

The *local, under-green* cleanup done inside the red→green→refactor loop, with
the tests fresh and green. This is the cheap subset; the whole-diff structural
smell pass (shotgun surgery, divergent change, speculative generality) lives in
the `code-review` skill (`code-review/smells.md`).

After a TDD cycle, look for:

- **Duplication** → Extract function/class
- **Long methods** → Break into private helpers (keep tests on public interface)
- **Shallow modules** → Combine or deepen
- **Feature envy** → Move logic to where data lives
- **Primitive obsession** → Introduce value objects
- **SOLID violations** → Apply the relevant principle where it reads naturally
- **Existing code** the new code reveals as problematic
