# Mocking in TypeScript

## `jest.mock` factories are hoisted

`jest.mock(...)` calls are hoisted above imports by Babel/ts-jest, before any
local variables are initialized. Referencing a plain local variable inside
the factory throws `ReferenceError: Cannot access '...' before
initialization`. Jest only exempts variable names prefixed with `mock`.
Reach for `jest.doMock` (not hoisted) if you need a factory that closes over
an arbitrary local.

```typescript
// WRONG: hoisting means `client` doesn't exist yet when the factory runs
const client = { charge: jest.fn() };
jest.mock("./stripe-client", () => ({ StripeClient: () => client }));

// RIGHT: name must start with `mock` to survive hoisting
const mockClient = { charge: jest.fn() };
jest.mock("./stripe-client", () => ({ StripeClient: () => mockClient }));
```
