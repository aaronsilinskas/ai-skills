---
name: bdd
description: >
  Write, implement, and review tests with a behavior-driven philosophy:
  red-green-refactor via vertical slices, held to a naming/structure/coverage
  quality bar. Use when building features or fixing bugs test-first, doing
  TDD/BDD, mentioning "red-green-refactor", writing new tests, auditing an
  existing test suite, naming test functions, planning coverage, or asking
  whether a test (or the whole suite) is any good — even if the user just
  says "add tests" or "check my tests."
argument-hint: "feature, module, or behavior to test"
---

# Behavior-Driven Development

## Core Philosophy

Tests document **why the code exists and what it guarantees** — not how it is
implemented. Good tests are integration-style: they exercise real code
through public interfaces and read like a specification ("user can checkout
with valid cart" tells you exactly what capability exists). They survive
refactors because they don't care about internal structure.

A test that breaks when you refactor internals — but the product behavior
didn't change — is a bad test. A test that passes when the product behavior
is broken is a worse test. Warning signs of the former: mocking internal
collaborators, testing private methods, asserting on call counts/order, or
verifying through means other than the public interface (e.g. querying a
database directly instead of calling the read API).

**Tautological tests** are a distinct failure mode: the expected value is
computed the same way the code computes it, so the test passes by
construction and can never disagree with the code — break the code wrong and
the assertion breaks wrong with it.

```python
# BAD: expected value recomputed the way the code computes it
def test_calculate_total_sums_line_items():
    items = [LineItem(price=10), LineItem(price=5)]
    expected = sum(item.price for item in items)
    assert calculate_total(items) == expected

# GOOD: expected value is an independent literal
def test_calculate_total_sums_line_items():
    assert calculate_total([LineItem(price=10), LineItem(price=5)]) == 15
```

The expected value must come from an independent source of truth — a
known-good literal, a worked example, the spec — never a recomputation of the
implementation.

Tests are also the *preferred home for behavior that would otherwise be
explained in a comment or docstring*. If a piece of source code is complex or
non-obvious enough that someone wants to narrate it in prose, capture that
behavior as a named test that asserts it instead — it documents the contract
executably and fails when it regresses. Treat each "this handles …" comment
in source as a missing test: name it and assert it (e.g.
`test_<thing>_when_<condition>_…`).

Ask before writing any test: **"What user-visible or system-level guarantee
does this verify?"**

## Anti-Pattern: Horizontal Slices

**Do not write all tests first, then all implementation.** Treating RED as
"write all tests" and GREEN as "write all code" produces:

- Tests written in bulk that test _imagined_ behavior, not _actual_ behavior
- Tests of the _shape_ of things (data structures, signatures) rather than
  user-facing behavior
- Tests insensitive to real changes — they pass when behavior breaks, fail
  when behavior is fine
- Test structure committed to before the implementation is understood

**Correct approach**: vertical slices via tracer bullets. One test → one
implementation → repeat. Each test responds to what you learned from the
previous cycle.

```
WRONG (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5

RIGHT (vertical):
  RED→GREEN: test1→impl1
  RED→GREEN: test2→impl2
  RED→GREEN: test3→impl3
  ...
```

## Process

### 1. Planning

When exploring the codebase, read `CONTEXT.md` (if it exists) so test names
and interface vocabulary match the project's domain language, and respect
ADRs in the area you're touching.

Before writing any code:

- [ ] Confirm with the user what interface changes are needed
- [ ] Confirm with the user which behaviors to test (prioritize)
- [ ] Identify opportunities for deep modules (small interface, deep
      implementation) — run the `codebase-design` skill for vocabulary and
      testability checks
- [ ] List the behaviors to test (not implementation steps)
- [ ] Get user approval on the plan

**You can't test everything.** Confirm with the user exactly which behaviors
matter most. Focus effort on critical paths and complex logic, not every
possible edge case.

### 2. Tracer Bullet

Write ONE test that confirms ONE thing about the system:

```
RED:   Write test for first behavior → test fails
GREEN: Write minimal code to pass → test passes
```

This proves the path works end-to-end.

### 3. Incremental Loop

For each remaining behavior:

```
RED:   Write next test → fails
GREEN: Minimal code to pass → passes
```

Rules:

- One test at a time
- Only enough code to pass the current test
- Don't anticipate future tests
- Keep tests focused on observable behavior

### 4. Refactor

After all tests pass, look for [refactor candidates](refactoring.md):

- [ ] Extract duplication
- [ ] Deepen modules (move complexity behind simple interfaces)
- [ ] Apply SOLID principles where natural
- [ ] Consider what new code reveals about existing code
- [ ] Run tests after each refactor step

**Never refactor while RED.** Get to GREEN first.

## Quality Bar

Everything below applies whether you just wrote the test (Process, above) or
are reviewing someone else's — the bar doesn't move based on who's holding
the pen.

### Test Naming

Test names are the primary communication surface. They should read like a
statement of guaranteed behavior.

**Format:** `test_<subject>_<condition_or_scenario>` or
`test_<what_is_guaranteed>`

**Goal:** A failing test name alone should tell you what broke — not just
which line.

#### Good names

```python
# Explains the guarantee and why it matters
def test_palette_wraps_position_so_out_of_range_values_still_render():
def test_effect_value_clamps_to_zero_when_level_is_below_threshold():
def test_renderer_produces_consistent_color_for_same_position():
def test_timer_accumulates_delta_across_multiple_updates():
def test_fire_step_produces_higher_intensity_at_base():
```

#### Bad names — avoid these

```python
# Mirrors code structure, doesn't say what's guaranteed
def test_get_value():
def test_palette_lut():
def test_update_returns_none():
def test_effect_calls_step():

# Over-specific to implementation details
def test_list_index_0_is_255():
def test_loop_iterates_16_times():
```

#### Name anti-patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| `test_<method_name>` | Tests the implementation, not behavior | Name the behavior the method enables |
| `test_<class>_works` | Vacuous — everything "works" until it doesn't | State exactly what works and under what condition |
| `test_<thing>_returns_<type>` | A type check, not a behavior check | Test the value contract, not the type |
| `test_<step>_step` | Just echoes code structure | Describe what the step produces |

#### The name must match what the test actually does

A name that overstates the test lies about coverage. Check the name against
the inputs fired and the assertions made — they must agree.

```python
# Name claims "near zero" — but fires exactly zero
def test_near_zero_axis_yields_near_zero_progress():
    fire(x=0.0)

# Fix: rename to the boundary it actually guards
def test_zero_acceleration_yields_zero_progress():
    fire(x=0.0)
```

If the name says "X causes Y", the test must change X and observe Y.

### Test Structure

#### One behavior per test

Each test should verify exactly one behavioral guarantee. If a test has
multiple unrelated `assert` statements, split it.

```python
# Too broad — two unrelated guarantees
def test_renderer():
    ...
    assert color == 0xFF0000
    assert "demo" in renderer.name

# Better — focused guarantees
def test_renderer_produces_packed_color_for_valid_input():
    ...
    assert color == 0xFF0000

def test_renderer_exposes_effect_name():
    ...
    assert renderer.name == "demo"
```

#### Arrange / Act / Assert

Use a clear three-section layout with a blank line between each section. Do
not add comments labeling the sections — the structure should be evident.

```python
def test_timer_accumulates_delta_across_multiple_updates():
    timer = EffectTimer()

    timer.update(0.1)
    timer.update(0.05)

    assert timer.elapsed == pytest.approx(0.15)
```

#### Avoid testing private internals

Test through the public API. Internal state is only worth asserting when the
product relies on it being observable (e.g., state shared between update and
render). The same rule applies to bypassing the interface entirely — reaching
around it to verify through some other means is just a different flavor of
coupling to implementation:

```python
# BAD: bypasses the interface to verify
def test_create_user_saves_to_database():
    create_user(name="Alice")
    row = db.query("SELECT * FROM users WHERE name = ?", ["Alice"])
    assert row is not None

# GOOD: verifies through the interface
def test_create_user_makes_user_retrievable():
    user = create_user(name="Alice")
    retrieved = get_user(user.id)
    assert retrieved.name == "Alice"
```

### Planning Coverage

Coverage should trace back to product guarantees, not code paths. Code that
is not covered by tests should be considered for removal or refactoring, not
for adding tests that just execute it.

#### Coverage checklist for any feature

- [ ] **Happy path:** Does it produce the correct result for normal inputs?
- [ ] **Boundary values:** What happens at zero, max, min, empty?
- [ ] **Invalid or unexpected inputs:** Does it fail safely or clamp
      gracefully?
- [ ] **Idempotence:** Calling it twice — same result? Or does state
      accumulate correctly?
- [ ] **Isolation:** Does it behave correctly in isolation (no hidden
      dependencies on ordering)?
- [ ] **Reset / restart behavior:** Does re-initialization give a clean
      slate?

#### Identifying product-focused edge cases

Ask: *What behavior would a user (or caller) actually notice if broken?*

- Output range violations (e.g., color channel > 255, position out of
  bounds)
- State corruption after repeated calls
- Delta-time edge cases (zero delta, very large spike)
- Empty or degenerate inputs (empty palette, zero-length strip)
- Interaction between two features used together (e.g., scale + sparkle
  applied to same effect)

Avoid manufacturing edge cases that can't occur in a real call sequence.

### What to Avoid

- **Do not write tests that just exercise a code path.** If deleting the
  test would have zero impact on catching real bugs, it doesn't need to
  exist.
- **Do not assert return type when the value itself can be asserted.**
  `assert color == 0xFF0000` is more useful than `assert isinstance(color,
  int)`.
- **Do not test framework or library behavior.** The standard library's own
  correctness is not your job to verify.
- **Do not construct tests purely to achieve line coverage.** Coverage is a
  byproduct of good behavioral tests, not a goal in itself.

### Examples

#### Reviewing an existing test

Given:

```python
def test_effect_renderer_returns_rgb_int() -> None:
    ...
    assert isinstance(color, int)
    assert color == 0xFF0000
```

Issues:
- Name says `returns_rgb_int` — the type check is noise if the value is
  already asserted
- Two assertions; the first is redundant
- Name doesn't explain *why* 0xFF0000 — what palette/position was expected
  to produce red?

Improved:

```python
def test_renderer_returns_full_red_at_max_value_with_two_stop_palette():
    effect = Effect("demo", lambda _: 1.0)
    palette = PaletteLUT256(bytes([0, 0, 0, 0, 255, 255, 0, 0]))  # black → red gradient
    renderer = EffectRenderer(effect, palette)
    ...
    assert color == 0xFF0000
```

#### Writing new tests

When asked to write tests for a module or feature:

1. Read the public API and identify the behavioral guarantees it makes.
2. List the happy-path cases, boundary values, and real-world edge cases
   separately.
3. Write one test per guarantee with a descriptive name.
4. Only assert what the test name claims — no bonus assertions.

## Mocking

Mock at **system boundaries** only:

- External APIs (payment, email, etc.)
- Databases (sometimes — prefer a real test database)
- Time/randomness
- File system (sometimes)

Don't mock your own classes/modules, internal collaborators, or anything you
control.

### Designing for mockability

At system boundaries, design interfaces that are easy to mock:

1. **Use dependency injection** — pass external dependencies in rather than
   constructing them internally.
2. **Prefer one function/method per external operation** over one generic
   call with conditional branching, so each seam is independently mockable,
   each mock returns exactly one shape, and it's obvious from the test setup
   which endpoints a test exercises.

The mechanics of mocking (patch locations, hoisting, relaxed-mock defaults)
are language-specific enough to trip people up even when the design
principle above is followed correctly. See:

- [mocking-python.md](mocking-python.md)
- [mocking-typescript.md](mocking-typescript.md)
- [mocking-kotlin.md](mocking-kotlin.md)

(For source-side quality guidance that pairs with these tests, see the
`code-quality` skill; it loads the matching platform reference for
hardware-constrained code.)

## Checklist Per Cycle

```
[ ] Test describes behavior, not implementation
[ ] Test uses public interface only
[ ] Test would survive internal refactor
[ ] Expected values are independent literals, not recomputed from the code
[ ] Test name matches the inputs fired and the assertions made
[ ] Code is minimal for this test
[ ] No speculative features added
```
