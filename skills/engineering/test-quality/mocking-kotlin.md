# Mocking in Kotlin

## Relaxed mocks hide missing stubs

`mockk<T>(relaxed = true)` returns default values (0, "", empty collections,
nulls) for any unstubbed call instead of failing. A test can pass because a
dependency silently returned a default, not because the behavior under test
is actually correct. Prefer strict mocks and stub only what the test needs,
so an unstubbed call fails loudly instead of returning a silent zero.

```kotlin
// Risky: relaxed mock returns 0 for unstubbed getTotal(), test can pass for the wrong reason
val cart = mockk<Cart>(relaxed = true)

// Safer: strict mock forces every used call to be stubbed explicitly
val cart = mockk<Cart>()
every { cart.getTotal() } returns 15
```
