# Planning coverage

Plan the tests for a module or feature before they exist:

1. Read the public API and identify the behavioral guarantees it makes.
2. List the happy-path cases, boundary values and real-world edge cases separately, using the checklist and edge cases below.
3. Plan one test per guarantee, each with a name that states it.
4. Each test asserts only what its name claims. No bonus assertions.

## Coverage checklist for any feature

- [ ] **Happy path:** does it produce the correct result for normal inputs?
- [ ] **Boundary values:** what happens at zero, max, min, empty?
- [ ] **Invalid or unexpected inputs:** does it fail safely or clamp gracefully?
- [ ] **Idempotence:** calling it twice, same result? Or does state accumulate correctly?
- [ ] **Isolation:** does it behave correctly in isolation, with no hidden dependency on ordering?
- [ ] **Reset / restart behavior:** does re-initialization give a clean slate?

## Product-focused edge cases

Ask: *what behavior would a user (or caller) actually notice if broken?*

- Output range violations (e.g. a color channel above 255, a position out of bounds)
- State corruption after repeated calls
- Delta-time edge cases (zero delta, a very large spike)
- Empty or degenerate inputs (empty palette, zero-length strip)
- Two features used together (e.g. scale and sparkle applied to the same effect)

Plan only edge cases that a real call sequence can reach.
