---
name: test-quality
description: "Quality bar for tests: names that state the guarantee, one behavior per test, coverage traced to guarantees. Use when reviewing or naming tests, or planning a feature's coverage; tdd owns the loop."
argument-hint: "test file, suite, or feature to review"
---

# Test Quality

The quality bar for tests. Run it as its own pass over existing tests, or over a coverage plan before the tests exist. The bar is the same whoever wrote the tests.

This bar assumes the test anti-patterns in the `tdd` skill (implementation-coupled, tautological): a test that fails them fails this bar too.

Ask of every test: **"What user-visible or system-level guarantee does this verify?"**

## Test naming

Test names are the primary communication surface. They should read like a statement of guaranteed behavior.

**Format:** `test_<subject>_<condition_or_scenario>` or `test_<what_is_guaranteed>`

**Goal:** a failing test's name alone should tell you what broke, not just which line. Use the domain terms from the project's `GLOSSARY.md` when it has one.

A source comment that states behavior is a missing test: the **test** bucket of `comments-backpressure` turns it into one, named by this **Test naming** section.

### Good names

```python
# Explains the guarantee and why it matters
def test_palette_wraps_position_so_out_of_range_values_still_render():
def test_effect_value_clamps_to_zero_when_level_is_below_threshold():
def test_renderer_produces_consistent_color_for_same_position():
def test_timer_accumulates_delta_across_multiple_updates():
def test_fire_step_produces_higher_intensity_at_base():
```

### Name anti-patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| `test_<method_name>` | Tests the implementation, not behavior | Name the behavior the method enables |
| `test_<class>_works` | Vacuous: everything "works" until it doesn't | State exactly what works and under what condition |
| `test_<thing>_returns_<type>` | A type check, not a behavior check | Test the value contract, not the type |
| `test_<step>_step` | Just echoes code structure | Describe what the step produces |
| `test_list_index_0_is_255` | Pins an implementation detail | State the observable result that detail produces |

### The name must match what the test actually does

A name that overstates the test lies about coverage. Check the name against the inputs fired and the assertions made. They must agree.

```python
# Name claims "near zero", but fires exactly zero
def test_near_zero_axis_yields_near_zero_progress():
    fire(x=0.0)

# Fix: rename to the boundary it actually guards
def test_zero_acceleration_yields_zero_progress():
    fire(x=0.0)
```

If the name says "X causes Y", the test must change X and observe Y.

## Test structure

### One behavior per test

Each test verifies exactly one behavioral guarantee. If a test has several unrelated assertions, split it.

```python
# Too broad: two unrelated guarantees
def test_renderer():
    ...
    assert color == 0xFF0000
    assert "demo" in renderer.name

# Better: focused guarantees
def test_renderer_produces_packed_color_for_valid_input():
    ...
    assert color == 0xFF0000

def test_renderer_exposes_effect_name():
    ...
    assert renderer.name == "demo"
```

### Arrange / Act / Assert

Use a clear three-section layout with a blank line between each section. Don't add comments labelling the sections. The structure should be evident.

```python
def test_timer_accumulates_delta_across_multiple_updates():
    timer = EffectTimer()

    timer.update(0.1)
    timer.update(0.05)

    assert timer.elapsed == pytest.approx(0.15)
```

### Assert through the public interface

Internal state is only worth asserting when the product relies on it being observable (e.g. state shared between update and render). Isolate that access in one dedicated helper rather than scattering it. Anything else that reaches past the interface is `tdd`'s implementation-coupled anti-pattern.

## Planning coverage

Coverage traces back to product guarantees, not code paths. Code that no behavioral test covers is a candidate for removal or refactoring, not for a test that just executes it.

When planning tests before they exist, or auditing a suite for coverage gaps, read [planning-coverage.md](planning-coverage.md).

## What to avoid

- **Tests that just exercise a code path.** If deleting the test would have zero impact on catching real bugs, it doesn't need to exist.
- **Asserting the return type when the value itself can be asserted.** `assert color == 0xFF0000` is more useful than `assert isinstance(color, int)`.
- **Testing framework or library behavior.** The standard library's own correctness is not your job to verify.
- **Tests built purely for line coverage.** Coverage is a byproduct of good behavioral tests, not a goal in itself.

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

- The name says `returns_rgb_int`, but the type check is noise once the value is asserted.
- Two assertions, and the first is redundant.
- The name doesn't explain *why* 0xFF0000. What palette and position were expected to produce red?

Improved:

```python
def test_renderer_returns_full_red_at_max_value_with_two_stop_palette():
    effect = Effect("demo", lambda _: 1.0)
    palette = PaletteLUT256(bytes([0, 0, 0, 0, 255, 255, 0, 0]))  # black → red gradient
    renderer = EffectRenderer(effect, palette)
    ...
    assert color == 0xFF0000
```

## Mocking

The rule (mock at system boundaries only, never your own modules) lives in `tdd`. What this skill adds is the per-language mechanics, which trip people up even when the rule is followed. Load only the file for the language under review:

- Python: [mocking-python.md](mocking-python.md)
- TypeScript: [mocking-typescript.md](mocking-typescript.md)
- Kotlin: [mocking-kotlin.md](mocking-kotlin.md)

A test that is hard to mock usually points at the source, not the test. Report the fix as a design finding rather than working around it in the test: `codebase-design`'s designing for testability covers taking dependencies in, and `tdd`'s mocking reference covers one function per external operation.

## Checklist

- [ ] Each test name states a guarantee, and matches the inputs fired and the assertions made
- [ ] One behavior per test, laid out as Arrange / Act / Assert without section comments
- [ ] Assertions go through the public interface, with expected values from an independent source (see `tdd`'s anti-patterns)
- [ ] Coverage traces to product guarantees, not code paths
- [ ] No test exists only to execute a code path, check a type, or test a library
- [ ] Mocks sit at system boundaries, and the matching language guide's gotchas are avoided
