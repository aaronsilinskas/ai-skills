---
name: as-test-dev
description: "Write, review, or restructure Python tests with a product-focused, behavior-driven philosophy. Use this skill whenever writing new tests, auditing existing ones, naming test functions, or planning coverage — even if the user just says 'add tests' or 'check my tests.' Also use when the user asks whether a test is good, what to test next, or whether their test suite is missing something. Covers naming conventions, test structure, and distinguishing behavior-driven tests from code-path-mirroring tests."
argument-hint: "feature, module, or behavior to test"
---

# Test Dev

## Core Philosophy

Tests document **why the code exists and what it guarantees**, not how it is implemented.

A test that breaks when you refactor internals — but the product behavior didn't change — is a bad test. A test that passes when the product behavior is broken is a worse test.

Ask before writing any test: **"What user-visible or system-level guarantee does this verify?"**

## Test Naming

Test names are the primary communication surface. They should read like a statement of guaranteed behavior.

**Format:** `test_<subject>_<condition_or_scenario>` or `test_<what_is_guaranteed>`

**Goal:** A failing test name alone should tell you what broke — not just which line.

### Good names

```python
# Explains the guarantee and why it matters
def test_palette_wraps_position_so_out_of_range_values_still_render():
def test_effect_value_clamps_to_zero_when_level_is_below_threshold():
def test_renderer_produces_consistent_color_for_same_position():
def test_timer_accumulates_delta_across_multiple_updates():
def test_fire_step_produces_higher_intensity_at_base():
```

### Bad names — avoid these

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

### Name anti-patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| `test_<method_name>` | Tests the implementation, not behavior | Name the behavior the method enables |
| `test_<class>_works` | Vacuous — everything "works" until it doesn't | State exactly what works and under what condition |
| `test_<thing>_returns_<type>` | A type check, not a behavior check | Test the value contract, not the type |
| `test_<step>_step` | Just echoes code structure | Describe what the step produces |

## Test Structure

### One behavior per test

Each test should verify exactly one behavioral guarantee. If a test has multiple unrelated `assert` statements, split it.

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

### Arrange / Act / Assert

Use a clear three-section layout with a blank line between each section. Do not add comments labeling the sections — the structure should be evident.

```python
def test_timer_accumulates_delta_across_multiple_updates():
    timer = EffectTimer()

    timer.update(0.1)
    timer.update(0.05)

    assert timer.elapsed == pytest.approx(0.15)
```

### Avoid testing private internals

Test through the public API. Internal state is only worth asserting when the product relies on it being observable (e.g., state shared between update and render).

## Planning Coverage

Coverage should trace back to product guarantees, not code paths. Code that is not covered by
tests should be considered for removal or refactoring, not for adding tests that just execute it.

### Coverage checklist for any feature

- [ ] **Happy path:** Does it produce the correct result for normal inputs?
- [ ] **Boundary values:** What happens at zero, max, min, empty?
- [ ] **Invalid or unexpected inputs:** Does it fail safely or clamp gracefully?
- [ ] **Idempotence:** Calling it twice — same result? Or does state accumulate correctly?
- [ ] **Isolation:** Does it behave correctly in isolation (no hidden dependencies on ordering)?
- [ ] **Reset / restart behavior:** Does re-initialization give a clean slate?

### Identifying product-focused edge cases

Ask: *What behavior would a user (or caller) actually notice if broken?*

- Output range violations (e.g., color channel > 255, position out of bounds)
- State corruption after repeated calls
- Delta-time edge cases (zero delta, very large spike)
- Empty or degenerate inputs (empty palette, zero-length strip)
- Interaction between two features used together (e.g., scale + sparkle applied to same effect)

Avoid manufacturing edge cases that can't occur in a real call sequence.

## What to Avoid

- **Do not write tests that just exercise a code path.** If deleting the test would have zero impact on catching real bugs, it doesn't need to exist.
- **Do not assert return type when the value itself can be asserted.** `assert color == 0xFF0000` is more useful than `assert isinstance(color, int)`.
- **Do not test framework or library behavior.** Python's `dict`, `list`, and standard library correctness are not your job to verify.
- **Do not construct tests purely to achieve line coverage.** Coverage is a byproduct of good behavioral tests, not a goal in itself.

## Examples

### Reviewing an existing test

Given:

```python
def test_effect_renderer_returns_rgb_int() -> None:
    ...
    assert isinstance(color, int)
    assert color == 0xFF0000
```

Issues:
- Name says `returns_rgb_int` — the type check is noise if the value is already asserted
- Two assertions; the first is redundant
- Name doesn't explain *why* 0xFF0000 — what palette/position was expected to produce red?

Improved:

```python
def test_renderer_returns_full_red_at_max_value_with_two_stop_palette():
    effect = Effect("demo", lambda _: 1.0)
    palette = PaletteLUT256(bytes([0, 0, 0, 0, 255, 255, 0, 0]))  # black → red gradient
    renderer = EffectRenderer(effect, palette)
    ...
    assert color == 0xFF0000
```

### Writing new tests

When asked to write tests for a module or feature:

1. Read the public API and identify the behavioral guarantees it makes.
2. List the happy-path cases, boundary values, and real-world edge cases separately.
3. Write one test per guarantee with a descriptive name.
4. Only assert what the test name claims — no bonus assertions.
