# TypeScript TSDoc

## The types carry the shapes

Leave parameter and return shapes to the type annotations: no `@param {type}` JSDoc types. Add a `@param` or `@throws` tag only for meaning the type can't express.

```typescript
/**
 * @param context - label prefixed to each error message
 * @throws if a key is blank or two bands overlap
 */
function validateBandMap(bands: Map<string, Range>, context: string): void { ... }
```

## Summary first

The first paragraph is the summary shown in tooling hovers: one sentence, before any `@remarks` or `@example` block.

## Symbol references

Use `{@link Name}` to reference another symbol so it resolves to a link in generated docs. Use `` `code` `` for inline literals.
