# Kotlin KDoc

## Block tags

Add `@param`, `@return` or `@throws` only for meaning the signature can't express. Each entry documents only its own item, never the function's broader contract.

```kotlin
/**
 * @param context label prefixed to each error message
 * @throws IllegalArgumentException if a key is blank or two bands overlap
 */
fun validateBandMap(bands: Map<String, IntRange>, context: String) { ... }
```

## Constructor properties

Document a primary-constructor property with `@property` on the class KDoc, once, rather than again on the property.

## Symbol references

Use `[Name]` to reference another class, function or property so it resolves to a link in generated docs. Use backticks for inline literals.
